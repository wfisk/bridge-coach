# -*- coding: utf-8 -*-
"""Entame, défense et plan de jeu calculés sans Claude.

À la table : l'entame et la défense ne voient que la main du meneur et les enchères, le plan
que le déclarant, le mort, l'entame et les enchères. Jamais les mains adverses ni le double mort
de la donne réelle ; celui-ci n'est que dans apres_coup, pour le commentaire.
L'entame vient des règles seules (entames.yaml), jamais d'une simulation au double mort. Le double
mort du plan et de apres_coup vient d'endplay (solveur DDS, installé dans .venv).

    entame_et_defense(donne, "4♠", "N", encheres) -> {"entame": {"joueur", "carte"}, "defense": texte}
    plan_de_jeu(donne, "4♠", "N", entame, encheres) -> texte
    apres_coup(donne, "4♠", "N", entame) -> texte du commentaire
Notation française : A R D V X, sièges N E S O ; N, S, E, O sont écrits en toutes lettres par build_pdf.

Les règles sont décrites dans systems/sef-2024/entames.md (entame, défense) et
systems/technique/jeu-de-la-carte.md (plan de jeu) : modifier les deux ensemble.
"""
import math, os, re, sys

COULEURS = "♠♥♦♣"
ORDRE = "ARDVX98765432"
LHO = {"N": "E", "E": "S", "S": "O", "O": "N"}
RHO = {v: k for k, v in LHO.items()}
PART = {"N": "S", "S": "N", "E": "O", "O": "E"}
ROT = ["N", "E", "S", "O"]
HON = "ARDVX"
NOM_HON = {"A": "l'as", "R": "le roi", "D": "la dame", "V": "le valet", "X": "le dix"}


def suites(main_fr):
    return dict(zip(COULEURS, ["" if p == "-" else p for p in main_fr.split()]))


# ---------------------------------------------------------------- entame selon les règles
# systems/sef-2024/entames.md, « Choix de la couleur » et « Choix de la carte »
def couleurs_nommees(encheres, donneur):
    """{siège: couleurs nommées naturellement} : enchères à la couleur jusqu'au palier de 3. Ne comptent pas :
    2♣ et 2♦ forts et le relais, Stayman et ses réponses, texas, la quatrième couleur, le cue-bid dans
    la couleur adverse, le contrôle après un fit (systems/sef-2024/entames.md, « Artificielles »)."""
    out = {x: [] for x in ROT}
    i0 = ROT.index(donneur); prec = {}; tout = {}          # dernière enchère et toutes les enchères de chaque siège
    premiere = True; camp_de = lambda x: (x, PART[x])
    for k, b in enumerate(encheres or []):
        qui = ROT[(i0 + k) % 4]; part = prec.get(PART[qui])
        if b in ("passe", "contre", "surcontre"): continue
        m = re.fullmatch(r"([1-7])([♣♦♥♠]|SA)", b)
        ouverture = premiere; premiere = False
        moi = list(tout.get(qui, [])); partenaire = list(tout.get(PART[qui], []))   # avant cette enchère
        prec[qui] = b; tout.setdefault(qui, []).append(b)
        if not m or m[2] == "SA" or m[1] > "3": continue
        fit = {x[1:] for x in moi + [b]} & {x[1:] for x in partenaire} - {"SA"}
        if fit and m[2] not in fit: continue               # après le fit, une nouvelle couleur est un contrôle
        if ouverture and b in ("2♣", "2♦"): continue       # les ouvertures fortes
        if part in ("2♣", "2♦") and len(partenaire) == 1 and b == "2♦" and part == "2♣" and not moi: continue   # le relais
        # Stayman et texas : seulement sur le 1SA ou le 2SA qui est la première enchère du partenaire, quand on n'a
        # pas encore parlé (ouverture ou intervention) ; dans 1♠ – 1SA – 2♥, le 2♥ de l'ouvreur est naturel
        sur_sa = not moi and partenaire == [part]
        if sur_sa and (part, b) in (("1SA", "2♣"), ("1SA", "2♦"), ("1SA", "2♥"), ("2SA", "3♣"), ("2SA", "3♦"), ("2SA", "3♥")): continue
        if partenaire == ["2♣"] and moi == ["1SA"] and b in ("2♦", "2♥", "2♠"): continue   # réponse au Stayman
        if partenaire == ["3♣"] and moi == ["2SA"] and b in ("3♦", "3♥", "3♠"): continue
        adverses = [c for x in ROT if x not in camp_de(qui) for c in out[x]]
        if m[2] in adverses: continue                      # cue-bid
        nous = {c for x in camp_de(qui) for c in out[x]}
        if m[2] not in nous and len(nous) >= 3: continue   # la quatrième couleur
        if m[2] not in out[qui]: out[qui].append(m[2])
    return out


_ENTAMES = {}


def regles_entame(nom="sef-2024"):
    """Les règles de systems/<nom>/entames.yaml (src/entames.py), ou None si le fichier ne peut
    pas être lu (le programme garde alors son code, entame_code)."""
    if nom not in _ENTAMES:
        racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            from entames import charger
            _ENTAMES[nom] = charger(os.path.join(racine, "systems", nom, "entames.yaml"))
        except Exception as ex:
            print(f"(entames {nom} non lues : {ex} ; le programme utilise son code)", file=sys.stderr)
            _ENTAMES[nom] = None
    return _ENTAMES[nom]


def entame_regle(main_fr, den, singleton=True, partenaire=(), adverses=(), palier=None, declarant=(), mort=()):
    """(carte, raison) : les règles de systems/sef-2024/entames.yaml, sinon entame_code.
    partenaire, adverses : couleurs nommées naturellement par le partenaire et par les adversaires ;
    palier : du contrat ; declarant, mort : couleurs nommées par chacun des deux adversaires."""
    r = regles_entame()
    if r: return r.entame(main_fr, den, singleton, partenaire, adverses, palier, declarant, mort)
    return entame_code(main_fr, den, singleton, partenaire, adverses, palier)


def entame_code(main_fr, den, singleton=True, partenaire=(), adverses=(), palier=None):
    """Le même choix écrit en Python (si entames.yaml ne peut pas être lu)."""
    s = suites(main_fr)
    possibles = [c for c in COULEURS if s[c] and c != den] or [c for c in COULEURS if s[c]]
    # 1. couleur du partenaire
    for c in partenaire:
        if c in possibles:
            return c + carte_partenaire(s[c], den), "dans la couleur du partenaire"
    hors = lambda cs: [c for c in cs if c not in adverses] or cs   # hors couleurs adverses si possible
    if den != "SA":
        # 2. séquence d'honneurs (AR compris), même dans une couleur adverse
        seqs = hors([c for c in possibles if tete_de_sequence(s[c])])
        if seqs:
            c = max(seqs, key=lambda c: -HON.index(tete_de_sequence(s[c])))
            t = tete_de_sequence(s[c])
            if s[c][0] == "A": t = "A"
            return c + t, "tête de séquence"
        # 3. as en tête au palier de 5 ou plus, sauf 4e meilleure possible sous un R ou une D
        aces = hors([c for c in possibles if s[c][0] == "A" and len(s[c]) > 1]) if (palier or 0) >= 5 else []
        sous_honneur = [c for c in hors(possibles) if len(s[c]) >= 4 and s[c][0] in "RD"]
        if aces and not sous_honneur:
            c = max(aces, key=lambda c: len(s[c])); return c + "A", "on n'entame pas sous l'as"
        # 4. singleton, pour couper (avec au moins deux atouts)
        sing = [c for c in hors(possibles) if len(s[c]) == 1 and s[c] not in "ARDV"]
        if singleton and sing and len(s.get(den, "")) >= 2:
            return sing[0] + s[sing[0]], "singleton, pour couper"
    # 5. la plus longue couleur (3 cartes au moins à la couleur, 4 à sans-atout) hors couleurs adverses
    mini = 4 if den == "SA" else 3
    cand = [c for c in possibles if c not in adverses and len(s[c]) >= mini] or possibles
    if den != "SA": cand = [c for c in cand if s[c][0] != "A"] or cand   # pas sous l'as
    c = max(cand, key=lambda c: (len(s[c]), den == "SA" and bool(tete_de_sequence(s[c][:3])),
                                 sum(len(HON) - HON.index(x) for x in s[c] if x in HON)))
    x, raison = carte_dans(s[c])
    return c + x, raison


