# -*- coding: utf-8 -*-
"""Lit une « feuille de route » PDF de FFBClubNet (mains, contrats, entames, résultats, sans
enchères ni double mort) et l'écrit comme une séance JSON (mêmes tables que simuler.py), que
rapport.sh accepte comme un .bws. Le double mort est calculé ici (endplay). Le nom du club, en
tête de page, n'est pas repris ; le PDF n'a pas de noms de joueurs, seulement des numéros de paires.

    python3 -I src/feuille_route.py feuille.pdf sortie.json

Lecture par positions : les signes de couleur des mains sont des images, seule la place d'une
ligne dit de quelle couleur il s'agit (une chicane est une ligne vide).
"""
import sys, os, re, json, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SYMBOLES = {"ª": "♠", "©": "♥", "¨": "♦", "§": "♣"}
# lignes de chaque main (♠ ♥ ♦ ♣), en points sous le libellé « Donne » de la donne
LIGNES = {"N": (10.4, -1.0, -12.8, -24.9), "O": (-22.2, -32.8, -44.5, -56.2),
          "E": (-22.2, -32.8, -44.5, -56.2), "S": (-50.2, -61.2, -71.7, -83.3)}
COLONNE = {"O": (195, 240), "N": (270, 330), "S": (270, 330), "E": (345, 400)}
EN_RANG = str.maketrans({"R": "K", "D": "Q", "V": "J", "X": "T"})
SIEGE_EN = {"N": "North", "E": "East", "S": "South", "O": "West"}
COUL = ("Spades", "Hearts", "Diamonds", "Clubs")
EN_DEN = {"♠": "S", "♥": "H", "♦": "D", "♣": "C", "SA": "NT"}


def mots(page):
    """[(texte, x, y)] : les mots de la page, avec leur position (y du bas du premier caractère)."""
    tp = page.get_textpage(); out = []; cur = None
    for i in range(tp.count_chars()):
        c = tp.get_text_range(i, 1)
        if c in "\r\n \x00\x02": cur = None; continue
        g, b, d, h = tp.get_charbox(i)
        if cur is not None and abs(cur[2] - b) < 3 and g - cur[3] < 4:
            cur[0] += c; cur[3] = d
        else:
            cur = [c, g, b, d]; out.append(cur)
    return [(t, x, y) for t, x, y, _ in out]


def lire_pdf(chemin):
    import pypdfium2
    doc = pypdfium2.PdfDocument(chemin)
    date = None; donnes = []
    for pg in doc:
        ws = mots(pg)
        texte = " ".join(t for t, _, _ in ws)
        m = re.search(r"\b(\d\d/\d\d/\d{4})\b", texte)
        if m and not date: date = m[1]
        ancres = sorted((y for t, x, y in ws if t == "Donne"), reverse=True)
        for k, a in enumerate(ancres):
            bas = ancres[k + 1] if k + 1 < len(ancres) else -1
            bloc = [w for w in ws if bas + 12 < w[2] < a + 16]    # le haut de la main N dépasse du libellé
            donnes.append(lire_donne(bloc, a))
    return date, donnes


def valeur_apres(bloc, a, mot):
    """Le mot à droite du libellé (Vulnérable : P ; Donneur : N ; n° 1)."""
    xs = [(x, y) for t, x, y in bloc if t == mot]
    if not xs: return None
    x0, y0 = xs[0]
    droite = sorted((x, t) for t, x, y in bloc if abs(y - y0) < 3 and x0 < x < 150 and t not in (":", "°", "n"))
    return droite[0][1] if droite else None


def lire_donne(bloc, a):
    n = int(next(t for t, x, y in bloc if abs(y - a) < 4 and 100 < x < 150 and t.isdigit()))
    mains = {}
    for s, offs in LIGNES.items():
        lo, hi = COLONNE[s]
        lignes = [""] * 4
        for t, x, y in bloc:
            if lo <= x <= hi and -95 < y - a < 18 and re.fullmatch(r"[ARDVX2-9]+|10", t):
                j = min(range(4), key=lambda i: abs(y - a - offs[i]))
                if abs(y - a - offs[j]) < 5: lignes[j] += t
        mains[s] = lignes
    entete = next(y for t, x, y in bloc if t == "Paires")
    tables = []
    ys = sorted({round(y) for t, x, y in bloc if y < entete - 5 and x < 75 and t.isdigit()}, reverse=True)
    for y0 in ys:
        rang = sorted((x, t) for t, x, y in bloc if abs(y - y0) < 3.5)
        tables.append(lire_ligne(rang))
    return dict(n=n, vul=valeur_apres(bloc, a, "Vulnérable"), donneur=valeur_apres(bloc, a, "Donneur"),
                mains=mains, tables=[t for t in tables if t])


