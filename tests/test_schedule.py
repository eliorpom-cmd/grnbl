"""Offline tests: when editions are prepared, read and sent."""

import unittest
from datetime import date, datetime

from grnbl import schedule


class Week(unittest.TestCase):
    def test_tuesday_prepares_wednesday_edition(self):
        self.assertEqual(schedule.edition_for(date(2026, 10, 20)), date(2026, 10, 21))

    def test_each_group_sends_on_its_day(self):
        edition = date(2026, 10, 28)
        self.assertEqual(schedule.send_time(edition, schedule.slot_of("sorties")), datetime(2026, 10, 28, 12, 0))
        self.assertEqual(schedule.send_time(edition, schedule.slot_of("nature")), datetime(2026, 10, 29, 18, 0))

    def test_a_moved_slot_sends_at_its_new_time_that_week_only(self):
        self.assertEqual(schedule.send_time(date(2026, 10, 21), schedule.slot_of("sorties")), datetime(2026, 10, 21, 18, 0))
        self.assertEqual(schedule.send_time(date(2026, 10, 21), schedule.slot_of("nature")), datetime(2026, 10, 22, 18, 0))

    def test_posts_are_written_for_their_sending_day(self):
        self.assertEqual(schedule.channel_day(date(2026, 10, 21), "bonsplans"), date(2026, 10, 22))
        self.assertEqual(schedule.channel_day(date(2026, 10, 21), "carburant"), date(2026, 10, 21))

    def test_every_event_group_has_a_slot(self):
        from grnbl.channels import CHANNELS
        self.assertTrue(all(schedule.slot_of(c) for c in CHANNELS))


class OneGroupPerEvent(unittest.TestCase):
    def test_taken_event_is_never_offered_again_even_as_a_reserve(self):
        from unittest import mock
        from grnbl import editor
        events = [{"title": "Forestivités", "start": "2026-10-24", "review": {"score": 4}},
                  {"title": "Fête de la science", "start": "2026-10-24", "review": {"score": 5}},
                  {"title": "Atelier", "start": "2026-10-24", "review": {"score": 3}}]
        seen = {}

        def ask(prompt, **_):
            seen["prompt"] = prompt
            return '[{"i": 2, "post": "week", "line": "x"}]'

        with mock.patch.object(editor, "candidates", return_value=list(enumerate(events))), \
                mock.patch.object(editor, "ask", ask), mock.patch.object(editor, "_taste", return_value=""):
            editor.select(events, date(2026, 10, 21), "sorties",
                          already=[{"i": 0, "reserve": False}, {"i": 1, "reserve": True}])
        offered = seen["prompt"].split("CANDIDATES:")[1]
        self.assertNotIn("Forestivités", offered)
        self.assertNotIn("Fête de la science", offered)
        self.assertIn("Atelier", offered)


if __name__ == "__main__":
    unittest.main()
