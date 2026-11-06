# -*- coding: utf-8 -*-
"""Règles d'enchères écrites dans systems/<système>/regles.yaml : lecture et application.

    s = charger("systems/sef-2024/regles.yaml")    # erreurs en français, avec le numéro de ligne
    r = s.choisir("ouverture", Main("A765 AX43 A982 3"), position=1)
    r.enchere, r.montre, r.ligne                   # "1♦", "12–21 H, 4+ carreaux", 38
    s.verifier()                                   # les exemples du fichier : [] si tout va bien

Couleurs écrites T K C P (trèfle, carreau, cœur, pique) ou ♣ ♦ ♥ ♠ ; le programme les
convertit en symboles. Format décrit en tête de regles.yaml et dans systems/README.md.
Lancé seul : vérifie le fichier.  python3 -I src/regles.py [systems/sef-2024/regles.yaml]
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from encheres.main import Main

LETTRES = {"T": "♣", "K": "♦", "C": "♥", "P": "♠"}
SYMBOLES = "♣♦♥♠"
OPS = {">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b,
       "<": lambda a, b: a < b, "=": lambda a, b: a == b}


class ErreurRegles(Exception):
    pass


def enchere(texte, ligne=None):
    """'1K' ou '1♦' -> '1♦' ; 'SA', 'passe', 'contre' inchangés."""
    t = str(texte).strip()
    if t in ("passe", "contre", "surcontre"): return t
    m = re.fullmatch(r"([1-7])(SA|[TKCP♣♦♥♠])", t)
    if not m: raise ErreurRegles(f"ligne {ligne} : enchère « {t} » non comprise (ex. 1K, 2SA, passe)")
    return m[1] + LETTRES.get(m[2], m[2])


def _jetons(cle):
    """'1K (1P) contre' -> ['1K', '(1P)', 'contre'] ; tirets et espaces séparent les enchères."""
    return re.findall(r"\(\s*[^)]*?\s*\)|[^\s()\-]+", str(cle))


def sequence(cle, ligne=None):
    """'1K - 1C' -> ('1♦', '1♥') ; '(1K) 1P (2K)' -> ('(1♦)', '1♠', '(2♦)') ; 'ouverture' -> ().
    Entre parenthèses : les enchères adverses (leurs passes sont sous-entendues)."""
    if cle == "ouverture": return ()
    morceaux = _jetons(cle)
    lettres = any(re.search(r"[TKCP]\)?$", x) for x in morceaux)
    symboles = any(re.search(r"[♣♦♥♠]\)?$", x) for x in morceaux)
    if lettres and symboles:
        raise ErreurRegles(f"ligne {ligne} : « {cle} » mélange lettres (T K C P) et symboles")
    out = []
    for x in morceaux:
        if x.startswith("("):
            b = enchere(x[1:-1], ligne)
            if b == "passe": continue                    # passe adverse : sous-entendue
            out.append(f"({b})")
        else:
            out.append(enchere(x, ligne))
    return tuple(out)


def positions(seq, ligne=None):
    """Séquence abrégée -> [(rôle, enchère)] dans l'ordre réel, en rétablissant les passes adverses
    sous-entendues, jusqu'à notre tour. Rôles depuis l'ouverture : U ouvreur, Y intervenant,
    W répondant, Z partenaire de l'intervenant."""
    out, attendu = [], None                              # camp attendu : True = adversaires
    for x in seq:
        eux = x.startswith("(")
        if attendu is None: attendu = eux
        if eux != attendu:
            if not attendu:
                raise ErreurRegles(f"ligne {ligne} : « {' '.join(seq)} » : il manque une enchère de notre camp "
                                   "(écrire « passe »)")
            out.append("(passe)"); attendu = not attendu
        out.append(x); attendu = not attendu
    while attendu:                                       # c'est à nous : passes adverses sous-entendues
        out.append("(passe)"); attendu = False
    return [("UYWZ"[i % 4], x) for i, x in enumerate(out)]


def nue(x):
    """'(1♦)' -> '1♦'."""
    return x[1:-1] if x.startswith("(") else x


# ---------------------------------------------------------------- conditions
JOUEURS = {"U": "l'ouvreur", "W": "le répondant", "Y": "l'intervenant", "Z": "le partenaire de l'intervenant"}
VERS_LETTRE = {v: k for k, v in LETTRES.items()}
TOKEN_JOUEUR = re.compile(r"(?<![A-Za-z])([UWYZ])([MN])?(?![A-Za-z(])")


