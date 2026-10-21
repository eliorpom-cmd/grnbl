"""Sends the day's posts to the WhatsApp channels, once, and only what was approved.

The outings posts go out only after the human pressed "Tout est bon" on the
board, that is when every line of the post carries a "keep" decision. The fuel
post is automatic. Each post is written to the outbox before sending:

    data/outbox/<day>/<channel>-<post>.json   {"text", "events", "status", "sent_at", "id"}

A post marked "sent" is never sent again, so the command can run as often as
needed (from the board, from a scheduler, by hand). Sending is a dry run unless
`send=True`: the dry run only writes the outbox and says what would go out.

The WhatsApp side is a separate Node script (whatsapp/send.mjs) that connects,
sends one message and disconnects: no server stays up, the same command runs on
this Mac now and on a small Linux server later. grnbl posts into the groups of
one WhatsApp community, one group per topic (admins only can write). Their ids
live in data/whatsapp.json, {"gratuit": "<id>@g.us", ...}, listed once by
`node whatsapp/send.mjs groups`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import memory, schedule
from .digest import alerts_post, fuel_post, outings_post_reviewed, picked, to_book_post
from .channels import CHANNELS, accepts
from .sources import alerts, fuel

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONFIG = DATA / "whatsapp.json"
SENDER = ROOT / "whatsapp" / "send.mjs"
PARIS = ZoneInfo("Europe/Paris")
POSTS = (("to_book", to_book_post), ("week", outings_post_reviewed))


def choices_path(day: date) -> Path:
    return DATA / "decisions" / f"{day.isoformat()}-posts.json"


def load_choices(day: date) -> dict:
    """What the human ticked in the board's lists: {channel: {post: [event index, ...]}}."""
    path = choices_path(day)
    return json.loads(path.read_text()) if path.exists() else {}


def save_choice(day: date, channel: str, post: str, ids: list[int] | None) -> None:
    """Store the ticked lines of one post, in order; None goes back to the editor's picks."""
    choices = load_choices(day)
    if ids is None:
        choices.get(channel, {}).pop(post, None)
    else:
        choices.setdefault(channel, {})[post] = ids
    path = choices_path(day)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(choices, ensure_ascii=False, indent=1))


def apply_choices(selection: list[dict] | None, choices: dict) -> list[dict] | None:
    """The editor's selection where the human's ticked lists replace the picks of their post.

    The editor's written line is kept for a line it had chosen (pick or reserve)."""
    if selection is None:
        return None
    out = [p for p in selection if p.get("post") not in choices.get(p.get("channel", "sorties"), {})]
    for channel, posts in choices.items():
        for post, ids in posts.items():
            lines = {p["i"]: p.get("line") for p in selection if p.get("channel", "sorties") == channel and p.get("post") == post}
            out += [{"i": i, "post": post, "channel": channel, "line": lines.get(i)} for i in ids]
    return out


def day_events(day: date) -> tuple[list[dict], list[dict] | None]:
    """The reviewed events with the human's decisions, and the editor's selection."""
    folder = DATA / "events" / day.isoformat()
    reviewed, sel = folder / "reviewed.json", folder / "selection.json"
    events = json.loads(reviewed.read_text()) if reviewed.exists() else []
    path = DATA / "decisions" / f"{day.isoformat()}.json"
    decisions = json.loads(path.read_text()) if path.exists() else {}
    for i, e in enumerate(events):
        e["i"] = i
        e["decision"] = decisions.get(str(i))
    selection = apply_choices(json.loads(sel.read_text()) if sel.exists() else None, load_choices(day))
    return events, in_their_group(events, selection)


def in_their_group(events: list[dict], selection: list[dict] | None) -> list[dict] | None:
    """Only the lines whose event belongs to that group (channels.home), each event once:
    a line ticked by hand or left from an older selection never reaches a second group."""
    if selection is None:
        return None
    seen, out = set(), []
    for p in selection:
        i, channel = p.get("i", -1), p.get("channel", "sorties")
        if not 0 <= i < len(events) or (channel in CHANNELS and not accepts(channel, events[i])):
            continue
        if not p.get("reserve"):
            if i in seen:
                continue
            seen.add(i)
        out.append(p)
    return out


