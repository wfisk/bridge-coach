# bridge-coach

Bridge Coach : « le compagnon du cours de bridge au club ». A Python program for a French bridge club: it imports club
tournaments (Bridgemate `.bws`, FFB pages, PBN), analyses each deal, writes PDF reports, lets members replay and practise
against bidding and card-playing robots (SEF 2024), and helps a teacher in class (Démo, quiz). Users are mostly seniors;
the app may be shown on a classroom TV.

This file is the map. **The detailed history of every file and the reasons behind each choice are in
`docs/notes-detaillees.md`**: read the part about a file before changing it, and write new details there, not here.
The code comes from earlier sessions: build on it rather than rewriting it.

## Running

- Python 3 from `.venv/` (`.venv/bin/python -I -X utf8 …`; always `-I`, and `-X utf8` because Windows does not default to
  UTF-8). This Mac's system Python is 3.9, so `.venv` pins `reportlab<4.3`; endplay (double-dummy solver) has no wheel
  for 3.14. Recreate: `python3 -m venv .venv && .venv/bin/pip install "reportlab<4.3" pypdfium2 endplay ruamel.yaml`.
- `./bridge-coach.sh` opens the app (NiceGUI in a pywebview window, `--navigateur` for a browser; port 8123,
  `BRIDGE_COACH_PORT` / `BRIDGE_COACH_DONNEES` for a second test instance started from the shell).
- `./rapport.sh [file.bws] [--sans-analyse] [--avec-noms]`: the PDF report from the command line.
- Tests: `for t in tests/test_*.py; do .venv/bin/python -I -X utf8 "$t"; done` (no pytest; publier.sh runs them all).
- Bidding bench: `src/outils/banc_encheres.py` (before / after on 20 000 random deals, IMP double dummy).

## Layout

    bridge-coach.sh, rapport.sh, installer.sh, raccourci-mac.sh     Mac launchers; installer.bat, bridge-coach.bat on Windows
    VERSION, publier.sh            ./publier.sh X.Y "note": tests, tag vX.Y, push; GitHub Actions builds the installers
    installer/                     installers' sources (Inno Setup .exe, macOS .pkg); they fetch the latest Release
    requirements.in / .txt         pinned libraries; requirements.txt generated with uv, hash-locked
    help/                          the app's French help (index.html, images/), nouveautes.html (members' changelog)
    systems/                       bidding systems: sef-2024/ (regles.yaml = the robots' rules, systeme.md, entames.yaml,
                                   a-faire.md = bench log), conventions/*.md, bridgez/ (hidden skeleton), technique/;
                                   */ffb/ (official documents, transcriptions) ignored by git
    docs/                          notes-detaillees.md (the detailed notes), bridge-analysis/ (old instructions)
    tests/                         one script per module, plain asserts
    src/
      app.py                       the app's entry point (70 lines): the page route, the window, start-up
      interface/                   the window (NiceGUI), split from app.py on 2026-11-19:
        commun.py                    imports, constants, etat.json, background jobs (rapport.py), help, HTML drawings,
                                     and F, the page's shared names (state dicts and every module's functions)
        fenetre.py                   construire(): the page (header, tabs, dialogs); binds each module's NOMS into F
        vues_donnes.py               Donnes / Analyse views, the expert, the Brouillon, a deal's right panel
        jouer_encheres.py, jouer_carte.py, table.py, onglet_jouer.py, demo_quiz.py      the Jouer tab
        editeur.py, navigation.py, onglet_fichier.py, onglet_rapports.py, onglet_systeme.py, onglet_reglages.py
      encheres/                    the bidding engine: encherir(), rules first (regles.py reads regles.yaml), then sef2024.py
      outils/                      developer tools run by hand: banc_encheres, essai_*, simuler, bilan, captures_aide
      flat modules                 importers (jet4, bws_extract, pbn, ffb_html, ffb_pdf, feuille_route); rapport (import,
                                   analysis, PDFs), build_pdf, comparer, couts, commentaires; card play (carte, lignes,
                                   modele, coups, signaux, coach, jeu); session files (fichiers, edition, brouillon,
                                   exporter); donnes (training deals), jouer, demo, quiz, classement, moi, maj (updates),
                                   palette, systeme_vue, fiche_conventions, question_expert, regles, entames

