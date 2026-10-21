"""Offline tests: the structured readers and how repeated sessions are merged."""

import unittest
from datetime import date

from datetime import datetime

from grnbl import channels, factcheck
from grnbl.digest import alerts_post
from grnbl.sources import alerts
from grnbl.scrape import jsonld, tourisme, tribe
from grnbl.scrape.extract import category_of
from grnbl.scrape.run import collapse, next_postable


class Tribe(unittest.TestCase):
    def test_room_gets_the_venue_name_and_time_is_kept(self):
        e = tribe.convert({
            "title": "Le Sommet des dieux", "start_date": "2026-11-04 20:00:00", "end_date": "2026-11-04 20:00:00",
            "all_day": False, "cost": "40€", "cost_details": {"values": ["40"]},
            "venue": {"venue": "Auditorium", "city": ""}, "url": "https://x/", "excerpt": "",
            "description": "<p>Un ciné-concert.</p>", "categories": [{"name": "Ciné Concert"}],
        }, {"place": "MC2", "town": "Grenoble"})
        self.assertEqual((e["start"], e["end"]), ("2026-11-04T20:00", None))
        self.assertEqual((e["venue"], e["town"]), ("MC2, Auditorium", "Grenoble"))
        self.assertEqual((e["free"], e["category"], e["description"]), (False, "concert", "Un ciné-concert."))

    def test_free_and_page_builder_codes_removed(self):
        e = tribe.convert({
            "title": "Jam", "start_date": "2026-10-22 00:00:00", "end_date": "2026-10-22 23:59:59", "all_day": True,
            "cost": "Gratuit", "venue": [], "description": '[et_pb_section fb_built="1"]Histoires[/et_pb_section]',
        })
        self.assertEqual((e["start"], e["free"], e["description"]), ("2026-10-22", True, "Histoires"))


class Labels(unittest.TestCase):
    def test_site_type_labels(self):
        self.assertEqual(category_of("Spectacle, Cirque"), "theatre")
        self.assertEqual(category_of("Visite guidée et/ou commentée"), "visit")
        self.assertEqual(category_of("Vide greniers"), "market")
        self.assertEqual(category_of("Spectacle, One man Show / One woman show"), "humour")
        self.assertIsNone(category_of(""))


class TouristOfficeSessions(unittest.TestCase):
    PERIODS = ("Dimanche 4 octobre 2026 de 14h30 à 15h30.\nDimanche 1er novembre 2026 de 14h30 à 15h30.\n"
               "Dimanche 6 décembre 2026 de 14h30 à 15h30.")

    def test_year_long_range_becomes_its_next_sessions(self):
        e = tourisme.sessions({"start": "2026-01-04", "end": "2026-12-06", "periods": self.PERIODS},
                              date(2026, 10, 18), date(2026, 12, 17))
        self.assertEqual((e["start"], e["end"]), ("2026-11-01T14:30", None))
        self.assertEqual(e["dates"], ["2026-11-01T14:30", "2026-12-06T14:30"])

    def test_all_sessions_past_drops_the_event(self):
        self.assertIsNone(tourisme.sessions({"start": "2026-01-04", "periods": self.PERIODS},
                                            date(2026, 12, 20), date(2027, 2, 1)))


class Series(unittest.TestCase):
    def test_sessions_of_one_tour_become_one_event(self):
        got = collapse([
            {"title": "Visites flash", "venue": "Musée", "start": "2026-10-25T15:00"},
            {"title": "Visites flash", "venue": "Musée", "start": "2026-10-21T15:00", "price": "Gratuit"},
            {"title": "Visites flash", "venue": "Autre lieu", "start": "2026-10-22T15:00"},
        ])
        self.assertEqual(len(got), 2)
        tour = next(e for e in got if e["venue"] == "Musée")
        self.assertEqual(tour["start"], "2026-10-21T15:00")
        self.assertEqual(tour["dates"], ["2026-10-21T15:00", "2026-10-25T15:00"])

    def test_session_too_close_to_book_moves_to_the_next(self):
        e = {"title": "Atelier", "booking": "required", "start": "2026-10-19T10:00",
             "dates": ["2026-10-19T10:00", "2026-10-26T10:00"]}
        next_postable(e, date(2026, 10, 18))
        self.assertEqual(e["start"], "2026-10-26T10:00")


class Channels(unittest.TestCase):
    def test_each_group_takes_only_its_theme(self):
        broc = {"title": "Vide-grenier à Eybens", "category": "market", "free": True}
        walk = {"title": "Oiseaux des milieux forestiers", "description": "Sortie nature avec la LPO"}
        kids = {"title": "Atelier", "review": {"family": True, "free": False}}
        show = {"title": "Concert", "category": "concert", "review": {"free": False}}
        self.assertEqual([c for c in channels.CHANNELS if channels.accepts(c, broc)], ["gratuit", "sorties", "bonsplans"])
        self.assertTrue(channels.accepts("nature", walk))
        self.assertFalse(channels.accepts("nature", {"title": "Balade théâtralisée - Cadavres exquis",
                                                     "venue": "Musée archéologique"}))
        self.assertTrue(channels.accepts("famille", kids))
        self.assertFalse(any(channels.accepts(c, show) for c in ("gratuit", "famille", "bonsplans", "nature")))


