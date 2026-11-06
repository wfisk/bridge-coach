# -*- coding: utf-8 -*-
"""Règles d'entame lues dans systems/<système>/entames.yaml (même syntaxe de conditions que
regles.yaml : virgule, ||, non, parenthèses), appliquées par jeu.entame_regle.

    from entames import charger
    e = charger("systems/sef-2024/entames.yaml")
    e.entame("D3 X642 V8743 X2", "♠", partenaire=["♥"])   # -> ("♥2", "dans la couleur du partenaire")
"""
import re
from regles import Condition, ErreurRegles, _zone, _couleur, sans_accents

COULEURS = "♠♥♦♣"
HON = "ARDVX"


def tete_de_sequence(p):
    """La première carte de deux honneurs qui se suivent (AR, RD, DV, VX), ou None."""
    for i in range(len(p) - 1):
        if p[i] in HON and p[i + 1] in HON and HON.index(p[i + 1]) == HON.index(p[i]) + 1:
            return p[i]
    return None


def honneur(p):
    """Un honneur dans la couleur : A R D V, et le X avec 4 cartes ou plus."""
    return any(x in ("ARDV" if len(p) <= 3 else "ARDVX") for x in p)


class ConditionEntame(Condition):
    """Condition sur une couleur candidate. ctx : {"p": cartes de la couleur, "c": la couleur,
    "partenaire": [...], "adverses": [...], "atouts": longueur à l'atout}."""

    def _clause(self, c, defs):
        ligne = self.ligne
        t = sans_accents(c).lower().strip()
        if t.startswith("non "):
            f = self._clause(c.strip()[4:], defs); return ("non", lambda m, x: not f[1](m, x), None)
        mots = {"partenaire": lambda m, x: x["c"] in x["partenaire"],
                "atout": lambda m, x: x["c"] == x.get("den"),
                "bicolore": lambda m, x: len(x.get("declarant", ())) >= 2,
                "soutenu": lambda m, x: x.get("den") in x.get("mort", ()),
                "adverse": lambda m, x: x["c"] in x["adverses"],
                "sequence": lambda m, x: tete_de_sequence(x["p"]) is not None,
                "honneur": lambda m, x: honneur(x["p"])}
        if t in mots: return ("mot", mots[t], None)
        m = re.fullmatch(r"tete\s+([ardvx]+)", t)
        if m:
            debut = m[1].upper(); return ("tete", lambda mm, x: x["p"].startswith(debut), None)
        m = re.fullmatch(r"(longueur|atouts|palier)\s*([!\d].*)", t)
        if m:
            neg = m[2].startswith("!"); lo, hi = _zone(m[2].lstrip("!").strip(), ligne, m[1])
            val = {"longueur": lambda x: len(x["p"]), "atouts": lambda x: x["atouts"],
                   "palier": lambda x: x.get("palier") or 0}[m[1]]
            return ("longueur", lambda mm, x: (lo <= val(x) <= hi) != neg, None)
        raise ErreurRegles(f"ligne {ligne} : condition d'entame « {c} » non comprise "
                           "(partenaire, adverse, sequence, honneur, tete AR, longueur 4+, atouts 2+)")


class Regle:
    def __init__(self, d, ligne, defs):
        self.ligne = ligne
        inconnues = set(d) - {"si", "contrat", "hors", "sauf", "choix", "carte", "raison", "nom", "atout"}
        if inconnues: raise ErreurRegles(f"ligne {ligne} : clé inconnue « {sorted(inconnues)[0]} »")
        self.si = ConditionEntame(d.get("si", ""), defs, ligne)
        self.sauf = ConditionEntame(d["sauf"], defs, ligne) if d.get("sauf") else None
        self.contrat = d.get("contrat")
        if self.contrat not in (None, "couleur", "SA"):
            raise ErreurRegles(f"ligne {ligne} : contrat « {self.contrat} » : couleur ou SA")
        self.hors = d.get("hors"); self.choix = d.get("choix", "premiere")
        if self.choix not in ("partenaire", "sequence", "longue", "longueur", "premiere"):
            raise ErreurRegles(f"ligne {ligne} : choix « {self.choix} » : partenaire, sequence, longue, "
                               "longueur ou premiere")
        self.carte = d.get("carte"); self.raison = d.get("raison"); self.nom = d.get("nom")
        self.atout = str(d.get("atout", "")).lower() in ("oui", "true")    # la règle choisit l'atout

    def vaut(self, den):
        return self.contrat is None or (self.contrat == "SA") == (den == "SA")


CARTES = ("tete", "haute", "basse", "4e", "2e", "A")


