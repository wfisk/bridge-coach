# -*- coding: utf-8 -*-
"""Une page « Donne n° » du site de la FFB imprimée en PDF (ffb_pdf.py). Les pièces simples se vérifient toujours ;
la lecture complète, sur un vrai PDF quand il est sur l'ordinateur (BRIDGE_COACH_PDF_FFB, sinon le PDF d'essai des
Téléchargements) : il contient de vrais noms, il ne va jamais dans le dépôt."""
import os, sys, tempfile
os.environ["BRIDGE_COACH_DONNEES"] = tempfile.mkdtemp(prefix="ffb-pdf-")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import ffb_pdf as F

# la couleur d'un symbole : couleur dominante, puis la part de la case remplie (le losange est plus fin)
assert F._couleur((0, 0, 0), .5) == "♠" and F._couleur((228, 40, 10), .5) == "♥"
assert F._couleur((230, 105, 75), .37) == "♦" and F._couleur((10, 140, 70), .53) == "♣"
# les colonnes de la fiche ambulante : un mot va dans la colonne dont il dépasse le début
bornes = [(70, "ns"), (150, "eo"), (218, "contrat"), (254, "decl")]
assert F._colonne(bornes, 100) == "ns" and F._colonne(bornes, 230) == "contrat" and F._colonne(bornes, 60) is None
assert F._nombre("75,00 %") == 75.0 and F._nombre("—") is None
assert not F.est_page_ffb(__file__)

pdf = os.environ.get("BRIDGE_COACH_PDF_FFB") or os.path.expanduser("~/Downloads/test canon.pdf")
if os.path.exists(pdf):
    _, club, titre, donnes, _ = F.lire(pdf)
    d = donnes[0]
    assert "03/11/2026" in titre and d["n"] == 1 and d["donneur"] == "N" and d["vul"] == "Personne"
    assert d["mains"]["S"] == ["D", "A87", "ADV62", "9742"] and d["mains"]["O"] == ["R93", "R432", "X3", "ADV5"]
    assert d["optimum"]["N"]["♠"] == 8 and d["optimum"]["E"]["♣"] == 7
    assert len(d["lignes"]) == 9
    l = d["lignes"][2]                                    # une table coupée par la page : les noms se recollent
    assert l["contrat"] == "1 NT" and l["declarant"] == "S" and l["entame"] == "H2" and l["resultat"] == "-3"
    assert len(l["ns"]) == 2 and len(l["eo"]) == 2
    assert [x["contrat"] for x in d["lignes"]].count("2 S") == 2 and d["lignes"][4]["contrat"] == "2 D"
    s = F.seance(pdf)                                     # l'importeur des pages FFB en fait la séance, sans alerte
    assert len(s["donnes"][0]["tables"]) == 9 and not s["alertes"]
    print("ok (avec le PDF d'essai)")
else:
    print("ok (sans PDF d'essai : la lecture complète n'est pas vérifiée)")
