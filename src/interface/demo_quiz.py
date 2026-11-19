# -*- coding: utf-8 -*-
"""Démo et quiz (pour la classe), et Revoir : pas à pas, les moments clés.
Les noms de la page (état, fonctions de tous les modules de l'interface) sont dans F (interface.commun) :
fenetre.construire les y range à chaque ouverture de la page."""
from interface.commun import *  # noqa: F401,F403 — les outils communs et F


# ---------------------------------------------------------------- la démonstration (un cours sur grand écran)
def demo_de(c, d):
    """La démonstration de la donne (demo.Demo), gardée tant qu'on reste sur la même donne."""
    if F.jeu.get("demo_cle") != (c, d["n"]):
        import demo
        F.jeu.update(demo=demo.Demo(d, lire_analyses(c)), demo_cle=(c, d["n"]), pas=0, demo_msg="")
        background_tasks.create(F.demo_fond(F.jeu["demo"]))
    return F.jeu["demo"]


async def demo_fond(m):
    """Les robots jouent toute la donne d'avance, en tâche de fond, pendant que l'enseignant parle : ▶ n'attend plus
    (l'utilisateur, 2026-11-18 : Démo et Revoir étaient lents ; aucune pause ajoutée). Une carte à la fois ; « et si… »
    (essayer) repart de la carte jouée, et le calcul d'avance le suit."""
    t0 = time.monotonic(); n0 = len(m.cartes)
    while F.jeu.get("demo") is m and not m.fini():
        try:
            if not await run.io_bound(m.calculer, len(m.cartes)): break
        except Exception:
            break
    n = len(m.cartes) - n0
    if n > 4 and m.fini(): noter_temps(f"Démo : les {n} cartes calculées d'avance (en tout)", time.monotonic() - t0)


async def demo_aller(k):
    """Va au pas k (0 : rien d'annoncé) ; une carte pas encore jouée est calculée (les robots réfléchissent)."""
    m = F.jeu.get("demo")
    if not m or F.jeu.get("demo_occupe"): return
    k = max(0, k); avant = F.jeu.get("pas", 0)
    qz = F.quiz_de(m, avant)
    if qz and not F.quiz_revelee(qz) and avant >= qz["pas"] and k > qz["pas"]:
        await F.quiz_reveler(m); return                   # la question posée : ▶ montre d'abord la réponse
    if k == 0: F.jeu.update(quiz_reveles=set(), quiz_choix={})   # au début : les questions se reposent
    if k == avant + 1 and k <= m.n_pas() + 1:           # un pli fini reste sur la table tant qu'on en parle ; il part vers
        await F.demo_ramasser(m, avant)                   # son gagnant quand on avance (l'utilisateur, 2026-11-13)
    if k > m.n_pas():                                  # une carte de plus : le robot réfléchit
        j = k - m.n_encheres - 1
        if m.fini(): return
        q = m.position(len(m.cartes) - 1)
        F.jeu.update(demo_occupe=True, demo_msg=f"{SIEGE[q.au_trait()]} réfléchit…"); F.vue_jouer.refresh()
        try:
            ok = await run.io_bound(m.calculer, j)
        finally:
            F.jeu.update(demo_occupe=False, demo_msg="")
        if not ok: k = m.n_pas()
    F.jeu["pas"] = min(k, m.n_pas()); F.vue_jouer.refresh()


def quiz_liste(m):
    """Les questions de la démonstration m quand le quiz est mis (quiz.questions : les décisions d'enchères serrées, puis
    l'entame), gardées tant qu'on reste sur la même donne ; [] sinon."""
    if not lire_etat().get("demo_quiz") or not m: return []
    if F.jeu.get("quiz_cle") != F.jeu.get("demo_cle"):
        try: qs = quiz.questions(m)
        except Exception: qs = []
        F.jeu.update(quiz_liste=qs, quiz_cle=F.jeu.get("demo_cle"), quiz_reveles=set(), quiz_choix={})
    return F.jeu.get("quiz_liste") or []


def quiz_de(m, k=None):
    """La question en cours au pas k (par défaut le pas de la démonstration) : la première qui n'est pas encore passée."""
    k = F.jeu.get("pas", 0) if k is None else k
    return next((q for q in F.quiz_liste(m) if q["pas"] >= k), None)


def quiz_revelee(q):
    return bool(q) and q["id"] in (F.jeu.get("quiz_reveles") or set())


