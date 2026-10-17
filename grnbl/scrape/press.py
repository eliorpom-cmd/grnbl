"""Local press: the articles that announce an outing before agendas list it.

Agendas say what is on; journalists say what is worth it, and often first: the
free Tour Perret visit of the 2026 architecture days was in L'Essentiel, not in
the tourist office database. Each paper's front pages are read for recent
article links, each new article is read once, and the AI pulls out the events
it announces, with how and when to book. An article's events are kept on disk
(data/press/), so a daily run only reads what was published since.
"""

from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import re
import urllib.parse
from datetime import date, timedelta
from pathlib import Path

from . import clean, extract
from .fetch import RAW, fetch

DATA = Path(__file__).resolve().parents[2] / "data"
CACHE = DATA / "press"

# index: pages listing recent articles. article: what an article link looks like;
# a "date" group (YYYY-MM-DD or YYYY/MM/DD) lets old articles be skipped without reading them.
PAPERS = [
    {"id": "press-lessentiel", "name": "L'Essentiel Grenoble",
     "index": ["https://www.lessentiel.fr/grenoble"],
     "article": r"/grenoble/(?:idees-sorties|environnement|sante|bonnes-adresses|notre-ville)/(?P<date>\d{4}-\d{2}-\d{2})/[^\"'#?]+"},
    {"id": "press-dauphine", "name": "Le Dauphiné libéré",
     "index": ["https://www.ledauphine.com/isere-sud/grenoble", "https://www.ledauphine.com/culture-loisirs"],
     "article": r"/(?:culture-loisirs|loisirs|sortir|patrimoine)/(?P<date>\d{4}/\d{2}/\d{2})/[^\"'#?]+"},
    {"id": "press-placegrenet", "name": "Place Gre'net",
     "index": ["https://www.placegrenet.fr/category/culture", "https://www.placegrenet.fr/"],
     "article": r"https://www\.placegrenet\.fr/(?P<date>\d{4}/\d{2}/\d{2})/[^\"'#?]+"},
    {"id": "press-ici", "name": "ICI Isère",
     "index": ["https://www.francebleu.fr/isere"],
     "article": r"/auvergne-rhone-alpes/isere-38/[a-z-]+/[a-z0-9-]*(?:sortie|festival|concert|gratuit|visite|expo|fete|spectacle|week-end|salon|marche|journees?)[a-z0-9-]*-\d+"},
    {"id": "press-petitbulletin", "name": "Le Petit Bulletin Grenoble",
     "index": ["https://www.petit-bulletin.fr/grenoble/"],
     "article": r"(?:https://www\.petit-bulletin\.fr/grenoble/)?article-\d+-[a-z0-9-]+\.html"},
]

PROMPT = """You read an article from the local press of Grenoble (France). Today is {today}.
Article: {url} ({paper}, published {published}).

List every event the article tells readers they can attend between {today} and {until}, in or near
Grenoble (about 30 km). Return ONLY a JSON array, [] if there is none (a report on a past event, news,
an opinion piece). One object per event:
{{"title": str, "start": "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM", "end": same or null,
  "venue": str or null, "town": str or null, "price": str or null, "free": true/false/null,
  "url": the event's own link if the article gives one, else null,
  "category": one of {cats}, "description": one short factual French sentence,
  "booking": "required" | "recommended" | "none" | null,
  "booking_opens": "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM" or null, "booking_deadline": same or null,
  "booking_url": str or null, "sold_out": true/false}}
Copy facts only, never invent a date, a price or a place. A missing year means the next occurrence.

ARTICLE:
{text}
"""


def article_links(paper: dict, page: str, base: str) -> list[str]:
    links = []
    for m in re.finditer(paper["article"], page):
        url = urllib.parse.urljoin(base, m.group(0))
        if url not in links:
            links.append(url)
    return links


def published(paper: dict, url: str) -> date | None:
    m = re.search(paper["article"], url)
    if m and "date" in m.groupdict() and m.group("date"):
        return date.fromisoformat(m.group("date").replace("/", "-"))
    return None


def _key(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def read_article(paper: dict, url: str, today: date, until: date) -> list[dict]:
    """The events of one article, from the disk if it was read before."""
    cached = CACHE / f"{_key(url)}.json"
    if cached.exists():
        return json.loads(cached.read_text())["events"]
    page = fetch(paper["id"], url, today, path=RAW / "press" / f"{_key(url)}.html")
    text = clean.to_text(page, url, limit=14_000)
    day = published(paper, url)
    answer = extract.ask(PROMPT.format(today=today.isoformat(), until=until.isoformat(), url=url, paper=paper["name"],
                                       published=day.isoformat() if day else "recently",
                                       cats=", ".join(extract.CATEGORIES), text=text))
    found = extract.parse_array(answer)
    for e in found:
        e["article"] = url
        e["url"] = e.get("url") or url
    CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps({"url": url, "read": today.isoformat(), "events": found}, ensure_ascii=False, indent=1))
    return found


def events(paper: dict, today: date, horizon: timedelta, max_age: timedelta = timedelta(days=14),
           max_undated: int = 25) -> list[dict]:
    links: list[str] = []
    for i, index in enumerate(paper["index"]):
        page = fetch(paper["id"], index, today, path=RAW / today.isoformat() / f"{paper['id']}-{i}.html")
        links += [l for l in article_links(paper, page, index) if l not in links]
    dated = [l for l in links if published(paper, l)]
    fresh = [l for l in dated if published(paper, l) >= today - max_age]
    undated = [l for l in links if not published(paper, l)][:max_undated]
    out = []
    with cf.ThreadPoolExecutor(4) as ex:
        results = ex.map(lambda u: _safe(read_article, paper, u, today, today + horizon), fresh + undated)
        for found in results:
            out += found
    return [e for e in out if str(e.get("end") or e["start"])[:10] >= today.isoformat()]


def _safe(fn, *args):
    try:
        return fn(*args)
    except Exception:  # noqa: BLE001 - one unreadable article is skipped, the paper goes on
        return []
