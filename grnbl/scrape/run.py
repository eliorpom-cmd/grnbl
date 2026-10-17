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

from . import clean, details, extract, jsonld, press, tourisme
from .. import editorial
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
        elif source["kind"] == "jsonld":
            html = fetch(source["id"], source["url"], today, refresh)
            found = jsonld.events(html)
        else:
            html = fetch(source["id"], source["url"], today, refresh)
            text = clean.to_text(html, source["url"])
            found = extract.events(text, source, today, today + HORIZON)
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
    # Each event's own page, for how and when to book.
    filled = details.enrich(list(merged.values()), today)
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
