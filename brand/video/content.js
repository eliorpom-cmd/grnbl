// Texts and numbers of the clips. Replace the numbers with the 21 October edition's, then re-render.
window.CONTENT = {
  // Full run on real data, 18 October 2026 (grnbl/CLAUDE.md, "Essai complet du 18/10").
  run: { date: "18 Oct 2026", sources: 38, events: 1203, kept: 448, minutes: 27, groups: 7, linesPerGroup: 11 },
  // Every source grnbl reads (grnbl/scrape/sources.py, plus the fuel feed and the yearly calendar).
  sources: ["L'Essentiel Grenoble", "Le Dauphiné libéré", "Place Gre'net", "ICI Isère", "Allevents Grenoble", "Eventbrite Grenoble", "Meetup Grenoble", "Grenoble Alpes Tourisme", "Ville de Grenoble", "Gre.mag", "Le Petit Bulletin", "ici Grenoble", "Grenoble-Alpes Métropole", "Université Grenoble Alpes", "MC2", "La Belle Électrique", "Le Summum", "Le Ciel", "Le Pacifique", "Cinémathèque de Grenoble", "Musée de Grenoble", "La Casemate", "L'Hexagone Meylan", "La Rampe Échirolles", "Espace 600", "Alpexpo", "Ville de Meylan", "Ville d'Échirolles", "Ville d'Eybens", "Ville de Seyssinet-Pariset", "Ville de Saint-Martin-d'Hères", "Brocabrac Isère", "Vide-Greniers.org Isère", "LPO Isère", "Bastille de Grenoble", "Les Allées Chantent", "Fuel prices (gov. feed)", "Yearly calendar"],
  // Before / after. EXAMPLE from the video plan (jury-2026-10-20.md §5): replace with a real event
  // of the edition, copied from its agenda page and from the board.
  before: {
    site: "grenoble-tourisme.com",
    title: "Guided visit of the Bastille forts",
    lines: ["From 1 January to 6 December 2026", "Several dates", "Booking required"],
  },
  after: {
    group: "🆓 Gratuit",
    head: "📅 *À réserver maintenant*",
    line: "🆓 *Visite guidée des forts de la Bastille* · dim. 1/11 à 14h30",
    sub: "   👉 Réserver avant ven. 30/10",
    caption: "Sun 1 Nov, 2:30 pm. Book before Friday.",
  },
};
