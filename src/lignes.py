# -*- coding: utf-8 -*-
"""Le déclarant simulé (systems/technique/jeu-de-la-carte.md, « Déclarant simulé »).

À chaque carte, le déclarant imagine des mondes fidèles aux enchères, à l'entame et à ce qui a été
joué, résout chacun et garde la carte qui gagne le contrat le plus souvent : il ne voit jamais les
mains adverses de la donne jouée. Seule la défense joue au double mort. Ce n'est pas une simulation
de l'entame, qui reste aux règles.

    jouer(m, den, decl, lead, pool, need, k, rnd) -> (levées, couleurs menées, plis)
    analyser(d, contrat, decl, entame, encheres) -> {"taux", "levees", "n", "rang", "ligne", "decide",
                                                     "impasses", "coupes_avant"}
    phrase(a) -> la phrase « Essai à la table » du plan de jeu
"""
import atexit, multiprocessing, os, random
from collections import Counter

from coups import FR, EN, Position, RANGS, _main
from jeu import COULEURS, LHO, PART, _donne_dds, donnes_du_declarant

LETTRES = dict(zip(COULEURS, "SHDC"))
CACHE = {}
PARALLELE = False       # rapport.py l'active : sur Mac et Windows, chaque processus relit le script lancé
ATTENTE = 900           # secondes : au-delà, un processus bloqué, on rejoue sans parallélisme
MEMOIRE_PROCESSUS = .8  # Go, mesuré sur Mac avec le solveur
_POOL = None


def _ensemble(main):
    """« AR5 D8 - X » -> {"SA", "SK", …}, en rangs anglais."""
    return {LETTRES[c] + r for c, p in _main(main).items() for r in p}


def _texte(cartes):
    return " ".join("".join(sorted((x[1] for x in cartes if x[0] == c), key=RANGS.index)).translate(FR) or "-" for c in "SHDC")


def _mondes(pos, pool, vides, k, rnd):
    """k mains adverses fidèles aux cartes jouées et aux défausses, prises dans pool (fidèle aux
    enchères), puis complétées au hasard si elles deviennent rares."""
    g, dr = LHO[pos.decl], PART[LHO[pos.decl]]
    joue = {g: [], dr: []}
    for s, x in zip(pos.sieges, pos.jouees):
        if s in joue: joue[s].append(x)

    def va(m):
        for s in (g, dr):
            h = _ensemble(m[s])
            if any(x not in h for x in joue[s]): return False
            if any(x[0] in vides[s] and x not in joue[s] for x in h): return False
        return True
    bons = [m for m in pool if va(m)]
    rnd.shuffle(bons); bons = bons[:k]
    if len(bons) < k:
        nous = _ensemble(pos.mains[pos.decl]) | _ensemble(pos.mains[PART[pos.decl]])
        libres = sorted({c + r for c in "SHDC" for r in RANGS} - nous - set(joue[g]) - set(joue[dr]))
        n = 13 - len(joue[g])
        for _ in range(4000):
            if len(bons) >= k: break
            rnd.shuffle(libres)
            lots = {g: joue[g] + libres[:n], dr: joue[dr] + libres[n:]}
            if any(x[0] in vides[s] for s in (g, dr) for x in lots[s] if x not in joue[s]): continue
            m = dict(pos.mains)
            for s in (g, dr): m[s] = _texte(lots[s])
            bons.append(m)
    return bons


def _carte(pos, pool, vides, need, k, rnd):
    """La carte du déclarant ou du mort qui gagne le contrat dans le plus de mondes ; à égalité, la plus
    prudente, puis celle qui fait le plus de levées, puis la plus petite."""
    from endplay.dds import solve_all_boards
    from endplay.types import Card
    leg = pos.legales()
    if len(leg) == 1: return leg[0]
    dd = []
    for m in _mondes(pos, pool, vides, k, rnd):
        x = _donne_dds(m, pos.den, pos.decl)
        for j in pos.jouees: x.play(Card(j))
        dd.append(x)
    gains = {c: 0 for c in leg}; total = {c: 0 for c in leg}
    for sol in solve_all_boards(dd):
        v = {(str(a)[0], str(a)[1:]): t for a, t in sol}
        prec = {}
        for c, r in leg:                                   # une carte absente vaut sa voisine équivalente
            t = v.get((c, r), prec.get(c, 0)); prec[c] = t
            gains[(c, r)] += pos.gagnes + t >= need; total[(c, r)] += t

    def prudence(x):
        """À égalité, le jeu sûr : quand tous les mondes disent « ça gagne », le double mort se moque de
        l'ordre, pas la table. On tire les atouts adverses, on ne coupe pas sans besoin."""
        if not gains[x] or pos.den not in LETTRES: return 0
        if not pos.pli:
            return x[0] == pos.den and any(LETTRES[pos.den] + y not in pos.jouees and LETTRES[pos.den] + y not in nous for y in RANGS)
        return x[0] != pos.den
    nous = _ensemble(pos.mains[pos.decl]) | _ensemble(pos.mains[PART[pos.decl]])
    return max(reversed(leg), key=lambda x: (gains[x], prudence(x), total[x]))


