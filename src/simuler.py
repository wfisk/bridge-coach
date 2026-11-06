# -*- coding: utf-8 -*-
"""Fabrique une séance simulée (Mitchell, N tables) pour essayer le rapport sans vrai tournoi.

Usage : python3 -I src/simuler.py source.bws N sortie.json

Les mains et le double mort viennent du .bws source ; le mouvement, les joueurs (noms inventés),
les contrats, les résultats, les entames et les enchères sont simulés. La sortie contient les
mêmes tables que le .bws (RoundData, PlayerNumbers, ReceivedData…) au format JSON ;
rapport.sh l'accepte comme un .bws :  ./rapport.sh sortie.json
"""
import sys, os, json, random, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bws_extract import construire, lire
from encheres import encherir

EN_RANG = str.maketrans({"R": "K", "D": "Q", "V": "J", "X": "T"})
EN_DEN = {"♠": "S", "♥": "H", "♦": "D", "♣": "C", "SA": "NT"}
SIEGE_EN = {"N": "N", "E": "E", "S": "S", "O": "W"}
LHO = {"N": "E", "E": "S", "S": "O", "O": "N"}
NOMS = ["MARTIN", "BERNARD", "DUBOIS", "THOMAS", "ROBERT", "RICHARD", "PETIT", "DURAND", "LEROY", "MOREAU",
        "SIMON", "LAURENT", "LEFEBVRE", "MICHEL", "GARCIA", "DAVID", "BERTRAND", "ROUX", "VINCENT", "FOURNIER",
        "MOREL", "GIRARD", "ANDRE", "MERCIER", "BLANC", "GUERIN", "BOYER", "GARNIER", "CHEVALIER", "FRANCOIS",
        "LEGRAND", "GAUTHIER", "PERRIN", "ROBIN", "CLEMENT", "MORIN", "NICOLAS", "HENRY", "ROUSSEL", "MATHIEU",
        "GAUTIER", "MASSON", "MARCHAND", "DUVAL", "DENIS", "DUMONT", "MARIE", "LEMAIRE"]
PRENOMS = ["Anne", "Paul", "Claire", "Louis", "Marie", "Henri", "Odile", "Bernard", "Agnès", "Michel", "Sophie", "Jean"]


def contrat_en(c):
    reste = c[1:]; x = reste.count("X")
    return f"{c[0]} {EN_DEN[reste.rstrip('X')]}" + {0: "", 1: " x", 2: " xx"}[x]

def bid_en(b):
    return {"passe": "PASS", "contre": "X", "surcontre": "XX"}.get(b) or b[0] + EN_DEN[b[1:]]