def carte_partenaire(p, den):
    """Carte dans la couleur du partenaire : as en tête à la couleur, plus haute du doubleton,
    tête de séquence, petite sous un honneur (le 10 compte avec 4 cartes), la plus haute de trois petites."""
    if p[0] == "A" and den != "SA": return "A"
    if len(p) <= 2: return p[0]
    t = tete_de_sequence(p)
    if t: return t
    if any(x in ("ARDV" if len(p) == 3 else "ARDVX") for x in p): return p[-1] if len(p) == 3 else p[3]
    return p[0] if len(p) == 3 else p[1]


def tete_de_sequence(p):
    for i in range(len(p) - 1):
        if p[i] in HON and p[i + 1] in HON and HON.index(p[i + 1]) == HON.index(p[i]) + 1:
            return p[i]
    return None


def carte_dans(p):
    """(carte, raison) dans une couleur p (cartes de la plus haute à la plus basse)."""
    t = tete_de_sequence(p)
    if t: return t, "tête de séquence"
    if len(p) <= 2: return p[0], "la plus haute du doubleton" if len(p) == 2 else "singleton"
    if any(x in ("ARDV" if len(p) == 3 else "ARDVX") for x in p):
        return (p[3] if len(p) >= 4 else p[-1]), "4e meilleure sous un honneur"
    if len(p) == 3: return p[0], "la plus haute de trois petites"
    return p[1], "deuxième carte, sans honneur"




# ---------------------------------------------------------------- double mort par entame
# systems/sef-2024/entames.md, « Défense »
def _pbn(mains):
    en = str.maketrans({"R": "K", "D": "Q", "V": "J", "X": "T"})
    return "N:" + " ".join(".".join(suites(mains[s])[c].translate(en) for c in COULEURS) for s in "NESO")


def _donne_dds(mains, den, decl):
    from endplay.types import Deal, Denom, Player
    d = Deal(_pbn(mains))
    d.trump = {"♠": Denom.spades, "♥": Denom.hearts, "♦": Denom.diamonds, "♣": Denom.clubs, "SA": Denom.nt}[den]
    d.first = {"N": Player.north, "E": Player.east, "S": Player.south, "O": Player.west}[LHO[decl]]
    return d


def _en_francais(resolu, main_meneur):
    """Résultat DDS -> {carte française: levées de la défense}, toutes les cartes de la main."""
    fr = str.maketrans({"K": "R", "Q": "D", "J": "V", "T": "X"})
    out = {str(c).translate(fr): t for c, t in resolu}
    # solve_board ne donne qu'une carte par groupe équivalent : compléter avec les cartes voisines
    main = suites(main_meneur)
    for c in COULEURS:
        p = main[c]
        for i, x in enumerate(p):
            if c + x in out: continue
            voisins = [c + y for y in p if c + y in out]
            plus_proche = min(voisins, key=lambda v: abs(p.index(v[1:]) - i)) if voisins else None
            if plus_proche: out[c + x] = out[plus_proche]
    return out


def levees_par_entame(mains, den, decl):
    """{carte française: levées de la défense} pour chaque entame possible, ou None sans endplay."""
    try:
        from endplay.dds import solve_board
    except ImportError:
        return None
    return _en_francais(solve_board(_donne_dds(mains, den, decl)), mains[LHO[decl]])


def lister(cartes):
    """['♣R', '♣D', '♠3'] -> '♣R ou ♣D, ♠3'"""
    par = {}
    for c in cartes: par.setdefault(c[0], []).append(c)
    return ", ".join(" ou ".join(v) for v in par.values())


# ---------------------------------------------------------------- lecture des enchères
# systems/sef-2024/entames.md, « Lecture des enchères pour le meneur »
MAJ = ("♥", "♠")


def lire_encheres(encheres, donneur):
    """Ce que montre chaque joueur, d'après une lecture simple du SEF :
    {siège: {"pts": [min, max], "L": {couleur: min}, "reg": bool}}. Lecture volontairement large
    (systems/sef-2024/entames.md, « Lecture des enchères pour la simulation »)."""
    c = {x: {"pts": [0, 37], "L": {k: 0 for k in COULEURS}, "reg": False} for x in ROT}
    def montre(x, lo=None, hi=None, coul=None, n=0, reg=None):
        if lo is not None: c[x]["pts"][0] = max(c[x]["pts"][0], lo)
        if hi is not None: c[x]["pts"][1] = min(c[x]["pts"][1], hi)
        if coul: c[x]["L"][coul] = max(c[x]["L"][coul], n)
        if reg: c[x]["reg"] = True
    i0 = ROT.index(donneur); ouvreur = None
    dits = {x: [] for x in ROT}                            # enchères de chacun (artificielles suivies de *)
    passe_avant = set()                                   # a passé avant l'ouverture
    cible = {x: [] for x in ROT}                          # couleur montrée par un texas
    naturelles = lambda xs: [y[1:].rstrip("*") for y in xs if y[0].isdigit() and not y.endswith("*")]
    for k, b in enumerate(encheres or []):
        x = ROT[(i0 + k) % 4]; p = PART[x]
        adv = naturelles(dits[LHO[x]] + dits[RHO[x]])
        if b == "passe":
            if ouvreur is None: montre(x, hi=11); passe_avant.add(x)          # n'a pas ouvert
            elif ouvreur == p and dits[p] == [dits[p][0]] and dits[p][0][0] == "1" and not dits[x] \
                    and not any(dits[y] for y in (LHO[x], RHO[x])):
                montre(x, hi=5)                                         # passe sur 1x du partenaire
            continue
        if b in ("contre", "surcontre"):
            if ouvreur is not None and ouvreur not in (x, p) and not dits[x] and not dits[p]:
                reveil = encheres[k - 2:k] == ["passe", "passe"]
                montre(x, lo=8 if reveil or x in passe_avant else 11)   # contre d'appel (réveil : moins)
            dits[x].append(b + "*"); continue
        niv, d = int(b[0]), b[1:]
        art = False
        if ouvreur is None:                                             # ouverture
            ouvreur = x
            if b == "1SA": montre(x, 15, 17, reg=True)
            elif b == "2SA": montre(x, 20, 21, reg=True)
            elif niv == 1: montre(x, 11, 21, d, 5 if d in MAJ else 3)
            elif b == "2♣": montre(x, 16); art = True
            elif b == "2♦": montre(x, 20); art = True
            elif niv == 2: montre(x, 5, 11, d, 6)
            elif niv == 3 and d != "SA": montre(x, 5, 11, d, 7)
        elif d != "SA" and d in adv and niv <= 4:
            art = True                                                  # cue-bid de la couleur adverse
        elif ouvreur == p and not dits[x]:                              # réponse
            ouv = dits[p][0].rstrip("*") if dits[p] else ""
            bas = 6 if x in passe_avant else None
            if ouv in ("1SA", "2SA") and niv == int(ouv[0]) + 1 and d in ("♦", "♥"):
                montre(x, coul={"♦": "♥", "♥": "♠"}[d], n=5); art = True  # texas
                cible[x].append({"♦": "♥", "♥": "♠"}[d])
            elif ouv in ("1SA", "2SA") and niv == int(ouv[0]) + 1 and d == "♣":
                montre(x, 8 if ouv == "1SA" else 4); art = True         # Stayman
            elif ouv == "2♣" and b == "2♦": art = True                  # réponse d'attente
            elif ouv == "1SA" and d == "SA": montre(x, {2: 8, 3: 10}.get(niv, 15), {2: 9, 3: 15}.get(niv))
            elif ouv == "2SA" and d == "SA": montre(x, 4, 11)
            elif d == "SA": montre(x, {1: 6, 2: 11, 3: 13}.get(niv, 13), {1: 10, 2: 12, 3: 17}.get(niv))
            elif ouv[1:] == d: montre(x, 6, None, d, 3 if d in MAJ else 4)   # soutien
            else: montre(x, bas or (6 if niv == 1 else 10), None, d, 3 if (niv, d) == (2, "♣") else 4)
        elif ouvreur not in (x, p) and not [y for y in dits[x] if not y.endswith("*")] and not dits[p]:
            ouv = dits[ouvreur][0].rstrip("*") if dits[ouvreur] else ""
            if d == "SA": montre(x, 15, 18, reg=True)                   # intervention
            elif ouv == "1SA": montre(x, 8, 17, d, 6)
            elif niv >= 3: montre(x, 5, 16, d, 6)
            else: montre(x, 8, 17, d, 5)
        elif d != "SA" and niv <= 3:
            mien = naturelles(dits[x]) + cible[x]; sien = naturelles(dits[p]) + cible[p]
            dernier_p = dits[p][-1] if dits[p] else ""
            if dernier_p.endswith("*") and dernier_p[1:-1] in ("♦", "♥") and dits[p][-1][0] in "23" \
                    and d == {"♦": "♥", "♥": "♠"}[dernier_p[1:-1]] and x == ouvreur:
                art = True                                              # l'ouvreur accepte le texas
            elif dernier_p == "2♣*" and x == ouvreur and niv == 2:      # réponse au Stayman
                art = d == "♦"
                if not art: montre(x, coul=d, n=4)
            elif d in sien: montre(x, coul=d, n=2 if sien.count(d) > 1 else 3)   # soutien (2 si répétée)
            elif d in mien: montre(x, coul=d, n=5 if d in MAJ else 4)  # couleur répétée
            elif len(set(mien + sien + adv + [d])) == 4 and x != ouvreur:
                art = True                                              # 4e couleur forcing
            else: montre(x, coul=d, n=4)                                # nouvelle couleur
        dits[x].append(b + ("*" if art else ""))
    return c


