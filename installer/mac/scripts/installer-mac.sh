#!/bin/bash
# Installe Bridge Coach dans un dossier, au nom de l'utilisateur : lancé par le postinstall de Bridge-Coach.pkg.
# Rien du programme n'est dans le .pkg : la dernière version publiée sur GitHub, chaque téléchargement vérifié par
# son empreinte SHA-256 :
#   1. l'archive du programme (bridge-coach-X.Y.zip), contre le SHA256SUMS publié avec elle ;
#   2. Python, contre l'empreinte écrite dans installer/python.txt de l'archive vérifiée ;
#   3. les bibliothèques, contre les empreintes de requirements.txt (pip --require-hashes).
# Usage : installer-mac.sh <dossier> [archive.zip SHA256SUMS]   (les deux derniers : essai sans GitHub)
set -euo pipefail
D="$1"; ZIP="${2:-}"; SOMMES="${3:-}"
DEPOT="wfisk/bridge-coach"
T="$(mktemp -d -t bridge-coach)"
trap 'rm -rf "$T"' EXIT
etape() { echo; echo "$1"; }
echec() { echo; echo "L'installation a échoué : $1"; exit 1; }
telecharger() { curl -fsSL --retry 3 -A "Bridge-Coach" -o "$2" "$1" || echec "téléchargement impossible : $1"; }
verifier() {
    [ "$(shasum -a 256 "$1" | cut -d' ' -f1)" = "$2" ] \
        || echec "empreinte incorrecte pour $(basename "$1") : le fichier téléchargé n'est pas celui qui a été publié. Rien n'a été installé."
}
adresse() { grep -o "\"browser_download_url\": *\"[^\"]*$1\"" "$T/version.json" | head -1 | sed 's/.*"\(https[^"]*\)"$/\1/'; }

etape "1/5  Dernière version de Bridge Coach"
if [ -z "$ZIP" ]; then
    telecharger "https://api.github.com/repos/$DEPOT/releases/latest" "$T/version.json"
    url_zip="$(adresse '/bridge-coach-[0-9.]*\.zip')"; url_sommes="$(adresse '/SHA256SUMS')"
    [ -n "$url_zip" ] && [ -n "$url_sommes" ] || echec "la dernière version n'a pas d'archive vérifiable sur GitHub."
    ZIP="$T/$(basename "$url_zip")"; SOMMES="$T/SHA256SUMS"
    echo "$(basename "$ZIP" .zip)"
    telecharger "$url_zip" "$ZIP"; telecharger "$url_sommes" "$SOMMES"
fi
nom="$(basename "$ZIP")"
attendu="$(awk -v n="$nom" '{ f = $2; sub(/^\*/, "", f); if (f == n) { print $1; exit } }' "$SOMMES")"
[ -n "$attendu" ] || echec "$nom n'a pas d'empreinte publiée."
verifier "$ZIP" "$attendu"
echo "Empreinte vérifiée."

etape "2/5  Mise en place du programme"
mkdir -p "$T/programme"
ditto -x -k "$ZIP" "$T/programme"
source="$T/programme"
haut=("$source"/*)
[ ${#haut[@]} -eq 1 ] && [ -d "${haut[0]}" ] && source="${haut[0]}"
[ -f "$source/src/app.py" ] || echec "l'archive ne contient pas le programme."
mkdir -p "$D"
# une installation précédente est remplacée en entier ; les fichiers de l'utilisateur sont ailleurs (Documents, et
# ses réglages dans ~/Library/Application Support/Bridge Coach)
find "$D" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
( shopt -s dotglob; mv "$source"/* "$D"/ )
echo "$D"

etape "3/5  Python"
case "$(uname -m)" in arm64) pf="mac-aarch64" ;; *) pf="mac-x86_64" ;; esac
ligne="$(grep "^$pf " "$D/installer/python.txt" | head -1)" || true
[ -n "$ligne" ] || echec "installer/python.txt ne dit pas quel Python prendre pour ce Mac."
read -r _ sha url <<< "$ligne"
telecharger "$url" "$T/python.tar.gz"
verifier "$T/python.tar.gz" "$sha"
echo "Empreinte vérifiée."
tar -xzf "$T/python.tar.gz" -C "$T"
mv "$T/python" "$D/.python"

etape "4/5  Bibliothèques (quelques minutes)"
"$D/.python/bin/python3" -m venv "$D/.venv"
"$D/.venv/bin/python" -m pip install -q --disable-pip-version-check --require-hashes -r "$D/requirements.txt"

etape "5/5  Vérification"
chmod +x "$D"/*.sh
( cd "$D" && .venv/bin/python -I -X utf8 -c "import sys; sys.path.insert(0, 'src'); import rapport, donnes, edition, app; print('Le programme se charge.')" )
echo; echo "Installation terminée."
