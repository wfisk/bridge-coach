# -*- coding: utf-8 -*-
"""Banc d'essai des enchères : les mêmes donnes tirées au hasard, enchéries deux fois (avant / après un changement),
et chaque séquence qui change jugée au double mort, en IMP pour le camp dont l'enchère change. Un outil de
développeur, lancé à la main (la règle du projet : un changement n'est gardé que s'il gagne sur des donnes neuves).

    .venv/bin/python -I -X utf8 src/outils/banc_encheres.py avant.json 20000 11            # enchérit, garde les contrats
    .venv/bin/python -I -X utf8 src/outils/banc_encheres.py apres.json 20000 11 DIFFERE_PAS_ETABLI=True
    .venv/bin/python -I -X utf8 src/outils/banc_encheres.py --comparer avant.json apres.json

Un drapeau du moteur se change en ajoutant NOM=valeur ; une règle de regles.yaml, en relançant après l'avoir écrite.
"""
import json, multiprocessing, os, random, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # src/ (les outils sont dans src/outils/)
sys.path.insert(1, os.path.dirname(os.path.abspath(__file__)))
RANGS = "AKQJT98765432"
FR = str.maketrans({"K": "R", "Q": "D", "J": "V", "T": "X"})
ROT = "NESO"
VULS = ("Personne", "N-S", "E-O", "Tous")
DRAPEAUX = {}


def donne(graine, n):
    rnd = random.Random(graine * 1_000_003 + n)
    jeu = [c + r for c in "SHDC" for r in RANGS]
    rnd.shuffle(jeu)
    mains = {}
    for i, s in enumerate(ROT):
        m = jeu[13 * i:13 * i + 13]
        mains[s] = " ".join(("".join(sorted((x[1] for x in m if x[0] == c), key=RANGS.index)) or "-").translate(FR) for c in "SHDC")
    return dict(n=n, donneur=ROT[n % 4], vul=VULS[(n // 4 + n) % 4], mains=mains)


def _init(drapeaux):
    import encheres
    for k, v in drapeaux.items(): setattr(encheres, k, v)


def _encherir(arg):
    import encheres
    graine, n = arg
    d = donne(graine, n)
    try:
        r = encheres.encherir(d)
        return n, r["contrat"] or "passe", r["declarant"], r["encheres"]
    except Exception as ex:
        return n, "erreur", None, [str(ex)]


def enchérir(sortie, nb, graine, drapeaux):
    with multiprocessing.Pool(max(1, (os.cpu_count() or 2) - 1), initializer=_init, initargs=(drapeaux,)) as p:
        res = p.map(_encherir, [(graine, n) for n in range(nb)], chunksize=50)
    json.dump(dict(graine=graine, drapeaux={k: repr(v) for k, v in drapeaux.items()},
                   donnes={str(n): [c, d, e] for n, c, d, e in res}), open(sortie, "w"), ensure_ascii=False)
    print(f"{nb} donnes enchéries, {sum(1 for x in res if x[1] == 'erreur')} erreurs : {sortie}")


def imp(x):
    import bws_extract
    return bws_extract.imp(x)


def _juger(arg):
    import classement, donnes as dn
    d, (ca, da, ea), (cb, db, eb) = arg
    dm = dn.double_mort(d["mains"])
    def sc(c, decl):
        if c == "passe": return 0
        return classement.score_ns(d, c, decl, dm[c[1:].rstrip("X")][decl])
    a, b = sc(ca, da), sc(cb, db)
    # le camp dont l'enchère change : le premier qui dit autre chose
    k = next((i for i, (x, y) in enumerate(zip(ea, eb)) if x != y), min(len(ea), len(eb)))
    s = ROT[(ROT.index(d["donneur"]) + k) % 4]
    signe = 1 if s in "NS" else -1
    return d["n"], signe * (b - a), ca, da, cb, db, " ".join(eb[:k + 1])


def comparer(fa, fb, montrer=15):
    A, B = json.load(open(fa)), json.load(open(fb))
    assert A["graine"] == B["graine"], "pas les mêmes donnes"
    diff = [n for n in A["donnes"] if A["donnes"][n][2] != B["donnes"][n][2]]
    args = [(donne(A["graine"], int(n)), A["donnes"][n], B["donnes"][n]) for n in diff]
    with multiprocessing.Pool(max(1, (os.cpu_count() or 2) - 1)) as p:
        res = p.map(_juger, args, chunksize=10)
    imps = [(imp(x), n, x, ca, da, cb, db, seq) for n, x, ca, da, cb, db, seq in res]
    tot = sum(i for i, *_ in imps)
    print(f"{len(A['donnes'])} donnes, {len(diff)} séquences changées : {tot:+d} IMP pour le camp qui change "
          f"({sum(1 for i, *_ in imps if i > 0)} gagnées, {sum(1 for i, *_ in imps if i < 0)} perdues)")
    for i, n, x, ca, da, cb, db, seq in sorted(imps)[:montrer // 2] + sorted(imps)[-(montrer - montrer // 2):]:
        print(f"  {i:+3d} IMP  donne {n:>5} : {ca} {da or ''} -> {cb} {db or ''}   ({seq})")
    return tot


if __name__ == "__main__":
    if sys.argv[1] == "--comparer":
        comparer(sys.argv[2], sys.argv[3])
    else:
        dr = {}
        for x in sys.argv[4:]:
            k, v = x.split("=", 1); dr[k] = eval(v)
        enchérir(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), dr)