def lire_ligne(rang):
    """Une ligne « paires, contrat, déclarant, résultat, entame, score, fréquences ». None : paire
    exempte (ligne de tirets). Le déclarant peut précéder le contrat (« S 3 SA +2 ») : on lit par colonnes."""
    def zone(lo, hi): return [t for x, t in rang if lo <= x < hi]
    ns, eo = zone(50, 80), zone(85, 120)
    if not ns or not eo or not ns[0].isdigit() or not eo[0].isdigit(): return None
    contrat = "".join(zone(135, 190)); milieu = zone(190, 245)
    entame = zone(250, 290)
    if any(t == "PASSE" for _, t in rang) or re.search(r"[Pp]as", contrat):   # passe générale
        return dict(ns=int(ns[0]), eo=int(eo[0]), contrat="passe", declarant=None, resultat="", entame="", score=0)
    if "%" in "".join(t for _, t in rang) or contrat.strip("-") == "":        # paire exempte
        return None
    s = contrat
    for k, v in SYMBOLES.items(): s = s.replace(k, v)
    m = re.fullmatch(r"([1-7])(♠|♥|♦|♣|SA)(X{0,2})", s.replace(" ", "").replace("x", "X"))
    if not m: raise ValueError(f"contrat illisible : {contrat!r} dans {rang}")
    decl = next(t for t in milieu if t in "NSEO")
    res = next(t for t in milieu if re.fullmatch(r"=|[+-]\d+", t))
    e = "".join(entame)
    for k, v in SYMBOLES.items(): e = e.replace(k, v)
    me = re.fullmatch(r"(10|[ARDVX2-9])(♠|♥|♦|♣)", e)
    carte = (me[2] + ("X" if me[1] == "10" else me[1])) if me else ""
    sc = [(x, t) for x, t in rang if 300 <= x < 395 and re.fullmatch(r"\d+", t)]
    score = (int(sc[0][1]) * (1 if sc[0][0] < 337 else -1)) if sc else None
    return dict(ns=int(ns[0]), eo=int(eo[0]), contrat=m[1] + m[2] + m[3], declarant=decl, resultat=res,
                entame=carte, score=score)


def double_mort(mains):
    """Levées au double mort, au format de HandEvaluation."""
    from endplay.types import Deal
    from endplay.dds import calc_dd_table
    en = {s: [x.translate(EN_RANG).replace("10", "T") for x in mains[s]] for s in "NESO"}
    pbn = "N:" + " ".join(".".join(en[s]) for s in "NESO")
    table = calc_dd_table(Deal(pbn)).to_list()             # lignes ♠ ♥ ♦ ♣ SA, colonnes N E S O
    he = {}
    for den, ligne in zip(COUL + ("Notrump",), table):
        for s, t in zip("NESO", ligne): he[SIEGE_EN[s] + den] = t
    for s in "NESO":
        he[SIEGE_EN[s] + "Hcp"] = sum({"A": 4, "R": 3, "D": 2, "V": 1}.get(c, 0) for x in mains[s] for c in x)
    return he


def verifier(d):
    """Chaque carte une fois, 13 cartes par main : une erreur de lecture ne passe pas."""
    vues = set()
    for s in "NESO":
        if sum(len(x) for x in d["mains"][s]) != 13:
            raise ValueError(f"donne {d['n']} : {s} n'a pas 13 cartes : {d['mains'][s]}")
        for c, x in zip("♠♥♦♣", d["mains"][s]):
            for r in x:
                if c + r in vues: raise ValueError(f"donne {d['n']} : {c}{r} deux fois")
                vues.add(c + r)
    if len(vues) != 52: raise ValueError(f"donne {d['n']} : {len(vues)} cartes")


def convertir(chemin):
    date, donnes = lire_pdf(chemin)
    if not donnes: raise ValueError("aucune donne trouvée dans le PDF")
    j, m, a = date.split("/")
    HR, HE, RD, RE = [], [], [], []
    for d in donnes:
        verifier(d); b = d["n"]
        hr = dict(Section=1, Board=b)
        for s in "NESO":
            for coul, x in zip(COUL, d["mains"][s]): hr[SIEGE_EN[s] + coul] = x.translate(EN_RANG)
        HR.append(hr); HE.append(dict(double_mort(d["mains"]), Section=1, Board=b))
        for k, t in enumerate(d["tables"], 1):
            # les tours ne sont pas dans le PDF : un « tour » par donne suffit à relier paires et résultats
            RD.append(dict(Section=1, Table=k, Round=b, NSPair=t["ns"], EWPair=t["eo"], LowBoard=b, HighBoard=b))
            r = {"ID": len(RE) + 1, "Section": 1, "Table": k, "Round": b, "Board": b, "PairNS": t["ns"],
                 "PairEW": t["eo"], "Erased": False}
            if t["contrat"] == "passe":
                r.update({"NS/EW": "", "Contract": "PASS", "Result": "", "LeadCard": ""})
            else:
                c = t["contrat"]; den = c[1:].rstrip("X"); x = c.count("X")
                r.update({"NS/EW": {"O": "W"}.get(t["declarant"], t["declarant"]),
                          "Contract": f"{c[0]} {EN_DEN[den]}" + {0: "", 1: " x", 2: " xx"}[x],
                          "Result": t["resultat"],
                          "LeadCard": ({"♠": "S", "♥": "H", "♦": "D", "♣": "C"}[t["entame"][0]] +
                                       t["entame"][1:].translate(EN_RANG)) if t["entame"] else ""})
            RE.append(r)
    T = dict(HandRecord=HR, HandEvaluation=HE, RoundData=RD, ReceivedData=RE, BiddingData=[], PlayerNumbers=[],
             Section=[dict(ID=1, Letter="A", Tables=max(len(d["tables"]) for d in donnes), Winners=2)],
             Session=[dict(ID=1, Name="Séance", Date=f"{a}-{m}-{j}T00:00:00")])
    return T, donnes


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage : python3 -I src/feuille_route.py feuille.pdf sortie.json")
    T, donnes = convertir(sys.argv[1])
    json.dump({"format": "tables Bridgemate (feuille de route FFBClubNet)", "tables": T},
              open(sys.argv[2], "w"), ensure_ascii=False)
    print(f"{len(donnes)} donnes, {sum(len(d['tables']) for d in donnes)} résultats : {sys.argv[2]}")


if __name__ == "__main__":
    main()
