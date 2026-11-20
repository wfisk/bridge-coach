# -*- coding: utf-8 -*-
"""L'onglet Système : le système des robots, en lecture seule.
Les noms de la page (état, fonctions de tous les modules de l'interface) sont dans F (interface.commun) :
fenetre.construire les y range à chaque ouverture de la page."""
from interface.commun import *  # noqa: F401,F403 — les outils communs et F


def panneau():
    """Le contenu de l'onglet Système."""
    with ui.column().classes("w-full gap-3") as F.pages_ui["sy"]:
        @ui.refreshable
        def page_systeme():
            cle = F.vue_page["Système"]
            if not cle.startswith("sy-"): return
            titre_ = dict(SYSTEME_PAGES).get(cle, "")
            with ui.row().classes("w-full items-center justify-between gap-3"):
                ui.html(systeme_vue.rouge(html_.escape(titre_)), sanitize=False).classes("font-bold titre-page")
                ui.input(placeholder="Chercher : 1SA 2♣, Stayman, contre…", value=F.sy_cherche["t"],
                         on_change=lambda e: (F.sy_cherche.update(t=e.value or ""), F.resultats_sy.refresh())) \
                    .props("outlined dense clearable debounce=400").classes("w-80")
            F.resultats_sy()
            if cle == "sy-vue":
                n_seq, n_enc, n_ex = systeme_vue.compter(SYSTEME_DATA)
                ui.html(f"<div class='syst'><p>Les robots de Bridge Coach jouent le <b>SEF 2024</b>, tel qu'il est écrit "
                        f"dans son fichier de règles : <b>{n_seq}</b> séquences, <b>{n_enc}</b> enchères décrites, "
                        f"<b>{n_ex}</b> mains d'exemple vérifiées à chaque lancement. Les pages à gauche les montrent "
                        "famille par famille, en lecture seule. Ce qui n'y est pas décrit, les robots le jouent avec "
                        "leurs règles générales.</p><p>Votre fiche de conventions dit ce que <b>vous</b> jouez avec "
                        "votre partenaire ; elle ne change pas les robots. « Écarts fiche / robots » liste où les deux "
                        "diffèrent.</p></div>", sanitize=False)
                ui.markdown(systeme_vue.lire_doc("systeme.md")).classes("syst aide")
            elif cle == "sy-entames":
                ui.markdown(systeme_vue.lire_doc("entames.md")).classes("syst aide")
            elif cle.startswith("sy-conv-"):
                doc = next((d for k_, _, d in systeme_vue.CONVENTIONS if "sy-conv-" + k_ == cle), "")
                ui.markdown(systeme_vue.lire_doc(doc)).classes("syst aide")
                ui.html(systeme_vue.regles_convention(cle[len("sy-conv-"):], SYSTEME_DATA), sanitize=False)
            else:
                ui.html(systeme_vue.page_famille(cle[3:], SYSTEME_DATA), sanitize=False)
        F.page_systeme = page_systeme
        @ui.refreshable
        def resultats_sy():
            t_ = F.sy_cherche["t"].strip()
            if len(t_) < 2: return
            r_ = systeme_vue.chercher(t_, SYSTEME_DATA)
            if not r_: ui.label("Rien de tel dans le système.").classes("text-base text-gray-700"); return
            with ui.row().classes("w-full gap-2 flex-wrap"):
                for cle_, fam_ in r_[:30]:
                    alts_ = systeme_vue.alternatives(cle_)
                    lib_ = ("Ouverture" if cle_ == "ouverture" else systeme_vue.sequence_texte(systeme_vue.jetons(alts_[0]))
                            + (f" (et {len(alts_) - 1} autre{'s' if len(alts_) > 2 else ''})" if len(alts_) > 1 else ""))
                    with ui.button(on_click=lambda c_=cle_, f_=fam_: F.aller_sequence(c_, f_)).props("outline no-caps dense color=grey-9"):
                        ui.html(systeme_vue.rouge(html_.escape(lib_)), sanitize=False)
            if len(r_) > 30: ui.label(f"… et {len(r_) - 30} autres : précisez.").classes("text-base text-gray-700")
        F.resultats_sy = resultats_sy
        F.page_systeme()
    with ui.column().classes("w-full gap-3") as F.systeme_col:   # votre fiche (déplacée ici à la fin) et les écarts
        pass
    with ui.column().classes("w-full gap-3") as F.pages_ui["ecarts"]:
        ui.label("Écarts fiche / robots").classes("text-lg font-bold")
        @ui.refreshable
        def page_ecarts():
            ec = F.ecarts_fiche()
            ui.label("Les robots jouent toujours le système de Bridge Coach. Votre fiche dit ce que vous jouez avec "
                     "votre partenaire : voici où elle s'en écarte.").classes("text-base text-gray-700 max-w-3xl")
            if not ec:
                ui.label("Aucun écart : votre fiche est celle de Bridge Coach.").classes("text-base font-bold"); return
            ui.html("<table class='syst' style='border-collapse:collapse'><tr style='text-align:left'><th style='padding:6px 12px 6px 0'>"
                    "Point</th><th style='padding:6px 12px'>Votre fiche</th><th style='padding:6px 12px'>Les robots</th></tr>"
                    + "".join(f"<tr style='border-top:1px solid var(--bc-tapis-200)'><td style='padding:6px 12px 6px 0'>"
                              f"<span class='note'>{html_.escape(sec_)}</span><br><b>{html_.escape(tit_)}</b></td>"
                              f"<td style='padding:6px 12px'>{html_.escape(v_)}</td><td style='padding:6px 12px;"
                              f"color:var(--bc-tapis-700)'>{html_.escape(d_)}</td></tr>" for sec_, tit_, v_, d_ in ec)
                    + "</table>", sanitize=False)
        F.page_ecarts = page_ecarts
        F.page_ecarts()


NOMS = ()