def jouer(m, den, decl, lead, pool, need, k=12, rnd=None):
    """(levées, couleurs menées par le camp du déclarant, plis [(siège, couleur, rang) × 4, gagnant])
    sur la donne m : le déclarant ne connaît de m que ses deux mains et les cartes jouées, la défense
    joue au double mort."""
    rnd = rnd or random.Random(1)
    pos = Position(m, den, decl); pos.sieges = []; ordre = []; plis = []
    vides = {LHO[decl]: set(), PART[LHO[decl]]: set()}

    def poser(c, r):
        s = pos.au_trait()
        if pos.pli and c != pos.pli[0][1] and s in vides: vides[s].add(LETTRES[pos.pli[0][1]])
        if not pos.pli and pos.camp(s): ordre.append(c)
        pos.sieges.append(s); en_cours = pos.pli + [(s, c, r)]; pos.jouer(c, r)
        if not pos.pli: plis.append((en_cours, pos.tete))
    poser(*lead); ordre.clear()
    while any(pos.reste[pos.au_trait()].values()):
        s = pos.au_trait()
        if pos.camp(s): poser(*_carte(pos, pool, vides, need, k, rnd)); continue
        leg = pos.legales()
        if len(leg) == 1: poser(*leg[0]); continue
        v = pos.valeurs(); fin = min(v.values())
        poser(*max((x for x, y in v.items() if y == fin), key=lambda x: RANGS.index(x[1])))
    return pos.gagnes, ordre, plis


def _essai(arg):
    m, den, decl, lead, pool, need, k, graine = arg
    return jouer(m, den, decl, lead, pool, need, k, random.Random(graine))


def _memoire():
    """La mémoire de l'ordinateur en Go, 8 si on ne sait pas la lire."""
    try:
        if os.name == "nt":
            import ctypes
            class M(ctypes.Structure):
                _fields_ = [("taille", ctypes.c_ulong), ("charge", ctypes.c_ulong), ("total", ctypes.c_ulonglong), ("reste", ctypes.c_ulonglong * 6)]
            m = M(); m.taille = ctypes.sizeof(M)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.total / 2 ** 30
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2 ** 30
    except (AttributeError, OSError, ValueError):
        return 8


def nb_processus(coeurs=None, memoire=None):
    """Un cœur reste libre pour le reste de l'ordinateur. Chaque processus prend environ 0,8 Go (le solveur) :
    on laisse 4 Go à Windows, à Bridgemate et au reste."""
    coeurs = coeurs or os.cpu_count() or 2; memoire = memoire or _memoire()
    return max(1, min(6, coeurs - 1, int((memoire - 4) / MEMOIRE_PROCESSUS)))


REPLIS = []                    # les fois où les processus ont échoué et où le calcul est passé sur un seul cœur


def _lancer(args):
    """Les essais, sur plusieurs processus si PARALLELE ; sans eux si le système les refuse ou si l'un
    d'eux se bloque. Un seul groupe de processus par exécution : sous Windows, en créer coûte cher."""
    global _POOL
    if PARALLELE:
        try:
            if _POOL is None:
                _POOL = multiprocessing.Pool(nb_processus())
                atexit.register(_POOL.terminate)
            return _POOL.map_async(_essai, args).get(ATTENTE)
        except (OSError, multiprocessing.TimeoutError) as ex:
            if _POOL: _POOL.terminate()
            _POOL = None
            REPLIS.append(type(ex).__name__)                # dit dans derniere-analyse.txt : le calcul a continué sur un seul cœur
    return [_essai(a) for a in args]


def _geste(pli, gagnant, avant, decl, den):
    """Ce que fait le camp du déclarant sur un pli : (meneur, couleur, tire | coupe | impasse | cede),
    None si la défense mène. avant : les cartes déjà tombées et celles du déclarant et du mort."""
    (s, c, r), (_, c2, r2), (_, c3, r3), _ = pli
    if s not in (decl, PART[decl]): return None
    if c3 == den and c != den: return s, c, "coupe"
    if c3 == c:                                            # l'impasse : la 3e main garde une carte plus forte
        haut = min(RANGS.index(r3), RANGS.index(r))
        if c2 != c or haut < RANGS.index(r2):
            fortes = [i for i, x in enumerate(RANGS) if i < haut and c + x in avant["3e"]]
            if fortes and any(min(fortes) < i < haut and c + x not in avant["vu"] for i, x in enumerate(RANGS)):
                return s, c, "impasse"
    return s, c, "tire" if gagnant in (decl, PART[decl]) else "cede"


