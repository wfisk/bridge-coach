# -*- coding: utf-8 -*-
"""L'onglet Fichier : nouveau, ouvrir, importer, exporter, infos, corbeille ; la mise à jour.
Les noms de la page (état, fonctions de tous les modules de l'interface) sont dans F (interface.commun) :
fenetre.construire les y range à chaque ouverture de la page."""
from interface.commun import *  # noqa: F401,F403 — les outils communs et F


def montrer_titre():
    t_ = titre_fenetre(F.choix["chemin"])
    ui.page_title(t_)                                  # l'onglet du navigateur
    if app.native.main_window:                         # la barre de titre de la fenêtre
        try: app.native.main_window.set_title(t_)
        except Exception: pass


async def chercher_maj():
    if maj.est_depot_git():
        F.etat_maj.text = "Ce dossier est une copie Git du programme : mettez-le à jour avec git pull."; return
    F.etat_maj.text = "Recherche sur GitHub…"; F.bouton_maj.set_visibility(False)
    try:
        v = await run.io_bound(maj.derniere_version)
    except Exception:
        F.etat_maj.text = "GitHub ne répond pas : vérifiez la connexion à Internet, puis réessayez."; return
    if not v or maj.cle(v) <= maj.cle(maj.version_locale()):
        F.etat_maj.text = f"Bridge Coach est à jour (version {maj.version_locale()})."; return
    F.maj_vue["version"] = v
    refusee = lire_etat().get("maj_annulee") == v      # annulée une fois : proposée encore, mais on le rappelle
    F.etat_maj.text = ((f"Vous aviez annulé la version {v}. " if refusee else f"La version {v} est disponible. ") +
                     "Bridge Coach va se fermer, se mettre à jour en une minute environ, "
                     "puis se rouvrir. Vos séances, vos rapports et vos réglages ne changent pas.")
    F.bouton_maj.text = f"Mettre à jour vers {v}"; F.bouton_maj.set_visibility(True)


def lancer_maj():
    v = F.maj_vue["version"]
    if not v: return
    if any(x.actif for x in (T, D, I)):
        F.etat_maj.text = "Un calcul est en cours : attendez qu'il se termine, puis recommencez."; return
    opts = {"creationflags": 0x00000008 | 0x00000200} if sys.platform == "win32" else {"start_new_session": True}
    subprocess.Popen([sys.executable, "-I", "-X", "utf8", os.path.join(ICI, "maj.py"), "--appliquer", v,
                      "--attendre", str(os.getpid()), "--journal", rapport.RAPPORTS], cwd=rapport.RACINE,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **opts)
    F.etat_maj.text = "Bridge Coach se ferme pour la mise à jour, puis se rouvre tout seul."
    ui.timer(1.5, app.shutdown, once=True)


def annuler_maj():
    """« Annuler la mise à jour » : la version d'avant revient telle qu'elle était (maj.annuler), sans rien télécharger."""
    a = maj.annulable()
    if not a: return
    if any(x.actif for x in (T, D, I)):
        F.etat_maj.text = "Un calcul est en cours : attendez qu'il se termine, puis recommencez."; return
    ecrire_etat(maj_annulee=a["apres"])
    opts = {"creationflags": 0x00000008 | 0x00000200} if sys.platform == "win32" else {"start_new_session": True}
    subprocess.Popen([sys.executable, "-I", "-X", "utf8", os.path.join(ICI, "maj.py"), "--appliquer", "annuler",
                      "--attendre", str(os.getpid()), "--journal", rapport.RAPPORTS], cwd=rapport.RACINE,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **opts)
    F.etat_maj.text = f"Bridge Coach se ferme, revient à la version {a['avant']}, puis se rouvre tout seul."
    ui.timer(1.5, app.shutdown, once=True)


def choisir(c):
    F.choix["chemin"] = c; F.faute.text = ""
    retenir(c); F.montrer_titre(); F.vue["entree"] = "seance"; F.vue.pop("version", None); F.expert_msg.update(texte="", faute=False); F.vue_seance.refresh(); F.barre_seance.refresh(); F.montrer_barre(); F.montrer_controles()
    F.resultats.refresh(); F.vue_analyse.refresh(); F.choix_r.update(quelles="toutes", nums=[]); F.options_rapports.refresh()
    try: F.choix_moi.set_options(F.options_joueurs(moi.nom()), value=moi.nom() or "")   # « Vous êtes » : les joueurs de cette séance
    except (NameError, AttributeError): pass
    if F.onglets.value not in (F.o_donnes, F.o_analyse, F.o_rapports, "Donnes", "Analyse", "Rapports"): F.onglets.set_value(F.o_donnes)


async def preparer_import(b):
    """Un fichier à importer : Fichier, Nouveau montre le titre et le nom proposés ; rien n'est écrit avant « Importer »."""
    if T.actif or D.actif or I.actif: return
    F.a_importer.update(chemin=b, prop=None, titre="", nom="", nom_touche=False, lecture=True, faute="")
    F.onglets.set_value(F.o_fichier); F.voir_page("Fichier", "nouveau")
    F.choisir_facon("pbn" if b.lower().endswith(".pbn") else "bws")
    F.formulaire_import.refresh()
    try:
        p = await run.io_bound(fichiers.proposer, b)
        F.a_importer.update(prop=p, titre=p["titre"], nom=p["nom"])
    except SystemExit as ex:
        F.a_importer["faute"] = str(ex)
    except Exception as ex:
        F.a_importer["faute"] = (f"{os.path.basename(b)} ne se lit pas : {ex}" if isinstance(ex, ValueError)
                               else f"{os.path.basename(b)} ne se lit pas comme un tournoi.")
    F.a_importer["lecture"] = False
    F.formulaire_import.refresh()


def fermer_import():
    F.a_importer.update(chemin=None, prop=None); F.formulaire_import.refresh()


def importer(b, nom=None, titre=None):
    if T.actif or D.actif or I.actif: return
    F.vu_i["fini"] = None; F.faute_i.text = ""
    F.fermer_import()
    F.onglets.set_value(F.o_donnes)
    lancer_import(b, nom, titre); F.nouveau.refresh()


def exporter_seance():
    c = F.choix["chemin"]
    if not c or not c.endswith(rapport.BC):
        ui.notify("Ouvrez d'abord une séance (Fichier, Ouvrir une séance)."); return
    F.exporte["faute"] = ""
    try:
        F.exporte["f"] = exporter.exporter(c, F.exporte["format"], F.exporte["quoi"], F.exporte["noms"])
        fichiers.journal_seance(c, f"Exportée : {os.path.basename(F.exporte['f'])}")
    except ValueError as ex:
        F.exporte["f"] = None; F.exporte["faute"] = str(ex)
    except PermissionError:
        F.exporte["f"] = None; F.exporte["faute"] = "Le fichier est ouvert dans un autre programme (Excel ?) : fermez-le, puis recommencez."
    except Exception:
        F.exporte["f"] = None; F.exporte["faute"] = "Cette séance ne peut pas être exportée."
    F.a_exporter.refresh()


def apres_changement(c, message=""):
    """Après un renommage, une copie ou la corbeille : la séance ouverte, les listes et le titre de la fenêtre suivent."""
    F.infos_ui.update(copie=False, faute="", fait=message)
    if c: F.choisir(c)
    else:
        F.choix["chemin"] = None; retenir(None); F.montrer_titre(); F.vue["entree"] = "seance"
        F.vue_seance.refresh(); F.barre_seance.refresh(); F.montrer_barre(); F.montrer_controles(); F.resultats.refresh(); F.vue_analyse.refresh()
    F.onglets.set_value(F.o_fichier); F.voir_page("Fichier", "infos" if c else "ouvrir")


def changer_titre_(c, titre):
    try:
        fichiers.changer_titre(c, titre)
    except ValueError as ex:
        F.infos_ui["faute"] = str(ex); F.page_infos.refresh(); return
    F.apres_changement(c, "Titre enregistré.")


