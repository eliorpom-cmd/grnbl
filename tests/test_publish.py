"""Offline tests: only approved posts go out, and never twice."""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from grnbl import memory, publish

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


if __name__ == "__main__":
    unittest.main()
