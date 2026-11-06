# -*- coding: utf-8 -*-
"""Positions de manuel pour src/coups.py : .venv/bin/python -I tests/test_coups.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import coups, jeu

FR = str.maketrans("KQJT", "RDVX")


def mains(n, e, s, o):
    return {k: v.translate(FR) for k, v in dict(N=n, E=e, S=s, O=o).items()}


def types(m, den, decl, entame):
    return {(x["type"], x.get("joueur")) for x in coups.analyser(m, den, decl, entame)}


assert ("squeeze", "O") in types(mains("- AQ 32 3", "- - - 98765", "A 3 AQ A", "- KJ KJ 2"), "SA", "S", "♣2")
assert ("mise en main", "O") in types(mains("2 32 - 3", "- - 32 98", "3 AQ - A", "A KJ - 2"), "SA", "S", "♣2")
assert ("laisser-passer", None) in types(mains("543 - - -", "876 - - -", "AJ2 - - -", "KQT - - -"), "SA", "S", "♠R")
assert not types(mains("AK AK AK AK", "32 32 32 32", "QJ QJ QJ QJ", "54 54 54 54"), "SA", "S", "♠5")
# élimination à la table : la dame de carreau se devine, sauf si la défense ouvre la couleur
d = {"n": 1, "donneur": "S", "mains": {"S": "ARX84 A52 AV2 A3", "N": "DV532 73 RX3 R62",
                                       "E": "7 RDV9 D98 V9874", "O": "96 X864 7654 DX5"}}
enc = ["1♠", "passe", "3♠", "passe", "4SA", "passe", "5♥", "passe", "6♠", "passe", "passe", "passe"]
s_d, s_m = jeu.suites(d["mains"]["S"]), jeu.suites(d["mains"]["N"])
cad = jeu.cadre_elimination(s_d, s_m, "S", "N", "♠", "♥R")
assert cad["cle"] == "♦" and cad["eliminer"] == ["♣"] and cad["sorties"] == ["♥"]
assert "Élimination possible" in jeu.plan_de_jeu(d, "6♠", "S", {"joueur": "O", "carte": "♥R"}, enc, simuler=True)
assert jeu.cadre_elimination(s_d, s_m, "S", "N", "SA") is None
# une donne passée à une table, avec un déclarant noté par Bridgemate : pas de coup cherché (rapport.coups_tables)
import rapport
passee = {"n": 17, "mains": d["mains"], "tables": [{"contrat": "passe", "declarant": "N", "entame": ""}]}
assert rapport.coups_tables(passee) == ""
assert jeu.trou("A32", "V86") and not jeu.trou("RD4", "V32") and not jeu.deux_sens("AR2", "DV3")
print("ok")
