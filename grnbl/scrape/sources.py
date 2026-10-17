"""Every agenda grnbl reads. Adding one is adding a line here.

kind:
  "jsonld"  the page publishes schema.org Event data: read by code, no AI.
  "ai"      plain HTML: cleaned to text, then an AI extracts the events.
"""

SOURCES = [
    # Aggregators with structured data
    {"id": "allevents", "name": "Allevents Grenoble", "url": "https://allevents.in/grenoble", "kind": "jsonld"},
    {"id": "eventbrite", "name": "Eventbrite Grenoble", "url": "https://www.eventbrite.fr/d/france--grenoble/events/", "kind": "jsonld"},
    {"id": "meetup", "name": "Meetup Grenoble", "url": "https://www.meetup.com/fr-FR/find/?location=fr--grenoble&source=EVENTS", "kind": "jsonld"},
    # City-wide agendas
    {"id": "tourisme", "name": "Grenoble Tourisme", "url": "https://www.grenoble-tourisme.com/fr/decouvrir/evenements/agenda/", "kind": "ai"},
    {"id": "ville", "name": "Ville de Grenoble", "url": "https://www.grenoble.fr/79-agenda.htm", "kind": "ai"},
    {"id": "gremag", "name": "Gre.mag", "url": "https://www.gre-mag.fr/agenda/?quand=7-jours", "kind": "ai"},
    {"id": "petitbulletin", "name": "Le Petit Bulletin", "url": "https://www.petit-bulletin.fr/grenoble/", "kind": "ai"},
    {"id": "icigrenoble", "name": "ici Grenoble", "url": "https://www.ici-grenoble.org/agenda", "kind": "ai"},
    {"id": "metropole", "name": "Grenoble-Alpes Métropole", "url": "https://www.grenoblealpesmetropole.fr/915-l-agenda-de-la-metropole.htm", "kind": "ai"},
    {"id": "placegrenet", "name": "Place Gre'net", "url": "https://www.placegrenet.fr/category/agenda", "kind": "ai"},
    {"id": "lessentiel", "name": "L'Essentiel Grenoble", "url": "https://www.lessentiel.fr/grenoble", "kind": "ai"},
    {"id": "dauphine", "name": "Le Dauphiné, Pour Sortir", "url": "https://www.ledauphine.com/pour-sortir", "kind": "ai"},
    {"id": "uga", "name": "Université Grenoble Alpes", "url": "https://www.univ-grenoble-alpes.fr/actualites/agenda/", "kind": "ai"},
    # Venues
    {"id": "mc2", "name": "MC2", "url": "https://www.mc2grenoble.fr/agenda", "kind": "ai"},
    {"id": "belleelectrique", "name": "La Belle Électrique", "url": "https://www.la-belle-electrique.com/", "kind": "ai"},
    {"id": "summum", "name": "Le Summum", "url": "https://www.summum-grenoble.com/", "kind": "ai"},
    {"id": "leciel", "name": "Le Ciel", "url": "https://le-ciel.fr/agenda/", "kind": "ai"},
    {"id": "pacifique", "name": "Le Pacifique", "url": "https://www.lepacifique-grenoble.com/evenements", "kind": "ai"},
    {"id": "cinematheque", "name": "Cinémathèque de Grenoble", "url": "https://www.cinemathequedegrenoble.fr/agenda/", "kind": "ai"},
    {"id": "museegrenoble", "name": "Musée de Grenoble", "url": "https://www.museedegrenoble.fr/1902-tout-l-agenda.htm", "kind": "ai"},
    {"id": "casemate", "name": "La Casemate", "url": "https://lacasemate.fr/programmations/", "kind": "ai"},
    {"id": "hexagone", "name": "L'Hexagone Meylan", "url": "https://www.theatre-hexagone.eu/", "kind": "ai"},
    {"id": "larampe", "name": "La Rampe Échirolles", "url": "https://www.larampe-echirolles.fr/tous-les-spectacles/", "kind": "ai"},
    {"id": "espace600", "name": "Espace 600", "url": "https://www.espace600.fr/evenements/", "kind": "ai"},
    {"id": "alpexpo", "name": "Alpexpo", "url": "https://www.alpexpo.com/agenda", "kind": "ai"},
    # Towns of the Métropole
    {"id": "meylan", "name": "Ville de Meylan", "url": "https://www.meylan.fr/41-agenda.htm", "kind": "ai"},
    {"id": "echirolles", "name": "Ville d'Échirolles", "url": "https://www.echirolles.fr/evenements", "kind": "ai"},
    {"id": "eybens", "name": "Ville d'Eybens", "url": "https://www.eybens.fr/125-agenda-culturel.htm", "kind": "ai"},
    {"id": "seyssinet", "name": "Ville de Seyssinet-Pariset", "url": "https://seyssinet-pariset.fr/agenda/", "kind": "ai"},
    {"id": "smh", "name": "Ville de Saint-Martin-d'Hères", "url": "https://www.saintmartindheres.fr/cadre-de-vie/evenementiel/", "kind": "ai"},
]
