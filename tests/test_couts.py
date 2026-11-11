# -*- coding: utf-8 -*-
"""Ce que chaque donne vous coûte face au champ : les enchères (contre le contrat recommandé), la carte (contre le double
mort, retenue seulement quand une autre table du même contrat a fait mieux ou qu'aucune ne l'a joué), le reste."""
import os, sys, tempfile
os.environ["BRIDGE_COACH_DONNEES"] = tempfile.mkdtemp(prefix="couts-")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import couts

DM = lambda sa, pi, co, ca, tr: {"SA": sa, "♠": pi, "♥": co, "♦": ca, "♣": tr}


def table(k, contrat, decl, levees, s, imp_ns=None):
    n = int(contrat[0]) + 6 if contrat != "passe" else 0
    res = "" if contrat == "passe" else ("=" if levees == n else f"{levees - n:+d}")
    return dict(table=k, paire_ns=f"{k}NS", paire_eo=f"{k}EO", contrat=contrat, declarant=decl, resultat=res,
                levees=levees, score_ns=s, imp_ns=imp_ns)


def enc(*appels):
    """Les enchères en grille Ouest/Nord/Est/Sud, Nord donneur (« – » sous Ouest)."""
    a = ["–"] + list(appels); return [a[i:i + 4] + [""] * (4 - len(a[i:i + 4])) for i in range(0, len(a), 4)]


# Donne 1 : vous (1NS) jouez 2♠ +2 alors que 4♠ fait (le recommandé) : une perte aux enchères, à vous (votre camp joue)
D1 = dict(n=1, donneur="N", vul="Personne", dm={"SA": {"N": 9, "S": 9, "E": 4, "O": 4}, "♠": {"N": 10, "S": 10, "E": 3, "O": 3},
          "♥": {"N": 7, "S": 7, "E": 6, "O": 6}, "♦": {"N": 7, "S": 7, "E": 6, "O": 6}, "♣": {"N": 7, "S": 7, "E": 6, "O": 6}},
          tables=[table(1, "2♠", "N", 10, 170), table(2, "4♠", "N", 10, 420), table(3, "4♠", "N", 10, 420)])
A1 = {"enc": enc("1♠", "passe", "3♠", "passe", "4♠", "passe", "passe", "passe")}
# Donne 2 : en défense (1EO) contre 4♠ N, le déclarant fait 10 levées, 9 au double mort ; l'autre table dans ce contrat
# le chute : une perte à la carte, retenue
D2 = dict(n=2, donneur="N", vul="Personne", dm={"SA": {"N": 8, "S": 8, "E": 5, "O": 5}, "♠": {"N": 9, "S": 9, "E": 4, "O": 4},
          "♥": {"N": 7, "S": 7, "E": 6, "O": 6}, "♦": {"N": 7, "S": 7, "E": 6, "O": 6}, "♣": {"N": 7, "S": 7, "E": 6, "O": 6}},
          tables=[table(1, "4♠", "N", 10, 420), table(2, "4♠", "N", 9, -50), table(3, "2♠", "N", 9, 140)])
A2 = {"enc": enc("1♠", "passe", "2♠", "passe", "passe", "passe")}
D2["tables"][0]["paire_ns"] = "4NS"                          # à cette table, Nord-Sud n'est pas la paire 1NS

c1 = couts.cout_donne(D1, A1, {"1NS"}, "IMP")
assert c1["camp"] == "NS" and c1["role"] == "jeu" and c1["encheres"] > 0 and c1["encheres_a_vous"]
assert c1["carte"] == 0                                    # 10 levées, comme le double mort
c2 = couts.cout_donne(D2, A2, {"1EO"}, "IMP")
assert c2["camp"] == "EO" and c2["role"] == "defense" and c2["carte"] > 0
assert c2["memes"] == 2 and c2["mieux"] == 2 and c2["carte_retenue"]     # 2♠ compte aussi : même dénomination, même camp
# les enchères de la donne 2 sont celles de Nord-Sud (4♠ au lieu de 2♠ recommandé) : pas à vous
assert not c2["encheres_a_vous"]
# la même défense, mais les autres tables à ♠ ont fait comme vous : le double mort seul ne suffit pas, rien à revoir
D2b = dict(D2, tables=[table(1, "4♠", "N", 10, 420), table(2, "4♠", "N", 10, 420), table(3, "2♠", "N", 10, 170)])
assert not couts.cout_donne(D2b, A2, {"1EO"}, "IMP")["carte_retenue"]

# la séance : les parts retenues et le reste font le total
b = couts.bilan([D1, D2], {"donnes": {"1": A1, "2": A2}}, {"1NS", "1EO"}, "IMP")
assert [c["n"] for c in b["encheres"]] == [1] and [c["n"] for c in b["carte"]] == [2]
assert b["n"] == 2 and abs(b["perte"] - b["reste"] - b["encheres"][0]["encheres"] - b["carte"][0]["carte"]) < 1e-9
# en match-points : des % face aux autres tables, vus de votre camp
m = couts.bilan([D1, D2], {"donnes": {"1": A1, "2": A2}}, {"1NS", "1EO"}, "MP")
assert m["lignes"][0]["vous"] == 0 and m["lignes"][0]["valeur_reco"] == 50   # 4♠ = égale les deux autres tables
# sans table à vous, ou seul à la table : rien
assert couts.cout_donne(D1, A1, {"9NS"}, "IMP") is None
print("ok")
