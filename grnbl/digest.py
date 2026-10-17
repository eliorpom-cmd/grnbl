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
    """The morning fuel post: the three cheapest stations per fuel. Pure data, no AI."""
    by_fuel = {i.data["fuel"]: i for i in items if i.topic == "fuel"}
    order = ["gazole", "e10", "sp98", "e85", "gplc"]
    rows = [by_fuel[k] for k in order if k in by_fuel]
    if not rows:
        return None
    medals = ["🥇", "🥈", "🥉"]
    lines = [f"⛽ *Les pleins les moins chers ce {DAYS[now.weekday()]}*"]
    for i in rows:
        d = i.data
        lines += ["", f"*{d['label']}*"]
        for medal, s in zip(medals, d["top3"]):
            lines.append(f"{medal} {euros(s['price'])} · {s['address']}, {s['town']}")
        if d["saving_tank"] >= 3:
            lines.append(f"_Jusqu'à {euros(d['saving_tank'], 0)} d'écart sur un plein avec la plus chère_")
    lines += ["", f"_Prix officiels (prix-carburants.gouv.fr), {max(i.data['stations'] for i in rows)} stations de la Métropole._"]
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


def _parse_start(raw) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(raw)[:16])
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=PARIS)


def chosen(events: list[dict]) -> list[dict]:
    """What goes out: the human's decision wins, otherwise the AI's verdict."""
    out = []
    for e in events:
        d, r = e.get("decision") or {}, e.get("review") or {}
        if d.get("status") == "drop":
            continue
        if d.get("status") != "keep" and (not r.get("keep") or r.get("duplicate_of") is not None):
            continue
        out.append(e)
    return out


def outings_post_reviewed(events: list[dict], now: datetime, days: int = 7, limit: int = 10) -> str | None:
    """The week's outings from the scraped agendas, free things first, then the best."""
    until = now + timedelta(days=days)
    rows = []
    for e in chosen(events):
        start = _parse_start(e.get("start"))
        end = _parse_start(e.get("end")) if e.get("end") else None
        # Running now (exhibitions) or starting this week.
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if not start or (start < midnight and not (end and end >= now)) or start > until:
            continue
        r, d = e.get("review") or {}, e.get("decision") or {}
        rows.append((r.get("free") is not True, -(r.get("score") or 0), start, e, d.get("line") or r.get("line") or e["title"]))
    if not rows:
        return None
    # Two parts: the best of the week whatever the price, then the best free ones.
    by_score = sorted(rows, key=lambda x: (x[1], x[2]))
    top = by_score[:4]
    free = [x for x in by_score if not x[0] and x not in top][: max(0, limit - len(top))]
    free_total = sum(1 for x in rows if not x[0])

    def entry(x):
        _, _, start, e, line = x
        end = _parse_start(e.get("end")) if e.get("end") else None
        if start < now.replace(hour=0, minute=0, second=0, microsecond=0) and end:
            when = f"jusqu'au {end.day}/{end.month:02d}"  # already running
        else:
            when = DAYS[start.weekday()] + f" {start.day}" + (f" à {start.hour}h{start.minute:02d}".replace("h00", "h") if start.hour else "")
        where = e.get("venue") or e.get("town") or ""
        free = (e.get("review") or {}).get("free")
        icon = "🆓" if free is True else "🎟️" if free is False else "📍"
        return [f"{icon} *{e['title'].strip()}* · {when}{' · ' + where.title() if where.isupper() and len(where) > 6 else ' · ' + where if where else ''}", f"   {line}"]

    lines = [f"🎭 *Cette semaine à Grenoble* · {len(rows)} sorties repérées, dont {free_total} gratuites", "", "⭐ *Les immanquables*"]
    for x in top:
        lines += entry(x)
    if free:
        lines += ["", "🆓 *Gratuit*"]
        for x in free:
            lines += entry(x)
    lines += ["", "_Réagis avec 👍 si tu y vas, ça nous aide à choisir les prochaines._"]
    return "\n".join(lines)
