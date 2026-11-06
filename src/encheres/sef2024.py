# -*- coding: utf-8 -*-
"""Règles d'enchères SEF 2024, étape 1 : séquences sans intervention adverse.

Chaque règle reflète une ligne de systems/sef-2024/systeme.md ou systems/conventions/*.md.
Une fonction de décision reçoit un Contexte et renvoie un Appel (enchère, explication,
ce que l'enchère montre). Si aucune règle ne s'applique, elle lève NonCouverte.
"""
from .main import COULEURS, MAJEURES, MINEURES

DENOMS = ["♣", "♦", "♥", "♠", "SA"]
MANCHE = {"SA": 3, "♠": 4, "♥": 4, "♦": 5, "♣": 5}
SEUIL_MANCHE = {"SA": 25, "♠": 25, "♥": 25, "♦": 29, "♣": 29}
PETIT_CHELEM, GRAND_CHELEM = 33, 37


class NonCouverte(Exception):
    pass


class Info:
    """Ce qu'un joueur a montré : zone de points (H ou HL) et longueurs minimales."""
    def __init__(self):
        self.pts = (0, 40); self.L = {c: 0 for c in COULEURS}; self.reguliere = False

    def montre(self, pts=None, L=None, reguliere=None):
        if pts: self.pts = (max(self.pts[0], pts[0]), min(self.pts[1], pts[1]))
        for c, n in (L or {}).items(): self.L[c] = max(self.L[c], n)
        if reguliere is not None: self.reguliere = reguliere


class Appel:
    def __init__(self, enchere, texte, pts=None, L=None, reguliere=None, nature="", atout=None):
        self.enchere, self.texte, self.nature, self.atout = enchere, texte, nature, atout
        self.pts, self.L, self.reguliere = pts, L, reguliere


def rang(enchere):
    """'3♥' -> 12 (ordre des enchères) ; 'passe' -> -1"""
    if enchere in ("passe", "contre", "surcontre"): return -1
    return (int(enchere[0]) - 1) * 5 + DENOMS.index(enchere[1:])

def e(niveau, d): return f"{niveau}{d}"

def plus_bas(d, apres):
    """Palier le plus bas où l'on peut nommer d après l'enchère `apres`."""
    n = 1
    while apres and rang(e(n, d)) <= rang(apres): n += 1
    return n


# ---------------------------------------------------------------- ouverture
def ouverture(m, position):
    h, hl = m.hcp, m.hl
    if m.reguliere and 24 <= h or hl >= 25:
        return Appel("2♦", "24+ H, forcing de manche (à confirmer)", (24, 40), nature="forcing")
    if (m.reguliere and 22 <= h <= 23) or (not m.reguliere and 21 <= hl <= 24):
        return Appel("2♣", "fort indéterminé, 21+ (à confirmer)", (21, 24), nature="forcing")
    if m.reguliere and 20 <= h <= 21:
        return Appel("2SA", "20–21 H, régulier", (20, 21), reguliere=True)
    if m.reguliere and 15 <= h <= 17 and max(m.L["♠"], m.L["♥"]) < 5:
        return Appel("1SA", "15–17 H, régulier", (15, 17), reguliere=True)
    ouvre = h >= 12 or (h >= 11 and (m.regle_des_20() if position <= 2 else True))
    if position == 4: ouvre = h >= 12 or (h >= 10 and (h + m.L["♠"] >= 15 or max(m.L.values()) >= 6))
    if not ouvre:
        for M in MAJEURES:
            if m.L[M] == 6 and 6 <= h <= 10 and position <= 3 and m.L["♠♥".replace(M, "")] < 4:
                return Appel(e(2, M), f"faible : 6 cartes à {M}, 6–10 H (zone à confirmer)", (6, 10), {M: 6})
        for c in COULEURS:
            if m.L[c] >= 7 and 6 <= h <= 10 and position <= 3:
                return Appel(e(3, c), f"barrage : 7 cartes à {c}, 6–10 H", (6, 10), {c: 7})
        if position == 3 and 8 <= h <= 10 and (m.regle_des_20() or (h == 10 and m.L["♠"] + m.L["♥"] >= 9)):
            c = max(COULEURS, key=lambda x: m.L[x])
            return Appel(e(1, c), "ouverture légère en troisième", (8, 10), {c: 4})
        return Appel("passe", "moins de 12 H")
    if max(m.L["♠"], m.L["♥"]) >= 5:
        M = "♠" if m.L["♠"] >= m.L["♥"] else "♥"
        return Appel(e(1, M), f"12–21 H, 5+ cartes à {M}", (11, 21), {M: 5})
    tr, ca = m.L["♣"], m.L["♦"]
    if ca > tr or (ca == tr and ca >= 4) or (m.forme == [4, 4, 3, 2] and ca == 3 and tr == 2):
        return Appel("1♦", "12–21 H, 4+ carreaux (sauf 4-4-3-2)", (11, 21), {"♦": 3 if ca == 3 else 4})
    return Appel("1♣", "12–21 H, 3+ trèfles", (11, 21), {"♣": 3})


