"""Offline tests: when editions are prepared, read and sent."""

import unittest
from datetime import date, datetime

from grnbl import schedule


class Week(unittest.TestCase):
    def test_tuesday_prepares_wednesday_edition(self):
        self.assertEqual(schedule.edition_for(date(2026, 10, 20)), date(2026, 10, 21))

    def test_each_group_sends_on_its_day(self):
        edition = date(2026, 10, 21)
        self.assertEqual(schedule.send_time(edition, schedule.slot_of("sorties")), datetime(2026, 10, 21, 12, 0))
        self.assertEqual(schedule.send_time(edition, schedule.slot_of("nature")), datetime(2026, 10, 22, 18, 0))

    def test_posts_are_written_for_their_sending_day(self):
        self.assertEqual(schedule.channel_day(date(2026, 10, 21), "bonsplans"), date(2026, 10, 22))
        self.assertEqual(schedule.channel_day(date(2026, 10, 21), "carburant"), date(2026, 10, 21))

    def test_every_event_group_has_a_slot(self):
        from grnbl.channels import CHANNELS
        self.assertTrue(all(schedule.slot_of(c) for c in CHANNELS))


if __name__ == "__main__":
    unittest.main()
