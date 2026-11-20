# -*- coding: utf-8 -*-
"""La carte de conventions (Réglages › Votre système) : .venv/bin/python -I -X utf8 tests/test_fiche_conventions.py"""
import os, sys, json, tempfile
ESSAI = tempfile.mkdtemp()
os.environ["BRIDGE_COACH_DONNEES"] = ESSAI
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import fiche_conventions as F

# des clés uniques ; la carte FFB SEF entière : chaque partie du recto, chaque ouverture du verso
cles = [i["cle"] for _, _, _, ls in F.TOUTES for i in ls]
assert len(cles) == len(set(cles)) == len(F.ITEMS)
assert {p for _, _, p, _ in F.TOUTES} <= {p for p, _ in F.PARTIES}
assert [o[1] for o in F.OUVERTURES] == ["1♣", "1♦", "1♥ / 1♠", "1SA", "2♣", "2♦", "2♥ / 2♠", "2SA", "3 à la couleur",
                                        "3SA", "4 à la couleur"]
for rid, _, _, cols in F.OUVERTURES:                     # contres négatifs sur les ouvertures de 1, le nombre de cartes
    for col, _ in F.COLONNES:                            # là où la carte en demande un
        attendu = (col != "cn" or rid in F.UN_PALIER) and (col != "mini" or bool(cols["mini"][0]))
        assert (f"ouv_{rid}_{col}" in F.ITEMS) == attendu, (rid, col)
assert F.texte("ouv_1sa_mini") == ""

# la feuille de prévisions de la FFB : ses trois parties, ses lignes, dans son ordre
assert [p for p, _ in F.FEUILLE] == ["Ouvertures", "Interventions", "Flanc"]
assert len(F.SUR_FEUILLE) == len(set(F.SUR_FEUILLE)) and all(c in F.ITEMS for c in F.SUR_FEUILLE)
for c in ("majeures5", "meilleure_mineure", "ouv_1sa_desc", "stayman_1sa", "texas_1sa", "ouv_2sa_desc", "stayman_2sa",
          "texas_2sa", "rectif_fittee", "deux_majeur", "chgt_2m_forcing", "ouv_2t_desc", "ouv_2t_rep", "ouv_2k_desc",
          "ouv_2k_rep", "ouv_3x_desc", "blackwood", "roudi", "drury", "lebensohl", "rubensohl", "quatrieme", "troisieme",
          "sa_forcing", "smi", "autres_conventions", "sa2", "sa2_rep", "int_couleur", "soutien_saut_barrage", "int_saut",
          "int_chgt_forcing", "saut_2", "saut_3", "contre_toutes", "ca_reponses", "bic_min_2k", "bic_min_2sa",
          "bic_maj_cue", "bic_maj_2sa", "bic_maj_3t", "def_sa_contre", "def_sa_2t",
          "def_sa_2k", "def_sa_2m", "def_sa_reveil", "sa4", "reveil_2sa", "reveil_couleur_limitee", "flanc_sa_entame",
          "sig_entame", "defausse_sa", "flanc_couleur_entame", "sig_entame_couleur", "sig_defausse"):
    assert c in F.SUR_FEUILLE, c
assert F.ITEMS["texas_1sa"]["type"] == "cases" and [o for o, _ in F.ITEMS["texas_1sa"]["options"]] == ["2♦", "2♥", "2♠", "2SA", "3♣"]
assert [o for o, _ in F.ITEMS["ouv_2t_desc"]["options"]] == ["Fort indéterminé", "Albarran"]
assert set(dict(F.ITEMS["sig_defausse"]["options"])) == {"SEF 2024", "Appel direct", "Pair-impair", "Italien", "Lavinthal"}
assert not F.reste([F.ITEMS["bic_maj_cue"]]) and F.reste([F.ITEMS["multi"]])      # le reste de la carte, sans la feuille

# tout s'ouvre déjà rempli comme le joue Bridge Coach : rien de vide ni « À convenir » ; des choix plutôt que du texte
for i in F.ITEMS.values():
    assert i["type"] in ("oui", "cases") or i["defaut"], i["cle"]
    assert "convenir" not in F.texte(i["cle"], defaut=True).lower(), i["cle"]
    if i["type"] == "choix": assert i["defaut"] in dict(i["options"]), i["cle"]
    assert i["incertain"] is False or i["incertain"] in F.POURQUOI, i["cle"]
