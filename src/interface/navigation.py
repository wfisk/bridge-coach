# -*- coding: utf-8 -*-
"""Les pages des onglets, la barre de gauche, l'aide contextuelle, les étapes de l'analyse expert.
Les noms de la page (état, fonctions de tous les modules de l'interface) sont dans F (interface.commun) :
fenetre.construire les y range à chaque ouverture de la page."""
from interface.commun import *  # noqa: F401,F403 — les outils communs et F


def aller_sequence(cle, famille=None):
    """Système : ouvre la famille de cette séquence et la fait défiler à l'écran, encadrée."""
    famille = famille or systeme_vue.famille_de_cle(cle, SYSTEME_DATA)
    if not famille: return
    F.sy_cherche["t"] = ""
    F.voir_page("Système", "sy-" + famille)
    a_ = systeme_vue.ancre(cle)
    ui.run_javascript(f"setTimeout(function(){{document.querySelectorAll('.sequence.vise').forEach(function(x){{x.classList.remove('vise')}});"
                      f"var e=document.getElementById({json.dumps(a_)}); if(e){{e.classList.add('vise'); e.scrollIntoView({{behavior:'smooth',block:'start'}});}}}}, 150)")


def ecarts_fiche():
    """[(section, point, votre fiche, les robots)] : les lignes de votre fiche qui diffèrent de Bridge Coach."""
    x = fiche_conventions.lire(); out = []
    for sec, titre_sec, _, items in fiche_conventions.TOUTES:
        for it in items:
            if fiche_conventions.valeur(it["cle"], x)[1]:
                out.append((titre_sec, it["titre"], fiche_conventions.texte(it["cle"], x) or "—",
                            fiche_conventions.texte(it["cle"], defaut=True) or "—"))
    return out


def retenir_page():
    """La page ouverte (onglet, entrée de la barre, version de l'analyse, page de l'aide) : rouverte au prochain lancement.
    Une autre page s'ouvre en haut (l'utilisateur, 2026-11-17 : Jouer s'ouvrait défilé, le haut de la table caché)."""
    o = F.onglets.value; nom = o if isinstance(o, str) else o.props.get("name", "Donnes")
    cle_ = (nom, F.vue.get("entree"), F.vue_aide["k"], F.vue_page["Fichier"], F.vue_page["Rapports"], F.vue_page["Réglages"], F.vue_page["Système"])
    if F.vue_haut["cle"] is not None and cle_ != F.vue_haut["cle"]:
        ui.run_javascript("window.scrollTo(0, 0)")
    F.vue_haut["cle"] = cle_
    ecrire_etat(page={"onglet": nom, "entree": F.vue.get("entree"), "version": F.vue.get("version"), "aide": F.vue_aide["k"],
                      "fichier": F.vue_page["Fichier"], "rapports": F.vue_page["Rapports"], "reglages": F.vue_page["Réglages"], "systeme": F.vue_page["Système"],
                      "nouveau": F.facon["k"], "replis": F.replis})


def onglet_a_pages():
    """« Fichier », « Rapports » ou « Réglages » quand l'un d'eux est ouvert, sinon None."""
    for nom, o in (("Fichier", F.o_fichier), ("Système", F.o_systeme), ("Rapports", F.o_rapports), ("Réglages", F.o_reglages)):
        if F.onglets.value in (o, nom): return nom
    return None


def montrer_pages():
    """Chaque onglet à pages montre la page choisie dans sa barre."""
    try: F.pages_ui
    except (NameError, AttributeError): return                           # la page se construit encore
    for nom, cles in F.PAGES.items():
        for cle, _ in cles:
            if cle in F.pages_ui: F.pages_ui[cle].set_visibility(F.vue_page[nom] == cle)   # (celles déjà construites)
    if "sy" in F.pages_ui:                               # Système : les pages des robots, dessinées à la demande
        F.pages_ui["sy"].set_visibility(F.vue_page["Système"].startswith("sy-")); F.page_systeme.refresh()


