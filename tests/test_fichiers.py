# -*- coding: utf-8 -*-
"""Le fichier d'une séance (titre, nom proposé, en-tête, renommer, dupliquer, corbeille) et l'export (PBN, CSV,
Excel) : .venv/bin/python -I -X utf8 tests/test_fichiers.py"""
import csv, datetime, json, os, sys, tempfile, zipfile
ESSAI = tempfile.mkdtemp()
os.environ["BRIDGE_COACH_DONNEES"] = ESSAI
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import fichiers as F, exporter as X, rapport

# noms et titres
assert F.slug("Tournoi du Jeudi, après-midi !") == "tournoi-du-jeudi-apres-midi"
assert F.nettoyer_nom("Mon tournoi.bc.json") == "mon-tournoi"
assert F.date_longue(datetime.date(2026, 11, 1)) == "dimanche 1er novembre 2026"
assert (F.moment("09:15"), F.moment("14:00"), F.moment("19:30"), F.moment(None)) == ("matin", "après-midi", "soir", "")
data = {"session": {"date": "05/11/2026", "tables": 7, "heure": "14:00"}, "donnes": []}
t = F.titre_propose(data, "bws")
assert t == "Tournoi du jeudi 5 novembre 2026 (après-midi, 7 tables)", t
assert F.nom_propose(data, t, "bws") == "2026-11-05-tournoi-jeudi-apres-midi"
assert F.titre_propose({"session": {"date": "05/11/2026", "titre": "Bridge game"}}, "bws").startswith("Tournoi du jeudi")
pbn = {"session": {"date": "07/11/2026", "titre": "Tournoi du club"}}
assert F.titre_propose(pbn, "pbn") == "Tournoi du club – samedi 7 novembre 2026"
assert F.nom_propose(pbn, F.titre_propose(pbn, "pbn"), "pbn") == "2026-11-07-tournoi-club"
assert F.entrainement(datetime.datetime(2026, 11, 3, 10), ["Squeeze + Impasse", "Aléatoire"]) == \
    ("Entraînement du mardi 3 novembre 2026 – Squeeze, Impasse", "2026-11-03-entrainement-squeeze-impasse")

# une séance jouée, à la main : une donne, deux tables, deux paires
rapport.preparer_donnees()
dossier = os.path.join(rapport.SEANCES, "2026-11"); os.makedirs(dossier)
d1 = {"n": 1, "donneur": "N", "vul": "Personne", "mains": {"N": "- A9742 AX76 D984", "E": "AD974 83 V82 AV5",
      "S": "5 RDVX65 RD54 62", "O": "RVX8632 - 93 RX73"}, "hcp": {"N": 10, "E": 12, "S": 11, "O": 7},
      "par": {"score_ns": -100, "contrat": "6♥", "declarant": "S", "contre": True, "resultat": "-1"},
      "tables": [{"table": 1, "paire_ns": "1", "paire_eo": "2", "nom_ns": "AB/CD", "nom_eo": "EF/GH", "contrat": "4♥",
                  "declarant": "S", "resultat": "+1", "entame": "♠R", "levees": 11, "dm": 11, "score_ns": 450,
                  "imp_ns": 2, "pct_ns": 75.0}]}
seance = {"session": {"date": "05/11/2026", "tables": 1, "sections": ["A"], "mitchell": False}, "donnes": [d1],
          "paires": {"1": {"nom": "AB/CD", "pct": 62.5, "imp": 3}, "2": {"nom": "EF/GH", "pct": 37.5, "imp": -3}},
          "joueurs": {"1": [{"initiales": "AB", "nom": "Anne BLANC"}, {"initiales": "CD", "nom": "Claude DURAND"}]}}
origine = os.path.join(ESSAI, "6000010TPP05112026A.bws"); open(origine, "wb").write(b"essai")
F.nouvel_entete(seance, "bws", origine, "Tournoi du jeudi")
assert seance["source"]["fichier"] == "6000010TPP05112026A.bws" and seance["source"]["chemin"] == origine
assert seance["fichier"]["cree_le"] and seance["fichier"]["journal"][0]["quoi"] == "Importée de 6000010TPP05112026A.bws"
assert "fichier" not in seance["session"] and seance["session"]["titre"] == "Tournoi du jeudi"
c = os.path.join(dossier, "2026-11-05-tournoi-jeudi" + rapport.BC)
rapport.ecrire_bc(seance, c)
lu = rapport.lire_bc(c)
assert list(lu)[:2] == ["fichier", "source"] and lu["fichier"]["modifie_le"]
assert F.deja_importe(origine) == c and F.titre_de(c) == "Tournoi du jeudi" and F.proposer_pour(c) is None
assert F.nom_libre(dossier, "2026-11-05-tournoi-jeudi") == "2026-11-05-tournoi-jeudi-2"

