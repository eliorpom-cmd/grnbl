"""Opens each event's own page to learn how and when to book.

Agenda lists rarely say it; the event page does ("Ouverture de la billetterie
le 7 octobre à 9h30. La réservation d'un créneau est obligatoire."). For every
event still without booking information, its page is read (kept on disk for
three days, data/details/) and the AI fills the booking fields, a dozen pages
per call.
"""

from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import time
from datetime import date, timedelta
from pathlib import Path

from . import clean, extract
from .fetch import RAW, fetch

DATA = Path(__file__).resolve().parents[2] / "data"
CACHE = DATA / "details"
MAX_AGE = timedelta(days=3)
FIELDS = ("booking", "booking_opens", "booking_deadline", "booking_url", "sold_out", "price", "free")

PROMPT = """Below are pages of events in the Grenoble area. Today is {today}.
For EACH page, return what it says about booking, in a JSON array, nothing else:
{{"k": <the page key>, "booking": "required" | "recommended" | "none" | null,
  "booking_opens": "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM" or null (when booking or registration opens, only if written),
  "booking_deadline": same or null, "booking_url": absolute link where people book or null,
  "sold_out": true only if the page says "complet", "price": as written or null, "free": true/false/null}}
Copy facts only. If the year is missing, use the occurrence before the event.

PAGES:
{pages}
"""


def _key(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def _fresh(path: Path) -> bool:
    return path.exists() and time.time() - path.stat().st_mtime < MAX_AGE.total_seconds()


def needs_page(e: dict, today: date) -> bool:
    url = e.get("url") or ""
    return (e.get("booking") is None and url.startswith("http") and not e.get("article")
            and str(e.get("end") or e["start"])[:10] >= (today + timedelta(days=1)).isoformat()
            and e.get("source") not in ("tourisme", "calendar"))


def enrich(events: list[dict], today: date, batch: int = 12) -> int:
    """Fills booking fields in place; returns how many events got some."""
    todo = [e for e in events if needs_page(e, today)]
    CACHE.mkdir(parents=True, exist_ok=True)
    known, ask_for = {}, []
    for e in todo:
        cached = CACHE / f"{_key(e['url'])}.json"
        if _fresh(cached):
            known[e["url"]] = json.loads(cached.read_text())
        elif e["url"] not in [x["url"] for x in ask_for]:
            ask_for.append(e)

    def read(e):
        try:
            page = fetch("detail", e["url"], today, path=RAW / "details" / f"{_key(e['url'])}.html")
            return e["url"], clean.to_text(page, e["url"], limit=60_000)
        except Exception:  # noqa: BLE001 - an unreachable page leaves the event as it was
            return e["url"], None

    with cf.ThreadPoolExecutor(6) as ex:
        texts = {u: t for u, t in ex.map(read, ask_for) if t}

    def text_for(url):
        # Pages carry menus first: keep the part around the event title when it is found.
        t = texts[url]
        title = next((e["title"] for e in ask_for if e["url"] == url), "")
        i = t.find(title[:30]) if title else -1
        return t[max(0, i - 200): max(0, i - 200) + 3000] if i >= 0 else t[:3000]

    urls = list(texts)
    chunks = [urls[i:i + batch] for i in range(0, len(urls), batch)]

    def one(chunk):
        pages = "\n\n".join(f"--- k {_key(u)} ---\n{text_for(u)}" for u in chunk)
        try:
            return chunk, extract.parse_array_raw(extract.ask(PROMPT.format(today=today.isoformat(), pages=pages)))
        except Exception:  # noqa: BLE001 - a failed batch is retried on the next run
            return chunk, None

    with cf.ThreadPoolExecutor(4) as ex:
        for chunk, answers in ex.map(one, chunks):
            if answers is None:
                continue
            by_k = {str(a.get("k")): a for a in answers}
            for u in chunk:
                info = {f: by_k.get(_key(u), {}).get(f) for f in FIELDS}
                (CACHE / f"{_key(u)}.json").write_text(json.dumps(info, ensure_ascii=False))
                known[u] = info

    filled = 0
    for e in todo:
        info = known.get(e["url"]) or {}
        if info.get("booking"):
            filled += 1
        for f in FIELDS:
            if info.get(f) is not None and e.get(f) in (None, False, ""):
                e[f] = info[f]
    return filled
