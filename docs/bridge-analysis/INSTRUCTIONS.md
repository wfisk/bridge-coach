# Bridge Analysis: analysing a session from a Bridgemate .bws file

## What the user gives you
A single Bridgemate file (`*.bws`, a Microsoft Access database) from a club or practice session.
Nothing else is needed: the file contains the hands, the auctions at each table, contracts, declarers,
opening leads, results, the pair movement and a double-dummy analysis.

## What to produce
One PDF, **entirely in French**, analysing every deal for the players (many are aged 70+).
Default file name: `Analyse-donnes-AAAA-MM-JJ.pdf` (e.g. `Analyse-donnes-2026-05-01.pdf`).

## File naming (agreed with the user)
For every file you create or deliver (PDF, JSON, working files), use **dashes** as separators
(no underscores or spaces) and write dates as **yyyy-mm-dd** (e.g. `donnes-2026-05-01.json`).

## Tools (files stored with these instructions)
| File | Role |
|---|---|
| `jet4.py` | Pure-Python reader for Access (Jet 4) files. No installation needed (package sites may be blocked). |
| `bws_extract.py` | `python3 bws_extract.py séance.bws donnes.json`: extracts everything into JSON, in French notation. Computes dealer and vulnerability from the board number, scores, IMPs (2 tables: direct comparison; more: against the average), par, tricks against double-dummy, pair totals, and **checks every recorded auction** (legal, ends in the scored contract). Player names are never exported. |
| `build_pdf.py` | `python3 build_pdf.py donnes.json analyse.json sortie.pdf`: builds the PDF. Prints a warning if a deal runs over two pages or has no written analysis. |
| `exemple_analyse_2026-10-23.json` | Complete worked example of `analyse.json` (24 deals, 23 Oct 2026): copy its style and level of detail. |

Requires Python 3 with `reportlab` and the DejaVu fonts (both usually present). Copy the scripts into the
working directory, keep the .bws in its own folder, and run Python with `-I`.

## Workflow
1. Run `bws_extract.py`. Read the **ALERTES**: an incomplete or impossible recorded auction must be
   rebuilt (from the scored contract and the logic of the auction) and declared in `encheres_corrigees`
   with a short note. If it is genuinely ambiguous, ask the user.
2. For each deal, write the analysis in `analyse.json`:
   - `enc`: recommended SEF auction, grid in the order **Ouest, Nord, Est, Sud**, "–" before the dealer.
   - `notes`: explanation of the auction (points, distribution, conventions).
   - `plan`: play plan for the recommended contract.
   - `comm`: comment on the contracts actually played (IMP).
   - `entame`: recommended opening lead against the recommended contract, e.g. `{"joueur": "E", "carte": "♥X"}`
     (the leader is the player to the declarer's left).
   - `defense`: short comment on the lead and the defence (partner's suit, passive or active lead,
     trump lead, forcing defence…), from the leader's hand and the auction only.
3. **The auction, lead, defence and play plan are written at the table** (see CLAUDE.md): never from the
   other hands or double-dummy. Only `comm` is checked against double-dummy (`dm` and `par` in the JSON),
   after the fact: number of tricks, makeable contracts, sacrifices. Never claim there that a contract
   makes if double-dummy says otherwise.
4. Run `build_pdf.py`, look at a few pages (render to PNG), fix, and deliver.

## Writing rules (agreed with the user)
- **French**, cards **A R D V X** (never AKQJ or 10). In the texts you may write N, S, E, O, N-S, E-O:
  they are written out automatically as Nord, Sud, Est, Ouest, Nord-Sud, Est-Ouest.
- System: **SEF 2024+**, 5-card majors, transfers (texas), Stayman, weak twos in the majors, Blackwood 3041.
  When an SEF treatment is uncertain, say so instead of guessing.
- **Scoring: IMP** (not matchpoints).
- Plans: short and practical. One or two paragraphs, enough to know how to play the key suit and
  what to avoid. No step-by-step lectures.
- **Never reduce the font size.** Each deal starts on a new page and takes **at most two pages**.
- Opening leads on the diagram: grey outline circle = lead made at one table, double outline = same lead
  at two or more tables, filled translucent grey circle = recommended lead (they combine). A legend sits
  to the right of the diagram. An actual lead is shown only if that table played the same denomination
  with the same declarer as the recommended contract (level and doubling do not matter); every lead still
  appears in the results table.
- Page order: hands → results → auctions at the tables → recommended auction → plan → lead and defence → comment →
  **double-dummy and par at the end** (an appendix, so it does not interrupt the reading).
- **No club name and no player names** (private games). Pairs by number only.
- Before sending to the group, the user may ask for a short email: it is written in French.

## Pitfalls already met (check every time)
- **Playing order in finesses**: the finesse works against the player who plays *just before* the cards
  you hope will win (order N → E → S → O). When leading from one hand, check who plays second.
- **8 cards → finesse, 9 → drop.** Cashing A-R then "finessing" on the 3rd round is just playing for the drop.
- Do not lead an honour for a finesse without the card below it (V without the X).
- **Opening leads (French conventions)**: against no-trumps, 4th best from a suit with an honour; from a long suit
  with no honour, the **2nd highest** (97542 → 7), never "top of nothing". Never lead a singleton trump.
  Against a grand slam, lead passively; against a small slam, often actively.
- Look for the **danger hand** and the **order of plays** (which finesse first, keep the entries); check
  what the defence does when it gets the lead (switch to the unbid suit, etc.).
- **4SA in SEF**: quantitative by default, even after a texas (2SA – 3♥ – 3♠ – 4SA = quantitative).
  Blackwood once a fit is shown, or when 4SA follows a bid at the 4 level (control bids).
- **Response with 4-card major + 5-card minor**: major first only with 5–11 H; with a game-forcing hand,
  longest suit first (e.g. 1♦ – 2♣ – … – 2♠).
- The Bridgemate sometimes misses bids: always read the alerts.
- Double-dummy assumes all cards visible: a gap is not always a mistake (lead, two-way guess).
