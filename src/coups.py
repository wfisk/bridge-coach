# -*- coding: utf-8 -*-
"""Squeeze, mise en main, laisser-passer et coup à blanc, repérés après coup au double mort.

Le solveur DDS (endplay) trouve ces coups sans les nommer : on joue la donne au double mort et
on teste chaque position de la ligne. Tout est vu cartes sur table : le résultat ne va que dans
le commentaire, jamais dans le plan (systems/technique/jeu-de-la-carte.md, « Coups »).

    analyser(mains, "SA", "S", "♠5") -> [{"type", "pli", "joueur", "couleur", "gain"}, …]
    phrase(mains, "3SA", "S", "♠5") -> « Au double mort, 3SA par S : squeeze sur E (pli 11). » ou ""
"""
import random

from jeu import COULEURS, LHO, PART, RHO, ROT, Simu, _donne_dds, donnes_du_declarant, nettement_meilleure

RANGS = "AKQJT98765432"
FR = str.maketrans({"K": "R", "Q": "D", "J": "V", "T": "X"})
EN = str.maketrans({"R": "K", "D": "Q", "V": "J", "X": "T"})
LETTRE = dict(zip(COULEURS, "SHDC"))
LIGNES = 3                                                # lignes jouées par position de départ


def _main(m):
    return dict(zip(COULEURS, [("" if p == "-" else p).translate(EN) for p in m.split()]))


class Position:
    """La donne jouée carte par carte : mains restantes, pli en cours, levées du déclarant."""

    def __init__(self, mains, den, decl):
        self.mains, self.den, self.decl = mains, den, decl
        self.reste = {s: _main(mains[s]) for s in ROT}
        self.jouees, self.pli = [], []                    # pli : [(siège, couleur, rang)]
        self.tete = LHO[decl]; self.gagnes = 0; self.n = 1; self.mene = None

    def camp(self, s): return s in (self.decl, PART[self.decl])

    def au_trait(self):
        return ROT[(ROT.index(self.tete) + len(self.pli)) % 4]

    def legales(self):
        m = self.reste[self.au_trait()]
        if self.pli and m[self.pli[0][1]]:
            c = self.pli[0][1]; return [(c, r) for r in m[c]]
        return [(c, r) for c in COULEURS for r in m[c]]

    def meilleur(self):
        """(siège, couleur, rang) qui tient le pli en cours."""
        c0 = self.pli[0][1]
        atout = [x for x in self.pli if x[1] == self.den]
        lot = atout or [x for x in self.pli if x[1] == c0]
        return min(lot, key=lambda x: RANGS.index(x[2]))

    def jouer(self, c, r):
        s = self.au_trait()
        self.reste[s][c] = self.reste[s][c].replace(r, "")
        self.pli.append((s, c, r)); self.jouees.append(LETTRE[c] + r)
        if len(self.pli) == 4:
            g = self.meilleur()[0]
            self.mene = self.pli[0][0]                    # qui a mené le dernier pli
            self.gagnes += self.camp(g)
            self.tete = g; self.pli = []; self.n += 1

    def _deal(self):
        from endplay.types import Card
        d = _donne_dds(self.mains, self.den, self.decl)
        for x in self.jouees: d.play(Card(x))
        return d

    def valeurs(self):
        """{(couleur, rang): levées finales du déclarant} pour les cartes jouables (une par groupe
        de cartes équivalentes)."""
        from endplay.dds import solve_board
        s = self.au_trait()
        rest = max(sum(len(p) for p in self.reste[x].values()) for x in ROT)
        out = {}
        for carte, t in solve_board(self._deal()):
            nom = str(carte); c, r = nom[0], nom[1:]
            out[(c, r)] = self.gagnes + (t if self.camp(s) else rest - t)
        return out

    def en_tete(self, tete):
        """Levées finales du déclarant si tete menait la position (début de pli seulement)."""
        from endplay.dds import solve_board
        rest = max(sum(len(p) for p in self.reste[x].values()) for x in ROT)
        t = max(t for _, t in solve_board(_donne_dds_reste(self.reste, self.den, tete)))
        return self.gagnes + (t if self.camp(tete) else rest - t)