PTS = {"A": 4, "R": 3, "D": 2, "V": 1}


class Simu(tuple):
    """(taux de chute, levées moyennes de la défense), avec les levées donne par donne."""
    def __new__(cls, taux, moy, levees, chute):
        t = super().__new__(cls, (taux, moy)); t.levees = levees; t.chute = chute; return t


def nettement_meilleure(a, b):
    """a bat-elle le contrat nettement plus souvent que b sur les mêmes donnes (test de McNemar,
    deux écarts-types) ? À taux égal, compare les levées moyennes (deux erreurs-types)."""
    gagne = sum(x >= a.chute and y < a.chute for x, y in zip(a.levees, b.levees))
    perd = sum(y >= a.chute and x < a.chute for x, y in zip(a.levees, b.levees))
    if gagne + perd and gagne - perd > 2 * math.sqrt(gagne + perd): return True
    if gagne != perd: return False
    ecarts = [x - y for x, y in zip(a.levees, b.levees)]
    m = sum(ecarts) / len(ecarts)
    var = sum((e - m) ** 2 for e in ecarts) / max(len(ecarts) - 1, 1)
    return m > 0 and m > 2 * math.sqrt(var / len(ecarts))


def raison_detaillee(raison, carte, main_fr):
    """Raison de l'entame avec la tenue, à la manière de l'analyse rédigée : « 4e meilleure de R843 »."""
    p = suites(main_fr)[carte[0]]
    return {"4e meilleure sous un honneur": f"4e meilleure de {p}" if len(p) >= 4 else f"la plus petite de {p}, sous un honneur",
            "tête de séquence": f"tête de séquence {p[:3] if len(p) >= 3 else p}" if p[:1] == carte[1:] else f"tête de la séquence intérieure de {p}",
            "dans la couleur du partenaire": f"dans la couleur de son partenaire ({p})",
            "on n'entame pas sous l'as": "à l'atout, on n'entame pas sous l'as",
            "deuxième carte, sans honneur": f"deuxième carte de {p}, sans honneur",
            "la plus haute de trois petites": f"la plus haute de {p}",
            "la plus haute du doubleton": f"la plus haute du doubleton {p}"}.get(raison, raison)


def bilan(t, need):
    """« contrat juste fait », « une levée de mieux », « une de chute »."""
    if t == need: return "contrat juste fait"
    if t > need: return f"{t - need} levée{'s' if t - need > 1 else ''} de mieux"
    return f"{need - t} de chute"


def entame_et_defense(d, contrat, decl, encheres=None):
    """Entame recommandée et commentaire de défense pour le contrat joué par decl
    (systems/sef-2024/entames.md). encheres : séquence depuis le donneur. Le meneur ne voit que sa
    main et les enchères : l'entame vient des règles seules, jamais d'un double mort."""
    den = contrat[1:].rstrip("X")
    meneur = LHO[decl]; main = d["mains"][meneur]
    nommees = couleurs_nommees(encheres, d["donneur"])
    regle, raison = entame_regle(main, den, partenaire=nommees[PART[meneur]],
                                 adverses=nommees[decl] + nommees[PART[decl]], palier=int(contrat[0]),
                                 declarant=nommees[decl], mort=nommees[PART[decl]])
    lecture = lecture_entame(d, contrat, decl, encheres, nommees, regle[0]) if encheres else ""
    raison = raison_detaillee(raison, regle, main)
    if regle[0] in nommees[meneur]:                        # sa propre couleur, soutenue par le partenaire
        raison = raison.replace("dans la couleur de son partenaire", "dans sa couleur, soutenue par son partenaire")
    return {"entame": {"joueur": meneur, "carte": regle},
            "defense": " ".join(x for x in (f"{meneur} entame {regle}, {raison}.", lecture) if x),
            "pourquoi": f"{meneur} entame {regle}, {raison}."}   # la seule raison de l'entame : le coach dit la suite


def lecture_entame(d, contrat, decl, encheres, nommees, entamee=None):
    """Ce que le meneur tire de sa main et des enchères : les points du partenaire et le style de
    défense (systems/sef-2024/entames.md, « Lecture pour le meneur »)."""
    den = contrat[1:].rstrip("X"); palier = int(contrat[0])
    meneur = LHO[decl]; part = PART[meneur]; mort = PART[decl]
    cx = lire_encheres(encheres, d["donneur"])
    nous = sum(PTS.get(x, 0) for x in d["mains"][meneur] if x in PTS)
    ld, hd = cx[decl]["pts"]; lm, hm = cx[mort]["pts"]
    haut = min(40 - nous - ld - lm, cx[part]["pts"][1])
    bas = max(cx[part]["pts"][0], 40 - nous - hd - hm, 0)
    phr = []
    if bas > haut: bas = haut
    if haut <= 20:
        phr.append(f"Le partenaire a {'environ ' + str(haut) if bas == haut else f'de {bas} à {haut}'} H." if bas else f"Le partenaire a au plus {haut} H.")
    moi = suites(d["mains"][meneur])
    annexes = list(dict.fromkeys(c for c in nommees[mort] + nommees[decl] if c not in (den, entamee)))
    if len(annexes) >= 3: annexes = []                     # toutes les couleurs nommées : le conseil ne dirait rien
    if palier >= 6:
        phr.append("Contre un chelem, il faut deux levées vite : la défense doit être active.")
    elif den != "SA" and len(moi[den]) >= 4:               # le déclarant n'a pas tant d'atouts d'avance
        phr.append(f"Avec {len(moi[den])} atouts, forcer le déclarant à couper : il peut perdre le contrôle.")
    elif den != "SA" and entamee and len(moi[entamee]) <= 2:
        phr.append("Une entame courte cherche une coupe : compter les rentrées du partenaire.")
    elif den == "SA":
        phr.append("À sans-atout, la défense cherche à affranchir une longueur : ne pas la lâcher." if not annexes
                   else f"À sans-atout, éviter d'ouvrir {lister_noms(annexes)}, et affranchir une longueur.")
    elif [c for c in nommees[mort] if c != den and len(moi[c]) <= 3]:   # avec quatre cartes, le meneur tient la couleur
        c = next(c for c in nommees[mort] if c != den and len(moi[c]) <= 3)
        phr.append(f"Le mort a montré les {NOM_COULEUR[c]} : ses défausses menacent, la défense doit prendre ses levées vite.")
    elif den in nommees[mort] and len(nommees[decl]) >= 2:
        phr.append("Le déclarant a deux couleurs et le mort soutient : il voudra couper ; rejouer atout dès que possible.")
    else:
        phr.append("Rien à affranchir chez eux : ne rien offrir, la défense peut attendre ses levées.")
    return " ".join(phr)


NOM_COULEUR = {"♠": "piques", "♥": "cœurs", "♦": "carreaux", "♣": "trèfles"}


def lister_noms(cs):
    v = list(dict.fromkeys(NOM_COULEUR[c] for c in cs))
    return "les " + (" ni les ".join(v))