def couleurs_des_joueurs(seq):
    """Séquence -> {"U": [♦, …], "W": [♥, …], "Y": […], "Z": […]} : les couleurs nommées par
    chacun, dans l'ordre (rôles : voir positions)."""
    out = {j: [] for j in JOUEURS}
    for j, x in positions(seq):
        b = nue(x)
        if b[0].isdigit() and b[1:] in SYMBOLES and b[1:] not in out[j]: out[j].append(b[1:])
    return out


def remplacer_joueurs(texte, roles, ligne, ou):
    """« 2U », « U 3+ », « UM » -> la couleur réelle (lettre T K C P) dans cette séquence."""
    def couleur(m):
        j, sel = m[1], m[2]
        cs = roles[j]
        if sel == "M": cs = [c for c in cs if c in "♥♠"]
        if sel == "N": cs = [c for c in cs if c in "♣♦"]
        if not cs:
            quoi = {"M": " de majeure", "N": " de mineure"}.get(sel, "")
            raise ErreurRegles(f"ligne {ligne} : « {m[0]} » : {JOUEURS[j]} n'a pas nommé de couleur{quoi} "
                               f"dans « {ou} »")
        return VERS_LETTRE[cs[0]]
    return TOKEN_JOUEUR.sub(couleur, str(texte))


def deplier(cle):
    """Clé générique -> clés réelles : « 1M » -> 1C, 1P ; « 1N » -> 1T, 1K ; « 1x » -> 1T, 1K, 1C, 1P
    (aussi entre parenthèses) ; « 1M - 2U » -> 1C - 2C, 1P - 2P (U W Y Z : la couleur de ce joueur,
    nommée plus tôt dans la clé)."""
    if cle == "ouverture": return [cle]
    morceaux = _jetons(cle)
    for i, x in enumerate(morceaux):
        m = re.fullmatch(r"(\(?)([1-7])([MNx])(\)?)", x)
        if m:
            out = []
            for c in {"M": "CP", "N": "TK", "x": "TKCP"}[m[3]]:
                out += deplier(" ".join(morceaux[:i] + [m[1] + m[2] + c + m[4]] + morceaux[i + 1:]))
            return out
    for i, x in enumerate(morceaux):                     # U W Y Z : couleur nommée plus tôt dans la clé
        m = re.fullmatch(r"(\(?)([1-7])([UWYZ])(\)?)", x)
        if m:
            roles = couleurs_des_joueurs(sequence(" ".join(morceaux[:i])))
            if not roles[m[3]]:
                raise ErreurRegles(f"« {cle} » : « {x} » renvoie à une couleur absente de la clé")
            morceaux[i] = m[1] + m[2] + VERS_LETTRE[roles[m[3]][0]] + m[4]
    return [" ".join(morceaux)]


def _couleur(x):
    x = x.strip()
    return LETTRES.get(x, x) if x in LETTRES or x in SYMBOLES else None


def _couleurs(x):
    """'TKCP' -> ['♣', '♦', '♥', '♠'] ; 'P' -> ['♠'] ; None si ce ne sont pas des couleurs."""
    if x and all(c in LETTRES or c in SYMBOLES for c in x) and len(set(x)) == len(x):
        return [LETTRES.get(c, c) for c in x]
    return None


def _zone(t, ligne, quoi):
    """'12+' -> (12, 99) ; '11-' -> (0, 11) ; '6-10' -> (6, 10) ; '11' ou '11=' -> (11, 11)."""
    m = re.fullmatch(r"(\d+)\s*(\+|=|-\s*(\d+)|-)?", t.strip())
    if not m: raise ErreurRegles(f"ligne {ligne} : « {quoi} {t} » : attendu 12+, 11-, 6-10 ou 11")
    lo = int(m[1])
    if m[2] == "+": return lo, 99
    if m[2] == "-": return 0, lo
    return (lo, int(m[3])) if m[3] else (lo, lo)


def _valeur(nom, main):
    if nom in ("majeure", "M"): return max(main.L["♠"], main.L["♥"])
    if nom in ("mineure", "N", "m"): return max(main.L["♦"], main.L["♣"])
    return main.L[_couleur(nom)]


