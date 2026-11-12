# -*- coding: utf-8 -*-
"""Réglages › Votre système : la fiche de conventions de la paire, modifiable, à imprimer ou garder en PDF pour un
partenaire.

Chaque ligne part de ce que joue Bridge Coach (le système de systems/sef-2024/, écrit ici pour un joueur, sans les
notes du programme) ; la paire change ce qu'elle joue autrement. Seules les lignes changées sont gardées, dans
<dossier de travail>/documents/fiche-conventions.json (la sauvegarde l'emporte) : « Revenir au système de Bridge Coach »
efface le changement. Une ligne que le système marque « à confirmer » est dite « à vérifier » tant qu'on ne l'a pas
réécrite. La fiche ne change pas ce que jouent les robots.
"""
import json, os, datetime

import rapport

# (section, [(clé, intitulé, ce que joue Bridge Coach, à vérifier)])
MODELE = [
    ("Général", [
        ("systeme", "Système", "SEF 2024 (Système d'Enseignement Français), naturel, majeures 5e", False),
        ("ouverture_3e", "En 3e position", "Ouverture légère dès 8 H avec la règle des 20, ou 10 H avec neuf cartes dans "
                                            "les majeures ; un deux faible ou un barrage passe d'abord", False),
        ("ouverture_4e", "En 4e position", "12 H et plus, ou 10–11 H avec une 6e ; sinon la règle des 15 (H + piques)", False),
    ]),
    ("Ouvertures", [
        ("1t", "1♣", "12–21 H, 3 cartes et plus", True),
        ("1k", "1♦", "12–21 H, 4 cartes et plus (sauf exceptions)", True),
        ("1m", "1♥ / 1♠", "12–21 H, 5 cartes et plus", False),
        ("1sa", "1SA", "15–17 H, régulier", True),
        ("2t", "2♣", "Fort indéterminé", True),
        ("2k", "2♦", "Forcing de manche", True),
        ("2m", "2♥ / 2♠", "Faible, 6 cartes", True),
        ("2sa", "2SA", "20–21 H, régulier", True),
        ("barrages", "Barrages", "Au palier de 3 : 7 cartes, faible", True),
    ]),
    ("Réponses et suites", [
        ("rep_mineure", "Sur 1♣ / 1♦", "Majeure 4e et mineure 5e : la majeure d'abord avec 5–11 H ; forcing de manche, "
                                       "la couleur la plus longue d'abord", False),
        ("sur_1sa", "Sur 1SA", "2♣ Stayman ; 2♦ / 2♥ texas ; 4SA quantitatif", False),
        ("sur_2sa", "Sur 2SA", "3♣ Stayman ; 3♦ / 3♥ texas ; 4SA quantitatif ; 4♣ / 4♦ : 6e, essai de chelem", True),
        ("sur_faibles", "Sur un deux faible ou un barrage", "La manche en majeure avec dix atouts ensemble, pour jouer "
                                                             "(loi des levées)", True),
        ("4e_couleur", "4e couleur", "Forcing, 11 H et plus, sans arrêt dans la couleur", False),
        ("drury", "Drury", "2♣ d'un partenaire qui a passé, sur 1♥ / 1♠ en 3e ou 4e : soutien et 10–11 points", True),
        ("bicolore_cher", "Redemande de l'ouvreur", "Deuxième couleur plus chère avec saut : 18 HL et plus, forcing", True),
    ]),
    ("Concurrence", [
        ("interv_1sa", "Intervention à 1SA", "15–18 H, régulier, arrêt dans leur couleur", False),
        ("interv_1", "Couleur au palier de 1", "5 cartes et plus, 8–16 H", False),
        ("interv_2", "Couleur au palier de 2", "Bonne 5e ou 6e, 11–16 H", False),
        ("saut_faible", "Saut", "Faible : 6 cartes, 6–10 H", False),
        ("bicolores", "Bicolores (5-5, 8–18 H, alertés)", "Sur 1♣ / 1♦ : 2♦ = les majeures, 2SA = les deux plus basses "
                                                           "libres. Sur 1♥ / 1♠ : cue-bid = trèfle et l'autre majeure "
                                                           "(Michaels), 2SA = les mineures, 3♣ = carreau et l'autre "
                                                           "majeure", True),
        ("contre_appel", "Contre d'appel", "12 H et plus, court dans leur couleur, 3 cartes dans les majeures libres ; "
                                           "ou 17 H et plus, toute forme", False),
        ("sur_1sa_adv", "Sur leur 1SA", "Couleur 6e naturelle au palier de 2 ; contre = 15 H et plus, punitif", False),
        ("sur_barrage", "Sur un barrage de 3", "Couleur 6e, 10–17 H ; contre d'appel 15 H et plus", True),
        ("reveil", "Réveil", "Les mêmes enchères avec 3 points de moins", False),
        ("spoutnik", "Contre Spoutnik", "6 H et plus, 4 cartes dans la ou les majeures non nommées", False),
        ("cue_bid", "Cue-bid de leur couleur", "Soutien et force : 4 atouts et 13 HLD sur une majeure, forcing de manche",
         True),
        ("loi", "Partielles disputées", "Loi des levées totales : jusqu'au palier égal au nombre d'atouts moins 6", False),
    ]),
    ("Chelem", [
        ("blackwood", "Demande de clés", "Blackwood 3041", False),
        ("controles", "Contrôles", "Après un fit, on nomme ses contrôles (as ou chicane, roi ou singleton) dès 28 points "
                                   "ensemble ; sauter une couleur la nie", False),
        ("quantitatif", "4SA quantitatif", "Sur 1SA et 2SA, même après un texas", False),
    ]),
    ("Entames", [
        ("entame_couleur", "Couleur", "Celle du partenaire ; sinon une séquence ; contre une couleur, jamais sous un as ; "
                                      "un singleton pour couper", False),
        ("entame_sequence", "Séquence", "La tête (R de RD, D de DV) ; l'as de AR", False),
        ("entame_honneur", "Avec un honneur", "4e meilleure ; la plus petite de trois cartes", False),
        ("entame_petites", "Sans honneur", "Doubleton : la plus haute ; trois petites : la plus haute ; quatre petites : "
                                           "la deuxième", True),
    ]),
    ("Signalisation", [
        ("sig_entame", "Sur l'entame du partenaire", "Pair-impair : impaire = continuez ; paire = changez, haute (7 et "
                                                     "plus) vers la plus chère des deux autres couleurs, basse vers la "
                                                     "moins chère", False),
        ("sig_defausse", "En défausse", "Préférence : dans une couleur dont on ne veut pas ; haute = la plus chère des "
                                        "deux autres, basse = la moins chère", False),
        ("sig_parite", "Quand le déclarant mène", "Parité : grosse puis petite avec un nombre pair, la plus petite avec "
                                                  "un nombre impair", False),
        ("sig_atout", "À l'atout", "Pas de signal", False),
    ]),
]
LIGNES = {cle: (section, titre, defaut, incertain) for section, ls in MODELE for cle, titre, defaut, incertain in ls}