# ---------------------------------------------------------------- réponses
def reponse_majeure(m, M):
    h = m.hcp
    if m.L[M] >= 3:
        dh = m.dh(M)
        if dh < 6: return Appel("passe", "moins de 6 points")
        if dh <= 10: return Appel(e(2, M), f"soutien simple, 6–10 DH, 3+ cartes à {M}", (6, 10), {M: 3}, nature="limite")
        if dh <= 12: return Appel(e(3, M), f"soutien limite, 11–12 DH, 3+ cartes à {M} (à confirmer)", (11, 12), {M: 3}, nature="invite")
        c = autre_couleur(m, M)
        return Appel(e(1 if c == "♠" and M == "♥" else 2, c), f"13+ points, fit {M} différé : couleur d'attente", (13, 40), {c: 3, M: 3}, nature="forcing")
    if h < 6: return Appel("passe", "moins de 6 H")
    if M == "♥" and m.L["♠"] >= 4:
        return Appel("1♠", "6+ H, 4+ piques", (6, 40), {"♠": 4}, nature="forcing")
    if h <= 10:
        return Appel("1SA", "6–10 H, sans fit", (6, 10), nature="limite")
    c = autre_couleur(m, M)
    return Appel(e(2, c), f"11+ H, 4+ cartes à {c}, forcing", (11, 40), {c: 5 if c == "♥" else 4}, nature="forcing")

def autre_couleur(m, M):
    """Couleur à nommer au palier de 2 sous la majeure M (♥ demande 5 cartes)."""
    choix = [c for c in ("♦", "♣") if m.L[c] >= 4] + (["♥"] if M == "♠" and m.L["♥"] >= 5 else [])
    if not choix: return "♣" if m.L["♣"] >= m.L["♦"] else "♦"
    return max(choix, key=lambda c: (m.L[c], -DENOMS.index(c)))

def reponse_mineure(m, mi):
    h = m.hcp
    if h < 6: return Appel("passe", "moins de 6 H")
    majs = [M for M in ("♥", "♠") if m.L[M] >= 4]
    mineure5 = max(m.L["♣"], m.L["♦"])
    if majs:
        if h >= 12 and mineure5 >= 5 and mineure5 > max(m.L[M] for M in majs):
            c = m.longue(MINEURES)
            n = 1 if rang(e(1, c)) > rang(e(1, mi)) else 2
            return Appel(e(n, c), f"12+ H, forcing de manche : la couleur la plus longue d'abord", (12, 40), {c: 5}, nature="forcing")
        M = "♠" if m.L["♠"] >= 5 and m.L["♠"] > m.L["♥"] else ("♥" if "♥" in majs else "♠")
        return Appel(e(1, M), f"6+ H, 4+ cartes à {M}", (6, 40), {M: 4}, nature="forcing")
    if mi == "♣" and m.L["♦"] >= 4 and (h <= 10 or not m.reguliere):
        return Appel("1♦", "6+ H, 4+ carreaux", (6, 40), {"♦": 4}, nature="forcing")
    if h <= 10:
        if m.L[mi] >= (5 if mi == "♣" else 4):
            return Appel(e(2, mi), f"6–10 H, soutien à {mi}", (6, 10), {mi: 4}, nature="limite")
        return Appel("1SA", "6–10 H, sans majeure 4e", (6, 10), nature="limite")
    if m.reguliere and h <= 12: return Appel("2SA", "11–12 H, régulier, sans majeure 4e", (11, 12), reguliere=True, nature="invite")
    if m.reguliere and h <= 15: return Appel("3SA", "13–15 H, régulier, sans majeure 4e", (13, 15), reguliere=True, nature="conclusion")
    if mi == "♦": return Appel("2♣", "11+ H, 4+ trèfles, forcing", (11, 40), {"♣": 4}, nature="forcing")
    raise NonCouverte("réponse forte à 1♣ sans majeure ni carreaux")

