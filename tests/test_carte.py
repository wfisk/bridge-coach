# -*- coding: utf-8 -*-
"""Le jeu de la carte : entame aux règles, cartes jouables, défense, réclamation, une donne jouée jusqu'au bout."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import carte, donnes, encheres

x = donnes.lire_texte("P AR6 C K ADV6532 T 953 / P V C X54 K X874 T VX842 / P 7543 C AD863 K R T AR7 / NV O")
d = donnes.donne_complete(1, donnes.SAISIE, x["mains"], True, x["donneur"], x["vul"])
seq = encheres.encherir(d)["encheres"]
p = carte.Partie(d, "6♦", "N", seq)
assert p.au_trait() == "S" and p.pos.pli[0][0] == "E"     # Est entame, Sud (le mort) suit
assert all(c == p.pos.pli[0][1] for c, _ in p.legales())  # il faut fournir
try:
    p.poser(("♣", "A")); assert False
except ValueError:
    pass
# la défense joue seule jusqu'au tour du déclarant ; chaque carte posée est jouable
p.poser(p.legales()[0]); p.defendre()
assert p.camp(p.au_trait()) or p.fini()
# une donne entière : le déclarant joue les cartes que proposerait le déclarant simulé
while not p.fini():
    if p.camp(p.au_trait()): p.poser(p.indice())
    else: p.poser(p.carte_defense())
g, ecart, dm = p.resultat()
assert len(p.plis) == 13 and g + p.levees()[1] == 13 and dm == 13
# la réclamation : acceptée seulement si la défense ne peut plus rien
q = carte.Partie(d, "6♦", "N", seq)
assert not q.reclamer() or q.levees()[0] == 13
print("ok")