Bidding systems: a regles.yaml may say `base: sef-2024` and write only its differences, `sans: [Roudi, …]` switches
conventions off by their `nom:` (70 calls named: Stayman, Texas, Roudi, Drury, Spoutnik, Bicolores, Landy, 4e couleur
forcing; Blackwood and Spoutnik also in the code, encheres.convention_active), `pret: non` hides it. The robots' system:
donne["systeme"] or encheres.choisir_systeme. systems/bridgez/ (the beginners' system) is an empty skeleton until the
book's pages arrive.

Interface code: a function that belongs to the page reads and calls everything through `F` (`F.jeu`, `F.vue_jouer()`);
a new one goes in its subject's module and in that module's `NOMS`. The other modules stay flat on purpose: members'
installed updater checks a new version with `import rapport, donnes, edition` from `src/`, so those must stay there, and
the rest import each other by flat names. The detailed notes name app.py functions by their old place.

Outside the folder, never in git: `bridge-coach.ini` (Mac `~/Library/Application Support/Bridge Coach`, Windows
`%APPDATA%\Bridge Coach`) says where the Bridgemate `.bws` are read (never written) and where the user's files go
(`~/Documents/bridge-coach-files`: `seances/AAAA-MM/<name>.bc.json`, `rapports/AAAA-MM/*.pdf`, `documents/`);
`etat.json` beside it remembers the app's state.

## Rules that always apply

- **Privacy.** Players appear by initials (pairs « AB/CD »). Full names and FFB licence numbers stay in the `.bc.json`
  and never leave the computer: not in reports (except `--avec-noms`), not in files for Claude, not in git. No club
  name. Never commit `.bws`, session JSON or reports (`.gitignore` covers them). The repository is public: before a
  push, `git diff origin/main | grep -ci "fisk\|reygner\|boscardin"` must find only `wfisk/bridge-coach`. Never push
  the branch `historique-prive` or the bundle in Documents.
- **Publishing.** Members get only `vX.Y` tags (publier.sh), never main; publish only when the user asks, with a
  « Quoi de neuf » section in help/nouveautes.html. Regenerate reports only when asked.
- **Bidding rules must generalise.** A rule change is kept only if it gains on fresh random deals (banc_encheres,
  2 × 20 000), not just on the session deal that prompted it; log each try in systems/sef-2024/a-faire.md. Follow the
  official SEF text; never guess a convention: ask for the page.
- **At the table, no hindsight.** Recommended auctions, leads, defence and play plans are chosen from what the player
  sees (their hand, dummy, the auction), never the hidden hands or double dummy; double dummy only after the fact
  (comments, « Cartes vues »). Leads come from entames.yaml rules, never a double-dummy simulation.
- **Words.** Everything members see is in French. In Jouer, the software is « le coach » (the teacher) and the other
  players « les robots »; « le programme » only for installing and updating. The program's analysis is « Analyse du
  coach », Claude's « l'expert ».
- **Readability.** Seniors and a classroom TV: text that changes is 16 px or more in dark grey; the type scale 13 / 14 /
  16 / 18 / 22 / 26 and colours are tokens (palette.py, `--bc-…`); controls in the right sidebar or above the table,
  never below the content.
- **Files.** Dashes and yyyy-mm-dd dates in names; session files are JSON that only gain fields.
- **Git.** Commit only your own files; never stash, reset or switch branches; leave `dump.txt` alone. Commit messages
  end with the Co-Authored-By line the session gives.

## Writing an expert analysis

Read `docs/bridge-analysis/PROJECT-INSTRUCTIONS.md` and `INSTRUCTIONS.md` first; the PDF is in French, SEF and IMP, with
fixed layout rules; `~/Documents/bridge-coach-files/documents/exemple_analyse_2026-10-23.json` is the style reference.
Use the session's system in `systems/` (`systeme.md`, its conventions, `entames.md`, its `ffb/` documents); never rely on
a line marked **(à confirmer)** without saying the treatment is uncertain.
- `enc` and `notes`: each call chosen from that player's hand and the auction so far, as at the table; when two calls
  were reasonable, « Décision serrée : » names the other. Check the coach's auction call by call: keep it only when every
  call reads naturally to a club partner.
- `entame`, `defense`: the leader's hand and the auction only, by entames.yaml. `plan`: declarer's and dummy's cards,
  the lead and the auction only.
- In `plan` and `defense`, keep the coach's text (« Le conseil du coach ») unchanged, then `<br/><b>Avis de l'expert
  :</b>` as a comment on it (« Le coach a raison : … », « Le coach oublie que … »), adding only what it corrects; when
  the expert's contract differs, still comment on the coach's advice, then what changes. Look for a hold-up,
  elimination, squeeze or coup in each contract.
- Two pages per deal is a guide, not a rule: the coach is never shortened to fit.

The full rules, with the reasons and the history of each, are in docs/notes-detaillees.md (the paragraphs after « Layout »,
and the build_pdf / rapport / coach entries).