def reponse_1sa(m, palier=1):
    """palier 1 : après 1SA (15–17) ; palier 2 : après 2SA (20–21)."""
    h, base = m.hcp, (15, 17) if palier == 1 else (20, 21)
    manque = 25 - base[0]                       # points pour la manche avec le minimum
    for M, t in (("♠", "♥"), ("♥", "♦")):
        if m.L[M] >= 5 and m.L[M] >= m.L["♠♥".replace(M, "")]:
            return Appel(e(palier + 1, t), f"texas : 5+ cartes à {M}", (0, 40), {M: 5}, nature="relais")
    if h >= manque - 2 and max(m.L["♠"], m.L["♥"]) == 4 and m.forme != [4, 3, 3, 3]:
        return Appel(e(palier + 1, "♣"), "Stayman : une majeure 4e", (manque - 2, 40), nature="relais")
    total_min = h + base[0]
    if total_min >= GRAND_CHELEM: return Appel("7SA", "grand chelem : 37+ points ensemble", (h, h), nature="conclusion")
    if total_min >= PETIT_CHELEM: return Appel("6SA", "petit chelem : 33+ points ensemble", (h, h), nature="conclusion")
    if total_min >= PETIT_CHELEM - 2: return Appel("4SA", "quantitatif : invite au chelem", (h, h), nature="invite")
    if total_min >= 25: return Appel("3SA", "manche", (h, h), nature="conclusion")
    if total_min >= 23 and palier == 1: return Appel("2SA", "invitation à 3SA", (8, 9), nature="invite")
    return Appel("passe", "pas de manche possible")


# ---------------------------------------------------------------- redemande de l'ouvreur
def redemande(m, ouv, rep, moi):
    """Seconde enchère de l'ouvreur (ouverture d'un à la couleur)."""
    h = m.hl; mc = ouv[1:]; rc = rep[1:]
    if rep == e(2, mc):                                    # soutien simple
        if h <= 14: return Appel("passe", "minimum, pas de manche")
        if h <= 17: return Appel(e(3, mc), "15–17, invite", (15, 17), nature="invite")
        return Appel(e(4 if mc in MAJEURES else 5, mc), "18+, manche", (18, 21), nature="conclusion")
    if rep == e(3, mc):                                    # soutien limite
        return Appel(e(MANCHE[mc], mc), "accepte l'invitation", (14, 21), nature="conclusion") if h >= 14 \
            else Appel("passe", "minimum, refuse l'invitation")
    if rep in ("2SA",):
        return Appel("3SA", "accepte", (14, 21), nature="conclusion") if m.hcp >= 14 else Appel("passe", "minimum")
    if rep == "3SA": return Appel("passe", "contrat atteint")
    if rc in MAJEURES and m.L[rc] >= 4:                    # fit dans la majeure du répondant
        if rep[0] == "1":
            d = m.dh(rc)
            if d <= 14 or m.hcp <= 12:                      # le saut demande aussi des honneurs
                return Appel(e(2, rc), f"12–14, 4 cartes à {rc}", (12, 14), {rc: 4}, nature="limite")
            if d <= 17: return Appel(e(3, rc), f"15–17, 4 cartes à {rc}", (15, 17), {rc: 4}, nature="invite")
            return Appel(e(4, rc), f"18+, 4 cartes à {rc}", (18, 21), {rc: 4}, nature="conclusion")
    if rep == "1SA":
        if m.reguliere and m.hcp <= 14: return Appel("passe", "régulier, minimum")
        if m.reguliere and m.hcp >= 18: return Appel("2SA", "18–19 H, régulier", (18, 19), reguliere=True, nature="invite")
        return couleur_suivante(m, mc, rep)
    if rep[0] == "1":                                      # nouvelle couleur au palier de 1
        if m.reguliere and m.hcp <= 14: return Appel("1SA", "12–14 H, régulier", (12, 14), reguliere=True, nature="limite")
        if m.reguliere and m.hcp >= 18: return Appel("2SA", "18–19 H, régulier", (18, 19), reguliere=True, nature="invite")
        if rc == "♥" and m.L["♠"] >= 4: return Appel("1♠", "4 piques", L={"♠": 4})
        if rc in MINEURES and m.L[rc] >= 4 and m.L[mc] < 5:
            return Appel(e(2, rc), f"12–14, fit {rc}", (12, 14), {rc: 4}, nature="limite")
        return couleur_suivante(m, mc, rep)
    # nouvelle couleur au palier de 2 (11+, forcing)
    if m.L[rc] >= (3 if rc == "♥" else 4):
        return Appel(e(3, rc), f"fit {rc}", (12, 21), {rc: 3}, nature="forcing")
    if m.reguliere: return Appel("2SA", "régulier", (12, 14), reguliere=True)
    return couleur_suivante(m, mc, rep)

