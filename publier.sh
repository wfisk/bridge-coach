#!/bin/sh
# Publie une version pour les membres : ./publier.sh 1.4 "Ce qui change, en une phrase"
# Écrit VERSION, vérifie les tests, crée l'étiquette v1.4 et l'envoie sur GitHub. Le bouton « Rechercher une mise à
# jour » des Réglages la trouve aussitôt. Seules les étiquettes vX.Y sont proposées : le travail en cours sur main
# n'arrive jamais tout seul chez les membres.
set -e
cd "$(dirname "$0")"
V="$1"; NOTE="$2"
case "$V" in ''|*[!0-9.]*) echo "Usage : ./publier.sh 1.4 \"Ce qui change\""; exit 1 ;; esac
[ -n "$NOTE" ] || { echo "Ajoutez une phrase qui dit ce qui change."; exit 1; }
[ "$(git branch --show-current)" = "main" ] || { echo "À publier depuis la branche main."; exit 1; }
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "Des modifications ne sont pas enregistrées (git commit d'abord)."; exit 1; }
git rev-parse -q --verify "refs/tags/v$V" >/dev/null && { echo "La version $V existe déjà."; exit 1; }
for t in tests/test_*.py; do .venv/bin/python -I -X utf8 "$t" >/dev/null || { echo "Test en échec : $t"; exit 1; }; done
echo "$V" > VERSION
git add VERSION
git commit -q -m "Version $V : $NOTE"
git tag -a "v$V" -m "$NOTE"
git push -q origin main "v$V"
echo "Version $V publiée. GitHub fait maintenant les installateurs (quelques minutes) :"
echo "  https://github.com/wfisk/bridge-coach/actions   puis   https://github.com/wfisk/bridge-coach/releases"
