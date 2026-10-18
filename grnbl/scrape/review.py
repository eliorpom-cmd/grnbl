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

import concurrent.futures as cf
import hashlib
import json
from datetime import date
from pathlib import Path

from .. import editorial, memory
from .extract import ask, parse_array

DATA = Path(__file__).resolve().parents[2] / "data"

PROMPT = """You review events scraped from Grenoble (France) agendas and local press for a WhatsApp channel
that tells ordinary people of the Grenoble area what is worth going to. Think like the friend who always knows
what's on: editorial, reliable, interesting. Not a listing of everything. Today is {today}.
Each event has a "timing": "book_now" (booking open, still time), "opens_soon" (booking opens soon),
"this_week" (no booking, in the coming days). Timing is already decided; you judge the interest.

For EACH event below, return one JSON object, in a JSON array, nothing else:
{{"i": <the event's i>, "keep": true/false, "why": short reason in French (only when keep is false),
  "score": 1-5 (5 = a great outing for many people: big concert, festival, popular free event),
  "free": true/false/null, "family": true if suited to children,
  "rare": true if it happens once a year or less (festival, heritage days, special opening, one-off visit),
          false for routine things (weekly market, regular club meeting, a show on a long run),
  "duplicate_of": <i of the same event listed earlier> or null,
  "line": one short, warm, factual French line for the post (what it is, no hype). Only facts given in the
          event: no date, history or detail from your own knowledge, they are often out of date}}

Drop: online-only events, events more than ~30 km from Grenoble, professional or paid trainings,
private or members-only meetings, religious services, political meetings, past events, ads, and anything
that is not an outing. Keep council meetings only if open and of general interest (rarely).
Also drop what everybody already knows or sees everywhere: ordinary league matches (keep a sports event
only if it is free and festive, or exceptional), commercial events (sales, shop openings, paid trade fairs
unless huge), weekly markets, cinema screenings of ordinary releases, recurring classes and club meetings.
Score high what people would hate to miss and rarely hear about: free and rare things, special openings
(a monument, a backstage visit), free concerts, festivals, things that need booking soon.
Signals given with each event: "sources" = how many agendas list it, "press" = a journalist wrote about it
(both mean people talk about it: raise the score a little), "routine" = it came back on 3+ different dates
lately (a weekly thing: lower the score, rarely worth a post).
{taste}

EVENTS:
{events}
"""


POSTABLE = editorial.POSTABLE
TIMING_WHY = {"too_late": "Trop tard : il fallait réserver avant", "sold_out": "Complet",
              "later": "Plus tard : revu quand ce sera le moment d'en parler"}


def _compact(i: int, e: dict, today: date) -> dict:
    return {"i": i, "title": e["title"], "start": e["start"], "end": e.get("end"), "venue": e.get("venue"),
            "town": e.get("town"), "price": e.get("price"), "category": e.get("category"),
            "description": (e.get("description") or "")[:200], "source": e.get("source_name"),
            "booking": e.get("booking"), "booking_opens": e.get("booking_opens"), "timing": editorial.timing(e, today),
            "sources": 1 + len(e.get("also") or []),
            "press": any(str(s).startswith("press-") for s in [e.get("source"), *(e.get("also") or [])]),
            "routine": bool(e.get("routine"))}


def taste_block(today: date) -> str:
    """The editor's past calls, so the review learns the channel's taste."""
    calls = memory.past_decisions(today)
    if not calls:
        return ""
    return ("The human editor of the channel corrected earlier reviews. Follow their taste:\n"
            + json.dumps(calls, ensure_ascii=False))


def review(events: list[dict], today: date, batch: int = 40, model: str = "sonnet") -> list[dict]:
    """The AI only sees what could go out today; the timing rules settle the rest."""
    verdicts: dict[int, dict] = {}
    seen, done = memory.start_dates(today), memory.posted()
    for i, e in enumerate(events):
        e["routine"] = memory.is_routine(e, seen)
        t = editorial.timing(e, today)
        if t not in POSTABLE:
            verdicts[i] = {"keep": False, "why": TIMING_WHY[t], "auto": True}
        elif memory.already_posted(e, done):
            verdicts[i] = {"keep": False, "why": "Déjà partagé", "auto": True}
    taste = taste_block(today)
    # An event already judged with the same facts keeps its verdict: only new or changed events cost tokens.
    keys = {i: memory.event_key(e) for i, e in enumerate(events)}
    index = {k: i for i, k in reversed(list(keys.items()))}
    fingerprints = {}
    for i, e in enumerate(events):
        if i in verdicts:
            continue
        fingerprints[i] = _fingerprint(e, today)
        last = _recall(fingerprints[i], today)
        if last:
            dup = index.get(last.pop("duplicate_key", None))
            verdicts[i] = {**last, "duplicate_of": dup if dup is not None and dup < i else None}
    todo = [(i, e) for i, e in enumerate(events) if i not in verdicts]
    chunks = [[_compact(i, e, today) for i, e in todo[at:at + batch]] for at in range(0, len(todo), batch)]

    def one(chunk):
        prompt = PROMPT.format(today=today.isoformat(), taste=taste, events=json.dumps(chunk, ensure_ascii=False))
        for attempt in range(2):
            try:
                return parse_array_any(ask(prompt, model=model, timeout=900))
            except Exception:  # noqa: BLE001 - retried once, then that batch stays "not reviewed"
                continue
        return []

    with cf.ThreadPoolExecutor(3) as ex:
        for answer in ex.map(one, chunks):
            for v in answer:
                i = v.get("i")
                if isinstance(i, int) and i in fingerprints:
                    verdicts[i] = v
                    dup = v.get("duplicate_of")
                    _remember(fingerprints[i], today, {**v, "duplicate_key": keys.get(dup) if isinstance(dup, int) else None})
    out = []
    for i, e in enumerate(events):
        v = verdicts.get(i, {"keep": None, "why": "not reviewed"})
        out.append({**e, "timing": editorial.timing(e, today),
                    "review": {k: v.get(k) for k in ("keep", "why", "score", "free", "family", "rare", "duplicate_of", "line", "auto")}})
    return out


SEEN = DATA / "review"
# Past this age a verdict is asked again: the editor's taste has had time to move.
REUSE_DAYS = 7


def _fingerprint(e: dict, today: date) -> str:
    facts = {k: v for k, v in _compact(0, e, today).items() if k != "i"}
    return hashlib.sha1(json.dumps(facts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]


def _recall(fingerprint: str, today: date) -> dict | None:
    path = SEEN / f"{fingerprint}.json"
    if not path.exists():
        return None
    last = json.loads(path.read_text())
    if (today - date.fromisoformat(last["day"])).days > REUSE_DAYS:
        return None
    return {k: v for k, v in last["verdict"].items() if k != "i"}


def _remember(fingerprint: str, today: date, verdict: dict) -> None:
    SEEN.mkdir(parents=True, exist_ok=True)
    (SEEN / f"{fingerprint}.json").write_text(json.dumps({"day": today.isoformat(), "verdict": verdict}, ensure_ascii=False))


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