def renommer_(c, nom):
    if T.actif or D.actif or I.actif:
        F.infos_ui["faute"] = "Un calcul est en cours : attendez qu'il se termine."; F.page_infos.refresh(); return
    try:
        n = fichiers.renommer(c, nom)
    except ValueError as ex:
        F.infos_ui["faute"] = str(ex); F.page_infos.refresh(); return
    except OSError:
        F.infos_ui["faute"] = "Le fichier n'a pas pu être renommé (ouvert dans un autre programme ?)."; F.page_infos.refresh(); return
    F.apres_changement(n, f"Renommée : {os.path.basename(n)}")


def adopter_(c, titre, nom):
    if T.actif or D.actif or I.actif:
        F.infos_ui["faute"] = "Un calcul est en cours : attendez qu'il se termine."; F.page_infos.refresh(); return
    try:
        n = fichiers.adopter(c, titre, nom)
    except (ValueError, OSError) as ex:
        F.infos_ui["faute"] = str(ex) if isinstance(ex, ValueError) else "Le fichier n'a pas pu être renommé."; F.page_infos.refresh(); return
    F.apres_changement(n, f"Titre et nom enregistrés : {os.path.basename(n)}")


def dupliquer_(c, nom, titre):
    try:
        n = fichiers.dupliquer(c, nom, titre)
    except ValueError as ex:
        F.infos_ui["faute"] = str(ex); F.page_infos.refresh(); return
    F.apres_changement(n, "Copie créée : c'est elle qui est ouverte.")


async def sauvegarder_():
    """Où l'écrire : la fenêtre demande (Documents par défaut) ; dans le navigateur, le dossier sauvegardes du dossier de travail."""
    F.sauve.update(fait="", faute="")
    nom_ = fichiers.nom_sauvegarde()
    if app.native.main_window:
        r = await app.native.main_window.create_file_dialog(dialog_type=webview_save(), directory=os.path.expanduser("~/Documents"),
                                                             save_filename=nom_)
        if not r: return
        cible = r if isinstance(r, str) else r[0]
        if not cible.lower().endswith(".zip"): cible += ".zip"
    else:
        os.makedirs(os.path.join(rapport.DONNEES, "sauvegardes"), exist_ok=True)
        cible = os.path.join(rapport.DONNEES, "sauvegardes", nom_)
    try:
        n = await run.io_bound(fichiers.sauvegarder, cible)
    except OSError:
        F.sauve["faute"] = "La sauvegarde n'a pas pu être écrite à cet endroit : choisissez un autre dossier."
        F.etat_sauvegarde.refresh(); return
    ecrire_etat(sauvegarde_le=datetime.datetime.now().isoformat(timespec="seconds"), sauvegarde_chemin=cible)
    F.sauve["fait"] = f"{n} séance{'s' if n > 1 else ''} sauvegardée{'s' if n > 1 else ''} dans {cible}"
    F.etat_sauvegarde.refresh()


def remettre_(d_):
    F.faute_o["texte"] = ""
    try:
        c = fichiers.remettre(d_)
    except (ValueError, OSError) as ex:
        F.faute_o["texte"] = str(ex) if isinstance(ex, ValueError) else "La séance n'a pas pu être remise."
        F.liste.refresh(); return
    F.choisir(c); F.onglets.set_value(F.o_fichier); F.voir_page("Fichier", "ouvrir")
    ui.notify(f"Séance remise : {fichiers.titre_de(c)}")


def demander_corbeille(c):
    F.a_jeter["c"] = c
    F.corbeille_texte.text = (f"Mettre « {fichiers.titre_de(c)} » à la corbeille, avec ses rapports, ses parties jouées et ses "
                            "versions gardées ? Rien n'est effacé : tout va dans le dossier corbeille du dossier de travail, "
                            "d'où vous pouvez le remettre.")
    F.corbeille_d.open()


def mettre_a_la_corbeille():
    """Depuis Infos (la séance ouverte) ou depuis une ligne d'Ouvrir une séance (n'importe laquelle)."""
    F.corbeille_d.close(); c = F.a_jeter["c"] or F.choix["chemin"]
    if not c: return
    ouverte = bool(F.choix["chemin"]) and os.path.abspath(c) == os.path.abspath(F.choix["chemin"])
    def faute(texte):
        if F.vue_page["Fichier"] == "infos": F.infos_ui["faute"] = texte; F.page_infos.refresh()
        else: F.faute_o["texte"] = texte; F.liste.refresh()
    if T.actif or D.actif or I.actif: faute("Un calcul est en cours : attendez qu'il se termine."); return
    titre_ = fichiers.titre_de(c)                     # avant : ensuite, le fichier n'est plus là
    try:
        fichiers.corbeille(c)
    except OSError:
        faute("La séance n'a pas pu aller à la corbeille (un fichier est ouvert ailleurs ?)."); return
    F.faute_o["texte"] = ""
    if ouverte: F.apres_changement(None)
    else: F.liste.refresh(); F.liste_i.refresh()
    ui.notify(f"« {titre_} » est dans la corbeille : « Remettre », en bas d'Ouvrir une séance, la replace.",
              multi_line=True, timeout=8000)


def demander_vider(n):
    F.vider_texte.text = (f"Vider la corbeille de Bridge Coach ? {'Ses ' + str(n) + ' séances' if n > 1 else 'La séance qu’elle contient'}, "
                        f"avec leurs rapports et leurs parties jouées, iront dans la {CORBEILLE_SYSTEME}. Vous pourrez encore "
                        "les y reprendre, jusqu'à ce que vous la vidiez.")
    F.vider_d.open()


def vider_corbeille_():
    F.vider_d.close(); F.faute_o["texte"] = ""
    try:
        n = fichiers.vider_corbeille()
    except OSError:
        F.faute_o["texte"] = (f"La corbeille n'a pas pu être vidée dans la {CORBEILLE_SYSTEME}. Rien n'a été effacé ; vous pouvez "
                            "la vider à la main : « Ouvrir la corbeille ».")
        F.liste.refresh(); return
    F.liste.refresh()
    ui.notify(f"{n} séance{'s' if n > 1 else ''} dans la {CORBEILLE_SYSTEME}.")


async def parcourir_i(types, envoi):
    if not app.native.main_window: return envoi.run_method("pickFiles")
    r = await app.native.main_window.create_file_dialog(allow_multiple=False, file_types=types)
    if r: await F.preparer_import(r[0])


async def recu_i(e):
    cible = os.path.join(tempfile.mkdtemp(prefix="import-"), os.path.basename(e.file.name))
    await e.file.save(cible)
    await F.preparer_import(cible)


async def parcourir():
    """Dans la fenêtre, le dialogue de l'ordinateur : celui d'une page n'y s'ouvre pas. Le navigateur garde le sien."""
    if not app.native.main_window: return F.envoi.run_method("pickFiles")
    r = await app.native.main_window.create_file_dialog(allow_multiple=False, file_types=TYPES_SEANCES)
    if r: F.choisir(r[0])


async def recu(e):
    """Le fichier choisi arrive par la page : on le garde sous son nom, dans un dossier provisoire."""
    cible = os.path.join(tempfile.mkdtemp(prefix="rapports-"), os.path.basename(e.file.name))
    await e.file.save(cible)
    F.choisir(cible)


def demarrer_donnes():
    if T.actif or D.actif or I.actif or not 1 <= F.total() <= 36: return
    F.vu_d["fini"] = None; F.faute_d.text = ""
    lancer_donnes([(t, k) for t, k in F.quotas.items() if k])
    F.fichier_cree.refresh()


def analyser_donnes():
    F.choisir(D.fichier); F.onglets.set_value(F.o_analyse)


def demarrer():
    if T.actif or D.actif or I.actif or not F.choix["chemin"]: return
    F.vu["fini"] = None; F.faute.text = ""; F.faute_r.text = ""; F.fait_a.text = ""
    lancer(F.choix["chemin"])
    F.resultats.refresh(); F.montrer_controles()


