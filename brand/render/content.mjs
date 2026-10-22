// Everything the visuals say. Edit here, then `node render.mjs` (see brand/render/README.md).
// The Gratuit posts and their English translation are real (21 October 2026 edition, the first
// events of each post); the other posts are examples in the same format as grnbl/digest.py.

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
_Les places partent avant le jour J : on vous prévient tant qu'il en reste._

*Visite au musée Lumière sur le noir*
Mercredi 28 oct. · 18h · Musée de Grenoble
Visite thématique « Lumière sur le noir » au Musée de Grenoble, sur réservation.
👉 Réserver : https://tmg-billetterie.mapado.com/event/788721-lumiere-sur-le-noir-visite-guidee-au-musee-de-grenoble

*Florie*
Vendredi 6 nov. · 20h30 · L'Atrium, Fontanil-Cornillon
Concert gratuit de Florie, révélée dans La Nouvelle Star, pop sensible entre guitare et nappes électro, à l'Atrium de Fontanil-Cornillon.
👉 Réserver : https://www.grenoble-tourisme.com/fr/decouvrir/evenements/agenda/detail/florie-7924519/

*Festival Livres à vous (18e édition)*
Mercredi 18 nov. · Pays voironnais
Festival du livre « Livres à vous », 18e édition, à Voiron et dans le Pays voironnais, du 18 au 22 novembre.
👉 Réserver : https://livresavous.fr/affiche-18eme-edition/` },
  { file: "gratuit-cette-semaine", group: "gratuit", day: "Aujourd'hui", time: "12:00", text:
`🆓 *Gratuit cette semaine*
_Sans réservation. 5 sorties choisies parmi les 29 repérées cette semaine._

*Les Forestivités*
Jusqu'au 1er nov. · Grenoble
Les Forestivités : deux semaines d'animations, visites et expositions autour de la forêt et du bois, gratuit.
🔗 https://www.grenoble-tourisme.com/fr/decouvrir/evenements/agenda/detail/les-forestivites-6223920/

*Blues Tour / Alex Henley*
Jeudi 22 oct. · Grenoble
Concert gratuit du bluesman texan Alex Henley à Grenoble.
🔗 https://www.grenoble-tourisme.com/fr/decouvrir/evenements/agenda/detail/blues-tour-alex-henley-8012795/

*Balade théâtralisée - Cadavres exquis*
Samedi 24 oct. · 4 Pl. Saint-Laurent
Balade théâtralisée gratuite « Cadavres exquis » au musée archéologique Saint-Laurent.
🔗 https://allevents.in/grenoble/balade-théâtralisée-cadavres-exquis/200030788986922` },
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
_Tickets sell out before the big day: we'll let you know while there are still some left._

*Light on the Dark Visit*
Wednesday 28 Oct · 6pm · Musée de Grenoble
Thematic visit "Light on the Dark" at the Musée de Grenoble, by reservation.
👉 Book: https://tmg-billetterie.mapado.com/event/788721-lumiere-sur-le-noir-visite-guidee-au-musee-de-grenoble

*Florie*
Friday 6 Nov · 8:30pm · L'Atrium, Fontanil-Cornillon
Free concert by Florie, revealed on La Nouvelle Star, sensitive pop mixing guitar and electronic layers, at the L'Atrium in Fontanil-Cornillon.
👉 Book: https://www.grenoble-tourisme.com/fr/decouvrir/evenements/agenda/detail/florie-7924519/`;

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