def read_at(day: date, channel: str, now: datetime) -> datetime:
    """When people will read a group's post of that edition: its sending time (schedule.py)."""
    slot = schedule.slot_of(channel)
    if not slot:
        return now
    at = schedule.send_time(day, slot).replace(tzinfo=PARIS)
    return max(at, now) if at.date() == now.date() else at


def outbox(day: date, now: datetime, fuel_text: str | None = None, alerts_text: str | None = None) -> list[dict]:
    """Every post of the day, with whether the human approved it."""
    events, selection = day_events(day)
    out = []
    for cid in CHANNELS:
        sel = [p for p in selection if p.get("channel", "sorties") == cid] if selection is not None else None
        for post, write in POSTS:
            text = write(events, read_at(day, cid, now), selection=sel)
            lines = picked(events, sel, post) or []
            if not text or not lines:
                continue
            approved = all((e.get("decision") or {}).get("status") == "keep" for e, _ in lines)
            out.append({"channel": cid, "post": post, "text": text, "approved": approved,
                        "events": [{"title": e["title"], "start": e["start"]} for e, _ in lines]})
    if fuel_text is None:
        fuel_text = fuel_post(fuel.collect(), now)
    if fuel_text:
        out.append({"channel": "carburant", "post": "fuel", "text": fuel_text, "approved": True, "events": []})
    if alerts_text is None:
        alerts_text = alerts_post(alerts.collect(now)[0], now)
    if alerts_text:
        out.append({"channel": "infos", "post": "alerts", "text": alerts_text, "approved": True, "events": []})
    return out


def _path(day: date, item: dict) -> Path:
    return DATA / "outbox" / day.isoformat() / f"{item['channel']}-{item['post']}.json"


def status(day: date) -> dict[str, dict[str, dict]]:
    """What the outbox says per channel and post: status, sent_at, error."""
    out: dict[str, dict[str, dict]] = {}
    for path in sorted((DATA / "outbox" / day.isoformat()).glob("*.json")):
        r = json.loads(path.read_text())
        out.setdefault(r["channel"], {})[r["post"]] = {k: r.get(k) for k in ("status", "sent_at", "error")}
    return out


def channel_ids() -> dict[str, str]:
    return json.loads(CONFIG.read_text()) if CONFIG.exists() else {}


def deliver(jid: str, text: str) -> str:
    """One message through the Node sender; returns WhatsApp's message id."""
    out = subprocess.run(["node", str(SENDER), "send", jid], input=json.dumps({"text": text}),
                         capture_output=True, text=True, timeout=120, cwd=ROOT)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip()[-300:] or f"sender exited {out.returncode}")
    return json.loads(out.stdout.strip().splitlines()[-1])["id"]


def run(day: date | None = None, send: bool = False, only: list[str] | None = None,
        items: list[dict] | None = None) -> list[tuple[str, str]]:
    """Writes the outbox and, with send=True, sends what is approved and not sent yet.
    Returns (post, what happened) for each post."""
    now = datetime.now(PARIS)
    day = day or now.date()
    ids = channel_ids()
    report = []
    for item in items if items is not None else outbox(day, now):
        name = f"{item['channel']}-{item['post']}"
        if only and item["channel"] not in only:
            continue
        path = _path(day, item)
        last = json.loads(path.read_text()) if path.exists() else {}
        if last.get("status") == "sent":
            report.append((name, "déjà envoyé"))
            continue
        status = "ready" if item["approved"] else "waiting"
        record = {**item, "status": status}
        if status == "waiting":
            report.append((name, "en attente de « Tout est bon »"))
        elif not send:
            report.append((name, "prêt (essai : rien envoyé)"))
        elif item["channel"] not in ids:
            report.append((name, f"groupe pas encore relié ({CONFIG.name})"))
        else:
            try:
                record["id"] = deliver(ids[item["channel"]], item["text"])
            except Exception as e:  # noqa: BLE001 - one failed post is reported, the others still go
                record["status"], record["error"] = "failed", str(e)[:300]
                report.append((name, f"échec : {record['error']}"))
            else:
                record["status"], record["sent_at"] = "sent", datetime.now(PARIS).isoformat(timespec="seconds")
                memory.mark_posted(item["events"], day)
                report.append((name, "envoyé"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=1))
    return report


def main(argv: list[str]) -> int:
    send = "--send" in argv
    only = [a for a in argv if not a.startswith("--")] or None
    for name, what in run(send=send, only=only):
        print(f"{name:22} {what}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
