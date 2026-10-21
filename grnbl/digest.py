"""Turns items into WhatsApp posts.

The tone is the point of the product: a friend who keeps an eye on the city for
you, not a city-hall bulletin. Short lines, the useful number first, plain
French. WhatsApp formatting only (*bold*, _italic_), no links to click through
unless they matter.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from . import editorial
from .channels import CHANNELS, accepts
from .items import Item
from .site import post_link

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
    """The picks for one post, in their order, minus what the human dropped.

    A removed pick is replaced by the next reserve, in the same slot, so the post keeps its length
    without another run. When the human picked the lines from the board's list, the selection holds
    exactly those (publish.apply_choices). None without a selection.
    """
    if selection is None:
        return None
    mine = [p for p in selection if p.get("post") == post and 0 <= p.get("i", -1) < len(events)]

    def usable(p):
        return ((events[p["i"]].get("decision") or {}).get("status")) != "drop"

    def line(p):
        e = events[p["i"]]
        return (e.get("decision") or {}).get("line") or p.get("line") or (e.get("review") or {}).get("line") or ""

    bench = iter([p for p in mine if p.get("reserve") and usable(p)])
    slots = [p if usable(p) else next(bench, None) for p in mine if not p.get("reserve")]
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
        block = (e.get("decision") or {}).get("block")
        if block:  # edited by hand in the board's preview: sent as written
            return block.split("\n")
        end = _parse_start(e.get("end")) if e.get("end") else None
        if start < now.replace(hour=0, minute=0, second=0, microsecond=0) and end:
            when = f"Jusqu'au {_day(end, weekday=False)}"  # already running
        else:
            when = _day(start)
        link = post_link(e) or clean_url(e.get("url"))
        return event_block(e, when, line, channel, f"🔗 {link}" if link else None)

    channel = next((p.get("channel") for p in selection or [] if p.get("channel")), "sorties")
    picks = picked(events, selection, "week")
    if picks is not None:
        if not picks:
            return None
        title = CHANNELS.get(channel, CHANNELS["sorties"])["week_title"]
        found = sum(1 for x in rows if accepts(channel, x[3])) if channel in CHANNELS else len(rows)
        kind = "idées" if channel in ("bonsplans", "nature") else "sorties"
        lines = [title, f"_Sans réservation. {len(picks)} {kind} choisies parmi les {found} repérées cette semaine._"]
        dated = [(e, line, _parse_start(e.get("start"))) for e, line in picks]
        # Day by day: what is already running (exhibitions) first, then in date order.
        for e, line, start in sorted((x for x in dated if x[2]), key=lambda x: x[2]):
            lines += [""] + entry((None, None, start, e, line))
        return "\n".join(lines)

    lines = [f"🎭 *Cette semaine à Grenoble* · {len(rows)} sorties repérées, dont {free_total} gratuites", "", "⭐ *Les immanquables*"]
    for x in top:
        lines += entry(x)
    if free:
        lines += ["", "🆓 *Gratuit*"]
        for x in free:
            lines += entry(x)
    return "\n".join(lines)


def alerts_post(alerts: list[dict], now: datetime) -> str | None:
    """A grave alert for the whole community: red weather warning, very bad air, a tram strike. Rare by design."""
    if not alerts:
        return None
    from .sources.alerts import COLORS
    lines = [f"🚨 *Alerte Grenoble* · {DAYS[now.weekday()]} {now.day}/{now.month:02d}"]
    weather = [a for a in alerts if a["kind"] == "weather"]
    if weather:
        lines += ["", "*Météo en Isère*"]
        for a in weather:
            dot, color = COLORS[a["level"]]
            lines.append(f"{dot} Vigilance {color} {a['what']} aujourd'hui")
        if any(a["level"] >= 3 for a in weather):
            lines.append("_Conseils et carte : vigilance.meteofrance.fr_")
    for a in (a for a in alerts if a["kind"] == "air"):
        day = "Aujourd'hui" if a["day"] == now.date().isoformat() else "Demain"
        lines += ["", f"😷 *Qualité de l'air {a['what']}* · {day} à Grenoble"]
        if a.get("comment"):
            lines.append(f"   {a['comment']}")
        lines.append("   _Un bon jour pour le tram ou le vélo. Détails : atmo-auvergnerhonealpes.fr_")
    transit = [a for a in alerts if a["kind"] == "transit"]
    if transit:
        lines += ["", "🚋 *Tram TAG*"]
        for a in transit:
            start = datetime.fromisoformat(a["start"])
            lines.append(f"• *{', '.join(a['lines'])}* · {a['title'].split(':', 1)[-1].strip()} (dès {_short_day(start)})")
            if a.get("detail"):
                lines.append(f"   {a['detail']}")
    lines += ["", "_Sources : Météo-France, Atmo AuRA, Mobilités M._"]
    return "\n".join(lines)


MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
# Venues some agendas give that are the publisher, not the place: the town says more.
NOT_A_PLACE = re.compile(r"office de tourisme|grenoble[- ]alpes métropole|^ville de\b", re.I)
TRACKING = re.compile(r"^(?:utm_\w+|fbclid|gclid|mc_\w+|_ga|ref|xtor)$", re.I)


def _calm(text: str) -> str:
    """Without the shouting some agendas use."""
    text = re.sub(r"\s+", " ", text or "").strip()
    return text.title() if sum(c.isupper() for c in text) > 0.6 * max(1, sum(c.isalpha() for c in text)) and len(text) > 6 else text


def title_of(e: dict) -> str:
    """The event's name as the post shows it, in bold: calm, capitalised, spaced."""
    t = _calm(e.get("title") or "")
    t = re.sub(r"\s*/\s*", " / ", t)
    # "vide grenier de voiron" gets its capital; "oiZo" is spelled that way on purpose.
    return t[:1].upper() + t[1:] if not any(c.isupper() for c in t) else t


