# -*- coding: utf-8 -*-
"""Le classement du tournoi rejoué : vos essais de l'onglet Jouer face aux tables du club, puis parmi les paires."""
import os, sys, tempfile
os.environ["BRIDGE_COACH_DONNEES"] = tempfile.mkdtemp(prefix="classement-")    # pas de « Vous êtes » de l'utilisateur
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import classement as C


def table(k, ns, eo, contrat, decl, res, s, pct=None, imp=None):
    return dict(table=k, paire_ns=ns, paire_eo=eo, contrat=contrat, declarant=decl, resultat=res, score_ns=s,
                pct_ns=pct, imp_ns=imp)


# trois tables, trois paires de chaque côté ; donne 1 personne vulnérable, donne 2 tous vulnérables
D1 = dict(n=1, donneur="N", vul="Personne", tables=[
    table(1, "1NS", "1EO", "4♠", "S", "=", 420, 75.0, 4), table(2, "2NS", "2EO", "4♠", "S", "-1", -50, 0.0, -9),
    table(3, "3NS", "3EO", "4♠", "S", "=", 420, 75.0, 4)])
D2 = dict(n=2, donneur="E", vul="Tous", tables=[
    table(1, "1NS", "1EO", "3SA", "O", "+1", -630, 50.0, -2), table(2, "2NS", "2EO", "3SA", "O", "=", -600, 100.0, 0),
    table(3, "3NS", "3EO", "3SA", "O", "+2", -660, 0.0, -3)])
D3 = dict(n=3, donneur="S", vul="N-S", tables=[table(1, "1NS", "1EO", "2♥", "N", "=", 110, 50.0, 0)])
D4 = dict(n=4, donneur="O", vul="E-O", tables=[], a_completer=False)       # un entraînement : pas de table de club
PAIRES = {"1NS": {"nom": "AB/CD", "pct": 66.7}, "2NS": {"nom": "EF/GH", "pct": 33.3}, "3NS": {"nom": "IJ/KL", "pct": 50.0},
          "1EO": {"nom": "MN/OP", "pct": 33.3}, "2EO": {"nom": "QR/ST", "pct": 66.7}, "3EO": {"nom": "UV/WX", "pct": 50.0}}
DATA = dict(session=dict(marque="MP"), donnes=[D1, D2, D3, D4], paires=PAIRES)

# un essai fini : la carte jouée jusqu'au bout, ou une passe générale ; les enchères seules ne comptent pas
assert C.fini({"contrat": "passe"}) and C.fini({"contrat": "4♠", "levees": 9}) and not C.fini({"contrat": "4♠"})
assert C.dernier_fini([{"contrat": "4♠", "levees": 10}, {"contrat": "3SA"}])["levees"] == 10
assert C.dernier_fini([{"contrat": "3SA"}]) is None
# le score : les levées faites à la carte, pas le double mort ; contré, vulnérable
assert C.score_ns(D1, "4♠", "S", 10) == 420 and C.score_ns(D1, "4♠", "S", 9) == -50
assert C.score_ns(D2, "3SA", "O", 10) == -630 and C.score_ns(D2, "2♥X", "N", 7) == -200
assert C.resultat("4♠", 11) == "+1" and C.resultat("4♠", 10) == "=" and C.resultat("3SA", 7) == "-2"

# rien de rejoué : tout à rejouer, pas de total
cl = C.classement(DATA, {"donnes": {}})
assert cl["rejouees"] == 0 and cl["total"] is None and C.ligne_seance(cl) == ""
assert [x["etat"] for x in cl["lignes"]] == ["a_rejouer", "a_rejouer", "a_rejouer", "sans_tables"]

