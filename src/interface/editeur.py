# -*- coding: utf-8 -*-
"""L'éditeur de donnes (séances d'entraînement et tapées) et les versions d'un fichier.
Les noms de la page (état, fonctions de tous les modules de l'interface) sont dans F (interface.commun) :
fenetre.construire les y range à chaque ouverture de la page."""
from interface.commun import *  # noqa: F401,F403 — les outils communs et F


def page_versions(c):
    """Les versions gardées d'une séance modifiable, pour revenir en arrière."""
    vs = edition.versions(c)
    ui.label("Versions précédentes").classes("text-base font-bold mt-4")
    ui.label("Chaque modification est enregistrée aussitôt. Une copie de la séance est gardée avant les changements, "
             "au plus toutes les 10 minutes (les 20 dernières).").classes("text-base text-gray-700")
    if not vs: ui.label("Aucune pour l'instant.").classes("text-base text-gray-700")
    for v in vs[:20]:
        try: nb = len(edition.lire(v)["donnes"])
        except Exception: nb = 0
        with ui.row().classes("items-center gap-4"):
            ui.label(f"{quand(v)} · {nb} donne{'s' if nb > 1 else ''}").classes("text-base")
            ui.button("Restaurer", on_click=lambda v=v: F.restaurer(c, v)).props("flat dense no-caps")


def restaurer(c, v):
    edition.restaurer(c, v); ui.notify("Version restaurée ; la version d'avant est gardée elle aussi.")
    F.vue_seance.refresh(); F.barre_seance.refresh(); F.vue_analyse.refresh()


def editeur_donne(c, d):
    """La donne d'une séance modifiable : les quatre mains en champs (une couleur par champ), enregistrées à chaque
    changement ; donneur, vulnérabilité, compléter au hasard, supprimer."""
    n = d["n"]
    with ui.row().classes("w-full items-center justify-between no-wrap"):
        ui.label(f"Donne {n}").classes("text-lg font-bold")
        ui.button("Terminer", icon="check", on_click=lambda: F.terminer()).props("outline")
    with ui.row().classes("items-center gap-4"):
        ui.select({s: SIEGE[s] for s in "NESO"}, value=d["donneur"], label="Donneur",
                  on_change=lambda e: (edition.regler(c, n, donneur=e.value), maj(), resultat.refresh())).classes("w-32")
        ui.select(["Personne", "N-S", "E-O", "Tous"], value=d["vul"], label="Vulnérabilité",
                  on_change=lambda e: (edition.regler(c, n, vul=e.value), maj(), resultat.refresh())).classes("w-36")
    ui.label("Tapez les cartes de chaque couleur (A R D V X 9 … 2, ou 10) ; une couleur vide est une chicane. "
             "Tout est enregistré dès que vous quittez un champ.").classes("text-base text-gray-700")
    tetes = {}

    def main_ed(s):
        with ui.column().classes("gap-1"):
            tetes[s] = ui.label("").classes("text-base font-bold text-gray-700")
            for k, coul in enumerate("♠♥♦♣"):
                v = d["mains"][s].split()[k]
                champ = ui.input(value="" if v == "-" else v).props(f'dense outlined prefix="{coul}"').classes("w-44")
                champ.on("blur", lambda e, s=s, k=k, champ=champ: poser(s, k, champ))
                champ.on("keydown.enter", lambda e, s=s, k=k, champ=champ: poser(s, k, champ))

    with ui.grid(columns="repeat(3, 190px)").classes("gap-3 items-start mt-2"):
        ui.label(""); main_ed("N"); ui.label("")
        main_ed("O"); centre = ui.label("").classes("text-base text-gray-700 whitespace-pre-line self-center"); main_ed("E")
        ui.label(""); main_ed("S"); ui.label("")
    msg = ui.label("").classes("text-base text-red-800")
    with ui.row().classes("gap-3 mt-1"):
        ui.button("Compléter au hasard", icon="casino", on_click=lambda: completer()).props("outline")
        ui.button("Supprimer la donne", icon="delete", on_click=lambda: F.demander_suppression(c, n)).props("outline color=red")

    @ui.refreshable
    def resultat():                                   # le par seulement : le double mort est dans l'onglet Analyse
        dd = edition.donne_de(edition.lire(c), n)
        if dd.get("par"): ui.html(f"<div style='font-size:var(--fs-texte)'>{par_html(dd)}</div>", sanitize=False)
    resultat()

    def maj():
        dd = edition.donne_de(edition.lire(c), n)
        nb, doubles, restantes = edition.etat(dd)
        for s in "NESO":
            k = len(edition.cartes(dd["mains"][s]))
            tetes[s].text = f"{SIEGE[s]} · {edition.points(dd['mains'][s])} H · {k} carte{'s' if k > 1 else ''}"
        centre.text = "Donne complète" if nb == 52 and not doubles else \
            f"{52 - nb} cartes à placer :\n" + "\n".join(f"{c_} {' '.join(r) or '—'}" for c_, r in restantes.items())
        msg.text = ("En double : " + ", ".join(f"{c_}{r}" for c_, r in doubles)) if doubles else msg.text

    def poser(s, k, champ):
        avant = edition.donne_de(edition.lire(c), n).get("a_completer", False)
        try:
            v = edition.poser_couleur(c, n, s, k, champ.value)
            champ.value = "" if v == "-" else v; msg.text = ""
        except ValueError as ex:
            msg.text = f"{SIEGE[s]}, {'♠♥♦♣'[k]} : {ex}"
        maj()
        if avant != edition.donne_de(edition.lire(c), n).get("a_completer", False):   # complète, ou plus complète
            resultat.refresh(); F.barre_seance.refresh()

    def completer():
        try:
            edition.completer_au_hasard(c, n)
        except ValueError as ex:
            msg.text = str(ex); return
        F.vue_seance.refresh(); F.barre_seance.refresh()
    maj()


