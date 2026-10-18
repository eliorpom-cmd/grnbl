"""The morning ping: a Discord message saying the posts are ready, with the board's link.

    python3 -m grnbl.notify            after a good run: what waits for review, channel by channel
    python3 -m grnbl.notify --failed 1 the run failed (exit code), with where the log is

Settings in data/notify.json (not versioned):
    {"discord": "https://discord.com/api/webhooks/...", "board": "https://..."}
Nothing is sent without a webhook, so the run never depends on Discord.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime

from . import publish
from .editor import CHANNELS

CONFIG = publish.DATA / "notify.json"
NAMES = {"gratuit": "🆓 Gratuit", "sorties": "🎭 Sorties", "carburant": "⛽ Carburant"}


def settings() -> dict:
    return json.loads(CONFIG.read_text()) if CONFIG.exists() else {}


def summary(now: datetime) -> str:
    day = now.date()
    items = publish.outbox(day, now, fuel_text="")  # fuel is reported from the outbox, not fetched again
    sent = publish.status(day)
    lines = [f"☀️ *grnbl* · les posts du {day.strftime('%d/%m')} sont prêts"]
    for cid in CHANNELS:
        mine = [i for i in items if i["channel"] == cid]
        out = sent.get(cid, {})
        if mine and all(out.get(i["post"], {}).get("status") == "sent" for i in mine):
            lines.append(f"{NAMES[cid]} : envoyé ✓")
        elif mine:
            todo = sum(len(i["events"]) for i in mine if not i["approved"])
            lines.append(f"{NAMES[cid]} : {todo} lignes à relire" if todo else f"{NAMES[cid]} : validé, à publier")
        else:
            lines.append(f"{NAMES[cid]} : rien aujourd'hui")
    fuel = sent.get("carburant", {}).get("fuel", {})
    lines.append(f"{NAMES['carburant']} : " + {"sent": f"envoyé à {(fuel.get('sent_at') or '')[11:16]} ✓",
                                                 "failed": f"échec ({fuel.get('error')})"}.get(fuel.get("status"), "pas envoyé (chaîne pas encore reliée ?)"))
    return "\n".join(lines)


def failure(code: str, now: datetime) -> str:
    return (f"⚠️ *grnbl* · la préparation du {now.strftime('%d/%m')} a échoué (code {code}).\n"
            f"Journal : data/logs/{now.date().isoformat()}.log · nouvel essai à 14 h.")


def post(text: str, cfg: dict) -> bool:
    if not cfg.get("discord"):
        return False
    board = cfg.get("board")
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
    try:
        print("discord:", "sent" if post(text, settings()) else f"no webhook in {CONFIG.name}")
    except Exception as e:  # noqa: BLE001 - a Discord outage never fails the morning run
        print(f"discord: failed ({e})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