def _donne_dds_reste(reste, den, tete):
    from endplay.types import Deal, Denom, Player
    pbn = "N:" + " ".join(".".join(reste[s][c] for c in COULEURS) for s in ROT)
    d = Deal(pbn)
    d.trump = {"♠": Denom.spades, "♥": Denom.hearts, "♦": Denom.diamonds, "♣": Denom.clubs, "SA": Denom.nt}[den]
    d.first = {"N": Player.north, "E": Player.east, "S": Player.south, "O": Player.west}[tete]
    return d


def levees(pos, c, sans=None):
    """Levées du déclarant dans la couleur c, jouée seule tour par tour contre les cartes réelles
    de la défense (sans : le rang que la défense vient de jeter) : chaque tour, notre plus petite
    carte maîtresse prend, chacun fournit sa plus petite ; sans carte maîtresse, on perd le tour."""
    nous = [list(pos.reste[s][c]) for s in (pos.decl, PART[pos.decl])]
    eux = [[x for x in pos.reste[s][c] if x != sans] for s in (LHO[pos.decl], LHO[PART[pos.decl]])]
    k = 0
    while nous[0] or nous[1]:
        hauts = [p[0] for p in eux if p]
        if not hauts: return k + max(len(p) for p in nous)
        haut = min(hauts, key=RANGS.index)
        bons = [(i, x) for i, p in enumerate(nous) for x in p if RANGS.index(x) < RANGS.index(haut)]
        if bons:
            i, x = max(bons, key=lambda v: RANGS.index(v[1]))
            nous[i].remove(x); k += 1
            if nous[1 - i]: nous[1 - i].pop()
            for p in eux:
                if p: p.pop()
        else:
            for p in nous:
                if p: p.pop()
            for p in eux:
                if p: p.remove(haut) if haut in p else p.pop()
    return k


def squeeze(pos, v):
    """Le défenseur au trait défausse et chaque défausse affranchit une carte, dans au moins deux
    couleurs, alors que le déclarant fait plus de levées que ses cartes maîtresses."""
    if not pos.pli: return False
    s = pos.au_trait(); c0 = pos.pli[0][1]
    if pos.camp(s) or pos.reste[s][c0]: return False
    if not pos.camp(pos.meilleur()[0]) and len(pos.pli) == 3: return False
    defausses = [(c, r) for c in COULEURS if c != pos.den for r in pos.reste[s][c]]
    if len({c for c, _ in defausses}) < 2: return False
    for c, r in defausses:
        if levees(pos, c, r) <= levees(pos, c): return False
    fin = min(v.values())
    sures = sum(levees(pos, c) for c in COULEURS if c != pos.den)
    if pos.den != "SA":                                    # chaque atout peut couper : pas de jeu croisé
        sures += sum(len(pos.reste[x][pos.den]) for x in (pos.decl, PART[pos.decl]))
    return fin > pos.gagnes + 1 + sures


def mise_en_main(pos, fin):
    """Un défenseur vient de prendre la main sur un pli mené par le déclarant, et sa défense
    gagnerait une levée si le déclarant menait à sa place, de l'une ou l'autre main."""
    if pos.pli or pos.camp(pos.tete) or pos.mene is None or not pos.camp(pos.mene): return False
    if max(sum(len(p) for p in pos.reste[x].values()) for x in ROT) < 2: return False
    return fin > max(pos.en_tete(pos.decl), pos.en_tete(PART[pos.decl]))


def baisse(pos, v):
    """Le camp du déclarant peut prendre le pli et gagne à ne pas le faire : (type, couleur, gain)."""
    s = pos.au_trait()
    if not pos.camp(s) or len(pos.pli) < 2: return None
    top = pos.meilleur()
    if pos.camp(top[0]): return None
    c0 = pos.pli[0][1]
    suivant = ROT[(ROT.index(s) + 1) % 4]
    dernier = len(pos.pli) == 3
    def prend(c, r):
        if c == top[1] and RANGS.index(r) < RANGS.index(top[2]):
            battu = True
        else:
            battu = c == pos.den and top[1] != pos.den
        if not battu: return False
        if dernier: return True
        if pos.reste[suivant][c0]:                        # le quatrième doit fournir : plus bas que nous ?
            return c == c0 and all(RANGS.index(x) > RANGS.index(r) for x in pos.reste[suivant][c0])
        return False
    oui = [x for k, x in v.items() if prend(*k)]
    non = [x for k, x in v.items() if not prend(*k)]
    if oui and non and max(non) > max(oui):
        nom = "coup à blanc" if pos.camp(pos.pli[0][0]) else "laisser-passer"
        return nom, c0, max(non) - max(oui)
    return None


