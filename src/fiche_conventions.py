# -*- coding: utf-8 -*-
"""Réglages › Votre système : la carte de conventions de la paire, toute la carte FFB SEF 2024, modifiable, et deux PDF.

La page demande tout ce que porte la carte officielle de la FFB (feuille SEF 2024), rangé comme sur la carte : au recto
le nom et le classement des joueurs, le résumé du système (principes, ouvertures fortes, barrages, après un contre d'appel
du n° 2, chelem), les enchères compétitives, les entames et la signalisation, la case des conventions (« rayez les
conventions non jouées ») ; au verso le tableau des ouvertures (artificielle, nombre minimum de cartes, description,
contres négatifs, réponses, suite des enchères, changements après intervention et passe).

Deux PDF (2026-11-14) :
- pdf_ffb() : la carte FFB, recto verso, A4 à l'italienne, disposée comme la carte officielle ;
- pdf_partenaire() : une fiche courte pour en parler avec un partenaire, dans l'esprit des feuilles de club (des
  questions, Oui / Non), avec ce que la paire joue autrement que Bridge Coach et ce qui reste à vérifier ensemble.

Chaque ligne part de ce que joue Bridge Coach (systems/sef-2024/, écrit ici pour un joueur). Une ligne que le système
marque « à confirmer » est « à vérifier » ; une ligne que Bridge Coach ne décrit pas reprend la carte FFB SEF et est
« à vérifier » aussi ; une convention que la carte SEF joue et Bridge Coach non est « à vérifier ». Seules les lignes
changées sont gardées, dans <dossier de travail>/documents/fiche-conventions.json (la sauvegarde l'emporte) :
« Revenir à Bridge Coach » efface le changement. Les noms complets n'en sortent jamais. La fiche ne change pas ce que
jouent les robots.

Le fichier de la version 1.13 se lit tel quel : « joueurs » (une ligne) devient les deux noms, « conventions » (Oui / Non)
rejoint « valeurs » à la première écriture ; les clés d'avant gardent leur nom.
"""
import json, os, datetime, re

import rapport

# Pourquoi « à vérifier » (la clé « incertain » de chaque ligne)
POURQUOI = {
    True: "Le système de Bridge Coach marque ce point « à confirmer » : relisez-le avec votre partenaire",
    "ffb": "Bridge Coach ne décrit pas ce point : la ligne reprend la carte FFB SEF, vérifiez-la avec votre partenaire",
    "sef": "La carte FFB SEF joue ce point autrement que Bridge Coach : décidez-en avec votre partenaire",
}


def O(cle, titre, desc, defaut, inc=False):
    """Une convention, Oui ou Non."""
    return dict(cle=cle, type="oui", titre=titre, desc=desc, defaut=bool(defaut), incertain=inc, court=True)


def T(cle, titre, defaut, inc=False, court=False):
    """Une ligne de texte (court : sur la fiche pour le partenaire)."""
    return dict(cle=cle, type="texte", titre=titre, desc="", defaut=defaut, incertain=inc, court=court)


# Le recto de la carte. (id, titre de la section, colonne de la carte, [lignes]). Les colonnes : « competitives »
# (à gauche), « entames » et « conventions » (au milieu), « resume » (à droite, sous le nom et le classement).
SECTIONS = [
    # ---------------------------------------------------------------- RÉSUMÉ DU SYSTÈME
    ("principes", "Principes de base et style général", "resume", [
        T("systeme", "Méthode de base", "SEF 2024", court=True),
        O("majeures5", "Majeures 5e", "1♥ / 1♠ : 5 cartes au moins", True),
        O("meilleure_mineure", "Meilleure mineure", "1♣ / 1♦ : la mineure la plus longue, 3 cartes au moins", True, True),
        O("spoutnik", "Contre Spoutnik", "Après leur intervention : la ou les majeures non nommées", True),
        O("stayman", "Stayman", "2♣ sur 1SA, 3♣ sur 2SA : demande des majeures 4e", True),
        O("texas", "Texas", "2♦ / 2♥ sur 1SA, 3♦ / 3♥ sur 2SA : transfert vers la majeure", True),
        O("quatrieme", "Quatrième couleur forcing", "La 4e couleur du répondant : forcing, 11 H et plus", True),
        T("tiers", "En 3e et 4e position",
          "En 3e : dès 8 H avec la règle des 20, ou 10 H et neuf cartes dans les majeures ; en 4e : 12 H, ou 10–11 H "
          "avec une 6e ou la règle des 15"),
    ]),
    ("fortes", "Ouvertures fortes", "resume", [
        O("deux_forts", "2♣ fort, 2♦ forcing de manche", "Les deux ouvertures fortes du SEF", True, True),
    ]),
    ("barrages", "Ouvertures de barrage", "resume", [
        O("deux_faibles", "Deux faibles", "2♥ / 2♠ : 6 cartes, main faible", True, True),
        O("barrages", "Barrages", "Au palier de 3 : 7 cartes, main faible", True, True),
        O("multi", "Multi 2♦", "2♦ : un deux faible en majeure, ou une main forte", False),
    ]),
    ("contre_n2", "Après un contre d'appel du n° 2", "resume", [
        T("cn2_couleur", "Changement de couleur", "1 sur 1 forcing ; à saut : barrage", "ffb", court=True),
        T("cn2_surcontre", "Surcontre", "10 H et plus", "ffb"),
        T("cn2_majeure", "Après une ouverture majeure",
          "Changement de couleur à double saut = splinter ; à saut en mineure = enchère de rencontre", "ffb"),
    ]),
    ("chelem", "Enchères de chelem", "resume", [
        O("blackwood", "Blackwood 5 clés 30-41", "4SA : les clés (les quatre as et le roi d'atout) ; 5♣ = 3 ou 0, 5♦ = 4 ou 1",
          True),
        O("controles", "Contrôles", "Après un fit, on nomme ses as, rois, singletons et chicanes", True),
        O("quantitatif", "4SA quantitatif", "Sur 1SA et 2SA : invitation au chelem", True),
        O("splinter", "Splinter", "Saut dans une couleur courte : fit et singleton ou chicane", False, "sef"),
        T("dame_atout", "Demande de la dame d'atout", "Après 5♣ / 5♦, la couleur suivante (hors atout)", True, court=True),
        T("rois", "Demande des rois", "5SA, toutes les clés promises : 6♣ = 0 roi, 6♦ = 1, 6♥ = 2, 6♠ = 3 (hors roi d'atout)",
          True, court=True),
        T("bw_intervention", "Intervention sur le Blackwood", "DOPI : contre = 0 clé, passe = 1 clé", "ffb"),
    ]),
    # ---------------------------------------------------------------- ENCHÈRES COMPÉTITIVES (tout est à confirmer)
    ("interventions", "Interventions", "competitives", [
        T("int_couleur", "Interventions", "Naturelles : au palier de 1, 5 cartes et 8–16 H (10 si la couleur est pauvre) ; "
          "au palier de 2, bonne 5e ou 6e et 11–16 H ; saut : faible, 6 cartes", True, court=True),
        T("int_reponses", "Réponses à l'intervention", "Soutien 7–10 DH au plus bas ; cue-bid de l'ouverture : fit et 11+ ; "
          "sans fit : SA avec arrêt ou couleur 5e", True, court=True),
        T("int_saut", "Saut dans une nouvelle couleur en réponse", "Enchère de rencontre", "ffb"),
        T("int_reveil", "En réveil, par une couleur", "Les mêmes enchères avec 3 points de moins", True),
        T("bicolores", "Bicolores 5-5", "Sur 1♣ / 1♦ : 2♦ = les majeures, 2SA = les deux couleurs libres les plus basses ; "
          "sur 1♥ / 1♠ : cue-bid = ♣ et l'autre majeure, 2SA = les mineures, 3♣ = ♦ et l'autre majeure ; 8–18 H, alertés",
          True, court=True),
        O("sa_bicolore", "2SA bicolore", "Sur leur ouverture : les deux couleurs les plus basses libres", True, True),
        O("cue_bid", "Cue-bid de soutien", "Leur couleur : soutien du partenaire et force", True, True),
        O("loi", "Loi des levées totales", "Disputer jusqu'au palier égal au nombre d'atouts moins 6", True),
    ]),
    ("contre_appel", "Contre d'appel", "competitives", [
        O("contre_appel", "Contre d'appel", "Court dans leur couleur, les autres couleurs", True),
        T("ca_style", "Style général", "12 H et plus, court dans leur couleur, 3 cartes au moins dans les majeures libres ; "
          "ou 17 H et plus, toute forme", True, court=True),
        T("ca_reponses", "Réponses", "La meilleure couleur (majeure 4e d'abord) au plus bas avec 0–8 H, à saut avec 9–11, "
          "la manche avec 12 ; 1SA avec 6–9 H et un arrêt", True),
        T("ca_reveil", "En réveil", "3 points de moins : dès 9 H", True),
        T("bic_reveil", "Bicolores en réveil", "Les mêmes qu'en 2e position", True),
    ]),
    ("sa_intervention", "Intervention à 1SA", "competitives", [
        T("sa2", "En 2e position", "15–18 H, régulier, arrêt dans leur couleur", True, court=True),
        T("sa2_rep", "Réponses du partenaire", "Comme sur une ouverture de 1SA : Stayman, texas", True),
        T("sa4", "En réveil (4e position)", "12–15 H (3 points de moins)", True),
        T("sa4_rep", "Réponses du partenaire", "Comme en 2e position", True),
    ]),
    ("quatrieme_position", "Intervention en 4e position", "competitives", [
        T("q4_cue", "Après deux couleurs nommées, le cue-bid de l'ouverture",
          "Bicolore 5-5 constructif des deux autres couleurs", "ffb"),
        T("q4_2sa", "2SA", "Bicolore 5-5 défensif des deux autres couleurs", "ffb"),
        T("q4_contre", "Contre", "L'ouverture et les deux autres couleurs, 4-4", "ffb"),
    ]),
    ("defense_sa", "Défense contre le SA fort", "competitives", [
        T("dsa", "Sur leur 1SA", "Couleur 6e naturelle au palier de 2, dès 8 H ; contre = 15 H et plus, punitif", True,
          court=True),
        T("dsa_contre", "Après notre 1SA contré", "Contre artificiel : on l'oublie ; contre punitif : sauvetage", "ffb"),
    ]),
    ("defense_2f", "Défense contre le deux faible", "competitives", [
        T("d2_contre", "Contre d'appel", "Avec la majeure libre 4e, avant une couleur au palier de 3 ; en réveil dès 10 H",
          True, court=True),
        T("d2_2sa", "2SA", "16–18 H, naturel, arrêt", "ffb"),
        T("d2_cue", "Cue-bid de leur majeure", "Demande en priorité un arrêt pour jouer 3SA", "ffb"),
        T("d2_4m", "4♣ / 4♦", "L'autre majeure 5e et la mineure nommée 5e", "ffb"),
        T("d2_rep", "Réponses au contre", "La meilleure couleur ; 2SA : mini cue-bid, 8 H et plus", "ffb"),
    ]),
    # ---------------------------------------------------------------- ENTAMES ET SIGNALISATION
    ("a_la_couleur", "À la couleur", "entames", [
        T("entame_couleur", "Entame", "Celle du partenaire ; sinon une séquence ; contre une couleur, jamais sous un as ; "
          "un singleton pour couper", court=True),
        T("sig_defausse", "Défausse", "Préférence : dans une couleur dont on ne veut pas ; haute = la plus chère des deux "
          "autres, basse = la moins chère", court=True),
        T("entame_as", "Sur l'entame de l'as", "Pair-impair, comme sur toute entame du partenaire"),
    ]),
    ("a_sans_atout", "À sans-atout", "entames", [
        T("entame_sa", "Entame", "Celle du partenaire ; sinon la plus longue hors de leurs couleurs (4 cartes au moins), "
          "4e meilleure", court=True),
        T("defausse_sa", "Défausse", "Préférence, comme à la couleur"),
    ]),
    ("signalisation", "Signalisation", "entames", [
        T("sig_entame", "Sur l'entame du partenaire", "Pair-impair : impaire = continuez ; paire = changez, haute (7 et plus) "
          "vers la plus chère des deux autres couleurs, basse vers la moins chère", court=True),
        T("sig_parite", "Quand le déclarant mène", "Parité : grosse puis petite avec un nombre pair, la plus petite avec un "
          "nombre impair", court=True),
        T("sig_atout", "À l'atout", "Pas de signal"),
    ]),
    ("attaque", "Attaque en cours du jeu", "entames", [
        T("attaque_couleur", "À la couleur", "La tête d'une séquence ; sinon comme à l'entame", True),
        T("attaque_sa", "À sans-atout", "La tête d'une séquence ; sinon comme à l'entame", True),
    ]),
    ("cartes_entame", "Les cartes d'entame", "entames", [
        T("entame_sequence", "Séquence", "La tête (R de RD, D de DV) ; l'as de AR", court=True),
        T("entame_honneur", "Avec un honneur", "4e meilleure ; la plus petite de trois cartes", court=True),
        T("entame_petites", "Sans honneur", "Doubleton : la plus haute ; trois petites : la plus haute ; quatre petites : "
          "la deuxième", True, court=True),
    ]),
    # ---------------------------------------------------------------- CONVENTIONS (rayez les conventions non jouées)
    ("conventions", "Conventions", "conventions", [
        O("fit_2sa", "2SA fitté", "Sur 1♥ / 1♠, même après intervention : fit par 3 cartes, 10–12 H", False, "sef"),
        O("fit_3sa", "3SA fitté", "Sur 1♥ / 1♠ : fit par 4 cartes, main régulière de manche", False),
        O("roudi", "Roudi", "2♣ du répondant après la redemande à 1SA : demande", False),
        O("landy", "Landy", "2♣ sur leur 1SA : les deux majeures", False),
        O("landik", "Landik", "Après 1♣ / 1♦ – passe – 1SA : 2♣ = les deux majeures", False),
        O("drury", "Drury", "2♣ fitté d'un partenaire qui a passé, sur 1♥ / 1♠ : 3 atouts (ou 4 sans courte), 11+ HLD", True),
        O("michaels", "Michaels précisé", "Sur 1♥ / 1♠ : le cue-bid = ♣ et l'autre majeure, 3♣ = ♦ et l'autre majeure",
          True, True),
        O("troisieme", "3e couleur forcing", "La troisième couleur nommée par la paire : forcing", False),
        O("rubensohl", "Rubensohl", "Après leur intervention sur 1SA : les enchères au palier de 3 sont des texas", False),
        O("lebensohl", "Lebensohl", "2SA après leur intervention sur 1SA, ou leur deux faible contré", False),
        O("truscott_majeur", "Truscott majeur", "Après leur contre d'appel de 1♥ / 1♠ : 2SA = soutien 4 cartes, 10 H et plus",
          False, "sef"),
        O("truscott_mineur", "Truscott mineur", "La même idée après leur contre d'appel de 1♣ / 1♦", False),
        O("super_truscott", "Super Truscott", "Une variante du Truscott, à préciser", False),
        O("mini_maxi", "Mini-Maxi", "À préciser", False),
        O("misere_doree", "Misère dorée", "À préciser", False),
        O("chasse_croise", "Chassé-croisé", "Sur 1SA et 2SA : les texas mineurs", False, "sef"),
        O("convention_2012", "Convention 2012", "Sur 1SA : la suite des texas mineurs", False, "sef"),
        O("mixed_raise", "Mixed raise", "Soutien à saut : 4 atouts et 7–10 points", False),
    ]),
]