def quiz_en_attente(m, k):
    """Une question attend sa réponse et la démonstration n'est pas plus loin : on ne montre que ce que voit le joueur
    qui décide (sa main ; les autres mains de dos, pas de double mort)."""
    qz = F.quiz_de(m, k)
    return bool(qz) and not F.quiz_revelee(qz) and k <= qz["pas"]


def quiz_bas(m):
    """Qui est en bas pendant le quiz : l'entameur (la question de la fin), sinon le premier qui décide ; la table ne
    tourne pas d'une question à l'autre."""
    qs = F.quiz_liste(m)
    return (qs[-1]["siege"] if qs[-1]["type"] == "entame" else qs[0]["siege"]) if qs else None


async def quiz_reveler(m):
    """« Montrer la réponse » : la réponse du coach, pourquoi, puis pour l'entame le double mort de chaque choix."""
    qz = F.quiz_de(m)
    if not qz or F.jeu.get("demo_occupe"): return
    F.jeu.setdefault("quiz_reveles", set()).add(qz["id"])
    F.jeu.update(demo_occupe=True, demo_msg="Le coach regarde les quatre mains…" if qz["type"] == "entame" else ""); F.vue_jouer.refresh()
    try: await run.io_bound(quiz.apres_coup, m, qz)
    except Exception: qz["apres_coup"] = ""
    finally: F.jeu.update(demo_occupe=False, demo_msg="")
    F.vue_jouer.refresh()


def quiz_choisir(x):
    """L'enseignant marque la réponse de la classe (un second clic l'ôte)."""
    qz = F.quiz_de(F.jeu.get("demo"))
    if not qz: return
    ch = F.jeu.setdefault("quiz_choix", {})
    ch[qz["id"]] = None if ch.get(qz["id"]) == x else x; F.vue_jouer.refresh()


def bouton_quiz(m, qz, k):
    """Le quiz, bien en vue sous Jouer | Revoir | Démo (l'utilisateur, 2026-11-17 : l'interrupteur au-dessus de la table
    passait inaperçu). Mis, la démonstration s'arrête à l'entame et pose la question."""
    on = bool(lire_etat().get("demo_quiz"))
    def basculer():
        ecrire_etat(demo_quiz=not on); F.jeu.update(quiz_cle=None, quiz_reveles=set(), quiz_choix={}); F.vue_jouer.refresh()
    ui.button("Quiz : activé" if on else "Faire un quiz", icon="quiz", on_click=basculer) \
        .props(("unelevated" if on else "outline") + " no-caps color=amber-9" + ("" if on else " text-color=amber-10")) \
        .classes("text-base w-full") \
        .tooltip("Cliquer pour arrêter le quiz" if on else
                 "La démonstration s'arrête aux décisions serrées des enchères puis à l'entame : la classe ne voit que "
                 "la main de celui qui décide et répond, puis « Montrer la réponse ».")
    if on and not m.decl:
        ui.label("Cette donne se passe : pas d'entame, donc pas de question.").classes("text-base text-gray-700")
    elif on and qz and k < qz["pas"]:
        n_ = len(F.quiz_liste(m))
        ui.label(f"▶ : la {'prochaine ' if n_ > 1 else ''}question s'affichera ici"
                 + (f" ({n_} questions sur cette donne)." if n_ > 1 else ".")).classes("text-base text-gray-700")