def _ligne(mains, den, decl, entame, rnd):
    pos = Position(mains, den, decl)
    if entame: pos.jouer(entame[0], entame[1:].translate(EN))
    trouve = []
    while any(pos.reste[pos.au_trait()].values()):
        v = pos.valeurs()
        s = pos.au_trait()
        fin = (max if pos.camp(s) else min)(v.values())
        if not pos.camp(s) and squeeze(pos, v):
            trouve.append({"type": "squeeze", "pli": pos.n, "joueur": s})
        if mise_en_main(pos, fin):
            trouve.append({"type": "mise en main", "pli": pos.n, "joueur": s})
        b = baisse(pos, v)
        if b:
            trouve.append({"type": b[0], "pli": pos.n, "couleur": b[1], "gain": b[2]})
        bons = [k for k, x in v.items() if x == fin]
        if rnd is None:                                   # le déclarant encaisse, la défense garde
            k = min(bons, key=lambda k: RANGS.index(k[1])) if pos.camp(s) else max(bons, key=lambda k: RANGS.index(k[1]))
        else:
            k = rnd.choice(bons)
        pos.jouer(*k)
    return trouve


def coups_a_venir(mains, den, decl, jouees):
    """Depuis la position réelle (jouees : les cartes déjà jouées, « SA » « HT »…) dans une donne imaginée mains : la
    suite au double mort passe-t-elle par un squeeze ou une mise en main ? [(type, joueur)] (le déclarant y pense)."""
    lettre = dict(zip("SHDC", COULEURS))
    pos = Position(mains, den, decl)
    for j in jouees: pos.jouer(lettre[j[0]], j[1:])
    vus = []
    while any(pos.reste[pos.au_trait()].values()):
        v = pos.valeurs(); s = pos.au_trait()
        fin = (max if pos.camp(s) else min)(v.values())
        if not pos.camp(s) and squeeze(pos, v): vus.append(("squeeze", s))
        if mise_en_main(pos, fin): vus.append(("mise en main", s))
        bons = [k for k, x in v.items() if x == fin]
        pos.jouer(*(min(bons, key=lambda k: RANGS.index(k[1])) if pos.camp(s) else max(bons, key=lambda k: RANGS.index(k[1]))))
    return sorted(set(vus))


def analyser(mains, den, decl, entame=None, lignes=LIGNES, graine=1):
    """Coups trouvés sur quelques lignes du double mort : le premier de chaque type et joueur."""
    try:
        import endplay.dds                                 # noqa: F401
    except ImportError:
        return []
    rnd = random.Random(graine); vus = {}
    for i in range(lignes):
        for x in _ligne(mains, den, decl, entame, None if i == 0 else rnd):
            vus.setdefault((x["type"], x.get("joueur"), x.get("couleur")), x)
    return sorted(vus.values(), key=lambda x: x["pli"])


CHANCES = {}


def chance_squeeze(d, contrat, decl, entame, encheres, n=60):
    """Part des donnes imaginées par le déclarant où le double mort passe par un squeeze, ou None
    (sans endplay ou sans assez de donnes). Le résultat est un peu optimiste : DDS voit tout."""
    cle = (d.get("n"), contrat, decl, entame, tuple(encheres or ()))
    if cle in CHANCES: return CHANCES[cle]
    try:
        import endplay.dds                                 # noqa: F401
    except ImportError:
        return None
    if not encheres or not entame: return None
    donnes = donnes_du_declarant(d, decl, encheres, entame, n)
    if len(donnes) < 15: return None
    den = contrat[1:].rstrip("X")
    k = sum(any(x["type"] == "squeeze" for x in analyser(m, den, decl, entame, lignes=3)) for m in donnes)
    CHANCES[cle] = k / len(donnes)
    return CHANCES[cle]