def _gestes(essai, decl, den):
    """Les gestes pli par pli d'un essai, sans le premier pli (celui de l'entame)."""
    m, (_, _, plis) = essai
    nous = {decl: _ensemble(m[decl]), PART[decl]: _ensemble(m[PART[decl]])}
    vu = set(); out = []
    for pli, g in plis:
        tr = pli[2][0]
        cartes = {LETTRES[c] + r for _, c, r in pli}
        avant = {"3e": nous.get(tr, set()), "vu": vu | nous[decl] | nous[PART[decl]] | {LETTRES[pli[1][1]] + pli[1][2]}}
        out.append((_geste([(s, LETTRES[c], r) for s, c, r in pli], g, avant, decl, LETTRES.get(den)), pli))
        vu |= cartes
        for s in nous: nous[s] -= cartes
    return out[1:]


def _ligne(gestes, n, mains, maxi=4):
    """L'ordre des couleurs le plus joué et ce qu'on y fait : [(couleur, geste, siège)]. La ligne carte par
    carte ne se lit pas : deux donnes imaginées la font diverger dès le 2e pli, mais pas les couleurs.
    Seules les couleurs attaquées dans la moitié des essais comptent."""
    par = {}
    for g in gestes:
        vues = {}
        for t in [x for x, _ in g if x]:
            vues.setdefault(t[1], []).append(t)
        rang = {c: i for i, c in enumerate(vues)}
        for c, v in vues.items(): par.setdefault(c, []).append((rang[c], v))
    out = []
    for c, v in par.items():
        if len(v) * 2 < n: continue
        fois = Counter(t[2] for _, x in v for t in {y[2]: y for y in x}.values())
        geste = next((g for g in ("impasse", "coupe") if fois[g] * 5 >= len(v) * 2), Counter(x[0][2] for _, x in v).most_common(1)[0][0])
        siege = Counter(t[0] for _, x in v for t in x if t[2] == geste).most_common(1)[0][0]
        if geste == "coupe" and len(_main(mains[PART[siege]])[next(a for a, b in LETTRES.items() if b == c)]) > 1:
            geste = "tire"                                 # la fin d'une couleur : pas une coupe à prévoir
        out.append((sum(r for r, _ in v) / len(v), c, geste, siege))
    return [x[1:] for x in sorted(out)[:maxi]]


def _decide(essais, gagne, decl, mains):
    """Ce qui fait gagner ou perdre sur les donnes imaginées : le partage d'une couleur ou la place de
    son plus gros honneur manquant. [(écart, texte)], le plus décisif d'abord."""
    g, dr = LHO[decl], PART[LHO[decl]]
    nous = _ensemble(mains[decl]) | _ensemble(mains[PART[decl]])
    out = []

    def comparer(oui, non, texte):
        if min(len(oui), len(non)) < 5: return
        a, b = sum(oui) / len(oui), sum(non) / len(non)
        if abs(a - b) >= .3: out.append((abs(a - b), texte(10 * round(a * 10), 10 * round(b * 10))))
    for c, L in zip(COULEURS, "SHDC"):
        manque = [r for r in RANGS if L + r not in nous]
        if len(manque) >= 3 and 13 - len(manque) >= 7:     # le partage d'une couleur à nous
            mm = len(manque); bon = (mm + 1) // 2 + (0 if mm % 2 else 1)
            lg = [len(_main(m[g])[c]) for m in essais]
            oui = [x for x, k in zip(gagne, lg) if max(k, mm - k) <= bon]
            non = [x for x, k in zip(gagne, lg) if max(k, mm - k) > bon]
            nom = f"{bon}-{mm - bon}"
            comparer(oui, non, lambda a, b, c=c, nom=nom: f"{c} {nom} ou mieux {a} %, plus mal partagés {b} %")
        if manque and manque[0] in "AKQ":                  # la place de l'honneur qui manque
            h = manque[0]; ou = [L + h in _ensemble(m[g]) for m in essais]
            oui = [x for x, k in zip(gagne, ou) if k]; non = [x for x, k in zip(gagne, ou) if not k]
            comparer(oui, non, lambda a, b, c=c, h=h: f"{c}{h.translate(FR)} en {g} {a} %, en {dr} {b} %")
    return sorted(out, key=lambda x: -x[0])[:2]


