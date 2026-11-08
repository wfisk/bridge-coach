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
# en défense : le joueur tient un défenseur ; s'il entame, rien n'est encore joué ; le programme joue le déclarant
from jeu import LHO as G, RHO as D_
p = carte.Partie(d, "6♦", "N", seq, humain=G["N"])
assert p.en_defense() and not p.pos.jouees and p.au_joueur() and not p.au_joueur("N") and not p.au_joueur("S")
p.poser(p.legales()[0])
while not p.fini() and not p.au_joueur(): p.poser(p.carte_robot())
assert p.fini() or p.au_trait() == G["N"]
p = carte.Partie(d, "6♦", "N", seq, humain=D_["N"])
assert len(p.pos.jouees) == 1 and not p.au_joueur("E" if D_["N"] == "O" else "O")
# les pensées : chaque carte d'un robot garde ses scores et ce qu'il croit ; le texte se lit ; l'avis sur votre carte
p = carte.Partie(d, "6♦", "N", seq, humain=G["N"])
x = p.legales()[0]; p.pensees.append(p.pensee(p.au_trait(), x, humain=True)); p.poser(x)
while not p.au_joueur() and not p.fini(): p.poser(p.carte_robot())
robot = [z for z in p.pensees if not z["humain"]]
assert robot and all(z["carte"] and isinstance(z["scores"], dict) for z in robot)
t = carte.texte_pensee(robot[0], "N"); assert t["titre"] and (t["raison"] or robot[0]["force"])
cartes = [(c, r) for c, r in [(j[0], j[1:]) for j in []]]
tout = [(cc, rr) for pli, _ in p.plis for _x, cc, rr in pli] + [(cc, rr) for _x, cc, rr in p.pos.pli]
a = carte.avis_programme(d, "6♦", "N", seq, G["N"], tout, 0)
assert a["carte"] and carte.texte_pensee(dict(p.pensees[0], avis=a), "N")["raison"]
print("ok")