def simuler(source, N, graine=7):
    random.seed(graine)
    T = lire(source)
    donnes = {d["n"]: d for d in construire(T)["donnes"]}
    nb = len(donnes); par_tour = max(1, nb // N)
    T["Section"] = [dict(ID=1, Letter="A", Tables=N, Winners=2, ScoringType=T["Section"][0].get("ScoringType")
                         if T.get("Section") else None)]
    T["RoundData"] = []
    for r in range(1, N + 1):                      # Mitchell : N-S fixes, E-O et étuis tournent
        for t in range(1, N + 1):
            k = (t + r - 2) % N
            T["RoundData"].append(dict(Section=1, Table=t, Round=r, NSPair=t, EWPair=(t - r) % N + 1,
                                       LowBoard=k * par_tour + 1, HighBoard=k * par_tour + par_tour))
    T["PlayerNumbers"] = []
    for i, (t, s) in enumerate((t, s) for t in range(1, N + 1) for s in "NSEW"):
        T["PlayerNumbers"].append(dict(Section=1, Table=t, Round=0, Direction=s, Number=f"{i:08d}",
                                       Name=f"{NOMS[i % len(NOMS)]} {PRENOMS[(i * 5) % len(PRENOMS)]}"))
    T["ReceivedData"], T["BiddingData"] = [], []
    for x in T["RoundData"]:
        for b in range(x["LowBoard"], x["HighBoard"] + 1):
            d = donnes.get(b)
            if not d: continue
            moteur = encherir(d)
            choix = [(t["contrat"], t["declarant"], t["encheres"]) for t in d["tables"] if t["contrat"] != "passe"]
            if moteur["contrat"] != "passe":
                choix += [(moteur["contrat"], moteur["declarant"], moteur["encheres"])] * 2
            if d["par"]:
                p = d["par"]; choix.append((p["contrat"] + ("X" if p["contre"] else ""), p["declarant"], []))
            c, decl, seq = random.choice(choix)
            dm = d["dm"][c[1:].rstrip("X")][decl]
            lev = max(0, min(13, dm + random.choice([0, 0, 0, 0, 1, -1, -1, -2])))
            need = int(c[0]) + 6
            main = d["mains"][LHO[decl]].split()
            coul = random.choice([k for k in range(4) if main[k] != "-"])
            T["ReceivedData"].append({"ID": len(T["ReceivedData"]) + 1, "Section": 1, "Table": x["Table"],
                                      "Round": x["Round"], "Board": b, "PairNS": x["NSPair"], "PairEW": x["EWPair"],
                                      "NS/EW": SIEGE_EN[decl], "Contract": contrat_en(c),
                                      "Result": "=" if lev == need else f"{lev - need:+d}",
                                      "LeadCard": "SHDC"[coul] + random.choice(main[coul]).translate(EN_RANG),
                                      "Erased": False})
            if seq and random.random() < 0.8:      # enchères enregistrées à 80 % des tables
                rot = ["N", "E", "S", "O"]; k0 = rot.index(d["donneur"])
                for j, bb in enumerate(seq):
                    T["BiddingData"].append(dict(ID=len(T["BiddingData"]) + 1, Section=1, Table=x["Table"],
                                                 Round=x["Round"], Board=b, Counter=j + 1,
                                                 Direction=SIEGE_EN[rot[(k0 + j) % 4]], Bid=bid_en(bb), Erased=False))
    return T


# ---------------------------------------------------------------- donnes aléatoires
RANGS_EN = "AKQJT98765432"
FR_RANG = str.maketrans({"K": "R", "Q": "D", "J": "V", "T": "X"})
SIEGES = {"N": "North", "E": "East", "S": "South", "O": "West"}
COUL_EN = {"♠": "Spades", "♥": "Hearts", "♦": "Diamonds", "♣": "Clubs"}


def donnes_aleatoires(nb):
    """nb donnes tirées au hasard, avec le double mort calculé par endplay (DDS)."""
    from endplay.types import Deal
    from endplay.dds import calc_dd_table
    HR, HE = [], []
    for b in range(1, nb + 1):
        jeu = [c + r for c in "SHDC" for r in RANGS_EN]
        random.shuffle(jeu)
        mains = {}
        for i, s in enumerate("NESO"):
            m = jeu[13 * i:13 * i + 13]
            mains[s] = {c: "".join(sorted((x[1] for x in m if x[0] == c), key=RANGS_EN.index)) for c in "SHDC"}
        hr = dict(Section=1, Board=b)
        for s, nom in SIEGES.items():
            for c, cn in zip("SHDC", ("Spades", "Hearts", "Diamonds", "Clubs")): hr[nom + cn] = mains[s][c]
        HR.append(hr)
        pbn = "N:" + " ".join(".".join(mains[s][c] for c in "SHDC") for s in "NESO")
        table = calc_dd_table(Deal(pbn)).to_list()     # lignes ♠ ♥ ♦ ♣ SA, colonnes N E S O
        he = dict(Section=1, Board=b)
        for den, ligne in zip(("Spades", "Hearts", "Diamonds", "Clubs", "Notrump"), table):
            for s, t in zip("NESO", ligne): he[SIEGES[s] + den] = t
        for s, nom in SIEGES.items():
            he[nom + "Hcp"] = sum({"A": 4, "K": 3, "Q": 2, "J": 1}.get(x, 0) for c in "SHDC" for x in mains[s][c])
        HR[-1]["_mains_fr"] = {s: " ".join((mains[s][c] or "-").translate(FR_RANG) for c in "SHDC") for s in "NESO"}
        HE.append(he)
    return HR, HE


def entame(main_fr, den):
    """Entame selon les règles de jeu.py ; un singleton est entamé une fois sur trois."""
    from jeu import entame_regle
    return entame_regle(main_fr, den, singleton=random.random() < 0.3)[0]


def simuler_aleatoire(N, nb, date):
    """Séance Mitchell de N tables sur nb donnes nouvelles : enchères par le moteur SEF (jugement
    légèrement différent à chaque table), entame par règles, levées proches du double mort."""
    HR, HE = donnes_aleatoires(nb)
    T = dict(HandRecord=HR, HandEvaluation=HE, Section=[dict(ID=1, Letter="A", Tables=N, Winners=2)],
             Session=[dict(ID=1, Name="Séance simulée", Date=date)], RoundData=[], PlayerNumbers=[],
             ReceivedData=[], BiddingData=[])
    par_tour = max(1, nb // N)
    for r in range(1, N + 1):
        for t in range(1, N + 1):
            k = (t + r - 2) % N
            T["RoundData"].append(dict(Section=1, Table=t, Round=r, NSPair=t, EWPair=(t - r) % N + 1,
                                       LowBoard=k * par_tour + 1, HighBoard=k * par_tour + par_tour))
    for i, (t, s) in enumerate((t, s) for t in range(1, N + 1) for s in "NSEW"):
        T["PlayerNumbers"].append(dict(Section=1, Table=t, Round=0, Direction=s, Number=f"{i:08d}",
                                       Name=f"{NOMS[i % len(NOMS)]} {PRENOMS[(i * 5) % len(PRENOMS)]}"))
    he = {h["Board"]: h for h in HE}
    for x in T["RoundData"]:
        for b in range(x["LowBoard"], x["HighBoard"] + 1):
            if b > nb: continue
            mains = HR[b - 1]["_mains_fr"]
            d = dict(n=b, donneur="NESO"[(b - 1) % 4], mains=mains)
            bruit = {s: random.choice([-1, 0, 0, 0, 1]) for s in "NESO"}
            enc = encherir(d, bruit)
            rot = ["N", "E", "S", "O"]; k0 = rot.index(d["donneur"])
            if random.random() < 0.85:                 # enchères enregistrées à 85 % des tables
                for j, bb in enumerate(enc["encheres"]):
                    T["BiddingData"].append(dict(ID=len(T["BiddingData"]) + 1, Section=1, Table=x["Table"],
                                                 Round=x["Round"], Board=b, Counter=j + 1,
                                                 Direction=SIEGE_EN[rot[(k0 + j) % 4]], Bid=bid_en(bb), Erased=False))
            row = {"ID": len(T["ReceivedData"]) + 1, "Section": 1, "Table": x["Table"], "Round": x["Round"],
                   "Board": b, "PairNS": x["NSPair"], "PairEW": x["EWPair"], "Erased": False}
            c, decl = enc["contrat"], enc["declarant"]
            if c == "passe":
                row.update({"NS/EW": "", "Contract": "PASS", "Result": "", "LeadCard": ""})
            else:
                den = c[1:].rstrip("X")
                dm = he[b][SIEGES[decl] + {"♠": "Spades", "♥": "Hearts", "♦": "Diamonds", "♣": "Clubs",
                                            "SA": "Notrump"}[den]]
                lev = max(0, min(13, dm + random.choice([0, 0, 0, 0, 0, 1, -1, -1, -2])))
                need = int(c[0]) + 6
                ent = entame(mains[LHO[decl]], den)
                row.update({"NS/EW": SIEGE_EN[decl], "Contract": contrat_en(c),
                            "Result": "=" if lev == need else f"{lev - need:+d}",
                            "LeadCard": {"♠": "S", "♥": "H", "♦": "D", "♣": "C"}[ent[0]] + ent[1:].translate(EN_RANG)})
            T["ReceivedData"].append(row)
    for h in HR: h.pop("_mains_fr")
    return T


if __name__ == "__main__":
    if sys.argv[1] == "--aleatoire":                    # simuler.py --aleatoire N sortie.json [nb donnes] [graine]
        N, out = int(sys.argv[2]), sys.argv[3]
        nb = int(sys.argv[4]) if len(sys.argv) > 4 else 24
        random.seed(int(sys.argv[5]) if len(sys.argv) > 5 else None)
        T = simuler_aleatoire(N, nb, datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))
    else:
        src, N, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
        T = simuler(src, N)
    for r in T.get("Session", []):
        if isinstance(r.get("Date"), datetime.datetime): r["Date"] = r["Date"].isoformat()
    T = {k: [{c: (v.isoformat() if isinstance(v, datetime.datetime) else v) for c, v in r.items()} for r in rows]
         for k, rows in T.items()}
    json.dump({"format": "tables Bridgemate (séance simulée)", "tables": T}, open(out, "w"), ensure_ascii=False)
    print(f"Séance simulée : {N} tables, {len(T['ReceivedData'])} résultats -> {out}")
