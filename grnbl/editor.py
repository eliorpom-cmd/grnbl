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

import concurrent.futures as cf
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

from . import editorial, factcheck, memory, schedule
from .channels import CHANNELS, accepts
from .digest import chosen
from .scrape import clean, details
from .scrape.extract import ask, parse_array_raw
from .scrape.fetch import RAW, fetch

DATA = Path(__file__).resolve().parents[1] / "data"
CANDIDATES = 40
ORDER = ["famille", "nature", "bonsplans", "gratuit", "sorties"]

PROMPT = """You are the editor of "{channel}", a WhatsApp channel for ordinary people of the Grenoble area
(families, students, retirees). Its promise: {promise}. The friend who always knows the good plans,
reliable and never boring. Today is {today}.

Below are the best candidates, already checked (dates, booking). Compose two posts:
- "to_book": up to {n_book} things to book NOW (timing book_now) or as soon as booking opens (opens_soon).
- "week": up to {n_week} things for the coming days that need no booking (timing this_week).

Choose them together, not one by one:
- variety: no more than two of the same kind (concert, exhibition, sport, kids, visit...);
{taste}
- buzz counts (press, several sources);
- leave out anything you would not tell a friend about: ordinary league matches, commercial routine.
The line uses only facts present in the candidate (title, dates, place, price, its line): never add a fact.
{taste_calls}
Then add up to 3 reserves per post ("reserve": true), best first: they replace a pick the human removes.
Return ONLY a JSON array, picks in the order they should appear, then the reserves:
{{"i": <candidate i>, "post": "to_book" | "week", "reserve": true/false,
  "why": short French reason for the editor (why this one),
  "line": the French line for the post: warm, factual, one sentence that says what you will see or do and
          why it is worth going. The post already shows the name in bold, then day, time, place and price on
          the line above: never repeat them, and never start with the event's name}}

CANDIDATES:
{candidates}
"""


def _taste(today: date) -> str:
    """The human's keep/drop calls: the editor learns what they like."""
    calls = memory.past_decisions(today)
    if not calls:
        return ""
    return ("The human editor kept or removed these earlier picks. Learn their taste from it:\n"
            + json.dumps([{k: c[k] for k in ("title", "category", "price", "editor")} for c in calls], ensure_ascii=False) + "\n")


def candidates(events: list[dict], today: date, channel: str, n: int = CANDIDATES) -> list[tuple[int, dict]]:
    index = {id(e): i for i, e in enumerate(events)}
    pool = [e for e in chosen(events) if editorial.timing(e, today) in ("book_now", "opens_soon", "this_week")
            and accepts(channel, e)]
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


def select(events: list[dict], today: date, channel: str, n_book: int = 5, n_week: int = 6,
           already: list[dict] | None = None) -> list[dict]:
    # One event, one group: candidates only holds the events whose home is this group
    # (channels.home); what an earlier group took, reserves included, is never offered again.
    used = {p["i"] for p in already or []}
    pool = [(i, e) for i, e in candidates(events, today, channel) if i not in used]
    if not pool:
        return []
    allowed = {i for i, _ in pool}
    c = CHANNELS[channel]
    prompt = PROMPT.format(channel=c["name"], promise=c["promise"], taste=c["taste"], today=today.isoformat(),
                           n_book=n_book, n_week=n_week,
                           taste_calls=_taste(today),
                           candidates=json.dumps([_brief(i, e, today) for i, e in pool], ensure_ascii=False))
    picks = [p for p in parse_array_raw(ask(prompt, model="sonnet", timeout=600))
             if p.get("i") in allowed and p.get("post") in ("to_book", "week")]
    # The rules stay the rules: the post follows the timing, the channel is written on each pick.
    for p in picks:
        p["post"] = "week" if editorial.timing(events[p["i"]], today) == "this_week" else "to_book"
        p["channel"] = channel
        p["reserve"] = p.get("reserve") is True
    return picks


ZOOM_PROMPT = """You write one line of a WhatsApp post for people of the Grenoble area. Today is {today}.
The post recommends this festival or multi-day event:
{event}

"Il y a un festival" makes nobody move. Find in the page below ONE precise moment of its programme that
would make people want to go: a show, a concert, a workshop, a visit, with its day, time and place,
between {first} and {last}. Prefer free, unusual, family-friendly or one-off moments.{free_only}
Return ONLY a JSON object:
{{"found": true/false, "what": the moment's name, "when": "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM", "where": place or null,
  "free": true/false/null,
  "line": one warm, concrete French sentence that starts with the moment (day, time, what happens, where)
          and ends by naming the festival as its frame, e.g. "Dimanche 18 à 15 h, ... au parc ... : c'est l'un
          des temps forts des Forestivités."}}
Use only facts from the page. If the page gives no precise moment in that window, return {{"found": false}}.

PAGE:
{page}
"""


