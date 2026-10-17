"""The tourist office agenda, read in full: the biggest single list of what's on.

grenoble-tourisme.com publishes the regional tourism database (Apidae) for the
Grenoble area: over a thousand events, 11 per page, newest end date first. The
first page alone (what a generic scraper sees) is mostly long exhibitions, so
the one-off things that matter (a free tower visit on one Sunday, booked ten
days ahead) were never reached.

Here every listing page is walked, and each event's own page is read once and
kept on disk (data/raw/tourisme-details/), because its blocks are fixed:
dates, prices, opening periods. Code reads those. The AI is only asked about
the events whose page talks about booking, to get when booking opens and closes,
which is written in free text.
"""

from __future__ import annotations

import concurrent.futures as cf
import html as htmllib
import json
import re
import time
from datetime import date, timedelta
from pathlib import Path

from . import clean, extract
from .fetch import RAW, fetch

BASE = "https://www.grenoble-tourisme.com"
LIST = BASE + "/fr/decouvrir/evenements/agenda/?offset={offset}"
DETAILS = RAW / "tourisme-details"
SOURCE = {"id": "tourisme", "name": "Grenoble Alpes Tourisme", "url": BASE + "/fr/decouvrir/evenements/agenda/"}
DETAIL_MAX_AGE = timedelta(days=3)

