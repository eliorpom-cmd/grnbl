"""Catches what the AI adds to a line that no source says.

The editor is told to use only the facts it is given, and mostly does, but not
always: "avec l'Orchestre national Auvergne-Rhône-Alpes" or "bluesman texan"
appeared in lines although no page said it (audit of 18/10/2026). Here every
name and number of a line is looked for in the event's own data and its page.
What is found nowhere is listed on the pick ("unverified") and shown on the
board, so the human checks those words during the weekly read.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

# Words that start sentences or carry no fact of their own.
COMMON = set("""
le la les l un une des du de d au aux et ou en dans pour par avec sur sous chez ce cet cette ces son sa ses leur leurs
tout tous toute toutes il elle on nous vous ils elles c qui que quoi dont ici voici voila plus moins tres
gratuit gratuite gratuits gratuites entree libre jusqu des a partir apres avant puis enfin aussi encore
lundi mardi mercredi jeudi vendredi samedi dimanche janvier fevrier mars avril mai juin juillet aout septembre
octobre novembre decembre ce soir demain aujourd hui weekend week end matin midi
decouvrez venez profitez plongez reservez relevez rendez vous rdv festival exposition concert spectacle atelier visite
temps forts fort sortie sorties saint sainte double majeur grand grande petit petits petite famille enfants
""".split())
# Words written with a capital in the line, or with letters other than a-z: names, places, titles.
WORD = re.compile(r"[A-ZÀ-ÖØ-Þ][\w'’-]+|\b\w*[A-ZÀ-Þ]\w*\b")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t)


def haystack(e: dict, page: str = "") -> str:
    facts = [str(e.get(k) or "") for k in ("title", "description", "venue", "town", "price", "periods",
                                             "start", "end", "booking_opens", "booking_deadline", "source_name")]
    facts += [str(d) for d in e.get("dates") or []]
    facts.append(_days_between(e.get("start"), e.get("end")))
    # Not the review's line: it is AI text too, and carried the same inventions.
    return " " + norm(" ".join(facts) + " " + page) + " "


def _days_between(start, end) -> str:
    """Every day of a run (an exhibition, a festival): a line may name any of them."""
    try:
        d, last = date.fromisoformat(str(start)[:10]), date.fromisoformat(str(end)[:10])
    except ValueError:
        return ""
    days = []
    while d <= last and len(days) < 120:
        days.append(str(d.day))
        d += timedelta(days=1)
    return " ".join(days)


def _found(word: str, hay: str) -> bool:
    """The word, or one of the same family ("archivistes" for "archiviste", "festive" for "festival")."""
    if f" {word} " in hay:
        return True
    stem = word[:max(4, min(6, len(word) - 2))]
    return len(word) > 4 and f" {stem}" in hay


DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MONTHS = ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre", "octobre",
          "novembre", "decembre"]
DAY_DATE = re.compile(rf"\b({'|'.join(DAYS)})\s+(\d{{1,2}})(?:er)?\s+({'|'.join(MONTHS)})\b")


def wrong_weekdays(line: str, year: int) -> list[str]:
    """"Mardi 28 octobre" when the 28th is a Wednesday: the calendar says which day it really is."""
    out = []
    for day, num, month in DAY_DATE.findall(norm(line)):
        try:
            d = date(year, MONTHS.index(month) + 1, int(num))
        except ValueError:
            continue
        if DAYS[d.weekday()] != day:
            out.append(f"{day} {num} {month} (c'est un {DAYS[d.weekday()]})")
    return out


def unverified(line: str, hay: str) -> list[str]:
    """Names and numbers of the line that appear nowhere in the event's facts or page."""
    out = []
    words = [p for w in WORD.findall(line or "") for p in norm(w).split()]
    for part in words:
        if len(part) > 2 and part not in COMMON and not _found(part, hay) and part not in out:
            out.append(part)
    digits = re.sub(r"[^0-9 ]", " ", hay)
    for n in NUMBER.findall(line or ""):
        n = n.replace(",", ".").split(".")[0]
        # Dates and hours are written 2026-10-22T20:00 in the facts: "22" or "20" must be found as a number.
        if n not in out and not re.search(rf"(?<!\d)0*{int(n)}(?!\d)", digits):
            out.append(n)
    return out


def check(line: str, e: dict, page: str = "") -> list[str]:
    """Everything to verify in a line: wrong weekdays first, then unknown names and numbers."""
    year = int(str(e.get("start") or date.today().year)[:4])
    return wrong_weekdays(line, year) + unverified(line, haystack(e, page))
