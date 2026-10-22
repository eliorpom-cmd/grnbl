"""Offline tests: the ticked lists replace the editor's picks of their post; a removed pick takes the next reserve."""

import unittest

from grnbl.digest import picked
from grnbl.publish import apply_choices


def ev(title, decision=None):
    return {"title": title, "decision": decision, "review": {"line": f"line {title}"}}


SEL = [{"i": 0, "post": "week", "channel": "gratuit", "line": "editor A"}, {"i": 1, "post": "week", "channel": "gratuit"},
       {"i": 2, "post": "week", "channel": "gratuit"},
       {"i": 3, "post": "week", "channel": "gratuit", "reserve": True, "line": "editor D"},
       {"i": 4, "post": "week", "channel": "gratuit", "reserve": True},
       {"i": 5, "post": "to_book", "channel": "gratuit"}, {"i": 1, "post": "week", "channel": "sorties"}]


def titles(events, sel, post="week", channel="gratuit"):
    return [e["title"] for e, _ in picked(events, [p for p in sel if p.get("channel") == channel], post)]


class Choices(unittest.TestCase):
    def setUp(self):
        self.events = [ev(t) for t in "ABCDEFG"]

    def test_no_choice_keeps_the_editor_picks(self):
        self.assertEqual(titles(self.events, apply_choices(SEL, {})), ["A", "B", "C"])

    def test_removed_pick_gets_next_reserve_in_its_slot(self):
        self.events[1]["decision"] = {"status": "drop"}
        self.assertEqual(titles(self.events, SEL), ["A", "D", "C"])

    def test_ticked_list_is_the_post_in_order(self):
        sel = apply_choices(SEL, {"gratuit": {"week": [0, 3, 6]}})
        self.assertEqual(titles(self.events, sel), ["A", "D", "G"])

    def test_editor_line_kept_for_its_own_lines(self):
        sel = apply_choices(SEL, {"gratuit": {"week": [3, 6]}})
        lines = [line for _, line in picked(self.events, [p for p in sel if p["channel"] == "gratuit"], "week")]
        self.assertEqual(lines, ["editor D", "line G"])

    def test_choice_touches_only_its_channel_and_post(self):
        sel = apply_choices(SEL, {"gratuit": {"week": [6]}})
        self.assertEqual(titles(self.events, sel, "to_book"), ["F"])
        self.assertEqual(titles(self.events, sel, "week", "sorties"), ["B"])

    def test_empty_list_empties_the_post(self):
        self.assertEqual(titles(self.events, apply_choices(SEL, {"gratuit": {"week": []}})), [])