def _maitre(pos, c, r):
    """Aucune carte plus haute dehors ? D'après nos mains et les cartes déjà jouées seulement."""
    nous = pos.reste[pos.decl][c] + pos.reste[PART[pos.decl]][c]
    vues = {x[1:] for x in pos.jouees if x[0] == LETTRE[c]}
    return all(x in nous or x in vues for x in RANGS[:RANGS.index(r)])


def _atouts_dehors(pos):
    if pos.den == "SA": return 0
    vus = sum(x[0] == LETTRE[pos.den] for x in pos.jouees)
    return 13 - vus - len(pos.reste[pos.decl][pos.den]) - len(pos.reste[PART[pos.decl]][pos.den])


def _suivre(pos, cle):
    """Le camp du déclarant fournit, par règle : le plus petit qui suffit, jamais le double mort.
    Dans la couleur clé, la plus petite carte qui bat le pli (c'est l'impasse)."""
    leg = pos.legales(); top = pos.meilleur(); c0 = pos.pli[0][1]
    gagne = pos.camp(top[0]); n = len(pos.pli)
    def bat(c, r):
        if top[1] == pos.den and c != pos.den: return False
        if c == top[1]: return RANGS.index(r) < RANGS.index(top[2])
        return c == pos.den
    if leg[0][0] == c0:
        bons = [x for x in leg if bat(*x)]
        if gagne and (n == 3 or _maitre(pos, top[1], top[2])): return leg[-1]
        if bons and (n == 3 or n == 2 or c0 == cle):
            if n == 2 and c0 != cle:
                m = [x for x in bons if _maitre(pos, *x)]
                return m[-1] if m else leg[-1]
            return bons[-1]
        return leg[-1]
    if not gagne:
        coupes = [x for x in leg if x[0] == pos.den and bat(*x)]
        if coupes: return coupes[-1]
    autres = [x for x in leg if x[0] not in (pos.den, cle)] or [x for x in leg if x[0] != pos.den] or leg
    long = max({x[0] for x in autres}, key=lambda c: len(pos.reste[pos.au_trait()][c]))
    return [x for x in autres if x[0] == long][-1]


def _passer(pos, cad):
    """Une carte pour donner la main au partenaire : une maîtresse à lui, jamais la clé. None sinon."""
    s = pos.au_trait(); p = PART[s]; den = pos.den
    for c in COULEURS:
        if c == cad["cle"] or not pos.reste[s][c] or not pos.reste[p][c]: continue
        if c == den and (_atouts_dehors(pos) or len(pos.reste[s][c]) < 2 or len(pos.reste[p][c]) < 2): continue
        if any(_maitre(pos, c, r) for r in pos.reste[p][c]) or c == den and pos.reste[p][c][0] < pos.reste[s][c][-1]:
            return (c, pos.reste[s][c][-1])
    return None


def _mener(pos, cad, phases):
    """Le camp du déclarant mène, en suivant la ligne : purge, élimination, sortie, impasse. None
    quand la ligne est au bout (les dernières cartes se jouent au double mort)."""
    s = pos.au_trait(); p = PART[s]; den = pos.den; cle = cad["cle"]
    moi, lui = pos.reste[s], pos.reste[p]
    while phases:
        ph = phases[0]
        if ph == "atouts":
            if _atouts_dehors(pos):
                m = [r for r in moi[den] if _maitre(pos, den, r)]
                if m: return (den, m[0])
                if moi[den] and any(_maitre(pos, den, r) for r in lui[den]): return (den, moi[den][-1])
        elif ph == "eliminer":
            for c in cad["eliminer"]:
                if moi[c]:
                    m = [r for r in moi[c] if _maitre(pos, c, r)]
                    if m and (lui[c] or not lui[den] or not m[1:]): return (c, m[0])
                    if not lui[c] and lui[den] and len(lui[den]) + len(moi[den]) > 1: return (c, moi[c][-1])
                    if any(_maitre(pos, c, r) for r in lui[c]): return (c, moi[c][-1])
                elif lui[c] and moi[den] and len(lui[den]) + len(moi[den]) > 1:
                    x = _passer(pos, cad)
                    if x: return x
        elif ph == "sortie":
            for c in cad["sorties"]:
                if moi[c]:
                    m = [r for r in moi[c] if _maitre(pos, c, r)]
                    return (c, m[0] if m else moi[c][-1])
                if lui[c]:
                    x = _passer(pos, cad)
                    if x: return x
        elif ph == "impasse":
            if moi[cle] and (s == cad["vers"] or not lui[cle]):
                phases.pop(0); return (cle, moi[cle][-1])
            if lui[cle]:
                x = _passer(pos, cad)
                if x: return x
        phases.pop(0)
    return None