def couleur_suivante(m, mc, rep):
    """Répète sa couleur (6+) ou nomme une deuxième couleur 4e moins chère."""
    h = m.hl
    autres = [c for c in COULEURS if c != mc and m.L[c] >= 4 and rang(e(2, c)) > rang(rep)
              and rang(e(2, c)) < rang(e(2, mc))]
    chers = [c for c in COULEURS if c != mc and m.L[c] >= 4 and rang(e(2, c)) > rang(e(2, mc))
             and rang(e(2, c)) > rang(rep)]
    if h >= 17 and chers and m.L[mc] < 6:                  # bicolore cher (reverse)
        c = max(chers, key=lambda x: m.L[x])
        return Appel(e(2, c), f"bicolore cher, 17+ HL, 4+ cartes à {c}", (17, 21), {c: 4, mc: 5}, nature="forcing")
    if m.L[mc] >= 6 or not autres:
        n = 3 if h >= 16 and m.L[mc] >= 6 else 2
        n = max(n, plus_bas(mc, rep))
        return Appel(e(n, mc), f"{'16–18' if n == 3 else '12–15'}, {m.L[mc]} cartes à {mc}",
                     (16, 18) if n == 3 else (12, 15), {mc: 6 if m.L[mc] >= 6 else 5}, nature="limite")
    c = max(autres, key=lambda x: m.L[x])
    if h >= 18 and rang(e(3, c)) > rang(rep):              # trop fort pour une deuxième couleur simple
        return Appel(e(3, c), f"bicolore fort, 18+ HL, 4+ cartes à {c}, forcing", (18, 21), {c: 4}, nature="forcing")
    return Appel(e(2, c), f"deuxième couleur, 4+ cartes à {c}", (12, 17), {c: 4})


# ---------------------------------------------------------------- conventions
def reponse_stayman(m, palier):
    for M in ("♥", "♠"):
        if m.L[M] >= 4: return Appel(e(palier + 1, M), f"4 cartes à {M}", L={M: 4})
    return Appel(e(palier + 1, "♦"), "pas de majeure 4e")

def reponse_blackwood(m, atout):
    k = m.cles(atout); dame = "D" in m.cartes[atout]
    if k in (0, 3): return Appel("5♣", f"{k} clé{'s' if k > 1 else ''} (3041 : 3 ou 0)")
    if k in (1, 4): return Appel("5♦", f"{k} clé{'s' if k > 1 else ''} (3041 : 4 ou 1)")
    return Appel("5♠" if dame else "5♥", f"2 clés {'avec' if dame else 'sans'} la dame d'atout")


# ---------------------------------------------------------------- concurrence (étape 2)
# Traitements SEF courants, tous « à confirmer » dans systems/sef-2024/systeme.md (section Concurrence).

def arret(m, c):
    """Arrêt dans la couleur c : A, Rx, Dxx, Vxxx. Sans couleur adverse (1SA adverse) : pas de condition."""
    if c not in m.cartes: return True
    p = m.cartes[c]
    return "A" in p or ("R" in p and len(p) >= 2) or ("D" in p and len(p) >= 3) or ("V" in p and len(p) >= 4)

def bonne_couleur(m, c):
    """Couleur 5e+ avec au moins deux des honneurs A R D V X (ou 6e+)."""
    return m.L[c] >= 6 or (m.L[c] >= 5 and sum(x in "ARDVX" for x in m.cartes[c]) >= 2)

