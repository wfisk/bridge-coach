# -*- coding: utf-8 -*-
"""Les vues de l'onglet Donnes et de l'Analyse, l'expert, le Brouillon, la barre de droite d'une donne.
Les noms de la page (état, fonctions de tous les modules de l'interface) sont dans F (interface.commun) :
fenetre.construire les y range à chaque ouverture de la page."""
from interface.commun import *  # noqa: F401,F403 — les outils communs et F


def page_vide(icone, titre, texte, actions):
    """Une page encore vide dit ce qui manque et mène à l'étape suivante d'un clic (l'utilisateur, 2026-11-17) :
    une icône, un titre, une phrase, un ou deux boutons (le premier plein)."""
    with ui.column().classes("w-full items-center text-center gap-3 mt-10").style("max-width:560px;margin-left:auto;margin-right:auto"):
        ui.icon(icone, size="48px").style("color:var(--bc-tapis-400)")
        ui.label(titre).classes("font-bold").style("font-size:var(--fs-titre)")
        ui.label(texte).classes("text-base text-gray-700")
        with ui.row().classes("gap-3 justify-center"):
            for i, (nom, ic, fn) in enumerate(actions):
                ui.button(nom, icon=ic, on_click=fn).props(("unelevated" if i == 0 else "outline") + " no-caps")


def sans_seance():
    F.page_vide("style", "Aucune séance ouverte",
              "Importez un tournoi de Bridgemate, créez des donnes d'entraînement, ou rouvrez une séance déjà faite.",
              [("Créer une séance", "add", lambda: (F.onglets.set_value(F.o_fichier), F.voir_page("Fichier", "nouveau"))),
               ("Ouvrir une séance", "folder_open", lambda: (F.onglets.set_value(F.o_fichier), F.voir_page("Fichier", "ouvrir")))])


@ui.refreshable
def vue_seance():
    c = F.choix["chemin"]; data = lire_seance(c)
    if not data:
        F.sans_seance(); return
    if F.vue["entree"] not in dict(F.entrees_de(data)): F.vue["entree"] = "seance"
    with ui.column().classes("w-full gap-3 min-w-0"):
        e = F.vue["entree"]
        ok, _ = edition.modifiable(c)
        if e == "seance":
            F.nouveau()                                  # un tournoi Bridgemate pas encore importé : sur la page Séance seulement
            page_seance(data, c)
            if brouillon.est_brouillon(c) and data.get("donnes"):   # le Brouillon : garder le cours d'ici, pas seulement
                def vers_enregistrer():                             # depuis Fichier, Infos (2026-11-18, le cours d'essai)
                    F.infos_ui.update(copie=True, faute=""); F.onglets.set_value(F.o_fichier); F.voir_page("Fichier", "infos"); F.page_infos.refresh()
                with ui.row().classes("items-center gap-3 mt-2"):
                    ui.button("Enregistrer le cours…", icon="save_as", on_click=vers_enregistrer).props("unelevated no-caps")
                    ui.label("en fait une séance datée d'aujourd'hui, avec ces donnes et leurs analyses.").classes("text-base text-gray-700")
            if data.get("alertes"): page_alertes(data)
            if ok: F.page_versions(c)
        elif e == "joueurs": page_joueurs(data)
        elif e == "alertes": page_alertes(data)
        elif not any(f"d{x['n']}" == e for x in data["donnes"]):   # Options, Classement de l'onglet Jouer : la séance
            page_seance(data, c)
        else:
            d = next(d for d in data["donnes"] if f"d{d['n']}" == e)
            if ok and (d.get("a_completer") or F.vue.get("edition") == d["n"]):
                F.editeur_donne(c, d)                    # une donne à compléter s'ouvre déjà en modification
            else:
                with ui.column().classes("w-full gap-3").style(f"padding-right:{LARGEUR_PANNEAU}px"):
                    page_donne(d, moi.paires(data), moi.tour_de(data, d["n"]), recommandee(F.choix["chemin"], d))
                with F.panneau_droit(d):
                    if ok: ui.button("Modifier la donne", icon="edit", on_click=lambda n=d["n"]: F.modifier(c, n)).props("outline").classes("w-full")


