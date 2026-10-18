"""Offline tests: a swapped line takes the removed pick's slot, a plain removal takes the next reserve."""

import unittest

from grnbl.digest import picked


def ev(title, decision=None):
    return {"title": title, "decision": decision, "review": {"line": f"line {title}"}}


SEL = [{"i": 0, "post": "week"}, {"i": 1, "post": "week"}, {"i": 2, "post": "week"},
       {"i": 3, "post": "week", "reserve": True}, {"i": 4, "post": "week", "reserve": True}]


def titles(events):
    return [e["title"] for e, _ in picked(events, SEL, "week")]


class Swap(unittest.TestCase):
    def test_untouched(self):
        self.assertEqual(titles([ev(t) for t in "ABCDEF"]), ["A", "B", "C"])

    def test_removed_pick_gets_next_reserve_in_its_slot(self):
        events = [ev(t) for t in "ABCDEF"]
        events[1]["decision"] = {"status": "drop"}
        self.assertEqual(titles(events), ["A", "D", "C"])

    def test_swap_takes_the_slot_with_the_chosen_event(self):
        events = [ev(t) for t in "ABCDEF"]
        events[1]["decision"] = {"status": "drop", "replaced_by": 5}
        self.assertEqual(titles(events), ["A", "F", "C"])
        self.assertEqual(picked(events, SEL, "week")[1][1], "line F")

    def test_swap_to_a_reserve_does_not_use_it_twice(self):
        events = [ev(t) for t in "ABCDEF"]
        events[0]["decision"] = {"status": "drop", "replaced_by": 3}
        events[2]["decision"] = {"status": "drop"}
        self.assertEqual(titles(events), ["D", "B", "E"])

    def test_swap_to_a_dropped_event_falls_back_to_reserve(self):
        events = [ev(t) for t in "ABCDEF"]
        events[1]["decision"] = {"status": "drop", "replaced_by": 5}
        events[5]["decision"] = {"status": "drop"}
        self.assertEqual(titles(events), ["A", "D", "C"])


if __name__ == "__main__":
    unittest.main()
