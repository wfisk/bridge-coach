# -*- coding: utf-8 -*-
"""L'onglet Jouer : la vue d'une donne, le verdict, la table seule, Revoir, la comparaison.
Les noms de la page (état, fonctions de tous les modules de l'interface) sont dans F (interface.commun) :
fenetre.construire les y range à chaque ouverture de la page."""
from interface.commun import *  # noqa: F401,F403 — les outils communs et F


def mains_fr(d, x):
    return dict(zip(carte.COULEURS, ("" if m == "-" else m for m in d["mains"][x].split())))


def vue_carte(c, d, data, places):
    """Le jeu de la carte : la table et le pli au centre ; le panneau de droite est dessiné par vue_jouer."""
    p = F.jeu["partie"]; s = places[3]; part = jouer.PART[s]   # le siège du bas : le vôtre, ou le déclarant que vous jouez
    tour = p.au_trait()
    cliquable = not p.fini() and not F.jeu["pense"] and not F.jeu["pli_vu"] and p.au_joueur(tour)
    voit = lambda x: p.fini() or x == s or (x == p.mort() and p.pos.jouees) or (p.camp(x) and not p.en_defense())

    def contenu(x, ou):
        if voit(x):
            with ui.column().classes("gap-1 " + ("items-center" if ou in ("haut", "bas") else "")):
                if not p.fini():
                    cartes = {k: "".join(r.translate(carte.FR) for r in v) for k, v in p.pos.reste[x].items()}
                    # toutes les cartes de la main se cliquent, comme à la table : rien ne dit lesquelles sont permises
                    # (l'utilisateur, 2026-11-11) ; une carte interdite tremble (carte_jouer)
                    jouables = ({(k, r) for k, v in cartes.items() for r in v} if cliquable and tour == x else None)
                    clic = lambda y: F.carte_jouer((y[0], y[1].translate(carte.EN)))
                    if x == p.mort():
                        posees, derniere, ecoule = F.pli_en_cours(p)
                        cr = posees.get(x)
                        F.mort_etale(cartes, jouables, clic, p.den, ou,
                                   F.carte_posee(*cr, ou if x == derniere else None, ecoule,
                                               premiere=x == next(iter(posees), None), cote=ou) if cr else "",
                                   a_vous=cliquable and tour == x)
                    else: F.eventail(cartes, jouables, clic, colonnes=ou in ("gauche", "droite"), cote=ou, grande=x == s, depart=F.mains_fr(d, x),
                                   a_vous=cliquable and tour == x)   # les cartes jouables ont déjà leur bord
        elif not p.fini():                               # un adversaire : sa main cachée, en éventail fermé
            F.dos(ou, sum(len(v) for v in p.pos.reste[x].values()))
    # la donne finie, la table garde sa forme (le mort à sa place, même vide) : rien ne bouge à la dernière carte
    # (l'utilisateur, 2026-11-16)
    F.table(d, places, contenu, lambda: ui.html(F.pli_html(p, places, p.mort()), sanitize=False),
          sur_table=[ou for x, ou in zip(places, ("haut", "gauche", "droite", "bas")) if x == p.mort()],
          tour=None if p.fini() or F.jeu["pli_vu"] else tour, ouvert=False,
          clic=F.ramasser_vite if F.jeu.get("pli_vu") else None)   # un pli fini : un clic le ramasse tout de suite


def options_joueurs(*garder):
    """Le choix d'un joueur : « Aucun (tous les joueurs) », puis votre nom (Réglages, « Votre nom »), une ligne de
    séparation, puis les autres joueurs de la séance ouverte, par ordre alphabétique (pas ceux de toutes les
    séances : l'utilisateur, 2026-11-16). garder : des noms à montrer même s'ils ne sont pas dans cette séance
    (le choix en cours, pour que la liste l'affiche)."""
    data_ = lire_seance(seance_active()) or {}
    noms_ = sorted({(j.get("nom") or "").strip() for v in (data_.get("joueurs") or {}).values() for j in v} - {""},
                   key=str.lower)
    noms_ += [x for x in garder if x and x not in noms_]
    mien = lire_etat().get("mon_nom")
    out = {"": "Aucun (tous les joueurs)"}
    if mien: out[mien] = f"{mien} (vous)"
    autres = sorted((x for x in noms_ if x != mien), key=str.lower)
    if mien and autres: out[SEPARATEUR] = "──────────"
    out.update({x: x for x in autres})
    return out


def siege_pour(c, d):
    """Votre place à cette donne, comme dans Jouer : celle de la partie gardée, sinon celle que donne l'option
    d'Options (sans rien lancer : la Démo ne fait pas jouer les robots de votre partie)."""
    if F.jeu.get("cle") == (c, d["n"]) and F.jeu.get("siege"): return F.jeu["siege"]
    x = jouer.en_cours(base_seance(c), d["n"]) or {}
    if x.get("siege"): return x["siege"]
    if place_jouer() == "joueur":
        pj = moi.place_du_joueur(lire_seance(c), d, joueur_jouer())
        if pj: return pj["siege"]
    if place_jouer() in ("camp", "defense", "hasard"): return None     # tirée au sort : pas encore connue
    return jouer.siege_choisi(place_jouer(), d, lire_analyses(c))


