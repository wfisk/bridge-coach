# bridge-coach

A Python program that opens a Bridgemate `.bws` file and produces a PDF report.

## Background

- `.bws` files come from Bridgemate Control Software, used to score duplicate
  bridge sessions. They are Microsoft Access (Jet) databases holding tables such
  as sections, tables, rounds, player numbers and received scores.
- The code comes from an earlier session. Build on it rather than rewriting it
  from scratch.

## Layout

    rapport.sh          the one command: ./rapport.sh [file.bws] [--sans-analyse] [--avec-noms]
                        without a file it lists the .bws in the Bridgemate folder set in bridge-coach.ini
                        (template bridge-coach.exemple.ini), newest first, ten at
                        a time; Enter picks the latest. It builds -analyse (the record of play, -archive, was dropped on
                        2026-11-09: the analysis holds the tables and results). -analyse is the program's analysis with the coach's
                        advice or, with a written analysis (and without --sans-analyse, the Rapports tab's « Inclure l'avis
                        de l'expert », etat avec_expert), Claude's analysis with the coach before the expert's advice; with a
                        written analysis also -comparaison (program and expert compared; -diff before 2026-11-09). One report since 1.4: building it removes
                        that session's old -standard, -expert and -archive PDFs, and the app lists an old -expert/-standard as the
                        session's analysis until then (rapports_de). Sorted alphabetically: analyse, comparaison
    bridge-coach.sh      opens the application (src/app.py): one window, one tab per job
    raccourci-mac.sh    creates /Applications/Bridge Coach.app and its Desktop link (a stay-open
                        AppleScript applet: a shell script in an .app is refused access to Documents, without
                        a prompt). The window's Python process leaves the Dock (src/app.py); clicking the icon
                        calls /devant to bring the window forward; the applet quits when the program ends
    installer.bat, bridge-coach.bat   the same two steps on Windows (not tried on a real PC yet). installer.bat looks for
                        Python 3.12 (then 3.13…3.9) through the py launcher, offers winget, and rebuilds a .venv made
                        with another version: endplay has no wheel for 3.14. It then makes the Desktop shortcut (cmd /c bridge-coach.bat,
                        minimised, src/icone.ico: a shortcut to a .bat cannot be pinned) and, if asked, a Start menu one to pin to the
                        taskbar by hand (Windows allows no scripted pinning). installer.sh offers raccourci-mac.sh, which offers the Dock
                        (--dock: no question; never twice). Python runs with
                        -X utf8 everywhere: Windows does not default to UTF-8, and -I ignores PYTHONUTF8
    bridge-coach.exemple.ini template of the user's bridge-coach.ini, copied on the first run
    VERSION, publier.sh  the published version; ./publier.sh 1.4 "note" runs the tests, writes VERSION, tags v1.4 and pushes.
                        Members are offered only vX.Y tags, never work in progress on main. The tag starts
                        .github/workflows/installateurs.yml (GitHub Actions): git archive -> bridge-coach-X.Y.zip, then
                        Bridge-Coach-Setup.exe (Inno Setup, windows-latest) and Bridge-Coach.pkg (pkgbuild/productbuild,
                        macos-latest), each tried by a full install into a throwaway folder, then the GitHub Release with
                        SHA256SUMS and a build-provenance attestation, notes from installer/notes-de-version.md and the tag
                        message. On main, when installer/ or requirements.txt change: the same tries, nothing published.
                        Installers are never in git (.gitignore: dist/, *.exe, *.pkg, *.dmg)
    installer/          the installers' sources. They hold no program code: each fetches the latest Release, checks
                        bridge-coach-X.Y.zip against its SHA256SUMS, then the standalone Python named in the zip's
                        installer/python.txt (python-build-standalone 3.12, sha256 per platform: changing Python needs no new
                        installer), then pip --require-hashes. windows/: bridge-coach.iss (no admin, %LOCALAPPDATA%\Programs\
                        Bridge Coach, uninstaller in .installeur/, Start menu + Desktop shortcuts) runs installer.ps1 from
                        PrepareToInstall (a failure stops before any shortcut; log %TEMP%\bridge-coach-installation.txt);
                        installer.ps1 is UTF-8 with BOM and CRLF (Windows PowerShell 5.1). mac/: a payload-free .pkg whose
                        postinstall (root) runs scripts/installer-mac.sh as the console user into ~/Library/Application
                        Support/Bridge Coach/programme (log ~/Library/Logs/Bridge Coach), then raccourci-mac.sh as root
                        (app chowned to the user). Both scripts take a local zip + SHA256SUMS for tests. Windows Setup.exe works on a
                        real PC (the user's work laptop, 2026-11-09); a club member is trying it; the Mac .pkg only on this Mac
    src/                Python code
      app.py            the NiceGUI application: one bar across the top (ui.header: the tabs, Aide; not the native bar: the window process leaves
                        the Dock, so macOS would show none). The first tab, Fichier, has a sidebar of pages like Rapports and Réglages
                        (PAGES["Fichier"], panneau_fichier; it opens on Ouvrir une séance; no more drop-down menu or dialogs, 2026-11-10):
                        Nouveau (the creation page; looking at it no longer closes the open session; three ways chosen by cards at its top,
                        saved in etat.json "page"."nouveau": Importer un tournoi Bridgemate (.bws of the Bridgemate folder, or any .bws / FFB
                        feuille de route .pdf), Importer un fichier PBN, Créer des donnes d'entraînement (themes or empty); the page says the .bws/.pbn is only read and the session is one .bc.json; the first two are the old
                        Importer page, merged in on 2026-11-11: rapport.py --importer, the .bc.json only, then it opens; .bws already
                        imported are marked; the Donnes tab offers a new .bws not yet imported; picking a file first shows a form (preparer_import,
                        formulaire_import: fichiers.proposer's title and date-first file name, editable, the name following the title until typed;
                        a file already imported is recognised by source.fichier and re-imported under its own name; then lancer_import --nom= --titre=;
                        2026-11-12)), Ouvrir une séance (the .bc.json by session date, shown by title with date, source and file name),
                        Ouvrir lists every session grouped by session month (ui.expansion; the open session's month unfolded, a year
                        heading when several years) and, folded at the bottom, the Corbeille with « Remettre » (fichiers.dans_la_corbeille,
                        remettre); Infos (page_infos: title editable, file / source / session / work done / history from the "fichier" block; Renommer,
                        Dupliquer…, Montrer dans le dossier, Mettre à la corbeille… with a confirm dialog; an older file without title or
                        date-first name gets « Utiliser ces propositions », fichiers.proposer_pour / adopter), Exporter… (exporter.py: PBN, CSV
                        or Excel, written beside the .bc.json, the session unchanged; « Avec les noms complets » off by default) and Ouvrir le dossier de travail; the open session is remembered in etat.json beside
                        bridge-coach.ini (retenir, seance_active) and named in the window title (titre_fenetre). The page open is saved too (etat.json "page": tab, sidebar entry, Standard | Expert, help section, Rapports and Réglages pages; retenir_page on every change) and reopened at start (PAGE). Fichier, Nouveau, Créer des donnes d'entraînement: "Créer une séance vide" (edited in the Donnes tab with the deal editor, editeur_donne),
                        then the theme drawing (a − / + count per kind of hand, 36 at most); either new file opens in the Donnes tab. Tabs: Donnes (opens on it) views the open
                        .bc.json with a sidebar (ui.left_drawer, light warm grey GRIS_BARRE like Claude's sidebar, the chosen entry a rounded darker pill, full height, Donnes tab only: Séance (alerts at its foot), Joueurs, a divider, one entry per deal (every tab has two entries then a divider, so Donne 1 stays in place): hands, each table's auction (encheres_html),
                        table results; vue_seance, page_donne…), view only so far. A deal page in Donnes, Analyse and Jouer has the same right sidebar (panneau_droit: fixed, LARGEUR_PANNEAU, the deal's name, a small board case, theme and par; Analyse adds the Standard | Expert toggle, the recommended contract, the lead and the double-dummy table (dm_html); Donnes the « Modifier la donne » button); Analyse: sidebar Analyse standard (status, date, "Lancer
                        l'analyse": rapport.py --analyse-seule, the analysis only, no PDF; the run block stays visible while it runs), Analyse expert
                        (status, date, and the steps to get it from Claude on the web: preparer_pour_claude writes ONE file,
                        <working folder>/pour-claude/<name>/seance-du-AAAA-MM-JJ.ai.json: "consigne" (CONSIGNE, the rules for
                        the expert analysis, in French), "seance" (seance_pour_claude: no analyses, no source, no title, players
                        by initials only: full names, club and original file name never leave the computer), "analyse_standard",
                        "exemple_analyse", "documents" (the system files); Claude returns seance-du-…-expert.json; importer_expert
                        checks it (four-column grids; each lead from the declarer's left, a card of that hand: rapport.entame_valide)
                        and merges it deal by deal into the .bc.json (the file before goes to versions/); "Aller aux rapports"
                        switches to the Rapports tab), then each deal's analysis laid out like its PDF page (page_analyse: title, diagramme_html with the lead marks of build_pdf.marques_entame and the vulnerability compass, Résultats à la table as the rank line, the recommended contract's double-dummy line and the full table folded in a ui.expansion (tableau_resultats, shared with Donnes; hearts and diamonds red through a v-html slot), the recommended auction beside its notes, expert text in the green ✦ block, plan, lead and defence, comment, cartes vues), the Expert's when it exists (toggle
                        Standard | Expert, Expert by default; page_analyse, lire_analyses); Rapports: « Vous êtes », then light options, one checkbox per thing
                        added, no help lines (the user, 2026-11-13: radios for two choices were too heavy; options_rapports, case):
                        Les donnes (« Seulement les donnes à revoir » / « Choisir les donnes », one unticks the other, choix_r per open
                        session, deal-number buttons; « Dans l'ordre où vous les avez jouées », etat ordre_joue), L'analyse (one box,
                        « Sans l'analyse du coach ni de l'expert » = facts only; unticked, the fullest analysis there is: the expert's,
                        else the coach's; etat rapport_niveau faits, anything else read as expert, niveau_rapport; the user, 2026-11-13),
                        Pages en plus (PAGES_EN_PLUS in the report's order: joueurs, champ, parcours, synthèse, then the separate
                        comparaison; etat rapport_pages); a box
                        that does not apply is greyed, unticked, the reason beside it; without « Vous êtes »: à revoir, ordre joué,
                        Vous face au champ, Votre parcours;
                        "Créer les rapports" (rapport.py --rapports + args_rapports: --niveau= --pages= --a-revoir / --donnes=; the PDFs
                        from the saved analyses; T.genre says which tab shows the progress), then the session's PDFs as links with file name and date (lien_pdf); Réglages.
                        Rapports and Réglages have a left sidebar of pages too (PAGES, vue_page, voir_page, pages_ui shown or hidden):
                        Créer les rapports | Rapports de la séance; Taille du texte | Votre nom | Dossiers | Sauvegarder mes séances
                        (fichiers.sauvegarder: one .zip of seances/ without versions/ or .bws, plus documents/; the window asks where,
                        ~/Documents by default; browser mode writes <working folder>/sauvegardes/; etat.json sauvegarde_le) | Mise à jour
                        du programme | Un problème, une idée ? (GITHUB: Issues to report a problem, Discussions for ideas and questions,
                        both enabled on wfisk/bridge-coach; shows derniere-erreur.txt with its date and « Montrer le fichier » to attach it;
                        warns never to post a .bc.json: full names, and GitHub is public). The help's same topic gives the addresses as
                        plain text (a link would open GitHub inside the app window).
                        Finished reports open the Rapports de la séance page. The left sidebar is LARGEUR_BARRE wide. Jouer (between Donnes and Analyse; Contrôle was removed): the player
                        bids one seat, the engine the three others (vue_jouer, boite_encheres; logic in jouer.py), then the
                        contract against Expert and Standard. Layout: the table on the left, a warm-neutral rounded square of fixed design size (COTE_TABLE 440px); the table, the four hands and the cards form one block that JS_AJUSTE (.ajuste) scales to fill the window, down to 0.45 or up to 2.4, growing only by real steps (6 %+) so a scrollbar appearing cannot make it shake, and never growing within the same deal at the same window size, so it doesn't swell as the hands empty (window.__echelleDonne) (2026-11-11: on a TV the cards grow, not just the table; every face-up card is one size, 55×79, in hands, dummy and trick) Every hand keeps a fixed place so nothing moves as cards are played (2026-11-13): a side hand's rows are LARGEUR_LIGNE wide (six cards), left-aligned, a longer suit overlapping more (serrer: --marge, .serre smaller figures), also dummy's side rows; a top or bottom hand keeps the width of thirteen cards (LARGEUR_MAIN, _GRANDE), from the left; a side's kept-trick row appears with its first trick (no « 0 »). (no name plates: the board case in the centre, bidding
                        cards, trick cards and dummy on it, the players' hands outside; the thinking player's name blinks on the case; hands as overlapping
                        cards drawn in CSS, CSS_CARTES, suits ♠ ♥ ♣ ♦ with a gap; dummy laid out as at the table: one column per suit, highest card on top, trumps on the left (mort_etale); the
                        trick as cards on the table just in front of each player, BORD_PLI px from that edge beyond the kept tricks (pli_cartes, ICI_PLI), dummy's beside dummy's own cards on the centre side (mort_etale posee), the same in the replay; since 2026-11-13 the four trick cards, dummy's too, form one tight cross (pli_cartes, CROIX_DX/DY ±60/±50 px), centred half-way between the bottom of dummy's longest column at the start of the deal and your kept tricks when dummy is spread at the top (mirrored at the bottom; the table is then HAUT_MORT 100 px taller than wide, 140 before 2026-11-13) and moved away from a side dummy by half the added width; dummy spread at the top or bottom has its name on one line, first name first, outside the mat above (below) the table, and its cards are centred (nom_mort, nom_html une_ligne); a ten shows as 10 on card faces (X in texts); your tricks and the defenders' turned face down on the table near each one's edge as in duplicate, each card overlapping the last, pointing to partner when won (green back), across when lost (plain light grey, not the hidden hands' back) (plis_gardes; not dummy's), with a badge at the end of every row giving that side's tricks (compte-plis: green for yours, red .autre for theirs, under a side column; their won tricks red too (.adverse); only your row and one opponent's row are drawn (rangees_plis); 2026-11-11); a card seen face up (your hand, dummy) glides from where it was to where it is after each redraw, the played card to the table and the rest closing up, all in one duration at the defenders' cards' pace (0.5–0.8 s, ease-out) (JS_GLISSE, FLIP on data-c, positions in the table's own units so a rescale moves nothing; the edge slide is dropped before measuring; positions forgotten on a new deal, data-donne; nothing flies on resize); a card from a hidden hand slides in from its player's edge like the bidding cards (pli_html, jeu["carte_arrive"]); hidden hands as a closed fan (dos); during play the board case stays on the table, small and faint, in shades of the table colour only (etui pale=True, ETUI_PALE), under the trick cards, and the sidebar shows it instead of the auction (Revoir les enchères); bids as real bidding cards (2026-11-11, from the user's photos), laid as on a real table, a quarter turn from
                        their box position: seen by the reader, bids white and wider than tall (84×50) with the big level and suit side by side (« 1♦ ») on
                        the right strip, PASS / X / XX / STOP / ALERT (printed in English, as on real cards) nearly square (56×50, the bids' height) with
                        a near-white edge, the name along the right edge (letters turned), a blank tab on the left edge (green, red,
                        blue, red, blue); no small repeated index (that is only for picking from a real box); each card shows
                        VU_CARTON px of its right strip under the next (LARGEUR_CARTON), each drawn upright
                        for the reader (.face) and laid upside down by the bidder, left to right from the bidder's own seat, each a
                        little over the last so the strip of the earlier ones shows (others read them right to left); one frame per seat
                        (.cadre, origin the row's bottom-left corner, turned 0/90/180/−90°), so a new card slides in from its own edge
                        (arrive-bas inside the frame); Stop and Alerte are not calls: on their own row in the box, and on the table to the left of
                        your row while set (a_part), never in it), the player always at the bottom, except during card play when they hold declarer and dummy
                        and bid from dummy's seat: declarer then takes the bottom and the whole table turns a half turn as
                        play starts (jeu["bas"], @keyframes tourne, TOURNE 1.4 s, continued across redraws; data-donne
                        carries the bottom seat so cards don't fly)
                        (the table and the board case turn with the seat; a hand on a side is one row per suit), the board case (etui: upright,
                        taller than wide, neutral grey; each seat's name on red if vulnerable, green if not, written to be read from
                        its own seat (sides turned, the top one upside down), names in capitals, white on red or green; the dealer's band white, « Donneur » written in red or green; the case 9:16 and light grey, North and South always on its short sides: upright when N-S sit top and bottom, lying when E-O do; the N-S bands run the full width, E-O between them) in the centre; hidden hands as small muted card backs in a closed fan; your hand a little below the table, each player's last bid clear and earlier ones lightly faded (a filter, no outline on the last one: the user's choice, 2026-11-11), every card with a small even shadow and each player's last with a deeper one, glowing when it is your turn to bid; when it is your turn to bid or play, the cards you play from glow yellow (your hand, or dummy when you play from it: .a-vous on .main-grande / .mort-table; the user rejected an underline and a pulsing outline); in card play every card of the hand you play from is clickable and none is dulled, as at the table (the user, 2026-11-11): an illegal card shakes (.carte.secoue, jeu["secoue"]) with a message and stays, and you play another (carte_jouer; no penalty card, deliberately: at the club no one imposes it, the user, 2026-11-11); .carte.terne is still drawn where a jouables set leaves cards out (Démo double mort); the sidebar during play shows the auction grid open on its white card (no small board case: it is on the table; no contract line), Indice and Réclamer only (no tricks line, no « Plis joués », no « Reprendre »: ⏮ goes to the start of the play, then of the deal, jeu_au_debut); a small green triangle on the table edge points to whoever must bid or play next, robots included (table tour=, .fleche-tour); disabled X/XX grey, the cards and the case sized so the layout fills the space, at the top of the screen; each bid pile sits mid-edge of the table, the same distance from its edge for all four players; the auction grid in the sidebar underlines each seat red or green (grille_html vul), each call's meaning opens in a bubble from the grid itself (hover, or a click keeps it: grille_html sens=, JS_SENS, .enc-sens; an alerted call carries a blue « A »; in Jouer and Démo; « Le sens des enchères » list and the alert lines under the box dropped, 2026-11-11), « Plis joués » sits in the sidebar, Indice under the bidding box, left-aligned, a right
                        sidebar (fixed, full height, LARGEUR_PANNEAU, the same grey with a thin left border) with the deal number and, beside it, an FFB-style board square (carre_donne: the number, N E S O red if
                        vulnerable or green, the dealer's side white with a border of its colour and a D, as on the board case), then the dealer and vulnerability in words (VUL_TXT),
                        the seat played (chosen in « Options », the first entry of the deal list: jouer.PLACES, jouer.siege_choisi: declarer (default), declaring side, defence, dealer, a fixed seat or random; the declarer is the recommended auction's, else the engine's; saved in etat.json as place_jouer, ecrire_etat), the auction, then the bidding box drawn as a red box (bid cards standing behind in the
                        order ♣ ♦ ♥ ♠ SA, your own last bid and every card below it gone (on the table), bids the others have overtaken in pale grey (tirette depassee, 2026-11-11), four levels, « … les autres enchères »; Passe, X, XX tabs in
                        front) or the play buttons. Jouer's sidebar starts with Options and Classement (classement.py). The sidebar entry (vue["entree"]) is shared by Donnes, Jouer and
                        Analyse: a deal chosen in one stays chosen in the others;
                        window 1200×850,
                        with Aide at the top. Rapports picks the .bws created last, runs rapport.py as a separate process
                        (never inside the server) and reads its lines ("Donne 3 sur 24", "Rapport prêt : …")
                        for the progress bar; Cancel stops the whole process group; French messages only,
                        the Python trace goes to rapports/derniere-erreur.txt. The bidding system (regles.yaml, 2–3 s to read and compile) is loaded in a background thread at startup (precharger, encheres.systeme with a lock), so the first click on Jouer does not wait. Window through pywebview,
                        browser if it is missing (--navigateur); always host 127.0.0.1 (NiceGUI would open 0.0.0.0 in browser
                        mode); port 8123, BRIDGE_COACH_PORT for a second test instance (with BRIDGE_COACH_DONNEES; the browser
                        pane cannot start it: macOS refuses it Documents, so start it from the shell). requirements.in pins the direct libraries by hand; requirements.txt is generated from it with uv
                        (universal: Windows and Mac, Python 3.9–3.13; this .venv's versions as constraints) with every
                        dependency and its SHA-256 hashes, so pip installs in hash-checking mode (needs a recent pip:
                        pip 21 rejects the socketio extra). The command is in its header.
                        Mac only so far; Windows not tested
      rapport.py        --rapports takes --niveau=faits|coach|expert (--sans-analyse = coach), --donnes=1,4,7 (chosen deals, in the
                        report's order: -donnes-1-4-7.pdf, one deal -donne-N.pdf) and --pages=champ,parcours,synthese,noms,comparaison
                        (default all but noms; --avec-noms adds it). Facts only: -releve[-a-revoir|-donnes-…].pdf, build_pdf an["faits"]
                        shows no coach or expert (no recommended row, lead or « Recommandé » column, no « Où vous pouviez faire
                        mieux »); the coach's analysis is only used to pick the deals à revoir. build_pdf an["choix"], an["pages"].
                        It also imports a source (.bws, FFB PDF, .pbn, simulated .json) into the Bridge Coach file
                        seances/AAAA-MM/<name>.bc.json (format, version, source, session, joueurs, donnes…;
                        entete, ecrire_bc; named --nom=, titled --titre=, else fichiers.proposer's; the original is NOT copied: once
                        imported, the session never needs it again, the user's choice 2026-11-12), builds the PDFs into
                        rapports/AAAA-MM/ (writes each PDF under a temporary name then swaps it in:
                        Documents is synced by a full iCloud, which kept old versions otherwise)
                        A .bc.json (or the old -donnes.json) is read as is (donnes_pretes), skipping the import. One already inside seances/ stays
                        where it is, under its own name (even with a date in it): no undated copy is made.
                        migrer(), on every start: reports/ → rapports/, <name>-donnes.json → <name>.bc.json with
                        its source and players (<name>-paires.json merged in, then removed)
      moi.py            who the user is: « Vous êtes » in the Rapports tab saves the full name in etat.json (moi.nom); moi.paires(data)
                        finds that player's pairs in a .bc.json's "joueurs"; their tables get a yellow row (SURLIGNE #fff2a8, stronger than before so it stays apart from the pale green « Recommandé » row for red-green colour blindness) in the
                        PDF results tables and summary (build_pdf.MES) and in the Donnes tab. Results tables are sorted best first from the user's side
                        (N-S when they did not play the deal; moi.ordre), with a rank line above (moi.votre_rang). The movement, when known, is
                        session.mouvement in the .bc.json (type, tables, relais, paire, tours: tour, table, donnes, adversaires,
                        relais) and paires[].position ("NS4", "EO4"); moi.parcours shows it on the Séance page and in the PDFs. A .bws import also keeps the whole movement, session.rondes (tour, table, ns, eo, donnes, from RoundData, 2026-11-10); moi.mouvement(data, mes) builds the rounds of whichever pair « Vous êtes » names from it (a hand-written session.mouvement wins when it is that pair's), and parcours, tour_de, tour_infos and ordre_des_donnes all go through it; « Vous face au champ » puts the deals you did not play last, under « Donnes non jouées »; the players page (--avec-noms) shows your pair in yellow; when both auctions show, the coach's grid comes first, then the expert's. The scoring is session.marque, "MP" or "IMP" (moi.marque, moi.MARQUES; 2026-11-10): read at import (.bws Section.ScoringType, 1 = match points, any other IMP; a PBN's [Scoring]; FFB results MP; training IMP), else guessed (MP above two tables); the Séance page's toggle corrects it (session.marque_choisie, kept on re-import, app.changer_marque). The footer and deal subtitles say it (MARQUE_TXT); « Vous face au champ » in IMP goes from 0 (datum) to your imp_ns, ±12 scale, rounds and session as totals (page_champ marque=, lignes_ensemble imp=, ligne_seance imp=); the .ai.json session carries it and CONSIGNE rule 7 asks the expert to judge for it Also holds dossier_des_reglages
                        (light: build_pdf imports it without the rest of the program)
      maj.py            updates from GitHub, standard library only: derniere_version (tags API, only on the Réglages
                        button), then a separate process (--appliquer V --attendre <app pid>) waits for the app to close,
                        downloads the tag's zip, moves the old program to .ancien-programme/, puts the new one, pip only if
                        requirements.txt changed, checks the new code imports, restores the old one on any failure, writes
                        rapports/derniere-mise-a-jour.txt and reopens the app. The zip is checked against the Release's SHA256SUMS
                        (archive_verifiee, empreinte_de); a tag with no Release assets falls back to the tag archive, unchecked.
                        Never touches .venv/.python/.installeur/.git; a Git clone is told
                        to use git pull. tests/test_maj.py applies a good and a broken version to throwaway copies
      donnes.py         creates training deals: a count per theme ("Squeeze=4" "Aléatoire=8", lire_quotas; the app's − / + list), each theme a test on a random
                        deal (THEMES: engine auction, double-dummy, coups.py or the plan's count), DELAI seconds per deal, then
                        random and says so. Writes AAAA-MM-JJ-entrainement-<themes>.bc.json (source "entrainement" or "saisie") and a .pbn for Bridgemate
                        (Control Software 3.1.2+: File, Import). Deals have no tables: their report has no results tables
                        Each theme has a family and a level (META: encheres / carte, 1 = 1re année, 2 = intermédiaire,
                        3 = avancé; new first-year themes Évaluer sa main, Soutien de la majeure, Compter ses levées, L'impasse);
                        a bidding theme and a card-play theme chosen together are combined in the same deals ("A + B",
                        combiner, test_theme; halfway through the delay the bidding theme alone is accepted, and said).
                        The app's New page: level buttons (etat "niveaux"), the two families side by side, Donnes au hasard,
                        a summary line and one button, « Créer N donnes » or « Créer une séance vide » with no theme.
                        Deals typed by hand (lire_texte / texte_de: "PRDX76C32K…T…" × 4 from North, then vulnerability
                        N-S, E-O as V/N and the dealer, "VVN"; West may be left out): donnes.py --texte only (the app types deals in the Donnes tab)
      fichiers.py       the session file itself (2026-11-12): titles and date-first names proposed at import (proposer, titre_propose:
                        « Tournoi du jeudi 5 novembre 2026 (après-midi, 7 tables) » from the .bws Session Date and Time, a PBN's
                        [Event]; nom_propose, nom_libre adds -2), the "fichier" block (nouvel_entete: cree_le, cree_avec = VERSION,
                        journal; rapport.ecrire_bc sets modifie_le and writes it first; ecrire_analyse adds a journal line), session.titre,
                        session.heure, source {type, fichier, importe, chemin, date_fichier}; lies(c): what goes with a session
                        (-jeu.json and other same-name files, versions/, its PDFs: <session date>-<nom_court>-<quoi>…, pour-claude/<file
                        name>, dossier_claude); renommer, dupliquer, corbeille (<working folder>/corbeille/<date-time>-<name>/, nothing
                        deleted). app.rapports_de lists only PDFs with this session's date. The "fichier" block never goes to Claude
                        (seance_pour_claude). tests/test_fichiers.py
      exporter.py       Fichier, Exporter…: PBN (donnes.pbn), CSV (résultats, donnes or paires; « ; », decimal comma, UTF-8 BOM for
                        French Excel), Excel .xlsx written with zipfile and XML only (no openpyxl: requirements are hash-locked and
                        members would need it; sheets Séance, Donnes, Résultats, Paires, header frozen, filters). Initials unless noms=True
      bws_extract.py    .bws -> donnes-AAAA-MM-JJ.json (prints ALERTES for broken auctions)
      pbn.py            .pbn import (rapport.py, the app's Importer): deals as in a training session (donnes.donne_complete:
                        double-dummy, points, par), source "pbn", title from [Event], date from [Date]; a deal with
                        [Contract] [Declarer] [Result] keeps one table played ([Auction] from the dealer, AP, notes skipped;
                        lead = first card of [Play]); a single missing hand (« - ») is filled in. tests/test_pbn.py
      jet4.py           pure-Python Access reader, nothing to install
      feuille_route.py  FFBClubNet "feuille de route" PDF -> session JSON (hands by position on the
                        page, contracts, leads, results; no auctions, double-dummy computed with
                        endplay; the club name is not kept); rapport.sh accepts the PDF directly.
                        FFBClubNet backups named .bws are password-protected 7z archives: not
                        readable, rapport.py says so
      build_pdf.py      donnes + analyse JSON -> PDF; when « Vous êtes » is set, a first page « Vous face au champ » (below; « La séance en un coup d'œil », page_ensemble, tried and left out)
                        (page_ensemble, lignes_ensemble): one row per deal in the report's order, a 0–100 % scale seen from
                        your side, the field as a light box plot (quartiles, median, min–max), your % as a hollow orange circle
                        (#e67700, 2.5 pt outline) and the recommended contract's % as a solid green circle (the expert's green),
                        each joined deal to deal by a solid line (broken at unplayed deals; OKLab distances orange–green 17.8+ in
                        every colour-vision type; red keeps its single meaning, a higher contract; the user's design, 2026-11-10),
                        the space between the two lines filled pale orange where you are above the recommended contract, pale green
                        where it is above you. (A dumbbell variant, style "haltere", was tried and left out.) « Vous face au champ » (page_champ, first): a bar from 50 %
                        (the field's average on each deal) to your %, red for a loss, blue for a gain (PERTE_C, GAIN_C), the gap in points
                        on the right replaced by your %, your contract and the best table's (« Meilleur », from your side: moi.ordre), the three costliest deals named under the title; grouped by round when the movement is known (moi.tour_infos, page_champ tours=): a title line per round, « Tour 1 · contre AP/EK » with your round average « moy. 48 % » in the % column, every other round on a pale band lighter than the field boxes, a relay round as one grey line « Tour 3 · relais (donnes 7–9) »; the last column is « Recommandé » (the recommended contract at its double-dummy result and what it would score at your table; « Meilleur », the best table, was dropped on 2026-11-11: it mostly shows another table's mistake); then « Où vous pouviez faire mieux » (paragraphe_couts, from src/couts.py, kept whole: on the next page when the chart fills this one): two sentences, the « Donnes à revoir » table (one row per costly part, Où / Ce qui s'est passé / Vous / Possible, deal numbers linked), your best moves, the rest; those deals get an orange dot before their number in the chart. Analyse, « Imprimer cette donne »: rapport.py --rapports --donne=N, an["seule"] in build_pdf, one deal without the
                        chart, summary or names page, <date>-<name>-donne-N.pdf, opened when ready (T.genre "imprimer"); « Rejouer
                        cette donne » opens it in Jouer. Rapports, « Seulement les donnes à revoir » (rapport.py --rapports --a-revoir, an["a_revoir"] in build_pdf.main): <date>-<name>-a-revoir-SS-AR.pdf, the chart for the whole session then only those deals, costliest first, no summary page; the full analysis is untouched (app.RAPPORTS, rapports_de); a two-line subtitle, the costliest deals on their own line; texts inside drawings go through build_pdf.chaine, which draws ♥ and ♦ in red like suits() does in paragraphs
                        (split where the lines cross: ecart_couleur); on the right your contract (pale red
                        when higher than the recommended one on the same side, pale blue when lower: sens_contrat, SENS), your %,
                        and the recommended contract (no %: the diamond shows it); a last « Séance » row: your session % (the
                        pair's official %, else the mean of your deals), the recommended contract's mean over the deals you
                        played, and the pairs' session % as the box (ligne_seance); then the deals (in the order played when the Rapports tab asks: moi.ordre_joue,
                        moi.ordre_des_donnes), each with its round line (moi.tour_de); each results table holds the
                        recommended contract as a pale green row ranked among the tables (comparer.table_recommandee: its
                        double-dummy result and score, and the % it would get against the tables, comparer.pct_face_aux_tables; no IMP; the app's Donnes tab shows it too, the expert's else the
                        standard's). Then at the end the pair's rounds (page_parcours) and, in -analyse, the summary
                        page, one line per deal: recommended contract, how many tables played it (same side, partner included),
                        higher (red), lower (blue), or let the other side play; your contract coloured the same way. Bidding
                        only, no leads, no IMP. Internal PDF links: the recommended contract goes to the deal's « Enchères
                        recommandées » (anchor reco<n>), the counts and the deal number to its « Résultats à la table » (res<n>)
      couts.py          what each deal costs you against the field (2026-11-11; the user rejected the best table and par as the
                        benchmark): bidding = the recommended contract minus yours, both double dummy (yours only when your side
                        plays the higher of the two contracts or doubled theirs: else the opponents decided); card play = your
                        contract double dummy minus your real result, as declarer or in defence, kept only when another table in
                        the same denomination and side did better or none played it (« à revoir »); the rest = other tables.
                        IMP against the datum, or % against the other tables. cout_donne, bilan (parts over SEUIL 3 IMP / 15 %,
                        your best moves; a_revoir, numeros_a_revoir). build_pdf.paragraphe_couts writes it under « Vous face au champ ». tests/test_couts.py
      commentaires.py   automatic factual comment per deal (best contracts from double-dummy, a grand slam
                        noted as rarely bid, a small slam played not called a miss, missed games/slams, tricks vs double-dummy, IMP between tables);
                        rapport.py uses it for any deal without a written `comm`, so the
                        report needs no Claude
      encheres/         offline bidding engine (stage 2: both sides bid — overcalls, take-out
                        and negative doubles, balancing, advances, law of total tricks)
        main.py         hand evaluation (H, HL, DH, shape, key cards)
        sef2024.py      SEF 2024 rules; each mirrors a line of systems/sef-2024/
        __init__.py     encherir(donne): simulates the auction for all four players (legality
                        checked), generic contract placement, Blackwood 3041
                        (chelem(): slam check before any game bid, 31+ with a fit, counted by valeur_fit: short suits count for the
                        short trump hand and when partner has shown as many trumps (5+), the long hand counts void 3, singleton 1; invitations: shape counts with an unshown fit, vulnerable
                        accept one point lighter and judge a wide range on the total with partner; from 28 with a fit shown by both, control
                        bids first: suite_controles, keys at 29+ with every suit controlled; soutien_lent, a forcing 3M, shows
                        the fit below game; avant_3sa, a cue-bid asks for their stopper before 3SA; instead of 3SA, a fit of 8+
                        in partner's minor and 29+ together bids 4 of the minor, forcing, then controls: FIT_MINEUR); contracts may be
                        doubled ("3♦X"); raises NonCouverte rather than guessing. A 4SA the player makes in Jouer, once a suit
                        has been named by both partners, is read as Blackwood 3041 for it (couleur_fixee; the robot used to pass it,
                        2026-11-12); without one it stays quantitative. The player's 5SA after their own Blackwood asks for kings outside
                        trumps (nature "rois"): partner answers by steps, 6♣ 0, 6♦ 1, 6♥ 2, 6♠ 3 (sef2024.reponse_rois), and the
                        asker bids 7 with every king, else 6 (apres_rois; the Indice says so). LENT_PUIS_CLES: after its own slow raise the engine may
                        still ask for key cards (kept, +13 IMP on 40 000 deals); DIFFERE_PAS_ETABLI (fix the trump suit with 3M
                        before control bids after a fit différé, as a club partner would read it) is off: neutral to negative
                        on 2 × 20 000 deals (systems/sef-2024/a-faire.md). The expert's CONSIGNE rule 1 now asks for auctions a
                        club partner reads the same way (agree trumps before controls; a suit bid twice shows length)
                        Benchmark: 6-table random session (seed 2026) vs Claude's analysis —
                        stage 2: 18/24 make, 10/24 par, 4.4 IMP avg (Claude 22, 19, 0.6)
      simuler.py        fake Mitchell session (N tables, invented names) from a real .bws's hands,
                        saved as JSON tables; rapport.sh accepts it like a .bws:
                        python3 -I src/simuler.py source.bws 12 sortie.json
                        New random deals (double-dummy by endplay/DDS, in .venv only;
                        auctions by the engine with ±1 point of judgement per player,
                        leads by simple French rules, tricks near double-dummy):
                        .venv/bin/python -I src/simuler.py --aleatoire 12 sortie.json [24] [seed]
      jeu.py            lead, defence and play plan without Claude, played at the table: French lead
                        rules (reading the auction: partner's suit, opponents' suits); the lead comes from
                        the rules alone, never a double-dummy simulation: an exception is a rule placed
                        higher in entames.yaml. plan_de_jeu sees only declarer, dummy, the lead and the auction: sure
                        tricks, losers on normal splits, finesses and what must be true for them (never
                        the defenders' hands). The real deal's double-dummy is only in apres_coup, added
                        to the comment. rapport.py adds them to the
                        automatic analysis for the engine's contract; its rules are written
                        in systems/sef-2024/entames.md and systems/technique/jeu-de-la-carte.md
      comparer.py       the -comparaison PDF, « Le Coach face à l'Expert »: the program (called « Coach » throughout, never
                        « Standard », 2026-11-10) vs Claude per deal, judged double-dummy, Expert always first.
                        Summary: same contract n/N and the Standard's IMP against the Expert first, par only as a
                        secondary table (par includes doubled sacrifices; a grand-slam par counts as the small slam,
                        par_pratique, shown "7♥ Sud (6♥)"). Then two tables like the summary page of
                        the reports: contracts (only where they differ; Standard red when higher than the Expert's on the
                        same side, blue when lower; each with its double-dummy result =, +1, −1; IMP the Standard
                        gains or loses against the Expert, bold when it gains), then leads (same declarer and
                        denomination, yellow when different); then auctions side by side where they differ (label and
                        Standard's contract in the same red/blue), the first differing call boxed, that player's hand,
                        the engine's reason (recomputed by encherir) and the Expert's notes
      bilan.py          a developer's tool, run by hand only (off the app and no longer built after each comparison, the
                        user's choice 2026-11-10): rapports/bilan-encheres.pdf: every session with both analyses, IMP the Coach loses by
                        session, by kind (missed slam, game too many…) and by the stage where the auctions part
                        (opening, response, rebid…), then every differing deal, costliest first:
                        .venv/bin/python -I src/bilan.py
      edition.py        sessions made in Bridge Coach (source "saisie"/"entrainement") are edited in the Donnes tab, deal by
                        deal: a deal shows as a page with "Modifier la donne" (editor; "Terminer" goes back), new or unfinished
                        deals open in the editor; a deal with an expert analysis asks first (a_analyse_expert), and changing it
                        sets that deal's expert entry aside (oublier_analyse: the file is first copied to versions/, the other deals keep theirs).
                        nouvelle_seance (« Entraînement du mardi 3 novembre 2026 », file 2026-11-03-entrainement.bc.json, -2 if
                        taken: donnes.nom_entrainement → fichiers.entrainement, themes added to title and name), ajouter_donne, poser_couleur (one suit, typed A R D V X
                        or K Q J T, saved at once), completer_au_hasard, regler (dealer, vulnerability), supprimer_donne
                        (renumbers; the standard analysis follows). Unfinished deals are saved with "a_completer"; dm, par
                        and points come once 52 cards are placed. Every save first copies the file to versions/ (at most one
                        copy per 10 minutes, 20 kept; restaurer). rapport.py leaves unfinished deals out of analysis and PDFs
      jouer.py          the Jouer tab's logic: default seat (declarer of the Expert's, else Standard's auction), legal calls,
                        avancer (encherir with imposees = the calls made, arret = the player's seat: stops there with the
                        system's call as the Indice; a call the engine would not make is read by encheres.interpreter from the
                        rule file, else as natural), comparer (contract, double-dummy result, IMP for the player against the
                        Expert / Standard, first differing call), attempts saved in <name>-jeu.json beside the session; the deal as left (seat, calls, cards played, claim) in its "en_cours" (garder_en_cours / en_cours; app: jeu_garder after every call and card, jeu_reprendre replays them; Recommencer les enchères / Reprendre le jeu de la carte reset; a seat change in Options clears them). A new bidding card slides in from its player's edge (arrive-bas/haut/gauche/droite, timed by jeu["arrive"] so redraws continue it); piles start at a fixed point so earlier cards never move. The bidding box's front row: Passe, X, XX, Stop (practice: a jump without Stop, or Stop without a jump, gets a note; saut), and Alerte placed by the player before their own artificial call (2026-11-11): jeu_annonce re-bids with the call, and when encherir marks it « alerte: oui » (regles.yaml, "alertes") without the Alerte card placed, the call is taken back with a message; the robots' alertable calls since yours are listed under the box (alertes_vues); Indice sits under the box on the left, its text just under it, and a second click hides it; Stop and Alerte sit in the box's front compartment on a second row under PASS X XX, Stop outlined in white to show on the red box (2026-11-11)
      demo.py           the Jouer tab's « Démonstration » (for a class on a big screen; app.vue_demo, mode saved in etat.json
                        mode_jouer): Demo(d, analyses) holds the recommended auction (Expert, else Coach, else the engine) with the
                        meaning of each call (encherir explications), then the robots' play at all four seats, one card at a time
                        when the teacher steps forward (calculer, carte.Partie.carte_robot, thoughts kept); position(j), dm(j)
                        (each playable card's tricks for declarer, double dummy, at any point), essayer(j, carte) (« et si… »: the
                        teacher plays another card, the robots carry on from there). Data only, no screen: a later web version
                        (students answering a quiz on their phones, the user's long-term plan) can serve the same steps.
                        All four hands open, your seat at the bottom as in Jouer and Revoir (siege_pour: the saved game, else the Options choice; declarer when unknown); dummy is never at the bottom: from the lead declarer takes it and the table turns half a turn as in Jouer (demo_bas_vu, jeu["tourne"]), kept tricks before each player as in Jouer (plis_gardes; also in vue_revoir), a void suit's symbol in pale grey everywhere, where a card's suit would sit, under an invisible rank, so it lines up with the other suits (.carte.vide, 2026-11-13); the controls (Jouer | Démo, then ⏮ ◀◀ ▶ looking exactly like Jouer's magneto: start, one step back, one step forward; during the auction only the grid on its white card
                        with the meaning bubbles (no contract, counter, Double mort or step text: the user, 2026-11-11; the Expert's notes and the
                        Double mort switch come at the end of the auction); during the play the same grid stays open (it gives the contract; no separate contract line), « Pli n · carte n », Double mort,
                        the current step's explanation) in the right sidebar; ← → and PageUp/PageDown on the keyboard
                        (demo_touche); in the play ▶ (filled) plays to the end of the trick, one card after another, and a light › one card
                        (demo_pli; in Revoir too, revoir_pli; no added pause in Démo or Revoir, pauses are for Jouer only; a finished trick in Démo stays on the table while the teacher talks about it; the next ▶ or › first ends it as in Jouer (the winning card glows 0.35 s, the four cards fly to the winner: demo_ramasser), then plays on; → the trick, Maj + → one card; the user, 2026-11-13: less clicking); during the
                        auction ▶ is one call; double-mort counts as badges on the cards' top corner (marques_dm, .carte .dm). tests/test_demo.py
      classement.py     the tournament replay scoreboard (Jouer tab, sidebar entry « Classement » under Options, 2026-11-11;
                        app.page_classement): for each deal the latest finished attempt in <name>-jeu.json (card play to the
                        last trick, "levees", or a passed-out deal; bidding alone does not count: fini, dernier_fini), the score
                        from the tricks really made (not double-dummy) seen from the seat played, then its MP % against the
                        club tables (pct_face, as comparer.pct_face_aux_tables) or IMP against their datum (session.marque);
                        the session line (mean %, or IMP total and per deal) ranked among the pairs' official results
                        (paires[].pct / .imp, else from the tables; IMP ranked per deal played), « Vous : 54,2 % — 3e sur 11
                        paires »; deals not replayed are listed, not counted (provisional ranking). The page: that line in
                        large type on yellow, a row per deal (click opens it), then the pairs with you in place. The deal list
                        marks « · jouée » (finished) or « · enchérie ». tests/test_classement.py
      carte.py          card play in the Jouer tab: Partie (coups.Position, lead from the rules, legal cards, tricks, claim
                        checked double-dummy); Partie(humain=seat): the player holds declarer and dummy, or one defender (en_defense; the
                        player then leads himself when on lead, the program plays declarer and dummy through indice() = lignes._carte and
                        partner through carte_defense; carte_robot, au_joueur). Thoughts: each robot card records Partie.pensee (seat, card, the scores of every legal card in its imagined
                        worlds from carte_defense / lignes._carte details, and its beliefs: croyance = modele.Modele.pensees from its
                        seat, kept and updated); your cards are recorded too; texte_pensee turns one into French (why this card,
                        the alternatives, what it believes); avis_programme: what the program would have played in your place.
                        The app does not show robot thoughts while you play (as at the table: the user, 2026-11-11), saves them with the deal (en_cours "pensees"), and
                        Revoir (the third mode, Jouer | Revoir | Démo at the top of the sidebar, tete_donne/mode_de; greyed out until the deal has been played to the end, donne_jouee) replays your own deal card by card (vue_revoir) with the same ⏮ ◀◀ ▶ buttons, the robots' thoughts as commentary; « Rejouer la carte » dropped (2026-11-11). Signals (carte.SIGNAUX; the user's system, 2026-11-11, written in entames.md and coded once in src/signaux.py, used to give and to read): among cards equally good in its
                        worlds, a defender signals (Partie.signal): pair-impair as its first card on partner's lead (odd: continue; even: switch, high even = the higher of the two other suits, low = the lower; 7+ high, 6- low), suit preference on discards (discard a suit you don't want, high/low for the other two), count when declarer leads, never in trumps. What it wants comes from its imagined worlds, not an honour rule (Partie.voeu: partner on lead at the start of the trick, best lead per suit double dummy). On lead, among equally good cards, it follows partner's last request (Partie.demande; pensee « suit »). The model reads the same meanings (modele.signaux_vus with the suit led, signal_plausible: the spirit on the imagined hand, EPS_SIGNAL) and its beliefs list them (« Est a fourni le ♥7, impair : il demande de continuer à ♥ ») ; carte.sens_signal words them in thoughts and the end-of-deal summary. essai_modele.banc_signaux, 240 deals against a double-dummy declarer: old
                        defence 9.59 tricks / 54 sets, model + signals 9.52 / 53: kept for the commentary and for you (signals cost
                        nothing: only among equal cards), and carte.MODELE was left off then; it is on since 2026-11-11, measured against our own declarer (essai_defense.py). analyse_jeu reviews the play double-dummy (cost of each
                        card, squeeze / mise en main / laisser-passer found or missed); resume_donne writes the end-of-deal summary
                        shown under the result. The robot declarer announces its plan with its first card (jeu.plan_de_jeu,
                        declarer's view, no simulation; pensee "plan", in the thoughts, replay and summary); at each trick it leads,
                        it plays 8 of its imagined worlds on double-dummy from the real position (coups.coups_a_venir) and says when
                        the rest passes through a squeeze or an endplay in a third of them or more (COUPS_A_VENIR). Its play already
                        follows such lines when its worlds agree; 24 worlds a card instead of 12 (MONDES_DECLARANT) gave +0.02 trick
                        and one contract in 120 deals, not kept. In defence the app draws dummy on the table at the side,
                        one row per suit overlapping like a hand, highest card toward dummy, trumps on dummy's right (mort_etale cote, table sur_table); the table is then a rectangle of the same height, wider by dummy's empty outside column (LARGEUR_TABLE_LARGE = COTE_TABLE + 84px); COTE_TABLE leaves room for a hidden hand above and yours below, so nothing shrinks at 1200×850. Defence like lignes.py from the defender's
                        seat: 16 worlds of the two hidden hands true to the auction (lire_encheres), cards played and shown voids,
                        solved double-dummy, the card that sets the contract most often (then most tricks, then the lowest). Classic habits (Partie.habitude, HABITUDES: second hand low, third hand high with the cheapest card that does, cover an honour with an honour but not the first of two touching honours led from dummy) only choose among cards the worlds rate nearly equal (same sets, at most TOLERANCE_LEVEES = 1/16 trick less a world): habits are not always right, the worlds overrule; mid-play leads take the top of a sequence (SEQUENCE). Both neutral on the bench (2 × 600 deals), kept for natural play and thoughts that name the habit. Written but off, no gain on 600 deals: more worlds on hard cards (MONDES_DIFFICILE), suit preference when giving a ruff (PREF_COUPE), the model reading touching honours (modele.LIRE_HONNEURS, phrase_honneur).
                        Bench vs a double-dummy declarer, 40 fresh deals: lead +0.23, defence +0.20 trick per deal (without the
                        auction +0.30). Indice: lignes._carte. The app adds a thinking pause to every engine call and card (reflexion: 0.9 s, 1.5 s at the 3-level or for a double, 1.9 s at game level, 2.6 s for a slam, +1.3 s when the rule's text says another call fitted too; cards 0.4 s when forced, 1.3 s to lead a trick, 0.8 s otherwise, +1.4 s when Partie.difficile: the best card beats another real choice in only a few of the imagined worlds)
      lignes.py         simulated declarer: at each card imagines 12 worlds true to the auction, lead and play,
                        solves them, keeps the card that wins most often (ties: the safe card — draw trumps, don't ruff —
                        only while the defenders may hold trumps; after that the most tricks, so dummy ruffs losers:
                        +0.14 trick a deal on 120 fresh deals, 2026-11-09); never sees the defenders' hands
                        of the deal played, defence double-dummy. analyser() runs it on 40 imagined deals: make
                        rate, order of the suits, what decides the contract (a split or a missing honour),
                        finesses taken, ruffs before trumps; plan_de_jeu follows these for its steps.
                        PARALLELE is switched on only by rapport.py (spawn re-reads the running script:
                        keep a __main__ guard); one Pool per run, falls back to plain play if it fails. Each worker
                        takes about 0.7 GB (the solver): nb_processus() leaves one core and 4 GB free
      modele.py         the model of the hidden hands, from one seat (declarer or a defender): Modele(d, seat, calls, cards played,
                        dummy). Imagined deals (known cards in place, shown voids respected, loose prefilter jeu.lire_encheres),
                        each weighted: the engine re-bids it with the real calls imposed (encherir returns "ecarts")
                        and every hidden player's call our system would not have made, passes included, multiplies the weight by
                        EPS_ENCHERE; the lead rule must give the card led (EPS_ENTAME). Draws until EFFICACE deals count. Tried
                        and dropped: a milder penalty for calls the system named as possible too, softening the weights. prediction(): H range, length distribution per suit, place of each A R D V X 9; pensees(): the same in
                        French; suite(cards): updated card by card from the same pool (0.07 s a card). carte.MODELE switches the
                        defence's imagined worlds to it: ON since 2026-11-11 (against our own simulated declarer, src/essai_defense.py, 598 fresh deals: +0.135 trick a deal ± 0.037 and 216 sets instead of 201; signals alone, without it, 0.00; against a double-dummy declarer it had shown only +0.03, since nothing can mislead or help there), about 0.2 s more a defender's card; carte.MODELE_DECLARANT feeds the simulated declarer's worlds from it (True: once after the lead; "suivi": refreshed
                        every card); off too: 240 deals against a double-dummy defence, +0.05 trick a deal, the same contracts made
                        (essai_modele.banc_declarant)
      essai_modele.py   bench of modele.py: random deals (engine auctions, random play) and the real 23/10 auctions (banc_reel),
                        Brier score of honour places, error on lengths and H, against no information and the old filter;
                        banc_defense: the same deals defended with and without the model against a double-dummy declarer
      coach.py          « Le conseil du coach », the program's own advice at the table, never the real hidden hands nor
                        double-dummy: conseil_plan (declarer's view through modele.Modele with the lead and dummy: the
                        defenders' points from the auction, each finesse of jeu.impasses with its chance from the auction
                        — take it at 65 %+, look elsewhere at 35 %-, else keep it for last —, where missing honours
                        lie, the danger hand at SA up to 3SA), conseil_defense (prose from the leader's seat after dummy: the count; don't give
                        dummy a ruff in the lead suit after the top cards; at SA keep running the long lead suit and
                        keep the entries; a race when dummy has a 4+ suit whose tops declarer's side probably holds
                        (model, 1.7+ of A K Q): switch at once to the best sequence; else trumps against ruffs, or wait),
                        conseil_encheres (the engine's close decisions; not used in the standard analysis, whose notes
                        already say « … convenait aussi »). Finesses the auction does not place are one sentence, left out
                        when the plan says the contract does not depend on a finesse (a deal stays within two pages). tests/test_coach.py
      essai_defense.py  bench of the defence against our own simulated declarer (who cannot see the hidden cards): the same fresh
                        random deals played by each variant (sans: no signals; signaux; modele = base: signals read by the hand model; then base plus habitudes, sequence, menee, lecture, difficile, coupe, tout; flags on carte or « modele.X »),
                        declarer's tricks, sets, and the gain per deal with its margin: .venv/bin/python -I -X utf8 src/essai_defense.py 600
      essai_jeu.py      bench: the simulated declarer on the real deal against double-dummy
                        (rerun after changing lignes.py; two sessions: 45 of the 52 makeable contracts; --aleatoire N for
                        fresh deals: 89 of 107, and the announced rate against the real result)
      coups.py          elimination at the table: jouer_ligne plays the strip and the plain line on
                        imagined deals (rules for declarer, double-dummy defence); the plan speaks
                        only if the strip clearly wins (jeu.cadre_elimination, phrase_elimination)
                        squeeze, end-play (mise en main), hold-up and duck found after the fact: plays
                        double-dummy lines and tests each position with the solver. Goes only in the
                        "Cartes vues" section, the last one of each deal (double-dummy of the
                        recommended contract, real finesses, coups; `vues` in the analysis)
      regles.py         reads systems/<system>/regles.yaml (bidding rules in French, T K C P,
                        ruamel.yaml): first matching rule per auction, French errors with line
                        numbers, examples checked as tests. Grammar: systems/grammaire.md.
                        The engine (encheres.encherir) asks the rule file first (openings, then
                        uncontested sequences of our side) and falls back to sef2024.py when a
                        sequence is not described. Covered so far: openings, responses to 1x,
                        1SA, 2SA, Stayman / transfer answers, opener's rebids (after 1x - 1y,
                        raises, 2-level responses, 1SA, 2SA, 3SA), responder's rebids after
                        opener's 1SA, raise, suit rebid, jump rebid or 2SA; direct overcalls
                        of 1x and 1SA; responder's bid after an overcall (raises, Spoutnik,
                        new suits, SA with a stopper), written once with relative bids (*U);
                        the overcaller's partner after a suit overcall or a take-out double;
                        balancing; after their 1x – passe – 2x, a strong hand (17+ H) doubles first, then bids its suit (+31 IMP on 20 000 random deals, 20 changed: 07/11 deal 24, 2026-11-10; leading the fit suit before partner's other suit was tried and dropped: neutral on the 348 real auctions); opener after an overcall (responder passed, or Spoutnik);
                        partner after our 1SA overcall; overcalls of weak twos and pre-empts; Drury (a passed hand's 2♣ over 1M in
                        3rd/4th seat: every rule now gets the seat, S 1-2 in a response = passed hand);
                        2♣ – 2♦ – 2♥ – 2♠ (four spades) and opener's 3♥; responder after opener's 2SA answer to the 4th suit;
                        cue-bids showing support and strength (nature cue, atout = the fit; follow-ups in
                        encheres/__init__.py: reponse_cue, reponse_cue_intervenant, apres_mon_cue).
                        Two-suited overcalls (5-5, 8–18 H, alerted; the user's scheme, 2026-11-08): over 1♣/1♦ 2♦ = majors,
                        2SA = the two lowest unbid; over 1♥/1♠ the cue-bid = clubs + other major (Michaels), 2SA = minors,
                        3♣ = diamonds + other major; advancer picks a suit by strength; +0.61 IMP a deal on 20 000 random
                        deals (331 uses) against the old natural overcalls.
                        Over a weak two (2026-11-13, deals 5, 20, 29 of 12/11, each kept on 2 × 20 000 deals, a-faire.md): balancing
                        (2x – passe – passe) has its own rules, double from 10 H; the take-out double comes before a 3-level suit with
                        four cards in the free major; a strong doubler (18+, no 5-card major) after partner's minor looks for 3SA
                        (CONTRE_FORT_3SA, avant_3sa turns it into the stopper-asking cue); the player's own cue-bid after their double
                        asks for a stopper (nature demande_arret) and the robot answers 3SA with one. Answering a take-out double with no better call, the longer minor (the « meilleure couleur » fallback had diamonds before clubs whatever their length: deal 11 of 12/11; +55 / +15 IMP, 2026-11-13). After 1x (2y) passe passe contre by opener, responder may pass for penalties (PASSE_PUNITIVE, encheres.transformer: five cards in their suit, or four with two honours, behind the overcaller; deal 18 of 12/11, +106 / +157 IMP), and an answer to a take-out double never jumps in a three-card suit (sef2024.SAUT_4_CARTES, +30 / +27 IMP). Two sections for one auction: the more specific
                        key (fewer M/N/x) wins over the generic one (regles.charger), else an error.
                        Responder after a take-out double is still the old code: a first rule
                        version (redouble, pre-emptive raise) cost 0.08 IMP on fresh deals
                        because the later rounds don't follow up those bids Keys put the opponents' calls in brackets ("1K (1P)");
                        the engine builds the same key at every turn (cle_regles). completer() adds the length a rule implies
                        without stating it (Spoutnik's free major, a repeated suit, a take-out double's majors). Check a change against the old
                        code on fresh random deals (simuler.py --aleatoire), not only the sessions
      entames.py        reads systems/<system>/entames.yaml: lead suit and card rules in the same
                        condition syntax (partenaire, adverse, sequence, honneur, tete AR,
                        longueur 4+, atouts 2+); jeu.entame_regle uses it, its old Python code
                        (entame_code) only if the file cannot be read; examples checked as tests
      essai_encheres.py test bench: python3 -I src/essai_encheres.py <name>.bc.json [deal…]
                        (contract reached, double-dummy, gap to par); rerun after any rule change
      fonts/            DejaVu fonts (macOS has none); build_pdf.py looks here first
    help/index.html     the application's help, in French, shown as a page of the window by the Aide button (top right, a blue
                        help icon; a hidden tab). Five categories, <h1 class="categorie"> (Démarrer, Revoir un tournoi, S'entraîner, Faire
                        cours, Réglages et aide: the program's three uses, the user, 2026-11-12), eleven topics, one page per <h2>,
                        written from what the user wants to do (fewer topics, longer pages, task-first, screenshots); the left
                        sidebar lists the pages under their category headings (categories_aide), a right column « Sur cette page » (sections_aide gives
                        (titre, html, [(ancre, h3)]); fixed on screen, page background, the section read is marked by JS_SUR_PAGE)
                        lists its <h3>. Numbered steps use <ol class="etapes">, tips <div class="astuce">. Screenshots in
                        help/images, served as /aide-images/ (img src="images/…"), click to enlarge. They come from
                        src/captures_aide.py: headless Chrome through CDP (websockets, already in .venv), 1200×850 at 2×, on a demo
                        folder with invented players (simuler.py --aleatoire; never real sessions: the images are public on GitHub),
                        the page chosen through etat.json « page », demo paths replaced on screen; rerun it after a screen changes
                        Contextual help (2026-11-12): every <h3> has a fixed id; app.AIDE_POUR maps (tab, page or entry, detail)
                        to a section id, like a route → help-topic table; the Aide button opens the section of the page shown
                        (cle_aide, section_aide: the most precise key first), and titre_page puts a blue « ? » beside page titles
                        (event « aide »). tests/test_app.py checks every mapped id exists.
    src/question_expert.py « Demander à l'expert » (2026-11-12): in Jouer's right sidebar (during and after a deal) and in Analyse,
                        one small .ai.json per deal in pour-claude/<file name>/donne-N[-apres].ai.json: a French instruction (be
                        « l'expert », a patient teacher; greet the player by first name and ask what they want to know), the deal,
                        auction and play, the system documents. During the deal only what the player sees (their hand, dummy after
                        the lead), never the hidden hands nor double dummy; after it everything (hands, dm, par, coach/expert
                        analyses, the tables). The app copies a one-line message (« Lis le fichier joint et suis sa consigne »),
                        shows a three-step window (Ouvrir l'expert, Montrer le fichier, coller) and opens the AI tool, adding the
                        message as ?q= for claude.ai and chatgpt.com. Réglages › L'expert: the tool's address (etat expert_url,
                        default https://claude.ai/new; also used by Analyse expert's steps) and the first name the expert may use
                        (etat expert_prenom, default the first name of « Votre nom »; the only name that leaves the computer, the
                        user's choice 2026-11-12). tests/test_question_expert.py
    src/fiche_conventions.py Réglages › Vous › « Votre système » (2026-11-12): the partnership's convention card, like a club bidding card
                        (the user, 2026-11-12: « juste oui ou non »): CONVENTIONS, 23 bidding items each Oui / Non (default = what
                        Bridge Coach plays, e.g. Stayman Oui, Landy Non); MODELE: the system line, then Entames and Signalisation
                        as short editable lines (systeme.md / entames.md written for a player). « à vérifier » where the system
                        says « à confirmer », until changed. Only what differs from Bridge Coach is kept, with the players' names and
                        « Nos accords particuliers », in <working folder>/documents/fiche-conventions.json (in the backup);
                        « Revenir à Bridge Coach » per line, « Tout remettre » for all. pdf(): one A4 page, conventions in two columns, red ♥ ♦
                        (documents/fiche-de-conventions.pdf), opened to print or send. It never changes what the robots play.
                        Linked from Jouer › Options. tests/test_fiche_conventions.py
    help/nouveautes.html the members' changelog, one <section data-version="X.Y.Z" data-date="AAAA-MM-JJ"> per version since
                        1.0, newest first, in plain French: shown once after an update (« Quoi de neuf », etat.json version_vue;
                        app.nouveautes), and all of them under the update button in Réglages › Mise à jour et nouveautés
                        (app.toutes_nouveautes; the two were combined, the user's choice 2026-11-12). Fill it in before each
                        ./publier.sh: tests/test_app.py fails when a published tag has no section
    docs/bridge-analysis/  earlier session's instructions (kept in step with the rules below) and
                        original scripts (reference)
    systems/            bidding systems: one folder per system + shared conventions/,
                        <system>/entames.md (leads, signals), technique/ (declarer play)
                        (format in systems/README.md; */ffb/ official docs are ignored by git).
                        The program doesn't read them: they are the reference Claude reads
                        to update sef2024.py and jeu.py; keep files and code in step

Three places outside this folder, none in git. `bridge-coach.ini` sits at a fixed place because it says
where the rest is: `~/Library/Application Support/Bridge Coach` on Mac, `%APPDATA%\Bridge Coach` on Windows
(`rapport.dossier_des_reglages`; `BRIDGE_COACH_DONNEES` puts everything in one folder, as in tests).
Its `[dossiers]` section gives `bridgemate`, where the .bws are read, never written (dummy here:
`~/Documents/bridgemate-files`; sub-folders are searched, the app starts on the file created last), and
`fichiers`, the user's files, `~/Documents/bridge-coach-files` by default, created on the first run:

    documents/          loose reference files, such as the style example of the analyses
    seances/AAAA-MM/    session data by month of the session (no folder per session), ignored
                        by git; the name chosen at import, the date first (2026-11-05-tournoi-jeudi-apres-midi; older
                        files keep their Bridgemate name, 1234567MULTI23102026S, until renamed in Fichier, Infos): <name>.bc.json (the session: everything the
                        reports need, and its analyses at the end, "analyses": {"standard": the program's analysis (engine
                        auctions + automatic comments; rewritten each run), "expert": written by Claude, the only part that
                        can't be recreated; wins deal by deal}, each with "fait_le"; rapport.analyse_de / ecrire_analyse;
                        written atomically, the file before copied to versions/, always before an expert change),
                        older imports have the original beside it (<name>.bws…; no longer copied), versions/ (dated copies; also the old separate
                        -standard.json / -expert.json / -expert-avant-*.json, folded in once by rapport.fondre_analyses),
                        <name>-jeu.json (the Jouer tab's attempts)
    rapports/AAAA-MM/   only the PDFs, ignored by git, with the date first: <date>-<name>-analyse.pdf (-analyse-SS-AR.pdf, the initials of the pair « Vous êtes » plays in, moi.initiales: each pair keeps its own copy, and the Rapports page lists them all as « Analyse pour SS/AR », app.rapports_de),
                        -comparaison.pdf (no spaces in names: dashes; a date already in the
                        name is not repeated and its time comes first, rapport.nom_court: 2026-11-01-224232-entrainement-comparaison.pdf)

Read `docs/bridge-analysis/PROJECT-INSTRUCTIONS.md` and
`docs/bridge-analysis/INSTRUCTIONS.md` before writing an analysis or changing the
report: the PDF is in French, uses SEF / IMP, and has fixed layout rules.
`~/Documents/bridge-coach-files/documents/exemple_analyse_2026-10-23.json` is the style reference.

For the recommended auctions, use the session's system in `systems/`
(`"systeme"` in the expert analysis, default `sef-2024`) rather than the short
system notes in the earlier instructions. Read its `systeme.md`, the conventions
it lists, its `entames.md` for leads and defence, and the official documents in its `ffb/` folder when present. Never
rely on a line marked **(à confirmer)** without saying the treatment is uncertain.

**The recommended auction is bid at the table, without hindsight.** When writing `enc`
and `notes` in an expert analysis, choose each call from that player's own hand and the
auction so far only, as a player at the table would. Do not look at the other hands, the
double-dummy table (`dm`), the par or the table results while choosing it, and do not pick
between two sound bids because one of them works double-dummy. When two calls were both
reasonable at the table, `notes` says so in a sentence starting "Décision serrée :" naming
the other call and why the chosen one was preferred.

**Card play is also played at the table.** The lead and defence (`entame`, `defense`) use only
the leader's hand and the auction, chosen by the rules in `entames.yaml`: never a double-dummy simulation.
The play plan (`plan`) uses only declarer's and dummy's cards, the lead and the auction. Never
the opponents' cards or the double-dummy, in those fields. Double-dummy appears only in `comm` and in the generated
"Cartes vues" section, after the fact, to say what the contract gives and what would have worked.
In `plan` and `defense`, the expert keeps the program's text with « Le conseil du coach » unchanged, then `<br/><b>Avis de l'expert :</b>` as a comment on the coach's advice, not another plan: one sentence saying whether the coach is right (« Le coach a raison : … », « Le coach oublie que … », « Le coach se trompe sur … »), then only what it corrects or adds (a count error, a better line, the order of play, the danger hand, the defence that beats the line, checked against its own defence advice, a hold-up, elimination, squeeze or coup); « Le coach a raison. » when nothing differs (CONSIGNE 5, since 2026-11-09). When its contract is not the program's (even one played by the other side), the expert still keeps the coach's advice (about the coach's own contract) and comments on it: what stays true, then only what changes for its own contract, in a few sentences (CONSIGNE 5; one call to Claude, the user's choice, 2026-11-10). At display time rapport.coach_pour_expert inserts the coach's text on every deal and names its contract in front (« Pour 4♥ par Nord : »). rapport.conseil_pour writes the coach's advice for any contract (about 13 s a deal); the 05/11 and 07/11 expert analyses were finished with it by hand, so their coach blocks speak about the expert's contract. When the expert's text still holds its own plan (no coach), the PDF shows it on the left under « ✦ L'expert », its avis on the right. The program's whole plan is the coach's block: coach.redaction_plan writes jeu.plan_de_jeu(parties=True) in a few sentences (« version A », the user's choice): the verdict (with the stake, or the tricks missing and the losers, ruffs and discards; a percentage only when in doubt), the plan in bridge words in playing order (coach._action), the chance left when tricks are missing (« Il faut réussir l'impasse au ♠R et trouver les ♠ 3-3 »), then what the auction says; jeu.compter_plan hands it the numbers (infos); in the expert report the program's structured copy of the plan is replaced by it (coach_pour_expert). The recommended auction's grid has a pale green header; when the expert bids differently, the coach's grid shows under it with a grey header, « ✦ L'expert » then « Le coach » under the cap (build_pdf.GRILLE reco/autre, app.grille_html qui; enc_coach, added by coach_pour_expert). `notes` is the expert's opinion on the auction. Expert texts are shown with the suit before the cards (build_pdf.couleur_devant: « AR♣ » -> « ♣AR ») and a capital first letter (majuscule). Only the expert's advice is highlighted: ✦, a pale green background and a green bar (build_pdf.AVIS, app.bloc_avis_html; purple was tried on 2026-11-09 and dropped with the coach's box: too much emphasis). « Le conseil du coach : » (MARQUE_COACH) is the program's own advice, plain text under a small cap and its bold title (src/icones/casquette.png in the PDF, app.CASQUETTE_SVG), before the expert's (decouper_avis). In the PDF (2026-11-10) plan and defence show the coach on the left and the expert on the right (avec_avis, colonne_avis), each title on its own line, the text cut at display time into short left-aligned paragraphs with an indented first line (paragraphes: NOUVEAU_PARAGRAPHE, FORCE, about two sentences each); the expert's auction notes too; « Plan de jeu » sits on a full-width light grey band (bande, BANDE); the comment and « Cartes vues » use the same short paragraphs; when no table recorded its auction, « Enchères aux tables » is one line; the section title is « Enchères recommandées » (the system is in the footer); the double-dummy results table's last column is « IMP / par », with a true minus sign; after « Entame et défense » (page, annexe pieces=True): « Commentaire sur les contrats joués » on the grey band, full width, then « Cartes vues (après coup) » on white, the double-dummy grid and par on the left beside its text (the double-dummy table of the tables was dropped: it repeated « Résultats à la table ») (the first deal, with the explanations, keeps the old layout); src/coach.py writes it into the standard analysis (rapport.encheres_auto: plan and defense), and the expert keeps it unchanged in plan and defense (CONSIGNE 5). An expert analysis written without it gets it at display time, in the expert PDF and the app's Expert view, when the expert plays the program's contract, declarer and lead (rapport.coach_pour_expert; the stored analysis is untouched). Two pages per deal is a guide, not a rule (the user, 2026-11-09): the coach is never shortened or removed to fit; build_pdf only warns. For each
contract, look for a hold-up, an elimination, a squeeze or a coup; if one fits, say so there. `tests/test_coups.py`
holds textbook positions for `coups.py`.
All three sessions now follow these rules: the 23/10 and 6-table auctions were rebid on
2026-10-30 and their card play redone on 2026-10-31 (earlier versions kept as
`-expert-avant-<date>.json`, now in `versions/`).

## Running on this Mac

System Python is 3.9, so `.venv/` pins `reportlab<4.3` (4.3+ needs 3.10).
To recreate it: `python3 -m venv .venv && .venv/bin/pip install "reportlab<4.3" pypdfium2 endplay ruamel.yaml`
(pypdfium2 reads FFB feuilles de route and renders pages to PNG for checking; endplay is the double-dummy solver, and it
imports numpy and matplotlib on load, so the install cannot drop them; checked 2026-11-09).

## Sessions with many tables

`bws_extract.construire` handles several sections (tables labelled A1, B1…) and
Mitchell movements (pair ids "3NS" / "3EO" when a number is used on both sides).
Results are linked to pairs through the round of each score. With more than two
tables: IMP against the datum plus a match-point % per result, results sorted by
score, identical table auctions grouped, and the automatic comment summarises the
field instead of one line per table. Unrecorded auctions are not alerts.

## Players

Players are identified by **initials** in reports and analyses, pair as "AB/CD" (North then South, or
East then West, at the starting table). This replaces the "no player names, pairs
by number" rule in docs/bridge-analysis. The `.bc.json` holds the players (user's decision, 2026-11-02):
`"joueurs": {pair: [{"initiales": "WF", "nom": "William Fisk", "licence": "90000001"}, …]}`, the full name optional; the FFB
licence number since 1.9 (2026-11-12: PlayerNumbers.Number of the .bws, without leading zeros, bws_extract.licence_ffb; older
Bridgemate sessions get it once at start-up from their original .bws, fichiers.ajouter_licences). moi.est / paires /
place_du_joueur recognise a player by licence first (compared without leading zeros), else by full name; etat.json
« licences » {name: licence} is filled when a name is picked (app.retenir_licence); moi.tous_les_joueurs lists each licensee
once. Réglages › Votre nom shows the licence; after the first import, « Qui utilise Bridge Coach ? » asks once (etat
qui_demande). Licences, like full names, never leave the computer (tests/test_licence.py checks the Claude files) (the .bws gives it
through `bws_extract.JOUEURS`; a feuille de route only through a `<name>-paires.json`, merged in on import; a
re-import keeps full names already there). Tables and `paires[].nom` keep the initials. The .bc.json lives in the
user's folder, never in git. Only `--avec-noms` shows full names in a report: an opening page of players
(`rapport.noms_complets`). Still no club name.

## Working notes

- Readability (the user, 2026-11-11): players are mostly seniors, and the app may be shown on a classroom TV. Content that
  changes (auctions, results tables, robots' thoughts, messages, explanations) is 15–16 px or more in dark grey (text-gray-700,
  no text-sm for it); fixed labels everyone knows (tabs, sidebars at Claude's sidebar size, buttons, a PASS card) keep
  their normal size. Results tables use short headings (N-S, E-O, Décl., Rés.) so they fit whole at 15 px.
- Réglages, « Taille du texte » (2026-11-11): Normale / Grande / Très grande = CSS zoom 1, 1.25, 1.5 on the whole page (etat.json
  "zoom", app.TAILLES, taille_texte; set in the head at load and by JS on change). Anything sized from the window must divide by
  the zoom: COTE_TABLE uses 100vw / var(--zoom), JS_AJUSTE divides innerHeight by --zoom and measures with offsetTop. Checked in
  the browser pane (Chromium), 1200×850 and 1920×1080; not yet in the pywebview window (WebKit).
- Réglages, « Votre nom » (etat.json mon_nom): the player pickers list « Aucun (tous les joueurs) », then that name
  « (vous) », a disabled line (SEPARATEUR), then everyone else A–Z (app.options_joueurs); choosing it fills an empty
  « Vous êtes ». Controls go in the right sidebar near the top or above the table, never below content (the user, 2026-11-11).
- Jouer, above the table on its own line (outils_table(d)): « Donne N », dealer and vulnerability (moved out of the right sidebar,
  the small FFB square and « Vous jouez X » dropped as repeats, 2026-11-11), then « table
  seule » (plein, basculer_plein) hides the header tabs (entete) and the left deal list (montrer_barre) but keeps the right
  sidebar (the bidding box and controls: the user's choice, for the classroom); the freed space makes JS_AJUSTE scale the table up.
- Jouer, Options, « Comme un joueur de la séance » (place_jouer "joueur", 2026-11-11): the player chosen (etat joueur_jouer, else
  « Vous êtes », else « Votre nom ») plays each deal from the seat they had (moi.place_du_joueur: their table, first of the pair
  North/East, second South/West; None when they did not play it: then the declarer's seat); « Dans l'ordre où ce joueur a joué
  les donnes » (etat ordre_joueur) sets the order of « Donne suivante » and of the Options page's « Aller à la première donne » (ordre_jouer, moi.ordre_des_donnes); the deal list stays by number (the user's choice). The four names of that table show discreetly
  by their hands, dark grey, the seat in bold capitals first (NORD…, shown for every hand even without names: nom_html siege=), then the first name and the FAMILY NAME under it (nom_html deux_lignes; beside the top and bottom hands, above the side ones, left-aligned on their cards), in Jouer, Revoir and
  Démo (jeu["noms"]); the round above the table. FFB-style coloured bands and player photos were tried and dropped (the user,
  2026-11-11: too much room, distracting). tests/test_place_joueur.py
- On screen the program's analysis is « Analyse du coach » and the Analyse toggle reads Coach | Expert (app.NOM_VERSION; the
  internal key stays "Standard" / "standard", the user, 2026-11-11).
- Jouer, the board case (etui) is drawn on the table during the bidding only, not during the card play (nor in Démo's or Revoir's play; the user, 2026-11-11):
  the compact FFB square (carre_donne, zoom .8, the words as its tooltip) starts the line above the table instead of « Donneur … ·
  Vulnérabilité … »; the Donnes/Analyse right panel keeps its small case. Clicking the last kept card opens the last trick in a
  window laid out as at the table, the winner gold (dernier_pli, emitEvent, fen_pli/contenu_pli); the table is not touched. Nothing is drawn under the table at the end of a deal
  (no result line, hands grid or comparison with the analyses: comparaison() is no longer called from Jouer).
- In Jouer's texts the software calls itself « le coach » (hints, « Qu'aurait joué le coach ? », « Le coach vérifie… »), and the
  other players are « les robots »; « le programme » stays only for the software itself (installation, updates). (the user, 2026-11-11)
- Jouer, 2026-11-11 UX round: the end of a deal shows a verdict in the sidebar (verdict: your contract against the Expert's, else the
  Coach's, double dummy and IMP; your card play against double dummy) and « Voir pourquoi » opening Revoir at your side's first card that
  cost a trick (faute_de, carte.analyse_jeu in the background; « Revoir la donne » when none). The deal list folds away while a deal is
  shown (montrer_barre, jeu["liste"], « Donnes » button on the top line). The player to move: see « Whose turn » below. At the end of a trick the winning card glows gold (.carte.gagnante), then the
  four cards move towards the player who won it, dummy included (jeu["ramasse"], .carte.vers-*); the kept trick and its side's count appear only once the cards have reached the winner, then the number in the circle rolls up (n-1 out, n in; compte_html, roule_depuis, jeu["compte_monte"] timed so a redraw continues it); the card that led is not marked (a black border, then a small arrow, were tried and dropped); dummy laid out on a side has its name under its rows. Bubbles inside the scaled table keep their
  real size (--echelle set by JS_AJUSTE). The Indice (bidding and card play) is a dotted-underlined line like a bid in the grid: hover or click opens its bubble (the meaning; in play carte.justification and the plan).
  The small square at the top turns with the table (carre-tourne, jeu["carre_bas"]/["carre_avant"]). Classement uses white cards,
  green / red for results above / below average.
- Jouer, second UX round (2026-11-11): the top line shows the small square (it turns with the table, its number and letters stay
  upright: .txt-carre, carre-contre), « Donne N », dealer and vulnerability in words, the round; no « Donnes » or full-screen button any
  more (plein stays in the code, unused). The deal list hides from a « « » icon at its top and comes back from a small « » » at the
  page's left edge (basculer_liste, etat.json liste_cachee, remembered). The bidding box stays while the robots bid, greyed
  (boite_encheres actif=False, .en-attente, only the bids already shown count). Whose turn: only your own cards glow yellow when it is your turn (your hand, or dummy when you play
  from it: .a-vous); no glow on names or on the robots' hands, no green triangle, no underline or bold (the user, 2026-11-11). Names grow back by up to a third when the table shrinks (font-size / max(--echelle, .75)). After the auction the card play
  starts by itself after 1.8 s (« Voir les mains sans jouer » stays during the pause; depart_auto, not after ◀◀ back to the auction).
  Revoir: the short reason (carte.justification) with the full thought behind « Plus », and at the costly card « Ici, ♥5 a coûté une
  levée : ♥9 la gardait » (carte.meilleure_carte, jeu["faute"]). Classement with nothing replayed offers « Commencer par la donne N ».
- Jouer, keyboard bidding (2026-11-12, encheres_clavier): a digit 1–7 then T K C P S (♣ ♦ ♥ ♠ SA), Enter = passe, X = contre,
  R = surcontre, Escape clears; the digit typed shows under the box. Start-up: a tournament in the Bridgemate folder not yet
  imported opens its import form once per file (etat bws_propose); « Ouvrir une séance » reminds to back up after 30 days
  (rappel_sauvegarde).
- Jouer, end of a deal: « Donne suivante » always opens the next deal in Jouer (jeu_suivante; picking a deal in the list keeps the mode); the deal summary
  (resume_de) shows in Revoir at the last card, not under the table; one trick count per side (rangees_plis). The result and « Donne suivante » (filled) sit in the right
  sidebar, never below the table (they were off screen); the summary, hands and comparison stay below. Robots' thoughts are not shown while
  you play.
- Jouer, top of the right sidebar (magneto): video-player controls. A deal opens waiting (jeu["attend"], kept in en_cours):
  ▶ (filled while waiting, tooltip « Commencer les enchères ») starts the robots' calls; ⏮ the start of the deal (jeu_au_debut); ◀◀ takes back your last call or card with
  what the program played after it (jeu_reculer: the auction re-asked from before your call; in the play, replayed up to your
  last card, au_joueur).

- Language: Python 3. Run Python with `-I`.
- File names use dashes and yyyy-mm-dd dates.
- Never commit `.bws` files, session JSON or generated reports: they hold
  session data. `.gitignore` covers `rapports/`, `reports/`, `seances/`, `bridge-coach.ini`, `docs/**/*.json`, `*.bws`,
  `*.pdf` and `*.zip`.
