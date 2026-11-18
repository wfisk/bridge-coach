# -*- coding: utf-8 -*-
"""Le nom de la technique dans l'avis du coach (carte.technique), sur des positions d'école : .venv/bin/python -I tests/test_technique.py"""
import os, sys, types
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import carte
from coups import Position
from jeu import PART

MAINS = dict(N="AD4 652 RV R7532", E="R83 R74 A87 DV98", S="752 AD3 DX963 A4", O="VX96 VX98 542 X6")


def position(den, tete, cartes, decl="N", vider=None):
    pos = Position(MAINS, den, decl); pos.tete = tete
    for x, c in (vider or {}).items(): pos.reste[x][c] = ""
    for c, r in cartes: pos.jouer(c, r)
    return types.SimpleNamespace(pos=pos, camp=pos.camp, mort=lambda: PART[decl])


nom = lambda p, coach, mien: (carte.technique(p, coach, mien) or ("",))[0]
# le déblocage : Est prend de l'as, Nord (♦RV) met le roi sous l'as, les carreaux du mort (♦DX96) passeront
assert nom(position("SA", "E", [("♦", "A"), ("♦", "3"), ("♦", "2")]), ("♦", "K"), ("♦", "J")) == "le déblocage"
# l'impasse : le mort mène petit pique vers ♠AD de Nord, le roi n'est pas chez eux
assert nom(position("SA", "S", []), ("♠", "2"), ("♣", "A")) == "l'impasse"
# le laisser-passer à sans-atout : Ouest entame le ♠V, Nord ne prend pas de l'as
assert nom(position("SA", "O", [("♠", "J")]), ("♠", "4"), ("♠", "A")) == "le laisser-passer (hold-up)"
# la coupe : le mort n'a plus de trèfle, Est mène la ♣D
assert nom(position("♥", "E", [("♣", "Q")], vider={"S": "♣"}), ("♥", "3"), ("♦", "3")) == "la coupe"
assert nom(position("♥", "E", [("♣", "Q")], vider={"S": "♣"}), ("♦", "3"), ("♥", "3")) == "la défausse d'une perdante"
# tirer les atouts : le mort mène l'♥A plutôt que l'♣A
assert nom(position("♥", "S", []), ("♥", "A"), ("♣", "A")) == "tirer les atouts"
# aucune règle claire : rien n'est nommé
assert carte.technique(position("SA", "S", []), ("♦", "3"), ("♦", "6")) is None
print("ok")
