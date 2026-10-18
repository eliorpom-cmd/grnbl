"""Offline tests: the structured readers and how repeated sessions are merged."""

import unittest
from datetime import date

from grnbl.scrape import tribe
from grnbl.scrape.run import collapse, next_postable


class Tribe(unittest.TestCase):
    def test_room_gets_the_venue_name_and_time_is_kept(self):
        e = tribe.convert({
            "title": "Le Sommet des dieux", "start_date": "2026-11-04 20:00:00", "end_date": "2026-11-04 20:00:00",
            "all_day": False, "cost": "40€", "cost_details": {"values": ["40"]},
            "venue": {"venue": "Auditorium", "city": ""}, "url": "https://x/", "excerpt": "",
            "description": "<p>Un ciné-concert.</p>", "categories": [{"name": "Ciné Concert"}],
        }, {"place": "MC2", "town": "Grenoble"})
        self.assertEqual((e["start"], e["end"]), ("2026-11-04T20:00", None))
        self.assertEqual((e["venue"], e["town"]), ("MC2, Auditorium", "Grenoble"))
        self.assertEqual((e["free"], e["category"], e["description"]), (False, "concert", "Un ciné-concert."))

    def test_free_and_page_builder_codes_removed(self):
        e = tribe.convert({
            "title": "Jam", "start_date": "2026-10-22 00:00:00", "end_date": "2026-10-22 23:59:59", "all_day": True,
            "cost": "Gratuit", "venue": [], "description": '[et_pb_section fb_built="1"]Histoires[/et_pb_section]',
        })
        self.assertEqual((e["start"], e["free"], e["description"]), ("2026-10-22", True, "Histoires"))


class Series(unittest.TestCase):
    def test_sessions_of_one_tour_become_one_event(self):
        got = collapse([
            {"title": "Visites flash", "venue": "Musée", "start": "2026-10-25T15:00"},
            {"title": "Visites flash", "venue": "Musée", "start": "2026-10-21T15:00", "price": "Gratuit"},
            {"title": "Visites flash", "venue": "Autre lieu", "start": "2026-10-22T15:00"},
        ])
        self.assertEqual(len(got), 2)
        tour = next(e for e in got if e["venue"] == "Musée")
        self.assertEqual(tour["start"], "2026-10-21T15:00")
        self.assertEqual(tour["dates"], ["2026-10-21T15:00", "2026-10-25T15:00"])

    def test_session_too_close_to_book_moves_to_the_next(self):
        e = {"title": "Atelier", "booking": "required", "start": "2026-10-19T10:00",
             "dates": ["2026-10-19T10:00", "2026-10-26T10:00"]}
        next_postable(e, date(2026, 10, 18))
        self.assertEqual(e["start"], "2026-10-26T10:00")


if __name__ == "__main__":
    unittest.main()
