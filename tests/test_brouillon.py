# -*- coding: utf-8 -*-
"""Le Brouillon (brouillon.py) et l'ordre des donnes (edition.deplacer, donneur et vulnérabilité selon le numéro) :
une donne ajoutée emporte ses analyses et son origine, pas les tables ; elle se retire ; l'ordre change avec les
analyses et les parties de Jouer ; une séance importée ne se réorganise pas, sa copie si."""
import json, os, shutil, sys, tempfile
ESSAI = tempfile.mkdtemp(prefix="brouillon-")
os.environ["BRIDGE_COACH_DONNEES"] = ESSAI
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import rapport, edition, fichiers, brouillon as B

# une séance importée, avec deux analyses
rapport.preparer_donnees()
src = os.path.join(rapport.SEANCES, "2026-11", "tournoi.bc.json"); os.makedirs(os.path.dirname(src))
mains = {"N": "AR52 D84 RV7 A96", "E": "V3 ARX96 852 D72", "S": "D9 R7 AD9842 R76", "O": "X8764 V532 X63 V"}
donnes = [dict(n=k, donneur="NESO"[(k - 1) % 4], vul=v, mains=mains, hcp={}, tables=[{"table": 1}], par="x", dm={})
          for k, v in ((1, "Personne"), (2, "N-S"), (3, "E-O"))]
data = dict(session=dict(date="12/11/2026", titre="Tournoi du jeudi"), donnes=donnes, paires={}, alertes=[])
rapport.entete(data, "bws", "tournoi"); fichiers.nouvel_entete(data, "bws", None, "Tournoi du jeudi")
data["analyses"] = {"standard": {"systeme": "sef-2024", "donnes": {"2": {"enc": "coach 2"}, "3": {"enc": "coach 3"}}},
                    "expert": {"systeme": "sef-2024", "donnes": {"3": {"enc": "expert 3"}}}}
rapport.ecrire_bc(data, src)

assert not edition.modifiable(src)[0] and "Dupliquez" in edition.modifiable(src)[1]
b = B.assurer()
assert B.est_brouillon(b) and B.nombre() == 0 and edition.modifiable(b)[0] and B.assurer() == b
assert b in rapport.glob_seances("*" + rapport.BC)                       # il est dans la liste des séances

# ajouter : la donne, ses analyses, son origine ; pas les tables ; une seconde fois ne la double pas
assert B.ajouter(src, 3) == 1 and B.ajouter(src, 2) == 2 and B.ajouter(src, 3) == 1 and B.nombre() == 2
br = rapport.lire_bc(b)
assert br["donnes"][0]["origine"] == {"fichier": "tournoi", "n": 3, "titre": "Tournoi du jeudi", "date": "12/11/2026"}
assert br["donnes"][0]["tables"] == [] and br["donnes"][0]["vul"] == "E-O" and br["donnes"][0]["donneur"] == "S"
assert rapport.analyse_de(b, "expert")["donnes"] == {"1": {"enc": "expert 3"}}
assert rapport.analyse_de(b, "standard")["donnes"] == {"1": {"enc": "coach 3"}, "2": {"enc": "coach 2"}}
assert B.numero_de(src, 3) == 1 and B.numero_de(src, 1) is None

# réorganiser : les analyses et les parties de Jouer suivent
jeu = b[:-len(rapport.BC)] + "-jeu.json"
json.dump({"donnes": {"1": ["partie de la donne 3"]}, "en_cours": {"2": {"siege": "N"}}}, open(jeu, "w"))
assert edition.deplacer(b, 1, 2) == []                                    # sans l'option : rien ne change d'autre
br = rapport.lire_bc(b)
assert [d["origine"]["n"] for d in br["donnes"]] == [2, 3]
assert rapport.analyse_de(b, "expert")["donnes"] == {"2": {"enc": "expert 3"}}
assert json.load(open(jeu)) == {"donnes": {"2": ["partie de la donne 3"]}, "en_cours": {"1": {"siege": "N"}}}

# donneur et vulnérabilité selon le numéro : la donne 2 (venue de la 3, Sud, E-O) devient Est, N-S
assert edition.changeraient(b) == [1, 2]
assert edition.regler_par_numero(b, True) == [1, 2]
br = rapport.lire_bc(b)
assert (br["donnes"][1]["donneur"], br["donnes"][1]["vul"]) == ("E", "N-S")
assert "a_revoir" in rapport.analyse_de(b, "expert")["donnes"]["2"]       # l'expert gardé, à revoir
assert rapport.analyse_de(b, "standard")["donnes"] == {}                  # le coach se refait

# retirer, enregistrer sous, vider
B.retirer(src, 2); assert B.nombre() == 1 and B.numero_de(src, 3) == 1
nom, titre = B.proposer(); assert nom.endswith("-cours") and titre.startswith("Cours du ")
c = B.enregistrer_sous(nom, titre)
assert rapport.lire_bc(c)["source"]["type"] == "saisie" and edition.modifiable(c)[0] and B.nombre() == 1
B.vider(); assert B.nombre() == 0 and not os.path.exists(jeu)
try: B.enregistrer_sous("autre", "x"); assert False
except ValueError: pass

# une séance importée se duplique, et la copie se réorganise
cp = fichiers.dupliquer(src, "tournoi-copie", "Copie")
assert edition.modifiable(cp)[0] and edition.deplacer(cp, 3, 1) == []
assert [d["vul"] for d in rapport.lire_bc(cp)["donnes"]] == ["E-O", "Personne", "N-S"]
shutil.rmtree(ESSAI, ignore_errors=True)
print("ok")
