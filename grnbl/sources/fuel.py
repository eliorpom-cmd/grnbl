"""Fuel prices across Grenoble-Alpes Métropole, from the official real-time feed.

Source: "Prix des carburants en France - flux instantané" (French Ministry of the
Economy), refreshed every few minutes, no key. Stations are kept when their
postal code belongs to one of the 49 communes of the Métropole.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median

from ..http import get_json
from ..items import Item

FEED = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/prix-des-carburants-en-france-flux-instantane-v2/records"
METRO_EPCI = "200040715"  # Grenoble-Alpes Métropole
FUELS = {"gazole": "Diesel (gazole)", "e10": "SP95-E10", "sp98": "SP98", "sp95": "SP95", "e85": "E85", "gplc": "GPL"}
# A price nobody has confirmed for this long is not today's price.
MAX_AGE = timedelta(days=3)
TANK_LITRES = 50


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
        return now - datetime.fromisoformat(stamp) <= MAX_AGE
    except ValueError:
        return False


def cheapest_by_fuel(stations: list[dict], now: datetime | None = None) -> list[Item]:
    """One item per fuel: the cheapest station, with how much it saves on a tank."""
    now = now or datetime.now(timezone.utc)
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
        prices = [p for p, _ in offers]
        items.append(
            Item(
                id=f"fuel:{key}:{best['id']}",
                topic="fuel",
                title=f"{label} le moins cher : {price:.3f} €".replace(".", ","),
                text=f"{best['adresse'].title()}, {best['ville'].title()}",
                place=best["ville"].title(),
                lat=float(best["latitude"]) if best.get("latitude") else None,
                lon=float(best["longitude"]) if best.get("longitude") else None,
                data={
                    "fuel": key,
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
    return cheapest_by_fuel(fetch_stations(metro_postcodes()))
