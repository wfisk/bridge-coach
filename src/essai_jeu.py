# -*- coding: utf-8 -*-
"""Banc d'essai du déclarant simulé :
    .venv/bin/python -I src/essai_jeu.py <nom>.bc.json <analyse.json> [k]
    .venv/bin/python -I src/essai_jeu.py --aleatoire <nombre de donnes> [graine]

Chaque contrat est joué sur la donne réelle par le déclarant simulé (lignes.py), qui ne la voit pas, et
comparé au double mort. --aleatoire : donnes nouvelles, enchères du moteur, entame aux règles, et le taux
annoncé par analyser() comparé au résultat réel. À relancer après tout changement de lignes.py.
"""
import json, sys, os, random
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def un(arg):
    import lignes, jeu
    from comparer import final, sequence
    from coups import EN, Position
    d, a, k = arg
    c, decl, dbl = final(a["enc"], d["donneur"])
    if c == "passe" or not a.get("entame"): return None
    seq = sequence(a["enc"], d["donneur"]); e = a["entame"]
    den = c[1:]; lead = (e["carte"][0], e["carte"][1:].translate(EN)); need = int(c[0]) + 6
    pool = jeu.donnes_du_declarant(d, decl, seq, e["carte"], 150)
    p = Position(d["mains"], den, decl); p.jouer(*lead); dm = max(p.valeurs().values())   # le mort joue : son meilleur choix
    lev = [lignes.jouer(d["mains"], den, decl, lead, pool, need, k, random.Random(i))[0] for i in range(3)]
    return dict(n=d["n"], c=c, decl=decl, need=need, dm=dm, lev=sum(lev) / 3, gagne=sum(x >= need for x in lev) / 3)


def frais(arg):
    """Une donne nouvelle : le taux annoncé, puis le déclarant simulé sur la donne elle-même."""
    import lignes, jeu
    from coups import EN, Position
    from encheres import encherir
    i, graine = arg
    rnd = random.Random(graine + i)
    cartes = [c + r for c in jeu.COULEURS for r in jeu.ORDRE]
    rnd.shuffle(cartes)
    mains = {s: " ".join("".join(sorted((x[1:] for x in cartes[13 * k:13 * k + 13] if x[0] == c), key=jeu.ORDRE.index)) or "-" for c in jeu.COULEURS)
             for k, s in enumerate("NESO")}
    d = dict(n=i + 1, donneur="NESO"[i % 4], mains=mains)
    r = encherir(d); c, decl = r["contrat"], r["declarant"]
    if c == "passe": return None
    e = jeu.entame_et_defense(d, c, decl, r["encheres"])["entame"]
    den = c[1:].rstrip("X"); need = int(c[0]) + 6; lead = (e["carte"][0], e["carte"][1:].translate(EN))
    p = Position(mains, den, decl); p.jouer(*lead); dm = max(p.valeurs().values())
    a = lignes.analyser(d, c, decl, e, r["encheres"])
    if not a: return None
    pool = jeu.donnes_du_declarant(d, decl, r["encheres"], e["carte"], 150)
    lev = [lignes.jouer(mains, den, decl, lead, pool, need, 12, random.Random(j))[0] for j in range(3)]
    return dict(n=i + 1, c=c, decl=decl, need=need, dm=dm, lev=sum(lev) / 3, gagne=sum(x >= need for x in lev) / 3, taux=a["taux"])


def bilan(res):
    n = len(res)
    print(f"{n} contrats : déclarant simulé {sum(x['lev'] for x in res) / n:.2f} levées, double mort {sum(x['dm'] for x in res) / n:.2f}, "
          f"gagnés {sum(x['gagne'] for x in res):.1f} contre {sum(x['dm'] >= x['need'] for x in res)} au double mort, "
          f"dont {sum(x['gagne'] for x in res if x['dm'] >= x['need']):.1f} parmi les faisables")
    for lo, hi in ((0, .25), (.25, .5), (.5, .75), (.75, .9), (.9, 1.01)):
        g = [x for x in res if lo <= x.get("taux", -1) < hi]
        if g: print(f"annoncé {lo:.0%}-{hi:.0%} : {len(g)} donnes, annoncé {sum(x['taux'] for x in g) / len(g):.0%}, réel {sum(x['gagne'] for x in g) / len(g):.0%}")


def main():
    if sys.argv[1] == "--aleatoire":
        graine = int(sys.argv[3]) if len(sys.argv) > 3 else 90000
        with Pool(6) as p:
            return bilan([x for x in p.map(frais, [(i, graine) for i in range(int(sys.argv[2]))]) if x])
    data = json.load(open(sys.argv[1])); an = json.load(open(sys.argv[2]))["donnes"]; k = int(sys.argv[3]) if len(sys.argv) > 3 else 12
    with Pool(6) as p:
        res = [x for x in p.map(un, [(d, an[str(d["n"])], k) for d in data["donnes"]]) if x]
    for x in res:
        print(f"{x['n']:2} {x['c']:4} {x['decl']} simulé {x['lev']:4.1f}, double mort {x['dm']}, il en faut {x['need']}")
    bilan(res)


if __name__ == "__main__":
    main()