def apres_coup(d, contrat, decl, entame):
    """Ce que le contrat recommandé donne sur la donne réelle, pour le commentaire seulement :
    double mort après l'entame, autres entames, entames des tables, impasses."""
    den = contrat[1:].rstrip("X"); need = int(contrat[0]) + 6; chute = 14 - need
    lev = levees_par_entame(d["mains"], den, decl)
    if not lev: return ""
    reco = entame["carte"]; v_reco = lev.get(reco, max(lev.values())); t = 13 - v_reco
    phr = [f"<b>Le contrat recommandé, {contrat} par {decl}</b>, au double mort après l'entame {reco} : "
           f"{t} levées ({bilan(t, need)})."]
    pires = sorted({v for v in lev.values() if v < v_reco}, reverse=True)
    if pires:
        gros = max(pires, key=lambda v: sum(x == v for x in lev.values()))
        for v in pires:
            cartes = sorted((c for c, x in lev.items() if x == v), key=ordre_carte)
            k = 13 - v
            fin = f"une {k}e levée" if k == t + 1 else f"{k} levées"
            if len(cartes) <= 6:
                phr.append(f"{lister(cartes)} donne{'nt' if len(cartes) > 1 else ''} {fin}.")
            elif v == gros:
                phr.append(f"Les autres entames donnent {fin}.")
    mieux = sorted((c for c, x in lev.items() if x > v_reco), key=ordre_carte)
    if mieux and len(mieux) <= 6:
        k = 13 - max(lev[c] for c in mieux)
        phr.append(f"Avec les cartes vues, {lister(mieux)} aurai{'en' if len(mieux) > 1 else ''}t fait mieux "
                   f"({k} levées au déclarant).")
    battent = [c for c, x in lev.items() if x >= chute]
    if battent and reco in battent and len(battent) <= 4:
        phr.append(f"Seule l'entame {battent[0]} bat le contrat." if len(battent) == 1 else
                   f"Seules les entames {lister(sorted(battent, key=ordre_carte))} battent le contrat.")
    jouees = {}
    for tb in d.get("tables", []):
        if tb.get("contrat", "").rstrip("X") == contrat.rstrip("X") and tb.get("declarant") == decl and tb.get("entame"):
            jouees[tb["entame"]] = jouees.get(tb["entame"], 0) + 1
    for c, k in jouees.items():
        if c != reco and c in lev and lev[c] < v_reco:
            phr.append(f"Après l'entame {c}, choisie à {k} table{'s' if k > 1 else ''}, "
                       f"le double mort donne {13 - lev[c]} levées au déclarant.")
    s_dec, s_mort = suites(d["mains"][decl]), suites(d["mains"][PART[decl]])
    for c in COULEURS:
        for _, h, avant in impasses((decl, s_dec), (PART[decl], s_mort), c):
            places = [x for x in h if x in suites(d["mains"][avant])[c]]
            phr.append(f"L'impasse à {c}{h[0]} {'réussit' if places else 'échoue'}.")
        phr += en_tete_reel(d["mains"], decl, c, s_dec[c], s_mort[c])
    return " ".join(phr)


def en_tete_reel(mains, decl, c, a, b):
    """Couleur à tirer en tête : si l'honneur reste, qui l'a et si l'impasse aurait réussi."""
    if not en_tete(a, b, c): return []
    h = next(x for x in "DV" if x not in a + b)
    qui = next(x for x in (LHO[decl], RHO[decl]) if h in suites(mains[x])[c])
    p = suites(mains[qui])[c]
    if len(p) <= 2: return [f"{ART[h].capitalize()}{c}{h} tombe en tête ({qui} l'a {'sec' if len(p) == 1 else 'seconde' if h == 'D' else 'second'})."]
    i = ORDRE.index(h); haut, bas = ORDRE[i - 1], ORDRE[i + 1]
    fourchette = decl if haut in a and bas in a else PART[decl]
    bon = qui == RHO[fourchette]
    return [f"{ART[h].capitalize()}{c}{h} ne tombe pas : {qui} a {p} ; l'impasse aurait {'réussi' if bon else 'échoué aussi'}."]


def ordre_carte(c): return (COULEURS.index(c[0]), ORDRE.index(c[1:]))


# ---------------------------------------------------------------- plan de jeu
# systems/technique/jeu-de-la-carte.md : le déclarant ne voit que sa main, le mort, l'entame
# et les enchères ; aucune de ces fonctions ne reçoit les mains adverses
NOM_C = {"♠": "piques", "♥": "cœurs", "♦": "carreaux", "♣": "trèfles"}
NOMBRE = {1: "un", 2: "deux", 3: "trois", 4: "quatre", 5: "cinq", 6: "six"}
ART = {"A": "l'", "R": "le ", "D": "la ", "V": "le ", "X": "le "}


def impasses(dec, mort, c):
    """Impasses classiques dans la couleur c : [(texte, honneurs manquants, siège qui doit les avoir)].
    Fourchette (haut et bas dans une main) : on joue de l'autre main vers elle ; l'impasse
    réussit si l'honneur manquant est dans la main qui joue avant la fourchette.
    Double impasse : A et V dans une main, R et D dehors."""
    out = []
    mains = {"dec": dec, "mort": mort}
    nous = dec[1][c] + mort[1][c]; n = len(nous)
    perd = tours_adverses(dec[1][c], mort[1][c], max(len(dec[1][c]), len(mort[1][c])))
    for nom, (siege, p) in mains.items():                 # double impasse AV(9) contre RD
        autre = mort if nom == "dec" else dec
        if "A" in p[c] and "V" in p[c] and not any(h in nous for h in "RD") and autre[1][c]:
            if "X" in nous and len(autre[1][c]) >= 2:      # sans le dix, un honneur de chaque côté ne donne rien
                return [(f"{c} : double impasse, jouer de {autre[0]} vers {p[c]} en {siege} : elle réussit si "
                         f"{RHO[siege]}, qui joue avant {siege}, a le {c}R ou la {c}D", "RD", RHO[siege])]
            return [(f"{c} : jouer de {autre[0]} vers {p[c]} en {siege} : l'impasse réussit si "
                     f"{RHO[siege]}, qui joue avant {siege}, a le {c}R et la {c}D", "RD", RHO[siege])]
    for h in "RDV":                                       # honneur adverse manquant
        if out: break                                     # la plus grosse impasse de la couleur suffit à dire
        if h in nous or h not in perd: continue
        if h != "R" and n >= 9: continue                  # 9 cartes : on tire en tête
        i = ORDRE.index(h); haut, bas = ORDRE[i - 1], ORDRE[i + 1]
        for nom, (siege, p) in mains.items():
            if haut in p[c] and bas in p[c]:              # fourchette : haut et bas dans la même main
                autre = mort if nom == "dec" else dec
                if not autre[1][c] or ORDRE.index(autre[1][c][-1]) < ORDRE.index(bas): break   # rien de petit pour jouer vers elle
                out.append((f"{c} : jouer de {autre[0]} vers {p[c]} en {siege} : l'impasse réussit si "
                            f"{RHO[siege]}, qui joue avant {siege}, a {ART[h]}{c}{h}" + (f" et l'{c}A" if h == "D" and "A" not in nous else ""),
                            h, RHO[siege]))
                break
    return out


def en_tete(a, b, c):
    """9 cartes ou plus sans la D ou le V : le texte « tirer en tête », ou None."""
    n = len(a + b)
    if n < 9: return None
    for h in "DV":
        i = ORDRE.index(h); haut, bas = ORDRE[i - 1], ORDRE[i + 1]
        if h in a + b or any(x not in a + b for x in ORDRE[:i]): continue   # il faut tout ce qui est au-dessus
        if (haut in a and bas in a) or (haut in b and bas in b):
            return f"{c} : {n} cartes sans {ART[h]}{c}{h} : tirer en tête pour {'la' if h == 'D' else 'le'} faire tomber, sans impasse"
    return None


def tours_adverses(a, b, r, partage=None):
    """Cartes adverses qui font une levée en r tours quand la couleur se partage normalement :
    les cartes qui manquent, distribuées en alternance aux deux adversaires. Chaque tour, nous
    gagnons avec notre plus petite carte maîtresse (l'autre main fournit sa plus petite) ; sans
    carte maîtresse, c'est l'adversaire. Ne dépend que de nos cartes. partage : une autre distribution."""
    nous = [list(a), list(b)]
    dehors = [x for x in ORDRE if x not in a + b]
    adv = partage(dehors) if partage else [dehors[0::2], dehors[1::2]]
    out = []
    for _ in range(r):
        hauts = [p[0] for p in adv if p]
        if not hauts or not (nous[0] or nous[1]): break
        haut = min(hauts, key=ORDRE.index)
        maitres = [(i, x) for i, p in enumerate(nous) for x in p if ORDRE.index(x) < ORDRE.index(haut)]
        if maitres:
            i, x = max(maitres, key=lambda v: ORDRE.index(v[1]))
            nous[i].remove(x)
            if nous[1 - i]: nous[1 - i].pop()
            for p in adv:
                if p: p.pop()
        else:                                              # nous jouons le bas de notre séquence de tête, la défense prend au plus juste
            tous = sorted(nous[0] + nous[1], key=ORDRE.index)
            k = 0
            while k + 1 < len(tous) and ORDRE.index(tous[k + 1]) == ORDRE.index(tous[k]) + 1: k += 1
            prise = max((x for p in adv for x in p if ORDRE.index(x) < ORDRE.index(tous[k])), key=ORDRE.index)
            i = 0 if tous[k] in nous[0] else 1
            nous[i].remove(tous[k])
            if nous[1 - i]: nous[1 - i].pop()
            for p in adv:
                if p: p.remove(prise) if prise in p else p.pop()
            out.append(prise)
    return out


