# -*- coding: utf-8 -*-
"""L'import des pages de résultats du site de la FFB : .venv/bin/python -I -X utf8 tests/test_ffb_html.py
Des pages inventées, au balisage des vraies (data-ui-id, ffb-suit-icon), et des joueurs inventés."""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import ffb_html

SESSION = "https://www.ffbridge.fr/competitions/results/groups/1/sessions/777"
ICONE = {"S": "spade", "H": "heart", "D": "diamond", "C": "club"}
TETE = f"""<!DOCTYPE html><html><head><title>Résultats - Fédération Française de Bridge</title>
<script>document.write("rien n'est exécuté")</script></head><body>
<a href="{SESSION}"> Tournoi du club - 05/11/2026 - Soir </a>
<ffb-competitions-results-print-context><div><p> Club inventé </p><p> Tournoi du club - 05/11/2026 - Soir </p></div>
</ffb-competitions-results-print-context>"""
FIN = "<svg><text>♠</text></svg></body></html>"
# N: ♠AKQ ♥AKQ ♦AKQ ♣AKQJ — E: ♠JT98 ♥JT9 ♦JT9 ♣T98 — S: ♠765 ♥8765 ♦876 ♣765 — O: ♠432 ♥432 ♦5432 ♣432
MAINS = {"N": ["ARD", "ARD", "ARD", "ARDV"], "E": ["V1098", "V109", "V109", "1098"],
         "S": ["765", "8765", "876", "765"], "W": ["432", "432", "5432", "432"]}


def icone(s):
    return (f'<ffb-suit-icon suit="NT"><span> SA </span></ffb-suit-icon>' if s == "NT" else
            f'<ffb-suit-icon suit="{s}"><tui-icon class="{ICONE[s]} fit-text"></tui-icon></ffb-suit-icon>')


def main(siege):
    out = f'<div class="player" data-ui-id="player-{siege}"><p> X </p></div>'
    for c, cartes in zip(("spade", "heart", "diamond", "club"), MAINS[siege]):
        cartes = cartes.replace("10", "T")
        out += (f'<div class="cards" data-ui-id="player-{siege}-{c}"><ffb-suit-icon><tui-icon class="{c} fit-text">'
                f'</tui-icon></ffb-suit-icon>' + "".join(f'<div class="card flex"> {"10" if x == "T" else x} </div>' for x in cartes)
                + "</div>")
    return out


def ligne(k, ns, eo, contrat, decl, entame, res, sns, seo, note):
    niv, den, x = contrat if contrat else (None, None, "")
    c = "PASSE" if not contrat else f'<ffb-contract><span><span>{niv}</span>{icone(den)}<span> {x}</span></span></ffb-contract>'
    e = "—" if not entame else f'<ffb-opening-lead><span>{icone(entame[0])}<span> {entame[1:]} </span></span></ffb-opening-lead>'
    td = lambda i, v: f'<td data-ui-id="teams-board-scores-table-row-{k}-{i}" id="{i}">{v}</td>'
    return (f'<tr data-ui-id="teams-board-scores-table-row-{k}" id="{100 + k}">' + td("table", "<div> </div>") + td("nsTeam", ns)
            + td("ewTeam", eo) + td("contract", c) + td("declarer", decl) + td("lead", e) + td("result", res)
            + td("nsScore", sns) + td("ewScore", seo) + td("nsNote", note) + td("ewNote", "") + "</tr>")


def donne(n, donneur, vul, lignes, optimum):
    grille = "".join(f'<tr data-ui-id="optimum-score-table-row-{i}"><td id="declarer"> {s} </td>'
                     + "".join(f'<td id="{d}"> {v} </td>' for d, v in zip(("C", "D", "H", "S", "NT"), vals)) + "</tr>"
                     for i, (s, vals) in enumerate(optimum))
    return (TETE + f'<h5 data-ui-id="board-number"> {n} </h5><p data-ui-id="dealer"> {donneur} </p>'
            f'<p data-ui-id="vulnerability"> {vul} </p>' + "".join(main(s) for s in "NESW")
            + '<table data-ui-id="teams-board-scores-table"><tbody data-ui-id="teams-board-scores-table-body">'
            + "".join(ligne(k, *l) for k, l in enumerate(lignes)) + "</tbody></table>"
            + f'<table data-ui-id="optimum-score-table"><tbody data-ui-id="optimum-score-table-body">{grille}</tbody></table>' + FIN)


def classement(rangs):
    rows = "".join(f'<a href="{SESSION}/pairs/{k}"><tr data-ui-id="ranking-row-{k}"><td data-ui-id="ranking-row-{k}-rank"> {r} </td>'
                   f'<td data-ui-id="ranking-row-{k}-position"> A {pos} </td><td data-ui-id="ranking-row-{k}-team">'
                   f'<ffb-team-players><span> {a} </span><span> - {b} </span></ffb-team-players></td>'
                   f'<td data-ui-id="ranking-row-{k}-sessionScore"> {pct}&nbsp;% </td></tr></a>'
                   for k, (r, pos, a, b, pct) in enumerate(rangs))
    return TETE + f'<table><tbody data-ui-id="ranking-body">{rows}</tbody></table>' + FIN


