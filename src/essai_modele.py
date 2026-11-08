# -*- coding: utf-8 -*-
"""Banc d'essai du modèle des mains cachées (modele.py) : .venv/bin/python -I src/essai_modele.py [donnes] [graine]

Des donnes tirées au hasard ; les enchères du moteur ; le jeu de la carte joué au hasard parmi les cartes légales
(seules comptent ici les cartes vues et les chicanes). À quatre moments (après les enchères, après l'entame,
après 3 et 6 plis) et de deux places (le déclarant, le défenseur à sa gauche), on compare la prédiction à la
vraie donne :
  honneurs : score de Brier de la place de chaque A R D V X 9 inconnu (0 parfait ; plus bas = mieux) ;
  longueurs : écart moyen entre la longueur attendue et la vraie (cartes) ;
  points : écart moyen entre les points H attendus et les vrais.
Trois versions : « hasard » (aucune information), « filtre » (le préfiltre seul, comme les simulations actuelles)
et « modèle » (enchères refaites par le moteur, entame)."""
import os, random, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import carte, encheres, jouer
from jeu import COULEURS, ORDRE, ROT, PTS, LHO, PART
from modele import Modele, SUIVIS

VULS = ["Personne", "N-S", "E-O", "Tous"]


def donne_au_hasard(rnd, n):
    paquet = [(c, r) for c in COULEURS for r in ORDRE]; rnd.shuffle(paquet)
    mains = {x: " ".join("".join(sorted((r for c, r in paquet[13 * i:13 * i + 13] if c == k), key=ORDRE.index)) or "-"
                         for k in COULEURS) for i, x in enumerate(ROT)}
    return dict(n=n, donneur=ROT[n % 4], vul=VULS[n % 4], mains=mains)


def jouer_au_hasard(d, contrat, decl, seq, plis, rnd):
    """Les cartes jouées [(siège, « ♠A »)] après plis plis (l'entame par la règle, puis au hasard)."""
    p = carte.Partie(d, contrat, decl, seq)
    while len(p.plis) < plis and not p.fini(): p.poser(rnd.choice(p.legales()))
    tout = [x for pli, _ in p.plis for x in pli] + list(p.pos.pli)
    return [(s, c + r.translate(carte.FR)) for s, c, r in tout]


def scores(m, d):
    p = m.prediction(); b = lo = h = 0.0; nb = nl = nh = 0
    vus = set().union(*[{(c, r) for c, x in zip(COULEURS, d["mains"][s].split()) if x != "-" for r in x} for s in m.vus])
    vus |= {(c, r.replace("10", "X")) for _, c_ in m.jouees for c, r in [(c_[0], c_[1:])]}
    for c in COULEURS:
        for r in SUIVIS:
            if (c, r) in vus: continue
            for x in m.caches:
                y = 1.0 if r in d["mains"][x].split()[COULEURS.index(c)] else 0.0
                b += (p[x]["cartes"].get((c, r), 0) - y) ** 2
            nb += 1
    for x in m.caches:
        s = dict(zip(COULEURS, d["mains"][x].split()))
        for c in COULEURS:
            vrai = 0 if s[c] == "-" else len(s[c]); lo += abs(p[x]["L"][c][0] - vrai); nl += 1
        h += abs(p[x]["H"][0] - sum(PTS.get(r, 0) for c in COULEURS for r in s[c] if s[c] != "-")); nh += 1
    return dict(honneurs=b / max(nb, 1), longueurs=lo / nl, points=h / nh, efficace=p["efficace"])


VERSIONS = {"hasard": dict(eps_enchere=1, eps_entame=1, prefiltre=False),
            "filtre": dict(eps_enchere=1, eps_entame=1, prefiltre=True),
            "modèle": dict()}


def banc(n_donnes=40, graine=7, n=300, versions=VERSIONS, moments=(0, 1, 3, 6), places=("decl", "def")):
    rnd = random.Random(graine); res = {}; t0 = time.time()
    k = 0
    while k < n_donnes:
        d = donne_au_hasard(rnd, rnd.randrange(10 ** 6))
        r = encheres.encherir(d)
        if r["contrat"] == "passe": continue
        k += 1; seq, c, decl = r["encheres"], r["contrat"], r["declarant"]
        for plis in moments:
            jouees = [] if plis == 0 else jouer_au_hasard(d, c, decl, seq, plis if plis > 1 else 0, random.Random(k))
            if plis == 1: jouees = jouees[:1]                       # l'entame seule
            for place in places:
                obs = decl if place == "decl" else LHO[decl]
                mort = PART[decl] if jouees else None
                for v, opt in versions.items():
                    m = Modele(d, obs, seq, jouees, mort=mort, n=n, graine=k, **opt)
                    s = scores(m, d)
                    for q, val in s.items():
                        res.setdefault((v, plis, place, q), []).append(val)
    moy = {kk: sum(v) / len(v) for kk, v in res.items()}
    return moy, time.time() - t0