def rafraichir():
    actif_i = I.actif
    F.barre_i.set_visibility(actif_i); F.texte_i.set_visibility(actif_i)
    if actif_i: F.texte_i.text = I.texte
    if I.fini and F.vu_i["fini"] is not I.proc:          # l'import vient de finir : la séance s'ouvre
        F.vu_i["fini"] = I.proc
        F.faute_i.text = "" if I.annule else I.erreur
        if I.fichier and not I.erreur:
            F.choisir(I.fichier)
            e_ = lire_etat()
            if not e_.get("mon_nom") and not e_.get("qui_demande"): F.demander_qui(I.fichier)   # une fois : qui êtes-vous ?
        F.nouveau.refresh()
    actif = T.actif; occupe = actif or actif_i         # un travail à la fois
    analyse_ = actif and T.genre == "analyse"; rapports_ = actif and T.genre == "rapports"
    F.creer.set_enabled(not occupe and not D.actif and bool(F.choix["chemin"])); F.stop.set_visibility(analyse_)
    standard_ = bool(F.choix["chemin"]) and bool(lire_analyses(F.choix["chemin"])[0])
    F.creer_r.set_enabled(not occupe and not D.actif and standard_); F.stop_r.set_visibility(rapports_)
    F.besoin_r.text = ("Aucune séance ouverte : Fichier, Ouvrir une séance" if not F.choix["chemin"] else
                     "" if standard_ else "Lancez d'abord l'analyse, dans l'onglet Analyse.")
    actif_d = D.actif
    F.creer_d.set_enabled(not occupe and not actif_d); F.stop_d.set_visibility(actif_d)
    F.barre_d.set_visibility(actif_d); F.texte_d.set_visibility(actif_d)
    if actif_d: F.barre_d.set_value(round(D.fraction, 3)); F.texte_d.text = D.texte
    if D.fini and F.vu_d["fini"] is not D.proc:
        F.vu_d["fini"] = D.proc
        F.faute_d.text = "" if D.annule else D.erreur
        F.fichier_cree.refresh()
        if D.fichier and not D.erreur and not D.annule:   # la nouvelle séance s'ouvre, comme une séance vide
            F.choisir(D.fichier); F.onglets.set_value(F.o_donnes)
            if D.notes: ui.notify("Tirées au hasard faute de temps : " + " ; ".join(D.notes) + ".", multi_line=True, timeout=10000)
    F.barre.set_visibility(analyse_); F.texte.set_visibility(analyse_)
    F.barre_r.set_visibility(rapports_); F.texte_r.set_visibility(rapports_)
    if actif:
        b, t_ = (F.barre, F.texte) if analyse_ else (F.barre_r, F.texte_r)
        b.set_value(round(T.fraction, 3)); t_.text = f"{T.texte} · {int(T.fraction * 100)} %"
    if T.fini and F.vu["fini"] is not T.proc:            # le travail vient de finir : une seule fois
        F.vu["fini"] = T.proc
        erreur = "" if T.annule else T.erreur
        if T.genre == "imprimer":                      # une donne à imprimer : son PDF s'ouvre
            if erreur: ui.notify(erreur, type="negative", multi_line=True)
            elif T.prets and not T.annule: ouvrir(T.prets[-1])
            F.resultats.refresh(); F.vue_analyse.refresh(); F.montrer_controles(); return
        if T.genre == "analyse":
            F.faute.text = erreur
            F.fait_a.text = "" if erreur or T.annule else "Analyse faite : lisez-la donne par donne. Les rapports PDF se font dans l'onglet Rapports."
        else:
            F.faute_r.text = erreur
            if not erreur and not T.annule: F.voir_page("Rapports", "seance")   # les rapports prêts : leur liste
        F.resultats.refresh(); F.vue_analyse.refresh(); F.montrer_controles()


