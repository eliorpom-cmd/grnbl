"""Fuel prices across Grenoble-Alpes Métropole, from the official real-time feed.

Source: "Prix des carburants en France - flux instantané" (French Ministry of the
Economy), refreshed every few minutes, no key. Stations are kept when their
postal code belongs to one of the 49 communes of the Métropole.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median
from zoneinfo import ZoneInfo

from ..http import get_json
from ..items import Item
from .stations import name_for, osm_stations

FEED = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/prix-des-carburants-en-france-flux-instantane-v2/records"
METRO_EPCI = "200040715"  # Grenoble-Alpes Métropole
FUELS = {"gazole": "Diesel (gazole)", "e10": "SP95-E10", "sp98": "SP98", "sp95": "SP95", "e85": "E85", "gplc": "GPL"}
# A price nobody has confirmed for this long is not today's price.
MAX_AGE = timedelta(days=3)
TANK_LITRES = 50
PARIS = ZoneInfo("Europe/Paris")


def metro_postcodes() -> set[str]:
    communes = get_json(f"https://geo.api.gouv.fr/epcis/{METRO_EPCI}/communes", {"fields": "codesPostaux"})
    return {cp for c in communes for cp in c.get("codesPostaux", [])}


def fetch_stations(postcodes: set[str]) -> list[dict]:
    quoted = ",".join(f'"{cp}"' for cp in sorted(postcodes))
    stations, offset = [], 0
    while True:
        page = get_json(FEED, {"where": f"cp in ({quoted})", "limit": 100, "offset": offset})
        stations += page.get("results", [])
        offset += 100
        if offset >= page.get("total_count", 0):
            return stations


def _fresh(stamp: str | None, now: datetime) -> bool:
    if not stamp:
        return False
    try:
        at = datetime.fromisoformat(stamp)
    except ValueError:
        return False
    # The feed gives an offset today; a stamp without one is read as French time rather than crash the post.
    return now - (at if at.tzinfo else at.replace(tzinfo=PARIS)) <= MAX_AGE


def _coords(s: dict) -> tuple[float | None, float | None]:
    geom = s.get("geom") or {}
    if isinstance(geom, dict) and geom.get("lat"):
        return geom["lat"], geom["lon"]
    try:
        return float(s["latitude"]) / 100_000, float(s["longitude"]) / 100_000
    except (KeyError, TypeError, ValueError):
        return None, None


def cheapest_by_fuel(stations: list[dict], now: datetime | None = None, osm: list[dict] | None = None) -> list[Item]:
    """One item per fuel: the cheapest station, with how much it saves on a tank."""
    now = now or datetime.now(timezone.utc)
    osm = osm or []
    items = []
    for key, label in FUELS.items():
        offers = [
            (float(s[f"{key}_prix"]), s)
            for s in stations
            if s.get(f"{key}_prix") and _fresh(s.get(f"{key}_maj"), now)
        ]
        if len(offers) < 2:
            continue
        offers.sort(key=lambda o: o[0])
        price, best = offers[0]
        top = offers[-1][0]
        # The three cheapest stations, ties included in order of the feed.
        podium = [
            {"price": p, "address": s["adresse"].title(), "town": s["ville"].title(),
             "name": name_for(str(s["id"]), *_coords(s), osm)}
            for p, s in offers[:3]
        ]
        prices = [p for p, _ in offers]
        lat, lon = _coords(best)
        items.append(
            Item(
                id=f"fuel:{key}:{best['id']}",
                topic="fuel",
                title=f"{label} le moins cher : {price:.3f} €".replace(".", ","),
                text=f"{best['adresse'].title()}, {best['ville'].title()}",
                place=best["ville"].title(),
                lat=lat,
                lon=lon,
                data={
                    "fuel": key,
                    "top3": podium,
                    "label": label,
                    "price": price,
                    "max": top,
                    "median": median(prices),
                    "stations": len(offers),
                    "saving_tank": round((top - price) * TANK_LITRES, 2),
                    "saving_vs_median": round((median(prices) - price) * TANK_LITRES, 2),
                },
            )
        )
    return items


def collect() -> list[Item]:
    return cheapest_by_fuel(fetch_stations(metro_postcodes()), osm=osm_stations())
