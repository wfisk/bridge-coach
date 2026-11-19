# -*- coding: utf-8 -*-
"""L'onglet Réglages.
Les noms de la page (état, fonctions de tous les modules de l'interface) sont dans F (interface.commun) :
fenetre.construire les y range à chaque ouverture de la page."""
from interface.commun import *  # noqa: F401,F403 — les outils communs et F


def panneau():
    """Le contenu de l'onglet Réglages."""
    with ui.column().classes("w-full gap-3") as F.pages_ui["affichage"]:
      titre_page("Taille du texte", "taille")
      ui.label("Toute la fenêtre change de taille : le texte, les cartes et les tableaux. « Compacte » pour un petit "
               "écran ; « Grande » pour une télévision en cours, ou si vous voyez moins bien. Le choix est gardé.") \
          .classes("text-base text-gray-700")

      def changer_taille(z):
          ecrire_etat(zoom=z); F.boutons_taille.refresh()
          if F.sur_jouer(): F.vue_jouer.refresh()            # A− A+ à côté de la table
          ui.run_javascript(f"document.documentElement.style.zoom = {z}; "
                            f"document.documentElement.style.setProperty('--zoom', {z}); window.dispatchEvent(new Event('resize'))")
      F.changer_taille = changer_taille

      @ui.refreshable
      def boutons_taille():
          with ui.row().classes("gap-3"):
              for z, nom in TAILLES:
                  ui.button(nom, on_click=lambda z=z: F.changer_taille(z)) \
                      .props("unelevated" if z == taille_texte() else "outline").classes("text-base px-4")
      F.boutons_taille = boutons_taille
      F.boutons_taille()

    with ui.column().classes("w-full gap-3") as F.pages_ui["nom"]:
      titre_page("Votre nom", "votre-table")
      ui.label("Qui utilise Bridge Coach sur cet ordinateur : choisissez votre nom tel que la FFB l'écrit, dans la liste "
               "des joueurs de vos tournois. Bridge Coach vous reconnaît ensuite par votre numéro de licence, même si "
               "votre nom est écrit autrement d'un tournoi à l'autre.").classes("text-base text-gray-700")

      def choisir_mon_nom(e):
          if e.value == SEPARATEUR: e.sender.value = lire_etat().get("mon_nom") or ""; return
          ecrire_etat(mon_nom=e.value or None); retenir_licence(e.value)
          if e.value and not moi.nom(): ecrire_etat(moi=e.value); F.vue_seance.refresh()   # « Vous êtes » vide : c'est vous
          F.choix_moi.set_options(F.options_joueurs(moi.nom()), value=moi.nom() or "")
          F.ma_licence.refresh()
      F.choisir_mon_nom = choisir_mon_nom
      F.noms_tous = {"": "Inconnu (pas de nom)"} | {x: x for x in moi.tous_les_noms(rapport.glob_seances("*" + rapport.BC))}
      if lire_etat().get("mon_nom") and lire_etat()["mon_nom"] not in F.noms_tous: F.noms_tous[lire_etat()["mon_nom"]] = lire_etat()["mon_nom"]
      ui.select(F.noms_tous, value=lire_etat().get("mon_nom") or "", with_input=True, on_change=F.choisir_mon_nom) \
          .classes("w-full").props("outlined dense")
      @ui.refreshable
      def ma_licence():
          n_ = lire_etat().get("mon_nom")
          if not n_:                              # facultatif : sans nom, l'utilisateur est « inconnu »
              ui.html("<div style='font-size:16px'>Vous êtes : <b>inconnu</b>.</div>", sanitize=False)
              ui.label("C'est facultatif. Sans nom, Bridge Coach marche aussi : vos tables ne sont simplement pas "
                       "surlignées.").classes("text-base text-gray-700"); return
          lic_ = moi.licence_de(n_)
          ui.html(f"<div style='font-size:16px'>Vous êtes <b>{html_.escape(n_)}</b>" +
                  (f", licence FFB <b>{lic_}</b>.</div>" if lic_ else ".</div>"), sanitize=False)
          if not lic_:
              ui.label("Licence inconnue : elle viendra avec le prochain tournoi Bridgemate importé où vous avez joué.") \
                  .classes("text-base text-gray-700")
          ui.label("Votre licence et les noms des joueurs restent sur cet ordinateur : rien de cela ne part chez l'expert "
                   "ni ailleurs.").classes("text-sm text-gray-600")
      F.ma_licence = ma_licence
      F.ma_licence()

    with ui.column().classes("w-full gap-5") as F.pages_ui["dossiers"]:
      titre_page("Dossiers", "reglages")
      for F.titre, F.chemin in (("Dossier de Bridgemate : les fichiers .bws, lus sans être modifiés", F.dossier),
                            ("Dossier de travail : vos séances et vos rapports", rapport.DONNEES),
                            ("Programme Bridge Coach : là où il est installé", rapport.RACINE)):
          with ui.row().classes("w-full items-center justify-between no-wrap"):
              with ui.column().classes("gap-0"):
                  ui.label(F.titre).classes("text-base")
                  ui.label(F.chemin).classes("text-base text-gray-700 break-all")
              if os.path.isdir(F.chemin):
                  ui.button("Ouvrir", on_click=lambda c=F.chemin: ouvrir(c)).props("outline").classes("shrink-0")
              else:
                  ui.label("Dossier introuvable").classes("text-base text-red-800 shrink-0")
      ui.button("Modifier les réglages", on_click=ouvrir_reglages).classes("w-full text-base py-3")
      ui.label("Après une modification : enregistrez, puis fermez et rouvrez Bridge Coach.").classes("text-base text-gray-700")

    with ui.column().classes("w-full gap-2") as F.pages_ui["systeme"]:   # Réglages, Votre système : la carte de conventions
      titre_page("Votre fiche de conventions", "systeme")
      ui.label("Votre feuille de prévisions, rangée comme celle de la FFB : ouvertures, interventions, flanc. Tout "
               "est déjà coché comme le joue Bridge Coach (SEF 2024) : changez seulement ce que votre paire joue "
               "autrement. Ce qui est écrit ici ne change pas ce que jouent les robots.").classes("text-base text-gray-700")
      # les noms : vous (« Votre nom ») et votre partenaire de la séance ouverte, s'ils sont encore vides ; l'IV à la main
      try:
          F.mien_ = lire_etat().get("mon_nom") or moi.nom()
          F.c_s = seance_active()
          F.part_ = fiche_conventions.partenaire_de(lire_seance(F.c_s), F.mien_) if (F.c_s and F.mien_) else None
          fiche_conventions.proposer_joueurs(F.mien_, F.part_)
      except Exception:
          pass
      F.fiche_ = fiche_conventions.lire()
      ui.label("Les joueurs").classes("text-lg font-bold mt-2")
      for F.n_ in (1, 2):
          with ui.row().classes("w-full no-wrap gap-3"):
              for F.k_, F.lib_, F.ex_, F.larg_ in ((f"nom{F.n_}", "Nom", "MARTIN", "grow"), (f"prenom{F.n_}", "Prénom", "Anne", "grow"),
                                           (f"classement{F.n_}", "IV (indice de valeur)", "45", "")):
                  F.z_ = ui.input(F.lib_, value=F.fiche_.get(F.k_) or "", placeholder=f"Par exemple : {F.ex_}") \
                      .props("outlined").classes(f"text-base {F.larg_}")
                  if not F.larg_: F.z_.style("width:190px")
                  F.z_.on("blur", lambda _, k=F.k_, z=F.z_: fiche_conventions.changer_entete(**{k: z.value}))
      ui.label("Le niveau de la compétition").classes("text-lg font-bold mt-2")
      F.niveau_ = ui.radio(fiche_conventions.NIVEAUX, value=F.fiche_.get("niveau") or None).props("inline").classes("text-base")
      F.niveau_.on_value_change(lambda e: fiche_conventions.changer_entete(niveau=e.value or ""))
      ui.label("Il est imprimé sur la feuille FFB. Les choix proposés sont les mêmes à tous les niveaux : le SEF 2024.") \
          .classes("text-base text-gray-700")
      # un bouton par document, chacun dit ce qu'il imprime (l'utilisateur, 2026-11-14 : un bouton pour deux
      # documents prêtait à confusion)
      with ui.column().classes("gap-2 mt-2"):
          for F.lib_, F.ic_, F.quoi_, F.dit_ in (
                  ("Feuille de prévisions", "print", "feuille", "1 page : la feuille FFB, pour la table"),
                  ("Carte de conventions complète", "print", "ffb",
                   "2 pages recto verso : toute la carte FFB SEF, les conventions non jouées rayées"),
                  ("La fiche pour mon partenaire", "handshake", "partenaire", "Pour en discuter ensemble")):
              with ui.row().classes("items-center no-wrap gap-3"):
                  ui.button(F.lib_, icon=F.ic_, on_click=lambda q=F.quoi_: F.imprimer_fiche(q)) \
                      .props("unelevated no-caps align=left").classes("text-base shrink-0").style("width:300px")
                  ui.label(F.dit_).classes("text-base text-gray-700")
      ui.button("Préremplir avec les choix standard (SEF 2024)", icon="restart_alt",
                on_click=lambda: F.remettre_fiche_d.open()).props("outline no-caps").classes("text-base")
      with ui.row().classes("items-center gap-2"):
          ui.label("à vérifier").classes("text-base").style("color:var(--bc-jaune-700)")
          ui.label(": Bridge Coach n'en est pas sûr, ou la carte FFB SEF le joue autrement ;").classes("text-base text-gray-700")
          ui.label("changé").classes("text-base text-primary font-bold")
          ui.label(": votre paire joue autrement que Bridge Coach.").classes("text-base text-gray-700")

      def ligne_fiche(it, rafraichir, titre=None):
          """Une ligne de la carte : Oui / Non pour une convention, un texte sinon ; « à vérifier », « changé »,
          « Revenir à Bridge Coach »."""
          cle_ = it["cle"]
          val_, _ = fiche_conventions.valeur(cle_, F.fiche_)
          with ui.row().classes("w-full items-start no-wrap gap-3 py-1").style("border-bottom:1px solid var(--bc-tapis-100)"):
              with ui.column().classes("gap-0 shrink-0").style("width:240px"):
                  ui.html(rouge(html_.escape(titre or it["titre"])), sanitize=False).classes("text-base font-bold pt-2")
                  if it["desc"]:
                      ui.html(rouge(html_.escape(it["desc"])), sanitize=False).classes("text-base text-gray-700")
              with ui.column().classes("grow gap-0"):
                  sens = libre = autre_cb = None; cases_ = []
                  if it["type"] == "cases":           # plusieurs cases à la fois (les texas, le flanc…)
                      libre_v = fiche_conventions.libre_de(cle_, F.fiche_)
                      with ui.row().classes("items-center gap-4"):
                          for o_, _ in it["options"]:
                              cases_.append((o_, ui.checkbox(o_, value=o_ in val_).classes("text-base")))
                          if it.get("autre"):
                              autre_cb = ui.checkbox(AUTRE_FICHE, value=bool(libre_v)).classes("text-base")
                      if it.get("autre"):
                          sens = ui.html("", sanitize=False).classes("text-base text-gray-700")
                          libre = ui.textarea(value=libre_v, placeholder="Ce que vous jouez") \
                              .props("outlined dense rows=2").classes("w-full text-base")
                          libre.set_visibility(bool(libre_v))
                      zone = None
                  elif it["type"] == "oui":
                      zone = ui.toggle({True: "Oui", False: "Non"}, value=val_) \
                          .props("no-caps toggle-color=primary").classes("text-base mt-1")
                  elif it["type"] == "choix":
                      # un choix, le standard déjà coché ; « Autre… » pour écrire le sien (l'utilisateur, 2026-11-14)
                      libelles = dict(it["options"])
                      zone = ui.radio([l for l, _ in it["options"]] + [AUTRE_FICHE],
                                      value=val_ if val_ in libelles else AUTRE_FICHE) \
                          .props("inline").classes("text-base")
                      sens = ui.html("", sanitize=False).classes("text-base text-gray-700")
                      libre = ui.textarea(value="" if val_ in libelles else val_,
                                          placeholder="Ce que vous jouez") \
                          .props("outlined dense rows=2").classes("w-full text-base")
                  else:
                      # pas d'autogrow : dans une section repliée, la hauteur se mesure à zéro et le texte est coupé
                      zone = ui.textarea(value=val_).props(f"outlined dense rows={max(1, -(-len(val_) // 38))}") \
                          .classes("w-full text-base")
                  with ui.row().classes("items-center gap-2"):
                      av = ui.label("à vérifier").classes("text-base").style("color:var(--bc-jaune-700)") \
                          .tooltip(fiche_conventions.POURQUOI.get(it["incertain"], ""))
                      ch = ui.label("changé").classes("text-base text-primary font-bold") \
                          .tooltip("Bridge Coach : " + (fiche_conventions.texte(cle_, defaut=True) or
                                                        fiche_conventions.RIEN))
                      rt = ui.button("Revenir à Bridge Coach", icon="undo").props("flat dense no-caps")
              def montrer(cle=cle_, av=av, ch=ch, rt=rt):
                  x_ = fiche_conventions.lire()
                  c_ = fiche_conventions.valeur(cle, x_)[1]
                  av.set_visibility(bool(fiche_conventions.a_verifier(cle, x_))); ch.set_visibility(c_); rt.set_visibility(c_)
                  rafraichir()
              def expliquer(it=it, z=zone, sens=sens, libre=libre, cs=cases_, acb=autre_cb):
                  """Sous un choix : ce qu'il veut dire sur la carte ; la zone à écrire pour « Autre… »."""
                  if sens is None: return
                  if it["type"] == "cases":                 # le sens de chaque case cochée
                      d_ = dict(it["options"])
                      t_ = [f"<b>{html_.escape(o)}</b> : {html_.escape(d_[o])}" for o, b in cs if b.value and d_[o] != o]
                      sens.set_content(rouge("<br/>".join(t_))); sens.set_visibility(bool(t_))
                      libre.set_visibility(bool(acb and acb.value)); return
                  t_ = dict(it["options"]).get(z.value, "")
                  sens.set_content(rouge(html_.escape(t_)) if t_ and t_ != z.value else "")
                  sens.set_visibility(bool(t_ and t_ != z.value)); libre.set_visibility(z.value == AUTRE_FICHE)
              def revenir(cle=cle_, z=zone, d=it["defaut"], m=montrer, e_=expliquer, libre=libre, cs=cases_,
                          acb=autre_cb):
                  fiche_conventions.changer(cle, d)
                  if cs:
                      for o_, b_ in cs: b_.value = o_ in d
                      if acb is not None: acb.value = False
                  else: z.value = d
                  if libre is not None: libre.value = ""
                  e_(); m()
              def choisir(e, cle=cle_, libre=libre, m=montrer, e_=expliquer):
                  e_()
                  if e.value != AUTRE_FICHE: fiche_conventions.changer(cle, e.value); m()
                  elif (libre.value or "").strip(): fiche_conventions.changer(cle, libre.value); m()
              if it["type"] == "cases":
                  def cocher(_=None, cle=cle_, cs=cases_, acb=autre_cb, libre=libre, m=montrer, e_=expliquer):
                      v_ = [o for o, b in cs if b.value]
                      if acb is not None and acb.value and (libre.value or "").strip(): v_.append(libre.value)
                      fiche_conventions.changer(cle, v_); e_(); m()
                  for _, b_ in cases_: b_.on_value_change(cocher)
                  if autre_cb is not None:
                      autre_cb.on_value_change(cocher); libre.on("blur", cocher)
                  expliquer()
              elif it["type"] == "oui":
                  zone.on_value_change(lambda e, cle=cle_, m=montrer: (fiche_conventions.changer(cle, e.value), m()))
              elif it["type"] == "choix":
                  zone.on_value_change(choisir)
                  libre.on("blur", lambda _, cle=cle_, z=libre, m=montrer:
                           (fiche_conventions.changer(cle, z.value), m()) if (z.value or "").strip() else None)
                  expliquer()
              else:
                  zone.on("blur", lambda _, cle=cle_, z=zone, m=montrer: (fiche_conventions.changer(cle, z.value), m()))
              rt.on_click(revenir)
              av.set_visibility(bool(fiche_conventions.a_verifier(cle_, F.fiche_)))
              ch.set_visibility(fiche_conventions.valeur(cle_, F.fiche_)[1]); rt.set_visibility(ch.visible)
      F.ligne_fiche = ligne_fiche

      ui.label("Méthode de base").classes("text-lg font-bold mt-4")
      F.ligne_fiche(fiche_conventions.ITEMS["systeme"], lambda: None, "Méthode de base")
      # d'abord la feuille de prévisions de la FFB, dépliée : ses lignes, rangées comme elle (l'utilisateur, 2026-11-14)
      for F.partie_, F.groupes_ in fiche_conventions.FEUILLE:
          ui.label(F.partie_.upper()).classes("text-xl font-bold mt-6").style("color:var(--bc-coeur-600)")
          for F.sous_t, F.cles_ in F.groupes_:
              if F.sous_t:
                  ui.html(rouge(html_.escape(F.sous_t)), sanitize=False).classes("text-lg font-bold mt-3")
              for F.c_ in F.cles_:
                  F.ligne_fiche(fiche_conventions.ITEMS[F.c_], lambda: None, fiche_conventions.titre_feuille(F.c_))
      # puis le reste de la carte FFB SEF, replié : ce qu'il faut de plus pour la carte officielle
      ui.label("LE DÉTAIL DE LA CARTE FFB SEF").classes("text-xl font-bold mt-8").style("color:var(--bc-coeur-600)")
      ui.label("Ce que la carte officielle imprime en plus, déjà rempli comme le joue Bridge Coach ; ce que vous "
               "avez choisi plus haut y est repris.").classes("text-base text-gray-700")
      for F.partie_, F.nom_partie in fiche_conventions.PARTIES:      # rangé comme sur la carte FFB
          F.sections_ = [(sec_, titre_sec, fiche_conventions.reste(items_))
                       for sec_, titre_sec, col_, items_ in fiche_conventions.TOUTES if col_ == F.partie_]
          F.sections_ = [x_ for x_ in F.sections_ if x_[2]]
          if not F.sections_: continue
          ui.label(F.nom_partie).classes("text-lg font-bold mt-4")
          if F.partie_ == "ouvertures":
              ui.label("Le verso de la carte : pour chaque ouverture, les colonnes du tableau.") \
                  .classes("text-base text-gray-700")
          for F.sec_, F.titre_sec, F.items_ in F.sections_:      # tout ouvert, pas de section repliée (l'utilisateur, 2026-11-14)
              ui.html(rouge(html_.escape(F.titre_sec)), sanitize=False).classes("text-lg font-bold mt-3")
              for F.it_ in F.items_:
                  F.ligne_fiche(fiche_conventions.ITEMS[F.it_["cle"]], lambda: None)
      ui.label("Nos accords particuliers").classes("text-lg font-bold mt-4")
      F.accords_in = ui.textarea(value=F.fiche_.get("accords") or "", placeholder="Ce qui n'est pas sur la carte : une "
                               "convention à vous, une exception, un rappel…").props("outlined autogrow").classes("w-full text-base")
      F.accords_in.on("blur", lambda: fiche_conventions.changer_entete(accords=F.accords_in.value))

    with ui.column().classes("w-full gap-3") as F.pages_ui["expert"]:   # Réglages, L'expert : l'outil d'IA et le prénom
      titre_page("L'expert", "questions-expert")
      ui.label("L'expert est un outil d'intelligence artificielle, sur Internet : Claude (claude.ai) par défaut, ou un "
               "autre que vous préférez. Il écrit l'analyse de l'expert et répond à vos questions sur une donne "
               "(« Demander à l'expert », dans Jouer et Analyse).").classes("text-base text-gray-700")
      F.adresse_in = ui.input("Adresse de l'outil", value=url_expert()).props("outlined").classes("w-full text-base")
      F.adresse_in.on("blur", lambda: ecrire_etat(expert_url=F.adresse_in.value.strip() or question_expert.ADRESSE))
      ui.label("Par exemple https://claude.ai/new ou https://chatgpt.com").classes("text-sm text-gray-600")
      F.prenom_in = ui.input("Le prénom que l'expert peut employer", value=prenom_expert()).props("outlined").classes("w-full text-base")
      F.prenom_in.on("blur", lambda: ecrire_etat(expert_prenom=F.prenom_in.value.strip()))
      ui.label("L'expert vous saluera par ce prénom. C'est le seul nom qui part chez lui : les autres joueurs n'y sont "
               "que par leurs initiales. Laissez vide pour rester anonyme.").classes("text-base text-gray-700")

    with ui.column().classes("w-full gap-3") as F.pages_ui["sauvegarde"]:   # Réglages, Sauvegarder mes séances
      titre_page("Sauvegarder mes séances", "sauvegarde")
      ui.label("Un seul fichier .zip avec toutes vos séances : leurs donnes, leurs résultats, vos parties jouées et "
               "surtout les analyses de l'expert, qui ne se refont pas. Les rapports PDF n'y sont pas : ils se refont "
               "en un clic. Gardez ce fichier ailleurs que sur l'ordinateur : une clé USB, un disque, un dossier en "
               "ligne.").classes("text-base text-gray-700")
      ui.button("Sauvegarder mes séances…", icon="save", on_click=lambda: F.sauvegarder_()).props("unelevated").classes("self-start")
      @ui.refreshable
      def etat_sauvegarde():
          e = lire_etat()
          if F.sauve["faute"]: ui.label(F.sauve["faute"]).classes("text-base text-red-800")
          if F.sauve["fait"]:
              ui.label(F.sauve["fait"]).classes("text-base text-primary break-all")
              ui.button("Montrer dans le dossier", icon="folder_open", on_click=lambda: montrer_fichier(e["sauvegarde_chemin"])).props("outline")
          elif e.get("sauvegarde_le"):
              ui.label(f"Dernière sauvegarde le {quand_iso(e['sauvegarde_le'])}.").classes("text-base text-gray-700")
          else:
              ui.label("Aucune sauvegarde faite pour l'instant.").classes("text-base text-gray-700")
      F.etat_sauvegarde = etat_sauvegarde
      F.etat_sauvegarde()

    with ui.column().classes("w-full gap-3") as F.pages_ui["contact"]:   # Réglages, Un problème, une idée ?
      titre_page("Un problème, une idée ?", "signaler")
      ui.label("Bridge Coach se discute sur GitHub, le site où vit son programme. Il faut un compte GitHub, gratuit, "
               "pour écrire ; tout le monde peut lire. Écrivez en français.").classes("text-base text-gray-700")
      for F.titre_, F.texte_, F.lien_, F.icone_ in (
              ("Signaler un problème", "Quelque chose ne marche pas, un message d'erreur, un résultat faux : dites ce que "
               "vous faisiez, ce que vous attendiez et ce qui s'est passé.", GITHUB + "/issues/new", "bug_report"),
              ("Proposer une idée, poser une question, discuter", "Une amélioration, une façon de faire, une question "
               "sur le bridge ou sur le programme : les discussions sont ouvertes à tous.", GITHUB + "/discussions", "forum")):
          with ui.row().classes("w-full items-start gap-3 no-wrap p-3").style("border:2px solid var(--bc-pique-100);border-radius:10px"):
              ui.icon(F.icone_, size="26px").classes("text-primary")
              with ui.column().classes("gap-1 grow"):
                  ui.label(F.titre_).classes("text-base font-bold")
                  ui.label(F.texte_).classes("text-base text-gray-700")
                  ui.button("Ouvrir dans le navigateur", icon="open_in_new", on_click=lambda l=F.lien_: ouvrir(l)).props("outline").classes("self-start")
                  ui.label(F.lien_).classes("text-sm text-gray-600 break-all")
      ui.label(f"Donnez aussi le numéro de version : {maj.version_locale()}, et votre système "
               f"({'Windows' if sys.platform == 'win32' else 'Mac'}).").classes("text-base text-gray-700")
      @ui.refreshable
      def fichier_erreur():
          f_ = os.path.join(rapport.RAPPORTS, "derniere-erreur.txt")
          if not os.path.exists(f_):
              ui.label("Quand un calcul échoue, Bridge Coach en écrit le détail dans le fichier derniere-erreur.txt "
                       "du dossier des rapports. Il n'y en a pas pour l'instant.").classes("text-base text-gray-700"); return
          le_ = datetime.datetime.fromtimestamp(os.path.getmtime(f_)).strftime("%d/%m/%Y à %H:%M")
          ui.html(f"<b>La dernière erreur</b> (le {le_}) est dans le fichier <b>derniere-erreur.txt</b>. Joignez-le à "
                  "votre signalement : glissez-le dans la case du message sur GitHub. Il ne contient que le détail "
                  "technique de l'erreur et des noms de dossiers de votre ordinateur, pas vos séances ni les noms "
                  "des joueurs ; ouvrez-le pour le vérifier si vous voulez.", sanitize=False).classes("text-base text-gray-700")
          with ui.row().classes("gap-3"):
              ui.button("Montrer le fichier", icon="folder_open", on_click=lambda: montrer_fichier(f_)).props("outline")
              ui.button("L'ouvrir", icon="description", on_click=lambda: ouvrir(f_)).props("flat")
      F.fichier_erreur = fichier_erreur
      F.fichier_erreur()
      F.f_t = os.path.join(rapport.RAPPORTS, TEMPS)       # le temps des calculs sur cet ordinateur (2026-11-18)
      if os.path.exists(F.f_t):
          ui.html("<b>Bridge Coach vous semble lent ?</b> Il note le temps de ses calculs dans le fichier "
                  "<b>temps-de-calcul.txt</b> : seulement des durées et le type d'ordinateur, aucune main ni aucun "
                  "nom. Joignez-le à votre message, il nous aide à le rendre plus rapide.", sanitize=False) \
              .classes("text-base text-gray-700")
          with ui.row().classes("gap-3"):
              ui.button("Montrer le fichier", icon="folder_open", on_click=lambda: montrer_fichier(F.f_t)).props("outline")
              ui.button("L'ouvrir", icon="description", on_click=lambda: ouvrir(F.f_t)).props("flat")
      ui.label("N'envoyez pas vos fichiers de séance (.bc.json) sur GitHub : ils contiennent les noms complets des "
               "joueurs, et tout ce qu'on y dépose est public.").classes("text-base text-gray-700")

    if DEV:                                            # Outils de développement : principes et fondations (palette.py)
      with ui.column().classes("gap-3").style(f"width:min(1100px, calc(100vw / var(--zoom, 1) - {LARGEUR_BARRE + 64}px))") \
              as F.pages_ui["design"]:                   # plus large que les autres pages : dix nuances par ligne
        ui.label("Conception de l'interface").classes("text-lg font-bold")
        ui.html(palette.html_page(), sanitize=False)

    with ui.column().classes("w-full gap-3") as F.pages_ui["maj"]:
      titre_page("Mise à jour et nouveautés", "mise-a-jour")
      ui.label(f"Bridge Coach, version {maj.version_locale()}").classes("text-base font-bold")
      with ui.row().classes("items-center gap-3"):
          ui.button("Rechercher une mise à jour", on_click=lambda: F.chercher_maj()).props("outline")
          F.bouton_maj = ui.button("", on_click=lambda: F.lancer_maj()).props("unelevated")
          F.bouton_maj.set_visibility(False)
      F.etat_maj = ui.label("Bridge Coach ne contacte GitHub que si vous cliquez ; il n'envoie rien.").classes("text-base text-gray-700")
      F.a_maj = maj.annulable()
      if F.a_maj:                                         # juste après une mise à jour : on peut revenir en arrière, une fois
          with ui.column().classes("w-full gap-2 p-3 mt-1").style(
                  "border:1px solid var(--bc-tapis-300);border-radius:10px;background:var(--bc-tapis-50)"):
              ui.label(f"Bridge Coach est passé de la version {F.a_maj['avant']} à la {F.a_maj['apres']}. Si quelque chose ne va "
                       f"pas, vous pouvez revenir à la {F.a_maj['avant']}, telle que vous l'aviez.").classes("text-base")
              def confirmer_annulation(a_maj=F.a_maj):
                  with ui.dialog() as dlg, ui.card().classes("max-w-md"):
                      ui.label(f"Revenir à la version {a_maj['avant']} ?").classes("text-lg font-bold")
                      ui.label("Bridge Coach se ferme, remet la version d'avant et se rouvre. Vos séances, vos "
                               "rapports et vos réglages restent ; ce que la nouvelle version a ajouté peut ne "
                               "pas s'afficher dans l'ancienne.").classes("text-base")
                      with ui.row().classes("justify-end w-full gap-2"):
                          ui.button("Rester en " + a_maj["apres"], on_click=dlg.close).props("flat no-caps")
                          ui.button(f"Revenir à la {a_maj['avant']}", on_click=lambda: (dlg.close(), F.annuler_maj())) \
                              .props("unelevated no-caps")
                  dlg.open()
              F.confirmer_annulation = confirmer_annulation
              ui.button("Annuler la mise à jour", icon="undo", on_click=F.confirmer_annulation).props("outline no-caps")
      F.journal = os.path.join(rapport.RAPPORTS, maj.JOURNAL)
      if os.path.exists(F.journal):
          F.lignes_j = [x for x in open(F.journal, encoding="utf-8").read().splitlines() if x.strip()]
          if F.lignes_j:
              F.le = datetime.datetime.fromtimestamp(os.path.getmtime(F.journal)).strftime("%d/%m/%Y")   # pas « quand » : la fonction
              ui.label(f"Dernière mise à jour, le {F.le} : {F.lignes_j[0]} — {F.lignes_j[-1]}").classes("text-base text-gray-700")
      ui.label("Ce qui a changé, version par version").classes("text-base font-bold mt-4")   # les nouveautés de chaque version
      F.installee = maj.version_locale()
      for F.k_, (F.v, F.d_, F.h) in enumerate(toutes_nouveautes()):
          F.titre_v = f"Version {F.v}" + (f" · {date_en_mots(F.d_)}" if F.d_ else "") + ("  (la vôtre)" if maj.cle(F.v) == maj.cle(F.installee) else "")
          with ui.expansion(F.titre_v, value=F.k_ == 0).classes("w-full").props("dense header-class='text-base font-bold'"):
              ui.html(F.h, sanitize=False).classes("aide pb-2")


NOMS = ()
