# -*- coding: utf-8 -*-
"""L'onglet Rapports : les options et la liste des rapports de la séance.
Les noms de la page (état, fonctions de tous les modules de l'interface) sont dans F (interface.commun) :
fenetre.construire les y range à chaque ouverture de la page."""
from interface.commun import *  # noqa: F401,F403 — les outils communs et F


def panneau():
    """Le contenu de l'onglet Rapports."""
    @ui.refreshable
    def options_rapports():
        """Les options, légères (l'utilisateur, 2026-11-13) : une case à cocher pour chaque chose qu'on ajoute,
        rien d'expliqué sous chaque ligne ; ce qui demande « Vous êtes » est grisé sans lui, la raison à côté.
        Les donnes : toutes, sauf « à revoir » ou « choisir » (l'une décoche l'autre), l'ordre joué ; l'analyse :
        le coach, puis l'expert (sans le coach : les faits seulement) ; les pages en plus."""
        c = F.choix["chemin"]
        data = lire_seance(c) if c else None
        nums_seance = [d["n"] for d in (data or {}).get("donnes", []) if not d.get("a_completer")]
        _, expert_ = lire_analyses(c) if c else (None, None)
        expert_ = bool(expert_ and expert_.get("donnes"))
        vous = bool(data and moi.paires(data))
        niveau = niveau_rapport()
        pages = set(pages_rapport())
        F.choix_r["nums"] = [n for n in F.choix_r["nums"] if n in nums_seance]
        if not vous and F.choix_r["quelles"] == "revoir": F.choix_r["quelles"] = "toutes"
        SANS_VOUS = "choisissez « Vous êtes »"

        def titre(t):
            ui.label(t).classes("text-base font-bold mt-3")

        def case(texte, valeur, quand, raison=""):
            """Une case ; grisée et décochée avec sa raison quand elle ne s'applique pas."""
            with ui.row().classes("items-center gap-2 no-wrap"):
                cb = ui.checkbox(texte, value=bool(valeur) and not raison, on_change=lambda e: quand(e.value)) \
                    .props("dense").classes("text-base")
                if raison:
                    cb.disable(); ui.label(f"({raison})").classes("text-base text-gray-500")

        def quelles_(q, v):
            F.choix_r["quelles"] = q if v else "toutes"; F.options_rapports.refresh()

        def niveau_(n):
            ecrire_etat(rapport_niveau=n); F.options_rapports.refresh()

        def page_(k, v):
            p_ = [x for x, _, _ in PAGES_EN_PLUS if (x in pages and x != k) or (x == k and v)]
            ecrire_etat(rapport_pages=p_); F.options_rapports.refresh()

        titre("Les donnes")
        case("Seulement les donnes à revoir", F.choix_r["quelles"] == "revoir", lambda v: quelles_("revoir", v),
             "" if vous else SANS_VOUS)
        case("Choisir les donnes", F.choix_r["quelles"] == "choisir", lambda v: quelles_("choisir", v))
        if F.choix_r["quelles"] == "choisir":
            def basculer(n):
                ns = F.choix_r["nums"]
                if n in ns: ns.remove(n)
                else: ns.append(n)
                F.options_rapports.refresh()
            with ui.row().classes("gap-1 ml-7 flex-wrap max-w-lg"):
                for n in nums_seance:
                    ui.button(str(n), on_click=lambda n=n: basculer(n)) \
                        .props(f"{'unelevated' if n in F.choix_r['nums'] else 'outline'} dense no-caps") \
                        .classes("text-base min-w-[2.6rem]")
        case("Dans l'ordre où vous les avez jouées", moi.ordre_joue(), lambda v: ecrire_etat(ordre_joue=v),
             "" if vous else SANS_VOUS)

        titre("L'analyse")                      # une case : l'analyse est là par défaut, celle de l'expert quand
        case("Version courte (sans commentaires)", niveau == "faits",   # il y en a une (l'utilisateur, 2026-11-13)
             lambda v: niveau_("faits" if v else "expert"))

        titre("Pages en plus")
        for k, nom_, _ in PAGES_EN_PLUS:
            raison = (SANS_VOUS if k in ("champ", "parcours") and not vous else
                      "avec l'analyse seulement" if k == "synthese" and niveau == "faits" else
                      "pas encore d'analyse de l'expert" if k == "comparaison" and not expert_ else
                      "avec l'analyse seulement" if k == "comparaison" and niveau == "faits" else
                      "toutes les donnes seulement" if k in ("synthese", "comparaison") and F.choix_r["quelles"] != "toutes"
                      else "")
            case(nom_, k in pages,
                 lambda v, k=k: page_(k, v), raison)
    F.options_rapports = options_rapports

    with ui.column().classes("w-full gap-2") as F.pages_ui["creer"]:   # les options, puis « Créer les rapports »
        titre_page("Créer les rapports", "rapport")
        ui.label("Vous êtes").classes("text-base font-bold")
        F.actuel = moi.nom()

        def choisir_moi(e):
            if e.value == SEPARATEUR: e.sender.value = moi.nom() or ""; return   # la ligne de séparation
            ecrire_etat(moi=e.value or moi.AUCUN); retenir_licence(e.value); F.vue_seance.refresh(); F.options_rapports.refresh()
        F.choisir_moi = choisir_moi
        F.choix_moi = ui.select(F.options_joueurs(F.actuel), value=F.actuel or "", with_input=True, on_change=F.choisir_moi) \
            .classes("w-full").props("outlined dense") \
            .props(":option-disable=\"o => typeof o.label === 'string' && o.label.startsWith('───')\"")   # la ligne ne se choisit pas
        F.options_rapports()
        F.creer_r = ui.button("Créer les rapports", icon="picture_as_pdf", on_click=lambda: F.maj_rapports()).classes("text-base px-6 mt-2")
        F.besoin_r = ui.label("").classes("text-base text-gray-700")
        F.barre_r = ui.linear_progress(value=0, show_value=False).props("size=16px rounded")
        F.texte_r = ui.label("").classes("text-base")
        F.stop_r = ui.button("Annuler", on_click=annuler).props("outline")
        F.faute_r = ui.label("").classes("text-base text-red-800")

    @ui.refreshable
    def resultats():
        c = F.choix["chemin"]
        if not c: F.sans_seance(); return
        prets = rapports_de(c)
        ui.label(f"Rapports de la séance du {infos_seance(c)[0]}").classes("font-bold titre-page")
        if not prets:
            F.page_vide("picture_as_pdf", "Pas encore de rapport",
                      "Les rapports PDF de la séance : chaque donne analysée, à lire, imprimer ou envoyer.",
                      [("Créer les rapports", "add", lambda: F.voir_page("Rapports", "creer"))]); return
        # une liste comme celle d'Ouvrir une séance (l'Explorateur, vue Détails) : un clic ouvre le PDF (2026-11-17)
        colonnes = "20px minmax(0, 1fr) minmax(0, 1.2fr) 150px"
        with ui.column().classes("w-full gap-0").style("max-width:980px"):
            with ui.element("div").classes("tableau-seances entete-seances").style(f"grid-template-columns:{colonnes}"):
                for t_ in ("", "Rapport", "Contenu", "Créé le"): ui.label(t_)
            for quoi, nom, detail in RAPPORTS:
                for f, pour in prets.get(quoi, []):    # l'analyse : une par paire (ses initiales)
                    titre_r = (f"{nom if ',' in pour else nom.replace('donnes', 'donne').replace('Donnes', 'Donne')} {pour}"
                               if quoi.endswith("donnes") else f"{nom} pour {pour}" if pour else nom)
                    with ui.element("div").classes("tableau-seances ligne-seance").style(f"grid-template-columns:{colonnes}") \
                            .on("click", lambda f=f: ouvrir(f)):
                        ui.icon("picture_as_pdf", size="18px").classes("icone-seance")
                        ui.label(titre_r).classes("titre-seance truncate")
                        ui.label(detail).classes("truncate text-gray-700")
                        ui.label(quand(f))
        if prets:
            ui.button("Ouvrir le dossier des rapports", on_click=lambda p=prets[next(iter(prets))][0][0]: ouvrir(os.path.dirname(p))) \
                .props("flat no-caps").classes("mt-2 px-0")
    F.resultats = resultats

    with ui.column().classes("w-full gap-2") as F.pages_ui["seance"]:
        F.resultats()


NOMS = ()
