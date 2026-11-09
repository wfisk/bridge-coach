# -*- coding: utf-8 -*-
"""L'application : .venv/bin/python -I tests/test_app.py"""
import glob, os, sys, tempfile
ESSAI = tempfile.mkdtemp()
os.environ["BRIDGE_COACH_DONNEES"] = ESSAI             # jamais les vrais fichiers de l'utilisateur
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import app, rapport

# les fichiers de l'utilisateur sont hors du programme, créés au premier lancement
assert rapport.SEANCES.startswith(ESSAI) and rapport.RAPPORTS.startswith(ESSAI) and rapport.CONFIG.startswith(ESSAI)
assert not os.path.abspath(rapport.DONNEES).startswith(rapport.RACINE)
# l'ancien rangement : reports/ devient rapports/, <nom>-donnes.json devient <nom>.bc.json avec ses joueurs ;
# les analyses à part (-standard.json, -expert.json) entrent dans le .bc.json, les anciens fichiers vont dans versions/
import json
os.makedirs(os.path.join(ESSAI, "reports", "2026-10")); open(os.path.join(ESSAI, "reports", "2026-10", "a-diff.pdf"), "w").close()
os.makedirs(os.path.join(ESSAI, "seances", "2026-10"))
vieux = os.path.join(ESSAI, "seances", "2026-10", "tournoi")
json.dump({"session": {"date": "30/10/2026"}, "paires": {"6": {"nom": "?"}},
           "donnes": [{"n": 1, "tables": [{"paire_ns": 6, "paire_eo": 7, "nom_ns": "?", "nom_eo": "?"}]}]}, open(vieux + "-donnes.json", "w"))
json.dump({"6": "AM/BD", "noms": {"6": ["Anne Martin", "Bruno Durand"]}}, open(vieux + "-paires.json", "w"))
open(vieux + ".pdf", "w").close()
json.dump({"donnes": {"1": {"enc": []}}}, open(vieux + "-standard.json", "w"))
json.dump({"donnes": {"1": {"enc": [["x"]]}}}, open(vieux + "-expert.json", "w"))
json.dump({"donnes": {}}, open(vieux + "-expert-avant-2026-10-30-120000.json", "w"))
rapport.preparer_donnees()
assert all(os.path.exists(x) for x in (rapport.SEANCES, rapport.RAPPORTS, rapport.CONFIG))
assert os.path.exists(os.path.join(rapport.RAPPORTS, "2026-10", "a-diff.pdf")) and not os.path.exists(os.path.join(ESSAI, "reports"))
assert not os.path.exists(vieux + "-donnes.json") and not os.path.exists(vieux + "-paires.json")
bc = json.load(open(vieux + ".bc.json"))
assert list(bc)[:5] == ["format", "version", "source", "session", "joueurs"] and bc["source"]["type"] == "feuille-de-route"
assert bc["joueurs"]["6"] == [{"initiales": "AM", "nom": "Anne Martin"}, {"initiales": "BD", "nom": "Bruno Durand"}]
assert bc["donnes"][0]["tables"][0]["nom_ns"] == "AM/BD" and rapport.noms_complets(bc) == {"6": ["Anne Martin", "Bruno Durand"]}
assert bc["analyses"]["standard"]["donnes"] == {"1": {"enc": []}} and bc["analyses"]["expert"]["donnes"] == {"1": {"enc": [["x"]]}}
assert list(bc)[-1] == "analyses" and "fait_le" in bc["analyses"]["expert"]
rangement = os.path.join(os.path.dirname(vieux), "versions")
assert sorted(os.listdir(rangement)) == ["tournoi-expert-avant-2026-10-30-120000.json", "tournoi-expert.json", "tournoi-standard.json"]
assert not glob.glob(vieux + "-*.json")
assert rapport.joueurs_bws({"paires": {"3": {"nom": "AB/CD"}}}, {"3": ["Anne B", "Carl D"]}) == \
    {"3": [{"initiales": "AB", "nom": "Anne B"}, {"initiales": "CD", "nom": "Carl D"}]}