def voir_page(nom, cle):
    F.vue_page[nom] = cle; F.montrer_pages(); F.barre_seance.refresh(); F.retenir_page()
    if cle == "seance": F.resultats.refresh()
    if nom == "Fichier": F.rafraichir_fichier()
    if cle == "contact": F.fichier_erreur.refresh()
    if cle == "ecarts": F.page_ecarts.refresh()          # la fiche a pu changer depuis


def rafraichir_fichier():
    """Les pages de Fichier se mettent à jour quand on y vient : les séances, les .bws, la séance à exporter."""
    try: F.liste.refresh(); F.liste_i.refresh(); F.a_exporter.refresh(); F.page_infos.refresh()
    except (NameError, AttributeError): pass                             # la page se construit encore


def voir_aide(k):
    F.vue_aide["k"] = k; F.page_aide.refresh(); F.barre_seance.refresh(); F.retenir_page()
    ui.run_javascript("window.scrollTo(0, 0)")


def cle_aide():
    """Où l'on est, pour AIDE_POUR : (onglet, page ou entrée, précision)."""
    o = F.onglets.value; nom = o if isinstance(o, str) else o.props.get("name", "")
    if nom in ("Fichier", "Système", "Rapports", "Réglages"):
        pg = F.vue_page[nom]
        if (nom, pg) == ("Fichier", "infos") and brouillon.est_brouillon(F.choix["chemin"]): return (nom, pg, "brouillon")
        return (nom, pg, F.facon["k"]) if (nom, pg) == ("Fichier", "nouveau") else (nom, pg)
    e = F.vue.get("entree") or ""
    if nom == "Jouer":
        if e in ("options", "classement"): return (nom, e)
        m = F.jeu.get("mode") or "jouer"
        if m in ("revoir", "demo"): return (nom, m)
        p_ = F.jeu.get("partie")
        if p_: return (nom, "defense" if p_.en_defense() else "carte")
        return (nom, "encheres")
    if nom == "Analyse": return (nom, e if e in ("standard", "expert") else "donne")
    if nom == "Donnes":
        if e in ("seance", "joueurs"): return (nom, e)
        c = F.choix["chemin"]
        return (nom, "saisie") if c and e.startswith("d") and edition.modifiable(c)[0] else (nom, "donne")
    return (nom,)


def ouvrir_aide(ancre=None):
    """L'aide, ouverte à la section voulue (sinon celle de la page où l'on est) : sa page, puis on y descend."""
    if not ancre and F.onglets.value in (F.o_aide, "Aide"): return   # déjà dans l'aide : on y reste
    ancre = ancre or section_aide(*F.cle_aide())
    k = next((i for i, (_, _, secs) in enumerate(sections_aide()) if ancre in [a for a, _ in secs]), F.vue_aide["k"])
    F.vue_aide["k"] = k
    if F.onglets.value not in (F.o_aide, "Aide"): F.onglets.set_value(F.o_aide)
    F.page_aide.refresh(); F.barre_seance.refresh(); F.retenir_page()
    ui.run_javascript(f"setTimeout(function () {{ window.allerAide && window.allerAide({json.dumps(ancre)}, true); }}, 120)")


@ui.refreshable
def page_aide():
    """Une page de l'aide, et à droite « Sur cette page » : ses sections, sur le même fond que le texte ; un clic
    y descend, la section lue est marquée en lisant (JS_SUR_PAGE)."""
    s_ = sections_aide(); cats = categories_aide()
    k_ = min(F.vue_aide["k"], len(s_) - 1)
    titre, h, sections = s_[k_]
    if k_ < len(cats) and cats[k_]: ui.label(cats[k_]).classes("text-sm text-gray-600 uppercase tracking-wide")
    with ui.row().classes("w-full no-wrap items-start gap-10"):
        ui.html(h, sanitize=False).classes("aide pb-24").style("flex:1 1 auto;min-width:0;max-width:46em")
        if sections:
            with ui.element("div").classes("sur-page-place shrink-0"), ui.column().classes("sur-page gap-0"):   # reste à l'écran
                ui.label("Sur cette page").classes("text-sm font-bold text-gray-700 mb-2")
                for ancre_, t_ in sections:
                    ui.html(f'<a href="#{ancre_}" data-ancre="{ancre_}" onclick="return allerAide(\'{ancre_}\')">{html_.escape(t_)}</a>',
                            sanitize=False)
    ui.run_javascript("window.suivreAide && window.suivreAide()")


