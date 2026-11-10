# -*- coding: utf-8 -*-
"""L'import d'un fichier PBN : .venv/bin/python -I tests/test_pbn.py"""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import pbn

PBN = """% PBN 2.1
[Event "Tournoi du club"]
[Scoring "MP"]
[Date "2026.11.07"]
[Board "1"]
[Dealer "N"]
[Vulnerable "None"]
[Deal "N:53.K873.AT64.AK8 KQ9.QT6.Q32.QJ76 A64.J94.K95.T953 JT872.A52.J87.42"]

[Board "2"]
[Dealer "E"]
[Vulnerable "NS"]
[Deal "N:AQ6.KJ963.A7.764 97.8.KQ8432.AK82 8532.AQT72.95.QJ KJT4.54.JT6.T953"]
[Declarer "N"]
[Contract "4H"]
[Result "9"]
[Auction "E"]
2D =1= Pass Pass 2H
Pass 4H AP
[Play "E"]
CA C4 CQ C3
{ un commentaire }

[Board "3"]
[Dealer "S"]
[Vulnerable "Both"]
[Deal "E:KQ9.QT6.Q32.QJ76 - JT872.A52.J87.42 53.K873.AT64.AK8"]
"""
f = os.path.join(tempfile.mkdtemp(), "club.pbn"); open(f, "w").write(PBN)
s = pbn.seance(f)
assert s["session"]["date"] == "07/11/2026" and s["session"]["titre"] == "Tournoi du club" and s["session"]["tables"] == 1
d1, d2, d3 = s["donnes"]
assert d1["mains"]["N"] == "53 R873 AX64 AR8" and d1["vul"] == "Personne" and d1["tables"] == [] and d1["dm"] and d1["par"]
t = d2["tables"][0]
assert (t["contrat"], t["declarant"], t["resultat"], t["entame"]) == ("4♥", "N", "-1", "♣A"), t
assert t["encheres"] == ["2♦", "passe", "passe", "2♥", "passe", "4♥", "passe", "passe", "passe"] and t["score_ns"] == -100   # N-S vulnérables
assert d2["donneur"] == "E" and d2["vul"] == "N-S"
# une main sautée (« - ») est complétée ; la donne part d'Est : Sud est la main qui manque
assert d3["mains"]["S"] == "A64 V94 R95 X953" and d3["mains"]["E"] == "RD9 DX6 D32 DV76" and d3["vul"] == "Tous"
assert pbn.appel("1NT") == "1SA" and pbn.appel("=2=") is None and pbn.contrat("3NTX") == "3SAX" and pbn.carte("H10") == "♥X"
try:
    pbn.mains_de("N:AKQ.xx.x.x - - -"); assert False
except pbn.ErreurPBN:
    pass
assert s["session"]["marque"] == "MP"
# la marque de la séance : lue, sinon devinée d'après le nombre de tables
import moi
assert moi.marque({"session": {"marque": "IMP", "tables": 9}}) == "IMP"
assert moi.marque({"session": {"tables": 9}}) == "MP" and moi.marque({"session": {"tables": 2}}) == "IMP"
assert moi.marque({"session": {}, "donnes": []}) == "IMP"
print("ok")