assert rapport.noms_complets({"joueurs": {"3": [{"initiales": "AB"}, {"initiales": "CD"}]}}) == {}

t = app.Travail()
app.lire_ligne(t, "Donne 1 sur 24\n")
assert t.fraction == 0 and t.texte == "Analyse de la donne 1 sur 24"
app.lire_ligne(t, "Donne 13 sur 24\n")
assert abs(t.fraction - app.PART_ANALYSE / 2) < 1e-9
app.lire_ligne(t, "Rapport prêt : /x/a-archive.pdf\n")
assert t.prets == ["/x/a-archive.pdf"] and t.fraction > app.PART_ANALYSE and t.texte == "Écriture des rapports"
app.lire_ligne(t, "ALERTE : donne 3\n")
assert len(t.prets) == 1
# jamais de trace Python à l'écran
assert app.message_erreur("Traceback (most recent call last):\n  x") == app.GENERIQUE and app.message_erreur("") == app.GENERIQUE
assert app.message_erreur("Ce fichier n'est pas lisible.\n") == "Ce fichier n'est pas lisible."
# le même nom pour un .bws, une séance simulée et une feuille de route
assert rapport.nom_seance("/a/2026-10-23-ma séance.bws") == "ma-séance" == rapport.nom_seance("ma séance.json") == rapport.nom_seance("ma séance.pdf")
# la séance ouverte est retenue d'un lancement à l'autre, et son nom va dans le titre de la fenêtre
assert app.ETAT.startswith(ESSAI) and app.seance_active() is None
f = os.path.join(ESSAI, "s.bc.json"); open(f, "w").close()
app.retenir(f); assert app.seance_active() == f
os.remove(f); assert app.seance_active() is None             # fichier disparu : rien
assert app.titre_fenetre("/a/b/s.bc.json") == "Bridge Coach – s.bc.json" and app.titre_fenetre(None) == "Bridge Coach"
# l'analyse de l'expert par Claude sur le web : le dossier préparé, puis l'import vérifié et fondu donne par donne
sc = os.path.join(rapport.SEANCES, "2026-10", "club.bc.json")
json.dump({"format": "bridge-coach", "source": {"type": "bws", "fichier": "6000010CLUB23102026A.bws"},
           "session": {"date": "23/10/2026", "titre": "Club des Lilas"},
           "joueurs": {"1": [{"initiales": "AM", "nom": "Anne Martin"}, {"initiales": "BD", "nom": "Bruno Durand"}]},
           "donnes": [{"n": 1}, {"n": 2}],
           "analyses": {"standard": {"systeme": "sef-2024", "donnes": {"1": {"enc": []}}, "fait_le": "2026-10-23T20:00:00"}}},
          open(sc, "w"))
