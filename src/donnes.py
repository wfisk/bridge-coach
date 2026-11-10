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

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from bws_extract import SEAT, SN, VUL16, par
from encheres import encherir
from encheres.main import Main
from jeu import COULEURS, ORDRE, compter_plan, levees_par_entame, entame_et_defense, _pbn
import coups, lignes

ALEATOIRE = "Aléatoire"
SAISIE = "Donne saisie"
LETTRES = {"P": "♠", "C": "♥", "K": "♦", "T": "♣"}
VUL_TEXTE = {"NN": "Personne", "VN": "N-S", "NV": "E-O", "VV": "Tous"}
DELAI = 150                                                # secondes pour trouver une donne d'un thème
SIEGES = "NESO"
EN = {"N": "N", "E": "E", "S": "S", "O": "W"}
COUL = {"SA": "NT", "♠": "S", "♥": "H", "♦": "D", "♣": "C"}
VUL_PBN = {"Personne": "None", "N-S": "NS", "E-O": "EW", "Tous": "All"}
RANG_EN = str.maketrans({"R": "K", "D": "Q", "V": "J", "X": "T"})
PART = {"N": "S", "S": "N", "E": "O", "O": "E"}


class Essai:
    """Une donne tirée, et ce qu'en disent le moteur et le solveur, calculés seulement si un thème le demande."""

    def __init__(self, d):
        self.d = d; self.mains = d["mains"]; self._enc = self._dm = None

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


def chelem(e, tricks):
    """Un camp fait exactement ce nombre de levées (12 ou 13 ou plus) à son meilleur contrat, avec les points pour y aller."""
    for s in "NE":
        t = max(x[y] for x in e.dm.values() for y in (s, PART[s]))
        if t in tricks and e.camp_h(s) >= 27: return True
    return False


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


def blackwood(e): return "4SA" in e.seq and bool(re.match(r"^[67]", e.contrat)) and e.fait()


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


def partielle(e):
    a = e.actives()
    c = e.contrat
    if c == "passe" or c[0] not in "123" or c.rstrip("X").endswith("SA") and c[0] == "3": return False
    return len({"NS" if s in "NS" else "EO" for _, s, b in a if b not in ("contre", "surcontre")}) == 2


def sacrifice(e):
    p = par(he_de(e.dm, {s: e.h(s) for s in SIEGES}), e.d["vul"], EN[e.d["donneur"]])
    return bool(p and p.get("contre"))


def stayman(e): return e.seq[:3] == ["1SA", "passe", "2♣"]


def texas(e): return e.seq[:3] in (["1SA", "passe", "2♦"], ["1SA", "passe", "2♥"])


def jeu_entame(e):
    """Le contrat dépend de l'entame : il chute sur une, gagne sur les autres."""
    if e.contrat == "passe" or int(e.contrat[0]) < 3: return False
    den = e.contrat[1:].rstrip("X"); need = int(e.contrat[0]) + 6
    v = levees_par_entame(e.mains, den, e.decl)            # les levées de la défense, selon l'entame
    return 13 - max(v.values()) < need <= 13 - min(v.values())


def coup(e, *genres):
    """Un de ces coups trouvé sur le contrat du moteur, qui gagne juste au double mort : sans levée de mieux, le coup compte."""
    if not (e.fait() and int(e.contrat[0]) >= 3): return False
    den = e.contrat[1:].rstrip("X")
    if e.dm[den][e.decl] != int(e.contrat[0]) + 6: return False
    entame = entame_et_defense(e.d, e.contrat, e.decl, e.seq)["entame"]["carte"]
    return any(x["type"] in genres for x in coups.analyser(e.mains, den, e.decl, entame))


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


def plan_compte(e, mot=None):
    """Le contrat (manche ou partielle) gagne juste au double mort et le plan à la table compte assez de levées
    (avec les partages normaux) ; mot : un mot que le plan doit contenir (« impasse »)."""
    if not (e.fait() and int(e.contrat[0]) >= 2): return False
    den = e.contrat[1:].rstrip("X")
    if e.dm[den][e.decl] != int(e.contrat[0]) + 6: return False
    entame = entame_et_defense(e.d, e.contrat, e.decl, e.seq)["entame"]
    compte, etapes, fin, reste = compter_plan(e.d, e.contrat, e.decl, entame, e.seq)
    if mot: return reste <= 0 and mot in (str(etapes) + str(fin)).lower()
    return reste <= 0


