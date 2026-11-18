# -*- coding: utf-8 -*-
"""Le quiz de la démonstration (Jouer › Démo, l'interrupteur « Quiz ») : la démonstration s'arrête à un moment clé, la
classe répond, puis l'enseignant montre la réponse. Pour commencer, l'entame (l'utilisateur, 2026-11-16).

Une question est une donnée (un dict de textes et de cartes), sans écran : la même pourra être servie plus tard aux
téléphones des élèves. Elle ne contient que ce que voit le joueur qui décide (sa main, les enchères), puis la réponse et
son explication ; le double mort ne vient qu'après coup (apres_coup), comme dans les analyses.

    q = question_entame(m)       # m : demo.Demo ; None si la donne se passe
    q["pas"]                     # le pas de la démonstration où elle se pose (les enchères finies, l'entame pas encore jouée)
    q["choix"]                   # [{"carte": "♥4", "raison": …, "bonne": bool}], une carte par couleur
    apres_coup(m, q)             # ajoute à chaque choix les levées de la défense au double mort, et une phrase
"""
import re

import carte, jeu, jouer

QUI = {"N": "Nord", "E": "Est", "S": "Sud", "O": "Ouest"}


def _contrat_txt(contrat):
    """« 4♠X » -> « 4♠ contré »."""
    if contrat.endswith("XX"): return contrat[:-2] + " surcontré"
    if contrat.endswith("X"): return contrat[:-1] + " contré"
    return contrat


def question_entame(m):
    """La question d'entame de la démonstration m (demo.Demo), ou None (donne passée, pas d'entame)."""
    if not m.decl or not m.cartes: return None
    d, decl = m.d, m.decl
    meneur = jeu.LHO[decl]
    den = m.contrat[1:].rstrip("X")
    main = jeu.suites(d["mains"][meneur])
    nommees = jeu.couleurs_nommees(m.seq, d["donneur"])
    bonne = carte.carte_fr(*m.cartes[0])                     # l'entame que la démonstration joue ensuite (les règles)
    raison = (m.pensees[0].get("entame") or "") if m.pensees else ""
    choix = []
    for c in jeu.COULEURS:                                   # une carte par couleur : celle qu'on y entamerait
        p = main[c]
        if not p: continue
        if c == bonne[0]:
            x, r = bonne[1:], "la carte des règles d'entame"
        elif c in nommees[jeu.PART[meneur]]:
            x, r = jeu.carte_partenaire(p, den), "dans la couleur du partenaire"
        else:
            x, r = jeu.carte_dans(p)
            if len(p) == 3 and r.startswith("4e meilleure"): r = "la plus petite, sous un honneur"
        choix.append(dict(carte=c + x, raison=r, bonne=c + x == bonne))
    return dict(id="entame", type="entame", pas=m.n_encheres, siege=meneur,
                voit=dict(main=d["mains"][meneur], encheres=list(m.seq), donneur=d["donneur"], vul=d.get("vul")),
                question=f"Vous êtes {QUI[meneur]}. {QUI[decl]} joue {_contrat_txt(m.contrat)}. Quelle est votre entame ?",
                choix=choix, reponse=bonne, chute=14 - (int(m.contrat[0]) + 6),   # levées de défense pour la chute
                explication=raison,
                lecture=jeu.lecture_entame(d, m.contrat, decl, m.seq, nommees, bonne[0]) if m.seq else "")


ALTERNATIVE = re.compile(r"\.?\s*(\d(?:SA|[♣♦♥♠])|passe|contre|surcontre) \(([^)]*)\) convenait aussi, mais vient après dans le système")