@ui.refreshable
def vue_analyse():
    c = F.choix["chemin"]; data = lire_seance(c)
    if not data: return
    std, exp = lire_analyses(c)
    e = F.entree_effective(data)
    if e == "standard":
        ui.label(f"Analyse du coach · séance du {data['session']['date']}").classes("text-lg font-bold")
        page_analyse_resume(data, std, False); return
    if e == "expert":
        ui.label(f"Analyse expert · séance du {data['session']['date']}").classes("text-lg font-bold")
        page_analyse_resume(data, exp, True)
        F.etapes_expert(c); return
    d = next((x for x in data["donnes"] if f"d{x['n']}" == e), None)
    if d is None: return
    n = str(d["n"])
    versions = [v for v, a in (("Standard", std), ("Expert", exp)) if a and (a.get("donnes") or {}).get(n, {}).get("enc")]
    if not versions:
        titre_donne(d)
        F.page_vide("insights", "Pas encore d'analyse",
                  "Le coach analyse toute la séance en quelques minutes : les enchères qu'il recommande, l'entame, le plan de jeu.",
                  [("Lancer l'analyse", "play_arrow", lambda: (F.aller("standard"), F.demarrer()))]); return
    if F.vue.get("version") not in versions: F.vue["version"] = "Expert" if "Expert" in versions else versions[0]
    a = (exp if F.vue["version"] == "Expert" else std)["donnes"][n]
    if F.vue["version"] == "Expert":                    # le conseil du coach avant l'avis de l'expert (même contrat)
        a = rapport.coach_pour_expert(d, a, (std or {}).get("donnes", {}).get(n))
    repli = (std or {}).get("donnes", {}).get(n, {})   # l'expert reprend du programme ce qu'il n'écrit pas (cartes vues…)
    with ui.column().classes("w-full gap-3").style(f"padding-right:{LARGEUR_PANNEAU}px"):
        page_analyse(d, a, repli, F.vue["version"], data, c, F.replis, F.retenir_page)
    with F.panneau_droit(d, par=False):
        if len(versions) > 1:                           # Standard | Expert, deux moitiés égales
            ui.toggle({v: NOM_VERSION[v] for v in versions}, value=F.vue["version"], on_change=lambda ev: (F.vue.update(version=ev.value), F.vue_analyse.refresh(), F.retenir_page())) \
                .props("no-caps spread toggle-color=primary").classes("w-full")
        else:
            ui.label("Analyse " + NOM_VERSION[F.vue['version']].lower().replace("coach", "du coach").replace("expert", "de l'expert")).classes("text-base font-bold")
        c_, decl = jouer.contrat(jouer.sequence(a["enc"], d["donneur"]), d["donneur"])
        lignes = [f"<b>Contrat recommandé</b> : {rouge(c_) if decl else 'passe générale'}" + (f" {SIEGE[decl]}" if decl else "")]
        e_ = a.get("entame")
        if isinstance(e_, dict) and e_.get("carte"):
            lignes.append(f"<b>Entame</b> : {rouge(e_['carte'])} ({SIEGE.get(e_.get('joueur'), e_.get('joueur', ''))})")
        if d.get("par"): lignes.append(par_html(d))
        ui.html("<div style='font-size:var(--fs-texte);line-height:1.6'>" + "<br/>".join(lignes) + "</div>", sanitize=False)
        if d.get("dm"): ui.html(dm_html(d), sanitize=False).classes("w-full")
        with ui.column().classes("w-full gap-2 mt-3"):    # de l'analyse à la table, ou sur papier pour un cours
            ui.button("Rejouer cette donne", icon="play_arrow", on_click=lambda: F.rejouer_donne(d)).props("outline no-caps").classes("w-full")
            ui.button("Imprimer cette donne", icon="print", on_click=lambda: F.imprimer_donne(c, d)) \
                .props("outline no-caps").classes("w-full").set_enabled(not (T.actif or D.actif or I.actif))
            F.bouton_expert(c, d, True, analyse=True)


def bouton_expert(c, d, fin_, analyse=False, pleine=True):
    """« Demander à l'expert », avec le ✦ vert de l'expert dans les rapports (l'utilisateur, 2026-11-13). pleine : sur
    toute la largeur, avec son texte (fin de donne, Analyse) ; sinon le ✦ seul, sur la ligne de l'Indice, le texte
    dans la bulle."""
    with ui.button(on_click=lambda: F.demander_expert(c, d, fin_, analyse=analyse)) \
            .props("outline no-caps" + ("" if pleine else " dense")).classes("w-full text-base" if pleine else "px-2") as b:
        ui.html(f"<span style='color:var(--bc-trefle-800);font-size:{18 if pleine else 20}px"   # le vert de l'expert (build_pdf.AVIS)
                f"{';margin-right:6px' if pleine else ''}'>✦</span>" + ("Demander à l'expert" if pleine else ""), sanitize=False)
    b.tooltip(("" if pleine else "Demander à l'expert : ") + "une question sur cette donne, ce que vous voyez"
              + ("" if fin_ else ", sans les mains cachées"))
    return b


