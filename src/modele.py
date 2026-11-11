# -*- coding: utf-8 -*-
"""Ce qu'un joueur peut savoir des mains qu'il ne voit pas : le modèle des mains cachées.

Depuis une place (le déclarant ou un défenseur), avec les enchères, les cartes jouées et les chicanes montrées,
on imagine des donnes complètes et on les pondère :
  - les cartes connues sont à leur place (sa main, le mort une fois étalé, les cartes jouées) ;
  - une couleur où un joueur n'a pas fourni est vide chez lui ;
  - les enchères : le moteur (encheres.encherir) refait la séquence de chaque donne imaginée ; chaque enchère d'un
    joueur caché que notre système n'aurait pas faite avec cette main (un passe aussi : ne pas parler dit quelque
    chose) divise le poids ;
  - l'entame : la règle d'entame (entames.yaml) appliquée à la main imaginée de l'entameur doit donner la carte jouée.
On en tire, pour chaque joueur caché, ses points H, la longueur de chaque couleur et la place des honneurs (A R D V X 9).
Mesure : src/essai_modele.py, sur des donnes tirées au hasard."""
import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import encheres, jeu, jouer
from jeu import COULEURS, ORDRE, ROT, PTS, PART, LHO

SUIVIS = "ARDVX9"                                          # les cartes dont on prédit la place
EPS_ENCHERE = 0.05                                         # une enchère que notre système n'aurait pas faite
EFFICACE = 150                                             # on imagine des donnes jusqu'à en avoir autant qui comptent
EPS_SIGNAL = 0.35                                          # un signal du partenaire que sa main imaginée n'aurait pas donné
LIRE_SIGNAUX = True                                        # un défenseur lit les signaux de son partenaire
LIRE_HONNEURS = False                                      # lire les honneurs du partenaire (le plus bas de cartes équivalentes en fournissant,
EPS_HONNEUR = 0.2                                          # le plus haut d'une séquence en menant, carte.SEQUENCE) : essayé le 2026-11-11,
                                                           # −0,008 levée (± 0,018) seul, −0,028 (± 0,019) avec SEQUENCE : non gardé
EPS_ENTAME = 0.05                                           # une entame que la règle n'aurait pas choisie


def _cartes(main):
    """« AR5 D83 - 762 » -> {(couleur, rang)}"""
    return {(c, r) for c, x in zip(COULEURS, main.split()) if x != "-" for r in x}


def _main(cartes):
    return " ".join("".join(sorted((r for c, r in cartes if c == k), key=ORDRE.index)) or "-" for k in COULEURS)


def carte_fr(c):
    """« ♠10 » ou « ♠X » -> (« ♠ », « X »)"""
    return c[0], c[1:].replace("10", "X")


def chicanes(jouees):
    """{siège: couleurs où il n'a pas fourni}, d'après les cartes jouées [(siège, « ♠A »)] dans l'ordre."""
    out = {x: set() for x in ROT}
    for i in range(0, len(jouees), 4):
        pli = jouees[i:i + 4]
        if not pli: continue
        demandee = pli[0][1][0]
        for x, c in pli[1:]:
            if c[0] != demandee: out[x].add(demandee)
    return out


