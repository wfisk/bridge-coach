# -*- coding: utf-8 -*-
"""La fiche de conventions (Réglages › Votre système) : .venv/bin/python -I -X utf8 tests/test_fiche_conventions.py"""
import os, sys, tempfile
ESSAI = tempfile.mkdtemp()
os.environ["BRIDGE_COACH_DONNEES"] = ESSAI
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import fiche_conventions as F

# chaque ligne part du système de Bridge Coach ; des clés uniques ; les lignes incertaines le disent
assert len(F.LIGNES) == sum(len(l) for _, l in F.MODELE) and F.valeur("1sa") == ("15–17 H, régulier", False)
assert F.LIGNES["1sa"][3] and not F.LIGNES["1m"][3]

# changer une ligne, revenir au système (texte vide ou identique), les noms et les accords
F.changer("1sa", "15–17 H, une majeure 5e possible")
assert F.valeur("1sa") == ("15–17 H, une majeure 5e possible", True)
F.changer("1sa", "15–17 H, régulier"); assert F.valeur("1sa")[1] is False
F.changer("1sa", "14–16 H"); F.changer("2sa", "  ")
assert F.valeur("2sa") == ("20–21 H, régulier", False)
F.changer_entete(joueurs="MARTIN Anne et BERNARD Henri", accords="Landy sur 1SA")
F.tout_remettre()
assert F.valeur("1sa")[1] is False and F.lire()["joueurs"] == "MARTIN Anne et BERNARD Henri" and F.lire()["accords"]

# le PDF : écrit dans documents/, lisible, avec les noms et un changement
F.changer("1sa", "14–16 H, régulier")
f = F.pdf()
assert f.endswith(os.path.join("documents", "fiche-de-conventions.pdf")) and open(f, "rb").read(4) == b"%PDF"
import pypdfium2
texte = "".join(p.get_textpage().get_text_range() for p in pypdfium2.PdfDocument(f))
assert "MARTIN Anne et BERNARD Henri" in texte and "14–16 H, régulier" in texte and "Landy sur 1SA" in texte
print("ok")
