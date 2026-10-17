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

from . import editorial
from .digest import chosen
from .scrape import clean, details
from .scrape.extract import ask, parse_array_raw
from .scrape.fetch import RAW, fetch

DATA = Path(__file__).resolve().parents[1] / "data"
CANDIDATES = 40

# Two channels, people join one or both. Which channel an event may go to is decided by code
# (is it free?), never by the AI: a paid event can never reach the free channel.
CHANNELS = {
    "gratuit": {
        "name": "grnbl · Gratuit",
        "promise": "only free outings: what costs nothing and is worth leaving the house for",
        "taste": "- only free things are offered to you here;\n"
                 "- the rare before the routine: a once-a-year opening beats an exhibition on a long run;",
    },
    "sorties": {
        "name": "grnbl · Sorties",
        "promise": "the best outings of the week, paid ones included: big concerts, shows, festivals, deals",
        "taste": "- paid things are welcome: a big concert or a show people will talk about deserves its place, and so\n"
                 "  does a discount or a good deal; a famous name is fine here when it is a real event;\n"
                 "- do not repeat what the free channel already posts (listed below), unless it is the event of the week;",
    },
}

PROMPT = """You are the editor of "{channel}", a WhatsApp channel for ordinary people of the Grenoble area
(families, students, retirees). Its promise: {promise}. The friend who always knows the good plans,
reliable and never boring. Today is {today}.

Below are the best candidates, already checked (dates, booking). Compose two posts:
- "to_book": up to {n_book} things to book NOW (timing book_now) or as soon as booking opens (opens_soon).
- "week": up to {n_week} things for the coming days that need no booking (timing this_week).

Choose them together, not one by one:
- variety: no more than two of the same kind (concert, exhibition, sport, kids, visit...);
- at least one for families with children;
{taste}
- buzz counts (press, several sources);
- leave out anything you would not tell a friend about: ordinary league matches, commercial routine.
The line uses only facts present in the candidate (title, dates, place, price, its line): never add a fact.
{already}
Return ONLY a JSON array, in the order the items should appear:
{{"i": <candidate i>, "post": "to_book" | "week", "why": short French reason for the editor (why this one),
  "line": the French line for the post: warm, factual, one sentence, the useful detail first}}

CANDIDATES:
{candidates}
"""


def _free(e: dict) -> bool | None:
    r = e.get("review") or {}
    return r.get("free") if r.get("free") is not None else e.get("free")


def candidates(events: list[dict], today: date, channel: str, n: int = CANDIDATES) -> list[tuple[int, dict]]:
    index = {id(e): i for i, e in enumerate(events)}
    pool = [e for e in chosen(events) if editorial.timing(e, today) in ("book_now", "opens_soon", "this_week")
            and (channel != "gratuit" or _free(e) is True)]
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


def select(events: list[dict], today: date, channel: str, n_book: int = 6, n_week: int = 8,
           already: list[dict] | None = None) -> list[dict]:
    pool = candidates(events, today, channel)
    if not pool:
        return []
    allowed = {i for i, _ in pool}
    c = CHANNELS[channel]
    taken = [events[p["i"]]["title"] for p in already or []]
    prompt = PROMPT.format(channel=c["name"], promise=c["promise"], taste=c["taste"], today=today.isoformat(),
                           n_book=n_book, n_week=n_week,
                           already=f"Already in the free channel: {json.dumps(taken, ensure_ascii=False)}\n" if taken else "",
                           candidates=json.dumps([_brief(i, e, today) for i, e in pool], ensure_ascii=False))
    picks = [p for p in parse_array_raw(ask(prompt, model="sonnet", timeout=600))
             if p.get("i") in allowed and p.get("post") in ("to_book", "week")]
    # The rules stay the rules: the post follows the timing, the channel is written on each pick.
    for p in picks:
        p["post"] = "week" if editorial.timing(events[p["i"]], today) == "this_week" else "to_book"
        p["channel"] = channel
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
    def one(p):
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
        if z.get("found") and z.get("line") and not (p.get("channel") == "gratuit" and z.get("free") is not True):
            p["zoom"] = {k: z.get(k) for k in ("what", "when", "where", "free")}
            p["line"] = z["line"]

    with cf.ThreadPoolExecutor(4) as ex:
        list(ex.map(one, picks))


def run(today: date | None = None) -> list[dict]:
    today = today or date.today()
    folder = DATA / "events" / today.isoformat()
    events = json.loads((folder / "reviewed.json").read_text())
    free = select(events, today, "gratuit")
    picks = free + select(events, today, "sorties", already=free)
    zoom(picks, events, today)
    (folder / "selection.json").write_text(json.dumps(picks, ensure_ascii=False, indent=1))
    return picks


if __name__ == "__main__":
    for p in run(date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else None):
        print(p["post"], p["i"], p["why"])
