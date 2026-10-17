"""Turns items into WhatsApp posts.

The tone is the point of the product: a friend who keeps an eye on the city for
you, not a city-hall bulletin. Short lines, the useful number first, plain
French. WhatsApp formatting only (*bold*, _italic_), no links to click through
unless they matter.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .items import Item

PARIS = ZoneInfo("Europe/Paris")
DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def euros(x: float, digits: int = 3) -> str:
    return f"{x:.{digits}f}".replace(".", ",") + " €"


def fuel_post(items: list[Item], now: datetime) -> str | None:
    """The morning fuel post: cheapest station per fuel, and what it saves on a tank."""
    by_fuel = {i.data["fuel"]: i for i in items if i.topic == "fuel"}
    order = ["gazole", "e10", "sp98", "e85", "gplc"]
    rows = [by_fuel[k] for k in order if k in by_fuel]
    if not rows:
        return None
    lines = [f"⛽ *Le plein le moins cher ce {DAYS[now.weekday()]}*", ""]
    for i in rows:
        d = i.data
        lines.append(f"*{d['label']}* : {euros(d['price'])} à {i.text}")
        if d["saving_tank"] >= 3:
            lines.append(f"   _{euros(d['saving_tank'], 0)} de moins sur un plein que la plus chère de la Métropole_")
    lines += ["", f"_Prix officiels relevés sur {max(i.data['stations'] for i in rows)} stations de la Métropole._"]
    return "\n".join(lines)


def _when(i: Item) -> str:
    day = DAYS[i.start.weekday()]
    if i.start.hour == 0 and i.start.minute == 0:
        return f"{day} {i.start.day}"
    return f"{day} {i.start.day} à {i.start.hour}h{i.start.minute:02d}".replace("h00", "h")


def outings_post(items: list[Item], now: datetime, days: int = 7, limit: int = 8) -> str | None:
    """The 'this week' post: free things first, then the rest, each in one line."""
    until = now + timedelta(days=days)
    sessions = [
        i for i in items
        if i.topic == "outings" and i.start and now <= i.start <= until
        and (i.end is None or i.end - i.start < timedelta(days=1))
    ]
    shows = [i for i in items if i.topic == "outings" and i.free and i.end and i.end - i.start >= timedelta(days=1)]
    if not sessions and not shows:
        return None
    sessions.sort(key=lambda i: (not i.free, i.start))
    free_count = sum(1 for i in sessions if i.free)
    lines = [f"🎭 *Cette semaine : {free_count} sorties gratuites près de chez toi*", ""]
    for i in sessions[:limit]:
        tag = "🆓" if i.free else "🎟️"
        lines.append(f"{tag} *{i.title.strip()}* · {_when(i)} · {i.place}")
    if shows:
        lines += ["", "🖼️ *Expos gratuites en ce moment*"]
        for i in shows[:3]:
            lines.append(f"• {i.title.strip()} · {i.place} · jusqu'au {i.end.day}/{i.end.month:02d}")
    lines += ["", "_Réagis avec 👍 si tu y vas, ça nous aide à choisir les prochaines._"]
    return "\n".join(lines)