def analyser(d, contrat, decl, entame, encheres, n=40, k=12):
    """Le déclarant simulé sur n donnes imaginées, jamais la donne réelle : taux de réussite, levées
    moyennes, rang où chaque couleur est attaquée, ordre des couleurs le plus joué, ce qui décide du contrat,
    part des essais qui font chaque impasse, et qui coupent avant de purger. None sans endplay ou sans
    assez de donnes."""
    cle = (tuple(sorted(d["mains"].items())), contrat, decl, entame["carte"], tuple(encheres or ()), n, k)
    if cle in CACHE: return CACHE[cle]
    try:
        import endplay.dds                                 # noqa: F401
    except ImportError:
        return None
    pool = donnes_du_declarant(d, decl, encheres or [], entame["carte"], n + 150)
    if len(pool) < n // 2 + 20: return None
    essais, reste = pool[:n], pool[n:]                     # le déclarant n'imagine pas la donne jouée
    den = contrat[1:].rstrip("X"); need = int(contrat[0]) + 6
    lead = (entame["carte"][0], entame["carte"][1:].translate(EN))
    res = _lancer([(m, den, decl, lead, reste, need, k, i) for i, m in enumerate(essais)])
    rangs = {}
    for _, o, _ in res:
        for c in dict.fromkeys(o): rangs.setdefault(c, []).append(o.index(c))
    gestes = [_gestes(x, decl, den) for x in zip(essais, res)]
    N = len(res); gagne = [x >= need for x, _, _ in res]
    imp = Counter(c for g in gestes for c in {t[1] for t, _ in g if t and t[2] == "impasse"})
    faites = Counter((t[1], t[0], p[0][2], p[2][2]) for g in gestes for t, p in g if t and t[2] == "impasse")
    carte = {}                                             # la façon la plus jouée de faire chaque impasse
    for x, _ in faites.most_common(): carte.setdefault(x[0], x[1:])
    avant = 0
    if den != "SA":                                        # une coupe de la main courte avant le 2e tour d'atout
        L = LETTRES[den]
        for g in gestes:
            tours = 0
            for t, _ in g:
                if t and t[1] == L: tours += 1
                if tours >= 2: break
                if t and t[2] == "coupe": avant += 1; break
    CACHE[cle] = {"taux": sum(gagne) / N, "levees": sum(x for x, _, _ in res) / N, "n": N,
                  "rang": {c: sum(v) / len(v) + (N - len(v)) for c, v in rangs.items()},
                  "ligne": _ligne(gestes, N, d["mains"]),
                  "decide": [x for _, x in _decide(essais, gagne, decl, d["mains"])],
                  "impasses": {c: v / N for c, v in imp.items()}, "impasse_type": carte, "coupes_avant": avant / N}
    return CACHE[cle]


CHANCE = ((.9, "presque sûr"), (.7, "probable"), (.4, "ouvert"), (.15, "difficile"), (0, "très difficile"))
FREQ = ((.75, "presque toujours"), (.4, "souvent"), (.15, "parfois"))


def _dire(x):
    c, g, s = x
    C = next(a for a, b in LETTRES.items() if b == c)
    return {"coupe": f"couper les {C} en {PART[s]}", "impasse": f"impasse à {C}", "cede": f"céder un {C}"}.get(g, f"tirer les {C}")


def phrase(a):
    """La phrase de l'essai pour le plan de jeu. Le taux est arrondi à la dizaine : sur 40 donnes, il
    n'est pas plus précis ; le mot compte plus que le chiffre."""
    mot = next(m for s, m in CHANCE if a["taux"] >= s)
    t = (f"<b>Essai à la table :</b> {mot}. Sur {a['n']} donnes imaginées, sans voir les mains adverses et face à la "
         f"meilleure défense, le contrat gagne environ {10 * round(a['taux'] * 10)} % du temps.")
    if a["ligne"]:
        t += " Ordre le plus joué : " + ", puis ".join(_dire(x) for x in a["ligne"]) + "."
    if a["decide"]:
        t += " Ce qui décide : " + " ; ".join(a["decide"]) + "."
    imp = [(c, next((m for s, m in FREQ if v >= s), None)) for c, v in sorted(a["impasses"].items(), key=lambda x: -x[1])]
    imp = [f"à {next(x for x, y in LETTRES.items() if y == c)} {m}" for c, m in imp if m]
    if imp: t += " Impasses tentées : " + ", ".join(imp) + "."
    return t