def modifier(c, n):
    """« Modifier la donne » : si elle a une analyse de l'expert, on prévient d'abord qu'elle sera mise de côté."""
    if edition.a_analyse_expert(c, n):
        F.confirmation_m.n = n; F.confirmation_m.open()
    else:
        F.vue["edition"] = n; F.vue_seance.refresh()


def modifier_quand_meme():
    F.confirmation_m.close(); F.vue["edition"] = F.confirmation_m.n; F.vue_seance.refresh()


def terminer():
    F.vue["edition"] = None; F.vue_seance.refresh(); F.barre_seance.refresh(); F.vue_analyse.refresh()


def demander_suppression(c, n):
    F.confirmation.n = n; F.confirmation_texte.text = f"Supprimer la donne {n} ? Les donnes suivantes prendront le numéro d'avant."
    F.confirmation.open()


def supprimer():
    c, n = F.choix["chemin"], F.confirmation.n
    F.confirmation.close()
    edition.supprimer_donne(c, n)
    data = lire_seance(c)
    reste = [d["n"] for d in data["donnes"]] if data else []
    F.vue["entree"] = f"d{min(n, max(reste))}" if reste else "seance"
    F.vue_seance.refresh(); F.barre_seance.refresh(); F.vue_analyse.refresh()


def ajouter():
    n = edition.ajouter_donne(F.choix["chemin"])
    F.aller(f"d{n}"); F.vue["edition"] = n


def creer_vide():
    c = edition.nouvelle_seance()
    n = edition.ajouter_donne(c)
    F.choisir(c); F.onglets.set_value(F.o_donnes); F.aller(f"d{n}")


def sur_analyse():
    return F.onglets.value in (F.o_analyse, "Analyse")


def sur_jouer():
    return F.onglets.value in (F.o_jouer, "Jouer")


def sur_donnes():
    return F.onglets.value in (F.o_donnes, "Donnes")


def sur_aide():
    return F.onglets.value in (F.o_aide, "Aide")


NOMS = ("page_versions", "restaurer", "editeur_donne", "modifier", "modifier_quand_meme", "terminer", "demander_suppression", "supprimer", "ajouter", "creer_vide", "sur_analyse", "sur_jouer", "sur_donnes", "sur_aide",)   # rangés dans F par fenetre.construire