# en partie : donne 1 en Sud, 4♠ +1 (450 bat les trois tables : 100 %) ; donne 2, un essai sans la carte (pas compté)
essais = {"donnes": {
    "1": [{"siege": "S", "contrat": "4♠", "declarant": "S", "levees": 9},        # le premier essai chute…
          {"siege": "S", "contrat": "4♠", "declarant": "S", "levees": 11}],      # … le dernier fini compte
    "2": [{"siege": "E", "contrat": "3SA", "declarant": "O"}]}}
cl = C.classement(DATA, essais)
l1 = cl["lignes"][0]
assert l1["etat"] == "rejouee" and l1["score"] == 450 and l1["pct"] == 100.0 and l1["resultat"] == "+1"
assert l1["meilleur"]["score"] == 420                                          # la meilleure table de votre camp
assert cl["lignes"][1]["etat"] == "a_rejouer" and cl["rejouees"] == 1 and not cl["complet"]
assert cl["total"] == 100.0 and cl["rang"] == 1 and cl["nb_paires"] == 6
assert C.ligne_seance(cl) == "Vous : 100,0 % — 1er sur 6 paires"

# en entier : donne 2 en Est, 3SA par Ouest = : −600 pour N-S bat −630 et −660, égale −600 : 83,3 % N-S, 16,7 % E-O ;
# donne 3 en Nord, 2♥ +1 (140 bat 110 : 100 %)
essais["donnes"]["2"].append({"siege": "E", "contrat": "3SA", "declarant": "O", "levees": 9})
essais["donnes"]["3"] = [{"siege": "N", "contrat": "2♥", "declarant": "N", "levees": 9}]
cl = C.classement(DATA, essais)
l2 = cl["lignes"][1]
assert l2["camp"] == "EO" and l2["score"] == 600 and abs(l2["pct"] - 16.67) < 0.01
assert l2["meilleur"]["score"] == 660 and l2["meilleur"]["contrat"] == "3SA"
assert cl["lignes"][2]["pct"] == 100.0
assert cl["complet"] and cl["rejouees"] == 3 and cl["a_compter"] == 3
assert abs(cl["total"] - 72.22) < 0.01 and cl["rang"] == 1 and cl["ex_aequo"] is False
assert C.ligne_seance(cl) == "Vous : 72,2 % — 1er sur 6 paires"
noms = [p["nom"] for p in cl["paires"]]
assert "Vous" in noms and len(noms) == 7

# une passe générale compte sans jeu de la carte
essais2 = {"donnes": {"3": [{"siege": "N", "contrat": "passe", "declarant": None}]}}
cl = C.classement(DATA, essais2)
assert cl["lignes"][2]["score"] == 0 and cl["lignes"][2]["pct"] == 0.0         # 0 contre 110 : battu

# en IMP : contre la moyenne des tables (datum), puis par donne parmi les paires
DATA_IMP = dict(DATA, session=dict(marque="IMP"))
cl = C.classement(DATA_IMP, {"donnes": {"1": [{"siege": "S", "contrat": "4♠", "declarant": "S", "levees": 10}]}})
# datum (420 − 50 + 420) / 3 = 263 → 260 ; 420 − 260 = 160 : 4 IMP
assert cl["lignes"][0]["imp"] == 4 and cl["total"] == 4 and cl["par_donne"] == 4
# les paires : leurs IMP des tables, par donne jouée ; 1NS : 4 − 2 + 0 = 2 sur 3 donnes
assert abs(C.resultats_paires(DATA_IMP, "IMP")["1NS"]["valeur"] - 2 / 3) < 1e-9
# QR/ST (2EO) : 9 + 0 sur 2 donnes, 4,5 par donne, devant vous
assert cl["rang"] == 2 and C.ligne_seance(cl) == "Vous : +4 IMP (+4,00 par donne) — 2e sur 6 paires"
cl = C.classement(DATA_IMP, {"donnes": {"1": [{"siege": "E", "contrat": "4♠", "declarant": "S", "levees": 10}]}})
assert cl["total"] == -4 and C.ligne_seance(cl).startswith("Vous : −4 IMP (−4,00 par donne)")
print("ok")