def donne_jouee(c, d):
    """La donne a-t-elle été jouée jusqu'au bout (sa dernière partie, gardée) ? Revoir n'a de sens qu'après."""
    x = jouer.en_cours(base_seance(c), d["n"]) or {}
    return bool(x.get("reclame") or len(x.get("cartes") or []) >= 52)


def verdict(c, d, p):
    """La donne finie, en une ou deux lignes (l'utilisateur, 2026-11-11 : le moment où l'on apprend) : votre contrat
    face au contrat recommandé (l'Expert, sinon le Coach), au double mort, en IMP ; puis votre jeu de la carte face
    au double mort de votre contrat."""
    try:
        r = jouer.comparer(d, F.jeu["seq"], F.jeu["siege"], lire_analyses(c))
    except Exception:
        return ""
    lignes = r["lignes"]; moi_ = lignes[0]
    ref = next((x for x in lignes if x["nom"] == "Expert"), None) or next((x for x in lignes if x["nom"] == "Standard"), None)
    nom_c = lambda t: re.sub(r" ([NESO])$", lambda m_: " par " + SIEGE[m_[1]], t)
    out = []
    if ref:
        qui = "l'Expert" if ref["nom"] == "Expert" else "le Coach"
        if ref["texte"] == moi_["texte"]:
            out.append(f"Même contrat que {qui} : {rouge(nom_c(ref['texte']))}.")
        else:
            lev = f", {ref['levees']} levées au double mort" if ref.get("levees") is not None else ""
            i_ = ref.get("imp")
            gain = "" if i_ in (None, 0) else (f" — {abs(i_)} IMP de {'plus' if i_ > 0 else 'moins'} pour vous")   # vos IMP face à lui
            out.append(f"Recommandé par {qui} : <b>{rouge(nom_c(ref['texte']))}</b>{lev}{gain}.")
    if p:
        g_, _e, dm = p.resultat()
        vous = g_ if not p.en_defense() else 13 - g_
        dm_vous = dm if not p.en_defense() else 13 - dm
        if vous < dm_vous: out.append(f"Au jeu de la carte : {dm_vous - vous} levée{'s' if dm_vous - vous > 1 else ''} de moins que le double mort.")
        elif vous > dm_vous: out.append(f"Au jeu de la carte : {vous - dm_vous} levée{'s' if vous - dm_vous > 1 else ''} de plus que le double mort.")
        else: out.append("Au jeu de la carte : autant que le double mort.")
    return "<br>".join(out)


def faute_de(p):
    """La première de vos cartes qui a coûté une levée au double mort (sinon de votre partenaire), son rang dans la donne, ou None ; calculée
    une fois, en arrière-plan, quand la donne finit (Revoir s'ouvre là)."""
    x = F.jeu.get("faute")
    if x and x[0] is p: return x[1]                   # (partie, rang de la carte, la carte qui gardait la levée)
    if not F.jeu.get("faute_calcul") is p:
        F.jeu["faute_calcul"] = p
        async def calcul():
            cartes = [(cc, r) for pli, _ in p.plis for _x, cc, r in pli]
            try:
                a = await run.io_bound(carte.analyse_jeu, p.d, p.contrat, p.decl, cartes)
                k = next((x_["k"] for x_ in a["cartes"] if x_["perte"] > 0 and p.au_joueur(x_["siege"])), None)
                if k is None:                          # sinon la première levée perdue par votre camp (votre partenaire)
                    k = next((x_["k"] for x_ in a["cartes"]
                              if x_["perte"] > 0 and p.camp(x_["siege"]) == p.camp(p.humain)), None)
                mieux = await run.io_bound(carte.meilleure_carte, p.d, p.contrat, p.decl, cartes, k) if k is not None else None
            except Exception:
                k = None; mieux = None
            F.jeu["faute"] = (p, k, mieux)
            if F.jeu.get("partie") is p: F.vue_jouer.refresh()
        background_tasks.create(calcul())
    return None


def changer_mode(m):
    F.jeu.update(mode=m, revoir=0 if m == "revoir" else None); ecrire_etat(mode_jouer=m); F.vue_jouer.refresh()


def tete_donne(d):
    """En haut de la barre de droite de Jouer : Jouer | Revoir | Démo (l'utilisateur, 2026-11-11). Revoir, la partie
    que vous avez jouée rejouée avec les commentaires des robots, s'ouvre une fois la donne jouée jusqu'au bout."""
    c = F.choix["chemin"]; m = F.mode_de(c, d)
    with ui.element("div").classes("inline-flex rounded overflow-hidden").style("box-shadow:0 1px 3px rgba(0,0,0,.18)"):
        for cle, nom in (("jouer", "Jouer"), ("revoir", "Revoir"), ("demo", "Démo")):
            b = ui.button(nom, on_click=lambda cle=cle: F.changer_mode(cle)) \
                .props(("unelevated color=primary" if m == cle else "flat color=white text-color=grey-9") + " no-caps square") \
                .classes("text-base")
            if cle == "revoir" and not F.donne_jouee(c, d):
                b.set_enabled(False); b.tooltip("Jouez d'abord la donne jusqu'au bout")
            elif cle == "revoir":
                b.tooltip("Votre partie, carte par carte, avec ce que pensaient les robots")
    F.bouton_brouillon(d)


def mode_de(c, d):
    """Le mode montré pour cette donne : Revoir seulement si elle a été jouée jusqu'au bout, sinon Jouer."""
    m = F.jeu.get("mode") or "jouer"
    return "jouer" if m == "revoir" and not F.donne_jouee(c, d) else m