def intervention(m, ouv, reveil, dernier):
    """Première action du camp adverse sur une ouverture (ouv = enchère de l'ouvreur, dernier = plus haute)."""
    h = m.hcp + (3 if reveil else 0)                       # en réveil : on « emprunte » 3 points
    oc = ouv[1:]
    palier = int(dernier[0])
    if palier >= 4 or (reveil and palier >= 3):            # pas d'intervention sur une manche
        return Appel("passe", "trop haut pour intervenir")
    if palier == 3: h -= 3                                 # au palier de 3 : 3 points de plus
    if oc == "SA":                                         # sur 1SA : naturel à 2, contre = force
        if h >= 15: return Appel("contre", "contre punitif sur SA, 15+ H", (15, 40), nature="punitif")
        for c in COULEURS:
            if m.L[c] >= 6 and h >= 8 and rang(e(2, c)) > rang(dernier):
                return Appel(e(2, c), f"intervention naturelle, 6 cartes à {c} (à confirmer)", (8, 16), {c: 6})
        return Appel("passe", "rien à dire sur 1SA")
    courtes = [c for c in COULEURS if c != oc]
    if m.reguliere and 15 <= h <= 18 and arret(m, oc) and rang("1SA") > rang(dernier):
        return Appel("1SA", f"15–18 H{' (réveil)' if reveil else ''}, régulier, arrêt à {oc}", (15, 18), reguliere=True)
    # couleur 5e
    for c in sorted(courtes, key=lambda c: (-m.L[c], -DENOMS.index(c))):
        if m.L[c] < 5: break
        n = plus_bas(c, dernier)
        r = 3 if reveil else 0                             # en réveil, la zone réelle est 3 points plus bas
        if n == 1 and 8 <= h <= 16 and bonne_couleur(m, c) or n == 1 and 10 <= h <= 16:
            return Appel(e(1, c), f"intervention{' de réveil' if reveil else ''}, 5+ cartes à {c}, {8 - r}–{16 - r} H",
                         (8 - r, 16 - r), {c: 5}, nature="reveil" if reveil else "")
        if n == 2 and 11 <= h <= 16 and bonne_couleur(m, c):
            return Appel(e(2, c), f"intervention{' de réveil' if reveil else ''} au palier de 2, 5+ cartes à {c}, "
                         f"{11 - r}–{16 - r} H", (11 - r, 16 - r), {c: 5}, nature="reveil" if reveil else "")
        if n <= 2 and m.L[c] >= 6 and 6 <= h <= 10 and not reveil:
            return Appel(e(n + 1, c), f"saut faible, 6 cartes à {c}, 6–10 H (à confirmer)", (6, 10), {c: 6})
    # contre d'appel
    if (h >= 12 and m.L[oc] <= 2 and all(m.L[c] >= 3 for c in courtes if c in MAJEURES)) or h >= 17:
        return Appel("contre", f"contre d'appel, {'17+' if h >= 17 else '12+'} H{', court à ' + oc if h < 17 else ''}",
                     (12, 40), {c: 3 for c in courtes if c in MAJEURES}, nature="appel")
    return Appel("passe", "pas d'intervention")

def avance_couleur(m, p, oc, dernier, reveil=False):
    """Le partenaire est intervenu dans la couleur p ; adversaires dans oc.
    reveil : intervention de réveil, qui comptait déjà 3 points du partenaire."""
    h = m.hcp - (3 if reveil else 0)
    if m.L[p] >= 3:
        dh = m.dh(p) - (3 if reveil else 0); n = plus_bas(p, dernier)
        if dh >= 13 and p in MAJEURES and rang(e(4, p)) > rang(dernier):
            return Appel(e(4, p), "fit et 13+ DH : manche", (13, 17), {p: 3}, nature="conclusion")
        if dh >= 11 and n + 1 <= 3: return Appel(e(n + 1, p), "fit, 11–12 DH : invitation (à confirmer)", (11, 12), {p: 3}, nature="invite")
        if dh >= 7 and n <= 3: return Appel(e(n, p), "soutien, 7–10 DH", (7, 10), {p: 3}, nature="limite")
        return Appel("passe", "fit mais trop faible")
    if oc and oc != "SA" and arret(m, oc) and m.reguliere:
        for niv, (lo, hi) in ((1, (8, 11)), (2, (12, 14)), (3, (15, 40))):
            if lo <= h <= hi and rang(e(niv, "SA")) > rang(dernier):
                return Appel(e(niv, "SA"), f"{lo}–{hi} H, arrêt à {oc}", (lo, hi), reguliere=True,
                             nature="invite" if niv == 2 else "conclusion" if niv == 3 else "limite")
    for c in sorted(COULEURS, key=lambda c: -m.L[c]):
        if c in (p, oc) or m.L[c] < 5: continue
        n = plus_bas(c, dernier)
        if n <= 2 and h >= 8 + 2 * (n - 1): return Appel(e(n, c), f"5+ cartes à {c}, {8 + 2 * (n - 1)}+ H", (8, 16), {c: 5})
    return Appel("passe", "rien à ajouter")