# Le verso : le tableau des ouvertures. (id, ouverture, artificielle ?, {colonne: (ce que joue Bridge Coach, incertain)})
# La feuille de prévisions de la FFB (2026-11-14, l'image que l'utilisateur a donnée) : ses lignes qui ne sont pas
# déjà sur la carte. Elles vont dans la section de la carte où la carte FFB les imprime.
def C(cle, titre, options, defaut, inc=False):
    """Des cases à cocher, plusieurs à la fois (les texas proposés…) : la valeur est la liste des cases cochées."""
    return dict(cle=cle, type="cases", titre=titre, desc="", options=[(o, o) for o in options], defaut=list(defaut),
                incertain=inc, court=True)


AJOUTS = {
    "principes": [
        T("stayman_1sa", "Stayman sur 1SA", "", True, court=True),
        C("texas_1sa", "Texas sur 1SA", ["2♦", "2♥", "2♠", "2SA", "3♣"], ["2♦", "2♥", "2♠"], True),
        T("rectif_1sa", "Rectification fittée sur 1SA", "", True, court=True),
        T("stayman_2sa", "Stayman sur 2SA", "", True, court=True),
        C("texas_2sa", "Texas sur 2SA", ["3♦", "3♥", "3♠", "3SA", "4♣"], ["3♦", "3♥"], "sef"),
        O("rectif_fittee", "Rectification fittée sur 2SA", "Sur le texas, l'ouvreur saute avec le fit", False, "sef"),
    ],
    "barrages": [
        T("deux_majeur", "2 majeure", "", True, court=True),
        O("chgt_2m_forcing", "Changement de couleur forcing", "Sur 2♥ / 2♠ faible : forcing un tour", True, True),
        T("soutien_3m", "Soutien à 3♥ / 3♠ sur le deux faible", "", True, court=True),
    ],
    "interventions": [
        T("bic_min_2k", "Sur 1♣ / 1♦ : 2♦", "", True, court=True),
        T("bic_min_2sa", "Sur 1♣ / 1♦ : 2SA", "", True, court=True),
        T("bic_maj_cue", "Sur 1♥ / 1♠ : le cue-bid", "", True, court=True),
        T("bic_maj_2sa", "Sur 1♥ / 1♠ : 2SA", "", True, court=True),
        T("bic_maj_3t", "Sur 1♥ / 1♠ : 3♣", "", True, court=True),
        O("soutien_saut_barrage", "Soutien à saut : barrage", "En réponse à l'intervention", True, True),
        C("int_chgt_forcing", "Changement de couleur sans saut forcing", ["1/1", "2/1", "2/2"], ["1/1", "2/1", "2/2"], "ffb"),
        T("saut_2", "Intervention à saut au palier de 2", "", True, court=True),
        T("saut_3", "Intervention à saut au palier de 3 et plus", "", True, court=True),
        O("reveil_couleur_limitee", "En réveil, couleur sans saut limitée à l'ouverture", "", True, True),
    ],
    "contre_appel": [
        T("contre_toutes", "Contre : toutes distributions à partir de", "", True, court=True),
    ],
    "sa_intervention": [
        T("reveil_2sa", "2SA en réveil", "", "ffb", court=True),
    ],
    "defense_sa": [
        T("def_sa_contre", "Contre", "", True, court=True),
        T("def_sa_2t", "2♣", "", True, court=True),
        T("def_sa_2k", "2♦", "", True, court=True),
        T("def_sa_2m", "2♥ / 2♠", "", True, court=True),
        O("def_sa_reveil", "Idem en réveil", "Les mêmes enchères après 1SA – passe – passe", True, "ffb"),
    ],
    "a_la_couleur": [
        T("flanc_couleur_entame", "Entame (la carte)", "", True, court=True),
        T("sig_entame_couleur", "Signal sur l'entame du partenaire", "", False, court=True),
    ],
    "a_sans_atout": [
        T("flanc_sa_entame", "Entame (la carte)", "", True, court=True),
    ],
    "chelem": [
        T("bw_sans_fit", "4SA sans fit annoncé", "", True, court=True),
    ],
    "conventions": [
        O("sa_forcing", "1SA forcing", "1♥ / 1♠ – 1SA : forcing un tour", False),
        O("smi", "S.M.I.", "Soutien mineur inversé", False),
        T("autres_conventions", "Autres conventions", "", court=True),
    ],
}
# remplacées par une ligne de la feuille (lire() reprend leur ancienne valeur)
SUPPRIMES = {"stayman", "texas", "deux_forts", "deux_faibles", "barrages", "landy", "dsa",
             "michaels", "bicolores", "sa_bicolore"}           # les bicolores : une ligne par enchère (2026-11-14)
DEPLACES = {"sig_entame": "a_sans_atout"}   # vers la section où la feuille les range


def _ranger():
    garde = {}
    for _, _, _, ls in SECTIONS:
        for i in list(ls):
            if i["cle"] in SUPPRIMES: ls.remove(i)
            elif i["cle"] in DEPLACES: ls.remove(i); garde[i["cle"]] = i
    for s, _, _, ls in SECTIONS:
        ls.extend(AJOUTS.get(s, []))
        ls.extend(garde[c] for c, d in DEPLACES.items() if d == s)
    for _, _, _, ls in SECTIONS:                             # un titre plus clair là où la feuille le dit autrement
        for i in ls:
            if i["cle"] == "sig_entame": i["titre"] = "Signal sur l'entame du partenaire"
            if i["cle"] == "sig_defausse": i["titre"] = "Défausse"
            if i["cle"] == "michaels": i["titre"] = "Bicolores : Michaels cue-bid"
            if i["cle"] == "blackwood": i.update(titre="Blackwood", desc="")
            if i["cle"] == "majeures5": i.update(titre="Majeure", desc="")
            if i["cle"] == "meilleure_mineure": i.update(titre="Mineure", desc="")
            if i["cle"] == "int_couleur": i["titre"] = "Intervention par une couleur"
            if i["cle"] == "ca_reponses": i["titre"] = "Réponses au contre d'appel"
            if i["cle"] == "sa2_rep": i.update(C("sa2_rep", "Réponses du partenaire", ["Naturel", "Stayman", "Texas"],
                                                   ["Stayman", "Texas"], True))


_ranger()

