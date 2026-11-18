# -*- coding: utf-8 -*-
"""Crée des donnes par thème, pour l'entraînement : un fichier Bridge Coach (<nom>.bc.json) que rapport.py lit tel quel.

    .venv/bin/python -I src/donnes.py <nombre> <thème 1> <thème 2> <thème 3> [graine]
    .venv/bin/python -I src/donnes.py --texte <fichier.txt>      (donnes saisies : une par ligne, voir lire_texte)

Chaque thème est un test sur une donne tirée au hasard, avec le donneur et la vulnérabilité du numéro de
donne : le contrat et les enchères du moteur, le double mort, ou les coups trouvés par coups.py. Un thème
qui n'aboutit pas dans le délai laisse une donne au hasard, et le programme le dit. À côté du .json, un
fichier .pbn, le format commun des donnes, pour les autres logiciels.
"""
import datetime, json, multiprocessing, os, random, re, sys, time, unicodedata
_T0 = time.time()                                          # pour « Temps : » : ce que coûte le chargement du programme

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from bws_extract import SEAT, SN, VUL16, imp, par, score, vul_of
from encheres import encherir
from encheres.main import Main
from jeu import (COULEURS, LHO, ORDRE, PTS, RHO, compter_plan, couleurs_nommees, donnes_du_declarant, entame_et_defense,
                 impasses, levees_par_entame, lire_encheres, suites, _pbn)
import coups, lignes

ALEATOIRE = "Aléatoire"
SAISIE = "Donne saisie"
LETTRES = {"P": "♠", "C": "♥", "K": "♦", "T": "♣"}
VUL_TEXTE = {"NN": "Personne", "VN": "N-S", "NV": "E-O", "VV": "Tous"}
DELAI = 150                                                # secondes pour trouver une donne d'un thème
MONDES = 60                                                # donnes imaginées pour juger un contrat à la table
TAUX = {"petit": .6, "grand": .7, "manche": .55, "sacrifice": .6}   # sa réussite minimale dans ces donnes imaginées
SIEGES = "NESO"
EN = {"N": "N", "E": "E", "S": "S", "O": "W"}
COUL = {"SA": "NT", "♠": "S", "♥": "H", "♦": "D", "♣": "C"}
VUL_PBN = {"Personne": "None", "N-S": "NS", "E-O": "EW", "Tous": "All"}
RANG_EN = str.maketrans({"R": "K", "D": "Q", "V": "J", "X": "T"})
PART = {"N": "S", "S": "N", "E": "O", "O": "E"}


class Essai:
    """Une donne tirée, et ce qu'en disent le moteur et le solveur, calculés seulement si un thème le demande."""

    def __init__(self, d):
        self.d = d; self.mains = d["mains"]; self._enc = self._dm = None; self._taux = {}; self.chances = None

    @property
    def enc(self):
        if self._enc is None:
            try:
                self._enc = encherir(self.d)
            except Exception:                              # séquence que le moteur ne couvre pas : la donne ne sert pas
                self._enc = dict(encheres=[], contrat="passe", declarant=None, explications=[])
        return self._enc

    @property
    def seq(self): return self.enc["encheres"]

    @property
    def contrat(self): return self.enc["contrat"]

    @property
    def decl(self): return self.enc["declarant"]

    def actives(self):
        """[(indice dans la séquence, siège, enchère)] sans les passes."""
        k = SIEGES.index(self.d["donneur"])
        return [(i, SIEGES[(k + i) % 4], b) for i, b in enumerate(self.seq) if b != "passe"]

    @property
    def dm(self):
        if self._dm is None: self._dm = double_mort(self.mains)
        return self._dm

    def fait(self):
        """Le contrat du moteur gagne au double mort."""
        c = self.contrat.rstrip("X")
        return c != "passe" and self.dm[c[1:]][self.decl] >= int(c[0]) + 6

    def taux(self, contrat=None, decl=None):
        """La part des MONDES donnes imaginées où le contrat (celui du moteur par défaut) gagne au double mort :
        le déclarant et le mort tels quels, les mains adverses au hasard, fidèles aux enchères (jeu.donnes_du_declarant,
        sans l'entame : la défense trouve la meilleure). Ce qu'un joueur peut juger à la table, jamais la donne réelle."""
        contrat = (contrat or self.contrat).rstrip("X"); decl = decl or self.decl
        if (contrat, decl) not in self._taux:
            self._taux[contrat, decl] = taux_contrat(self.d, contrat, decl, self.seq)
        return self._taux[contrat, decl]

    def h(self, s): return Main(self.mains[s]).hcp

    def camp_h(self, s): return self.h(s) + self.h(PART[s])


def double_mort(mains):
    from endplay.types import Deal
    from endplay.dds import calc_dd_table
    table = calc_dd_table(Deal(_pbn(mains))).to_list()     # lignes ♠ ♥ ♦ ♣ SA, colonnes N E S O
    return {den: dict(zip("NESO", ligne)) for den, ligne in zip(("♠", "♥", "♦", "♣", "SA"), table)}


def he_de(dm, hcp):
    """Le double mort sous la forme qu'attend bws_extract.par."""
    he = {SEAT[EN[s]] + SN[COUL[c]]: v for c, x in dm.items() for s, v in x.items()}
    he.update({SEAT[EN[s]] + "Hcp": v for s, v in hcp.items()})
    return he


def pbn(data):
    """Le fichier .pbn : un bloc par donne, mains dans l'ordre N E S O, à partir de Nord, et le double mort
    quand la séance l'a (DoubleDummyTricks). Sert à l'export de toute séance (Fichier, Exporter)."""
    out = ['% PBN 2.1', '% Bridge Coach', '']
    jour = "/".join(reversed(data["session"]["date"].split("/"))).replace("/", ".")
    for d in data["donnes"]:
        mains = " ".join(".".join("" if x == "-" else x.translate(RANG_EN) for x in d["mains"][s].split()) for s in SIEGES)
        event = unicodedata.normalize("NFD", d.get("theme") or "Bridge Coach").encode("ascii", "ignore").decode()   # le PBN n'est pas en UTF-8
        out += [f'[Event "{event}"]', f'[Date "{jour}"]', f'[Board "{d["n"]}"]', f'[Dealer "{EN[d["donneur"]]}"]',
                f'[Vulnerable "{VUL_PBN[d["vul"]]}"]', f'[Deal "N:{mains}"]']
        if d.get("dm"):                                   # levées au double mort : N, S, E, O ; SA ♠ ♥ ♦ ♣ en hexadécimal
            out.append('[DoubleDummyTricks "' + "".join(f"{d['dm'][x][s]:x}" for s in "NSEO" for x in ("SA", "♠", "♥", "♦", "♣")) + '"]')
        out.append('')
    return "\n".join(out)


