# -*- coding: utf-8 -*-
"""Couleurs et tri de la page de synthèse : .venv/bin/python -I tests/test_synthese.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from build_pdf import rang_contrat, sens_contrat

N = lambda c: (c, "N"); E = lambda c: (c, "E")
assert sens_contrat(N("4♠"), N("3♠")) == "plus"
assert sens_contrat(N("3♠"), N("4♠")) == "moins"
assert sens_contrat(N("3♠"), N("3♥")) == "plus"                                # même palier : la dénomination
assert sens_contrat(N("3SA"), N("4♣")) == "moins"
assert sens_contrat(("4♠", "S"), N("4♠")) is None                              # même contrat, le partenaire
assert sens_contrat(N("4♠X"), N("4♠")) is None                                 # le contre ne compte pas
assert sens_contrat(E("4♣"), N("3♥")) is None                                  # l'autre camp
assert sens_contrat("passe", N("1♣")) == "moins"
assert sens_contrat(N("1♣"), "passe") == "plus"
assert sorted(["3SA", "4♠X", "passe", "3♣", "4♥", "1♦"], key=rang_contrat) == ["passe", "1♦", "3♣", "3SA", "4♥", "4♠X"]
print("ok")
