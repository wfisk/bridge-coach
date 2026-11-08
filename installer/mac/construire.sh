#!/bin/sh
# Fait Bridge-Coach.pkg : ./installer/mac/construire.sh [version] [dossier de sortie]   (GitHub Actions, ou ici)
# Un paquet sans fichiers : seulement le script postinstall, qui télécharge et vérifie tout.
set -e
cd "$(dirname "$0")"
V="${1:-1.0}"; SORTIE="$(mkdir -p "${2:-../../dist}" && cd "${2:-../../dist}" && pwd)"
T="$(mktemp -d)"
pkgbuild --nopayload --scripts scripts --identifier fr.bridgecoach.installateur --version "$V" "$T/composant.pkg"
productbuild --distribution distribution.xml --resources ressources --package-path "$T" "$SORTIE/Bridge-Coach.pkg"
rm -rf "$T"
echo "$SORTIE/Bridge-Coach.pkg"