NS1, NS2 = "DURAND Alice - MARTIN Paul", "PETIT Claire - LE ROUX Jean-Marc"
EO1, EO2 = "BLANC Hugo - NOIR Lise", "VERT Anne - ROSE Marc"
OPT = [("N", (13, 12, 13, 12, 13)), ("S", (13, 12, 13, 12, 13)), ("E", (0, 1, 0, 1, 0)), ("O", (0, 1, 0, 1, 0))]   # ♣ ♦ ♥ ♠ SA
d = tempfile.mkdtemp()
pages = {
    # Mitchell, 2 tables, 1 donne par tour : au tour 1, table 1 NS1-EO1 donne 1, table 2 NS2-EO2 donne 2 ; au tour 2, les E-O montent
    "donne-01.html": donne(1, "Nord", "Personne", [
        # l'ordre des noms de la fiche n'est pas celui du classement : les paires se reconnaissent quand même
        (NS1, EO1, ("7", "NT", ""), "N", "S10", "=", "1520", "—", "100,00 %"),
        ("LE ROUX Jean-Marc - PETIT Claire", "NOIR Lise - BLANC Hugo", ("6", "C", "X"), "S", "HV", "+1", "1190", "—", "0 %")],
        OPT),
    "donne-02.html": donne(2, "Est", "Nord - Sud", [
        (NS2, EO2, None, "", "", "", "", "", "0 %"),
        (NS1, EO2, ("7", "S", ""), "N", "D2", "=", "2210", "—", "100 %")],
        [("N", (13, 12, 13, 12, 12))] + OPT[1:]),                 # une case fausse : signalée
    "ns.html": classement([(1, "NS1", "DURAND Alice", "MARTIN Paul", "75,00"), (2, "NS2", "PETIT Claire", "LE ROUX Jean-Marc", "25,00")]),
    "eo.html": classement([(1, "EO2", "VERT Anne", "ROSE Marc", "75,00"), (2, "EO1", "BLANC Hugo", "NOIR Lise", "25,00")]),
    "autre.html": "<html><body>Une autre page</body></html>",
}
for f, h in pages.items(): open(os.path.join(d, f), "w", encoding="utf-8").write(h)

assert ffb_html.reference(os.path.join(d, "donne-02.html")) == "ffbridge-seance-777"
assert ffb_html.reference(os.path.join(d, "autre.html")) is None
ref, liste = ffb_html.pages_du_tournoi(os.path.join(d, "eo.html"))
assert ref == "ffbridge-seance-777" and len(liste) == 4

s = ffb_html.seance(os.path.join(d, "donne-01.html"))
assert s["session"]["date"] == "05/11/2026" and s["session"]["marque"] == "MP" and s["session"]["moment"] == "soir"
assert s["session"]["tables"] == 2 and s["session"]["mitchell"]
d1, d2 = s["donnes"]
assert d1["mains"]["N"] == "ARD ARD ARD ARDV" and d1["mains"]["E"] == "VX98 VX9 VX9 X98" and d1["donneur"] == "N"
assert d2["donneur"] == "E" and d2["vul"] == "N-S" and d1["dm"]["SA"]["N"] == 13
t = {x["table"]: x for x in d1["tables"]}
assert t[1]["contrat"] == "7SA" and t[1]["entame"] == "♠X" and t[1]["score_ns"] == 1520 and t[1]["paire_eo"] == "1EO"
assert t[2]["contrat"] == "6♣X" and t[2]["entame"] == "♥V" and t[2]["resultat"] == "+1" and t[2]["paire_eo"] == "1EO"
assert t[2]["score_ns"] == 1190 and t[1]["pct_ns"] == 100.0 and t[2]["pct_ns"] == 0.0
t2 = {x["table"]: x for x in d2["tables"]}
assert t2[2]["contrat"] == "passe" and t2[1]["paire_ns"] == "1NS" and t2[1]["paire_eo"] == "2EO"
assert s["paires"]["1NS"]["nom"] == "AD/PM" and s["paires"]["2NS"]["nom"] == "CP/JMLR" and s["paires"]["2EO"]["nom"] == "AV/MR"
assert s["paires"]["1NS"]["pct"] == 75.0 and s["paires"]["2EO"]["rang"] == 1      # le % et le rang officiels
r = {(x["tour"], x["table"]): (x["ns"], x["eo"], x["donnes"]) for x in s["session"]["rondes"]}
assert r[(1, "1")] == ("1NS", "1EO", [1]) and r[(2, "1")] == ("1NS", "2EO", [2]) and r[(2, "2")] == ("2NS", "1EO", [1])
assert any("Donne 2 : double mort différent de la page de la FFB (N SA)" in a for a in s["alertes"]) and len(s["alertes"]) == 1

from bws_extract import JOUEURS
assert JOUEURS["1NS"] == ["DURAND Alice", "MARTIN Paul"]                  # les noms complets, comme pour un .bws

try:
    ffb_html.pages_du_tournoi(os.path.join(d, "autre.html")); raise AssertionError
except ffb_html.ErreurFFB:
    pass
print("ffb_html : ok")
