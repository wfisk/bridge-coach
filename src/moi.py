# -*- coding: utf-8 -*-
"""Qui est l'utilisateur : son nom complet, choisi dans Réglages (« Vous êtes »), gardé dans etat.json à côté de
bridge-coach.ini. Les rapports et l'onglet Donnes surlignent la ligne de ses tables : les paires de la séance dont un
joueur porte ce nom ("joueurs" du .bc.json). Léger : build_pdf.py l'importe sans le reste du programme."""
import json, os, sys


def dossier_des_reglages():
    """Un lieu fixe, propre à l'ordinateur : bridge-coach.ini dit où sont les fichiers, il ne peut pas être avec eux.
    BRIDGE_COACH_DONNEES sert aux essais : tout va alors dans ce dossier."""
    if os.environ.get("BRIDGE_COACH_DONNEES"): return os.environ["BRIDGE_COACH_DONNEES"]
    if sys.platform == "win32": return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Bridge Coach")
    if sys.platform == "darwin": return os.path.expanduser("~/Library/Application Support/Bridge Coach")
    return os.path.expanduser("~/.config/bridge-coach")


ETAT = os.path.join(dossier_des_reglages(), "etat.json")
SURLIGNE = "#fff3bf"                                       # le fond de vos lignes, dans les PDF et l'application


def nom():
    """Le nom choisi (« MARTIN Anne »), ou None."""
    try:
        return (json.load(open(ETAT, encoding="utf-8")) or {}).get("moi") or None
    except (OSError, ValueError, AttributeError):
        return None


def paires(data, qui=None):
    """Les paires de la séance où joue l'utilisateur (ou qui), d'après les noms complets des joueurs."""
    qui = (qui if qui is not None else nom() or "").strip().lower()
    if not qui: return set()
    return {str(k) for k, v in (data.get("joueurs") or {}).items()
            if any((j.get("nom") or "").strip().lower() == qui for j in v)}


def a_joue(t, mes_paires):
    """La table t est-elle une des siennes ?"""
    return bool(mes_paires) and (str(t.get("paire_ns")) in mes_paires or str(t.get("paire_eo")) in mes_paires)


def tous_les_noms(seances):
    """Les noms complets des joueurs de ces séances (.bc.json), triés : de quoi choisir le sien."""
    out = set()
    for c in seances:
        try:
            for v in (json.load(open(c, encoding="utf-8")).get("joueurs") or {}).values():
                out.update(j["nom"].strip() for j in v if (j.get("nom") or "").strip())
        except (OSError, ValueError, AttributeError):
            pass
    return sorted(out, key=str.lower)
