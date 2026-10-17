"""Plain agenda pages to events, with an AI reading the cleaned text.

Every site lays out its agenda differently; writing and maintaining thirty
parsers would be most of the project. Instead the page is reduced to text with
its links (clean.py) and a small, fast model returns the events in one shape.
The AI only transcribes what is on the page: the review that decides what is
worth posting comes later and is a separate step.

The model is called through the Claude Code CLI (`claude -p`) so it runs on the
maintainer's subscription during the hackathon; swapping in the API is a
change to `ask()` only.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
from datetime import date, datetime
from pathlib import Path

CATEGORIES = ["concert", "theatre", "dance", "humour", "cinema", "exhibition", "kids", "sport",
              "talk", "workshop", "festival", "party", "market", "outdoor", "other"]

PROMPT = """You extract events from the text of a web page of a Grenoble (France) agenda.
Source: {name} ({url}). Today is {today}.

Return ONLY a JSON array, no prose. One object per event that takes place between {today} and {until}:
{{"title": str, "start": "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM", "end": same format or null,
  "venue": str or null, "town": str or null, "price": str or null (as written, e.g. "12 €", "Gratuit"),
  "free": true/false/null, "url": absolute link to the event or null,
  "category": one of {cats}, "description": one short sentence in French or null,
  "booking": "required" | "recommended" | "none" | null (only what the page says),
  "booking_opens": "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM" or null (when booking or registration opens),
  "booking_deadline": same format or null, "booking_url": str or null,
  "sold_out": true only if the page says "complet"}}

Rules: copy facts from the page only, never invent a date, a price or a place. If the year is missing,
use the next occurrence after today. Skip events without a usable date, past events, and navigation or
advertising. A run of dates (exhibition, festival) is one event with start and end. Return [] if none.

PAGE TEXT:
{text}
"""


# Claude Code's own system prompt, tools, settings and MCP servers add ~30,000
# tokens to every call; this step needs none of them (measured: 31,067 -> 560).
SYSTEM = "You are a careful data assistant. Follow the instructions exactly and return only the requested output."
BARE = ["--system-prompt", SYSTEM, "--tools", "", "--strict-mcp-config", "--setting-sources", "",
        "--disable-slash-commands", "--no-session-persistence"]
USAGE = Path(__file__).resolve().parents[2] / "data" / "usage.jsonl"
_lock = threading.Lock()


def ask(prompt: str, model: str = "haiku", timeout: int = 240) -> str:
    # Haiku only copies facts from pages: thinking multiplied its output by 9 for the
    # same events (MC2 page: 18,054 -> 2,030 tokens). Sonnet judges, it keeps thinking.
    env = {**os.environ, "MAX_THINKING_TOKENS": "0"} if model == "haiku" else None
    out = subprocess.run(
        ["claude", "-p", "--model", model, "--output-format", "json", *BARE],
        input=prompt, capture_output=True, text=True, timeout=timeout, env=env,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip()[:300] or f"claude exited {out.returncode}")
    reply = json.loads(out.stdout)
    if reply.get("is_error"):
        raise RuntimeError(str(reply.get("result"))[:300])
    _log(model, reply.get("usage") or {})
    return reply.get("result") or ""


def _log(model: str, usage: dict) -> None:
    """One line per call, so the token cost of a morning can be read back (see usage())."""
    line = {"at": datetime.now().isoformat(timespec="seconds"), "model": model,
            "in": sum(usage.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")),
            "out": usage.get("output_tokens", 0)}
    with _lock:
        USAGE.parent.mkdir(parents=True, exist_ok=True)
        with USAGE.open("a") as f:
            f.write(json.dumps(line) + "\n")


def usage(day: date | None = None) -> dict[str, dict[str, int]]:
    """Calls and tokens per model for one day."""
    day = (day or date.today()).isoformat()
    total: dict[str, dict[str, int]] = {}
    if USAGE.exists():
        for raw in USAGE.read_text().splitlines():
            line = json.loads(raw)
            if line["at"].startswith(day):
                t = total.setdefault(line["model"], {"calls": 0, "in": 0, "out": 0})
                t["calls"] += 1
                t["in"] += line["in"]
                t["out"] += line["out"]
    return total


def parse_array_raw(answer: str) -> list[dict]:
    """The JSON array in a model answer, whatever prose surrounds it."""
    start, end = answer.find("["), answer.rfind("]")
    if start < 0 or end < start:
        return []
    return [e for e in json.loads(answer[start:end + 1]) if isinstance(e, dict)]


def parse_array(answer: str) -> list[dict]:
    return [e for e in parse_array_raw(answer) if e.get("title") and e.get("start")]


# An agenda page that has not changed since the last reading gives the same events:
# its last extraction is reused, minus what is over, instead of asking the AI again.
SEEN = Path(__file__).resolve().parents[2] / "data" / "extract"
REUSE_DAYS = 7


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()


def still_on(e: dict, today: date) -> bool:
    return str(e.get("end") or e.get("start"))[:10] >= today.isoformat()


def events(text: str, source: dict, today: date, until: date) -> list[dict]:
    cached, digest = SEEN / f"{source['id']}.json", text_hash(text)
    if cached.exists():
        last = json.loads(cached.read_text())
        if last["hash"] == digest and (today - date.fromisoformat(last["day"])).days <= REUSE_DAYS:
            return [e for e in last["events"] if still_on(e, today)]
    prompt = PROMPT.format(name=source["name"], url=source["url"], today=today.isoformat(),
                           until=until.isoformat(), cats=", ".join(CATEGORIES), text=text)
    found = parse_array(ask(prompt))
    SEEN.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps({"hash": digest, "day": today.isoformat(), "events": found}, ensure_ascii=False))
    return found