class Modele:
    """Le modèle vu de la place observateur. d : la donne (seules sont lues la main de l'observateur, celle du mort
    si mort est donné, le donneur et la vulnérabilité) ; seq : les enchères depuis le donneur ; jouees : les cartes
    jouées dans l'ordre, [(siège, « ♠A »)], l'entame d'abord."""

    def __init__(self, d, observateur, seq, jouees=(), mort=None, n=300, graine=0,
                 eps_enchere=EPS_ENCHERE, eps_entame=EPS_ENTAME, prefiltre=True,
                 efficace=EFFICACE, n_max=2000):
        self.d, self.obs, self.seq, self.mort = d, observateur, list(seq), mort
        self.jouees = [(x, c[0] + c[1:].replace("10", "X")) for x, c in jouees]
        self.n, self.rnd, self.cible, self.n_max = n, random.Random(graine), efficace, n_max
        self.eps_enchere, self.eps_entame, self.prefiltre = eps_enchere, eps_entame, prefiltre
        self.vus = {observateur} | ({mort} if mort else set())
        self.caches = [x for x in ROT if x not in self.vus]
        self.connues = {x: _cartes(d["mains"][x]) for x in self.vus}
        self.jouees_par = {x: {carte_fr(c) for y, c in self.jouees if y == x} for x in ROT}
        self.vides = chicanes(self.jouees)
        fini = jouer.fin(self.seq)
        self.contrat, self.decl = jouer.contrat(self.seq, d["donneur"]) if fini else ("passe", None)
        self.cx = jeu.lire_encheres(self.seq, d["donneur"])
        self._mondes = None
        self.den = self.contrat[1:].rstrip("X") if self.decl else None
        self.signaux = signaux_vus(self.jouees, self.decl, self.den) if (LIRE_SIGNAUX and self.decl and observateur != self.decl
                                                                         and observateur != PART[self.decl]) else []

    # ---------------------------------------------------------------- les donnes imaginées
    def _tirer(self):
        """Une répartition des cartes inconnues entre les mains cachées (cartes déjà jouées comprises), ou None."""
        connues = set().union(*self.connues.values()) | {k for x in self.caches for k in self.jouees_par[x]}
        libres = [(c, r) for c in COULEURS for r in ORDRE if (c, r) not in connues]
        self.rnd.shuffle(libres)
        mains, i = {}, 0
        for x in self.caches:
            k = 13 - len(self.jouees_par[x])
            lot = libres[i:i + k]; i += k
            if any(c in self.vides[x] for c, _ in lot): return None
            mains[x] = set(lot) | self.jouees_par[x]
        return mains

    def _plausible(self, mains):
        """Préfiltre lâche : les points et les longueurs lus simplement dans les enchères (jeu.lire_encheres)."""
        for x, cartes in mains.items():
            h = sum(PTS.get(r, 0) for _, r in cartes)
            lo, hi = self.cx[x]["pts"]
            if not lo - 3 <= h <= hi + 3: return False
            for c, v in self.cx[x]["L"].items():
                if sum(1 for k, _ in cartes if k == c) < v - 1: return False
        return True

    def _poids(self, mains):
        """Le poids d'une donne imaginée : ses enchères refaites par le moteur, puis l'entame."""
        m = {x: _main(mains[x]) if x in mains else self.d["mains"][x] for x in ROT}
        dd = dict(n=self.d.get("n", 0), donneur=self.d["donneur"], vul=self.d.get("vul", "Personne"), mains=m)
        w = 1.0
        if self.eps_enchere < 1 and self.seq:
            try:
                r = encheres.encherir(dd, imposees=self.seq)
                i0 = ROT.index(self.d["donneur"])
                faux = sum(1 for k in r.get("ecarts", []) if k < len(self.seq) and ROT[(i0 + k) % 4] in mains)
                w *= self.eps_enchere ** faux
            except Exception:
                w *= self.eps_enchere ** 3
        if self.jouees and self.decl and LHO[self.decl] in mains: w *= self._facteur_entame(m)
        for x, carte, sens, c, c0 in self.signaux:          # les signaux du partenaire (pair-impair, préférence, parité)
            if x in mains: w *= signal_plausible(m[x], carte, sens, c, self.den, c0)
        return w, m

    def mondes(self):
        """[(mains, poids)] : n donnes imaginées et leur poids."""
        if self._mondes is not None: return self._mondes
        self._mondes = []
        self._completer()                                  # assez de donnes qui comptent (efficace) : on s'arrête
        return self._mondes

    def suite(self, jouees, mort=None):
        """Le modèle après d'autres cartes jouées : les donnes imaginées encore possibles (chaque carte jouée par un
        joueur caché est dans sa main, ses chicanes sont respectées, le mort étalé est le vrai) gardent leur poids ;
        de nouvelles donnes complètent la réserve s'il en reste trop peu. Bien plus rapide qu'un nouveau modèle."""
        m = Modele(self.d, self.obs, self.seq, jouees, mort=mort or self.mort, n=self.n, graine=self.rnd.random(),
                   eps_enchere=self.eps_enchere, eps_entame=self.eps_entame,
                   prefiltre=self.prefiltre, efficace=self.cible, n_max=self.n_max)
        garde = []
        neufs = [z for z in m.signaux if z not in self.signaux]     # un signal vient d'être vu : il compte aussi
        for mains, w in self.mondes():
            if any(mains[x] != self.d["mains"][x] for x in m.vus): continue          # le mort réel, désormais vu
            ok = True
            for x in m.caches:
                cartes = _cartes(mains[x])
                if not m.jouees_par[x] <= cartes or any((c, r) in cartes and (c, r) not in m.jouees_par[x]
                                                       for c in m.vides[x] for r in ORDRE):
                    ok = False; break
            if ok:
                for x, carte, sens, c, c0 in neufs:
                    if x in m.caches: w *= signal_plausible(mains[x], carte, sens, c, m.den, c0)
                garde.append((mains, w))
        if m.jouees and not self.jouees and m.decl and LHO[m.decl] in m.caches:    # l'entame vient d'être vue
            garde = [(mains, w * m._facteur_entame(mains)) for mains, w in garde]
        m._mondes = garde
        if len(garde) < m.n: m._completer()
        return m

    def _completer(self):
        """Ajoute des donnes tirées à neuf jusqu'à n (et assez de donnes efficaces)."""
        out = self._mondes or []
        sw = sum(w for _, w in out); sw2 = sum(w * w for _, w in out)
        for _ in range(self.n_max * 60):
            if len(out) >= self.n and (len(out) >= self.n_max or sw * sw >= self.cible * sw2): break
            mains = self._tirer()
            if mains is None or (self.prefiltre and not self._plausible(mains)): continue
            w, mm = self._poids(mains)
            out.append((mm, w)); sw += w; sw2 += w * w
        self._mondes = out

    def _facteur_entame(self, m):
        """Le poids de l'entame dans une donne imaginée m (mains complètes) : la règle choisit-elle la carte jouée ?"""
        if self.eps_entame >= 1: return 1.0
        dd = dict(n=self.d.get("n", 0), donneur=self.d["donneur"], vul=self.d.get("vul", "Personne"), mains=m)
        try:
            e = jeu.entame_et_defense(dd, self.contrat, self.decl, self.seq)["entame"]["carte"]
            return 1.0 if e.replace("10", "X") == self.jouees[0][1] else self.eps_entame
        except Exception:
            return 1.0

    # ---------------------------------------------------------------- ce qu'on en tire
    def poids(self):
        """Les poids des donnes imaginées. (Les adoucir quand peu de donnes comptent a été essayé : moins juste sur
        les vraies enchères comme sur les donnes tirées au hasard, essai_modele.py, 2026-11-08.)"""
        return [w for _, w in self.mondes()]

    def prediction(self):
        """{siège caché: {"H": (moyenne, bas, haut), "L": {couleur: (moyenne, {n: proba})}, "cartes": {(c, r): proba}}}
        et "efficace" : le nombre de donnes qui comptent vraiment (somme des poids au carré)."""
        ms = [(m, w) for (m, _), w in zip(self.mondes(), self.poids())]
        tot = sum(w for _, w in ms) or 1.0
        out = {}
        for x in self.caches:
            hs, L, cartes = [], {c: {} for c in COULEURS}, {}
            for m, w in ms:
                s = jeu.suites(m[x])
                hs.append((sum(PTS.get(r, 0) for c in COULEURS for r in s[c]), w))
                for c in COULEURS:
                    L[c][len(s[c])] = L[c].get(len(s[c]), 0) + w / tot
                    for r in s[c]:
                        if r in SUIVIS: cartes[(c, r)] = cartes.get((c, r), 0) + w / tot
            hs.sort()
            cumul, bas, haut = 0, None, None
            for h, w in hs:
                cumul += w / tot
                if bas is None and cumul >= .1: bas = h
                if haut is None and cumul >= .9: haut = h
            moy = sum(h * w for h, w in hs) / tot
            out[x] = {"H": (moy, bas, haut), "L": {c: (sum(k * p for k, p in L[c].items()), L[c]) for c in COULEURS},
                      "cartes": cartes}
        out["efficace"] = tot ** 2 / (sum(w * w for _, w in ms) or 1)
        return out

    def pensees(self):
        """Ce que pense le joueur de chaque main cachée, en français : ses points, sa forme la plus probable et les
        honneurs qu'il croit y voir (sûr à 85 %+, probable à 60 %+), ou qu'il croit absents (moins de 10 %)."""
        p = self.prediction(); out = []
        for x in self.caches:
            moy, bas, haut = p[x]["H"]
            pts = f"{moy:.0f} H" if bas == haut else f"{bas}–{haut} H (vers {moy:.0f})"
            forme = []
            for c in COULEURS:                              # la plus courte plage de longueurs qui fait 70 %
                dist = p[x]["L"][c][1]; ks = sorted(dist)
                a_, b_ = min(((i, j) for i in ks for j in ks if j >= i and sum(dist[k] for k in ks if i <= k <= j) >= .7),
                             key=lambda ij: (ij[1] - ij[0], -sum(dist[k] for k in ks if ij[0] <= k <= ij[1])))
                forme.append(f"{c}{a_}" if a_ == b_ else f"{c}{a_}–{b_}")
            rang = lambda kv: (COULEURS.index(kv[0][0]), SUIVIS.index(kv[0][1]))
            sur = [f"{c}{r}" for (c, r), q in sorted(p[x]["cartes"].items(), key=rang) if q >= .85]
            prob = [f"{c}{r}" for (c, r), q in sorted(p[x]["cartes"].items(), key=rang) if .6 <= q < .85]
            t = f"{NOMS[x]} : {pts} ; {' '.join(forme)}"
            if sur: t += " ; a " + ", ".join(sur)
            if prob: t += " ; sans doute " + ", ".join(prob)
            out.append(t)
        import signaux                                     # ce que disent les signaux du partenaire (signaux.py)
        for x, carte, sens, c, c0 in self.signaux:
            if sens.startswith("honneur"):                 # « Est a fourni la ♥D : il n'a pas le ♥V. »
                connues = set().union(*self.connues.values())
                ph = phrase_honneur(NOMS[x], carte, sens, c0, connues)
                if ph: out.append(ph)
                continue
            ph = signaux.phrase(NOMS[x], carte[0] + carte[1], sens, c, self.den, c0)
            if ph: out.append(ph)
        return out