def avance_contre(m, eux, dernier, libre):
    """Le partenaire a fait un contre d'appel ; eux = couleurs adverses. libre : l'adversaire a enchéri entre-temps."""
    h = m.hcp
    if libre and h < 6: return Appel("passe", "faible, libéré par l'enchère adverse")
    choix = [c for c in COULEURS if c not in eux]
    if not choix: return Appel("passe", "toutes les couleurs ont été nommées")
    majs = [c for c in choix if c in MAJEURES and m.L[c] >= 4]
    c = max(majs or choix, key=lambda x: (m.L[x], DENOMS.index(x)))
    oc = eux[0] if eux else None
    if h >= 12:
        if c in MAJEURES and m.L[c] >= 4 and rang(e(4, c)) > rang(dernier):
            return Appel(e(4, c), f"12+ H, 4+ cartes à {c} : manche", (12, 17), {c: 4}, nature="conclusion")
        if oc and arret(m, oc) and rang("3SA") > rang(dernier): return Appel("3SA", f"12+ H, arrêt à {oc}", (12, 17), nature="conclusion")
    if 6 <= h <= 9 and not majs and oc and arret(m, oc) and m.reguliere and rang("1SA") > rang(dernier):
        return Appel("1SA", f"6–9 H, arrêt à {oc}, sans majeure 4e", (6, 9), reguliere=True, nature="limite")
    n = plus_bas(c, dernier)
    if h >= 9 and n + 1 <= 3: return Appel(e(n + 1, c), f"9–11 H, 4+ cartes à {c} (saut)", (9, 11), {c: 4}, nature="invite")
    return Appel(e(n, c), f"0–8 H, meilleure couleur {c}", (0, 8), {c: 4 if m.L[c] >= 4 else 3}, nature="limite")

def reponse_concurrence(m, ouv, oc, dernier):
    """Réponse à l'ouverture ouv après une intervention adverse à la couleur oc (ou SA)."""
    h = m.hcp; p = ouv[1:]
    if p != "SA" and m.L[p] >= (3 if p in MAJEURES else 4):
        dh = m.dh(p); n = plus_bas(p, dernier)
        if dh >= 13 and p in MAJEURES and rang(e(4, p)) > rang(dernier):
            return Appel(e(4, p), "fit et 13+ DH : manche", (13, 17), {p: 3}, nature="conclusion")
        if dh >= 11 and n + 1 <= 3: return Appel(e(n + 1, p), "fit, 11–12 DH : invitation", (11, 12), {p: 3}, nature="invite")
        if dh >= 6 and n <= 2 + (m.L[p] >= 4): return Appel(e(n, p), "soutien, 6–10 DH", (6, 10), {p: 3}, nature="limite")
        return Appel("passe", "fit mais trop faible pour monter")
    if h < 6: return Appel("passe", "moins de 6 H")
    if p == "SA":                                          # intervention sur 1SA : naturel (à confirmer)
        if h >= 10 and oc != "SA" and arret(m, oc) and rang("3SA") > rang(dernier):
            return Appel("3SA", f"10+ H, arrêt à {oc}", (10, 15), nature="conclusion")
        if h >= 8 and oc != "SA" and arret(m, oc) and m.reguliere and rang("2SA") > rang(dernier):
            return Appel("2SA", f"8–9 H, arrêt à {oc} : invitation", (8, 9), reguliere=True, nature="invite")
        for c in sorted(COULEURS, key=lambda c: -m.L[c]):
            if c == oc or m.L[c] < 5: continue
            n = plus_bas(c, dernier)
            if n <= 2 or (n == 3 and h >= 10):
                return Appel(e(n, c), f"5+ cartes à {c} après l'intervention (à confirmer)", (6, 15), {c: 5},
                             nature="limite" if n == 2 else "forcing")
        return Appel("passe", "rien d'adapté après l'intervention sur 1SA")
    if oc != "SA":
        libres = [c for c in MAJEURES if c not in (p, oc) and m.L[c] >= 4]
        if libres and rang(dernier) < rang("3♣"):
            return Appel("contre", f"Spoutnik : 6+ H, 4 cartes à {' et '.join(libres)} (à confirmer)", (6, 40),
                         {c: 4 for c in libres}, nature="spoutnik")
        if libres and SPOUTNIK_3 and h >= SPOUTNIK_3 and rang(dernier) < rang("4♣"):   # leur saut au palier de 3
            return Appel("contre", f"Spoutnik au palier de 3 : {SPOUTNIK_3}+ H, 4 cartes à {' et '.join(libres)} (à confirmer)",
                         (SPOUTNIK_3, 40), {c: 4 for c in libres}, nature="spoutnik")
    for c in sorted(COULEURS, key=lambda c: -m.L[c]):
        if c in (p, oc) or m.L[c] < 5: continue
        n = plus_bas(c, dernier)
        if (n == 1 and h >= 6) or (n == 2 and h >= 11):
            return Appel(e(n, c), f"{'6' if n == 1 else '11'}+ H, 5+ cartes à {c}", (6 if n == 1 else 11, 40), {c: 5},
                         nature="forcing")
    if oc != "SA" and arret(m, oc):
        for niv, (lo, hi) in ((1, (8, 10)), (2, (11, 12)), (3, (13, 40))):
            if lo <= h <= hi and rang(e(niv, "SA")) > rang(dernier):
                return Appel(e(niv, "SA"), f"{lo}–{hi} H, arrêt à {oc}", (lo, hi), reguliere=True,
                             nature="invite" if niv == 2 else "conclusion" if niv == 3 else "limite")
    return Appel("passe", "rien d'adapté après l'intervention")

