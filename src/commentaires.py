# -*- coding: utf-8 -*-
"""Commentaire automatique d'une donne, sans analyse rédigée.

Phrases factuelles tirées de la séance (<nom>.bc.json) : meilleur contrat de
chaque camp au double mort, par, contrat et levées de chaque table comparés au
double mort, manche ou chelem manqués, écart entre les tables.
N, S, E, O et N-S, E-O sont écrits en toutes lettres par build_pdf.py.
"""
import re
from bws_extract import score, vul_of

EN = {"SA": "NT", "♠": "S", "♥": "H", "♦": "D", "♣": "C"}
MANCHE = {"SA": 3, "♠": 4, "♥": 4, "♦": 5, "♣": 5}
CAMP = {"NS": "N-S", "EO": "E-O"}
RANG = {"partielle": 0, "manche": 1, "petit chelem": 2, "grand chelem": 3}


def camp(siege): return "NS" if siege in "NS" else "EO"

def pl(n, mot): return f"{n} {mot}{'s' if n > 1 else ''}"

def palier(niveau, st):
    if niveau == 7: return "grand chelem"
    if niveau == 6: return "petit chelem"
    return "manche" if niveau >= MANCHE[st] else "partielle"

def meilleur(d, c):
    """Meilleur contrat non contré gagnant pour le camp c au double mort :
    (score pour ce camp, niveau, couleur, déclarant, levées) ou None."""
    best = None
    for st, par_siege in d["dm"].items():
        for s in ("NS" if c == "NS" else "EO"):
            t = par_siege[s]
            for niveau in range(1, min(t - 6, 7) + 1):   # à score égal, le palier le plus bas…
                v = score(niveau, EN[st], 0, vul_of(d["vul"], "NS" if c == "NS" else "EW"), t)
                if best is None or v > best[0]: best = (v, niveau, st, s, t)
    if best and palier(best[1], best[2]) == "partielle":   # …sauf en partielle : le plus haut qui gagne
        v, niveau, st, s, t = best
        best = (v, min(t - 6, MANCHE[st] - 1), st, s, t)
    return best

def contrat(c):
    """'4♥XX' -> (4, '♥', 2) ; 'passe' -> None"""
    m = re.fullmatch(r"([1-7])(SA|♠|♥|♦|♣)(X{0,2})", c)
    return (int(m[1]), m[2], len(m[3])) if m else None


def commentaire(d):
    if not d.get("dm"): return ""
    out = []
    # 1. Ce que permettent les cartes
    phr = []
    for c in ("NS", "EO"):
        b = meilleur(d, c)
        if b is None:
            phr.append(f"{CAMP[c]} ne gagnent aucun contrat")
        else:
            v, niveau, st, s, t = b
            phr.append(f"{CAMP[c]} peuvent gagner {niveau}{st} par {s} ({pl(t, 'levée')}, {palier(niveau, st)})")
    out.append("<b>Au double mort</b>, " + " ; ".join(phr) + ".")
    if any((b := meilleur(d, c)) and b[1] == 7 for c in ("NS", "EO")):
        out.append("Le grand chelem est rarement demandé : le petit chelem fait déjà un bon score dans la plupart des salles.")
    if not d["tables"]:                                    # donnes créées : personne ne les a jouées
        return "<br/>".join(out)
    if len(d["tables"]) > 2:
        return "<br/>".join(out + resume(d))

    # 2. Chaque table : seulement ce qui mérite d'être relevé (le détail est dans l'annexe)
    calmes = 0
    for t in d["tables"]:
        tete = f"<b>Table {t['table']}</b> ({t['contrat']} par {t['declarant']} {t['resultat']}) : "
        if contrat(t["contrat"]) is None: calmes += 1; continue
        ph = remarques(d, t)
        if ph: out.append(tete + " ; ".join(ph) + ".")
        else: calmes += 1
    if calmes == len(d["tables"]):
        out.append("Aux tables, contrats et levées conformes au double mort.")

    # 3. Comparaison des deux tables
    if len(d["tables"]) == 2:
        a, b = d["tables"]
        imp = abs(a["imp_ns"])
        if imp == 0:
            out.append("Même score aux deux tables : 0 IMP.")
        else:
            g = a if a["imp_ns"] > 0 else b
            meme = a["contrat"] == b["contrat"] and camp(a["declarant"]) == camp(b["declarant"])
            cause = ("même contrat aux deux tables, la différence vient du nombre de levées" if meme
                     else "contrats différents aux deux tables")
            qui = g.get("nom_ns") or g["paire_ns"]
            out.append(f"{imp} IMP pour la paire N-S {qui} (table {g['table']}) : {cause}.")
    return "<br/>".join(out)


