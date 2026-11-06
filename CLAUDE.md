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
                        a time; Enter picks the latest. It builds -archive (what was played: tables,
                        results, factual comment, no recommendations) and -standard (program only);
                        with a written analysis also
                        -expert (Claude's analysis) and -diff (standard and expert compared).
                        Sorted alphabetically: archive, diff, expert, standard
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
                        Members are offered only vX.Y tags, never work in progress on main
    src/                Python code
      app.py            the NiceGUI application: one bar across the top (ui.header: Fichier menu, the tabs, Aide; not the native bar: the window process leaves
                        the Dock, so macOS would show none) with Ouvrir une séance (the .bc.json, by session date), Importer
                        (rapport.py --importer: the .bc.json only, then it opens; .bws already imported are marked; the Rapports
                        tab offers a new .bws not yet imported), Exporter en PBN (donnes.pbn beside the .bc.json, with
                        DoubleDummyTricks) and the working folder; the open session is remembered in etat.json beside
                        bridge-coach.ini (retenir, seance_active) and named in the window title (titre_fenetre). Fichier, Nouveau…: closes the open session (plain title; the
                        remembered one changes only once a new file exists), then a page (a hidden tab, like Aide): "Créer une séance vide" (edited in the Donnes tab with the deal editor, editeur_donne),
                        then the theme drawing (a − / + count per kind of hand, 36 at most); either new file opens in the Donnes tab. Tabs: Donnes (opens on it) views the open
                        .bc.json with a sidebar (ui.left_drawer, light warm grey GRIS_BARRE like Claude's sidebar, the chosen entry a rounded darker pill, full height, Donnes tab only: Séance (alerts at its foot), Joueurs, a divider, one entry per deal (every tab has two entries then a divider, so Donne 1 stays in place): hands, double-dummy, par, each table's auction (encheres_html),
                        table results; vue_seance, page_donne…), view only so far. A deal page in Donnes, Analyse and Jouer has the same right sidebar (panneau_droit: fixed, LARGEUR_PANNEAU, the deal's name, a small board case, theme and par; Analyse adds the Standard | Expert toggle, the recommended contract and the lead; Donnes the « Modifier la donne » button); Analyse: sidebar Analyse standard (status, date, "Lancer
                        l'analyse": rapport.py, analysis and PDFs; the run block stays visible while it runs), Analyse expert
                        (status, date, and the steps to get it from Claude on the web: preparer_pour_claude copies the session,
                        the standard analysis, the system files, the example and CONSIGNE.txt (the rules for the expert
                        analysis, in French) into <working folder>/pour-claude/<name>/; importer_expert checks the returned
                        JSON (four-column grids; each lead from the declarer's left, a card of that hand: rapport.entame_valide), keeps the old file as -expert-avant-<date-time>.json and merges deal by deal; "Mettre à jour les rapports"
                        runs rapport.py --rapports: the PDFs from the saved -standard.json, no new analysis), then each deal's analysis, the Expert's when it exists (toggle
                        Standard | Expert, Expert by default; page_analyse, lire_analyses); Rapports: the session's PDFs and the bilan as links with
                        file name and date (lien_pdf); Réglages. Jouer (between Donnes and Analyse; Contrôle was removed): the player
                        bids one seat, the engine the three others (vue_jouer, boite_encheres; logic in jouer.py), then the
                        contract against Expert and Standard. Layout: the table on the left, a large warm-neutral rounded square (no name plates: the board case in the centre, bidding
                        cards, trick cards and dummy on it, the players' hands outside; the thinking player's name blinks on the case; hands as overlapping
                        cards drawn in CSS, CSS_CARTES, suits ♠ ♥ ♣ ♦ with a gap; dummy laid out as at the table: one column per suit, highest card on top, trumps on the left (mort_etale); the
                        trick in the centre as cards; bids as bidding cards stacked in front of each player (yours and partner's left to right, the
                        side players' top to bottom), each label on the edge left visible,
                        bidding-box colours: SA grey, ♠ blue, ♥ red, ♦ orange, ♣ green, Passe green, X red, XX blue), the player always at the bottom
                        (the table and the board case turn with the seat; a hand on a side is one row per suit), the board case (etui: upright,
                        taller than wide, neutral grey; each seat's name on red if vulnerable, green if not, written to be read from
                        its own seat (sides turned, the top one upside down), the dealer written « DONNEUR » in capitals; the case 9:16 and light grey, North and South always on its short sides: upright when N-S sit top and bottom, lying when E-O do; the N-S bands run the full width, E-O between them) in the centre; hidden hands as small muted card backs (dos) in a slight fan; your hand larger, a little below the table, each player's last bid clear and earlier ones veiled, glowing when it is your turn to bid; disabled X/XX grey, the cards and the case sized so the layout fills the space, at the top of the screen; side bids start level with the seat's name; the auction grid in the sidebar underlines each seat red or green (grille_html vul), « Le sens des enchères » and « Plis joués » sit in the sidebar, Indice on the front of the bidding box, a right
                        sidebar (fixed, full height, LARGEUR_PANNEAU, the same grey with a thin left border) with the deal number,
                        the seat played (no choice for now; an « Options » entry heads the deal list, a placeholder), the auction, then the bidding box drawn as a red box (bid cards standing behind in the
                        order ♣ ♦ ♥ ♠ SA, only the bids still possible, four levels, « … les autres enchères »; Passe, X, XX tabs in
                        front) or the play buttons. The sidebar entry (vue["entree"]) is shared by Donnes, Jouer and
                        Analyse: a deal chosen in one stays chosen in the others;
                        window 1200×850,
                        with Aide at the top. Rapports picks the .bws created last, runs rapport.py as a separate process
                        (never inside the server) and reads its lines ("Donne 3 sur 24", "Rapport prêt : …")
                        for the progress bar; Cancel stops the whole process group; French messages only,
                        the Python trace goes to rapports/derniere-erreur.txt. Window through pywebview,
                        browser if it is missing (--navigateur); always host 127.0.0.1 (NiceGUI would open 0.0.0.0 in browser
                        mode). requirements.txt pins exact tested versions (wheels checked for Windows/Mac, Python 3.9–3.13).
                        Mac only so far; Windows not tested
      rapport.py        imports a source (.bws, FFB PDF, simulated .json) into the Bridge Coach file
                        seances/AAAA-MM/<name>.bc.json (format, version, source, session, joueurs, donnes…;
                        entete, ecrire_bc), keeps a copy of the original beside it, builds the PDFs into
                        rapports/AAAA-MM/ (writes each PDF under a temporary name then swaps it in:
                        Documents is synced by a full iCloud, which kept old versions otherwise)
                        A .bc.json (or the old -donnes.json) is read as is (donnes_pretes), skipping the import.
                        migrer(), on every start: reports/ → rapports/, <name>-donnes.json → <name>.bc.json with
                        its source and players (<name>-paires.json merged in, then removed)
      maj.py            updates from GitHub, standard library only: derniere_version (tags API, only on the Réglages
                        button), then a separate process (--appliquer V --attendre <app pid>) waits for the app to close,
                        downloads the tag's zip, moves the old program to .ancien-programme/, puts the new one, pip only if
                        requirements.txt changed, checks the new code imports, restores the old one on any failure, writes
                        rapports/derniere-mise-a-jour.txt and reopens the app. Never touches .venv/.git; a Git clone is told
                        to use git pull. tests/test_maj.py applies a good and a broken version to throwaway copies
      donnes.py         creates training deals: a count per theme ("Squeeze=4" "Aléatoire=8", lire_quotas; the app's − / + list), each theme a test on a random
                        deal (THEMES: engine auction, double-dummy, coups.py or the plan's count), DELAI seconds per deal, then
                        random and says so. Writes entrainement-<date>-<HHMMSS>.bc.json (source "entrainement" or "saisie") and a .pbn for Bridgemate
                        (Control Software 3.1.2+: File, Import). Deals have no tables: reports skip the archive
                        Deals typed by hand (lire_texte / texte_de: "PRDX76C32K…T…" × 4 from North, then vulnerability
                        N-S, E-O as V/N and the dealer, "VVN"; West may be left out): donnes.py --texte only (the app types deals in the Donnes tab)
      bws_extract.py    .bws -> donnes-AAAA-MM-JJ.json (prints ALERTES for broken auctions)
      jet4.py           pure-Python Access reader, nothing to install
      feuille_route.py  FFBClubNet "feuille de route" PDF -> session JSON (hands by position on the
                        page, contracts, leads, results; no auctions, double-dummy computed with
                        endplay; the club name is not kept); rapport.sh accepts the PDF directly.
                        FFBClubNet backups named .bws are password-protected 7z archives: not
                        readable, rapport.py says so
      build_pdf.py      donnes + analyse JSON -> PDF; -standard and -expert open with a summary page:
                        the deals where a table's contract differs from the recommended one, one line
                        per table, lowest contract first, with the pairs' initials (declaring pair in
                        bold), the contract and the table's result (-1 = +2). Same side: red = higher than
                        recommended, blue = lower; no colour for the other side or the same contract by
                        partner. Then a sentence listing the deals where every table agreed, and a short
                        list of different leads (same denomination only; yellow). No IMP here: this page
                        shows where the contracts differ, not performance; results by table are on each
                        deal's page. Pairs sit in a fixed-width column so contracts line up
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
                        sets that deal's expert entry aside (oublier_analyse: dated -expert-avant- copy, the other deals keep theirs).
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
                        Expert / Standard, first differing call), attempts saved in <name>-jeu.json beside the session
      carte.py          card play in the Jouer tab: Partie (coups.Position, lead from the rules, legal cards, tricks, claim
                        checked double-dummy); the player holds declarer and dummy. Defence like lignes.py from the defender's
                        seat: 16 worlds of the two hidden hands true to the auction (lire_encheres), cards played and shown voids,
                        solved double-dummy, the card that sets the contract most often (then most tricks, then the lowest).
                        Bench vs a double-dummy declarer, 40 fresh deals: lead +0.23, defence +0.20 trick per deal (without the
                        auction +0.30). Indice: lignes._carte. The app adds a thinking pause (0.8–0.9 s) to every engine call and card
      lignes.py         simulated declarer: at each card imagines 12 worlds true to the auction, lead and play,
                        solves them, keeps the card that wins most often; never sees the defenders' hands
                        of the deal played, defence double-dummy. analyser() runs it on 40 imagined deals: make
                        rate, order of the suits, what decides the contract (a split or a missing honour),
                        finesses taken, ruffs before trumps; plan_de_jeu follows these for its steps.
                        PARALLELE is switched on only by rapport.py (spawn re-reads the running script:
                        keep a __main__ guard); one Pool per run, falls back to plain play if it fails. Each worker
                        takes about 0.7 GB (the solver): nb_processus() leaves one core and 4 GB free
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
    help/index.html     the application's help, in French, shown as a page of the window by the Aide button (a hidden tab, 16px)
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
                        reports need), the original beside it (<name>.bws, the FFB .pdf…), -standard.json (the program's analysis:
                        engine auctions + automatic comments; overwritten each run, copy it to
                        -expert.json to edit by hand), -expert.json (written by hand or by
                        Claude: the only file that can't be recreated; wins deal by deal).
                        Each analysis JSON has the same suffix as its PDF (-standard, -expert)
    rapports/AAAA-MM/   only the PDFs, ignored by git, with the date first: <date>-<name>-archive.pdf,
                        -standard.pdf, -diff.pdf, -expert.pdf (no spaces in names: dashes; a date already in the
                        name is not repeated and its time comes first, rapport.nom_court: 2026-11-01-224232-entrainement-diff.pdf)

Read `docs/bridge-analysis/PROJECT-INSTRUCTIONS.md` and
`docs/bridge-analysis/INSTRUCTIONS.md` before writing an analysis or changing the
report: the PDF is in French, uses SEF / IMP, and has fixed layout rules.
`~/Documents/bridge-coach-files/documents/exemple_analyse_2026-10-23.json` is the style reference.

For the recommended auctions, use the session's system in `systems/`
(`"systeme"` in the `-expert.json`, default `sef-2024`) rather than the short
system notes in the earlier instructions. Read its `systeme.md`, the conventions
it lists, its `entames.md` for leads and defence, and the official documents in its `ffb/` folder when present. Never
rely on a line marked **(à confirmer)** without saying the treatment is uncertain.

**The recommended auction is bid at the table, without hindsight.** When writing `enc`
and `notes` in an `-expert.json`, choose each call from that player's own hand and the
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
In `plan`, the expert keeps the program's layout (`plan_de_jeu` with `simuler=True, verdict=False`: first trick,
hold-up and squeeze worked out from declarer's view),
then `<br/><b>Avis de l'expert :</b>` and three or four sentences of judgement the program lacks (why the plan works, the danger hand, the order of play) (`defense` ends the same way, after the rule's text; `notes` is the expert's opinion on the auction). The expert report marks all three with a ✦, a pale green background and a green bar; the standard report has none. For each
contract, look for a hold-up, an elimination, a squeeze or a coup; if one fits, say so there. `tests/test_coups.py`
holds textbook positions for `coups.py`.
All three sessions now follow these rules: the 23/10 and 6-table auctions were rebid on
2026-10-30 and their card play redone on 2026-10-31 (earlier versions kept as
`-expert-avant-<date>.json`).

## Running on this Mac

System Python is 3.9, so `.venv/` pins `reportlab<4.3` (4.3+ needs 3.10).
To recreate it: `python3 -m venv .venv && .venv/bin/pip install "reportlab<4.3" pypdfium2 endplay ruamel.yaml`
(pypdfium2 renders pages to PNG for checking; endplay is only for random simulations).

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