dossier, consigne = app.preparer_pour_claude(sc)
assert os.listdir(dossier) == ["seance-du-2026-10-23.ai.json"]           # un seul fichier à donner à Claude
tout = json.load(open(os.path.join(dossier, "seance-du-2026-10-23.ai.json")))
assert tout["consigne"] == consigne and "seance-du-2026-10-23-expert.json" in consigne and "Décision serrée" in consigne
assert "systeme.md" in tout["documents"] and tout["analyse_standard"]["donnes"] == {"1": {"enc": []}}
texte = json.dumps(tout, ensure_ascii=False)                                        # ni noms, ni club, ni fichier d'origine
assert "Anne" not in texte and "Durand" not in texte and "Lilas" not in texte and "6000010" not in texte
assert tout["seance"]["joueurs"] == {"1": [{"initiales": "AM"}, {"initiales": "BD"}]} and "analyses" not in tout["seance"]
grille = [["–", "1♠", "passe", "passe"], ["passe", "", "", ""]]
x = os.path.join(ESSAI, "x-expert.json")
json.dump({"donnes": {"1": {"enc": grille, "notes": "a"}}}, open(x, "w"))
assert "1 donne importée" in app.importer_expert(sc, x) and "1 donnes sur 2" in app.importer_expert(sc, x)
json.dump({"donnes": {"2": {"enc": grille}}}, open(x, "w"))
assert "2 donnes sur 2" in app.importer_expert(sc, x)                 # la donne 1 reste
bc = json.load(open(sc))
assert set(bc["analyses"]["expert"]["donnes"]) == {"1", "2"} and bc["analyses"]["standard"]["donnes"] == {"1": {"enc": []}}
assert app.lire_analyses(sc)[1]["donnes"]["1"]["notes"] == "a"
assert len(glob.glob(os.path.join(rapport.SEANCES, "2026-10", "versions", "club-v-*.bc.json"))) >= 1   # le fichier d'avant gardé
assert not glob.glob(os.path.join(rapport.SEANCES, "2026-10", "club-*.json"))                     # plus de fichiers à part
for mauvais, mot in (('{"donnes": {"9": {"enc": []}}}', "pas dans cette séance"), ('{"donnes": {"1": {"enc": [["1♠"]]}}}', "quatre colonnes"),
                     ("pas du json", "lisible"), ('{"autre": 1}', "donnes")):
    open(x, "w").write(mauvais)
    try:
        app.importer_expert(sc, x); raise AssertionError(mauvais)
    except ValueError as e:
        assert mot in str(e), (mot, str(e))
# l'entame vient de la gauche du déclarant, avec une carte de sa main : sinon l'import refuse, en nommant la donne
json.dump({"format": "bridge-coach", "session": {"date": "23/10/2026"}, "donnes": [{"n": 1, "donneur": "N",
           "mains": {"N": "AR5 D84 RV7 A962", "E": "943 RD82 7 V8652", "S": "DV2 AV3 AD3 RD73", "O": "X876 X5 X986543 -"}}]}, open(sc, "w"))
for entame, ok in (({"joueur": "E", "carte": "♥R"}, True), ({"joueur": "O", "carte": "♥R"}, False), ({"joueur": "E", "carte": "♥A"}, False)):
    json.dump({"donnes": {"1": {"enc": grille, "entame": entame}}}, open(x, "w"))
    try:
        app.importer_expert(sc, x); assert ok, entame
    except ValueError as e:
        assert not ok and "Donne 1" in str(e) and "Est qui entame" in str(e), str(e)
# une analyse déjà rangée avec une carte absente : le rapport saute les cartes vues au lieu de s'arrêter
assert rapport.entame_valide({"mains": {"E": "943 RD82 7 V8652"}}, "N", "♥R") and not rapport.entame_valide({"mains": {"E": "943 RD82 7 V8652"}}, "N", "♦A")
assert rapport.cartes_vues({"n": 1, "mains": {"E": "943 RD82 7 V8652"}}, "1♠", "N", {"carte": "♦A"}) == ""
# un .bc.json (ou l'ancien -donnes.json) se lit tel quel ; une séance simulée reste aux tables, et le reste est refusé
assert rapport.nom_seance("/a/ma-séance.bc.json") == "ma-séance" == rapport.nom_seance("/a/ma-séance-donnes.json")
assert rapport.nom_seance("/a/entrainement-2026-11-01-224232.bc.json") == "entrainement-2026-11-01-224232"
essai = os.path.join(ESSAI, "x.bc.json")
def ecrire(texte):
    with open(essai, "w", encoding="utf-8") as f: f.write(texte)
ecrire('{"session": {"date": "23/10/2026"}, "donnes": [{"n": 1}]}')
assert rapport.donnes_pretes(essai)["alertes"] == [] and rapport.donnes_pretes("x.bws") is None
ecrire('{"tables": {}}')
assert rapport.donnes_pretes(essai) is None
ecrire('{"session": {"date": "02/11/2026"}, "donnes": []}')
try:
    rapport.donnes_pretes(essai); raise AssertionError
