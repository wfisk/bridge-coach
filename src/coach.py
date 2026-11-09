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


def _tete(x):
    """Les honneurs de tête qui se suivent depuis l'as dans une couleur (« AR8 » -> 2, « RD5 » -> 0)."""
    k = 0
    for r in "ARDVX":
        if r in x: k += 1
        else: break
    return k


def _sequence(x):
    """La tête de séquence d'une couleur (deux honneurs qui se suivent parmi A R D V), ou None : « RD843 » -> « R »."""
    for h, h2 in zip("ARDV", "RDVX"):
        if h in x and h2 in x: return h
    return None


def conseil_defense(d, contrat, decl, entame, encheres):
    """Le conseil du coach à la défense, vu de l'entameur une fois le mort étalé, en quelques phrases : le compte d'après
    les enchères ; la couleur d'entame (ne pas offrir une coupe au mort) ; la course quand le mort a une longue qui
    fournira des défausses (changer tout de suite pour sa meilleure séquence) ; sinon l'atout contre les coupes, ou
    attendre. Il ne voit que sa main, le mort et les enchères."""
    if not entame or contrat == "passe": return ""
    mort = PART[decl]; g = LHO[decl]; part = PART[g]
    den = contrat.rstrip("X")[1:]; atout = den if den in COULEURS else None
    try:
        p = _modele(d, g, encheres, [(g, entame["carte"])], mort=mort).prediction()
    except Exception:
        return ""
    if p.get("efficace", 0) < 8: return ""
    s_moi, s_mort = jeu.suites(d["mains"][g]), jeu.suites(d["mains"][mort])
    c0, h0 = entame["carte"][0], entame["carte"][1:].replace("10", "X")
    phrases = [f"{NOMS[g]} compte : le déclarant {_pts(p, decl)}, {NOMS[part]} {_pts(p, part)}."]
    # la couleur d'entame : après les levées de tête, le mort coupe-t-il ?
    tetes = _tete(s_moi[c0])
    if atout and c0 != atout and s_mort.get(atout) and 0 < len(s_mort[c0]) <= tetes:
        cartes = " et ".join(f"{c0}{r}" for r in s_moi[c0][:len(s_mort[c0])])
        phrases.append(f"Après {cartes}, ne pas jouer un {'troisième' if len(s_mort[c0]) == 2 else 'autre'} {c0} : le mort coupe.")
    elif atout and c0 != atout and s_mort.get(atout) and len(s_mort[c0]) == 0:
        phrases.append(f"Le mort n'a plus de {c0} : ne pas continuer la couleur, il couperait.")
    # à sans-atout : sa longue est l'arme ; la continuer à chaque prise de main, et garder ses reprises pour l'encaisser
    if not atout and len(s_moi[c0]) >= 5:
        reprises = [f"{c}{r}" for c in COULEURS if c != c0 for r in s_moi[c][:1] if r in "AR"]
        phrases.append(f"La longue de {NOMS[g]} à {c0} est l'arme de la défense : la rejouer à chaque prise de main pour "
                       "l'affranchir" + (f", et garder ses reprises ({', '.join(reprises)}) pour l'encaisser." if reprises else "."))
    # la course : une longue du mort qui fournira des défausses (ou des levées à SA), si le camp du déclarant en a les têtes
    def menace(c):
        tetes_camp = sum(h in s_mort[c] for h in "ARD") + sum(p[decl]["cartes"].get((c, h), 0) for h in "ARD" if h not in s_mort[c])
        return len(s_mort[c]) >= 4 and tetes_camp >= 1.7   # 07/11 : 1,9 et 1,8 vraies menaces, 1,6 non
    longue = max((c for c in COULEURS if c != atout and c != c0 and menace(c)), key=lambda c: len(s_mort[c]), default=None)
    if longue and not atout:
        n = len(s_mort[longue])
        phrases.append(f"Le mort a {NOMBRES.get(n, n).replace('une', 'un') if n < 5 else n} {jeu.NOM_C[longue]} qui donneront des "
                       "levées au déclarant : la défense doit affranchir les siennes avant.")
    elif longue:
        n = len(s_mort[longue])
        phrases.append(f"Le mort a {NOMBRES.get(n, n).replace('une', 'un') if n < 5 else n} {jeu.NOM_C[longue]} : une fois "
                       f"affranchis, ils donneront {'une défausse' if not atout or n == 4 else 'des défausses'} au déclarant ; "
                       "la défense doit prendre ses levées avant.")
        sequences = [c for c in COULEURS if c not in (atout, longue) and _sequence(s_moi[c])
                     and not any(h in s_mort[c] for h in "ARDV"[:"ARDV".index(_sequence(s_moi[c]))])]
        if c0 in sequences and len(sequences) > 1: sequences.remove(c0)
        if sequences:
            c = max(sequences, key=lambda c: len(s_moi[c]))
            h = _sequence(s_moi[c]); h2 = "ARDVX"["ARDV".index(h) + 1]
            phrases.append(f"Changer tout de suite pour {ART[h]}{c}{h}, pour affranchir {ART[h2] if h2 != 'X' else 'le '}{c}{h2} avant.")
        else:
            phrases.append("Encaisser ses levées dès que possible.")
    elif not atout: pass                                   # à SA, la longue d'entame a déjà dit le plan
    elif atout and any(len(s_mort[c]) <= 1 for c in COULEURS if c != atout) and len(s_mort.get(atout, "")) >= 2:
        court = [c for c in COULEURS if c != atout and len(s_mort[c]) <= 1]
        phrases.append(f"Le mort est court à {' et à '.join(court)} avec des atouts : rejouer atout à chaque prise de main, "
                       "pour réduire ses coupes.")
    else:
        phrases.append("Le mort n'a ni longue ni coupe : rien ne presse, laisser le déclarant ouvrir les couleurs.")
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


