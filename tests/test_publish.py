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
        for target, name, value in ((publish, "DATA", self.tmp), (memory, "POSTED", self.tmp / "posted.json")):
            p = mock.patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_waiting_post_is_not_offered(self):
        report = dict(publish.run(DAY, send=True, items=[item("gratuit", False)]))
        self.assertIn("attente", report["gratuit-week"])

    def test_dry_run_changes_nothing(self):
        report = dict(publish.run(DAY, send=False, items=[item("gratuit", True)]))
        self.assertIn("essai", report["gratuit-week"])
        self.assertEqual(publish.status(DAY)["gratuit"]["week"]["status"], "ready")

    def test_posted_once_and_remembered(self):
        publish.run(DAY, send=True, items=[item("gratuit", True)])
        publish.mark_posted(DAY, "gratuit")
        report = dict(publish.run(DAY, send=True, items=[item("gratuit", True)]))
        self.assertEqual(report["gratuit-week"], "déjà envoyé")
        self.assertTrue(memory.already_posted({"title": "Visite", "start": "2026-10-20"}))

    def test_outings_slot_does_not_wait_for_the_fuel_or_alert_sources(self):
        # tick.send_slots runs publish for the outings groups only: a fuel or alert source that
        # is down must not stop them, so those sources are not even read.
        broken = mock.Mock(side_effect=RuntimeError("source down"))
        with mock.patch.object(publish.fuel, "collect", broken), mock.patch.object(publish.alerts, "collect", broken):
            self.assertEqual(publish.run(DAY, send=True, only=["gratuit", "sorties"]), [])
            with self.assertRaises(RuntimeError):  # the fuel run still reads its source
                publish.run(DAY, send=True, only=["carburant"])
        self.assertEqual(broken.call_count, 1)

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
        report = dict(publish.run(day, send=True, items=items))
        self.assertEqual(report["gratuit-week"], "à poster à la main")
        posted = json.loads((self.tmp / "outbox" / day.isoformat() / "gratuit-week.json").read_text())["text"]
        self.assertIn("Visite gratuite du fort.", posted)
        self.assertNotIn("ENGLISH", posted)


class ManualPosting(unittest.TestCase):
    """Elior pastes each approved post by hand, then marks it posted."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for target, name, value in ((publish, "DATA", self.tmp), (memory, "POSTED", self.tmp / "posted.json")):
            p = mock.patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_approved_post_waits_for_a_human(self):
        report = dict(publish.run(DAY, send=True, items=[item("gratuit", True), item("sorties", False)]))
        self.assertEqual(report["gratuit-week"], "à poster à la main")
        self.assertEqual(publish.status(DAY)["gratuit"]["week"]["status"], "to_post")

    def test_marked_posted_once_and_remembered(self):
        publish.run(DAY, send=True, items=[item("gratuit", True), item("sorties", False)])
        self.assertEqual(publish.mark_posted(DAY, "gratuit"), ["gratuit-week"])
        self.assertEqual(publish.mark_posted(DAY, "gratuit"), [])
        self.assertEqual(publish.mark_posted(DAY, "sorties"), [])  # not approved: never marked
        self.assertTrue(publish.status(DAY)["gratuit"]["week"]["by_hand"])
        self.assertIn("visite|2026-10-20", (self.tmp / "posted.json").read_text())


if __name__ == "__main__":
    unittest.main()