def relance_ouvreur(m, ouv, oc, dernier):
    """L'ouvreur reparle alors que le partenaire a passé (intervention ou contre adverse)."""
    h = m.hl; c = ouv[1:]
    if c in MAJEURES and m.L[c] >= 7 and h >= 19 and rang(e(4, c)) > rang(dernier):
        return Appel(e(4, c), f"{m.L[c]} cartes à {c}, 19+ HL : manche", (19, 21), {c: 7}, nature="conclusion")
    if c != "SA" and m.L[c] >= 6:
        n = plus_bas(c, dernier)
        if n <= 2 or (n == 3 and h >= 16): return Appel(e(n, c), f"{m.L[c]} cartes à {c}, répète en concurrence", L={c: 6})
    if h >= 17 and oc and oc != "SA" and m.L[oc] <= 2:
        return Appel("contre", f"contre de réveil, 17+, court à {oc}", (17, 21), nature="appel")
    return Appel("passe", "rien à ajouter")

SPOUTNIK_LIBRE = True   # contre Spoutnik sans longueurs connues : il promet la majeure libre
SPOUTNIK_3 = 0          # contre Spoutnik sur leur intervention au palier de 3 dès ce nombre de H (0 : jamais)


def apres_spoutnik(m, ouv, oc, dp, dernier):
    """L'ouvreur répond au contre Spoutnik du partenaire (majeure(s) 4e promise(s) dans dp.L)."""
    c = ouv[1:]
    promises = {M for M in MAJEURES if dp.L and dp.L.get(M)}
    if not promises and SPOUTNIK_LIBRE:                    # contre du fichier de règles : la (les) majeure(s) libre(s)
        promises = {M for M in MAJEURES if M not in (oc, c)}
    for M in MAJEURES:
        if M in promises and m.L[M] >= 4:
            n = plus_bas(M, dernier)
            return Appel(e(n + (1 if m.hl >= 16 else 0), M), f"4 cartes à {M}{', 16+' if m.hl >= 16 else ''}",
                         (16, 21) if m.hl >= 16 else (12, 15), {M: 4}, nature="invite" if m.hl >= 16 else "limite")
    if oc and arret(m, oc) and m.reguliere:
        n = plus_bas("SA", dernier)
        return Appel(e(n, "SA"), f"régulier, arrêt à {oc}", (12, 14), reguliere=True, nature="limite")
    if c == "SA": return Appel("passe", "")
    n = plus_bas(c, dernier)
    if n >= 4: return Appel("passe", "trop haut pour répéter")
    return Appel(e(n, c), f"répète sa couleur", (12, 15), {c: 5}, nature="limite")
