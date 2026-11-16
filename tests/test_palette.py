# -*- coding: utf-8 -*-
"""La palette (palette.py) : dix nuances par couleur de base, la base gardée exacte, la même clarté d'une couleur à
l'autre à un même pas, les rôles en variables CSS, et la page de Réglages, Outils de développement."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import palette as p

ech = p.echelles()
for nom, base, *_ in p.BASES:
    e = ech[nom]
    assert list(e) == list(p.PAS) and len(e) == 10
    assert e[p.pas_de_base(base)] == base.lower()                       # la couleur du bridge, exacte
    clartes = [p.oklch(e[k])[0] for k in p.PAS]
    assert clartes == sorted(clartes, reverse=True), nom                # de la plus claire à la plus sombre
    assert "#ffffff" not in e.values() and "#000000" not in e.values()  # ni blanc ni noir purs
# un même pas, une même clarté (hors la base, gardée exacte)
for k in (100, 400, 700):
    ls = [p.oklch(ech[n][k])[0] for n, b, *_ in p.BASES if p.pas_de_base(b) != k]
    assert max(ls) - min(ls) < .02, (k, ls)
assert abs(p.contraste("#ffffff", "#000000") - 21) < .01
v = p.variables()
assert v["--bc-danger"] == "var(--bc-coeur-600)" and v["--bc-success"] == "var(--bc-trefle-600)"
assert all(f"--bc-{r}-text-emphasis" in v for r, *_ in p.ROLES)
assert p.css().startswith("<style>:root {")
inv = p.inventaire()
assert inv and all(e >= 0 for *_, e in inv)
assert "Principes" in p.html_page() and "--bc-trefle-50" in p.html_page()
print("ok")
