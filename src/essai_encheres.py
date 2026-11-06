# -*- coding: utf-8 -*-
"""Essai du moteur d'enchères sur une séance : contrat atteint, double mort, écart au par.

Usage : python3 -I src/essai_encheres.py seances/AAAA-MM/<nom>.bc.json [n° de donne…]
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from encheres import encherir
from bws_extract import score, vul_of, imp

EN = {"SA": "NT", "♠": "S", "♥": "H", "♦": "D", "♣": "C"}


def resultat(d, r):
    """(levées au double mort, score N-S) du contrat atteint."""
    if r["contrat"] == "passe": return None, 0
    c = r["contrat"]; niveau, st, dbl = int(c[0]), c[1:].rstrip("X"), c.count("X")
    t = d["dm"][st][r["declarant"]]
    camp = "NS" if r["declarant"] in "NS" else "EW"
    v = score(niveau, EN[st], dbl, vul_of(d["vul"], camp), t)
    return t, v if camp == "NS" else -v


def main():
    data = json.load(open(sys.argv[1]))
    choix = {int(x) for x in sys.argv[2:]}
    bilan = dict(n=0, gagne=0, par=0, non=0, imp=0)
    for d in data["donnes"]:
        if choix and d["n"] not in choix: continue
        r = encherir(d)
        t, v = resultat(d, r)
        ecart = imp(v - d["par"]["score_ns"]) if d["par"] else imp(v)
        ok = t is None or t >= int(r["contrat"][0]) + 6
        bilan["n"] += 1; bilan["gagne"] += ok; bilan["par"] += ecart == 0
        bilan["non"] += r["statut"] != "complète"; bilan["imp"] += abs(ecart)
        par = f"{d['par']['contrat']} {d['par']['declarant']}" if d["par"] else "passe"
        print(f"Donne {d['n']:2} (donneur {d['donneur']}) : {' '.join(r['encheres'])}")
        print(f"   → {r['contrat']} {r['declarant'] or ''} : {t} levées au double mort, {v:+d} N-S ;"
              f" par {par} ({ecart:+d} IMP){'' if ok else ' CHUTE'}"
              f"{'' if r['statut'] == 'complète' else ' [' + r['statut'] + ']'}")
        if choix:
            for s, b, x in r["explications"]: print(f"      {s} {b:6} {x}")
        for n in r["notes"]: print("      " + n)
    b = bilan
    print(f"\n{b['n']} donnes : {b['gagne']} contrats gagnants au double mort, {b['par']} au par, "
          f"{b['non']} séquences non couvertes, écart moyen au par {b['imp'] / max(b['n'], 1):.1f} IMP")


main()
