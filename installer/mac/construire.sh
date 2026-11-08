#!/bin/sh
# Fait Bridge-Coach.pkg : ./installer/mac/construire.sh [version] [dossier de sortie]   (GitHub Actions, ou ici)
# Un paquet sans fichiers : seulement le script postinstall, qui télécharge et vérifie tout.
set -e
V="${1:-1.0}"
SORTIE="${2:-$(dirname "$0")/../../dist}"           # relatif au dossier d'où on lance, avant le cd
mkdir -p "$SORTIE"; SORTIE="$(cd "$SORTIE" && pwd)"
cd "$(dirname "$0")"
T="$(mktemp -d)"
pkgbuild --nopayload --scripts scripts --identifier fr.bridgecoach.installateur --version "$V" "$T/composant.pkg"
productbuild --distribution distribution.xml --resources ressources --package-path "$T" "$SORTIE/Bridge-Coach.pkg"
rm -rf "$T"
echo "$SORTIE/Bridge-Coach.pkg"
