"""Offline tests: only approved posts go out, and never twice."""

import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

from grnbl import memory, publish, translate

DAY = date(2026, 10, 17)


def item(channel, approved, title="Visite"):
    return {"channel": channel, "post": "week", "text": f"post {channel}", "approved": approved,
            "events": [{"title": title, "start": "2026-10-20"}]}


class Publish(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for target, name, value in ((publish, "DATA", self.tmp), (publish, "CONFIG", self.tmp / "whatsapp.json"),
                                    (memory, "POSTED", self.tmp / "posted.json")):
            p = mock.patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)
        (self.tmp / "whatsapp.json").write_text(json.dumps({"gratuit": "1@newsletter", "sorties": "2@newsletter"}))

    def run_publish(self, items, send=True):
        with mock.patch.object(publish, "deliver", return_value="MSG1") as deliver:
            report = dict(publish.run(DAY, send=send, items=items))
        return report, deliver

    def test_waiting_post_is_not_sent(self):
        report, deliver = self.run_publish([item("gratuit", False)])
        self.assertEqual(deliver.call_count, 0)
        self.assertIn("attente", report["gratuit-week"])

    def test_dry_run_sends_nothing(self):
        _, deliver = self.run_publish([item("gratuit", True)], send=False)
        self.assertEqual(deliver.call_count, 0)

    def test_sent_once_and_remembered(self):
        self.run_publish([item("gratuit", True)])
        report, deliver = self.run_publish([item("gratuit", True)])
        self.assertEqual(deliver.call_count, 0)
        self.assertEqual(report["gratuit-week"], "déjà envoyé")
        self.assertTrue(memory.already_posted({"title": "Visite", "start": "2026-10-20"}))

    def test_one_failure_does_not_stop_the_others(self):
        with mock.patch.object(publish, "deliver", side_effect=[RuntimeError("offline"), "MSG2"]):
            report = dict(publish.run(DAY, send=True, items=[item("gratuit", True), item("sorties", True, "Bal")]))
        self.assertIn("échec", report["gratuit-week"])
        self.assertEqual(report["sorties-week"], "envoyé")
        self.assertFalse(memory.already_posted({"title": "Visite", "start": "2026-10-20"}))

    def test_english_translation_is_never_published(self):
        # A real edition day on disk: one approved free outing picked for the Gratuit group.
        day, now = date(2026, 10, 21), datetime(2026, 10, 20, 11, 0, tzinfo=publish.PARIS)
        folder = self.tmp / "events" / day.isoformat()
        folder.mkdir(parents=True)
        (folder / "reviewed.json").write_text(json.dumps([{
            "title": "Visite du fort", "start": "2026-10-24T14:00", "venue": "Bastille", "free": True, "booking": "none",
            "review": {"keep": True, "score": 4, "free": True, "line": "Visite gratuite du fort, sans réserver."}}]))
        (folder / "selection.json").write_text(json.dumps([{"i": 0, "post": "week", "channel": "gratuit", "line": "Visite gratuite du fort."}]))
        (self.tmp / "decisions").mkdir()
        (self.tmp / "decisions" / f"{day.isoformat()}.json").write_text(json.dumps({"0": {"status": "keep", "line": None}}))
        with mock.patch.object(translate, "DATA", self.tmp), \
                mock.patch.object(translate, "translate", return_value="ENGLISH: free visit of the fort.") as model:
            self.assertEqual(translate.run(day, now), {"gratuit/week": "translated"})
            self.assertEqual(translate.run(day, now), {"gratuit/week": "unchanged"})  # same French text, no new call
            stored = translate.load(day)["gratuit/week"]
        self.assertEqual(model.call_count, 1)
        self.assertEqual(stored["en"], "ENGLISH: free visit of the fort.")
        items = publish.outbox(day, now, fuel_text="", alerts_text="")
        self.assertEqual([i["text"] for i in items], [stored["fr"]])
        with mock.patch.object(publish, "deliver", return_value="MSG1") as deliver:
            report = dict(publish.run(day, send=True, items=items))
        self.assertEqual(report["gratuit-week"], "envoyé")
        sent = deliver.call_args.args[1]
        self.assertIn("Visite gratuite du fort.", sent)
        self.assertNotIn("ENGLISH", sent)


if __name__ == "__main__":
    unittest.main()
