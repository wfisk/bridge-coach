# -*- coding: utf-8 -*-
"""Enchères recommandées calculées sans Claude (étape 2 : les deux camps enchérissent).

    from encheres import encherir
    r = encherir(donne)      # donne = un élément de <nom>.bc.json["donnes"]
    r["encheres"]            # séquence depuis le donneur : ["1♠", "2♥", "2♠", ...]
    r["explications"]        # [(siège, enchère, explication)] pour les quatre joueurs
    r["contrat"], r["declarant"], r["statut"]   # contrat : "4♠", "3♥X"… ; statut : "complète" ou "non couverte : …"
"""
from .main import Main, COULEURS, MAJEURES
from . import sef2024 as S
from .sef2024 import Appel, Info, NonCouverte, e, rang, MANCHE, SEUIL_MANCHE, PETIT_CHELEM, GRAND_CHELEM

ROT = ["N", "E", "S", "O"]
PART = {"N": "S", "S": "N", "E": "O", "O": "E"}
DOUBLES = ("contre", "surcontre")


def camp(s): return "NS" if s in "NS" else "EO"


# ---------------------------------------------------------------- règles du fichier (systems/<système>/regles.yaml)
_SYSTEME = {}


def systeme(nom="sef-2024"):
    """Les règles écrites dans systems/<nom>/regles.yaml (src/regles.py), ou None si elles ne
    peuvent pas être lues (ruamel.yaml absent, fichier en erreur : le moteur garde son code)."""
    if nom not in _SYSTEME:
        import os, sys
        racine = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        sys.path.insert(0, os.path.join(racine, "src"))
        try:
            from regles import charger
            _SYSTEME[nom] = charger(os.path.join(racine, "systems", nom, "regles.yaml"))
        except Exception as ex:                          # ImportError, ErreurRegles…
            print(f"(règles {nom} non lues : {ex} ; le moteur utilise son code)", file=sys.stderr)
            _SYSTEME[nom] = None
    return _SYSTEME[nom]


def cle_regles(seq, i0, s):
    """La séquence telle que l'écrit le fichier de règles, vue du camp de s : depuis l'ouverture,
    nos enchères telles quelles (passes comprises), celles des adversaires entre parenthèses
    (leurs passes omises). Ex. ('1♦', '(1♠)')."""
    debut = next(k for k, b in enumerate(seq) if b != "passe")
    out = []
    for k in range(debut, len(seq)):
        qui = ROT[(i0 + k) % 4]
        if camp(qui) == camp(s): out.append(seq[k])
        elif seq[k] != "passe": out.append(f"({seq[k]})")
    return tuple(out)


NOM_COULEUR = {"♠": ("pique", "piques"), "♥": ("cœur", "cœurs"), "♦": ("carreau", "carreaux"), "♣": ("trèfle", "trèfles")}
NOMBRE = {2: "deux", 3: "trois", 4: "quatre", 5: "cinq", 6: "six", 7: "sept", 8: "huit", 9: "neuf", 10: "dix"}
LETTRE = {"T": "♣", "K": "♦", "C": "♥", "P": "♠"}


def decrire_main(m, r, mo):
    """« 5 H, six piques, trois cœurs, singleton carreau » : ce qui compte pour cette enchère."""
    utiles = set(mo["L"]) | {c for c in COULEURS if m.L[c] >= 5}
    if r.enchere[0].isdigit() and r.enchere[1:] in COULEURS: utiles.add(r.enchere[1:])
    morceaux = [f"{m.hcp} H"]
    for c in COULEURS:
        if m.L[c] == 0: morceaux.append(f"chicane {NOM_COULEUR[c][0]}")
        elif m.L[c] == 1: morceaux.append(f"singleton {NOM_COULEUR[c][0]}")
        elif c in utiles: morceaux.append(f"{NOMBRE.get(m.L[c], m.L[c])} {NOM_COULEUR[c][1]}")
    if mo["reg"] and m.reguliere: morceaux.append("main régulière")
    return ", ".join(morceaux)


def compte_hld(m, r):
    """« HLD 7 = 5 H + 2 (courtes) » quand la règle compte en HLD."""
    import re
    if "HLD" not in r.condition.texte: return ""
    x = re.search(r"HLD\(([TKCP♠♥♦♣])\)", r.condition.texte)
    atout = LETTRE.get(x[1], x[1]) if x else r.condition.atout
    if not atout: return ""
    from regles import hld_detail
    t, h, courtes, atouts = hld_detail(m, atout)
    return f"HLD {t} = {h} H + {courtes} (courtes)" + (f" + {atouts} (atouts en plus)" if atouts else "")


def vul_vue(donne, s):
    """Les camps vulnérables vus du joueur s : () , ("nous",), ("eux",) ou ("nous", "eux")."""
    v = donne.get("vul", "Personne")
    nous_ns = s in "NS"
    out = []
    if v == "Tous" or v == ("N-S" if nous_ns else "E-O"): out.append("nous")
    if v == "Tous" or v == ("E-O" if nous_ns else "N-S"): out.append("eux")
    return tuple(out)


def depuis_regles(cle, m, position=None, vul=(), partenaire=None):
    """L'enchère du fichier de règles pour cette séquence, en Appel, ou None (séquence non décrite).
    L'explication dit ce que la main contient, ce que l'enchère montre, le compte des points (HLD),
    le statut de la règle, et l'autre enchère que la main permettait (la règle suivante vraie)."""
    sy = systeme()
    if not sy: return None
    vraies = sy.toutes(cle, m, position, vul, partenaire)
    if not vraies: return None
    r = vraies[0]
    mo = r.condition.montre()
    if mo["pts"] and mo["pts"][1] >= 37: mo["pts"] = (mo["pts"][0], 40)   # pas de maximum : zone ouverte (40)
    texte = f"{decrire_main(m, r, mo)} : {r.montre}" if r.montre else decrire_main(m, r, mo)
    compte = compte_hld(m, r)
    if compte: texte += f" ; {compte}"
    texte += {"à confirmer": " (à confirmer)", "SA": " (Standard American)"}.get(r.source, "")
    if r.note: texte += f" — {r.note}"
    autre = next((x for x in vraies[1:] if x.enchere not in (r.enchere, "passe")), None) \
        if cle != "ouverture" else None                 # ouvertures : l'ordre du système suffit
    if autre and r.enchere != "passe":
        texte += f". {autre.enchere} ({autre.montre}) convenait aussi, mais vient après dans le système"
    elif autre:
        texte += f". {autre.enchere} ({autre.montre}) était possible"
    return Appel(r.enchere, texte, mo["pts"], mo["L"], True if mo["reg"] else None, nature=r.nature,
                 atout=r.atout or (r.enchere[1:] if r.enchere[0].isdigit() and r.enchere[1:] != "SA" else None))