def entrees_de(data):
    """Les entrées de la barre latérale : la séance, puis (onglet Donnes) les joueurs et les alertes, puis chaque donne."""
    if F.sur_jouer():                                   # Jouer : les donnes seules, et celles déjà enchéries
        faits = jouer.lire_essais(base_seance(F.choix["chemin"]))["donnes"]
        donnes = data["donnes"]                   # par numéro, toujours (l'ordre joué : Options et « Donne suivante »)
        return [("options", "Options"), ("classement", "Classement")] + [(f"d{d['n']}", f"Donne {d['n']}" + (" · jouée" if classement.dernier_fini(faits.get(str(d["n"])))
                                                                                   else " · enchérie" if faits.get(str(d["n"])) else ""))
                                            for d in donnes if not d.get("a_completer")]
    haut = [("standard", "Analyse du coach"), ("expert", "Analyse expert")] if F.sur_analyse() else \
        [("seance", "Séance"), ("joueurs", "Joueurs")]   # toujours deux entrées : Donne 1 à la même hauteur partout
    return haut + [(f"d{d['n']}", f"Donne {d['n']}") for d in data["donnes"]]


def etapes_expert(c):
    """Les étapes pour obtenir l'analyse de l'expert de Claude, sur le web (claude.ai)."""
    nom = nom_pour_claude(lire_seance(c))
    ui.label("Obtenir l'analyse de l'expert avec Claude").classes("text-base font-bold mt-4")
    ui.label("L'analyse de l'expert est écrite par Claude (claude.ai, dans votre navigateur). Comptez une "
             "conversation par séance ; pour 24 donnes, Claude peut répondre en plusieurs fois.").classes("text-base text-gray-700")
    etape = lambda k, texte: ui.html(f"<div style='font-size:16px'><b>{k}.</b> {texte}</div>", sanitize=False)
    with ui.column().classes("gap-3 max-w-2xl"):
        etape(1, "Préparez le fichier : Bridge Coach met dans un seul fichier tout ce dont Claude a besoin (la séance, "
                 "l'analyse du coach, le système, un exemple et la consigne), puis ouvre son dossier. Les joueurs n'y "
                 "sont que par leurs initiales : les noms complets ne quittent pas l'ordinateur.")
        ui.button("Préparer le fichier pour Claude", icon="folder_open", on_click=lambda: F.preparer_expert(c)).props("outline")
        etape(2, f"Ouvrez <b>{html_.escape(nom_outil(url_expert()))}</b> dans votre navigateur et commencez une nouvelle conversation.")
        ui.button("Ouvrir l'expert", icon="open_in_new", on_click=lambda: ouvrir(url_expert())).props("outline")
        etape(3, f"Glissez le fichier <code>{nom}.ai.json</code> dans la conversation.")
        etape(4, "Copiez la consigne, collez-la dans la conversation, puis envoyez.")
        ui.button("Copier la consigne", icon="content_copy", on_click=lambda: F.copier_consigne(c)).props("outline")
        etape(5, f"Claude écrit le fichier <code>{nom}-expert.json</code> : téléchargez-le avec le bouton sous sa réponse. "
                 "S'il répond en plusieurs fois, téléchargez chaque fichier.")
        etape(6, "Importez le fichier téléchargé (un par un s'il y en a plusieurs). Les donnes s'ajoutent à l'analyse "
                 "de l'expert, rangée dans la séance ; la version d'avant est gardée dans versions/.")
        ui.button("Importer l'analyse de l'expert…", icon="file_download", on_click=lambda: F.choisir_expert()).props("outline")
        etape(7, "Lisez-la ici, donne par donne. Pour les rapports PDF : l'onglet Rapports, « Créer les rapports ».")
        ui.button("Aller aux rapports", icon="picture_as_pdf", on_click=lambda: F.onglets.set_value(F.o_rapports)).props("outline")
        if F.expert_msg["texte"]:
            ui.label(F.expert_msg["texte"]).classes("text-base " + ("text-red-800" if F.expert_msg["faute"] else "text-primary") + " break-all")


