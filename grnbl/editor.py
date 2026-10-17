"""The editor-in-chief: composes the posts from the best candidates, side by side.

The review scores each event on its own, so a big paid concert and a league
match can outrank a once-a-year free opening. Here one model sees the forty
best candidates together and picks what goes out, the way the person who always
knows what's on would: variety (not three concerts), something for families,
free things, the rare before the routine, and what must be booked soon. It says
why for each pick; the admin board shows it and the human still decides.

Output: data/events/<day>/selection.json, read by digest.py when it exists.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from . import editorial
from .digest import chosen
from .scrape.extract import ask, parse_array_raw

DATA = Path(__file__).resolve().parents[1] / "data"
CANDIDATES = 40

PROMPT = """You are the editor of "grnbl", a WhatsApp channel for ordinary people of the Grenoble area
(families, students, retirees). Its promise: the friend who always knows the good plans, reliable and never
boring, never what everybody already saw everywhere. Today is {today}.

Below are the best candidates, already checked (dates, booking). Compose two posts:
- "to_book": up to {n_book} things to book NOW (timing book_now) or as soon as booking opens (opens_soon).
- "week": up to {n_week} things for the coming days that need no booking (timing this_week).

Choose them together, not one by one:
- variety: no more than two of the same kind (concert, exhibition, sport, kids, visit...);
- at least one for families with children and, if any exist, at least two that are free;
- the rare before the routine: a once-a-year opening beats a show on a long run;
- buzz counts (press, several sources), big names alone do not: a paid concert or show by a famous artist is
  already advertised everywhere, never pick it; at most two paid items per post;
- leave out anything you would not tell a friend about.
The line uses only facts present in the candidate (title, dates, place, price, its line): never add a fact.

Return ONLY a JSON array, in the order the items should appear:
{{"i": <candidate i>, "post": "to_book" | "week", "why": short French reason for the editor (why this one),
  "line": the French line for the post: warm, factual, one sentence, the useful detail first}}

CANDIDATES:
{candidates}
"""


def candidates(events: list[dict], today: date, n: int = CANDIDATES) -> list[tuple[int, dict]]:
    index = {id(e): i for i, e in enumerate(events)}
    pool = [e for e in chosen(events) if editorial.timing(e, today) in ("book_now", "opens_soon", "this_week")]
    pool.sort(key=lambda e: (-((e.get("review") or {}).get("score") or 0), str(e["start"])))
    return [(index[id(e)], e) for e in pool[:n]]


def _brief(i: int, e: dict, today: date) -> dict:
    r = e.get("review") or {}
    return {"i": i, "title": e["title"], "start": e["start"], "end": e.get("end"),
            "where": e.get("venue") or e.get("town"), "price": e.get("price"), "free": r.get("free"),
            "family": r.get("family"), "rare": r.get("rare"), "routine": e.get("routine"),
            "category": e.get("category"), "score": r.get("score"), "timing": editorial.timing(e, today),
            "booking_opens": e.get("booking_opens"), "sources": 1 + len(e.get("also") or []),
            "press": any(str(s).startswith("press-") for s in [e.get("source"), *(e.get("also") or [])]),
            "line": (e.get("decision") or {}).get("line") or r.get("line")}


def select(events: list[dict], today: date, n_book: int = 6, n_week: int = 8) -> list[dict]:
    pool = candidates(events, today)
    if not pool:
        return []
    allowed = {i for i, _ in pool}
    prompt = PROMPT.format(today=today.isoformat(), n_book=n_book, n_week=n_week,
                           candidates=json.dumps([_brief(i, e, today) for i, e in pool], ensure_ascii=False))
    picks = [p for p in parse_array_raw(ask(prompt, model="sonnet", timeout=600))
             if p.get("i") in allowed and p.get("post") in ("to_book", "week")]
    # The rules stay the rules: a pick in the wrong post is moved, not trusted.
    for p in picks:
        t = editorial.timing(events[p["i"]], today)
        p["post"] = "week" if t == "this_week" else "to_book"
    return picks


def run(today: date | None = None) -> list[dict]:
    today = today or date.today()
    folder = DATA / "events" / today.isoformat()
    events = json.loads((folder / "reviewed.json").read_text())
    picks = select(events, today)
    (folder / "selection.json").write_text(json.dumps(picks, ensure_ascii=False, indent=1))
    return picks


if __name__ == "__main__":
    for p in run(date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else None):
        print(p["post"], p["i"], p["why"])