COMPLETER_SPOUTNIK = True      # contre Spoutnik sans longueur : la majeure libre (une seule) compte 4 cartes
COMPLETER_REPETE = True        # couleur répétée sans longueur : une carte de plus que montré, 5 au moins, 6 au plus
COMPLETER_APPEL = True         # contre d'appel sans longueur : 3 cartes dans chaque majeure non nommée


def completer(a, s, hist, infos):
    """Ce qu'une enchère du fichier de règles implique sans l'écrire (sa condition est un « ou ») : la longueur
    que les enchères suivantes du partenaire doivent connaître pour trouver le fit."""
    nommees = {b.enchere[1:] for _, b in hist if b.enchere[0].isdigit()}
    libres = [M for M in MAJEURES if M not in nommees]
    if a.enchere == "contre" and not a.L:
        if COMPLETER_SPOUTNIK and a.nature == "spoutnik" and len(libres) == 1: a.L = {libres[0]: 4}
        elif COMPLETER_APPEL and a.nature == "appel" and libres: a.L = {M: 3 for M in libres}
        return
    c = a.enchere[1:]
    if COMPLETER_REPETE and a.enchere[0].isdigit() and c in COULEURS and not (a.L or {}).get(c) \
            and a.nature not in ("controle", "soutien_lent", "demande_arret", "relais", "blackwood", "cue") \
            and any(x == s and b.enchere[1:] == c and b.nature != "relais" for x, b in hist):
        a.L = dict(a.L or {}, **{c: min(max(infos[s].L[c] + 1, 5), 6)})


def encherir(donne, bruit=None):
    """bruit = {siège: ±points} : jugement d'un joueur plus optimiste ou plus prudent (simulations)."""
    mains = {s: Main(donne["mains"][s]) for s in ROT}
    for s, dv in (bruit or {}).items(): mains[s].hcp += dv
    i0 = ROT.index(donne["donneur"])
    seq, expl, hist = [], [], []         # hist : [(siège, Appel)] de toutes les enchères autres que passe
    infos = {s: Info() for s in ROT}
    etat = dict(dernier=None, par=None, dbl=0)   # plus haute enchère, son auteur, contre / surcontre
    ouvreur = None; statut = "complète"
    for k in range(80):
        s = ROT[(i0 + k) % 4]
        try:
            v = vul_vue(donne, s); global _VUL; _VUL = v
            if ouvreur is None: a = depuis_regles("ouverture", mains[s], k + 1, v) or S.ouverture(mains[s], k + 1)
            else:
                ip = infos[PART[s]]
                dp = next((b for x, b in reversed(hist) if camp(x) == camp(s) and b.enchere not in DOUBLES), None)
                a = suite_controles(mains[s], s, hist, infos, etat) if dp and dp.nature in ("controle", "soutien_lent") and dp is not moi_dernier(hist, s) \
                    else reponse_arret(mains[s], dp, hist, s, etat["dernier"]) if dp and dp.nature == "demande_arret" and dp is not moi_dernier(hist, s) \
                    else depuis_regles(cle_regles(seq, i0, s), mains[s], k % 4 + 1, vul=v,   # le siège (S 1-2 : main passée en réponse)
                                       partenaire={"H": ip.pts[0], "L": dict(ip.L)})   # séquence décrite dans le fichier ?
                if a is None and camp(s) == camp(ouvreur): a = cote_ouvreur(mains[s], s, hist, infos, etat, ouvreur)
                elif a is None: a = cote_defense(mains[s], s, hist, infos, etat, seq)
        except NonCouverte as ex:
            statut = f"non couverte : {ex}"; a = Appel("passe", "séquence non couverte")
        except Exception as ex:                          # jamais d'arrêt du rapport : on passe et on le dit
            statut = f"erreur : {type(ex).__name__} {ex}"; a = Appel("passe", "erreur du moteur")
        if ouvreur is not None and statut == "complète":
            a = avant_3sa(mains[s], s, a, hist, infos, etat)
            a = chelem(mains[s], s, a, hist, infos, etat)
            a = punir(mains[s], s, a, hist, infos, etat)
        if not legal(a.enchere, s, etat):
            a = Appel("passe", f"({a.enchere} n'est plus possible)")
        seq.append(a.enchere); expl.append((s, a.enchere, a.texte))
        if a.enchere != "passe":
            completer(a, s, hist, infos)
            hist.append((s, a)); infos[s].montre(a.pts, a.L, a.reguliere)
            if ouvreur is None: ouvreur = s
            if a.enchere == "contre": etat["dbl"] = 1
            elif a.enchere == "surcontre": etat["dbl"] = 2
            else: etat.update(dernier=a.enchere, par=s, dbl=0)
        if fin(seq): break
    d = etat["dernier"]
    decl = next(x for x, a in hist if camp(x) == camp(etat["par"]) and a.enchere[1:] == d[1:]) if d else None
    return dict(encheres=seq, explications=expl, contrat=(d + "X" * etat["dbl"]) if d else "passe",
                declarant=decl, statut=statut, notes=[])


# ---------------------------------------------------------------- vulnérabilité (placer)
_VUL = ()                      # camps vulnérables vus du joueur qui enchérit (posé par encherir)
LOI_FAV, LOI_DEF = 0, 0       # loi des levées : un palier de plus en favorable, de moins en défavorable (0 : la loi seule)


