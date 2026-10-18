"""WordPress sites running The Events Calendar: their REST API, read by code, no AI.

Many venues (MC2, Le Ciel, Seyssinet-Pariset) use this plugin. Its API
(/wp-json/tribe/events/v1/events) lists the whole season with times, prices
and venues, where the agenda page only shows its first screen.
"""

from __future__ import annotations

import html as htmllib
import json
import re
import urllib.parse
from datetime import date

from .fetch import fetch

_TAG = re.compile(r"<[^>]+>")
# Page-builder shortcodes left in the text ([et_pb_section …]).
_SHORTCODE = re.compile(r"\[/?[a-z_]+[^\]]*\]")

# Words in the site's own category names, to the shared categories (extract.CATEGORIES).
_CATS = [
    ("concert", ("concert", "musique", "jazz", "rock", "chanson", "rap", "électro", "opéra", "classique")),
    ("theatre", ("théâtre", "theatre", "marionnette", "cirque")),
    ("dance", ("danse",)),
    ("humour", ("humour", "stand-up", "one man")),
    ("cinema", ("ciné", "cine", "film", "projection")),
    ("exhibition", ("expo",)),
    ("kids", ("jeune public", "enfant", "famille")),
    ("talk", ("conférence", "rencontre", "débat", "lecture")),
    ("workshop", ("atelier", "stage")),
    ("festival", ("festival",)),
    ("market", ("marché", "brocante", "vide-grenier")),
    ("sport", ("sport",)),
]


def _text(s: str | None) -> str:
    s = _SHORTCODE.sub(" ", htmllib.unescape(_TAG.sub(" ", s or "")))
    return re.sub(r"\s+", " ", s).strip()


def _category(e: dict) -> str | None:
    names = " ".join(c.get("name", "") for c in e.get("categories") or [])
    names += " " + " ".join(str(f.get("value", "")) for f in (e.get("custom_fields") or {}).values()
                            if isinstance(f, dict))
    names = names.lower()
    if not names.strip():
        return None
    return next((cat for cat, words in _CATS if any(w in names for w in words)), "other")


def _when(e: dict, key: str) -> str | None:
    """'2026-11-04 20:00:00' -> '2026-11-04T20:00', or the day alone for all-day events."""
    v = e.get(key)
    if not v:
        return None
    return v[:10] if e.get("all_day") else v[:16].replace(" ", "T")


def convert(e: dict, source: dict | None = None) -> dict:
    """`source` may give "place" and "town": the venue's own name, for sites whose
    rooms are listed alone ("Auditorium" at the MC2)."""
    source = source or {}
    venue = e.get("venue") if isinstance(e.get("venue"), dict) else {}
    room = _text(venue.get("venue")) or None
    place = source.get("place")
    if place and (not room or place.lower() not in room.lower()):
        room = f"{place}, {room}" if room else place
    cost = _text(e.get("cost")) or None
    values = (e.get("cost_details") or {}).get("values") or []
    free = None
    if cost and re.search(r"gratuit|entrée libre|libre participation", cost, re.I):
        free = True
    elif values:
        free = all(str(v) in ("0", "0.0") for v in values)
    end = _when(e, "end_date")
    start = _when(e, "start_date")
    return {
        "title": _text(e.get("title")),
        "start": start,
        "end": end if end and end != start else None,
        "venue": room,
        "town": _text(venue.get("city")) or source.get("town"),
        "price": cost,
        "free": free,
        "url": e.get("url"),
        "category": _category(e),
        "description": max(_text(e.get("excerpt")), _text(e.get("description")), key=len)[:300] or None,
    }


def events(source: dict, today: date, until: date, refresh: bool = False, max_pages: int = 10) -> list[dict]:
    root = "https://" + urllib.parse.urlparse(source["url"]).netloc
    query = urllib.parse.urlencode({"per_page": 50, "start_date": today.isoformat(),
                                    "end_date": until.isoformat() + " 23:59:59"})
    url, out = f"{root}/wp-json/tribe/events/v1/events?{query}", []
    for page in range(1, max_pages + 1):
        data = json.loads(fetch(f"{source['id']}-api-{page}", url, today, refresh))
        out += [convert(e, source) for e in data.get("events") or []]
        url = data.get("next_rest_url")
        if not url:
            break
    return [e for e in out if e["title"] and e["start"]]
