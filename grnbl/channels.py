"""The WhatsApp groups grnbl writes to, and which events each one may carry.

People join the groups they care about. Which group an event may go to is
decided here, by code, never by the AI: each event has exactly one home group
(`home`), so a paid event can never reach the free group, a concert never lands
in the flea-market one, and nobody reads the same event in two groups. The
editor (editor.py) then picks the best of what each group accepts.
"""

from __future__ import annotations

import re

BARGAIN = re.compile(r"vide[- ]?grenier|brocante|braderie|bourse (?:aux|au|à|de)|\btroc\b|vente (?:solidaire|de livres|"
                     r"au déballage|de jouets)|déstockage|\bpuces\b|ressourcerie|recyclerie|foire aux|vide[- ]?dressing|"
                     r"gratiferia|repair caf", re.I)
# Nature: these words count in the title. Only the strong ones also count in the description, so an art
# exhibition "by an artist who loves the mountains" or a talk mentioning the forest stays out.
NATURE = re.compile(r"randonn|\brando|balade (?:nature|botanique|naturaliste|en (?:montagne|forêt))|sortie nature|\bnature\b|oiseau|ornitho|\bfaune|\bflore\b|forêt|montagne|"
                    r"\balpes\b|\bski\b|raquette|escalade|via ferrata|cueillette|champignon|mycolog|astronom|"
                    r"marais|\blpo\b|espace naturel|alpinis|glacier|grimpe|biodiversit", re.I)
NATURE_STRONG = re.compile(r"randonn|sortie nature|balade (?:nature|botanique|naturaliste)|ornitho|oiseaux|\blpo\b|"
                           r"champignon|mycolog|espace naturel sensible|\bski\b|raquettes|escalade|via ferrata|biodiversit|"
                           r"alpinis|haute montagne|guides? (?:professionnels )?de (?:la )?montagne", re.I)
# Made for children, not merely fine for them: the review's "family" flag is true for most outings.
# Broad words count in the title only: "testimonies of their children" in a talk's description is not a kids' event.
KIDS = re.compile(r"enfant|famille|jeune public|tout[- ]petits?|p'tits|petite enfance|mômes|\bkids?\b|\bbébés?\b|"
                  r"dès \d+ ans|à partir de \d+ ans|\d+\s?(?:-|–|/|à)\s?\d+ ans|halloween|sorcières?|\bcontes?\b|"
                  r"marionnette|ludoth|jeu de piste", re.I)
KIDS_STRONG = re.compile(r"jeune public|tout[- ]petits|petite enfance|mômes|pour (?:les )?enfants|en famille|"
                         r"dès \d+ ans|à partir de \d+ ans|\d+\s?(?:-|–|/|à)\s?\d+ ans|ludoth|halloween", re.I)
GROWN_UPS = re.compile(r"soirée|\bclub\b|\bbar\b|\+ ?18|adultes? seulement|réservé aux adultes", re.I)


def _review(e: dict) -> dict:
    return e.get("review") or {}


def is_free(e: dict) -> bool | None:
    r = _review(e)
    return r.get("free") if r.get("free") is not None else e.get("free")


def _words(e: dict) -> str:
    return " ".join(str(e.get(k) or "") for k in ("title", "description", "venue"))


def for_families(e: dict) -> bool:
    if e.get("category") == "kids":
        return True
    kids = KIDS.search(e.get("title") or "") or KIDS_STRONG.search(e.get("description") or "")
    return bool(kids) and not GROWN_UPS.search(e.get("title") or "")


def is_bargain(e: dict) -> bool:
    return bool(BARGAIN.search(_words(e)))


def outdoors(e: dict) -> bool:
    return (e.get("category") == "outdoor" or bool(NATURE.search(e.get("title") or ""))
            or bool(NATURE_STRONG.search(e.get("description") or "")))


def home(e: dict) -> str:
    """The one group an event belongs to. Theme groups first, from the most specific: a toy swap is a
    bargain before it is for families, a children's Halloween trail is for families before it is outdoors.
    What fits no theme goes to Gratuit when it is free, else to Sorties."""
    if is_bargain(e):
        return "bonsplans"
    if for_families(e):
        return "famille"
    if outdoors(e):
        return "nature"
    return "gratuit" if is_free(e) is True else "sorties"


CHANNELS = {
    "gratuit": {
        "name": "grnbl · Gratuit", "label": "🆓 Gratuit", "week_title": "🆓 *Gratuit cette semaine*",
        "promise": "only free outings: what costs nothing and is worth leaving the house for",
        "taste": "- only free things are offered to you here;\n"
                 "- the rare before the routine: a once-a-year opening beats an exhibition on a long run;",
            },
    "sorties": {
        "name": "grnbl · Sorties", "label": "🎭 Sorties", "week_title": "🎭 *Cette semaine à Grenoble*",
        "promise": "the best paid outings of the week: big concerts, shows, festivals, deals (free ones have their own group)",
        "taste": "- paid things are welcome: a big concert or a show people will talk about deserves its place, and so\n"
                 "  does a discount or a good deal; a famous name is fine here when it is a real event;",
            },
    "famille": {
        "name": "grnbl · Enfants & famille", "label": "👨‍👩‍👧 Famille", "week_title": "👨‍👩‍👧 *Cette semaine en famille*",
        "promise": "what to do with children: workshops, shows for young audiences, family visits, holiday activities",
        "taste": "- every pick must work with children; say the age when the page gives it;\n"
                 "- free or cheap first: families go out several at a time;\n"
                 "- the variety rule applies, the \"one for families\" rule does not: everything here is for them;",
            },
    "bonsplans": {
        "name": "grnbl · Bons plans & brocantes", "label": "🛍️ Bons plans", "week_title": "🛍️ *Les bons plans de la semaine*",
        "promise": "flea markets, car-boot sales, ski and toy swaps, charity sales: where to find things for little",
        "taste": "- the bigger the better: a town's yearly braderie beats a school's small sale;\n"
                 "- a ski swap before winter or a toy swap before Christmas is exactly what people need;\n"
                 "- the variety and \"one for families\" rules do not apply here;",
            },
    "nature": {
        "name": "grnbl · Montagne & nature", "label": "🏔️ Nature", "week_title": "🏔️ *Dehors cette semaine*",
        "promise": "outdoor and mountain: guided nature walks, bird watching, mountain festivals and films, station openings",
        "taste": "- guided outings with a naturalist, a mountain film night, a first day of skiing: things to do outside\n"
                 "  or about the mountains; free ones first;\n"
                 "- leave out sport competitions people only watch;",
            },
}


def accepts(channel: str, e: dict) -> bool:
    """One event, one group: the group may carry the event only if it is the event's home."""
    return home(e) == channel