def afficher(moy, versions=VERSIONS, moments=(0, 1, 3, 6), places=("decl", "def")):
    noms = {0: "enchères", 1: "entame", 3: "3 plis", 6: "6 plis"}
    for q in ("honneurs", "longueurs", "points"):
        print(f"\n{q}")
        print("moment     place  " + "  ".join(f"{v:>8}" for v in versions))
        for plis in moments:
            for place in places:
                print(f"{noms[plis]:<10} {place:<5}  " + "  ".join(f"{moy[(v, plis, place, q)]:8.3f}" for v in versions))
    print("\ndonnes efficaces (modèle) :", " ".join(f"{noms[p]} {moy[('modèle', p, 'decl', 'efficace')]:.0f}" for p in moments))


if __name__ == "__main__":
    nd = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    g = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    moy, t = banc(nd, g)
    afficher(moy)
    print(f"\n{nd} donnes, {t:.0f} s")


def banc_reel(chemins, n=300, versions=VERSIONS):
    """Les vraies enchères et entames des tables (séances .bws) : après les enchères et après l'entame, du déclarant
    et du défenseur à sa gauche. Les joueurs y suivent moins bien le système que le moteur."""
    import json
    res = {}; k = 0
    for f in chemins:
        for d in json.load(open(f, encoding="utf-8"))["donnes"]:
            for t in d["tables"]:
                seq = t.get("encheres") or []
                if not seq or not t.get("entame") or t["contrat"] == "passe" or not jouer.fin(seq): continue
                c, decl = jouer.contrat(seq, d["donneur"])
                if decl != t["declarant"]: continue
                k += 1
                for plis, jouees in ((0, []), (1, [(LHO[decl], t["entame"])])):
                    for place in ("decl", "def"):
                        obs = decl if place == "decl" else LHO[decl]
                        for v, opt in versions.items():
                            m = Modele(d, obs, seq, jouees, mort=PART[decl] if jouees else None, n=n, graine=k, **opt)
                            for q, val in scores(m, d).items(): res.setdefault((v, plis, place, q), []).append(val)
    return {kk: sum(v) / len(v) for kk, v in res.items()}, k


def _une_defense(arg):
    """Une donne jouée jusqu'au bout : le déclarant au double mort (il voit tout), la défense par carte_defense,
    avec ou sans le modèle. Les levées du déclarant."""
    graine, avec = arg
    import carte as C
    C.MODELE = avec
    rnd = random.Random(graine)
    while True:
        d = donne_au_hasard(rnd, rnd.randrange(10 ** 6))
        r = encheres.encherir(d)
        if r["contrat"] != "passe": break
    p = C.Partie(d, r["contrat"], r["declarant"], r["encheres"], graine=graine)
    lettre = dict(zip("SHDC", COULEURS))
    while not p.fini():
        if p.camp(p.au_trait()):
            v = p.pos.valeurs()
            c, rg = max(v, key=v.get)
            p.poser((lettre.get(c, c), rg))
        else:
            p.poser(p.carte_defense())
    return p.levees()[0], int(r["contrat"][0]) + 6


def banc_defense(n_donnes=24, graine=3):
    """Le modèle rend-il la défense meilleure ? Mêmes donnes, déclarant parfait ; levées du déclarant (moins = mieux)."""
    from multiprocessing import Pool
    args = [(graine * 1000 + i, avec) for i in range(n_donnes) for avec in (False, True)]
    with Pool(max(1, (os.cpu_count() or 2) - 1)) as pool:
        res = pool.map(_une_defense, args)
    sans = [res[i] for i in range(0, len(res), 2)]; avec = [res[i] for i in range(1, len(res), 2)]
    lev = lambda xs: sum(t for t, _ in xs) / len(xs)
    chutes = lambda xs: sum(t < b for t, b in xs)
    return dict(sans=lev(sans), avec=lev(avec), chutes_sans=chutes(sans), chutes_avec=chutes(avec), n=n_donnes)
