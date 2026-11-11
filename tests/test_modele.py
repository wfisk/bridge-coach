# -*- coding: utf-8 -*-
"""Le modèle des mains cachées : .venv/bin/python -I tests/test_modele.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import encheres, modele
from jeu import COULEURS

d = dict(n=1, donneur="N", vul="Personne",
         mains=dict(N="AR5 D83 A92 D862", E="D43 R52 RD84 753", S="V8 AV976 V75 AX4", O="X9762 X4 X63 RV9"))
seq = encheres.encherir(d)["encheres"]
assert seq[0] == "1SA"
# vu de Sud : l'ouvreur de 1SA a 15–17 H, régulier ; aucune carte de Sud n'est attribuée ailleurs
m = modele.Modele(d, "S", seq, n=200, efficace=60, n_max=600)
p = m.prediction()
moy, bas, haut = p["N"]["H"]
assert 14 <= moy <= 18 and bas >= 13 and haut <= 18, p["N"]["H"]
assert all(p["N"]["L"][c][1].get(0, 0) + p["N"]["L"][c][1].get(1, 0) < .05 for c in COULEURS)   # régulier : pas de courte
assert all(q == 0 or (c, r) not in modele._cartes(d["mains"]["S"]) for x in m.caches for (c, r), q in p[x]["cartes"].items())
# chaque honneur inconnu est quelque part : les probabilités des mains cachées font 1
for c in COULEURS:
    for r in modele.SUIVIS:
        if (c, r) in modele._cartes(d["mains"]["S"]): continue
        assert abs(sum(p[x]["cartes"].get((c, r), 0) for x in m.caches) - 1) < 1e-6, (c, r)
# une chicane montrée : Est ne fournit pas à cœur, il n'a plus de cœur dans aucune donne imaginée
jouees = [("E", "♠3"), ("S", "♠8"), ("O", "♠2"), ("N", "♠A"), ("N", "♥3"), ("E", "♣3"), ("S", "♥A"), ("O", "♥4")]
assert modele.chicanes(jouees)["E"] == {"♥"}
m2 = modele.Modele(d, "N", seq, jouees, mort="S", n=150, efficace=40, n_max=400)
for mains, w in m2.mondes():
    assert mains["E"].split()[1] == "-" and "3" in mains["E"].split()[0] and "3" in mains["E"].split()[3]
# la suite garde les donnes encore possibles, plus vite qu'un modèle neuf
m3 = m2.suite(jouees + [("N", "♦2")])
assert all(mains["S"] == d["mains"]["S"] for mains, _ in m3.mondes())
assert len(modele.Modele(d, "N", seq, jouees, mort="S", n=50, efficace=10, n_max=100).pensees()) == 2
# les signaux (signaux.py) : pair-impair sur l'entame du partenaire, préférence en défausse, parité
main = "R95 X87 6543 D32"                                  # ♠R95 : on veut que le partenaire continue les piques
assert modele.signal_plausible(main, ("♠", "9"), "attitude", "♠", "♥", "♠") == 1.0          # impaire : continuez
assert modele.signal_plausible(main, ("♠", "X"), "attitude", "♠", "♥", "♠") == 1.0          # pas de choix d'impaire ? neutre
assert modele.signal_plausible("R96 X87 6543 D32", ("♠", "6"), "attitude", "♠", "♥", "♠") == modele.EPS_SIGNAL   # paire : changez ?
assert modele.signal_plausible(main, ("♦", "6"), "parité", "♦") == 1.0       # quatre carreaux : grosse d'abord
assert modele.signal_plausible(main, ("♦", "3"), "parité", "♦") == modele.EPS_SIGNAL
assert modele.signal_plausible("R5 X87 65432 D32", ("♠", "5"), "attitude", "♠", "♥", "♠") == 1.0   # pas le choix : neutre
# défausse : ♦8 (haute) refuse les ♦ et demande la plus chère des deux autres hors atout (♠ et ♣, atout ♥ : les ♠)
assert modele.signal_plausible("A7 X8 8642 9532", ("♦", "8"), "défausse", "♦", "♥", "♥") == 1.0
assert modele.signal_plausible("72 X8 8642 A532", ("♦", "8"), "défausse", "♦", "♥", "♥") == modele.EPS_SIGNAL  # l'as est à ♣
sv = modele.signaux_vus([("E", "♥3"), ("S", "♥2"), ("O", "♥9"), ("N", "♥A")], "N", "♠")
assert ("O", ("♥", "9"), "attitude", "♥", "♥") in sv
assert not modele.signaux_vus([("E", "♠3"), ("S", "♠2"), ("O", "♠9"), ("N", "♠A")], "N", "♠")   # pas de signal à l'atout
# le module partagé : la même lecture des deux côtés
import signaux
assert signaux.carte_attitude(list("972"), True) == ("7", "impair")
assert signaux.carte_attitude(list("862"), False, "♠", ["♠", "♣"]) == ("8", "pair haut:♠")
assert signaux.carte_attitude(list("862"), False, "♣", ["♠", "♣"]) == ("2", "pair bas:♣")
assert signaux.lire("8", "attitude", "♦", "♥") == {"continuer": False, "prefere": "♠"}
assert signaux.carte_defausse({"♦": list("852")}, ["♠", "♣", "♦"], "♥", "♥") == (("♦", "8"), "défausse haute:♦:♠")
assert signaux.lire("8", "défausse", "♦", "♥", "♥") == {"refuse": "♦", "prefere": "♠"}
print("ok")