# ce qui va avec : essais de Jouer, versions, rapports, dossier pour Claude
open(os.path.join(dossier, "2026-11-05-tournoi-jeudi-jeu.json"), "w").write("{}")
os.makedirs(os.path.join(dossier, "versions"))
open(os.path.join(dossier, "versions", "2026-11-05-tournoi-jeudi-v-2026-11-06-101010.bc.json"), "w").write("{}")
r = os.path.join(rapport.RAPPORTS, "2026-11"); os.makedirs(r)
for n in ("analyse-AB-CD", "comparaison", "analyse 2", "donnes-3-17-5", "releve-AB-CD", "releve-donne-12"):
    open(os.path.join(r, f"2026-11-05-tournoi-jeudi-{n}.pdf"), "w").write("%PDF")
open(os.path.join(r, "2026-11-05-tournoi-jeudi-2-analyse.pdf"), "w").write("%PDF")   # une autre séance : pas à elle
os.makedirs(F.dossier_claude(c))
assert len(F.pdfs(c)) == 6, F.pdfs(c)
import app
rp = app.rapports_de(c)
assert sorted(rp) == ["analyse", "comparaison", "donnes", "releve", "releve-donnes"] and rp["analyse"][0][1] == "AB/CD", rp
assert rp["donnes"][0][1] == "3, 17, 5" and rp["releve-donnes"][0][1] == "12" and rp["releve"][0][1] == "AB/CD"
assert app.args_rapports("choisir", [3, 5])[-1] == "--donnes=3,5" and "--a-revoir" in app.args_rapports("revoir")
assert app.titre_fenetre(c) == "Bridge Coach – Tournoi du jeudi"

# renommer : tout suit
n = F.renommer(c, "Jeudi au club")
assert os.path.basename(n) == "jeudi-au-club.bc.json" and not os.path.exists(c)
assert os.path.exists(os.path.join(dossier, "jeudi-au-club-jeu.json"))
assert os.path.exists(os.path.join(dossier, "versions", "jeudi-au-club-v-2026-11-06-101010.bc.json"))
assert sorted(os.listdir(r)) == ["2026-11-05-jeudi-au-club-analyse 2.pdf", "2026-11-05-jeudi-au-club-analyse-AB-CD.pdf",
                                 "2026-11-05-jeudi-au-club-comparaison.pdf", "2026-11-05-jeudi-au-club-donnes-3-17-5.pdf",
                                 "2026-11-05-jeudi-au-club-releve-AB-CD.pdf", "2026-11-05-jeudi-au-club-releve-donne-12.pdf",
                                 "2026-11-05-tournoi-jeudi-2-analyse.pdf"]
assert os.path.isdir(F.dossier_claude(n))
assert rapport.lire_bc(n)["fichier"]["journal"][-1]["quoi"] == "Renommée : 2026-11-05-tournoi-jeudi → jeudi-au-club"
try: F.renommer(n, ""); raise AssertionError
except ValueError: pass
F.changer_titre(n, "Le jeudi du club")
assert F.titre_de(n) == "Le jeudi du club"

# dupliquer : une nouvelle naissance, les analyses comprises, pas les essais
nc, tc = F.proposer_copie(n)
assert nc == "jeudi-au-club-copie" and tc == "Le jeudi du club (copie)"
cp = F.dupliquer(n, nc, tc)
x = rapport.lire_bc(cp)
assert x["session"]["titre"] == tc and len(x["fichier"]["journal"]) == 1 and "Copie de" in x["fichier"]["journal"][0]["quoi"]
assert not os.path.exists(os.path.join(dossier, "jeudi-au-club-copie-jeu.json"))

