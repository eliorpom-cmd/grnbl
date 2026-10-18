"""Practical alerts for the Grenoble area: weather warnings, air quality, tram and bus disruptions.

Pure data, no AI, like the fuel post. The point is to say something only when
it matters: an orange storm warning, a pollution episode tomorrow, a tram line
cut from tonight. A quiet day gives no post at all.

Sources (all public, no key of ours):
- Météo-France warnings for Isère (the endpoint its mobile app reads, with the
  public token the open-source meteofrance-api library ships);
- Atmo Auvergne-Rhône-Alpes, the air quality index of Grenoble (embedded in
  the town's public page: their API needs an account, their WFS times out);
- Mobilités M (data.mobilites-m.fr), disruptions of the TAG network.
"""

from __future__ import annotations

import html as htmllib
import json
import re
import urllib.request
from datetime import date, datetime, timedelta

from ..http import _CTX, get_json

WARNINGS = "https://webservice.meteofrance.com/v3/warning/currentphenomenons"
METEO_TOKEN = "__Wj7dVSTjV9YGu1guveLyDq0g7S7TfTjaHBTPTpO0kj8__"
AIR_PAGE = "https://www.atmo-auvergnerhonealpes.fr/air-commune/grenoble/38185/indice-atmo"
TRANSIT = "https://data.mobilites-m.fr/api/dyn/evtTC/json"

PHENOMENA = {"1": "vent violent", "2": "pluie-inondation", "3": "orages", "4": "crues", "5": "neige-verglas",
             "6": "canicule", "7": "grand froid", "8": "avalanches"}
COLORS = {2: ("🟡", "jaune"), 3: ("🟠", "orange"), 4: ("🔴", "rouge")}
AIR_LEVELS = {1: "bonne", 2: "moyenne", 3: "dégradée", 4: "mauvaise", 5: "très mauvaise", 6: "extrêmement mauvaise"}
# Only what is grave and rare: it goes to the community's announcements, which every member gets.
WEATHER_MIN = 4   # red warning only (orange comes several times a year)
AIR_MIN = 5       # "très mauvaise" or worse
# A strike or the whole tram network stopped, not one line's night works or a moved stop.
MAIN_LINES = re.compile(r"^SEM_[A-E]$")
SERIOUS = re.compile(r"grève|mouvement social|aucun tram|ensemble du réseau|tout le réseau|réseau (?:tram )?interrompu|"
                     r"trafic (?:totalement )?interrompu sur (?:toutes|l'ensemble)", re.I)


def weather(domain: str = "38") -> list[dict]:
    """Yellow, orange and red warnings for the department today."""
    data = get_json(WARNINGS, {"domain": domain, "depth": 1, "with_coastal_bulletin": "false", "token": METEO_TOKEN})
    out = []
    for p in data.get("phenomenons_max_colors") or []:
        level = int(p.get("phenomenon_max_color_id") or 1)
        name = PHENOMENA.get(str(p.get("phenomenon_id")))
        if level >= WEATHER_MIN and name:
            out.append({"kind": "weather", "level": level, "what": name})
    return sorted(out, key=lambda a: -a["level"])


def parse_air(page: str) -> dict[str, dict]:
    """Index and comment per day, from the JSON embedded in the Atmo page."""
    days = {d: {"index": float(i)} for d, i in re.findall(r'"(\d{4}-\d{2}-\d{2})":\{"indice_atmo":([\d.]+)', page)}
    for d, text in re.findall(r'"(\d{4}-\d{2}-\d{2})":"((?:[^"\\]|\\.)*)"', page):
        if d in days and len(text) > 30:
            days[d]["comment"] = htmllib.unescape(json.loads(f'"{text}"')).strip()
    return days


def air(today: date) -> list[dict]:
    """Today or tomorrow at "dégradé" or worse: worth telling people, who can leave the car."""
    req = urllib.request.Request(AIR_PAGE, headers={"User-Agent": "Mozilla/5.0 (Macintosh) grnbl"})
    with urllib.request.urlopen(req, timeout=30, context=_CTX) as resp:
        days = parse_air(resp.read().decode("utf-8", "ignore"))
    out = []
    for offset in (0, 1):
        d = (today + timedelta(days=offset)).isoformat()
        level = round(days.get(d, {}).get("index", 0))
        if level >= AIR_MIN:
            out.append({"kind": "air", "level": level, "day": d, "what": AIR_LEVELS.get(level, "dégradée"),
                        "comment": days[d].get("comment")})
    return out


def _when(raw: str) -> datetime:
    return datetime.strptime(raw, "%d/%m/%Y %H:%M")


def _first_sentence(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    m = re.match(r"(.+?[.!])(?:\s|$)", text)
    return (m.group(1) if m else text)[:220]


def transit_from(records: dict, now: datetime, ahead: timedelta = timedelta(hours=36)) -> list[dict]:
    """Disruptions of the main lines that start between yesterday evening and tomorrow:
    news, not the works that have been running for months."""
    out = []
    for r in records.values():
        lines = [l for l in (r.get("listeLigne") or "").split(",") if MAIN_LINES.match(l.strip())]
        if not lines:
            continue
        start, end = _when(r["dateDebut"]), _when(r["dateFin"])
        if not (now - timedelta(hours=12) <= start <= now + ahead) or end < now:
            continue
        title, _, rest = (r.get("texte") or "").partition("|")
        if not SERIOUS.search(r.get("texte") or ""):
            continue
        out.append({"code": r.get("code"), "kind": "transit", "lines": [l.split("_")[1] for l in lines], "title": title.strip(),
                    "detail": _first_sentence(rest.split("|")[-1]), "start": start.isoformat(timespec="minutes"),
                    "end": end.isoformat(timespec="minutes")})
    return sorted(out, key=lambda a: a["start"])


def transit(now: datetime) -> list[dict]:
    return transit_from(get_json(TRANSIT), now)


def collect(now: datetime) -> tuple[list[dict], list[str]]:
    """Every alert worth a post, and the sources that could not be read."""
    out, failed = [], []
    for name, read in (("météo", lambda: weather()), ("air", lambda: air(now.date())),
                       ("TAG", lambda: transit(now.replace(tzinfo=None)))):
        try:
            out += read()
        except Exception:  # noqa: BLE001 - one source down leaves the others
            failed.append(name)
    return out, failed
