# -*- coding: utf-8 -*-
"""Le quiz de la démonstration (src/quiz.py) : .venv/bin/python -I -X utf8 tests/test_quiz.py"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import demo, quiz

d = dict(n=1, donneur="N", vul="Personne",
         mains=dict(N="AR5 D83 A92 D862", E="D43 R52 RD84 753", S="V8 AV976 V75 AX4", O="X9762 X4 X63 RV9"))
m = demo.Demo(d)
q = quiz.question_entame(m)
assert q["type"] == "entame" and q["pas"] == m.n_encheres
assert q["siege"] == {"N": "E", "E": "S", "S": "O", "O": "N"}[m.decl]          # l'entameur, à gauche du déclarant
assert q["voit"]["main"] == d["mains"][q["siege"]] and q["voit"]["encheres"] == m.seq
assert not any(v in json.dumps(q["voit"], ensure_ascii=False) for s, v in d["mains"].items() if s != q["siege"])   # rien d'autre
# une carte par couleur non vide, toutes de la main ; une seule bonne : celle que la démonstration joue ensuite
main = dict(zip("♠♥♦♣", d["mains"][q["siege"]].split()))
assert [x["carte"][0] for x in q["choix"]] == [c for c in "♠♥♦♣" if main[c] not in ("", "-")]
assert all(x["carte"][1:] in main[x["carte"][0]] for x in q["choix"])
assert [x["carte"] for x in q["choix"] if x["bonne"]] == [q["reponse"]]
assert q["reponse"] == m.cartes[0][0] + m.cartes[0][1].translate(str.maketrans({"K": "R", "Q": "D", "J": "V", "T": "X"}))
assert q["explication"] and "levée" not in q["explication"]                      # la raison : les règles, pas le double mort
json.dumps(q)                                                                       # des données, sans objet
print("ok question")

quiz.apres_coup(m, q)                                                               # le double mort, après coup seulement
assert all(isinstance(x.get("levees"), int) for x in q["choix"]) and isinstance(q["apres_coup"], str)
assert all(quiz.texte_levees(q, x) for x in q["choix"])
print("ok après coup")

passee = demo.Demo(dict(d, n=2, mains=dict(N="5432 432 432 432", E="AR5 D83 A92 D86", S="V8 AV97 V75 AX4", O="X976 X4 X63 RV92")))
assert passee.decl or quiz.question_entame(passee) is None
print("ok")
