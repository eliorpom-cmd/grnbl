"""Offline tests: what has been read or judged once is not sent to the AI again."""

import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from grnbl.scrape import extract, review

TODAY = date(2026, 10, 17)
SOURCE = {"id": "salle", "name": "Salle", "url": "https://example.org/agenda"}


class UnchangedPage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.object(extract, "SEEN", Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_twice(self, first: str, second: str, later: date):
        answer = json.dumps([{"title": "Concert", "start": "2026-10-20"}, {"title": "Expo", "start": "2026-10-18"}])
        with mock.patch.object(extract, "ask", return_value=answer) as ask:
            extract.events(first, SOURCE, TODAY, TODAY + timedelta(days=60))
            found = extract.events(second, SOURCE, later, later + timedelta(days=60))
        return ask.call_count, found

    def test_same_text_is_not_read_again_and_past_events_drop(self):
        calls, found = self.run_twice("page", "page", date(2026, 10, 19))
        self.assertEqual(calls, 1)
        self.assertEqual([e["title"] for e in found], ["Concert"])

    def test_changed_text_is_read_again(self):
        calls, _ = self.run_twice("page", "page with a new show", TODAY)
        self.assertEqual(calls, 2)

    def test_old_reading_is_not_trusted(self):
        calls, _ = self.run_twice("page", "page", TODAY + timedelta(days=extract.REUSE_DAYS + 1))
        self.assertEqual(calls, 2)


class JudgedOnce(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for target, value in ((review, "SEEN"), (review.memory, "POSTED")):
            p = mock.patch.object(target, value, Path(self.tmp.name) / value)
            p.start()
            self.addCleanup(p.stop)
        for name, value in (("start_dates", {}), ("past_decisions", [])):
            p = mock.patch.object(review.memory, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def ev(self, title, **kw):
        return {"title": title, "start": "2026-10-20", "booking": "none", **kw}

    def fake_ask(self, prompt, **kw):
        chunk = json.loads(prompt.split("EVENTS:\n", 1)[1])
        self.asked.extend(e["title"] for e in chunk)
        return json.dumps([{"i": e["i"], "keep": True, "score": 4, "line": e["title"],
                            "duplicate_of": 0 if e["title"] == "Fête (bis)" else None} for e in chunk])

    def judge(self, events):
        self.asked = []
        with mock.patch.object(review, "ask", side_effect=self.fake_ask):
            return review.review(events, TODAY)

    def test_only_new_or_changed_events_are_asked(self):
        self.judge([self.ev("Fête"), self.ev("Fête (bis)"), self.ev("Bal")])
        out = self.judge([self.ev("Fête"), self.ev("Fête (bis)"), self.ev("Bal", price="5 €"), self.ev("Nouveau")])
        self.assertEqual(sorted(self.asked), ["Bal", "Nouveau"])
        self.assertEqual(out[0]["review"]["score"], 4)
        # A remembered duplicate still points at today's position of the other event.
        self.assertEqual(out[1]["review"]["duplicate_of"], 0)


    def test_a_duplicate_must_point_to_an_earlier_event(self):
        # The model sometimes marks both copies, or an event as its own duplicate: one copy must stay.
        answer = json.dumps([{"i": 0, "keep": True, "duplicate_of": 1}, {"i": 1, "keep": True, "duplicate_of": 0},
                             {"i": 2, "keep": True, "duplicate_of": 2}, {"i": 3, "keep": True, "duplicate_of": "0"}])
        with mock.patch.object(review, "ask", return_value=answer):
            out = review.review([self.ev("Fête"), self.ev("Fête !"), self.ev("Bal"), self.ev("Expo")], TODAY)
        self.assertEqual([e["review"]["duplicate_of"] for e in out], [None, 0, None, None])
        from grnbl.digest import chosen
        self.assertEqual([e["title"] for e in chosen(out)], ["Fête", "Bal", "Expo"])


if __name__ == "__main__":
    unittest.main()
