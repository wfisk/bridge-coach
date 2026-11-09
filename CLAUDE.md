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
                        written analysis also -diff (program and expert compared). One report since 1.4: building it removes
                        that session's old -standard, -expert and -archive PDFs, and the app lists an old -expert/-standard as the
                        session's analysis until then (rapports_de). Sorted alphabetically: analyse, diff
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
      app.py            the NiceGUI application: one bar across the top (ui.header: Fichier menu, the tabs, Aide; not the native bar: the window process leaves
                        the Dock, so macOS would show none) with Ouvrir une séance (the .bc.json, by session date), Importer
                        (rapport.py --importer: the .bc.json only, then it opens; .bws already imported are marked; the Rapports
                        tab offers a new .bws not yet imported), Exporter en PBN (donnes.pbn beside the .bc.json, with
                        DoubleDummyTricks) and the working folder; the open session is remembered in etat.json beside
                        bridge-coach.ini (retenir, seance_active) and named in the window title (titre_fenetre). The page open is saved too (etat.json "page": tab, sidebar entry, Standard | Expert, help section, Rapports and Réglages pages; retenir_page on every change) and reopened at start (PAGE). Fichier, Nouveau…: closes the open session (plain title; the
                        remembered one changes only once a new file exists; « Annuler » reopens the session and page from before: avant_nouveau, annuler_nouveau), then a page (a hidden tab, like Aide): "Créer une séance vide" (edited in the Donnes tab with the deal editor, editeur_donne),
                        then the theme drawing (a − / + count per kind of hand, 36 at most); either new file opens in the Donnes tab. Tabs: Donnes (opens on it) views the open
                        .bc.json with a sidebar (ui.left_drawer, light warm grey GRIS_BARRE like Claude's sidebar, the chosen entry a rounded darker pill, full height, Donnes tab only: Séance (alerts at its foot), Joueurs, a divider, one entry per deal (every tab has two entries then a divider, so Donne 1 stays in place): hands, each table's auction (encheres_html),
                        table results; vue_seance, page_donne…), view only so far. A deal page in Donnes, Analyse and Jouer has the same right sidebar (panneau_droit: fixed, LARGEUR_PANNEAU, the deal's name, a small board case, theme and par; Analyse adds the Standard | Expert toggle, the recommended contract, the lead and the double-dummy table (dm_html); Donnes the « Modifier la donne » button); Analyse: sidebar Analyse standard (status, date, "Lancer
                        l'analyse": rapport.py --analyse-seule, the analysis only, no PDF; the run block stays visible while it runs), Analyse expert
                        (status, date, and the steps to get it from Claude on the web: preparer_pour_claude writes ONE file,
                        <working folder>/pour-claude/<name>/seance-du-AAAA-MM-JJ-pour-claude.json: "consigne" (CONSIGNE, the rules for
                        the expert analysis, in French), "seance" (seance_pour_claude: no analyses, no source, no title, players
                        by initials only: full names, club and original file name never leave the computer), "analyse_standard",
                        "exemple_analyse", "documents" (the system files); Claude returns seance-du-…-expert.json; importer_expert
                        checks it (four-column grids; each lead from the declarer's left, a card of that hand: rapport.entame_valide)
                        and merges it deal by deal into the .bc.json (the file before goes to versions/); "Aller aux rapports"
                        switches to the Rapports tab), then each deal's analysis laid out like its PDF page (page_analyse: title, diagramme_html with the lead marks of build_pdf.marques_entame and the vulnerability compass, Résultats à la table as the rank line, the recommended contract's double-dummy line and the full table folded in a ui.expansion (tableau_resultats, shared with Donnes; hearts and diamonds red through a v-html slot), the recommended auction beside its notes, expert text in the green ✦ block, plan, lead and defence, comment, cartes vues), the Expert's when it exists (toggle
                        Standard | Expert, Expert by default; page_analyse, lire_analyses); Rapports: options (« Vous êtes », played order, the
                        names page), "Créer les rapports" (rapport.py --rapports: the PDFs from the saved analyses; T.genre says which
                        tab shows the progress), then the session's PDFs and the bilan as links with file name and date (lien_pdf); Réglages.
                        Rapports and Réglages have a left sidebar of pages too (PAGES, vue_page, voir_page, pages_ui shown or hidden):
                        Créer les rapports | Rapports de la séance | Toutes les séances (the bilan); Dossiers | Mise à jour du programme.
                        Finished reports open the Rapports de la séance page. The left sidebar is LARGEUR_BARRE wide. Jouer (between Donnes and Analyse; Contrôle was removed): the player
                        bids one seat, the engine the three others (vue_jouer, boite_encheres; logic in jouer.py), then the
                        contract against Expert and Standard. Layout: the table on the left, a large warm-neutral rounded square sized to the window (COTE_TABLE: what the width and height leave, 440px at least; below that the whole table, hands and all, scales down to fit the window instead of scrolling: JS_AJUSTE, .ajuste) (no name plates: the board case in the centre, bidding
                        cards, trick cards and dummy on it, the players' hands outside; the thinking player's name blinks on the case; hands as overlapping
                        cards drawn in CSS, CSS_CARTES, suits ♠ ♥ ♣ ♦ with a gap; dummy laid out as at the table: one column per suit, highest card on top, trumps on the left (mort_etale); the
                        trick as cards on the table just in front of each player, BORD_PLI px from that edge beyond the kept tricks (pli_cartes, ICI_PLI), dummy's beside dummy's own cards on the centre side (mort_etale posee), the same in the replay; a ten shows as 10 on card faces (X in texts); your tricks and the defenders' turned face down on the table near each one's edge as in duplicate, each card overlapping the last, pointing to partner when won (green back), across when lost (grey) (plis_gardes; not dummy's), with a green badge at the end of your row giving your side's tricks (compte-plis); a card seen face up (your hand, dummy) glides from where it was to where it is after each redraw, the played card to the table and the rest closing up, all in one duration at the defenders' cards' pace (0.5–0.8 s, ease-out) (JS_GLISSE, FLIP on data-c, positions in the table's own units so a rescale moves nothing; the edge slide is dropped before measuring; positions forgotten on a new deal, data-donne; nothing flies on resize); a card from a hidden hand slides in from its player's edge like the bidding cards (pli_html, jeu["carte_arrive"]); hidden hands as a closed fan (dos); during play the board case stays on the table, small and faint, in shades of the table colour only (etui pale=True, ETUI_PALE), under the trick cards, and the sidebar shows it instead of the auction (Revoir les enchères); bids as bidding cards stacked in front of each player (yours and partner's left to right, the
                        side players' top to bottom), each label on the edge left visible,
                        bidding-box colours: SA grey, ♠ blue, ♥ red, ♦ orange, ♣ green, Passe green, X red, XX blue), the player always at the bottom
                        (the table and the board case turn with the seat; a hand on a side is one row per suit), the board case (etui: upright,
                        taller than wide, neutral grey; each seat's name on red if vulnerable, green if not, written to be read from
                        its own seat (sides turned, the top one upside down), names in capitals, white on red or green; the dealer's band white, « Donneur » written in red or green; the case 9:16 and light grey, North and South always on its short sides: upright when N-S sit top and bottom, lying when E-O do; the N-S bands run the full width, E-O between them) in the centre; hidden hands as small muted card backs in a closed fan; your hand larger, a little below the table, each player's last bid clear and earlier ones veiled, glowing when it is your turn to bid; when it is your turn to bid or play, the cards you play from glow yellow (your hand, or dummy when you play from it: .a-vous on .main-grande / .mort-table; the user rejected an underline and a pulsing outline); cards you cannot play are dull but opaque (.carte.terne: grey card and text, never transparent, since dummy's columns overlap); a small green triangle on the table edge points to whoever must bid or play next, robots included (table tour=, .fleche-tour); disabled X/XX grey, the cards and the case sized so the layout fills the space, at the top of the screen; each bid pile sits mid-edge of the table, the same distance from its edge for all four players; the auction grid in the sidebar underlines each seat red or green (grille_html vul), « Le sens des enchères » and « Plis joués » sit in the sidebar, Indice on the front of the bidding box, a right
                        sidebar (fixed, full height, LARGEUR_PANNEAU, the same grey with a thin left border) with the deal number,
                        the seat played (chosen in « Options », the first entry of the deal list: jouer.PLACES, jouer.siege_choisi: declarer (default), declaring side, defence, dealer, a fixed seat or random; the declarer is the recommended auction's, else the engine's; saved in etat.json as place_jouer, ecrire_etat), the auction, then the bidding box drawn as a red box (bid cards standing behind in the
                        order ♣ ♦ ♥ ♠ SA, only the bids still possible, four levels, « … les autres enchères »; Passe, X, XX tabs in
                        front) or the play buttons. The sidebar entry (vue["entree"]) is shared by Donnes, Jouer and
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
      rapport.py        imports a source (.bws, FFB PDF, simulated .json) into the Bridge Coach file
                        seances/AAAA-MM/<name>.bc.json (format, version, source, session, joueurs, donnes…;
                        entete, ecrire_bc), keeps a copy of the original beside it, builds the PDFs into
                        rapports/AAAA-MM/ (writes each PDF under a temporary name then swaps it in:
                        Documents is synced by a full iCloud, which kept old versions otherwise)
                        A .bc.json (or the old -donnes.json) is read as is (donnes_pretes), skipping the import. One already inside seances/ stays
                        where it is, under its own name (even with a date in it): no undated copy is made.
                        migrer(), on every start: reports/ → rapports/, <name>-donnes.json → <name>.bc.json with
                        its source and players (<name>-paires.json merged in, then removed)
      moi.py            who the user is: « Vous êtes » in the Rapports tab saves the full name in etat.json (moi.nom); moi.paires(data)
                        finds that player's pairs in a .bc.json's "joueurs"; their tables get a pale yellow row (SURLIGNE) in the
                        PDF results tables and summary (build_pdf.MES) and in the Donnes tab. Results tables are sorted best first from the user's side
                        (N-S when they did not play the deal; moi.ordre), with a rank line above (moi.votre_rang). The movement, when known, is
                        session.mouvement in the .bc.json (type, tables, relais, paire, tours: tour, table, donnes, adversaires,
                        relais) and paires[].position ("NS4", "EO4"); moi.parcours shows it on the Séance page and in the PDFs Also holds dossier_des_reglages
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
                        random and says so. Writes entrainement-<date>-<HHMMSS>.bc.json (source "entrainement" or "saisie") and a .pbn for Bridgemate
                        (Control Software 3.1.2+: File, Import). Deals have no tables: their report has no results tables
                        Each theme has a family and a level (META: encheres / carte, 1 = 1re année, 2 = intermédiaire,
                        3 = avancé; new first-year themes Évaluer sa main, Soutien de la majeure, Compter ses levées, L'impasse);
                        a bidding theme and a card-play theme chosen together are combined in the same deals ("A + B",
                        combiner, test_theme; halfway through the delay the bidding theme alone is accepted, and said).
                        The app's New page: level buttons (etat "niveaux"), the two families side by side, Donnes au hasard,
                        a summary line and one button, « Créer N donnes » or « Créer une séance vide » with no theme.
                        Deals typed by hand (lire_texte / texte_de: "PRDX76C32K…T…" × 4 from North, then vulnerability
                        N-S, E-O as V/N and the dealer, "VVN"; West may be left out): donnes.py --texte only (the app types deals in the Donnes tab)
      bws_extract.py    .bws -> donnes-AAAA-MM-JJ.json (prints ALERTES for broken auctions)
      jet4.py           pure-Python Access reader, nothing to install
      feuille_route.py  FFBClubNet "feuille de route" PDF -> session JSON (hands by position on the
                        page, contracts, leads, results; no auctions, double-dummy computed with
                        endplay; the club name is not kept); rapport.sh accepts the PDF directly.
                        FFBClubNet backups named .bws are password-protected 7z archives: not
                        readable, rapport.py says so
      build_pdf.py      donnes + analyse JSON -> PDF; deals first (in the order played when the Rapports tab asks: moi.ordre_joue,
                        moi.ordre_des_donnes), each with its round line (moi.tour_de); each results table holds the
                        recommended contract as a pale green row ranked among the tables (comparer.table_recommandee: its
                        double-dummy result and score, no IMP or %; the app's Donnes tab shows it too, the expert's else the
                        standard's). Then at the end the pair's rounds (page_parcours) and, in -analyse, the summary
                        page, one line per deal: recommended contract, how many tables played it (same side, partner included),
                        higher (red), lower (blue), or let the other side play; your contract coloured the same way. Bidding
                        only, no leads, no IMP. Internal PDF links: the recommended contract goes to the deal's « Enchères
                        recommandées » (anchor reco<n>), the counts and the deal number to its « Résultats à la table » (res<n>)
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
                        doubled ("3♦X"); raises NonCouverte rather than guessing
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
      comparer.py       the -diff PDF: program vs Claude per deal, judged double-dummy, Expert always first.
                        Summary: same contract n/N and the Standard's IMP against the Expert first, par only as a
                        secondary table (par includes doubled sacrifices; a grand-slam par counts as the small slam,
                        par_pratique, shown "7♥ Sud (6♥)"). Then two tables like the summary page of
                        the reports: contracts (only where they differ; Standard red when higher than the Expert's on the
                        same side, blue when lower; each with its double-dummy result =, +1, −1; IMP the Standard
                        gains or loses against the Expert, bold when it gains), then leads (same declarer and
                        denomination, yellow when different); then auctions side by side where they differ (label and
                        Standard's contract in the same red/blue), the first differing call boxed, that player's hand,
                        the engine's reason (recomputed by encherir) and the Expert's notes
      bilan.py          rapports/bilan-encheres.pdf: every session with both analyses, IMP the Standard loses by
                        session, by kind (missed slam, game too many…) and by the stage where the auctions part
                        (opening, response, rebid…), then every differing deal, costliest first. rapport.py reruns it
                        after each -diff
      edition.py        sessions made in Bridge Coach (source "saisie"/"entrainement") are edited in the Donnes tab, deal by
                        deal: a deal shows as a page with "Modifier la donne" (editor; "Terminer" goes back), new or unfinished
                        deals open in the editor; a deal with an expert analysis asks first (a_analyse_expert), and changing it
                        sets that deal's expert entry aside (oublier_analyse: the file is first copied to versions/, the other deals keep theirs).
                        nouvelle_seance ("Entraînement AAAA-MM-JJ", file entrainement-AAAA-MM-JJ.bc.json, time
                        added only if taken: donnes.nom_entrainement), ajouter_donne, poser_couleur (one suit, typed A R D V X
                        or K Q J T, saved at once), completer_au_hasard, regler (dealer, vulnerability), supprimer_donne
                        (renumbers; the standard analysis follows). Unfinished deals are saved with "a_completer"; dm, par
                        and points come once 52 cards are placed. Every save first copies the file to versions/ (at most one
                        copy per 10 minutes, 20 kept; restaurer). rapport.py leaves unfinished deals out of analysis and PDFs
      jouer.py          the Jouer tab's logic: default seat (declarer of the Expert's, else Standard's auction), legal calls,
                        avancer (encherir with imposees = the calls made, arret = the player's seat: stops there with the
                        system's call as the Indice; a call the engine would not make is read by encheres.interpreter from the
                        rule file, else as natural), comparer (contract, double-dummy result, IMP for the player against the
                        Expert / Standard, first differing call), attempts saved in <name>-jeu.json beside the session; the deal as left (seat, calls, cards played, claim) in its "en_cours" (garder_en_cours / en_cours; app: jeu_garder after every call and card, jeu_reprendre replays them; Recommencer les enchères / Reprendre le jeu de la carte reset; a seat change in Options clears them). A new bidding card slides in from its player's edge (arrive-bas/haut/gauche/droite, timed by jeu["arrive"] so redraws continue it); piles start at a fixed point so earlier cards never move. The bidding box's front row: Passe, X, XX, Stop (practice: a jump without Stop, or Stop without a jump, gets a note; saut), and Alerte only when partner's last call is marked « alerte: oui » in regles.yaml (alerte_due; encherir returns "alertes", jouer.avancer_alertes); Indice sits under the box, right above its text, and a second click hides it
      carte.py          card play in the Jouer tab: Partie (coups.Position, lead from the rules, legal cards, tricks, claim
                        checked double-dummy); Partie(humain=seat): the player holds declarer and dummy, or one defender (en_defense; the
                        player then leads himself when on lead, the program plays declarer and dummy through indice() = lignes._carte and
                        partner through carte_defense; carte_robot, au_joueur). Thoughts: each robot card records Partie.pensee (seat, card, the scores of every legal card in its imagined
                        worlds from carte_defense / lignes._carte details, and its beliefs: croyance = modele.Modele.pensees from its
                        seat, kept and updated); your cards are recorded too; texte_pensee turns one into French (why this card,
                        the alternatives, what it believes); avis_programme: what the program would have played in your place.
                        The app shows the last robot thought in the sidebar, saves them with the deal (en_cours "pensees"), and
                        « Revoir la donne avec les pensées » replays the deal card by card (vue_revoir). Signals (carte.SIGNAUX): among cards equally good in its
                        worlds, a defender signals (Partie.signal: attitude on partner's lead, count when declarer leads, attitude
                        on a discard; first card in the suit only; entames.md, à confirmer); the model reads partner's signals
                        (modele.signaux_vus, signal_plausible, EPS_SIGNAL). essai_modele.banc_signaux, 240 deals against a double-dummy declarer: old
                        defence 9.59 tricks / 54 sets, model + signals 9.52 / 53: kept for the commentary and for you (signals cost
                        nothing: only among equal cards), but carte.MODELE stays off. analyse_jeu reviews the play double-dummy (cost of each
                        card, squeeze / mise en main / laisser-passer found or missed); resume_donne writes the end-of-deal summary
                        shown under the result. The robot declarer announces its plan with its first card (jeu.plan_de_jeu,
                        declarer's view, no simulation; pensee "plan", in the thoughts, replay and summary); at each trick it leads,
                        it plays 8 of its imagined worlds on double-dummy from the real position (coups.coups_a_venir) and says when
                        the rest passes through a squeeze or an endplay in a third of them or more (COUPS_A_VENIR). Its play already
                        follows such lines when its worlds agree; 24 worlds a card instead of 12 (MONDES_DECLARANT) gave +0.02 trick
                        and one contract in 120 deals, not kept. In defence the app draws dummy on the table at the side,
                        one row per suit overlapping like a hand, highest card toward dummy, trumps on dummy's right (mort_etale cote, table sur_table); the table is then a rectangle of the same height, wider by dummy's empty outside column (LARGEUR_TABLE_LARGE = COTE_TABLE + 84px); COTE_TABLE leaves room for a hidden hand above and yours below, so nothing shrinks at 1200×850. Defence like lignes.py from the defender's
                        seat: 16 worlds of the two hidden hands true to the auction (lire_encheres), cards played and shown voids,
                        solved double-dummy, the card that sets the contract most often (then most tricks, then the lowest).
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
                        defence's imagined worlds to it (off: 160 deals against a double-dummy declarer, 0.03 trick a deal better, same sets); carte.MODELE_DECLARANT feeds the simulated declarer's worlds from it (True: once after the lead; "suivi": refreshed
                        every card); off too: 240 deals against a double-dummy defence, +0.05 trick a deal, the same contracts made
                        (essai_modele.banc_declarant)
      essai_modele.py   bench of modele.py: random deals (engine auctions, random play) and the real 23/10 auctions (banc_reel),
                        Brier score of honour places, error on lengths and H, against no information and the old filter;
                        banc_defense: the same deals defended with and without the model against a double-dummy declarer
      coach.py          « Le conseil du coach », the program's own advice at the table, never the real hidden hands nor
                        double-dummy: conseil_plan (declarer's view through modele.Modele with the lead and dummy: the
                        defenders' points from the auction, each finesse of jeu.impasses with its chance from the auction
                        — take it at 65 %+, look elsewhere at 35 %-, else keep it for last —, where missing honours
                        lie, the danger hand at SA up to 3SA), conseil_defense (the leader's count after dummy, then attack
                        if dummy has a long suit for discards, lead trumps if it is short with trumps, else wait),
                        conseil_encheres (the engine's close decisions; not used in the standard analysis, whose notes
                        already say « … convenait aussi »). Finesses the auction does not place are one sentence, left out
                        when the plan says the contract does not depend on a finesse (a deal stays within two pages). tests/test_coach.py
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
                        balancing; opener after an overcall (responder passed, or Spoutnik);
                        partner after our 1SA overcall; overcalls of weak twos and pre-empts; Drury (a passed hand's 2♣ over 1M in
                        3rd/4th seat: every rule now gets the seat, S 1-2 in a response = passed hand);
                        2♣ – 2♦ – 2♥ – 2♠ (four spades) and opener's 3♥; responder after opener's 2SA answer to the 4th suit;
                        cue-bids showing support and strength (nature cue, atout = the fit; follow-ups in
                        encheres/__init__.py: reponse_cue, reponse_cue_intervenant, apres_mon_cue).
                        Two-suited overcalls (5-5, 8–18 H, alerted; the user's scheme, 2026-11-08): over 1♣/1♦ 2♦ = majors,
                        2SA = the two lowest unbid; over 1♥/1♠ the cue-bid = clubs + other major (Michaels), 2SA = minors,
                        3♣ = diamonds + other major; advancer picks a suit by strength; +0.61 IMP a deal on 20 000 random
                        deals (331 uses) against the old natural overcalls. Two sections for one auction: the more specific
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
    help/index.html     the application's help, in French, shown as a page of the window by the Aide button (a hidden tab, 16px),
                        one topic at a time: five <h2> categories (Démarrer, Les séances, Jouer, Analyse et rapports, Installation et
                        réglages), each with <h3> topics; the sidebar shows each category's name above its topics (sections_aide gives
                        (catégorie, titre, html), page_aide)
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
                        by git; the original name, no date prefix (Bridgemate names already hold
                        it: 1234567MULTI23102026S = 23/10/2026): <name>.bc.json (the session: everything the
                        reports need, and its analyses at the end, "analyses": {"standard": the program's analysis (engine
                        auctions + automatic comments; rewritten each run), "expert": written by Claude, the only part that
                        can't be recreated; wins deal by deal}, each with "fait_le"; rapport.analyse_de / ecrire_analyse;
                        written atomically, the file before copied to versions/, always before an expert change),
                        the original beside it (<name>.bws, the FFB .pdf…), versions/ (dated copies; also the old separate
                        -standard.json / -expert.json / -expert-avant-*.json, folded in once by rapport.fondre_analyses),
                        <name>-jeu.json (the Jouer tab's attempts)
    rapports/AAAA-MM/   only the PDFs, ignored by git, with the date first: <date>-<name>-analyse.pdf,
                        -diff.pdf (no spaces in names: dashes; a date already in the
                        name is not repeated and its time comes first, rapport.nom_court: 2026-11-01-224232-entrainement-diff.pdf)

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
In `plan` and `defense`, the expert keeps the program's text with « Le conseil du coach » unchanged, then `<br/><b>Avis de l'expert :</b>` as a comment on the coach's advice, not another plan: one sentence saying whether the coach is right (« Le coach a raison : … », « Le coach oublie que … », « Le coach se trompe sur … »), then only what it corrects or adds (a count error, a better line, the order of play, the danger hand, the defence that beats the line, checked against its own defence advice, a hold-up, elimination, squeeze or coup); « Le coach a raison. » when nothing differs (CONSIGNE 5, since 2026-11-09). When its contract is not the program's, the coach does not speak about that deal, and the expert writes the plan itself. The program's whole plan is the coach's block: coach.redaction_plan writes jeu.plan_de_jeu(parties=True) in a few sentences (« version A », the user's choice): the verdict (with the stake, or the tricks missing and the losers, ruffs and discards; a percentage only when in doubt), the plan in bridge words in playing order (coach._action), the chance left when tricks are missing (« Il faut réussir l'impasse au ♠R et trouver les ♠ 3-3 »), then what the auction says; jeu.compter_plan hands it the numbers (infos); in the expert report the program's structured copy of the plan is replaced by it (coach_pour_expert). The auction grid's header takes the colour of whoever recommends it (build_pdf.bidding qui, app.grille_html qui): pale green the coach, pale purple the expert; when the expert bids differently, both grids show, « ✦ L'expert » then « Le coach » under the cap (enc_coach, added by coach_pour_expert). `notes` is the expert's opinion on the auction. The expert report marks all three with a ✦, a pale purple background and a purple bar (build_pdf.AVIS, VIOLET; app.bloc_avis_html); the standard report has none. « Le conseil du coach : » (MARQUE_COACH) is the program's own advice, drawn the same way in Bridge Coach's green under a small cap (src/icones/casquette.png in the PDF, app.CASQUETTE_SVG), before the expert's (decouper_avis); src/coach.py writes it into the standard analysis (rapport.encheres_auto: plan and defense), and the expert keeps it unchanged in plan and defense (CONSIGNE 5). An expert analysis written without it gets it at display time, in the expert PDF and the app's Expert view, when the expert plays the program's contract, declarer and lead (rapport.coach_pour_expert; the stored analysis is untouched). A deal that would pass two pages drops the coach's defence block, then shortens the coach's plan to its verdict, count and order of play (build_pdf.abreger_plan: the plan is the coach's, it is never removed); if that does not bring the deal back to two pages, it keeps its full coach and stays at three (build_pdf.main, fabriquer). Long expert texts already made some deals three pages before the coach (07/11 session 1). For each
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
`"joueurs": {pair: [{"initiales": "WF", "nom": "William Fisk"}, …]}`, the full name optional (the .bws gives it
through `bws_extract.JOUEURS`; a feuille de route only through a `<name>-paires.json`, merged in on import; a
re-import keeps full names already there). Tables and `paires[].nom` keep the initials. The .bc.json lives in the
user's folder, never in git. Only `--avec-noms` shows full names in a report: an opening page of players
(`rapport.noms_complets`). Still no club name.

## Working notes

- Language: Python 3. Run Python with `-I`.
- File names use dashes and yyyy-mm-dd dates.
- Never commit `.bws` files, session JSON or generated reports: they hold
  session data. `.gitignore` covers `rapports/`, `reports/`, `seances/`, `bridge-coach.ini`, `docs/**/*.json`, `*.bws`,
  `*.pdf` and `*.zip`.
