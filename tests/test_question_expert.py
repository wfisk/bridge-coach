# -*- coding: utf-8 -*-
"""« Demander à l'expert » : le fichier d'une question sur une donne. .venv/bin/python -I -X utf8 tests/test_question_expert.py"""
import json, os, sys, tempfile
ESSAI = tempfile.mkdtemp()
os.environ["BRIDGE_COACH_DONNEES"] = ESSAI
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import question_expert as Q, carte, rapport

assert Q.prenom_de("MARTIN Anne") == "Anne" == Q.prenom_de("Anne Martin") and Q.prenom_de("") == ""
assert Q.encheres(["passe", "1♥"], "E") == [{"joueur": "E", "enchere": "passe"}, {"joueur": "S", "enchere": "1♥"}]

d = {"n": 1, "donneur": "N", "vul": "Personne", "mains": {"N": "- A9742 AX76 D984", "E": "AD974 83 V82 AV5",
     "S": "5 RDVX65 RD54 62", "O": "RVX8632 - 93 RX73"}, "hcp": {"N": 10, "E": 12, "S": 11, "O": 7},
     "dm": {"♥": {"N": 11, "S": 11, "E": 2, "O": 2}}, "par": {"contrat": "6♥"},
     "tables": [{"table": 1, "nom_ns": "AB/CD", "nom_eo": "EF/GH", "contrat": "4♥", "declarant": "S", "resultat": "+1"}]}
data = {"session": {"date": "05/11/2026", "tables": 1, "marque": "IMP"}, "donnes": [d],
        "joueurs": {"1": [{"initiales": "AB", "nom": "Anne BLANC"}]}}
seq = ["1♥", "passe", "4♥", "passe", "passe", "passe"]

# pendant les enchères : la main du joueur seulement, et le prénom réglé
f = Q.fichier(data, d, "S", seq[:2], None, False, prenom="Anne")
assert list(f["donne"]["mains"]) == ["S"] and f["moment"] == "pendant" and f["interlocuteur"] == "Anne"
assert "Anne" in f["consigne"] and "EN COURS" in f["consigne"] and "systeme.md" in f["documents"]
assert "« Bonjour Anne ! Que voulez-vous savoir" in f["consigne"] and "♥️" in f["consigne"] and "TON PREMIER MESSAGE" in f["consigne"]
assert "BLANC" not in json.dumps(f, ensure_ascii=False) and "dm" not in f["donne"]

# pendant le jeu de la carte, déclarant en Sud : Sud et le mort (Nord) une fois l'entame faite, jamais Est ni Ouest
p = carte.Partie(d, "4♥", "S", seq, humain="S")
f = Q.fichier(data, d, "S", seq, p, False, prenom="")
assert sorted(f["donne"]["mains"]) == ["N", "S"] and f["interlocuteur"] is None and "un joueur du club" in f["consigne"]
assert "« Bonjour ! Que voulez-vous" in f["consigne"] and "{" not in f["consigne"]
assert f["jeu"] and f["jeu"][0]["cartes"][0]["joueur"] == "O" and f["contrat"]["contrat"] == "4♥"

# après la donne : tout, analyses et résultats compris
an = ({"donnes": {"1": {"enc": [["–", "1♥", "passe", "4♥"]], "comm": "…"}}}, None)
f = Q.fichier(data, d, "S", seq, p, True, an, prenom="Anne")
assert sorted(f["donne"]["mains"]) == ["E", "N", "O", "S"] and f["donne"]["dm"] and "FINIE" in f["consigne"]
assert f["analyse_du_coach"]["comm"] == "…" and "analyse_de_l_expert" not in f and f["resultats_des_tables"][0]["contrat"] == "4♥"

# écrit dans pour-claude/<séance>/, le message, l'adresse avec le message pour claude.ai et ChatGPT seulement
rapport.preparer_donnees()
c = os.path.join(rapport.SEANCES, "2026-11", "2026-11-05-tournoi-jeudi.bc.json"); os.makedirs(os.path.dirname(c))
chemin = Q.ecrire(c, f, 1, True)
assert chemin.endswith(os.path.join("pour-claude", "2026-11-05-tournoi-jeudi", "donne-1-apres.ai.json"))
assert json.load(open(chemin, encoding="utf-8"))["moment"] == "apres"
assert Q.message("donne-1.ai.json").startswith("Bonjour ! Lis le fichier joint, donne-1.ai.json")
assert Q.adresse_avec_message("https://claude.ai/new", "Lis le fichier").startswith("https://claude.ai/new?q=Lis%20le")
assert Q.adresse_avec_message("https://chatgpt.com", "a").endswith("?q=a")
assert Q.adresse_avec_message("https://mon-ia.example/chat", "a") == "https://mon-ia.example/chat"
print("ok")
