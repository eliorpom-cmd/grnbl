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


if __name__ == "__main__":
    unittest.main()