# La feuille de prévisions : ce que la page montre d'abord, et l'ordre de la fiche pour le partenaire.
# (partie, [(sous-titre ou None, [clés])])
FEUILLE = [
    ("Ouvertures", [
        (None, ["majeures5", "meilleure_mineure"]),
        ("1SA", ["ouv_1sa_desc", "stayman_1sa", "texas_1sa", "rectif_1sa"]),
        ("2SA", ["ouv_2sa_desc", "stayman_2sa", "texas_2sa", "rectif_fittee"]),
        ("2 majeure", ["deux_majeur", "chgt_2m_forcing", "ouv_2m_suite", "soutien_3m"]),
        ("2♣ et 2♦", ["ouv_2t_desc", "ouv_2t_rep", "ouv_2k_desc", "ouv_2k_rep"]),
        ("Barrages au palier de 3 et plus", ["ouv_3x_desc"]),
        ("Conventions", ["blackwood", "bw_sans_fit", "roudi", "drury", "lebensohl", "rubensohl", "quatrieme", "troisieme", "sa_forcing",
                         "smi", "autres_conventions"]),
    ]),
    ("Interventions", [
        ("Par 1SA", ["sa2", "sa2_rep"]),
        ("Par une couleur, sans saut", ["int_couleur", "soutien_saut_barrage", "int_saut", "int_chgt_forcing"]),
        ("Avec saut", ["saut_2", "saut_3"]),
        ("Par contre", ["contre_toutes", "ca_reponses"]),
        ("Enchères de bicolore sur 1♣ / 1♦", ["bic_min_2k", "bic_min_2sa"]),
        ("Enchères de bicolore sur 1♥ / 1♠", ["bic_maj_cue", "bic_maj_2sa", "bic_maj_3t"]),
        ("Sur ouverture de 1SA fort", ["def_sa_contre", "def_sa_2t", "def_sa_2k", "def_sa_2m", "def_sa_reveil"]),
        ("Réveil", ["sa4", "reveil_2sa", "reveil_couleur_limitee"]),
    ]),
    ("Flanc", [
        ("Sans-atout", ["flanc_sa_entame", "sig_entame", "defausse_sa"]),
        ("Couleur", ["flanc_couleur_entame", "sig_entame_couleur", "sig_defausse"]),
    ]),
]
# sur la feuille, quelques lignes portent un autre nom que dans la carte (la colonne du tableau des ouvertures…)
TITRE_FEUILLE = {"ouv_1sa_desc": "Points", "ouv_2sa_desc": "Points", "deux_majeur": "2♥ / 2♠",
                 "ouv_2t_desc": "2♣", "ouv_2t_rep": "Réponse 2♦", "ouv_2k_desc": "2♦", "ouv_2k_rep": "Réponses à 2♦",
                 "ouv_3x_desc": "Barrages", "sa2": "Points", "sa2_rep": "Réponses", "int_couleur": "Intervention",
                 "soutien_saut_barrage": "Réponse : soutien à saut barrage", "int_saut": "Changement de couleur à saut",
                 "saut_2": "Au palier de 2", "saut_3": "Au palier de 3 et plus",
                 "contre_toutes": "Toutes distributions à partir de", "ca_reponses": "Réponses",
                 "bic_min_2k": "2♦", "bic_min_2sa": "2SA", "bic_maj_cue": "Le cue-bid (2♥ / 2♠)", "bic_maj_2sa": "2SA",
                 "bic_maj_3t": "3♣",
                 "sa4": "1SA en réveil", "reveil_2sa": "2SA en réveil", "reveil_couleur_limitee": "Couleur sans saut limitée à "
                 "l'ouverture", "flanc_sa_entame": "Entame", "flanc_couleur_entame": "Entame", "sig_entame": "Appel",
                 "sig_entame_couleur": "Appel", "stayman_1sa": "Stayman", "texas_1sa": "Texas", "stayman_2sa": "Stayman",
                 "texas_2sa": "Texas", "quatrieme": "4e couleur forcing",
                 "rectif_1sa": "Rectification fittée", "bw_sans_fit": "4SA sans fit", "rectif_fittee": "Rectification fittée",
                 "ouv_2m_suite": "Réponses au relais 2SA", "soutien_3m": "Soutien à 3♥ / 3♠"}


def titre_feuille(cle):
    return TITRE_FEUILLE.get(cle) or ITEMS[cle]["titre"]


# d'anciennes valeurs Oui / Non devenues un choix, ou une ligne remplacée (lire)
MIGRE = {"majeures5": {False: "Majeure 4e"}, "meilleure_mineure": {False: "♦ 4e"},
         "blackwood": {False: "Pas de Blackwood"}, "deux_faibles": ("deux_majeur", {False: "Fort"}),
         "landy": ("def_sa_2t", {True: "Landy"}), "stayman": ("stayman_1sa", {False: "Pas de Stayman"}),
         "texas": ("texas_1sa", {False: []})}
RENOMME = {"systeme": {"SEF 2024, naturel, 1SA 15–17 H": "SEF 2024"}, "sig_defausse": {"Préférence": "Lavinthal"}, "defausse_sa": {"Comme à la couleur": "Lavinthal"},
           "sig_entame": {"Appel-refus": "Petit appel"}, "ouv_2t_rep": {"2♦ d'attente": "Obligatoire"},
           "ouv_3x_desc": {"Barrage, main faible": "Naturel"}}

COLONNES = [("art", "Artificielle"), ("mini", "Nombre minimum de cartes"), ("desc", "Description"),
            ("cn", "Contres négatifs jusqu'à"), ("rep", "Réponses (et ce qui change après une intervention)"),
            ("suite", "Suite des enchères"), ("chg", "Changements après intervention et passe")]
_CHG_MINEURE = ("Contre Spoutnik ; couleur 5e au palier de 1 dès 6 H, au palier de 2 dès 11 H (forcing) ; SA avec arrêt : "
                "1SA 8–10, 2SA 11–12, 3SA 13 ; cue-bid = soutien et force", True)
OUVERTURES = [
    ("1t", "1♣", False, {
        "mini": ("3", False), "desc": ("12–21 H, la meilleure mineure", True), "cn": ("2♠ (Spoutnik)", True),
        "rep": ("Couleur 4e au palier de 1 dès 6 H, au palier de 2 dès 10 H ; soutien 4 cartes dès 6 H ; 1SA 6–10, "
                "2SA 11–12, 3SA 13–17", False),
        "suite": ("2e couleur moins chère à saut avec 18 HL : forcing", True), "chg": _CHG_MINEURE}),
    ("1k", "1♦", False, {
        "mini": ("3", True), "desc": ("12–21 H ; 4 cartes sauf exception", True), "cn": ("2♠ (Spoutnik)", True),
        "rep": ("Comme sur 1♣ ; avec une majeure 4e et une mineure 5e : la majeure d'abord avec 5–11 H, la plus longue "
                "d'abord avec un jeu de manche", False),
        "suite": ("1♦ – 2♣ : redemande à 2♦ = misère, 2SA = 12–14 avec arrêts dans les majeures", "ffb"),
        "chg": _CHG_MINEURE}),
    ("1m", "1♥ / 1♠", False, {
        "mini": ("5", False), "desc": ("12–21 H", False), "cn": ("3♦ (Spoutnik)", True),
        "rep": ("Soutien simple 6–10 DH ; 1SA 6–10 ; 2 sur 1 dès 10 H ; Drury d'une main passée", False),
        "suite": ("Quatrième couleur forcing ; 2♥ / 2♠ – 2SA : essai généralisé ; 3♣ / 3♦ : essai, demande de complément", "ffb"),
        "chg": ("Cue-bid = soutien 4 cartes et 13 HLD, forcing de manche ; Spoutnik ; un saut dans une nouvelle couleur = "
                "barrage", True)}),
    ("1sa", "1SA", False, {
        "mini": ("", False), "desc": ("15–17 H, régulier", True), "cn": ("", False),
        "rep": ("2♣ Stayman ; 2♦ / 2♥ texas ; 2♠ texas mineur ; 2SA 8–9 ; 3SA 10–15 ; 4SA quantitatif", True),
        "suite": ("Après le texas, 4SA reste quantitatif", False),
        "chg": ("Couleur 5e naturelle ; 2SA 8–9 avec arrêt ; 3SA 10 et plus avec arrêt", True)}),
    ("2t", "2♣", True, {
        "mini": ("", False), "desc": ("Fort indéterminé", True), "cn": ("", False),
        "rep": ("2♦ d'attente", False),
        "suite": ("Redemandes à 2♥ / 2♠ naturelles ; 2SA 22–23 H ; 3SA fort bicolore majeur 5-5", "ffb"),
        "chg": ("2♣ – 2♦ – 3♠ = 7 cartes, 8 levées de jeu", "ffb")}),
    ("2k", "2♦", True, {
        "mini": ("", False), "desc": ("Forcing de manche", True), "cn": ("", False),
        "rep": ("2♠ = A♥ ou A♠ ; 3♣ = A♣ ; 3♦ = A♦ ; 3♥ / 3♠ / 3SA = 2 as", "ffb"),
        "suite": ("Redemande de l'ouvreur à 3SA : forcing jusqu'à 4SA", "ffb"),
        "chg": ("2♣ – 2♦ – 4♠ = 8 cartes, 8 levées de jeu", "ffb")}),
    ("2m", "2♥ / 2♠", False, {
        "mini": ("6", False), "desc": ("Faible, 5–10 H", True), "cn": ("", False),
        "rep": ("2SA : relais forcing, 15 H et plus ; changement de couleur forcing un tour ; 3M : barrage ; la manche avec "
                "dix atouts ensemble, pour jouer", True),
        "suite": ("Sur 2SA : par paliers", True), "chg": ("Contres punitifs", "ffb")}),
    ("2sa", "2SA", False, {
        "mini": ("", False), "desc": ("20–21 H, régulier", True), "cn": ("", False),
        "rep": ("3♣ Stayman ; 3♦ / 3♥ texas ; 4♣ / 4♦ naturel, essai de chelem ; 4SA quantitatif", True),
        "suite": ("Texas mineurs : propositions de chelem", "ffb"),
        "chg": ("2SA – 4♦ = 5♥ et 5♠, limité à la manche", "ffb")}),
    ("3x", "3 à la couleur", False, {
        "mini": ("7", False), "desc": ("Barrage, main faible", True), "cn": ("", False),
        "rep": ("La manche en majeure avec dix atouts ensemble, ou deux atouts et 12 HLD", True),
        "suite": ("", False), "chg": ("Changement de couleur forcing", "ffb")}),
    ("3sa", "3SA", False, {
        "mini": ("7", False), "desc": ("Mineure 7e affranchie, sans levée de défense à côté", "ffb"), "cn": ("", False),
        "rep": ("4♦ : nomme ta courte ; 4SA : pas de courte", "ffb"), "suite": ("", False), "chg": ("", False)}),
    ("4x", "4 à la couleur", False, {
        "mini": ("8", False), "desc": ("8 cartes, ou 7-4, sans l'ouverture", "ffb"), "cn": ("", False),
        "rep": ("", False), "suite": ("", False), "chg": ("", False)}),
]
UN_PALIER = {"1t", "1k", "1m"}                          # les contres négatifs : seulement sur les ouvertures de 1


def _ouvertures():
    """Le tableau des ouvertures, en sections comme le recto : une par ouverture."""
    sections = []
    for rid, nom, art, cols in OUVERTURES:
        lignes = [O(f"ouv_{rid}_art", "Artificielle", "", art)]
        for col, titre in COLONNES[1:]:
            if col == "cn" and rid not in UN_PALIER: continue
            if col == "mini" and not cols[col][0]: continue
            d, inc = cols[col]
            lignes.append(T(f"ouv_{rid}_{col}", titre, d, inc, court=col in ("mini", "desc")))
        sections.append((f"ouv_{rid}", f"Ouverture de {nom}", "ouvertures", lignes))
    return sections


SECTIONS_OUVERTURES = _ouvertures()
TOUTES = SECTIONS + SECTIONS_OUVERTURES

# Des choix à l'écran plutôt qu'un texte à taper (l'utilisateur, 2026-11-14 : « easy to fill in on the screen with all
# standard defaults already selected »). clé : (le choix du SEF / de Bridge Coach, [(libellé court, texte sur la carte)]).
# « Autre… » reste toujours possible : un texte à soi. Une case vide sur la carte devient « Rien de particulier ».
RIEN = "Rien de particulier"
PREF = "Préférence : dans une couleur dont on ne veut pas ; haute = la plus chère des deux autres, basse = la moins chère"
PAIR_IMPAIR = ("Pair-impair : impaire = continuez ; paire = changez, haute (7 et plus) vers la plus chère des deux autres "
               "couleurs, basse vers la moins chère")