def is_umbrella(e: dict) -> bool:
    """A festival, a month of events, a run of days: worth zooming into one moment."""
    start, end = editorial._day(e.get("start")), editorial._day(e.get("end"))
    words = ("festival", "fête", "fete", "mois ", "semaine", "journées", "forestivit", "rencontres", "biennale")
    return bool(end and start and (end - start).days >= 2) or e.get("category") == "festival" \
        or any(w in e["title"].lower() for w in words)


def _programme(url: str, today: date) -> str:
    """The event page, plus its programme page when it links to one."""
    page = fetch("zoom", url, today, path=RAW / "details" / f"{details._key(url)}.html")
    text = clean.to_text(page, url, limit=60_000)
    # Follow the programme, or the organiser's own site (tourist office pages link to it).
    links = re.findall(r"\[([^\]]*)\]\((https?://[^)]+)\)", text)
    wanted = ("programm", "agenda", "site internet", "site web", "en savoir plus", "plus d'info")
    follow = next((u for label, u in links if any(w in label.lower() for w in wanted) and u != url), None)
    if follow:
        try:
            more = fetch("zoom", follow, today, path=RAW / "details" / f"{details._key(follow)}.html")
            text = text[:9000] + "\n\nPROGRAMME PAGE:\n" + clean.to_text(more, follow, limit=60_000)
        except Exception:  # noqa: BLE001 - the event page alone is still worth reading
            pass
    return text[:18_000]


def zoom(picks: list[dict], events: list[dict], today: date) -> None:
    """For each umbrella pick, one precise moment of its programme becomes the line."""
    edition = today

    def one(p):
        today = schedule.channel_day(edition, p["channel"])
        e = events[p["i"]]
        if not is_umbrella(e) or not e.get("url"):
            return
        first = max(today + timedelta(days=editorial.NOTICE_WALK_IN), editorial._day(e["start"]) or today)
        last = min(today + timedelta(days=editorial.WEEK if p["post"] == "week" else editorial.BOOK_AHEAD),
                   editorial._day(e.get("end")) or first)
        try:
            text = _programme(e["url"], today)
            brief = {k: e.get(k) for k in ("title", "start", "end", "venue", "town", "price", "description")}
            answer = ask(ZOOM_PROMPT.format(today=today.isoformat(), event=json.dumps(brief, ensure_ascii=False),
                                            first=first.isoformat(), last=max(first, last).isoformat(), page=text,
                                            free_only=" It is for the free channel: the moment MUST be free (written on the page)."
                                            if p.get("channel") == "gratuit" else ""),
                         timeout=300)
            z = json.loads(answer[answer.find("{"): answer.rfind("}") + 1])
        except Exception:  # noqa: BLE001 - no zoom: the general line stays
            return
        when = editorial._day(z.get("when"))
        # The moment must fall in the window asked: a session already past is no reason to go.
        if not when or not first <= when <= max(first, last):
            return
        if z.get("found") and z.get("line") and not (p.get("channel") == "gratuit" and z.get("free") is not True):
            p["zoom"] = {k: z.get(k) for k in ("what", "when", "where", "free")}
            p["line"] = z["line"]

    with cf.ThreadPoolExecutor(4) as ex:
        list(ex.map(one, picks))


def check(picks: list[dict], events: list[dict], today: date) -> None:
    """What a line says that its event's data and page do not (factcheck.py): shown on the board."""
    def one(p):
        e = events[p["i"]]
        try:
            page = _programme(e["url"], today) if e.get("url") else ""
        except Exception:  # noqa: BLE001 - checked against the data alone
            page = ""
        p["check"] = factcheck.check(p.get("line") or "", e, page)

    with cf.ThreadPoolExecutor(6) as ex:
        list(ex.map(one, picks))


def run(today: date | None = None) -> list[dict]:
    today = today or date.today()
    folder = DATA / "events" / today.isoformat()
    events = json.loads((folder / "reviewed.json").read_text())
    # Each group is written for its own sending day (schedule.py), not the day it is prepared.
    day = lambda channel: schedule.channel_day(today, channel)
    # The most specific groups choose first, so an event lands where it fits best.
    picks: list[dict] = []
    for channel in ORDER:
        picks += select(events, day(channel), channel, already=picks)
    zoom(picks, events, today)
    check(picks, events, today)
    (folder / "selection.json").write_text(json.dumps(picks, ensure_ascii=False, indent=1))
    return picks


if __name__ == "__main__":
    for p in run(date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else None):
        print(p["post"], p["i"], p["why"])