def hld_detail(main, atout):
    """(HLD, H, points des courtes, points des atouts en plus) : voir hld."""
    courtes = sum({0: 3, 1: 2, 2: 1}.get(main.L[c], 0) for c in SYMBOLES if c != atout)
    coupe = any(main.L[c] <= 1 for c in SYMBOLES if c != atout)
    atouts = max(0, main.L[atout] - 3) if coupe else 0
    return main.hcp + courtes + atouts, main.hcp, courtes, atouts


def hld(main, atout):
    """Points pour soutenir la couleur atout (systems/grammaire.md, HLD) : H + courtes hors atout
    (chicane 3, singleton 2, doubleton 1) + 1 par atout au-delà du 3e, seulement avec un singleton
    ou une chicane, c'est-à-dire quand le mort peut couper (pas pour un simple doubleton)."""
    courtes = sum({0: 3, 1: 2, 2: 1}.get(main.L[c], 0) for c in SYMBOLES if c != atout)
    coupe = any(main.L[c] <= 1 for c in SYMBOLES if c != atout)
    return main.hcp + courtes + (max(0, main.L[atout] - 3) if coupe else 0)


def sans_accents(t):
    import unicodedata
    return "".join(x for x in unicodedata.normalize("NFD", t) if unicodedata.category(x) != "Mn")


MOTS = {"reguliere": "reg", "irreguliere": "irreg", "reg": "reg", "irreg": "irreg",
        "regle des 20": "règle des 20", "regle des 15": "règle des 15",
        "majeure": "M", "mineure": "N"}


def _mot(c):
    """Mot-clé sans accents ni majuscules inutiles : « Régulière » -> « reg »."""
    return MOTS.get(sans_accents(c).lower(), c)


