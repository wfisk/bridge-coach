# -*- coding: utf-8 -*-
"""Le conseil du coach : ce que le programme ajoute, à la table, après son plan, sa défense et ses enchères.

Il voit ce qu'un joueur voit à la table : le déclarant sa main, le mort, l'entame et les enchères ; le défenseur sa main,
le mort et les enchères. Les mains cachées viennent du modèle (modele.py) : des donnes imaginées fidèles aux enchères et
à l'entame, pondérées. Jamais la donne réelle, jamais le double mort. Le texte suit build_pdf.MARQUE_COACH.

    conseil_plan(d, contrat, decl, entame, encheres)     -> texte ou "" (le déclarant)
    conseil_defense(d, contrat, decl, entame, encheres)  -> texte ou "" (l'entameur, le mort étalé)
    conseil_encheres(r)                                  -> texte ou "" (les décisions serrées du moteur)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jeu
from jeu import COULEURS, PART, LHO, RHO

NOMS = {"N": "Nord", "S": "Sud", "E": "Est", "O": "Ouest"}
ART = {"A": "l'", "R": "le ", "D": "la ", "V": "le "}
NETTE = .65          # une place d'honneur se dit à partir de 65 % d'un côté
POURCENT = lambda p: f"{round(p * 20) * 5:.0f} %"     # par pas de 5 : le modèle n'est pas plus précis


def _modele(d, obs, encheres, jouees=(), mort=None):
    import modele
    return modele.Modele(d, obs, encheres, jouees, mort=mort, graine=7)


def _pts(p, x):
    moy, bas, haut = p[x]["H"]
    return f"{bas} H" if bas == haut else f"{bas} à {haut} H"


def conseil_plan(d, contrat, decl, entame, encheres):
    """Le conseil du coach au déclarant : les points des défenseurs, la chance de chaque impasse d'après les enchères,
    la place probable des honneurs qui manquent, et à SA la main dangereuse."""
    if not entame or contrat == "passe": return ""
    mort = PART[decl]; g, dr = LHO[decl], RHO[decl]
    try:
        m = _modele(d, decl, encheres, [(g, entame["carte"])], mort=mort)
        p = m.prediction()
    except Exception:
        return ""
    if p.get("efficace", 0) < 8: return ""                # trop peu de donnes imaginées comptent : rien de sûr à dire
    den = contrat.rstrip("X")[1:]
    s_dec, s_mort = jeu.suites(d["mains"][decl]), jeu.suites(d["mains"][mort])
    phrases = []
    a_parle = {x for i, x in enumerate(_parleurs(encheres, d["donneur"])) if x}
    if a_parle & {g, dr}:
        phrases.append(f"Les enchères donnent à {NOMS[g]} {_pts(p, g)} et à {NOMS[dr]} {_pts(p, dr)}.")
    vus = set()
    for c in COULEURS:                                     # les impasses du plan, et leur chance d'après les enchères
        for texte, hs, qui in jeu.impasses((decl, s_dec), (mort, s_mort), c):
            q = 1.0
            for h in hs: q *= p[qui]["cartes"].get((c, h), 0)
            vus.update((c, h) for h in hs)
            noms = " et ".join(f"{ART[h]}{c}{h}" for h in hs)
            if q >= NETTE: avis = "faites-la"
            elif q <= 1 - NETTE: avis = "cherchez d'abord une autre ligne (jeu en tête, mise en main, défausse)"
            else:
                phrases.append(f"L'impasse à {c} demande {noms} en {NOMS[qui]} : rien dans les enchères ne {'les' if len(hs) > 1 else 'la' if hs == 'D' else 'le'} "
                               "place ; tentez d'abord les autres chances et gardez-la pour la fin.")
                continue
            phrases.append(f"L'impasse à {c} demande {noms} en {NOMS[qui]} : d'après les enchères, environ {POURCENT(q)} ; {avis}.")
    for c in COULEURS:                                     # les honneurs qui manquent ailleurs : de quel côté ?
        nous = s_dec[c] + s_mort[c]
        if len([h for h in "ARDV" if h in nous]) < 2: continue
        for h in "ARD":
            if h in nous or (c, h) in vus or c + h == entame["carte"].replace("10", "X"): continue   # l'entame est connue
            if not any(h2 in nous for h2 in "ARDV"[("ARD".index(h)) + 1:]): continue   # rien en dessous à protéger
            qg = p[g]["cartes"].get((c, h), 0); qd = p[dr]["cartes"].get((c, h), 0)
            tot = qg + qd
            if tot < .5: continue                          # (une carte déjà jouée)
            x, q = (g, qg / tot) if qg >= qd else (dr, qd / tot)
            if q >= NETTE:
                phrases.append(f"{ART[h].capitalize()}{c}{h} est plutôt en {NOMS[x]} (environ {POURCENT(q)}).")
    if den == "SA" and int(contrat[0]) <= 3:               # la main dangereuse : celle qui affranchit sa longue (au chelem,
                                                           # céder la main, c'est chuter : rien à dire)
        c = entame["carte"][0]
        L = p[g]["L"][c][1]; q5 = sum(v for k, v in L.items() if k >= 5)
        if q5 >= .6:
            phrases.append(f"Main dangereuse : {NOMS[g]}, qui a sans doute cinq cartes à {c} ou plus ({POURCENT(q5)}) : "
                           f"s'il faut céder la main, la céder à {NOMS[dr]}.")
    return " ".join(phrases)


def _parleurs(encheres, donneur):
    """Pour chaque enchère, le siège qui l'a faite s'il a dit autre chose que passe (sinon None)."""
    rot = ["N", "E", "S", "O"]; i0 = rot.index(donneur)
    return [rot[(i0 + i) % 4] if b != "passe" else None for i, b in enumerate(encheres)]


def conseil_defense(d, contrat, decl, entame, encheres):
    """Le conseil du coach à la défense, vu de l'entameur une fois le mort étalé : le compte des points (le déclarant et le
    partenaire d'après les enchères), puis attaquer ou attendre selon le mort : une longue qui fournira des défausses, des
    coupes au mort, ou rien à craindre."""
    if not entame or contrat == "passe": return ""
    mort = PART[decl]; g = LHO[decl]; part = PART[g]
    den = contrat.rstrip("X")[1:]
    try:
        p = _modele(d, g, encheres, [(g, entame["carte"])], mort=mort).prediction()
    except Exception:
        return ""
    if p.get("efficace", 0) < 8: return ""
    s_moi, s_mort = jeu.suites(d["mains"][g]), jeu.suites(d["mains"][mort])
    h_moi = sum(jeu.PTS.get(r, 0) for c in COULEURS for r in s_moi[c]); h_mort = sum(jeu.PTS.get(r, 0) for c in COULEURS for r in s_mort[c])
    phrases = [f"Le compte, vu de {NOMS[g]} après le mort : {h_moi} H en main, {h_mort} au mort, le déclarant {_pts(p, decl)} "
               f"d'après les enchères : {NOMS[part]} a {_pts(p, part)}."]
    longue = None                                          # une longue du mort qui va donner des défausses
    for c in COULEURS:
        if c == den: continue
        x = s_mort[c]
        if len(x) >= 5 and sum(h in x for h in "ARD") >= 2: longue = c
        elif len(x) >= 4 and all(h in x for h in "ARD"): longue = c
    court = [c for c in COULEURS if c != den and den in COULEURS and len(s_mort[c]) <= 1 and len(s_mort.get(den, "")) >= 2]
    if longue:
        phrases.append(f"Le mort a une longue à {longue} qui va fournir des défausses au déclarant : la défense doit prendre "
                       "ses levées vite, en attaquant la couleur où elle peut en affranchir une avant que la longue ne soit prête.")
    elif court:
        phrases.append(f"Le mort est court à {' et à '.join(court)} avec des atouts : le déclarant voudra y couper ; "
                       "jouer atout à chaque prise de main réduit ces coupes.")
    else:
        phrases.append("Le mort n'a ni longue à affranchir ni coupe facile : rien ne presse, la défense peut attendre ses "
                       "levées et laisser le déclarant ouvrir les couleurs lui-même.")
    return " ".join(phrases)


def conseil_encheres(r):
    """Le conseil du coach sur les enchères : les appels où le système en offrait deux (le moteur le dit dans son
    explication : « … convenait aussi, mais vient après dans le système »), en une phrase chacun. r : encheres.encherir."""
    import re
    out = []
    for s, b, x in r.get("explications") or []:
        m = re.search(r"(\S+) \(([^)]*)\) convenait aussi", x or "")
        if m and b != "passe":
            out.append(f"{NOMS.get(s, s)} : {b} plutôt que {m[1]} ({m[2]}), que le système classe après.")
    if not out: return ""
    return ("Décision serrée : " if len(out) == 1 else "Décisions serrées : ") + " ".join(out)