CHOIX = {
    "ouv_1t_mini": ("3", [("2", None), ("3", None), ("4", None)]),
    "ouv_1k_mini": ("3", [("3", None), ("4", None)]),
    "ouv_1m_mini": ("5", [("4", None), ("5", None)]),
    "ouv_2m_mini": ("6", [("5", None), ("6", None)]),
    "ouv_3x_mini": ("7", [("6", None), ("7", None)]),
    "ouv_3sa_mini": ("7", [("7", None), ("8", None)]),
    "ouv_4x_mini": ("8", [("7", None), ("8", None)]),
    "ouv_1t_cn": ("2♠", [("2♥", None), ("2♠", "2♠ (Spoutnik)"), ("3♦", None), ("3♠", None), ("4♦", None)]),
    "ouv_1k_cn": ("2♠", [("2♥", None), ("2♠", "2♠ (Spoutnik)"), ("3♦", None), ("3♠", None), ("4♦", None)]),
    "ouv_1m_cn": ("3♦", [("2♠", None), ("3♦", "3♦ (Spoutnik)"), ("3♠", None), ("4♦", None)]),
    "ouv_1sa_desc": ("15–17 H", [("15–17 H", "15–17 H, régulier"), ("15–17 H et demi", "15–17 H et demi, régulier"),
                                 ("14–16 H", "14–16 H, régulier"), ("12–14 H", "12–14 H, régulier")]),
    "ouv_2sa_desc": ("20–21 H", [("20–21 H", "20–21 H, régulier"), ("20–22 H", "20–22 H, régulier"),
                                 ("21–22 H", "21–22 H, régulier")]),
    "ouv_2t_desc": ("Fort indéterminé", [("Fort indéterminé", None), ("Albarran", None)]),
    "ouv_2k_desc": ("Forcing de manche", [("Forcing de manche", None), ("Multi", "Multi : un deux faible en majeure, ou "
                                          "une main forte"), ("Faible", "Faible, 6 carreaux")]),
    "ouv_2m_desc": ("Faible, 5–10 H", [("Faible, 5–10 H", None), ("Faible, 6–10 H", None), ("Faible, 6–11 H", None)]),
    "ouv_3x_desc": ("Naturel", [("Naturel", "Barrage naturel, main faible"), ("Bicolore", "Enchères de bicolores")]),
    "ouv_3sa_desc": ("Mineure 7e affranchie", [("Mineure 7e affranchie", "Mineure 7e affranchie, sans levée de défense à "
                                                "côté"), ("Pour jouer", "Pour jouer, main régulière")]),
    "ouv_2t_rep": ("Obligatoire", [("Obligatoire", "2♦ obligatoire, d'attente"),
                                   ("Par paliers", "Réponses par paliers de contrôles")]),
    "ouv_2k_rep": ("As majeur", [("As majeur", "2♠ = A♥ ou A♠ ; 3♣ = A♣ ; 3♦ = A♦ ; 3♥ / 3♠ / 3SA = 2 as"),
                                 ("As sans jeu", "2♠ = pas d'as, main sans jeu")]),
    "cn2_couleur": ("À saut : barrage", [("À saut : barrage", "1 sur 1 forcing ; à saut : barrage"),
                                         ("À saut : fort", "1 sur 1 forcing ; à saut : fort")]),
    "cn2_surcontre": ("10 H et plus", [("10 H et plus", None), ("Fitté ou punitif", None)]),
    "dame_atout": ("La couleur suivante", [("La couleur suivante", "Après 5♣ / 5♦, la couleur suivante (hors atout)"),
                                           ("La couleur collée", "La couleur collée à la réponse"), ("Pas de demande", None)]),
    "rois": ("Par paliers", [("Par paliers", "5SA, toutes les clés promises : 6♣ = 0 roi, 6♦ = 1, 6♥ = 2, 6♠ = 3 (hors "
                              "roi d'atout)"), ("En Baron", "5SA : réponses en Baron"),
                             ("Le roi le moins cher", "5SA : on nomme le roi le moins cher")]),
    "bw_intervention": ("DOPI", [("DOPI", "DOPI : contre = 0 clé, passe = 1 clé"),
                                 ("ROPI", "ROPI (après leur contre) : surcontre = 0 clé, passe = 1 clé"),
                                 ("DEPO", "DEPO : contre = nombre pair de clés, passe = impair")]),
    "int_saut": ("Fitté", [("Fitté", "Fitté : enchère de rencontre"), ("Barrage", None), ("Naturel, forcing", None)]),
    "ca_reveil": ("Dès 9 H", [("Dès 7 H", "7 H et plus"), ("Dès 8 H", "8 H et plus"),
                              ("Dès 9 H", "3 points de moins : dès 9 H")]),
    "bic_reveil": ("Oui", [("Oui", "Les mêmes qu'en 2e position"), ("Non", "Pas de bicolores en réveil")]),
    "sa2": ("15–18 H", [("15–18 H", "15–18 H, régulier, arrêt dans leur couleur"),
                        ("16–18 H", "16–18 H, régulier, arrêt dans leur couleur")]),
    "sa4": ("12–15 H", [("10–12 H", None), ("12–15 H", "12–15 H (3 points de moins)"), ("10–13 HL", None)]),
    "sa4_rep": ("Comme en 2e position", [("Comme en 2e position", None), ("Minou-Matou", None), ("Naturelles", None)]),
    "q4_cue": ("5-5 constructif", [("5-5 constructif", "Bicolore 5-5 constructif des deux autres couleurs"),
                                   ("Naturel", None)]),
    "q4_2sa": ("5-5 défensif", [("5-5 défensif", "Bicolore 5-5 défensif des deux autres couleurs"),
                                ("Naturel", "Naturel, arrêt dans les deux couleurs")]),
    "q4_contre": ("4-4", [("4-4", "L'ouverture et les deux autres couleurs, 4-4"), ("Punitif", None)]),
    "dsa_contre": ("Contre artificiel : on l'oublie", [("Contre artificiel : on l'oublie", "Contre artificiel : on "
                   "l'oublie ; contre punitif : sauvetage"), ("Système de sauvetage", "Système de sauvetage à convenir")]),
    "d2_2sa": ("16–18 H", [("15–18 H", "15–18 H, naturel, arrêt"), ("16–18 H", "16–18 H, naturel, arrêt")]),
    "d2_cue": ("Demande d'arrêt", [("Demande d'arrêt", "Demande en priorité un arrêt pour jouer 3SA"),
                                   ("Bicolore", "Bicolore : l'autre majeure et une mineure")]),
    "d2_4m": ("Autre majeure + mineure", [("Autre majeure + mineure", "L'autre majeure 5e et la mineure nommée 5e"),
                                          ("Naturel", None)]),
    "d2_rep": ("2SA mini cue-bid", [("2SA mini cue-bid", "La meilleure couleur ; 2SA : mini cue-bid, 8 H et plus"),
                                    ("Lebensohl", "Lebensohl"), ("Naturelles", None)]),
    "sig_defausse": ("Lavinthal", [("Appel direct", "Appel direct : une grosse carte appelle"),
                                   ("Pair-impair", "Pair-impair : impaire = je veux cette couleur ; paire = non, sa hauteur dit "
                                    "laquelle"), ("Italien", "Italien (appel-refus et préférence)"), ("Lavinthal", PREF)]),
    "defausse_sa": ("Lavinthal", [("Lavinthal", PREF), ("Pair-impair", "Pair-impair : impaire = je veux cette couleur ; "
                                  "paire = non, sa hauteur dit laquelle"), ("Italien", "Italien (appel-refus et préférence)")]),
    "sig_entame": ("Pair-impair", [("Pair-impair", PAIR_IMPAIR), ("Gros appel", "Gros appel : une grosse carte "
                                   "demande de continuer"), ("Petit appel", "Petit appel : une petite carte demande de continuer")]),
    "sig_entame_couleur": ("Pair-impair", [("Pair-impair", PAIR_IMPAIR), ("Appel direct", "Appel direct : une grosse "
                                           "carte demande de continuer"), ("Petit appel", "Petit appel : une petite carte "
                                           "demande de continuer")]),
    "flanc_sa_entame": ("4e meilleure", [("4e meilleure", "4e meilleure sous un honneur ; la tête d'une séquence"),
                                         ("Pair-impair", "Pair-impair")]),
    "flanc_couleur_entame": ("4e meilleure", [("Pair-impair", "Pair-impair"), ("4e meilleure", "4e meilleure sous un "
                             "honneur, la plus petite de trois ; la plus haute d'un doubleton ou de trois petites ; la "
                             "deuxième de quatre petites")]),
    "systeme": ("SEF 2024", [("SEF 2024", "SEF 2024 (Système d'Enseignement Français), majeure 5e, 1SA 15–17 H")]),
    # la feuille de prévisions (2026-11-14)
    "majeures5": ("Majeure 5e", [("Majeure 5e", "1♥ / 1♠ : 5 cartes au moins"), ("Majeure 4e", "1♥ / 1♠ : 4 cartes")]),
    "meilleure_mineure": ("Meilleure mineure", [("Meilleure mineure", "1♣ / 1♦ : la mineure la plus longue, 3 cartes au "
                          "moins"), ("♦ 4e", "1♦ promet 4 cartes")]),
    "stayman_1sa": ("3 paliers", [("4 paliers", "Stayman 4 paliers : 2♦, 2♥, 2♠, 2SA (les deux majeures)"),
                                  ("3 paliers", "Stayman : 2♦ pas de majeure 4e, 2♥ (peut avoir 4♠), 2♠")]),
    "stayman_2sa": ("3 paliers", [("4 paliers", "Stayman 4 paliers"), ("Puppet", "Puppet Stayman (cherche la majeure 5e)"),
                                  ("3 paliers", "3♣ Stayman, mêmes réponses que sur 1SA")]),
    # le moteur, 2026-11-14 : la rectification fittée sur 1SA, et les réponses au deux faible (systeme.md, à confirmer)
    "rectif_1sa": ("Oui", [("Oui", "Oui : 4 atouts et 16–17 H (1SA – 2♦ – 3♥, 1SA – 2♥ – 3♠)"),
                           ("Non", "Non : l'ouvreur complète toujours le texas")]),
    "ouv_2m_suite": ("Par paliers", [("Par paliers", "Sur 2SA (relais forcing, 15 H et plus) : 3♣ = minimum, couleur "
                                      "pauvre ; 3♦ = minimum, belle couleur ; 3♥ = maximum, couleur pauvre ; 3♠ = maximum, "
                                      "belle couleur ; 3SA = ARD"),
                                     ("Force ou singleton", "Sur 2SA : 3x = force, 4x = singleton")]),
    "soutien_3m": ("Barrage", [("Barrage", "Barrage : trois atouts, pour jouer"),
                               ("Invitation", "Invitation à la manche")]),
    "deux_majeur": ("Faible", [("Faible", "2♥ / 2♠ : faible, 6 cartes"), ("Fort", "2♥ / 2♠ : fort")]),
    # 4SA sans fit (2026-11-17, blackwood-3041.md et systeme.md « Chelem : les contrôles », à confirmer)
    "bw_sans_fit": ("Blackwood", [("Blackwood", "Après une couleur naturelle, le partenaire n'ayant pas limité sa main : "
                                   "Blackwood 3041, atout la dernière couleur nommée naturellement ; pour jouer sa propre "
                                   "couleur, la nommer d'abord au palier de 4. Après une enchère naturelle à SA, 4SA reste "
                                   "quantitatif"),
                                  ("Quantitatif", "4SA sans fit annoncé : quantitatif")]),
    "blackwood": ("5 clés 30-41", [("5 clés 30-41", "Blackwood 5 clés 30-41 : 5♣ = 3 ou 0, 5♦ = 4 ou 1, 5♥ = 2 sans la "
                  "dame d'atout, 5♠ = 2 avec"), ("5 clés 41-30", "Blackwood 5 clés 41-30"), ("4 as", "Blackwood 4 as")]),
    "int_couleur": ("Naturel", [("Naturel", "Naturelles : au palier de 1, 5 cartes et 8–16 H (10 si la couleur est "
                    "pauvre) ; au palier de 2, bonne 5e ou 6e et 11–16 H")]),
    "saut_2": ("Faible", [("Faible", "Faible, 6 cartes")]),
    "saut_3": ("Barrage", [("Barrage", None)]),
    "contre_toutes": ("17 H", [("16 H", "16 H"),
                               ("17 H", "17 H"),
                               ("18 H", "18 H")]),
    "ca_reponses": ("Naturelles", [("Naturelles", "La meilleure couleur (majeure 4e d'abord) au plus bas avec 0–8 H, à "
                    "saut avec 9–11, la manche avec 12 ; 1SA avec 6–9 H et un arrêt")]),
    # les bicolores (regles.yaml : 5-5 au moins, 8–18 H, alertés ; l'utilisateur, 2026-11-14 : une ligne par enchère)
    "bic_min_2k": ("Les deux majeures", [("Les deux majeures", "Les deux majeures, 5-5, 8–18 H (sur 1♦ : le cue-bid)"),
                                         ("Naturel", "Naturel, faible")]),
    "bic_min_2sa": ("Les deux plus basses", [("Les deux plus basses", "Les deux couleurs libres les plus basses, 5-5, "
                                              "8–18 H : ♦ et ♥ sur 1♣, ♣ et ♥ sur 1♦"),
                                             ("Les mineures", "Les deux mineures, 5-5")]),
    "bic_maj_cue": ("♣ et l'autre majeure", [("♣ et l'autre majeure", "Trèfle et l'autre majeure, 5-5, 8–18 H"),
                                             ("L'autre majeure et une mineure", "L'autre majeure et une mineure non "
                                              "précisée, 5-5")]),
    "bic_maj_2sa": ("Les mineures", [("Les mineures", "Les deux mineures, 5-5, 8–18 H")]),
    "bic_maj_3t": ("♦ et l'autre majeure", [("♦ et l'autre majeure", "Carreau et l'autre majeure, 5-5, 8–18 H"),
                                            ("Naturel", "Naturel, barrage")]),
    "def_sa_contre": ("Punitif", [("Punitif", "Contre punitif, 15 H et plus")]),
    "def_sa_2t": ("Naturel", [("Landy", "Landy : les deux majeures"), ("Naturel", "Naturel, 6 cartes, dès 8 H")]),
    "def_sa_2k": ("Naturel", [("Naturel", "Naturel, 6 cartes, dès 8 H")]),
    "def_sa_2m": ("Naturel", [("Naturel", "Naturels, 6 cartes, dès 8 H")]),
    "reveil_2sa": ("17–19 H", [("17–19 H", "17–19 H, régulier")]),
    "entame_as": ("Pair-impair", [("Pair-impair", "Pair-impair, comme sur toute entame du partenaire"),
                                  ("Appel-refus", "Appel-refus si trois petites cartes au mort"), ("Parité", "Parité")]),
    "sig_parite": ("Parité", [("Parité", "Parité : grosse puis petite avec un nombre pair, la plus petite avec un nombre "
                               "impair"), ("Parité inversée", "Parité inversée : petite puis grosse avec un nombre pair"),
                              ("Pas de signal", None)]),
    "sig_atout": ("Pas de signal", [("Pas de signal", None), ("Parité", None), ("Appel de couleur", None)]),
    "attaque_couleur": ("Tête de séquence", [("Tête de séquence", "La tête d'une séquence ; sinon comme à l'entame"),
                                             ("Pair-impair", None), ("Petit prometteur", None)]),
    "attaque_sa": ("Tête de séquence", [("Tête de séquence", "La tête d'une séquence ; sinon comme à l'entame"),
                                        ("Petit prometteur", None), ("Pair-impair", None)]),
    "entame_sequence": ("Tête de séquence", [("Tête de séquence", "La tête (R de RD, D de DV) ; l'as de AR"),
                                             ("Roi de AR", "La tête (R de RD, D de DV) ; le roi de AR")]),
    "entame_honneur": ("4e meilleure", [("4e meilleure", "4e meilleure ; la plus petite de trois cartes"),
                                        ("3e et 5e", "3e et 5e meilleure"), ("Pair-impair", "Pair-impair")]),
    "entame_petites": ("Haute, puis 2e de quatre", [("Haute, puis 2e de quatre", "Doubleton : la plus haute ; trois "
                       "petites : la plus haute ; quatre petites : la deuxième"), ("Pair-impair", "Pair-impair"),
                       ("Petite", "La plus petite")]),
}