def maj_rapports():
    if T.actif or D.actif or I.actif or not F.choix["chemin"]: return
    F.vu["fini"] = None; F.faute.text = ""; F.faute_r.text = ""; F.fait_a.text = ""
    if F.choix_r["quelles"] == "choisir" and not F.choix_r["nums"]:
        F.faute_r.text = "Choisissez au moins une donne, ou « Toutes les donnes »."; return
    lancer_rapports(F.choix["chemin"], F.choix_r["quelles"], sorted(F.choix_r["nums"]))
    F.resultats.refresh(); F.montrer_controles()


def preparer_expert(c):
    try:
        dossier, _ = preparer_pour_claude(c)
        F.expert_msg.update(texte=f"Fichier prêt dans {dossier}", faute=False); ouvrir(dossier)
    except Exception:
        F.expert_msg.update(texte="Le fichier n'a pas pu être préparé.", faute=True)
    F.vue_analyse.refresh()


def copier_consigne(c):
    date = (lire_seance(c) or {}).get("session", {}).get("date", "")
    ui.clipboard.write(CONSIGNE.format(nom=nom_pour_claude(lire_seance(c)), date=date, marque=moi.MARQUES[moi.marque(lire_seance(c) or {})]))
    ui.notify("Consigne copiée : collez-la dans la conversation avec Claude.")


def importer_expert_de(chemin):
    try:
        F.expert_msg.update(texte=importer_expert(F.choix["chemin"], chemin), faute=False); F.options_rapports.refresh()
    except ValueError as ex:
        F.expert_msg.update(texte=str(ex), faute=True)
    F.vue_analyse.refresh(); F.barre_seance.refresh(); F.resultats.refresh()


async def choisir_expert():
    if not app.native.main_window: return F.envoi_x.run_method("pickFiles")
    try:
        r = await app.native.main_window.create_file_dialog(allow_multiple=False, file_types=TYPES_EXPERT)
    except Exception as ex:                            # jamais un clic sans effet : le message s'affiche
        F.expert_msg.update(texte=f"La fenêtre de choix de fichier ne s'est pas ouverte ({ex}).", faute=True); F.vue_analyse.refresh(); return
    if r: F.importer_expert_de(r[0])


async def recu_x(e):
    cible = os.path.join(tempfile.mkdtemp(prefix="expert-"), os.path.basename(e.file.name))
    await e.file.save(cible)
    F.importer_expert_de(cible)


def entree_effective(data):
    """L'entrée montrée : celle choisie si elle existe dans cet onglet, sinon la première."""
    es = F.entrees_de(data)
    if F.vue["entree"] in dict(es): return F.vue["entree"]
    if F.sur_jouer():                                   # Jouer : la première donne, pas les options ni le classement
        return next((k for k, _ in es if k.startswith("d")), es[0][0])
    return es[0][0]


def montrer_controles():
    """« Lancer l'analyse » : sur la page Analyse standard, ou partout pendant qu'une analyse tourne."""
    try: F.controles
    except (NameError, AttributeError): return                           # la page se construit encore : l'onglet change avant la barre
    data = lire_seance(F.choix["chemin"])
    F.controles.set_visibility(bool(data) and ((T.actif and T.genre == "analyse") or (F.sur_analyse() and F.entree_effective(data) == "standard")))