def sures(a, b):
    """Levées d'honneurs de tête : nos cartes qui se suivent depuis l'as, dans la limite des tours."""
    k = 0
    for x in ORDRE:
        if x not in a + b: break
        k += 1
    return min(k, max(len(a), len(b)))


def nommer_perdantes(perd, den):
    """{♠: 1, ♦: 2} -> « le ♠R et deux carreaux » (atout : « un atout »)."""
    morceaux = []
    for c, (k, cartes) in perd.items():
        if not k: continue
        if c == den and k > 1: morceaux.append(f"{NOMBRE.get(k, k)} atouts")
        elif k == 1 and cartes and cartes[0] in "ARDV": morceaux.append(f"{ART[cartes[0]]}{c}{cartes[0]}")
        else: morceaux.append(f"{NOMBRE.get(k, k)} {NOM_C[c] if k > 1 else NOM_C[c][:-1]}")
    return ", ".join(morceaux[:-1]) + (" et " if len(morceaux) > 1 else "") + morceaux[-1] if morceaux else "aucune"


def lister_levees(par_couleur):
    """{♠: 2, ♦: 1} -> « deux piques et un carreau »."""
    m = [f"{NOMBRE.get(n, n)} {NOM_C[c] if n > 1 else NOM_C[c][:-1]}" for c, n in par_couleur.items() if n]
    return ", ".join(m[:-1]) + (" et " if len(m) > 1 else "") + (m[-1] if m else "aucune")


def partage_normal(m):
    """Le partage qu'on espère pour m cartes adverses."""
    if m == 4: return "2-2 ou 3-1"
    return f"{(m + 1) // 2}-{m // 2}"


def placer(h, c, avant, decl, cx, restant, entame):
    """Ce que l'entame et les enchères disent de l'honneur h : texte, ou "" si elles ne disent rien."""
    g, dr = LHO[decl], RHO[decl]
    if entame and entame["carte"] == c + h:
        return f" ({g} l'a entamé)" if avant == g else f" ({g} l'a entamé : l'impasse est inutile)"
    if not cx: return ""
    v = PTS[h]
    for x, y in ((g, dr), (dr, g)):
        lo = cx[x]["pts"][0]
        if restant - lo < v:                               # l'autre n'a pas la place de l'honneur
            return f" ({x} a montré {lo} H sur les {restant} qui manquent : {'favorable' if x == avant else 'elle échoue'})"
        if lo >= 8 and cx[y]["pts"][0] < 6:
            return f" ({x} a montré {lo} H ou plus : {'favorable' if x == avant else 'défavorable'})"
    return ""


def menaces(s_dec, s_mort, decl, mort, den):
    """Cartes qui deviennent maîtresses si un adversaire lâche sa garde : notre plus haute carte
    non maîtresse, sous un seul honneur adverse, dans une couleur où cet honneur fait une levée."""
    out = []
    for c in COULEURS:
        a, b = s_dec[c], s_mort[c]; nous = a + b
        dehors = [x for x in ORDRE if x not in nous]
        if c == den or not nous or not dehors: continue
        h = dehors[0]
        sous = [x for x in ORDRE[ORDRE.index(h) + 1:] if x in nous]
        perd = tours_adverses(a, b, max(len(a), len(b)))
        if not sous or not perd: continue
        x = sous[0]; entree = any(ORDRE.index(y) < ORDRE.index(h) for y in nous)
        if h in perd and not (dehors[1:] and ORDRE.index(dehors[1]) < ORDRE.index(x)):
            out.append({"c": c, "carte": x, "honneur": h, "main": decl if x in a else mort, "entree": entree})
        elif len(perd) == 1 and max(len(a), len(b)) >= 4:  # la dernière carte d'une couleur longue
            p, qui = (a, decl) if len(a) >= len(b) else (b, mort)
            out.append({"c": c, "carte": p[-1], "honneur": perd[0], "main": qui, "entree": entree})
    return sorted(out, key=lambda m: (not m["entree"], ORDRE.index(m["carte"])))


def adversaire_fort(decl, cx):
    """L'adversaire que les enchères désignent pour garder les honneurs, ou None."""
    if not cx: return None
    g, dr = LHO[decl], RHO[decl]
    for x, y in ((g, dr), (dr, g)):
        if cx[x]["pts"][0] >= 8 and cx[y]["pts"][0] < 6: return x
    return None


def phrase_squeeze(d, contrat, decl, entame, encheres, reste, simuler=True):
    """À la table : il manque une levée, deux menaces et une rentrée, et rien dans les enchères
    n'interdit qu'un adversaire garde les deux couleurs (systems/technique/jeu-de-la-carte.md,
    « Préparer un squeeze »). Avec simuler, la fréquence sur des donnes tirées au hasard ; on se
    tait si elle est négligeable."""
    if reste != 1: return ""
    den = contrat[1:].rstrip("X"); need = int(contrat[0]) + 6; mort = PART[decl]
    s_dec, s_mort = suites(d["mains"][decl]), suites(d["mains"][mort])
    m = menaces(s_dec, s_mort, decl, mort, den)
    if len(m) < 2 or not m[0]["entree"]: return ""
    m = m[:2]
    cx = lire_encheres(encheres, d["donneur"]) if encheres else None
    qui = adversaire_fort(decl, cx)
    if m[0]["main"] == m[1]["main"]:                       # même main : il faut défausser avant elle
        avant = RHO[m[0]["main"]]
        if qui and qui != avant: return ""
        qui = avant
    txt = " et ".join(f"{ART[x['carte']] if x['carte'] in ART else 'le '}{x['c']}{x['carte']} en {x['main']} "
                      f"(contre {ART[x['honneur']] if x['honneur'] in ART else 'le '}{x['c']}{x['honneur']})" for x in m)
    garde = f"si {qui} garde les deux" if qui else "si le même adversaire garde les deux"
    n = 13 - need
    prep = f"Céder d'abord {'une levée' if n == 1 else f'{NOMBRE.get(n, n)} levées'} pour ne plus en perdre qu'une, " if n else ""
    fin = "puis tirer les gagnantes" if n else "Tirer les gagnantes"
    out = f"Squeeze possible : il manque une levée. Menaces : {txt}, {garde}. {prep}{fin} en gardant ces cartes et la rentrée à {m[0]['c']}."
    if simuler:
        import coups
        p = coups.chance_squeeze(d, contrat, decl, entame, encheres)
        if p is not None:
            if p < 0.05: return ""
            out += f" Sur des donnes tirées au hasard, fidèles aux enchères et à l'entame, le squeeze joue environ {5 * round(p * 20)} % du temps."
    return out


def deux_sens(a, b):
    """Fourchette dans les deux mains (AV2 face à RX3) : la dame se devine, l'honneur manquant
    tombe si la défense ouvre la couleur."""
    dehors = [x for x in ORDRE if x not in a + b]
    if not dehors or dehors[0] in "AR": return False
    i = ORDRE.index(dehors[0]); haut, bas = ORDRE[i + 1], ORDRE[i + 2] if i + 2 < 13 else ""
    if not (bas and haut in a + b and bas in a + b): return False
    return (haut in a) != (bas in a) and any(ORDRE.index(x) < i for x in a) and any(ORDRE.index(x) < i for x in b)


def trou(a, b):
    """Deux de nos honneurs avec un honneur adverse entre eux (AX2 face à V86, RV face à 76) :
    la défense perd une levée si c'est elle qui ouvre la couleur."""
    h = [x for x in ORDRE[:5] if x in a + b]
    return len(h) >= 2 and ORDRE.index(h[-1]) - ORDRE.index(h[0]) >= len(h)


