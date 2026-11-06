# -*- coding: utf-8 -*-
"""Le jeu de la carte dans l'onglet Jouer : le joueur tient le déclarant et le mort, le programme défend.

La défense joue à la table, comme le déclarant simulé (lignes.py) : à chaque carte, le défenseur imagine les mains
qu'il ne voit pas (le déclarant et son partenaire), fidèles aux enchères (jeu.lire_encheres), aux cartes jouées et aux
couleurs où un joueur a défaussé ; il résout chaque monde au double mort et joue la carte qui fait chuter le
contrat le plus souvent, puis celle qui donne le plus de levées, puis la plus petite. Il ne voit jamais les mains
réelles cachées. L'entame vient des règles (entames.yaml), jamais d'un double mort.

    p = Partie(d, "4♠", "S", encheres)       # entame jouée par la défense
    p.legales() ; p.poser(("♠", "A"))           # une carte du déclarant ou du mort (rangs anglais)
    p.defendre()                                # les cartes de la défense jusqu'au tour du déclarant
    p.indice()                                  # la carte du déclarant simulé (lignes.py)
    p.reclamer()                                # le reste des levées, si la défense ne peut plus rien
"""
import random
from coups import Position, RANGS, EN, FR, _main
from jeu import COULEURS, LHO, RHO, PART, ROT, PTS, _donne_dds, lire_encheres, entame_et_defense, donnes_du_declarant

LETTRE = dict(zip(COULEURS, "SHDC"))
MONDES = 16                                               # mondes imaginés par carte de la défense


def carte_fr(c, r):
    """(« ♠ », « J ») -> « ♠V »."""
    return c + r.translate(FR)