MOT = ((.9, "presque sûr"), (.7, "probable"), (.4, "ouvert"), (.15, "difficile"), (0, "très difficile"))
NOMBRES = {1: "une", 2: "deux", 3: "trois", 4: "quatre"}
COULEUR_DE = {v: k for k, v in jeu.NOM_C.items()}          # « Piques » -> ♠


def _action(e, c_imp):
    """Une étape du plan (texte de jeu.compter_plan) en quelques mots du joueur : (couleur ou None, action ou None, phrase
    entière à garder telle quelle ou None). c_imp : les impasses dont le coach donne la chance, à ne pas redire."""
    import re
    m = re.match(r"<b>([^<]+?) ?:</b>\s*(.*)", e)
    if not m: return None, None, re.sub(r"<[^>]+>", "", e)
    titre, reste = m[1], m[2].rstrip(".")
    c = COULEUR_DE.get(titre.lower())
    if titre == "Atout":
        return "atout", re.sub(r" \(il en restera assez pour couper\)", "", reste.split(" : ")[-1].split(".")[0]), None
    if titre == "Coupes": return None, f"couper {reste}", None
    if titre == "Premier pli": return None, "au premier pli, " + reste[0].lower() + reste[1:], None
    if titre in ("En réserve", "Levée manquante", "Levées manquantes"): return "reserve", reste, None
    if c:
        if reste.startswith("les affranchir"): return c, f"affranchir les {c}", None
        if reste.startswith("céder la main"): return c, f"céder un {c} pour affranchir la couleur", None
        if reste.startswith("à attaquer"): return c, f"jouer les {c}", None
        if reste.startswith("à couper"): return c, f"couper les {c}" + reste[len("à couper"):], None
        if "impasse" in reste:
            h = re.search(r"a (?:le |la |l')([♠♥♦♣][ARDV])", reste)
            return c, f"faire l'impasse au {h[1]}" if h else f"faire l'impasse à {c}", None
        if reste.startswith("attention au blocage"): return c, None, f"Attention au blocage à {c} : " + reste.split(". ", 1)[-1] + "."
        return c, f"jouer les {c} ({reste.split('.')[0]})", None
    return None, None, re.sub(r"<[^>]+>", "", e).rstrip(".") + "."