assert all(F.ITEMS[c]["type"] != "texte" for c in F.SUR_FEUILLE)          # la feuille : rien à taper
assert F.valeur("ouv_1sa_desc") == ("15–17 H", False) and F.texte("ouv_1sa_desc") == "15–17 H, régulier"
assert F.valeur("texas_1sa") == (["2♦", "2♥", "2♠"], False) and F.texte("texas_1sa") == "2♦, 2♥, 2♠"
assert F.valeur("sig_entame")[0] == F.valeur("sig_entame_couleur")[0] == ["SEF 2024"]   # les signaux des robots (2026-11-20)
assert F.valeur("sig_defausse")[0] == ["SEF 2024"]       # défausse : parité, appel direct en urgence (src/signaux.py)
# le flanc : plusieurs cases sur chaque ligne, le choix de Bridge Coach seul coché au départ, et « Autre… »
for c in F.PLUSIEURS:
    assert F.ITEMS[c]["type"] == "cases" and F.ITEMS[c]["autre"] and len(F.ITEMS[c]["defaut"]) == 1, c
assert F.valeur("sig_entame_couleur", {"valeurs": {"sig_entame_couleur": "Appel direct"}}) == (["Appel direct"], True)
assert F._migrer({"sig_entame_couleur": "Appel direct", "sig_defausse": "Préférence"}) == {"sig_entame_couleur": ["Appel direct"],
                                                                                  "sig_defausse": ["Lavinthal"]}   # plus le choix par défaut depuis le 2026-11-20
assert F.valeur("def_sa_2t")[0] == "Landy" and F.valeur("blackwood")[0] == "5 clés 30-41" and F.valeur("drury")[0]
# la feuille en noir et blanc : un choix en gras sur fond gris clair, avec ☒ ; les autres simples, avec ☐
assert F.coche("Oui", True).startswith(f'<font backColor="{F.SURLIGNE}"><b>') and F.coche("Non", False) == "Non ☐"
assert F.cases_de("rectif_fittee", {}, str).count("backColor") == 1 and "<b>&nbsp;NON ☒" in F.cases_de("rectif_fittee", {}, str)
# le moteur, 2026-11-14 : rectification fittée sur 1SA (pas sur 2SA) ; sur le deux faible, 2SA relais par paliers,
# changement de couleur forcing, 3M barrage
assert F.valeur("rectif_1sa") == ("Oui", False) and "16–17 H" in F.texte("rectif_1sa") and F.a_verifier("rectif_1sa")
assert F.valeur("rectif_fittee") == (False, False)
assert F.valeur("ouv_2m_suite")[0] == "Par paliers" and "3♦ = minimum, belle couleur" in F.texte("ouv_2m_suite")
assert F.valeur("chgt_2m_forcing")[0] is True and F.valeur("soutien_3m")[0] == "Barrage"
assert all(c in F.SUR_FEUILLE for c in ("rectif_1sa", "ouv_2m_suite", "soutien_3m"))
# 4SA sans fit (2026-11-17) : Blackwood 3041 après une couleur naturelle, à vérifier (« à confirmer » dans le système)
assert F.valeur("bw_sans_fit") == ("Blackwood", False) and F.a_verifier("bw_sans_fit") and "bw_sans_fit" in F.SUR_FEUILLE
assert "dernière couleur nommée" in F.texte("bw_sans_fit") and F.ITEMS["bw_sans_fit"]["section"] == "chelem"
# les bicolores, une ligne par enchère, comme les joue Bridge Coach (regles.yaml, à confirmer)
assert "michaels" not in F.ITEMS and "bicolores" not in F.ITEMS
assert [F.valeur(c)[0] for c in ("bic_min_2k", "bic_min_2sa", "bic_maj_cue", "bic_maj_2sa", "bic_maj_3t")] == \
    ["Les deux majeures", "Les deux plus basses", "♣ et l'autre majeure", "Les mineures", "♦ et l'autre majeure"]
assert all(F.a_verifier(c) for c in ("bic_min_2k", "bic_maj_3t"))
assert "<b>&nbsp;précisés ☒&nbsp;</b>" in F.michaels_feuille({}, str) and "non précisés ☐" in F.michaels_feuille({}, str) and "3♣ = ♦ et l'autre majeure" in F.michaels_feuille({}, str)
assert F._migrer({"michaels": "Non précisés"}) == {"bic_maj_cue": "L'autre majeure et une mineure"}
assert F.a_verifier("entame_petites") and not F.a_verifier("sig_atout") and F.a_verifier("q4_cue") == F.POURQUOI["ffb"]

