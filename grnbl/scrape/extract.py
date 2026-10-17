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

import json
import subprocess
from datetime import date

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


def ask(prompt: str, model: str = "haiku", timeout: int = 240) -> str:
    out = subprocess.run(
        ["claude", "-p", "--model", model, "--output-format", "text"],
        input=prompt, capture_output=True, text=True, timeout=timeout,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip()[:300] or f"claude exited {out.returncode}")
    return out.stdout


def parse_array_raw(answer: str) -> list[dict]:
    """The JSON array in a model answer, whatever prose surrounds it."""
    start, end = answer.find("["), answer.rfind("]")
    if start < 0 or end < start:
        return []
    return [e for e in json.loads(answer[start:end + 1]) if isinstance(e, dict)]


def parse_array(answer: str) -> list[dict]:
    return [e for e in parse_array_raw(answer) if e.get("title") and e.get("start")]


def events(text: str, source: dict, today: date, until: date) -> list[dict]:
    prompt = PROMPT.format(name=source["name"], url=source["url"], today=today.isoformat(),
                           until=until.isoformat(), cats=", ".join(CATEGORIES), text=text)
    return parse_array(ask(prompt))
