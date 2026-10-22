"""Prepares the day's posts for the WhatsApp groups, once, and only what was approved.

The outings posts are ready only after the human pressed "Tout est bon" on the
board, that is when every line of the post carries a "keep" decision. Each post
is written to the outbox:

    data/outbox/<day>/<channel>-<post>.json   {"text", "events", "status", "sent_at", "by_hand"}

Posting is done by hand: WhatsApp has no official way to post into community
groups from a normal account, and an unofficial client would break its terms.
At its slot an approved post becomes "to_post"; the human copies it from the
board into the group and clicks "I posted it" (mark_posted). A post marked
"sent" is never offered again. Without `send=True` the run is a dry run that
only says what is ready.
"""

from __future__ import annotations

import json
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
    """What the outbox says per channel and post: status, sent_at, error, by_hand."""
    out: dict[str, dict[str, dict]] = {}
    for path in sorted((DATA / "outbox" / day.isoformat()).glob("*.json")):
        r = json.loads(path.read_text())
        out.setdefault(r["channel"], {})[r["post"]] = {k: r.get(k) for k in ("status", "sent_at", "error", "by_hand")}
    return out


def mark_posted(day: date, channel: str) -> list[str]:
    """The human pasted the channel's approved posts into WhatsApp: record them as sent, once."""
    done = []
    for path in sorted((DATA / "outbox" / day.isoformat()).glob(f"{channel}-*.json")):
        record = json.loads(path.read_text())
        if record.get("status") == "sent" or not record.get("approved"):
            continue
        record.update(status="sent", by_hand=True, sent_at=datetime.now(PARIS).isoformat(timespec="seconds"))
        memory.mark_posted(record.get("events") or [], day)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=1))
        done.append(path.stem)
    return done


def run(day: date | None = None, send: bool = False, only: list[str] | None = None,
        items: list[dict] | None = None) -> list[tuple[str, str]]:
    """Writes the outbox and, with send=True, sends what is approved and not sent yet.
    Returns (post, what happened) for each post."""
    now = datetime.now(PARIS)
    day = day or now.date()
    report = []
    if items is None:
        # Fuel and alerts are read from the network: not when the run is for other groups only,
        # so a source that is down cannot hold back the outings posts (tick.send_slots).
        skip = lambda channel: "" if only and channel not in only else None
        items = outbox(day, now, fuel_text=skip("carburant"), alerts_text=skip("infos"))
    for item in items:
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
        else:
            record["status"] = "to_post"
            report.append((name, "à poster à la main"))
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