def cadre_elimination(s_dec, s_mort, decl, mort, den, entame=None):
    """Ce qu'il faut pour une élimination, d'après nos deux mains : la couleur clé, que la défense
    doit ouvrir pour nous ; les couleurs à éliminer (gagnantes, puis coupes) ; les couleurs où
    rendre la main ; au moins un atout gardé. None si la donne ne s'y prête pas."""
    if den == "SA": return None
    tours = (13 - len(s_dec[den] + s_mort[den]) + 1) // 2
    cotes = [c for c in COULEURS if c != den]
    perd = {c: tours_adverses(s_dec[c], s_mort[c], max(len(s_dec[c]), len(s_mort[c]))) for c in COULEURS}
    imp = {c: impasses((decl, s_dec), (mort, s_mort), c) for c in cotes}
    entamee = entame[0] if entame else None
    def rang(c):
        return 0 if imp[c] else 1 if deux_sens(s_dec[c], s_mort[c]) else 2
    cles = [c for c in cotes if c != entamee and perd[c] and s_dec[c] + s_mort[c]
            and (imp[c] or deux_sens(s_dec[c], s_mort[c]) or trou(s_dec[c], s_mort[c]))]
    for cle in sorted(cles, key=rang):
        if imp[cle]: vers = PART[LHO[imp[cle][0][2]]]      # on joue de cette main vers la fourchette
        elif deux_sens(s_dec[cle], s_mort[cle]): vers = decl
        else: vers = mort if ORDRE.index(s_dec[cle][0] if s_dec[cle] else "2") < ORDRE.index(s_mort[cle][0] if s_mort[cle] else "2") else decl
        coupes = {decl: 0, mort: 0}; eliminer, sorties = [], []
        for c in cotes:
            a, b = s_dec[c], s_mort[c]
            if c == cle or not a + b: continue
            # l'entame a joué pour nous dans une fourchette : plus de perdante à l'intérieur
            ouverte = c == entamee and imp[c] and len(tours_adverses(a, b, min(len(a), len(b)))) <= 1
            if ouverte or not tours_adverses(a, b, min(len(a), len(b))):
                eliminer.append(c)
                if len(a) != len(b): coupes[decl if len(a) < len(b) else mort] += abs(len(a) - len(b))
            else:
                sorties.append(c)
        if not sorties and perd[den]: sorties.append(den)
        if len(eliminer) + len(sorties) < 2 and not (eliminer and cle in perd and len(perd[cle]) > 1): continue
        ici, la = len(s_dec[den]) - tours - coupes[decl], len(s_mort[den]) - tours - coupes[mort]
        if min(ici, la) >= 0 and ici + la >= 1:            # un atout suffit pour la coupe et défausse
            return {"cle": cle, "vers": vers, "sorties": sorties, "eliminer": eliminer}
    return None


def phrase_elimination(d, contrat, decl, entame, encheres, reste):
    """À la table : il manque une ou deux levées, nos deux mains se prêtent à une élimination, et,
    sur des donnes imaginées, la ligne jouée bat nettement la même sans élimination (systems/
    technique/jeu-de-la-carte.md, « Préparer une élimination »). Sinon le plan n'en parle pas."""
    if reste not in (1, 2) or not entame: return ""
    den = contrat[1:].rstrip("X"); mort = PART[decl]
    s_dec, s_mort = suites(d["mains"][decl]), suites(d["mains"][mort])
    cad = cadre_elimination(s_dec, s_mort, decl, mort, den, entame)
    if not cad: return ""
    import coups
    a, b = coups.chance_elimination(d, contrat, decl, entame, encheres, cad)
    if a is None or a[0] <= b[0] or not nettement_meilleure(a, b): return ""
    cle = cad["cle"]; sorties = [c for c in cad["sorties"] if c != cle]
    fin = f"{cle}{s_dec[cle] or '–'} face à {cle}{s_mort[cle] or '–'}"
    el = " et ".join(NOM_C[c] for c in cad["eliminer"])
    ph = [f"Élimination possible : {fin} donne une levée de plus si la défense doit ouvrir la couleur. "
          f"Purger les atouts en gardant de quoi couper"]
    if el: ph.append(f"éliminer les {el} (les gagnantes, puis couper le reste)")
    rendre = " puis ".join("avec le dernier atout" if c == den else f"à {c}" for c in sorties) or f"à {cle}"
    tx = ", ".join(ph) + f", puis rendre la main {rendre} : l'adversaire en main doit jouer {cle} ou donner une coupe et défausse."
    return tx + f" Sur des donnes imaginées, face à la meilleure défense, le contrat gagne {5 * round(a[0] * 20)} % du temps, contre {5 * round(b[0] * 20)} % sans élimination."


def donnes_du_declarant(d, decl, encheres, entame, n, essais=30000):
    """n donnes : le déclarant et le mort tels quels, le reste au hasard, fidèle aux enchères et
    à l'entame. Ce que le déclarant peut imaginer : jamais les mains adverses réelles."""
    import random
    rnd = random.Random(d.get("n"))
    mort = PART[decl]; g, dr = LHO[decl], RHO[decl]
    cx = lire_encheres(encheres, d["donneur"])
    vues = {c: suites(d["mains"][decl])[c] + suites(d["mains"][mort])[c] for c in COULEURS}
    e = (COULEURS.index(entame[0]), entame[1:])
    reste = [(COULEURS.index(k), x) for k in COULEURS for x in ORDRE if x not in vues[k] and (COULEURS.index(k), x) != e]
    out = []
    for marge, moins_L in ((1, 0), (3, 1)):
        out = []
        for _ in range(essais):
            rnd.shuffle(reste)
            lots = {g: reste[:12] + [e], dr: reste[12:]}
            ok = True
            for x, cartes in lots.items():
                L = [0, 0, 0, 0]; h = 0
                for k, r in cartes:
                    L[k] += 1; h += PTS.get(r, 0)
                lo, hi = cx[x]["pts"]
                if not lo - marge <= h <= hi + marge: ok = False; break
                if any(L[COULEURS.index(k)] < v - moins_L for k, v in cx[x]["L"].items()): ok = False; break
                if cx[x]["reg"] and (min(L) < 2 or L.count(2) > 1): ok = False; break
            if not ok: continue
            m = {decl: d["mains"][decl], mort: d["mains"][mort]}
            for x, cartes in lots.items():
                m[x] = " ".join("".join(sorted((r for kk, r in cartes if kk == k), key=ORDRE.index)) or "-" for k in range(4))
            out.append(m)
            if len(out) >= n: return out
        if len(out) >= n // 4: return out
    return out


VERS_FR = str.maketrans({"K": "R", "Q": "D", "J": "V", "T": "X"})
PURGE_DABORD = "purger les atouts (il en restera assez pour couper), puis faire les coupes"
COUPES_DABORD = "faire d'abord les coupes, puis purger les atouts"
ATOUT_PUIS = "tirer un ou deux tours d'atout, puis faire les coupes en gardant de quoi couper"


def plan_de_jeu(d, contrat, decl, entame=None, encheres=None, simuler=False, verdict=True, parties=False):
    """Plan de jeu du déclarant (systems/technique/jeu-de-la-carte.md), à la table : il part de
    sa main, du mort, de l'entame et des enchères, jamais des mains adverses. Le compte, puis les
    étapes numérotées dans l'ordre de jeu. verdict=False : sans la dernière phrase (l'expert la
    remplace par son avis). parties=True : les morceaux, pour que le coach les rédige (coach.redaction_plan) :
    {"compte", "etapes" (dans l'ordre de jeu), "essai" (lignes.analyser ou None), "fin"}."""
    essai = ""; a = None
    if simuler and entame:                                 # l'ordre et les choix : ceux du déclarant simulé
        import lignes
        a = lignes.analyser(d, contrat, decl, entame, encheres)
    infos = {}
    compte, etapes, fin, reste = compter_plan(d, contrat, decl, entame, encheres, a, infos)
    if a:
        vus = [x[0] for x in a["ligne"]]                   # d'abord l'ordre le plus joué, puis le rang moyen
        def rang(e):
            if not e[0]: return 99
            L = "SHDC"[COULEURS.index(e[0])]
            return vus.index(L) if L in vus else 20 + a["rang"].get(e[0], 60)
        etapes.sort(key=rang)
        i = next((k for k, e in enumerate(etapes) if e[1].startswith("<b>Atout")), None)   # les deux étapes disent le même ordre
        j = next((k for k, e in enumerate(etapes) if e[1].startswith("<b>Coupes")), None)
        if i is not None and j is not None and (j < i) != (COUPES_DABORD in etapes[i][1]): etapes[i], etapes[j] = etapes[j], etapes[i]
        essai = lignes.phrase(a)
    etapes = [x for _, x in etapes]
    s = phrase_squeeze(d, contrat, decl, entame and entame["carte"], encheres, reste, simuler) if entame else ""
    if s: etapes.append(s)
    if simuler and entame:
        e = phrase_elimination(d, contrat, decl, entame["carte"], encheres, reste)
        if e: etapes.append(e); fin = "Jouer l'élimination avant d'attaquer la couleur."
        import coups
        pp = coups.premier_pli(d, contrat, decl, entame["carte"], encheres)
        if pp:                                             # son pourcentage, à cartes vues, n'est pas celui de l'essai
            pp = re.sub(r" \(le contrat gagne \d+\s?% du temps, contre \d+\s?% avec ([^)]+)\)", r" (plutôt que \1)", pp)
            etapes.insert(0, pp.replace("Premier pli :", "<b>Premier pli :</b>"))
    if parties: return {"compte": compte, "etapes": etapes, "essai": a, "fin": fin, "infos": infos}
    texte = [compte] + [f"{k}. {x}" for k, x in enumerate(etapes, 1)] + ([essai] if essai else [])
    return "<br/>".join(texte + ([fin] if verdict and fin else []))