NOMS = {"N": "Nord", "S": "Sud", "E": "Est", "O": "Ouest"}


def phrase_honneur(nom, carte, sens, vues, connues=()):
    """Ce que dit un honneur du partenaire (le plus bas de cartes équivalentes en fournissant, le plus haut d'une
    séquence en menant) : l'honneur voisin qu'il n'a pas, ou "" s'il n'y en a pas, si ce n'est pas un honneur ou si
    l'observateur le voit déjà (connues : sa main et le mort)."""
    ordre = "ARDVX98765432"
    pas = 1 if sens == "honneur suivi" else -1
    i = ordre.index(carte[1]) + pas
    while 0 <= i < len(ordre) and (carte[0], ordre[i]) in vues: i += pas
    if not 0 <= i < len(ordre) or ordre[i] not in "ARDVX" or (carte[0], ordre[i]) in connues: return ""
    nomme = lambda r: {"A": "l'as", "R": "le roi", "D": "la dame", "V": "le valet", "X": "le 10"}.get(r, f"le {r}")
    verbe = "a fourni" if sens == "honneur suivi" else "a mené"
    return f"{nom} {verbe} {nomme(carte[1])} {carte[0]} : il n'a pas {nomme(ordre[i])} {carte[0]}."


def aime(tenue):
    """Une tenue (« ARx », rangs français) qu'on aime : l'as, le roi, ou la dame avec le valet (comme carte.aime)."""
    return "A" in tenue or "R" in tenue or ("D" in tenue and "V" in tenue)


