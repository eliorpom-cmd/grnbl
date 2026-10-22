"""Events at the Isère département museums in the Métropole (most of them free).

Source: "Agenda des musées départementaux" on opendata.isere.fr (an export of
Apidae, the regional tourism database), updated daily, no key. Dates only exist
as French text ("Dimanche 1er novembre 2026 de 14h30 à 16h."), so they are
parsed here.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from ..http import get_json
from ..items import Item

FEED = "https://opendata.isere.fr/api/explore/v2.1/catalog/datasets/agenda-musee-dep/records"
METRO_EPCI = "200040715"
PARIS = ZoneInfo("Europe/Paris")

MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "décembre": 12, "decembre": 12,
}
_HOUR = r"(\d{1,2})h(\d{2})?"
# "Dimanche 1er novembre 2026 de 14h30 à 16h." / "Jeudi 12 novembre 2026 à partir de 18h30."
DAY_RE = re.compile(
    rf"(\d{{1,2}})(?:er)?\s+({'|'.join(MONTHS)})\s+(\d{{4}})"
    rf"(?:\s+(?:de|à partir de)\s+{_HOUR})?(?:\s+à\s+{_HOUR})?",
    re.IGNORECASE,
)
# "Du 25/04/2026 au 25/04/2027 ..." - an exhibition, open on its usual days.
RANGE_RE = re.compile(r"Du\s+(\d{2})/(\d{2})(?:/(\d{4}))?\s+au\s+(\d{2})/(\d{2})(?:/(\d{4}))?", re.IGNORECASE)


def _at(d: date, h: str | None, m: str | None) -> datetime:
    t = time(int(h), int(m or 0)) if h else time(0, 0)
    return datetime.combine(d, t, PARIS)


def parse_occurrences(text: str) -> list[tuple[datetime, datetime | None]]:
    """Dated sessions in the text, in order. Empty when it only gives a range."""
    out = []
    for day, month, year, h1, m1, h2, m2 in DAY_RE.findall(text or ""):
        try:
            d = date(int(year), MONTHS[month.lower()], int(day))
            start = _at(d, h1 or None, m1 or None)
            end = _at(d, h2, m2) if h2 else None
        except ValueError:  # a typo on the page ("31 novembre", "25h") skips that session, not the source
            continue
        out.append((start, end))
    return sorted(out)


def parse_range(text: str, today: date) -> tuple[date, date] | None:
    """An exhibition's opening and closing dates; a missing year means this year."""
    m = RANGE_RE.search(text or "")
    if not m:
        return None
    d1, mo1, y1, d2, mo2, y2 = m.groups()
    start = date(int(y1 or today.year), int(mo1), int(d1))
    end = date(int(y2 or y1 or today.year), int(mo2), int(d2))
    return start, end


def items_from(records: list[dict], now: datetime, horizon: timedelta = timedelta(days=14)) -> list[Item]:
    """One item per upcoming session within the horizon, plus exhibitions open now."""
    out = []
    for r in records:
        text = r.get("horaires_ouverture") or ""
        # Sold out: nothing to tell people about.
        if "COMPLET" in (r.get("nom") or "").upper():
            continue
        free = r.get("tarif_type") in ("GRATUIT", "ACCES_LIBRE")
        base = dict(
            topic="outings",
            title=r.get("nom") or "",
            text=(r.get("descriptif_court") or "").strip(),
            place=r.get("adresse_nom_du_lieu") or r.get("adresse_nom_commune"),
            lat=float(r["coordonnees_y_wgs84"]) if r.get("coordonnees_y_wgs84") else None,
            lon=float(r["coordonnees_x_wgs84"]) if r.get("coordonnees_x_wgs84") else None,
            url=r.get("contact_site_web"),
            free=free,
            data={"price": r.get("tarif"), "kind": r.get("type"), "commune": r.get("adresse_nom_commune")},
        )
        # A session without an hour starts at midnight: it is still upcoming for the whole of its day.
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        sessions = [s for s in parse_occurrences(text)
                    if (midnight if s[0].time() == time(0) else now) <= s[0] <= now + horizon]
        for start, end in sessions:
            out.append(Item(id=f"musees:{r['id']}:{start:%Y%m%d%H%M}", start=start, end=end, **base))
        if not sessions and not parse_occurrences(text):
            span = parse_range(text, now.date())
            if span and span[0] <= now.date() <= span[1]:
                out.append(
                    Item(
                        id=f"musees:{r['id']}",
                        start=datetime.combine(span[0], time(0), PARIS),
                        end=datetime.combine(span[1], time(23, 59), PARIS),
                        **base,
                    )
                )
    return sorted(out, key=lambda i: i.start)


def collect(now: datetime | None = None) -> list[Item]:
    now = now or datetime.now(PARIS)
    page = get_json(FEED, {"where": f'idepci="{METRO_EPCI}"', "limit": 100})
    return items_from(page.get("results", []), now)
