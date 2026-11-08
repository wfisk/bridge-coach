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


def mon_camp(tables, mes_paires):
    """("NS" ou "EO", la table) si l'utilisateur a joué la donne, sinon (None, None)."""
    for t in tables:
        if a_joue(t, mes_paires):
            return ("NS" if str(t.get("paire_ns")) in mes_paires else "EO"), t
    return None, None


def ordre(tables, mes_paires=frozenset()):
    """Les tables du meilleur résultat au moins bon : vu de votre camp si vous avez joué la donne, sinon de Nord-Sud.
    À score égal, votre table d'abord, puis l'ordre des tables."""
    camp, _ = mon_camp(tables, mes_paires)
    signe = -1 if camp == "EO" else 1
    rang = {id(t): k for k, t in enumerate(tables)}
    return sorted(tables, key=lambda t: (-signe * (t.get("score_ns") or 0), not a_joue(t, mes_paires), rang[id(t)]))


def votre_rang(tables, mes_paires, decrire=lambda t: ""):
    """« Votre résultat : 8e sur 24 (50 %) – meilleur : +200 (3♠ Sud -2) », ou "" si vous n'avez pas joué la donne.
    decrire(t) : le contrat d'une table en texte."""
    camp, t = mon_camp(tables, mes_paires)
    if not camp or len(tables) < 2: return ""
    s = lambda x: (x.get("score_ns") or 0) * (1 if camp == "NS" else -1)
    rang = 1 + sum(1 for x in tables if s(x) > s(t))
    egaux = sum(1 for x in tables if s(x) == s(t)) > 1
    pct = t.get("pct_ns")
    pct = None if pct is None else pct if camp == "NS" else 100 - pct
    meilleure = max(tables, key=s)
    texte = f"Votre résultat : {rang}{'er' if rang == 1 else 'e'}{' ex aequo' if egaux else ''} sur {len(tables)}"
    if pct is not None: texte += f" ({pct:.0f} %)"
    if s(meilleure) > s(t): texte += f" – meilleur : {s(meilleure):+d} ({decrire(meilleure)})"
    else: texte += " – le meilleur score de la donne"
    return texte