def panneau():
    """Le haut de l'onglet Fichier (la page Nouveau)."""
    titre_page("Nouvelle séance", "importer")
    ui.html("Une séance réunit les donnes, les joueurs, les résultats et les analyses. Trois façons d'en créer "
            "une :", sanitize=False).classes("text-base text-gray-700")
    F.FACONS = [("bws", "Importer un tournoi", "Bridgemate (.bws), feuille de route (.pdf) ou pages du site de la FFB",
                 "table_restaurant"),
              ("pbn", "Importer un fichier PBN", "des donnes de BBO, Funbridge, d'un autre logiciel…", "description"),
              ("themes", "Créer des donnes d'entraînement", "sur des thèmes choisis, ou une séance vide", "school")]
    F.sections_n = {}

    def choisir_facon(k):
        F.facon["k"] = k; F.cartes_facon.refresh()
        for x, col in F.sections_n.items(): col.set_visibility(x == k)
        F.retenir_page()
    F.choisir_facon = choisir_facon

    @ui.refreshable
    def cartes_facon():
        with ui.row().classes("w-full no-wrap gap-3 mt-2 mb-4 items-stretch"):   # trois cartes de même taille
            for k, titre, sous, icone in F.FACONS:
                choisi = F.facon["k"] == k
                with ui.column().classes("gap-1 p-3 cursor-pointer").style(
                        "flex:1 1 0;min-width:0;border-radius:10px;" + ("background:var(--bc-pique-50);border:2px solid var(--bc-pique-600)" if choisi else
                                                 "background:var(--bc-blanc);border:2px solid var(--bc-pique-100)")) \
                        .on("click", lambda k=k: F.choisir_facon(k)):
                    with ui.row().classes("items-start no-wrap gap-2"):
                        ui.icon(icone, size="22px").classes("text-primary" if choisi else "text-gray-600")
                        ui.label(titre).classes("text-base font-bold")
                    ui.label(sous).classes("text-base text-gray-700")
    F.cartes_facon = cartes_facon
    F.cartes_facon()

    @ui.refreshable
    def formulaire_import():
        """Avant d'importer : le titre et le nom du fichier proposés, à changer si on veut (fichiers.proposer)."""
        x = F.a_importer
        if not x["chemin"]: return
        with ui.column().classes("w-full gap-2 p-4 mb-4").style("border:2px solid var(--bc-pique-600);border-radius:10px;background:var(--bc-pique-50)"):
            ui.label(f"Importer {os.path.basename(x['chemin'])}").classes("text-lg font-bold break-all")
            if x["lecture"]:
                ui.label("Lecture du fichier…").classes("text-base text-gray-700"); return
            if x["faute"]:
                ui.label(x["faute"]).classes("text-base text-red-800")
                ui.button("Fermer", on_click=lambda: F.fermer_import()).props("flat"); return
            p = x["prop"]
            ui.label(f"Séance du {p['date']}").classes("text-base text-gray-700")
            if p["deja"]:
                ui.html(f"Déjà importé : <b>{html_.escape(fichiers.titre_de(p['deja']))}</b>. L'importer à nouveau met "
                        "cette séance à jour ; ses analyses, ses parties jouées et les noms complets restent.",
                        sanitize=False).classes("text-base text-gray-700")
            titre_in = ui.input("Titre", value=x["titre"]).props("outlined").classes("w-full text-base")
            nom_in = ui.input("Nom du fichier", value=x["nom"]).props("outlined suffix=.bc.json").classes("w-full text-base")
            nom_in.set_enabled(not p["deja"])          # un réimport garde son fichier (Fichier, Infos le renomme)
            aide = ui.label("").classes("text-base")

            def verifier():
                n = fichiers.nettoyer_nom(nom_in.value); x["nom"] = nom_in.value; x["titre"] = titre_in.value
                pris = n and not p["deja"] and os.path.exists(os.path.join(p["dossier"], n + rapport.BC))
                aide.text = ("Donnez un nom au fichier." if not n else
                             f"Ce nom est déjà pris : {n}.bc.json" if pris else
                             f"Enregistré sous : {n}.bc.json" if n != nom_in.value.strip() else "")
                aide.classes(replace="text-base " + ("text-red-800" if (pris or not n) else "text-gray-700"))
                ok.set_enabled(bool(n) and not pris and bool(titre_in.value.strip()))

            def titre_change(e):
                if not x["nom_touche"] and not p["deja"]:   # le nom suit le titre, tant qu'on ne l'a pas tapé
                    x["nom"] = fichiers.nom_libre(p["dossier"], fichiers.nom_propose(
                        {"session": {"date": p["date"]}}, e.value, p["genre"]))
                    nom_in.value = x["nom"]           # (x["nom"] d'abord : nom_change n'y voit pas une frappe)
                verifier()

            def nom_change(_):
                if nom_in.value != x["nom"]: x["nom_touche"] = True
                verifier()
            with ui.row().classes("gap-3"):
                ok = ui.button("Importer" if not p["deja"] else "Importer à nouveau", icon="download",
                               on_click=lambda: F.importer(x["chemin"], fichiers.nettoyer_nom(nom_in.value), titre_in.value.strip())) \
                    .props("unelevated")
                ui.button("Annuler", on_click=lambda: F.fermer_import()).props("flat")
            titre_in.on_value_change(titre_change); nom_in.on_value_change(nom_change)
            verifier()
    F.formulaire_import = formulaire_import
    F.formulaire_import()

    with ui.column().classes("w-full gap-0") as F.sections_n["themes"]:
      ui.label("Choisissez des thèmes et combien de donnes de chacun ; sans thème, la séance est vide et vous tapez "
               "les mains dans l'onglet Donnes. Les thèmes d'enchères et de jeu de la carte choisis ensemble sont "
               "réunis dans les mêmes donnes. Elles sont créées dans une nouvelle séance .bc.json, avec un .pbn à côté "
               "pour Bridgemate.").classes("text-base text-gray-700")
      F.quotas = {x: 0 for x in donnes.themes_tries()}
      F.niveaux = set(lire_etat().get("niveaux") or [1])   # les niveaux montrés, gardés d'une fois sur l'autre
      F.total = lambda: sum(k for _, k in donnes.combiner([(t, k) for t, k in F.quotas.items() if k]))

      def changer(x, k):
          avant = F.quotas[x]; F.quotas[x] = max(0, F.quotas[x] + k)
          if F.total() > 36: F.quotas[x] = avant          # 36 donnes au plus
          F.liste_themes.refresh(); F.bouton_creer()
      F.changer = changer

      def basculer(n):
          F.niveaux.symmetric_difference_update({n})
          if not F.niveaux: F.niveaux.add(n)
          ecrire_etat(niveaux=sorted(F.niveaux)); F.liste_themes.refresh()
      F.basculer = basculer

      def theme_ligne(x):
          k = F.quotas[x]
          with ui.row().classes("w-full items-center justify-between no-wrap"):
              ui.label(x).classes("text-base" + (" font-bold text-primary" if k else ""))
              with ui.row().classes("items-center no-wrap gap-0"):
                  ui.button(icon="remove", on_click=lambda x=x: F.changer(x, -1)).props("flat round dense").set_enabled(k > 0)
                  ui.label(str(k)).classes("w-7 text-center text-base" + (" font-bold" if k else " text-gray-400"))
                  ui.button(icon="add", on_click=lambda x=x: F.changer(x, 1)).props("flat round dense")
      F.theme_ligne = theme_ligne

      @ui.refreshable
      def liste_themes():
          with ui.row().classes("gap-2 mt-2"):            # les niveaux montrés
              for n, nom in donnes.NIVEAUX.items():
                  ui.button(nom, on_click=lambda n=n: F.basculer(n)) \
                      .props(("unelevated" if n in F.niveaux else "outline") + " dense no-caps rounded").classes("px-3")
          with ui.row().classes("w-full no-wrap items-start gap-4 mt-2"):
              for f, titre in donnes.FAMILLES.items():
                  with ui.column().classes("gap-0 grow basis-0 p-3").style(
                          "background:var(--bc-blanc);border:1px solid var(--bc-pique-100);border-radius:10px"):
                      ui.label(titre).classes("text-base font-bold mb-1")
                      caches = []
                      for n, nom in donnes.NIVEAUX.items():
                          ts = donnes.themes_de(f, n)
                          vus = ts if n in F.niveaux else [t for t in ts if F.quotas[t]]   # un thème choisi reste visible
                          if n not in F.niveaux and len(vus) < len(ts):
                              m = len(ts) - len(vus)
                              caches.append(f"{m} " + {1: "de 1re année", 2: "intermédiaire" + "s" * (m > 1),
                                                       3: "avancé" + "s" * (m > 1)}[n])
                          if not vus: continue
                          ui.label(nom).classes("text-base text-gray-700 mt-2")
                          for t in vus: F.theme_ligne(t)
                      if caches: ui.label("Autres thèmes : " + ", ".join(caches)).classes("text-base text-gray-600 mt-2")
          with ui.row().classes("w-full items-center justify-between no-wrap mt-2").style("max-width:50%"):
              ui.label("Donnes au hasard").classes("text-base")
              with ui.row().classes("items-center no-wrap gap-0"):
                  k = F.quotas[donnes.ALEATOIRE]
                  ui.button(icon="remove", on_click=lambda: F.changer(donnes.ALEATOIRE, -1)).props("flat round dense").set_enabled(k > 0)
                  ui.label(str(k)).classes("w-7 text-center text-base" + (" font-bold" if k else " text-gray-400"))
                  ui.button(icon="add", on_click=lambda: F.changer(donnes.ALEATOIRE, 1)).props("flat round dense")
          choisis = donnes.combiner([(t, k) for t, k in F.quotas.items() if k])
          n = F.total()
          resume = " ; ".join(f"{t} {k}" for t, k in choisis)
          ui.label(f"{n} donne{'s' if n > 1 else ''} : {resume}" if n else "Aucun thème choisi : la séance sera vide.") \
              .classes("text-base mt-3 pt-2 w-full").style("border-top:1px solid var(--bc-pique-100)")
      F.liste_themes = liste_themes
      F.liste_themes()

      def bouton_creer():
          n = F.total()
          F.creer_d.text = f"Créer {n} donne{'s' if n > 1 else ''}" if n else "Créer une séance vide"
          F.creer_d.set_enabled(not (T.actif or D.actif or I.actif))
      F.bouton_creer = bouton_creer

      with ui.column().classes("w-full gap-4"):
          F.creer_d = ui.button("Créer une séance vide", icon="add", on_click=lambda: F.demarrer_donnes() if F.total() else F.creer_vide()) \
              .props("unelevated").classes("text-base self-start")
          F.barre_d = ui.linear_progress(value=0, show_value=False).props("size=16px rounded")
          F.texte_d = ui.label("").classes("text-base")
          F.stop_d = ui.button("Annuler", on_click=lambda: annuler(D)).props("outline")
          F.faute_d = ui.label("").classes("text-base text-red-800")

          @ui.refreshable
          def fichier_cree():
              if not D.fichier or D.actif: return
              ui.label("Donnes créées").classes("text-base font-bold")
              ui.label(os.path.basename(D.fichier)).classes("text-base text-gray-700 break-all")
              if D.notes:
                  ui.label("Tirées au hasard faute de temps : " + " ; ".join(D.notes) + ".").classes("text-base text-red-800")
              with ui.row().classes("gap-3"):
                  ui.button("Analyser ces donnes", on_click=lambda: F.analyser_donnes())
                  ui.button("Ouvrir le dossier", on_click=lambda: ouvrir(os.path.dirname(D.fichier))).props("outline")
              ui.label("Le fichier .pbn du dossier s'importe dans Bridgemate : Fichier, Importer.").classes("text-base text-gray-700")
          F.fichier_cree = fichier_cree
          F.fichier_cree()


