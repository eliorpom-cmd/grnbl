"""HTML to compact text an AI can read cheaply, keeping where each link goes."""

from __future__ import annotations

import html as htmllib
import re
import urllib.parse

_DROP = re.compile(r"<(script|style|noscript|svg|iframe|form|head)\b.*?</\1>", re.S | re.I)
_CHROME = re.compile(r"<(nav|footer)\b.*?</\1>", re.S | re.I)
_LINK = re.compile(r'<a\b[^>]*href="([^"#][^"]*)"[^>]*>(.*?)</a>', re.S | re.I)
_BLOCK = re.compile(r"</?(p|div|li|h[1-6]|br|tr|article|section|time)\b[^>]*>", re.I)
_TAG = re.compile(r"<[^>]+>")


def to_text(html: str, base_url: str, limit: int = 45_000) -> str:
    h = _DROP.sub(" ", html)
    h = _CHROME.sub(" ", h)

    def link(m):
        text = _TAG.sub(" ", m.group(2)).strip()
        if not text:
            return " "
        url = urllib.parse.urljoin(base_url, htmllib.unescape(m.group(1)))
        return f" [{text}]({url}) "

    h = _LINK.sub(link, h)
    h = _BLOCK.sub("\n", h)
    h = htmllib.unescape(_TAG.sub(" ", h))
    lines = [re.sub(r"[ \t ]+", " ", l).strip() for l in h.splitlines()]
    out, prev = [], None
    for l in lines:
        if l and l != prev:
            out.append(l)
        prev = l
    return "\n".join(out)[:limit]