except SystemExit as e:
    assert "aucune donne" in str(e)
for mauvais in ("pas du json", '{"donnes": []}'):
    ecrire(mauvais)
    try:
        rapport.donnes_pretes(essai); raise AssertionError
    except SystemExit as e:
        assert "lisible" in str(e)
# les donnes : la répartition, l'ordre alphabétique, les lignes suivies par la barre
import donnes
assert donnes.lire_quotas(["Squeeze=4", "Aléatoire=8", "Inconnu=3", "Texas=0", "Stayman=x"]) == [("Squeeze", 4), ("Aléatoire", 8)]
noms = donnes.themes_tries()
assert noms[0] == "Aléatoire" and all(x in noms for x in ("Chelem", "Drury", "Roudi", "Squeeze")) and noms.index("Entame décisive") < noms.index("Grand chelem")
t = app.Travail(1.0, "Création de la donne")
app.lire_ligne(t, "Donne 2 sur 4\n"); app.lire_ligne(t, "Thème non trouvé : Squeeze, 1 donne(s)\n"); app.lire_ligne(t, "Fichier prêt : /x/y.bc.json\n")
assert t.fraction == .25 and t.texte == "Création de la donne 2 sur 4" and t.notes == ["Squeeze, 1 donne(s)"] and t.fichier == "/x/y.bc.json"
# le .pbn : Nord d'abord, rangs anglais, chicane vide
pbn = donnes.pbn(dict(session=dict(date="01/11/2026"), donnes=[dict(n=2, donneur="O", vul="N-S", theme="Texas", mains=dict(N="ARDV X - 2", E="- - - -", S="9 9 9 9", O="8 8 8 8"))]))
assert '[Dealer "W"]' in pbn and '[Vulnerable "NS"]' in pbn and '[Deal "N:AKQJ.T..2 ... 9.9.9.9 8.8.8.8"]' in pbn and '[Date "2026.11.01"]' in pbn
# le modèle des réglages donne les deux dossiers
assert open(rapport.CONFIG, encoding="utf-8").read().count("~/Documents/") == 2 and rapport.reglage("bridgemate", "").endswith("bridgemate-files")
# le tournoi proposé est le dernier fichier créé, pas le nom le plus récent
assert os.path.isfile(app.AIDE)
assert "<h1>Aide de Bridge Coach</h1>" in app.texte_aide() and "<style>" not in app.texte_aide()   # l'aide s'affiche dans la fenêtre
with open(rapport.CONFIG, "w") as f: f.write("[dossiers]\nbridgemate = seances\n")
for nom in ("ancien-01012026.bws", "nouveau-31122026.bws"): open(os.path.join(rapport.SEANCES, nom), "w").close()
app.creation = lambda f: 2 if "ancien" in f else 1
ordre = app.reglages()[0]
assert os.path.basename(ordre[0]) == "ancien-01012026.bws"
# donnes saisies : la ligne se relit à l'identique, Ouest se déduit, les erreurs sont dites
import donnes
s = "PAR6CKADV6532T953PVCX54KX874TVX842P7543CAD863KRTAR7PDX982CRV972K9TD6NVO"
x = donnes.lire_texte(s)
assert x["vul"] == "E-O" and x["donneur"] == "O" and x["mains"]["O"] == "DX982 RV972 9 D6"
assert donnes.texte_de(dict(x, n=1)) == s and donnes.lire_texte("par6 c kadv6532 t953 pvcx54kx874tvx842 p7543cad863krtar7")["mains"] == x["mains"]
print("ok")

# les filtres de fichiers sont acceptés par pywebview (une apostrophe dans la description les fait refuser sans bruit)
from webview.util import parse_file_type
for types in (app.TYPES_FICHIERS, app.TYPES_SEANCES, app.TYPES_IMPORT, app.TYPES_EXPERT):
    for f in types: parse_file_type(f)
