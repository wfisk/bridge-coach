# -*- coding: utf-8 -*-
"""Banc de la défense, face à notre déclarant simulé (lignes.py, qui ne voit pas les mains cachées) : la défense contre
un déclarant au double mort (essai_modele.banc_defense) ne peut montrer ni la valeur des signaux ni celle d'une défense
qui trompe ; celui-ci le peut. Mêmes donnes au hasard, mêmes enchères du moteur, mêmes tirages : chaque variante de la
défense joue la même donne contre le même déclarant.

    .venv/bin/python -I -X utf8 src/essai_defense.py 200 [graine] [variantes…]

Variantes : sans (ni signal ni demande suivie), signaux (carte.SIGNAUX), modele = base (signaux et le modèle des mains
cachées, carte.MODELE), puis chacun des ajouts du 2026-11-11 sur la base : habitudes (carte.HABITUDES), sequence
(carte.SEQUENCE et modele.LIRE_HONNEURS), difficile (carte.MONDES_DIFFICILE), coupe (carte.PREF_COUPE), et tout. On compte les levées du déclarant (moins =
mieux pour la défense) et les chutes, donne par donne, puis l'écart moyen de chaque variante à la première.
"""
import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

NEUF_OFF = {"HABITUDES": False, "SEQUENCE": False, "PREF_COUPE": False, "MONDES_DIFFICILE": 16,
            "modele.LIRE_HONNEURS": False}
VARIANTES = {"sans": dict(NEUF_OFF, SIGNAUX=False, MODELE=False), "signaux": dict(NEUF_OFF, SIGNAUX=True, MODELE=False),
             "modele": dict(NEUF_OFF, SIGNAUX=True, MODELE=True)}
VARIANTES["base"] = VARIANTES["modele"]                    # le réglage du 2026-11-11 (signaux et modèle)
VARIANTES["habitudes"] = dict(VARIANTES["base"], HABITUDES=True)
VARIANTES["sequence"] = dict(VARIANTES["base"], SEQUENCE=True, **{"modele.LIRE_HONNEURS": True})
VARIANTES["menee"] = dict(VARIANTES["base"], SEQUENCE=True)          # mener le haut d'une séquence, sans le lire
VARIANTES["lecture"] = dict(VARIANTES["base"], **{"modele.LIRE_HONNEURS": True})   # lire les honneurs fournis, seulement
VARIANTES["difficile"] = dict(VARIANTES["base"], MONDES_DIFFICILE=48)
VARIANTES["coupe"] = dict(VARIANTES["base"], PREF_COUPE=True)
VARIANTES["tout"] = dict(SIGNAUX=True, MODELE=True, HABITUDES=True, SEQUENCE=True, PREF_COUPE=True,
                         MONDES_DIFFICILE=48, **{"modele.LIRE_HONNEURS": True})


def une(arg):
    """Une donne jouée par les robots avec une variante de la défense : (graine, variante, levées du déclarant, requises)
    ou None (passe générale)."""
    graine, variante = arg
    import carte as C, donnes, encheres
    C.COUPS_A_VENIR = False                                # le banc ne lit pas les pensées
    import modele as M
    for k, v in VARIANTES[variante].items():                # « modele.X » : un réglage du modèle, sinon de carte.py
        setattr(M, k[7:], v) if k.startswith("modele.") else setattr(C, k, v)
    rnd = random.Random(graine)
    d = donnes.donne_complete(graine % 100000 + 1, "Aléatoire", donnes.tirer(rnd), True)
    r = encheres.encherir(d)
    if r["contrat"] == "passe": return None
    p = C.Partie(d, r["contrat"], r["declarant"], r["encheres"], graine=graine)
    while not p.fini():
        s = p.au_trait()
        p.poser(p.indice() if p.camp(s) else p.carte_defense())    # sans écrire les pensées : plus vite
    return graine, variante, p.pos.gagnes, p.besoin


def main():
    from multiprocessing import get_context
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    n = int(args[0]) if args else 50
    graine = int(args[1]) if len(args) > 1 else 11
    variantes = args[2:] or list(VARIANTES)
    travail = [(graine * 100003 + i, v) for i in range(n) for v in variantes]
    with get_context("spawn").Pool(max(1, (os.cpu_count() or 2) - 1)) as pool:
        res = [x for x in pool.imap_unordered(une, travail, chunksize=1) if x]
    par = {}
    for g, v, lev, besoin in res: par.setdefault(g, {})[v] = (lev, besoin)
    complets = {g: x for g, x in par.items() if all(v in x for v in variantes)}
    ref = variantes[0]
    print(f"{len(complets)} donnes jouées (sur {n} tirées), défense contre notre déclarant simulé")
    for v in variantes:
        lev = sum(x[v][0] for x in complets.values()) / len(complets)
        chutes = sum(x[v][0] < x[v][1] for x in complets.values())
        ecarts = [x[ref][0] - x[v][0] for x in complets.values()]           # levées gagnées par la défense sur « ref »
        m = sum(ecarts) / len(ecarts)
        et = (sum((e - m) ** 2 for e in ecarts) / max(1, len(ecarts) - 1)) ** .5 / len(ecarts) ** .5
        print(f"  {v:8} déclarant {lev:5.2f} levées, {chutes} chutes ; défense {m:+.3f} levée par donne face à « {ref} »"
              f" (± {et:.3f}), {sum(e > 0 for e in ecarts)} donnes mieux, {sum(e < 0 for e in ecarts)} moins bien")


if __name__ == "__main__":
    main()