def dernier_pli(_=None):
    """Un clic sur la dernière carte des plis gardés : le dernier pli dans une fenêtre, posé comme à la table, la carte
    gagnante dorée (l'utilisateur, 2026-11-11 : sans toucher aux cartes de la table)."""
    p = F.jeu.get("partie")
    if not p or not p.plis or not F.jeu.get("cle") or F.mode_de(F.jeu["cle"][0], F.jeu["d"]) != "jouer": return    # la partie de Jouer (Revoir, Démo : leurs flèches)
    F.jeu["pli_montre"] = p.plis[-1]; F.contenu_pli.refresh(); F.fen_pli.open()


def appliquer_plein():
    """La place que prennent les barres, pour la taille de la table (COTE_TABLE). Table seule : sans les onglets ni la
    barre de gauche ; la barre de droite reste (la boîte à enchères, les commandes ; le choix de l'utilisateur)."""
    if not F.plein["on"]: l, h, m, t = 740, 420, 640, f"{HAUTEUR_BARRE}px"
    else: l, h, m, t = 440, 330, 820, "0px"           # sans les onglets : la barre de droite monte en haut
    ui.run_javascript(f"var r = document.documentElement.style; r.setProperty('--reserve-l', '{l}px'); "
                      f"r.setProperty('--haut-panneau', '{t}'); "
                      f"r.setProperty('--reserve-h', '{h}px'); r.setProperty('--table-max', '{m}px'); "
                      "setTimeout(function () { window.dispatchEvent(new Event('resize')); }, 50)")


def basculer_plein():
    F.plein["on"] = not F.plein["on"]
    F.entete.set_value(not F.plein["on"]); F.montrer_barre(); F.vue_jouer.refresh()


def outils_table(d, extra=None):
    """Au-dessus de la table, sur sa ligne : la donne, son donneur et sa vulnérabilité (ôtés de la barre de droite pour
    lui laisser la place ; le petit carré de la FFB aussi : il répétait l'étui), et à droite « table seule » (sans les
    barres). Les cartes grandissent avec la place (l'utilisateur, 2026-11-11)."""
    with ui.row().classes("w-full gap-x-4 gap-y-1 items-center justify-center").style(   # centrée au-dessus de la table (2026-11-14)
            "margin-bottom:-8px;white-space:nowrap"):   # pas de marge négative en haut : le panneau rognait le carré
        # plus de petit carré de la donne : les mots disent le donneur et la vulnérabilité (l'utilisateur, 2026-11-14)
        with ui.element("div"): titre_donne(d, centre=True)
        if place_jouer() == "joueur":                  # comme un joueur de la séance : son tour, ses adversaires
            pj = F.jeu.get("place_joueur")
            if pj:                                     # les noms sont près des mains
                if pj.get("tour"): ui.html(f"<div style='font-size:var(--fs-titre)'>Tour <b>{pj['tour']}</b></div>", sanitize=False)
            else:
                ui.html(f"<div style='font-size:var(--fs-titre);color:var(--bc-tapis-600)'>{joueur_jouer()} n'a pas joué cette donne</div>", sanitize=False)
        if extra:
            with ui.row().classes("items-center gap-3 no-wrap"):   # Démo : le double mort, sur la même ligne
                extra()                          # Démo : le double mort, au-dessus de la table