MONTHS = {"janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
          "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12}
_M = "|".join(MONTHS)
# "Du 11 octobre au 1 novembre 2026", "Du 11 au 31 octobre 2026", "Le 18 octobre 2026", "Le dimanche 18 octobre 2026"
RANGE_RE = re.compile(rf"Du (\d{{1,2}})(?:er)?(?: ({_M}))?(?: (\d{{4}}))? au (\d{{1,2}})(?:er)? ({_M}) (\d{{4}})", re.I)
DAY_RE = re.compile(rf"Le (?:\w+ )?(\d{{1,2}})(?:er)? ({_M}) (\d{{4}})", re.I)
FREE_RE = re.compile(r"\b(gratuit|accès libre|entrée libre|libre participation)\b", re.I)
BOOKING_RE = re.compile(r"r[ée]serv|inscri|billetterie|complet", re.I)


def parse_cards(page: str) -> list[dict]:
    """The events listed on one agenda page: id, title, town, the end date shown, coordinates."""
    out = []
    for block in re.split(r"<li\s+id=\"id_result_", page)[1:]:
        block = block[: block.find("</li>")]
        link = re.search(r'href="(/fr/decouvrir/evenements/agenda/detail/[^"]*-(\d+)/)"', block)
        title = re.search(r"<h2>\s*(.*?)\s*</h2>", block, re.S)
        if not link or not title:
            continue
        text = htmllib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", block)))
        parts = [p.strip() for p in text.split("|") if p.strip() and "{%" not in p and "data-" not in p]
        until = re.search(r"Jusqu.au (\d{2})/(\d{2})/(\d{4})", text)
        lat = re.search(r'data-latitude="([\d.-]+)"', block)
        lon = re.search(r'data-longitude="([\d.-]+)"', block)
        name = htmllib.unescape(re.sub(r"\s+", " ", title.group(1))).strip()
        after = parts[parts.index(name) + 1:] if name in parts else []
        out.append({
            "id": link.group(2), "url": BASE + link.group(1), "title": name,
            "town": after[0] if after else None,
            "until": date(int(until.group(3)), int(until.group(2)), int(until.group(1))).isoformat() if until else None,
            "lat": float(lat.group(1)) if lat else None, "lon": float(lon.group(1)) if lon else None,
            "family": 'class="family"' in block,
        })
    return out


def walk_listing(today: date, refresh: bool = False, pause: float = 0.5) -> list[dict]:
    """Every card of the agenda, page after page, until a page comes back empty."""
    cards, seen, offset = [], set(), 0
    while offset < 3000:
        page = fetch("tourisme", LIST.format(offset=offset), today, refresh,
                     path=RAW / today.isoformat() / "tourisme" / f"list-{offset}.html")
        found = [c for c in parse_cards(page) if c["id"] not in seen]
        if not found:
            break
        for c in found:
            seen.add(c["id"])
        cards += found
        offset += 11
        time.sleep(pause)
    return cards


def detail_text(page: str, url: str) -> str:
    """The event's own block, from its title to the equipment list, links kept."""
    text = clean.to_text(page, url, limit=200_000)
    start = text.find("Nouvelle recherche")
    end = min([i for i in (text.find("Équipements et caractéristiques", start), text.find("Cliquez pour charger la carte", start),
                           text.find("À voir aussi", start)) if i > 0] or [start + 4000])
    block = text[start + len("Nouvelle recherche"):end] if start >= 0 else text[:4000]
    return re.sub(r"\[(Ajouter|Supprimer) [^\]]*\]\([^)]*\)", "", block).strip()[:4000]


def parse_dates(text: str) -> tuple[date, date] | None:
    """First and last day from the heading line under the title."""
    m = RANGE_RE.search(text)
    if m:
        d1, mo1, y1, d2, mo2, y2 = m.groups()
        end = date(int(y2), MONTHS[mo2.lower()], int(d2))
        start_month = MONTHS[mo1.lower()] if mo1 else end.month
        start_year = int(y1) if y1 else (end.year if start_month <= end.month else end.year - 1)
        return date(start_year, start_month, int(d1)), end
    m = DAY_RE.search(text)
    if m:
        d = date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
        return d, d
    return None


def section(text: str, title: str, stops: tuple[str, ...]) -> str | None:
    i = text.find(title)
    if i < 0:
        return None
    j = min([k for k in (text.find(s, i + len(title)) for s in stops) if k > 0] or [len(text)])
    return text[i + len(title):j].strip() or None


def event_from(card: dict, text: str) -> dict | None:
    dates = parse_dates(text[:600])
    if not dates:
        return None
    prices = section(text, "Tarifs", ("Périodes d’ouverture", "Périodes d'ouverture"))
    periods = section(text, "Périodes d’ouverture", ("Équipements",)) or section(text, "Périodes d'ouverture", ("Équipements",))
    body = text.split("\n")
    description = " ".join(l for l in body[2:12] if len(l) > 60)[:400] or None
    return {
        "title": card["title"], "start": dates[0].isoformat(),
        "end": dates[1].isoformat() if dates[1] != dates[0] else None,
        "venue": None, "town": card["town"], "price": prices,
        "free": True if prices and FREE_RE.search(prices) and not re.search(r"\d+\s*€", prices)
        else False if prices and re.search(r"\d", prices) else None,
        "url": card["url"], "category": None, "description": description,
        "periods": periods, "family": card["family"], "lat": card["lat"], "lon": card["lon"],
        "apidae": card["id"],
    }


BOOKING_PROMPT = """Below are event pages from the Grenoble tourist office. Today is {today}.
For EACH one, read what it says about booking or registration and return a JSON array, nothing else:
{{"apidae": <its id>, "booking": "required" | "recommended" | "none" | null,
  "booking_opens": "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM" or null (when booking or registration opens, only if written),
  "booking_deadline": same format or null (last day to book, only if written),
  "booking_url": absolute link where people book, or null,
  "sold_out": true only if the page says it is full ("complet"),
  "venue": the place name or null}}
Copy facts only. If the year is missing, use the next occurrence before the event.

PAGES:
{pages}
"""


def add_booking(events: list[dict], texts: dict[str, str], today: date, batch: int = 12) -> None:
    """Asks the AI about booking only for pages that mention it; others get booking=None."""
    asking = [e for e in events if BOOKING_RE.search(texts[e["apidae"]])]
    for e in events:
        e.update({"booking": None, "booking_opens": None, "booking_deadline": None, "booking_url": None, "sold_out": False})
    by_id = {e["apidae"]: e for e in events}

    def one(chunk):
        pages = "\n\n".join(f"--- id {e['apidae']} ---\n{texts[e['apidae']][:2500]}" for e in chunk)
        return extract.parse_array_raw(extract.ask(BOOKING_PROMPT.format(today=today.isoformat(), pages=pages)))

    chunks = [asking[i:i + batch] for i in range(0, len(asking), batch)]
    with cf.ThreadPoolExecutor(4) as ex:
        for answers in ex.map(lambda c: _safe(one, c), chunks):
            for a in answers:
                e = by_id.get(str(a.get("apidae")))
                if e:
                    for k in ("booking", "booking_opens", "booking_deadline", "booking_url", "venue"):
                        if a.get(k):
                            e[k] = a[k]
                    e["sold_out"] = a.get("sold_out") is True


def _safe(fn, arg):
    try:
        return fn(arg)
    except Exception:  # noqa: BLE001 - one failed batch leaves those events without booking info
        return []


def events(today: date, horizon: timedelta, refresh: bool = False) -> list[dict]:
    cards = walk_listing(today, refresh)
    cards = [c for c in cards if not c["until"] or c["until"] >= today.isoformat()]
    DETAILS.mkdir(parents=True, exist_ok=True)

    def read(card):
        path = DETAILS / f"{card['id']}.html"
        stale = not path.exists() or time.time() - path.stat().st_mtime > DETAIL_MAX_AGE.total_seconds()
        try:
            page = fetch("tourisme", card["url"], today, refresh=stale or refresh, path=path)
        except Exception:  # noqa: BLE001 - a missing page drops one event, not the source
            return card, None
        return card, detail_text(page, card["url"])

    texts, out = {}, []
    with cf.ThreadPoolExecutor(6) as ex:
        for card, text in ex.map(read, cards):
            if not text:
                continue
            e = event_from(card, text)
            if not e or e["start"] > (today + horizon).isoformat() or (e["end"] or e["start"]) < today.isoformat():
                continue
            texts[card["id"]] = text
            out.append(e)
    add_booking(out, texts, today)
    return out


if __name__ == "__main__":
    found = events(date.today(), timedelta(days=60))
    print(json.dumps(found[:5], ensure_ascii=False, indent=1), len(found))
