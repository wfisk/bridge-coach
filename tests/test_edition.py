# -*- coding: utf-8 -*-
"""Les séances créées et modifiées dans Bridge Coach : .venv/bin/python -I tests/test_edition.py"""
import json, os, random, sys, tempfile
ESSAI = tempfile.mkdtemp()
os.environ["BRIDGE_COACH_DONNEES"] = ESSAI
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import edition as E, rapport

# les couleurs tapées : rangées, en français ou en anglais, chicane, erreurs en français
assert E.lire_couleur("r a 10 6") == "ARX6" == E.lire_couleur("KA T6") and E.lire_couleur("") == "-" == E.lire_couleur(" - ")
for faux, mot in (("AZ", "n'est pas une carte"), ("AA", "deux fois")):
    try: E.lire_couleur(faux); raise AssertionError(faux)
    except ValueError as e: assert mot in str(e)

import datetime
jour = datetime.datetime(2026, 11, 3, 14, 30, 12)
c = E.nouvelle_seance(jour)
data = E.lire(c)
assert os.path.basename(c) == "entrainement-2026-11-03.bc.json" and data["session"]["titre"] == "Entraînement 2026-11-03"
assert data["source"]["type"] == "saisie" and data["donnes"] == []
assert os.path.basename(E.nouvelle_seance(jour)) == "entrainement-2026-11-03-143012.bc.json"   # le nom est pris : l'heure en plus
assert E.modifiable(c) == (True, "")
assert E.ajouter_donne(c) == 1 and E.ajouter_donne(c) == 2
d = E.donne_de(E.lire(c), 2)
assert d["donneur"] == "E" and d["vul"] == "N-S" and d["a_completer"] and d["mains"]["N"] == "- - - -"

# une main tapée couleur par couleur, enregistrée tout de suite ; un doublon se voit
assert E.poser_couleur(c, 1, "N", 0, "akq2") == "ARD2"
E.poser_couleur(c, 1, "S", 0, "A")
_, doubles, _ = E.etat(E.donne_de(E.lire(c), 1))
assert doubles == [("♠", "A")]
E.poser_couleur(c, 1, "S", 0, "")
# compléter au hasard : la donne devient complète, double mort et par calculés
E.poser_couleur(c, 1, "N", 1, "ARD"); E.poser_couleur(c, 1, "N", 2, "ARD"); E.poser_couleur(c, 1, "N", 3, "AR2")
E.completer_au_hasard(c, 1, random.Random(3))
d = E.donne_de(E.lire(c), 1)
assert "a_completer" not in d and d["dm"] and d["par"] and d["hcp"]["N"] == 9 + 9 + 9 + 7 and d["mains"]["N"] == "ARD2 ARD ARD AR2"
assert sum(len(E.cartes(d["mains"][s])) for s in "NESO") == 52
# supprimer : les suivantes reprennent le numéro, l'analyse standard suit
rapport.ecrire_analyse(c, "standard", {"donnes": {"1": {"enc": []}, "2": {"enc": [["x"]]}}})
E.ajouter_donne(c); E.supprimer_donne(c, 1)
data = E.lire(c)
assert [d["n"] for d in data["donnes"]] == [1, 2] and data["donnes"][0]["donneur"] == "E"   # l'ancienne 2 garde son donneur
assert rapport.analyse_de(c, "standard")["donnes"] == {"1": {"enc": [["x"]]}}
# les versions : au plus une toutes les 10 minutes, restaurer garde la version du moment
vs = E.versions(c)
assert len(vs) == 1
E.ECART_VERSIONS = 0
E.ajouter_donne(c)
assert len(E.versions(c)) >= 2
E.restaurer(c, E.versions(c)[-1])
assert [d["n"] for d in E.lire(c)["donnes"]] == []                  # la toute première version : la séance vide
# une analyse de l'expert ne bloque plus la séance : la donne changée perd la sienne (le fichier d'avant va dans
# versions/), pas les autres
E.ECART_VERSIONS = 600                                        # seule l'analyse de l'expert force une copie
E.ajouter_donne(c); E.ajouter_donne(c)
rapport.ecrire_analyse(c, "expert", {"systeme": "sef-2024", "donnes": {"1": {"enc": [["a"]]}, "2": {"enc": [["b"]]}}})
quand = rapport.analyse_de(c, "expert")["fait_le"]
assert E.modifiable(c) == (True, "") and E.a_analyse_expert(c, 1) and not E.a_analyse_expert(c, 3)
avant = len(E.versions(c))
E.poser_couleur(c, 1, "N", 0, "A")
assert rapport.analyse_de(c, "expert")["donnes"] == {"2": {"enc": [["b"]]}} and rapport.analyse_de(c, "expert")["fait_le"] == quand
assert len(E.versions(c)) == avant + 1 and "1" in json.load(open(E.versions(c)[0]))["analyses"]["expert"]["donnes"]
E.poser_couleur(c, 1, "N", 0, "AR")                          # plus rien à retirer : pas de nouvelle copie forcée
assert len(E.versions(c)) == avant + 1
E.supprimer_donne(c, 1)                                       # la donne 2 devient la 1, son analyse de l'expert suit
assert rapport.analyse_de(c, "expert")["donnes"] == {"1": {"enc": [["b"]]}}
# les thèmes : chacun a sa famille et son niveau ; ceux d'enchères et de jeu de la carte sont réunis dans les mêmes donnes
import donnes as Dn
assert set(Dn.META) == set(Dn.THEMES) - {Dn.ALEATOIRE}
assert Dn.combiner([("Stayman", 2), ("L'impasse", 1), ("Squeeze", 2), (Dn.ALEATOIRE, 1)]) == \
    [("Stayman + L'impasse", 1), ("Stayman + Squeeze", 1), ("Squeeze", 1), (Dn.ALEATOIRE, 1)]
assert Dn.lire_quotas(["Stayman + L'impasse=2", "Inconnu=1"]) == [("Stayman + L'impasse", 2)]
assert "Évaluer sa main" in Dn.themes_de("encheres", 1) and "Squeeze" in Dn.themes_de("carte", 3)
print("ok")