def aller(k):
    F.vue["entree"] = k; F.vue["edition"] = None; F.montrer_barre(); F.barre_seance.refresh(); F.vue_seance.refresh(); F.vue_analyse.refresh(); F.vue_jouer.refresh(); F.montrer_controles()
    F.retenir_page()


@ui.refreshable
def barre_seance():
    if F.onglet_a_pages():                              # Rapports, Réglages : une entrée par page
        nom = F.onglet_a_pages()
        for k_, (cle, titre) in enumerate(F.PAGES[nom]):
            groupe = F.GROUPES_PAGES.get(nom, {}).get(cle)
            if groupe:                                  # l'intertitre d'un groupe de pages, petit et discret
                ui.label(groupe).classes("text-xs text-gray-600 uppercase font-bold px-2 " + ("mt-1" if k_ == 0 else "mt-4")) \
                    .style("letter-spacing:.06em")
            with ui.button(on_click=lambda c=cle: F.voir_page(nom, c)).props("flat no-caps align=left dense color=grey-10") \
                    .classes("entree-barre text-left" + (" choisie" if F.vue_page[nom] == cle else "")):
                ui.html(systeme_vue.rouge(html_.escape(titre)), sanitize=False)   # « Après 1♥ / 1♠ » : ♥ ♦ en rouge
        return
    if F.sur_aide():                                    # l'aide : une entrée par page (peu de pages, plus longues)
        cats, avant = categories_aide(), None
        for k, (titre, _, _) in enumerate(sections_aide()):
            cat = cats[k] if k < len(cats) else ""
            if cat and cat != avant:                     # l'intertitre de la catégorie, comme dans Réglages
                ui.label(cat).classes("text-xs text-gray-600 uppercase font-bold px-2 " + ("mt-1" if avant is None else "mt-4")) \
                    .style("letter-spacing:.06em")
            avant = cat
            ui.button(titre, on_click=lambda k=k: F.voir_aide(k)).props("flat no-caps align=left dense color=grey-10") \
                .classes("entree-barre aide-sujet text-left" + (" choisie" if k == F.vue_aide["k"] else ""))
        return
    data = lire_seance(F.choix["chemin"])
    if not data: return
    a_finir = {f"d{d['n']}" for d in data["donnes"] if d.get("a_completer")}
    es = F.entrees_de(data); haut = [x for x in es if not x[0].startswith("d")]
    for k, (cle, nom) in enumerate(es):
        if cle in a_finir: nom += " · à compléter"
        choisie = cle == F.entree_effective(data)            # comme la barre de Claude : un fond un peu plus soutenu
        if F.vue.get("reorg") and cle.startswith("d") and F.sur_donnes():   # Réorganiser : ↑ ↓ au bout de chaque donne
            n_ = int(cle[1:]); dernier = max(x["n"] for x in data["donnes"])
            with ui.row().classes("w-full items-center no-wrap gap-0"):
                ui.button(nom, on_click=lambda k=cle: F.aller(k)).props("flat no-caps align=left dense color=grey-10") \
                    .classes("entree-barre grow min-w-0" + (" choisie" if choisie else ""))
                ui.button(icon="arrow_upward", on_click=lambda n_=n_: F.deplacer_(n_, n_ - 1)).props("flat round dense color=grey-8") \
                    .set_enabled(n_ > 1)
                ui.button(icon="arrow_downward", on_click=lambda n_=n_: F.deplacer_(n_, n_ + 1)).props("flat round dense color=grey-8") \
                    .set_enabled(n_ < dernier)
            continue
        ui.button(nom, on_click=lambda k=cle: F.aller(k)).props("flat no-caps align=left dense color=grey-10") \
            .classes("entree-barre" + (" choisie" if choisie else ""))
        if k == len(haut) - 1:                            # deux places en haut, puis un trait : Donne 1 ne bouge pas
            for _ in range(2 - len(haut)): ui.element("div").classes("entree-barre")
            ui.separator().classes("my-2")
    if not F.sur_analyse() and not F.sur_jouer() and edition.modifiable(F.choix["chemin"])[0]:
        ui.button("Ajouter une donne", icon="add", on_click=lambda: F.ajouter()).props("flat no-caps align=left dense no-wrap") \
            .classes("entree-barre mt-2 text-primary")
        if len(data["donnes"]) > 1:
            ui.button("Terminer" if F.vue.get("reorg") else "Réorganiser les donnes", icon="check" if F.vue.get("reorg") else "swap_vert",
                      on_click=lambda: (F.vue.update(reorg=not F.vue.get("reorg")), F.barre_seance.refresh())) \
                .props("flat no-caps align=left dense no-wrap").classes("entree-barre text-primary")


