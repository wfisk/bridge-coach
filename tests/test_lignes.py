# -*- coding: utf-8 -*-
"""Le déclarant simulé : .venv/bin/python -I tests/test_lignes.py"""
import os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import lignes
from coups import Position

enc = ["1SA", "passe", "3SA", "passe", "passe", "passe"]
d = {"n": 1, "donneur": "S", "mains": {"S": "AR5 AD3 A92 D862", "N": "D43 R52 RD84 753",
                                       "O": "V9872 V8 X63 AV9", "E": "X6 X9764 V75 RX4"}}
entame = {"joueur": "O", "carte": "♠7"}
a = lignes.analyser(d, "3SA", "S", entame, enc, n=6, k=6)
assert a and 0 <= a["taux"] <= 1 and a["n"] == 6
# à la table : changer les mains adverses de la donne ne change rien à l'analyse
autre = dict(d, mains=dict(d["mains"], E="V9872 V8 X63 AV9", O="X6 X9764 V75 RX4"))
b = lignes.analyser(autre, "3SA", "S", entame, enc, n=6, k=6)
assert (a["taux"], a["levees"], a["rang"]) == (b["taux"], b["levees"], b["rang"])
# les mondes respectent les défausses et les cartes jouées
p = Position(d["mains"], "SA", "S"); p.sieges = []
for c, r in (("♠", "7"), ("♠", "3"), ("♠", "T"), ("♠", "A")):
    p.sieges.append(p.au_trait()); p.jouer(c, r)
for m in lignes._mondes(p, [], {"O": {"H"}, "E": set()}, 6, random.Random(1)):
    assert "7" in m["O"].split()[0] and m["O"].split()[1] == "-" and "X" in m["E"].split()[0]
