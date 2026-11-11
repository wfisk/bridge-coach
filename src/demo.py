# -*- coding: utf-8 -*-
"""La démonstration d'une donne, pour un cours : les quatre mains ouvertes, l'enseignant avance (→) et recule (←) dans
les enchères puis dans le jeu de la carte ; à chaque pas, ce que pense le joueur. Les enchères sont la séquence
recommandée (l'Expert, sinon le Coach, sinon le moteur) avec le sens de chaque enchère ; la carte est jouée par les
robots aux quatre places (carte.Partie), une carte à la fois, quand on avance. Le double mort de chaque carte jouable
se lit à tout moment (dm), et l'enseignant peut essayer une autre carte (essayer) : la suite repart de là.

Tout ici est des données (des dict, du texte), sans écran : une version web (les élèves sur leur téléphone) pourra
servir les mêmes pas et les mêmes questions.

    m = Demo(d, analyses)        # analyses : (standard, expert) du .bc.json, ou (None, None)
    m.n_encheres                 # les pas d'enchères (0 … n_encheres - 1), puis les cartes
    m.etape(k)                   # {"type": "enchere"|"carte"|"fin", …} ; une carte se calcule à la demande
    m.position(j)                # la Partie après la carte j (j = -1 : avant l'entame)
    m.dm(j)                      # {(couleur, rang): levées du déclarant} pour qui joue la carte j + 1
    m.essayer(j, carte)          # la carte j + 1 remplacée ; les cartes suivantes sont oubliées
"""
import carte, jouer
from encheres import encherir

SOURCES = {"expert": "l'Expert", "standard": "le Coach", "moteur": "le moteur d'enchères"}


def sequence_recommandee(d, analyses):
    """(séquence depuis le donneur, source, notes) : l'Expert d'abord, sinon le Coach, sinon le moteur."""
    for nom, a in (("expert", (analyses or (None, None))[1]), ("standard", (analyses or (None, None))[0])):
        x = ((a or {}).get("donnes") or {}).get(str(d["n"])) or {}
        if x.get("enc"):
            return jouer.sequence(x["enc"], d["donneur"]), nom, x.get("notes") or ""
    return encherir(d)["encheres"], "moteur", ""


class Demo:
    def __init__(self, d, analyses=None):
        self.d = d
        self.seq, self.source, self.notes = sequence_recommandee(d, analyses)
        try:
            ex = encherir(d, imposees=self.seq)["explications"][:len(self.seq)]
            # (siège, enchère, sens) : on garde le sens
            self.explications = [(x[2] if isinstance(x, (list, tuple)) and len(x) > 2 else str(x or "")) for x in ex]
        except Exception:
            self.explications = [""] * len(self.seq)
        self.contrat, self.decl = jouer.contrat(self.seq, d["donneur"])
        self.n_encheres = len(self.seq)
        self.cartes, self.pensees = [], []                # le jeu calculé jusqu'ici, et ce que pensait chaque joueur
        self._partie = None
        if self.decl:
            self._partie = self._neuve()
            self._partie.poser(self._partie.entame)        # l'entame, par les règles d'entame
            self.cartes = list(self._cartes_de(self._partie))
            self.pensees = [self._pensee_entame()]

    def _neuve(self):
        """Une Partie au début, l'entame pas encore jouée (humain = l'entameur : elle n'est pas posée d'office ; les
        robots jouent toutes les places quand on appelle carte_robot)."""
        return carte.Partie(self.d, self.contrat, self.decl, self.seq, humain=carte.LHO[self.decl])

    # ---------------------------------------------------------------- les pas
    def _cartes_de(self, p):
        lettre = dict(zip("SHDC", carte.COULEURS))
        return [(lettre[j[0]], j[1:]) for j in p.pos.jouees]

    def _pensee_entame(self):
        from jeu import entame_et_defense
        e = entame_et_defense(self.d, self.contrat, self.decl, self.seq)
        meneur = carte.LHO[self.decl]
        return dict(n=0, siege=meneur, carte=carte.carte_fr(*self.cartes[0]), humain=False, role="defense", plan="",
                    coups=[], signal=None, suit=None, croyance=[], mondes=0, force=False, scores={},
                    entame=e["pourquoi"].replace(f"{meneur} entame", f"{carte.NOMS[meneur]} entame"))

    def fini(self):
        return not self.decl or (self._partie is not None and self._partie.fini() and len(self.cartes) == len(self._partie.pos.jouees))

    def calculer(self, j):
        """Joue les robots jusqu'à la carte j comprise (0 : l'entame) ; renvoie False si la donne finit avant."""
        p = self._partie
        while len(self.cartes) <= j:
            if p is None or p.fini(): return False
            x = p.carte_robot()                            # garde sa pensée dans p.pensees
            p.poser(x)
            self.cartes.append(x)
            self.pensees.append(p.pensees[-1])
        return True

    def etape(self, k):
        """Le pas k : une enchère (k < n_encheres), puis une carte (calculée si besoin), puis la fin."""
        if k < self.n_encheres:
            i0 = jouer.ROT.index(self.d["donneur"])
            return dict(type="enchere", k=k, siege=jouer.ROT[(i0 + k) % 4], appel=self.seq[k],
                        explication=self.explications[k] if k < len(self.explications) else "")
        j = k - self.n_encheres
        if not self.decl or not self.calculer(j):
            return dict(type="fin", k=k)
        return dict(type="carte", k=k, j=j, siege=self.pensees[j]["siege"], carte=self.cartes[j], pensee=self.pensees[j])

    def n_pas(self):
        """Le nombre de pas connus (les cartes non encore calculées n'y sont pas)."""
        return self.n_encheres + len(self.cartes)

    # ---------------------------------------------------------------- la position, le double mort, « et si… »
    def position(self, j):
        """Une Partie neuve après les cartes 0 … j (j = -1 : avant l'entame, les mains entières)."""
        q = self._neuve()
        for x in self.cartes[:j + 1]: q.poser(x)
        return q

    def dm(self, j):
        """Au double mort, pour le joueur qui joue la carte j + 1 : {(couleur, rang anglais): levées finales du
        déclarant}, toutes les cartes jouables (une carte équivalente vaut sa voisine de la même couleur)."""
        q = self.position(j)
        if q.fini(): return {}
        v = q.pos.valeurs()
        out = {}
        for x in q.legales():
            if x in v: out[x] = v[x]; continue
            memes = [y for y in v if y[0] == x[0]]           # la carte de la même suite que le solveur a gardée
            if memes:
                rangs = carte.RANGS
                out[x] = v[min(memes, key=lambda y: abs(rangs.index(y[1]) - rangs.index(x[1])))]
        return out

    def essayer(self, j, x):
        """La carte j + 1 devient x (jouable à ce moment) ; les robots reprendront de là quand on avancera."""
        q = self.position(j)
        if x not in q.legales(): raise ValueError(f"{carte.carte_fr(*x)} ne peut pas être jouée")
        s = q.au_trait()
        q.poser(x)
        self._partie = q
        self.cartes = self.cartes[:j + 1] + [x]
        self.pensees = self.pensees[:j + 1] + [dict(n=j + 1, siege=s, carte=carte.carte_fr(*x), humain=True,
                                                     role="declarant" if q.camp(s) else "defense", plan="", coups=[],
                                                     signal=None, suit=None, croyance=[], mondes=0, force=False,
                                                     scores={}, essai=True)]