def deplacer_(n, vers):
    """Donnes, Réorganiser : la donne n va à la place vers ; la donne montrée la suit."""
    c = F.choix["chemin"]
    if T.actif or D.actif or I.actif: ui.notify("Un calcul est en cours : attendez qu'il se termine."); return
    ch = edition.deplacer(c, n, vers)
    if F.vue.get("entree") == f"d{n}": F.vue["entree"] = f"d{vers}"
    if ch: ui.notify(f"Donneur et vulnérabilité selon le numéro : donne{'s' if len(ch) > 1 else ''} {', '.join(map(str, ch))} "
                     "changée(s) ; l'analyse de l'expert y est « à revoir ».", multi_line=True)
    F.barre_seance.refresh(); F.vue_seance.refresh(); F.vue_analyse.refresh(); F.badge_brouillon.refresh()


def basculer_liste(cachee=None):
    """La barre de gauche, cachée ou montrée, sur toutes les pages, par le bouton tout à gauche de la barre de menus
    (gardé dans etat.json, d'une fois sur l'autre ; l'utilisateur, 2026-11-11, puis 2026-11-13 : le bouton ne bouge
    plus et ne prend plus de ligne dans la barre)."""
    if cachee is None: cachee = not lire_etat().get("liste_cachee")
    ecrire_etat(liste_cachee=cachee); F.montrer_barre(); F.vue_jouer.refresh()


def montrer_barre():
    """La barre latérale : sur les onglets Donnes, Jouer et Analyse quand une séance est ouverte ; toujours sur
    Rapports, Réglages et l'aide."""
    cachee = bool(lire_etat().get("liste_cachee"))
    F.icone_barre.set_content(icone_panneau(cachee))   # le bouton de la barre de menus suit l'état
    F.bouton_barre._props["title"] = "Montrer la barre de gauche" if cachee else "Cacher la barre de gauche"
    F.bouton_barre.update()
    if F.plein["on"] and F.sur_jouer(): F.tiroir.set_value(False); return   # Jouer, table seule
    if cachee: F.tiroir.set_value(False); return          # cachée par vous (le bouton tout à gauche de la barre de menus)
    F.tiroir.set_value(F.sur_aide() or bool(F.onglet_a_pages()) or (F.onglets.value in (F.o_donnes, "Donnes", F.o_jouer, "Jouer", F.o_analyse, "Analyse")
                                    and lire_seance(F.choix["chemin"]) is not None))   # l'aide a toujours sa barre


NOMS = ("aller_sequence", "ecarts_fiche", "retenir_page", "onglet_a_pages", "montrer_pages", "voir_page", "rafraichir_fichier", "voir_aide", "cle_aide", "ouvrir_aide", "page_aide", "entrees_de", "etapes_expert", "maj_rapports", "preparer_expert", "copier_consigne", "importer_expert_de", "choisir_expert", "recu_x", "entree_effective", "montrer_controles", "aller", "barre_seance", "deplacer_", "basculer_liste", "montrer_barre",)   # rangés dans F par fenetre.construire