# ---------------------------------------------------------------- chelem (étape 4)
SEUIL_CHELEM_FIT = 31          # points du camp (les miens + le minimum du partenaire) avec un fit de 8+
SEUIL_CONTROLES = 28           # dès ce total avec un fit : on nomme ses contrôles avant de conclure (0 : jamais)
FIT_MONTRE = True              # le fit se lit aussi sur les longueurs montrées (Spoutnik, réponse 4e…)
SOUTIEN_LENT = True            # fit et chelem possible : soutien forcing au palier de 3 plutôt que la manche
DRURY_PLACE = True             # après le 2♣ Drury du partenaire, pas de recherche de chelem
FIT_MINEUR = 8                 # avant 3SA, un fit de 8+ cartes dans la mineure du partenaire… (0 : jamais)
SEUIL_FIT_MINEUR = 29          # …et ce total : 4 de la mineure, forcing, au lieu de 3SA
ARRET_CUE = True               # avant 3SA sans arrêt dans leur couleur : cue-bid qui demande l'arrêt
SEUIL_ACCORD = 29              # total des deux mains pour demander les clés une fois toutes les couleurs contrôlées
INVITE_LARGE = "vul"           # vulnérable, ma zone montrée large (plus de 6 points) : accepter sur le total avec le partenaire
INVITE_VUL = 1                 # …un point de moins vulnérable (manche vulnérable à l'IMP)
INVITE_MILIEU_VUL = 1          # zone étroite : accepter avec ce nombre de points de moins vulnérable
INVITE_FORME = True            # sur une invitation dans sa couleur, fit pas encore montré : compter la forme (valeur_fit)
COURTES_SI_PART_LONG = True    # le partenaire a montré autant d'atouts que moi (5+) : mes courtes comptent
COURTES_LONG = {0: 3, 1: 1}    # {longueur: points} d'une couleur courte pour la main longue à l'atout
PART_MARGE = 0                 # part de la fourchette du partenaire comptée en plus de son minimum
MANCHES = ("3SA", "4♥", "4♠", "5♣", "5♦")


def valeur_fit(m, atout, part_l=0):
    """Ce que vaut la main une fois le fit trouvé : l'atout court compte ses courtes, le long compte aussi les siennes,
    moins cher (il n'y coupera pas toujours). part_l : les atouts montrés par le partenaire ; s'il en a montré
    autant que moi (cinq au moins), c'est lui le long et mes courtes comptent (COURTES_SI_PART_LONG)."""
    if m.L[atout] <= 4: return m.dh(atout)
    if COURTES_SI_PART_LONG and part_l >= max(5, m.L[atout]): return m.dh(atout)
    return m.hl + sum(COURTES_LONG.get(m.L[c], 0) for c in COULEURS if c != atout)


def chelem(m, s, a, hist, infos, etat):
    """Avant de conclure à la manche (ou de passer sur la manche du partenaire) : le chelem ?
    Avec un fit : Blackwood 3041 si le camp a 31+ points (les miens, HLD si j'ai l'atout court,
    + le minimum montré par le partenaire). Sans fit, à SA : 6SA avec 33+ H, 4SA quantitatif
    avec 31–32 H. Rien si le camp a déjà parlé au palier de 4SA ou plus."""
    nos = [b for x, b in hist if camp(x) == camp(s)]
    if not nos or any(b.nature in ("blackwood", "controle", "soutien_lent") or (b.enchere[0].isdigit() and rang(b.enchere) >= rang("4SA")) for b in nos):
        return a
    if DRURY_PLACE and any(b.nature == "drury" for x, b in hist if x == PART[s]):   # après Drury, la réponse de l'ouvreur place le contrat
        return a
    dernier = etat["dernier"]
    if a.enchere in MANCHES and rang(a.enchere) > rang(dernier or "passe"): cible = a.enchere
    elif a.enchere == "passe" and etat["par"] == PART[s] and etat["dbl"] == 0 and dernier in MANCHES: cible = dernier
    else: return a
    part = infos[PART[s]]; d = cible[1:]
    if part.pts[0] == 0: return a                       # le partenaire n'a rien montré
    if d != "SA" and m.L[d] + max(part.L[d], 3 if d in [x.enchere[1:] for y, x in hist if y == s] and a.enchere == "passe" else 0) >= 8:
        t = valeur_fit(m, d, part.L[d]) + part.pts[0] + int(PART_MARGE * (min(part.pts[1], 40) - part.pts[0]))
        mine = [b.enchere[1:] for x, b in hist if x == s]; lui = [b.enchere[1:] for x, b in hist if x == PART[s]]
        moi_i = infos[s]
        etabli = (d in mine and d in lui) or (FIT_MONTRE and moi_i.L[d] + part.L[d] >= 8)
        if SEUIL_CONTROLES and t >= SEUIL_CONTROLES and a.enchere != "passe" and etabli:
            c = prochain_controle(m, d, dernier, cible)
            if c: return Appel(c, f"{m.hcp} H, fit à {d} : chelem possible, contrôle à {c[1:]}", (valeur_fit(m, d, part.L[d]), 40),
                               nature="controle", atout=d)
        elif SOUTIEN_LENT and SEUIL_CONTROLES and t >= SEUIL_CONTROLES and a.enchere != "passe" and d in lui and d in MAJEURES \
                and moi_i.pts[0] >= 11 and rang(e(3, d)) > rang(dernier):
            return Appel(e(3, d), f"{m.hcp} H, {m.L[d]} cartes à {d} : fit, forcing, chelem possible", (valeur_fit(m, d, part.L[d]), 40),
                         {d: 3}, nature="soutien_lent", atout=d)
        if t >= SEUIL_CHELEM_FIT and rang("4SA") > rang(dernier):
            return Appel("4SA", f"{m.hcp} H, {m.L[d]} cartes à {d} : chelem en vue ({t}+ points ensemble), "
                         f"Blackwood 3041", nature="blackwood", atout=d)
        return a
    if d == "SA" and FIT_MINEUR and rang(dernier) < rang("4♣"):
        lui = {b.enchere[1:] for x, b in hist if x == PART[s] and b.enchere[0].isdigit()}
        fits = [c for c in COULEURS if c not in MAJEURES and c in lui and m.L[c] + part.L[c] >= FIT_MINEUR]
        c = max(fits, key=lambda x: (m.L[x] + part.L[x], x == "♦"), default=None)
        if c:
            t = valeur_fit(m, c, part.L[c]) + part.pts[0]
            if t >= SEUIL_FIT_MINEUR and rang(e(4, c)) > rang(dernier):
                return Appel(e(4, c), f"{m.hcp} H, {m.L[c]} cartes à {c} : fit, {t}+ points ensemble, "
                             "forcing, chelem possible (plutôt que 3SA)", (valeur_fit(m, c, part.L[c]), 40), {c: 4},
                             nature="soutien_lent", atout=c)
    if d == "SA":
        t = m.hcp + part.pts[0]
        if t >= PETIT_CHELEM and rang("6SA") > rang(dernier):
            return Appel("6SA", f"{m.hcp} H : {t}+ points ensemble, petit chelem", nature="conclusion")
        if t >= PETIT_CHELEM - 2 and part.pts[1] < 40 and rang("4SA") > rang(dernier):
            return Appel("4SA", f"{m.hcp} H : {t}–{m.hcp + part.pts[1]} points ensemble, quantitatif : "
                         "invite au chelem", nature="invite")
    return a


