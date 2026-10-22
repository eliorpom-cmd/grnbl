"""Downloads a page politely, and keeps a dated copy on disk.

Politely means: grnbl says who it is (no browser disguise), reads each site's
robots.txt and skips what it disallows, honours its Crawl-delay, and waits at
least a second between two pages of the same site. On 21/10/2026 none of the
45 sites read disallowed our pages, and all of them answered the honest name.

The copy matters twice: re-running the extraction does not hit the site again,
and when an extracted event looks wrong the page it came from is still there.
"""

from __future__ import annotations

import gzip
import ssl
import threading
import time
import urllib.error
import urllib.request
import urllib.robotparser
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from ..http import USER_AGENT

RAW = Path(__file__).resolve().parents[2] / "data" / "raw"
UA = USER_AGENT
MIN_GAP = 1.0  # seconds between two requests to the same site, unless its robots.txt asks for more

_STRICT_OFF = ssl.create_default_context()
_STRICT_OFF.verify_flags &= ~ssl.VERIFY_X509_STRICT
# Some small venues serve a broken certificate chain. The pages are public
# listings and nothing is sent, so a second try without verification is fine.
_UNVERIFIED = ssl._create_unverified_context()


_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
_last_hit: dict[str, float] = {}
_lock = threading.Lock()


def _rules(url: str) -> urllib.robotparser.RobotFileParser | None:
    """The site's robots.txt, read once per run. None when it has none (everything is allowed)."""
    parts = urlsplit(url)
    site = f"{parts.scheme}://{parts.netloc}"
    with _lock:
        if site in _robots:
            return _robots[site]
    rp = urllib.robotparser.RobotFileParser()
    try:
        req = urllib.request.Request(site + "/robots.txt", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15, context=_STRICT_OFF) as resp:
            rp.parse(resp.read().decode("utf-8", errors="ignore").splitlines())
    except Exception:  # noqa: BLE001 - no robots.txt (404) or unreachable: no rules to follow
        rp = None
    with _lock:
        _robots[site] = rp
    return rp


def allowed(url: str) -> bool:
    rp = _rules(url)
    return rp is None or rp.can_fetch(UA, url)


def _wait_turn(url: str) -> None:
    """At most one request per MIN_GAP (or the site's Crawl-delay) to the same site, across threads."""
    rp, host = _rules(url), urlsplit(url).netloc
    gap = max(MIN_GAP, float((rp.crawl_delay(UA) if rp else None) or 0))
    while True:
        with _lock:
            wait = _last_hit.get(host, 0) + gap - time.monotonic()
            if wait <= 0:
                _last_hit[host] = time.monotonic()
                return
        time.sleep(wait)


def fetch(source_id: str, url: str, today: date | None = None, refresh: bool = False,
          path: Path | None = None) -> str:
    """`path` overrides the dated copy, for pages kept across days (event detail pages)."""
    today = today or date.today()
    path = path or RAW / today.isoformat() / f"{source_id}.html"
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8", errors="ignore")
    if not allowed(url):
        raise RuntimeError(f"{source_id}: robots.txt disallows {url}")
    headers = {"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9", "Accept-Encoding": "gzip",
               "Accept": "text/html,application/xhtml+xml"}
    last = None
    for ctx in (_STRICT_OFF, _UNVERIFIED):
        for _ in range(2):
            try:
                _wait_turn(url)
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                    body = resp.read()
                    if resp.headers.get("Content-Encoding") == "gzip":
                        body = gzip.decompress(body)
                    charset = resp.headers.get_content_charset() or "utf-8"
                    html = body.decode(charset, errors="ignore")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(html, encoding="utf-8")
                return html
            except (ssl.SSLError, urllib.error.URLError) as e:
                last = e
                # urlopen wraps certificate errors in URLError: no point retrying with the same context.
                if isinstance(e, ssl.SSLError) or isinstance(e.reason, ssl.SSLError):
                    break  # try the next context
                time.sleep(2)
            except Exception as e:  # noqa: BLE001 - any network failure: retry once, then give up
                last = e
                time.sleep(2)
    raise RuntimeError(f"{source_id}: {last}")