@ui.refreshable
def vue_jouer():
    c = F.choix["chemin"]; data = lire_seance(c)
    if not data:
        F.sans_seance(); return
    es = F.entrees_de(data) if F.sur_jouer() else []
    if not es: return
    e = F.entree_effective(data)
    if e == "options":
        titre_page("Options", "encherir")
        with ui.row().classes("items-center gap-2"):          # le système des robots, sur la fiche de conventions
            ui.label("Les robots jouent le SEF 2024.").classes("text-base text-gray-700")
            ui.button("Votre fiche de conventions", icon="description",
                      on_click=lambda: (F.onglets.set_value(F.o_systeme), F.voir_page("Système", "systeme"))).props("flat dense no-caps")
        ui.label("La place que vous jouez").classes("text-base font-bold mt-2")
        ui.label("Le déclarant est celui de la séquence recommandée (l'analyse de l'expert, sinon la standard, sinon "
                 "les enchères du coach). Le choix vaut pour toutes les donnes et reste d'une fois sur l'autre.") \
            .classes("text-base text-gray-700 max-w-2xl")
        def repartir():
            F.jeu["cle"] = None                            # les donnes repartent du début, à la nouvelle place
            x = jouer.lire_essais(base_seance(c))
            if x.pop("en_cours", None) is not None:
                json.dump(x, open(jouer.fichier_jeu(base_seance(c)), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        def changer(ev):
            if ev.value is None: return                   # l'autre liste de choix qui se vide
            ecrire_etat(place_jouer=ev.value); repartir(); F.barre_seance.refresh(); F.vue_jouer.refresh()
        places_ = dict(jouer.PLACES); cle1 = next(iter(places_))   # « comme un joueur » en premier, ses réglages juste dessous
        ui.radio({cle1: places_[cle1]}, value=place_jouer() if place_jouer() == cle1 else None, on_change=changer).classes("text-base")
        if place_jouer() == "joueur":                    # quel joueur, et dans quel ordre
            noms_seance = sorted({j["nom"].strip() for v in (data.get("joueurs") or {}).values() for j in v
                                  if (j.get("nom") or "").strip()}, key=str.lower)
            if not noms_seance:
                ui.label("Cette séance ne garde pas le nom des joueurs : le choix n'est pas possible.").classes("text-base text-gray-700")
            else:
                actuel = joueur_jouer() if joueur_jouer() in noms_seance else noms_seance[0]
                mien = lire_etat().get("mon_nom")
                opts = ({mien: f"{mien} (vous)", SEPARATEUR: "──────────"} if mien in noms_seance else {})
                opts.update({x: x for x in noms_seance if x != mien})
                def choisir_joueur(ev):
                    if ev.value == SEPARATEUR: ev.sender.value = joueur_jouer(); return
                    ecrire_etat(joueur_jouer=ev.value); retenir_licence(ev.value); repartir(); F.barre_seance.refresh(); F.vue_jouer.refresh()
                with ui.column().classes("gap-2 ml-8 max-w-md"):
                    ui.select(opts, value=actuel, with_input=True, on_change=choisir_joueur).classes("w-full") \
                        .props("outlined dense") \
                        .props(":option-disable=\"o => typeof o.label === 'string' && o.label.startsWith('───')\"")
                    ui.checkbox("Dans l'ordre où ce joueur a joué les donnes", value=bool(lire_etat().get("ordre_joueur")),
                                on_change=lambda ev: (ecrire_etat(ordre_joueur=ev.value), F.vue_jouer.refresh())).classes("text-base")
                    ui.label("Tour après tour : « Donne suivante », à la fin de chaque donne, suit cet ordre ; les donnes qu'il "
                             "n'a pas jouées viennent à la fin, jouées à la place du déclarant. Au-dessus des cartes : le nom "
                             "des quatre joueurs de sa table.").classes("text-base text-gray-700")
                    premiere = (F.ordre_jouer(data) or [None])[0]
                    if premiere is not None:
                        ui.button(f"Aller à la première donne (donne {premiere})", icon="arrow_forward",
                                  on_click=lambda n=premiere: F.aller(f"d{n}")).props("unelevated no-caps").classes("text-base mt-1")
        # « Toujours Nord / Sud / Est / Ouest » : un seul choix, puis la place (l'utilisateur, 2026-11-17 : dix choix, c'était trop)
        autres = {k: v for k, v in places_.items() if k != cle1 and k not in jouer.ROT}
        autres = dict(list(autres.items())[:-1] + [("fixe", "Toujours la même place")] + list(autres.items())[-1:])
        p_ = place_jouer()
        def changer_autre(ev):
            if ev.value == "fixe": ev = type("E", (), {"value": lire_etat().get("siege_fixe") or "S"})()
            changer(ev)
        ui.radio(autres, value="fixe" if p_ in jouer.ROT else (p_ if p_ != cle1 else None), on_change=changer_autre).classes("text-base")
        if p_ in jouer.ROT:
            with ui.row().classes("items-center gap-3 ml-8"):
                ui.toggle({x: SIEGE[x] for x in "NESO"}, value=p_,
                          on_change=lambda ev: (ecrire_etat(siege_fixe=ev.value), changer(ev))).props("no-caps")
        ui.label("Quand l'autre camp gagne le contrat, vous jouez la carte en défense : les robots tiennent le déclarant, "
                 "son mort et votre partenaire.").classes("text-base text-gray-700")
        ui.label("Le coach pendant le jeu").classes("text-base font-bold mt-4")
        ui.checkbox("Le coach m'arrête quand il aurait fait autrement", value=coach_arrete(),
                    on_change=lambda ev: (ecrire_etat(coach_arrete=bool(ev.value)), F.vue_jouer.refresh())).classes("text-base")
        ui.label("Avant que votre enchère ou votre carte soit jouée, il dit la sienne et pourquoi, puis vous gardez votre "
                 "choix ou prenez le sien. Décochée : vous jouez sans interruption.") \
            .classes("text-base text-gray-700 max-w-2xl")
        return
    if e == "classement":
        page_classement(c, data, F.aller); return
    d = next(x for x in data["donnes"] if f"d{x['n']}" == e)
    if F.mode_de(c, d) == "demo":                      # la démonstration, pour un cours : une vue à part
        pj = moi.place_du_joueur(data, d, joueur_jouer()) if place_jouer() == "joueur" else None
        F.jeu["noms"] = (pj or {}).get("noms") or {}; F.jeu["place_joueur"] = pj
        F.vue_demo(c, d, data); return
    if F.jeu["cle"] != (c, d["n"]): F.jeu_depart(c, d)
    pj = moi.place_du_joueur(data, d, joueur_jouer()) if place_jouer() == "joueur" else None
    F.jeu["noms"] = (pj or {}).get("noms") or {}; F.jeu["place_joueur"] = pj
    s = F.jeu["siege"]; part = jouer.PART[s]
    p = F.jeu["partie"]
    # vos cartes toujours en bas ; la table et l'étui tournent avec vous. Vous tenez le déclarant et son mort, et vous
    # avez enchéri de la place du mort : pendant le jeu de la carte, le déclarant passe devant vous (la table tourne)
    bas = p.decl if p and not p.en_defense() and s == p.mort() else s
    vu = F.jeu.get("bas_vu")                           # (séance, donne, siège du bas) au dessin d'avant
    if vu and vu[:2] == (c, d["n"]) and vu[2] != bas and p and not p.pos.jouees[1:]:
        F.jeu["tourne"] = time.monotonic()   # le début du jeu de la carte : la table tourne d'un demi-tour
    F.jeu["bas_vu"] = (c, d["n"], bas); F.jeu["bas"] = bas
    gauche, droite = jouer.ROT[(jouer.ROT.index(bas) + 1) % 4], jouer.ROT[(jouer.ROT.index(bas) + 3) % 4]
    places = (jouer.PART[bas], gauche, droite, bas); F.jeu["places"] = places
    attente = F.jeu["affiche"] < len(F.jeu["seq"])
    fini = F.jeu["indice"] is None and not attente
    if F.mode_de(c, d) == "revoir" and p and p.fini():   # Revoir : votre partie, carte par carte, avec les pensées
        if F.jeu.get("revoir") is None: F.jeu["revoir"] = 0
        F.vue_revoir(c, d, data, places, p); return
    c_, decl = jouer.contrat(F.jeu["seq"], d["donneur"]) if fini else ("passe", None)
    a_jouer = fini and not p and c_ != "passe" and not F.jeu.get("sans_jouer")   # au déclarant ou en défense
    montrer = (fini and not a_jouer and not p) or (p and p.fini())

    with ui.row().classes("w-full no-wrap items-start gap-4").style(f"padding-right:{LARGEUR_PANNEAU}px"):
        with ui.column().classes("grow min-w-0 gap-2 relative"):     # la table
            F.outils_table(d)
            if p:
                F.vue_carte(c, d, data, places)
            else:
                def contenu(x, ou):
                    if x == s or montrer:
                        F.eventail(F.mains_fr(d, x), colonnes=ou in ("gauche", "droite"), cote=ou, grande=x == s, depart=F.mains_fr(d, x),
                                 a_vous=x == s and not fini and not attente and not F.jeu.get("attend"))
                    else: F.dos(ou, 13)
                F.table(d, places, contenu, lambda: ui.html(F.tapis_encheres(d, places), sanitize=False),
                      tour=None if F.jeu.get("attend") else F.jeu["pense"] if attente else (s if not fini else None),
                      ouvert=bool(montrer))
        expert_ici = {"fait": False}                  # « Demander à l'expert » placé sur la ligne de l'Indice ?
        with F.panneau_droit():                                                         # la barre de droite : l'essentiel
            F.appliquer_plein()
            F.tete_donne(d)
            F.magneto(c, d)
            # la grille des enchères, toujours ouverte sur sa carte blanche, même pendant le jeu (elle dit le contrat) ;
            # l'étui n'est plus que sur la table (l'utilisateur, 2026-11-11 : pas deux fois)
            with ui.element("div").classes("w-full rounded-xl border border-gray-200 bg-white p-2"):
                vues = F.jeu["seq"] if p else F.jeu["seq"][:F.jeu["affiche"]]
                ui.html(grille_html(jouer.grille(vues, d["donneur"], not fini and not attente and not p), d["vul"],
                                    sens=F.sens_jouer(len(vues)))
                        .replace("border-collapse:collapse", "border-collapse:separate;border-spacing:4px 0"), sanitize=False)
            if p:
                if not p.fini():
                    with ui.row().classes("gap-2 items-center"):
                        # plus de bouton Indice (l'utilisateur, 2026-11-18) : le coach vous arrête quand il aurait joué autrement
                        F.bouton_expert(c, d, False, pleine=False); expert_ici["fait"] = True
                        if not p.en_defense():
                            ui.button("Réclamer", icon="done_all", on_click=lambda: F.carte_reclamer()).props("outline dense no-caps") \
                                .tooltip("Réclamer : vous annoncez que vous ferez toutes les levées qui restent, sans les jouer. "
                                         "Le coach vérifie, cartes vues : si la défense peut en faire une, la donne continue.")
                    if F.jeu["msg"]: ui.label(F.jeu["msg"]).classes("text-base")
                    F.bloc_avis_coach(d)
                # pas de pensées des robots pendant le jeu : à la table, on n'entend pas les autres réfléchir (et elles
                # disent ce qu'ils croient des mains cachées ; l'utilisateur, 2026-11-11). Elles restent pour « Revoir la
                # donne avec les pensées », après la donne, et pour la Démo
            elif F.jeu.get("attend"):                         # « Commencer les enchères » est en haut : rien à redire ici
                pass
            elif not fini and attente:                      # les autres enchérissent : la boîte reste, grisée
                F.boite_encheres(d, actif=False)
            elif not fini and not attente and F.avis_ici():  # le coach vous arrête : son avis à la place de la boîte,
                F.bloc_avis_coach(d)                          # en haut, là où l'on regarde (l'utilisateur, 2026-11-18 : la barre)
            elif not fini and not attente:
                F.boite_encheres(d)
                with ui.row().classes("w-full gap-2 items-center"):   # sous la boîte (plus d'Indice : le coach vous arrête)
                    F.bouton_expert(c, d, False, pleine=False); expert_ici["fait"] = True
                if F.jeu.get("note"):
                    ui.html(f"<div style='font-size:var(--fs-texte);color:var(--bc-jaune-700)'>{rouge(F.jeu['note'])}</div>", sanitize=False)
                if F.jeu.get("clavier"):                      # un chiffre tapé au clavier : la couleur est attendue
                    ui.label(f"Au clavier : {F.jeu['clavier']}… puis T, K, C, P ou S (Échap pour effacer)").classes("text-base text-primary")
                else:
                    ui.label("Au clavier : 1 puis T K C P S (1♣ … 1SA), Entrée passe, X contre, R surcontre.") \
                        .classes("text-sm text-gray-600")
            elif a_jouer:                                   # les enchères finies : le jeu de la carte part tout seul, comme à
                ui.label(f"{'Vous jouez' if jouer.camp(decl) == jouer.camp(s) else 'Vous défendez contre'} {c_} par {SIEGE[decl]} : "
                         "le jeu de la carte commence…").classes("text-base")      # la table (l'utilisateur, 2026-11-11)
                ui.button("Voir les mains sans jouer", on_click=lambda: (F.jeu.update(sans_jouer=True), F.jeu_garder(), F.vue_jouer.refresh())) \
                    .props("flat no-caps dense")
                cle_ = (c, d["n"], len(F.jeu["seq"]))
                if F.jeu.get("depart_auto") != cle_:
                    F.jeu["depart_auto"] = cle_
                    async def depart(cle_=cle_):
                        await asyncio.sleep(1.8)
                        if (F.jeu.get("cle") == cle_[:2] and len(F.jeu["seq"]) == cle_[2] and not F.jeu.get("partie")
                                and not F.jeu.get("sans_jouer") and F.mode_de(c, d) == "jouer"):   # le mode montré : « revoir »
                            # gardé d'une autre donne s'affiche Jouer ici, et bloquait le départ (2026-11-13)
                            F.carte_demarrer(d)
                    background_tasks.create(depart())
            if (p and p.fini()) or (montrer and not p):     # la donne finie : la suite, en haut de la barre (pas sous la table)
                with ui.column().classes("w-full gap-2 mt-2"):
                    if p:
                        g_, ecart_, _dm = p.resultat()
                        fait = "fait tout juste" if ecart_ == 0 else f"fait avec {ecart_} de mieux" if ecart_ > 0 else f"chute de {-ecart_}"
                        ui.html(f"<div style='font-size:16px'><b>{g_} levées</b> : {rouge(p.contrat)} {fait}.</div>", sanitize=False)
                    ui.button("Donne suivante", icon="arrow_forward", on_click=lambda: F.jeu_suivante(data, d)) \
                        .props("unelevated no-caps").classes("w-full text-base")
                    v = F.verdict(c, d, p)                        # en deux lignes : face au contrat recommandé, et au jeu
                    if v: ui.html(f"<div style='font-size:16px;line-height:1.4'>{v}</div>", sanitize=False)
                    if p:                                       # Revoir, ouvert là où vous avez perdu une levée
                        f_ = F.faute_de(p)
                        ui.button("Voir pourquoi" if f_ is not None else "Revoir la donne", icon="replay",
                                  on_click=lambda f_=f_: (F.changer_mode("revoir"), F.jeu.update(revoir=f_ or 0), F.vue_jouer.refresh())) \
                            .props("outline no-caps").classes("w-full text-base")
            if not F.jeu.get("attend") and not expert_ici["fait"]:   # ailleurs que sur la ligne de l'Indice : sur toute la
                fin_ = bool((p and p.fini()) or (montrer and not p))   # largeur (une question à l'outil d'IA réglé)
                F.bouton_expert(c, d, fin_).classes("mt-2")

    if fini and not F.jeu["garde"]:
        jouer.enregistrer(base_seance(c), d["n"], s, F.jeu["seq"], d["donneur"]); F.jeu["garde"] = True; F.barre_seance.refresh()
    # la donne finie : rien sous la table (l'utilisateur, 2026-11-11) ; le résultat et « Donne suivante » sont dans la
    # barre, le résumé dans Revoir à la dernière carte
    if p and p.fini() and not F.jeu["garde_jeu"]:
        jouer.completer_jeu(base_seance(c), d["n"], [carte.carte_fr(cc, r) for pli, _ in p.plis for _x, cc, r in pli],
                            p.resultat()[0])
        F.jeu["garde_jeu"] = True


def resume_de(d, p):
    """Le résumé écrit de la donne jouée (carte.resume_donne), calculé une fois."""
    if F.jeu.get("resume_de") is not p:
        try:
            tout = [(cc, r_) for pli, _ in p.plis for _x, cc, r_ in pli]
            F.jeu["resume"] = carte.resume_donne(d, p.contrat, p.decl, p.humain, tout, p.pensees, p.resultat()[0])
        except Exception:
            F.jeu["resume"] = []
        F.jeu["resume_de"] = p
    return F.jeu.get("resume") or []


def vue_revoir(c, d, data, places, p):
    """La donne rejouée carte par carte : les quatre mains telles qu'elles étaient, le pli en cours, et ce que
    pensait le joueur de la carte montrée (◀ ▶). Votre carte : ce que le programme aurait joué à votre place."""
    cartes = [(cc, r_) for pli, _ in p.plis for _x, cc, r_ in pli]
    k = max(0, min(F.jeu["revoir"], len(cartes) - 1)); F.jeu["revoir"] = k; F.jeu["revoir_n"] = len(cartes)   # pour les flèches du clavier
    q = carte.Partie(d, p.contrat, p.decl, p.encheres, humain=p.humain)
    for x in cartes[len(q.pos.jouees):k + 1]: q.poser(x)
    pli = q.pos.pli or (q.plis[-1][0] if q.plis else [])
    posees = {x: (cc, r_.translate(carte.FR)) for x, cc, r_ in pli}
    def centre():
        ui.html(f"<div style='position:absolute;inset:0;pointer-events:none'><div style='position:absolute;left:50%;top:50%;"
                f"transform:translate(-50%,-50%);z-index:0'></div>{F.pli_cartes(q, places, posees, mort=q.mort())}"
                + F.rangees_plis(q, places, lambda x: x != q.mort())
                + "</div>", sanitize=False)
    def contenu(x, ou):
        reste = {kk: "".join(r_.translate(carte.FR) for r_ in v) for kk, v in q.pos.reste[x].items()}
        if x == q.mort(): F.mort_etale(reste, None, None, q.den, ou,
                                     F.carte_posee(*posees[x], premiere=x == next(iter(posees), None), cote=ou) if x in posees else "")
        else: F.eventail(reste, colonnes=ou in ("gauche", "droite"), cote=ou, grande=x == F.jeu["siege"], depart=F.mains_fr(d, x))
    with ui.row().classes("w-full no-wrap items-start gap-4").style(f"padding-right:{LARGEUR_PANNEAU}px"):
        with ui.column().classes("grow min-w-0 gap-2"):
            F.outils_table(d)
            F.table(d, places, contenu, centre,
                  sur_table=[ou for x, ou in zip(places, ("haut", "gauche", "droite", "bas")) if x == q.mort()],
                  clic=lambda: F.revoir_aller(F.jeu.get("revoir", 0) + 1))   # un clic sur le tapis : une carte
        with F.panneau_droit():
            F.appliquer_plein()
            F.tete_donne(d)
            F.boutons_pas(lambda: F.revoir_aller(0), lambda: F.revoir_aller(k - 1), lambda: F.revoir_aller(k + 1),   # comme Jouer et Démo
                        ok_debut=k > 0, ok_recul=k > 0, ok_avance=k < len(cartes) - 1 and not F.jeu.get("revoir_suite"),
                        aide_recul="Une carte en arrière (←)", aide_avance="Une carte (→ ; Maj + → : tout le pli)")
            rv = F.revue_de(p, d, cartes)
            F.bande_plis(p, cartes, rv, k)
            ui.label(f"{p.contrat} par {SIEGE[p.decl]} · carte {k + 1} sur {len(cartes)} · pli {k // 4 + 1}").classes("text-base font-bold")
            moments = F.moments_cles(p, cartes, rv)
            if moments:                                     # les moments clés : un clic y va ; « Moment suivant »
                suivant = next((m for m in moments if m[0] > k), None)
                with ui.element("div").classes("w-full rounded-lg").style(
                        "border:1px solid var(--bc-tapis-200);background:var(--bc-blanc);padding:6px 8px"):
                    with ui.row().classes("w-full items-center justify-between no-wrap"):
                        ui.label("Moments clés").classes("text-base font-bold whitespace-nowrap")
                        ui.button("Suivant", on_click=lambda m=suivant: F.revoir_aller(m[0]) if m else None) \
                            .props("flat dense no-caps icon-right=chevron_right").set_enabled(suivant is not None)
                    if rv.get("a") is None:
                        ui.label("Le coach revoit la donne…").classes("text-base text-gray-700")
                    puce = {"entame": "var(--bc-tapis-500)", "perte": "var(--bc-coeur-600)", "cadeau": "var(--bc-pique-500)",
                            "coach": "var(--bc-trefle-600)", "coup": "var(--bc-jaune-600)"}
                    for kk, genre, texte in moments:
                        ici = kk == k
                        ui.html(f"<div style='display:flex;gap:6px;align-items:baseline;padding:2px 4px;border-radius:4px;cursor:pointer;"
                                f"font-size:var(--fs-liste);{'background:var(--bc-jaune-100);font-weight:700' if ici else ''}'>"
                                f"<span style='flex:none;width:8px;height:8px;border-radius:50%;background:{puce[genre]}'></span>"
                                f"<span style='flex:none;color:var(--bc-tapis-700)'>Pli {kk // 4 + 1}</span><span>{texte}</span></div>",
                                sanitize=False).on("click", lambda kk=kk: F.revoir_aller(kk))
            if k == len(cartes) - 1 and F.resume_de(d, p):  # la fin du film : le résumé de la donne
                with ui.element("div").classes("w-full").style(
                        "background:var(--bc-pique-50);border:1px solid var(--bc-pique-100);border-radius:6px;padding:8px 10px"):
                    ui.label("Résumé de la donne").classes("text-base font-bold")
                    for ligne in F.resume_de(d, p):
                        ui.html(f"<div style='font-size:var(--fs-texte);margin-top:4px'>{rouge(ligne)}</div>", sanitize=False)
            f_ = F.jeu.get("faute")                           # la carte qui a coûté la levée : le dire, et ce qui la gardait
            perte_k = next((x for x in ((rv.get("a") or {}).get("cartes") or [])
                            if x["k"] == k and x["perte"] > 0 and p.camp(x["siege"]) == p.camp(p.humain)), None)
            mieux = rv["mieux"].get(k) if perte_k else (f_[2] if f_ and f_[0] is p and f_[1] == k else None)
            if perte_k or (f_ and f_[0] is p and f_[1] == k):
                ui.html(f"<div style='font-size:16px;background:var(--bc-coeur-100);border-left:3px solid var(--bc-coeur-600);padding:6px 8px;"
                        f"border-radius:4px'>Cartes vues : ici, <b>{rouge(carte.carte_fr(*cartes[k]))}</b> a coûté une levée"
                        + (f" ; <b>{rouge(mieux)}</b> la gardait." if mieux else ".") + "</div>", sanitize=False).classes("w-full")
                # sur la table : la carte jouée bordée de rouge, celle qui gardait la levée bordée de vert dans la main
                css = f".cadre-table [data-c='{carte.carte_fr(*cartes[k])}'] {{ outline: 3px solid var(--bc-coeur-600); outline-offset: 1px; }}"
                if mieux: css += f" .cadre-table [data-c='{mieux}'] {{ outline: 3px solid var(--bc-trefle-600); outline-offset: 1px; }}"
                ui.html(f"<style>{css}</style>", sanitize=False)
            z = next((z for z in p.pensees if z["n"] == k), None)
            if z:                                           # court, comme dans la Démo ; le détail derrière « Plus »
                t_ = carte.texte_pensee(z, p.decl)
                court = t_["raison"] if z["humain"] else carte.justification(z, p.decl)
                ui.html(pensee_html(dict(titre=t_["titre"], raison=court, croyance=[], plan="")), sanitize=False).classes("w-full")
                if t_.get("croyance") or t_.get("plan") or (not z["humain"] and t_["raison"] != court):
                    with ui.expansion("Plus").props("dense header-class='text-primary text-base px-1'").classes("w-full"):
                        ui.html(pensee_html(t_), sanitize=False).classes("w-full")
            if z and z["humain"]:                           # votre carte : l'avis du coach, de lui-même (2026-11-18)
                av = z.get("avis")
                if not av:
                    ui.label("Le coach regarde cette carte…").classes("text-base text-gray-700")
                elif av.get("technique") and av["carte"] != z["carte"]:
                    ui.html(f"<div style='font-size:var(--fs-texte)'>{CASQUETTE_SVG} Le coach aurait joué <b>{rouge(av['carte'])}</b>. "
                            f"<b>{rouge(av['technique'][0][0].upper() + av['technique'][0][1:])}</b> : {rouge(av['technique'][1])}</div>",
                            sanitize=False).classes("w-full")
            elif k == 0: ui.html(pensee_html(dict(titre=f"{SIEGE[carte.LHO[p.decl]]} entame {carte.carte_fr(*cartes[0])}",
                                                  raison="L'entame suit les règles du système (entames.yaml).", croyance=[])),
                                 sanitize=False).classes("w-full")


def comparaison(c, d, data, s):
    """Le contrat du joueur face aux analyses, les séquences, le double mort."""
    r = jouer.comparer(d, F.jeu["seq"], s, lire_analyses(c))
    ui.label("Votre contrat face aux analyses").classes("text-base font-bold mt-4")
    lignes = []
    nom_contrat = lambda texte: re.sub(r" ([NESO])$", lambda m: " " + SIEGE[m[1]], texte)
    for x in r["lignes"]:
        m = x["marge"]; res = "" if x["levees"] is None else ("=" if m == 0 else f"+{m}" if m > 0 else f"<span style='color:var(--bc-coeur-600)'>−{-m}</span>")
        i = "" if x["imp"] is None else ("0" if x["imp"] == 0 else f"{x['imp']:+d}".replace("-", "−"))
        lignes.append(f"<tr><td style='padding:2px 12px;font-weight:600'>{x['nom']}</td><td style='padding:2px 12px'>{rouge(nom_contrat(x['texte']))}</td>"
                      f"<td style='padding:2px 12px;text-align:center'>{res}</td><td style='padding:2px 12px;text-align:right'>{i}</td></tr>")
    ui.html("<table style='font-size:var(--fs-texte);border-collapse:collapse'><tr><th></th><th style='padding:2px 12px;text-align:left'>Contrat</th>"
            "<th style='padding:2px 12px'>Double mort</th><th style='padding:2px 12px'>IMP pour vous</th></tr>" + "".join(lignes) + "</table>",
            sanitize=False)
    ui.label("IMP pour vous : ce que votre contrat gagne (+) ou perd (−) face à celui de l'analyse, au double mort.").classes("text-base text-gray-700")
    if r["ecart"]:
        k = r["ecart"]
        ui.html(f"<div style='font-size:var(--fs-texte);margin-top:6px'>Première différence : <b>{SIEGE[k['siege']]}</b> dit {rouge(k['vous'])}, "
                f"l'analyse {k['nom'].lower()} {rouge(k['reference'])}.</div>", sanitize=False)
    with ui.row().classes("gap-8 items-start mt-2"):
        for x in r["lignes"]:
            with ui.column().classes("gap-0"):
                ui.label(x["nom"]).classes("text-base font-bold")
                ui.html(grille_html(jouer.grille(x["seq"], d["donneur"])), sanitize=False)
    page_dm_par(d)


NOMS = ("mains_fr", "vue_carte", "options_joueurs", "siege_pour", "donne_jouee", "verdict", "faute_de", "changer_mode", "tete_donne", "mode_de", "dernier_pli", "appliquer_plein", "basculer_plein", "outils_table", "vue_jouer", "resume_de", "vue_revoir", "comparaison",)   # rangés dans F par fenetre.construire