def controle(m, c):
    """1 : contrôle du premier tour (as, chicane) ; 2 : du deuxième (roi, singleton) ; 0 : deux perdantes rapides possibles."""
    if m.L[c] == 0 or "A" in m.cartes[c]: return 1
    return 2 if m.L[c] == 1 or "R" in m.cartes[c] else 0


CONTROLE_PALIER = 1            # palier minimum d'un contrôle ; 3 a perdu (−285, −385, −124 IMP) : le moins cher


def prochain_controle(m, d, dernier, cible):
    """Le contrôle le plus économique sous la manche, au palier CONTROLE_PALIER au moins, ou None."""
    for b in sorted((e(max(S.plus_bas(c, dernier), CONTROLE_PALIER), c) for c in COULEURS if c != d), key=rang):
        if rang(b) < rang(cible) and controle(m, b[1:]): return b
    return None


def moi_dernier(hist, s):
    return next((a for x, a in reversed(hist) if x == s and a.enchere not in DOUBLES), None)


def suite_controles(m, s, hist, infos, etat):
    """Le partenaire a nommé un contrôle. Une couleur qu'il a sautée et que je ne tiens pas : deux perdantes
    possibles, on s'arrête à la manche. Toutes tenues et assez de points : on demande les clés. Sinon je nomme
    mon contrôle suivant ; sans contrôle sous la manche, je conclus."""
    dernier = etat["dernier"]
    ctl = [(i, x, a) for i, (x, a) in enumerate(hist) if a.nature in ("controle", "soutien_lent") and camp(x) == camp(s)]
    d = ctl[-1][2].atout; cible = e(MANCHE[d], d)
    fin = lambda txt: Appel(cible, txt, nature="conclusion") if rang(cible) > rang(dernier) else Appel("passe", txt)
    montres, sautes = set(), set()                        # ce que le partenaire a montré, et ce qu'il a dénié
    for i, x, a in ctl:
        if x != PART[s] or a.nature != "controle":
            continue
        avant = next((b.enchere for _, b in reversed(hist[:i]) if b.enchere not in DOUBLES), "passe")
        sautes |= {c for c in COULEURS if c != d and c not in montres and rang(e(S.plus_bas(c, avant), c)) < rang(a.enchere)}
        montres.add(a.enchere[1:])
    sautes -= montres
    mes = {c for c in COULEURS if c != d and controle(m, c)}
    t = valeur_fit(m, d, infos[PART[s]].L[d]) + infos[PART[s]].pts[0]
    if sautes - mes: return fin(f"pas de contrôle à {' ni '.join(sorted(sautes - mes))} : la manche")
    if t < SEUIL_CONTROLES: return fin(f"{t} points ensemble : la manche")
    couverts = mes | montres
    if t >= SEUIL_ACCORD and couverts >= {c for c in COULEURS if c != d} and rang("4SA") > rang(dernier):
        return Appel("4SA", f"toutes les couleurs contrôlées, {t} points ensemble : Blackwood 3041", nature="blackwood", atout=d)
    c = prochain_controle(m, d, dernier, cible)
    if c and c[1:] not in {a.enchere[1:] for _, x, a in ctl if x == s and a.nature == "controle"}:
        return Appel(c, f"{m.hcp} H : contrôle à {c[1:]}", (valeur_fit(m, d, infos[PART[s]].L[d]), 40), nature="controle", atout=d)
    return fin("plus de contrôle à montrer : la manche")


PUNIR_PALIER = 3               # contre punitif de leur contrat à la couleur dès ce palier (0 : jamais)
PUNIR_POINTS = 20              # …si notre camp a ce total (mes H + le minimum du partenaire)
PUNIR_LEVEES = 2               # …et ce nombre de levées d'atout dans ma main


def levees_atout(m, d):
    """Les levées d'atout probables en défense : A ; R second ; D troisième ; V quatrième ; une de plus avec 5 cartes."""
    p, n = m.cartes[d], m.L[d]
    return ("A" in p) + ("R" in p and n >= 2) + ("D" in p and n >= 3) + ("V" in p and n >= 4) + (n >= 5)


def punir(m, s, a, hist, infos, etat):
    """Leur contrat à la couleur, assez haut : contre punitif avec des levées d'atout quand notre camp a la majorité
    des points. Sur le contre punitif du partenaire, on le laisse."""
    if not PUNIR_PALIER or not etat["par"] or camp(etat["par"]) == camp(s): return a
    dp = next((b for x, b in reversed(hist) if x == PART[s]), None)
    if etat["dbl"] == 1 and dp and dp.enchere == "contre" and dp.nature == "punitif" and a.enchere != "passe" \
            and hist[-1][1] is dp:
        return Appel("passe", "laisse le contre punitif du partenaire")
    d = etat["dernier"][1:]
    if etat["dbl"] or a.enchere != "passe" or d == "SA" or int(etat["dernier"][0]) < PUNIR_PALIER: return a
    if not any(camp(x) == camp(s) and b.enchere != "passe" for x, b in hist): return a     # nous n'avons rien dit
    if m.L[d] < 4 or levees_atout(m, d) < PUNIR_LEVEES or m.hcp + infos[PART[s]].pts[0] < PUNIR_POINTS: return a
    return Appel("contre", f"{m.hcp} H, {m.L[d]} cartes à {d} : contre punitif", nature="punitif")


def couleur_adverse(hist, s):
    """La couleur nommée par les adversaires, si une seule ; sinon None."""
    eux = {a.enchere[1:] for x, a in hist if camp(x) != camp(s) and a.enchere[0].isdigit() and a.enchere[1:] != "SA"}
    return next(iter(eux)) if len(eux) == 1 else None


