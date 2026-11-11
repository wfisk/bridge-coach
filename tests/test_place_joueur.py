# -*- coding: utf-8 -*-
"""Jouer « comme un joueur de la séance » : sa place à chaque donne, ses adversaires, les quatre noms (moi.place_du_joueur)."""
import os, sys, tempfile
os.environ["BRIDGE_COACH_DONNEES"] = tempfile.mkdtemp(prefix="place-")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import moi

J = lambda ini, nom: {"initiales": ini, "nom": nom}
DATA = dict(joueurs={"1NS": [J("AA", "ALPHA Anne"), J("BB", "BETA Bob")], "1EO": [J("CC", "GAMMA Carl"), J("DD", "DELTA Dora")],
                     "2NS": [J("EE", "EPSILON Eve"), J("FF", "ZETA Fred")], "2EO": [J("GG", "ETA Gil"), J("HH", "THETA Hugo")]},
            session=dict(rondes=[{"tour": 1, "table": "1", "ns": "1NS", "eo": "1EO", "donnes": [1]},
                                 {"tour": 2, "table": "1", "ns": "1NS", "eo": "2EO", "donnes": [2]}]))
D1 = dict(n=1, tables=[dict(paire_ns="1NS", paire_eo="1EO"), dict(paire_ns="2NS", paire_eo="2EO")])
D2 = dict(n=2, tables=[dict(paire_ns="1NS", paire_eo="2EO")])

p = moi.place_du_joueur(DATA, D1, "beta bob")
assert p["siege"] == "S" and p["paire"] == "1NS" and p["tour"] == 1          # le second de la paire : Sud
assert p["adversaires"] == ["GAMMA Carl", "DELTA Dora"]
assert p["noms"] == {"N": "ALPHA Anne", "S": "BETA Bob", "E": "GAMMA Carl", "O": "DELTA Dora"}
p = moi.place_du_joueur(DATA, D2, "ETA Gil")
assert p["siege"] == "E" and p["tour"] == 2 and p["noms"]["O"] == "THETA Hugo"
assert moi.place_du_joueur(DATA, D2, "GAMMA Carl") is None                    # il n'a pas joué cette donne
assert moi.place_du_joueur(DATA, D1, "") is None
print("ok")
