"""English translations of the composed posts: `python3 -m grnbl.translate [YYYY-MM-DD]`.

The posts go out in French. For readers who do not read it (a jury, a guest),
the board shows each post's English translation under its WhatsApp preview,
marked as not posted. Translations live in data/events/<day>/posts.en.json:

    {"<channel>/<post>": {"fr": the French text translated, "en": its translation, "at": ..., "error": ...}}

publish.py and digest.py never read that file, so nothing English can reach
WhatsApp or Discord (tested). A translation that fails is logged and left
empty: it never blocks an edition or a send. Only posts whose French text
changed since the last run go back to the model, so running it again is cheap.
"""

from __future__ import annotations

import concurrent.futures as cf
import json
import sys
import threading
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import publish
from .scrape.extract import ask

DATA = Path(__file__).resolve().parents[1] / "data"
PARIS = ZoneInfo("Europe/Paris")

PROMPT = """Translate this WhatsApp post from French into natural English, for a reader who does not speak French
and wants to understand exactly what it says.
Keep exactly: the line breaks and blank lines, every emoji, the WhatsApp formatting (*bold*, _italic_), links,
numbers, prices and the order of the lines.
Keep names of venues, towns, organisations, bands and shows as written; translate event titles made of ordinary words.
Dates and times in English: "mercredi 21" -> "Wednesday 21", "sam. 24/10 à 20h" -> "Sat 24/10 at 8pm".
Add nothing, explain nothing. Return only the translated post.

POST:
{post}
"""

_write = threading.Lock()   # one writer of posts.en.json at a time
_busy = threading.Lock()    # one background run at a time
_guard = threading.Lock()
_queued: set[date] = set()


def path(day: date) -> Path:
    return DATA / "events" / day.isoformat() / "posts.en.json"


def load(day: date) -> dict:
    p = path(day)
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except ValueError:
        return {}


def key(channel: str, post: str) -> str:
    return f"{channel}/{post}"


def current_posts(day: date, now: datetime | None = None) -> dict[str, str]:
    """The French text of each composed post, exactly as the board and the outbox build it."""
    now = now or datetime.now(PARIS)
    # Empty fuel and alert texts: those posts are not composed, and this skips fetching them.
    return {key(i["channel"], i["post"]): i["text"] for i in publish.outbox(day, now, fuel_text="", alerts_text="")}


def needs(entry: dict | None, text: str) -> bool:
    """True when the post has never been translated in this exact wording."""
    return entry is None or entry.get("fr") != text


def shown(entry: dict | None, text: str) -> dict | None:
    """What the board shows under a post: the translation, and whether it is of an older wording."""
    if not entry:
        return None
    return {"text": entry.get("en") or "", "stale": entry.get("fr") != text, "error": bool(entry.get("error"))}


def translate(text: str) -> str:
    return ask(PROMPT.format(post=text), model="haiku").strip()


def run(day: date, now: datetime | None = None, retry: bool = True) -> dict[str, str]:
    """Translates the posts that are new or changed; returns {post key: what happened}.

    retry=True also redoes the posts whose last translation failed."""
    posts = current_posts(day, now)
    known = load(day)
    todo = {k: t for k, t in posts.items()
            if needs(known.get(k), t) or (retry and not (known.get(k) or {}).get("en"))}
    report = {k: "unchanged" for k in posts if k not in todo}

    def one(item):
        k, text = item
        try:
            return k, {"fr": text, "en": translate(text)}
        except Exception as e:  # noqa: BLE001 - a failed translation never blocks anything else
            print(f"translate {day} {k}: {e}", file=sys.stderr, flush=True)
            return k, {"fr": text, "en": "", "error": str(e)[:300]}

    with cf.ThreadPoolExecutor(4) as ex:
        done = dict(ex.map(one, todo.items()))
    if done:
        stamp = datetime.now(PARIS).isoformat(timespec="seconds")
        with _write:
            # Re-read: a background run may have written in the meantime.
            known = load(day)
            for k, entry in done.items():
                known[k] = {**entry, "at": stamp}
            p = path(day)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(known, ensure_ascii=False, indent=1))
    report.update({k: "failed" if e.get("error") else "translated" for k, e in done.items()})
    return report


def safe_run(day: date) -> dict[str, str]:
    """run() for the edition pipeline: any problem is logged, never raised."""
    try:
        return run(day)
    except Exception as e:  # noqa: BLE001 - translations are a bonus, the edition goes on
        print(f"translate {day}: {e}", file=sys.stderr, flush=True)
        return {}


def refresh_later(day: date) -> None:
    """Translates the day's changed posts in the background (the board calls it, never waits).

    Calls arriving while a run is queued are merged into it; failed posts are not retried here,
    so a broken `claude` cannot make the board call it on every refresh."""
    with _guard:
        if day in _queued:
            return
        _queued.add(day)
    threading.Thread(target=_background, args=(day,), daemon=True).start()


def _background(day: date) -> None:
    with _busy:
        with _guard:
            _queued.discard(day)
        try:
            run(day, retry=False)
        except Exception as e:  # noqa: BLE001 - the board keeps working without translations
            print(f"translate {day}: {e}", file=sys.stderr, flush=True)


def busy() -> bool:
    return _busy.locked() or bool(_queued)


def main(argv: list[str]) -> int:
    day = date.fromisoformat(argv[0]) if argv else datetime.now(PARIS).date()
    report = run(day)
    if not report:
        print(f"{day}: no composed post (is data/events/{day}/selection.json there?)")
    for k, what in sorted(report.items()):
        print(f"{k:22} {what}")
    return 1 if any(w == "failed" for w in report.values()) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
