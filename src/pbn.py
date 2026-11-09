# -*- coding: utf-8 -*-
"""Lit un fichier PBN (Portable Bridge Notation) et en fait une séance Bridge Coach, comme un entraînement : les mains,
le donneur et la vulnérabilité de chaque donne ; le double mort, les points et le par sont calculés (donnes.donne_complete).
Quand le fichier donne aussi le contrat, le déclarant et le résultat (et les enchères, l'entame), la donne garde cette
table jouée, avec son score et son écart au par.

    seance(chemin) -> les données d'une séance (session, donnes, paires, alertes), que rapport.py range en .bc.json

Ce qui est lu : [Board] [Dealer] [Vulnerable] [Deal] [Date] [Event], et [Auction] [Contract] [Declarer] [Result] [Play]
(la première carte : l'entame). Les notes (=1=), les commentaires ({…}, ;…) et les autres balises sont ignorés.
"""
import datetime, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SIEGES = "NESO"
DE_PBN = {"N": "N", "E": "E", "S": "S", "W": "O"}
VUL = {"none": "Personne", "love": "Personne", "-": "Personne", "ns": "N-S", "ew": "E-O", "all": "Tous", "both": "Tous"}
RANG = str.maketrans({"K": "R", "Q": "D", "J": "V", "T": "X"})
COUL = {"S": "♠", "H": "♥", "D": "♦", "C": "♣", "NT": "SA", "N": "SA"}


class ErreurPBN(ValueError):
    pass


def _blocs(texte):
    """Les donnes du fichier : [(balises {nom: valeur}, sections {nom: lignes qui suivent la balise})]."""
    texte = re.sub(r"\{[^}]*\}", " ", texte)                  # commentaires {…}
    blocs, tags, sections, courante = [], {}, {}, None
    for ligne in texte.splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("%") or ligne.startswith(";"):
            if not ligne and tags:                           # une ligne vide sépare deux donnes
                blocs.append((tags, sections)); tags, sections, courante = {}, {}, None
            continue
        m = re.match(r'\[(\w+)\s+"([^"]*)"\]', ligne)
        if m:
            nom, val = m[1], m[2]
            if nom == "Board" and "Board" in tags:            # une nouvelle donne sans ligne vide avant
                blocs.append((tags, sections)); tags, sections = {}, {}
            tags[nom] = val; courante = nom; sections.setdefault(nom, [])
        elif courante:
            sections[courante].append(ligne)
    if tags: blocs.append((tags, sections))
    return [b for b in blocs if "Deal" in b[0]]


def mains_de(deal):
    """« N:AKQ.xx.x.x … » -> {siège: « ♠ ♥ ♦ ♣ » en rangs français}. Une main inconnue (« - ») est complétée si c'est la
    seule qui manque."""
    m = re.match(r"\s*([NESW]):(.*)", deal)
    if not m: raise ErreurPBN(f"donne illisible : {deal}")
    depart = SIEGES.index(DE_PBN[m[1]]); parties = m[2].split()
    if len(parties) != 4: raise ErreurPBN(f"il faut quatre mains : {deal}")
    mains = {}
    for k, p in enumerate(parties):
        s = SIEGES[(depart + k) % 4]
        if p == "-": mains[s] = None; continue
        couleurs = p.replace("10", "T").split(".")
        if len(couleurs) != 4: raise ErreurPBN(f"main illisible : {p}")
        mains[s] = [c.upper() for c in couleurs]
    manque = [s for s, x in mains.items() if x is None]
    if len(manque) == 1:                                     # la main qui manque : les cartes qui restent
        mains[manque[0]] = ["".join(r for r in "AKQJT98765432" if r not in "".join(x[i] for x in mains.values() if x))
                            for i in range(4)]
    elif manque: raise ErreurPBN("plusieurs mains manquent")
    out = {}
    for s in SIEGES:
        x = mains[s]
        if sum(len(c) for c in x) != 13: raise ErreurPBN(f"la main de {s} n'a pas 13 cartes")
        out[s] = " ".join(("".join(sorted(c, key="AKQJT98765432".index)).translate(RANG)) or "-" for c in x)
    toutes = sorted(c + r for s in SIEGES for c, x in zip("SHDC", mains[s]) for r in x)
    if len(set(toutes)) != 52: raise ErreurPBN("une carte est en double ou manque")
    return out


def appel(x):
    """Une enchère PBN en français : « 1NT » -> « 1SA », « 2S » -> « 2♠ », Pass, X, XX ; None pour une note."""
    x = x.strip().upper().rstrip("!?")
    if not x or x.startswith("=") or x.startswith("$") or x in ("*", "+", "-"): return None
    if x in ("PASS", "P"): return "passe"
    if x == "X": return "contre"
    if x == "XX": return "surcontre"
    m = re.fullmatch(r"([1-7])(NT|N|S|H|D|C)", x)
    return m[1] + COUL[m[2]] if m else None


