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
this Mac now and on a small Linux server later. Channel ids live in
data/whatsapp.json, {"gratuit": "<id>@newsletter", ...}, written once by
`node whatsapp/send.mjs channels`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import memory
from .digest import fuel_post, outings_post_reviewed, picked, to_book_post
from .editor import CHANNELS
from .sources import fuel

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONFIG = DATA / "whatsapp.json"
SENDER = ROOT / "whatsapp" / "send.mjs"
PARIS = ZoneInfo("Europe/Paris")
POSTS = (("to_book", to_book_post), ("week", outings_post_reviewed))


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
    return events, json.loads(sel.read_text()) if sel.exists() else None


def outbox(day: date, now: datetime, fuel_text: str | None = None) -> list[dict]:
    """Every post of the day, with whether the human approved it."""
    events, selection = day_events(day)
    out = []
    for cid in CHANNELS:
        sel = [p for p in selection if p.get("channel", "sorties") == cid] if selection is not None else None
        for post, write in POSTS:
            text = write(events, now, selection=sel)
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
    return out


def _path(day: date, item: dict) -> Path:
    return DATA / "outbox" / day.isoformat() / f"{item['channel']}-{item['post']}.json"


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
            report.append((name, f"pas d'identifiant de chaîne dans {CONFIG.name}"))
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