def jouer_ligne(m, den, decl, lead, cad, phases):
    """Levées du déclarant sur une donne imaginée : la ligne pour le déclarant, sans regarder les
    mains adverses, le double mort pour la défense ; au bout de la ligne, le double mort pour tous."""
    pos = Position(m, den, decl); pos.jouer(*lead)
    phases = list(phases); cle = cad["cle"]
    while any(pos.reste[pos.au_trait()].values()):
        s = pos.au_trait()
        if not pos.camp(s):
            v = pos.valeurs(); fin = min(v.values())
            pos.jouer(*max((k for k, x in v.items() if x == fin), key=lambda k: RANGS.index(k[1])))
            continue
        if not pos.pli:
            k = _mener(pos, cad, phases)
            if k is None: break
        else:
            k = _suivre(pos, cle)
        pos.jouer(*k)
    if not any(pos.reste[pos.au_trait()].values()): return pos.gagnes
    return max(pos.valeurs().values())


def chance_elimination(d, contrat, decl, entame, encheres, cad, n=40):
    """(avec élimination, sans) sur les mêmes donnes imaginées : la même ligne, la couleur clé jouée
    en dernier ou tout de suite, pour que le double mort final n'avantage aucune des deux. (None,
    None) sans endplay ou sans assez de donnes."""
    cle = (d.get("n"), contrat, decl, entame, tuple(encheres or ()), "elimination")
    if cle in CHANCES: return CHANCES[cle]
    try:
        import endplay.dds                                 # noqa: F401
    except ImportError:
        return None, None
    if not encheres: return None, None
    donnes = donnes_du_declarant(d, decl, encheres, entame, n)
    if len(donnes) < 15: return None, None
    den = contrat[1:].rstrip("X"); need = int(contrat[0]) + 6
    lead = (entame[0], entame[1:].translate(EN))
    a = [jouer_ligne(m, den, decl, lead, cad, ("atouts", "eliminer", "sortie", "impasse")) for m in donnes]
    b = [jouer_ligne(m, den, decl, lead, cad, ("atouts", "impasse", "eliminer", "sortie")) for m in donnes]
    CHANCES[cle] = _simu(a, need), _simu(b, need)
    return CHANCES[cle]


def _apres(m, den, decl, cartes):
    pos = Position(m, den, decl)
    for c, r in cartes: pos.jouer(c, r)
    return pos


def _options_mort(pos):
    """Les cartes du mort à essayer : toute la couleur fournie ; défaussant, le plus petit atout et
    la plus petite carte de chaque couleur."""
    leg = pos.legales()
    if pos.pli and leg[0][0] == pos.pli[0][1]: return leg
    par = {}
    for c, r in leg: par[c] = (c, r)                       # la dernière est la plus petite
    return list(par.values())


def _naturelle(options, den):
    atouts = [x for x in options if x[0] == den]
    return atouts[-1] if atouts else options[-1]


def _simu(totaux, need):
    """Comme pour l'entame, mais vu du déclarant : part des donnes où le contrat gagne."""
    return Simu(sum(x >= need for x in totaux) / len(totaux), sum(totaux) / len(totaux), totaux, need)


def _ecart(a, b, autre):
    if a[0] != b[0]: return f"le contrat gagne {a[0]:.0%} du temps, contre {b[0]:.0%} {autre}"
    return f"{a[1] - b[1]:.1f} levée de plus en moyenne".replace(".", ",")


