# -*- coding: utf-8 -*-
"""La page de l'application : construire() la bâtit (la barre du haut, les onglets, les dialogues) et range
dans F l'état de la page et les fonctions de chaque module de l'interface.
Les noms de la page (état, fonctions de tous les modules de l'interface) sont dans F (interface.commun) :
fenetre.construire les y range à chaque ouverture de la page."""
from interface.commun import *  # noqa: F401,F403 — les outils communs et F
from interface import vues_donnes, jouer_encheres, jouer_carte, table, onglet_jouer, demo_quiz, editeur, navigation, onglet_fichier, onglet_rapports, onglet_systeme, onglet_reglages

MODULES = (vues_donnes, jouer_encheres, jouer_carte, table, onglet_jouer, demo_quiz, editeur, navigation, onglet_fichier, onglet_rapports, onglet_systeme, onglet_reglages,)


def construire():
    F.__dict__.clear()
    for m in MODULES:
        for nom in m.NOMS: setattr(F, nom, getattr(m, nom))
    ui.colors(primary="#1f6b45")
    ui.add_css("body, .q-layout, .q-page, .q-page-container, .q-tab-panels, .q-tab-panel { background: var(--bc-blanc); } "   # une page toute blanche
               # l'échelle du texte (palette.TEXTE, l'utilisateur, 2026-11-17) : 16 le texte et les boutons, 14 les listes, la
               # navigation et les bulles, 13 les en-têtes de colonnes et les petites étiquettes ; jamais moins de 13
               "body { font-size: var(--fs-texte); } .q-btn { text-transform: none; } .q-btn .block { font-size: var(--fs-texte); } "
               ".entree-barre .block, .q-tab__label { font-size: var(--fs-liste); } .q-tooltip { font-size: var(--fs-liste); } "
               ".q-field__native, .q-field__input { font-size: var(--fs-texte); } .q-notification__message { font-size: var(--fs-texte); } "
               ".text-xs { font-size: var(--fs-petit) !important; line-height: 1.3 !important; } "
               # les titres (2026-11-17) : la page 22, une section 18, le texte 16 — une hiérarchie qui se voit, comme le PDF
               ".titre-page { font-size: var(--fs-grand); line-height: 1.25; } "
               # lisible de loin (des joueurs âgés, un écran de télévision en cours) : le contenu qui change en grand ; les
               # libellés fixes que chacun connaît (onglets, barres latérales, boutons) gardent leur taille (le choix de l'utilisateur)
               ".q-table td { font-size: var(--fs-texte) !important; padding: 4px 6px !important; } "
               ".q-table th { font-size: var(--fs-petit) !important; padding: 4px 6px !important; font-weight: 700; }"
               ".classement th, .classement td { font-size: var(--fs-titre) !important; padding: 6px 10px !important; }" + CSS_AIDE + CSS_CARTES
               + systeme_vue.CSS)
    ui.add_head_html(palette.css() + JS_GLISSE + JS_SENS + JS_SUR_PAGE + JS_SYSTEME)   # les couleurs : --bc-… (palette.py)
    F.z = taille_texte()
    ui.add_head_html(f"<style>:root {{ zoom: {F.z}; --zoom: {F.z}; }}</style>")   # la taille du texte choisie dans Réglages
    F.seances, F.dossier = reglages()
    F.deja = [x for x in seances_bc() if not brouillon.est_brouillon(x)]   # la séance ouverte par défaut : pas le Brouillon
    brouillon.assurer()                                    # le Brouillon existe toujours
    F.choix = {"chemin": T.seance or seance_active() or (F.deja[0] if F.deja else None)}
    F.choix_r = {"quelles": "toutes", "nums": []}            # Rapports, « Les donnes » : le temps de la séance ouverte
    ui.page_title(titre_fenetre(F.choix["chemin"]))
    F.PAGE = lire_etat().get("page") or {}                    # la page ouverte à la dernière fermeture (retenir_page)
    F.vue = {"entree": F.PAGE.get("entree") or "seance"}       # l'entrée choisie dans la barre latérale de l'onglet Donnes
    if F.PAGE.get("version"): F.vue["version"] = F.PAGE["version"]   # Standard | Expert, dans l'onglet Analyse
    F.replis = dict(F.PAGE.get("replis") or {})                # Analyse : « Les … tables » et « Enchères aux tables » ouverts ou non

    F.question = {"f": None, "message": ""}

    F.qui_ = {"noms": [], "choix": None}

    F.jeu = {"cle": None, "mode": lire_etat().get("mode_jouer") or "jouer"}   # la donne en cours dans l'onglet Jouer ; Jouer | Démonstration (gardé)

    F.COUL_BOITE = {"SA": "sa", "♠": "pique", "♥": "coeur", "♦": "carreau", "♣": "trefle"}   # les couleurs des cartons

    F.CARTE_H, F.PAS_COLONNE = CARTE_L * 3 / 2, 26   # une carte (2:3, --carte-h), et ce qu'en montre la suivante dans une colonne du mort
    F.HAUT_NOM_MORT = 12              # le bord de la table (le nom du mort est hors du tapis) : là commencent ses colonnes
    F.BORD_PLIS = 12 + 28             # vos plis gardés : à 12 px du bord, hauts de 28 px
    F.HAUTEUR_TABLE_HAUTE = COTE_TABLE_PX + HAUT_MORT   # la table quand le mort est étalé en haut ou en bas
    F.CROIX_DX, F.CROIX_DY = 60, 50   # le pli en croix : les cartes des côtés à ±60 px du centre, celles du haut et du bas à ±50
    F.BORD_PLI = 54          # une carte jouée : sur la table, devant son joueur, au-delà de ses plis gardés (12 + 30 px)
    F.ICI_PLI = {"haut": f"top:{F.BORD_PLI}px;left:50%;transform:translateX(-50%)",
               "bas": f"bottom:{F.BORD_PLI}px;left:50%;transform:translateX(-50%)",
               "gauche": f"left:{F.BORD_PLI}px;top:50%;transform:translateY(-50%)",
               "droite": f"right:{F.BORD_PLI}px;top:50%;transform:translateY(-50%)"}

    F.ETUI = (135, 240, 30, 14)    # les côtés de l'étui (9:16), l'épaisseur des bandes, le texte
    F.TOURNE = 1.4                 # secondes : la table tourne d'un demi-tour quand le déclarant que vous jouez passe devant vous
    # l'étui en filigrane pendant le jeu de la carte : quelques nuances de la table (tapis-100), sans rouge ni vert
    F.ETUI_PALE = {"fond": "var(--bc-tapis-200)", "bord": "var(--bc-tapis-300)", "rouge": "var(--bc-tapis-300)",
                 "vert": "var(--bc-tapis-300)", "encre": "var(--bc-tapis-500)"}

    F.LARGEUR_CARTON = {"bid": 89, "carre": 50}             # .carton.bid, .carton.carre
    F.VU_CARTON = {"bid": 58, "carre": 36}                   # ce qui dépasse d'un carton recouvert : son indice, ou son onglet

    F.lettres = lambda m: "".join(f"<b>{c}</b>" for c in m)   # un mot écrit tout le long du bord du carton

                # l'étui au centre pendant les enchères seulement ; pendant le jeu de la carte, la table reste libre (l'utilisateur)

    F.ORDRE_MAIN = "♠♥♣♦"                                    # noir, rouge, noir, rouge

    F.face = lambda r: "<span class='dix'>10</span>" if r == "X" else r   # sur une carte à jouer, le dix s'écrit 10 (X dans les textes)

    F.marques_dm = {}                                       # démonstration : {(couleur, rang fr): (levées, meilleure ?)}

    F.COULEUR_TOUCHE = {"T": "♣", "K": "♦", "C": "♥", "P": "♠", "S": "SA"}   # trèfle, carreau, cœur, pique, sans-atout

    F.plein = {"on": False}                                 # Jouer, « table seule » : sans les barres ni les onglets
    ui.keyboard(on_key=F.demo_touche, ignore=["input", "select", "textarea"])   # la démonstration : ← → au clavier

    with ui.dialog() as F.fen_pli, ui.card().classes("items-center"):   # le dernier pli, dans une fenêtre : la table ne change pas
        @ui.refreshable
        def contenu_pli():
            x = F.jeu.get("pli_montre")
            if not x: return
            pli, g = x
            places = F.jeu.get("places") or ("N", "O", "E", "S")
            cartes_ = {s_: (cc, r.translate(carte.FR)) for s_, cc, r in pli}
            premier = pli[0][0] if pli else None
            def nom(s_):                                  # « Samir SAYEGH » : le prénom d'abord, comme à la table
                n_ = (F.jeu.get("noms") or {}).get(s_)
                if not n_: return SIEGE[s_]
                m_ = n_.split(); k_ = next((i for i, w in enumerate(m_) if not w.isupper()), len(m_)) or 1
                return " ".join(m_[k_:] + m_[:k_])
            def case(s_, ou):
                cc, r = cartes_.get(s_, ("", ""))
                h = (f"<div data-c='' class='carte{' r' if cc in '♥♦' else ''}{' gagnante' if s_ == g else ''}"
                     f"{f' premiere p-{ou}' if s_ == premier else ''}' style='margin:0'>{F.face(r)}<br/>{cc}</div>") if cc else ""
                return (f"<div style='display:flex;flex-direction:column;align-items:center;gap:4px'>"
                        f"<div style='font-size:var(--fs-texte);color:var(--bc-tapis-800)'>{nom(s_)}</div>{h}</div>")
            ui.label("Le dernier pli").classes("text-lg font-bold")
            ui.html("<div style='display:grid;grid-template-columns:repeat(3,auto);gap:10px 18px;align-items:center;justify-items:center'>"
                    f"<div></div>{case(places[0], 'haut')}<div></div>"
                    f"{case(places[1], 'gauche')}<div></div>{case(places[2], 'droite')}"
                    f"<div></div>{case(places[3], 'bas')}<div></div></div>", sanitize=False)
            ui.label(f"Gagné par {nom(g)}.").classes("text-base text-gray-700")
            ui.button("Fermer", on_click=F.fen_pli.close).props("flat no-caps")
        F.contenu_pli = contenu_pli
        F.contenu_pli()

    ui.on("dernier_pli", F.dernier_pli)

        # « Donne suivante » et les autres boutons de fin : dans la barre de droite (vue_jouer), jamais sous le contenu

    F.vue_aide = {"k": int(F.PAGE.get("aide") or 0)}          # la section de l'aide montrée

    F.PAGES = {"Fichier": [("nouveau", "Nouveau"), ("ouvrir", "Ouvrir une séance"),   # (Importer : une des trois façons de Nouveau)
                         ("infos", "Infos"), ("exporter", "Exporter…"), ("dossier", "Ouvrir le dossier de travail")],
             "Rapports": [("creer", "Créer les rapports"), ("seance", "Rapports de la séance")],   # (le bilan : bilan.py, à la main)
             "Système": SYSTEME_PAGES,                                      # le système des robots, puis votre fiche
             "Réglages": [("nom", "Votre nom"), ("affichage", "Taille du texte"), ("expert", "L'expert"),
                          ("dossiers", "Dossiers"), ("sauvegarde", "Sauvegarder mes séances"),
                          ("maj", "Mise à jour et nouveautés"), ("contact", "Un problème, une idée ?")]
             + [("design", "Conception de l'interface")] * DEV}     # la barre de gauche de ces onglets
    # les intertitres de la barre de Réglages : vous, vos séances, le programme (l'utilisateur, 2026-11-12 : un peu d'ordre) ;
    # les outils de développement, dans un dépôt Git seulement (DEV : pas chez les membres)
    F.GROUPES_PAGES = {"Système": SYSTEME_GROUPES, "Réglages": {"nom": "Vous", "dossiers": "Vos séances", "maj": "Le programme", "design": "Outils de développement"}}
    F.vue_page = {"Fichier": "nouveau" if F.PAGE.get("fichier") == "importer" else
                           F.PAGE.get("fichier") if F.PAGE.get("fichier") in ("nouveau", "ouvrir", "infos", "exporter", "dossier") else "ouvrir",
                "Rapports": F.PAGE.get("rapports") if F.PAGE.get("rapports") in ("creer", "seance") else "creer",
                "Réglages": F.PAGE.get("reglages") if F.PAGE.get("reglages") in ("affichage", "nom", "dossiers", "expert", "sauvegarde", "maj", "contact") + ("design",) * DEV else
                    "maj" if F.PAGE.get("reglages") == "nouveautes" else "affichage",
                "Système": F.PAGE.get("systeme") if F.PAGE.get("systeme") in dict(SYSTEME_PAGES) else
                    "systeme" if F.PAGE.get("reglages") == "systeme" else "sy-vue"}
    F.sy_cherche = {"t": ""}                                # Système : la recherche

    F.facon = {"k": F.PAGE.get("nouveau") if F.PAGE.get("nouveau") in ("bws", "pbn", "themes") else   # Fichier, Nouveau : la façon choisie
             ("bws" if F.PAGE.get("fichier") == "importer" else "themes")}

    F.sauve = {"fait": "", "faute": ""}                     # Réglages, Sauvegarder mes séances
    F.a_importer = {"chemin": None, "prop": None, "titre": "", "nom": "", "nom_touche": False, "lecture": False, "faute": ""}

    F.vue_haut = {"cle": None}

    F.expert_msg = {"texte": "", "faute": False}

    F.vu = {"fini": None}; F.vu_d = {"fini": None}; F.vu_i = {"fini": None}

    with ui.header(elevated=False).classes("bg-white text-primary px-2 py-0 border-b border-gray-300") as F.entete:   # la barre de menus
        with ui.row().classes("w-full items-center justify-between no-wrap"):
            with ui.button(on_click=lambda: F.basculer_liste()).props("flat dense round color=grey-7").classes("mr-1") \
                    as F.bouton_barre:                     # montrer / cacher la barre de gauche, à sa place fixe : l'icône d'un
                F.icone_barre = ui.html(icone_panneau(False), sanitize=False)   # panneau latéral, pas un menu (l'utilisateur)
            with ui.tabs().props("no-caps dense inline-label align=left active-color=primary indicator-color=primary").classes("text-gray-700 grow") as F.onglets:   # les onglets, dans la barre
                F.o_fichier = ui.tab("Fichier")                     # une page, comme Rapports et Réglages : sa barre à gauche
                F.o_donnes = ui.tab("Donnes")
                F.o_jouer = ui.tab("Jouer")
                F.o_analyse = ui.tab("Analyse")
                F.o_rapports = ui.tab("Rapports")
                F.o_systeme = ui.tab("Système")                     # le système des robots et votre fiche : comme Réglages, il ne
                                                                  # dépend pas de la séance ouverte, à côté de lui (2026-11-16)
                F.o_reglages = ui.tab("Réglages")
                F.o_aide = ui.tab("Aide").classes("hidden")          # la page d'aide : montrée par le bouton de droite
            @ui.refreshable
            def badge_brouillon():                               # le Brouillon, toujours à portée : ouvert d'un clic
                n_ = brouillon.nombre()
                with ui.button(on_click=lambda: F.ouvrir_brouillon()).props("flat no-caps dense").classes("px-3") \
                        .tooltip("Le Brouillon : les donnes que vous y avez mises, pour préparer un cours"):
                    with ui.row().classes("items-center gap-1 no-wrap"):
                        ui.icon("shopping_basket", size="20px").classes("text-gray-700")
                        ui.label("Brouillon").classes("text-gray-800")
                        if n_: ui.label(str(n_)).style("background:var(--bc-success-bg-subtle);color:var(--bc-success-text-emphasis);"
                                                       "border-radius:10px;padding:0 7px;font-size:13px;font-weight:700")
            F.badge_brouillon = badge_brouillon
            F.badge_brouillon()
            with ui.button(on_click=lambda: F.ouvrir_aide()).props("flat no-caps dense").classes("px-3") as F.aide:   # l'aide de la page ouverte
                with ui.row().classes("items-center gap-1 no-wrap"):   # une icône de couleur : l'aide se voit (l'utilisateur, 2026-11-12)
                    ui.icon("help", size="22px").style("color:var(--bc-pique-600)")
                    ui.label("Aide")
            F.onglets.on_value_change(lambda e: (F.aide.classes(add="bg-green-50 font-bold") if e.value in (F.o_aide, "Aide")
                                               else F.aide.classes(remove="bg-green-50 font-bold"), F.montrer_barre(), F.barre_seance.refresh(),
                                               F.vue_analyse.refresh(), F.vue_jouer.refresh(), F.montrer_controles(), F.retenir_page(),
                                               e.value in (F.o_fichier, "Fichier") and F.rafraichir_fichier()))

    with ui.left_drawer(value=False, fixed=True, bordered=True).props(f"width={LARGEUR_BARRE} behavior=desktop") \
            .classes("p-2 gap-0").style(f"background:{GRIS_BARRE}") as F.tiroir:      # la barre latérale de des onglets Donnes et Analyse : bord gauche, toute la hauteur
        F.barre_seance()

    with ui.column().classes("w-full px-0 pt-0 pb-6 gap-0"):   # la marge de la page seule (16 px), comme les barres (l'utilisateur)

        with ui.tab_panels(F.onglets, value=F.o_donnes, animated=False).classes("w-full"):
            with ui.tab_panel(F.o_donnes).classes("px-0 pt-0"):   # en haut comme Jouer : le titre de la donne au même endroit
                @ui.refreshable
                def nouveau():
                    neuf = next((b for b in reglages()[0] if not deja_importe(b)), None)
                    if not neuf or I.actif: return
                    with ui.row().classes("w-full max-w-xl items-center justify-between no-wrap bg-green-50 rounded px-3 py-2 mb-3"):
                        with ui.column().classes("gap-0"):
                            ui.label(f"Nouveau tournoi dans Bridgemate, du {date_lisible(neuf)}").classes("text-base")
                            ui.label(os.path.basename(neuf)).classes("text-base text-gray-700 break-all")
                        ui.button("Importer…", on_click=lambda b=neuf: F.preparer_import(b)).classes("shrink-0")
                F.nouveau = nouveau
                F.barre_i = ui.linear_progress(value=0, show_value=False).props("size=16px rounded indeterminate").classes("max-w-xl")
                F.texte_i = ui.label("").classes("text-base")
                F.faute_i = ui.label("").classes("text-base text-red-800")
                for F.x_ in (F.barre_i, F.texte_i, F.faute_i): F.x_.set_visibility(False)   # vides : pas de place prise au-dessus de la donne
                F.faute_i.bind_visibility_from(F.faute_i, "text", backward=bool)
                F.vue_seance()

            with ui.tab_panel(F.o_jouer).classes("px-0 pt-0"):   # en haut, la marge de gauche seulement (l'utilisateur, 2026-11-11)
                F.vue_jouer()

            with ui.tab_panel(F.o_analyse).classes("px-0 pt-0 gap-3"):
                with ui.column().classes("w-full gap-3 pb-3 border-b border-gray-200") as F.controles:   # fixe : la barre y avance
                    with ui.row().classes("w-full items-center gap-4 no-wrap"):
                        F.creer = ui.button("Lancer l'analyse", icon="play_arrow", on_click=lambda: F.demarrer()).classes("text-base px-6")
                    F.barre = ui.linear_progress(value=0, show_value=False).props("size=16px rounded").classes("max-w-xl")
                    F.texte = ui.label("").classes("text-base")
                    F.stop = ui.button("Annuler", on_click=annuler).props("outline")
                    F.faute = ui.label("").classes("text-base text-red-800")
                    F.fait_a = ui.label("").classes("text-base text-primary")
                F.vue_analyse()

            F.pages_ui = {}
            with ui.tab_panel(F.o_rapports).classes("px-0 pt-0 gap-4 max-w-xl"):
                onglet_rapports.panneau()

            with ui.tab_panel(F.o_systeme).classes("px-0 pt-0 gap-3"):   # Système : lecture seule (systeme_vue.py)
                onglet_systeme.panneau()

            with ui.tab_panel(F.o_reglages).classes("px-0 pt-0 gap-5 max-w-xl"):
              onglet_reglages.panneau()

            F.montrer_pages()                                # chaque onglet à pages s'ouvre sur sa première page

            with ui.tab_panel(F.o_aide).classes("px-0 pt-0").style("max-width:1100px"):   # une page comme les autres : un onglet la quitte
                F.page_aide()                                    # une section à la fois, choisie dans la barre de gauche

            with ui.tab_panel(F.o_fichier).classes("px-0 pt-0 max-w-3xl") as F.panneau_fichier, \
                    ui.column().classes("w-full gap-0") as F.pages_ui["nouveau"]:   # Fichier : ses pages, la première Nouveau
                onglet_fichier.panneau()

    onglet_fichier.pages_ouvrir_nouveau()
    with ui.dialog() as F.confirmation_m, ui.card().classes("w-full max-w-md"):
        ui.label("Cette donne a une analyse de l'expert. Si vous la modifiez, cette analyse est mise de côté (gardée dans "
                 "une copie datée) : il faudra la redemander à Claude pour cette donne. Les autres donnes gardent la leur.").classes("text-base")
        with ui.row().classes("gap-3 justify-end w-full"):
            ui.button("Annuler", on_click=lambda: F.confirmation_m.close()).props("flat")
            ui.button("Modifier quand même", icon="edit", on_click=lambda: F.modifier_quand_meme())

    with ui.dialog() as F.confirmation, ui.card().classes("w-full max-w-md"):
        F.confirmation_texte = ui.label("").classes("text-base")
        with ui.row().classes("gap-3 justify-end w-full"):
            ui.button("Annuler", on_click=lambda: F.confirmation.close()).props("flat")
            ui.button("Supprimer", icon="delete", on_click=lambda: F.supprimer()).props("color=red")

    with ui.dialog() as F.remettre_fiche_d, ui.card().classes("w-full max-w-md"):
        ui.label("Préremplir toute la carte avec les choix standard du SEF 2024 (ce que joue Bridge Coach) ? Les lignes que "
                 "vous avez changées sont effacées ; les noms, les IV, le niveau et vos accords particuliers restent.") \
            .classes("text-base")
        with ui.row().classes("gap-3 justify-end w-full"):
            ui.button("Annuler", on_click=lambda: F.remettre_fiche_d.close()).props("flat")
            ui.button("Préremplir", icon="restart_alt", on_click=lambda: F.remettre_fiche()).props("color=red")

    with ui.dialog() as F.qui_d, ui.card().classes("w-full max-w-md gap-3"):   # après le premier import : qui êtes-vous ?
        @ui.refreshable
        def fenetre_qui():
            ui.label("Qui utilise Bridge Coach ?").classes("text-lg font-bold")
            ui.label("Si vous le voulez, choisissez votre nom parmi les joueurs de ce tournoi : vos tables seront surlignées "
                     "partout, et les rapports faits pour votre paire. C'est facultatif : sans nom, vous restez « inconnu ». "
                     "Vous pourrez le changer dans Réglages, Votre nom.").classes("text-base text-gray-700")
            ui.select({n: n for n in F.qui_["noms"]}, with_input=True, label="Votre nom",
                      on_change=lambda e: F.qui_.update(choix=e.value)).classes("w-full").props("outlined")
            with ui.row().classes("w-full justify-end gap-3"):
                ui.button("Rester inconnu", on_click=lambda: F.qui_d.close()).props("flat")
                ui.button("C'est moi", icon="check", on_click=lambda: F.c_est_moi()).props("unelevated")
        F.fenetre_qui = fenetre_qui
        F.fenetre_qui()

    with ui.dialog() as F.question_d, ui.card().classes("w-full max-w-lg gap-3"):   # « Demander à l'expert » : trois gestes
        @ui.refreshable
        def fenetre_question():
            f_ = F.question["f"]
            if not f_: return
            ui.label("Demander à l'expert").classes("text-lg font-bold")
            ui.label("Bridge Coach a préparé la donne pour l'expert. Trois gestes :").classes("text-base")
            etape_ = lambda k, t: ui.html(f"<div style='font-size:16px'><b>{k}.</b> {t}</div>", sanitize=False)
            etape_(1, f"Ouvrez l'expert ({html_.escape(nom_outil(url_expert()))}) dans votre navigateur.")
            ui.button("Ouvrir l'expert", icon="open_in_new",
                      on_click=lambda: ouvrir(question_expert.adresse_avec_message(url_expert(), F.question["message"]))).props("unelevated")
            etape_(2, f"Glissez-y le fichier <b>{html_.escape(os.path.basename(f_))}</b> :")
            ui.button("Montrer le fichier", icon="folder_open", on_click=lambda: montrer_fichier(F.question["f"])).props("outline")
            etape_(3, "Collez le message (⌘V sur Mac, Ctrl+V sous Windows ; il est déjà copié), puis envoyez. L'expert vous "
                      "salue et vous demande ce que vous voulez savoir.")
            ui.html(f"<div style='font-size:var(--fs-texte);color:var(--bc-tapis-700);background:var(--bc-tapis-100);padding:6px 10px;border-radius:6px'>"
                    f"{html_.escape(F.question['message'])}</div>", sanitize=False)
            with ui.row().classes("w-full justify-end"):
                ui.button("Fermer", on_click=lambda: F.question_d.close()).props("flat")
        F.fenetre_question = fenetre_question
        F.fenetre_question()

    with ui.dialog() as F.corbeille_d, ui.card().classes("w-full max-w-md"):
        F.corbeille_texte = ui.label("").classes("text-base")
        with ui.row().classes("gap-3 justify-end w-full"):
            ui.button("Annuler", on_click=lambda: F.corbeille_d.close()).props("flat")
            ui.button("Mettre à la corbeille", icon="delete", on_click=lambda: F.mettre_a_la_corbeille()).props("color=red")
    F.numero_c = {"c": None}; F.vider_apres = {"c": None}
    with ui.dialog() as F.numero_d, ui.card().classes("w-full max-w-md"):   # Infos : donneur et vulnérabilité selon le numéro
        F.numero_texte = ui.label("").classes("text-base")
        with ui.row().classes("gap-3 justify-end w-full"):
            ui.button("Annuler", on_click=lambda: (F.numero_d.close(), F.page_infos.refresh())).props("flat")
            ui.button("Changer", on_click=lambda: F.appliquer_numero_(F.numero_c["c"])).props("unelevated")
    with ui.dialog() as F.vider_d_b, ui.card().classes("w-full max-w-md"):   # Infos du Brouillon : le vider
        ui.label("Vider le Brouillon ? Ses donnes, leurs analyses et vos parties jouées dessus partent. La version d'avant "
                 "est gardée (Versions gardées, dans Donnes, Séance).").classes("text-base")
        with ui.row().classes("gap-3 justify-end w-full"):
            ui.button("Annuler", on_click=lambda: F.vider_d_b.close()).props("flat")
            ui.button("Vider", icon="remove_shopping_cart", on_click=lambda: F.vider_brouillon_()).props("color=red")
    with ui.dialog() as F.vider_apres_d, ui.card().classes("w-full max-w-md"):   # après « Enregistrer sous… »
        ui.label("Le cours est enregistré. Vider le Brouillon pour le prochain ?").classes("text-base")
        with ui.row().classes("gap-3 justify-end w-full"):
            ui.button("Garder le Brouillon", on_click=lambda: (F.vider_apres_d.close(), F.choisir(F.vider_apres["c"]),
                                                                 F.onglets.set_value(F.o_fichier), F.voir_page("Fichier", "infos"))).props("flat")
            ui.button("Vider le Brouillon", icon="remove_shopping_cart", on_click=lambda: F.vider_brouillon_(F.vider_apres["c"])).props("unelevated")
    with ui.dialog() as F.vider_d, ui.card().classes("w-full max-w-md"):   # Ouvrir une séance, la corbeille : la vider
        F.vider_texte = ui.label("").classes("text-base")
        with ui.row().classes("gap-3 justify-end w-full"):
            ui.button("Annuler", on_click=lambda: F.vider_d.close()).props("flat")
            ui.button("Vider la corbeille", icon="delete_sweep", on_click=lambda: F.vider_corbeille_()).props("color=red")

    F.envoi_x = ui.upload(on_upload=lambda e: F.recu_x(e), auto_upload=True, max_files=1).props('accept=".json"').classes("hidden")

    onglet_fichier.pages_exporter_infos()
    F.montrer_pages()

    F.maj_vue = {"version": None}

    F.a_jeter = {"c": None}                                  # la séance que la fenêtre de confirmation mettra à la corbeille

    ui.on("systeme_vers", lambda e: F.aller_sequence(SYSTEME_ANCRES.get(e.args, "")) if isinstance(e.args, str) else None)
    ui.on("aide", lambda e: F.ouvrir_aide(e.args if isinstance(e.args, str) else None))   # les « ? » des titres (titre_page)
    try:                                                   # un tournoi pas encore importé : son import s'ouvre, une fois par fichier
        F.neuf_bws = next((b for b in reglages()[0] if not deja_importe(b)), None)
    except OSError:
        F.neuf_bws = None
    if F.neuf_bws and lire_etat().get("bws_propose") != F.neuf_bws:
        ecrire_etat(bws_propose=F.neuf_bws)
        ui.timer(.6, lambda: F.preparer_import(F.neuf_bws), once=True)
    F.e0 = lire_etat()
    if not F.e0.get("licences_ajoutees"):                    # une fois : les séances d'avant la 1.9 reçoivent les licences
        for F.c_ in rapport.glob_seances("*" + rapport.BC):
            try: fichiers.ajouter_licences(F.c_)
            except Exception: pass
        ecrire_etat(licences_ajoutees=True)
    retenir_licence(F.e0.get("mon_nom"), moi.nom(), F.e0.get("joueur_jouer"))
    F.vue_v, F.version_ = lire_etat().get("version_vue"), maj.version_locale()
    if F.vue_v != F.version_:                                  # après une mise à jour, une fois : quoi de neuf (help/nouveautes.html)
        ecrire_etat(version_vue=F.version_)
        F.neuf = nouveautes(F.vue_v, F.version_) if F.vue_v else []   # (la première installation : rien à montrer)
        if F.neuf:
            with ui.dialog() as F.quoi_neuf, ui.card().classes("w-full max-w-lg gap-2"):
                F.titre_ = f"Quoi de neuf dans Bridge Coach {F.version_} ?"
                ui.label(F.titre_).classes("text-lg font-bold")
                for F.v, F.h in F.neuf:
                    if len(F.neuf) > 1: ui.label(f"Version {F.v}").classes("text-base font-bold text-gray-700 mt-1")
                    ui.html(F.h, sanitize=False).classes("aide")
                with ui.row().classes("gap-3 justify-end w-full mt-2"):
                    ui.button("Toutes les nouveautés", icon="history",
                              on_click=lambda: (F.quoi_neuf.close(), F.onglets.set_value(F.o_reglages), F.voir_page("Réglages", "maj"))).props("flat")
                    ui.button("C'est noté", on_click=lambda: F.quoi_neuf.close()).props("unelevated")
            ui.timer(1.0, F.quoi_neuf.open, once=True)
    ui.timer(.4, F.rafraichir)
    ui.timer(.5, lambda: F.montrer_titre(), once=True)
    F.pages_ui["systeme"].move(F.systeme_col)                # votre fiche de conventions : dans l'onglet Système (2026-11-16)
    F.depart = {"Fichier": F.o_fichier, "Jouer": F.o_jouer, "Analyse": F.o_analyse, "Système": F.o_systeme, "Rapports": F.o_rapports, "Réglages": F.o_reglages,
              "Aide": F.o_aide}.get(F.PAGE.get("onglet"))
    if F.depart: ui.timer(.05, lambda: F.onglets.set_value(F.depart), once=True)   # l'onglet de la dernière fois
    F.montrer_barre(); F.montrer_controles()       # la fenêtre naît avec le titre du programme seul
    F.rafraichir()