def fini(seq):
    """La séquence est-elle terminée : quatre passes, ou trois passes après une enchère ?"""
    return (len(seq) == 4 and all(x == "passe" for x in seq)) or \
        (len(seq) >= 4 and any(x != "passe" for x in seq) and seq[-3:] == ["passe"] * 3)


def encheres(lignes, donneur, debut):
    """Les enchères depuis le donneur ; « AP » : tout le monde passe. [Auction] doit partir du donneur."""
    if debut and debut != donneur: return []
    out = []
    for t in " ".join(lignes).split():
        if t.upper() == "AP":
            while not fini(out): out.append("passe")
            break
        a = appel(t)
        if a: out.append(a)
        if fini(out): break
    return out if fini(out) else []


def contrat(c):
    """« 4S » « 3NTX » « 2HXX » -> « 4♠ », « 3SAX »… ; None si Pass ou illisible."""
    c = (c or "").strip().upper()
    m = re.fullmatch(r"([1-7])(NT|N|S|H|D|C)(X{0,2})", c)
    return m[1] + COUL[m[2]] + m[3] if m else None


def carte(x):
    """« SK » -> « ♠R », « H10 » -> « ♥X »."""
    x = x.strip().upper().replace("10", "T")
    m = re.fullmatch(r"([SHDC])([AKQJT2-9])", x)
    return COUL[m[1]] + m[2].translate(RANG) if m else ""


def seance(chemin):
    """Les données d'une séance à partir du PBN (pour rapport.py)."""
    import donnes as dn
    from bws_extract import score, imp, vul_of
    texte = open(chemin, encoding="latin-1").read()          # le PBN est en ASCII ou ISO-8859-1
    blocs = _blocs(texte)
    if not blocs: raise ErreurPBN("aucune donne trouvée dans ce fichier PBN")
    out, date, titre = [], None, None
    for k, (tags, sections) in enumerate(blocs, 1):
        try:
            n = int(re.sub(r"\D", "", tags.get("Board", "")) or k)
        except ValueError:
            n = k
        mains = mains_de(tags["Deal"])
        donneur = DE_PBN.get(tags.get("Dealer", "").strip().upper()[:1]) or SIEGES[(n - 1) % 4]
        vul = VUL.get(tags.get("Vulnerable", "").strip().lower()) or dn.VUL16[(n - 1) % 16]
        d = dn.donne_complete(n, "PBN", mains, True, donneur, vul)
        d.pop("theme", None)
        date = date or re.match(r"(\d{4})\.(\d\d)\.(\d\d)", tags.get("Date", "") or "")
        titre = titre or (tags.get("Event") or "").strip("? ")
        c = contrat(tags.get("Contract")); decl = DE_PBN.get(tags.get("Declarer", "").strip().upper()[:1])
        res = tags.get("Result", "").strip()
        if c and decl and res.isdigit():                     # une table jouée : contrat, résultat, enchères, entame
            niv, den, x = int(c[0]), c[1:].rstrip("X"), c.count("X")
            lev = int(res); need = niv + 6
            camp = "NS" if decl in "NS" else "EW"
            v = score(niv, {"SA": "NT", "♠": "S", "♥": "H", "♦": "D", "♣": "C"}[den], x, vul_of(vul, camp), lev)
            ns = v if camp == "NS" else -v
            enc = encheres(sections.get("Auction", []), donneur, DE_PBN.get(tags.get("Auction", "").strip().upper()[:1]))
            jeu = " ".join(sections.get("Play", [])).split()
            t = dict(paire_ns="", paire_eo="", nom_ns="", nom_eo="", encheres=enc, encheres_ok=bool(enc),
                     encheres_msg="" if enc else "enchères non enregistrées", table=1, contrat=c, declarant=decl,
                     resultat="=" if lev == need else f"{lev - need:+d}", entame=carte(jeu[0]) if jeu else "",
                     levees=lev, dm=d["dm"][den][decl], score_ns=ns, pct_ns=50.0,
                     ecart_par_imp=imp(ns - d["par"]["score_ns"]), imp_ns=0)
            d["tables"] = [t]
        out.append(d)
    out.sort(key=lambda x: x["n"])
    if len({d["n"] for d in out}) != len(out): raise ErreurPBN("deux donnes portent le même numéro")
    jour = (datetime.date(int(date[1]), int(date[2]), int(date[3])) if date else
            datetime.date.fromtimestamp(os.path.getmtime(chemin)))
    session = dict(date=jour.strftime("%d/%m/%Y"), tables=max(len(d["tables"]) for d in out), sections=["A"],
                   mitchell=False, themes=[])
    if titre: session["titre"] = titre
    return dict(session=session, donnes=out, paires={}, alertes=[])


if __name__ == "__main__":
    import json
    print(json.dumps(seance(sys.argv[1]), ensure_ascii=False, indent=1)[:3000])