def redaction_plan(d, contrat, decl, entame, encheres):
    """Le plan de jeu du programme, rédigé par le coach en quelques phrases, comme un avis : le verdict (et l'enjeu, ou
    ce qui manque), le plan dans l'ordre de jeu, la chance qui reste quand il manque des levées, puis ce que disent les
    enchères. Les morceaux viennent de jeu.plan_de_jeu(parties=True) : rien de nouveau n'est calculé."""
    import re
    p = jeu.plan_de_jeu(d, contrat, decl, entame, encheres, simuler=True, parties=True)
    a, inf = p["essai"], p["infos"]; need = inf.get("need", int(contrat[0]) + 6); reste = inf.get("reste", 0)
    taux = a["taux"] if a else (1 if reste <= 0 else .3)
    mot = next(m for x, m in MOT if taux >= x)
    pct = f" (environ {10 * round(taux * 10)} % sur nos essais)" if a and .15 <= taux < .9 else ""
    manque = f"il manque {NOMBRES.get(reste, reste)} levée{'s' if reste > 1 else ''}"
    phrases = []
    # 1. le verdict
    if inf.get("sa"):
        v = f"Contrat {mot}{pct} : {inf['ks']} levées sûres, il en faut {need}"
        if inf.get("k", 0) > inf["ks"]: v += f" ; {inf['k']} avec des partages normaux"
        v += f", {manque}." if reste > 0 else "."
    else:
        perd = inf.get("perdantes", "")                    # les perdantes, et ce qui s'en va : coupes au mort, défausses
        nc = sum((inf.get("coupes") or {}).values()); nd = inf.get("defausses", 0)
        if perd and nc: perd += f", dont {NOMBRES.get(nc, nc).replace('une', 'un')} à couper {inf.get('coupe_ou', 'au mort')}"
        if perd and nd: perd += f" ; {NOMBRES.get(nd, nd)} défausse{'s' if nd > 1 else ''} sur les {inf.get('defausse_sur', '')}"
        v = f"Contrat {mot}{pct}" + (f" : {manque}" if reste > 0 else "")
        v += f" (perdantes : {perd})." if perd and reste > 0 else "."
        if reste <= 0 and perd: v += f" Perdantes : {perd}."
    if reste <= 0 and a and taux >= .9 and a.get("levees", 0) >= need + .4 and need < 13:
        v = v[:-1] + f" ; l'enjeu est la {need + 1}e levée."
    if reste <= 0 and a and taux < .4:                     # le compte y est, l'essai dit non : dire pourquoi
        v += (" Le compte y est avec des partages normaux, mais il faut céder la main pour affranchir ses levées : la "
              "défense a le temps de prendre les siennes d'abord.")
    phrases.append(v)
    # 2. le plan, dans l'ordre de jeu
    c_ = conseil_plan(d, contrat, decl, entame, encheres, sans_impasse="ne dépend pas d'une impasse" in (p["fin"] or ""), morceaux=True)
    actions, a_part, reserve, a_affranchir = [], [], [], []
    coupe = next((x for x in p["etapes"] if x.startswith("<b>Coupes")), None)
    for e in p["etapes"]:
        e = re.sub(r" \([NSEO] a montré [^)]*\)", "", e)
        c, act, entiere = _action(e, c_["impasses"])
        if c == "reserve": reserve.append(act); continue
        if c == "atout":                                   # l'ordre atout / coupes, tel que le compte l'a choisi
            act = re.sub(r" \(il en restera assez pour couper\)", "", inf.get("conseil") or act)
            if inf.get("en_tete"): act = act.replace("faire tomber les atouts", "tirer les atouts en tête, sans impasse")
        if c == "atout" and coupe:                         # « faire les coupes » : dire lesquelles, une seule fois
            act = act.replace("faire les coupes", _action(coupe, {})[1]).replace("faire d'abord les coupes", "d'abord " + _action(coupe, {})[1])
        elif e is coupe: continue
        if c and c in jeu.COULEURS and act and "affranchir" in act: a_affranchir.append(c)
        if act and act not in actions: actions.append(act)
        if entiere: a_part.append(entiere)
    fusion = []                                            # « jouer les ♣, jouer les ♦ » -> « jouer les ♣ et les ♦ »
    for act in actions:
        if fusion and act.startswith("jouer les ") and fusion[-1].startswith("jouer les ") and "(" not in act + fusion[-1]:
            fusion[-1] += " et les " + act[len("jouer les "):]
        else: fusion.append(act)
    actions = fusion
    if actions:
        plan = actions[0] if len(actions) == 1 else ", ".join(actions[:-1]) + ", puis " + actions[-1]
        phrases.append(plan[0].upper() + plan[1:] + ".")
    phrases += a_part
    dites_imp = set()
    # 3. la chance qui reste, quand il manque des levées : les impasses en réserve et les couleurs à affranchir
    if reste > 0:
        besoins = []
        for r in reserve:                                  # l'impasse en réserve, avec sa chance d'après les enchères
            for h in re.findall(r"a (?:le |la |l')([♠♥♦♣][ARDV])", r):
                ch = re.search(r"environ (\d+ %)", c_["impasses"].get(h[0], ("", ""))[0])
                besoins.append(f"réussir l'impasse au {h}" + (f" (d'après les enchères, environ {ch[1]})" if ch else ""))
                if ch: dites_imp.add(h[0])
        mort = PART[decl]
        for c in a_affranchir:                             # la couleur à affranchir : le partage qu'il faut
            n = len(jeu.suites(d["mains"][decl])[c] + jeu.suites(d["mains"][mort])[c])
            if 13 - n >= 4: besoins.append(f"trouver les {c} {jeu.partage_normal(13 - n)}")
        if besoins:
            ph = "Il faut " + (besoins[0] if len(besoins) == 1 else ", ".join(besoins[:-1]) + " et " + besoins[-1]) + "."
            if a and taux < .15: ph += " Même alors, une bonne défense trouve presque toujours la parade."
            phrases.append(ph)
        elif a and taux < .15: phrases.append("Contre une bonne défense, rien ne suffit : limiter la chute, ou compter sur une erreur.")
    # 4. ce que disent les enchères
    for c, (seule, courte) in c_["impasses"].items():
        if c not in dites_imp and not (reste > 0 and "rien dans les enchères" in seule.lower()):
            phrases.append(seule)
    phrases += [c_["points"]] + c_["honneurs"] + [c_["danger"]]
    return " ".join(x.strip() for x in phrases if x and x.strip())
