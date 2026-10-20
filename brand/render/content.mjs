// Everything the visuals say. Edit here, then `node render.mjs` (see brand/render/README.md).
// Post texts follow the exact format of grnbl/digest.py, but the events, prices and addresses
// are EXAMPLES (data/ is not in the repo): replace them with real posts copied from the board.

export const GROUPS = [
  { id: "community", name: "grnbl", file: "communaute", label: "Communauté" },
  { id: "infos", name: "Annonces", file: "annonces", icon: "megaphone", alert: true, label: "Annonces (alertes)" },
  { id: "gratuit", name: "grnbl · Gratuit", file: "gratuit", icon: "gift", label: "Gratuit" },
  { id: "sorties", name: "grnbl · Sorties", file: "sorties", icon: "ticket", label: "Sorties" },
  { id: "carburant", name: "grnbl · Carburant", file: "carburant", icon: "fuel", label: "Carburant" },
  { id: "famille", name: "grnbl · Enfants & famille", file: "famille", icon: "baby", label: "Enfants & famille" },
  { id: "bonsplans", name: "grnbl · Bons plans & brocantes", file: "bons-plans", icon: "tag", label: "Bons plans & brocantes" },
  { id: "nature", name: "grnbl · Montagne & nature", file: "nature", icon: "mountain-snow", label: "Montagne & nature" },
];

// The two announcement fonts kept out of the four of brand/autocollants-5.html.
export const FONTS = [
  { id: "familjen", family: "Familjen Grotesk", file: "FamiljenGrotesk.ttf", weights: "400 700" },
  { id: "host", family: "Host Grotesk", file: "HostGrotesk.ttf", weights: "300 800" },
];

// ---------- Posts (French, EXAMPLES) ----------
export const POSTS = [
  { file: "gratuit-a-reserver", group: "gratuit", day: "Aujourd'hui", time: "12:00", text:
`📅 *À réserver maintenant*
_Ce qui part vite : les places se prennent avant le jour J._

🆓 *Visite de la tour Perret* · dimanche 1/11 à 14h30 · Parc Paul-Mistral
   La tour de béton de 1925, fermée le reste de l'année : 20 places par créneau.
   👉 Réserver avant vendredi 30/10 : grenoble-tourisme.com

🆓 *Atelier gravure au Musée de Grenoble* · samedi 24/10 à 10h · Musée de Grenoble
   On repart avec sa propre estampe, dès 8 ans.
   ⏰ Réservations dès jeudi 22/10 à 9h : museedegrenoble.fr

🆓 *Soirée étoiles au fort de la Bastille* · vendredi 23/10 à 20h30 · Bastille
   Télescopes tournés vers Saturne, si le ciel est dégagé.
   👉 Réserver : bastille-grenoble.fr` },
  { file: "gratuit-cette-semaine", group: "gratuit", day: "Aujourd'hui", time: "12:00", text:
`🎭 *Cette semaine à Grenoble* · notre sélection parmi 78 sorties repérées

🆓 *Concert de midi de l'orchestre universitaire* · jeudi 22 à 12h30 · Campus de Saint-Martin-d'Hères
   Quarante minutes de Dvořák sur la pause déjeuner, entrée libre.

🆓 *Visite libre du Muséum* · dimanche 25 · Muséum de Grenoble
   Les collections et le jardin des plantes, gratuits toute la journée.

🆓 *Projection en plein air à la Casemate* · vendredi 23 à 19h · La Casemate
   Un documentaire sur les glaciers des Alpes, suivi d'un échange.

🆓 *Bal folk sur le parvis* · samedi 24 à 18h · Place Saint-André
   Initiation pour débutants la première demi-heure.` },
  { file: "sorties-cette-semaine", group: "sorties", day: "Aujourd'hui", time: "12:00", text:
`🎭 *Cette semaine à Grenoble* · notre sélection parmi 169 sorties repérées

🎟️ *Concert à la Belle Électrique* · vendredi 23 à 20h · La Belle Électrique
   La date rock du mois, encore des places en fosse.

🎟️ *Danse contemporaine à la MC2* · jeudi 22 à 19h30 · MC2
   Une pièce pour douze danseurs, tarif réduit à 10 € pour les moins de 26 ans.

🎟️ *Ciné-concert à la Cinémathèque* · samedi 24 à 20h · Cinémathèque de Grenoble
   Un film muet de 1927 accompagné au piano.` },
  { file: "carburant", group: "carburant", day: "Aujourd'hui", time: "10:00", text:
`⛽ *Les pleins les moins chers ce mercredi*

*Gazole*
🥇 1,589 € · *Intermarché*, avenue Gabriel-Péri, Saint-Martin-d'Hères
🥈 1,598 € · *Carrefour Market*, cours Jean-Jaurès, Grenoble
🥉 1,604 € · *Leclerc*, rue de la Liberté, Échirolles
_Jusqu'à 16 € d'écart sur un plein avec la plus chère_

*SP95-E10*
🥇 1,689 € · *Auchan*, avenue de l'Europe, Échirolles
🥈 1,695 € · *Intermarché*, avenue Gabriel-Péri, Saint-Martin-d'Hères
🥉 1,702 € · *Super U*, route de Lyon, Fontaine
_Jusqu'à 15 € d'écart sur un plein avec la plus chère_

_Prix officiels (prix-carburants.gouv.fr), 84 stations de la Métropole._` },
  { file: "famille-cette-semaine", group: "famille", day: "Aujourd'hui", time: "12:00", text:
`👨‍👩‍👧 *Cette semaine en famille* · notre sélection parmi 41 sorties repérées

🆓 *Contes pour les 3-6 ans* · mercredi 21 à 10h30 · Bibliothèque Kateb-Yacine
   Une demi-heure d'histoires, sans inscription.

🎟️ *Spectacle de marionnettes* · samedi 24 à 15h · Espace 600
   Dès 5 ans, 6 € la place.

🆓 *Atelier sciences à la Casemate* · mercredi 28 à 14h · La Casemate
   Fabriquer une fusée à eau, de 8 à 12 ans.` },
  { file: "bons-plans", group: "bonsplans", day: "Aujourd'hui", time: "18:00", text:
`🛍️ *Les bons plans de la semaine* · notre sélection parmi 23 idées repérées

🆓 *Bourse aux skis* · samedi 24 à 8h · Gymnase municipal, Gières
   Skis, chaussures et casques d'occasion avant l'hiver : arriver tôt.

🆓 *Grande braderie de Fontaine* · dimanche 25 à 7h · Centre-ville, Fontaine
   Plus de 300 exposants dans les rues du centre.

🆓 *Bourse aux jouets* · dimanche 25 à 9h · Alpexpo
   Jouets et livres d'enfants à petits prix avant Noël.` },
  { file: "nature", group: "nature", day: "Aujourd'hui", time: "18:00", text:
`🏔️ *Dehors cette semaine* · notre sélection parmi 19 idées repérées

🆓 *Sortie oiseaux migrateurs avec la LPO* · samedi 24 à 9h · Parc de l'Île d'Amour, Meylan
   Jumelles prêtées, guide naturaliste, retour vers midi.

🎟️ *Soirée films de montagne* · vendredi 23 à 20h · Le Summum
   Trois films d'alpinisme, 8 €.

🆓 *Balade nature sur la Bastille* · dimanche 25 à 10h · Jardin des Dauphins
   Deux heures à pied avec un guide, sans inscription.` },
  { file: "annonces-alerte", group: "infos", day: "Aujourd'hui", time: "07:45", text:
`🚨 *Alerte Grenoble* · mardi 20/10

*Météo en Isère*
🔴 Vigilance rouge pluie-inondation aujourd'hui
_Conseils et carte : vigilance.meteofrance.fr_

_Sources : Météo-France, Atmo AuRA, Mobilités M._` },
];