def pages_ouvrir_nouveau():
    """Fichier : Ouvrir une séance, et les façons d'importer."""
    with F.panneau_fichier, ui.column().classes("w-full gap-2") as F.pages_ui["ouvrir"]:   # Fichier, Ouvrir une séance
        titre_page("Ouvrir une séance", "retrouver")
        F.faute_o = {"texte": ""}
        F.recherche_o = {"texte": ""}
        ui.input(placeholder="Chercher une séance : un mot du titre, une date (12/11)…",
                 on_change=lambda e: (F.recherche_o.update(texte=e.value or ""), F.liste.refresh())) \
            .props("outlined dense clearable debounce=250").classes("w-full text-base").style("max-width:760px")

        F.tri_o = {"col": "date", "desc": True}             # Ouvrir une séance : la colonne de tri, comme l'Explorateur
        F.fermes_o = set()                                   # les mois repliés (un clic sur leur titre)
        F.ICONE_SOURCE = {"bws": "emoji_events", "ffb-html": "emoji_events", "ffb-pdf": "emoji_events",
                        "feuille-de-route": "emoji_events", "entrainement": "school", "saisie": "edit_note",
                        "pbn": "description", "simulation": "casino", "brouillon": "shopping_basket"}
        F.COLONNES_O = (("nom", "Nom"), ("date", "Date"), ("type", "Type"), ("donnes", "Donnes"),
                      ("partenaire", "Partenaire"), ("resultat", "Résultat"))

        def trier_par(col):
            if F.tri_o["col"] == col: F.tri_o["desc"] = not F.tri_o["desc"]
            else: F.tri_o.update(col=col, desc=col in ("date", "donnes", "resultat"))
            F.liste.refresh()
        F.trier_par = trier_par

        def cle_tri(c):
            r = resume_seance(c); date, source = infos_seance(c)
            j, m, a_ = (date.split("/") + ["", "", ""])[:3]
            return {"nom": (r["court"] or r["titre"] or fichiers.titre_de(c)).lower(), "date": a_ + m + j + heure_seance(c),
                    "type": source.lower(), "donnes": r["donnes"] or 0, "partenaire": (r["partenaire"] or "").lower(),
                    "resultat": -1 if r["pct"] is None else r["pct"]}[F.tri_o["col"]]
        F.cle_tri = cle_tri

        def entete_ouvrir():
            """La ligne des colonnes, une fois en haut, comme l'Explorateur de Windows (l'utilisateur, 2026-11-17) :
            un clic trie, un second inverse ; la flèche dit l'ordre."""
            with ui.element("div").classes("tableau-seances entete-seances"):
                ui.element("div")                          # la colonne de l'icône
                for col, t in F.COLONNES_O:
                    fl = ("▼" if F.tri_o["desc"] else "▲") if F.tri_o["col"] == col else ""
                    ui.label(f"{t} {fl}".strip()).classes("cursor-pointer select-none" + (" actif" if fl else "")) \
                        .on("click", lambda col=col: F.trier_par(col))
                ui.element("div")
        F.entete_ouvrir = entete_ouvrir

        def ligne_ouvrir(c, est, brouillon_=False, n_b=0):
            """Une séance, une ligne de la liste comme dans l'Explorateur de Windows, vue Détails (l'utilisateur, 2026-11-17) :
            l'icône du genre, le nom (le titre court), la date, le type, les donnes, votre partenaire, votre % et votre rang ;
            une ligne fine, en bleu pâle sous la souris et en bleu pour la séance ouverte ; la corbeille au survol."""
            date, source = infos_seance(c)
            r = resume_seance(c)
            res = ""
            if r["pct"] is not None:
                res = f"{r['pct']:.1f} %".replace(".", ",") + (f" · {r['rang']}{'re' if r['rang'] == 1 else 'e'}/{r['paires']}"
                                                              if r["rang"] and r["paires"] else "")
            genre = "brouillon" if brouillon_ else next((k for k, v in SOURCES.items() if v == source), "")
            with ui.element("div").classes("tableau-seances ligne-seance" + (" ouverte" if est else "")) \
                    .on("click", lambda c=c: F.choisir(c)):
                ui.icon(F.ICONE_SOURCE.get(genre, "insert_drive_file"), size="18px").classes("icone-seance")
                ui.label("Brouillon" if brouillon_ else (r["court"] or r["titre"] or fichiers.titre_de(c))).classes("titre-seance truncate")
                ui.label("" if brouillon_ else f"{date} {heure_seance(c)}".strip()).classes("whitespace-nowrap")
                ui.label("Cours" if brouillon_ else source).classes("truncate")
                n = n_b if brouillon_ else r["donnes"]
                ui.label("" if n is None else str(n)).classes("text-right")
                ui.label(r["partenaire"]).classes("truncate")
                ui.label(res).classes("text-right")
                if brouillon_: ui.element("div")
                else:
                    ui.button(icon="delete_outline", on_click=lambda c=c: F.demander_corbeille(c)) \
                        .props("flat round dense size=sm color=grey-7").classes("poubelle").tooltip("Mettre à la corbeille…") \
                        .on("click.stop", lambda: None)
        F.ligne_ouvrir = ligne_ouvrir

        def groupe_ouvrir(cle, titre, n):
            """Le titre d'un groupe (un mois), comme ceux de l'Explorateur : « Novembre 2026 (8) » et un trait ; un clic replie."""
            ferme = cle in F.fermes_o
            with ui.element("div").classes("groupe-seances cursor-pointer select-none") \
                    .on("click", lambda: (F.fermes_o.symmetric_difference_update({cle}), F.liste.refresh())):
                ui.icon("chevron_right" if ferme else "expand_more", size="18px")
                ui.label(f"{titre} ({n})")
                ui.element("div").classes("trait")
            return not ferme
        F.groupe_ouvrir = groupe_ouvrir

        @ui.refreshable
        def liste():
            b_ = brouillon.assurer()
            tout = [x for x in seances_bc() if not brouillon.est_brouillon(x)]
            n_b = brouillon.nombre(); ouv_b = brouillon.est_brouillon(F.choix["chemin"])
            if not tout:
                with ui.row().classes("items-center gap-3"):
                    ui.label("Pas encore de séance.").classes("text-base text-gray-700")
                    ui.button("Créer une séance", icon="add", on_click=lambda: F.voir_page("Fichier", "nouveau")).props("unelevated no-caps")
            rappel = rappel_sauvegarde(len(tout))
            if rappel:                                     # une sauvegarde vieille d'un mois, ou jamais faite
                with ui.row().classes("w-full items-center justify-between no-wrap gap-3 px-3 py-2 mb-2") \
                        .style("background:var(--bc-jaune-50);border-left:4px solid var(--bc-jaune-400);border-radius:6px"):
                    ui.label(rappel).classes("text-base")
                    ui.button("Sauvegarder", icon="save", on_click=lambda: (F.onglets.set_value(F.o_reglages), F.voir_page("Réglages", "sauvegarde"))) \
                        .props("outline").classes("shrink-0")
            cherche = F.recherche_o["texte"].strip().lower()
            if cherche:                                    # la recherche : seulement les séances dont le titre ou la date répond
                tout = [c for c in tout if cherche in (fichiers.titre_de(c) + " " + resume_seance(c)["titre"] + " " + infos_seance(c)[0] + " "
                                                       + os.path.basename(c)).lower()]
            ouverte = os.path.abspath(F.choix["chemin"]) if F.choix["chemin"] else None
            with ui.column().classes("w-full gap-0 liste-seances"):
                F.entete_ouvrir()
                if not cherche: F.ligne_ouvrir(b_, ouv_b, brouillon_=True, n_b=n_b)   # le Brouillon, toujours en tête
                if F.tri_o["col"] == "date":                 # par date : groupés par mois, comme l'Explorateur
                    mois = {}
                    for c in sorted(tout, key=F.cle_tri, reverse=F.tri_o["desc"]):
                        j, m, a_ = (infos_seance(c)[0].split("/") + ["", "", ""])[:3]
                        mois.setdefault((a_, m), []).append(c)
                    for (a_, m), cs in mois.items():
                        nom_mois = (fichiers.MOIS[int(m) - 1].capitalize() + " " + a_) if m.isdigit() else "Sans date"
                        if F.groupe_ouvrir((a_, m), nom_mois, len(cs)):
                            for c in cs: F.ligne_ouvrir(c, ouverte == os.path.abspath(c))
                else:
                    for c in sorted(tout, key=F.cle_tri, reverse=F.tri_o["desc"]): F.ligne_ouvrir(c, ouverte == os.path.abspath(c))
            if cherche and not tout:
                ui.label(f"Aucune séance ne contient « {F.recherche_o['texte'].strip()} ».").classes("text-base text-gray-700")
            jetees = fichiers.dans_la_corbeille()
            if jetees:                                     # la corbeille, repliée : on en remet une d'un clic
                with ui.expansion(f"Corbeille · {len(jetees)} séance{'s' if len(jetees) > 1 else ''}", icon="delete") \
                        .classes("w-full text-base mt-3").props("dense header-class='text-base text-gray-700'"):
                    ui.label("Rien n'y est effacé. « Remettre » replace la séance avec ses rapports et ses parties jouées.") \
                        .classes("text-base text-gray-700")
                    for d_, titre_, date_, quand_ in jetees:
                        with ui.row().classes("w-full items-center justify-between no-wrap gap-3 py-1"):
                            with ui.column().classes("gap-0"):
                                ui.label(titre_).classes("text-base font-bold")
                                ui.label(f"Séance du {date_} · mise à la corbeille le {quand_}").classes("text-sm text-gray-600")
                            ui.button("Remettre", icon="restore_from_trash", on_click=lambda d_=d_: F.remettre_(d_)).props("outline").classes("shrink-0")
                    with ui.row().classes("items-center gap-3 mt-2"):
                        ui.button("Vider la corbeille…", icon="delete_sweep", on_click=lambda n_=len(jetees): F.demander_vider(n_)) \
                            .props("outline color=red")
                        ui.button("Ouvrir la corbeille", icon="folder_open", on_click=lambda: ouvrir(fichiers.corbeille_dossier())).props("flat")
                    ui.label(f"Elle occupe {fichiers.en_mots(fichiers.taille_corbeille())}. La vider envoie ces séances dans la "
                             f"{CORBEILLE_SYSTEME}, d'où vous pouvez encore les reprendre tant que vous ne la videz pas.") \
                        .classes("text-base text-gray-700")
            if F.faute_o["texte"]: ui.label(F.faute_o["texte"]).classes("text-base text-red-800")
        F.liste = liste
        F.liste()
        ui.label("Ou une séance Bridge Coach (.bc.json) ailleurs sur l'ordinateur :").classes("text-base mt-2")
        F.envoi = ui.upload(on_upload=lambda e: F.recu(e), auto_upload=True, max_files=1).props('accept=".json"').classes("hidden")
        ui.button("Choisir un fichier…", on_click=lambda: F.parcourir()).props("outline")

    with F.pages_ui["nouveau"], ui.column().classes("w-full gap-2") as F.sections_n["bws"]:   # Nouveau, depuis un tournoi Bridgemate
        ui.html("Choisissez un tournoi : Bridge Coach en reprend les donnes, les joueurs, les enchères et les résultats dans "
                "une nouvelle séance, sous le titre que vous voulez. Le tournoi de Bridgemate reste tel quel.",
                sanitize=False).classes("text-base text-gray-700")
        ui.label("Les tournois du dossier de Bridgemate, les plus récents d'abord :").classes("text-base mt-1")
        @ui.refreshable
        def liste_i():
            bws = reglages()[0][:10]
            if not bws: ui.label(f"Aucun fichier .bws dans {F.dossier}.").classes("text-base text-gray-700")
            if not bws: return
            # comme Ouvrir une séance : le titre lisible du tournoi (fichiers.proposer), pas le nom du fichier .bws (2026-11-17)
            colonnes = "20px minmax(0, 1fr) 110px 110px"
            with ui.column().classes("w-full gap-0").style("max-width:860px"):
                with ui.element("div").classes("tableau-seances entete-seances").style(f"grid-template-columns:{colonnes}"):
                    for t_ in ("", "Tournoi", "Date", ""): ui.label(t_)
                for b in bws:
                    titre_b, deja_b = titre_bws(b)
                    with ui.element("div").classes("tableau-seances ligne-seance").style(f"grid-template-columns:{colonnes}") \
                            .on("click", lambda b=b: F.preparer_import(b)):
                        ui.icon("emoji_events", size="18px").classes("icone-seance")
                        ui.label(titre_b).classes("titre-seance truncate")
                        ui.label(date_lisible(b))
                        ui.label("déjà importé" if deja_b else "nouveau").classes("text-right" + ("" if deja_b else " font-bold")) \
                            .style("" if deja_b else "color:var(--bc-trefle-700)")
        F.liste_i = liste_i
        F.liste_i()
        ui.label("Ou un tournoi ailleurs sur l'ordinateur : un .bws, la feuille de route .pdf de FFBClubNet, ou les pages "
                 "du site de la FFB enregistrées depuis le navigateur.").classes("text-base mt-2")
        ui.html("<b>Les pages du site de la FFB :</b> enregistrez toutes les pages « Donne n° » et toutes les pages des "
                "paires (NS 1, EO 1…) dans un même dossier, puis choisissez la première donne, par exemple "
                "<b>donne01.html</b> : les autres pages sont lues avec elle. La feuille de route et les pages de la FFB "
                "donnent les mains et les résultats, sans les enchères.", sanitize=False).classes("text-base")
        F.envoi_i = ui.upload(on_upload=lambda e: F.recu_i(e), auto_upload=True, max_files=1).props('accept=".bws,.pdf,.html,.htm"').classes("hidden")
        ui.button("Choisir un fichier…", icon="folder_open", on_click=lambda: F.parcourir_i(TYPES_BWS, F.envoi_i)).props("outline").classes("self-start")

    with F.pages_ui["nouveau"], ui.column().classes("w-full gap-2") as F.sections_n["pbn"]:   # Nouveau, depuis un fichier PBN
        ui.html("Un fichier .pbn (Portable Bridge Notation) : les donnes d'un tournoi, de BBO, de Funbridge ou d'un autre "
                "logiciel. Bridge Coach <b>importe</b> les mains, le donneur et la vulnérabilité, et, quand le fichier les donne, "
                "le contrat, les enchères, l'entame et le résultat d'une table, dans une nouvelle séance. Le fichier .pbn reste "
                "tel quel.",
                sanitize=False).classes("text-base text-gray-700")
        F.envoi_p = ui.upload(on_upload=lambda e: F.recu_i(e), auto_upload=True, max_files=1).props('accept=".pbn"').classes("hidden")
        ui.button("Choisir un fichier .pbn…", icon="folder_open", on_click=lambda: F.parcourir_i(TYPES_PBN, F.envoi_p)).props("unelevated").classes("self-start")
    for F.x, F.col in F.sections_n.items(): F.col.set_visibility(F.x == F.facon["k"])



