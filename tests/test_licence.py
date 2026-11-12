# -*- coding: utf-8 -*-
"""Vous reconnaître par votre licence FFB : .venv/bin/python -I -X utf8 tests/test_licence.py"""
import json, os, sys, tempfile
ESSAI = tempfile.mkdtemp()
os.environ["BRIDGE_COACH_DONNEES"] = ESSAI
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import bws_extract, moi, rapport

# le numéro de Bridgemate, sans zéro de tête ; autre chose que des chiffres : rien
assert bws_extract.licence_ffb("12345678") == "12345678" and bws_extract.licence_ffb("00987654") == "987654"
assert bws_extract.licence_ffb(987654) == "987654" and bws_extract.licence_ffb("") == bws_extract.licence_ffb("A1") == bws_extract.licence_ffb("0") == ""

# joueurs_bws garde la licence à côté des initiales et du nom
data = {"paires": {"1": {"nom": "AM/HB"}}}
j = rapport.joueurs_bws(data, {"1": ["MARTIN Anne", "BERNARD Henri"]}, {"1": ["12345678", ""]})
assert j["1"][0] == {"initiales": "AM", "nom": "MARTIN Anne", "licence": "12345678"} and "licence" not in j["1"][1]

# la licence l'emporte sur l'orthographe du nom ; sans licence connue, le nom
seance = {"joueurs": {"3NS": [{"initiales": "AM", "nom": "MARTIN-DUPONT Anne", "licence": "12345678"}],
                      "5EO": [{"initiales": "AM", "nom": "MARTIN Anne", "licence": "777"}]}}
json.dump({"moi": "MARTIN Anne", "licences": {"MARTIN Anne": "012345678"}}, open(moi.ETAT, "w", encoding="utf-8"))
assert moi.licence_de("MARTIN Anne") == "012345678"
assert moi.paires(seance) == {"3NS"}                       # la même licence (sans les zéros), un autre nom d'usage
json.dump({"moi": "MARTIN Anne"}, open(moi.ETAT, "w", encoding="utf-8"))
assert moi.paires(seance) == {"5EO"}                       # licence inconnue : par le nom
assert moi.est({"nom": "martin anne"}, "MARTIN Anne") and not moi.est({"nom": ""}, "")

# la place à une donne, par la licence aussi
json.dump({"licences": {"MARTIN Anne": "12345678"}}, open(moi.ETAT, "w", encoding="utf-8"))
d = {"n": 1, "tables": [{"paire_ns": "3NS", "paire_eo": "5EO"}]}
assert moi.place_du_joueur(seance, d, "MARTIN Anne")["siege"] == "N"

# un licencié écrit de deux façons n'est qu'une fois dans la liste, sous le nom de la dernière séance
rapport.preparer_donnees()
dossier = os.path.join(rapport.SEANCES, "2026-11"); os.makedirs(dossier)
for nom_f, n in (("2026-11-01-a.bc.json", "MARTIN Anne"), ("2026-11-08-b.bc.json", "MARTIN-DUPONT Anne")):
    json.dump({"joueurs": {"1": [{"initiales": "AM", "nom": n, "licence": "12345678"}, {"initiales": "HB", "nom": "BERNARD Henri"}]}},
              open(os.path.join(dossier, nom_f), "w", encoding="utf-8"))
tous = moi.tous_les_joueurs(rapport.glob_seances("*" + rapport.BC))
assert tous == {"MARTIN-DUPONT Anne": "12345678", "BERNARD Henri": ""}, tous
assert moi.tous_les_noms(rapport.glob_seances("*" + rapport.BC)) == ["BERNARD Henri", "MARTIN-DUPONT Anne"]

# la licence ne part jamais chez l'expert : ni dans la séance pour Claude, ni dans une question sur une donne
import app, question_expert
plein = {"session": {"date": "01/11/2026", "tables": 1}, "donnes": [], "joueurs": seance["joueurs"], "paires": {}}
assert "12345678" not in json.dumps(app.seance_pour_claude(plein), ensure_ascii=False)
d2 = {"n": 1, "donneur": "N", "vul": "Personne", "mains": {"N": "- A9742 AX76 D984", "E": "AD974 83 V82 AV5",
      "S": "5 RDVX65 RD54 62", "O": "RVX8632 - 93 RX73"}, "tables": []}
q = question_expert.fichier(dict(plein, donnes=[d2]), d2, "S", [], None, True, prenom="Anne")
assert "12345678" not in json.dumps(q, ensure_ascii=False) and "MARTIN" not in json.dumps(q, ensure_ascii=False)
print("ok")
