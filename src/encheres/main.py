# -*- coding: utf-8 -*-
"""Évaluation d'une main (notation française : "ARX62 A3 AR X842", couleurs ♠ ♥ ♦ ♣)."""

COULEURS = "♠♥♦♣"
HONNEURS = {"A": 4, "R": 3, "D": 2, "V": 1}
MAJEURES = "♠♥"
MINEURES = "♦♣"


class Main:
    def __init__(self, texte):
        parts = texte.split()
        self.cartes = {c: ("" if p == "-" else p) for c, p in zip(COULEURS, parts)}
        self.L = {c: len(self.cartes[c]) for c in COULEURS}
        self.hcp = sum(HONNEURS.get(x, 0) for p in self.cartes.values() for x in p)
        forme = sorted(self.L.values(), reverse=True)
        self.forme = forme
        self.reguliere = forme in ([4, 3, 3, 3], [4, 4, 3, 2], [5, 3, 3, 2])

    @property
    def hl(self):
        """Points H + points de longueur (1 par carte au-delà de la 5e)."""
        return self.hcp + sum(max(0, n - 5) for n in self.L.values())

    def dh(self, atout):
        """Points H + points de distribution avec un fit à `atout` (chicane 3, singleton 2, doubleton 1)."""
        court = sum({0: 3, 1: 2, 2: 1}.get(self.L[c], 0) for c in COULEURS if c != atout)
        return self.hcp + court

    def longue(self, parmi=COULEURS):
        """La plus longue couleur parmi `parmi` (à égalité, la plus haute)."""
        return max(parmi, key=lambda c: (self.L[c], -COULEURS.index(c)))

    def cles(self, atout):
        """Nombre de clés (4 as + roi d'atout) pour le Blackwood 3041."""
        return sum(p.count("A") for p in self.cartes.values()) + ("R" in self.cartes[atout])

    def levees(self):
        """Levées de jeu : par couleur, la longueur moins les perdantes (A, R, D absents parmi les
        trois premières cartes, ou moins si la couleur est plus courte)."""
        n = 0
        for c in COULEURS:
            p, k = self.cartes[c], min(self.L[c], 3)
            n += self.L[c] - sum(h not in p for h in "ARD"[:k])
        return n

    def regle_des_20(self):
        a, b = sorted(self.L.values(), reverse=True)[:2]
        return self.hcp + a + b >= 20