def _choix():
    """Les lignes à choisir, et une case vide de la carte : « Rien de particulier »."""
    for _, _, _, ls in TOUTES:
        for i in ls:
            if i["cle"] in CHOIX:
                d, opts = CHOIX[i["cle"]]
                i.update(type="choix", options=[(l, t if t is not None else l) for l, t in opts], defaut=d)
                assert d in dict(i["options"]), i["cle"]
            elif i["type"] == "texte" and not i["defaut"]:
                i.update(type="choix", options=[(RIEN, "")], defaut=RIEN)
            if i["cle"] in PLUSIEURS:                         # plusieurs cases, et « Autre… » pour un texte à soi
                i.update(type="cases", defaut=[i["defaut"]], autre=True)


# le flanc : on peut cocher plusieurs choix sur chaque ligne (l'utilisateur, 2026-11-14 : « can we check more than one ») ;
# le choix de Bridge Coach reste le seul coché au départ
PLUSIEURS = {"flanc_sa_entame", "sig_entame", "defausse_sa", "flanc_couleur_entame", "sig_entame_couleur", "sig_defausse"}
_choix()
ITEMS = {i["cle"]: dict(i, section=s) for s, _, _, ls in TOUTES for i in ls}
CONVENTIONS = [i for i in ITEMS.values() if i["type"] == "oui"]
PARTIES = [("resume", "Résumé du système"), ("competitives", "Enchères compétitives"),
           ("entames", "Entames et signalisation"), ("conventions", "Conventions"), ("ouvertures", "Les ouvertures")]
# l'en-tête : le nom, le prénom et l'IV (indice de valeur FFB, le classement) des deux joueurs, et le niveau de la
# compétition (imprimé sur la feuille ; il ne change pas les choix : le même système à tous les niveaux pour l'instant)
ENTETE = ["nom1", "prenom1", "classement1", "nom2", "prenom2", "classement2", "niveau"]
NIVEAUX = ["Club / Challenge", "Espérance", "Promotion", "Honneur", "Excellence", "Performance", "Expert"]


def separer_nom(complet):
    """« MARTIN Anne » ou « DE LA TOUR Marie-Claire » -> (nom, prénom) : le nom de famille en capitales d'abord, comme
    dans Bridge Coach ; sans capitales, le dernier mot est le nom."""
    mots = (complet or "").split()
    if not mots: return "", ""
    i = 0
    while i < len(mots) and mots[i] == mots[i].upper() and any(ch.isalpha() for ch in mots[i]): i += 1
    if 0 < i < len(mots) or i == len(mots) == 1: return " ".join(mots[:i] or mots), " ".join(mots[i:])
    if i == len(mots): return " ".join(mots), ""
    return mots[-1].upper(), " ".join(mots[:-1])


def proposer_joueurs(moi_nom=None, partenaire=None):
    """Remplit les noms encore vides : vous (« Votre nom ») et votre partenaire, quand Bridge Coach les connaît.
    Ce qui est déjà écrit ne change pas ; l'IV se tape à la main."""
    x = lire(); change = False
    for n, (nm, pr) in ((1, separer_nom(moi_nom)), (2, separer_nom(partenaire))):
        if nm and not (x.get(f"nom{n}") or x.get(f"prenom{n}")):
            x[f"nom{n}"], x[f"prenom{n}"] = nm, pr; change = True
    if change: ecrire(x)
    return x


def partenaire_de(data, qui):
    """Le nom complet du partenaire de qui dans une séance (« joueurs »), ou None."""
    import moi
    if not data or not qui: return None
    for k in sorted(moi.paires(data, qui)):
        for j in (data.get("joueurs") or {}).get(k, []):
            if j.get("nom") and not moi.est(j, qui, moi.licence_de(qui)): return j["nom"]
    return None
SUR_FEUILLE = [c for _, g in FEUILLE for _, cs in g for c in cs]


def reste(section_items):
    """Les lignes d'une section de la carte qui ne sont pas déjà sur la feuille de prévisions (« Le reste de la carte »)."""
    return [i for i in section_items if i["cle"] not in SUR_FEUILLE and i["cle"] != "systeme"]   # la méthode : en haut


def chemin():
    return os.path.join(rapport.DONNEES, "documents", "fiche-conventions.json")


def lire():
    """{"joueur1", "classement1", "joueur2", "classement2", "accords", "valeurs": {clé: texte ou Oui (True) / Non
    (False)}} : seulement ce que la paire a changé. Le fichier d'avant (« joueurs » sur une ligne, « conventions » à part)
    se lit tel quel."""
    try:
        x = json.load(open(chemin(), encoding="utf-8"))
        x = x if isinstance(x, dict) else {}
    except (OSError, ValueError):
        x = {}
    vals = x.get("valeurs") if isinstance(x.get("valeurs"), dict) else {}
    for c, v in (x.pop("conventions", None) or {}).items():         # les Oui / Non d'avant (_migrer les range)
        if c not in vals: vals[c] = bool(v)
    vals = _migrer(vals)
    if vals: x["valeurs"] = vals
    else: x.pop("valeurs", None)
    if x.get("joueurs") and not (x.get("joueur1") or x.get("joueur2")):   # « MARTIN Anne et BERNARD Henri »
        deux = [p.strip() for p in re.split(r"\s+(?:et|&)\s+|\s*/\s*|\s*,\s*", x["joueurs"], maxsplit=1)]
        x["joueur1"] = deux[0]
        if len(deux) > 1: x["joueur2"] = deux[1]
    x.pop("joueurs", None)
    for n in (1, 2):                                          # un nom complet sur une ligne : le nom et le prénom
        j = x.pop(f"joueur{n}", None)
        if j and not (x.get(f"nom{n}") or x.get(f"prenom{n}")): x[f"nom{n}"], x[f"prenom{n}"] = separer_nom(j)
    return x


def _migrer(vals):
    """Les valeurs d'avant la feuille de prévisions : un Oui / Non devenu un choix, une ligne remplacée par une autre,
    un libellé renommé ; une valeur qui ne va plus avec sa ligne est oubliée (la ligne revient à Bridge Coach)."""
    out = {}
    for c, v in vals.items():
        m = MIGRE.get(c)
        if isinstance(m, tuple):                              # une ligne remplacée par une ligne de la feuille
            nv = m[1].get(bool(v)) if isinstance(v, bool) else None
            if nv is not None and m[0] not in vals: out[m[0]] = nv
            continue
        if c == "michaels":                                   # avant : une ligne « Michaels précisés / non précisés »
            if v in ("Non précisés", False) and "bic_maj_cue" not in vals:
                out["bic_maj_cue"] = "L'autre majeure et une mineure"
            continue
        it = ITEMS.get(c)
        if not it: continue
        if it["type"] == "oui":
            if isinstance(v, bool): out[c] = v
        elif it["type"] == "cases":
            if isinstance(v, str) and v.strip() and it.get("autre"): v = [RENOMME.get(c, {}).get(v, v)]
            if isinstance(v, list): out[c] = _cases(it, v)
        elif isinstance(v, bool):
            nv = (m or {}).get(v)
            if nv is not None: out[c] = nv
        elif isinstance(v, str) and v.strip():
            out[c] = RENOMME.get(c, {}).get(v, v)
    return {c: v for c, v in out.items() if v != ITEMS[c]["defaut"] and
            not (ITEMS[c]["type"] == "cases" and set(v) == set(ITEMS[c]["defaut"]))}


