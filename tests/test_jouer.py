# -*- coding: utf-8 -*-
"""L'onglet Jouer : le moteur reprend après les enchères du joueur, l'indice, les enchères possibles, la comparaison."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import donnes, encheres, jouer

x = donnes.lire_texte("P AR6 C K ADV6532 T 953 / P V C X54 K X874 T VX842 / P 7543 C AD863 K R T AR7 / NV O")
d = donnes.donne_complete(1, donnes.SAISIE, x["mains"], True, x["donneur"], x["vul"])
# sans enchère imposée, le moteur ne change pas
assert encheres.encherir(d, imposees=[])["encheres"] == encheres.encherir(d)["encheres"]
# Sud parle après passe – 1♦ – passe ; l'indice est l'enchère du système
seq, ex, ind = jouer.avancer(d, [], "S")
assert seq == ["passe", "1♦", "passe"] and ind["enchere"] == "1♥"
# Sud dit 1♠ à la place : Nord continue avec cette enchère, lue dans le fichier de règles
seq, ex, ind = jouer.avancer(d, seq + ["1♠"], "S")
assert seq[3] == "1♠" and ex[3][2].startswith("votre enchère") and ind is not None
# les enchères possibles : rien en dessous de la dernière, pas de surcontre sans contre
ok = jouer.legales(["1♥", "passe"], "N")
assert "1♥" not in ok and "1♠" in ok and "contre" not in ok and "surcontre" not in ok
assert "contre" in jouer.legales(["1♥"], "N")
# jusqu'au bout, puis la comparaison et le contrat
while ind is not None: seq, ex, ind = jouer.avancer(d, seq + [ind["enchere"]], "S")
assert jouer.fin(seq)
c, decl = jouer.contrat(seq, d["donneur"])
r = jouer.comparer(d, seq, "S", (None, None))
assert r["lignes"][0]["nom"] == "Vous" and r["lignes"][0]["texte"] == f"{c} {decl}"
assert jouer.grille(["passe", "1♦"], "O", True) == [["passe", "1♦", "?", ""]]
print("ok")
