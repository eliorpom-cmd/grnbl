"""Offline tests: when an event may be posted, and the parsers of the new sources."""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from grnbl import editorial
from grnbl.scrape import press, tourisme

TODAY = date(2026, 10, 17)


class Timing(unittest.TestCase):
    def ev(self, start, **kw):
        return {"title": "x", "start": start, **kw}

    def test_booking_needed_and_too_close_is_too_late(self):
        # The free Tour Perret visit: booking required, the day after.
        self.assertEqual(editorial.timing(self.ev("2026-10-18", booking="required"), TODAY), "too_late")

    def test_booking_open_with_time_left_is_book_now(self):
        self.assertEqual(editorial.timing(self.ev("2026-10-30", booking="required"), TODAY), "book_now")

    def test_booking_opening_within_a_week_is_announced(self):
        e = self.ev("2026-11-05", booking="required", booking_opens="2026-10-21T10:00")
        self.assertEqual(editorial.timing(e, TODAY), "opens_soon")

    def test_booking_deadline_passed(self):
        e = self.ev("2026-11-05", booking="required", booking_deadline="2026-10-16")
        self.assertEqual(editorial.timing(e, TODAY), "too_late")

    def test_walk_in_today_is_too_late_tomorrow_is_fine(self):
        self.assertEqual(editorial.timing(self.ev("2026-10-17T20:00"), TODAY), "too_late")
        self.assertEqual(editorial.timing(self.ev("2026-10-18"), TODAY), "this_week")
        self.assertEqual(editorial.timing(self.ev("2026-11-10"), TODAY), "later")

    def test_running_exhibition_and_sold_out(self):
        self.assertEqual(editorial.timing(self.ev("2026-09-01", end="2026-11-03"), TODAY), "this_week")
        self.assertEqual(editorial.timing(self.ev("2026-10-25", sold_out=True), TODAY), "sold_out")


class Calendar(unittest.TestCase):
    def test_first_sunday(self):
        self.assertEqual(editorial.first_sunday(2026, 11), date(2026, 11, 1))
        self.assertEqual(editorial.first_sunday(2026, 12), date(2026, 12, 6))

    def test_unconfirmed_dates_are_watched_not_posted(self):
        data = {"events": [{"id": "a", "name": "A", "what": "w", "rule": "r", "free": True,
                            "occurrences": [{"start": "2026-10-30", "end": "2026-10-30", "confirmed": False},
                                            {"start": "2026-11-02", "end": "2026-11-02", "confirmed": True}],
                            "booking": {"required": False}, "announce_days": 7, "watch": ["https://example.org"]}]}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "c.json"
            path.write_text(json.dumps(data))
            events, watch = editorial.calendar_events(TODAY, path)
        self.assertEqual([e["start"] for e in events], ["2026-11-02"])
        self.assertEqual([w["expected"] for w in watch], ["2026-10-30"])

    def test_real_calendar_loads(self):
        events, _ = editorial.calendar_events(TODAY)
        self.assertTrue(any(e["calendar_id"] == "premier-dimanche" and e["start"] == "2026-11-01" for e in events))


class Tourisme(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(tourisme.parse_dates("Du 11 octobre au 1 novembre 2026"), (date(2026, 10, 11), date(2026, 11, 1)))
        self.assertEqual(tourisme.parse_dates("Du 20 au 24 décembre 2026"), (date(2026, 12, 20), date(2026, 12, 24)))
        self.assertEqual(tourisme.parse_dates("Du 12 décembre 2026 au 3 janvier 2027"), (date(2026, 12, 12), date(2027, 1, 3)))
        self.assertEqual(tourisme.parse_dates("Le dimanche 18 octobre 2026"), (date(2026, 10, 18), date(2026, 10, 18)))

    def test_card(self):
        page = '''<li
          id="id_result_27494" data-latitude="45.18" data-longitude="5.75"><figure><figcaption>
          <h2> Fête du Cinéma d&#x27;animation </h2><p>Saint-Martin-d'Hères</p><p>Jusqu’au 01/11/2026</p>
          <a href="/fr/decouvrir/evenements/agenda/detail/fete-du-cinema-6692308/">voir</a>
          <span class="family"></span></figcaption></figure></li>'''
        (card,) = tourisme.parse_cards(page)
        self.assertEqual((card["id"], card["title"], card["town"], card["until"], card["family"]),
                         ("6692308", "Fête du Cinéma d'animation", "Saint-Martin-d'Hères", "2026-11-01", True))


class Press(unittest.TestCase):
    def test_links_and_dates(self):
        paper = next(p for p in press.PAPERS if p["id"] == "press-placegrenet")
        page = '<a href="https://www.placegrenet.fr/2026/10/07/rencontres-cine-montagne/691079">x</a>'
        (url,) = press.article_links(paper, page, "https://www.placegrenet.fr/")
        self.assertEqual(press.published(paper, url), date(2026, 10, 7))


if __name__ == "__main__":
    unittest.main()
