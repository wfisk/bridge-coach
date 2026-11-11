# -*- coding: utf-8 -*-
"""La démonstration (src/demo.py) : .venv/bin/python -I -X utf8 tests/test_demo.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import demo

d = dict(n=1, donneur="N", vul="Personne",
         mains=dict(N="AR5 D83 A92 D862", E="D43 R52 RD84 753", S="V8 AV976 V75 AX4", O="X9762 X4 X63 RV9"))
m = demo.Demo(d)
assert m.source == "moteur" and m.n_encheres == len(m.seq) and m.decl
e = m.etape(0)
assert e["type"] == "enchere" and e["siege"] == "N" and e["appel"] == m.seq[0]
c0 = m.etape(m.n_encheres)                                 # l'entame, par les règles
assert c0["type"] == "carte" and c0["j"] == 0 and c0["pensee"].get("entame")
c1 = m.etape(m.n_encheres + 1)                             # la carte suivante, jouée par un robot
assert c1["type"] == "carte" and len(m.cartes) == 2
v = m.dm(1)                                                 # le double mort pour la carte 3
q = m.position(1)
assert set(v) == set(q.legales()) and all(0 <= t <= 13 for t in v.values())
# « et si… » : une autre carte à la place de la carte 2 ; la suite est oubliée
autre = next(x for x in m.position(0).legales() if x != m.cartes[1])
m.essayer(0, autre)
assert m.cartes[1] == autre and len(m.cartes) == 2 and m.pensees[1].get("essai")
assert m.etape(m.n_encheres + 2)["type"] == "carte"        # les robots reprennent de là
print("ok")
assert all(isinstance(x, str) for x in m.explications)
print("ok explications")