class Condition:
    """« H 12+, P 5+ || HL 25+ » : virgule = et, || (ou « ou ») = ou, parenthèses pour grouper.
    Points : H, HL, HLD (HLD(P) : avec P pour atout ; sans couleur, celle de l'enchère).
    Une condition = un contexte puis une seule zone : couleurs (T K C P, une ou plusieurs ;
    M / m : la plus longue majeure / mineure) ou points. Zones : 5+ (au moins), 1- (au plus),
    1 ou 1= (exactement), 0-3 (de 0 à 3) ; ! devant la zone : le contraire, pour chaque couleur
    citée (TKCP !1- : aucun singleton ni chicane). non devant une condition : son contraire."""

    def __init__(self, texte, definitions, ligne, atout=None, dernier=-1):
        self.texte, self.ligne, self.atout, self.dernier = texte or "", ligne, atout, dernier
        self.arbre = self._arbre(self.texte, definitions)

    def _arbre(self, texte, defs):
        """« H 20+, (C 9+ || P 9+) » -> arbre : virgule = et, || (ou « ou ») = ou (plus faible),
        parenthèses pour grouper, « non » devant une condition ou une parenthèse."""
        texte = re.sub(r"\b(HLD|HL|H|palier|honneurs|fit)\(\s*([^)\s]+)\s*\)", r"\1[\2]", texte)   # HLD(P) n'est pas un groupe
        toks = [("ou" if t.strip() == "||" else t.strip())
                for t in re.split(r"(\(|\)|,|\|\||\bou\b)", texte) if t.strip()]
        pos = [0]
        voir = lambda: toks[pos[0]] if pos[0] < len(toks) else None
        def prendre(): pos[0] += 1; return toks[pos[0] - 1]
        def expr():
            n = [et()]
            while voir() == "ou": prendre(); n.append(et())
            return ("ou", n) if len(n) > 1 else n[0]
        def et():
            n = [terme()]
            while voir() == ",": prendre(); n.append(terme())
            return ("et", n) if len(n) > 1 else n[0]
        def terme():
            t = voir()
            if t == "(":
                prendre(); n = expr()
                if voir() != ")": raise ErreurRegles(f"ligne {self.ligne} : « {texte} » : parenthèse non fermée")
                prendre(); return n
            if t is None or t in (")", ",", "ou"):
                raise ErreurRegles(f"ligne {self.ligne} : « {texte} » : condition manquante"
                                   + (f" avant « {t} »" if t else " en fin de ligne"))
            prendre()
            if sans_accents(t).lower() == "non": return ("non", terme())
            return ("c", self._clause(t, defs))
        if not toks: return ("et", [])
        n = expr()
        if voir() is not None:
            raise ErreurRegles(f"ligne {self.ligne} : « {texte} » : « {voir()} » en trop (parenthèse fermante ?)")
        return n

    def _clause(self, c, defs):
        ligne = self.ligne
        if sans_accents(c).startswith("non "):
            f = self._clause(c[4:].strip(), defs); return ("non", lambda m, ctx: not f[1](m, ctx), None)
        nom = next((k for k in defs if sans_accents(k) == sans_accents(c)), None)
        if nom:
            sous = defs[nom]; return ("déf", lambda m, ctx: sous.vraie(m, ctx), sous)
        c = re.sub(r"^\S+", lambda m: _mot(m[0]), c) if " " in c else _mot(c)
        c = _mot(c) if sans_accents(c).lower().startswith("regle des") else c
        m = re.fullmatch(r"([TKCP♣♦♥♠])\s+est\s+([TKCP♣♦♥♠])", c)    # Y est C : couleur de ce joueur
        if m:
            vrai = _couleur(m[1]) == _couleur(m[2]); return ("fixe", lambda mm, ctx: vrai, None)
        m = re.fullmatch(r"honneurs\[([TKCP♣♦♥♠])\]\s*([!\d].*)", c)  # honneurs (A R D V X) dans la couleur
        if m:
            k = _couleur(m[1]); neg = m[2].startswith("!")
            lo, hi = _zone(m[2].lstrip("!").strip(), ligne, "honneurs")
            return ("honneurs", lambda mm, ctx: (lo <= sum(x in "ARDVX" for x in mm.cartes[k]) <= hi) != neg, None)
        m = re.fullmatch(r"palier\[([TKCP♣♦♥♠]|SA)\]\s*([!\d].*)", c)  # palier le plus bas dans la séquence
        if m:
            d = "SA" if m[1] == "SA" else _couleur(m[1])
            n = palier_libre(d, self.dernier)
            neg = m[2].startswith("!"); lo, hi = _zone(m[2].lstrip("!").strip(), ligne, "palier")
            vrai = (lo <= n <= hi) != neg; return ("fixe", lambda mm, ctx: vrai, None)
        m = re.fullmatch(r"(arret|bonne)\s+([TKCP♣♦♥♠])", sans_accents(c))
        if m:
            k = _couleur(m[2])
            if m[1] == "arret":                          # A, Rx, Dxx, Vxxx
                return ("arret", lambda mm, ctx: (lambda p: "A" in p or ("R" in p and len(p) >= 2) or
                        ("D" in p and len(p) >= 3) or ("V" in p and len(p) >= 4))(mm.cartes[k]), None)
            return ("bonne", lambda mm, ctx: mm.L[k] >= 6 or (mm.L[k] >= 5 and
                    sum(x in "ARDVX" for x in mm.cartes[k]) >= 2), [(k, 5)])
        m = re.fullmatch(r"fit\[([TKCP♣♦♥♠])\]\s*([!\d].*)", c)    # mes cartes + celles que le partenaire a montrées
        if m:
            k = _couleur(m[1]); neg = m[2].startswith("!")
            lo, hi = _zone(m[2].lstrip("!").strip(), ligne, "fit")
            return ("fit", lambda mm, ctx: (lo <= mm.L[k] + (ctx.get("partenaire") or {}).get("L", {}).get(k, 0) <= hi) != neg, None)
        m = re.fullmatch(r"camp\s+(HLD|HL|H)(?:\[([TKCP♣♦♥♠])\])?\s*([!\d].*)", c)   # mes points + le minimum du partenaire
        if m:
            atout = _couleur(m[2]) if m[2] else self.atout
            if m[1] == "HLD" and not atout:
                raise ErreurRegles(f"ligne {ligne} : « {c} » : préciser l'atout, par exemple camp HLD(P)")
            val = {"H": lambda mm: mm.hcp, "HL": lambda mm: mm.hl, "HLD": lambda mm: hld(mm, atout)}[m[1]]
            neg = m[3].startswith("!"); lo, hi = _zone(m[3].lstrip("!").strip(), ligne, "camp")
            return ("camp", lambda mm, ctx: (lo <= val(mm) + (ctx.get("partenaire") or {}).get("H", 0) <= hi) != neg, None)
        m = re.fullmatch(r"levees\s*([!\d].*)", sans_accents(c))   # levées de jeu (main.levees)
        if m:
            neg = m[1].startswith("!"); lo, hi = _zone(m[1].lstrip("!").strip(), ligne, "levées")
            return ("levees", lambda mm, ctx: (lo <= mm.levees() <= hi) != neg, None)
        m = re.fullmatch(r"([NV])([NV])", c)                   # NN NV VN VV : nous puis eux, N non vulnérable, V vulnérable
        if m:
            nous, eux = m[1] == "V", m[2] == "V"
            return ("vul", lambda mm, ctx: (("nous" in (ctx.get("vul") or ())) == nous
                                            and ("eux" in (ctx.get("vul") or ())) == eux), None)
        m = re.fullmatch(r"vul\s+(nous|eux)", sans_accents(c).lower())   # vulnérabilité de notre camp / du leur
        if m:
            k = m[1]; return ("vul", lambda mm, ctx: k in (ctx.get("vul") or ()), None)
        if c == "reg": return ("forme", lambda m, ctx: m.reguliere, "reg")
        if c == "irreg": return ("forme", lambda m, ctx: not m.reguliere, None)
        if c == "règle des 20": return ("règle", lambda m, ctx: m.regle_des_20(), None)
        if c == "règle des 15": return ("règle", lambda m, ctx: m.hcp + m.L["♠"] >= 15, None)
        m = re.fullmatch(r"forme\s+(\d)-(\d)-(\d)-(\d)", c)
        if m:
            f = sorted(map(int, m.groups()), reverse=True)
            if sum(f) != 13: raise ErreurRegles(f"ligne {ligne} : « {c} » : la forme doit faire 13 cartes")
            return ("forme", lambda mm, ctx: mm.forme == f, None)
        # somme de longueurs : « M+m 9+ », « P + C 8+ » (une couleur ou M / m de chaque côté du +)
        m = re.fullmatch(r"(\S+(?:\s*\+\s*\S+)+)\s+([!\d].*)", c)
        if m:
            parts = [x.strip() for x in m[1].split("+")]
            if not all(_couleur(x) or x in ("M", "N", "m") for x in parts):
                raise ErreurRegles(f"ligne {ligne} : « {c} » : une somme s'écrit avec des couleurs, M ou N (ex. M+N 9+)")
            if len(m[2].split()) > 1:
                raise ErreurRegles(f"ligne {ligne} : « {c} » : une seule zone par condition")
            neg = m[2].startswith("!"); lo, hi = _zone(m[2].lstrip("!").strip(), ligne, m[1])
            return ("longueur", lambda mm, ctx: (lo <= sum(_valeur(x, mm) for x in parts) <= hi) != neg, None)
        # une condition = un contexte puis une seule zone, avec ! possible :
        #   couleurs (T K C P, une ou plusieurs ; M, m) : TKCP !1-   points (H, HL, HLD) : H 12+
        m = re.fullmatch(r"S\s*([!\d].*)", c)                 # siège : S1, S 1-2, S 3+
        if m: c = "position " + m[1]
        m = re.fullmatch(r"(HLD|HL|H)(?:\[([TKCP♣♦♥♠])\])?\s*([!\d].*)|([TKCP♣♦♥♠]+|M|N|m)\s*([!\d].*)", c)
        if m and (m[1] or _couleurs(m[4]) or m[4] in ("M", "N", "m")):
            ctxt, z = (m[1], m[3]) if m[1] else (m[4], m[5])
            if len(z.split()) > 1:
                raise ErreurRegles(f"ligne {ligne} : « {c} » : une seule zone par condition ; "
                                   f"écrire par exemple « {ctxt} !1-, {ctxt} !6+ »")
            neg = z.startswith("!"); lo, hi = _zone(z.lstrip("!").strip(), ligne, ctxt)
            dans = (lambda v: not lo <= v <= hi) if neg else (lambda v: lo <= v <= hi)
            if m[1]:                                      # points
                atout = _couleur(m[2]) if m[2] else self.atout
                if ctxt == "HLD" and not atout:
                    raise ErreurRegles(f"ligne {ligne} : « {c} » : préciser l'atout, par exemple HLD(P)")
                if ctxt == "H" and m[2]:                  # H(K) : les points d'honneur de cette couleur
                    k = _couleur(m[2])
                    return ("points", lambda mm, ctx: dans(sum({"A": 4, "R": 3, "D": 2, "V": 1}.get(x, 0) for x in mm.cartes[k])), None)
                val = {"H": lambda mm: mm.hcp, "HL": lambda mm: mm.hl,
                       "HLD": lambda mm: hld(mm, atout)}[ctxt]
                return ("points", lambda mm, ctx: dans(val(mm)), None if neg else (ctxt, lo, min(hi, 37)))
            if ctxt in ("M", "N", "m"):
                return ("longueur", lambda mm, ctx: dans(_valeur(ctxt, mm)), None)
            cs = _couleurs(ctxt)                          # chaque couleur citée respecte la zone
            mini = (hi + 1 if lo == 0 else 0) if neg else lo
            return ("longueur", lambda mm, ctx: all(dans(mm.L[k]) for k in cs), [(k, mini) for k in cs] if mini else None)
        m = re.fullmatch(r"position\s+(.+)", c)
        if m:
            lo, hi = _zone(m[1], ligne, "position")
            return ("position", lambda mm, ctx: lo <= (ctx.get("position") or 1) <= hi, None)
        m = re.fullmatch(r"(\S+)\s*(>=|<=|>|<|=)\s*(\S+)", c)
        if m and all(_couleur(x) or x in ("majeure", "mineure", "M", "N", "m") for x in (m[1], m[3])):
            a, op, b = m[1], OPS[m[2]], m[3]
            return ("compare", lambda mm, ctx: op(_valeur(a, mm), _valeur(b, mm)), None)
        raise ErreurRegles(f"ligne {ligne} : condition « {c} » non comprise")

    def vraie(self, main, ctx, n=None):
        n = n or self.arbre
        if n[0] == "c": return n[1][1](main, ctx)
        if n[0] == "non": return not self.vraie(main, ctx, n[1])
        if n[0] == "ou": return any(self.vraie(main, ctx, x) for x in n[1])
        return all(self.vraie(main, ctx, x) for x in n[1])

    def montre(self, n=None):
        """Ce que la condition garantit, pour lire les enchères :
        {"pts": (min, max), "L": {couleur: min}, "reg": bool} ; les points sont les H, sinon HL ou HLD
        (« ou » : le plus large des cas ; « non » : rien de sûr)."""
        n = n or self.arbre
        vide = {"pts": None, "L": {}, "reg": False}
        if n[0] == "c":
            genre, _, info = n[1]
            if genre == "points" and info: return {"pts": (info[1], info[2]), "L": {}, "reg": False, "sorte": info[0]}
            if genre == "longueur" and info: return {"pts": None, "L": {k: v for k, v in info}, "reg": False}
            if genre == "forme" and info == "reg": return dict(vide, reg=True)
            if genre == "déf" and info: return info.montre()
            return vide
        if n[0] == "non" or not n[1]: return vide
        parts = [self.montre(x) for x in n[1]]
        if n[0] == "ou":
            pts = None if any(p["pts"] is None for p in parts) else \
                (min(p["pts"][0] for p in parts), max(p["pts"][1] for p in parts))
            return {"pts": pts, "reg": all(p["reg"] for p in parts),
                    "L": {c: min(p["L"].get(c, 0) for p in parts) for c in SYMBOLES
                          if min(p["L"].get(c, 0) for p in parts)}}
        L = {}
        for p in parts:
            for c, v in p["L"].items(): L[c] = max(L.get(c, 0), v)
        zones = [p for p in parts if p["pts"]]
        meilleur = [p for p in zones if p.get("sorte") == "H"] or zones   # les H d'abord
        pts = (max(p["pts"][0] for p in meilleur), min(p["pts"][1] for p in meilleur)) if meilleur else None
        return {"pts": pts, "L": L, "reg": any(p["reg"] for p in parts)}


