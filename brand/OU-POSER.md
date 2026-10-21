# Où poser quoi

Planche pour tout voir : `brand/visuels-11.html`. Les fichiers texte existent en deux versions,
`-familjen` et `-host` : n'utiliser que ceux de la police choisie. Pour refaire un fichier : `brand/render/README.md`.

## Photos WhatsApp (`export/whatsapp/`, 640 × 640)
- `communaute.png` → photo de la communauté (WhatsApp l'arrondit en carré).
- `annonces.png` → photo du groupe d'annonces de la communauté (reçoit les alertes ; le seul rouge).
- `gratuit.png` → groupe Gratuit.
- `sorties.png` → groupe Sorties.
- `carburant.png` → groupe Carburant.
- `famille.png` → groupe Enfants & famille.
- `bons-plans.png` → groupe Bons plans & brocantes.
- `nature.png` → groupe Montagne & nature.
- À faire au passage : renommer la communauté « GRNBL » en « grnbl » (minuscules).

## Devpost (`export/devpost/`, 2400 × 1600, 3:2)
- `cover-*.png` → « Thumbnail / cover image » du projet.
- `1-problem-*.png` → galerie, 1re image (le problème, les sources).
- `2-pipeline-*.png` → galerie, 2e (38 sources → 1 203 → 448 → ~11 lignes → 7 groupes).
- `3-post-*.png` → galerie, 3e (un post et sa traduction anglaise).
- `4-numbers-*.png` → galerie, 4e (45 sorties, 15-17 €, 1 203 événements).
- `5-board-*.png` → galerie, 5e (tableau de relecture ; reconstitution, une vraie capture du tableau peut la remplacer).
- `6-community-*.png` → galerie, 6e (la communauté et ses groupes).

## Vidéo (`export/video/`, 1920 × 1080)
- `00-title-*.png` → premier plan de la vidéo (2-3 s).
- `01-the-problem-*.png` → carton avant 0:00-0:15 (ou en ouverture du problème, 1 s).
- `02-the-proof-*.png` → avant 0:15.
- `03-the-product-*.png` → avant 0:40.
- `04-what-is-not-obvious-*.png` → avant 1:00.
- `05-how-it-works-*.png` → avant 1:45.
- `06-it-ran-for-real-*.png` → avant 2:40.
- `07-limits-next-*.png` → avant 3:05.
- `08-close-*.png` → avant 3:20 (facultatif : le carton de fin suffit).
- `99-end-*.png` → dernier plan (lien du repo, outils, auteur).
- `lower-third-elior-*.png` → par-dessus le plan face caméra (PNG transparent, calque au-dessus).
- `lower-third-real-post-*.png` → par-dessus le téléphone qui reçoit le post du mercredi.
- `lower-third-board-*.png` → par-dessus la capture du tableau.
- `lower-third-timing-*.png` → par-dessus l'avant/après « 1 Jan - 6 Dec » / « Sun 1 Nov ».
- `lower-third-fuel-*.png` → par-dessus le post carburant.

## Posts dans WhatsApp (`export/posts/`, 1080 × 2340) — TEXTES D'EXEMPLE
Format exact de `grnbl/digest.py`, mais événements, prix, adresses et nombres inventés (`data/` n'est pas
dans le repo). À remplacer par les vrais posts de l'édition du 21/10 avant la vidéo ou Devpost
(`brand/render/content.mjs`, puis `node render.mjs posts devpost`), ou mieux, filmer le vrai téléphone.
- `communaute-liste.png` → vidéo, partie 03 (la communauté et ses groupes).
- `gratuit-a-reserver.png` → vidéo, partie 04 (annoncé quand on peut réserver) ; aussi dans `3-post`.
- `gratuit-cette-semaine.png` → vidéo, partie 03 ; aussi dans la couverture Devpost.
- `sorties-cette-semaine.png` → vidéo, partie 03 (exemple de la chaîne payante).
- `carburant.png` → vidéo, partie 02 (preuve : l'écart sur un plein).
- `famille-cette-semaine.png` → vidéo, partie 03 (au choix).
- `bons-plans.png` → vidéo, partie 03 (au choix).
- `nature.png` → vidéo, partie 03 (au choix).
- `annonces-alerte.png` → vidéo, partie 05 (alertes rares, validées à la main) ; alerte fictive.
