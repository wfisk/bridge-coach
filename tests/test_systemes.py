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

# le système de la donne, sans changer celui du programme ; bridgez (sans quelques conventions) enchérit comme le SEF
# sur une donne où ces conventions ne servent pas
assert noms and regles.charger(os.path.join(RACINE, "systems", "bridgez", "regles.yaml")).sans >= {"Roudi", "Spoutnik"}
D = banc_encheres.donne(11, 5)
a = E.encherir(D)
b = E.encherir(dict(D, systeme="bridgez"))
assert a["encheres"] == b["encheres"] and E.systeme_actif() == "sef-2024", (a["encheres"], b["encheres"])
E.choisir_systeme("bridgez")
assert E.systeme_actif() == "bridgez" and os.environ["BRIDGE_COACH_SYSTEME"] == "bridgez"
E.choisir_systeme("sef-2024")
print("ok")

# un système sans certaines conventions (« sans: ») : leurs règles disparaissent, l'enchère naturelle les remplace ;
# Blackwood et Spoutnik, joués aussi par le code, sont coupés là aussi
with tempfile.TemporaryDirectory() as d:
    os.symlink(os.path.join(RACINE, "systems", "sef-2024"), os.path.join(d, "sef-2024"))
    os.makedirs(os.path.join(d, "simple"))
    open(os.path.join(d, "simple", "regles.yaml"), "w", encoding="utf-8").write(
        'systeme: simple\ntitre: "Simple"\nbase: sef-2024\nsans: [Roudi, Stayman, Spoutnik, Blackwood]\n')
    simple = regles.charger(os.path.join(d, "simple", "regles.yaml"))
assert simple.sans == {"Roudi", "Stayman", "Spoutnik", "Blackwood"} and simple.verifier() == []
assert sef.choisir("1K - 1P - 1SA", Main("RV972 AR2 A9 643")).enchere == "2♣"            # le SEF : Roudi
assert simple.choisir("1K - 1P - 1SA", Main("RV972 AR2 A9 643")).enchere != "2♣"         # sans Roudi : naturel
assert simple.choisir("1SA", Main("AD95 R852 RV4 63")).enchere != "2♣"                    # sans Stayman
E._SYSTEME["simple"] = simple                             # le moteur s'en sert comme d'un dossier de systems/
assert E.convention_active("Blackwood") and not E.encherir(dict(D, systeme="simple")) is None
vus = {"blackwood": False, "spoutnik": False}
for n in range(4000):
    d_ = banc_encheres.donne(13, n)
    natures = [x for x, _nom in E.encherir(d_)["conventions"]]
    for k in vus:
        if k in natures and not vus[k]:
            r = E.encherir(dict(d_, systeme="simple"))
            assert k not in [x for x, _nom in r["conventions"]], (k, r["encheres"])
            vus[k] = True
    if all(vus.values()): break
assert all(vus.values()), vus
print("ok")