class Regle:
    def __init__(self, enchere, condition, montre, source, note, ligne):
        self.enchere, self.condition, self.montre = enchere, condition, montre
        self.source, self.note, self.ligne = source, note, ligne
        self.nature = ""; self.atout = None


def palier_libre(d, dernier):
    """Le palier le plus bas où nommer d (« ♠ » ou « SA ») après l'enchère de rang dernier (8 : impossible)."""
    return next((n for n in range(1, 8) if rang(f"{n}{d}") > dernier), 8)


def relatives(b, dernier):
    """« *P » -> le palier le plus bas à pique ; « *P+1 » -> avec un saut ; None si impossible."""
    m = re.fullmatch(r"\*([TKCP♣♦♥♠]|SA)(?:\+(\d))?", str(b).strip())
    if not m: return b
    d = "SA" if m[1] == "SA" else _couleur(m[1])
    n = palier_libre(d, dernier) + int(m[2] or 0)
    return f"{n}{VERS_LETTRE.get(d, d)}" if n <= 7 else None


def rang(b):
    """'1♣' -> 0 … '7SA' -> 34 ; passe, contre -> -1."""
    if not b[0].isdigit(): return -1
    return (int(b[0]) - 1) * 5 + ["♣", "♦", "♥", "♠", "SA"].index(b[1:])