def taux_contrat(d, contrat, decl, seq, n=MONDES):
    """La part des n donnes imaginées (fidèles aux enchères) où contrat gagne au double mort ; None sans donnes."""
    from endplay.types import Deal, Denom
    from endplay.dds import calc_all_tables
    mondes = donnes_du_declarant(d, decl, seq, None, n)
    if len(mondes) < n // 2: return None
    den = contrat[1:]; need = int(contrat[0]) + 6
    garde = {"♠": Denom.spades, "♥": Denom.hearts, "♦": Denom.diamonds, "♣": Denom.clubs, "SA": Denom.nt}[den]
    tables = calc_all_tables([Deal(_pbn(m)) for m in mondes], exclude=[x for x in (Denom.spades, Denom.hearts, Denom.diamonds, Denom.clubs, Denom.nt) if x != garde])
    i = ("♠", "♥", "♦", "♣", "SA").index(den); j = SIEGES.index(decl)
    return sum(t.to_list()[i][j] >= need for t in tables) / len(mondes)


def cles(e, decl, den):
    """(clés, dame d'atout) du camp du déclarant : les quatre as et le roi d'atout (les as seuls à SA)."""
    m = [e.mains[decl].split(), e.mains[PART[decl]].split()]
    n = sum("A" in x[k] for x in m for k in range(4))
    if den == "SA": return n, True
    k = COULEURS.index(den)
    return n + sum("R" in x[k] for x in m), any("D" in x[k] for x in m) or sum(len(x[k].replace("-", "")) for x in m) >= 10


def enchere_saine(e, niveau):
    """Le moteur arrive lui-même au contrat de ce niveau (6 ou 7), sans contre, par une séquence que le système
    décrit jusqu'au bout et sans enchère folle : au petit chelem il manque au plus une clé, au grand aucune, ni la
    dame d'atout."""
    c = e.contrat
    if e.enc.get("statut") != "complète" or c == "passe" or c.endswith("X") or int(c[0]) != niveau: return False
    k, dame = cles(e, e.decl, c[1:])
    return k >= (4 if c[1:] == "SA" else 5) and dame if niveau == 7 else k >= (3 if c[1:] == "SA" else 4)


def a_la_table(e, cle):
    """Le contrat du moteur gagne dans assez de donnes imaginées (TAUX[cle]) et, sous le grand chelem, le palier du
    dessus dans la même dénomination n'est pas aussi un bon pari (petit chelem au lieu de la manche, grand au lieu du
    petit : la donne enseignerait un contrat trop bas) ; retient ce qu'en dira le commentaire."""
    t = e.taux()
    if t is None or t < TAUX[cle]: return False
    c = e.contrat.rstrip("X")
    if c[0] != "7":
        haut = ("6" if c[0] in "345" else "7") + c[1:]
        u = e.taux(haut, e.decl)
        if u is not None and u >= TAUX["grand" if haut[0] == "7" else "petit"]: return False
    e.chances = dict(contrat=c, declarant=e.decl, taux=round(t, 2), mondes=MONDES, encheres=list(e.seq),
                     dm=e.dm[c[1:]][e.decl])
    return True


def chelem(e, niveaux):
    """Un chelem que le moteur demande (niveaux : (6,), (7,) ou les deux), sain, et qui gagne assez souvent à la table.
    Le double mort de la donne réelle ne décide pas : un bon chelem peut chuter sur une mauvaise répartition."""
    if max(e.camp_h(s) for s in "NE") < 25: return False   # filtre rapide, avant les enchères
    return any(enchere_saine(e, x) for x in niveaux) and a_la_table(e, "petit" if int(e.contrat[0]) == 6 else "grand")


def manche(e, contrats):
    """Une manche que le moteur demande et qui gagne assez souvent à la table (pas seulement au double mort)."""
    c = e.contrat
    if not (c.rstrip("X") in contrats and e.enc.get("statut") == "complète" and not c.endswith("X")): return False
    if not a_la_table(e, "manche"): return False
    return not (c[0] == "5" and any((e.taux("3SA", x) or 0) >= TAUX["manche"] for x in (e.decl, PART[e.decl])))
    # en mineure, 3SA (une levée de moins à faire) ne doit pas être aussi un bon pari


def premier_actif(e, i=0):
    a = e.actives()
    return a[i] if len(a) > i else (None, None, None)


def ouverture(e): return premier_actif(e)[2]


def rang_ouverture(e): return premier_actif(e)[0]


def barrage(e):
    o = ouverture(e)
    return o in ("2♥", "2♠") or (o and o[0] in "34" and o[1:] != "SA")


BICOLORES = ("cue-bid bicolore", "bicolore : 5-5", "bicolore mineur")


def bicolore(e):
    """Une intervention bicolore du moteur (regles.yaml) : cue-bid (Michaels), 2♦ sur 1♣ (les majeures), 2SA, 3♣."""
    return any(any(m in x for m in BICOLORES) for _s, _b, x in e.enc.get("explications", []))


def blackwood(e):
    """Le moteur demande les clés (Blackwood 3041) puis s'arrête à 5 (deux clés manquent : son contrat doit gagner
    à la table) ou demande un chelem sain et de bonnes chances."""
    if max(e.camp_h(s) for s in "NE") < 25: return False
    i = next((k for k, (_s, b, x) in enumerate(e.enc["explications"]) if b == "4SA" and "Blackwood" in str(x)), None)
    if i is None or e.contrat == "passe" or e.contrat.endswith("X"): return False
    if e.contrat[0] == "5": return e.enc.get("statut") == "complète" and a_la_table(e, "petit")
    return chelem(e, (6, 7))


def intervention(e):
    a = e.actives()
    return len(a) >= 2 and a[0][2] != "contre" and a[1][1] in (voisins(a[0][1])) and a[1][2][0] in "1234" and a[1][2] != "contre"


def voisins(s):
    i = SIEGES.index(s); return SIEGES[(i + 1) % 4], SIEGES[(i + 3) % 4]


def contre_appel(e):
    a = e.actives()
    return len(a) >= 2 and a[1][2] == "contre" and a[0][2][0] == "1" and a[1][1] in voisins(a[0][1])


def spoutnik(e):
    a = e.actives()
    return len(a) >= 3 and a[0][2][0] == "1" and a[1][1] in voisins(a[0][1]) and a[1][2] not in ("contre", "surcontre") and a[2][1] == PART[a[0][1]] and a[2][2] == "contre"