def premier_pli(d, contrat, decl, entame, encheres, n=60):
    """Le premier pli, vu du déclarant : quelle carte du mort, et faut-il laisser passer. Sur n donnes
    imaginées (le déclarant et le mort tels quels, le reste fidèle aux enchères et à l'entame),
    chaque choix est joué au double mort. On garde le plus petit du mort, et on prend, sauf si un
    autre choix est nettement meilleur (même test que pour l'entame)."""
    try:
        import endplay.dds                                 # noqa: F401
    except ImportError:
        return ""
    donnes = donnes_du_declarant(d, decl, encheres or [], entame, n)
    if len(donnes) < 15: return ""
    den = contrat[1:].rstrip("X"); need = int(contrat[0]) + 6
    lead = (entame[0], entame[1:].translate(EN)); mort = PART[decl]; g = LHO[decl]; dr = RHO[decl]
    options = _options_mort(_apres(donnes[0], den, decl, [lead]))
    totaux = {o: [] for o in options}
    for m in donnes:
        for o in options:
            v = _apres(m, den, decl, [lead, o]).valeurs()
            totaux[o].append(min(v.values()))
    sim = {o: _simu(t, need) for o, t in totaux.items()}
    nat = _naturelle(options, den); choix = nat
    best = max(options, key=lambda o: (sim[o][0], sim[o][1], RANGS.index(o[1])))   # à égalité, la plus petite
    if len(options) > 1 and best != nat and nettement_meilleure(sim[best], sim[nat]): choix = best
    phr = []
    fr = lambda o: o[0] + o[1].translate(FR)
    # le plus petit ne vaut d'être dit que si le mort avait un honneur capable de battre l'entame
    honneur = options[0][0] == lead[0] and nat[1] not in "AKQJT" and RANGS.index(options[0][1]) < RANGS.index(lead[1]) \
        and options[0][1] in "AKQJT"
    if len(options) > 1 and choix != nat:
        ecart = _ecart(sim[choix], sim[nat], f"avec {fr(nat)}")
        verbe = "mettre" if choix[0] == lead[0] else "couper de" if choix[0] == den else "défausser"
        phr.append(f"Premier pli : {verbe} {fr(choix)} du mort ({ecart}).")
    elif len(options) > 1 and honneur:
        phr.append(f"Premier pli : ne rien mettre du mort, {fr(nat)}.")
    prendre, passer = [], []
    for m in donnes:                                       # le déclarant, en quatrième
        pos = _apres(m, den, decl, [lead, choix])
        v = pos.valeurs()
        fin = min(v.values())
        k = max((x for x, y in v.items() if y == fin), key=lambda x: RANGS.index(x[1]))
        pos.jouer(*k)
        top = pos.meilleur()
        if pos.camp(top[0]): continue
        v = pos.valeurs()
        def gagne(c, r):
            return (c == top[1] and RANGS.index(r) < RANGS.index(top[2])) or (c == pos.den and top[1] != pos.den)
        oui = [x for k, x in v.items() if gagne(*k)]; non = [x for k, x in v.items() if not gagne(*k)]
        if oui and non:
            prendre.append(max(oui)); passer.append(max(non))
    if len(prendre) >= 15:
        a, b = _simu(passer, need), _simu(prendre, need)
        if nettement_meilleure(a, b):
            tours = 7 - sum(len(p) for p in (donnes[0][decl], donnes[0][mort]) for p in [dict(zip(COULEURS, p.split()))[lead[0]].replace("-", "")])
            regle = f" Règle de 7 : {tours} tour{'s' if tours > 1 else ''} à laisser passer." if den == "SA" and tours > 0 else ""
            phr.append(f"Ne pas prendre le premier tour : {_ecart(a, b, 'en prenant')}.{regle}")
    return " ".join(phr)


def texte(x):
    if x["type"] in ("squeeze", "mise en main"):
        return f"{x['type']} {'sur' if x['type'] == 'squeeze' else 'de'} {x['joueur']} (pli {x['pli']})"
    return f"{x['type']} à {x['couleur']} (pli {x['pli']})"


def phrase(mains, contrat, decl, entame=None):
    """La phrase du commentaire, ou "" s'il n'y a rien."""
    den = contrat[1:].rstrip("X")
    trouve = analyser(mains, den, decl, entame)
    if not trouve: return ""
    return f"Au double mort, {contrat} par {decl} : " + ", ".join(texte(x) for x in trouve) + "."