def demander_expert(c, d, apres, analyse=False):
    """Écrit le fichier de la question (question_expert), copie le court message, et montre les trois gestes."""
    data = lire_seance(c) or {}
    p_ = None if analyse else (F.jeu.get("partie") if F.jeu.get("cle") == (c, d["n"]) else None)
    siege = (F.siege_pour(c, d) or "S") if analyse else F.jeu.get("siege") or "S"
    seq = [] if analyse else F.jeu["seq"] if apres else F.jeu["seq"][:F.jeu.get("affiche", len(F.jeu["seq"]))]
    contenu = question_expert.fichier(data, d, siege, seq, p_, apres, lire_analyses(c) if apres else (None, None),
                                      prenom_expert())
    try:
        F.question["f"] = question_expert.ecrire(c, contenu, d["n"], apres)
    except OSError:
        ui.notify("Le fichier pour l'expert n'a pas pu être écrit.", type="negative"); return
    F.question["message"] = question_expert.message(os.path.basename(F.question["f"]))
    ui.clipboard.write(F.question["message"])
    F.fenetre_question.refresh(); F.question_d.open()


def demander_qui(c):
    """Après le premier import, une fois : « Qui utilise Bridge Coach ? », parmi les joueurs de ce tournoi."""
    data = lire_seance(c) or {}
    noms_ = sorted({(j.get("nom") or "").strip() for v in (data.get("joueurs") or {}).values() for j in v} - {""}, key=str.lower)
    ecrire_etat(qui_demande=True)
    if not noms_: return
    F.qui_.update(noms=noms_, choix=None); F.fenetre_qui.refresh(); F.qui_d.open()


def c_est_moi():
    n_ = F.qui_["choix"]
    if not n_: return
    ecrire_etat(mon_nom=n_); retenir_licence(n_)
    if not moi.nom(): ecrire_etat(moi=n_)
    F.qui_d.close(); F.vue_seance.refresh(); F.resultats.refresh()
    try: F.ma_licence.refresh(); F.choix_moi.set_options(F.options_joueurs(moi.nom()), value=moi.nom() or "")
    except (NameError, AttributeError): pass
    ui.notify(f"Bonjour {question_expert.prenom_de(n_)} ! Vos tables sont maintenant surlignées.")


def imprimer_fiche(quoi):
    """La feuille de prévisions (« feuille »), la carte FFB complète (« ffb ») ou la fiche pour le partenaire
    (« partenaire ») en PDF, dans documents/, ouverte : de là on l'imprime ou on l'envoie."""
    try:
        f_ = {"feuille": fiche_conventions.pdf_feuille, "ffb": fiche_conventions.pdf_ffb,
              "partenaire": fiche_conventions.pdf_partenaire}[quoi]()
    except Exception:
        ui.notify("La fiche n'a pas pu être écrite.", type="negative"); return
    ouvrir(f_)
    ui.notify(f"La fiche est ouverte : imprimez-la depuis là. Elle est gardée dans {f_}", multi_line=True, timeout=8000)


def remettre_fiche():
    fiche_conventions.tout_remettre(); F.remettre_fiche_d.close()
    ui.notify("La carte est préremplie avec les choix standard du SEF 2024.")
    ui.navigate.reload()


def rejouer_donne(d):
    """Analyse → Jouer, sur la même donne, au début de ses enchères."""
    F.jeu["mode"] = "jouer"; ecrire_etat(mode_jouer="jouer")
    F.onglets.set_value(F.o_jouer); F.aller(f"d{d['n']}")