def drury(e):
    """Un partenaire qui a passé, un fit et 9–11 H, sur une ouverture de 1♥ ou 1♠ en 3e ou 4e (conventions/drury.md)."""
    i, s, o = premier_actif(e)
    if i not in (2, 3) or o not in ("1♥", "1♠"): return False
    k = COULEURS.index(o[1]); p = PART[s]
    return len(e.mains[p].split()[k].replace("-", "")) >= 3 and 9 <= e.h(p) <= 11


def roudi(e):
    """Pas dans le système : 1m – 1M – 1SA, et le répondant a de quoi chercher la manche (11+ H)."""
    a = e.actives()
    if len(a) < 3: return False
    if a[0][2] not in ("1♣", "1♦") or a[1][2] not in ("1♥", "1♠") or a[2][2] != "1SA": return False
    return a[1][1] == PART[a[0][1]] and a[2][1] == a[0][1] and e.h(a[1][1]) >= 11


def quatrieme(e):
    return any("couleur" in str(x[2]).lower() and ("4e" in str(x[2]) or "quatrième" in str(x[2]).lower()) for x in e.enc["explications"])


def reveil(e):
    return len(e.seq) >= 4 and e.seq[0][0] == "1" and e.seq[1:3] == ["passe", "passe"] and e.seq[3] != "passe"


# ---------------------------------------------------------------- à la table : des donnes imaginées, jamais la donne réelle
DENS = ("♠", "♥", "♦", "♣", "SA")
EN_COUL = dict(zip(DENS, "SHDCN"))
MONDES_VUS = 40                                            # donnes imaginées pour les décisions de compétition et l'entame


def mondes_vus(d, gardes, seq, n=MONDES_VUS, graine=None):
    """n donnes : les mains des sièges gardes telles quelles, les autres au hasard, fidèles aux enchères (jeu.lire_encheres,
    lecture large ; une marge de 1 H, puis de 3 H et une carte de moins si les donnes sont rares). Ce que voit le camp ou
    le joueur qui décide, jamais les autres mains réelles."""
    rnd = random.Random(d.get("n") if graine is None else graine)
    cx = lire_encheres(seq, d["donneur"])
    autres = [x for x in SIEGES if x not in gardes]
    vues = {(c, r) for x in gardes for c, p in suites(d["mains"][x]).items() for r in p}
    reste = [(c, r) for c in COULEURS for r in ORDRE if (c, r) not in vues]
    for marge, moins in ((1, 0), (3, 1)):
        out = []
        for _ in range(20000):
            rnd.shuffle(reste)
            lots = {x: reste[13 * k:13 * k + 13] for k, x in enumerate(autres)}
            ok = True
            for x, cartes in lots.items():
                h = sum(PTS.get(r, 0) for _, r in cartes); L = {c: 0 for c in COULEURS}
                for c, _ in cartes: L[c] += 1
                lo, hi = cx[x]["pts"]
                if not lo - marge <= h <= hi + marge or any(L[c] < v - moins for c, v in cx[x]["L"].items()) \
                        or cx[x]["reg"] and (min(L.values()) < 2 or list(L.values()).count(2) > 1):
                    ok = False; break
            if not ok: continue
            m = {x: d["mains"][x] for x in gardes}
            for x, cartes in lots.items():
                m[x] = " ".join("".join(sorted((r for k, r in cartes if k == c), key=ORDRE.index)) or "-" for c in COULEURS)
            out.append(m)
            if len(out) >= n: return out
        if len(out) >= n // 4: return out
    return out


def levees_dm(mondes, dens):
    """[{dénomination: {siège: levées}}] au double mort, seulement pour les dénominations dens."""
    if not mondes: return []
    from endplay.types import Deal, Denom
    from endplay.dds import calc_all_tables
    D_ = dict(zip(DENS, (Denom.spades, Denom.hearts, Denom.diamonds, Denom.clubs, Denom.nt)))
    tables = calc_all_tables([Deal(_pbn(m)) for m in mondes], exclude=[D_[x] for x in DENS if x not in dens])
    return [{x: dict(zip(SIEGES, t.to_list()[DENS.index(x)])) for x in dens} for t in tables]


def marque(contrat, decl, vul, levees):
    """La marque du camp du déclarant ("4♠X")."""
    c = contrat.rstrip("X"); x = len(contrat) - len(c)
    return score(int(c[0]), EN_COUL[c[1:]], x, vul_of(vul, "NS" if decl in "NS" else "EO"), levees)


def camp_de(s): return "NS" if s in "NS" else "EO"


def declarant_de(e, siege, den):
    """Le premier du camp de siege à avoir nommé den (le déclarant si ce contrat avait été joué)."""
    return next((x for _, x, b in e.actives() if camp_de(x) == camp_de(siege) and b[1:] == den), siege)


def dernier_contrat(e, camp, avant=None):
    """(contrat, déclarant) : la dernière enchère naturelle de ce camp (avant l'indice avant), ou (None, None)."""
    for i, x, b in reversed(e.actives()):
        if (avant is None or i < avant) and camp_de(x) == camp and b[0].isdigit():
            return b, declarant_de(e, x, b[1:])
    return None, None