def ecrire(x):
    os.makedirs(os.path.dirname(chemin()), exist_ok=True)
    provisoire = chemin() + ".provisoire"
    with open(provisoire, "w", encoding="utf-8") as f: json.dump(x, f, ensure_ascii=False, indent=1)
    os.replace(provisoire, chemin())


def valeur(cle, fiche=None):
    """(ce que joue la paire : un texte, ou True / False pour une convention ; changé par rapport à Bridge Coach ?)."""
    it = ITEMS[cle]
    v = ((fiche if fiche is not None else lire()).get("valeurs") or {}).get(cle)
    if v is None or (it["type"] == "oui" and bool(v) == it["defaut"]): return it["defaut"], False
    if it["type"] == "cases":
        if isinstance(v, str) and v.strip() and it.get("autre"): v = [v]            # une ancienne valeur unique
        v = _cases(it, v) if isinstance(v, list) else it["defaut"]
        return v, set(v) != set(it["defaut"])
    return (bool(v) if it["type"] == "oui" else v), True


def texte(cle, fiche=None, defaut=False):
    """Ce que la carte imprime : « Oui » / « Non », le texte d'un choix (son libellé court à l'écran), ou la ligne ;
    defaut : celui de Bridge Coach. Une case que la carte n'a pas pour cette ouverture : ""."""
    it = ITEMS.get(cle)
    if not it: return ""
    v = it["defaut"] if defaut else valeur(cle, fiche)[0]
    if it["type"] == "oui": return "Oui" if v else "Non"
    if it["type"] == "choix": return dict(it["options"]).get(v, v)
    if it["type"] == "cases":
        if not v: return "Aucun"
        sens = dict(it["options"])
        parts = [sens.get(o, o) for o in v]
        return (" ; " if any(sens.get(o, o) != o for o in v) else ", ").join(parts)
    return v


def _cases(it, v):
    """Les cases cochées dans l'ordre de la ligne, puis le texte écrit dans « Autre… » s'il y en a un."""
    noms = [o for o, _ in it["options"]]
    libres = [e.strip() for e in v if isinstance(e, str) and e.strip() and e not in noms] if it.get("autre") else []
    return [o for o in noms if o in v] + libres[:1]


def libre_de(cle, fiche=None):
    """Le texte écrit dans « Autre… » d'une ligne à plusieurs cases, ou ""."""
    it = ITEMS[cle]
    noms = dict(it["options"])
    return next((e for e in valeur(cle, fiche)[0] if e not in noms), "") if it["type"] == "cases" else ""


def coches_texte(cle, x, t):
    """Une ligne à plusieurs cases pour la fiche et la carte : chaque choix coché en gras sur gris avec ☒, suivi de ce
    qu'il veut dire ; le texte d'« Autre… » de même."""
    it = ITEMS[cle]; sens = dict(it["options"])
    out = []
    for o in valeur(cle, x)[0]:
        if o in sens: out.append(coche(t(o), True) + (f" {t(sens[o])}" if sens[o] != o else ""))
        else: out.append("Autre : " + ecrit(t(o)))
    return " ; ".join(out) if out else "Aucun"


def autre(cle, fiche=None):
    """Un choix réécrit par la paire (« Autre… ») : sa valeur n'est aucun des libellés proposés."""
    it = ITEMS[cle]
    if it["type"] == "cases": return bool(libre_de(cle, fiche))
    return it["type"] == "choix" and valeur(cle, fiche)[0] not in dict(it["options"])


def convention(cle, fiche=None):
    """(jouée par la paire ?, changé par rapport à Bridge Coach ?)."""
    return valeur(cle, fiche)


def changer(cle, v):
    """Garde ce que joue la paire ; le même que Bridge Coach, ou un texte vide : la ligne revient au système."""
    it = ITEMS[cle]
    x = lire(); vals = x.setdefault("valeurs", {})
    if it["type"] == "oui":
        if bool(v) == it["defaut"]: vals.pop(cle, None)
        else: vals[cle] = bool(v)
    elif it["type"] == "cases":
        v = _cases(it, [v] if isinstance(v, str) else (v or []))
        if set(v) == set(it["defaut"]): vals.pop(cle, None)
        else: vals[cle] = v
    else:
        t = (v or "").strip()
        if not t or t == it["defaut"] or t == texte(cle, defaut=True): vals.pop(cle, None)
        else: vals[cle] = t
    if not vals: x.pop("valeurs", None)
    ecrire(x)


def choisir_convention(cle, oui):
    changer(cle, bool(oui))


def a_verifier(cle, fiche=None):
    """Le pourquoi du « à vérifier », ou None : la ligne est sûre, ou la paire l'a déjà changée."""
    it = ITEMS[cle]
    return None if not it["incertain"] or valeur(cle, fiche)[1] else POURQUOI[it["incertain"]]


def changements(section, fiche=None):
    """Le nombre de lignes changées dans une section (l'en-tête de la section le dit)."""
    return sum(valeur(i["cle"], fiche)[1] for s, _, _, ls in TOUTES if s == section for i in ls)


def changer_entete(**champs):
    x = lire(); x.update({k: (v or "").strip() for k, v in champs.items()}); ecrire(x)


def tout_remettre():
    """Toutes les lignes reviennent au système de Bridge Coach ; les noms, les classements et les accords restent."""
    x = lire(); x.pop("valeurs", None); ecrire(x)


def joueur(x, n):
    """« MARTIN Anne », ou ""."""
    return " ".join(v for v in (x.get(f"nom{n}"), x.get(f"prenom{n}")) if v)


def joueurs(x):
    """« MARTIN Anne (IV 45) et BERNARD Henri » : les deux noms, sur la fiche du partenaire."""
    n = [joueur(x, k) + (f" (IV {x[f'classement{k}']})" if x.get(f"classement{k}") else "") for k in (1, 2) if joueur(x, k)]
    return " et ".join(n)


# ---------------------------------------------------------------- les PDF
def _commun():
    from reportlab.lib import colors
    import build_pdf as B                                    # les polices DejaVu et les cœurs et carreaux en rouge
    from xml.sax.saxutils import escape
    return colors, B, (lambda s: B.suits(escape(str(s))))


def _ecrire_pdf(sortie, construire):
    os.makedirs(os.path.dirname(sortie), exist_ok=True)
    provisoire = sortie[:-4] + ".provisoire.pdf"
    construire(provisoire)
    os.replace(provisoire, sortie)
    return sortie


def pdf(sortie=None):
    """Les trois PDF ; renvoie le chemin de la carte FFB complète (gardé pour l'ancien appel)."""
    pdf_partenaire(); pdf_feuille()
    return pdf_ffb(sortie)


BOITE = {True: "☒", False: "☐"}
SURLIGNE = "#ebebeb"           # 8 % de gris : avec le gras et ☒, le choix se voit en noir et blanc (l'utilisateur, 2026-11-14)


def coche(libelle, oui):
    """Une option de la feuille et sa case : choisie, en gras sur fond gris clair avec ☒ ; sinon simple, avec ☐."""
    if not oui: return f"{libelle} ☐"
    return f'<font backColor="{SURLIGNE}"><b>&nbsp;{libelle} ☒&nbsp;</b></font>'


def ecrit(texte_):
    """Un texte écrit dans « Autre » : en gras, sans fond gris (un long texte grisé paraît lourd : l'utilisateur,
    2026-11-14 ; le gris reste aux cases cochées)."""
    return f"<b>{texte_}</b>"


def cases_de(cle, x, t):
    """Une ligne de la feuille comme la FFB l'imprime : chaque choix suivi de sa case, cochée (☒) ou non (☐), « Autre : »
    avec le texte écrit ; OUI / NON pour une convention."""
    it = ITEMS[cle]; v = valeur(cle, x)[0]
    if it["type"] == "oui": return f"{coche('OUI', bool(v))}  {coche('NON', not v)}"
    if it["type"] == "cases":
        morceaux = [coche(t(o), o in v) for o, _ in it["options"]]
        if it.get("autre"):
            libre = libre_de(cle, x)
            morceaux.append(f"Autre : {ecrit(t(libre))}" if libre else "Autre : ……")
        return "  ".join(morceaux)
    opts = [o for o, _ in it["options"] if o != RIEN]
    morceaux = [coche(t(o), o == v) for o in opts]
    libre = t(texte(cle, x)) if autre(cle, x) else ""
    morceaux.append(f"Autre : {ecrit(libre)}" if libre else "Autre : ……")
    return "  ".join(morceaux)


def michaels_feuille(x, t):
    """La ligne « Michael's Cue-bid précisés ☐ non précisés ☐ Autre : » de la feuille officielle : précisés quand le
    cue-bid sur une majeure nomme la mineure (♣ et l'autre majeure), le détail des cinq enchères écrit dans « Autre »."""
    precises = valeur("bic_maj_cue", x)[0] == ITEMS["bic_maj_cue"]["defaut"]
    non = valeur("bic_maj_cue", x)[0] == "L'autre majeure et une mineure"
    court = lambda c: valeur(c, x)[0] if not autre(c, x) else texte(c, x)
    detail = (f"sur 1♣ / 1♦ : 2♦ = {court('bic_min_2k')}, 2SA = {court('bic_min_2sa')} ; sur 1♥ / 1♠ : cue-bid = "
              f"{court('bic_maj_cue')}, 2SA = {court('bic_maj_2sa')}, 3♣ = {court('bic_maj_3t')} (5-5)")
    return f"{coche('précisés', precises)}  {coche('non précisés', non)}  Autre : {ecrit(t(detail))}"


