"""Offline tests: when an event may be posted, and the parsers of the new sources."""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from grnbl import editorial, memory
from grnbl.digest import picked
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
        # Last day today: nobody can plan for it from a morning post.
        self.assertEqual(editorial.timing(self.ev("2026-10-13", end="2026-10-17"), TODAY), "too_late")


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

    def test_an_impossible_date_drops_the_event_not_the_source(self):
        self.assertIsNone(tourisme.parse_dates("Le mardi 31 novembre 2026"))
        self.assertIsNone(tourisme.parse_dates("Du 30 février au 3 mars 2026"))

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


class Memory(unittest.TestCase):
    def test_routine_needs_three_dates(self):
        seen = {"marche saint bruno": {"2026-10-17", "2026-10-18", "2026-10-20"}, "tour perret": {"2026-10-18"}}
        self.assertTrue(memory.is_routine({"title": "Marché Saint-Bruno", "start": "2026-10-21"}, seen))
        self.assertFalse(memory.is_routine({"title": "Tour Perret", "start": "2026-10-18"}, seen))

    def test_already_posted_matches_title_and_day(self):
        done = {"visites gratuites de la tour perret|2026-10-18": "2026-10-07"}
        self.assertTrue(memory.already_posted({"title": "Visites gratuites de la Tour Perret", "start": "2026-10-18T10:00"}, done))
        self.assertFalse(memory.already_posted({"title": "Visites gratuites de la Tour Perret", "start": "2027-10-17"}, done))


class EditorPicks(unittest.TestCase):
    def test_order_and_human_drop_win(self):
        events = [{"title": "A", "start": "2026-10-20"}, {"title": "B", "start": "2026-10-21", "decision": {"status": "drop"}},
                  {"title": "C", "start": "2026-10-22", "decision": {"status": "keep", "line": "mine"}}]
        selection = [{"i": 2, "post": "week", "line": "ai"}, {"i": 1, "post": "week"}, {"i": 0, "post": "week", "line": "a"}]
        got = picked(events, selection, "week")
        self.assertEqual([(e["title"], line) for e, line in got], [("C", "mine"), ("A", "a")])
        self.assertIsNone(picked(events, None, "week"))


class Reserves(unittest.TestCase):
    def test_a_dropped_pick_is_replaced_by_the_first_reserve(self):
        events = [{"title": t, "start": "2026-10-20"} for t in "ABCD"]
        events[1]["decision"] = {"status": "drop"}
        selection = [{"i": 0, "post": "week"}, {"i": 1, "post": "week"},
                     {"i": 2, "post": "week", "reserve": True}, {"i": 3, "post": "week", "reserve": True}]
        self.assertEqual([e["title"] for e, _ in picked(events, selection, "week")], ["A", "C"])


class StationNames(unittest.TestCase):
    def test_by_feed_id_then_by_distance(self):
        from grnbl.sources.stations import name_for
        osm = [{"lat": 45.2, "lon": 5.74, "ref": "38000015", "brand": "Esso", "name": None},
               {"lat": 45.21, "lon": 5.75, "ref": None, "brand": "Carrefour", "name": "Carrefour Market"}]
        self.assertEqual(name_for("38000015", None, None, osm), "Esso")
        self.assertEqual(name_for("x", 45.2101, 5.7501, osm), "Carrefour Market")
        self.assertIsNone(name_for("x", 45.3, 5.9, osm))


class Channels(unittest.TestCase):
    def test_free_channel_never_gets_paid_events(self):
        from grnbl.editor import candidates
        ok = {"review": {"keep": True, "score": 4}}
        events = [{"title": "Concert", "start": "2026-10-20", "free": False, **ok},
                  {"title": "Visite", "start": "2026-10-20", "review": {"keep": True, "score": 3, "free": True}},
                  {"title": "Atelier", "start": "2026-10-20", "free": None, **ok}]
        self.assertEqual([e["title"] for _, e in candidates(events, TODAY, "gratuit")], ["Visite"])
        self.assertEqual(len(candidates(events, TODAY, "sorties")), 3)



def _kept(title, start, **kw):
    return {"title": title, "start": start, "review": {"keep": True, "score": 4, "free": True}, **kw}