def quiz_panneau(qz):
    """Dans la barre de droite, à la fin des enchères : la question, les choix en grandes cartes ; puis la réponse."""
    vu = F.quiz_revelee(qz); pris = (F.jeu.get("quiz_choix") or {}).get(qz["id"]); enchere = qz["type"] == "enchere"
    with ui.element("div").classes("w-full rounded-xl p-3").style(
            "background:var(--bc-highlight-bg-subtle,var(--bc-jaune-50));border:1px solid var(--bc-highlight-border-subtle,var(--bc-jaune-200))"):
        ui.html(f"<div style='font-size:18px;font-weight:700;line-height:1.35'>{rouge(qz['question'])}</div>", sanitize=False)
        with ui.element("div").classes("w-full mt-3").style("display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--sp-2)"):   # 4 cartes tiennent
            for x in qz["choix"]:
                c_ = x["carte"]; bord = "var(--bc-pique-600)" if c_ == pris else "var(--bc-tapis-200)"
                fond = ("var(--bc-trefle-100)" if x["bonne"] else "var(--bc-blanc)") if vu else ("var(--bc-pique-50)" if c_ == pris else "var(--bc-blanc)")
                if vu and x["bonne"]: bord = "var(--bc-trefle-600)"
                ui.button(on_click=lambda c_=c_: F.quiz_choisir(c_)).props("flat no-caps").style(
                    f"background:{fond};border:2px solid {bord};border-radius:10px;min-width:0;padding:6px 2px")                         .add_slot("default", f"<div style='font-size:24px;line-height:1.1;color:{'var(--bc-coeur-600)' if ('♥' in c_ or '♦' in c_) else 'var(--bc-tapis-900)'}'>"
                                         + (c_ if enchere else f"{c_[1:].replace('X', '10')}<br/>{c_[0]}") + "</div>")   # le rang au-dessus, comme sur une carte
        if not vu:
            ui.label("La classe répond ; un clic marque sa réponse.").classes("text-base text-gray-700 mt-2")
            ui.button("Montrer la réponse", icon="visibility", on_click=lambda: F.quiz_reveler(F.jeu.get("demo")))                     .props("unelevated no-caps").classes("text-base mt-2").set_enabled(not F.jeu.get("demo_occupe"))
            return
        bon = qz["reponse"]
        if pris: ui.html(f"<div style='font-size:var(--fs-titre);margin-top:10px'><b>{'Bravo !' if pris == bon else 'Pas tout à fait.'}</b> "
                         f"La classe a choisi {rouge(pris)}.</div>", sanitize=False)
        if enchere:
            ui.html(f"<div style='font-size:var(--fs-titre);margin-top:8px'><b>Le coach dit {rouge(bon)}.</b> {rouge(qz['explication'])}."
                    + "".join(f"<br/>Décision serrée : {rouge(a_)} convenait aussi." for a_ in qz.get("alternatives") or [])
                    + "</div>", sanitize=False)
            ui.label("▶ : les enchères continuent.").classes("text-base text-gray-700 mt-2")
            return
        ui.html(f"<div style='font-size:var(--fs-titre);margin-top:8px'><b>Le coach entame {rouge(bon)}.</b> {rouge(qz['explication'])}"
                + (f"<br/>{rouge(qz['lecture'])}" if qz.get("lecture") else "") + "</div>", sanitize=False)
        lignes = [f"{rouge(x['carte'])} : {quiz.texte_levees(qz, x)}" for x in qz["choix"] if quiz.texte_levees(qz, x)]
        if lignes or qz.get("apres_coup"):
            ui.html("<div style='font-size:16px;margin-top:8px;color:var(--bc-tapis-800)'><b>Après coup</b> (les quatre mains vues), "
                    "levées de la défense :<br/>" + " · ".join(lignes)
                    + (f"<br/>{rouge(qz['apres_coup'])}" if qz.get("apres_coup") else "") + "</div>", sanitize=False)
        ui.label("▶ : l'entame est jouée, la démonstration continue.").classes("text-base text-gray-700 mt-2")


async def demo_ramasser(m, k):
    """Le pas k a terminé un pli et l'on avance : la carte gagnante luit, puis les quatre cartes partent vers le joueur qui
    l'a gagné, comme dans Jouer ; ensuite seulement la carte suivante (l'utilisateur, 2026-11-13)."""
    c = k - m.n_encheres
    if c <= 0 or c % 4 or c >= 52: return
    q = m.position(c - 1)
    if not q.plis: return
    pli, g = q.plis[-1]
    F.jeu.update(demo_occupe=True, gagnante=next(((cc, r.translate(carte.FR)) for x_, cc, r in pli if x_ == g), None))
    try:
        F.vue_jouer.refresh(); await asyncio.sleep(.35)
        if F.jeu.get("pas") != k or F.jeu.get("demo") is not m: return
        F.jeu["ramasse"] = dict(zip(F.jeu.get("demo_places") or (), ("haut", "gauche", "droite", "bas"))).get(g, "bas")
        F.vue_jouer.refresh(); await asyncio.sleep(.45)
    finally:
        F.jeu.update(demo_occupe=False, gagnante=None, ramasse=None); F.vue_jouer.refresh()


