"""When to tell people about an event: the rule that makes a tip useful.

A free tower visit announced the day before is worthless if the slots were
booked out ten days earlier. So every event gets a status for today, from its
date and what is known about booking:

  book_now      booking is open and there is still time: goes in "À réserver".
  opens_soon    booking opens within a week: announced with the opening date.
  this_week     no booking needed, happens in the coming days: the weekly post.
  later         fine, but too far ahead to post now.
  too_late      it needs booking and the event is too close, or booking closed.
  sold_out      the page says it is full.

The rules are code, not AI, so they are the same every day and easy to check.
The yearly rendez-vous of calendar.json go through the same rules.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

CALENDAR = Path(__file__).with_name("calendar.json")

# Days between the post and the event, at least.
NOTICE_BOOKING = 4      # people need time to book and organise
NOTICE_WALK_IN = 1      # a walk-in event is announced the day before at the latest
WEEK = 8                # the weekly post covers the next eight days
BOOK_AHEAD = 60         # "À réserver" looks this far ahead
OPENS_SOON = 7          # booking that opens within a week is announced now


def _day(raw) -> date | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw)[:16]).date() if "T" in str(raw) else date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def timing(e: dict, today: date) -> str:
    start, end = _day(e.get("start")), _day(e.get("end"))
    if not start:
        return "later"
    if e.get("sold_out"):
        return "sold_out"
    lead = (start - today).days
    booking = e.get("booking")
    opens, deadline = _day(e.get("booking_opens")), _day(e.get("booking_deadline"))
    if booking == "required":
        if deadline and deadline < today:
            return "too_late"
        if opens and opens > today:
            return "opens_soon" if (opens - today).days <= OPENS_SOON and lead >= NOTICE_BOOKING else "later"
        if lead < NOTICE_BOOKING:
            return "too_late"
        return "book_now" if lead <= BOOK_AHEAD else "later"
    # Running already (an exhibition): fine for the weekly post until it closes.
    if start < today and end and end >= today:
        return "this_week"
    if lead < NOTICE_WALK_IN:
        return "too_late"
    if booking == "recommended" and lead > WEEK and lead <= BOOK_AHEAD:
        return "book_now"
    return "this_week" if lead <= WEEK else "later"


def first_sunday(year: int, month: int) -> date:
    d = date(year, month, 1)
    return d + timedelta(days=(6 - d.weekday()) % 7)


def calendar_events(today: date, path: Path = CALENDAR) -> tuple[list[dict], list[dict]]:
    """The calendar's confirmed dates in the event shape, plus what to watch.

    An unconfirmed date coming close is never posted: it goes to the admin
    board as "to check", with the official pages to look at.
    """
    data = json.loads(path.read_text())
    events, watch = [], []
    for rv in data["events"]:
        occurrences = list(rv.get("occurrences", []))
        if rv.get("monthly") == "first-sunday":
            for k in range(3):
                y, m = today.year + (today.month - 1 + k) // 12, (today.month - 1 + k) % 12 + 1
                d = first_sunday(y, m).isoformat()
                occurrences.append({"start": d, "end": d, "confirmed": True})
        booking = rv.get("booking") or {}
        for occ in occurrences:
            start, end = date.fromisoformat(occ["start"]), date.fromisoformat(occ.get("end") or occ["start"])
            if end < today:
                continue
            lead = (start - today).days
            if not occ.get("confirmed"):
                # Look when booking would normally open, or when the announcement window starts.
                look = max(booking.get("lead_days") or 0, rv.get("announce_days") or 0) + 30
                if lead <= look:
                    watch.append({"id": rv["id"], "name": rv["name"], "expected": occ["start"],
                                  "why": f"{rv['rule']} Date attendue vers le {start.day}/{start.month:02d}, pas encore confirmée.",
                                  "check": rv.get("watch", [])})
                continue
            # An unknown opening date stays unknown: the official page is scraped instead of guessing.
            opens = occ.get("booking_opens")
            events.append({
                "title": rv["name"], "start": occ["start"], "end": occ.get("end") if occ.get("end") != occ["start"] else None,
                "venue": None, "town": rv.get("town"), "price": "Gratuit" if rv.get("free") else None,
                "free": rv.get("free"), "url": (booking.get("url") or (rv.get("watch") or [None])[0]),
                "category": "festival", "description": occ.get("note") or rv["what"],
                "booking": "required" if booking.get("required") else "none",
                "booking_opens": opens, "booking_deadline": None, "booking_url": booking.get("url"),
                "sold_out": False, "family": rv.get("family"),
                "source": "calendar", "source_name": "Calendrier grnbl", "calendar_id": rv["id"],
                "announce_days": rv.get("announce_days"),
            })
    return events, watch
