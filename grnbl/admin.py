"""The admin board: `python3 -m grnbl.admin`, then open the link it prints.

Shows today's reviewed events with the AI's verdict, lets the human approve,
drop or rewrite each one, and previews the posts exactly as they will go out.
Decisions are kept in data/decisions/<day>.json; the AI never publishes alone.

The board can publish to WhatsApp, so it is reachable only with its key
(data/board-key, made on first start): the link `/?key=<key>` sets a cookie,
every page and API call checks it. The same rule holds behind a tunnel, on a
server or locally, with no dependency on the host.
"""

from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import sys
import threading
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from .digest import alerts_post, fuel_post, outings_post_reviewed, picked, title_of, to_book_post
from .editor import CHANNELS, candidates
from . import editorial
from . import publish, schedule, translate
from .sources import alerts, fuel

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PAGE = Path(__file__).with_name("admin.html")
PARIS = ZoneInfo("Europe/Paris")

# The board speaks English (the posts stay French); WhatsApp group names stay as they are.
LABELS = {"gratuit": "🆓 Free", "sorties": "🎭 Outings", "famille": "👨‍👩‍👧 Family", "bonsplans": "🛍️ Deals",
          "nature": "🏔️ Outdoors", "infos": "🚨 Alerts", "carburant": "⛽ Fuel"}


KEY_FILE = DATA / "board-key"
COOKIE = "grnbl_key"
MAX_BODY = 1_000_000  # a decision or a post's ticked lines: a few kilobytes at most


def board_key() -> str:
    if not KEY_FILE.exists():
        KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        KEY_FILE.write_text(secrets.token_urlsafe(32))
        KEY_FILE.chmod(0o600)
    return KEY_FILE.read_text().strip()


def day_folder(day: date) -> Path:
    return DATA / "events" / day.isoformat()


def load(day: date) -> dict:
    folder = day_folder(day)
    reviewed = folder / "reviewed.json"
    events = json.loads(reviewed.read_text()) if reviewed.exists() else []
    decisions_path = DATA / "decisions" / f"{day.isoformat()}.json"
    decisions = json.loads(decisions_path.read_text()) if decisions_path.exists() else {}
    selection_path = folder / "selection.json"
    picks = json.loads(selection_path.read_text()) if selection_path.exists() else []
    by_i = {p["i"]: {**p, "rank": rank} for rank, p in enumerate(picks)}
    for i, e in enumerate(events):
        e["i"] = i
        e["decision"] = decisions.get(str(i))
        e["pick"] = by_i.get(i)
    return {"day": day.isoformat(), "events": events, **run_state(day)}


def run_state(day: date) -> dict:
    """Where the day's run is, so the board says "preparing" instead of looking empty."""
    if (day_folder(day) / "selection.json").exists():
        return {"state": "ready"}
    log = DATA / "logs" / f"{day.isoformat()}.log"
    lines = log.read_text().splitlines() if log.exists() else []
    started = next((l[14:19] for l in lines if l.startswith("== ") and "morning run" in l), None)
    ended = [l for l in lines if l.startswith("== ") and "done, exit" in l]
    if ended and not ended[-1].endswith("exit 0"):
        return {"state": "failed", "log": f"data/logs/{day.isoformat()}.log"}
    if started and not ended:
        return {"state": "preparing", "since": started}
    return {"state": "none"}


def save_decision(day: date, i: int, decision: dict | None) -> None:
    path = DATA / "decisions" / f"{day.isoformat()}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    decisions = json.loads(path.read_text()) if path.exists() else {}
    if decision is None:
        decisions.pop(str(i), None)
    else:
        decisions[str(i)] = decision
    path.write_text(json.dumps(decisions, ensure_ascii=False, indent=1))


def _price(e: dict, free: bool) -> str:
    """A short price for the review line: agendas paste whole fare tables."""
    if free:
        return "free"
    raw = (e.get("price") or "").strip()
    if not raw or "non renseign" in raw.lower():
        return ""
    amounts = sorted({float(a.replace(",", ".")) for a in re.findall(r"(\d+(?:[.,]\d+)?)\s*€", raw)})
    fmt = lambda x: f"{x:g}".replace(".", ",")  # noqa: E731
    if amounts:
        return f"{fmt(amounts[0])} €" if len(amounts) == 1 else f"{fmt(amounts[0])}–{fmt(amounts[-1])} €"
    first = raw.splitlines()[0].rstrip(".")
    return first if len(first) <= 40 else first[:39] + "…"


