# Bidding systems

Reference used when writing the recommended auctions in a report. One folder per
system, plus shared conventions:

    systems/
      conventions/<name>.md     one convention, written once, shared by systems
      <system>/systeme.md       the system itself, as a sequence tree
      <system>/conventions.md   which conventions it plays (links to conventions/)
      <system>/regles.yaml      the bidding rules the program reads (being built up)
      <system>/entames.md       opening leads, defence and signals
      technique/jeu-de-la-carte.md  declarer play, the same for every system
      <system>/ffb/             official documents (booklet, convention card):
                                copyrighted, ignored by git

A partnership's own agreements are a system of their own (e.g. `sef-2024-william/`)
whose `systeme.md` says "as sef-2024, except…" and lists only the differences.

A session's `analyse-*.json` names its system with `"systeme": "<folder>"`.
When it is absent the system is `sef-2024`.

## Format

Files are in French, with the same notation as the reports: A R D V X, SA,
passe, contre, surcontre; H = points d'honneur.

Each auction is a nested list: one bid per line, its meaning after the colon,
the answers indented below it. This follows the spirit of BML (Bidding Markup
Language), so it can be converted later if needed.

    ## 1SA (15–17 H, régulier)
    - 2♣ : Stayman
      - 2♦ : pas de majeure 4e
      - 2♥ : 4 cœurs, peut avoir 4 piques

Mark anything not checked against the official documents or agreed with the
partner as **(à confirmer)**. An analysis must not rely on such a line without
saying the treatment is uncertain.

## Not read by the program

The program never reads these files. The bidding rules live in
`src/encheres/sef2024.py`, the lead and play rules in `src/jeu.py`; each piece of
code names the file it mirrors. When a file changes, update the code to match
(and the other way round).

## regles.yaml: rules the program reads

Unlike the `.md` files, `regles.yaml` is read by the program (`src/regles.py`).
Its grammar is described in French in [grammaire.md](grammaire.md): suits T K C P,
points H / HL / HLD, players U W (us) and Y Z (them), zones `5+` `1-` `6-10`,
`,` = and, `||` = or, generic sections like `"1M"`, examples checked as tests.
Check the file after any change with `.venv/bin/python -I src/regles.py`.
