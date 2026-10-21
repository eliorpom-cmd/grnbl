"""Offline tests: grnbl reads sites politely (robots.txt, one page a second per site)."""

import tempfile
import time
import unittest
import urllib.robotparser
from pathlib import Path
from unittest import mock

from grnbl.scrape import fetch


def rules(text):
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(text.splitlines())
    return rp


class Polite(unittest.TestCase):
    def setUp(self):
        fetch._robots.clear()
        fetch._last_hit.clear()
        self.addCleanup(fetch._robots.clear)
        self.addCleanup(fetch._last_hit.clear)

    def test_disallowed_page_is_never_downloaded(self):
        fetch._robots["https://site.example"] = rules("User-agent: *\nDisallow: /private/")
        with mock.patch("urllib.request.urlopen") as get:
            with self.assertRaisesRegex(RuntimeError, "robots.txt"):
                fetch.fetch("x", "https://site.example/private/page", path=Path(tempfile.mkdtemp()) / "p.html")
        get.assert_not_called()
        self.assertTrue(fetch.allowed("https://site.example/agenda"))

    def test_no_robots_txt_means_allowed(self):
        fetch._robots["https://open.example"] = None
        self.assertTrue(fetch.allowed("https://open.example/anything"))

    def test_same_site_waits_its_turn_other_sites_do_not(self):
        fetch._robots["https://a.example"] = rules("User-agent: *\nCrawl-delay: 1")
        fetch._robots["https://b.example"] = None
        with mock.patch.object(fetch, "MIN_GAP", 0.1):
            t = time.monotonic()
            fetch._wait_turn("https://a.example/1")
            fetch._wait_turn("https://b.example/1")
            self.assertLess(time.monotonic() - t, 0.1)
            fetch._wait_turn("https://a.example/2")
            self.assertGreaterEqual(time.monotonic() - t, 0.99)

    def test_says_who_it_is(self):
        self.assertTrue(fetch.UA.startswith("grnbl/"))
        self.assertNotIn("Mozilla", fetch.UA)


if __name__ == "__main__":
    unittest.main()
