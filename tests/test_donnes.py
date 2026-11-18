# -*- coding: utf-8 -*-
"""Les donnes d'entraînement par thème : .venv/bin/python -I -X utf8 tests/test_donnes.py

Un thème de contrat (chelem, manche) garde une donne seulement si le moteur y arrive par une séquence saine et si le
contrat gagne assez souvent à la table, jugé sur des donnes imaginées fidèles aux enchères, jamais sur la seule
répartition réelle."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import donnes as D
import commentaires

# 1. Un chelem qui gagne au double mort sur cette répartition, 5 % du temps à la table, que le moteur ne demande pas
# (1♦ – 1SA – 3SA) : l'ancien test (double mort et 27 H) le gardait, le nouveau non.
d = dict(n=1, donneur="N", vul="Personne",
         mains={"N": "V32 RVX X2 R7632", "E": "RD64 D765 984 54", "S": "A875 9 ARD53 AD9", "O": "X9 A8432 V76 VX8"})
e = D.Essai(d)
assert e.dm["♦"]["N"] == 12 and e.contrat == "3SA"
assert e.taux("6♦", "N") < .2
assert not D.THEMES["Petit chelem"](e) and not D.THEMES["Chelem"](e)

# 2. À la table : la réussite ne dépend pas des mains adverses réelles (mêmes enchères, mains d'Est et Ouest échangées)
seq = e.seq
t1 = D.taux_contrat(d, "3SA", "S", seq)
autre = dict(d, mains=dict(d["mains"], E=d["mains"]["O"], O=d["mains"]["E"]))
assert D.taux_contrat(autre, "3SA", "S", seq) == t1

# 3. Pas d'enchère folle : un petit chelem où il manque deux clés n'est pas sain, même déclaré par le moteur
f = D.Essai(dict(n=1, donneur="N", vul="Personne",
                 mains={"N": "RDV32 R2 R32 R32", "S": "X9876 AD3 D4 AD4", "E": "A54 VX98 A765 76", "O": "- 7654 VX98 VX985"}))
f._enc = dict(encheres=["1♠", "passe", "4SA", "passe", "5♣", "passe", "6♠", "passe", "passe", "passe"], contrat="6♠",
              declarant="N", statut="complète", explications=[])
assert D.cles(f, "N", "♠") == (3, True) and not D.enchere_saine(f, 6)

# 4. Une donne trouvée pour chaque thème de chelem : le contrat du moteur, sain, gagne au moins TAUX à la table ;
# le commentaire le dit, et dit si la répartition réelle le fait chuter
for theme, niveau, cle in (("Petit chelem", 6, "petit"), ("Grand chelem", 7, "grand")):
    n, t, mains, ok, chances = D.chercher((3, theme, 7, 120))
    assert ok and t == theme and chances, theme
    g = D.Essai(dict(n=3, donneur="S", vul=D.VUL16[2], mains=mains))
    assert int(g.contrat[0]) == niveau and D.enchere_saine(g, niveau)
    assert chances["taux"] >= D.TAUX[cle] and chances["contrat"] == g.contrat.rstrip("X") and chances["encheres"] == g.seq
    x = D.donne_complete(n, t, mains, ok, chances=chances)
    assert x["chances"] == chances
    phrase = commentaires.chances(x)
    assert "donnes imaginées" in phrase and ("il gagne" in phrase or "il chute" in phrase)
    assert phrase in commentaires.commentaire(x)

# 5. Une manche en mineure ne garde pas une donne où le chelem, ou 3SA, était aussi un bon pari
n, t, mains, ok, chances = D.chercher((5, "Manche en mineure", 11, 120))
g = D.Essai(dict(n=5, donneur="N", vul=D.VUL16[4], mains=mains))
assert ok and g.contrat.rstrip("X") in ("5♣", "5♦") and chances["taux"] >= D.TAUX["manche"]
assert (g.taux("6" + g.contrat[1], g.decl) or 0) < D.TAUX["petit"]
assert all((g.taux("3SA", s) or 0) < D.TAUX["manche"] for s in (g.decl, D.PART[g.decl]))
print("ok")
