# -*- coding: utf-8 -*-
"""Le classement du tournoi rejoué : vos donnes rejouées dans l'onglet Jouer, face aux tables du club ce soir-là.

Pour chaque donne, le dernier essai fini (<séance>-jeu.json : enchères puis jeu de la carte, ou une passe générale) :
votre contrat, les levées vraiment faites à la carte (pas le double mort), votre score vu de votre camp, puis votre
% face aux tables du club (match-points, comme Bridgemate les compte) ou vos IMP contre la moyenne des tables (le
datum) pour une séance en IMP. Le total de la séance (% moyen, ou IMP par donne) est classé parmi les résultats
officiels des paires. Les donnes pas encore rejouées sont listées, pas comptées.
"""
from bws_extract import score, vul_of, imp
import moi

EN = {"SA": "NT", "♠": "S", "♥": "H", "♦": "D", "♣": "C"}
camp = lambda s: "NS" if s in "NS" else "EO"


def fini(e):
    """L'essai est-il allé au bout : une passe générale, ou le jeu de la carte joué jusqu'à la dernière levée ?"""
    return bool(e) and (e.get("contrat") == "passe" or e.get("levees") is not None)


def dernier_fini(essais):
    """Le dernier essai fini d'une donne (une liste d'essais, le plus ancien d'abord), ou None."""
    return next((e for e in reversed(essais or []) if fini(e)), None)


def score_ns(d, contrat, decl, levees):
    """Le score Nord-Sud d'un contrat (« 4♥X ») joué par decl, avec les levées faites par le déclarant."""
    if contrat == "passe" or not decl: return 0
    n, den, x = int(contrat[0]), contrat[1:].rstrip("X"), contrat.count("X")
    v = score(n, EN[den], x, vul_of(d["vul"], "NS" if decl in "NS" else "EW"), levees)
    return v if decl in "NS" else -v


def resultat(contrat, levees):
    """« = », « +1 », « -2 » ; "" pour une passe générale."""
    if contrat == "passe": return ""
    e = levees - int(contrat[0]) - 6
    return "=" if e == 0 else f"{e:+d}"


def datum(tables):
    """La moyenne des scores N-S des tables, arrondie à la dizaine (comme bws_extract pour les IMP)."""
    ts = [t.get("score_ns") or 0 for t in tables]
    return round(sum(ts) / len(ts) / 10) * 10 if ts else 0


def pct_face(tables, s_ns):
    """Le % N-S de ce score face aux tables : 1 par table battue, ½ par égalité (comparer.pct_face_aux_tables)."""
    ts = [t.get("score_ns") or 0 for t in tables if not t.get("recommande")]
    if not ts: return None
    return round(100 * (sum(s_ns > x for x in ts) + sum(s_ns == x for x in ts) / 2) / len(ts), 2)


def ligne_donne(d, e, marque):
    """Une donne : {n, etat ("rejouee", "a_rejouer", "sans_tables"), et pour une donne rejouée : siege, camp, contrat,
    declarant, levees, resultat, score (vu de votre camp), pct ou imp, meilleur (la meilleure table de votre camp)}."""
    tables = [t for t in d.get("tables") or [] if not t.get("recommande")]
    out = dict(n=d["n"], etat="a_rejouer", nb_tables=len(tables))
    if not tables: out["etat"] = "sans_tables"
    if not e: return out
    s = e.get("siege") or "S"; signe = 1 if camp(s) == "NS" else -1
    c, decl = e.get("contrat") or "passe", e.get("declarant")
    lev = e.get("levees")
    ns = score_ns(d, c, decl, lev) if c != "passe" else 0
    out.update(siege=s, camp=camp(s), contrat=c, declarant=decl if c != "passe" else None, levees=lev,
               resultat=resultat(c, lev) if c != "passe" else "", score=signe * ns, date=e.get("date"))
    if not tables: return out
    out["etat"] = "rejouee"
    if marque == "IMP":
        out["imp"] = signe * imp(ns - datum(tables)); out["pct"] = None
    else:
        p = pct_face(tables, ns); out["pct"] = p if signe == 1 else round(100 - p, 2); out["imp"] = None
    m = max(tables, key=lambda t: signe * (t.get("score_ns") or 0))
    out["meilleur"] = dict(contrat=m.get("contrat", ""), declarant=m.get("declarant", ""), resultat=m.get("resultat", ""),
                           score=signe * (m.get("score_ns") or 0))
    return out