def _place(e: dict) -> str:
    """Venue and town ("L'Atrium, Fontanil-Cornillon"), the town alone when the venue is the publisher."""
    venue, town = _calm(e.get("venue") or ""), _calm(e.get("town") or "")
    if NOT_A_PLACE.search(venue):
        venue = ""
    # "Gymnase du Chamandier, 51, Rue de la Gare, Gieres": the place's name is enough.
    venue = re.sub(r"\s*\([^)]{20,}\)", "", venue.split(",")[0]).strip()
    if venue and town and town.lower() not in venue.lower() and town.lower() != "grenoble":
        return f"{venue}, {town}"
    return venue or town


def clean_url(url: str | None) -> str | None:
    """The source link without its tracking tail (utm_…), so a post is not half made of link."""
    if not url:
        return None
    parts = urlsplit(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not TRACKING.match(k)])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def _day(d: datetime, weekday: bool = True) -> str:
    """"Lundi 23 nov. · 12h15", or without the time when the source gives none."""
    out = (DAYS[d.weekday()].capitalize() + " " if weekday else "") + f"{d.day}{'er' if d.day == 1 else ''} {MONTHS[d.month - 1]}"
    return out + (f" · {d.hour}h{d.minute:02d}".replace("h00", "h") if d.hour or d.minute else "")


def short_price(e: dict) -> str:
    """"Gratuit", "12 €", "8–15 €", or nothing: agendas paste whole fare tables."""
    r = e.get("review") or {}
    if (r.get("free") if r.get("free") is not None else e.get("free")) is True:
        return "Gratuit"
    raw = str(e.get("price") or "")
    amounts = sorted({float(a.replace(",", ".")) for a in re.findall(r"(\d+(?:[.,]\d+)?)\s*€", raw)})
    fmt = lambda x: f"{x:g}".replace(".", ",")  # noqa: E731
    if not amounts:
        return ""
    return f"{fmt(amounts[0])} €" if len(amounts) == 1 else f"{fmt(amounts[0])}–{fmt(amounts[-1])} €"


def event_block(e: dict, when: str, line: str, channel: str | None, action: str | None) -> list[str]:
    """One event of a post: the name in bold, then when · where · price, our line, the link.

    The price is left out in the free group, where everything is free."""
    price = "" if channel == "gratuit" else short_price(e)
    meta = " · ".join(x for x in (when, _place(e), price) if x)
    out = [f"*{title_of(e)}*", meta]
    if line and line.strip() != title_of(e):
        out.append(line.strip())
    return out + ([action] if action else [])


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
    channel = next((p.get("channel") for p in selection or [] if p.get("channel")), None)
    lines = (["📅 *À noter dès maintenant*", "_Les dates à retenir des prochaines semaines._"] if channel == "bonsplans" else
             ["📅 *À réserver maintenant*", "_Les places partent avant le jour J : on vous prévient tant qu'il en reste._"])
    # In date order, the way people read a week; the board decides which lines, not their order.
    for opens_first, start, _, e, line in sorted(rows[:limit], key=lambda x: x[1]):
        lines.append("")
        block = (e.get("decision") or {}).get("block")
        if block:  # edited by hand in the board's preview: sent as written
            lines.append(block)
            continue
        opens = _parse_start(e.get("booking_opens")) if e.get("booking_opens") else None
        deadline = _parse_start(e.get("booking_deadline")) if e.get("booking_deadline") else None
        # The event's page on the site when links are on (site.py, off by default), else the source.
        link = post_link(e) or clean_url(e.get("booking_url") or e.get("url"))
        if opens and opens.date() > today:
            action = f"⏰ Réservations dès {_day(opens).lower()}{' : ' + link if link else ''}"
        else:
            verb = "Infos" if channel == "bonsplans" else "Réserver"
            action = f"👉 {verb}{' avant ' + _day(deadline).lower() if deadline else ''}{' : ' + link if link else ''}"
        lines += event_block(e, _day(start), line, channel, action)
    return "\n".join(lines)
