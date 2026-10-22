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


class Tick(unittest.TestCase):
    """The hourly run: alerts confirmed on a second look, each slot sent once, a reminder before."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        from grnbl import notify, tick
        self.tick = tick
        p = mock.patch.object(schedule, "STATE", Path(tempfile.mkdtemp()) / "state.json")
        p.start()
        self.addCleanup(p.stop)
        self.ping = mock.Mock()
        for target, name, value in ((tick, "print", lambda *a: None), (notify, "ping", self.ping), (notify, "alert", lambda text: text),
                                    (notify, "reminder", lambda *a: "reminder"), (notify, "not_sent", lambda *a: "not sent")):
            p = mock.patch.object(target, name, value, create=True)
            p.start()
            self.addCleanup(p.stop)

    def at(self, day, hour, minute=0):
        from zoneinfo import ZoneInfo
        return datetime(2026, 10, day, hour, minute, tzinfo=ZoneInfo("Europe/Paris"))

    def test_an_alert_is_pinged_only_when_seen_again_45_minutes_later_and_only_once(self):
        from unittest import mock
        red = [{"kind": "weather", "what": "orages", "level": 4}]
        with mock.patch.object(self.tick.alerts, "collect", return_value=(red, [])), \
                mock.patch.object(self.tick, "alerts_post", return_value="ALERTE"):
            self.tick.check_alerts(self.at(22, 9, 0))
            self.tick.check_alerts(self.at(22, 9, 30))
            self.assertEqual(self.ping.call_count, 0)
            self.tick.check_alerts(self.at(22, 9, 50))
            self.tick.check_alerts(self.at(22, 10, 50))
        self.assertEqual([c.args[0] for c in self.ping.call_args_list], ["ALERTE"])

    def test_an_alert_gone_at_the_second_look_is_never_pinged(self):
        from unittest import mock
        red = [{"kind": "air", "day": "2026-10-22", "level": 5, "what": "très mauvaise"}]
        with mock.patch.object(self.tick.alerts, "collect", side_effect=[(red, []), ([], []), (red, [])]):
            for hour in (9, 10, 11):
                self.tick.check_alerts(self.at(22, hour))
        self.assertEqual(self.ping.call_count, 0)

    def test_no_alert_check_at_night(self):
        from unittest import mock
        with mock.patch.object(self.tick.alerts, "collect") as collect:
            self.tick.check_alerts(self.at(22, 3))
        self.assertEqual(collect.call_count, 0)

    def test_slot_reminds_two_hours_before_then_sends_once_at_its_hour(self):
        from unittest import mock
        from grnbl import publish
        edition = date(2026, 10, 28)
        items = [{"channel": "gratuit", "post": "week", "approved": False}]
        with mock.patch.object(self.tick, "this_week_edition", return_value=edition), \
                mock.patch.object(publish, "outbox", return_value=items), \
                mock.patch.object(publish, "status", return_value={}), \
                mock.patch.object(publish, "run", return_value=[("gratuit-week", "en attente")]) as run:
            for hour in (9, 10, 11, 12, 13):
                self.tick.send_slots(self.at(28, hour, 5))
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.kwargs["only"], ["gratuit", "sorties", "famille"])
        self.assertEqual([c.args[0] for c in self.ping.call_args_list], ["reminder", "not sent"])


if __name__ == "__main__":
    unittest.main()
