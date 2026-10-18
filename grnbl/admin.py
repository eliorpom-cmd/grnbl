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
import secrets
import sys
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from .digest import alerts_post, fuel_post, outings_post_reviewed, picked, to_book_post
from .editor import CHANNELS, candidates
from . import editorial
from . import publish, schedule
from .sources import alerts, fuel

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PAGE = Path(__file__).with_name("admin.html")
PARIS = ZoneInfo("Europe/Paris")


KEY_FILE = DATA / "board-key"
COOKIE = "grnbl_key"


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


def _row(e: dict, post: str, **extra) -> dict:
    d, r = e.get("decision") or {}, e.get("review") or {}
    return {"i": e["i"], "post": post, "title": e["title"], "start": e.get("start"), "place": e.get("venue") or e.get("town") or "",
            "status": d.get("status"), "line": d.get("line") or r.get("line") or "", "score": r.get("score"),
            "free": (r.get("free") if r.get("free") is not None else e.get("free")) is True, **extra}


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


# Posted every day for that day, outside the weekly editions.
DAILY = ("carburant", "infos")
_FUEL: dict = {}


def fuel_cached(now: datetime) -> str | None:
    """The fuel post, fetched at most every ten minutes: the board refreshes posts after each decision."""
    if not _FUEL or (now - _FUEL["at"]).total_seconds() > 600:
        try:
            text = fuel_post(fuel.collect(), now)
        except Exception as e:  # noqa: BLE001 - the board still shows the outings
            text = f"(carburant indisponible : {e})"
        _FUEL.update(at=now, text=text)
    return _FUEL["text"]


_ALERTS: dict = {}


def alerts_cached(now: datetime) -> str | None:
    """The practical alerts post, fetched at most every ten minutes, like the fuel one."""
    if not _ALERTS or (now - _ALERTS["at"]).total_seconds() > 600:
        # A source that cannot be read is left out: this text is what gets published.
        _ALERTS.update(at=now, text=alerts_post(alerts.collect(now)[0], now))
    return _ALERTS["text"]


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
        self._send(403, "Lien du tableau requis : ouvre le lien du message Discord.".encode(), "text/plain; charset=utf-8")
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
            for cid, c in CHANNELS.items():
                sel = [p for p in selection or [] if p.get("channel", "sorties") == cid] if selection is not None else None
                mine = choices.get(cid, {})
                used = publish.apply_choices(sel, {cid: mine}) if sel is not None else None
                at = publish.read_at(self.day, cid, now)
                live = {post: [e["i"] for e, _ in picked(data, used, post) or []] for post in ("to_book", "week")}
                channels.append({
                    "id": cid, "name": c["name"], "label": c["label"],
                    "posts": [t for t in (to_book_post(data, at, selection=used), outings_post_reviewed(data, at, selection=used)) if t],
                    # Only an edition is sent at its slot (tick.py); older daily runs are not scheduled.
                    "sends_at": at.isoformat(timespec="minutes") if self.day in editions else None,
                    "lists": choice_list(data, sel, live, cid, now.date()) if sel is not None else {},
                    "custom": {post: post in mine for post in ("to_book", "week")},
                })
            alerts_text = alerts_cached(now)
            channels.append({"id": "infos", "name": "GRNBL · Annonces", "label": "🚨 Alertes",
                             "posts": [alerts_text] if alerts_text else [], "picks": []})
            channels.append({"id": "carburant", "name": "grnbl · Carburant", "label": "⛽ Carburant", "posts": [fuel_text] if fuel_text else [], "picks": []})
            # Fuel and alerts are daily, filed under today; the groups under their edition.
            today = now.date()
            sent, ids = {**publish.status(self.day), **{k: v for k, v in publish.status(today).items() if k in DAILY}}, publish.channel_ids()
            for c in channels:
                c["outbox"], c["linked"] = sent.get(c["id"], {}), c["id"] in ids
            return self._json({"channels": channels, "watch": watch})
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if not self._allowed():
            return
        if self.path not in ("/api/decide", "/api/publish", "/api/choose"):
            return self._send(404, b"not found", "text/plain")
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
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
            return self._json({"ok": True, "report": report})
        i = body.get("i")
        if not isinstance(i, int):
            return self._json({"ok": False}, 400)
        decision = body.get("decision")
        if decision is not None:
            decision = {"status": decision.get("status"), "line": decision.get("line")}
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