def _row(e: dict, post: str, **extra) -> dict:
    d, r = e.get("decision") or {}, e.get("review") or {}
    free = (r.get("free") if r.get("free") is not None else e.get("free")) is True
    return {"i": e["i"], "post": post, "title": e["title"], "start": e.get("start"), "place": e.get("venue") or e.get("town") or "",
            "status": d.get("status"), "line": d.get("line") or r.get("line") or "", "score": r.get("score"), "free": free,
            "price": _price(e, free), "booking": e.get("booking"), "booking_opens": e.get("booking_opens"),
            "booking_deadline": e.get("booking_deadline"), "source": e.get("source_name") or "", "block": d.get("block"), **extra}


def parts(post: str, text: str, lists: dict) -> dict:
    """A post as the board edits it: the heading, then each line's block with the event it belongs to."""
    head, *blocks = text.split("\n\n")
    owner = {r["sent"]: r["i"] for r in lists.get(post, []) if r.get("sent")}
    return {"post": post, "head": head, "blocks": [{"i": owner.get(b.strip("\n")), "text": b.strip("\n")} for b in blocks]}


def attach_sent(lists: dict, texts: list[tuple[str, str]]) -> None:
    """Give each ticked row the exact block of the WhatsApp message it becomes, so the board reviews
    what is sent, not the editor's short line. A ticked row with no block is not in the message
    (to_book_post keeps 8 lines at most, or its timing changed): `sent` stays None and the board says so."""
    by_post = dict(texts)
    for post, rows in lists.items():
        blocks = [b.strip("\n") for b in (by_post.get(post) or "").split("\n\n")[1:]]  # the first block is the heading
        for row in rows:
            if row["on"] and row.get("block"):
                row["sent"] = row["block"] if row["block"] in blocks else None
            elif row["on"]:
                mark = f"*{title_of(row)}*"
                row["sent"] = next((b.strip("\n") for b in blocks if mark in b.split("\n", 1)[0]), None)


def choice_list(events: list[dict], sel: list[dict], live: dict, channel: str, today: date, n: int = 12) -> dict:
    """Per post, what the human can tick: the current lines first, then the editor's other picks and
    reserves, then the best other candidates of the channel. The current lines come ticked."""
    out = {}
    for post in ("to_book", "week"):
        fits = ("this_week",) if post == "week" else ("book_now", "opens_soon")
        editor = [p for p in sel if p["post"] == post and p["i"] < len(events)]
        why = {p["i"]: p.get("why") for p in editor}
        checks = {p["i"]: p.get("check") or [] for p in editor}
        mains = [p["i"] for p in editor if not p.get("reserve")]
        # Stable order: the editor's picks stay in place when unticked, the human's additions follow.
        order = mains + live.get(post, []) + [p["i"] for p in editor] + \
            [e["i"] for _, e in candidates(events, today, channel) if editorial.timing(e, today) in fits]
        seen, rows = set(), []
        for i in order:
            e = events[i]
            if i in seen or ((e.get("decision") or {}).get("status") == "drop" and i not in live.get(post, [])):
                continue
            seen.add(i)
            rows.append(_row(e, post, on=i in live.get(post, []), main=i in mains, editor=i in why, why=why.get(i) or "", check=checks.get(i, [])))
        out[post] = rows[:max(n, len(live.get(post, [])))]
    return out


def review_path(day: date) -> Path:
    return DATA / "decisions" / f"{day.isoformat()}-review.json"


def load_review(day: date) -> dict:
    """Where the card review stands beyond the decisions themselves, so a closed tab resumes in place:
    `pending` = replacement cards offered but not answered, `passed` = replacements turned down,
    `later` = lines set aside to check, `verdicts` = what was chosen for them, applied together at the end."""
    path = review_path(day)
    state = json.loads(path.read_text()) if path.exists() else {}
    return {"pending": state.get("pending") or [], "passed": state.get("passed") or [],
            "later": state.get("later") or [], "verdicts": state.get("verdicts") or {}}


def save_review(day: date, state: dict) -> None:
    def line(p):
        if p.get("channel") not in CHANNELS or p.get("post") not in ("to_book", "week"):
            raise ValueError("unknown channel or post")
        return {"channel": p["channel"], "post": p["post"], "i": int(p["i"]), "instead": str(p.get("instead") or "")}
    verdicts = {}
    for i, v in (state.get("verdicts") or {}).items():
        if v.get("v") in ("keep", "drop"):
            verdicts[str(int(i))] = {"v": v["v"], "block": v.get("block") if isinstance(v.get("block"), str) else None}
    clean = {"pending": [line(p) for p in state.get("pending") or []], "passed": sorted({int(i) for i in state.get("passed") or []}),
             "later": [line(p) for p in state.get("later") or []], "verdicts": verdicts}
    path = review_path(day)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=1))