# « Vous êtes » : vos tables sont repérées par votre nom complet, dans chaque séance
import moi
assert moi.ETAT == app.ETAT and moi.nom() is None
s = {"joueurs": {"1": [{"initiales": "AM", "nom": "MARTIN Anne"}, {"initiales": "BD", "nom": "DURAND Bruno"}],
                 "2": [{"initiales": "CL", "nom": "LEROY Claire"}]}}
assert moi.paires(s, "martin anne") == {"1"} and moi.paires(s, "") == set()
assert moi.a_joue({"paire_ns": "2", "paire_eo": "1"}, {"1"}) and not moi.a_joue({"paire_ns": "", "paire_eo": ""}, {"1"})
app.ecrire_etat(moi="MARTIN Anne"); assert moi.nom() == "MARTIN Anne" and moi.paires(s) == {"1"}
app.ecrire_etat(moi=None); assert moi.nom() is None
print("ok")
# les tables du meilleur au moins bon, vu de votre camp ; votre rang au-dessus du tableau
T = [dict(paire_ns="", paire_eo="", score_ns=-200, pct_ns=9), dict(paire_ns="3", paire_eo="2", score_ns=-100, pct_ns=50),
     dict(paire_ns="", paire_eo="", score_ns=110, pct_ns=89), dict(paire_ns="", paire_eo="", score_ns=-100, pct_ns=50)]
assert [t["score_ns"] for t in moi.ordre(T, {"2"})] == [-200, -100, -100, 110] and moi.ordre(T, {"2"})[1] is T[1]   # E-O : votre table d'abord à égalité
assert [t["score_ns"] for t in moi.ordre(T, set())] == [110, -100, -100, -200]                                       # sans vous : Nord-Sud
assert moi.votre_rang(T, {"2"}, lambda t: "3♠ S -2") == "Votre résultat : 2e ex aequo sur 4 (50 %) – meilleur : +200 (3♠ S -2)"
assert moi.votre_rang(T, set()) == ""
print("ok")
# le mouvement : vos tours, la ligne de chaque donne, l'ordre joué (le relais à sa place, puis les autres donnes)
M = dict(session=dict(mouvement=dict(paire="2", tours=[dict(tour=1, table=4, donnes=[4, 5], adversaires="3"),
                                                        dict(tour=2, table=6, donnes=[1, 2], adversaires=None, relais=True),
                                                        dict(tour=3, table=1, donnes=[3], adversaires="3")])),
         paires={"2": dict(nom="AB/CD", position="EO4"), "3": dict(nom="EF/GH", position="NS4")},
         donnes=[dict(n=k, tables=[dict(paire_ns="3", paire_eo="2", pct_ns=40)] if k in (3, 4, 5) else []) for k in range(1, 7)])
assert moi.parcours(M)[0] == dict(tour=1, table=4, donnes="4–5", adversaires="EF/GH (NS4)", pct="60 %")
assert moi.parcours(M)[1]["adversaires"] == "relais : pas de jeu" and moi.parcours(M)[2]["donnes"] == "3"
assert moi.tour_de(M, 4) == "Tour 1 · table 4 · AB/CD (EO4) contre EF/GH (NS4)" and "relais" in moi.tour_de(M, 2) and moi.tour_de(M, 6) == ""
assert [d["n"] for d in moi.ordre_des_donnes(M, {"2"})] == [4, 5, 1, 2, 3, 6]
assert [d["n"] for d in moi.ordre_des_donnes(M, {"3"})] == [1, 2, 3, 4, 5, 6] and moi.parcours({"session": {}}) == []
app.ecrire_etat(ordre_joue=True); assert moi.ordre_joue(); app.ecrire_etat(ordre_joue=False); assert not moi.ordre_joue()
print("ok")
