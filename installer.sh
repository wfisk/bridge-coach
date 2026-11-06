#!/bin/sh
# Installe le programme : environnement Python dans .venv/ et bibliothèques.
# Les fichiers de l'utilisateur vont dans ~/Documents/bridge-coach-files, créé au premier lancement.
# Usage : ./installer.sh        (Mac ou Linux, Python 3.9 ou plus récent)
set -e
ICI="$(cd "$(dirname "$0")" && pwd)"
cd "$ICI"
PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
    echo "Python 3 introuvable : l'installer (https://www.python.org) puis relancer ./installer.sh"; exit 1
fi
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || {
    echo "Il faut Python 3.9 ou plus récent ($("$PY" --version) trouvé)."; exit 1; }
if [ ! -x .venv/bin/python ]; then
    echo "Création de l'environnement Python (.venv)…"
    "$PY" -m venv .venv
fi
echo "Installation des bibliothèques…"
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt
chmod +x rapport.sh
echo "Vérification…"
.venv/bin/python -I -c "import sys; sys.path.insert(0, 'src'); import reportlab, endplay, ruamel.yaml; \
from regles import charger; from entames import charger as ch; \
e = charger('systems/sef-2024/regles.yaml').verifier() + ch('systems/sef-2024/entames.yaml').verifier(); \
print('Règles lues, exemples vérifiés.' if not e else e)"
echo
if [ "$(uname)" = "Darwin" ] && [ -t 0 ] && [ ! -d "/Applications/Bridge Coach.app" ]; then
    printf "Créer l'application Bridge Coach (dossier Applications et Bureau) ? [O/n] "
    read reponse || reponse=""
    case "$reponse" in n|N|non|Non|NON) echo "Plus tard : ./raccourci-mac.sh" ;; *) ./raccourci-mac.sh ;; esac
    echo
fi
echo "Installation terminée. Pour ouvrir l'application : Bridge Coach, sur le Bureau ou dans Applications (ou ./bridge-coach.sh)."
echo "En ligne de commande :"
echo "  ./rapport.sh                (choisir parmi les .bws du dossier de bridge-coach.ini)"
echo "  ./rapport.sh séance.bws     (un fichier précis)"
