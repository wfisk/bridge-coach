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
# le résumé écrit d'une donne jouée jusqu'au bout par le programme
p = carte.Partie(d, "6♦", "N", seq)
while not p.fini(): p.poser(p.indice() if p.camp(p.au_trait()) else p.carte_robot())
tout = [(cc, rr) for pli, _ in p.plis for _x, cc, rr in pli]
res = carte.resume_donne(d, "6♦", "N", "N", tout, p.pensees, p.levees()[0])
assert res[0].startswith("6♦ par Nord") and any(l.startswith("Vos cartes") for l in res)
a = carte.analyse_jeu(d, "6♦", "N", tout)
assert len(a["cartes"]) == 52 and all(z["perte"] >= 0 for z in a["cartes"])
# le plan du déclarant, annoncé avec sa première carte ; les coups à venir dans ses donnes imaginées
p = carte.Partie(d, "6♦", "N", seq, humain=G["N"])
p.poser(p.legales()[0])
while not p.au_joueur() and not p.fini(): p.poser(p.carte_robot())
z = next(z for z in p.pensees if not z["humain"] and z["role"] == "declarant")
assert z["plan"] and "Compte" in z["plan"] and carte.texte_pensee(z, "N")["plan"]
from coups import coups_a_venir
assert isinstance(coups_a_venir(d["mains"], "♦", "N", []), list)
# les habitudes ne départagent que des cartes presque égales dans les mondes ; troisième en main : la plus petite qui suffit
from coups import RANGS
p = carte.Partie(d, "6♦", "N", seq)
p.poser(p.legales()[-1])                                   # le mort (Sud) fournit petit
s = p.au_trait(); leg = p.legales()
assert s == "O" and p.pos.pli[0][0] == "E"
egal = {x: 0 for x in leg}
h = p.habitude(s, leg, egal, egal, leg[-1], 16)
gagne = max((x for x in p.pos.pli if x[1] == p.pos.pli[0][1]), key=lambda x: -RANGS.index(x[2]))
plus = [x for x in leg if x[0] == gagne[1] and RANGS.index(x[1]) < RANGS.index(gagne[2])]
if gagne[0] == "S" and plus: assert h[0] == plus[-1] and h[1].startswith("Troisième"), h
autre = {x: (1 if x == leg[0] else 0) for x in leg}         # une carte fait chuter dans un monde de plus : elle seule compte
h = p.habitude(s, leg, autre, egal, leg[0], 16)
assert h is None or h[0] == leg[0]
print("ok")