def avant_3sa(m, s, a, hist, infos, etat):
    """3SA sans arrêt dans leur couleur : le cue-bid demande l'arrêt au partenaire. S'il ne l'a pas, on joue
    la manche dans sa couleur la plus longue."""
    if not ARRET_CUE or a.enchere != "3SA": return a
    oc = couleur_adverse(hist, s)
    if not oc or S.arret(m, oc): return a
    nos = [b for x, b in hist if camp(x) == camp(s)]
    if any(b.enchere[1:] == "SA" for b in nos): return a  # le partenaire ou moi avons déjà parlé à SA
    part = infos[PART[s]]
    if any(b.nature == "demande_arret" for b in nos):
        c = max((x for x in COULEURS if x != oc), key=lambda x: m.L[x] + part.L[x])
        b = e(MANCHE[c], c)
        return Appel(b, f"pas d'arrêt à {oc} : la manche à {c}", nature="conclusion") if rang(b) > rang(etat["dernier"]) else a
    c = e(S.plus_bas(oc, etat["dernier"]), oc)
    if rang(c) >= rang("3SA"): return a
    return Appel(c, f"{m.hcp} H, pas d'arrêt à {oc} : cue-bid, demande l'arrêt pour jouer 3SA", nature="demande_arret")


def reponse_arret(m, dp, hist, s, dernier):
    """Le partenaire demande l'arrêt dans leur couleur : 3SA avec l'arrêt, sinon on nomme sa couleur la plus longue."""
    oc = dp.enchere[1:]
    if S.arret(m, oc) and rang("3SA") > rang(dernier):
        return Appel("3SA", f"arrêt à {oc}", nature="conclusion")
    c = m.longue([x for x in COULEURS if x != oc])
    return Appel(e(S.plus_bas(c, dernier), c), f"pas d'arrêt à {oc} : {m.L[c]} cartes à {c}", L={c: m.L[c]})


def legal(b, s, etat):
    if b == "passe": return True
    if b == "contre": return bool(etat["dernier"]) and camp(etat["par"]) != camp(s) and etat["dbl"] == 0
    if b == "surcontre": return etat["dbl"] == 1 and camp(etat["par"]) == camp(s)
    if not (len(b) in (2, 3) and b[0] in "1234567" and b[1:] in ("SA", "♠", "♥", "♦", "♣")): return False   # « 10♠ »…
    return rang(b) > rang(etat["dernier"] or "passe")


def fin(seq):
    if len(seq) >= 4 and all(x == "passe" for x in seq): return True
    return len(seq) >= 4 and any(x != "passe" for x in seq) and seq[-3:] == ["passe"] * 3


# ---------------------------------------------------------------- les deux camps
def cote_ouvreur(m, s, hist, infos, etat, ouvreur):
    dernier = etat["dernier"]
    nos = [(x, a) for x, a in hist if camp(x) == camp(s) and a.enchere not in DOUBLES]
    eux = [a.enchere for x, a in hist if camp(x) != camp(s) and a.enchere not in DOUBLES]
    ouv = nos[0][1].enchere
    du_part = [a for x, a in hist if x == PART[s]]
    if s == ouvreur and not du_part:                      # le partenaire a passé (après un contre adverse…)
        return S.relance_ouvreur(m, ouv, eux[-1][1:] if eux else None, dernier) if (eux or etat["dbl"]) \
            else Appel("passe", "")
    if du_part and du_part[-1].enchere == "surcontre" and not any(x == PART[s] for x, _ in nos):
        return Appel("passe", "laisse le partenaire décider après son surcontre")
    if not eux:                                           # sans intervention à la couleur : système normal
        return suivante(m, s, nos, infos, dernier)
    oc = eux[-1][1:]
    if s != ouvreur and not [a for x, a in hist if x == s]:
        dp = du_part[-1] if du_part else None
        if dp and dp.enchere == "contre" and dp.nature == "appel":     # l'ouvreur a recontré : répondre
            return S.avance_contre(m, [c for c in (x[1:] for x in eux) if c != "SA"], dernier, False)
        return S.reponse_concurrence(m, ouv, oc, dernier)
    dp = du_part[-1]
    if dp.nature == "blackwood": return S.reponse_blackwood(m, dp.atout)
    if len(nos) >= 2 and nos[-2][1].nature == "blackwood" and nos[-2][0] == s:
        return apres_blackwood(m, nos[-2][1].atout, nos[-1][1].enchere, infos[PART[s]])
    if dp.nature == "spoutnik": return S.apres_spoutnik(m, ouv, oc, dp, dernier)
    moi = next((a for x, a in reversed(hist) if x == s and a.enchere not in DOUBLES), None)
    if moi and moi.nature == "cue": return apres_mon_cue(m, s, moi, etat, False)
    if dp.nature == "cue": return reponse_cue(m, dp, oc, dernier)
    a = soutien_apres_contre(m, s, hist, dernier)
    if a: return a
    return placer(m, s, nos or [(PART[s], dp)], infos, dernier, adverse=camp(etat["par"]) != camp(s))


def cote_defense(m, s, hist, infos, etat, seq):
    dernier = etat["dernier"]
    nos = [(x, a) for x, a in hist if camp(x) == camp(s)]
    eux = [a.enchere[1:] for x, a in hist if camp(x) != camp(s) and a.enchere not in DOUBLES]
    mes = [a for x, a in nos if x == s]; du_part = [a for x, a in nos if x == PART[s]]
    adverse = camp(etat["par"]) != camp(s)
    if not mes and not du_part:                           # première action : intervention ou réveil
        if not adverse: return Appel("passe", "")
        reveil = seq[-2:] == ["passe", "passe"]
        ouv = next(a.enchere for x, a in hist if camp(x) != camp(s) and a.enchere not in DOUBLES)
        return S.intervention(m, ouv, reveil, dernier)
    if not mes:                                           # le partenaire est intervenu : avancer
        dp = du_part[-1]
        i = max(j for j, (x, _) in enumerate(hist) if x == PART[s])
        libre = any(camp(x) != camp(s) for x, _ in hist[i + 1:])
        if dp.enchere == "contre" and dp.nature == "appel":
            return S.avance_contre(m, [c for c in eux if c != "SA"], dernier, libre)
        if dp.enchere == "contre": return Appel("passe", "laisse le contre punitif")
        if dp.enchere[1:] == "SA": return placer(m, s, nos, infos, dernier, adverse=adverse)   # 1SA, 2SA bicolore…
        return S.avance_couleur(m, dp.enchere[1:], eux[-1] if eux else None, dernier, dp.nature == "reveil")
    dp = du_part[-1] if du_part else Appel("passe", "")
    if dp.nature == "blackwood": return S.reponse_blackwood(m, dp.atout)
    moi = mes[-1]
    if moi.nature == "cue": return apres_mon_cue(m, s, moi, etat, True)
    if dp.nature == "cue": return reponse_cue_intervenant(m, dp, dernier)
    if moi.nature == "appel" and du_part and len(mes) == 1 and m.hcp >= 17:   # contre fort : montrer sa couleur
        pc = dp.enchere[1:] if dp.enchere not in DOUBLES else None
        c = m.longue([x for x in COULEURS if x not in eux])
        if m.L[c] >= 5 and c != pc and (not pc or pc == "SA" or m.L[pc] < 4):
            n = S.plus_bas(c, dernier)
            if n <= 3: return Appel(e(n, c), f"contre fort (17+) puis {m.L[c]} cartes à {c}", (17, 21), {c: m.L[c]})
    a = soutien_apres_contre(m, s, hist, dernier)
    if a: return a
    if not du_part:                                       # j'ai parlé seul : le partenaire a passé
        moi = mes[-1]
        if moi.nature == "appel" and m.hcp >= 17:          # contre fort : nommer sa couleur
            c = m.longue([x for x in COULEURS if x not in eux])
            n = S.plus_bas(c, dernier)
            if n <= 3: return Appel(e(n, c), f"contre fort puis {m.L[c]} cartes à {c}", (17, 21), {c: 5})
        return Appel("passe", "")
    return placer(m, s, nos, infos, dernier, adverse=adverse)


