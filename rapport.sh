#!/bin/sh
# Produit les PDF d'une séance : ./rapport.sh [séance.bws] [--sans-analyse] [--avec-noms]
# Sans fichier : choisir parmi les .bws du dossier réglé dans bridge-coach.ini.
ICI="$(cd "$(dirname "$0")" && pwd)"
exec "$ICI/.venv/bin/python" -I -X utf8 "$ICI/src/rapport.py" "$@"
