# -*- coding: utf-8 -*-
"""Lit un fichier Bridgemate (.bws) et produit un JSON avec tout ce qu'il faut pour l'analyse.

Usage : python3 bws_extract.py séance.bws donnes.json

Contenu du JSON (tout en notation française : A R D V X, sièges N E S O) :
  session : date, nombre de tables
  donnes  : pour chaque donne
      n, donneur, vul, mains {N,E,S,O}, hcp
      tables : [{table, paire_ns, paire_eo, contrat, declarant, resultat, entame,
                 levees, dm, score_ns, imp_ns, ecart_par_imp,
                 encheres [..], encheres_ok, encheres_msg}]
      dm  : {"SA": {"N":..,"S":..,"E":..,"O":..}, "♠": ...}
      par : {score_ns, contrat, declarant, contre, resultat} ou null (passe générale)
  paires : {numéro: {imp, decl_ecart, decl_n, def_ecart, def_n}}
  alertes : liste de messages (séquences incomplètes, incohérences)
Les noms des joueurs ne sont PAS exportés.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jet4 import Jet4

FR = str.maketrans({"T": "X", "K": "R", "Q": "D", "J": "V"})
SUIT = {"S": "♠", "H": "♥", "D": "♦", "C": "♣", "NT": "SA"}
EN2FR = {"N": "N", "E": "E", "S": "S", "W": "O"}
SEAT = {"N": "North", "E": "East", "S": "South", "W": "West"}
SN = {"C": "Clubs", "D": "Diamonds", "H": "Hearts", "S": "Spades", "NT": "Notrump"}
STR = ["C", "D", "H", "S", "NT"]
ORDER = ["N", "E", "S", "W"]
VUL16 = ["Personne", "N-S", "E-O", "Tous", "N-S", "E-O", "Tous", "Personne",
         "E-O", "Tous", "Personne", "N-S", "Tous", "Personne", "N-S", "E-O"]
IMPT = [20, 50, 90, 130, 170, 220, 270, 320, 370, 430, 500, 600, 750, 900, 1100, 1300,
        1500, 1750, 2000, 2250, 2500, 3000, 3500, 4000]
HCP = {"A": 4, "R": 3, "D": 2, "V": 1}


def imp(diff):
    n = sum(1 for x in IMPT if abs(diff) >= x)
    return n if diff >= 0 else -n

def donneur(b): return "NESO"[(b - 1) % 4]
def vul(b): return VUL16[(b - 1) % 16]
def vul_of(v, side): return v == "Tous" or v == ("N-S" if side == "NS" else "E-O")

def main_fr(hr, seat):
    return " ".join((hr[seat + s] or "-").translate(FR) for s in ("Spades", "Hearts", "Diamonds", "Clubs"))

def bid_fr(x):
    x = x.upper().strip()
    if x == "PASS": return "passe"
    if x in ("X", "DBL"): return "contre"
    if x in ("XX", "RDBL"): return "surcontre"
    return x[0] + SUIT.get(x[1:], x[1:])

def contrat_fr(c):
    p = c.split()
    if p[0].upper() == "PASS": return "passe"
    s = p[0] + SUIT.get(p[1], p[1])
    if len(p) > 2: s += {"x": "X", "xx": "XX"}[p[2].lower()]
    return s

def carte_fr(c):
    if not c: return ""
    return SUIT[c[0]] + c[1:].replace("10", "X").translate(FR)

def score(level, strain, dbl, vul_, tricks):
    need = level + 6
    if tricks >= need:
        over = tricks - need
        if strain == "NT": base = 40 + 30 * (level - 1)
        else: base = (30 if strain in ("H", "S") else 20) * level
        base *= (1, 2, 4)[dbl]
        s = base + (50 if base < 100 else (500 if vul_ else 300))
        if level == 6: s += 750 if vul_ else 500
        if level == 7: s += 1500 if vul_ else 1000
        s += 50 * dbl
        if dbl == 0: s += over * (20 if strain in ("C", "D") else 30)
        else: s += over * (200 if vul_ else 100) * dbl
        return s
    down = need - tricks
    if dbl == 0: return -(100 if vul_ else 50) * down
    pts = (200 + 300 * (down - 1)) if vul_ else (100 + 200 * min(down - 1, 2) + 300 * max(down - 3, 0))
    return -pts * dbl

def parse_contract(c):
    p = c.split()
    if p[0].upper() == "PASS": return None
    return int(p[0]), p[1], {"": 0, "x": 1, "xx": 2}[p[2].lower() if len(p) > 2 else ""]

def tricks_made(r):
    pc = parse_contract(r["Contract"])
    if pc is None: return None
    res = r["Result"].strip()
    return pc[0] + 6 + (0 if res in ("=", "") else int(res))

def score_ns(r, v):
    pc = parse_contract(r["Contract"])
    if pc is None: return 0
    lvl, st, dbl = pc
    side = "NS" if r["NS/EW"] in "NS" else "EW"
    s = score(lvl, st, dbl, vul_of(v, side), tricks_made(r))
    return s if side == "NS" else -s

def par(he, v, dealer_en):
    best = {}
    for side in ("NS", "EW"):
        for si, st in enumerate(STR):
            t, who = max((he[SEAT[p] + SN[st]], p) for p in side.replace("EW", "EW"))
            for lvl in range(1, 8):
                best[(side, (lvl - 1) * 5 + si)] = (t, who)
    def val(side, r):
        t, who = best[(side, r)]; lvl, st = r // 5 + 1, STR[r % 5]
        s = score(lvl, st, 0 if t >= lvl + 6 else 1, vul_of(v, side), t)
        return s if side == "NS" else -s
    better = lambda side, w, x: (w > x) if side == "NS" else (w < x)
    memo = {}
    def V(r, side):
        if (r, side) in memo: return memo[(r, side)]
        other = "EW" if side == "NS" else "NS"
        res = (val(side, r), (r, side))
        for j in range(r + 1, 35):
            w = V(j, other)
            if better(other, w[0], res[0]): res = w
        memo[(r, side)] = res
        return res
    def opens(side):
        res = None
        for j in range(35):
            w = V(j, side)
            if res is None or better(side, w[0], res[0]): res = w
        return res
    first = "NS" if dealer_en in "NS" else "EW"
    second = "EW" if first == "NS" else "NS"
    v1, v2 = opens(first), opens(second)
    r2 = v2 if better(second, v2[0], 0) else (0, None)
    pv, ch = v1 if (better(first, v1[0], r2[0]) or v1[0] == r2[0]) else r2
    if ch is None: return None
    r, side = ch
    t, who = best[(side, r)]; lvl = r // 5 + 1
    return {"score_ns": pv, "contrat": f"{lvl}{SUIT[STR[r % 5]]}", "declarant": EN2FR[who],
            "contre": t < lvl + 6, "resultat": "=" if t == lvl + 6 else f"{t - lvl - 6:+d}"}

def valider(seq, dealer_en, contract, decl):
    """seq = [(siège, enchère brute)]. Renvoie (ok, message)."""
    if not seq: return False, "aucune enchère enregistrée"
    pos = ORDER.index(dealer_en)
    last = last_by = None; dbl = 0; first = {}
    for k, (who, bid) in enumerate(seq):
        if who != ORDER[(pos + k) % 4]:
            return False, f"tour {k+1} : enchère de {EN2FR[who]} au lieu de {EN2FR[ORDER[(pos+k)%4]]}"
        B = bid.upper(); side = "NS" if who in "NS" else "EW"
        if B == "PASS": continue
        if B in ("X", "DBL"):
            if last is None or last_by == side or dbl: return False, f"contre impossible au tour {k+1}"
            dbl = 1; continue
        if B in ("XX", "RDBL"):
            if dbl != 1 or last_by != side: return False, f"surcontre impossible au tour {k+1}"
            dbl = 2; continue
        r = (int(B[0]) - 1) * 5 + STR.index(B[1:])
        if last is not None and r <= last: return False, f"enchère insuffisante au tour {k+1}"
        last, last_by, dbl = r, side, 0
        first.setdefault((side, r % 5), who)
    if last is None:
        return (contract.upper().startswith("PASS"), "passe générale")
    c = f"{last//5+1} {STR[last%5]}" + {0: "", 1: " x", 2: " xx"}[dbl]
    d = first[(last_by, last % 5)]
    want = " ".join(contract.split()).lower()
    if c.lower() != want or d != decl:
        return False, f"la séquence aboutit à {contrat_fr(c)} par {EN2FR[d]}, mais le contrat marqué est {contrat_fr(contract)} par {EN2FR[decl]}"
    n = 0
    for _, x in reversed(seq):
        if x.upper() == "PASS": n += 1
        else: break
    if n < 3: return True, "passes finales manquants (complétés)"
    return True, "ok"


def extraire(path):
    db = Jet4(path)
    T = {n: db.rows(n) for n in ("HandRecord", "HandEvaluation", "ReceivedData", "BiddingData", "RoundData", "Session")}
    HR = {r["Board"]: r for r in T["HandRecord"]}
    HE = {r["Board"]: r for r in T["HandEvaluation"]}
    RES = {}
    for r in T["ReceivedData"]:
        if not r.get("Erased"): RES.setdefault(r["Board"], {})[r["Table"]] = r
    BIDS = {}
    for r in sorted(T["BiddingData"], key=lambda r: r["ID"]):
        if r.get("Erased"): continue
        BIDS.setdefault(r["Board"], {}).setdefault(r["Table"], {})[r["Counter"]] = (r["Direction"], r["Bid"])
    def pairs(b, t):
        for x in T["RoundData"]:
            if x["Table"] == t and x["LowBoard"] <= b <= x["HighBoard"]:
                return x["NSPair"], x["EWPair"]
        return None, None
    alertes, donnes = [], []
    paires = {}
    for b in sorted(RES):
        v, dl = vul(b), donneur(b)
        dl_en = {"O": "W"}.get(dl, dl)
        hr = HR.get(b)
        mains = {k: main_fr(hr, s) for k, s in (("N", "North"), ("E", "East"), ("S", "South"), ("O", "West"))} if hr else None
        hcp = {k: sum(HCP.get(c, 0) for c in m.replace(" ", "")) for k, m in mains.items()} if mains else None
        he = HE.get(b)
        dm = None
        if he:
            dm = {lab: {EN2FR[p]: he[SEAT[p] + SN[st]] for p in "NSEW"}
                  for st, lab in (("NT", "SA"), ("S", "♠"), ("H", "♥"), ("D", "♦"), ("C", "♣"))}
        pr = par(he, v, dl_en) if he else None
        scores = {t: score_ns(r, v) for t, r in RES[b].items()}
        # IMP : deux tables = comparaison directe ; plus = contre la moyenne (datum)
        tabs = sorted(scores)
        if len(tabs) == 2:
            i = imp(scores[tabs[0]] - scores[tabs[1]]); imps = {tabs[0]: i, tabs[1]: -i}
        else:
            datum = round(sum(scores.values()) / len(scores) / 10) * 10
            imps = {t: imp(scores[t] - datum) for t in tabs}
        tables = []
        for t in tabs:
            r = RES[b][t]; pc = parse_contract(r["Contract"])
            seq = [BIDS[b][t][k] for k in sorted(BIDS.get(b, {}).get(t, {}))]
            decl = r["NS/EW"]
            ok, msg = valider(seq, dl_en, r["Contract"], decl) if pc else (True, "passe générale")
            if not ok: alertes.append(f"Donne {b}, table {t} : séquence d'enchères à vérifier ({msg}).")
            made = tricks_made(r)
            ddv = he[SEAT[decl] + SN[pc[1]]] if (he and pc) else None
            ns, ew = pairs(b, t)
            tables.append(dict(table=t, paire_ns=ns, paire_eo=ew, contrat=contrat_fr(r["Contract"]),
                               declarant=EN2FR.get(decl, decl), resultat=r["Result"].strip(),
                               entame=carte_fr(r.get("LeadCard")), levees=made, dm=ddv,
                               score_ns=scores[t], imp_ns=imps[t],
                               ecart_par_imp=imp(scores[t] - pr["score_ns"]) if pr else imp(scores[t]),
                               encheres=[bid_fr(x) for _, x in seq], encheres_ok=ok, encheres_msg=msg))
            # bilan par paire
            for p in (ns, ew):
                paires.setdefault(p, dict(imp=0, decl_ecart=0, decl_n=0, def_ecart=0, def_n=0))
            paires[ns]["imp"] += imps[t]; paires[ew]["imp"] -= imps[t]
            if pc and ddv is not None:
                dec_p, def_p = (ns, ew) if decl in "NS" else (ew, ns)
                paires[dec_p]["decl_ecart"] += made - ddv; paires[dec_p]["decl_n"] += 1
                paires[def_p]["def_ecart"] += ddv - made; paires[def_p]["def_n"] += 1
        donnes.append(dict(n=b, donneur=dl, vul=v, mains=mains, hcp=hcp, tables=tables, dm=dm, par=pr))
    if len(tabs) == 2:  # en match à deux tables, chaque IMP compte pour les deux camps
        pass
    s = T["Session"][0] if T["Session"] else {}
    date = s.get("Date").strftime("%d/%m/%Y") if s.get("Date") else ""
    return dict(session=dict(date=date, tables=len({t for d in donnes for t in [x["table"] for x in d["tables"]]})),
                donnes=donnes, paires={str(k): v for k, v in sorted(paires.items())}, alertes=alertes)


if __name__ == "__main__":
    data = extraire(sys.argv[1])
    json.dump(data, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
    print(f"{len(data['donnes'])} donnes, séance du {data['session']['date']}, {data['session']['tables']} tables")
    for a in data["alertes"]: print("ALERTE :", a)