# un choix proposé, « Autre… » (un texte à soi), des cases, et le retour au standard
F.changer("ouv_1sa_desc", "14–16 H"); assert F.valeur("ouv_1sa_desc") == ("14–16 H", True) and not F.autre("ouv_1sa_desc")
F.changer("ouv_1sa_desc", "16–18 H, régulier"); assert F.autre("ouv_1sa_desc") and F.texte("ouv_1sa_desc") == "16–18 H, régulier"
F.changer("ouv_1sa_desc", "15–17 H, régulier"); assert F.valeur("ouv_1sa_desc")[1] is False     # le texte du standard
F.changer("texas_1sa", ["2♥", "2♦"]); assert F.valeur("texas_1sa") == (["2♦", "2♥"], True)
F.changer("texas_1sa", ["2♠", "2♥", "2♦"]); assert F.valeur("texas_1sa")[1] is False
F.changer("texas_1sa", []); assert F.texte("texas_1sa") == "Aucun"; F.changer("texas_1sa", ["2♦", "2♥", "2♠"])
F.changer("autres_conventions", "Multi 2♦"); assert F.texte("autres_conventions") == "Multi 2♦"
F.changer("autres_conventions", F.RIEN); assert "valeurs" not in F.lire()
F.changer("sig_defausse", ["Pair-impair", "Lavinthal"])
assert F.valeur("sig_defausse") == (["Pair-impair", "Lavinthal"], True) and not F.autre("sig_defausse")
F.changer("sig_defausse", ["Lavinthal", "Défausse paire : appel"])
assert F.libre_de("sig_defausse") == "Défausse paire : appel" and F.autre("sig_defausse")
f_ = F.cases_de("sig_defausse", F.lire(), str)
assert f_.count("backColor") == 1 and "Pair-impair ☐" in f_ and "<b>Défausse paire : appel</b>" in f_   # « Autre » : gras seul
assert "<b>&nbsp;Lavinthal ☒&nbsp;</b>" in F.coches_texte("sig_defausse", F.lire(), str)
F.changer("sig_defausse", ["SEF 2024"]); assert "valeurs" not in F.lire()   # revenu au choix de Bridge Coach

# le fichier de la version 1.13 se lit : « joueurs » sur une ligne, « conventions » à part, des Oui / Non devenus des choix
os.makedirs(os.path.dirname(F.chemin()), exist_ok=True)
json.dump({"joueurs": "MARTIN Anne et BERNARD Henri", "accords": "Landy sur 1SA",
           "conventions": {"landy": True, "drury": False, "stayman": True, "majeures5": False},
           "valeurs": {"sig_atout": "Parité", "sig_defausse": "Préférence", "systeme": "SEF 2024, 1SA 14–16 H"}},
          open(F.chemin(), "w", encoding="utf-8"))
x = F.lire()
assert (x["nom1"], x["prenom1"], x["nom2"], x["prenom2"]) == ("MARTIN", "Anne", "BERNARD", "Henri")
assert "joueurs" not in x and "joueur1" not in x and "conventions" not in x
assert x["valeurs"] == {"sig_atout": "Parité", "systeme": "SEF 2024, 1SA 14–16 H", "drury": False,
                        "majeures5": "Majeure 4e", "sig_defausse": ["Lavinthal"]}, x["valeurs"]   # Landy (2026-11-19) ; la préférence n'est plus le choix de Bridge Coach (2026-11-20)
assert F.valeur("def_sa_2t")[0] == "Landy" and not F.a_verifier("drury")    # changé : plus « à vérifier »
F.changer("drury", True)                                  # la première écriture range tout dans « valeurs »
y = json.load(open(F.chemin(), encoding="utf-8"))
assert "conventions" not in y and "joueurs" not in y and y["nom1"] == "MARTIN" and "drury" not in y["valeurs"]
F.changer_entete(classement1="45", classement2="38", niveau="Promotion")
assert F.joueurs(F.lire()) == "MARTIN Anne (IV 45) et BERNARD Henri (IV 38)"
# les noms proposés : seulement là où rien n'est écrit ; le partenaire de la séance
assert F.separer_nom("DE LA TOUR Marie-Claire") == ("DE LA TOUR", "Marie-Claire") and F.separer_nom("Anne Martin") == ("MARTIN", "Anne")
assert F.proposer_joueurs("DUPONT Jean", "DURAND Paul")["nom1"] == "MARTIN"
seance = {"joueurs": {"3NS": [{"nom": "DUPONT Jean", "initiales": "JD"}, {"nom": "DURAND Paul", "initiales": "PD"}]}}
assert F.partenaire_de(seance, "DUPONT Jean") == "DURAND Paul" and F.partenaire_de(None, "DUPONT Jean") is None
F.tout_remettre()
x = F.lire()
assert "valeurs" not in x and x["nom1"] == "MARTIN" and x["classement2"] == "38" and x["accords"] == "Landy sur 1SA"
assert x["niveau"] == "Promotion"                        # préremplir : les noms, les IV, le niveau, les accords restent

