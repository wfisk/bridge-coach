# -*- coding: utf-8 -*-
"""Le conseil du coach : ce que le programme ajoute, à la table, après son plan, sa défense et ses enchères.

Il voit ce qu'un joueur voit à la table : le déclarant sa main, le mort, l'entame et les enchères ; le défenseur sa main,
le mort et les enchères. Les mains cachées viennent du modèle (modele.py) : des donnes imaginées fidèles aux enchères et
à l'entame, pondérées. Jamais la donne réelle, jamais le double mort. Le texte suit build_pdf.MARQUE_COACH.

    conseil_plan(d, contrat, decl, entame, encheres)     -> texte ou "" (le déclarant)
    conseil_defense(d, contrat, decl, entame, encheres)  -> texte ou "" (l'entameur, le mort étalé)
    conseil_encheres(r)                                  -> texte ou "" (les décisions serrées du moteur ; pas dans
                                                           l'analyse standard : ses explications les disent déjà)
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


def conseil_plan(d, contrat, decl, entame, encheres, sans_impasse=False, morceaux=False):
    """Le conseil du coach au déclarant : les points des défenseurs, la chance de chaque impasse d'après les enchères,
    la place probable des honneurs qui manquent, et à SA la main dangereuse. sans_impasse : le plan dit déjà que le
    contrat ne dépend pas d'une impasse ; les impasses que les enchères ne départagent pas ne se disent pas.
    morceaux=True : {"points", "impasses": {couleur: (phrase seule, phrase courte après l'étape du plan)}, "honneurs",
    "danger"}, pour que redaction_plan place chaque impasse après l'étape qui la propose."""
    vide = {"points": "", "impasses": {}, "honneurs": [], "danger": ""}
    if not entame or contrat == "passe": return vide if morceaux else ""
    mort = PART[decl]; g, dr = LHO[decl], RHO[decl]
    try:
        p = _modele(d, decl, encheres, [(g, entame["carte"])], mort=mort).prediction()
    except Exception:
        return vide if morceaux else ""
    if p.get("efficace", 0) < 8: return vide if morceaux else ""   # trop peu de donnes imaginées comptent : rien de sûr
    den = contrat.rstrip("X")[1:]
    s_dec, s_mort = jeu.suites(d["mains"][decl]), jeu.suites(d["mains"][mort])
    out = dict(vide, impasses={}, honneurs=[])
    a_parle = {x for x in _parleurs(encheres, d["donneur"]) if x}
    if a_parle & {g, dr}:
        out["points"] = f"Les enchères donnent à {NOMS[g]} {_pts(p, g)} et à {NOMS[dr]} {_pts(p, dr)}."
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
                if sans_impasse: continue
                pron = "les" if len(hs) > 1 else "la" if hs == "D" else "le"
                out["impasses"][c] = (f"L'impasse à {c} demande {noms} en {NOMS[qui]} : rien dans les enchères ne {pron} place ; "
                                      "tentez d'abord les autres chances et gardez-la pour la fin.",
                                      f"Rien dans les enchères ne {pron} place : gardez cette impasse pour la fin.")
                continue
            out["impasses"][c] = (f"L'impasse à {c} demande {noms} en {NOMS[qui]} : d'après les enchères, environ {POURCENT(q)} ; {avis}.",
                                  f"D'après les enchères, elle réussit environ {POURCENT(q)} du temps : {avis}.")
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
                out["honneurs"].append(f"{ART[h].capitalize()}{c}{h} est plutôt en {NOMS[x]} (environ {POURCENT(q)}).")
    if den == "SA" and int(contrat[0]) <= 3:               # la main dangereuse : celle qui affranchit sa longue (au chelem,
        c = entame["carte"][0]                             # céder la main, c'est chuter : rien à dire)
        L = p[g]["L"][c][1]; q5 = sum(v for k, v in L.items() if k >= 5)
        if q5 >= .6:
            out["danger"] = (f"Main dangereuse : {NOMS[g]}, qui a sans doute cinq cartes à {c} ou plus ({POURCENT(q5)}) : "
                             f"s'il faut céder la main, la céder à {NOMS[dr]}.")
    if morceaux: return out
    return " ".join([out["points"]] + [x[0] for x in out["impasses"].values()] + out["honneurs"] + [out["danger"]]).strip()


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
    phrases = [f"Le compte, vu de {NOMS[g]} : {h_moi} H en main, {h_mort} au mort, le déclarant {_pts(p, decl)} : "
               f"{NOMS[part]} a {_pts(p, part)}."]
    longue = None                                          # une longue du mort qui va donner des défausses
    for c in COULEURS:
        if c == den: continue
        x = s_mort[c]
        if len(x) >= 5 and sum(h in x for h in "ARD") >= 2: longue = c
        elif len(x) >= 4 and all(h in x for h in "ARD"): longue = c
    court = [c for c in COULEURS if c != den and den in COULEURS and len(s_mort[c]) <= 1 and len(s_mort.get(den, "")) >= 2]
    if longue:
        phrases.append(f"Le mort a une longue à {longue} qui fournira des défausses : prendre ses levées vite, avant qu'elle soit prête.")
    elif court:
        phrases.append(f"Le mort est court à {' et à '.join(court)} avec des atouts : rejouer atout à chaque prise de main.")
    else:
        phrases.append("Ni longue ni coupe au mort : rien ne presse, laisser le déclarant ouvrir les couleurs.")
    return " ".join(phrases)


def conseil_encheres(r):
    """Le conseil du coach sur les enchères : les appels où le système en offrait deux (le moteur le dit dans son
    explication : « … convenait aussi, mais vient après dans le système »), en une phrase chacun. r : encheres.encherir."""
    import re
    out = []
    for s, b, x in r.get("explications") or []:
        m = re.search(r"(\S+) \(([^)]*)\) convenait aussi", x or "")
        if m and b != "passe":
            out.append(f"{NOMS.get(s, s)} {b} plutôt que {m[1]} ({m[2]})")
    if not out: return ""
    return ("Décision serrée" if len(out) == 1 else "Décisions serrées") + " (l'autre enchère vient après dans le système) : " \
        + " ; ".join(out) + "."


def redaction_plan(d, contrat, decl, entame, encheres):
    """Tout le plan de jeu du programme, rédigé par le coach comme un avis : le verdict de l'essai à la table et ce qui
    décide, le compte, l'ordre de jeu, chaque étape en une phrase, puis ce que disent les enchères (conseil_plan).
    Les morceaux viennent de jeu.plan_de_jeu(parties=True) : rien de nouveau n'est calculé, tout est dit autrement."""
    import re, lignes
    p = jeu.plan_de_jeu(d, contrat, decl, entame, encheres, simuler=True, parties=True)
    a = p["essai"]; phrases = []
    if a:                                                  # 1. le verdict : l'essai à la table, plus sûr que le compte seul
        mot = next(m for x, m in lignes.CHANCE if a["taux"] >= x)
        v = (f"Le contrat est {mot} : sur {a['n']} donnes imaginées, sans voir les mains adverses, il gagne environ "
             f"{10 * round(a['taux'] * 10)} % du temps")
        need = int(contrat[0]) + 6
        if a["decide"]: v += " ; ce qui décide : " + " ; ".join(a["decide"]) + "."
        elif a["taux"] >= .9 and a.get("levees", 0) >= need + .4 and need < 13:
            v += f" ; l'enjeu est la {need + 1}e levée."
        else: v += "."
        phrases.append(v)
    compte = re.sub(r"^<b>Compte :</b> [^.]*\.\s*", "", p["compte"]).strip()   # 2. le compte, sans redire le contrat
    if compte: phrases.append(compte[0].upper() + compte[1:])
    if a and a["ligne"]:                                   # 3. l'ordre le plus joué par le déclarant simulé
        ordre = ", puis ".join(lignes._dire(x) for x in a["ligne"])
        phrases.append(f"Le déclarant simulé joue le plus souvent dans cet ordre : {ordre}.")
    sans = "ne dépend pas d'une impasse" in (p["fin"] or "")
    c_ = conseil_plan(d, contrat, decl, entame, encheres, sans_impasse=sans, morceaux=True)
    dites = set()
    for e in p["etapes"]:                                  # 4. chaque étape, une phrase ; l'impasse avec sa chance d'après
        e = re.sub(r" \([NSEO] a montré [^)]*\)", "", e)   # les enchères (le modèle), à la place de l'ancienne estimation
        m = re.match(r"<b>([^<]+?) ?:</b>\s*(.*)", e)
        t = f"{m[1]} : {m[2]}" if m else e
        for c, (seule, courte) in c_["impasses"].items():
            if c not in dites and "impasse" in t and c in t:
                t = t.rstrip() + " " + courte; dites.add(c)
        phrases.append(t)
    if p["fin"] and not (a and a["taux"] >= .9 and "tient" in p["fin"]): phrases.append(p["fin"])
    phrases += [c_["points"]] + [seule for c, (seule, _) in c_["impasses"].items() if c not in dites] + c_["honneurs"] + [c_["danger"]]
    return " ".join(x.strip() for x in phrases if x.strip())