class Systeme:
    def __init__(self, nom, sequences, exemples, chemin):
        self.nom, self.sequences, self.exemples, self.chemin = nom, sequences, exemples, chemin

    def choisir(self, seq, main, position=None, vul=(), partenaire=None):
        """Première règle de la séquence (« ouverture », « 1K - 1C » ou un tuple) vraie pour la main.
        vul : les camps vulnérables vus du joueur, parmi « nous » et « eux » ;
        partenaire : ce qu'il a montré, {"H": minimum de points, "L": {couleur: longueur minimale}}."""
        return next(iter(self.toutes(seq, main, position, vul, partenaire)), None)

    def toutes(self, seq, main, position=None, vul=(), partenaire=None):
        """Les règles vraies pour la main, dans l'ordre du fichier (enchères impossibles écartées) :
        la première est choisie, les suivantes sont les autres enchères possibles."""
        cle = seq if isinstance(seq, tuple) else sequence(seq)
        if cle not in self.sequences: return []
        dernier = max((rang(nue(b)) for b in cle), default=-1)
        return [r for r in self.sequences[cle]
                if not (r.enchere[0].isdigit() and rang(r.enchere) <= dernier)
                and r.condition.vraie(main, {"position": position, "vul": vul, "partenaire": partenaire})]

    def verifier(self):
        """Les exemples du fichier : liste des écarts (vide si tout va bien)."""
        out = []
        for cle, ex in self.exemples:
            for e in ex:
                v = {"nous": ("nous",), "eux": ("eux",), "tous": ("nous", "eux"), "VN": ("nous",), "NV": ("eux",),
                     "VV": ("nous", "eux")}.get(e.get("vul"), ())
                pos = e.get("position", 1 if cle == "ouverture" else 3)   # sans siège : une réponse ordinaire (pas une main passée)
                r = self.choisir(cle, Main(e["main"]), pos, v, montre_texte(e.get("partenaire")))
                obtenu = r.enchere if r else "aucune règle"
                if obtenu != e["attendu"]:
                    out.append(f"ligne {e['ligne']} : {e['main']} après « {' - '.join(cle) or 'ouverture'} » : "
                               f"{e['attendu']} attendu, {obtenu} obtenu"
                               + (f" (règle ligne {r.ligne})" if r else ""))
        return out