class PostLines(unittest.TestCase):
    """How each event reads in the posts: day and time, booking dates, no time when the source gives none."""

    def setUp(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        self.now = datetime(2026, 10, 21, 12, 0, tzinfo=ZoneInfo("Europe/Paris"))

    def week(self, events):
        from grnbl.digest import outings_post_reviewed
        sel = [{"i": i, "post": "week", "channel": "gratuit"} for i in range(len(events))]
        return outings_post_reviewed(events, self.now, selection=sel)

    def test_event_without_a_time_keeps_its_day_and_gets_no_hour(self):
        # The midnight trap (CLAUDE.md, Pièges): a date without a time parses as 00:00 and must not vanish.
        text = self.week([{"title": "Fête", "start": "2026-10-24", "venue": "Parc",
                           "review": {"keep": True, "free": True, "line": "l"}}])
        self.assertIn("*Fête*\nSamedi 24 oct. · Parc", text)
        self.assertNotIn(" à ", text.split("\n")[2])

    def test_event_with_a_time_shows_it_without_zero_minutes(self):
        text = self.week([{"title": "Concert", "start": "2026-10-24T20:00", "venue": "Salle",
                           "review": {"keep": True, "free": True, "line": "l"}},
                          {"title": "Visite", "start": "2026-10-25T14:30", "venue": "Musée",
                           "review": {"keep": True, "free": True, "line": "l"}}])
        self.assertIn("Samedi 24 oct. · 20h · Salle", text)
        self.assertIn("Dimanche 25 oct. · 14h30 · Musée", text)

    def test_event_just_after_midnight_keeps_its_time(self):
        from grnbl.digest import to_book_post
        night = {"title": "Nuit des étoiles", "start": "2026-10-24T00:30", "venue": "Bastille",
                 "review": {"keep": True, "free": True, "line": "l"}}
        self.assertIn("Samedi 24 oct. · 0h30 · Bastille", self.week([night]))
        night = {**night, "start": "2026-11-07T00:30", "booking": "required"}
        sel = [{"i": 0, "post": "to_book", "channel": "gratuit"}]
        self.assertIn("Samedi 7 nov. · 0h30", to_book_post([night], self.now, selection=sel))

    def test_week_without_editor_keeps_tomorrow_and_running_exhibitions_whatever_the_clock_seconds(self):
        # The midnight trap: "now" carries seconds; midnight must be 00:00:00, or a no-time start is misread.
        from datetime import datetime
        from grnbl.digest import outings_post_reviewed
        now = datetime(2026, 10, 21, 12, 0, 37, 250000, tzinfo=self.now.tzinfo)
        kept = {"keep": True, "free": True, "line": "l"}
        events = [{"title": "Demain", "start": "2026-10-22", "venue": "Parc", "review": kept},
                  {"title": "Expo longue", "start": "2026-10-01", "end": "2026-11-15", "venue": "Musée", "review": kept},
                  {"title": "Expo finie", "start": "2026-10-01", "end": "2026-10-20", "venue": "Musée", "review": kept},
                  {"title": "Ce soir", "start": "2026-10-21T20:00", "venue": "Salle", "review": kept},
                  {"title": "Trop loin", "start": "2026-11-20", "venue": "Salle", "review": kept}]
        text = outings_post_reviewed(events, now)
        self.assertIn("*Demain*\nJeudi 22 oct. · Parc", text)
        self.assertIn("*Expo longue*\nJusqu'au 15 nov. · Musée", text)
        for gone in ("Expo finie", "Ce soir", "Trop loin"):  # ended, same day (announced the day before), too far
            self.assertNotIn(gone, text)
        self.assertIn("2 sorties repérées, dont 2 gratuites", text)

    def test_nothing_this_week_means_no_post(self):
        from grnbl.digest import outings_post_reviewed, to_book_post
        self.assertIsNone(outings_post_reviewed([], self.now))
        self.assertIsNone(to_book_post([], self.now))
        self.assertIsNone(self.week([]))

    def test_shouting_venue_names_are_calmed_down(self):
        text = self.week([{"title": "Bal", "start": "2026-10-24T20:00", "venue": "SALLE DES FETES",
                           "review": {"keep": True, "free": True, "line": "l"}}])
        self.assertIn("· Salle Des Fetes", text)

    def test_to_book_post_announces_opening_and_deadline(self):
        from grnbl.digest import to_book_post
        events = [{"title": "Visite tour", "start": "2026-11-08T10:00", "booking": "required", "booking_opens": "2026-10-26T09:00",
                   "booking_url": "https://example.org/a", "review": {"keep": True, "free": True, "line": "l"}},
                  {"title": "Atelier", "start": "2026-10-31T14:00", "booking": "required", "booking_deadline": "2026-10-29",
                   "url": "https://example.org/b", "review": {"keep": True, "free": False, "line": "l"}}]
        sel = [{"i": 0, "post": "to_book", "channel": "gratuit"}, {"i": 1, "post": "to_book", "channel": "gratuit"}]
        text = to_book_post(events, self.now, selection=sel)
        self.assertIn("⏰ Réservations dès lundi 26 oct. · 9h : https://example.org/a", text)
        self.assertIn("👉 Réserver avant jeudi 29 oct. : https://example.org/b", text)
        self.assertIn("*Visite tour*\nDimanche 8 nov. · 10h", text)
        self.assertIn("*Atelier*\nSamedi 31 oct. · 14h", text)

    def test_fuel_post_lists_three_stations_and_the_saving_only_when_it_matters(self):
        from grnbl.digest import fuel_post
        from grnbl.items import Item
        top3 = [{"price": 1.589, "name": "Intermarché", "address": "av. A", "town": "SMH"},
                {"price": 1.604, "address": "rue B", "town": "Échirolles"},
                {"price": 1.695, "name": "Total", "address": "rue C", "town": "Grenoble"}]
        def item(saving):
            return Item(id="fuel:gazole", topic="fuel", title="Gazole", data={"fuel": "gazole", "label": "Gazole", "top3": top3,
                                                             "saving_tank": saving, "stations": 120})
        text = fuel_post([item(12.0)], self.now)
        self.assertIn("🥇 1,589 € · *Intermarché*, av. A, SMH", text)
        self.assertIn("🥈 1,604 € · rue B, Échirolles", text)
        self.assertIn("Jusqu'à 12 € d'écart", text)
        self.assertIn("120 stations", text)
        self.assertNotIn("écart", fuel_post([item(2.0)], self.now))



class EditedBlock(unittest.TestCase):
    """A block edited by hand in the board's preview is sent as written, in its slot."""

    def test_week_post_uses_the_edited_block(self):
        from datetime import datetime
        from grnbl.digest import outings_post_reviewed
        from zoneinfo import ZoneInfo
        now = datetime(2026, 10, 21, 12, 0, tzinfo=ZoneInfo("Europe/Paris"))
        events = [{"title": "A", "start": "2026-10-23T20:00", "venue": "Salle", "review": {"keep": True, "free": True, "line": "line A"}},
                  {"title": "B", "start": "2026-10-24T20:00", "venue": "Salle", "review": {"keep": True, "free": True, "line": "line B"},
                   "decision": {"status": "keep", "block": "🆓 *B, edited* · samedi\n   my own words"}}]
        sel = [{"i": 0, "post": "week", "channel": "gratuit"}, {"i": 1, "post": "week", "channel": "gratuit"}]
        text = outings_post_reviewed(events, now, selection=sel)
        self.assertIn("🆓 *B, edited* · samedi\n   my own words", text)
        self.assertIn("*A*", text)
        self.assertNotIn("line B", text)


if __name__ == "__main__":
    unittest.main()
