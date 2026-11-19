# -*- coding: utf-8 -*-
"""Plusieurs systèmes d'enchères : un système bâti sur un autre (« base: »), le système d'une donne, le système actif.
    .venv/bin/python -I -X utf8 tests/test_systemes.py"""
import os, sys, tempfile
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "src"))
import regles, encheres as E
from encheres.main import Main
from outils import banc_encheres

noms = {n: (t, b, p) for n, t, b, p in regles.systemes()}
assert noms["sef-2024"] == ("SEF 2024", "", True) and noms["bridgez"][1:] == ("sef-2024", False)

# un système d'essai bâti sur le SEF : sa section « 1SA » remplace celle du SEF, le reste est hérité
with tempfile.TemporaryDirectory() as d:
    os.symlink(os.path.join(RACINE, "systems", "sef-2024"), os.path.join(d, "sef-2024"))
    os.makedirs(os.path.join(d, "essai"))
    open(os.path.join(d, "essai", "regles.yaml"), "w", encoding="utf-8").write(
        'systeme: essai\ntitre: "Essai"\nbase: sef-2024\n"1SA":\n  - 3SA: { si: "H 10+", montre: "la manche" }\n'
        '  - passe: { montre: "rien" }\n  - exemples:\n      - { main: "AD9 R82 D43 8642", attendu: 3SA }\n')
    s = regles.charger(os.path.join(d, "essai", "regles.yaml"))
    sef = regles.charger(os.path.join(RACINE, "systems", "sef-2024", "regles.yaml"))
    assert s.titre == "Essai" and s.base == "sef-2024" and s.pret and s.verifier() == []
    assert s.choisir("1SA", Main("AV975 R82 V4 863")).enchere == "passe"           # la section de l'essai : pas de texas
    assert sef.choisir("1SA", Main("AV975 R82 V4 863")).enchere == "2♥"            # le SEF : texas
    assert s.choisir("1C", Main("R82 D75 RV73 X52"), position=2).enchere == sef.choisir("1C", Main("R82 D75 RV73 X52"), position=2).enchere

# le système de la donne, sans changer celui du programme ; bridgez (encore vide) enchérit comme le SEF
D = banc_encheres.donne(11, 5)
a = E.encherir(D)
b = E.encherir(dict(D, systeme="bridgez"))
assert a["encheres"] == b["encheres"] and E.systeme_actif() == "sef-2024"
E.choisir_systeme("bridgez")
assert E.systeme_actif() == "bridgez" and os.environ["BRIDGE_COACH_SYSTEME"] == "bridgez"
E.choisir_systeme("sef-2024")
print("ok")
