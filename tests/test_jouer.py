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
# la place du joueur selon l'option : le déclarant de référence vient du moteur sans analyse
import random
decl = jouer.siege_par_defaut(d, (None, None))
assert decl == jouer.contrat(encheres.encherir(d)["encheres"], d["donneur"])[1]
r = random.Random(1)
assert jouer.siege_choisi("E", d, (None, None), r) == "E" and jouer.siege_choisi("donneur", d, (None, None), r) == "O"
assert jouer.siege_choisi("declarant", d, (None, None), r) == decl
assert all(jouer.siege_choisi("camp", d, (None, None), r) in (decl, jouer.PART[decl]) for _ in range(10))
assert all(jouer.camp(jouer.siege_choisi("defense", d, (None, None), r)) != jouer.camp(decl) for _ in range(10))
assert {jouer.siege_choisi("hasard", d, (None, None), r) for _ in range(40)} == set("NESO")
# les enchères à alerter viennent des règles (alerte: oui) : le texas ne s'alerte pas, le Spoutnik oui
d = dict(n=1, donneur="N", vul="Personne", mains=dict(N="AR5 D83 A92 D862", S="RV752 D84 X63 92", E="D43 R52 RD84 753", O="V98 AV976 V75 AX"))
seq, ex, ind, al = jouer.avancer_alertes(d, [], "S")
seq, ex, ind, al = jouer.avancer_alertes(d, seq + [ind["enchere"]], "N")
assert seq[:3] == ["1SA", "passe", "2♥"] and al == []
d = dict(n=1, donneur="N", vul="Personne", mains=dict(N="A5 R2 AD982 R532", E="RDV96 A85 R4 V96", S="X87 DV64 X53 A84", O="432 X973 V76 DX7"))
seq, ex, ind, al = jouer.avancer_alertes(d, ["1♦", "1♠", "contre"], "N")
assert seq[2] == "contre" and 2 in al, (seq, al)
print("ok")

# 4SA du joueur, une couleur nommée par les deux partenaires : Blackwood 3041, le partenaire répond (donne 17, 12/11/2026)
from encheres import encherir as _encherir
_d = {"n": 17, "donneur": "N", "vul": "Personne",
      "mains": {"N": "752 5 D43 D87642", "E": "X63 AD932 862 AR", "S": "R984 74 VX75 V93", "O": "ADV RVX86 AR9 X5"}}
_r = _encherir(_d, imposees=["passe", "1♥", "passe", "2♦", "passe", "2SA", "passe", "3♥", "passe", "4♥", "passe", "4SA"])
assert _r["encheres"][12:14] == ["passe", "5♠"], _r["encheres"]        # 2 clés avec la dame d'atout, pas passe
_r = _encherir(_d, imposees=["passe", "1♥", "passe", "2♦", "passe", "2SA", "passe", "4SA"])
assert _r["encheres"][8:] == ["passe", "passe", "passe"]                # sans couleur fixée : quantitatif, minimum passe