def resultats_paires(data, marque):
    """Les paires de la séance : {clé: {"nom", "valeur", "donnes"}} ; valeur = leur % officiel (match-points) ou leurs
    IMP par donne (IMP). Calculé des tables quand la séance ne garde pas le total officiel."""
    pcts, imps = {}, {}
    for d in data.get("donnes") or []:
        for t in d.get("tables") or []:
            for k, sg in ((t.get("paire_ns"), 1), (t.get("paire_eo"), -1)):
                if k in (None, ""): continue
                k = str(k)
                if t.get("pct_ns") is not None: pcts.setdefault(k, []).append(t["pct_ns"] if sg == 1 else 100 - t["pct_ns"])
                if t.get("imp_ns") is not None: imps.setdefault(k, []).append(sg * t["imp_ns"])
    out = {}
    for k in sorted(set(pcts) | set(imps) | set(map(str, data.get("paires") or {}))):
        p = (data.get("paires") or {}).get(k) or {}
        nom = p.get("nom") or "/".join(j.get("initiales", "") for j in (data.get("joueurs") or {}).get(k, [])) or k
        if marque == "IMP":
            n = len(imps.get(k, []))
            total = p.get("imp") if p.get("imp") is not None else sum(imps.get(k, []))
            v = total / n if n else None
        else:
            v = p.get("pct") if p.get("pct") is not None else (sum(pcts[k]) / len(pcts[k]) if pcts.get(k) else None)
            n = len(pcts.get(k, []))
        if v is not None: out[k] = dict(nom=nom, valeur=v, donnes=n)
    return out


def classement(data, essais):
    """Le tableau de bord du tournoi rejoué. essais : le contenu de <séance>-jeu.json (jouer.lire_essais).
    {"marque", "lignes" (toutes les donnes, par numéro), "rejouees", "a_compter" (donnes avec des tables), "total"
    (% moyen, ou somme des IMP), "par_donne" (IMP par donne), "rang", "ex_aequo", "nb_paires", "paires" (le
    classement : [{nom, valeur, vous}] du meilleur au moins bon, vous à votre place), "complet"}."""
    marque = moi.marque(data)
    par_n = (essais or {}).get("donnes") or {}
    donnes = sorted((d for d in data.get("donnes") or [] if not d.get("a_completer")), key=lambda d: d["n"])
    lignes = [ligne_donne(d, dernier_fini(par_n.get(str(d["n"]))), marque) for d in donnes]
    faites = [x for x in lignes if x["etat"] == "rejouee"]
    a_compter = sum(1 for x in lignes if x["etat"] != "sans_tables")
    out = dict(marque=marque, lignes=lignes, rejouees=len(faites), a_compter=a_compter,
               complet=bool(faites) and len(faites) == a_compter, total=None, par_donne=None, rang=None, ex_aequo=False,
               nb_paires=0, paires=[])
    if not faites: return out
    if marque == "IMP":
        out["total"] = sum(x["imp"] for x in faites); vous = out["par_donne"] = out["total"] / len(faites)
    else:
        vous = out["total"] = sum(x["pct"] for x in faites) / len(faites)
    autres = resultats_paires(data, marque)
    out["nb_paires"] = len(autres)
    if autres:
        out["rang"] = 1 + sum(1 for p in autres.values() if p["valeur"] > vous + 1e-9)
        out["ex_aequo"] = any(abs(p["valeur"] - vous) <= 1e-9 for p in autres.values())
        mes = moi.paires(data)
        liste = [dict(nom=p["nom"], valeur=p["valeur"], vous=False, la_votre=k in mes) for k, p in autres.items()]
        liste.append(dict(nom="Vous", valeur=vous, vous=True, la_votre=False))
        out["paires"] = sorted(liste, key=lambda p: (-p["valeur"], not p["vous"]))
    return out


# ---------------------------------------------------------------- en texte
def fr(x, dec=1):
    """54.25 -> « 54,3 »."""
    return f"{x:.{dec}f}".replace(".", ",")


def rang_txt(r, ex_aequo=False):
    return f"{r}{'er' if r == 1 else 'e'}{' ex aequo' if ex_aequo else ''}"


def ligne_seance(cl):
    """« Vous : 54,2 % — 3e sur 11 paires » (ou « Vous : +12 IMP (+0,5 par donne) — … »), "" sans donne rejouée."""
    if not cl["rejouees"]: return ""
    if cl["marque"] == "IMP":
        t = f"Vous : {cl['total']:+d} IMP ({'+' if cl['par_donne'] >= 0 else '−'}{fr(abs(cl['par_donne']), 2)} par donne)"
    else:
        t = f"Vous : {fr(cl['total'])} %"
    if cl["rang"]: t += f" — {rang_txt(cl['rang'], cl['ex_aequo'])} sur {cl['nb_paires']} paires"
    return t.replace("-", "−") if cl["marque"] == "IMP" and cl["total"] < 0 else t
