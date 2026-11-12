# -*- coding: utf-8 -*-
"""Réglages › Votre système : la fiche de conventions de la paire, modifiable, à imprimer ou garder en PDF pour un
partenaire. Les enchères : les conventions principales, Oui ou Non. Le jeu de la carte : quelques lignes à réécrire.

Chaque ligne part de ce que joue Bridge Coach (le système de systems/sef-2024/, écrit ici pour un joueur, sans les
notes du programme) ; la paire change ce qu'elle joue autrement. Seules les lignes changées sont gardées, dans
<dossier de travail>/documents/fiche-conventions.json (la sauvegarde l'emporte) : « Revenir au système de Bridge Coach »
efface le changement. Une ligne que le système marque « à confirmer » est dite « à vérifier » tant qu'on ne l'a pas
réécrite. La fiche ne change pas ce que jouent les robots.
"""
import json, os, datetime

import rapport

# Les enchères : les conventions principales, à cocher Oui ou Non (l'utilisateur, 2026-11-12 : « juste oui ou non ») :
# (clé, nom, ce qu'elle dit en quelques mots, jouée par Bridge Coach, à vérifier). Bridge Coach joue celles à True.
CONVENTIONS = [
    ("majeures5", "Majeures 5e", "1♥ / 1♠ : 5 cartes au moins", True, False),
    ("meilleure_mineure", "Meilleure mineure", "1♣ / 1♦ : la mineure la plus longue, 3 cartes au moins", True, True),
    ("barrages", "Barrages", "Au palier de 3 : 7 cartes, main faible", True, True),
    ("stayman", "Stayman", "2♣ sur 1SA, 3♣ sur 2SA : demande des majeures 4e", True, False),
    ("texas", "Texas", "2♦ / 2♥ sur 1SA, 3♦ / 3♥ sur 2SA : transfert vers la majeure", True, False),
    ("deux_faibles", "Deux faibles", "2♥ / 2♠ : 6 cartes, main faible", True, True),
    ("deux_forts", "2♣ fort, 2♦ forcing de manche", "Les deux ouvertures fortes du SEF", True, True),
    ("quatrieme", "Quatrième couleur forcing", "La 4e couleur du répondant : forcing, 11 H et plus", True, False),
    ("drury", "Drury", "2♣ d'un partenaire qui a passé, sur 1♥ / 1♠ : soutien limite", True, True),
    ("contre_appel", "Contre d'appel", "Court dans leur couleur, les autres couleurs", True, False),
    ("spoutnik", "Contre Spoutnik", "Après leur intervention : la ou les majeures non nommées", True, False),
    ("cue_bid", "Cue-bid de soutien", "Leur couleur : soutien du partenaire et force", True, True),
    ("michaels", "Michaels", "Le cue-bid sur leur ouverture : bicolore 5-5", True, True),
    ("sa_bicolore", "2SA bicolore", "Sur leur ouverture : les deux couleurs les plus basses libres", True, True),
    ("loi", "Loi des levées totales", "Disputer jusqu'au palier égal au nombre d'atouts moins 6", True, False),
    ("blackwood", "Blackwood 3041", "4SA : les clés (cinq, avec le roi d'atout)", True, False),
    ("controles", "Contrôles", "Après un fit, on nomme ses as, rois, singletons et chicanes", True, False),
    ("quantitatif", "4SA quantitatif", "Sur 1SA et 2SA : invitation au chelem", True, False),
    ("landy", "Landy", "2♣ sur leur 1SA : les deux majeures", False, False),
    ("roudi", "Roudi", "2♣ du répondant après la redemande à 1SA : demande", False, False),
    ("lebensohl", "Lebensohl", "2SA après leur intervention sur 1SA, ou leur deux faible contré", False, False),
    ("splinter", "Splinter", "Saut dans une couleur courte : fit et singleton ou chicane", False, False),
    ("multi", "Multi 2♦", "2♦ : un deux faible en majeure, ou une main forte", False, False),
]
CONV = {c[0]: c for c in CONVENTIONS}

# Le système en une ligne, puis le jeu de la carte : (section, [(clé, intitulé, ce que joue Bridge Coach, à vérifier)])
MODELE = [
    ("Général", [
        ("systeme", "Système", "SEF 2024, naturel, 1SA 15–17 H", False),
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


def convention(cle, fiche=None):
    """(jouée par la paire ?, changé par rapport à Bridge Coach ?)."""
    v = ((fiche if fiche is not None else lire()).get("conventions") or {}).get(cle)
    return (v, True) if v is not None and v != CONV[cle][3] else (CONV[cle][3], False)


def choisir_convention(cle, oui):
    """Oui ou Non pour la paire ; le même choix que Bridge Coach n'est pas gardé (la ligne revient au système)."""
    x = lire(); cs = x.setdefault("conventions", {})
    if bool(oui) == CONV[cle][3]: cs.pop(cle, None)
    else: cs[cle] = bool(oui)
    ecrire(x)


def changer_entete(**champs):
    x = lire(); x.update({k: (v or "").strip() for k, v in champs.items()}); ecrire(x)


def tout_remettre():
    """Toutes les lignes reviennent au système de Bridge Coach ; les noms et les accords particuliers restent."""
    x = lire(); x.pop("valeurs", None); x.pop("conventions", None); ecrire(x)


# ---------------------------------------------------------------- le PDF
def pdf(sortie=None):
    """La fiche en PDF, A4, à imprimer ou à envoyer ; renvoie son chemin (<documents>/fiche-de-conventions.pdf)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, KeepTogether
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
    story.append(Paragraph(f"Établie le {datetime.date.today():%d/%m/%Y} avec Bridge Coach", sous))
    general = MODELE[0][1]
    story.append(Paragraph(t(valeur(general[0][0], x)[0]), B.st("fc_sys", fontName="DVB", fontSize=10, leading=13, spaceBefore=4)))
    story.append(Paragraph("Conventions d'enchères", h))
    oui_non = lambda c: ('<font color="#1f6b45"><b>✔ Oui</b></font>' if convention(c, x)[0]
                         else '<font color="#999999">✘ Non</font>')
    cases = [[Paragraph(f"<b>{t(nom)}</b><br/><font size=7.4 color='#666666'>{t(desc)}</font>", cel), Paragraph(oui_non(c), cel)]
             for c, nom, desc, _, _ in CONVENTIONS]
    moitie = (len(cases) + 1) // 2
    rangs = [cases[i] + (cases[i + moitie] if i + moitie < len(cases) else ["", ""]) for i in range(moitie)]
    tab = Table(rangs, colWidths=[6.6 * cm, 1.95 * cm, 6.6 * cm, 1.95 * cm])
    tab.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), .3, colors.HexColor("#dddddd")),
                             ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
                             ("LEFTPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (2, 0), (2, -1), 12)]))
    story.append(tab)
    for section, lignes in MODELE[1:]:
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