def chemin():
    return os.path.join(rapport.DONNEES, "documents", "fiche-conventions.json")


def lire():
    """{"joueurs": "…", "accords": "…", "valeurs": {clé: texte}} : seulement ce que la paire a changé."""
    try:
        x = json.load(open(chemin(), encoding="utf-8"))
        return x if isinstance(x, dict) else {}
    except (OSError, ValueError):
        return {}


def ecrire(x):
    os.makedirs(os.path.dirname(chemin()), exist_ok=True)
    provisoire = chemin() + ".provisoire"
    with open(provisoire, "w", encoding="utf-8") as f: json.dump(x, f, ensure_ascii=False, indent=1)
    os.replace(provisoire, chemin())


def valeur(cle, fiche=None):
    """(le texte de la ligne, changé par la paire ?)."""
    v = ((fiche if fiche is not None else lire()).get("valeurs") or {}).get(cle)
    return (v, True) if v is not None else (LIGNES[cle][2], False)


def changer(cle, texte):
    """Garde le texte de la paire ; le même que Bridge Coach, ou vide : la ligne revient au système."""
    x = lire(); vals = x.setdefault("valeurs", {})
    t = (texte or "").strip()
    if not t or t == LIGNES[cle][2]: vals.pop(cle, None)
    else: vals[cle] = t
    ecrire(x)


def changer_entete(**champs):
    x = lire(); x.update({k: (v or "").strip() for k, v in champs.items()}); ecrire(x)


def tout_remettre():
    """Toutes les lignes reviennent au système de Bridge Coach ; les noms et les accords particuliers restent."""
    x = lire(); x.pop("valeurs", None); ecrire(x)


# ---------------------------------------------------------------- le PDF
def pdf(sortie=None):
    """La fiche en PDF, A4, à imprimer ou à envoyer ; renvoie son chemin (<documents>/fiche-de-conventions.pdf)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, KeepTogether
    import build_pdf as B                                    # les polices DejaVu et les cœurs et carreaux en rouge
    from xml.sax.saxutils import escape
    x = lire()
    sortie = sortie or os.path.join(rapport.DONNEES, "documents", "fiche-de-conventions.pdf")
    titre = B.st("fc_t", fontName="DVB", fontSize=15, leading=19, spaceAfter=2)
    sous = B.st("fc_s", fontName="DV", fontSize=9.5, leading=12, textColor=colors.HexColor("#555"))
    h = B.st("fc_h", fontName="DVB", fontSize=10.5, leading=13, textColor=colors.HexColor(B.INK), spaceBefore=7, spaceAfter=3)
    cel = B.st("fc_c", fontName="DV", fontSize=8.6, leading=10.8)
    cel_b = B.st("fc_cb", fontName="DVB", fontSize=8.6, leading=10.8)
    t = lambda s: B.suits(escape(s))
    story = [Paragraph("Fiche de conventions", titre)]
    if x.get("joueurs"): story.append(Paragraph(t(x["joueurs"]), B.st("fc_j", fontName="DVB", fontSize=11, leading=14)))
    story.append(Paragraph(f"Système de base : SEF 2024 · établie le {datetime.date.today():%d/%m/%Y} avec Bridge Coach", sous))
    for section, lignes in MODELE:
        rangs = [[Paragraph(t(titre_l), cel_b), Paragraph(t(valeur(cle, x)[0]), cel)] for cle, titre_l, _, _ in lignes]
        tab = Table(rangs, colWidths=[4.3 * cm, 13.3 * cm])
        tab.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), .3, colors.HexColor("#dddddd")),
                                 ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 3)]))
        story.append(KeepTogether([Paragraph(section, h), tab]))
    if (x.get("accords") or "").strip():
        story += [Paragraph("Nos accords particuliers", h),
                  Paragraph(t(x["accords"]).replace("\n", "<br/>"), cel)]
    os.makedirs(os.path.dirname(sortie), exist_ok=True)
    provisoire = sortie[:-4] + ".provisoire.pdf"
    SimpleDocTemplate(provisoire, pagesize=A4, leftMargin=1.7 * cm, rightMargin=1.7 * cm, topMargin=1.4 * cm,
                      bottomMargin=1.4 * cm, title="Fiche de conventions", author="Bridge Coach").build(story)
    os.replace(provisoire, sortie)
    return sortie
