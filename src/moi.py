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
SURLIGNE = "#fff2a8"                                       # le fond de vos lignes, dans les PDF et l'application


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


# ---------------------------------------------------------------- le mouvement : vos tours, tables et adversaires
def _paire(data, k):
    """« AP/EK (NS4) » : les initiales d'une paire et sa position."""
    p = (data.get("paires") or {}).get(str(k)) or {}
    nom = p.get("nom") or "/".join(j.get("initiales", "") for j in (data.get("joueurs") or {}).get(str(k), []))
    return f"{nom} ({p['position']})" if p.get("position") else nom


def _etendue(donnes):
    return f"{donnes[0]}–{donnes[-1]}" if len(donnes) > 1 else str(donnes[0]) if donnes else ""


def mouvement(data, mes=None):
    """Le parcours de votre paire (ou des paires mes) : {"paire", "tours": [{tour, table, donnes, adversaires, relais}]}.
    Celui que la séance décrit à la main (session.mouvement) s'il est le vôtre ; sinon celui que donne le mouvement entier
    lu dans le .bws (session.rondes), pour n'importe quelle paire choisie dans « Vous êtes » ; {} sinon. Sans « Vous
    êtes », le mouvement écrit à la main."""
    s = data.get("session") or {}
    mes = {str(x) for x in (paires(data) if mes is None else mes)}
    m = s.get("mouvement") or {}
    if m.get("tours") and (not mes or str(m.get("paire")) in mes): return m
    rondes = s.get("rondes") or []
    k = next((p for p in sorted(mes) if any(p in (r["ns"], r["eo"]) for r in rondes)), None)
    if not k: return {}
    tours = []
    for t in sorted({r["tour"] for r in rondes}):
        r = next((r for r in rondes if r["tour"] == t and k in (r["ns"], r["eo"])), None)
        tours.append(dict(tour=t, table=r["table"], donnes=r["donnes"], adversaires=r["eo"] if r["ns"] == k else r["ns"],
                          relais=False) if r else dict(tour=t, table="", donnes=[], adversaires=None, relais=True))
    return dict(paire=k, tours=tours)


def parcours(data):
    """Les tours d'une paire ("mouvement" de la séance) : tour, table, donnes, adversaires, % moyen du tour.
    [] si la séance ne décrit pas son mouvement."""
    m = mouvement(data)
    k = str(m.get("paire", "")); out = []
    for t in m.get("tours") or []:
        pcts = []
        for d in data.get("donnes", []):
            if d["n"] not in t["donnes"]: continue
            for x in d.get("tables", []):
                if x.get("pct_ns") is None: continue
                if str(x.get("paire_ns")) == k: pcts.append(x["pct_ns"])
                elif str(x.get("paire_eo")) == k: pcts.append(100 - x["pct_ns"])
        out.append(dict(tour=t["tour"], table=t["table"], donnes=_etendue(t["donnes"]),
                        adversaires="relais : pas de jeu" if t.get("relais") or not t.get("adversaires") else _paire(data, t["adversaires"]),
                        pct=f"{sum(pcts) / len(pcts):.0f} %" if pcts else ""))
    return out


def qui_parcourt(data):
    """« WF/FR (EO4) » : la paire dont le mouvement décrit les tours."""
    m = mouvement(data)
    return _paire(data, m["paire"]) if m.get("paire") else ""


def tour_de(data, n):
    """« Tour 1 · table 4 · contre AP/EK (NS4) » pour la donne n, ou "" si le mouvement ne la place pas."""
    m = mouvement(data)
    for t in m.get("tours") or []:
        if n in t["donnes"]:
            if t.get("relais") or not t.get("adversaires"):
                return f"Tour {t['tour']} · table {t['table']} : relais, donne non jouée par {qui_parcourt(data)}"
            return f"Tour {t['tour']} · table {t['table']} · {qui_parcourt(data)} contre {_paire(data, t['adversaires'])}"
    return ""


MARQUES = {"MP": "match-points", "IMP": "IMP"}


def marque(data):
    """La marque de la séance, "MP" (match-points) ou "IMP" : celle que la séance a gardée (session.marque, lue à
    l'import ou choisie sur la page Séance), sinon devinée : match-points à plus de deux tables, IMP sinon (un
    entraînement, un match à deux tables)."""
    s = data.get("session") or {}
    if s.get("marque") in MARQUES: return s["marque"]
    tables = s.get("tables") or max((len(d.get("tables") or []) for d in data.get("donnes") or []), default=0)
    return "MP" if tables > 2 else "IMP"


def tour_infos(data, n):
    """Le tour de la donne n : {"tour": 1, "contre": "AP/EK", "relais": False}, ou None si le mouvement ne la place pas."""
    for t in mouvement(data).get("tours") or []:
        if n in t["donnes"]:
            relais = bool(t.get("relais") or not t.get("adversaires"))
            contre = "" if relais else _paire(data, t["adversaires"]).split(" (")[0]
            return dict(tour=t["tour"], contre=contre, relais=relais)
    return None


def ordre_joue():
    """L'option de Réglages : les rapports présentent les donnes dans l'ordre où vous les avez jouées."""
    try:
        return bool((json.load(open(ETAT, encoding="utf-8")) or {}).get("ordre_joue"))
    except (OSError, ValueError, AttributeError):
        return False


def ordre_des_donnes(data, mes_paires):
    """Les donnes dans l'ordre où vos paires les ont jouées (tour après tour, le relais à sa place), puis les autres
    par numéro ; par numéro si la séance ne décrit pas votre parcours."""
    donnes = sorted(data.get("donnes", []), key=lambda d: d["n"])
    m = mouvement(data, mes_paires)
    if str(m.get("paire", "")) not in {str(x) for x in mes_paires}: return donnes
    rang = {n: k for k, n in enumerate(n for t in m.get("tours") or [] for n in t["donnes"])}
    return sorted(donnes, key=lambda d: (rang.get(d["n"], len(rang)), d["n"]))