def reponse_cue(m, dp, oc, dernier):
    """Le partenaire a fait un cue-bid, forcing de manche. Fit majeur : la manche, ou le palier de 3 avec
    15+ HL (arriver lentement montre des points en plus). Mineure : l'arrêt, sinon on répète sa couleur."""
    c = dp.atout
    if c in MAJEURES:
        if m.hl >= 15 and rang(e(3, c)) > rang(dernier):
            return Appel(e(3, c), f"sur le cue-bid : {m.hl} HL, des points en plus", (15, 21), {c: 5})
        return Appel(e(4, c), "sur le cue-bid : la manche, sans rien de plus", (12, 14), {c: 5}, nature="conclusion")
    if S.arret(m, oc):
        if m.hcp >= 14 or rang("2SA") <= rang(dernier):
            return Appel("3SA", f"sur le cue-bid : arrêt à {oc}", (12, 21), nature="conclusion")
        return Appel("2SA", f"sur le cue-bid : arrêt à {oc}, 12–13 H", (12, 13))
    n = S.plus_bas(c, dernier)
    return Appel(e(n, c), f"sur le cue-bid : pas d'arrêt à {oc}, répète sa couleur", (12, 21), {c: 3})


def reponse_cue_intervenant(m, dp, dernier):
    """Le partenaire demande la force de mon intervention : répétition simple, moins de 13 HL ;
    avec un saut, la valeur d'une ouverture."""
    c = dp.atout; n = S.plus_bas(c, dernier)
    if n > 3: return Appel("passe", "trop haut pour répondre au cue-bid")
    if m.hl >= 13 and n <= 2: return Appel(e(n + 1, c), f"sur le cue-bid : {m.hl} HL, valeur d'une ouverture", (13, 18))
    if m.hl >= 13: return Appel(e(4, c), f"sur le cue-bid : {m.hl} HL, la manche", (13, 18), nature="conclusion")
    return Appel(e(n, c), f"sur le cue-bid : {m.hl} HL, moins qu'une ouverture", (8, 12))


def apres_mon_cue(m, s, moi, etat, intervenant):
    """J'ai fait le cue-bid, le partenaire a répondu : le contrat final. L'intervenant n'a promis qu'un tour :
    on s'arrête avec 11–12 points face à une intervention sans ouverture."""
    c = moi.atout; dernier = etat["dernier"]; part = etat["par"]
    if part == PART[s] and dernier in MANCHES: return Appel("passe", "manche atteinte")
    if intervenant:
        if m.dh(c) < 13 and part == PART[s] and int(dernier[0]) <= 2:
            return Appel("passe", "face à une intervention sans ouverture : pas de manche")
        return Appel(e(4, c), "fit, valeur de manche ensemble", nature="conclusion")
    if c in MAJEURES: return Appel(e(4, c), "la manche", nature="conclusion")
    if part == PART[s] and dernier[1:] == "SA" and rang("3SA") > rang(dernier):
        return Appel("3SA", "le partenaire a l'arrêt : la manche", nature="conclusion")
    if m.L[c] >= 3 and rang(e(5, c)) > rang(dernier):
        return Appel(e(5, c), f"pas d'arrêt : la manche à {c}", nature="conclusion")
    return Appel("3SA", "la manche, à SA faute de mieux", nature="conclusion")


def soutien_apres_contre(m, s, hist, dernier):
    """J'ai fait un contre d'appel, le partenaire a répondu dans une couleur sans sauter (0–8 H) :
    avec du soutien et des points en plus, je soutiens. Le partenaire a en moyenne 4 H ;
    comptés en HLD, il faut 21 pour la manche en majeure, 19 pour monter d'un palier."""
    mes = [a for x, a in hist if x == s]; lui = [a for x, a in hist if x == PART[s]]
    if not mes or not lui or mes[-1].enchere != "contre" or mes[-1].nature != "appel": return None
    r = lui[-1]
    if r.enchere in DOUBLES or r.enchere[1:] == "SA" or r.nature != "limite" or not r.pts or r.pts[1] > 8: return None
    c = r.enchere[1:]
    if dernier != r.enchere or m.L[c] < 3: return None
    t = m.dh(c) + (1 if m.L[c] >= 4 else 0)
    if m.L[c] == 3 and t < 20: return None
    n = int(r.enchere[0])
    if c in MAJEURES and t >= 21 and n < 4:
        return Appel(e(4, c), f"{m.hcp} H, {m.L[c]} cartes à {c} : manche face à la réponse au contre",
                     nature="conclusion")
    if t >= 19 and n + 1 < MANCHE[c]:
        return Appel(e(n + 1, c), f"{m.hcp} H, {m.L[c]} cartes à {c} : soutien, invitation", nature="invite")
    return None


