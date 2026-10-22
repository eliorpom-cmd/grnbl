"""Offline tests: the parsers that turn messy source data into Items."""

import unittest
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from grnbl.sources.fuel import cheapest_by_fuel
from grnbl.sources.museums import parse_occurrences, parse_range, items_from

PARIS = ZoneInfo("Europe/Paris")


class MuseumDates(unittest.TestCase):
    def test_sessions_with_hours_and_first_of_month(self):
        got = parse_occurrences("Dimanche 1er novembre 2026 de 14h30 à 16h.\n\nJeudi 12 novembre 2026 à partir de 18h30.")
        self.assertEqual(got[0], (datetime(2026, 11, 1, 14, 30, tzinfo=PARIS), datetime(2026, 11, 1, 16, 0, tzinfo=PARIS)))
        self.assertEqual(got[1], (datetime(2026, 11, 12, 18, 30, tzinfo=PARIS), None))

    def test_an_impossible_day_skips_that_session_only(self):
        got = parse_occurrences("Mardi 31 novembre 2026 de 14h à 15h.\n\nJeudi 12 novembre 2026 de 25h à 26h."
                                "\n\nDimanche 15 novembre 2026 à partir de 10h.")
        self.assertEqual(got, [(datetime(2026, 11, 15, 10, 0, tzinfo=PARIS), None)])

    def test_exhibition_range_with_and_without_year(self):
        self.assertEqual(parse_range("Du 25/04/2026 au 25/04/2027 le mardi", date(2026, 10, 17)),
                         (date(2026, 4, 25), date(2027, 4, 25)))
        self.assertEqual(parse_range("Du 01/01 au 30/05 le mardi", date(2026, 10, 17)),
                         (date(2026, 1, 1), date(2026, 5, 30)))

    def test_only_upcoming_sessions_and_no_sold_out(self):
        now = datetime(2026, 10, 17, 9, 0, tzinfo=PARIS)
        records = [
            {"id": "1", "nom": "Visite", "tarif_type": "GRATUIT",
             "horaires_ouverture": "Vendredi 16 octobre 2026 de 10h à 11h.\n\nDimanche 18 octobre 2026 de 10h30 à 12h."},
            {"id": "2", "nom": "COMPLET | Atelier", "tarif_type": "PAYANT",
             "horaires_ouverture": "Dimanche 18 octobre 2026 de 14h à 15h."},
        ]
        items = items_from(records, now)
        self.assertEqual([i.id for i in items], ["musees:1:202610181030"])
        self.assertTrue(items[0].free)


class Fuel(unittest.TestCase):
    def station(self, id, price, age_days=0):
        now = datetime(2026, 10, 17, 7, tzinfo=timezone.utc)
        return {"id": id, "adresse": "rue x", "ville": "GRENOBLE", "latitude": "45.1", "longitude": "5.7",
                "gazole_prix": price, "gazole_maj": (now - timedelta(days=age_days)).isoformat()}

    def test_cheapest_and_saving_on_a_tank(self):
        now = datetime(2026, 10, 17, 8, tzinfo=timezone.utc)
        items = cheapest_by_fuel([self.station("a", 2.30), self.station("b", 2.10), self.station("c", 2.50)], now)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].data["price"], 2.10)
        self.assertEqual(items[0].data["saving_tank"], 20.0)

    def test_a_stale_price_is_ignored(self):
        now = datetime(2026, 10, 17, 8, tzinfo=timezone.utc)
        items = cheapest_by_fuel([self.station("old", 1.50, age_days=10), self.station("a", 2.3), self.station("b", 2.4)], now)
        self.assertEqual(items[0].data["price"], 2.3)


class Fetch(unittest.TestCase):
    def test_a_broken_certificate_goes_straight_to_the_second_try(self):
        import ssl
        import tempfile
        import urllib.error
        from pathlib import Path
        from unittest import mock
        from grnbl.scrape import fetch

        class Page:
            headers = mock.Mock(get=lambda *a: None, get_content_charset=lambda: "utf-8")
            def read(self): return b"<p>agenda</p>"
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def urlopen(req, timeout, context):
            if context is fetch._STRICT_OFF:
                raise urllib.error.URLError(ssl.SSLCertVerificationError("bad chain"))
            return Page()

        out = Path(tempfile.mkdtemp()) / "page.html"
        with mock.patch.object(fetch.urllib.request, "urlopen", side_effect=urlopen) as opened, \
                mock.patch.object(fetch.time, "sleep") as slept:
            self.assertEqual(fetch.fetch("salle", "https://x.test", path=out), "<p>agenda</p>")
        self.assertEqual((opened.call_count, slept.call_count), (2, 0))


if __name__ == "__main__":
    unittest.main()
