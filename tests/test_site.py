"""Offline tests: the static site built from a small fake edition."""

import json
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

from grnbl import digest, site
from grnbl.digest import PARIS

FIXTURE = Path(__file__).parent / "fixtures" / "site_edition.json"
SETTINGS = {"url": "https://example.test", "umami": "", "links": False}


def edition():
    data = json.loads(FIXTURE.read_text())
    return date.fromisoformat(data["day"]), data["events"], data["selection"]


class Site(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp()) / "site"
        self.day, self.events, self.selection = edition()

    def build(self, **settings):
        return site.build(self.day, self.events, self.selection, self.out, {**SETTINGS, **settings}, og_image=None)

    def read(self, rel):
        return (self.out / rel).read_text()

    def test_one_page_per_posted_event(self):
        slugs = self.build()
        self.assertEqual(sorted(slugs), sorted(["tour-perret-visite-des-95-metres-25-10", "bourse-aux-skis-de-meylan-24-10",
                                                "les-rencontres-cine-montagne-22-10", "atelier-dessin-famille-28-10"]))
        for name in ("index.html", "404.html", "sitemap.xml", "robots.txt"):
            self.assertTrue((self.out / name).exists(), name)

    def test_dropped_event_has_no_page(self):
        self.build()
        self.assertNotIn("retire", " ".join(p.name for p in (self.out / "e").iterdir()))
        self.assertNotIn("Concert retiré", self.read("index.html"))

    def test_event_page_facts_and_button(self):
        self.build()
        page = self.read("e/tour-perret-visite-des-95-metres-25-10/index.html")
        self.assertIn("dimanche 25 octobre à 10 h", page)
        self.assertIn("Parc Paul-Mistral, Grenoble", page)
        self.assertIn("Gratuit", page)
        self.assertIn('href="https://example.org/perret/reserver"', page)
        self.assertIn('data-umami-event="reserve_click"', page)
        self.assertIn(">Réserver<", page)
        # WhatsApp marks are stripped, the source's own text never appears.
        self.assertIn("en haut de la tour Perret", page)
        self.assertNotIn("SOURCE TEXT", page)
        # Shared by two groups: one page, both labels.
        self.assertIn("🆓 Gratuit", page)
        self.assertIn("🎭 Sorties", page)

    def test_event_without_booking_links_to_organiser(self):
        self.build()
        page = self.read("e/bourse-aux-skis-de-meylan-24-10/index.html")
        self.assertIn("Voir la page de l'organisateur", page)
        self.assertIn("Salle Des Fêtes De Meylan", page)

    def test_booking_opening_and_other_dates(self):
        self.build()
        page = self.read("e/atelier-dessin-famille-28-10/index.html")
        self.assertIn("Réservations à partir du lundi 26 octobre à 9 h", page)
        self.assertIn("jeudi 29 octobre à 14 h 30", page)

    def test_zoom_moment_and_escaping(self):
        self.build()
        page = self.read("e/les-rencontres-cine-montagne-22-10/index.html")
        self.assertIn("Le moment à ne pas manquer", page)
        self.assertIn("Les Rencontres &lt;Ciné&gt; Montagne", page)
        self.assertNotIn("<Ciné>", page)

    def test_site_url_is_the_only_setting_for_links(self):
        self.build(url="https://grnbl.xyz")
        self.assertIn('<link rel="canonical" href="https://grnbl.xyz/e/bourse-aux-skis-de-meylan-24-10">',
                      self.read("e/bourse-aux-skis-de-meylan-24-10/index.html"))
        self.assertIn("<loc>https://grnbl.xyz/e/atelier-dessin-famille-28-10/</loc>", self.read("sitemap.xml"))
        self.assertIn("Sitemap: https://grnbl.xyz/sitemap.xml", self.read("robots.txt"))

    def test_umami_tag_only_with_an_id(self):
        self.build()
        self.assertNotIn("stats.byelior.dev", self.read("index.html"))
        self.build(umami="abc-123")
        self.assertIn('data-website-id="abc-123"', self.read("index.html"))

    def test_index_groups_and_count(self):
        self.build()
        page = self.read("index.html")
        self.assertIn("mercredi 21 octobre 2026", page)
        self.assertIn("4 sorties", page)
        self.assertLess(page.index("🆓 Gratuit"), page.index("🎭 Sorties"))

    def test_og_image_copied_when_present(self):
        img = Path(tempfile.mkdtemp()) / "og.png"
        img.write_bytes(b"\x89PNG fake")
        site.build(self.day, self.events, self.selection, self.out, SETTINGS, og_image=img)
        self.assertTrue((self.out / "og.png").exists())
        self.assertIn('property="og:image" content="https://example.test/og.png"', self.read("index.html"))


class PostLinks(unittest.TestCase):
    """The WhatsApp posts do not change unless links are switched on."""

    def setUp(self):
        _, self.events, self.selection = edition()
        for i, e in enumerate(self.events):
            e["i"] = i
        self.now = datetime(2026, 10, 21, 12, tzinfo=PARIS)
        self.sel = [p for p in self.selection if p["channel"] == "gratuit"]

    def post(self, env):
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(site, "SETTINGS", Path("/nonexistent")):
            return digest.to_book_post(self.events, self.now, selection=self.sel)

    def test_links_off_by_default(self):
        text = self.post({"SITE_LINKS": "", "SITE_URL": ""})
        self.assertIn("https://example.org/perret/reserver", text)
        self.assertNotIn("/e/", text)

    def test_links_on_point_to_the_page(self):
        text = self.post({"SITE_LINKS": "1", "SITE_URL": "https://example.test"})
        self.assertIn("https://example.test/e/tour-perret-visite-des-95-metres-25-10", text)

    def test_settings_file_switch(self):
        tmp = Path(tempfile.mkdtemp()) / "site.json"
        tmp.write_text(json.dumps({"links": True, "url": "https://grnbl.xyz/"}))
        with mock.patch.dict(os.environ, {"SITE_LINKS": "", "SITE_URL": ""}), mock.patch.object(site, "SETTINGS", tmp):
            self.assertEqual(site.post_link(self.events[1]), "https://grnbl.xyz/e/bourse-aux-skis-de-meylan-24-10")


if __name__ == "__main__":
    unittest.main()