# Posted every day for that day, outside the weekly editions.
DAILY = ("carburant", "infos")
_FUEL: dict = {}
_ALERTS: dict = {}


def _kept_fresh(cache: dict, now: datetime, compute) -> str | None:
    """The last text at once, refreshed in the background every ten minutes: reading fuel prices and
    weather can take many seconds, and the board must never wait on them to show the edition."""
    if not cache.get("busy") and (not cache or (now - cache["at"]).total_seconds() > 600):
        cache["busy"] = True

        def refresh():
            try:
                cache["text"] = compute(now)
            finally:
                cache.update(at=now, busy=False)
        threading.Thread(target=refresh, daemon=True).start()
    return cache.get("text")


def _fuel_text(now: datetime) -> str | None:
    try:
        return fuel_post(fuel.collect(), now)
    except Exception as e:  # noqa: BLE001 - the board still shows the outings
        return f"(fuel prices unavailable: {e})"


def fuel_cached(now: datetime) -> str | None:
    """The fuel post, fetched at most every ten minutes: the board refreshes posts after each decision."""
    return _kept_fresh(_FUEL, now, _fuel_text)


def alerts_cached(now: datetime) -> str | None:
    """The practical alerts post, fetched at most every ten minutes, like the fuel one.
    A source that cannot be read is left out: this text is what gets published."""
    return _kept_fresh(_ALERTS, now, lambda at: alerts_post(alerts.collect(at)[0], at))


