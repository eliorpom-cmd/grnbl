"""The morning ping: a Discord message saying the posts are ready, with the board's link.

    python3 -m grnbl.notify            after a good run: what waits for review, channel by channel
    python3 -m grnbl.notify --failed 1 the run failed (exit code), with where the log is

Settings in data/notify.json (not versioned):
    {"discord": "https://discord.com/api/webhooks/...", "board": "https://grnbl.byelior.dev"}
The link carries the board's key (data/board-key), so one tap opens it signed in.
Nothing is sent without a webhook, so the run never depends on Discord.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import date, datetime

from . import publish, schedule
from .admin import board_key
from .digest import DAYS
from .channels import CHANNELS

CONFIG = publish.DATA / "notify.json"
NAMES = {**{cid: c["label"] for cid, c in CHANNELS.items()}, "carburant": "⛽ Carburant"}


def settings() -> dict:
    return json.loads(CONFIG.read_text()) if CONFIG.exists() else {}


def _when(at: datetime) -> str:
    return f"{DAYS[at.weekday()]} {at.day}/{at.month:02d} à {at.hour}h{at.minute:02d}".replace("h00", "h")


def summary(now: datetime, edition: date | None = None) -> str:
    """The edition is ready: what each group will send, and when, so it is read in one sitting."""
    edition = edition or schedule.current_edition(now.date())
    items = publish.outbox(edition, now, fuel_text="", alerts_text="")
    sent = publish.status(edition)
    lines = [f"📬 *grnbl* · l'édition du {edition.strftime('%d/%m')} est prête à relire"]
    first = None
    for cid in CHANNELS:
        mine = [i for i in items if i["channel"] == cid]
        slot = schedule.slot_of(cid)
        at = schedule.send_time(edition, slot) if slot else None
        out = sent.get(cid, {})
        if mine and all(out.get(i["post"], {}).get("status") == "sent" for i in mine):
            lines.append(f"{NAMES[cid]} : envoyé ✓")
        elif mine:
            todo = sum(len(i["events"]) for i in mine if not i["approved"])
            when = f" · part {_when(at)}" if at else ""
            lines.append((f"{NAMES[cid]} : {todo} lignes à relire" if todo else f"{NAMES[cid]} : validé") + when)
            if todo and at and (first is None or at < first):
                first = at
        else:
            lines.append(f"{NAMES[cid]} : rien cette fois")
    if first:
        lines.append(f"_À valider avant {_when(first)} : un post pas validé ne part pas._")
    return "\n".join(lines)


def reminder(edition: date, labels: list[str], at: datetime) -> str:
    return (f"⏰ *grnbl* · {', '.join(labels)} part {_when(at)} mais n'est pas encore validé.\n"
            "Ouvre le tableau et appuie sur « Tout est bon », sinon le post ne part pas.")


def not_sent(labels: list[str], at: datetime) -> str:
    return f"⚠️ *grnbl* · {', '.join(labels)} n'est pas parti {_when(at)} : pas validé à temps."


def alert(text: str) -> str:
    return ("🚨 *grnbl* · alerte à valider. Rien n'est envoyé sans toi : onglet Infos du tableau, "
            "bouton Publier.\n\n" + text)


def ping(text: str) -> None:
    """Sends a message to the Discord webhook; an outage is printed, never raised."""
    try:
        print("discord:", "sent" if post(text, settings()) else f"no webhook in {CONFIG.name}")
    except Exception as e:  # noqa: BLE001 - Discord down never stops the schedule
        print(f"discord: failed ({e})")


def failure(code: str, now: datetime) -> str:
    return (f"⚠️ *grnbl* · la préparation du {now.strftime('%d/%m')} a échoué (code {code}).\n"
            f"Journal : data/logs/{now.date().isoformat()}.log · nouvel essai à l'heure suivante.")


def post(text: str, cfg: dict) -> bool:
    if not cfg.get("discord"):
        return False
    board = f"{cfg['board'].rstrip('/')}/?key={board_key()}" if cfg.get("board") else None
    # Discord uses **bold**; the summary is written with WhatsApp's *bold*.
    body = {"content": text.replace("*", "**") + (f"\n→ Ouvrir le tableau : {board}" if board else ""),
            "allowed_mentions": {"parse": []}}
    req = urllib.request.Request(cfg["discord"], data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "grnbl (notify, 1.0)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return 200 <= r.status < 300


def main(argv: list[str]) -> int:
    now = datetime.now(publish.PARIS)
    text = failure(argv[1] if len(argv) > 1 else "?", now) if argv[:1] == ["--failed"] else summary(now)
    if "--print" in argv:
        print(text)
        return 0
    ping(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
