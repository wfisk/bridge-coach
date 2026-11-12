# -*- coding: utf-8 -*-
"""La fiche de conventions (Réglages › Votre système) : .venv/bin/python -I -X utf8 tests/test_fiche_conventions.py"""
import os, sys, tempfile
ESSAI = tempfile.mkdtemp()
os.environ["BRIDGE_COACH_DONNEES"] = ESSAI
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import fiche_conventions as F

# chaque ligne part du système de Bridge Coach ; des clés uniques ; les lignes incertaines le disent
assert len(F.LIGNES) == sum(len(l) for _, l in F.MODELE) and F.valeur("systeme") == ("SEF 2024, naturel, 1SA 15–17 H", False)
assert F.LIGNES["entame_petites"][3] and not F.LIGNES["sig_atout"][3]

# les conventions : Oui ou Non, au départ celles de Bridge Coach ; le même choix que Bridge Coach n'est pas gardé
assert len(F.CONV) == len(F.CONVENTIONS) and F.convention("stayman") == (True, False) and F.convention("landy") == (False, False)
F.choisir_convention("landy", True); F.choisir_convention("drury", False); F.choisir_convention("stayman", True)
assert F.convention("landy") == (True, True) and F.convention("drury") == (False, True) and "stayman" not in F.lire()["conventions"]
F.choisir_convention("landy", False); assert F.convention("landy") == (False, False)

# changer une ligne, revenir au système (texte vide ou identique), les noms et les accords
F.changer("systeme", "SEF 2024, 1SA 14–16 H")
assert F.valeur("systeme") == ("SEF 2024, 1SA 14–16 H", True)
F.changer("systeme", "SEF 2024, naturel, 1SA 15–17 H"); assert F.valeur("systeme")[1] is False
F.changer("systeme", "Autre"); F.changer("sig_atout", "  ")
assert F.valeur("sig_atout") == ("Pas de signal", False)
F.changer_entete(joueurs="MARTIN Anne et BERNARD Henri", accords="Landy sur 1SA")
F.tout_remettre()
assert F.valeur("systeme")[1] is False and F.lire()["joueurs"] == "MARTIN Anne et BERNARD Henri" and F.lire()["accords"]
assert F.convention("drury") == (True, False)            # tout remettre : les conventions aussi

# le PDF : écrit dans documents/, lisible, avec les noms et un changement
F.changer("systeme", "SEF 2024, 1SA 14–16 H"); F.choisir_convention("landy", True)
f = F.pdf()
assert f.endswith(os.path.join("documents", "fiche-de-conventions.pdf")) and open(f, "rb").read(4) == b"%PDF"
import pypdfium2
texte = "".join(p.get_textpage().get_text_range() for p in pypdfium2.PdfDocument(f))
assert "MARTIN Anne et BERNARD Henri" in texte and "1SA 14–16 H" in texte and "Landy sur 1SA" in texte and "Oui" in texte
print("ok")