class JsonLdDates(unittest.TestCase):
    def test_french_and_timezone_dates(self):
        self.assertEqual(jsonld._iso("18/10/2026"), "2026-10-18")
        self.assertEqual(jsonld._iso("2026-10-18T09:00:00+02:00"), "2026-10-18T09:00")
        self.assertEqual(jsonld._iso("2026-10-18T00:00:00"), "2026-10-18")
        self.assertEqual(jsonld._town("Grenoble-38"), "Grenoble")


class Alerts(unittest.TestCase):
    def test_air_index_and_comment_from_the_page(self):
        page = ('{"2026-10-19":{"indice_atmo":3.2,"indice_stat":"x"}} '
                '{"2026-10-19":"Lundi 19 octobre, \\u00e9pisode de pollution aux particules fines attendu."}')
        got = alerts.parse_air(page)["2026-10-19"]
        self.assertEqual(round(got["index"]), 3)
        self.assertTrue(got["comment"].startswith("Lundi 19 octobre, épisode"))

    def test_only_strikes_and_network_stops(self):
        now = datetime(2026, 10, 18, 10, 0)
        records = {
            "a": {"listeLigne": "SEM_A,SEM_B", "dateDebut": "19/10/2026 05:00", "dateFin": "19/10/2026 23:00",
                  "texte": "Grève : trafic très perturbé|Mouvement social : aucun tram sur les lignes A et B. Bus de secours."},
            "n": {"listeLigne": "SEM_A", "dateDebut": "19/10/2026 22:00", "dateFin": "23/10/2026 02:00",
                  "texte": "A : travaux de nuit|Pas de tram entre Gares et Chavant après 22 h."},
            "b": {"listeLigne": "SEM_C5", "dateDebut": "15/07/2026 04:00", "dateFin": "19/12/2026 03:00",
                  "texte": "C5 : travaux|depuis l'été"},
            "c": {"listeLigne": "TPV_569", "dateDebut": "18/10/2026 14:00", "dateFin": "31/12/2050 23:59", "texte": "x|y"},
        }
        got = alerts.transit_from(records, now)
        self.assertEqual([(a["lines"], a["detail"]) for a in got],
                         [(["A", "B"], "Mouvement social : aucun tram sur les lignes A et B.")])

    def test_quiet_day_no_post(self):
        self.assertIsNone(alerts_post([], datetime(2026, 10, 18, 10, 0)))


class FactCheck(unittest.TestCase):
    EVENT = {"title": "BLUES TOUR/ ALEX HENLEY", "start": "2026-10-22T20:00", "venue": "Le Trankilou",
             "description": "TEXAS SOUL BLUES TOUR WITH ALEX HENLEY"}

    def test_facts_from_the_page_pass(self):
        self.assertEqual(factcheck.check("Jeudi 22 octobre à 20h, Alex Henley au Trankilou.", self.EVENT), [])

    def test_any_day_of_a_run_passes(self):
        run = {"title": "Jeu de piste", "start": "2026-10-17", "end": "2026-11-01"}
        self.assertEqual(factcheck.check("Samedi 24 octobre, jeu de piste.", run), [])

    def test_added_name_number_and_wrong_weekday_are_flagged(self):
        got = factcheck.check("Mardi 22 octobre, Alex Henley et l'Orchestre national, 12 €.", self.EVENT)
        self.assertEqual(got, ["mardi 22 octobre (c'est un jeudi)", "orchestre", "12"])

    def test_wrong_weekday_in_the_short_form_of_the_posts_is_flagged(self):
        self.assertEqual(factcheck.wrong_weekdays("Mardi 22/10 à 20h", 2026), ["mardi 22/10 (c'est un jeudi)"])
        self.assertEqual(factcheck.wrong_weekdays("Jeudi 22/10 à 20h", 2026), [])
        # A time after a comma is not a month.
        self.assertEqual(factcheck.wrong_weekdays("Samedi 7, 10 h", 2026), [])

    def test_a_january_day_named_by_a_december_event_is_checked_in_the_next_year(self):
        winter = {"title": "Marché de Noël", "start": "2026-12-01", "end": "2027-01-03"}
        # 3 January 2027 is a Sunday; read in 2026 it would wrongly be a Saturday.
        self.assertEqual(factcheck.check("Dimanche 3 janvier, dernier jour du marché de Noël.", winter), [])


if __name__ == "__main__":
    unittest.main()
