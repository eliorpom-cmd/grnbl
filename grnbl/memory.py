"""What grnbl remembers from one day to the next.

Three things a person who keeps an eye on the city knows without thinking:
  - what was already shared, so it is not shared again (data/posted.json);
  - what comes back every week (a market, a club night): routine, not news,
    told apart from the days of scraping kept in data/events/<day>/all.json;
  - what the human editor kept or dropped before (data/decisions/), given to
    the AI review as examples of the channel's taste.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
POSTED = DATA / "posted.json"


def title_key(title: str) -> str:
    t = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def event_key(e: dict) -> str:
    return f"{title_key(e['title'])}|{str(e['start'])[:10]}"


# Seen on this many different dates within the window: it is a routine.
ROUTINE_DATES = 3


def start_dates(today: date, days: int = 60) -> dict[str, set[str]]:
    """Every start date each title had, over the past days of scraping (and today's)."""
    seen: dict[str, set[str]] = {}
    for folder in sorted((DATA / "events").glob("20*")):
        try:
            day = date.fromisoformat(folder.name)
        except ValueError:
            continue
        if not today - timedelta(days=days) <= day <= today or not (folder / "all.json").exists():
            continue
        for e in json.loads((folder / "all.json").read_text()):
            # A collapsed series carries all its sessions (scrape/run.collapse).
            for start in e.get("dates") or [e["start"]]:
                seen.setdefault(title_key(e["title"]), set()).add(str(start)[:10])
    return seen


def is_routine(e: dict, seen: dict[str, set[str]]) -> bool:
    return len(seen.get(title_key(e["title"]), ())) >= ROUTINE_DATES


def posted() -> dict[str, str]:
    return json.loads(POSTED.read_text()) if POSTED.exists() else {}


def mark_posted(events: list[dict], day: date) -> None:
    """Called when a post goes out: those events will not be shared again."""
    done = posted()
    for e in events:
        done.setdefault(event_key(e), day.isoformat())
    POSTED.parent.mkdir(parents=True, exist_ok=True)
    POSTED.write_text(json.dumps(done, ensure_ascii=False, indent=1))


def already_posted(e: dict, done: dict[str, str] | None = None) -> bool:
    return event_key(e) in (posted() if done is None else done)


def past_decisions(today: date, limit: int = 40) -> list[dict]:
    """The human's latest keep/drop calls, newest first, as short examples."""
    out = []
    for path in sorted((DATA / "decisions").glob("20*.json"), reverse=True):
        day = path.stem
        if day > today.isoformat():
            continue
        reviewed = DATA / "events" / day / "reviewed.json"
        if not reviewed.exists():
            continue
        events = json.loads(reviewed.read_text())
        for i, d in json.loads(path.read_text()).items():
            if d.get("status") not in ("keep", "drop") or int(i) >= len(events):
                continue
            e = events[int(i)]
            out.append({"title": e["title"], "category": e.get("category"), "price": e.get("price"),
                        "town": e.get("town"), "ai_said": (e.get("review") or {}).get("keep"),
                        "editor": d["status"], "line": d.get("line")})
            if len(out) >= limit:
                return out
    return out
