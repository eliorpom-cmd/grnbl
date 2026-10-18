"""Runs every source and writes what it found.

data/raw/<day>/<source>.html     the pages as downloaded
data/events/<day>/<source>.json  the events of each source, as extracted
data/events/<day>/all.json       everything, merged and deduplicated, ready for the review

One failing source never stops the others: it is reported and skipped.
"""

from __future__ import annotations

import concurrent.futures as cf
import json
import re
import time
import unicodedata
from datetime import date, timedelta
from pathlib import Path

from . import clean, details, extract, jsonld, press, tourisme, tribe
from .. import editorial
from ..editorial import POSTABLE
from .fetch import fetch
from .sources import SOURCES

DATA = Path(__file__).resolve().parents[2] / "data"
# Far enough to catch what must be booked weeks ahead.
HORIZON = timedelta(days=60)


def _key(e: dict) -> str:
    """Same event announced by two sources: same normalised title, same day."""
    t = unicodedata.normalize("NFKD", e["title"]).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    return f"{t}|{str(e['start'])[:10]}"


def _series_key(e: dict) -> str:
    t = unicodedata.normalize("NFKD", f"{e['title']}|{e.get('venue') or ''}").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9|]+", " ", t.lower()).strip()


def collapse(events: list[dict]) -> list[dict]:
    """The same session repeated through the weeks (a guided tour every Sunday) is one
    event with its dates, not a dozen lines for the review to judge one by one."""
    groups: dict[str, list[dict]] = {}
    for e in events:
        groups.setdefault(_series_key(e), []).append(e)
    out = []
    for group in groups.values():
        group.sort(key=lambda e: str(e["start"]))
        first = group[0]
        if len(group) > 1:
            first["dates"] = [str(e["start"]) for e in group]
            for e in group[1:]:
                for k, v in e.items():  # a later session may say what the first one does not
                    if first.get(k) in (None, "") and v not in (None, ""):
                        first[k] = v
        out.append(first)
    return out


def next_postable(e: dict, today: date) -> None:
    """A series starts on its first session that can still be announced: when
    the next one is too close to book, the one after is posted instead."""
    for d in e.get("dates") or []:
        if editorial.timing({**e, "start": d, "end": None}, today) in POSTABLE:
            if d != e["start"]:
                e["start"], e["end"] = d, None
            return


def _ai_pages(source: dict, today: date, refresh: bool) -> list[dict]:
    """An agenda read by the AI, following its next pages while they still hold
    events within the horizon. `next` is the URL of page {n}, from `first` on."""
    until, found, seen = today + HORIZON, [], set()
    pages = [(source["id"], source["url"])]
    if source.get("next"):
        first = source.get("first", 2)
        pages += [(f"{source['id']}-p{n}", source["next"].format(n=n))
                  for n in range(first, first + source.get("max_pages", 8))]
    for i, (page_id, url) in enumerate(pages):
        text = clean.to_text(fetch(page_id, url, today, refresh), url)
        digest = extract.text_hash(text)
        if digest in seen:  # past the last page, the site repeats one
            break
        seen.add(digest)
        got = extract.events(text, {**source, "id": page_id}, today, until)
        found += got
        if i and not got:
            break
    return found


def run_source(source: dict, today: date, refresh: bool = False) -> tuple[str, list[dict], str | None]:
    out_path = DATA / "events" / today.isoformat() / f"{source['id']}.json"
    if out_path.exists() and not refresh:
        return source["id"], json.loads(out_path.read_text()), None
    try:
        if source["kind"] == "tourisme":
            found = tourisme.events(today, HORIZON, refresh)
        elif source["kind"] == "press":
            paper = next(p for p in press.PAPERS if p["id"] == source["id"])
            found = press.events(paper, today, HORIZON)
        elif source["kind"] == "tribe":
            found = tribe.events(source, today, today + HORIZON, refresh)
        elif source["kind"] == "jsonld":
            html = fetch(source["id"], source["url"], today, refresh)
            found = jsonld.events(html)
        else:
            found = _ai_pages(source, today, refresh)
    except Exception as e:  # noqa: BLE001 - reported, the run goes on
        return source["id"], [], str(e)[:200]
    for e in found:
        e["source"] = source["id"]
        e["source_name"] = source["name"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(found, ensure_ascii=False, indent=1))
    return source["id"], found, None


def run_all(today: date | None = None, only: list[str] | None = None, refresh: bool = False, workers: int = 6):
    today = today or date.today()
    chosen = [s for s in SOURCES if not only or s["id"] in only]
    report, merged = [], {}
    t0 = time.time()
    with cf.ThreadPoolExecutor(workers) as ex:
        for sid, found, err in ex.map(lambda s: run_source(s, today, refresh), chosen):
            report.append((sid, len(found), err))
            for e in found:
                k = _key(e)
                if k in merged:
                    merged[k].setdefault("also", []).append(e["source"])
                else:
                    merged[k] = e
    found = collapse(list(merged.values()))
    report.append(("series", len(merged) - len(found), None))
    # Each event's own page, for how and when to book.
    filled = details.enrich(found, today)
    for e in found:
        next_postable(e, today)
    merged = {_key(e): e for e in found}
    report.append(("details", filled, None))
    # The yearly rendez-vous; a scraped event with the same title and day is kept instead.
    cal, watch = editorial.calendar_events(today)
    for e in cal:
        merged.setdefault(_key(e), e)
    report.append(("calendar", len(cal), None))
    events = sorted(merged.values(), key=lambda e: str(e["start"]))
    folder = DATA / "events" / today.isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "all.json").write_text(json.dumps(events, ensure_ascii=False, indent=1))
    (folder / "watch.json").write_text(json.dumps(watch, ensure_ascii=False, indent=1))
    return report, events, time.time() - t0