def imprimer_donne(c, d):
    """La page de cette donne seule, en PDF (rapport.py --rapports --donne=N), ouverte dès qu'elle est prête."""
    if T.actif or D.actif or I.actif: return
    T.__init__(0.0, "Impression"); T.genre = "imprimer"; T.seance = c; T.texte = f"Donne {d['n']} : préparation de la page"
    demarrer_travail(T, [os.path.join(ICI, "rapport.py"), c, "--rapports", f"--donne={d['n']}"]
                     + [f"--niveau={niveau_rapport()}"])
    ui.notify(f"La donne {d['n']} se prépare : le PDF s'ouvre dans un instant.")


def panneau_droit(d=None, par=True):
    """La barre de droite d'une donne, la même dans Donnes, Jouer et Analyse : même largeur, même gris ; avec d, l'étui
    et le par (le nom de la donne, son donneur et sa vulnérabilité sont dans le titre de la page, titre_donne). Renvoie la colonne, à remplir."""
    col = ui.column().classes("gap-3 p-4 overflow-y-auto").style(
        f"position:fixed;top:var(--haut-panneau, {HAUTEUR_BARRE}px);right:0;bottom:0;width:{LARGEUR_PANNEAU}px;background:{GRIS_BARRE};"
        "border-left:1px solid var(--bc-tapis-200);z-index:1;overflow-x:hidden")
    if d is not None:
        with col:                                      # « Donne N », le donneur, la vulnérabilité et le thème sont dans le
            with ui.row().classes("w-full justify-center"):   # titre de la page (titre_donne), comme dans Jouer
                ui.html(F.etui(d, ("N", "O", "E", "S"), petit=True), sanitize=False)
            if par and d.get("par"): ui.html(f"<div style='font-size:var(--fs-texte)'>{par_html(d)}</div>", sanitize=False)
            F.bouton_brouillon(d)
    return col


def bouton_brouillon(d):
    """« Ajouter au Brouillon » ; « ✓ Dans le Brouillon » (un clic l'en retire) ; dans le Brouillon lui-même :
    « Retirer du Brouillon »."""
    c = F.choix["chemin"]
    if not c or not os.path.isfile(c) or d.get("a_completer"): return
    if brouillon.est_brouillon(c):
        ui.button("Retirer du Brouillon", icon="remove_shopping_cart", on_click=lambda: F.brouillon_retirer(c, d["n"])) \
            .props("outline no-caps color=grey-8").classes("w-full")
    elif brouillon.numero_de(c, d["n"]):
        # discret : une case cochée, pas le bouton le plus voyant de la page (l'utilisateur, 2026-11-17)
        ui.button("Dans le Brouillon", icon="check_circle", on_click=lambda: F.brouillon_retirer(c, d["n"])) \
            .props("flat dense no-caps").classes("w-full").style("color:var(--bc-trefle-700);background:var(--bc-trefle-50)") \
            .tooltip("Un clic l'en retire")
    else:
        ui.button("Ajouter au Brouillon", icon="add_shopping_cart", on_click=lambda: F.brouillon_ajouter(c, d["n"])) \
            .props("flat dense no-caps").classes("w-full").style("color:var(--bc-tapis-700)") \
            .tooltip("Le Brouillon prépare un cours : Fichier, Ouvrir une séance")


def brouillon_change():
    """Après un ajout ou un retrait : le compteur de la barre du haut, et les pages de la donne."""
    F.badge_brouillon.refresh()
    try: F.vue_seance.refresh(); F.vue_analyse.refresh(); F.vue_jouer.refresh(); F.barre_seance.refresh(); F.liste.refresh()
    except (NameError, AttributeError): pass


def brouillon_ajouter(c, n):
    k = brouillon.ajouter(c, n)
    ui.notify(f"Donne {n} ajoutée au Brouillon (donne {k} du Brouillon).")
    F.brouillon_change()


def brouillon_retirer(c, n):
    brouillon.retirer(c, n)
    if brouillon.est_brouillon(c): F.vue["entree"] = "seance"
    ui.notify("Donne retirée du Brouillon.")
    F.brouillon_change()


def ouvrir_brouillon():
    F.choisir(brouillon.assurer()); F.onglets.set_value(F.o_donnes)


NOMS = ("page_vide", "sans_seance", "vue_seance", "vue_analyse", "bouton_expert", "demander_expert", "demander_qui", "c_est_moi", "imprimer_fiche", "remettre_fiche", "rejouer_donne", "imprimer_donne", "panneau_droit", "bouton_brouillon", "brouillon_change", "brouillon_ajouter", "brouillon_retirer", "ouvrir_brouillon",)   # rangés dans F par fenetre.construire