def pages_exporter_infos():
    """Fichier : Exporter et Infos."""
    with F.panneau_fichier, ui.column().classes("w-full gap-3") as F.pages_ui["exporter"]:   # Fichier, Exporter…
        titre_page("Exporter la séance", "exporter")
        ui.label("Le fichier exporté est écrit à côté de la séance, dans le dossier de travail. La séance elle-même ne "
                 "change pas.").classes("text-base text-gray-700")
        F.exporte = {"f": None, "format": lire_etat().get("export_format") or "excel", "quoi": "resultats", "noms": False, "faute": ""}
        @ui.refreshable
        def a_exporter():
            c = F.choix["chemin"]
            if not c or not c.endswith(rapport.BC):
                F.sans_seance(); return
            ui.label(f"Séance : {fichiers.titre_de(c)}").classes("text-base font-bold")
            with ui.column().classes("gap-2"):
                for k, nom, sous in exporter.FORMATS:          # le format : trois cartes, comme Nouveau
                    choisi = F.exporte["format"] == k
                    with ui.row().classes("items-center gap-3 p-3 cursor-pointer no-wrap w-full").style(
                            "border-radius:10px;" + ("background:var(--bc-pique-50);border:2px solid var(--bc-pique-600)" if choisi else
                                                     "background:var(--bc-blanc);border:2px solid var(--bc-pique-100)")) \
                            .on("click", lambda k=k: (F.exporte.update(format=k, f=None, faute=""), ecrire_etat(export_format=k), F.a_exporter.refresh())):
                        ui.icon("radio_button_checked" if choisi else "radio_button_unchecked", size="22px") \
                            .classes("text-primary" if choisi else "text-gray-600")
                        with ui.column().classes("gap-0"):
                            ui.label(nom).classes("text-base font-bold")
                            ui.label(sous).classes("text-base text-gray-700")
            if F.exporte["format"] == "csv":
                ui.toggle({k: v for k, v in exporter.TABLEAUX}, value=F.exporte["quoi"],
                          on_change=lambda e: F.exporte.update(quoi=e.value, f=None)).props("no-caps")
            if F.exporte["format"] in ("csv", "excel"):
                ui.checkbox("Avec les noms complets des joueurs (sinon les initiales, comme dans les rapports)", value=F.exporte["noms"],
                            on_change=lambda e: F.exporte.update(noms=e.value)).classes("text-base")
            ui.button("Exporter", icon="file_download", on_click=lambda: F.exporter_seance()).props("unelevated").classes("self-start mt-1")
            if F.exporte["faute"]: ui.label(F.exporte["faute"]).classes("text-base text-red-800")
            if F.exporte["f"] and os.path.dirname(F.exporte["f"]) == os.path.dirname(c):
                ui.label(f"Exporté : {os.path.basename(F.exporte['f'])}").classes("text-base break-all")
                with ui.row().classes("gap-3"):
                    if not F.exporte["f"].endswith(".pbn"):
                        ui.button("Ouvrir le fichier", icon="open_in_new", on_click=lambda: ouvrir(F.exporte["f"])).props("outline")
                    ui.button("Montrer dans le dossier", icon="folder_open", on_click=lambda: montrer_fichier(F.exporte["f"])).props("outline")
        F.a_exporter = a_exporter
        F.a_exporter()

    with F.panneau_fichier, ui.column().classes("w-full gap-3") as F.pages_ui["infos"]:   # Fichier, Infos
        titre_page("Infos sur la séance", "infos")
        F.infos_ui = {"copie": False, "faute": "", "fait": ""}
        def bloc_ordre(c, data):
            """Fichier, Infos : « Donneur et vulnérabilité selon le numéro », pour les séances faites dans Bridge Coach ; une
            séance importée garde ceux qui ont été joués (la dupliquer d'abord)."""
            ok_, pourquoi = edition.modifiable(c)
            if not ok_: return                              # une séance importée : rien à régler ici (l'utilisateur, 2026-11-17)
            titre_section("Donneur et vulnérabilité")
            on = bool((data.get("session") or {}).get("donneur_par_numero"))
            ui.checkbox("Selon le numéro de la donne, comme au club et pour une machine à donnes", value=on,
                        on_change=lambda e: F.demander_numero(c, e.value)).classes("text-base")
            ui.label("Sinon, chaque donne garde le donneur et la vulnérabilité qu'elle avait (une donne venue d'un tournoi, ceux de "
                     "son tournoi).").classes("text-base text-gray-700")
        F.bloc_ordre = bloc_ordre

        def demander_numero(c, oui):
            if not oui:
                edition.regler_par_numero(c, False); F.page_infos.refresh(); return
            ch = edition.changeraient(c)
            an_ = (rapport.lire_bc(c).get("analyses") or {})
            exp_ = [n for n in ch if str(n) in ((an_.get("expert") or {}).get("donnes") or {})]
            if not exp_:
                F.appliquer_numero_(c); return
            F.numero_texte.text = (f"{len(ch)} donne{'s' if len(ch) > 1 else ''} change{'nt' if len(ch) > 1 else ''} de donneur ou de "
                                 f"vulnérabilité, dont {len(exp_)} avec une analyse de l'expert (donne{'s' if len(exp_) > 1 else ''} "
                                 f"{', '.join(map(str, exp_))}). Son texte reste, marqué « à revoir » ; l'analyse du coach se refait "
                                 "(Analyse, « Lancer l'analyse »).")
            F.numero_c["c"] = c; F.numero_d.open()
        F.demander_numero = demander_numero

        def appliquer_numero_(c):
            F.numero_d.close()
            ch = edition.regler_par_numero(c, True)
            ui.notify(f"Donneur et vulnérabilité selon le numéro : {len(ch)} donne{'s' if len(ch) > 1 else ''} changée{'s' if len(ch) > 1 else ''}."
                      if ch else "Donneur et vulnérabilité selon le numéro : aucune donne ne change.")
            F.page_infos.refresh(); F.vue_seance.refresh(); F.vue_analyse.refresh(); F.barre_seance.refresh()
        F.appliquer_numero_ = appliquer_numero_

        def enregistrer_brouillon(nom, titre):
            try:
                c = brouillon.enregistrer_sous(nom, titre)
            except ValueError as ex:
                F.infos_ui["faute"] = str(ex); F.page_infos.refresh(); return
            F.infos_ui.update(copie=False, faute=""); F.page_infos.refresh()   # le formulaire se ferme, plus d'ancien message
            F.vider_apres["c"] = c; F.vider_apres_d.open()
        F.enregistrer_brouillon = enregistrer_brouillon

        def vider_brouillon_(ouvrir_c=None):
            F.vider_d_b.close(); F.vider_apres_d.close()
            brouillon.vider(); F.badge_brouillon.refresh()
            if ouvrir_c: F.choisir(ouvrir_c); F.onglets.set_value(F.o_fichier); F.voir_page("Fichier", "infos")
            else: F.page_infos.refresh(); F.vue_seance.refresh(); F.barre_seance.refresh()
            ui.notify("Le Brouillon est vide.")
        F.vider_brouillon_ = vider_brouillon_

        @ui.refreshable
        def page_infos():
            c = F.choix["chemin"]
            if not c or not c.endswith(rapport.BC) or not os.path.isfile(c):
                F.sans_seance(); return
            try:
                data = rapport.lire_bc(c)
            except (OSError, ValueError):
                ui.label("Cette séance ne se lit pas.").classes("text-base text-red-800"); return
            s = data.get("session", {}); src = data.get("source") or {}; f = data.get("fichier") or {}
            lies_ = fichiers.lies(c); est_b = brouillon.est_brouillon(c)
            titre_in = ui.input("Titre", value=s.get("titre") or "").props("outlined").classes("w-full text-base")
            titre_in.set_visibility(not est_b)                 # le Brouillon garde son nom : on l'enregistre sous un autre
            b_titre = ui.button("Enregistrer le titre", icon="check", on_click=lambda: F.changer_titre_(c, titre_in.value)).props("outline").classes("self-start")
            b_titre.set_enabled(False); b_titre.set_visibility(not est_b)
            titre_in.on_value_change(lambda e: b_titre.set_enabled(bool(e.value.strip()) and e.value.strip() != (s.get("titre") or "")))
            prop = None if est_b else fichiers.proposer_pour(c)   # une séance d'avant les titres : titre et nom proposés
            if prop:
                with ui.column().classes("w-full gap-1 p-3").style("border-radius:10px;background:var(--bc-pique-50)"):
                    ui.label("Ce fichier date d'avant les titres. Bridge Coach propose :").classes("text-base")
                    ui.html(f"le titre <b>{html_.escape(prop[0])}</b><br/>et le nom <b>{html_.escape(prop[1])}.bc.json</b>",
                            sanitize=False).classes("text-base")
                    ui.button("Utiliser ces propositions", icon="auto_fix_high", on_click=lambda: F.adopter_(c, *prop)).props("unelevated").classes("self-start mt-1")

            def bloc(nom, lignes, section=False):
                lignes = [(k, v) for k, v in lignes if v not in (None, "", [])]
                if not lignes: return
                if section: titre_section(nom)
                else: ui.label(nom).classes("text-base font-bold mt-2")
                with ui.grid(columns="170px 1fr").classes("w-full gap-x-4 gap-y-1 text-base"):   # les mêmes colonnes partout
                    for k, v in lignes:
                        ui.label(k).classes("text-gray-700"); ui.label(str(v)).classes("break-all")
            d = fichiers.date_de(data)
            cree = f.get("cree_le") or src.get("importe") or datetime.datetime.fromtimestamp(creation(c)).isoformat(timespec="seconds")

            def details():                                 # le fichier lui-même, replié en bas (l'utilisateur, 2026-11-17 : la
                with ui.expansion("Détails du fichier", icon="description").classes("w-full text-base mt-4") \
                        .props("dense header-class='text-base text-gray-700'"):                       # séance avant le fichier)
                    bloc("Le fichier", [("Nom", os.path.basename(c)), ("Dossier", os.path.dirname(c)), ("Créé le", quand_iso(cree)),
                                        ("Avec Bridge Coach", f.get("cree_avec")),
                                        ("Versions gardées", len([v for v in lies_["versions"] if v.endswith(rapport.BC)]) or ""),
                                        ("Modifié le", quand_iso(f.get("modifie_le") or datetime.datetime.fromtimestamp(os.path.getmtime(c)).isoformat(timespec="seconds")))])
                    bloc("D'où elle vient", [("Source", SOURCES.get(src.get("type"), src.get("type"))),
                                             ("Fichier d'origine", src.get("fichier") if src.get("type") not in ("entrainement", "saisie", "brouillon") else ""),
                                             ("Il était dans", os.path.dirname(src["chemin"]) if src.get("chemin") else ""),
                                             ("Daté du", quand_iso(src.get("date_fichier"))),
                                             ("Importée le", quand_iso(src.get("importe")) if src.get("type") not in ("entrainement", "saisie", "brouillon") else "")])
                    j = list(reversed(f.get("journal") or []))
                    if j:
                        ui.label("Son histoire").classes("text-base font-bold mt-2")
                        with ui.grid(columns="170px 1fr").classes("w-full gap-x-4 gap-y-1 text-base"):
                            for x in j[:20]:
                                ui.label(quand_iso(x.get("le"))).classes("text-gray-700"); ui.label(x.get("quoi", "")).classes("break-all")
            a_finir = sum(1 for x in data.get("donnes", []) if x.get("a_completer"))
            mes = moi.paires(data)
            bloc("La séance", [("Date", fichiers.date_longue(d) if d else s.get("date")), ("Heure", s.get("heure")),
                               ("Tables", s.get("tables") or "aucune : donnes non jouées"),
                               ("Mouvement", "Mitchell" if s.get("mitchell") else "Howell ou tables fixes" if s.get("tables") else ""),
                               ("Marque", moi.MARQUES.get(moi.marque(data))),
                               ("Donnes", f"{len(data.get('donnes', []))}" + (f", dont {a_finir} à compléter" if a_finir else "")),
                               ("Paires", len(data.get("paires") or {}) or ""),
                               ("Thèmes", ", ".join(s.get("themes") or [])),
                               ("Vous êtes", ("dans la paire " + ", ".join(sorted((data.get("paires") or {}).get(k, {}).get("nom") or k for k in mes)))
                                if mes else "")], section=True)
            ans = data.get("analyses") or {}
            joues = sum(1 for v in (jouer.lire_essais(base_seance(c)).get("donnes") or {}).values() if v)
            bloc("Le travail fait", [("Analyse du coach", quand_iso((ans.get("standard") or {}).get("fait_le"))),
                                     ("Analyse de l'expert", quand_iso((ans.get("expert") or {}).get("fait_le"))),
                                     ("Rapports PDF", len(lies_["pdf"]) or ""),
                                     ("Donnes rejouées", joues or "")], section=True)

            F.bloc_ordre(c, data)
            if brouillon.est_brouillon(c):                  # le Brouillon : ni renommé ni jeté ; on l'enregistre sous un nom
                titre_section("Le Brouillon")
                ui.label("Il est toujours là. Pour garder le cours que vous y avez préparé : « Enregistrer sous… » en fait une "
                         "séance datée d'aujourd'hui ; vous pouvez ensuite vider le Brouillon pour le prochain.").classes("text-base text-gray-700")
                with ui.row().classes("gap-3"):
                    ui.button("Enregistrer sous…", icon="save_as", on_click=lambda: (F.infos_ui.update(copie=True), F.page_infos.refresh())) \
                        .props("unelevated").set_enabled(bool(data.get("donnes")))
                    ui.button("Vider le Brouillon…", icon="remove_shopping_cart", on_click=lambda: F.vider_d_b.open()) \
                        .props("outline color=red").set_enabled(bool(data.get("donnes")))
                if F.infos_ui["copie"]:
                    n0, t0 = brouillon.proposer()
                    with ui.column().classes("w-full gap-2 p-3").style("border:2px solid var(--bc-pique-600);border-radius:10px;background:var(--bc-pique-50)"):
                        ui.label("Une séance avec les donnes du Brouillon et leurs analyses :").classes("text-base")
                        t_in = ui.input("Titre", value=t0).props("outlined").classes("w-full text-base")
                        n_in = ui.input("Nom du fichier", value=n0).props("outlined suffix=.bc.json").classes("w-full text-base")
                        with ui.row().classes("gap-3"):
                            ui.button("Enregistrer", icon="save", on_click=lambda: F.enregistrer_brouillon(n_in.value, t_in.value)).props("unelevated")
                            ui.button("Annuler", on_click=lambda: (F.infos_ui.update(copie=False), F.page_infos.refresh())).props("flat")
                if F.infos_ui["faute"]: ui.label(F.infos_ui["faute"]).classes("text-base text-red-800")
                details(); return
            titre_section("Le fichier")
            with ui.row().classes("items-start gap-3 w-full no-wrap"):
                nom_in = ui.input("Nom du fichier", value=fichiers.base(c)).props("outlined suffix=.bc.json").classes("grow text-base")
                ui.button("Renommer", icon="drive_file_rename_outline", on_click=lambda: F.renommer_(c, nom_in.value)).props("outline").classes("mt-2")
            ui.label("Ses rapports, ses parties jouées et ses versions gardées suivent le nouveau nom.").classes("text-base text-gray-700")
            with ui.row().classes("gap-3"):
                ui.button("Dupliquer…", icon="content_copy", on_click=lambda: (F.infos_ui.update(copie=True), F.page_infos.refresh())).props("outline")
                ui.button("Montrer dans le dossier", icon="folder_open", on_click=lambda: montrer_fichier(c)).props("outline")
                ui.button("Mettre à la corbeille…", icon="delete", on_click=lambda: F.demander_corbeille(c)).props("outline color=red")
            if F.infos_ui["copie"]:
                n0, t0 = fichiers.proposer_copie(c)
                with ui.column().classes("w-full gap-2 p-3").style("border:2px solid var(--bc-pique-600);border-radius:10px;background:var(--bc-pique-50)"):
                    ui.label("Une copie de la séance, ses analyses comprises (pas ses parties jouées ni ses rapports) :").classes("text-base")
                    t_in = ui.input("Titre de la copie", value=t0).props("outlined").classes("w-full text-base")
                    n_in = ui.input("Nom du fichier", value=n0).props("outlined suffix=.bc.json").classes("w-full text-base")
                    with ui.row().classes("gap-3"):
                        ui.button("Créer la copie", icon="content_copy", on_click=lambda: F.dupliquer_(c, n_in.value, t_in.value)).props("unelevated")
                        ui.button("Annuler", on_click=lambda: (F.infos_ui.update(copie=False), F.page_infos.refresh())).props("flat")
            if F.infos_ui["faute"]: ui.label(F.infos_ui["faute"]).classes("text-base text-red-800")
            if F.infos_ui["fait"]: ui.label(F.infos_ui["fait"]).classes("text-base text-primary")
            details()
        F.page_infos = page_infos
        F.page_infos()

    with F.panneau_fichier, ui.column().classes("w-full gap-2") as F.pages_ui["dossier"]:   # Fichier, Ouvrir le dossier de travail
        titre_page("Le dossier de travail", "fichiers")
        ui.label("Vos séances (seances), vos rapports (rapports) et les fichiers préparés pour Claude (pour-claude). "
                 "Il se change dans Réglages, Dossiers.").classes("text-base text-gray-700")
        ui.label(rapport.DONNEES).classes("text-base break-all")
        ui.button("Ouvrir le dossier de travail", icon="folder_open", on_click=lambda: ouvrir(rapport.DONNEES)).props("outline")


NOMS = ("montrer_titre", "chercher_maj", "lancer_maj", "annuler_maj", "choisir", "preparer_import", "fermer_import", "importer", "exporter_seance", "apres_changement", "changer_titre_", "renommer_", "adopter_", "dupliquer_", "sauvegarder_", "remettre_", "demander_corbeille", "mettre_a_la_corbeille", "demander_vider", "vider_corbeille_", "parcourir_i", "recu_i", "parcourir", "recu", "demarrer_donnes", "analyser_donnes", "demarrer", "rafraichir",)   # rangés dans F par fenetre.construire
