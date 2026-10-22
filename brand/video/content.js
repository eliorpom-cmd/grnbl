// Texts and numbers of the clips. Replace the numbers with the 21 October edition's, then re-render.
window.CONTENT = {
  // Weekly edition of 21 October 2026 (data/events/2026-10-21: 41 source files, all.json, reviewed.json,
  // 49 picks outside reserves over 5 groups, posts.en.json).
  run: { date: "21 Oct 2026", sources: 41, events: 1092, kept: 427, posts: 10, groups: 5, linesPerGroup: 10 },
  // Every source grnbl reads (grnbl/scrape/sources.py, plus the fuel feed and the yearly calendar).
  sources: ["L'Essentiel Grenoble", "Le Dauphiné libéré", "Place Gre'net", "ICI Isère", "Allevents Grenoble", "Eventbrite Grenoble", "Meetup Grenoble", "Grenoble Alpes Tourisme", "Ville de Grenoble", "Gre.mag", "Le Petit Bulletin", "ici Grenoble", "Grenoble-Alpes Métropole", "Université Grenoble Alpes", "MC2", "La Belle Électrique", "Le Summum", "Le Ciel", "Le Pacifique", "Cinémathèque de Grenoble", "Musée de Grenoble", "La Casemate", "L'Hexagone Meylan", "La Rampe Échirolles", "Espace 600", "Alpexpo", "Ville de Meylan", "Ville d'Échirolles", "Ville d'Eybens", "Ville de Seyssinet-Pariset", "Ville de Saint-Martin-d'Hères", "Brocabrac Isère", "Vide-Greniers.org Isère", "LPO Isère", "Bastille de Grenoble", "Les Allées Chantent", "Fuel prices (gov. feed)", "Yearly calendar"],
  // Before / after: a real event of the 21 October edition. Agenda line from gre-mag.fr, post block
  // from data/outbox/2026-10-21/sorties-to_book.json.
  before: {
    site: "gre-mag.fr",
    title: "Foire de Grenoble",
    lines: ["Du 30 octobre au 8 novembre", "Alpexpo", "5 euros en prévente jusqu'au 29 octobre ; 7 euros ensuite"],
  },
  after: {
    group: "🎭 Sorties",
    head: "📅 *À réserver maintenant*",
    line: "*Foire de Grenoble*\nVendredi 30 oct. · Alpexpo",
    when: "Vendredi 30 oct.",
    sub: "👉 Réserver avant jeudi 29 oct.",
    caption: "Fri 30 Oct. Book before Thursday: €5 instead of €7.",
  },
};