def partielle(e):
    """Une partielle disputée : les deux camps nomment une couleur, le moteur s'arrête sous la manche, et la dernière
    décision de chaque camp est juste en moyenne à la table (IMP sur MONDES_VUS donnes imaginées depuis ce camp, ses deux
    mains connues) : le camp qui joue a eu raison de surenchérir plutôt que de défendre le dernier contrat adverse,
    l'autre a raison de défendre plutôt que de monter d'un palier dans sa couleur."""
    a = e.actives()
    c = e.contrat
    if c == "passe" or c[0] not in "123" or c.rstrip("X").endswith("SA") and c[0] == "3": return False
    if len({camp_de(s) for _, s, b in a if b not in ("contre", "surcontre")}) != 2: return False
    if e.enc.get("statut") != "complète" or c.endswith("X"): return False
    nous, eux = camp_de(e.decl), "EO" if camp_de(e.decl) == "NS" else "NS"
    i_c = max(i for i, x, b in a if b == c)
    leur, leur_decl = dernier_contrat(e, eux, i_c)          # ce qu'ils auraient joué si nous avions passé
    if leur is None: return False
    vul = e.d["vul"]; seq = e.seq
    # 1. notre camp : jouer c plutôt que défendre leur contrat
    w = levees_dm(mondes_vus(e.d, tuple(x for x in SIEGES if camp_de(x) == nous), seq), {c[1:], leur[1:]})
    if len(w) < MONDES_VUS // 2: return False
    gain = [imp(marque(c, e.decl, vul, t[c[1:]][e.decl]) + marque(leur, leur_decl, vul, t[leur[1:]][leur_decl])) for t in w]
    if sum(gain) / len(gain) < 0: return False
    # 2. leur camp : défendre c plutôt que monter d'un palier dans leur dernière couleur
    den = leur[1:]
    rang = ("♣", "♦", "♥", "♠", "SA").index
    haut = next((f"{k}{den}" for k in range(1, 8) if (k, rang(den)) > (int(c[0]), rang(c[1:]))), None)
    if haut is None: return False
    w = levees_dm(mondes_vus(e.d, tuple(x for x in SIEGES if camp_de(x) == eux), seq), {c[1:], den})
    if len(w) < MONDES_VUS // 2: return False
    gain = [imp(-marque(c, e.decl, vul, t[c[1:]][e.decl]) - marque(haut, leur_decl, vul, t[den][leur_decl])) for t in w]
    if sum(gain) / len(gain) < 0: return False
    e.chances = dict(genre="partielle", contrat=c.rstrip("X"), declarant=e.decl, contre=leur, plus_haut=haut,
                     mondes=len(w), encheres=list(seq), dm=e.dm[c[1:]][e.decl])
    return True


def fit(e, s):
    """La plus longue couleur commune du camp de s (cartes à deux)."""
    a, b = e.mains[s].split(), e.mains[PART[s]].split()
    return max(len(x.replace("-", "")) + len(y.replace("-", "")) for x, y in zip(a, b))


def sacrifice(e):
    """Un sacrifice, jugé à la table (les deux mains du camp qui se sacrifie connues, les autres imaginées d'après les
    enchères) : leur contrat, une manche ou un chelem, gagne au moins TAUX["sacrifice"] du temps, et le sacrifice contré
    coûte en moyenne moins que ce qu'ils auraient marqué. Deux cas : le moteur le fait lui-même (son contrat est contré
    au-dessus du leur), ou il les laisse jouer alors que le camp a nommé une couleur où il a 9 cartes ou plus : le
    sacrifice au palier le moins cher dans cette couleur était le bon pari (le commentaire le dit)."""
    if not any(e.camp_h(x) <= 17 and fit(e, x) >= 9 for x in "NE"): return False   # filtre rapide, avant les enchères
    c = e.contrat
    if c == "passe" or c.endswith("XX") or e.enc.get("statut") != "complète": return False
    vul = e.d["vul"]
    if c.endswith("X") and dernier_contrat(e, "EO" if camp_de(e.decl) == "NS" else "NS")[0]:   # 1. le moteur se sacrifie
        sac, sac_decl, robots = c, e.decl, True
        nous = camp_de(e.decl); eux = "EO" if nous == "NS" else "NS"
        i_c = max(i for i, x, b in e.actives() if b == c.rstrip("X"))
        leur, leur_decl = dernier_contrat(e, eux, i_c)
    else:                                                  # 2. il les laisse jouer leur manche
        leur, leur_decl = c.rstrip("X"), e.decl
        eux = camp_de(e.decl); nous = "EO" if eux == "NS" else "NS"
        robots = False
        rang = ("♣", "♦", "♥", "♠", "SA").index
        nommees = [(x, b[1:]) for _, x, b in e.actives() if camp_de(x) == nous and b[0].isdigit() and b[1:] != "SA"]
        bonnes = [(x, den) for x, den in nommees if sum(len(suites(e.mains[y])[den]) for y in SIEGES if camp_de(y) == nous) >= 9]
        if not bonnes: return False
        x, den = bonnes[0]
        if c.endswith("X"): return False
        niveau = next((k for k in range(1, 8) if (k, rang(den)) > (int(leur[0]), rang(leur[1:]))), 8)
        if niveau > 7: return False
        sac, sac_decl = f"{niveau}{den}X", declarant_de(e, x, den)
    if leur is None or marque(leur, leur_decl, vul, int(leur[0]) + 6) < 300: return False   # pas une manche
    w = levees_dm(mondes_vus(e.d, tuple(x for x in SIEGES if camp_de(x) == nous), e.seq), {sac[1:-1], leur[1:]})
    if len(w) < MONDES_VUS // 2: return False
    eux_marquent = [marque(leur, leur_decl, vul, t[leur[1:]][leur_decl]) for t in w]
    nous_marquons = [marque(sac, sac_decl, vul, t[sac[1:-1]][sac_decl]) for t in w]
    taux = sum(t[leur[1:]][leur_decl] >= int(leur[0]) + 6 for t in w) / len(w)
    cout = -sum(nous_marquons) / len(w); perte = sum(eux_marquent) / len(w)
    if taux < TAUX["sacrifice"] or cout <= 0 or cout >= perte: return False
    e.chances = dict(genre="sacrifice", contrat=sac, declarant=sac_decl, contre=leur, contre_decl=leur_decl, robots=robots,
                     taux=round(taux, 2), cout=round(cout), perte=round(perte), mondes=len(w), encheres=list(e.seq),
                     dm=e.dm[sac[1:-1]][sac_decl])
    return True


def stayman(e): return e.seq[:3] == ["1SA", "passe", "2♣"]


def texas(e): return e.seq[:3] in (["1SA", "passe", "2♦"], ["1SA", "passe", "2♥"])


ENTAME_PRES = .1                                          # l'entame de la règle : au plus 10 points sous la meilleure
ENTAME_MIN = .3                                           # et une vraie chance de battre le contrat, pas un coup de chance


