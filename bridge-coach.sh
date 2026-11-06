#!/bin/sh
# Ouvre l'application des rapports : ./bridge-coach.sh [--navigateur]
ICI="$(cd "$(dirname "$0")" && pwd)"
exec "$ICI/.venv/bin/python" -I -X utf8 "$ICI/src/app.py" "$@"