# ce que rend l'analyse pour le plan
assert set(a) >= {"ligne", "decide", "impasses", "coupes_avant"} and "Essai à la table" in lignes.phrase(a)
# une impasse : ♠2 de S, ♠5 d'O, ♠D de N, S garde A et R manque ; pas d'impasse si N met l'as
nous = {"S": {"S2"}, "N": {"SA", "SQ"}}
vu = {"SA", "SQ", "S2", "S5"}
assert lignes._geste([("S", "S", "2"), ("O", "S", "5"), ("N", "S", "Q"), ("E", "S", "6")], "N", {"3e": nous["N"], "vu": vu}, "S", None)[2] == "impasse"
assert lignes._geste([("S", "S", "2"), ("O", "S", "5"), ("N", "S", "A"), ("E", "S", "6")], "N", {"3e": nous["N"], "vu": vu}, "S", None)[2] == "tire"
# la coupe : la 3e main coupe une couleur qui n'est pas l'atout
assert lignes._geste([("S", "H", "2"), ("O", "H", "5"), ("N", "S", "3"), ("E", "H", "6")], "N", {"3e": set(), "vu": vu}, "S", "S")[2] == "coupe"
# le partage ou l'honneur qui décide : ici le contrat ne gagne que si O a l'as de cœur
essais = [dict(d["mains"], O="V9872 V8 X63 AV9" if i % 2 else "V9872 V8 X63 RV9") for i in range(20)]
assert any("♣A en O 100 %, en E 0 %" in x for _, x in lignes._decide(essais, [i % 2 == 1 for i in range(20)], "S", d["mains"]))
# les perdantes : R V contre A et D dehors, deux levées ; R D V contre l'as, une seule
import jeu
assert len(jeu.tours_adverses("RVX752", "864", 6)) == 2 and len(jeu.tours_adverses("RDV75", "864", 5)) == 1
# la double impasse : sans le dix, il faut les deux honneurs du bon côté
av = jeu.impasses(("N", {"♦": "84"}), ("S", {"♦": "AV5"}), "♦")[0][0]
assert "le ♦R et la ♦D" in av
assert "le ♦R ou la ♦D" in jeu.impasses(("N", {"♦": "84"}), ("S", {"♦": "AVX5"}), "♦")[0][0]
# les enchères artificielles ne nomment pas de couleur (donneur Nord, Est et Ouest passent)
nom = lambda *e: jeu.couleurs_nommees([x for b in e for x in (b, "passe")], "N")
assert nom("1SA", "2♣", "2♦", "2SA")["N"] == [] and nom("1SA", "2♣", "2♦", "2SA")["S"] == []          # Stayman et réponse
assert nom("1SA", "2♦", "2♥")["S"] == []                                                             # texas
assert nom("2♣", "2♦", "2♥")["N"] == ["♥"] and nom("2♣", "2♦", "2♥")["S"] == []                      # 2♣ fort et relais
assert nom("1♦", "1♥", "1♠", "2♣")["S"] == ["♥"]                                                     # quatrième couleur
# une impasse exige une petite carte pour jouer vers la fourchette ; pas de 3-0 coûteux sans raison
assert not jeu.impasses(("N", {"♥": "R"}), ("S", {"♥": "ADX863"}), "♥")
# le nombre de processus : 8 Go laissent 5 processus au plus ; un petit PC reste à un cœur libre
assert lignes.nb_processus(8, 8) == 5 and lignes.nb_processus(4, 16) == 3 and lignes.nb_processus(12, 32) == 6 and lignes.nb_processus(2, 4) == 1
# l'honneur entamé prend notre carte maîtresse : 62 face à AX8, entame ♠R, on perd encore un pique
d = dict(n=1, donneur="N", vul="Personne", mains=dict(N="62 V765 AX5 R876", E="RDV93 R3 R64 D52", S="AX8 AD98 DV82 X4", O="754 X42 973 AV93"))
p = jeu.plan_de_jeu(d, "3♥", "N", {"joueur": "E", "carte": "♠R"}, ["1♥", "passe", "3♥", "passe", "passe", "passe"], simuler=False, verdict=False)
assert "le ♠V, le ♥R" in p
# cue-bid du répondant : 4 atouts et 13+ points, forcing de manche
import encheres
d = dict(n=1, donneur="N", vul="Personne", mains=dict(N="73 AR975 R42 D82", E="ARDV5 3 D85 VX93", S="82 DV64 AV7 AR64", O="X964 X82 X963 75"))
assert encheres.encherir(d)["encheres"][:4] == ["1♥", "1♠", "2♠", "passe"] and encheres.encherir(d)["contrat"] == "4♥"
# contrôles après un fit : le contrôle à trèfle, puis les clés quand tout est contrôlé
d = dict(n=1, donneur="N", vul="Personne", mains=dict(N="AR986 5 RD4 AR32", E="53 RDV94 VX85 95", S="DV74 A632 A93 64", O="X2 X87 762 DVX87"))
r = encheres.encherir(d)
assert r["encheres"][:7] == ["1♠", "passe", "3♠", "passe", "4♣", "passe", "4SA"] and r["contrat"] == "6♠"
# la couleur sautée que personne ne tient : on s'arrête à la manche
m = encheres.Main("DV74 632 AR3 V64")
assert encheres.controle(m, "♦") == 1 and encheres.controle(m, "♥") == 0
assert jeu.couleurs_nommees(["1♠", "passe", "3♠", "passe", "4♣"], "N")["N"] == ["♠"]
assert jeu.couleurs_nommees(["1♠", "passe", "2♠", "passe", "3♥"], "N")["N"] == ["♠"]
# 3SA sans arrêt : 7♦ en N, 16–18 HL, saut à 3♦ malgré l'intervention, puis S demande l'arrêt à pique
d = dict(n=1, donneur="O", vul="E-O", mains=dict(N="AR6 - ADV6532 953", E="V X54 X874 VX842", S="7543 AD863 R AR7", O="DX982 RV972 9 D6"))
assert encheres.encherir(d)["encheres"][:8] == ["passe", "1♦", "passe", "1♥", "1♠", "3♦", "passe", "3♠"]
# une septième carte maîtresse vaut plus que deux points à SA : N accepte l'invitation quantitative
import donnes
x = donnes.lire_texte("P AR6 C K ADV6532 T 953 / P V C X54 K X874 T VX842 / P 7543 C AD863 K R T AR7 / NV O")
assert encheres.encherir(dict(n=1, mains=x["mains"], vul=x["vul"], donneur=x["donneur"]))["contrat"] == "6SA"
print("ok")