# ---------------------------------------------------------------- aiguillage
def suivante(m, s, nos, infos, dernier):
    k = len(nos)                         # enchères déjà faites par le camp
    ench = [a.enchere for _, a in nos]
    ouv = ench[0]
    part = infos[PART[s]]; moi = infos[s]
    dern_part = next((a for x, a in reversed(nos) if x == PART[s]), None)
    if dern_part is None: return Appel("passe", "le partenaire n'a pas parlé : rien à ajouter")

    if dern_part.nature == "blackwood":
        return S.reponse_blackwood(m, dern_part.atout)
    if len(nos) >= 2 and nos[-2][1].nature == "blackwood":
        return apres_blackwood(m, nos[-2][1].atout, dern_part.enchere, part)

    if k == 1:                           # réponse à l'ouverture
        if ouv in ("1♥", "1♠"): return S.reponse_majeure(m, ouv[1])
        if ouv in ("1♣", "1♦"): return S.reponse_mineure(m, ouv[1])
        if ouv == "1SA": return S.reponse_1sa(m, 1)
        if ouv == "2SA": return S.reponse_1sa(m, 2)
        if ouv == "2♣": return Appel("2♦", "relais", nature="relais")
        if ouv == "2♦": return Appel("2♥", "relais (à confirmer)", nature="relais")
        if ouv[0] in "23":                # faible ou barrage
            c = ouv[1:]
            if m.L[c] >= 2 and m.dh(c) + 8 >= SEUIL_MANCHE[c] + (0 if ouv[0] == "2" else -2):
                return Appel(e(MANCHE[c], c), "manche face au barrage", nature="conclusion")
            return Appel("passe", "pas de manche face à un barrage")
        raise NonCouverte(f"réponse à {ouv}")

    if k == 2:                           # deuxième enchère de l'ouvreur
        rep = ench[1]
        if ouv in ("1SA", "2SA"):
            p = 1 if ouv == "1SA" else 2
            if rep == e(p + 1, "♣"): return S.reponse_stayman(m, p)
            if rep == e(p + 1, "♦"): return Appel(e(p + 1, "♥"), "complète le texas", L={"♥": 2})
            if rep == e(p + 1, "♥"): return Appel(e(p + 1, "♠"), "complète le texas", L={"♠": 2})
            return accepte_ou_passe(m, nos, moi)
        if ouv in ("2♣", "2♦"):
            if m.reguliere: return Appel("2SA" if ouv == "2♣" else "2SA", "régulier, fort", reguliere=True)
            c = m.longue()
            n = S.plus_bas(c, rep)
            return Appel(e(n, c), f"{m.L[c]} cartes à {c}", L={c: 5})
        return S.redemande(m, ouv, rep, moi)

    if k == 3 and ouv in ("1SA", "2SA"):
        p = 1 if ouv == "1SA" else 2
        base = 15 if p == 1 else 20
        rep = ench[1]
        if rep in (e(p + 1, "♦"), e(p + 1, "♥")): return apres_texas(m, ench[2][1:], base, dernier)
        if rep == e(p + 1, "♣"): return apres_stayman(m, ench[2][1:], base, dernier)

    return placer(m, s, nos, infos, dernier)


# ---------------------------------------------------------------- suites de conventions
def apres_texas(m, M, base, dernier):
    h = m.hcp; t = h + base; six = m.L[M] >= 6
    if t >= PETIT_CHELEM and six: return Appel(e(6, M), "petit chelem", nature="conclusion")
    if t >= PETIT_CHELEM - 2: return Appel("4SA", "quantitatif (après un texas)", nature="invite")
    if t >= 25:
        if six or not m.reguliere: return Appel(e(4, M), "manche", nature="conclusion")
        return Appel("3SA", "manche, choix entre 3SA et 4" + M, nature="choix", atout=M) if rang("3SA") > rang(dernier) \
            else Appel(e(4, M), "manche", nature="conclusion")
    if t >= 23:
        a = Appel(e(3, M), "invitation, 6 cartes", nature="invite") if six else Appel("2SA", "invitation, 5 cartes", nature="invite", atout=M)
        if rang(a.enchere) > rang(dernier): return a
    return Appel("passe", "pas de manche")

def apres_stayman(m, rep, base, dernier):
    h = m.hcp
    if rep in MAJEURES and m.L[rep] >= 4:
        t = m.dh(rep) + base
        if t >= PETIT_CHELEM: return Appel("4SA", "Blackwood 3041, fit " + rep, nature="blackwood", atout=rep)
        if t >= 25: return Appel(e(4, rep), "manche avec le fit", nature="conclusion")
        return Appel(e(3, rep), "invitation avec le fit", nature="invite")
    t = h + base
    if t >= PETIT_CHELEM: return Appel("6SA", "petit chelem", nature="conclusion")
    if t >= 25: return Appel("3SA", "manche, pas de fit majeur", nature="conclusion")
    return Appel("2SA" if rang("2SA") > rang(dernier) else "passe", "invitation", nature="invite")


BONUS_LONGUE = {5: 1, 6: 2, 7: 3}   # points en plus à SA pour une couleur longue avec deux des trois gros honneurs


def bonus_sa(m):
    """À SA, une bonne couleur longue (deux des trois gros honneurs A R D) vaut des points de plus :
    elle fournit des levées de longueur, plus que le point par carte compté en HL."""
    return max([BONUS_LONGUE.get(min(m.L[c], 7), 0) for c in COULEURS if sum(x in "ARD" for x in m.cartes[c]) >= 2] + [0])


def accepte_ou_passe(m, nos, moi):
    """L'ouvreur de SA répond à une invitation ou à un choix du répondant."""
    a = nos[-1][1]
    lo, hi = moi.pts
    maxi = m.hcp + bonus_sa(m) >= (lo + hi) / 2
    if a.nature == "invite" and a.enchere == "4SA": return Appel("6SA" if maxi else "passe", "maximum" if maxi else "minimum")
    if a.nature == "invite": return Appel("3SA" if maxi else "passe", "maximum" if maxi else "minimum")
    return Appel("passe", "")


def apres_blackwood(m, atout, reponse, part):
    mes = m.cles(atout)
    n = {"5♣": (0, 3), "5♦": (1, 4), "5♥": (2, 2), "5♠": (2, 2)}[reponse]
    lui = n[1] if mes + n[1] <= 5 and mes <= 2 else n[0]
    manque = 5 - mes - lui
    if manque >= 2:
        if rang(e(5, atout)) > rang(reponse): return Appel(e(5, atout), "il manque deux clés", nature="conclusion")
        return Appel(e(6, atout), "il manque deux clés, mais 5" + atout + " n'est plus possible", nature="conclusion")
    if manque == 0 and m.hcp + part.pts[0] >= GRAND_CHELEM:
        return Appel(e(7, atout), "toutes les clés, grand chelem", nature="conclusion")
    return Appel(e(6, atout), "petit chelem" + (" (une clé manque)" if manque else ""), nature="conclusion")


