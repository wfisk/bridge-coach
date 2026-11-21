# -*- coding: utf-8 -*-
"""L'import d'un .bws (bws_extract.construire) : .venv/bin/python -I -X utf8 tests/test_bws.py
Une donne rejouée à la même table à un autre tour (mouvement du 20/11/2026, 3 tables, 6 paires) : les deux résultats
restent, chacun avec ses propres enchères ; avant le 21/11/2026 le second effaçait le premier et les enchères se mêlaient."""
import datetime, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import bws_extract as B

MAIN = {"North": ("KT8", "A965", "K965", "A2"), "East": ("97654", "Q4", "A73", "T94"),
        "South": ("A3", "KJT2", "QJ", "J8765"), "West": ("QJ2", "873", "T842", "KQ3")}
hr = {"Section": 1, "Board": 1}
for siege, couleurs in MAIN.items():
    for nom, c in zip(("Spades", "Hearts", "Diamonds", "Clubs"), couleurs): hr[siege + nom] = c

def resultat(table, tour, contrat, decl, res):
    return {"Section": 1, "Table": table, "Round": tour, "Board": 1, "NS/EW": decl, "Contract": contrat,
            "Result": res, "LeadCard": "", "Erased": False}

def encheres(table, tour, liste, depart):
    sieges = "NESW"
    return [{"ID": depart + k, "Section": 1, "Table": table, "Round": tour, "Board": 1, "Counter": k + 1,
             "Direction": sieges[k % 4], "Bid": b, "Erased": False} for k, b in enumerate(liste)]

T = {"Section": [{"ID": 1, "Letter": "A", "ScoringType": 2}],
     "Session": [{"Date": datetime.datetime(2026, 11, 20)}],
     "PlayerNumbers": [], "HandRecord": [hr], "HandEvaluation": [],
     "RoundData": [dict(Section=1, Table=1, Round=1, NSPair=6, EWPair=1, LowBoard=1, HighBoard=4),
                   dict(Section=1, Table=2, Round=3, NSPair=2, EWPair=4, LowBoard=1, HighBoard=4),
                   dict(Section=1, Table=2, Round=4, NSPair=3, EWPair=5, LowBoard=1, HighBoard=4)],
     "ReceivedData": [resultat(1, 1, "4 H", "S", "="), resultat(2, 3, "3 NT", "N", "+1"),
                      resultat(2, 4, "3 NT", "N", "+1")],
     "BiddingData": encheres(1, 1, ["1D", "Pass", "1H", "Pass", "2H", "Pass", "3C", "Pass", "4H", "Pass", "Pass", "Pass"], 1)
                    + encheres(2, 3, ["1NT", "2S", "3NT", "Pass", "Pass", "Pass"], 100)
                    + encheres(2, 4, ["1D", "Pass", "2C", "Pass", "3NT", "Pass", "Pass", "Pass"], 200)}

data = B.construire(T)
d = data["donnes"][0]
assert len(d["tables"]) == 3, [t["table"] for t in d["tables"]]
etiquettes = sorted(str(t["table"]) for t in d["tables"])
assert etiquettes == ["1", "2 (tour 3)", "2 (tour 4)"], etiquettes
par_tour = {t["tour"]: t for t in d["tables"]}
assert par_tour[3]["encheres"] == ["1SA", "2♠", "3SA", "passe", "passe", "passe"], par_tour[3]["encheres"]
assert par_tour[4]["encheres"][:3] == ["1♦", "passe", "2♣"], par_tour[4]["encheres"]
assert all(t["encheres_ok"] for t in d["tables"]), data["alertes"]
assert not data["alertes"], data["alertes"]
assert (par_tour[3]["paire_ns"], par_tour[3]["paire_eo"]) == ("2", "4")
assert (par_tour[4]["paire_ns"], par_tour[4]["paire_eo"]) == ("3", "5")
assert data["session"]["tables"] == 2                 # deux tables physiques
assert sum(t["imp_ns"] for t in d["tables"]) in (-1, 0, 1)   # IMP au datum sur trois résultats

# l'ordre des tables dans le PDF : section, numéro, puis le tour
import build_pdf
assert sorted(["2 (tour 4)", "10", 1, "2 (tour 3)", "A3"], key=build_pdf._ordre_table) == \
    [1, "2 (tour 3)", "2 (tour 4)", "10", "A3"]
print("test_bws : ok")