# exporter : PBN, CSV (point-virgule, virgule décimale, UTF-8 avec BOM), Excel
assert open(X.pbn(n), encoding="utf-8").read().startswith("% PBN")
f = X.csv_(n, "resultats")
lignes = list(csv.reader(open(f, encoding="utf-8-sig"), delimiter=";"))
assert lignes[0][:3] == ["Donne", "Table", "Paire N-S"] and lignes[1][13] == "75,0" and lignes[1][12] == "-450"
assert "Anne BLANC" not in open(f, encoding="utf-8-sig").read()
assert "Anne BLANC" in open(X.csv_(n, "paires", noms=True), encoding="utf-8-sig").read()
z = zipfile.ZipFile(X.excel(n))
assert {"xl/workbook.xml", "xl/worksheets/sheet4.xml", "[Content_Types].xml"} <= set(z.namelist())
wb = z.read("xl/workbook.xml").decode()
assert all(f'name="{s}"' in wb for s in ("Séance", "Donnes", "Résultats", "Paires"))
import xml.dom.minidom
for nom in z.namelist(): xml.dom.minidom.parseString(z.read(nom))   # chaque partie est du XML bien formé
assert X.colonne(0) == "A" and X.colonne(25) == "Z" and X.colonne(26) == "AA"
vide = dict(seance, donnes=[dict(d1, tables=[])])
cv = os.path.join(dossier, "vide" + rapport.BC); rapport.ecrire_bc(vide, cv)
try: X.csv_(cv, "resultats"); raise AssertionError
except ValueError as e: assert "pas été jouées" in str(e)

# une séance d'avant les titres : titre et nom proposés
vieux = os.path.join(dossier, "6000010TPP05112026A" + rapport.BC)
rapport.ecrire_bc({"session": {"date": "05/11/2026", "tables": 7}, "source": {"type": "bws"}, "donnes": [d1]}, vieux)
t, nom = F.proposer_pour(vieux)
assert t == "Tournoi du jeudi 5 novembre 2026 (7 tables)" and nom == "2026-11-05-tournoi-jeudi"
assert os.path.basename(F.adopter(vieux, t, nom)) == "2026-11-05-tournoi-jeudi.bc.json"

# la corbeille : tout part ensemble, rien n'est effacé
poubelle = F.corbeille(n)
assert not os.path.exists(n) and os.path.exists(os.path.join(poubelle, "jeudi-au-club.bc.json"))
assert os.path.exists(os.path.join(poubelle, "jeudi-au-club-jeu.json"))
assert len(os.listdir(os.path.join(poubelle, "rapports"))) == 6 and os.listdir(r) == ["2026-11-05-tournoi-jeudi-2-analyse.pdf"]
assert os.path.isdir(os.path.join(poubelle, "pour-claude")) and os.path.exists(cp)

# la remettre : la séance, ses parties jouées, ses rapports et ses versions reviennent ; la corbeille se vide
jetees = F.dans_la_corbeille()
assert len(jetees) == 1 and jetees[0][1] == "Le jeudi du club" and jetees[0][2] == "05/11/2026"
rendu = F.remettre(jetees[0][0])
assert rendu == n and os.path.exists(os.path.join(dossier, "jeudi-au-club-jeu.json"))
assert "2026-11-05-jeudi-au-club-comparaison.pdf" in os.listdir(r) and os.path.isdir(F.dossier_claude(n))
assert os.path.exists(os.path.join(dossier, "versions", "jeudi-au-club-v-2026-11-06-101010.bc.json"))
assert F.dans_la_corbeille() == [] and rapport.lire_bc(n)["fichier"]["journal"][-1]["quoi"] == "Remise de la corbeille"
F.dupliquer(n, "double", "Double")                      # un nom déjà pris à la place : on le dit, rien ne bouge
d2 = F.corbeille(os.path.join(dossier, "double" + rapport.BC)); F.dupliquer(n, "double", "Double")
try: F.remettre(d2); raise AssertionError
except ValueError as e: assert "déjà" in str(e) and os.path.isdir(d2)

# la sauvegarde : les séances et documents/, sans versions/ ni originaux .bws ni PDF
open(os.path.join(dossier, "2026-11-05-tournoi-jeudi.bws"), "w").write("x")
os.makedirs(os.path.join(ESSAI, "documents"), exist_ok=True); open(os.path.join(ESSAI, "documents", "exemple.json"), "w").write("{}")
zf = os.path.join(ESSAI, F.nom_sauvegarde())
k = F.sauvegarder(zf)
noms = zipfile.ZipFile(zf).namelist()
assert k == sum(1 for x in noms if x.endswith(rapport.BC)) >= 3 and "seances/2026-11/jeudi-au-club.bc.json" in noms
assert "seances/2026-11/jeudi-au-club-jeu.json" in noms and "documents/exemple.json" in noms
assert not any("versions" in x or x.endswith((".bws", ".pdf")) for x in noms)

# ce qui part chez Claude ne nomme pas le fichier d'origine
assert "fichier" not in app.seance_pour_claude(rapport.lire_bc(cp)) and "source" not in app.seance_pour_claude(rapport.lire_bc(cp))
print("ok")
