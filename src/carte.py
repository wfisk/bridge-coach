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
MODELE = False                                            # vrai : les mondes viennent du modèle des mains cachées (modele.py)
MODELE_DECLARANT = False                                  # vrai : la réserve du déclarant simulé vient aussi du modèle ;
                                                          # « suivi » : renouvelée à chaque carte par le modèle mis à jour


def carte_fr(c, r):
    """(« ♠ », « J ») -> « ♠V »."""
    return c + r.translate(FR)


class Partie:
    def __init__(self, d, contrat, decl, encheres, graine=None, humain=None):
        self.d, self.decl = d, decl
        self.den = contrat[1:].rstrip("X"); self.besoin = int(contrat[0]) + 6
        self.contrat, self.encheres = contrat, list(encheres)
        self.pos = Position(d["mains"], self.den, decl); self.pos.sieges = []
        self.vides = {s: set() for s in ROT}               # les couleurs où chacun a montré une chicane
        self.plis = []                                     # [(cartes [(siège, couleur, rang)], gagnant)]
        self.rnd = random.Random(graine if graine is not None else d.get("n", 0))
        self.cx = lire_encheres(self.encheres, d["donneur"])
        self._pool = None; self.reclame = False; self.difficile = False
        self.dernier = None                                # le dernier choix calculé : rôle, mondes, scores de chaque carte
        self.pensees = []                                  # une par carte jouée : qui, quoi, ce qu'il croyait, pourquoi
        e = entame_et_defense(d, contrat, decl, self.encheres)["entame"]["carte"]   # « ♠V » : les règles d'entame
        self.entame = (e[0], e[1:].translate(EN))
        self.humain = humain if humain is not None else decl   # la place du joueur : le déclarant (et le mort) ou un défenseur
        if self.humain != LHO[decl]: self.poser(self.entame)    # le joueur qui entame choisit lui-même sa carte

    # ---------------------------------------------------------------- qui joue
    def au_joueur(self, s=None):
        """La place s (par défaut celle au trait) est-elle jouée par le joueur ? Au camp du déclarant, il tient le
        déclarant et le mort ; en défense, sa seule main."""
        s = s or self.au_trait()
        return self.camp(s) and self.camp(self.humain) if self.camp(self.humain) else s == self.humain

    def en_defense(self): return not self.camp(self.humain)

    def carte_robot(self):
        """La carte de la place au trait jouée par le programme : le déclarant simulé (lignes.py) pour le camp du
        déclarant, la défense (carte_defense) sinon. Ce qu'il pensait en la choisissant est gardé (self.pensees)."""
        s = self.au_trait()
        x = self.indice() if self.camp(s) else self.carte_defense()
        self.pensees.append(self.pensee(s, x))
        return x

    def croyance(self, s):
        """Ce que croit le joueur s (le déclarant pour le mort) des mains qu'il ne voit pas : modele.Modele.pensees,
        le modèle de chaque place gardé et mis à jour carte après carte."""
        import modele
        vue = self.decl if s == self.mort() else s
        lettre = dict(zip("SHDC", COULEURS))
        jouees = [(x, lettre[j[0]] + j[1:].translate(FR)) for x, j in zip(self.pos.sieges, self.pos.jouees)]
        if not hasattr(self, "_croyances"): self._croyances = {}
        try:
            m = self._croyances.get(vue)
            mort = self.mort() if jouees else None
            m = m.suite(jouees, mort) if m and mort else modele.Modele(self.d, vue, self.encheres, jouees, mort=mort,
                                                                       graine=len(jouees), n=200, efficace=80, n_max=800)
            self._croyances[vue] = m
            return m.pensees()
        except Exception:
            return []

    def pensee(self, s, x, humain=False):
        """La pensée d'une carte : qui la joue, la carte, ce qu'il croyait et les scores des cartes qu'il avait (pour un
        robot : son dernier calcul). Tout en texte et nombres, pour être gardé avec la donne."""
        ch = self.dernier if self.dernier and self.dernier.get("siege") == s else None
        return dict(n=len(self.pos.jouees), siege=s, carte=carte_fr(*x), humain=humain,
                    role="declarant" if self.camp(s) else "defense",
                    croyance=[] if humain else self.croyance(s), mondes=ch["mondes"] if ch else 0,
                    force=bool(ch and ch["force"]),
                    scores={carte_fr(*k): list(v) for k, v in (ch["scores"].items() if ch else [])})

    def premiere(self):
        """La carte d'entame jouée (couleur, rang anglais), ou None."""
        if not self.pos.jouees: return None
        j = self.pos.jouees[0]
        return dict(zip("SHDC", COULEURS))[j[0]], j[1:]

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

    def _mondes_modele(self, s, k):
        """k donnes tirées, selon leur poids, dans le modèle des mains cachées vu du défenseur s (modele.py) :
        les enchères refaites par le moteur, l'entame, les cartes jouées, les chicanes. Le modèle de chaque défenseur
        est gardé d'une carte à l'autre et seulement mis à jour."""
        import modele
        lettre = dict(zip("SHDC", COULEURS))
        jouees = [(x, lettre[j[0]] + j[1:].translate(FR)) for x, j in zip(self.pos.sieges, self.pos.jouees)]
        if not hasattr(self, "_modeles"): self._modeles = {}
        m = self._modeles.get(s)
        m = m.suite(jouees) if m else modele.Modele(self.d, s, self.encheres, jouees, mort=self.mort(),
                                                     graine=self.rnd.random())
        self._modeles[s] = m
        ms = m.mondes(); ws = m.poids()
        if not ms: return []
        return [mains for mains in self.rnd.choices([x for x, _ in ms], weights=ws, k=k)]

    # ---------------------------------------------------------------- la défense
    def _mondes(self, s, k):
        if MODELE: return self._mondes_modele(s, k)
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
        s = self.au_trait(); leg = self.legales(); self.difficile = False
        self.dernier = dict(role="defense", siege=s, mondes=0, scores={}, force=len(leg) == 1)
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
        self.dernier.update(mondes=len(dd), scores={x: (chute[x], total[x]) for x in leg})
        cle = lambda x: (chute[x], total[x])
        meilleure = max(leg, key=lambda x: (chute[x], total[x], RANGS.index(x[1])))
        # difficile : la meilleure carte ne fait chuter que dans un ou deux mondes de plus qu'une autre (l'application
        # réfléchit plus longtemps) ; si toutes chutent aussi souvent, rien ne se décide ici
        moins = [chute[x] for x in leg if chute[x] < chute[meilleure]]
        self.difficile = bool(moins) and chute[meilleure] - max(moins) <= max(1, len(dd) // 16)
        return meilleure

    def defendre(self, sur_carte=None):
        """Joue les cartes de la défense jusqu'au tour du déclarant (ou du mort), ou jusqu'à la fin."""
        while not self.fini() and not self.camp(self.au_trait()):
            c = self.carte_defense(); self.poser(c)
            if sur_carte: sur_carte(c)

    # ---------------------------------------------------------------- l'aide au déclarant
    def indice(self):
        """La carte que jouerait le déclarant simulé (lignes.py), qui ne voit que le déclarant et le mort ; pour un
        défenseur au trait, celle de la défense (carte_defense)."""
        if not self.camp(self.au_trait()): return self.carte_defense()
        if MODELE_DECLARANT == "suivi":                   # le modèle du déclarant, mis à jour à chaque carte
            import modele
            lettre = dict(zip("SHDC", COULEURS))
            jouees = [(x, lettre[j[0]] + j[1:].translate(FR)) for x, j in zip(self.pos.sieges, self.pos.jouees)]
            m = getattr(self, "_modele_decl", None)
            m = m.suite(jouees) if m else modele.Modele(self.d, self.decl, self.encheres, jouees, mort=self.mort(),
                                                         graine=self.rnd.random())
            self._modele_decl = m
            ms = m.mondes(); ws = m.poids()
            if ms: self._pool = self.rnd.choices([mm for mm, _ in ms], weights=ws, k=40)
        import lignes
        if self._pool is None:
            if MODELE_DECLARANT:                          # les donnes imaginées par le modèle, vu du déclarant après l'entame
                import modele
                m = modele.Modele(self.d, self.decl, self.encheres, [(LHO[self.decl], carte_fr(*(self.premiere() or self.entame)))],
                                  mort=self.mort(), graine=self.rnd.random())
                ms = m.mondes(); ws = m.poids()
                self._pool = [x for x in self.rnd.choices([mm for mm, _ in ms], weights=ws, k=40)] if ms else []
            if not self._pool:
                self._pool = donnes_du_declarant(self.d, self.decl, self.encheres, carte_fr(*(self.premiere() or self.entame)), 40)
        vides = {x: set(LETTRE[c] for c in self.vides[x]) for x in (LHO[self.decl], RHO[self.decl])}
        details = {}
        x = lignes._carte(self.pos, self._pool, vides, self.besoin, 12, random.Random(len(self.pos.jouees)), details)
        self.dernier = dict(role="declarant", siege=self.au_trait(), mondes=details.get("mondes", 0),
                            scores=details.get("scores", {}), force=len(self.legales()) == 1)
        return x

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


NOMS = {"N": "Nord", "S": "Sud", "E": "Est", "O": "Ouest"}


def texte_pensee(pz, decl):
    """La pensée d'une carte en français : {"titre", "raison", "croyance": [lignes]}. pz : Partie.pensee."""
    import re
    t = _texte_pensee(pz, decl)
    t["raison"] = re.sub(r"\b([01]) mondes\b", r"\1 monde", t["raison"])   # 0 ou 1 monde, au singulier
    return t


def _texte_pensee(pz, decl):
    mort = PART[decl]
    qui = "Le déclarant, au mort," if pz["siege"] == mort else NOMS[pz["siege"]]
    titre = f"{qui} joue {pz['carte']}"
    if pz["humain"]:
        titre = f"Vous jouez {pz['carte']}" + (" au mort" if pz["siege"] == mort else "")
        a = pz.get("avis")
        if not a: return dict(titre=titre, raison="", croyance=[])
        m = a.get("mondes") or 0; sc = a.get("scores") or {}
        but = "faire chuter le contrat" if pz["role"] == "defense" else "gagner le contrat"
        if a["carte"] == pz["carte"] or (m and sc.get(a["carte"]) == sc.get(pz["carte"])):
            raison = "Le programme aurait joué la même carte (ou une carte équivalente)."
        elif not m: raison = f"Le programme aurait joué {a['carte']}."
        else:
            v, w = sc.get(pz["carte"], [0, 0]), sc.get(a["carte"], [0, 0])
            raison = (f"À votre place, le programme aurait joué {a['carte']} : pour {but}, elle réussit dans {w[0]} mondes sur {m}, "
                      f"la vôtre dans {v[0]}.")
            if v[0] == w[0]: raison = (f"À votre place, le programme aurait joué {a['carte']} : autant de chances de {but} "
                                       f"({w[0]} sur {m}), mais plus de levées en moyenne.")
        return dict(titre=titre, raison=raison, croyance=list(a.get("croyance") or []))
    sc, m = pz.get("scores") or {}, pz.get("mondes") or 0
    virgule = lambda x: f"{x:.1f}".replace(".", ",")
    camp = "la défense" if pz["role"] == "defense" else "le déclarant"
    if pz.get("force") or len(sc) <= 1: raison = "Carte forcée."
    elif not m: raison = ""
    else:
        a, t = sc.get(pz["carte"], [0, 0])
        but = "faire chuter le contrat" if pz["role"] == "defense" else "gagner le contrat"
        moins = {}                                     # les cartes qui réussissent moins souvent, une par résultat
        for k, (x, y) in sc.items():
            if x < a: moins.setdefault(x, k)
        alt = ", ".join(f"{k} : {x} sur {m}" for x, k in sorted(moins.items(), reverse=True)[:2])
        moins_lev = any(x == a and y < t for k, (x, y) in sc.items() if k != pz["carte"])
        if (a == 0 or a == m) and not moins:           # rien ne se décide sur le contrat : on joue pour les levées
            etat = ("le contrat est gagné" if (pz["role"] == "defense") == (a == 0) else "le contrat chute")
            raison = f"Dans toutes les donnes qu'il imagine, {etat} ; il cherche le plus de levées pour {camp}"
            raison += f" : {virgule(t / m)} en moyenne avec cette carte" + (" (moins avec les autres)." if moins_lev else ".")
        elif not moins and not moins_lev:
            raison = f"Ses cartes se valent : chacune peut {but} dans {a} mondes sur {m} ; il joue la plus petite."
        else:
            raison = f"Pour {but} : cette carte réussit dans {a} mondes sur {m}"
            raison += f" ({alt})" if alt else ""
            raison += ", et donne le plus de levées." if moins_lev else "."
    return dict(titre=titre, raison=raison, croyance=list(pz.get("croyance") or []))


def avis_programme(d, contrat, decl, encheres, humain, cartes, k):
    """Ce que le programme aurait joué à la place du joueur pour la carte k (cartes : toutes les cartes jouées,
    (couleur, rang anglais)) : sa carte, les scores de chaque carte possible, ce qu'il croyait. Pour la relecture."""
    q = Partie(d, contrat, decl, encheres, humain=humain)
    for x in cartes[len(q.pos.jouees):k]: q.poser(x)
    s = q.au_trait(); x = q.indice()
    ch = q.dernier or {}
    return dict(carte=carte_fr(*x), mondes=ch.get("mondes", 0),
                scores={carte_fr(*kk): list(v) for kk, v in (ch.get("scores") or {}).items()}, croyance=q.croyance(s))
