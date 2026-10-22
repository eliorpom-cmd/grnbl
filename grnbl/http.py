"""Tiny JSON-over-HTTP helper on the standard library, so the project installs nothing."""

from __future__ import annotations

import json
import ssl
import urllib.parse
import urllib.request

# Said as it is: a small bot, what it does, where its code is. Every source was checked to answer it normally.
USER_AGENT = "grnbl/0.1 (weekly local events digest; +https://github.com/eliorpom-cmd/grnbl)"

# Certificates are still verified. Python 3.13+ adds VERIFY_X509_STRICT by
# default, and some French public APIs (geo.api.gouv.fr) serve a chain that
# fails only that extra check.
_CTX = ssl.create_default_context()
_CTX.verify_flags &= ~ssl.VERIFY_X509_STRICT


def get_json(url: str, params: dict | None = None, timeout: float = 30):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as resp:
        return json.load(resp)
