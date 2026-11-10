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
# 05/11 donne 28 : Ouest entame ♥A de ARX83 contre 4♠ ; sa seule séquence est la couleur d'entame : la continuer,
# jamais « changer pour l'♥A » qu'il vient de jouer
d28 = dict(n=28, donneur="O", vul="N-S", mains=dict(N="AV3 V74 ARD752 R", E="R97 952 84 VX942", S="DX8642 D6 VX3 A6", O="5 ARX83 96 D8753"))
x = coach.conseil_defense(d28, "4♠", "S", {"joueur": "O", "carte": "♥A"},
                          ["passe", "1♦", "passe", "1♠", "passe", "3♦", "passe", "3♠", "passe", "4♠", "passe", "passe", "passe"])
assert "Changer tout de suite pour l'♥A" not in x and "Continuer ♥" in x, x
# les enchères : une décision serrée du moteur, dite en une phrase
r = {"explications": [("N", "2♦", "19 H : 11+ H, forcing. 2♣ (11+ H, forcing) convenait aussi, mais vient après dans le système")]}
assert coach.conseil_encheres(r) == "Décision serrée (l'autre enchère vient après dans le système) : Nord 2♦ plutôt que 2♣ (11+ H, forcing)."
assert coach.conseil_encheres({"explications": [("N", "passe", "rien")]}) == ""
# l'analyse de l'expert, affichée avec le conseil du coach avant son avis, sur toutes les donnes (un seul passage chez Claude)
import rapport
from build_pdf import MARQUE_AVIS, MARQUE_COACH
grille = [["–", "–", "–", "1♠"], ["passe", "4♠", "passe", "passe"], ["passe", "", "", ""]]   # donneur Sud : 4♠ par Sud
std = {"enc": grille, "entame": {"joueur": "O", "carte": "♦R"}, "plan": "Plan." + MARQUE_COACH + " Coach.", "defense": "Déf."}
exp = {"enc": grille, "entame": {"joueur": "O", "carte": "♦R"}, "plan": "Plan." + MARQUE_AVIS + " Expert.", "defense": "Déf."}
x = rapport.coach_pour_expert(dict(d, donneur="S"), exp, std)
assert x["plan"] == MARQUE_COACH + " Coach." + MARQUE_AVIS + " Expert." and x["defense"] == "Déf." and exp["plan"].endswith("Expert.")   # le plan : tout au coach
assert rapport.coach_pour_expert(dict(d, donneur="S"), dict(exp, entame={"joueur": "O", "carte": "♣2"}), std)["enc_coach"] == grille
assert rapport.coach_pour_expert(dict(d, donneur="S"), dict(exp, entame={"joueur": "O", "carte": "♣2"}), std)["plan"].startswith(MARQUE_COACH + " Coach.")
# un autre contrat (ici 3♠) : le coach parle du sien, nommé en tête ; un plan écrit par l'expert lui-même reste tel quel
autre = [["–", "–", "–", "1♠"], ["passe", "3♠", "passe", "passe"], ["passe", "", "", ""]]
y = rapport.coach_pour_expert(dict(d, donneur="S"), dict(exp, enc=autre, plan=MARQUE_AVIS + " Le coach joue 4♠."), std)
assert y["plan"] == MARQUE_COACH + " <i>Pour 4♠ par Sud :</i> Coach." + MARQUE_AVIS + " Le coach joue 4♠.", y["plan"]
assert rapport.coach_pour_expert(dict(d, donneur="S"), dict(exp, enc=autre), std)["plan"] == exp["plan"]
print("ok")
# le % du contrat recommandé, joué face aux tables : celles qu'il bat, plus la moitié de celles qu'il égale
from comparer import pct_face_aux_tables
tabs = [{"score_ns": s} for s in (420, 420, 170, -50)]
assert pct_face_aux_tables(tabs, 420) == 75.0 and pct_face_aux_tables(tabs, 450) == 100.0 and pct_face_aux_tables([], 0) is None
print("ok")