def jeu_entame(e):
    """Le contrat dépend de l'entame : celle des règles (entames.yaml) le bat, une autre le laisse gagner, au double mort
    de la donne réelle ; et à la table (la main du meneur connue, les trois autres imaginées d'après les enchères), cette
    entame bat le contrat au moins ENTAME_MIN du temps, à ENTAME_PRES près aussi souvent que la meilleure entame : la
    donne n'enseigne pas une entame chanceuse."""
    if e.contrat == "passe" or int(e.contrat[0]) < 3: return False
    den = e.contrat[1:].rstrip("X"); need = int(e.contrat[0]) + 6
    v = levees_par_entame(e.mains, den, e.decl)            # les levées de la défense, selon l'entame
    if not v or not 13 - max(v.values()) < need <= 13 - min(v.values()): return False
    regle = entame_et_defense(e.d, e.contrat, e.decl, e.seq)["entame"]["carte"]
    if 13 - v.get(regle, 0) >= need: return False          # l'entame de la règle laisse gagner : celle qui bat est chanceuse
    meneur = LHO[e.decl]
    w = [levees_par_entame(m, den, e.decl) for m in mondes_vus(e.d, (meneur,), e.seq)]
    w = [x for x in w if x]
    if len(w) < MONDES_VUS // 2: return False
    bat = {c: sum(x.get(c, 0) >= 14 - need for x in w) / len(w) for c in v}
    if bat[regle] < ENTAME_MIN or bat[regle] < max(bat.values()) - ENTAME_PRES: return False
    meilleure = max(bat, key=bat.get)
    e.chances = dict(genre="entame", contrat=e.contrat.rstrip("X"), declarant=e.decl, entame=regle, taux=round(bat[regle], 2),
                     meilleure=meilleure, taux_meilleure=round(bat[meilleure], 2), mondes=len(w), encheres=list(e.seq))
    return True


def laisser_passer_reel(e, entame):
    """Sur la donne réelle, au double mort : sur l'entame (le mort fournit petit, le troisième joue au mieux), laisser
    passer gagne le contrat et prendre le fait chuter. Le laisser-passer est nécessaire, pas seulement possible."""
    den = e.contrat[1:].rstrip("X"); need = int(e.contrat[0]) + 6
    pos = coups._apres(e.mains, den, e.decl, [(entame[0], entame[1:].translate(coups.EN))])
    pos.jouer(*coups._naturelle(coups._options_mort(pos), den))
    v = pos.valeurs(); fin = min(v.values())
    pos.jouer(*max((x for x, y in v.items() if y == fin), key=lambda x: coups.RANGS.index(x[1])))
    top = pos.meilleur()
    if pos.camp(top[0]): return False                      # le troisième n'a pas pris : rien à laisser passer
    v = pos.valeurs()
    prend = lambda c, r: (c == top[1] and coups.RANGS.index(r) < coups.RANGS.index(top[2])) or (c == den and top[1] != den)
    oui = [x for k, x in v.items() if prend(*k)]; non = [x for k, x in v.items() if not prend(*k)]
    return bool(oui and non) and max(non) >= need > max(oui)


def hold_up(e):
    """À SA, l'entame (des règles) dans une couleur où le déclarant n'a qu'un arrêt, l'as (filtre rapide) ; sur la
    donne réelle, laisser passer le premier tour gagne et prendre chute (laisser_passer_reel) ; et c'est aussi la bonne
    ligne à la table : sur les donnes imaginées par le déclarant (sa main et le mort, l'entame, le reste d'après les
    enchères), ne pas prendre gagne nettement plus souvent que prendre (coups.premier_pli). Une donne où le
    laisser-passer ne marche que par chance n'apprend pas une mauvaise habitude."""
    c = e.contrat
    if c == "passe" or c.endswith("X") or not c.endswith("SA") or int(c[0]) < 2: return False
    entame = entame_et_defense(e.d, c, e.decl, e.seq)["entame"]["carte"]
    nous = suites(e.mains[e.decl])[entame[0]] + suites(e.mains[PART[e.decl]])[entame[0]]
    if "A" not in nous or "R" in nous or len(nous) > 7: return False   # filtre rapide : un seul arrêt, l'as
    if not laisser_passer_reel(e, entame): return False
    txt = coups.premier_pli(e.d, c, e.decl, entame, e.seq)
    if "Ne pas prendre" not in txt: return False
    e.chances = dict(genre="hold-up", contrat=c, declarant=e.decl, entame=entame, texte=txt, encheres=list(e.seq))
    return True


def squeeze_lisible(e):
    """Un squeeze (coup) sur un défenseur qui a parlé : une enchère, des points ou une longueur montrés (jeu.lire_encheres).
    Le déclarant peut alors lire la fin de coup ; un squeeze sur un joueur muet ne s'enseigne qu'au double mort."""
    if not coup(e, "squeeze"): return False
    cx = lire_encheres(e.seq, e.d["donneur"])
    k = SIEGES.index(e.d["donneur"])
    a_parle = {SIEGES[(k + i) % 4] for i, b in enumerate(e.seq) if b != "passe"}
    for x in e._coups:
        if x["type"] == "squeeze" and (x["joueur"] in a_parle or cx[x["joueur"]]["pts"][0] >= 8
                                       or any(v >= 4 for v in cx[x["joueur"]]["L"].values())):
            e.chances = dict(genre="squeeze", contrat=e.contrat.rstrip("X"), declarant=e.decl, joueur=x["joueur"],
                             encheres=list(e.seq))
            return True
    return False


def coup(e, *genres):
    """Un de ces coups trouvé sur le contrat du moteur, qui gagne juste au double mort : sans levée de mieux, le coup compte."""
    if not (e.fait() and int(e.contrat[0]) >= 3): return False
    den = e.contrat[1:].rstrip("X")
    if e.dm[den][e.decl] != int(e.contrat[0]) + 6: return False
    entame = entame_et_defense(e.d, e.contrat, e.decl, e.seq)["entame"]["carte"]
    e._coups = coups.analyser(e.mains, den, e.decl, entame)
    return any(x["type"] in genres for x in e._coups)


def plan_court(e):
    """(le compte, la fin du plan) si le déclarant compte une levée de moins, à la table, et que le contrat gagne
    juste au double mort : la levée existe, il faut la trouver. None sinon."""
    if not (e.fait() and int(e.contrat[0]) >= 2): return None
    den = e.contrat[1:].rstrip("X")
    if e.dm[den][e.decl] != int(e.contrat[0]) + 6: return None
    entame = entame_et_defense(e.d, e.contrat, e.decl, e.seq)["entame"]
    _, _, fin, reste = compter_plan(e.d, e.contrat, e.decl, entame, e.seq)
    return (reste, fin) if reste == 1 else None


def evaluer(e):
    """1re année : décider d'ouvrir ou de passer. Un joueur qui parle avant l'ouverture (ou l'ouvreur) a 10 à 12 H."""
    i, s, o = premier_actif(e)
    if i is None: return any(10 <= e.h(x) <= 12 for x in SIEGES)
    k = SIEGES.index(e.d["donneur"])
    return any(10 <= e.h(SIEGES[(k + j) % 4]) <= 12 for j in range(i + 1))


def soutien_majeure(e):
    """1re année : 1♥ ou 1♠ d'ouverture, et le partenaire soutient la majeure à sa première enchère (2, 3 ou 4)."""
    i, s, o = premier_actif(e)
    if o not in ("1♥", "1♠") or i + 2 >= len(e.seq): return False
    b = e.seq[i + 2]
    return b in (f"2{o[1]}", f"3{o[1]}", f"4{o[1]}")


