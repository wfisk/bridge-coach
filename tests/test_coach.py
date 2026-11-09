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
assert coach.conseil_defense(d, "4♠", "S", {"joueur": "O", "carte": "♦R"}, enc).startswith("Ouest compte : le déclarant")
# la course : 07/11 donne 13, Est entame ♣A de AR82 contre 4♥ ; le mort (Sud) a ♣DV et quatre piques 8532 : pas de 3e trèfle,
# et passer au ♦R (RD8432) avant que les piques ne donnent une défausse
d13 = dict(n=13, donneur="N", vul="Personne", mains=dict(N="AD6 RV963 A7 764", E="97 8 RD8432 AR82", S="8532 ADX72 95 DV", O="RVX4 54 VX6 X953"))
x = coach.conseil_defense(d13, "4♥", "N", {"joueur": "E", "carte": "♣A"}, ["1♥", "2♦", "3♥", "passe", "4♥", "passe", "passe", "passe"])
assert "ne pas jouer un troisième ♣" in x and "le ♦R" in x, x
# les enchères : une décision serrée du moteur, dite en une phrase
r = {"explications": [("N", "2♦", "19 H : 11+ H, forcing. 2♣ (11+ H, forcing) convenait aussi, mais vient après dans le système")]}
assert coach.conseil_encheres(r) == "Décision serrée (l'autre enchère vient après dans le système) : Nord 2♦ plutôt que 2♣ (11+ H, forcing)."
assert coach.conseil_encheres({"explications": [("N", "passe", "rien")]}) == ""
# l'analyse de l'expert, affichée avec le conseil du coach avant son avis, seulement pour le même contrat et la même entame
import rapport
from build_pdf import MARQUE_AVIS, MARQUE_COACH
grille = [["–", "–", "–", "1♠"], ["passe", "4♠", "passe", "passe"], ["passe", "", "", ""]]   # donneur Sud : 4♠ par Sud
std = {"enc": grille, "entame": {"joueur": "O", "carte": "♦R"}, "plan": "Plan." + MARQUE_COACH + " Coach.", "defense": "Déf."}
exp = {"enc": grille, "entame": {"joueur": "O", "carte": "♦R"}, "plan": "Plan." + MARQUE_AVIS + " Expert.", "defense": "Déf."}
x = rapport.coach_pour_expert(dict(d, donneur="S"), exp, std)
assert x["plan"] == MARQUE_COACH + " Coach." + MARQUE_AVIS + " Expert." and x["defense"] == "Déf." and exp["plan"].endswith("Expert.")   # le plan : tout au coach
assert rapport.coach_pour_expert(dict(d, donneur="S"), dict(exp, entame={"joueur": "O", "carte": "♣2"}), std)["enc_coach"] == grille
assert MARQUE_COACH not in rapport.coach_pour_expert(dict(d, donneur="S"), dict(exp, entame={"joueur": "O", "carte": "♣2"}), std)["plan"]
print("ok")
