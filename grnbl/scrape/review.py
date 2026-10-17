"""The AI review: what is worth telling people about.

Extraction copies what the pages say. The review judges it, the way the person
in the family who always knows what's on would: is it in reach of Grenoble,
open to the public, worth leaving the house for? It also catches the same event
announced twice under different names, which the exact-title merge misses.

Output per event: keep or drop, why, an interest score, and the one line the
post will use. Nothing is published from here: the admin board shows the result
and the human has the last word.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .extract import ask, parse_array

DATA = Path(__file__).resolve().parents[2] / "data"

PROMPT = """You review events scraped from Grenoble (France) agendas for a WhatsApp channel that tells
ordinary people of the Grenoble area what is worth going to. Think like the friend who always knows what's on.
Today is {today}.

For EACH event below, return one JSON object, in a JSON array, nothing else:
{{"i": <the event's i>, "keep": true/false, "why": short reason in French (only when keep is false),
  "score": 1-5 (5 = a great outing for many people: big concert, festival, popular free event),
  "free": true/false/null, "family": true if suited to children,
  "duplicate_of": <i of the same event listed earlier> or null,
  "line": one short, warm, factual French line for the post (what it is, no hype, no invented facts)}}

Drop: online-only events, events more than ~30 km from Grenoble, professional or paid trainings,
private or members-only meetings, religious services, political meetings, past events, ads, and anything
that is not an outing. Keep council meetings only if open and of general interest (rarely).

EVENTS:
{events}
"""


def _compact(i: int, e: dict) -> dict:
    return {"i": i, "title": e["title"], "start": e["start"], "end": e.get("end"), "venue": e.get("venue"),
            "town": e.get("town"), "price": e.get("price"), "category": e.get("category"),
            "description": (e.get("description") or "")[:200], "source": e.get("source_name")}


def review(events: list[dict], today: date, batch: int = 70, model: str = "sonnet") -> list[dict]:
    verdicts: dict[int, dict] = {}
    for at in range(0, len(events), batch):
        chunk = [_compact(i, e) for i, e in enumerate(events[at:at + batch], start=at)]
        answer = ask(PROMPT.format(today=today.isoformat(), events=json.dumps(chunk, ensure_ascii=False)),
                     model=model, timeout=600)
        for v in parse_array_any(answer):
            if isinstance(v.get("i"), int):
                verdicts[v["i"]] = v
    out = []
    for i, e in enumerate(events):
        v = verdicts.get(i, {"keep": None, "why": "not reviewed"})
        out.append({**e, "review": {k: v.get(k) for k in ("keep", "why", "score", "free", "family", "duplicate_of", "line")}})
    return out


def parse_array_any(answer: str) -> list[dict]:
    """Like extract.parse_array, without requiring a title: verdicts have none."""
    start, end = answer.find("["), answer.rfind("]")
    if start < 0 or end < start:
        return []
    return [v for v in json.loads(answer[start:end + 1]) if isinstance(v, dict)]


def run(today: date | None = None) -> list[dict]:
    today = today or date.today()
    folder = DATA / "events" / today.isoformat()
    events = json.loads((folder / "all.json").read_text())
    reviewed = review(events, today)
    (folder / "reviewed.json").write_text(json.dumps(reviewed, ensure_ascii=False, indent=1))
    return reviewed