def a_une_impasse(e):
    """Filtre rapide : une impasse classique (jeu.impasses) existe dans le camp du déclarant du moteur."""
    if e.contrat == "passe": return False
    d_, m_ = suites(e.mains[e.decl]), suites(e.mains[PART[e.decl]])
    return any(impasses((e.decl, d_), (PART[e.decl], m_), c) for c in COULEURS)


def plan_compte(e, mot=None):
    """Le contrat (manche ou partielle) gagne juste au double mort et le plan à la table compte assez de levées
    (avec les partages normaux) ; mot : un mot que le plan doit contenir. « impasse » : il manque une levée avec les
    partages normaux, le plan dit qu'il faut réussir une impasse, et impasse_juste."""
    if mot == "impasse" and not a_une_impasse(e): return False
    if not (e.fait() and int(e.contrat[0]) >= 2): return False
    den = e.contrat[1:].rstrip("X")
    if e.dm[den][e.decl] != int(e.contrat[0]) + 6: return False
    entame = entame_et_defense(e.d, e.contrat, e.decl, e.seq)["entame"]
    compte, etapes, fin, reste = compter_plan(e.d, e.contrat, e.decl, entame, e.seq)
    if mot == "impasse":                                   # une levée manque sans impasse, et une impasse la donne (reste <= 0
        plan = " ".join(t for _, t in etapes if "Levée manquante" in t)    # veut dire : le contrat n'en dépend pas)
        return reste == 1 and "Il faut réussir" in str(fin) and impasse_juste(e, entame, plan)
    if mot: return reste <= 0 and mot in (str(etapes) + str(fin)).lower()
    return reste <= 0


IMPASSE_MIN = .5                                          # l'honneur bien placé dans au moins la moitié des donnes imaginées


def impasse_juste(e, entame, plan):
    """Une impasse du plan (jeu.impasses, nommée dans le plan) réussit sur la donne réelle, et le déclarant a raison de la
    faire : dans au moins IMPASSE_MIN des donnes qu'il imagine (sa main et le mort, l'entame, le reste fidèle aux
    enchères), l'honneur est du bon côté. Une impasse que les enchères condamnent n'est pas un bon exemple."""
    decl = e.decl; mort = PART[decl]
    s_dec, s_mort = suites(e.mains[decl]), suites(e.mains[mort])
    imps = [(c, t, h, w) for c in COULEURS for t, h, w in impasses((decl, s_dec), (mort, s_mort), c) if t.split(" : ")[1] in plan
            or t in plan]
    if not imps: return False
    def reussit(m, c, t, h, w):
        x = suites(m[w])[c]
        return any(y in x for y in h) if " ou " in t else all(y in x for y in h)
    imps = [x for x in imps if reussit(e.mains, *x)]          # elle réussit sur la donne
    if not imps: return False
    mondes = donnes_du_declarant(e.d, decl, e.seq, entame["carte"], 60)
    if len(mondes) < 20: return False
    for c, t, h, w in imps:
        p = sum(reussit(m, c, t, h, w) for m in mondes) / len(mondes)
        if p >= IMPASSE_MIN:
            e.chances = dict(genre="impasse", contrat=e.contrat.rstrip("X"), declarant=decl, impasse=t, taux=round(p, 2),
                             mondes=len(mondes), encheres=list(e.seq))
            return True
    return False


THEMES = {
    ALEATOIRE: lambda e: True,
    "Barrage": barrage,
    "Michaels et bicolores": bicolore,
    "Blackwood": blackwood,
    "Chelem": lambda e: chelem(e, (6, 7)),
    "Contre d'appel": contre_appel,
    "Contre Spoutnik": spoutnik,
    "Drury": drury,
    "Enchères à SA": lambda e: ouverture(e) in ("1SA", "2SA"),
    "Entame décisive": jeu_entame,
    "Grand chelem": lambda e: chelem(e, (7,)),
    "Hold-up": hold_up,
    "Intervention": intervention,
    "Jeu de la carte": lambda e: bool(plan_court(e)),
    "Jeu de la carte avancé": lambda e: coup(e, "squeeze", "mise en main", "laisser-passer", "coup à blanc"),
    "Manche à SA": lambda e: manche(e, ("3SA",)),
    "Manche en majeure": lambda e: manche(e, ("4♥", "4♠")),
    "Manche en mineure": lambda e: manche(e, ("5♣", "5♦")),
    "Mise en main": lambda e: coup(e, "mise en main"),
    "Partielle disputée": partielle,
    "Petit chelem": lambda e: chelem(e, (6,)),
    "Quatrième couleur forcing": quatrieme,
    "Réveil": reveil,
    "Roudi": roudi,
    "Sacrifice": sacrifice,
    "Squeeze": squeeze_lisible,
    "Stayman": stayman,
    "Texas": texas,
    "Évaluer sa main": evaluer,
    "Soutien de la majeure": soutien_majeure,
    "Compter ses levées": lambda e: plan_compte(e),
    "L'impasse": lambda e: plan_compte(e, "impasse"),
}

# un thème rare : à mi-temps, le test d'avant suffit (le commentaire ne dit alors rien de la table)
SOUPLE = {"Squeeze": lambda e: coup(e, "squeeze")}

# la famille (enchères ou jeu de la carte) et le niveau (1 : 1re année, 2 : intermédiaire, 3 : avancé) de chaque thème
FAMILLES = {"encheres": "Enchères", "carte": "Jeu de la carte"}
NIVEAUX = {1: "1re année", 2: "Intermédiaire", 3: "Avancé"}
META = {
    "Évaluer sa main": ("encheres", 1), "Soutien de la majeure": ("encheres", 1), "Enchères à SA": ("encheres", 1),
    "Manche à SA": ("encheres", 1), "Manche en majeure": ("encheres", 1), "Manche en mineure": ("encheres", 1),
    "Stayman": ("encheres", 1), "Texas": ("encheres", 1), "Barrage": ("encheres", 1), "Intervention": ("encheres", 1),
    "Contre d'appel": ("encheres", 2), "Contre Spoutnik": ("encheres", 2), "Réveil": ("encheres", 2), "Michaels et bicolores": ("encheres", 2),
    "Quatrième couleur forcing": ("encheres", 2), "Partielle disputée": ("encheres", 2), "Blackwood": ("encheres", 2),
    "Petit chelem": ("encheres", 2), "Drury": ("encheres", 2),
    "Chelem": ("encheres", 3), "Grand chelem": ("encheres", 3), "Roudi": ("encheres", 3), "Sacrifice": ("encheres", 3),
    "Compter ses levées": ("carte", 1), "L'impasse": ("carte", 1), "Entame décisive": ("carte", 1), "Jeu de la carte": ("carte", 1),
    "Hold-up": ("carte", 2),
    "Jeu de la carte avancé": ("carte", 3), "Mise en main": ("carte", 3), "Squeeze": ("carte", 3),
}
COMBINE = " + "                                           # « Stayman + L'impasse » : une donne pour les deux thèmes