// English translation of the first post, as the board shows it ("English translation (not posted)").
export const POST_EN = `📅 *Book now*
_What goes fast: places are taken before the day._

🆓 *Visit of the Perret tower* · Sunday 1/11 at 2:30 pm · Parc Paul-Mistral
   The 1925 concrete tower, closed the rest of the year: 20 places per slot.
   👉 Book before Friday 30/10

🆓 *Printmaking workshop at the Musée de Grenoble* · Saturday 24/10 at 10 am
   You leave with your own print, from age 8.
   ⏰ Booking opens Thursday 22/10 at 9 am`;

// ---------- Video (English) ----------
// Parts of the PROPOSED VIDEO PLAN (neighborhood-hacks-recherche/recherche/jury-2026-10-20.md, section 5).
export const PARTS = [
  { n: "01", title: "The problem", sub: "Without someone like my mum, nobody hears about it." },
  { n: "02", title: "The proof", sub: "What Grenoble offers in one week." },
  { n: "03", title: "The product", sub: "One WhatsApp community, one group per topic." },
  { n: "04", title: "What is not obvious", sub: "Announced while you can still book." },
  { n: "05", title: "How it works", sub: "AI reads, code keeps the guarantees, a human checks." },
  { n: "06", title: "It ran for real", sub: "Real groups, real posts, every week." },
  { n: "07", title: "Limits & next", sub: "What it does not do yet." },
  { n: "08", title: "Close", sub: "grnbl: Grenoble, in your pocket." },
];

export const LOWER_THIRDS = [
  { file: "elior", title: "Elior", sub: "Made grnbl, Grenoble" },
  { file: "real-post", title: "A real post", sub: "grnbl · Gratuit, Wednesday 12:00" },
  { file: "board", title: "The review board", sub: "About 11 lines per group, then All good" },
  { file: "timing", title: "Timing is code, not AI", sub: "Never posted once it is too late to book" },
  { file: "fuel", title: "Fuel, every morning", sub: "Official prices, posted at 10:00" },
];

export const TAGLINE = "Grenoble, in your pocket.";
export const PITCH = "The person who always knows what’s on, for a whole city, inside WhatsApp.";
export const REPO = "github.com/eliorpom-cmd/grnbl";
