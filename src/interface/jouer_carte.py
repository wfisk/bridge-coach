# -*- coding: utf-8 -*-
"""Jouer : le jeu de la carte, l'avis du coach, la réclamation.
Les noms de la page (état, fonctions de tous les modules de l'interface) sont dans F (interface.commun) :
fenetre.construire les y range à chaque ouverture de la page."""
from interface.commun import *  # noqa: F401,F403 — les outils communs et F


# ---------------------------------------------------------------- le jeu de la carte
def carte_demarrer(d):
    c_, decl = jouer.contrat(F.jeu["seq"], d["donneur"])
    F.jeu.update(partie=carte.Partie(d, c_, decl, F.jeu["seq"], humain=F.jeu["siege"]), pli_vu=None, revoir=None, msg="", garde_jeu=False, sans_jouer=False)
    F.jeu_garder(); F.vue_jouer.refresh(); background_tasks.create(F.carte_defense())


async def attendre_ou_clic(t):
    """Attend t secondes, ou moins si le joueur clique le tapis (ramasser_vite)."""
    ev = F.jeu["presse"] = asyncio.Event()
    try: await asyncio.wait_for(ev.wait(), t)
    except asyncio.TimeoutError: pass


def ramasser_vite():
    ev = F.jeu.get("presse")
    if ev: ev.set()


async def carte_poser(x):
    """Pose une carte ; si elle termine le pli, le pli reste un instant sous les yeux."""
    p = F.jeu["partie"]; avant = len(p.plis)
    p.poser(x); F.jeu["msg"] = ""; F.jeu_garder()
    if len(p.plis) > avant:                      # le pli complet : la carte gagnante luit doucement, puis les quatre cartes
        pli, g = p.plis[-1]                      # vont vers les plis gardés du camp gagnant (l'utilisateur, 2026-11-11)
        F.jeu["gagnante"] = next(((cc, r.translate(carte.FR)) for x_, cc, r in pli if x_ == g), None)
        F.jeu["pli_vu"] = p.plis[-1]; F.vue_jouer.refresh()
        await F.attendre_ou_clic(1.1)                # un clic sur le tapis ramasse le pli tout de suite
        places = F.jeu.get("places") or ()               # vers le joueur qui a gagné le pli (le mort aussi) : c'est ainsi
        F.jeu["ramasse"] = dict(zip(places, ("haut", "gauche", "droite", "bas"))).get(g, "bas")   # qu'on voit qui l'a gagné
        F.vue_jouer.refresh()
        await asyncio.sleep(.45)
        F.jeu.update(pli_vu=None, ramasse=None, gagnante=None, compte_monte=(p.camp(g), time.monotonic()))   # le pli arrive : le compte roule
    F.vue_jouer.refresh()


async def carte_defense():
    """Le programme joue les autres places (les défenseurs, ou le déclarant et son mort quand vous défendez), chacun
    après un temps de réflexion, jusqu'à votre tour."""
    p = F.jeu["partie"]
    while p and not p.fini() and not p.au_joueur() and F.jeu["partie"] is p:
        F.jeu["pense"] = p.au_trait(); F.vue_jouer.refresh()
        pause = 0.4 if len(p.legales()) == 1 else 1.3 if not p.pos.pli else 0.8   # forcée : vite ; une entame : on réfléchit
        def robot(p=p):
            t0 = time.monotonic(); x_ = p.carte_robot()
            noter_temps("La carte d'un robot (" + ("déclarant" if p.camp(p.pos.au_trait()) else "défense") + ")", time.monotonic() - t0)
            return x_
        x, _ = await asyncio.gather(run.io_bound(robot), asyncio.sleep(pause))
        if getattr(p, "difficile", False): await asyncio.sleep(1.4)   # la bonne carte ne s'imposait pas : il hésite
        F.jeu["pense"] = None
        await F.carte_poser(x)
    F.coach_prevoir(p)


def coach_prevoir(p):
    """À votre tour de jouer, le coach cherche déjà sa carte (en tâche de fond) : quand vous jouez, son avis est prêt."""
    if not coach_arrete() or not p or p.fini() or not p.au_joueur() or F.jeu.get("partie") is not p: return
    cle_ = (id(p), len(p.pos.jouees))
    if (F.jeu.get("coach_carte") or {}).get("cle") == cle_: return
    s_ = p.au_trait()
    def calcul():
        t0 = time.monotonic()
        x_ = p.indice()
        noter_temps("La carte du coach (" + ("en défense" if p.en_defense() else "déclarant") + ")", time.monotonic() - t0)
        z = p.pensee(s_, x_)
        return dict(x=x_, scores=z.get("scores") or {}, mondes=z.get("mondes") or 0, role=z.get("role"),
                    pourquoi=carte.justification(z, p.decl), plan=z.get("plan") or "", pensee=z)
    tache = asyncio.ensure_future(run.io_bound(calcul))
    F.jeu["coach_carte"] = dict(cle=cle_, tache=tache)