def questions_encheres(m, nb=2):
    """Les décisions d'enchères serrées de la démonstration m (2026-11-18, l'utilisateur : le quiz après l'entame) : un
    appel de la séquence recommandée pour lequel le moteur dit qu'un autre « convenait aussi ». Au plus nb questions, les
    plus hautes d'abord gardées, puis dans l'ordre des enchères. Chacune : pas = le nombre d'appels déjà faits, siege =
    celui qui parle, voit = sa main et les enchères jusque-là, choix = l'appel recommandé et l'autre (« bonne » marque
    le premier), explication = la raison du coach."""
    out = []
    i0 = jeu.ROT.index(m.d["donneur"]) if hasattr(jeu, "ROT") else "NESO".index(m.d["donneur"])
    for i, (appel, texte) in enumerate(zip(m.seq, m.explications)):
        if appel == "passe" or not texte: continue
        alts = [(a, sens) for a, sens in ALTERNATIVE.findall(texte) if a != appel]
        if not alts: continue
        siege = "NESO"[(i0 + i) % 4]
        raison = ALTERNATIVE.sub("", texte).strip().rstrip(".")
        choix = sorted([dict(carte=appel, raison=raison, bonne=True)] + [dict(carte=a, raison=sens, bonne=False) for a, sens in alts[:2]],
                       key=lambda x: _rang(x["carte"]))
        out.append(dict(id=f"enchere-{i}", type="enchere", pas=i, siege=siege,
                        voit=dict(main=m.d["mains"][siege], encheres=list(m.seq[:i]), donneur=m.d["donneur"], vul=m.d.get("vul")),
                        question=f"Vous êtes {QUI[siege]}. Que dites-vous ?", choix=choix, reponse=appel,
                        explication=raison, alternatives=[f"{a} ({sens})" for a, sens in alts[:2]]))
    out = sorted(sorted(out, key=lambda q: -_rang(q["reponse"]))[:nb], key=lambda q: q["pas"])
    return out


def _rang(appel):
    """L'ordre des appels : passe, puis 1♣ … 7SA, puis contre et surcontre."""
    if appel == "passe": return 0
    if appel in ("contre", "surcontre", "X", "XX"): return 99
    return int(appel[0]) * 5 + "♣♦♥♠S".index(appel[1]) if appel[0].isdigit() else 50


def questions(m):
    """Toutes les questions de la démonstration m, dans l'ordre où elles se posent : les décisions d'enchères serrées,
    puis l'entame."""
    q = questions_encheres(m)
    e = question_entame(m)
    return q + ([e] if e else [])


def apres_coup(m, q):
    """Ajoute le double mort de chaque choix (levées de la défense, « levees ») et une phrase (q["apres_coup"]) :
    ce que l'entame donne si l'on voit les quatre mains. Une phrase vide si le solveur manque."""
    if not q or q.get("apres_coup") is not None: return q
    if q.get("type") != "entame": q["apres_coup"] = ""; return q   # une enchère : pas de double mort à montrer
    v = jeu.levees_par_entame(m.d["mains"], m.contrat[1:].rstrip("X"), m.decl)
    q["apres_coup"] = ""
    if not v: return q
    for x in q["choix"]: x["levees"] = v.get(x["carte"])
    connus = [x for x in q["choix"] if x.get("levees") is not None]
    bon = next((x for x in connus if x["bonne"]), None)
    if not bon: return q
    meilleur = max(x["levees"] for x in connus)
    if bon["levees"] == meilleur:
        q["apres_coup"] = "Au double mort, c'est aussi la meilleure entame."
    else:
        mieux = [x["carte"] for x in connus if x["levees"] == meilleur]
        q["apres_coup"] = (f"Au double mort, {jeu.lister(mieux)} {'faisait' if len(mieux) == 1 else 'faisaient'} mieux "
                           f"({meilleur} levée{'s' if meilleur > 1 else ''} pour la défense au lieu de {bon['levees']}) : "
                           "on ne pouvait pas le savoir en voyant sa seule main.")
        if meilleur >= q["chute"] > bon["levees"]:
            q["apres_coup"] += " Celle-là faisait chuter le contrat."
    return q


def texte_levees(q, x):
    """« 4 levées, chute » : ce que donne le choix x pour la défense, au double mort ; "" sans double mort."""
    t = x.get("levees")
    if t is None: return ""
    return f"{t} levée{'s' if t > 1 else ''}" + (", chute" if t >= q["chute"] else "")