class EditorSelect(unittest.TestCase):
    """The AI proposes, the code decides: offered events only, post by timing, channel on each pick."""

    def select(self, events, answer, channel="sorties", already=None):
        from unittest import mock
        from grnbl import editor
        with mock.patch.object(editor, "ask", return_value=answer) as ask, \
                mock.patch.object(editor, "_taste", return_value=""):
            picks = editor.select(events, TODAY, channel, already=already)
        return picks, ask

    def test_picks_outside_the_offered_events_are_dropped(self):
        events = [_kept("Visite", "2026-10-20"), {"title": "Rejeté", "start": "2026-10-20", "review": {"keep": False}}]
        picks, _ = self.select(events, '[{"i": 0, "post": "week"}, {"i": 1, "post": "week"}, {"i": 7, "post": "week"},'
                                        ' {"i": "0", "post": "week"}, {"i": 0, "post": "elsewhere"}]')
        self.assertEqual([p["i"] for p in picks], [0])

    def test_an_event_listed_twice_is_picked_once(self):
        events = [_kept("Visite", "2026-10-20"), _kept("Expo", "2026-10-20")]
        picks, _ = self.select(events, '[{"i": 0, "post": "week"}, {"i": 1, "post": "week"}, {"i": 0, "post": "week"},'
                                        ' {"i": 1, "post": "week", "reserve": true}]')
        self.assertEqual([(p["i"], p["reserve"]) for p in picks], [(0, False), (1, False)])
        week = [e["title"] for e, _ in picked(events, picks, "week")]
        self.assertEqual(week, ["Visite", "Expo"])

    def test_post_follows_the_timing_not_the_ai(self):
        events = [_kept("Concert", "2026-10-20"),
                  _kept("Visite de la tour", "2026-11-01", booking="required")]
        picks, _ = self.select(events, '[{"i": 0, "post": "to_book"}, {"i": 1, "post": "week", "reserve": "yes"}]')
        self.assertEqual([(p["i"], p["post"], p["channel"], p["reserve"]) for p in picks],
                         [(0, "week", "sorties", False), (1, "to_book", "sorties", False)])

    def test_paid_event_is_never_offered_to_the_free_group(self):
        events = [_kept("Concert payant", "2026-10-20"), _kept("Expo", "2026-10-20")]
        events[0]["review"]["free"] = False
        picks, ask = self.select(events, '[{"i": 0, "post": "week"}, {"i": 1, "post": "week"}]', channel="gratuit")
        self.assertEqual([p["i"] for p in picks], [1])
        self.assertNotIn("Concert payant", ask.call_args.args[0])

    def test_nothing_to_offer_asks_nothing(self):
        picks, ask = self.select([_kept("Passé", "2026-10-01")], "[]")
        self.assertEqual(picks, [])
        self.assertEqual(ask.call_count, 0)

    def test_reserves_of_an_earlier_group_stay_available(self):
        events = [_kept("Atelier", "2026-10-20")]
        picks, _ = self.select(events, '[{"i": 0, "post": "week"}]', already=[{"i": 0, "reserve": True}])
        self.assertEqual([p["i"] for p in picks], [0])

    def test_groups_choose_in_order_each_seeing_the_earlier_picks(self):
        from unittest import mock
        from grnbl import editor
        tmp = Path(tempfile.mkdtemp())
        (tmp / "events" / TODAY.isoformat()).mkdir(parents=True)
        (tmp / "events" / TODAY.isoformat() / "reviewed.json").write_text("[]")
        calls = []

        def select(events, day, channel, already):
            calls.append((channel, len(already)))
            return [{"i": len(calls), "post": "week", "channel": channel}]

        with mock.patch.object(editor, "DATA", tmp), mock.patch.object(editor, "select", select), \
                mock.patch.object(editor, "zoom"), mock.patch.object(editor, "check"):
            picks = editor.run(TODAY)
        self.assertEqual(calls, [(c, k) for k, c in enumerate(editor.ORDER)])
        self.assertEqual(len(json.loads((tmp / "events" / TODAY.isoformat() / "selection.json").read_text())), len(picks))


class EditorZoom(unittest.TestCase):
    """A festival pick gets one precise moment of its programme, within the post's window."""

    def zoom(self, channel, answer):
        from unittest import mock
        from grnbl import editor
        events = [{"title": "Festival des arts", "start": "2026-10-20", "end": "2026-10-30", "url": "https://x.test"}]
        pick = {"i": 0, "post": "week", "channel": channel, "line": "general"}
        with mock.patch.object(editor, "_programme", return_value="page"), \
                mock.patch.object(editor, "ask", return_value=json.dumps(answer)):
            editor.zoom([pick], events, TODAY)
        return pick

    def test_moment_in_the_window_becomes_the_line(self):
        pick = self.zoom("sorties", {"found": True, "what": "Bal", "when": "2026-10-25", "free": False, "line": "Dimanche 25 : bal."})
        self.assertEqual(pick["line"], "Dimanche 25 : bal.")
        self.assertEqual(pick["zoom"]["what"], "Bal")

    def test_free_group_keeps_the_general_line_unless_the_moment_is_free(self):
        for free in (False, None):
            pick = self.zoom("gratuit", {"found": True, "what": "Bal", "when": "2026-10-25", "free": free, "line": "Bal payant."})
            self.assertEqual(pick["line"], "general")
            self.assertNotIn("zoom", pick)

    def test_moment_before_the_post_is_read_is_ignored(self):
        # Gratuit sends on Wednesday 21: a session on the 21st is already too late to plan for.
        pick = self.zoom("sorties", {"found": True, "what": "Bal", "when": "2026-10-21", "free": True, "line": "Mercredi : bal."})
        self.assertEqual(pick["line"], "general")


if __name__ == "__main__":
    unittest.main()