def test_theme(theme):
    """Le test d'un thème, ou de deux combinés (« A + B ») : la donne doit satisfaire les deux."""
    parts = theme.split(COMBINE)
    tests = [THEMES[x] for x in parts]
    return (lambda e: all(t(e) for t in tests)) if len(tests) > 1 else tests[0]


def themes_de(famille, niveau):
    return sorted((t for t, (f, n) in META.items() if f == famille and n == niveau),
                  key=lambda x: unicodedata.normalize("NFD", x).lower())


def combiner(quotas):
    """[(thème, k)] -> les mêmes, les thèmes d'enchères et de jeu de la carte appariés dans les mêmes donnes : autant de
    donnes que la plus longue des deux listes ; ce qui reste d'une famille garde ses propres donnes."""
    enc = [t for t, k in quotas if META.get(t, ("", 0))[0] == "encheres" for _ in range(k)]
    jeu = [t for t, k in quotas if META.get(t, ("", 0))[0] == "carte" for _ in range(k)]
    autres = [(t, k) for t, k in quotas if META.get(t, ("", 0))[0] not in ("encheres", "carte")]
    paires = [f"{a}{COMBINE}{b}" for a, b in zip(enc, jeu)] + enc[len(jeu):] + jeu[len(enc):]
    out = {}
    for t in paires: out[t] = out.get(t, 0) + 1
    return list(out.items()) + autres


def themes_tries():
    return sorted(THEMES, key=lambda x: unicodedata.normalize("NFD", x).lower())


def lire_quotas(args):
    """« Squeeze=4 » « Aléatoire=8 » -> [("Squeeze", 4), ("Aléatoire", 8)] ; les thèmes inconnus et les zéros sont ignorés."""
    out = []
    for a in args:
        t, _, k = a.rpartition("=")
        if all(x in THEMES for x in t.split(COMBINE)) and k.isdigit() and int(k) > 0: out.append((t, int(k)))
    return out


def tirer(rnd):
    cartes = [c + r for c in COULEURS for r in ORDRE]
    rnd.shuffle(cartes)
    return {s: " ".join("".join(sorted((x[1:] for x in cartes[13 * k:13 * k + 13] if x[0] == c), key=ORDRE.index)) or "-" for c in COULEURS)
            for k, s in enumerate(SIEGES)}


def chercher_chrono(arg):
    """chercher, avec l'heure où le processus a commencé cette donne et sa durée (temps-de-calcul.txt : un PC lent
    perd-il son temps à démarrer les processus ou à calculer ?)."""
    t = time.time(); x = chercher(arg)
    return t, time.time() - t, x


def chercher(arg):
    """(n, thème, mains, trouvé, chances) : une donne du thème pour le n° de donne, dans le délai ; chances : ce que
    a_la_table a retenu du contrat (enchères, réussite à la table, double mort réel), ou None."""
    n, theme, graine, delai = arg
    rnd = random.Random(graine); test = test_theme(theme)
    d = dict(n=n, donneur=SIEGES[(n - 1) % 4], vul=VUL16[(n - 1) % 16], mains=None)
    debut = time.time(); fin = debut + delai; essais = 0
    seul = theme.split(COMBINE)[0] if COMBINE in theme else None   # deux thèmes : à mi-temps, le premier suffit
    while True:
        d["mains"] = tirer(rnd); essais += 1
        e = Essai(d)
        if test(e): return n, theme, d["mains"], True, e.chances
        if seul and time.time() > debut + delai / 2 and THEMES[seul](e): return n, seul, d["mains"], True, e.chances
        if theme in SOUPLE and time.time() > debut + delai / 2 and SOUPLE[theme](e): return n, theme, d["mains"], True, None
        if time.time() > fin: return n, theme, tirer(rnd), False, None