async def demo_pli(k):
    """▶ : pendant le jeu, la carte suivante et, si elle est de votre camp (vous ou votre partenaire, le joueur du bas et
    celui d'en face), la carte de l'adversaire qui suit dans le même pli : une entame adverse seule, puis les deux cartes
    suivantes, puis la dernière (l'utilisateur, 2026-11-13 : moins de clics, mais pas tout le pli). Pendant les
    enchères : l'enchère suivante, que l'enseignant commente une à une."""
    m = F.jeu.get("demo")
    if not m or F.jeu.get("demo_occupe") or F.jeu.get("demo_suite"): return
    cible = k + 1                                     # Maj + → : jusqu'à la fin du pli (l'utilisateur, 2026-11-18 :
    if k >= m.n_encheres:                             # un seul pas sur → et le bouton ›, le pli entier au clavier)
        j = k - m.n_encheres                          # cartes déjà montrées
        cible = m.n_encheres + (j // 4 + 1) * 4
    F.jeu["demo_suite"] = True
    try:
        while F.jeu.get("pas", 0) < cible and F.jeu.get("demo") is m:
            avant = F.jeu.get("pas", 0)
            if avant >= m.n_pas() and m.fini(): break
            await F.demo_aller(avant + 1)
            if F.jeu.get("pas", 0) == avant: break        # plus rien à jouer
            # pas de pause ajoutée : elle ne sert qu'à Jouer, cartes cachées (l'utilisateur, 2026-11-13)
    finally:
        F.jeu["demo_suite"] = False; F.vue_jouer.refresh()


def revue_de(p, d, cartes):
    """La revue de la donne pour Revoir, calculée une fois en tâche de fond : chaque carte au double mort (ce qu'elle
    coûte : carte.analyse_jeu), la carte qui gardait la levée pour chaque carte coûteuse de votre camp, puis l'avis du
    coach sur chacune de vos cartes qui ne l'a pas encore (carte.avis_programme). Renvoie ce qui est déjà prêt."""
    r = F.jeu.get("revue")
    if r and r["p"] is p: return r
    r = F.jeu["revue"] = dict(p=p, a=None, mieux={})
    async def calcul():
        try:
            r["a"] = await run.io_bound(carte.analyse_jeu, d, p.contrat, p.decl, cartes)
            if F.jeu.get("revue") is r: F.vue_jouer.refresh()
            for x in r["a"]["cartes"]:
                if x["perte"] > 0 and p.camp(x["siege"]) == p.camp(p.humain):
                    r["mieux"][x["k"]] = await run.io_bound(carte.meilleure_carte, d, p.contrat, p.decl, cartes, x["k"])
            if F.jeu.get("revue") is r: F.vue_jouer.refresh()
            for z in p.pensees:                       # vos cartes : l'avis du coach, s'il n'a pas été gardé en jouant
                if F.jeu.get("revue") is not r: return
                if z.get("humain") and not z.get("avis") and 0 < z["n"] < len(cartes):
                    z["avis"] = await run.io_bound(carte.avis_programme, d, p.contrat, p.decl, p.encheres, p.humain, cartes, z["n"])
                    if F.jeu.get("revoir") == z["n"]: F.vue_jouer.refresh()
            F.jeu_garder()
        except Exception:
            pass
    background_tasks.create(calcul())
    return r


def moments_cles(p, cartes, r):
    """Les cartes qui ont compté, dans l'ordre : l'entame, chaque carte de votre camp qui a coûté une levée (cartes
    vues), chaque levée offerte par l'adversaire, les techniques que le coach nomme sur vos cartes, les coups.
    [(k, genre, texte)] ; genre : entame | perte | cadeau | coach | coup."""
    out = [(0, "entame", f"L'entame : {rouge(carte.carte_fr(*cartes[0]))} ({SIEGE[carte.LHO[p.decl]]})")]
    a = (r or {}).get("a") or {}
    for x in a.get("cartes") or []:
        if x["perte"] <= 0 or x["k"] == 0: continue
        if p.camp(x["siege"]) == p.camp(p.humain):
            out.append((x["k"], "perte", f"{rouge(x['carte'])} coûte {'une levée' if x['perte'] == 1 else str(x['perte']) + ' levées'}"))
        else:
            out.append((x["k"], "cadeau", f"{SIEGE[x['siege']]} offre une levée ({rouge(x['carte'])})"))
    for z in p.pensees:
        av = z.get("avis") if z.get("humain") else None
        if av and av.get("technique") and av["carte"] != z["carte"]:
            out.append((z["n"], "coach", f"Le coach : {rouge(av['carte'])}, {rouge(av['technique'][0])}"))
    for co in a.get("coups") or []:
        if co["type"] in ("squeeze", "mise en main"):
            out.append((co["k"], "coup", f"{co['type'].capitalize()} sur {SIEGE[co['joueur']]}"))
    vus, propre = set(), []
    for m in sorted(out, key=lambda m: m[0]):
        if (m[0], m[1]) in vus: continue
        vus.add((m[0], m[1])); propre.append(m)
    return propre


def bande_plis(p, cartes, r, k):
    """Les 13 plis en une bande : vert, gagné par votre camp ; gris, perdu ; un point rouge où une carte de votre camp a
    coûté une levée. Un clic va au début de ce pli ; le pli montré est encadré."""
    pertes = {x["pli"] for x in (((r or {}).get("a") or {}).get("cartes") or [])
              if x["perte"] > 0 and p.camp(x["siege"]) == p.camp(p.humain)}
    with ui.element("div").classes("w-full").style("display:grid;grid-template-columns:repeat(13,minmax(0,1fr));gap:3px"):
        for i, (pli, g) in enumerate(p.plis):
            gagne = p.camp(g) == p.camp(p.humain)
            ici = k // 4 == i
            fond = "var(--bc-trefle-500)" if gagne else "var(--bc-tapis-300)"
            bord = "2px solid var(--bc-noir)" if ici else "2px solid transparent"
            point = ("<span style='position:absolute;top:-3px;right:-3px;width:8px;height:8px;border-radius:50%;"
                     "background:var(--bc-coeur-600)'></span>") if i + 1 in pertes else ""
            ui.html(f"<div style='position:relative;height:24px;border-radius:4px;background:{fond};border:{bord};"
                    f"color:var(--bc-blanc);font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;"
                    f"cursor:pointer' title='Pli {i + 1}{' : gagné' if gagne else ' : perdu'}'>{i + 1}{point}</div>", sanitize=False) \
                .on("click", lambda i=i: F.revoir_aller(4 * i))


def revoir_aller(k):
    """Revoir : à la carte k (bornée)."""
    n = F.jeu.get("revoir_n") or 1
    F.jeu["revoir"] = max(0, min(n - 1, k)); F.vue_jouer.refresh()


async def revoir_pli(k, n):
    """Revoir, ▶ : les cartes jusqu'à la fin du pli en cours, une à une (k : la dernière carte montrée, n : le nombre de cartes)."""
    if F.jeu.get("revoir_suite"): return
    cible = min(n - 1, ((k + 1) // 4 + 1) * 4 - 1)
    F.jeu["revoir_suite"] = True
    try:
        if F.jeu.get("mode") == "revoir":              # tout le pli d'un coup : pas de pause ajoutée (2026-11-13)
            F.jeu["revoir"] = cible; F.vue_jouer.refresh()
    finally:
        F.jeu["revoir_suite"] = False


async def demo_essayer(m, j, x):
    """Double mort : l'enseignant joue une autre carte à la place de la carte j + 1 ; la suite repart de là."""
    try: await run.io_bound(m.essayer, j, x)
    except ValueError: return
    F.jeu["pas"] = m.n_encheres + j + 2; F.vue_jouer.refresh()
    background_tasks.create(F.demo_fond(m))           # la nouvelle suite se calcule d'avance, elle aussi


async def encheres_clavier(cle):
    """Enchérir au clavier, dans Jouer : un chiffre puis T K C P S (1 puis C = 1♥), Entrée = passe, X = contre,
    R = surcontre, Échap efface le chiffre tapé. Le chiffre attendu s'affiche sous la boîte (jeu["clavier"])."""
    if F.jeu.get("partie") or F.jeu.get("attend") or not F.jeu.get("d") or not F.jeu.get("cle") \
            or F.mode_de(F.jeu["cle"][0], F.jeu["d"]) != "jouer": return     # le mode montré, pas celui gardé
    d = F.jeu["d"]; k = cle.upper() if len(cle) == 1 else cle
    appel = None
    if k.isdigit() and "1" <= k <= "7":
        F.jeu["clavier"] = k; F.vue_jouer.refresh(); return
    if k == "Escape" and F.jeu.get("clavier"):
        F.jeu["clavier"] = None; F.vue_jouer.refresh(); return
    if k in F.COULEUR_TOUCHE and F.jeu.get("clavier"): appel = F.jeu["clavier"] + F.COULEUR_TOUCHE[k]
    elif k == "Enter": appel = "passe"
    elif k == "X": appel = "contre"
    elif k == "R": appel = "surcontre"
    if not appel: return
    F.jeu["clavier"] = None
    if appel not in jouer.legales(F.jeu["seq"], d["donneur"]):
        F.jeu["note"] = f"{appel} n'est pas possible ici."; F.vue_jouer.refresh(); return
    await F.jeu_annonce(d, appel)


async def demo_touche(e):
    """Le clavier : ← → (et Page précédente / suivante d'une télécommande de présentation) dans la démonstration ;
    les enchères au clavier dans Jouer (encheres_clavier)."""
    if not e.action.keydown or not F.sur_jouer(): return
    cle = e.key.name if hasattr(e.key, "name") else str(e.key)
    maj_ = bool(getattr(getattr(e, "modifiers", None), "shift", False))   # → : un pas (une carte) ; Maj + → : tout le pli (2026-11-18)
    if F.jeu.get("mode") == "revoir" and cle in ("ArrowRight", "PageDown", "ArrowLeft", "PageUp") and F.jeu.get("revoir_n"):
        k, n = F.jeu.get("revoir", 0), F.jeu["revoir_n"]
        if cle in ("ArrowRight", "PageDown") and maj_: await F.revoir_pli(k, n); return
        F.revoir_aller(k + (1 if cle in ("ArrowRight", "PageDown") else -1)); return
    if F.jeu.get("mode") != "demo": return await F.encheres_clavier(cle)
    if not F.jeu.get("demo"): return
    if cle in ("ArrowRight", "PageDown") and maj_: await F.demo_pli(F.jeu.get("pas", 0)); return
    if F.jeu.get("demo_suite"): return
    if cle in ("ArrowRight", "PageDown"): await F.demo_aller(F.jeu.get("pas", 0) + 1)
    elif cle in ("ArrowLeft", "PageUp"): await F.demo_aller(F.jeu.get("pas", 0) - 1)


def vue_demo(c, d, data):
    """Les quatre mains ouvertes, le déclarant en bas ; l'enseignant avance (→) et recule (←) dans les enchères recommandées,
    puis dans le jeu de la carte des robots ; la barre de droite dit ce que pense le joueur du pas montré. Double
    mort : sous chaque carte jouable, les levées du déclarant ; un clic sur une carte l'essaie."""
    m = F.demo_de(c, d)
    k = max(0, min(F.jeu.get("pas", 0), m.n_pas())); F.jeu["pas"] = k
    # les onglets prennent les flèches quand ils ont le focus : on le leur ôte, ← → restent à la démonstration
    ui.run_javascript("var a = document.activeElement; if (a && a.closest && a.closest('.q-tabs')) a.blur()")
    bas = F.siege_pour(c, d) or m.decl or "S"             # la même place en bas que dans Jouer et Revoir (l'utilisateur, 2026-11-11)
    qz = F.quiz_de(m, k); attente = F.quiz_en_attente(m, k)
    if F.quiz_bas(m): bas = F.quiz_bas(m)                    # le quiz : la classe est à la place de l'entameur
    if m.decl and bas == jouer.PART[m.decl] and k > m.n_encheres:
        bas = m.decl                                    # le mort n'est jamais en bas : dès l'entame, le déclarant passe devant vous
    vu = F.jeu.get("demo_bas_vu")                          # et la table tourne d'un demi-tour, comme dans Jouer
    if vu and vu[:2] == (c, d["n"]) and vu[2] != bas: F.jeu["tourne"] = time.monotonic()
    F.jeu["demo_bas_vu"] = (c, d["n"], bas)
    places = (jouer.PART[bas], jouer.ROT[(jouer.ROT.index(bas) + 1) % 4], jouer.ROT[(jouer.ROT.index(bas) + 3) % 4], bas)
    F.jeu["demo_bas"] = bas
    F.jeu["demo_places"] = places                         # pour ramasser le pli vers son gagnant (demo_ramasser)
    en_jeu = k > m.n_encheres                          # une carte au moins est jouée
    j = k - m.n_encheres - 1                           # la dernière carte montrée
    q = m.position(j) if m.decl and k >= m.n_encheres else None
    F.marques_dm.clear()
    voir_dm = F.jeu.get("demo_dm") and q is not None and not q.fini() and not attente   # la réponse ne se lit pas sur les cartes
    if voir_dm:
        v = m.dm(j)
        if v:
            best = (max if q.camp(q.au_trait()) else min)(v.values())
            F.marques_dm.update({(x[0], x[1].translate(carte.FR)): (t, t == best) for x, t in v.items()})
    jouables = set(F.marques_dm) if voir_dm else None
    clic = lambda y: F.demo_essayer(m, j, (y[0], y[1].translate(carte.EN)))
    with ui.row().classes("w-full no-wrap items-start gap-4").style(f"padding-right:{LARGEUR_PANNEAU}px"):
        with ui.column().classes("grow min-w-0 gap-2 relative"):
            def interrupteur_dm():                   # dès la fin des enchères : sous chaque carte jouable, le double mort
                if m.decl and k >= m.n_encheres and not attente:
                    ui.switch("Double mort", value=bool(F.jeu.get("demo_dm")),
                              on_change=lambda ev: (F.jeu.update(demo_dm=ev.value), F.vue_jouer.refresh())).classes("text-base") \
                        .tooltip("Sous chaque carte jouable : les levées du déclarant au double mort (en vert la meilleure). "
                                 "Un clic sur une carte l'essaie.")
            F.outils_table(d, extra=interrupteur_dm)
            if q is None or not en_jeu:                 # les enchères : les mains entières, les cartons sur la table
                def contenu(x, ou):
                    if attente and x != qz["siege"]:            # le quiz : les autres mains de dos
                        F.dos(ou, 13); return
                    if q is not None and voir_dm and x == q.au_trait():   # l'entame au double mort
                        F.eventail(F.mains_fr(d, x), jouables, clic, colonnes=ou in ("gauche", "droite"), cote=ou, grande=x == bas, depart=F.mains_fr(d, x))
                    else:
                        F.eventail(F.mains_fr(d, x), colonnes=ou in ("gauche", "droite"), cote=ou, grande=x == bas, depart=F.mains_fr(d, x))
                F.table(d, places, contenu, lambda: ui.html(F.tapis_encheres(d, places, m.seq[:k]), sanitize=False),
                      tour=None if k >= m.n_encheres else jouer.ROT[(jouer.ROT.index(d["donneur"]) + k) % 4],
                      clic=None if attente else (lambda: F.demo_aller(F.jeu.get("pas", 0) + 1)),
                      ouvert=not attente or (qz is not None and qz["siege"] in places[1:3]))   # le quiz : les autres
                                                       # mains de dos, à la place de Jouer ; ouverte si celui qui décide est
                                                       # sur un côté, sa main visible (2026-11-18). (leur nom
                                                       # juste au-dessus, pas en haut d'une place de main ouverte, 2026-11-17)
            else:
                pli = q.pos.pli or (q.plis[-1][0] if q.plis else [])   # un pli fini reste sur la table jusqu'au pas suivant
                posees = {x: (cc, r_.translate(carte.FR)) for x, cc, r_ in pli}
                bulles = {}                                 # au survol d'une carte du pli : pourquoi celle-là
                for idx in range((j // 4) * 4, j + 1):
                    z = m.pensees[idx]
                    bulles[z["siege"]] = (f"<b>{SIEGE[z['siege']]} {'entame' if idx == 0 else 'joue'} {rouge(z['carte'])}</b><br>"
                                          + (rouge(z["entame"]) if z.get("entame") else
                                             "La carte essayée : les robots reprennent de là." if z.get("essai") else
                                             rouge(carte.justification(z, m.decl))))
                def centre():
                    ui.html(f"<div style='position:absolute;inset:0;pointer-events:none'><div style='position:absolute;left:50%;top:50%;"
                            f"transform:translate(-50%,-50%);z-index:0'></div>"
                            f"{F.pli_cartes(q, places, posees, mort=q.mort(), bulles=bulles)}"
                            + F.rangees_plis(q, places, lambda x: x != q.mort())   # les plis gardés, comme dans Jouer (pas le mort)
                            + "</div>", sanitize=False)
                tour = None if q.fini() else q.au_trait()
                def contenu(x, ou):
                    reste = {kk: "".join(r_.translate(carte.FR) for r_ in vv) for kk, vv in q.pos.reste[x].items()}
                    jx = jouables if x == tour else None
                    if x == q.mort():
                        F.mort_etale(reste, jx, clic, q.den, ou,
                                   F.carte_posee(*posees[x], premiere=x == next(iter(posees), None), bulle=bulles.get(x, ""), cote=ou)
                                   if x in posees else "")
                    else:
                        F.eventail(reste, jx, clic, colonnes=ou in ("gauche", "droite"), cote=ou, grande=x == bas, depart=F.mains_fr(d, x))
                F.table(d, places, contenu, centre,
                      sur_table=[ou for x, ou in zip(places, ("haut", "gauche", "droite", "bas")) if x == q.mort()],
                      tour=tour, clic=lambda: F.demo_aller(F.jeu.get("pas", 0) + 1))   # un clic sur le tapis : un pas
        with F.panneau_droit():
            F.appliquer_plein()
            F.tete_donne(d)
            F.bouton_quiz(m, qz, k)
            fin = m.fini() and k >= m.n_pas()
            # les mêmes boutons de magnétoscope que Jouer (magneto), au même endroit ; ici ⏮ le début, ◀◀ un pas en
            # arrière, ▶ un pas en avant (l'utilisateur, 2026-11-11 : la même allure, pas forcément le même sens)
            libre = not fin and not F.jeu.get("demo_occupe") and not F.jeu.get("demo_suite")
            F.boutons_pas(lambda: F.demo_aller(0), lambda: F.demo_aller(k - 1), lambda: F.demo_aller(k + 1),
                        ok_debut=k > 0 and not F.jeu.get("demo_occupe"), ok_recul=k > 0 and not F.jeu.get("demo_occupe"),
                        ok_avance=libre, aide_avance=("Une carte (→ ; Maj + → : tout le pli)" if k >= m.n_encheres
                                                      else "L'enchère suivante (→)"))
            src = {"expert": "de l'Expert", "standard": "du Coach", "moteur": "du moteur"}[m.source]
            n_ = min(k, m.n_encheres); i0 = jouer.ROT.index(d["donneur"])
            grille_demo = lambda: ui.html(grille_html(jouer.grille(m.seq[:n_], d["donneur"]), d.get("vul"),
                                          sens={i: (jouer.ROT[(i0 + i) % 4], m.explications[i] if i < len(m.explications) else "", False)
                                                for i in range(n_)})
                                          .replace("border-collapse:collapse", "border-collapse:separate;border-spacing:4px 0"),
                                          sanitize=False)
            if F.jeu.get("demo_msg"): ui.label(F.jeu["demo_msg"]).classes("text-base pense")
            if k <= m.n_encheres:                       # les enchères : la grille seule, sur sa carte blanche (l'utilisateur,
                with ui.element("div").classes("w-full rounded-xl border border-gray-200 bg-white p-2"):   # 2026-11-11)
                    grille_demo()
                if qz and k == qz["pas"]:
                    F.quiz_panneau(qz)
                if k == m.n_encheres and m.notes and m.decl and not attente:     # la fin des enchères : l'avis de qui les recommande
                    ui.html(f"<div style='font-size:16px'><b>L'avis {src} :</b> {rouge(m.notes)}</div>", sanitize=False)
                if k == m.n_encheres and not m.decl:
                    ui.label("La donne se passe : rien à montrer au jeu de la carte.").classes("text-base")

            else:                                       # le jeu de la carte : les enchères restent (elles disent le contrat),
                with ui.element("div").classes("w-full rounded-xl border border-gray-200 bg-white p-2"):   # où l'on en est,
                    grille_demo()                                                                          # le double mort
                # les cartes du pli et leur raison : sur la table, au survol de chaque carte (l'utilisateur, 2026-11-11 :
                # pas de répétition dans la barre)
    F.marques_dm.clear()


NOMS = ("demo_de", "demo_fond", "demo_aller", "quiz_liste", "quiz_de", "quiz_revelee", "quiz_en_attente", "quiz_bas", "quiz_reveler", "quiz_choisir", "bouton_quiz", "quiz_panneau", "demo_ramasser", "demo_pli", "revue_de", "moments_cles", "bande_plis", "revoir_aller", "revoir_pli", "demo_essayer", "encheres_clavier", "demo_touche", "vue_demo",)   # rangés dans F par fenetre.construire
