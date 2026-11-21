# -*- coding: utf-8 -*-
"""L'onglet Système (systeme_vue.py) : tout le fichier de règles se lit, chaque condition se traduit en français,
les familles couvrent toutes les séquences, les liens « La suite » mènent à une séquence décrite."""
import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import systeme_vue as v

s = v.lire()
n_seq, n_enc, n_ex = v.compter(s)
assert n_seq > 100 and n_enc > 500 and n_ex > 50
fams = v.familles(s)
assert sum(len(seqs) for _, _, secs in fams for _, seqs in secs) == n_seq      # chaque séquence dans une famille
assert fams[0][0] == "ouvertures"
# toutes les conditions traduites (rien laissé en <code>)
for _, seqs in s["sections"]:
    for cle, regles, _ in seqs:
        for r in regles:
            assert "<code>" not in v.condition(r["si"], s["definitions"]), (cle, r["si"])
assert v.condition("H 8+, M 4, non forme 4-3-3-3") == "8 H ou plus, une majeure de 4 cartes, pas de répartition 4-3-3-3"
assert v.condition("reg, H 15-17, M 4-") == "main régulière, 15 à 17 H, pas de majeure de 5 cartes"
assert v.condition("P 5+, P >= C") == "5 piques ou plus, au moins autant de piques que de cœurs"
assert v.condition("") == "dans tous les autres cas"
# la navigation
ix = v.index(s)
assert v.suite(ix, "1SA", "2T") == ("1SA - 2T", "1SA – 2♣")
assert v.suite(ix, "ouverture", "1SA")[0] == "1SA"
assert v.famille_de_cle("1SA - 2T", s) == "sa"
assert ("1SA - 2T", "sa") in v.chercher("1SA 2♣", s) and v.chercher("Drury", s)
# chaque lien de chaque page mène à une ancre de la même application
ancres = {v.ancre(c) for _, l in s["sections"] for c, _, _ in l}
for k, _, _ in fams:
    for a in re.findall(r"data-vers='([^']+)'", v.page_famille(k, s)): assert a in ancres, a
assert "♠" in v.main_html("A765 AX43 A982 3") and "10" in v.main_html("A765 AX43 A982 3")
assert v.lire_doc("systeme.md").startswith("# SEF 2024")
# un système bâti sur le SEF (le SEF simplifié) : la base sans ses conventions coupées, ses propres sections à leur place
ss = v.lire("sef-simplifie")
assert ss["titre"] == "SEF simplifié" and ss["base"] == "sef-2024" and "Roudi" in ss["sans"]
assert not any(str(r.get("nom")) == "Roudi" for _, l in ss["sections"] for _, rr, _ in l for r in rr)
assert [c[0] for c in v.conventions(ss)] == ["stayman", "texas", "blackwood"] and len(v.conventions(s)) == len(v.CONVENTIONS)
ouv = next(r for _, l in ss["sections"] for c, r, _ in l if c == "ouverture")
assert any(x["enchere"] == "2K" and "faible" in x["montre"] for x in ouv)                 # son 2♦ faible, à la place du SEF
cles = [c for _, l in ss["sections"] for c, _, _ in l]
assert len(cles) == len(set(cles)) and "2T - 2K - 3C | 2T - 2K - 3P" in cles             # chaque séquence une fois
fams_s = v.familles(ss)
assert sum(len(seqs) for _, _, secs in fams_s for _, seqs in secs) == v.compter(ss)[0]
for _, seqs in ss["sections"]:
    for cle, regles, _ in seqs:
        for r in regles: assert "<code>" not in v.condition(r["si"], ss["definitions"]), (cle, r["si"])
assert v.lire_doc("systeme.md", "sef-simplifie", "sef-2024").startswith("# SEF simplifié")
assert v.lire_doc("entames.md", "sef-simplifie", "sef-2024") == v.lire_doc("entames.md")   # les entames de sa base
print("ok")
