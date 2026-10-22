"""When each group posts, and when its posts are prepared and read.

Events can be planned ahead, so they are not posted every day: once a week an
"edition" is prepared (collect, review, editor), the human reads it in one
sitting, and each group's posts then go out on their own day and hour. A post
the human has not approved does not go out; a reminder comes before.

Fuel goes out every morning on its own. Alerts are checked every hour and only
ever sent by the human (alerts.py, tick.py).

An edition is dated by its first sending day: its data lives in
data/events/<edition>/ and its outbox in data/outbox/<edition>/.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"

# weekday: Monday = 0. Each slot names the groups it sends.
SLOTS = [
    {"id": "mercredi", "weekday": 2, "at": time(12, 0), "channels": ["gratuit", "sorties", "famille"]},
    {"id": "jeudi", "weekday": 3, "at": time(18, 0), "channels": ["bonsplans", "nature"]},
]
PREPARE = {"weekday": 1, "at": time(10, 0)}  # Tuesday 10:00, for the slots of the next days
REMIND_BEFORE = timedelta(hours=2)
FUEL_AT = time(10, 0)
ALERT_HOURS = range(7, 23)  # checked every hour from 7:00 to 22:00
# One-off shifts of a slot for a given edition: {(edition, slot id): time}.
MOVED = {(date(2026, 10, 21), "mercredi"): time(18, 0)}  # posts reworked on the day, sent in the evening


def next_day(weekday: int, after: date) -> date:
    """The first date on that weekday strictly after `after`."""
    return after + timedelta(days=(weekday - after.weekday() - 1) % 7 + 1)


def edition_for(prepare_day: date) -> date:
    """The edition a preparation on that day is for: the first slot after it."""
    return min(next_day(s["weekday"], prepare_day) for s in SLOTS)


def slot_of(channel: str) -> dict | None:
    return next((s for s in SLOTS if channel in s["channels"]), None)


def send_time(edition: date, slot: dict) -> datetime:
    """When the slot of that edition sends: its weekday on or after the edition day."""
    day = edition + timedelta(days=(slot["weekday"] - edition.weekday()) % 7)
    return datetime.combine(day, MOVED.get((edition, slot["id"]), slot["at"]))


def channel_day(edition: date, channel: str) -> date:
    """The day a group's posts are written for: its own sending day, so "this week"
    and booking deadlines are counted from when people read it."""
    slot = slot_of(channel)
    return send_time(edition, slot).date() if slot else edition


def editions() -> list[date]:
    out = []
    for folder in (DATA / "events").glob("20*"):
        try:
            day = date.fromisoformat(folder.name)
        except ValueError:
            continue
        # An edition is dated by its first slot; other folders are trials or older daily runs.
        if (folder / "selection.json").exists() and day.weekday() == min(s["weekday"] for s in SLOTS):
            out.append(day)
    return sorted(out)


def current_edition(today: date) -> date:
    """The edition the board shows: the latest prepared one up to a week ahead, else today."""
    ready = [d for d in editions() if d <= today + timedelta(days=7)]
    return ready[-1] if ready else today


STATE = DATA / "schedule-state.json"


def state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def remember(key: str, value=True) -> None:
    s = state()
    s[key] = value
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=1))