def _feuille(x, larg, haut, marge, t, B, colors):
    """La première page de la feuille officielle : la « Feuille de prévisions » de la FFB, sa mise en page (l'utilisateur,
    2026-11-14 : « one option to print out using more or less this format since it is the official card ») : à gauche
    INTERVENTIONS puis FLANC (sur fond gris), à droite le titre, NOM / IV des deux joueurs, la méthode de base, le
    niveau, puis les ouvertures ; en bas à droite nos accords particuliers. Les mêmes lignes et les mêmes mots, les
    cases cochées. Sans le logo de la FFB (un titre en texte)."""
    from reportlab.platypus import Paragraph, Table, TableStyle, KeepInFrame, FrameBreak, Spacer
    import datetime
    ROUGE = colors.HexColor("#d4141c")       # le flanc sur blanc : seul le choix est sur fond gris (l'utilisateur, 2026-11-14)
    gros = B.st("fv_g", fontName="DVB", fontSize=20, leading=23, textColor=ROUGE)
    sous = B.st("fv_s", fontName="DVB", fontSize=9.6, leading=12, spaceBefore=3)
    ligne = B.st("fv_l", fontName="DV", fontSize=9.2, leading=12.4, leftIndent=8)
    titre = B.st("fv_t", fontName="DVB", fontSize=19, leading=22, alignment=1)
    federation = B.st("fv_f", fontName="DVB", fontSize=8, leading=10, alignment=1, textColor=colors.HexColor("#333333"))
    lf = (larg - 2 * marge - 0.35 * 28.35) / 2
    hc = haut - 2 * marge

    def groupes(gs):
        out = []
        for sous_t, cles in gs:
            if sous_t and sous_t.startswith("Enchères de bicolore sur 1♥"): continue    # avec celle sur 1♣ / 1♦
            if sous_t and sous_t.startswith("Enchères de bicolore"):     # la ligne de la feuille officielle
                out.append(Paragraph("Enchères de bicolore", sous))
                out.append(Paragraph(f"<b>Michael's Cue-bid</b> : {michaels_feuille(x, t)}", ligne))
                continue
            if sous_t: out.append(Paragraph(t(sous_t), sous))
            if sous_t == "Conventions":                       # en ligne, comme sur la feuille
                oui = [c for c in cles if ITEMS[c]["type"] == "oui"]
                for c in cles:
                    if c == "blackwood": out.append(Paragraph(f"<b>Blackwood</b> : {cases_de(c, x, t)}", ligne))
                    elif ITEMS[c]["type"] == "choix" and c != "autres_conventions":
                        out.append(Paragraph(f"<b>{t(titre_feuille(c))}</b> : {cases_de(c, x, t)}", ligne))
                out.append(Paragraph("   ".join(coche(t(titre_feuille(c)), bool(valeur(c, x)[0])) for c in oui), ligne))
                a = texte("autres_conventions", x)
                out.append(Paragraph("<b>Autres</b> : " + (ecrit(t(a)) if a else "……"), ligne))
                continue
            for c in cles:
                out.append(Paragraph(f"<b>{t(titre_feuille(c))}</b> : {cases_de(c, x, t)}", ligne))
        return out

    def cadre(contenu, largeur, fond=None):
        tab = Table([[contenu]], colWidths=[largeur])
        st = [("BOX", (0, 0), (-1, -1), 1.4, ROUGE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
              ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
              ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]
        if fond: st.append(("BACKGROUND", (0, 0), (-1, -1), fond))
        tab.setStyle(TableStyle(st)); return tab

    parts = dict(FEUILLE)
    flanc = Table([[groupes(parts["Flanc"])]], colWidths=[lf - 14])
    flanc.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),           # sur blanc, comme le reste
                               ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    gauche = cadre([Paragraph("INTERVENTIONS", gros)] + groupes(parts["Interventions"]) +
                   [Spacer(1, 6), Paragraph("FLANC", gros), flanc], lf)
    nom = lambda n: (f"NOM : <b>{t(x.get(f'nom{n}') or '………………')}</b>&nbsp;&nbsp;&nbsp;"
                     f"PRÉNOM : <b>{t(x.get(f'prenom{n}') or '………………')}</b>&nbsp;&nbsp;&nbsp;"
                     f"IV : <b>{t(x.get(f'classement{n}') or '……')}</b>")
    methode = texte("systeme", x) if autre("systeme", x) else valeur("systeme", x)[0]
    entete = [Paragraph("FÉDÉRATION FRANÇAISE DE BRIDGE", federation), Paragraph("FEUILLE DE PRÉVISIONS", titre),
              Spacer(1, 4), Paragraph(nom(1), B.st("fv_n", fontName="DV", fontSize=10, leading=14)),
              Paragraph(nom(2), B.st("fv_n2", fontName="DV", fontSize=10, leading=14)),
              Paragraph(f"Méthode de base : <b>{t(methode)}</b>", B.st("fv_m", fontName="DV", fontSize=10,
                                                                                   leading=14, spaceBefore=2))]
    if x.get("niveau"):
        entete.append(Paragraph(f"Compétition : <b>{t(x['niveau'])}</b>", B.st("fv_c", fontName="DV", fontSize=10, leading=14)))
    ouv = cadre(groupes(parts["Ouvertures"]), lf)
    accords = (x.get("accords") or "").strip()
    acc = cadre([Paragraph("<b>NOS ACCORDS PARTICULIERS</b> (autres conventions à alerter)", sous),
                 Paragraph(t(accords).replace("\n", "<br/>") if accords else "<br/>" * 3, ligne)], lf)
    droite = entete + [Spacer(1, 6), ouv, Spacer(1, 6), acc,
                       Paragraph(f"Établie le {datetime.date.today():%d/%m/%Y}", B.st("fv_p", fontName="DV", fontSize=7, leading=9,
                                                                    textColor=colors.HexColor("#555555"), spaceBefore=3))]
    return [KeepInFrame(lf, hc, [gauche], mode="shrink"), FrameBreak(), KeepInFrame(lf, hc, droite, mode="shrink")]


def pdf_feuille(sortie=None):
    """La feuille de prévisions, une page, disposée comme celle de la FFB : la feuille courte pour la table (l'utilisateur,
    2026-11-14 : un bouton par document). Renvoie son chemin (<documents>/feuille-de-previsions.pdf)."""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame
    colors, B, t = _commun()
    sortie = sortie or os.path.join(rapport.DONNEES, "documents", "feuille-de-previsions.pdf")
    larg, haut = landscape(A4)
    marge, ecart = 0.9 * cm, 0.35 * cm
    lf, hc = (larg - 2 * marge - ecart) / 2, haut - 2 * marge
    histoire = _feuille(lire(), larg, haut, marge, t, B, colors)

    def construire(chemin_):
        doc = BaseDocTemplate(chemin_, pagesize=(larg, haut), leftMargin=marge, rightMargin=marge, topMargin=marge,
                              bottomMargin=marge, title="Feuille de prévisions", author="")
        doc.addPageTemplates([PageTemplate(id="feuille", frames=[
            Frame(marge + k * (lf + ecart), marge, lf, hc, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
                  id=f"f{k}") for k in range(2)])])
        doc.build(histoire)
    return _ecrire_pdf(sortie, construire)


def pdf_ffb(sortie=None):
    """La carte de conventions FFB SEF, recto verso, A4 à l'italienne, comme la carte officielle : au recto trois colonnes
    (enchères compétitives ; entames et signalisation, puis les conventions, celles qu'on ne joue pas rayées ; le nom et
    le classement, puis le résumé du système), au verso le tableau des ouvertures. Renvoie son chemin
    (<documents>/carte-de-conventions-ffb.pdf)."""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Table, TableStyle, KeepInFrame,
                                    FrameBreak, NextPageTemplate, Spacer, PageBreak)
    colors, B, t = _commun()
    x = lire()
    sortie = sortie or os.path.join(rapport.DONNEES, "documents", "carte-de-conventions-ffb.pdf")
    VERT, ROUGE, NOIR = colors.HexColor("#1f8a2e"), colors.HexColor("#d4141c"), colors.black
    tete = B.st("ffb_t", fontName="DVB", fontSize=11, leading=14, alignment=1, textColor=VERT)
    titre_s = B.st("ffb_ts", fontName="DVB", fontSize=8.6, leading=10.4, textColor=NOIR)
    ligne = B.st("ffb_l", fontName="DV", fontSize=8, leading=9.8, textColor=NOIR)
    petit = B.st("ffb_p", fontName="DV", fontSize=6.6, leading=8, textColor=colors.HexColor("#333333"))
    entete_rouge = B.st("ffb_r", fontName="DVB", fontSize=10, leading=12.5, alignment=1, textColor=ROUGE)
    bande = B.st("ffb_b", fontName="DVB", fontSize=10.5, leading=13, alignment=1, textColor=colors.white)
    val = lambda c: texte(c, x)
    joue = lambda c: bool(valeur(c, x)[0])

    titre_de = {s: n for s, n, _, _ in TOUTES}

    def lignes_de(section):
        """Les lignes d'une section : « Titre : texte » ; les conventions jouées, à la suite."""
        ls = [i for s, _, _, l in TOUTES if s == section for i in l]
        out = [Paragraph(f"<b>{t(i['titre'])}</b> : " + (coches_texte(i["cle"], x, t) if i.get("autre") and
                                                         i["type"] == "cases" else t(val(i["cle"]))), ligne)
               for i in ls if i["type"] != "oui" and val(i["cle"])]
        oui = [t(i["titre"]) for i in ls if i["type"] == "oui" and joue(i["cle"]) and i["titre"] != titre_de[section]]
        if oui: out.insert(1 if section == "principes" else 0, Paragraph(" · ".join(oui), ligne))
        return out

    def boite(titre, contenu):
        return [Paragraph(t(titre).upper(), titre_s)] + contenu

    def colonne(entete, blocs, largeur):
        """Une colonne de la carte : un cadre, son titre, des cases séparées d'un trait."""
        rangs = [[entete]] + [[b] for b in blocs]
        tab = Table(rangs, colWidths=[largeur])
        st = [("BOX", (0, 0), (-1, -1), .8, NOIR), ("LINEBELOW", (0, 0), (-1, -2), .6, NOIR),
              ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4),
              ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3),
              ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (0, 0), 7), ("BOTTOMPADDING", (0, 0), (0, 0), 7)]
        tab.setStyle(TableStyle(st))
        return tab

    def ouv(rid, col):
        return val(f"ouv_{rid}_{col}")

    larg, haut = landscape(A4)
    marge = 0.9 * cm
    ecart = 0.35 * cm
    lc = (larg - 2 * marge - 2 * ecart) / 3
    hc = haut - 2 * marge
    cadres = [Frame(marge + k * (lc + ecart), marge, lc, hc, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
                    id=f"c{k}") for k in range(3)]
    verso = Frame(marge, marge, larg - 2 * marge, hc, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    lci = lc - 8

    # --- à gauche : les enchères compétitives
    comp = [boite(titre, lignes_de(s)) for s, titre, col, _ in SECTIONS if col == "competitives"]
    gauche = colonne(Paragraph("ENCHÈRES COMPÉTITIVES", tete), comp, lc)
    # --- au milieu : les entames et la signalisation, puis les conventions (celles qu'on ne joue pas, rayées)
    ent = [boite(titre, lignes_de(s)) for s, titre, col, _ in SECTIONS if col == "entames"]
    conv = [i for s, _, col, ls in SECTIONS if col == "conventions" for i in ls]
    noms = []
    jouees = [(i["titre"], joue(i["cle"])) for i in conv if i["type"] == "oui"]
    jouees.insert(3, ("Landy", valeur("def_sa_2t", x)[0] == "Landy"))          # sur la feuille : des choix
    jouees.insert(6, ("Michaels précisé", valeur("bic_maj_cue", x)[0] == ITEMS["bic_maj_cue"]["defaut"]))
    for n, oui in jouees:
        n = t(n)
        noms.append(n if oui else f'<strike><font color="#8a8a8a">{n}</font></strike>')
    if val("autres_conventions"): noms.append(f"<br/><b>Autres :</b> {t(val('autres_conventions'))}")
    ent.append([Paragraph("CONVENTIONS", titre_s), Paragraph("(Rayez les conventions non jouées)", petit),
                Paragraph("    ".join(noms), B.st("ffb_cv", fontName="DV", fontSize=8.2, leading=11.5))])
    milieu = colonne(Paragraph("ENTAMES ET SIGNALISATION", tete), ent, lc)
    # --- à droite : le nom et le classement, puis le résumé du système
    x = dict(x, joueur1=joueur(x, 1), joueur2=joueur(x, 2))
    x["classement1"] = f"IV {x['classement1']}" if x.get("classement1") else ""
    x["classement2"] = f"IV {x['classement2']}" if x.get("classement2") else ""
    nom = lambda j, c: Paragraph(f"<b>{t(x.get(j) or ' ')}</b><br/>{t(x.get(c) or '')}" if x.get(j)
                                 else '<font color="#777777">Nom du joueur</font><br/> ', B.st("ffb_n", fontName="DV",
                                 fontSize=8.6, leading=11, alignment=1))
    tab_noms = Table([[nom("joueur1", "classement1"), nom("joueur2", "classement2")]], colWidths=[lci / 2] * 2)
    tab_noms.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 1),
                                  ("RIGHTPADDING", (0, 0), (-1, -1), 1)]))
    couv = [Paragraph("CARTE DE CONVENTIONS FFB SEF<br/>NOM ET CLASSEMENT", entete_rouge), Spacer(1, 5), tab_noms]
    resume = []
    for s, titre, col, _ in SECTIONS:
        if col != "resume": continue
        c = lignes_de(s)
        if s == "principes":
            c.insert(2, Paragraph(f"<b>1SA</b> {t(ouv('1sa', 'desc'))} · <b>2SA</b> {t(ouv('2sa', 'desc'))}", ligne))
        if s == "fortes":
            c = [Paragraph(f"<b>{t(n)}</b> {t(ouv(r, 'desc'))}", ligne) for r, n in (("2sa", "2SA"), ("2t", "2♣"), ("2k", "2♦"))]
        if s == "barrages":
            c = [Paragraph("(indiquez d'abord les ouvertures artificielles)", petit)]
            if joue("multi"): c.append(Paragraph("<b>Multi 2♦</b>", ligne))
            for r, n in (("2m", "2♥ / 2♠"), ("3x", "3♣ / ♦ / ♥ / ♠"), ("3sa", "3SA"), ("4x", "4♣ / ♦ / ♥ / ♠")):
                m = ouv(r, "mini")
                c.append(Paragraph(f"<b>{t(n)}</b> {t(ouv(r, 'desc'))}" + (f", {t(m)} cartes" if m else ""), ligne))
        if s == "contre_n2" and joue("truscott_majeur"):
            c.append(Paragraph("Convention Truscott", ligne))
        resume.append(boite(titre, c))
    droite = Table([[couv], [Paragraph("RÉSUMÉ DU SYSTÈME", bande)]] + [[b] for b in resume], colWidths=[lc])
    droite.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), .8, NOIR), ("LINEBELOW", (0, 0), (-1, -2), .6, NOIR),
                                ("BACKGROUND", (0, 1), (0, 1), NOIR), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                                ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                                ("TOPPADDING", (0, 0), (0, 0), 7), ("BOTTOMPADDING", (0, 0), (0, 0), 8)]))
    histoire = [NextPageTemplate("verso")]
    for k, col in enumerate((gauche, milieu, droite)):
        histoire.append(KeepInFrame(lc, hc, [col], mode="shrink"))
        histoire.append(FrameBreak() if k < 2 else PageBreak())

    # --- le verso : le tableau des ouvertures
    th = B.st("ffb_th", fontName="DVB", fontSize=7.4, leading=9, alignment=1, textColor=colors.white)
    td = B.st("ffb_td", fontName="DV", fontSize=7.8, leading=9.6, textColor=NOIR)
    tdc = B.st("ffb_tdc", fontName="DVB", fontSize=9.5, leading=11.5, alignment=1, textColor=NOIR)
    tdm = B.st("ffb_tdm", fontName="DV", fontSize=8.4, leading=10, alignment=1, textColor=NOIR)
    titres = ["OUVERTURE", "Cocher si artificiel", "Nombre mini de cartes", "DESCRIPTION", "CONTRES NÉGATIFS Jusqu'à",
              "RÉPONSES (ainsi que les modifications après interventions)", "SUITE des ENCHÈRES",
              "CHANGEMENTS après INTERVENTION et PASSE"]
    rangs = [[Paragraph(h, th) for h in titres]]
    for rid, n, _, cols in OUVERTURES:
        art = "✔" if joue(f"ouv_{rid}_art") else ""
        cn = ouv(rid, "cn") if rid in UN_PALIER else ""
        rangs.append([Paragraph(t(n), tdc), Paragraph(art, tdm), Paragraph(t(ouv(rid, "mini")), tdm),
                      Paragraph(t(ouv(rid, "desc")), td), Paragraph(t(cn), td), Paragraph(t(ouv(rid, "rep")), td),
                      Paragraph(t(ouv(rid, "suite")), td), Paragraph(t(ouv(rid, "chg")), td)])
    lv = larg - 2 * marge
    parts = [.075, .055, .055, .13, .075, .23, .17, .21]
    tab = Table(rangs, colWidths=[lv * p for p in parts], repeatRows=1)
    tab.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .6, NOIR), ("BACKGROUND", (0, 0), (-1, 0), NOIR),
                             ("VALIGN", (0, 0), (-1, 0), "MIDDLE"), ("VALIGN", (0, 1), (-1, -1), "MIDDLE"),
                             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                             ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
    verso_h = [tab]
    if (x.get("accords") or "").strip():
        verso_h += [Spacer(1, 8), Paragraph("<b>AUTRES ACCORDS</b>", titre_s),
                    Paragraph(t(x["accords"]).replace("\n", "<br/>"), ligne)]
    verso_h.append(Spacer(1, 6))
    verso_h.append(Paragraph(f"Établie le {datetime.date.today():%d/%m/%Y}", petit))   # les adversaires la voient
    histoire.append(KeepInFrame(lv, hc, verso_h, mode="shrink"))

    def construire(chemin_):
        doc = BaseDocTemplate(chemin_, pagesize=(larg, haut), leftMargin=marge, rightMargin=marge, topMargin=marge,
                              bottomMargin=marge, title="Carte de conventions FFB SEF", author="")
        doc.addPageTemplates([PageTemplate(id="recto", frames=cadres), PageTemplate(id="verso", frames=[verso])])
        doc.build(histoire)
    return _ecrire_pdf(sortie, construire)


