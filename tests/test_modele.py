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
# les signaux (signaux.py, SEF 2024 p. 84–85 et notre méthode, entames.md) : appel-refus sur l'As ou la Dame (à
# l'atout l'As ou le Roi, le mort a trois petites cartes), préférence sur un singleton du mort, la parité sinon ; en
# défausse la parité, ou l'appel direct (une grosse carte) en urgence
main = "R95 X87 6543 D32"                                  # ♠R95 : on veut que le partenaire continue les piques
assert modele.signal_plausible(main, ("♠", "9"), "appel", "♠", "♥", "♠") == 1.0              # grosse : continuez
assert modele.signal_plausible(main, ("♠", "5"), "appel", "♠", "♥", "♠") == modele.EPS_SIGNAL   # petite : changez ?
assert modele.signal_plausible("V96 X87 6543 D32", ("♠", "6"), "appel", "♠", "♥", "♠") == 1.0   # rien à ♠ : changez
assert modele.signal_plausible(main, ("♦", "6"), "parité", "♦") == 1.0       # quatre carreaux : grosse d'abord
assert modele.signal_plausible(main, ("♦", "3"), "parité", "♦") == modele.EPS_SIGNAL
assert modele.signal_plausible("R5 X87 65432 D32", ("♠", "5"), "appel", "♠", "♥", "♠") == 1.0   # pas le choix : neutre
# défausse : une petite carte refuse la couleur ; une grosse l'appelle (appel direct)
assert modele.signal_plausible("A7 X8 8642 9532", ("♦", "2"), "défausse", "♦", "♥", "♥") == 1.0
assert modele.signal_plausible("A7 X8 AR42 9532", ("♦", "2"), "défausse", "♦", "♥", "♥") == modele.EPS_SIGNAL   # il aime les ♦
assert modele.signal_plausible("A7 X8 AR82 9532", ("♦", "8"), "défausse", "♦", "♥", "♥") == 1.0    # appel direct
assert modele.signal_plausible("A7 X8 9842 9532", ("♦", "8"), "défausse", "♦", "♥", "♥") == modele.EPS_SIGNAL
sv = modele.signaux_vus([("E", "♥3"), ("S", "♥2"), ("O", "♥9"), ("N", "♥A")], "N", "♠")
assert ("O", ("♥", "9"), "parité", "♥", "♥") in sv          # sur une petite carte menée : la parité
sv = modele.signaux_vus([("E", "♥A"), ("S", "♥2"), ("O", "♥9"), ("N", "♥3")], "N", "♠")
assert ("O", ("♥", "9"), "appel", "♥", "♥") in sv            # sur l'As : l'appel-refus
assert not modele.signaux_vus([("E", "♠3"), ("S", "♠2"), ("O", "♠9"), ("N", "♠A")], "N", "♠")   # pas de signal à l'atout
# le module partagé : la même lecture des deux côtés
import signaux
assert signaux.mode_entame("♠", "A", "752") == "appel" and signaux.mode_entame("♠", "A", "7") == "préférence"
assert signaux.mode_entame("♠", "A", "D52") == "parité" and signaux.mode_entame("♠", "5", "752") == "parité"
assert signaux.mode_entame("SA", "D") == "appel" and signaux.mode_entame("SA", "R") == signaux.mode_entame("SA", "4") == "parité"
assert signaux.carte_appel(list("83"), True) == ("8", "appel") and signaux.carte_appel(list("83"), False) == ("3", "refus")
assert signaux.carte_appel(list("52"), True) is None          # pas de grosse carte : rien ne dit « continuez »
assert signaux.carte_preference(list("862"), "♠", ["♠", "♣"]) == ("8", "préférence haute:♠")
assert signaux.carte_preference(list("862"), "♣", ["♠", "♣"]) == ("2", "préférence basse:♣")
assert signaux.lire("8", "appel", "♦", "♥") == {"continuer": True} and signaux.lire("3", "appel", "♦", "♥") == {"continuer": False}
assert signaux.carte_defausse({"♦": list("852")}, ["♠", "♣", "♦"], {"♦": 4}) == (("♦", "5"), "défausse parité paire:♦")
assert signaux.carte_defausse({"♦": list("852")}, ["♠", "♣", "♦"], {"♦": 3}) == (("♦", "2"), "défausse parité impaire:♦")
assert signaux.carte_defausse({"♠": list("82"), "♦": list("52")}, ["♠", "♣", "♦"], {"♠": 3, "♦": 3}, urgence=True) == (("♠", "8"), "défausse appel:♠")
assert signaux.lire("8", "défausse", "♦", "♥", "♥") == {"prefere": "♦"} and signaux.lire("3", "défausse", "♦", "♥", "♥") == {"refuse": "♦"}
# la coupe donnée : haute demande la plus chère des deux autres couleurs hors atout, basse la moins chère
assert signaux.carte_coupe(list("852"), "♠", ["♠", "♣"]) == ("8", "coupe haute:♠")
assert signaux.carte_coupe(list("852"), "♣", ["♠", "♣"]) == ("2", "coupe basse:♣")
assert signaux.lire("8", "coupe", "♦", "♥", "♦") == {"prefere": "♠"}
# les honneurs : il fournit le plus bas de cartes équivalentes, il mène le plus haut d'une séquence
vues = frozenset()
assert modele.signal_plausible("DV5 X87 6543 D32", ("♠", "D"), "honneur suivi", "♠", "♥", vues) == modele.EPS_HONNEUR
assert modele.signal_plausible("D95 X87 6543 D32", ("♠", "D"), "honneur suivi", "♠", "♥", vues) == 1.0
assert modele.signal_plausible("RD5 X87 6543 D32", ("♠", "D"), "honneur mené", "♠", "♥", vues) == modele.EPS_HONNEUR
assert modele.signal_plausible("R95 X87 6543 D32", ("♠", "R"), "honneur suivi", "♠", "♥", frozenset({("♠", "D"), ("♠", "V")})) == 1.0
assert modele.signal_plausible("RX5 X87 6543 D32", ("♠", "R"), "honneur suivi", "♠", "♥", frozenset({("♠", "D"), ("♠", "V")})) == modele.EPS_HONNEUR
modele.LIRE_HONNEURS = True                                # écrit, éteint par défaut (sans gain au banc)
sv = modele.signaux_vus([("E", "♥3"), ("S", "♥2"), ("O", "♥D"), ("N", "♥A")], "N", "♠")
modele.LIRE_HONNEURS = False
assert ("O", ("♥", "D"), "honneur suivi", "♥", frozenset({("♥", "3"), ("♥", "2")})) in sv
assert modele.phrase_honneur("Ouest", ("♥", "D"), "honneur suivi", frozenset()) == "Ouest a fourni la dame ♥ : il n'a pas le valet ♥."
assert modele.phrase_honneur("Ouest", ("♥", "D"), "honneur suivi", frozenset(), {("♥", "V")}) == ""   # le valet est vu
print("ok")