class Handler(BaseHTTPRequestHandler):
    # None = follow the calendar: the board runs for days and must show today's run.
    pinned: date | None = None

    @property
    def day(self) -> date:
        return self.pinned or schedule.current_edition(datetime.now(PARIS).date())

    def _allowed(self) -> bool:
        """The key from the cookie, or from ?key= once (then kept in a cookie and dropped from the URL)."""
        key = board_key()
        cookies = dict(c.strip().split("=", 1) for c in (self.headers.get("Cookie") or "").split(";") if "=" in c)
        if hmac.compare_digest(cookies.get(COOKIE, ""), key):
            return True
        query = parse_qs(urlsplit(self.path).query).get("key", [""])[0]
        if query and hmac.compare_digest(query, key):
            self.send_response(303)
            self.send_header("Location", urlsplit(self.path).path or "/")
            secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" or self.headers.get("Cf-Visitor") else ""
            self.send_header("Set-Cookie", f"{COOKIE}={key}; Path=/; HttpOnly; SameSite=Strict; Max-Age=31536000{secure}")
            self.end_headers()
            return False
        self._send(403, "Board link required: open the link from the Discord message.".encode(), "text/plain; charset=utf-8")
        return False

    def _send(self, code: int, body: bytes, kind: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, code: int = 200) -> None:
        self._send(code, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def do_GET(self):
        if not self._allowed():
            return
        self.path = urlsplit(self.path).path
        if self.path == "/":
            return self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        if self.path == "/api/events":
            return self._json(load(self.day))
        if self.path == "/api/posts":
            now = datetime.now(PARIS)
            data = load(self.day)["events"]
            fuel_text = fuel_cached(now)
            sel_path = day_folder(self.day) / "selection.json"
            selection = json.loads(sel_path.read_text()) if sel_path.exists() else None
            watch_path = day_folder(self.day) / "watch.json"
            watch = json.loads(watch_path.read_text()) if watch_path.exists() else []
            channels, choices, editions = [], publish.load_choices(self.day), schedule.editions()
            english, stale = translate.load(self.day), False
            for cid, c in CHANNELS.items():
                sel = [p for p in selection or [] if p.get("channel", "sorties") == cid] if selection is not None else None
                mine = choices.get(cid, {})
                used = publish.in_their_group(data, publish.apply_choices(sel, {cid: mine})) if sel is not None else None
                at = publish.read_at(self.day, cid, now)
                live = {post: [e["i"] for e, _ in picked(data, used, post) or []] for post in ("to_book", "week")}
                texts = [(post, write(data, at, selection=used)) for post, write in publish.POSTS]
                texts = [(post, t) for post, t in texts if t]
                stale |= any(translate.needs(english.get(translate.key(cid, post)), t) for post, t in texts)
                lists = choice_list(data, sel, live, cid, now.date()) if sel is not None else {}
                attach_sent(lists, texts)
                channels.append({
                    "id": cid, "name": c["name"], "label": LABELS.get(cid, c["label"]),
                    "posts": [t for _, t in texts],
                    "parts": [parts(post, t, lists) for post, t in texts],
                    # English translation under each post, for the board only (translate.py).
                    "en": [translate.shown(english.get(translate.key(cid, post)), t) for post, t in texts],
                    # Only an edition is sent at its slot (tick.py); older daily runs are not scheduled.
                    "sends_at": at.isoformat(timespec="minutes") if self.day in editions else None,
                    "lists": lists,
                    "custom": {post: post in mine for post in ("to_book", "week")},
                })
            if stale:
                translate.refresh_later(self.day)  # in the background; the next refresh shows it
            alerts_text = alerts_cached(now)
            channels.append({"id": "infos", "name": "GRNBL · Annonces", "label": LABELS["infos"],
                             "posts": [alerts_text] if alerts_text else [], "picks": []})
            channels.append({"id": "carburant", "name": "grnbl · Carburant", "label": LABELS["carburant"], "posts": [fuel_text] if fuel_text else [], "picks": []})
            # Fuel and alerts are daily, filed under today; the groups under their edition.
            today = now.date()
            sent = {**publish.status(self.day), **{k: v for k, v in publish.status(today).items() if k in DAILY}}
            for c in channels:
                c["outbox"] = sent.get(c["id"], {})
            return self._json({"channels": channels, "watch": watch, "translating": translate.busy(), "review": load_review(self.day),
                               "auto_send": False})
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if not self._allowed():
            return
        if self.path not in ("/api/decide", "/api/publish", "/api/choose", "/api/review"):
            return self._send(404, b"not found", "text/plain")
        size = int(self.headers.get("Content-Length") or 0)
        if size > MAX_BODY:
            return self._send(413, b"too large", "text/plain")
        body = json.loads(self.rfile.read(size) or b"{}")
        if self.path == "/api/review":
            try:
                save_review(self.day, body)
            except (KeyError, TypeError, ValueError):
                return self._json({"ok": False}, 400)
            return self._json({"ok": True})
        if self.path == "/api/choose":
            # The ticked lines of one post, in order; null goes back to the editor's picks.
            ids = body.get("ids")
            ok = ids is None or (isinstance(ids, list) and all(isinstance(i, int) for i in ids))
            if not ok or body.get("channel") not in CHANNELS or body.get("post") not in ("to_book", "week"):
                return self._json({"ok": False}, 400)
            publish.save_choice(self.day, body["channel"], body["post"], ids)
            return self._json({"ok": True})
        if self.path == "/api/publish":
            # Sends the channel's approved posts that are not out yet; the outbox prevents doubles.
            channel = str(body.get("channel"))
            day = datetime.now(PARIS).date() if channel in DAILY else self.day
            report = publish.run(day, send=True, only=[channel])
            # Posted by hand from the board's Copy button: record it.
            report += [(name, "posté à la main") for name in publish.mark_posted(day, channel)]
            return self._json({"ok": True, "report": report, "failed": []})
        i = body.get("i")
        if not isinstance(i, int):
            return self._json({"ok": False}, 400)
        decision = body.get("decision")
        if decision is not None:
            decision = {"status": decision.get("status"), "line": decision.get("line")}
            block = (body.get("decision") or {}).get("block")
            if isinstance(block, str) and block.strip():
                decision["block"] = block.strip("\n")  # the line's whole block, edited in the preview
        save_decision(self.day, i, decision)
        self._json({"ok": True})

    def log_message(self, *args):  # quiet
        pass


def main(argv: list[str]) -> int:
    if argv:
        Handler.pinned = date.fromisoformat(argv[0])
    # Local by default; a host such as Deployxa sets GRNBL_HOST=0.0.0.0 and its own PORT.
    host, port = os.environ.get("GRNBL_HOST", "127.0.0.1"), int(os.environ.get("PORT", "8730"))
    server = ThreadingHTTPServer((host, port), Handler)
    key = board_key() if host == "127.0.0.1" else "…"  # keep the key out of a host's logs
    print(f"grnbl admin: http://{host}:{port}/?key={key}  ({Handler.pinned or 'today'})", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