def signaux_vus(jouees, decl, den=None):
    """Les signaux qu'un défenseur a pu donner : [(siège, (couleur, rang), sens, couleur, couleur menée)], sens
    « attitude » (le partenaire mène : pair-impair), « parité » (le déclarant mène) ou « défausse » (préférence).
    Seulement la première carte d'un défenseur dans la couleur menée, jamais à l'atout ; une défausse hors atout.
    Comme carte.Partie.signal, vu de l'extérieur (signaux.py)."""
    from jeu import PART as P, LHO as G
    out, deja, vues = [], set(), set()
    for i in range(0, len(jouees), 4):
        pli = jouees[i:i + 4]
        if not pli: continue
        meneur, c0 = pli[0][0], pli[0][1][0]
        if LIRE_HONNEURS:                                  # les honneurs : (siège, carte, sens, couleur, cartes vues avant)
            for k, (x, c) in enumerate(pli):
                carte = carte_fr(c)
                if x in (G[decl], P[G[decl]]) and carte[1] in "ARDV" and carte[0] == c0 and (i or k):
                    out.append((x, carte, "honneur mené" if k == 0 else "honneur suivi", c0,
                                frozenset(vues | {carte_fr(y) for _, y in pli[:k]})))
            vues |= {carte_fr(c) for _, c in pli}
        for x, c in pli[1:]:
            if x not in (G[decl], P[G[decl]]): continue
            carte = carte_fr(c)
            if c[0] == c0:
                if (x, c0) in deja or c0 == den: continue
                deja.add((x, c0))
                if meneur == P[x]: out.append((x, carte, "attitude", c0, c0))
                elif meneur in (decl, P[decl]): out.append((x, carte, "parité", c0, c0))
            elif c[0] != den:
                out.append((x, carte, "défausse", c[0], c0))
    return out


