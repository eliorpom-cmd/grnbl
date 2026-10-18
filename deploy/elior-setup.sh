#!/bin/bash
# The two steps of the Deployxa move that need Elior at the keyboard (about 5 min):
# sign the Deployxa CLI in, then make a long-lived Claude token for the server.
# The token is pasted hidden and written to data/secrets/ (git-ignored, mode 600):
# it never shows on screen, in the shell history or in a chat.
set -u
cd "$(dirname "$0")/.." || exit 1

echo "1/2  Connexion à Deployxa (une page s'ouvre dans le navigateur)"
if npx -y @deployxa/cli@1.0.4 whoami >/dev/null 2>&1; then
  echo "déjà connecté"
else
  npx -y @deployxa/cli@1.0.4 login || { echo "Échec de la connexion Deployxa : relance ce script."; exit 1; }
fi

echo
echo "2/2  Jeton Claude pour le serveur (une page s'ouvre, valide avec ton compte Claude)"
claude setup-token
echo
echo "Copie le jeton affiché juste au-dessus (il commence par sk-ant-), puis colle-le ici."
echo "Rien ne s'affiche pendant que tu colles, c'est normal. Termine par Entrée."
read -rs token
case "$token" in
  sk-ant-*) ;;
  *) echo "Ça ne ressemble pas à un jeton Claude (sk-ant-…) : relance le script."; exit 1 ;;
esac
mkdir -p data/secrets
umask 077
printf '%s\n' "$token" > data/secrets/claude-oauth-token
echo "Jeton enregistré dans data/secrets/claude-oauth-token. Tu peux fermer ce terminal (clear pour effacer l'écran)."