def montre_texte(texte):
    """« H 12, C 5 » (exemples) -> {"H": 12, "L": {"♥": 5}} : ce que le partenaire a montré."""
    out = {"H": 0, "L": {}}
    for x in str(texte or "").split(","):
        if not x.strip(): continue
        nom, n = x.split()
        if nom == "H": out["H"] = int(n)
        else: out["L"][_couleur(nom)] = int(n)
    return out


def charger(chemin):
    """Lit regles.yaml. Les tabulations en début de ligne sont remplacées par deux espaces ;
    toute erreur est signalée en français avec son numéro de ligne."""
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError
    texte = open(chemin, encoding="utf-8").read()
    texte = "\n".join(re.sub(r"^\t+", lambda m: "  " * len(m[0]), l) for l in texte.split("\n"))
    try:
        doc = YAML().load(texte)
    except YAMLError as ex:
        mark = getattr(ex, "problem_mark", None)
        ou = f"ligne {mark.line + 1}, colonne {mark.column + 1}" if mark else "position inconnue"
        raise ErreurRegles(f"{os.path.basename(chemin)}, {ou} : {getattr(ex, 'problem', None) or ex}") from None
    cle_defs = next((k for k in doc if sans_accents(str(k)) == "definitions"), None)
    defs_txt = doc.get(cle_defs) or {} if cle_defs else {}
    def definitions(roles, ou, dernier):
        """Les définitions de cette séquence (U W Y Z remplacés), dans l'ordre du fichier."""
        defs = {}
        for nom in defs_txt:
            lg = defs_txt.lc.key(nom)[0] + 1
            try:
                texte = remplacer_joueurs(defs_txt[nom], roles, lg, ou)
            except ErreurRegles:
                continue                                  # sans objet dans cette séquence (Y absent…)
            defs[nom] = Condition(texte, defs, lg, None, dernier)
        return defs
    definitions({j: ["♣"] for j in JOUEURS}, "", -1)    # vérifie la syntaxe une fois
    sequences, exemples, origine = {}, [], {}
    for cle in doc:
        if cle in ("systeme", cle_defs): continue
        ligne_cle = doc.lc.key(cle)[0] + 1
        cles = [x for k in str(cle).split("|") for x in deplier(k.strip())]   # « a | b » : plusieurs clés
        for cle_reelle in cles:                          # « 1M » vaut pour 1C et 1P
            seq = sequence(cle_reelle, ligne_cle)
            rangs = [rang(nue(x)) for x in seq if rang(nue(x)) >= 0]
            if len(cles) > 1 and any(b <= a for a, b in zip(rangs, rangs[1:])):
                continue                                  # combinaison impossible d'une clé générique
            if seq in sequences:
                raise ErreurRegles(f"ligne {ligne_cle} : séquence « {cle_reelle} » déjà décrite ligne {origine[seq]}")
            origine[seq] = ligne_cle
            roles = couleurs_des_joueurs(seq)
            dernier = max((rang(nue(x)) for x in seq), default=-1)
            defs = definitions(roles, cle_reelle, dernier)
            regles, exs = [], []
            for i, item in enumerate(doc[cle]):
                ligne = doc[cle].lc.item(i)[0] + 1
                if not hasattr(item, "items") or len(item) != 1:
                    raise ErreurRegles(f"ligne {ligne} : une règle par ligne, sous la forme  - 1K: {{ si: \"...\" }}")
                (b, v), = item.items()
                if b == "exemples":
                    for j, ex in enumerate(v):
                        lj = v.lc.item(j)[0] + 1
                        if "apres" in ex and sequence(ex["apres"], lj) != seq: continue
                        exs.append(dict(ex, attendu=enchere(remplacer_joueurs(ex["attendu"], roles, lj, cle_reelle), lj),
                                        ligne=lj))
                    continue
                v = v or {}
                inconnues = set(v) - {"si", "montre", "source", "note", "voir", "nom", "apres", "nature", "atout"}
                if inconnues: raise ErreurRegles(f"ligne {ligne} : clé inconnue « {', '.join(inconnues)} »")
                if "apres" in v and seq not in [sequence(x, ligne) for x in str(v["apres"]).split("|")]:
                    continue                              # règle réservée à d'autres séquences (« apres: 1P »)
                b = relatives(remplacer_joueurs(b, roles, ligne, cle_reelle), dernier)
                if b is None: continue                    # au-delà du palier de 7
                e = enchere(b, ligne)
                atout = e[1:] if e[0].isdigit() and e[1:] != "SA" else None
                si = remplacer_joueurs(v.get("si") or "", roles, ligne, cle_reelle)
                r = Regle(e, Condition(si, defs or {}, ligne, atout, dernier), v.get("montre", ""),
                          v.get("source", "SEF"), v.get("note"), ligne)
                r.nature = v.get("nature", "")
                r.atout = _couleur(remplacer_joueurs(v["atout"], roles, ligne, cle_reelle)) if v.get("atout") else None
                regles.append(r)
            sequences[seq] = regles
            exemples.append((seq, exs))
    return Systeme(doc.get("systeme"), sequences, exemples, chemin)


if __name__ == "__main__":
    chemin = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "systems", "sef-2024", "regles.yaml")
    try:
        s = charger(chemin)
    except ErreurRegles as ex:
        raise SystemExit(f"ERREUR : {ex}")
    n = sum(len(r) for r in s.sequences.values()); k = sum(len(e) for _, e in s.exemples)
    ecarts = s.verifier()
    print(f"{s.nom} : {len(s.sequences)} séquences, {n} règles, {k} exemples, {len(ecarts)} écart(s)")
    for e in ecarts: print("  ", e)
