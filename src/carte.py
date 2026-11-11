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
MODELE = True                                             # les mondes de la défense viennent du modèle des mains cachées (modele.py), qui lit les signaux du partenaire : face à notre déclarant simulé, 598 donnes, +0,135 levée par donne (± 0,037) et 216 chutes au lieu de 201 (essai_defense.py, 2026-11-11)
MONDES_DECLARANT = 12                                     # mondes imaginés par carte du déclarant simulé
COUPS_A_VENIR = True                                      # le déclarant regarde si la suite passe par un squeeze, une mise en main
SIGNAUX = True                                            # les défenseurs signalent (appel, parité) entre cartes équivalentes
HABITUDES = True                                          # les habitudes classiques (second en main petit, troisième haut, couvrir un
                                                          # honneur) départagent des cartes presque égales ; les mondes décident d'abord.
                                                          # Neutre (essai_defense.py, 2 × 600 donnes : +0,015 ± 0,013 et −0,007 ± 0,012),
                                                          # gardé : le jeu paraît naturel et les pensées nomment l'habitude
TOLERANCE_LEVEES = 1 / 16                                 # « presque égales » : autant de chutes, au plus 1/16 de levée de moins par monde
SEQUENCE = True                                           # en tête (hors entame), la plus haute d'une séquence d'honneurs : neutre
                                                          # (0,000 ± 0,014), gardé : un partenaire humain le lit comme à la table
MONDES_DIFFICILE = 16                                     # > MONDES : sur une carte difficile, plus de mondes ; 48 essayé (600 donnes,
                                                          # essai_defense.py, 2026-11-11) : −0,005 levée (± 0,030), plus lent : non gardé