def lire_texte(ligne):
    """« PRDX76C32K…T… » × 4 (Nord, Est, Sud, Ouest), puis la vulnérabilité (N-S puis E-O : V ou N) et le donneur :
    « VVN » = tous vulnérables, donneur Nord. Les cartes : A R D V X (ou 10) 9 … 2 ; une couleur vide ne garde que sa
    lettre. La quatrième main peut manquer : ce sont les cartes qui restent. Sans la fin, vulnérabilité et donneur
    suivent le numéro de la donne. -> {"mains": …, "vul": … ou None, "donneur": … ou None} ; ValueError en français."""
    x = re.sub(r"[^A-Z0-9]", "", ligne.upper()).replace("10", "X")
    if not x: raise ValueError("ligne vide")
    vul = donneur = None
    if x[-1] in "NESO":                                    # aucune carte ne s'écrit N, E, S ou O : la fin est là
        if len(x) < 3 or x[-3:-1] not in VUL_TEXTE: raise ValueError(f"fin « {x[-3:]} » : vulnérabilité N-S et E-O (V ou N), puis le donneur (N, E, S ou O)")
        vul, donneur, x = VUL_TEXTE[x[-3:-1]], x[-1], x[:-3]
    if x[0] != "P": raise ValueError("chaque main commence par P (les piques), puis C, K et T")
    groupes = re.findall(r"([PCKT])([^PCKT]*)", x)
    if len(groupes) not in (12, 16): raise ValueError(f"{len(groupes)} couleurs trouvées : il en faut 16 (ou 12, la dernière main se déduit)")
    mains, vues = {}, set()
    for k in range(len(groupes) // 4):
        cartes = []
        for (lettre, rangs), attendue in zip(groupes[4 * k:4 * k + 4], "PCKT"):
            if lettre != attendue: raise ValueError(f"main {SIEGES[k]} : {attendue} attendu, {lettre} trouvé (ordre P C K T)")
            for r in rangs:
                if r not in ORDRE: raise ValueError(f"main {SIEGES[k]} : « {r} » n'est pas une carte")
                if (lettre, r) in vues: raise ValueError(f"{LETTRES[lettre]}{r} apparaît deux fois")
                vues.add((lettre, r)); cartes.append((lettre, r))
        if len(cartes) != 13: raise ValueError(f"main {SIEGES[k]} : {len(cartes)} cartes au lieu de 13")
        mains[SIEGES[k]] = cartes
    if len(mains) == 3:
        mains["O"] = [(l, r) for l in "PCKT" for r in ORDRE if (l, r) not in vues]
    return dict(mains={s: " ".join("".join(sorted((r for l, r in c if l == lettre), key=ORDRE.index)) or "-" for lettre in "PCKT")
                       for s, c in mains.items()}, vul=vul, donneur=donneur)


def texte_de(d):
    """La donne écrite comme lire_texte la lit."""
    corps = "".join(lettre + ("" if x == "-" else x) for s in SIEGES for lettre, x in zip("PCKT", d["mains"][s].split()))
    return corps + {v: k for k, v in VUL_TEXTE.items()}[d["vul"]] + d["donneur"]


def creer_saisies(lignes, dossier=None):
    """Les donnes saisies à la main, dans un fichier comme ceux de creer. Les lignes vides ne comptent pas."""
    lues = [lire_texte(l) for l in lignes if l.strip()]
    donnes = []
    for n, x in enumerate(lues, 1):
        donnes.append(donne_complete(n, SAISIE, x["mains"], True, x["donneur"], x["vul"]))
        print(f"Donne {n} sur {len(lues)}", flush=True)
    return ecrire(donnes, [SAISIE], dossier)


def donne_complete(n, theme, mains, trouve, donneur=None, vul=None, chances=None):
    dm = double_mort(mains)
    d = dict(n=n, donneur=donneur or SIEGES[(n - 1) % 4], vul=vul or VUL16[(n - 1) % 16], mains=mains, tables=[], dm=dm,
             theme=theme if trouve else ALEATOIRE)
    if chances and trouve: d["chances"] = chances           # le contrat du thème jugé à la table (commentaires.chances)
    d["hcp"] = {s: Main(mains[s]).hcp for s in SIEGES}
    d["par"] = par(he_de(dm, d["hcp"]), d["vul"], EN[d["donneur"]])
    return d


def creer(quotas, graine=None, delai=DELAI, dossier=None):
    """quotas : [(thème, nombre de donnes)]. Écrit le fichier et le renvoie. Dit l'avancement ligne par ligne, comme rapport.py."""
    rnd = random.Random(graine)
    themes = list(dict.fromkeys(x for t, k in quotas if k > 0 for x in t.split(COMBINE)))
    tirage = [t for t, k in quotas for _ in range(k)]
    nombre = len(tirage)
    rnd.shuffle(tirage)
    args = [(i, t, rnd.randrange(2 ** 31), delai) for i, t in enumerate(tirage, 1)]
    res = []; departs = []; durees = []; npro = lignes.nb_processus(); t_pool = time.time()
    with multiprocessing.Pool(npro) as p:
        for k, (dep, duree, x) in enumerate(p.imap_unordered(chercher_chrono, args), 1):
            res.append(x); departs.append(dep); durees.append(duree); print(f"Donne {k} sur {nombre}", flush=True)
    print(f"Temps : chargement {t_pool - _T0:.1f} s, démarrage des {npro} processus {min(departs) - t_pool:.1f} s, "
          f"une donne {sum(durees) / len(durees):.1f} s de calcul en moyenne, en tout {time.time() - t_pool:.1f} s", flush=True)
    res.sort()
    manquees = [x[1] for x in res if not x[3]]
    voulus = {i: t for i, t, _, _ in args}
    for n, t, m, ok, _ in res:                             # deux thèmes voulus, un seul trouvé : on le dit
        if ok and voulus.get(n) != t: print(f"Thème non trouvé : {voulus[n]}, la donne {n} ne garde que {t}", flush=True)
    donnes = [donne_complete(n, t, m, ok, chances=c) for n, t, m, ok, c in res]
    chemin = ecrire(donnes, themes, dossier)
    for t in dict.fromkeys(manquees):
        print(f"Thème non trouvé : {t}, {manquees.count(t)} donne(s) tirée(s) au hasard à la place", flush=True)
    print(f"Fichier prêt : {chemin}", flush=True)
    return chemin


def nom_entrainement(dossier, now, themes=()):
    """(titre, nom) : « Entraînement du mardi 3 novembre 2026 – Squeeze », « 2026-11-03-entrainement-squeeze » ; -2, -3…
    si ce nom est déjà pris (fichiers.entrainement)."""
    import fichiers
    titre, nom = fichiers.entrainement(now, themes)
    return titre, fichiers.nom_libre(dossier, nom)


def ecrire(donnes, themes, dossier=None):
    """Le fichier Bridge Coach (.bc.json) et le .pbn à côté ; renvoie le chemin du .bc.json."""
    import rapport
    now = datetime.datetime.now()
    data = dict(session=dict(date=now.strftime("%d/%m/%Y"), tables=0, sections=["A"], mitchell=False, themes=list(themes),
                                marque="IMP"),
                donnes=donnes, paires={}, alertes=[])
    rapport.preparer_donnees()
    sortie = dossier or os.path.join(rapport.SEANCES, now.strftime("%Y-%m"))
    os.makedirs(sortie, exist_ok=True)
    titre, nom = nom_entrainement(sortie, now, themes)
    genre = "saisie" if list(themes) == [SAISIE] else "entrainement"
    rapport.entete(data, genre, nom)
    import fichiers
    fichiers.nouvel_entete(data, genre, None, titre, "Donnes saisies" if genre == "saisie" else
                           f"Créée : {len(donnes)} donne{'s' if len(donnes) > 1 else ''} d'entraînement")
    chemin = os.path.join(sortie, nom + rapport.BC)
    rapport.ecrire_bc(data, chemin)
    with open(os.path.join(sortie, nom + ".pbn"), "w", encoding="utf-8") as f: f.write(pbn(data))
    return chemin


if __name__ == "__main__":
    multiprocessing.freeze_support()
    if sys.argv[1] == "--texte":
        print(f"Fichier prêt : {creer_saisies(open(sys.argv[2], encoding='utf-8').read().splitlines())}", flush=True)
        sys.exit()
    graine = next((int(a.split("=", 1)[1]) for a in sys.argv[1:] if a.startswith("--graine=")), None)
    q = lire_quotas([a for a in sys.argv[1:] if not a.startswith("--")])
    creer(combiner(q) if "--combiner" in sys.argv else q, graine)   # donnes.py "Squeeze=4" "Aléatoire=8"
