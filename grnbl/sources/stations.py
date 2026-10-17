"""Fuel station names, which the official price feed does not give.

The feed has an id, an address and prices, no brand: "3 Av du Maréchal Randon"
means little, "Esso" does. OpenStreetMap knows the brand of almost every
station, and many carry the feed's own id (ref:FR:prix-carburants). The
stations of the Grenoble area are downloaded once a week and kept on disk;
a station is matched by that id, or else by the nearest one within 200 m.
"""

from __future__ import annotations

import json
import math
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

CACHE = Path(__file__).resolve().parents[2] / "data" / "osm-fuel.json"
MAX_AGE = 7 * 86400
# The public Overpass endpoints are often full; the first that answers wins.
MIRRORS = ["https://overpass-api.de/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
# Grenoble-Alpes Métropole and a margin: south, west, north, east.
BBOX = (44.95, 5.45, 45.35, 6.05)
QUERY = '[out:json][timeout:60];nwr["amenity"="fuel"]({},{},{},{});out tags center;'


def _download() -> list[dict]:
    body = urllib.parse.urlencode({"data": QUERY.format(*BBOX)}).encode()
    last = None
    for url in MIRRORS * 2:  # busy servers often answer on a second try
        try:
            req = urllib.request.Request(url, data=body, headers={"User-Agent": "grnbl/0.1 (+https://grnbl.xyz)"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.load(resp)
            out = []
            for el in data.get("elements", []):
                tags = el.get("tags", {})
                lat = el.get("lat") or (el.get("center") or {}).get("lat")
                lon = el.get("lon") or (el.get("center") or {}).get("lon")
                if lat is None:
                    continue
                out.append({"lat": lat, "lon": lon, "ref": tags.get("ref:FR:prix-carburants"),
                            "brand": tags.get("brand"), "name": tags.get("name")})
            return out
        except Exception as e:  # noqa: BLE001 - next mirror
            last = e
            time.sleep(2)
    raise RuntimeError(f"no Overpass mirror answered: {last}")


def osm_stations() -> list[dict]:
    if CACHE.exists() and time.time() - CACHE.stat().st_mtime < MAX_AGE:
        return json.loads(CACHE.read_text())
    try:
        stations = _download()
    except Exception:  # noqa: BLE001 - an old list beats no names
        return json.loads(CACHE.read_text()) if CACHE.exists() else []
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(stations, ensure_ascii=False))
    return stations


def _metres(lat1, lon1, lat2, lon2) -> float:
    k = math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot((lat2 - lat1) * 111_320, (lon2 - lon1) * 111_320 * k)


def label(osm: dict) -> str | None:
    """"Esso", "Carrefour Market", "Total Access": the brand, or the name when it says more."""
    brand = osm.get("brand")
    name = re.sub(r"^(station[- ](essence|service)|station)\s+", "", osm.get("name") or "", flags=re.I).strip() or None
    if brand and name:
        if name.lower().startswith(brand.lower()):
            return name
        return f"{brand} {name}" if brand.lower() not in name.lower() and len(name) < 30 else brand
    return brand or name


def name_for(station_id: str, lat: float | None, lon: float | None, osm: list[dict], within: float = 200) -> str | None:
    for s in osm:
        if s.get("ref") == station_id:
            return label(s)
    if lat is None or lon is None:
        return None
    near = min(osm, key=lambda s: _metres(lat, lon, s["lat"], s["lon"]), default=None)
    if near and _metres(lat, lon, near["lat"], near["lon"]) <= within:
        return label(near)
    return None