class Entames:
    def __init__(self, couleur, cartes, exemples, chemin):
        self.couleur, self.cartes, self.exemples, self.chemin = couleur, cartes, exemples, chemin

    def entame(self, main_fr, den, singleton=True, partenaire=(), adverses=(), palier=None,
               declarant=(), mort=()):
        """(carte, raison) : la première règle de « couleur » qui désigne une couleur, puis la
        carte selon sa liste. partenaire, adverses : couleurs nommées naturellement."""
        s = dict(zip(COULEURS, ["" if p == "-" else p for p in main_fr.split()]))
        possibles = [c for c in COULEURS if s[c] and c != den] or [c for c in COULEURS if s[c]]
        atouts = len(s.get(den, ""))
        ctx = lambda c: {"p": s[c], "c": c, "partenaire": list(partenaire), "adverses": list(adverses),
                         "atouts": atouts, "den": den, "palier": palier, "declarant": list(declarant),
                         "mort": list(mort)}
        for r in self.couleur:
            if not r.vaut(den) or (r.nom == "singleton" and not singleton): continue
            base = possibles
            if r.atout:
                if den == "SA" or not s.get(den): continue
                base = [den]
            if r.hors == "adverses": base = [c for c in possibles if c not in adverses] or possibles
            if r.sauf and any(r.sauf.vraie(None, ctx(c)) for c in base): continue
            cand = [c for c in (base if r.atout else possibles) if r.si.vraie(None, ctx(c))]
            if r.hors == "adverses": cand = [c for c in cand if c not in adverses] or cand   # si possible
            if not cand: continue
            c = self._choisir(r.choix, cand, s, den, partenaire)
            x, raison = self.carte(s[c], den, r.carte)
            return c + x, r.raison or raison
        raise ErreurRegles(f"{self.chemin} : aucune règle d'entame pour {main_fr} ({den})")

    @staticmethod
    def _choisir(choix, cand, s, den, partenaire):
        if choix == "partenaire": return next(c for c in partenaire if c in cand)
        if choix == "sequence": return max(cand, key=lambda c: -HON.index(tete_de_sequence(s[c])))
        if choix == "longueur": return max(cand, key=lambda c: len(s[c]))
        if choix == "longue":
            return max(cand, key=lambda c: (len(s[c]), den == "SA" and bool(tete_de_sequence(s[c][:3])),
                                            sum(len(HON) - HON.index(x) for x in s[c] if x in HON)))
        return cand[0]

    def carte(self, p, den, liste):
        """(carte, raison) dans la couleur p (de la plus haute à la plus basse), selon la liste."""
        for r in self.cartes[liste]:
            if not r.vaut(den) or not r.si.vraie(None, {"p": p, "c": None, "partenaire": [], "adverses": [],
                                                        "atouts": 0}):
                continue
            x = {"tete": tete_de_sequence(p), "haute": p[0], "basse": p[-1], "A": "A",
                 "4e": p[3] if len(p) >= 4 else p[-1], "2e": p[1] if len(p) >= 2 else p[0]}[r.carte]
            return x, r.raison or ""
        raise ErreurRegles(f"{self.chemin} : liste de cartes « {liste} » sans règle pour {p}")

    def verifier(self):
        """Les exemples du fichier : liste des écarts (vide si tout va bien)."""
        out = []
        for e in self.exemples:
            den = re.fullmatch(r"\d(SA|[TKCP])", str(e["contrat"]))
            den = den[1] if den[1] == "SA" else _couleur(den[1])
            part = [_couleur(x) for x in str(e.get("partenaire", "")).split() if x]
            adv = [_couleur(x) for x in str(e.get("adverses", "")).split() if x]
            obtenu, _ = self.entame(e["main"], den, partenaire=part, adverses=adv, palier=int(str(e["contrat"])[0]))
            if obtenu != e["attendu"]:
                out.append(f"ligne {e['ligne']} : {e['main']} contre {e['contrat']} : {e['attendu']} attendu, {obtenu} obtenu")
        return out


def charger(chemin):
    """Lit entames.yaml ; toute erreur est signalée en français avec son numéro de ligne."""
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError
    texte = re.sub(r"(?m)^\t+", lambda m: "  " * len(m[0]), open(chemin, encoding="utf-8").read())
    try:
        doc = YAML().load(texte)
    except YAMLError as ex:
        raise ErreurRegles(f"{chemin} : {ex}")
    ligne = lambda seq, i: seq.lc.item(i)[0] + 1
    couleur = [Regle(dict(x), ligne(doc["couleur"], i), {}) for i, x in enumerate(doc["couleur"])]
    cartes = {}
    for nom, liste in doc["carte"].items():
        cartes[nom] = [Regle(dict(x), ligne(liste, i), {}) for i, x in enumerate(liste)]
        for r in cartes[nom]:
            if r.carte not in CARTES:
                raise ErreurRegles(f"ligne {r.ligne} : carte « {r.carte} » : {', '.join(CARTES)}")
    for r in couleur:
        if r.carte not in cartes:
            raise ErreurRegles(f"ligne {r.ligne} : liste de cartes « {r.carte} » inconnue")
    exemples = [dict(x, ligne=ligne(doc.get("exemples", []), i)) for i, x in enumerate(doc.get("exemples", []))]
    return Entames(couleur, cartes, exemples, chemin)
