"""schema.org Event data embedded in a page (JSON-LD): read by code, no AI."""

from __future__ import annotations

import html as htmllib
import json
import re

_LD = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)


def _walk(node):
    if isinstance(node, list):
        for n in node:
            yield from _walk(n)
    elif isinstance(node, dict):
        t = node.get("@type")
        types = t if isinstance(t, list) else [t]
        if any(isinstance(x, str) and x.endswith("Event") for x in types):
            yield node
        for key in ("@graph", "itemListElement", "item", "subEvent"):
            if key in node:
                yield from _walk(node[key])


def _place(loc) -> tuple[str | None, str | None]:
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if not isinstance(loc, dict):
        return (loc if isinstance(loc, str) else None), None
    addr = loc.get("address")
    town = addr.get("addressLocality") if isinstance(addr, dict) else (addr if isinstance(addr, str) else None)
    return loc.get("name"), town


def _iso(raw) -> str | None:
    """'18/10/2026' or '2026-10-18T09:00:00+02:00' to the shared shape: '2026-10-18', '2026-10-18T09:00'."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    raw = raw.strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})(?:\D+(\d{1,2})[:h](\d{2}))?", raw)
    if m:
        d, mo, y, h, mi = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}" + (f"T{int(h):02d}:{mi}" if h else "")
    m = re.match(r"(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2}))?", raw)
    if not m:
        return None
    return m.group(1) + (f"T{m.group(2)}" if m.group(2) and m.group(2) != "00:00" else "")


def _town(raw: str | None) -> str | None:
    """'Grenoble-38' (department appended by some sites) to 'Grenoble'."""
    return re.sub(r"-\d{2,3}$", "", raw.strip()) if isinstance(raw, str) and raw.strip() else None


def events(html: str) -> list[dict]:
    """Raw events in the common extraction shape (see extract.py)."""
    out = []
    for block in _LD.findall(html):
        try:
            data = json.loads(htmllib.unescape(block.strip()))
        except json.JSONDecodeError:
            continue
        for e in _walk(data):
            venue, town = _place(e.get("location"))
            offers = e.get("offers")
            offer = offers[0] if isinstance(offers, list) and offers else offers if isinstance(offers, dict) else {}
            price = offer.get("price") if isinstance(offer, dict) else None
            out.append({
                "title": (e.get("name") or "").strip(),
                "start": _iso(e.get("startDate")),
                "end": _iso(e.get("endDate")),
                "venue": venue,
                "town": _town(town),
                "price": None if price in (None, "") else str(price),
                "free": True if str(price) in ("0", "0.0", "0.00") or e.get("isAccessibleForFree") is True else None,
                "url": e.get("url"),
                "category": None,
                "description": (e.get("description") or "")[:300],
            })
    return [e for e in out if e["title"] and e["start"]]