def signal_plausible(main, carte, sens, c, den=None, c0=None):
    """1 si la main imaginée (13 cartes, « ARx Dx … ») va avec ce signal, EPS_SIGNAL sinon ; 1 aussi quand elle n'avait
    pas le choix. Le signaleur décide selon ses donnes imaginées (carte.Partie.voeu) ; ici, de l'extérieur, on en garde
    l'esprit sur la main : continuer une couleur où il a un honneur (ou la longueur à sans-atout, ou un doubleton pour
    couper), ne pas vouloir une couleur sans honneur, préférer celle où il a un as ou un roi (signaux.lire)."""
    import signaux
    tenues = [("" if t == "-" else t) for t in main.split()]
    tenue = tenues[COULEURS.index(c)]
    if sens in ("honneur suivi", "honneur mené"):          # c0 : les cartes vues avant celle-ci
        ordre = "ARDVX98765432"
        pas = 1 if sens == "honneur suivi" else -1         # suivi : il n'a pas la suivante plus basse ; mené : la plus haute
        i = ordre.index(carte[1]) + pas
        while 0 <= i < len(ordre) and (c, ordre[i]) in c0: i += pas
        return EPS_HONNEUR if 0 <= i < len(ordre) and ordre[i] in tenue else 1.0
    petites = [r for r in tenue if r not in "ARDV"]
    if len(petites) < 2 or carte[1] not in petites: return 1.0
    if sens == "parité":
        haute = carte[1] != petites[-1]
        return 1.0 if haute == (len(tenue) % 2 == 0) else EPS_SIGNAL
    m = signaux.lire(carte[1], sens, c, den, c0)
    t = lambda k: tenues[COULEURS.index(k)]
    fort = lambda k: "A" in t(k) or "R" in t(k)
    if sens == "attitude":
        veut = aime(tenue) or (den == "SA" and len(tenue) >= 4) or \
            (den in COULEURS and den != c and len(tenue) <= 2 and len(t(den)) >= 1)
        if m.get("continuer") is not None and m["continuer"] != veut: return EPS_SIGNAL
        if m.get("prefere") and not fort(m["prefere"]) and any(fort(k) for k in signaux.autres(den, c, c) if k != m["prefere"]):
            return EPS_SIGNAL
        return 1.0
    if sens == "défausse":
        if aime(tenue) and len(tenue) >= 2: return EPS_SIGNAL   # il garde une couleur qu'il aime
        if m.get("prefere") and not fort(m["prefere"]) and any(fort(k) for k in signaux.autres(den, c, c0) if k != m["prefere"]):
            return EPS_SIGNAL
        return 1.0
    return 1.0

if __name__ == "__main__":
    import json
    d = json.load(open(sys.argv[1], encoding="utf-8"))["donnes"][int(sys.argv[2]) - 1]
    r = encheres.encherir(d)
    m = Modele(d, sys.argv[3] if len(sys.argv) > 3 else "S", r["encheres"])
    p = m.prediction()
    for t in m.pensees(): print(t)
    for x in m.caches:
        print(x, d["mains"][x], {k: round(v, 1) if isinstance(v, float) else v for k, v in zip(("moy", "bas", "haut"), p[x]["H"])},
              {c: round(p[x]["L"][c][0], 1) for c in COULEURS})