THEMES = {
    ALEATOIRE: lambda e: True,
    "Barrage": barrage,
    "Michaels et bicolores": bicolore,
    "Blackwood": blackwood,
    "Chelem": lambda e: chelem(e, (12, 13)),
    "Contre d'appel": contre_appel,
    "Contre Spoutnik": spoutnik,
    "Drury": drury,
    "Enchères à SA": lambda e: ouverture(e) in ("1SA", "2SA"),
    "Entame décisive": jeu_entame,
    "Grand chelem": lambda e: chelem(e, (13,)),
    "Hold-up": lambda e: coup(e, "laisser-passer"),
    "Intervention": intervention,
    "Jeu de la carte": lambda e: bool(plan_court(e)),
    "Jeu de la carte avancé": lambda e: coup(e, "squeeze", "mise en main", "laisser-passer", "coup à blanc"),
    "Manche à SA": lambda e: e.contrat.rstrip("X") == "3SA" and e.fait(),
    "Manche en majeure": lambda e: e.contrat.rstrip("X") in ("4♥", "4♠") and e.fait(),
    "Manche en mineure": lambda e: e.contrat.rstrip("X") in ("5♣", "5♦") and e.fait(),
    "Mise en main": lambda e: coup(e, "mise en main"),
    "Partielle disputée": partielle,
    "Petit chelem": lambda e: chelem(e, (12,)),
    "Quatrième couleur forcing": quatrieme,
    "Réveil": reveil,
    "Roudi": roudi,
    "Sacrifice": sacrifice,
    "Squeeze": lambda e: coup(e, "squeeze"),
    "Stayman": stayman,
    "Texas": texas,
    "Évaluer sa main": evaluer,
    "Soutien de la majeure": soutien_majeure,
    "Compter ses levées": lambda e: plan_compte(e),
    "L'impasse": lambda e: plan_compte(e, "impasse"),
}

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


def chercher(arg):
    """(n, thème, mains, trouvé) : une donne du thème pour le n° de donne, dans le délai."""
    n, theme, graine, delai = arg
    rnd = random.Random(graine); test = test_theme(theme)
    d = dict(n=n, donneur=SIEGES[(n - 1) % 4], vul=VUL16[(n - 1) % 16], mains=None)
    debut = time.time(); fin = debut + delai; essais = 0
    seul = theme.split(COMBINE)[0] if COMBINE in theme else None   # deux thèmes : à mi-temps, le premier suffit
    while True:
        d["mains"] = tirer(rnd); essais += 1
        e = Essai(d)
        if test(e): return n, theme, d["mains"], True, essais
        if seul and time.time() > debut + delai / 2 and THEMES[seul](e): return n, seul, d["mains"], True, essais
        if time.time() > fin: return n, theme, tirer(rnd), False, essais


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


def donne_complete(n, theme, mains, trouve, donneur=None, vul=None):
    dm = double_mort(mains)
    d = dict(n=n, donneur=donneur or SIEGES[(n - 1) % 4], vul=vul or VUL16[(n - 1) % 16], mains=mains, tables=[], dm=dm,
             theme=theme if trouve else ALEATOIRE)
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
    res = []
    with multiprocessing.Pool(lignes.nb_processus()) as p:
        for k, x in enumerate(p.imap_unordered(chercher, args), 1):
            res.append(x); print(f"Donne {k} sur {nombre}", flush=True)
    res.sort()
    manquees = [x[1] for x in res if not x[3]]
    voulus = {i: t for i, t, _, _ in args}
    for n, t, m, ok, _ in res:                             # deux thèmes voulus, un seul trouvé : on le dit
        if ok and voulus.get(n) != t: print(f"Thème non trouvé : {voulus[n]}, la donne {n} ne garde que {t}", flush=True)
    donnes = [donne_complete(n, t, m, ok) for n, t, m, ok, _ in res]
    chemin = ecrire(donnes, themes, dossier)
    for t in dict.fromkeys(manquees):
        print(f"Thème non trouvé : {t}, {manquees.count(t)} donne(s) tirée(s) au hasard à la place", flush=True)
    print(f"Fichier prêt : {chemin}", flush=True)
    return chemin


def nom_entrainement(dossier, now):
    """« entrainement-2026-11-03 » ; l'heure s'ajoute seulement si ce nom est déjà pris ce jour-là."""
    import rapport
    nom = f"entrainement-{now.strftime('%Y-%m-%d')}"
    return nom if not os.path.exists(os.path.join(dossier, nom + rapport.BC)) else f"{nom}-{now.strftime('%H%M%S')}"


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
    nom = nom_entrainement(sortie, now)
    data["session"]["titre"] = f"Entraînement {now.strftime('%Y-%m-%d')}"
    rapport.entete(data, "saisie" if list(themes) == [SAISIE] else "entrainement", nom)
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