def resume(d):
    """À partir de 3 tables : vue d'ensemble plutôt qu'une ligne par table."""
    ts = d["tables"]; n = len(ts); out = []
    # contrats joués, du plus fréquent au plus rare
    freq = {}
    for t in ts:
        c = t["contrat"]; k = c if c == "passe" else f"{c} {CAMP[camp(t['declarant'])]}"
        freq[k] = freq.get(k, 0) + 1
    out.append(f"<b>Contrats joués</b> ({n} tables) : "
               + ", ".join(f"{k} ×{v}" if v > 1 else k for k, v in sorted(freq.items(), key=lambda x: -x[1])) + ".")
    # meilleur contrat de chaque camp : combien de tables l'ont joué
    for cc in ("NS", "EO"):
        b = meilleur(d, cc)
        if b is None or palier(b[1], b[2]) == "partielle": continue
        v, niveau, st, s, tr = b
        ok = sum(1 for t in ts if (c := contrat(t["contrat"])) and camp(t["declarant"]) == cc
                 and c[1] == st and c[0] >= niveau and c[0] <= niveau + (tr - niveau - 6))
        out.append(f"{CAMP[cc]} : {niveau}{st} ({palier(niveau, st)}) atteint à {ok} table{'s' if ok > 1 else ''} sur {n}.")
    # écarts au double mort
    plus = sum(1 for t in ts if t["dm"] is not None and t["levees"] is not None and t["levees"] > t["dm"])
    moins = sum(1 for t in ts if t["dm"] is not None and t["levees"] is not None and t["levees"] < t["dm"])
    if plus or moins:
        out.append(f"Levées : le déclarant a fait moins que le double mort à {moins} table{'s' if moins > 1 else ''}, "
                   f"plus à {plus} (cadeau de la défense).")
    # manches et chelems manqués
    manques = {}
    for t in ts:
        for ph in remarques(d, t):
            if "pouvaient gagner" in ph: manques[ph] = manques.get(ph, 0) + 1
    for ph, k in manques.items():
        out.append(f"{ph[0].upper()}{ph[1:]} : manqué à {k} table{'s' if k > 1 else ''}.")
    # meilleur et moins bon score Nord-Sud
    hi = max(ts, key=lambda t: t["score_ns"]); lo = min(ts, key=lambda t: t["score_ns"])
    if hi["score_ns"] != lo["score_ns"]:
        q = lambda t: f"{t['contrat']} par {t['declarant']} {t['resultat']}, table {t['table']}, {t.get('nom_ns') or t['paire_ns']}"
        out.append(f"Meilleur score N-S : {hi['score_ns']:+d} ({q(hi)}) ; le moins bon : {lo['score_ns']:+d} ({q(lo)}).")
    return out


def remarques(d, t):
    """Ce qui mérite d'être relevé à une table : levées contre le double mort, manche ou chelem manqués."""
    c = contrat(t["contrat"])
    if c is None: return []
    niveau, st, dbl = c
    cd = camp(t["declarant"]); need = niveau + 6
    ph = []
    if t["dm"] is not None:
        ok_dm = t["dm"] >= need
        ecart = t["levees"] - t["dm"]
        if ecart == 0:
            if not ok_dm: ph.append("le contrat chutait cartes vues")
        elif ecart > 0:
            ph.append(f"{pl(ecart, 'levée')} de plus que le double mort ({t['dm']}), cadeau de la défense"
                      + (" ; le contrat chutait cartes vues" if not ok_dm and t['levees'] >= need else ""))
        else:
            ph.append(f"{pl(-ecart, 'levée')} de moins que le double mort ({t['dm']})"
                      + (" ; le contrat gagnait cartes vues" if ok_dm and t['levees'] < need else "")
                      + (" ; il chutait de toute façon cartes vues" if not ok_dm else ""))
    # manche ou chelem manqués, par le déclarant ou par la défense
    for cc in ("NS", "EO"):
        b = meilleur(d, cc)
        if b is None: continue
        v, n2, st2, s2, t2 = b
        obtenu = t["score_ns"] * (1 if cc == "NS" else -1)
        joue = RANG[palier(niveau, st)] if cc == cd else 0
        if v > obtenu and RANG[palier(n2, st2)] > joue and not (n2 == 7 and joue == RANG["petit chelem"]):   # petit chelem joué : prudence admise
            ph.append(f"{CAMP[cc]} pouvaient gagner {n2}{st2} ({palier(n2, st2)}, {v:+d})")
    return ph