def tete_commune(a, b):
    """Nombre de cartes de tête des deux mains qui se suivent depuis l'as."""
    k = 0
    for x in ORDRE:
        if x not in a + b: return k
        k += 1
    return k


def mauvais_partage(a, b):
    """(n, p) : le partage qui nous coûte une levée de plus que le normal, ou None si m < 3 : n cartes
    chez l'un, p chez l'autre."""
    m = 13 - len(a) - len(b)
    if m < 3: return None
    h = (m + 1) // 2 + 1 if m % 2 else m // 2 + 2
    return (h, m - h) if h <= m else None


def maniement(a, b, c, decl, mort):
    """La couleur à tirer, dans l'ordre : l'honneur de la main courte d'abord (la couleur ne se
    bloque pas), puis ce que donnent le partage normal et le mauvais. None si elle n'a pas assez de
    cartes maîtresses pour que ce soit dit simplement. (texte, levées perdues si le partage est mauvais)."""
    m = 13 - len(a) - len(b); t = tete_commune(a, b)
    L, C = (a, b) if len(a) >= len(b) else (b, a)
    p = mauvais_partage(a, b)
    if not p or t < 2 or t < p[0] - 1 or not C or len(L) <= t: return None
    d1 = next((x for x in C if x in ORDRE[:t]), None)
    tete = f"{c}{d1} d'abord, puis vers {L}" if d1 else f"{c}{L[0]} d'abord, de {L}"
    n = len(L); perte = max(p[0] - t, 0); mot = lambda x: NOMBRE.get(x, x)
    txt = f"{tete}. {partage_normal(m)} : {mot(n)} levées."
    if perte: txt += f" {p[0]}-{p[1]} : {mot(n - perte)} levées, il en faudra {'une' if perte == 1 else mot(perte)} de plus ailleurs."
    else: txt += f" Même {p[0]}-{p[1]}, la couleur tient."
    return txt, perte


