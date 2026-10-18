"""Turns items into WhatsApp posts.

The tone is the point of the product: a friend who keeps an eye on the city for
you, not a city-hall bulletin. Short lines, the useful number first, plain
French. WhatsApp formatting only (*bold*, _italic_), no links to click through
unless they matter.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import editorial
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
            where = f"*{s['name']}*, {s['address']}, {s['town']}" if s.get("name") else f"{s['address']}, {s['town']}"
            lines.append(f"{medal} {euros(s['price'])} · {where}")
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


def picked(events: list[dict], selection: list[dict] | None, post: str) -> list[tuple[dict, str]] | None:
    """The editor's picks for one post, in its order, minus what the human dropped.

    A pick the human swapped (decision "replaced_by": i) gives its slot to that event; any other
    removed pick is replaced by the next reserve, in the same slot, so the post keeps its length
    without another run. None without a selection.
    """
    if selection is None:
        return None
    mine = [p for p in selection if p.get("post") == post and 0 <= p.get("i", -1) < len(events)]

    def decision(i):
        return events[i].get("decision") or {}

    def line(p):
        e = events[p["i"]]
        return (e.get("decision") or {}).get("line") or p.get("line") or (e.get("review") or {}).get("line") or ""

    slots, used = [], set()
    for p in (p for p in mine if not p.get("reserve")):
        if decision(p["i"]).get("status") != "drop":
            slots.append(p)
        else:
            j = decision(p["i"]).get("replaced_by")
            ok = isinstance(j, int) and 0 <= j < len(events) and decision(j).get("status") != "drop"
            slots.append({"i": j, "post": post} if ok else None)
        if slots[-1]:
            used.add(slots[-1]["i"])
    bench = iter([p for p in mine if p.get("reserve") and decision(p["i"]).get("status") != "drop" and p["i"] not in used])
    slots = [s or next(bench, None) for s in slots]
    return [(events[p["i"]], line(p)) for p in slots if p]


def outings_post_reviewed(events: list[dict], now: datetime, days: int = 7, limit: int = 10,
                          selection: list[dict] | None = None) -> str | None:
    """The week's outings from the scraped agendas, free things first, then the best.

    Only what needs no booking, or is already running: what must be booked goes in to_book_post.
    """
    until = now + timedelta(days=days)
    rows = []
    for e in chosen(events):
        if editorial.timing(e, now.date()) != "this_week":
            continue
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

    picks = picked(events, selection, "week")
    if picks is not None:
        if not picks:
            return None
        lines = [f"🎭 *Cette semaine à Grenoble* · notre sélection parmi {len(rows)} sorties repérées", ""]
        for e, line in picks:
            start = _parse_start(e.get("start"))
            if start:
                lines += ([""] if len(lines) > 2 else []) + entry((None, None, start, e, line))
        lines += ["", "_Réagis avec 👍 si tu y vas, ça nous aide à choisir les prochaines._"]
        return "\n".join(lines)

    lines = [f"🎭 *Cette semaine à Grenoble* · {len(rows)} sorties repérées, dont {free_total} gratuites", "", "⭐ *Les immanquables*"]
    for x in top:
        lines += entry(x)
    if free:
        lines += ["", "🆓 *Gratuit*"]
        for x in free:
            lines += entry(x)
    lines += ["", "_Réagis avec 👍 si tu y vas, ça nous aide à choisir les prochaines._"]
    return "\n".join(lines)


def _place(e: dict) -> str:
    """Venue or town, without the shouting some agendas use."""
    where = (e.get("venue") or e.get("town") or "").strip()
    return where.title() if where.isupper() and len(where) > 6 else where


def _short_day(d: datetime) -> str:
    return f"{DAYS[d.weekday()]} {d.day}/{d.month:02d}" + (f" à {d.hour}h{d.minute:02d}".replace("h00", "h") if d.hour else "")


def to_book_post(events: list[dict], now: datetime, limit: int = 8, selection: list[dict] | None = None) -> str | None:
    """"À réserver maintenant": what needs booking, soonest deadline first.

    The post the weekly digest cannot be: by the time a free visit is "this
    week", its slots are gone. Booking that opens in the coming days is
    announced with its opening date, so people can be there at the minute.
    """
    today = now.date()
    rows = []
    for e in chosen(events):
        t = editorial.timing(e, today)
        if t not in ("book_now", "opens_soon"):
            continue
        start = _parse_start(e.get("start"))
        if not start:
            continue
        r, d = e.get("review") or {}, e.get("decision") or {}
        rows.append((t != "opens_soon", start, -(r.get("score") or 0), e, d.get("line") or r.get("line") or e.get("description") or ""))
    picks = picked(events, selection, "to_book")
    if picks is not None:
        order = {id(e): k for k, (e, _) in enumerate(picks)}
        lines_by = {id(e): line for e, line in picks}
        rows = [(r[0], r[1], order[id(r[3])], r[3], lines_by[id(r[3])]) for r in rows if id(r[3]) in order]
        rows.sort(key=lambda x: x[2])
    else:
        rows.sort(key=lambda x: (x[0], x[1], x[2]))
    if not rows:
        return None
    lines = ["📅 *À réserver maintenant*", "_Ce qui part vite : les places se prennent avant le jour J._", ""]
    for opens_first, start, _, e, line in rows[:limit]:
        r = e.get("review") or {}
        icon = "🆓" if (r.get("free") if r.get("free") is not None else e.get("free")) is True else "🎟️"
        where = _place(e)
        if lines[-1]:
            lines.append("")
        lines.append(f"{icon} *{e['title'].strip()}* · {_short_day(start)}{' · ' + where if where else ''}")
        if line:
            lines.append(f"   {line}")
        opens = _parse_start(e.get("booking_opens")) if e.get("booking_opens") else None
        deadline = _parse_start(e.get("booking_deadline")) if e.get("booking_deadline") else None
        link = e.get("booking_url") or e.get("url")
        if opens and opens.date() > today:
            lines.append(f"   ⏰ Réservations dès {_short_day(opens)}{' : ' + link if link else ''}")
        else:
            lines.append(f"   👉 Réserver{' avant ' + _short_day(deadline) if deadline else ''}{' : ' + link if link else ''}")
    lines += ["", "_Réagis avec 👍 si tu as réservé._"]
    return "\n".join(lines)