def pdf_partenaire(sortie=None):
    """La fiche pour en parler avec un partenaire : A4 en hauteur, en gros caractères, dans l'esprit des feuilles de
    club. Les ouvertures en un tableau, les conventions en Oui / Non, les lignes principales, puis « Ce que nous jouons
    hors SEF standard » et « À vérifier ensemble », sans jamais nommer le programme. Renvoie son chemin (<documents>/fiche-pour-mon-partenaire.pdf)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, KeepTogether, Spacer
    colors, B, t = _commun()
    x = lire()
    sortie = sortie or os.path.join(rapport.DONNEES, "documents", "fiche-pour-mon-partenaire.pdf")
    titre = B.st("fp_t", fontName="DVB", fontSize=17, leading=21, spaceAfter=2)
    sous = B.st("fp_s", fontName="DV", fontSize=10, leading=13, textColor=colors.HexColor("#555"))
    h = B.st("fp_h", fontName="DVB", fontSize=12.5, leading=15.5, textColor=colors.HexColor(B.GREEN), spaceBefore=9,
             spaceAfter=4)
    cel = B.st("fp_c", fontName="DV", fontSize=10, leading=12.6)
    cel_b = B.st("fp_cb", fontName="DVB", fontSize=10, leading=12.6)
    gris = colors.HexColor("#dddddd")
    val = lambda c: texte(c, x)
    def marque(*cles):
        """≠ : un choix hors SEF standard ; ? : à vérifier ensemble."""
        m = ""
        cles = [c for c in cles if c in ITEMS]
        if any(valeur(c, x)[1] for c in cles): m += ' <font color="#1565c0"><b>≠</b></font>'
        if any(a_verifier(c, x) for c in cles): m += ' <font color="#b35c00"><b>?</b></font>'
        return m
    style_lignes = TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), .3, gris),
                               ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                               ("LEFTPADDING", (0, 0), (-1, -1), 3)])
    larg = A4[0] - 3.2 * cm
    histoire = [Paragraph("Nos conventions", titre),
                Paragraph("Pour discuter avec votre partenaire — en compétition, utilisez la feuille FFB.",
                          B.st("fp_comp", fontName="DVI", fontSize=8, leading=10, textColor=colors.HexColor("#666666"),
                               spaceAfter=3))]
    if joueurs(x): histoire.append(Paragraph(t(joueurs(x)), B.st("fp_j", fontName="DVB", fontSize=12, leading=15)))
    # une fiche entre deux partenaires : jamais le nom du programme (l'utilisateur, 2026-11-14)
    histoire.append(Paragraph(f"Une fiche à discuter ensemble, établie le {datetime.date.today():%d/%m/%Y}. "
                              f"<font color='#1565c0'><b>≠</b></font> : un choix hors SEF standard ; "
                              f"<font color='#b35c00'><b>?</b></font> : à vérifier ensemble.", sous))
    if x.get("niveau"): histoire.append(Paragraph(f"Compétition : {t(x['niveau'])}", sous))
    histoire.append(Paragraph("Méthode de base : " + t(val("systeme")) + marque("systeme"),
                              B.st("fp_sys", fontName="DVB", fontSize=11, leading=14, spaceBefore=5)))
    # la feuille de prévisions : ouvertures, interventions, flanc
    for partie, groupes in FEUILLE:
        rangs, style = [], [("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (-1, -1), 3)]
        for sous, cles in groupes:
            if sous:
                style += [("SPAN", (0, len(rangs)), (-1, len(rangs))), ("TOPPADDING", (0, len(rangs)), (-1, len(rangs)), 6)]
                rangs.append([Paragraph(f"<b>{t(sous)}</b>", cel_b), ""])
            for c in cles:
                it = ITEMS[c]
                v = val(c) or ("—" if it["type"] != "oui" else "")
                v = coches_texte(c, x, t) if it["type"] == "cases" and it.get("autre") else t(v)
                rangs.append([Paragraph(t(titre_feuille(c)), cel), Paragraph(v + marque(c), cel)])
                style.append(("LINEBELOW", (0, len(rangs) - 1), (-1, len(rangs) - 1), .3, gris))
        tab = Table(rangs, colWidths=[6.4 * cm, larg - 6.4 * cm]); tab.setStyle(TableStyle(style))
        histoire += [Paragraph(partie, h), tab]
    # nos choix hors SEF standard, puis ce qui est à vérifier ensemble
    nom_section = {s: titre_ for s, titre_, _, _ in TOUTES}
    groupe = {c: sous or partie for partie, g in FEUILLE for sous, cs in g for c in cs}
    lib = lambda i: f"{groupe[i['cle']]} — {titre_feuille(i['cle'])}" if i["cle"] in SUR_FEUILLE else f"{nom_section[i['section']]} — {i['titre']}"
    autres = [i for i in ITEMS.values() if valeur(i["cle"], x)[1]]
    if autres:
        rangs = [[Paragraph(t(lib(i)), cel_b),
                  Paragraph(t(val(i["cle"])) +
                            f'<br/><font color="#777777" size="8.5">SEF standard : '
                            f'{t(texte(i["cle"], defaut=True) or RIEN)}</font>', cel)]
                 for i in autres]
        tab = Table(rangs, colWidths=[6 * cm, larg - 6 * cm]); tab.setStyle(style_lignes)
        histoire += [KeepTogether([Paragraph("Nos choix hors SEF standard", h), tab])]
    verif = [c for c in ["systeme"] + SUR_FEUILLE if a_verifier(c, x)]           # les lignes de cette fiche seulement
    if verif:
        par_groupe = {}                                       # « 1SA : Stayman, Rectification fittée »
        for c in verif:
            g_ = "Méthode de base" if c == "systeme" else groupe[c]
            if g_ in ("Sans-atout", "Couleur"): g_ = f"Flanc à {'sans-atout' if g_ == 'Sans-atout' else 'la couleur'}"
            par_groupe.setdefault(g_, []).append("" if c == "systeme" else titre_feuille(c))
        rangs = [[Paragraph(t(g_), cel_b), Paragraph(t(", ".join(n for n in ns if n) or "—"), cel)]
                 for g_, ns in par_groupe.items()]
        tab = Table(rangs, colWidths=[6.4 * cm, larg - 6.4 * cm]); tab.setStyle(style_lignes)
        histoire += [KeepTogether([Paragraph("À vérifier ensemble", h), tab])]
    histoire.append(Paragraph("Nos accords particuliers", h))
    if (x.get("accords") or "").strip():
        histoire.append(Paragraph(t(x["accords"]).replace("\n", "<br/>"), cel))
    else:                                                     # des lignes pour écrire à la main
        blanc = Table([[""]] * 4, colWidths=[larg], rowHeights=[0.75 * cm] * 4)
        blanc.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), .4, colors.HexColor("#999999"))]))
        histoire.append(blanc)

    def construire(chemin_):
        SimpleDocTemplate(chemin_, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.4 * cm,
                          bottomMargin=1.4 * cm, title="Nos conventions", author="").build(histoire)
    return _ecrire_pdf(sortie, construire)