def compter_plan(d, contrat, decl, entame=None, encheres=None, essai=None, infos=None):
    """(le compte, les étapes dans l'ordre de jeu, la phrase de fin, levées qui manquent avec des
    partages normaux). essai : lignes.analyser, qui tranche ce que le compte seul ne dit pas. infos (un dict) reçoit
    les chiffres du compte, pour que le coach les rédige : need, reste, gain (impasses possibles) ; à SA ks (levées
    sûres) et k (avec des partages normaux) ; à la couleur perdantes (texte), permis, coupes, conseil (l'ordre atout/coupes)."""
    den = contrat[1:].rstrip("X"); need = int(contrat[0]) + 6
    mort = PART[decl]; s_dec, s_mort = suites(d["mains"][decl]), suites(d["mains"][mort])
    cx = lire_encheres(encheres, d["donneur"]) if encheres else None
    restant = 40 - sum(PTS.get(x, 0) for c in COULEURS for x in s_dec[c] + s_mort[c])   # H adverses
    tete = f"{decl} déclarant à {contrat}" + (f", entame {entame['carte']}." if entame else ".")
    lead = entame["carte"][0] if entame else None; meneur = entame["joueur"] if entame else None
    imps = {c: impasses((decl, s_dec), (mort, s_mort), c) for c in COULEURS}
    if den == "SA" and lead: imps[lead] = []               # la couleur d'entame : la défense l'a ouverte
    elif lead:                                             # l'entame prend une carte à la main qui devait jouer vers la fourchette
        s_ = {decl: s_dec, mort: s_mort}
        imps[lead] = [(t, h, w) for t, h, w in imps[lead] if len(s_[RHO[w]][lead]) > 1 and LHO[w] != decl]
    gain = sum(1 for c in COULEURS if imps[c])             # une levée de plus par couleur, au mieux
    r = {c: max(len(s_dec[c]), len(s_mort[c])) for c in COULEURS}
    etapes = []; vue = set()
    if den == "SA":
        sur = {c: sures(s_dec[c], s_mort[c]) for c in COULEURS}
        tops = {c: r[c] - len(tours_adverses(s_dec[c], s_mort[c], r[c])) for c in COULEURS}
        ks = sum(sur.values())
        ordre = sorted(COULEURS, key=lambda c: (-(tops[c] - sur[c]), -len(s_dec[c] + s_mort[c])))
        principal = next((c for c in ordre if tops[c] > sur[c]), None)   # la couleur à affranchir
        partage = {c: sur[c] if imps[c] and c != principal else tops[c] for c in COULEURS}   # l'impasse n'est pas comptée
        k = min(sum(partage.values()), 13)
        ph = f"Levées sûres : {lister_levees(sur)} : {ks} ; il en faut {need}."
        if infos is not None: infos.update(ks=ks, k=k)
        if partage != sur: ph += f" Avec des partages normaux : {lister_levees(partage)} : {k} levées."
        cumul = ks
        for c in ordre:                                    # les couleurs qu'il faut affranchir, la plus payante d'abord
            if cumul >= need or partage[c] <= sur[c]: continue
            cumul += partage[c] - sur[c]; n = len(s_dec[c]) + len(s_mort[c])
            vue.add(c); nom = NOM_C[c].capitalize()
            m = maniement(s_dec[c], s_mort[c], c, decl, mort)
            espoir = f", il en manque {13 - n}, on espère {partage_normal(13 - n)}" if n >= 7 else ""
            if imps[c]: etapes.append((c, f"<b>{nom} :</b> " + " ".join(x.replace(f"{c} : ", "", 1) + placer(hh[0], c, av, decl, cx, restant, entame) + "."
                                                                    for x, hh, av in imps[c])))
            elif m: etapes.append((c, f"<b>{nom} :</b> {m[0]}"))
            else: etapes.append((c, f"<b>{nom} :</b> les affranchir ({s_dec[c] or '–'} face à {s_mort[c] or '–'}{espoir})."))
        reste = need - k
        for c in COULEURS:                                 # la main longue n'a pas de quoi reprendre la main
            lo, co = (decl, mort) if len(s_dec[c]) >= len(s_mort[c]) else (mort, decl)
            L, C = (s_dec, s_mort) if lo == decl else (s_mort, s_dec)
            t = tete_commune(s_dec[c], s_mort[c])
            if C[c] and len(C[c]) <= 2 and len(L[c]) >= 4 and all(x in ORDRE[:t] for x in C[c]) and not any(L[x][:1] == "A" for x in COULEURS if x != c):
                etapes.append((c, f"<b>{NOM_C[c].capitalize()} :</b> attention au blocage. {lo} n'a pas de rentrée ailleurs : débloquer {c}{C[c]} de {co} dès que possible."))
    else:
        h = decl if len(s_dec[den]) >= len(s_mort[den]) else mort   # main longue à l'atout
        longue, courte = (s_dec, s_mort) if h == decl else (s_mort, s_dec)
        nommees, coupes = {}, {}
        atouts_courts = len(courte[den])
        for c in COULEURS:                                # perdantes de la main longue à l'atout
            pc = tours_adverses(s_dec[c], s_mort[c], len(longue[c]) if c != den else r[c])
            nommees[c] = (len(pc), pc)
        en_trop = sum(k for k, _ in nommees.values()) - (13 - need)   # on ne coupe que ce qu'il faut
        for c in COULEURS:
            pc = nommees[c][1]
            if en_trop > 0 and c != den and pc and atouts_courts and len(courte[c]) < len(longue[c]):
                forcees = max(len(courte[c]) - tete_commune(s_dec[c], s_mort[c]), 0)   # les tours où la main courte fournit encore
                k = min(len(pc) - forcees, len(longue[c]) - len(courte[c]), atouts_courts, en_trop)
                if k <= 0: continue
                coupes[c] = k; atouts_courts -= k; en_trop -= k
        coupes = {c: n for c, n in coupes.items() if n}
        total = sum(k for k, _ in nommees.values())
        permis = 13 - need
        if lead and entame["carte"][1:] in "ARDV":             # l'honneur entamé est sorti : on recompte la couleur sans lui
            h_e = entame["carte"][1:]
            a_e, b_e = list(s_dec[lead]), list(s_mort[lead])    # le premier tour : notre plus petite carte qui bat l'honneur, sinon nos deux plus basses
            battent = [v for v in a_e + b_e if ORDRE.index(v) < ORDRE.index(h_e)]
            bat = not battent
            if battent:
                v = max(battent, key=ORDRE.index)
                gagne, autre = (a_e, b_e) if v in a_e else (b_e, a_e)
                gagne.remove(v)
                if autre: autre.pop()
            else:
                for p_e in (a_e, b_e):
                    if p_e: p_e.pop()
            partis = set(s_dec[lead] + s_mort[lead]) | {h_e}
            sans = lambda x: (lambda y: [y[0::2], y[1::2]])([v for v in x if v not in partis])
            reste_tours = tours_adverses(a_e, b_e, max(len(longue[lead]) - 1, 0), sans)
            k = len(reste_tours) + bat
            if k <= nommees[lead][0]: nommees[lead] = (k, ([h_e] if bat else []) + reste_tours)
        if lead and entame["carte"][1:] in nommees[lead][1] and nommees[lead][0] > 1:   # la carte d'entame ne se nomme pas
            nommees[lead] = (nommees[lead][0], [])
        ph = f"Perdantes si les couleurs se partagent normalement : {nommer_perdantes(nommees, den)}"
        if coupes:
            ph += f", dont {NOMBRE.get(sum(coupes.values()), sum(coupes.values()))} à couper au mort" if h == decl \
                else f", dont {NOMBRE.get(sum(coupes.values()), sum(coupes.values()))} à couper en {decl}"
        ph += f" ; on peut en perdre {permis}."
        if infos is not None: infos.update(perdantes=nommer_perdantes(nommees, den), permis=permis, total=total, coupes=dict(coupes),
                                           coupe_ou="au mort" if h == decl else f"en {decl}")
        defausses = {}                                     # les cartes maîtresses en trop de la main courte
        for c in COULEURS:
            if c != den and len(courte[c]) > len(longue[c]):
                k = min(tete_commune(s_dec[c], s_mort[c]), len(courte[c])) - len(longue[c])
                if k > 0: defausses[c] = k
        libres = max(total - sum(coupes.values()), 0)
        n_def = min(sum(defausses.values()), libres)
        if infos is not None: infos.update(defausses=n_def, defausse_sur=" et ".join(NOM_C[c] for c in defausses))
        if n_def:
            ph += (f" {'Une défausse' if n_def == 1 else NOMBRE.get(n_def, n_def).capitalize() + ' défausses'} sur les "
                   f"{' et '.join(NOM_C[c] for c in defausses)} maîtres{'' if h != decl else ' du mort'}.")
        reste = total - sum(coupes.values()) - n_def - permis
        n_at = len(s_dec[den]) + len(s_mort[den]); m = 13 - n_at
        conseil = "faire tomber les atouts"
        if coupes:
            court = min(len(s_dec[den]), len(s_mort[den]))
            conseil = PURGE_DABORD if court - (m + 1) // 2 >= sum(coupes.values()) else COUPES_DABORD
        if essai and essai["coupes_avant"] >= .6: conseil = COUPES_DABORD
        elif essai and essai["coupes_avant"] <= .4 and coupes and conseil == COUPES_DABORD and sum(coupes.values()) < len(courte[den]):
            conseil = ATOUT_PUIS
        at = f"<b>Atout :</b> {n_at} cartes, il en manque {m}, on espère {partage_normal(m)} : {conseil}."
        vue.add(den)
        for txt, hh, avant in imps[den]: at += " " + txt + placer(hh[0], den, avant, decl, cx, restant, entame) + "."
        e = en_tete(s_dec[den], s_mort[den], den)
        if e: at += " " + e + "."
        if infos is not None: infos["en_tete"] = bool(e)
        p = mauvais_partage(s_dec[den], s_mort[den])
        if p and len(tours_adverses(s_dec[den], s_mort[den], r[den], lambda x: [x[:p[0]], x[p[0]:]])) > nommees[den][0]:
            at += f" Si l'atout est {p[0]}-{p[1]}, il coûte une levée de plus."
        etapes.append((den, at))
        if infos is not None: infos["conseil"] = conseil
        if coupes:
            ou = "au mort" if h == decl else f"en {decl}"
            etapes.append((next(iter(coupes)), f"<b>Coupes :</b> {lister_levees(coupes)} {ou}."))
    annexes = [c for c in COULEURS if c not in vue]
    for c in annexes:                                      # les couleurs à tirer en tête
        e = en_tete(s_dec[c], s_mort[c], c)
        if e: etapes.append((c, e + "."))
    reserve = []
    for c in annexes:                                      # les impasses, en dernier
        for txt, hh, avant in imps[c]:
            ph_i = txt + placer(hh[0], c, avant, decl, cx, restant, entame) + "."
            if den == "SA" and meneur and meneur not in avant and reste > 0:   # la défense reprend du bon côté
                ph_i += f" Si elle perd, {meneur} reprend la main et rejoue sa couleur."
            if essai and essai["impasses"].get("SHDC"[COULEURS.index(c)], 0) >= .4:   # le déclarant simulé la joue
                etapes.append((c, f"<b>{NOM_C[c].capitalize()} :</b> " + ph_i.replace(f"{c} : ", "", 1)))
            else: reserve.append(ph_i)
    if essai:                                              # ce que le déclarant simulé joue et que le compte ne dit pas
        for x in essai["ligne"]:
            c = COULEURS["SHDC".index(x[0])]
            if any(t == c for t, _ in etapes) or c == den: continue
            if x[1] == "coupe" and reste > 0: etapes.append((c, f"<b>{NOM_C[c].capitalize()} :</b> à couper en {PART[x[2]]}."))
            if x[1] == "cede" and s_dec[c] and s_mort[c]: etapes.append((c, f"<b>{NOM_C[c].capitalize()} :</b> céder la main pour les affranchir."))
            if x[1] == "tire" and den == "SA": etapes.append((c, f"<b>{NOM_C[c].capitalize()} :</b> à attaquer ({s_dec[c] or '–'} face à {s_mort[c] or '–'})."))
        for L, (qui, r, r3) in essai["impasse_type"].items():  # l'impasse jouée, même partagée entre les deux mains
            c = COULEURS["SHDC".index(L)]
            if essai["impasses"][L] >= .4 and not any("impasse" in x and (t == c or f"{c} :" in x) for t, x in etapes):
                r, r3 = r.translate(VERS_FR), r3.translate(VERS_FR)
                etapes.append((c, f"<b>{NOM_C[c].capitalize()} :</b> impasse : mener {c}{r} de {qui}, mettre {c}{r3} en {PART[qui]}."))
    if reserve:
        titre = "En réserve" if reste <= 0 else "Levée manquante" if reste == 1 else "Levées manquantes"
        etapes.append((None, f"<b>{titre} :</b> " + " ".join(reserve)))
    if reste <= 0:
        if den == "SA" and ks >= need: fin = "Les levées sûres suffisent : ne pas prendre de risque."
        else: fin = "Avec des partages normaux, le contrat ne dépend pas d'une impasse." if gain \
            else "Le contrat tient si les couleurs se partagent normalement."
    elif reste <= gain:
        fin = "Il faut réussir une impasse." if reste == 1 else f"Il faut réussir {NOMBRE[reste]} impasses."
    else:
        k = reste - gain
        fin = (f"Même avec les impasses, il manque {'une' if k == 1 else NOMBRE.get(k, k)} "
               f"levée{'s' if k > 1 else ''} : compter sur la défense, ou limiter la chute.")
    if infos is not None: infos.update(need=need, reste=reste, gain=gain, sa=den == "SA")
    return f"<b>Compte :</b> {tete} {ph}", etapes, fin, reste
