# -*- coding: utf-8 -*-
"""L'onglet Jouer : un joueur enchérit une donne à sa place, le programme tient les trois autres sièges.

Le moteur (encheres.encherir) rejoue la séquence avec les enchères déjà faites (imposees) et s'arrête quand c'est au
joueur (arret) : il dit alors ce que le système lui ferait dire (l'indice). À la fin, le contrat du joueur est comparé
à ceux de l'Expert et du Standard, jugés au double mort. Les essais vont dans <séance>-jeu.json, à côté de la séance :
les analyses ne changent jamais.
"""
import datetime, json, os, re
from encheres import encherir
from bws_extract import score, vul_of, imp

ROT = "NESO"
GRILLE = "ONES"                     # les colonnes des grilles d'enchères des analyses et des rapports
PART = {"N": "S", "S": "N", "E": "O", "O": "E"}
EN = {"SA": "NT", "♠": "S", "♥": "H", "♦": "D", "♣": "C"}
DENOMS = ["♣", "♦", "♥", "♠", "SA"]
camp = lambda s: "NS" if s in "NS" else "EO"


def rang(b):
    return (int(b[0]) - 1) * 5 + DENOMS.index(b[1:])


def sequence(enc, donneur):
    """La séquence depuis le donneur, à partir d'une grille Ouest Nord Est Sud."""
    cases = [c for ligne in enc for c in ligne]
    return [c for c in cases[GRILLE.index(donneur):] if c not in ("", "–")]


def grille(seq, donneur, a_vous=False):
    """La séquence en grille Ouest Nord Est Sud, « ? » à la place de l'enchère attendue."""
    cases = ["–"] * GRILLE.index(donneur) + list(seq) + (["?"] if a_vous else [])
    cases += [""] * (-len(cases) % 4)
    return [cases[i:i + 4] for i in range(0, len(cases), 4)]


def fin(seq):
    return len(seq) >= 4 and (all(x == "passe" for x in seq) or (seq[-3:] == ["passe"] * 3 and any(x != "passe" for x in seq)))


def etat(seq, donneur):
    """(dernière enchère, son siège, contre 0/1/2, siège qui parle maintenant)."""
    dernier = par = None; dbl = 0; i0 = ROT.index(donneur)
    for k, b in enumerate(seq):
        s = ROT[(i0 + k) % 4]
        if b == "contre": dbl = 1
        elif b == "surcontre": dbl = 2
        elif b != "passe": dernier, par, dbl = b, s, 0
    return dernier, par, dbl, ROT[(i0 + len(seq)) % 4]


def legales(seq, donneur):
    """Les enchères possibles maintenant : les paliers au-dessus de la dernière, passe, contre, surcontre."""
    dernier, par, dbl, s = etat(seq, donneur)
    out = {f"{n}{d}" for n in range(1, 8) for d in DENOMS if not dernier or rang(f"{n}{d}") > rang(dernier)}
    out.add("passe")
    if dernier and camp(par) != camp(s) and dbl == 0: out.add("contre")
    if dbl == 1 and camp(par) == camp(s): out.add("surcontre")
    return out


def contrat(seq, donneur):
    """(contrat avec ses X, déclarant) ou ("passe", None) : le déclarant est le premier du camp à avoir nommé la couleur."""
    dernier, par, dbl, _ = etat(seq, donneur)
    if not dernier: return "passe", None
    i0 = ROT.index(donneur)
    decl = next(ROT[(i0 + k) % 4] for k, b in enumerate(seq)
                if b not in ("passe", "contre", "surcontre") and camp(ROT[(i0 + k) % 4]) == camp(par) and b[1:] == dernier[1:])
    return dernier + "X" * dbl, decl


def siege_par_defaut(d, analyses):
    """Le déclarant de la séquence recommandée (l'Expert d'abord, sinon le Standard) ; Sud s'il n'y en a pas."""
    for a in analyses:
        enc = ((a or {}).get("donnes") or {}).get(str(d["n"]), {}).get("enc")
        if enc:
            c, decl = contrat(sequence(enc, d["donneur"]), d["donneur"])
            if decl: return decl
    return "S"


def avancer(d, seq, siege):
    """Le moteur parle jusqu'au tour du joueur ou jusqu'à la fin : (séquence, explications, indice ou None)."""
    if fin(seq): return list(seq), encherir(d, imposees=seq)["explications"][:len(seq)], None
    r = encherir(d, imposees=seq, arret=siege)
    return r["encheres"], r["explications"], (r.get("conseil") if r.get("a_vous") else None)


def resultat(d, c, decl):
    """Levées au double mort, écart (=, +1, −1) et score pour Nord-Sud."""
    if c == "passe": return dict(texte="passe générale", levees=None, marge=0, ns=0)
    n, den, x = int(c[0]), c[1:].rstrip("X"), c.count("X")
    t = d["dm"][den][decl]; m = t - n - 6
    v = score(n, EN[den], x, vul_of(d["vul"], "NS" if decl in "NS" else "EW"), t)
    return dict(texte=f"{c} {decl}", levees=t, marge=m, ns=v if decl in "NS" else -v)


def comparer(d, seq, siege, analyses):
    """Le contrat du joueur face à l'Expert et au Standard : contrat, résultat au double mort, IMP vus du camp du joueur
    face à l'Expert, et la première enchère du joueur qui diffère de la séquence recommandée."""
    c, decl = contrat(seq, d["donneur"])
    moi = resultat(d, c, decl); moi.update(nom="Vous", seq=list(seq))
    lignes = [moi]
    signe = 1 if camp(siege) == "NS" else -1
    for nom, a in zip(("Standard", "Expert"), analyses):
        enc = ((a or {}).get("donnes") or {}).get(str(d["n"]), {}).get("enc")
        if not enc: continue
        s2 = sequence(enc, d["donneur"]); c2, decl2 = contrat(s2, d["donneur"])
        r = resultat(d, c2, decl2); r.update(nom=nom, seq=s2)
        lignes.append(r)
    ref = next((x for x in lignes if x["nom"] == "Expert"), None) or next((x for x in lignes if x["nom"] == "Standard"), None)
    for x in lignes: x["imp"] = signe * imp(moi["ns"] - x["ns"]) if x is not moi else None
    ecart = None                                          # la première enchère où la séquence s'écarte de la référence
    if ref:
        k = next((k for k in range(max(len(seq), len(ref["seq"])))
                  if k >= len(seq) or k >= len(ref["seq"]) or seq[k] != ref["seq"][k]), None)
        if k is not None and k < len(seq) and k < len(ref["seq"]):
            ecart = dict(tour=k, siege=ROT[(ROT.index(d["donneur"]) + k) % 4], vous=seq[k], reference=ref["seq"][k], nom=ref["nom"])
    return dict(lignes=[moi] + [x for x in lignes if x is not moi][::-1], ecart=ecart)


def fichier_jeu(base):
    return base + "-jeu.json"


def lire_essais(base):
    try:
        return json.load(open(fichier_jeu(base), encoding="utf-8"))
    except (OSError, ValueError):
        return {"donnes": {}}


def enregistrer(base, n, siege, seq, donneur):
    """Un essai de plus pour la donne n."""
    x = lire_essais(base)
    c, decl = contrat(seq, donneur)
    x["donnes"].setdefault(str(n), []).append(dict(date=datetime.datetime.now().isoformat(timespec="seconds"),
                                                 siege=siege, encheres=list(seq), contrat=c, declarant=decl))
    json.dump(x, open(fichier_jeu(base), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