def avis_carte(p, x, r):
    """L'avis du coach quand votre carte x n'est pas la sienne (r : son calcul), ou None si elles se valent dans ses
    donnes imaginées. Serrée : la sienne ne réussit que dans un monde ou deux de plus, ou seulement plus de levées."""
    if not r or r["x"] == x: return None
    sc, n = r["scores"], r["mondes"]
    f = lambda c_: carte.carte_fr(*c_)
    mien, sien = sc.get(f(x)), sc.get(f(r["x"]))
    if mien is not None and sien is not None and mien[0] == sien[0] and (sien[1] - mien[1]) < 0.1 * max(1, n):
        return None                               # autant de réussites et moins d'un dixième de levée : rien à dire
    but = "faire chuter le contrat" if r.get("role") == "defense" else "gagner le contrat"
    virgule = lambda v: f"{v:.1f}".replace(".", ",")
    lignes = [f"Le coach jouerait <b>{rouge(f(r['x']))}</b>."]
    try:                                          # la technique, nommée : « le déblocage », « l'impasse »…
        tech = carte.technique(p, r["x"], x, r.get("pensee"))
    except Exception:
        tech = None
    if tech:
        lignes.append(f"<b>{rouge(tech[0][0].upper() + tech[0][1:])}</b> : {rouge(tech[1])}")
    serree = False
    if mien is not None and sien is not None and n:
        ecart = sien[0] - mien[0]
        serree = ecart <= max(1, n // 12)
        if ecart > 0:
            lignes.append(f"Pour {but}, sa carte réussit dans {sien[0]} des {n} donnes qu'il imagine, "
                          f"la vôtre dans {mien[0]}.")
        else:
            lignes.append(f"Autant de chances de {but} ({sien[0]} donnes sur {n}), mais plus de levées en moyenne : "
                          f"{virgule(sien[1] / n)} avec sa carte, {virgule(mien[1] / n)} avec la vôtre.")
    if r.get("pourquoi") and not tech: lignes.append(f"<b>Pourquoi :</b> {rouge(r['pourquoi'])}")
    lignes.append("<span style='color:var(--bc-tapis-700)'>Il ne voit pas les mains cachées : il imagine des donnes "
                  "fidèles aux enchères et aux cartes jouées.</span>")
    tete = "Décision serrée : les deux cartes se tiennent." if serree else "Le coach aurait joué une autre carte."
    return dict(genre="carte", mien=x, coach=r["x"], serree=serree, tete=tete, lignes=lignes,
                ou=(F.jeu.get("cle"), len(p.pos.jouees)), nom_mien=f(x), nom_coach=f(r["x"]))


def meme_resultat(p, x, y):
    """Les cartes x et y font-elles autant de levées sur la vraie donne, au double mort ? Cela sert seulement à ne
    pas vous arrêter pour rien (une défausse qui ne change rien, l'utilisateur, 2026-11-18) ; l'avis du coach, lui,
    ne vient que de ce qu'il voit à la table : sa main, le mort, les enchères, les cartes jouées."""
    try:
        v = p.pos.valeurs()                       # une carte par groupe de cartes équivalentes
    except Exception:
        return False
    val, prec = {}, {}
    for c_, r_ in sorted(p.legales(), key=lambda k: (k[0], carte.RANGS.index(k[1]))):   # de la plus haute
        t_ = v.get((c_, r_), prec.get(c_)); prec[c_] = t_; val[(c_, r_)] = t_
    return val.get(x) is not None and val.get(x) == val.get(y)


async def carte_jouer(x, force=False):
    p = F.jeu["partie"]
    if not p or F.jeu["pense"] or F.jeu["pli_vu"] or p.fini() or not p.au_joueur(): return
    if x not in p.legales():                       # interdite : la carte tremble et reste dans la main
        entame = p.pos.pli[0][1] if p.pos.pli else None
        mort = p.au_trait() == p.mort() and not p.en_defense()
        F.jeu["secoue"] = (x[0], x[1].translate(carte.FR))
        F.jeu["msg"] = ((f"Le mort a du {entame} : il doit fournir. Choisissez une autre carte du mort." if mort else
                       f"Vous avez du {entame} : vous devez fournir.") if entame else "Cette carte ne peut pas être jouée.")
        F.vue_jouer.refresh()
        await asyncio.sleep(.7); F.jeu["secoue"] = None
        return
    F.jeu["msg"] = ""; F.jeu["avis_coach"] = None
    if not force and coach_arrete():                    # pas la carte du coach : il vous arrête et dit pourquoi
        F.coach_prevoir(p)
        t_ = (F.jeu.get("coach_carte") or {}).get("tache")
        if t_ is not None:
            if not t_.done(): F.jeu["msg"] = "Le coach regarde votre carte…"; F.vue_jouer.refresh()
            try: r = await t_
            except Exception: r = None
            F.jeu["msg"] = ""
            if F.jeu.get("partie") is not p or p.fini() or not p.au_joueur(): return
            avis = F.avis_carte(p, x, r)
            if avis and await run.io_bound(F.meme_resultat, p, x, avis["coach"]):
                avis = None                         # sur la vraie donne, les deux cartes font autant : pas d'arrêt
            if avis:
                F.jeu["avis_coach"] = avis; F.vue_jouer.refresh(); return
    z_ = p.pensee(p.au_trait(), x, humain=True)       # votre carte, pour la relecture
    cc_ = F.jeu.get("coach_carte") or {}               # ce que le coach aurait joué là (déjà calculé) : gardé pour Revoir
    t_ = cc_.get("tache")
    if t_ is not None and t_.done() and cc_.get("cle") == (id(p), len(p.pos.jouees)) and not t_.exception():
        r_ = t_.result()
        try: tech_ = carte.technique(p, r_["x"], x, r_.get("pensee")) if r_["x"] != x else None
        except Exception: tech_ = None
        z_["avis"] = dict(carte=carte.carte_fr(*r_["x"]), mondes=r_["mondes"],
                          scores={k_: list(v_) for k_, v_ in r_["scores"].items()}, croyance=[],
                          technique=list(tech_) if tech_ else None, pourquoi=r_.get("pourquoi") or "")
    p.pensees.append(z_)
    await F.carte_poser(x)
    await F.carte_defense()


def avis_ici():
    """L'avis du coach en attente vaut-il encore pour la position présente ? (sinon il est oublié)"""
    a = F.jeu.get("avis_coach")
    if not a: return False
    p = F.jeu.get("partie")
    ici = (F.jeu.get("cle"), len(p.pos.jouees) if a["genre"] == "carte" and p else len(F.jeu["seq"]))
    if a["ou"] != ici: F.jeu["avis_coach"] = None; return False
    return True


def bloc_avis_coach(d):
    """L'arrêt du coach, dans la barre de droite : ce qu'il aurait fait, pourquoi (ou que c'était serré), puis deux
    boutons : garder votre choix, ou prendre le sien."""
    if not F.avis_ici(): return                      # la position a changé : l'avis ne vaut plus
    a = F.jeu["avis_coach"]
    fond = "var(--bc-jaune-50)" if a["serree"] else "var(--bc-tapis-100)"
    with ui.element("div").classes("w-full rounded-xl p-3 avis-coach").style(
            f"background:{fond};border:1px solid var(--bc-jaune-300);font-size:var(--fs-texte)"):
        ui.html(f"<div style='font-weight:700;margin-bottom:4px'>{CASQUETTE_SVG} {a['tete']}</div>"
                + "".join(f"<div style='margin-top:4px'>{l}</div>" for l in a["lignes"]), sanitize=False)
        with ui.column().classes("w-full gap-2 mt-2"):
            if a["genre"] == "enchere":
                garder = lambda: F.jeu_annonce(d, a["mien"], force=True)
                prendre = lambda: F.jeu_annonce(d, a["coach"], force=True, du_coach=True)
            else:
                garder = lambda: F.carte_jouer(a["mien"], force=True)
                prendre = lambda: F.carte_jouer(a["coach"], force=True)
            ui.button(f"Prendre {a['nom_coach']}, comme le coach", on_click=prendre) \
                .props("unelevated no-caps").classes("w-full")   # en blanc sur le vert : pas de rouge ici
            # le vôtre, sur fond clair : ♥ ♦ en rouge
            with ui.button(on_click=garder).props("outline no-caps").classes("w-full"):
                ui.html(f"<span style='font-size:var(--fs-texte)'>Garder {rouge(a['nom_mien'])}</span>", sanitize=False)
            autre = "une autre enchère" if a["genre"] == "enchere" else "une autre carte"
            ui.button(f"Choisir {autre}", on_click=lambda: (F.jeu.update(avis_coach=None), F.vue_jouer.refresh())) \
                .props("flat dense no-caps").classes("self-center")


async def carte_reclamer():
    p = F.jeu["partie"]
    if not p or p.fini(): return
    ok = await run.io_bound(p.reclamer)
    if ok: F.jeu_garder()
    F.jeu["msg"] = "" if ok else "Pas encore : la défense peut faire au moins une levée de plus."
    F.vue_jouer.refresh()


NOMS = ("carte_demarrer", "attendre_ou_clic", "ramasser_vite", "carte_poser", "carte_defense", "coach_prevoir", "avis_carte", "meme_resultat", "carte_jouer", "avis_ici", "bloc_avis_coach", "carte_reclamer",)   # rangés dans F par fenetre.construire
