# -*- coding: utf-8 -*-
"""Le conseil du coach : .venv/bin/python -I tests/test_coach.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import coach

# Ouest ouvre 1SA (15–17), Nord-Sud jouent 4♠ ; AD de trèfle au mort (Nord), Sud joue vers la fourchette : l'impasse
# demande le ♣R en Ouest, qui a presque tous les points : « faites-la ».
d = dict(n=1, donneur="O", vul="Personne",
         mains=dict(N="DV4 R73 V52 AD64", E="975 V9842 X87 92", S="AR8632 A5 A43 53", O="X ADX6 RD96 RV87"))
enc = ["1SA", "passe", "passe", "2♠", "passe", "4♠", "passe", "passe", "passe"]
p = coach.conseil_plan(d, "4♠", "S", {"joueur": "O", "carte": "♦R"}, enc)
assert "♣R en Ouest" in p and "faites-la" in p, p
# à la table : la donne réelle des défenseurs ne change rien au conseil (le coach ne voit que Sud, Nord et les enchères)
autre = dict(d, mains=dict(d["mains"], E="X V9842 X87 R92", O="975 ADX6 RD96 V87"))
assert coach.conseil_plan(autre, "4♠", "S", {"joueur": "O", "carte": "♦R"}, enc) == p
# la défense : le compte vu de l'entameur
assert coach.conseil_defense(d, "4♠", "S", {"joueur": "O", "carte": "♦R"}, enc).startswith("Le compte, vu de Ouest")
# les enchères : une décision serrée du moteur, dite en une phrase
r = {"explications": [("N", "2♦", "19 H : 11+ H, forcing. 2♣ (11+ H, forcing) convenait aussi, mais vient après dans le système")]}
assert coach.conseil_encheres(r) == "Décision serrée (l'autre enchère vient après dans le système) : Nord 2♦ plutôt que 2♣ (11+ H, forcing)."
assert coach.conseil_encheres({"explications": [("N", "passe", "rien")]}) == ""
print("ok")