# les deux PDF : écrits dans documents/, lisibles, rangés comme la feuille (fiche) et comme la carte (FFB)
F.changer("ouv_1sa_desc", "14–16 H"); F.changer("def_sa_2t", "Landy"); F.changer("rois", "En Baron")
F.changer("texas_1sa", ["2♦", "2♥"]); F.changer("sig_defausse", ["Pair-impair", "Lavinthal"])
import pypdfium2
f = F.pdf_ffb()
assert f.endswith(os.path.join("documents", "carte-de-conventions-ffb.pdf")) and open(f, "rb").read(4) == b"%PDF"
doc = pypdfium2.PdfDocument(f)
assert len(doc) == 2                                     # la carte SEF complète, recto verso
recto, verso = (p.get_textpage().get_text_range() for p in doc)
assert "FEUILLE DE PRÉVISIONS" not in recto + verso      # un document par bouton
e = F.pdf_feuille()                                      # la feuille de prévisions, une page
assert e.endswith(os.path.join("documents", "feuille-de-previsions.pdf")) and open(e, "rb").read(4) == b"%PDF"
assert len(pypdfium2.PdfDocument(e)) == 1
feuille = pypdfium2.PdfDocument(e)[0].get_textpage().get_text_range()
assert "pages 2 et 3" not in feuille
for f_, txt_ in ((f, recto + verso), (e, feuille)):       # les adversaires voient ces feuilles : ni le programme ni l'auteur
    assert "Bridge Coach" not in txt_ and "Établie le" in txt_
    assert "Bridge Coach" not in (pypdfium2.PdfDocument(f_).get_metadata_dict().get("Author") or "")
for mot in ("FEUILLE DE PRÉVISIONS", "INTERVENTIONS", "FLANC", "NOM : MARTIN", "PRÉNOM : Anne", "IV : 45", "IV : 38",
            "Méthode de base : SEF 2024", "Compétition : Promotion", "Landy ☒", "14–16 H ☒", "SEF 2024 ☒",
            "NOS ACCORDS PARTICULIERS", "Landy sur 1SA", "Roudi ☒", "Michael's Cue-bid", "précisés ☒",
            "2SA = Les deux plus basses", "4SA sans fit", "Blackwood ☒"):
    assert mot in feuille, mot
assert feuille.index("INTERVENTIONS") < feuille.index("FLANC")
for mot in ("MARTIN Anne", "BERNARD Henri", "ENCHÈRES COMPÉTITIVES", "ENTAMES ET SIGNALISATION", "RÉSUMÉ DU SYSTÈME",
            "Baron", "Landy", "Rayez les conventions non jouées", "14–16 H", "Texas sur 1SA"):
    assert mot in recto, mot
assert "Pair-impair ☒" in recto and "Lavinthal ☒" in recto           # la carte complète : les deux cases cochées
for mot in ("OUVERTURE", "CONTRES", "SUITE des ENCHÈRES", "14–16 H", "Landy sur 1SA"):
    assert mot in verso, mot
g = F.pdf_partenaire()
assert g.endswith(os.path.join("documents", "fiche-pour-mon-partenaire.pdf")) and open(g, "rb").read(4) == b"%PDF"
texte = "".join(p.get_textpage().get_text_range() for p in pypdfium2.PdfDocument(g))
for mot in ("Enchères de bicolore sur 1♣ / 1♦", "Enchères de bicolore sur 1♥ / 1♠", "Le cue-bid (2♥ / 2♠)",
            "Trèfle et l'autre majeure", "Nos conventions", "MARTIN Anne (IV 45)", "en compétition, utilisez la feuille FFB", "Compétition : Promotion", "Ouvertures", "Interventions", "Flanc", "Sur ouverture de 1SA fort",
            "14–16 H", "Nos choix hors SEF standard", "SEF standard : 15–17 H, régulier", "À vérifier ensemble",
            "Landy sur 1SA", "Pair-impair ☒", "Lavinthal ☒"):
    assert mot in texte, mot
assert "Bridge Coach" not in texte and "Bridge Coach" not in (pypdfium2.PdfDocument(g).get_metadata_dict().get("Author") or "")
assert texte.index("Ouvertures") < texte.index("Interventions") < texte.index("Flanc")
assert F.pdf().endswith("carte-de-conventions-ffb.pdf")  # l'ancien appel : les deux PDF

# les noms complets ne vont jamais dans les fichiers pour Claude
import question_expert, inspect
assert "fiche_conventions" not in inspect.getsource(question_expert)
print("ok")
