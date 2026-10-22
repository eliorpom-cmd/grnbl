"""Downloads a page like a browser would, and keeps a dated copy on disk.

The copy matters twice: re-running the extraction does not hit the site again,
and when an extracted event looks wrong the page it came from is still there.
"""

from __future__ import annotations

import gzip
import ssl
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

RAW = Path(__file__).resolve().parents[2] / "data" / "raw"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

_STRICT_OFF = ssl.create_default_context()
_STRICT_OFF.verify_flags &= ~ssl.VERIFY_X509_STRICT
# Some small venues serve a broken certificate chain. The pages are public
# listings and nothing is sent, so a second try without verification is fine.
_UNVERIFIED = ssl._create_unverified_context()


def fetch(source_id: str, url: str, today: date | None = None, refresh: bool = False,
          path: Path | None = None) -> str:
    """`path` overrides the dated copy, for pages kept across days (event detail pages)."""
    today = today or date.today()
    path = path or RAW / today.isoformat() / f"{source_id}.html"
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8", errors="ignore")
    headers = {"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9", "Accept-Encoding": "gzip",
               "Accept": "text/html,application/xhtml+xml"}
    last = None
    for ctx in (_STRICT_OFF, _UNVERIFIED):
        for _ in range(2):
            try:
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
