"""The WhatsApp groups grnbl writes to, and which events each one may carry.

People join the groups they care about. Which group an event may go to is
decided here, by code, never by the AI: a paid event can never reach the free
group, a concert never lands in the flea-market one. The editor (editor.py)
then picks the best of what each group accepts.
"""

from __future__ import annotations

import re

BARGAIN = re.compile(r"vide[- ]?grenier|brocante|braderie|bourse (?:aux|au|à|de)|\btroc\b|vente (?:solidaire|de livres|"
                     r"au déballage|de jouets)|déstockage|\bpuces\b|ressourcerie|recyclerie|foire aux|vide[- ]?dressing|"
                     r"gratiferia|repair caf", re.I)
NATURE = re.compile(r"randonn|\brando|balade (?:nature|botanique|naturaliste|en (?:montagne|forêt))|sortie nature|\bnature\b|oiseau|ornitho|\bfaune|\bflore\b|forêt|montagne|"
                    r"sommet|bastille|\bski\b|raquette|escalade|via ferrata|trail|cueillette|champignon|astronom|"
                    r"étoiles|marais|\blpo\b|espace naturel|alpin|glacier|grimpe", re.I)


def _review(e: dict) -> dict:
    return e.get("review") or {}


def is_free(e: dict) -> bool | None:
    r = _review(e)
    return r.get("free") if r.get("free") is not None else e.get("free")


def _words(e: dict) -> str:
    return " ".join(str(e.get(k) or "") for k in ("title", "description", "venue"))


def for_families(e: dict) -> bool:
    return _review(e).get("family") is True or e.get("family") is True or e.get("category") == "kids"


def is_bargain(e: dict) -> bool:
    return bool(BARGAIN.search(_words(e)))


def outdoors(e: dict) -> bool:
    return e.get("category") == "outdoor" or bool(NATURE.search(_words(e)))


CHANNELS = {
    "gratuit": {
        "name": "grnbl · Gratuit", "label": "🆓 Gratuit", "week_title": "🎭 *Cette semaine à Grenoble*",
        "promise": "only free outings: what costs nothing and is worth leaving the house for",
        "taste": "- only free things are offered to you here;\n"
                 "- the rare before the routine: a once-a-year opening beats an exhibition on a long run;",
        "accepts": lambda e: is_free(e) is True,
    },
    "sorties": {
        "name": "grnbl · Sorties", "label": "🎭 Sorties", "week_title": "🎭 *Cette semaine à Grenoble*",
        "promise": "the best outings of the week, paid ones included: big concerts, shows, festivals, deals",
        "taste": "- paid things are welcome: a big concert or a show people will talk about deserves its place, and so\n"
                 "  does a discount or a good deal; a famous name is fine here when it is a real event;\n"
                 "- what other groups already post is listed below: do not repeat it;",
        "accepts": lambda e: True,
    },
    "famille": {
        "name": "grnbl · Enfants & famille", "label": "👨‍👩‍👧 Famille", "week_title": "👨‍👩‍👧 *Cette semaine en famille*",
        "promise": "what to do with children: workshops, shows for young audiences, family visits, holiday activities",
        "taste": "- every pick must work with children; say the age when the page gives it;\n"
                 "- free or cheap first: families go out several at a time;\n"
                 "- the variety rule applies, the \"one for families\" rule does not: everything here is for them;",
        "accepts": for_families,
    },
    "bonsplans": {
        "name": "grnbl · Bons plans & brocantes", "label": "🛍️ Bons plans", "week_title": "🛍️ *Les bons plans de la semaine*",
        "promise": "flea markets, car-boot sales, ski and toy swaps, charity sales: where to find things for little",
        "taste": "- the bigger the better: a town's yearly braderie beats a school's small sale;\n"
                 "- a ski swap before winter or a toy swap before Christmas is exactly what people need;\n"
                 "- the variety and \"one for families\" rules do not apply here;",
        "accepts": is_bargain,
    },
    "nature": {
        "name": "grnbl · Montagne & nature", "label": "🏔️ Nature", "week_title": "🏔️ *Dehors cette semaine*",
        "promise": "outdoor and mountain: guided nature walks, bird watching, mountain festivals and films, station openings",
        "taste": "- guided outings with a naturalist, a mountain film night, a first day of skiing: things to do outside\n"
                 "  or about the mountains; free ones first;\n"
                 "- leave out sport competitions people only watch;",
        "accepts": outdoors,
    },
}


def accepts(channel: str, e: dict) -> bool:
    return CHANNELS[channel]["accepts"](e)
