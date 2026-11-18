# -*- coding: utf-8 -*-
"""La défense à la couleur (encheres.sacrifier) : jugée à la table, sur sa main et les enchères.
    .venv/bin/python -I -X utf8 tests/test_sacrifice.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import encheres as E

def enc(mains, vul, donneur="N"):
    return E.encherir(dict(n=1, donneur=donneur, vul=vul, mains=mains))

# 1. Un manuel : Nord barre à 3♠ (sept piques, deux chicanes), Ouest dit 4♥ ; Sud, non vulnérable contre vulnérables,
#    deux piques et rien en défense : 4♠, et les adversaires le contrent.
M = {"N": "AV98532 - - RVX965", "E": "X6 A932 AR942 A3", "S": "D4 8754 D763 872", "O": "R7 RDVX6 VX85 D4"}
r = enc(M, "E-O")
assert r["encheres"][:8] == ["3♠", "contre", "passe", "4♥", "passe", "passe", "4♠", "contre"], r["encheres"]
assert r["contrat"] == "4♠X" and r["declarant"] == "N"
s, b, texte = r["explications"][6]
assert s == "S" and "défense à la couleur" in texte and "9 atouts" in texte and "−500" in texte and "620" in texte

# 2. Vulnérables contre non vulnérables : jamais. Sud laisse jouer 4♥.
r = enc(M, "N-S")
assert "4♠" not in r["encheres"][4:] or r["contrat"].startswith("4♥"), r["encheres"]
assert not any("défense à la couleur" in t for _, _, t in r["explications"])

# 3. De la défense : AR 2, AD 1,5, A 1, RD 1, Rx 0,5 ; dans notre couleur, l'as seul. Avec ce qu'il faut pour les faire
#    chuter (ici : le seuil relevé), Sud défend.
m = E.Main("A4 AR54 RD63 R72")
assert E.defense_main(m, {"♥"}, "♠") == 1 + 2 + 1 + 0.5
assert E.defense_main(E.Main("D4 8754 D763 872"), {"♥"}, "♠") == 0
avant = E.SACRIFICE_DEF
try:
    E.SACRIFICE_DEF = 3
    r = enc(M, "E-O")
    assert not any("défense à la couleur" in t for _, _, t in r["explications"]), r["explications"]
finally:
    E.SACRIFICE_DEF = avant

# 4. Le prix : valeurs et chutes contrées
assert E.valeur_contrat("4♥", True) == 620 and E.valeur_contrat("4♠", False) == 420 and E.valeur_contrat("5♦", True) == 600
assert E.valeur_contrat("6♥", False) == 980 and E.valeur_contrat("3SA", False) == 400
assert [E.chute_contree(k, False) for k in (1, 2, 3, 4)] == [100, 300, 500, 800]
assert [E.chute_contree(k, True) for k in (1, 2, 3)] == [200, 500, 800]

# 5. Coupé, le sacrifice ne se relève pas : après le contre, personne ne remonte dans la même couleur
for vul in ("E-O", "Personne"):
    r = enc(M, vul)
    ech = [b for b in r["encheres"] if b[0].isdigit()]
    assert len(ech) == len(set(ech))
print("test_sacrifice : ok")