PREF_COUPE = False                                        # en donnant une coupe, la hauteur demande le retour : rare, −0,005 (± 0,004) : non gardé
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
        plan = ""
        if not humain and self.camp(s) and getattr(self, "_plan_neuf", False):
            plan = self.plan; self._plan_neuf = False      # le plan, avec la première carte du déclarant
        cv = (ch or {}).get("coups") or {}
        coups = [dict(type=t, joueur=j, n=v, sur=cv["n"]) for (t, j), v in
                 ((k, v) for k, v in cv.items() if k != "n") if v * 3 >= cv.get("n", 99)]   # au moins un tiers des donnes
        return dict(n=len(self.pos.jouees), siege=s, carte=carte_fr(*x), humain=humain, plan=plan, coups=coups,
                    signal=(ch.get("signal") if ch and ch.get("role") == "defense" else None),
                    suit=(ch.get("suit") if ch and ch.get("role") == "defense" else None),   # la demande du partenaire suivie
                    habitude=(ch.get("habitude") if ch and ch.get("role") == "defense" else None),
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

    def _mondes_modele(self, s, k, encore=False):
        """k donnes tirées, selon leur poids, dans le modèle des mains cachées vu du défenseur s (modele.py) :
        les enchères refaites par le moteur, l'entame, les cartes jouées, les chicanes. Le modèle de chaque défenseur
        est gardé d'une carte à l'autre et seulement mis à jour."""
        import modele
        lettre = dict(zip("SHDC", COULEURS))
        jouees = [(x, lettre[j[0]] + j[1:].translate(FR)) for x, j in zip(self.pos.sieges, self.pos.jouees)]
        if not hasattr(self, "_modeles"): self._modeles = {}
        m = self._modeles.get(s)
        if encore and m: pass                             # mêmes cartes jouées : le même modèle, d'autres tirages
        else: m = m.suite(jouees) if m else modele.Modele(self.d, s, self.encheres, jouees, mort=self.mort(),
                                                     graine=self.rnd.random())
        self._modeles[s] = m
        ms = m.mondes(); ws = m.poids()
        if not ms: return []
        return [mains for mains in self.rnd.choices([x for x, _ in ms], weights=ws, k=k)]

    # ---------------------------------------------------------------- la défense
    def _mondes(self, s, k, encore=False):
        if MODELE: return self._mondes_modele(s, k, encore)
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

    def _scores(self, mondes, leg):
        """Chaque carte légale jouée dans chaque monde, résolu au double mort : {carte: chutes}, {carte: levées de la
        défense}, nombre de mondes résolus."""
        from endplay.dds import solve_all_boards
        from endplay.types import Card
        dd = []
        for m in mondes:
            x = _donne_dds(m, self.den, self.decl)
            for j in self.pos.jouees: x.play(Card(j))
            dd.append(x)
        chute = {c: 0 for c in leg}; total = {c: 0 for c in leg}
        if not dd: return chute, total, 0
        reste = max(sum(len(p) for p in self.pos.reste[x].values()) for x in ROT)   # levées à jouer, pli en cours compris
        for sol in solve_all_boards(dd):
            v = {(str(a)[0], str(a)[1:]): t for a, t in sol}
            prec = {}
            for c, r in leg:                               # une carte absente vaut sa voisine équivalente
                t = v.get((c, r), prec.get(c, 0)); prec[c] = t
                decl_final = self.pos.gagnes + (reste - t)  # t : levées de la défense à partir d'ici
                chute[(c, r)] += decl_final < self.besoin; total[(c, r)] += t
        return chute, total, len(dd)

    def _difficile(self, leg, chute, meilleure, n):
        """La meilleure carte ne fait chuter que dans un ou deux mondes de plus qu'une autre."""
        moins = [chute[x] for x in leg if chute[x] < chute[meilleure]]
        return bool(moins) and chute[meilleure] - max(moins) <= max(1, n // 16)

    def _touche(self, s, c, haut, bas):
        """Les rangs haut et bas (anglais) de la couleur c se touchent pour s : chaque rang entre les deux est déjà
        joué ou dans sa main."""
        i, j = RANGS.index(haut), RANGS.index(bas)
        return all(LETTRE[c] + r in self.pos.jouees or r in self.pos.reste[s][c] for r in RANGS[i + 1:j])

    def habitude(self, s, leg, chute, total, meilleure, n):
        """(carte, texte) : l'habitude classique, si elle choisit une carte presque aussi bonne dans les mondes (même
        nombre de chutes, au plus TOLERANCE_LEVEES levée de moins par monde) ; None sinon. Les habitudes ne sont pas
        toujours justes : elles ne départagent que ce que les mondes laissent ouvert."""
        pli = self.pos.pli
        if not pli or len(pli) == 3: return None
        proches = [x for x in leg if chute[x] == chute[meilleure] and total[x] >= total[meilleure] - TOLERANCE_LEVEES * n]
        c0 = pli[0][1]
        miennes = sorted((x for x in proches if x[0] == c0), key=lambda x: RANGS.index(x[1]))   # de la plus haute
        if not miennes: return None
        haut = lambda r, q: RANGS.index(r) < RANGS.index(q)
        if len(pli) == 1 and self.camp(pli[0][0]):     # second en main
            r0 = pli[0][2]
            if r0 in "KQJT":
                du_mort = pli[0][0] == self.mort()
                suivante = RANGS[RANGS.index(r0) + 1]
                if not (du_mort and suivante in self.pos.reste[self.mort()][c0]):   # couvrir le dernier des honneurs
                    plus = [x for x in miennes if haut(x[1], r0) and x[1] in "AKQJ"]
                    if plus: return plus[-1], "Il couvre l'honneur par un honneur."
            return miennes[-1], "Second en main, il joue petit."
        if len(pli) == 2 and pli[0][0] == PART[s]:     # troisième en main, sur l'entame du partenaire
            atout = self.den if self.den in COULEURS else None
            gagne = max(pli, key=lambda x: (x[1] == atout, x[1] == c0, -RANGS.index(x[2])))
            if gagne[1] != c0: return None              # coupé : rien à monter
            if self.camp(gagne[0]) or pli[0][2] not in "AKQJT":
                plus = [x for x in miennes if haut(x[1], gagne[2])]
                if plus:
                    x = plus[-1]                         # la plus petite qui suffit (la plus basse de ses équivalentes)
                    if self.camp(gagne[0]) or x != miennes[-1]:
                        return x, "Troisième en main, il joue haut (la plus petite qui suffit)."
            return miennes[-1], None
        return None

    def carte_defense(self):
        """La carte du défenseur au trait : celle qui fait chuter le contrat dans le plus de mondes imaginés."""
        s = self.au_trait(); leg = self.legales(); self.difficile = False
        self.dernier = dict(role="defense", siege=s, mondes=0, scores={}, force=len(leg) == 1)
        if len(leg) == 1: return leg[0]
        mondes = self._mondes(s, MONDES)
        chute, total, n = self._scores(mondes, leg)
        if not n: return leg[-1]
        cle = lambda x: (chute[x], total[x])
        meilleure = max(leg, key=lambda x: (chute[x], total[x], RANGS.index(x[1])))
        if MONDES_DIFFICILE > MONDES and self._difficile(leg, chute, meilleure, n):   # une carte difficile : plus de mondes
            plus = self._mondes(s, MONDES_DIFFICILE - MONDES, encore=True)
            c2, t2, n2 = self._scores(plus, leg)
            for x in leg: chute[x] += c2[x]; total[x] += t2[x]
            n += n2; mondes = mondes + plus
            meilleure = max(leg, key=lambda x: (chute[x], total[x], RANGS.index(x[1])))
        self._vus_mondes = mondes                        # gardés pour le vœu du signal (voeu)
        self.dernier.update(mondes=n, scores={x: (chute[x], total[x]) for x in leg})
        avec_signal = True
        if HABITUDES:
            h = self.habitude(s, leg, chute, total, meilleure, n)
            if h and h[0] != meilleure:
                meilleure = h[0]
                if h[1]: self.dernier["habitude"] = h[1]
                if h[1] and not h[1].startswith("Second"): avec_signal = False   # couvrir, monter : pas de signal
        egales = [x for x in leg if cle(x) == cle(meilleure)]
        if not self.pos.pli and self.pos.jouees:         # en tête, hors entame
            if SIGNAUX:                                  # parmi les cartes aussi bonnes, ce que le partenaire a demandé
                dem = self.demande(s)
                if dem:
                    suivies = [x for x in egales if x[0] == dem["couleur"]]
                    if suivies and meilleure[0] != dem["couleur"]:
                        meilleure = max(suivies, key=lambda x: RANGS.index(x[1]))
                    if meilleure[0] == dem["couleur"]: self.dernier["suit"] = dem["texte"]
            c = meilleure[0]
            memes = sorted((x for x in egales if x[0] == c), key=lambda x: RANGS.index(x[1]))
            if SEQUENCE and len(memes) >= 2 and memes[0][1] in "AKQJT" and self._touche(s, c, memes[0][1], memes[1][1]):
                meilleure = memes[0]; self.dernier["habitude"] = "En tête, il mène la plus haute de sa séquence."
            elif PREF_COUPE and SIGNAUX:
                sig = self.signal_coupe(s, memes)
                if sig: meilleure, self.dernier["signal"] = sig
        elif SIGNAUX and avec_signal and self.pos.pli:   # entre cartes aussi bonnes, celle qui renseigne le partenaire
            sig = self.signal(s, egales)
            if sig: meilleure, self.dernier["signal"] = sig
        # difficile : l'application réfléchit plus longtemps ; si toutes chutent aussi souvent, rien ne se décide ici
        self.difficile = self._difficile(leg, chute, meilleure, n)
        return meilleure

    def signal_coupe(self, s, memes):
        """En menant une couleur que le partenaire va couper : la hauteur de la carte demande le retour (haute : la plus
        chère des deux autres couleurs hors atout ; basse : la moins chère), selon les donnes imaginées (voeu)."""
        import signaux
        if self.den not in COULEURS or len(memes) < 2: return None
        c = memes[0][0]; p = PART[s]
        if c == self.den or c not in self.vides[p] or self.den in self.vides[p]: return None
        deux = signaux.autres(self.den, c, c)
        if len(deux) < 2: return None
        v = self.voeu(s)
        pref = max(deux, key=lambda k: v.get(k, -1))
        choix = signaux.carte_coupe([x[1] for x in memes], pref, deux)
        return ((c, choix[0]), choix[1]) if choix else None

    def voeu(self, s):
        """Ce que veut le défenseur s, lu dans ses donnes imaginées (pas une règle fixe : selon la situation) : si son
        partenaire avait la main au début de ce pli, quelle couleur rapporterait le plus à la défense au double mort.
        {couleur: levées moyennes de la défense}, la meilleure entame du partenaire dans chaque couleur."""
        from endplay.dds import solve_board
        from endplay.types import Player
        import signaux
        lettre = dict(zip("SHDC", COULEURS))
        k = len(self.pos.jouees) - len(self.pos.pli)    # les plis finis
        jouees = {}
        for x, j in zip(self.pos.sieges[:k], self.pos.jouees[:k]): jouees.setdefault(x, set()).add(lettre[j[0]] + j[1:].translate(FR))
        somme = {c: 0.0 for c in COULEURS}; n = {c: 0 for c in COULEURS}
        for m in getattr(self, "_vus_mondes", [])[:MONDES]:
            reste = {}
            for x in ROT:
                parts = m[x].split()
                reste[x] = " ".join("".join(r for r in (parts[i] if parts[i] != "-" else "") if c + r not in jouees.get(x, ()))
                                    or "-" for i, c in enumerate(COULEURS))
            try:
                deal = _donne_dds(reste, self.den, self.decl)
                deal.first = {"N": Player.north, "E": Player.east, "S": Player.south, "O": Player.west}[PART[s]]
                meilleur = {}
                for carte, t in solve_board(deal):
                    c = str(carte)[0]; meilleur[c] = max(meilleur.get(c, 0), t)
            except Exception:
                continue
            for c, t in meilleur.items(): somme[c] += t; n[c] += 1
        return {c: somme[c] / n[c] for c in COULEURS if n[c]}

    def signal(self, s, egales):
        """(carte, sens) : le signal du défenseur s parmi des cartes également bonnes, ou None (signaux.py, entames.md).
        Sur la couleur du partenaire, la première fois : pair-impair (impaire = continuez ; paire = changez, haute ou
        basse pour la couleur voulue). Défausse : préférence de couleur. Couleur du déclarant : la parité. Ce que le
        défenseur veut vient de ses donnes imaginées (voeu), selon la situation."""
        import signaux
        if len(egales) < 2: return None
        pli = self.pos.pli
        if not pli: return None                         # en tête : pas de signal (le choix de la carte d'attaque)
        c0, meneur = pli[0][1], pli[0][0]
        memes = [x for x in egales if x[0] == c0]
        deja = any(x == s and j[0] == LETTRE[c0] for x, j in zip(self.pos.sieges, self.pos.jouees))
        if memes and deja: return None                  # le signal se donne la première fois qu'on joue la couleur
        if memes and c0 == self.den: return None        # à l'atout : ni pair-impair ni parité
        if memes:
            if len(memes) < 2: return None
            rangs = [x[1] for x in memes]
            if meneur == PART[s]:                       # le partenaire mène : pair-impair
                v = self.voeu(s)
                if c0 not in v: return None
                deux = signaux.autres(self.den, c0, c0)
                continuer = v[c0] >= max([v[c] for c in v if c != c0] or [0]) - 0.25
                pref = max(deux, key=lambda c: v.get(c, -1)) if deux else None
                choix = signaux.carte_attitude(rangs, continuer, pref, deux)
            elif self.camp(meneur):                     # le déclarant mène : la parité
                choix = signaux.carte_parite(rangs, len(self.pos.reste[s][c0]))
            else:
                return None
            return ((c0, choix[0]), choix[1]) if choix else None
        if c0 != self.den and not any(x[0] == self.den for x in egales):   # une défausse (pas une coupe)
            par = {}
            for c, r in egales: par.setdefault(c, []).append(r)
            v = self.voeu(s)
            ordre = sorted(COULEURS, key=lambda c: -v.get(c, -1))
            choix = signaux.carte_defausse(par, ordre, self.den, c0)
            return choix
        return None

    def demande(self, s):
        """La dernière demande du partenaire de s, lue dans ses signaux (signaux.lire) : {"couleur", "texte"} ou None."""
        import signaux
        p = PART[s]; out = None; vu = set()
        for i in range(0, len(self.pos.jouees) - len(self.pos.pli), 4):
            sieges = self.pos.sieges[i:i + 4]; cartes = self.pos.jouees[i:i + 4]
            c0 = dict(zip("SHDC", COULEURS))[cartes[0][0]]; meneur = sieges[0]
            if PREF_COUPE and meneur == p and self.den in COULEURS and c0 != self.den:   # il m'a donné une coupe
                j = cartes[sieges.index(s)]
                if dict(zip("SHDC", COULEURS))[j[0]] == self.den:
                    rang = cartes[0][1:]
                    m = signaux.lire(rang, "coupe", c0, self.den, c0)
                    if m.get("prefere"):
                        out = {"couleur": m["prefere"], "texte": signaux.phrase(NOMS[p], c0 + rang.translate(FR), "coupe", c0, self.den)}
            for x, j in zip(sieges[1:], cartes[1:]):
                if x != p: continue
                c = dict(zip("SHDC", COULEURS))[j[0]]; rang = j[1:]
                if c == c0:
                    if (x, c0) in vu or c0 == self.den: continue
                    vu.add((x, c0))
                    if meneur != s: continue            # seule l'attitude sur notre couleur dit quoi rejouer
                    m = signaux.lire(rang, "attitude", c0, self.den, c0)
                    if m.get("continuer"): out = {"couleur": c0, "texte": signaux.phrase(NOMS[x], c + rang.translate(FR), "attitude", c0, self.den)}
                    elif m.get("prefere"): out = {"couleur": m["prefere"], "texte": signaux.phrase(NOMS[x], c + rang.translate(FR), "attitude", c0, self.den)}
                elif c != self.den:
                    m = signaux.lire(rang, "défausse", c, self.den, c0)
                    if m.get("prefere"): out = {"couleur": m["prefere"], "texte": signaux.phrase(NOMS[x], c + rang.translate(FR), "défausse", c, self.den, c0)}
        return out

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
        if not hasattr(self, "plan"):                     # sa première carte : le déclarant fait son plan (jeu.plan_de_jeu)
            try:
                from jeu import plan_de_jeu
                e = self.premiere() or self.entame
                self.plan = plan_de_jeu(self.d, self.contrat, self.decl, {"joueur": LHO[self.decl], "carte": carte_fr(*e)},
                                        self.encheres, simuler=False, verdict=False)
            except Exception:
                self.plan = ""
            self._plan_neuf = True
        details = {}
        x = lignes._carte(self.pos, self._pool, vides, self.besoin, MONDES_DECLARANT, random.Random(len(self.pos.jouees)), details)
        self.dernier = dict(role="declarant", siege=self.au_trait(), mondes=details.get("mondes", 0),
                            scores=details.get("scores", {}), force=len(self.legales()) == 1)
        if not self.pos.pli and COUPS_A_VENIR:          # en tête d'un pli : la suite passe-t-elle par un coup ?
            self.dernier["coups"] = self.coups_a_venir(vides)
        return x

    def coups_a_venir(self, vides, k=8):
        """Dans k donnes imaginées par le déclarant, la suite au double mort passe-t-elle par un squeeze ou une mise en
        main ? {"n": k, (type, joueur): nombre de donnes}. Seulement ce que le déclarant peut imaginer."""
        import lignes
        from coups import coups_a_venir
        mondes = lignes._mondes(self.pos, self._pool, vides, k, random.Random(len(self.pos.jouees) + 7))
        out = {"n": len(mondes)}
        for m in mondes:
            try:
                for c in coups_a_venir(m, self.den, self.decl, self.pos.jouees):
                    out[c] = out.get(c, 0) + 1
            except Exception:
                pass
        return out

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


def sens_signal(sig, c):
    """Ce que dit un signal (carte.Partie.signal, signaux.py), en français : « impaire à ♥ : il demande de continuer »."""
    if sig == "impair": return f"impaire à {c} : il demande de continuer la couleur"
    if sig == "pair": return f"paire à {c} : il demande de changer de couleur"
    if sig.startswith("pair "):
        h, x = sig[5:].split(":")
        return f"paire {'haute' if h == 'haut' else 'basse'} à {c} : il demande de changer, pour {x}"
    if sig.startswith("coupe "):
        h, x = sig[6:].split(":")
        return f"{c} {'haut' if h == 'haute' else 'bas'} pour la coupe : il demande le retour à {x}"
    if sig.startswith("défausse"):
        morceaux = sig.split(":")
        if len(morceaux) == 3:
            h = "haute" if morceaux[0].endswith("haute") else "basse"
            return f"défausse {h} à {morceaux[1]} : il ne veut pas de {morceaux[1]} et préfère {morceaux[2]}"
        return f"défausse à {morceaux[1]} : il ne veut pas de {morceaux[1]}"
    return {"appel": f"un appel à {c} : il aime la couleur", "refus": f"un refus à {c} : il n'aime pas la couleur",
            "parité paire": f"la parité à {c} : un nombre pair de cartes (grosse puis petite)",
            "parité impaire": f"la parité à {c} : un nombre impair de cartes (la plus petite)"}.get(sig, sig)


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
    for c in pz.get("coups") or []:
        quoi = "un squeeze sur" if c["type"] == "squeeze" else "une mise en main de"
        raison = (raison + " " if raison else "") + (f"Dans {c['n']} de ses {c['sur']} donnes imaginées, la suite passe par "
                                                     f"{quoi} {NOMS[c['joueur']]} : il garde ses menaces et ses communications.")
    sig = pz.get("signal")
    if sig:
        sens = sens_signal(sig, pz["carte"][0])
        if raison.endswith(" ; il joue la plus petite."):           # une seule phrase : ses cartes se valent, il signale
            raison = raison[:-len(" ; il joue la plus petite.")] + f" ; il choisit celle qui signale : {sens}."
        else:
            raison = (raison + " " if raison else "") + f"Parmi les cartes qui se valent, il choisit celle qui signale : {sens}."
    if pz.get("habitude"):                                 # une habitude classique départage des cartes presque égales
        raison = (raison + " " if raison else "") + pz["habitude"][:-1] + " : ses donnes imaginées laissent le choix."
    if pz.get("suit"):                                     # en tête, il suit la demande de son partenaire
        raison = (raison + " " if raison else "") + pz["suit"] + " Parmi les cartes qui se valent, il le suit."
    return dict(titre=titre, raison=raison, croyance=list(pz.get("croyance") or []), plan=pz.get("plan") or "")


def avis_programme(d, contrat, decl, encheres, humain, cartes, k):
    """Ce que le programme aurait joué à la place du joueur pour la carte k (cartes : toutes les cartes jouées,
    (couleur, rang anglais)) : sa carte, les scores de chaque carte possible, ce qu'il croyait. Pour la relecture."""
    q = Partie(d, contrat, decl, encheres, humain=humain)
    for x in cartes[len(q.pos.jouees):k]: q.poser(x)
    s = q.au_trait(); x = q.indice()
    ch = q.dernier or {}
    return dict(carte=carte_fr(*x), mondes=ch.get("mondes", 0),
                scores={carte_fr(*kk): list(v) for kk, v in (ch.get("scores") or {}).items()}, croyance=q.croyance(s))


def analyse_jeu(d, contrat, decl, cartes):
    """Le jeu réel revu cartes vues (double mort), pour le résumé : pour chaque carte, ce qu'elle coûte en levées
    face à la meilleure carte de ce joueur à ce moment, et les coups qui se présentaient (squeeze, mise en main,
    laisser-passer ou coup à blanc), joués ou manqués. cartes : [(couleur, rang anglais)] dans l'ordre.
    {"dm": levées du déclarant au double mort au départ, "cartes": [{k, siege, carte, perte, pli}], "coups": [...]}"""
    from coups import squeeze, mise_en_main, baisse
    den = contrat[1:].rstrip("X")
    pos = Position(d["mains"], den, decl)
    out, coups, dm = [], [], None
    for k, x in enumerate(cartes):
        s = pos.au_trait()
        try:
            v = pos.valeurs()
        except Exception:
            v = {}
        if v:
            meilleur = (max if pos.camp(s) else min)(v.values())
            if dm is None: dm = meilleur
            val = v.get(x)
            if val is None:                                # une carte équivalente à une autre : la même valeur
                val = next((v[y] for y in v if y[0] == x[0]), meilleur)
            perte = (meilleur - val) if pos.camp(s) else (val - meilleur)
            if not pos.camp(s) and squeeze(pos, v):
                coups.append(dict(type="squeeze", pli=pos.n, joueur=s, k=k))
            if mise_en_main(pos, meilleur):
                coups.append(dict(type="mise en main", pli=pos.n, joueur=s, k=k))
            b = baisse(pos, v)
            if b:
                joue = val == meilleur                     # le déclarant a-t-il trouvé la carte qui gagne la levée ?
                coups.append(dict(type=b[0], pli=pos.n, couleur=b[1], gain=b[2], joue=joue, joueur=s, k=k))
        else:
            perte = 0
        out.append(dict(k=k, siege=s, carte=carte_fr(*x), perte=perte, pli=pos.n))
        pos.jouer(*x)
    return dict(dm=dm, cartes=out, coups=coups)


def resume_donne(d, contrat, decl, humain, cartes, pensees, levees):
    """Le résumé écrit de la donne jouée, en paragraphes : le résultat face au double mort, les cartes qui ont coûté
    une levée (cartes vues), les coups (squeeze, mise en main, laisser-passer), les signaux de la défense, ce que
    croyaient les joueurs du programme comparé aux vraies mains, et vos cartes."""
    import re
    a = analyse_jeu(d, contrat, decl, cartes)
    mort = PART[decl]; besoin = int(contrat[0]) + 6
    def nom(s, sujet=True):
        if humain is not None and (s == humain or (s == mort and humain == decl)): return "vous" if not sujet else "Vous"
        if s == mort: return "le mort" if not sujet else "Le mort"
        return NOMS[s]
    out = []
    ecart = levees - besoin
    res = "gagné tout juste" if ecart == 0 else f"gagné avec {ecart} de mieux" if ecart > 0 else f"chute de {-ecart}"
    t = f"{contrat} par {NOMS[decl]} : {levees} levées, contrat {res}."
    if a["dm"] is not None:
        t += f" Cartes vues (double mort), le contrat en donnait {a['dm']}"
        t += "." if a["dm"] == levees else (f" : le déclarant a fait {levees - a['dm']} de mieux, grâce à la défense." if levees > a["dm"]
                                           else f" : {a['dm'] - levees} levée{'s' if a['dm'] - levees > 1 else ''} de moins.")
    out.append(t)
    couteuses = [z for z in a["cartes"] if z["perte"] > 0]
    if couteuses:
        lignes = [f"pli {z['pli']}, {nom(z['siege'], False)} : {z['carte']} ({z['perte']} levée{'s' if z['perte'] > 1 else ''})"
                  for z in couteuses[:6]]
        out.append("Les cartes qui ont coûté, cartes vues : " + " ; ".join(lignes) + ".")
    else:
        out.append("Aucune carte n'a coûté de levée, cartes vues : chacun a joué au mieux.")
    vus = []
    for c in a["coups"]:
        if c["type"] == "squeeze": vus.append(f"{NOMS[c['joueur']]} a été squeezé au pli {c['pli']}")
        elif c["type"] == "mise en main": vus.append(f"{NOMS[c['joueur']]} a été mis en main au pli {c['pli']}")
        else:
            g = f"{c['gain']} levée{'s' if c['gain'] > 1 else ''}"
            vus.append(f"{c['type']} à {c['couleur']} au pli {c['pli']} : " + ("trouvé" if c["joue"] else f"manqué, il rapportait {g}"))
    out.append(("Les coups : " + " ; ".join(vus) + ".") if vus else "Pas de squeeze ni de mise en main dans cette donne.")
    plan = next((z["plan"] for z in pensees if z.get("plan")), "")
    if plan:
        import re as _re
        out.insert(1, "Le plan du déclarant, à sa première carte : " + _re.sub(r"<[^>]+>", " ", plan).replace("  ", " ").strip())
    sig = [f"{NOMS[z['siege']]} ({z['carte']}) : {sens_signal(z['signal'], z['carte'][0])}" for z in pensees if z.get("signal")]
    if sig: out.append("Les signaux de la défense : " + " ; ".join(sig[:8]) + ".")
    cr = []                                                # ce qu'ils croyaient, face aux vraies mains
    for z in pensees:
        if z.get("humain") or not z.get("croyance"): continue
        for ligne in z["croyance"]:
            m = re.match(r"(\w+) : (\d+)(?:–(\d+))? H", ligne)
            if not m: continue
            s = {v: k for k, v in NOMS.items()}.get(m.group(1))
            if not s: continue
            vrai = sum(PTS.get(r, 0) for r in d["mains"][s].replace(" ", ""))
            lo, hi = int(m.group(2)), int(m.group(3) or m.group(2))
            cr.append((z["siege"], s, lo, hi, vrai))
        if len(cr) >= 2: break
    if cr:
        out.append("Ce qu'ils croyaient à leur première carte : " + " ; ".join(
            f"{NOMS[x] if x != mort else 'le déclarant'} voyait {NOMS[s]} à {lo}–{hi} H, il en avait {v}"
            + ("" if lo <= v <= hi else " (à côté)") for x, s, lo, hi, v in cr) + ".")
    if humain is not None:
        miennes = [z for z in a["cartes"] if nom(z["siege"]) == "Vous"]
        perdues = [z for z in miennes if z["perte"] > 0]
        out.append("Vos cartes : " + ("aucune n'a coûté de levée, cartes vues." if not perdues else
                   f"{len(perdues)} sur {len(miennes)} ont coûté, cartes vues ("
                   + ", ".join(f"pli {z['pli']} {z['carte']}" for z in perdues[:4]) + ")."))
    return out