# ---------------------------------------------------------------- placement du contrat
def moi_pts(m, moi):
    """La force qu'on montre en invitant : le partenaire doit pouvoir compter dessus."""
    return max(m.hcp, moi.pts[0])


def placer(m, s, nos, infos, dernier, adverse=False):
    """adverse : le contrat en cours appartient aux adversaires (concurrence)."""
    part = infos[PART[s]]; moi = infos[s]
    dp = next((a for x, a in reversed(nos) if x == PART[s]), None)
    if dp is None: return Appel("passe", "le partenaire n'a pas parlé : rien à ajouter")
    if dp.nature == "conclusion":
        M = m.longue(MAJEURES)
        if dp.enchere == "3SA" and m.L[M] >= 7 and not m.reguliere:
            return Appel(e(4, M), f"{m.L[M]} cartes à {M} : la manche à la couleur", nature="conclusion")
        return Appel("passe", "contrat fixé par le partenaire")
    if dp.nature in ("invite", "choix"):
        lo, hi = moi.pts
        d = dp.enchere[1:]
        val = m.hl + (bonus_sa(m) if d == "SA" else 0)
        if INVITE_FORME and d in COULEURS and m.L[d] + part.L[d] >= 8 \
                and d not in [a.enchere[1:] for x, a in nos if x == s]:   # fit pas encore montré : la forme compte
            val = max(val, valeur_fit(m, d, part.L[d]))
        vul = "nous" in _VUL
        large = INVITE_LARGE is True or (INVITE_LARGE == "vul" and vul)
        if hi < 40 and not (large and hi - lo > 6): maxi = val >= (lo + hi) / 2 - (INVITE_MILIEU_VUL if vul else 0)
        else:                                              # zone ouverte ou large (12–21) : compter ensemble
            maxi = val + part.pts[0] >= SEUIL_MANCHE[d] - (INVITE_VUL if vul else 0)
        if dp.nature == "choix":
            M = dp.atout
            return Appel(e(4, M), f"3 cartes à {M}", nature="conclusion") if m.L[M] >= 3 else Appel("passe", f"pas 3 cartes à {M}")
        if dp.enchere == "4SA": return Appel("6SA", "maximum, accepte le chelem", nature="conclusion") if maxi else Appel("passe", "minimum")
        if d == "SA" and getattr(dp, "atout", None) and m.L[dp.atout] >= 3:
            M = dp.atout
            return Appel(e(4 if maxi else 3, M), "3 cartes à " + M, nature="conclusion")
        if maxi:
            cible = e(MANCHE[d], d)
            if rang(cible) > rang(dernier): return Appel(cible, "accepte l'invitation", nature="conclusion")
        return Appel("passe", "refuse l'invitation")

    # couleur du contrat
    fits = [c for c in COULEURS if m.L[c] + part.L[c] >= 8]
    majs = [c for c in fits if c in MAJEURES]
    if majs: d = max(majs, key=lambda c: m.L[c] + part.L[c])
    elif m.reguliere or part.reguliere or not fits: d = "SA"
    else: d = max(fits, key=lambda c: m.L[c] + part.L[c])
    mes = m.dh(d) if d != "SA" and m.L[d] < part.L[d] else m.hl
    tmin, tmax = mes + part.pts[0], mes + min(part.pts[1], 37)
    seuil = SEUIL_MANCHE[d]
    if d in "♦♣" and tmax >= 25 and tmin < 29:
        d, seuil = "SA", 25                         # mineure : préférer 3SA (ou l'inviter)

    if tmin >= PETIT_CHELEM:
        if d == "SA":
            cible = "7SA" if tmin >= GRAND_CHELEM else "6SA"
            return Appel(cible, "chelem à SA" , nature="conclusion") if rang(cible) > rang(dernier) else Appel("passe", "")
        if rang("4SA") > rang(dernier):
            return Appel("4SA", f"Blackwood 3041, atout {d}", nature="blackwood", atout=d)
    cible_manche = e(MANCHE[d], d)
    if tmin >= seuil:
        if rang(cible_manche) > rang(dernier): return Appel(cible_manche, "manche", nature="conclusion")
        return Appel("passe", "manche atteinte")
    if tmax >= seuil and (tmin >= seuil - 3 or (tmin + tmax) / 2 >= seuil - 2):
        inv = e(MANCHE[d] - 1, d)
        if rang(inv) > rang(dernier): return Appel(inv, "invitation à la manche", (moi_pts(m, moi), moi_pts(m, moi) + 2), nature="invite")
        return Appel("passe", "trop haut pour inviter")
    # partielle : rester dans le fit s'il y en a un
    if fits: d = majs and d if majs else max(fits, key=lambda c: m.L[c] + part.L[c])
    if not fits and d == "SA" and not m.reguliere:      # sans fit : rejouer sa couleur longue
        c = m.longue()
        n = S.plus_bas(c, dernier)
        if m.L[c] >= 5 and c not in (dernier or "")[1:] and n <= 3 and not adverse:
            return Appel(e(n, c), f"sans fit, {m.L[c]} cartes à {c}", L={c: m.L[c]}, nature="conclusion")
    if adverse:                                     # concurrence : loi des levées totales
        if not fits or d == "SA": return Appel("passe", "pas de fit pour disputer la partielle")
        total = m.L[d] + part.L[d]; n = S.plus_bas(d, dernier)
        bonus = LOI_FAV if ("nous" not in _VUL and "eux" in _VUL) else -LOI_DEF if ("nous" in _VUL and "eux" not in _VUL) else 0
        if n <= min(total - 6 + bonus, 3) and rang(e(n, d)) < rang(e(MANCHE[d], d)):
            return Appel(e(n, d), f"loi des levées : {total} atouts, on dispute au palier {n}", nature="conclusion")
        return Appel("passe", "laisse jouer l'adversaire")
    if dernier[1:] == d or (d == "SA" and dernier[1:] in MAJEURES and part.L[dernier[1:]] >= 5):
        return Appel("passe", "partielle atteinte")
    if dernier[1:] in fits: return Appel("passe", "partielle dans le fit")
    cible_manche = e(MANCHE[d], d)
    n = S.plus_bas(d, dernier)
    if n <= (2 if d == "SA" else 3) and rang(e(n, d)) < rang(cible_manche):
        return Appel(e(n, d), "partielle", nature="conclusion")
    return Appel("passe", "partielle, rien de mieux")