class Partie:
    def __init__(self, d, contrat, decl, encheres, graine=None):
        self.d, self.decl = d, decl
        self.den = contrat[1:].rstrip("X"); self.besoin = int(contrat[0]) + 6
        self.contrat, self.encheres = contrat, list(encheres)
        self.pos = Position(d["mains"], self.den, decl); self.pos.sieges = []
        self.vides = {s: set() for s in ROT}               # les couleurs où chacun a montré une chicane
        self.plis = []                                     # [(cartes [(siège, couleur, rang)], gagnant)]
        self.rnd = random.Random(graine if graine is not None else d.get("n", 0))
        self.cx = lire_encheres(self.encheres, d["donneur"])
        self._pool = None; self.reclame = False
        e = entame_et_defense(d, contrat, decl, self.encheres)["entame"]["carte"]   # « ♠V » : les règles d'entame
        self.entame = (e[0], e[1:].translate(EN))
        self.poser(self.entame)

    # ---------------------------------------------------------------- l'état
    def au_trait(self): return self.pos.au_trait()
    def fini(self): return self.reclame or not any(self.pos.reste[self.au_trait()].values())
    def legales(self): return self.pos.legales()
    def camp(self, s): return self.pos.camp(s)
    def levees(self): return self.pos.gagnes, len(self.plis) - self.pos.gagnes
    def mort(self): return PART[self.decl]

    def poser(self, carte):
        c, r = carte
        if carte not in self.legales(): raise ValueError(f"{carte_fr(c, r)} ne peut pas être jouée")
        s = self.au_trait()
        if self.pos.pli and c != self.pos.pli[0][1]: self.vides[s].add(self.pos.pli[0][1])
        en_cours = self.pos.pli + [(s, c, r)]
        self.pos.sieges.append(s); self.pos.jouer(c, r)
        if not self.pos.pli: self.plis.append((en_cours, self.pos.tete))

    # ---------------------------------------------------------------- la défense
    def _mondes(self, s, k):
        """k donnes complètes imaginées par le défenseur s : sa main et le mort tels quels, les deux autres mains
        réparties au hasard, fidèles aux cartes jouées, aux chicanes montrées et, autant que possible, aux enchères."""
        caches = [x for x in ROT if x not in (s, self.mort())]
        joue = {x: [] for x in ROT}
        for x, carte in zip(self.pos.sieges, self.pos.jouees): joue[x].append((carte[0], carte[1:]))
        vus = {(LETTRE[c], r) for x in (s, self.mort()) for c in COULEURS for r in self.pos.reste[x][c]}
        libres = [(l, r) for l in "SHDC" for r in RANGS if (l, r) not in vus and l + r not in self.pos.jouees]
        n = {x: sum(len(p) for p in self.pos.reste[x].values()) for x in caches}
        lettre_vers = dict(zip("SHDC", COULEURS))
        mondes = []
        for marge, souple in ((1, 0), (3, 1), (40, 99)):  # les enchères d'abord, puis de moins en moins
            for _ in range(3000):
                if len(mondes) >= k: return mondes
                self.rnd.shuffle(libres)
                lots = {caches[0]: libres[:n[caches[0]]], caches[1]: libres[n[caches[0]]:]}
                if any(lettre_vers[l] in self.vides[x] for x in caches for l, _ in lots[x]): continue
                ok = True
                for x in caches:
                    tout = lots[x] + joue[x]; L = {k_: 0 for k_ in COULEURS}; h = 0
                    for l, r in tout:
                        L[lettre_vers[l]] += 1; h += PTS.get(r.translate(FR), 0)
                    lo, hi = self.cx[x]["pts"]
                    if not lo - marge <= h <= hi + marge or any(L[c] < v - souple for c, v in self.cx[x]["L"].items()):
                        ok = False; break
                if not ok: continue
                m = {}
                for x in ROT:
                    if x in caches: cartes = lots[x] + joue[x]
                    else: cartes = [(LETTRE[c], r) for c in COULEURS for r in self.pos.reste[x][c]] + joue[x]
                    m[x] = " ".join("".join(sorted((r for l, r in cartes if l == LETTRE[c]), key=RANGS.index)).translate(FR) or "-"
                                    for c in COULEURS)
                mondes.append(m)
        return mondes

    def carte_defense(self):
        """La carte du défenseur au trait : celle qui fait chuter le contrat dans le plus de mondes imaginés."""
        from endplay.dds import solve_all_boards
        from endplay.types import Card
        s = self.au_trait(); leg = self.legales()
        if len(leg) == 1: return leg[0]
        dd = []
        for m in self._mondes(s, MONDES):
            x = _donne_dds(m, self.den, self.decl)
            for j in self.pos.jouees: x.play(Card(j))
            dd.append(x)
        if not dd: return leg[-1]
        reste = max(sum(len(p) for p in self.pos.reste[x].values()) for x in ROT)   # levées à jouer, pli en cours compris
        chute = {c: 0 for c in leg}; total = {c: 0 for c in leg}
        for sol in solve_all_boards(dd):
            v = {(str(a)[0], str(a)[1:]): t for a, t in sol}
            prec = {}
            for c, r in leg:                               # une carte absente vaut sa voisine équivalente
                t = v.get((c, r), prec.get(c, 0)); prec[c] = t
                decl_final = self.pos.gagnes + (reste - t)  # t : levées de la défense à partir d'ici
                chute[(c, r)] += decl_final < self.besoin; total[(c, r)] += t
        return max(leg, key=lambda x: (chute[x], total[x], RANGS.index(x[1])))

    def defendre(self, sur_carte=None):
        """Joue les cartes de la défense jusqu'au tour du déclarant (ou du mort), ou jusqu'à la fin."""
        while not self.fini() and not self.camp(self.au_trait()):
            c = self.carte_defense(); self.poser(c)
            if sur_carte: sur_carte(c)

    # ---------------------------------------------------------------- l'aide au déclarant
    def indice(self):
        """La carte que jouerait le déclarant simulé (lignes.py), qui ne voit que le déclarant et le mort."""
        import lignes
        if self._pool is None:
            self._pool = donnes_du_declarant(self.d, self.decl, self.encheres, carte_fr(*self.entame), 40)
        vides = {x: set(LETTRE[c] for c in self.vides[x]) for x in (LHO[self.decl], RHO[self.decl])}
        return lignes._carte(self.pos, self._pool, vides, self.besoin, 12, random.Random(len(self.pos.jouees)))

    def reclamer(self):
        """True si le déclarant fait toutes les levées qui restent, quoi que fasse la défense (double mort)."""
        from endplay.dds import solve_board
        s = self.au_trait(); reste = max(sum(len(p) for p in self.pos.reste[x].values()) for x in ROT)
        t = max(t for _, t in solve_board(self.pos._deal()))
        ok = (t == reste) if self.camp(s) else (t == 0)
        if ok: self.pos.gagnes += reste; self.reclame = True
        return ok

    def resultat(self):
        """(levées du déclarant, écart au contrat, levées au double mort au départ)."""
        g = self.pos.gagnes
        return g, g - self.besoin, self.d["dm"][self.den][self.decl]
