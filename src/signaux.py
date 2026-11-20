# -*- coding: utf-8 -*-
"""La signalisation de la défense, en un seul endroit : la méthode du SEF 2024 (chapitre 11, p. 83–85), complétée
là où le livre ne dit rien (systems/sef-2024/entames.md, « Notre signalisation » ; l'utilisateur, 2026-11-20 : « use the
book … we need to develop our method »). Le défenseur qui signale (carte.Partie) et celui qui lit (carte.Partie,
modele.Modele, les pensées) passent par ces fonctions : un robot lit son partenaire comme il aurait signalé lui-même.

  - Sur l'entame (ou la couleur menée) du partenaire, la première carte : le sens dépend de la carte menée
    (mode_entame). À sans-atout, sur l'As ou la Dame : appel-refus (une grosse carte inutile = continuez, la plus
    petite = changez) ; sur le Roi : débloquer un honneur, sinon la parité ; sur une petite carte : la parité. À la
    couleur, sur l'As ou le Roi : appel-refus quand le mort a trois petites cartes (ou qu'on ne le voit pas encore),
    préférence quand il a un singleton, la parité sinon ; sur une autre carte : la parité.
  - Quand le déclarant mène : la parité, grosse puis petite avec un nombre pair de cartes.
  - En défausse : la parité dans une couleur qu'on ne veut pas ; en urgence (une couleur nettement meilleure que les
    autres pour la défense), une grosse carte de cette couleur l'appelle : « appel direct ».
  - En donnant une coupe au partenaire (notre ajout, éteint : carte.PREF_COUPE) : la hauteur demande le retour.
  - Jamais à l'atout ; les honneurs ne signalent pas.

Une carte « grosse » est un 7 ou plus, « petite » un 6 ou moins : celui qui lit ne voit pas les autres petites cartes
du signaleur, la frontière est fixe, comme à la table. Ce que le défenseur veut (continuer, ou quelle couleur) vient
de ses donnes imaginées (carte.Partie.voeu), selon la situation. Les cartes sont en rangs anglais (« T » = 10) ou
français (« X »).
"""
COULEURS = ["♠", "♥", "♦", "♣"]                           # de la plus chère à la moins chère
VALEUR = {"T": 10, "X": 10, "9": 9, "8": 8, "7": 7, "6": 6, "5": 5, "4": 4, "3": 3, "2": 2}
HAUTE = 7                                                  # 7 et plus : une carte haute ; 6 et moins : une basse
# (celui qui lit ne voit pas les autres petites cartes du signaleur : la frontière est fixe, comme à la table)


def petite(r):
    return r in VALEUR


def impaire(r):
    return petite(r) and VALEUR[r] % 2 == 1


def autres(den, c_exclue, c_menee=None):
    """Les deux couleurs entre lesquelles un signal de préférence choisit, de la plus chère à la moins chère : à la
    couleur, les deux couleurs hors atout autres que c_exclue ; à sans-atout, les deux autres que c_exclue et la
    couleur menée (c_menee)."""
    sans = {c_exclue} | ({den} if den in COULEURS else {c_menee})
    xs = [c for c in COULEURS if c not in sans]
    return [xs[0], xs[-1]] if len(xs) >= 2 else xs        # trois couleurs (sans-atout, sur l'entame) : la plus chère ou la moins chère


def mode_entame(den, mene, mort=None):
    """Le sens de la première carte du partenaire de celui qui a mené la couleur (SEF 2024 p. 84) : « appel »
    (appel-refus), « préférence » ou « parité ». mene : le rang de la carte menée (français ou anglais) ; mort : la
    tenue du mort dans la couleur au début du pli (None : on ne la connaît pas)."""
    mene = {"K": "R", "Q": "D", "J": "V", "T": "X"}.get(mene, mene)
    if den == "SA": return "appel" if mene in ("A", "D") else "parité"
    if mene in ("A", "R"):
        if mort is not None and len(mort) == 1: return "préférence"
        if mort is None or (len(mort) >= 3 and not any(x in "ARDVAKQJ" for x in mort)): return "appel"
    return "parité"


# ---------------------------------------------------------------- donner un signal (le défenseur qui joue)
def carte_appel(rangs, continuer):
    """Appel-refus parmi des cartes également bonnes : la plus grosse (7 ou plus) pour « continuez », la plus petite
    (6 ou moins) pour « changez ». (rang, « appel » / « refus ») ou None quand aucune carte ne dit ce message."""
    p = sorted((r for r in rangs if petite(r)), key=lambda r: VALEUR[r])
    if continuer:
        h = [r for r in p if VALEUR[r] >= HAUTE]
        return (h[-1], "appel") if h else None
    b = [r for r in p if VALEUR[r] < HAUTE]
    return (b[0], "refus") if b else None


def carte_preference(rangs, prefere, deux):
    """La préférence (le mort a un singleton) : grosse pour la plus chère des deux autres couleurs hors atout, petite
    pour la moins chère. (rang, sens) ou None."""
    p = sorted((r for r in rangs if petite(r)), key=lambda r: VALEUR[r])
    if not deux or len(deux) < 2: return None
    if prefere == deux[0]:
        h = [r for r in p if VALEUR[r] >= HAUTE]
        return (h[-1], f"préférence haute:{prefere}") if h else None
    b = [r for r in p if VALEUR[r] < HAUTE]
    return (b[0], f"préférence basse:{prefere}") if b else None


def carte_parite(rangs, nombre):
    """La parité : grosse avec un nombre pair, petite avec un nombre impair."""
    p = sorted((r for r in rangs if petite(r)), key=lambda r: VALEUR[r])
    if len(p) < 2: return None
    return (p[-1], "parité paire") if nombre % 2 == 0 else (p[0], "parité impaire")


def carte_defausse(par_couleur, voeu_ordre, nombres, urgence=False):
    """La défausse. En urgence, l'appel direct : une grosse carte (7 ou plus) de la couleur voulue (voeu_ordre[0]).
    Sinon la parité dans la couleur la moins voulue : parmi ses petites cartes (6 ou moins, pour ne pas ressembler à
    un appel), la plus grosse avec un nombre pair, la plus petite avec un nombre impair (nombres : {couleur: cartes
    tenues avant la défausse}). ((couleur, rang), sens) ou None."""
    if urgence and voeu_ordre:
        d = voeu_ordre[0]
        h = sorted((r for r in par_couleur.get(d, []) if petite(r) and VALEUR[r] >= HAUTE), key=lambda r: VALEUR[r])
        if h: return (d, h[-1]), f"défausse appel:{d}"
    for d in reversed(voeu_ordre):
        p = sorted((r for r in par_couleur.get(d, []) if petite(r) and VALEUR[r] < HAUTE), key=lambda r: VALEUR[r])
        if not p: continue
        if nombres.get(d, 0) % 2 == 0: return (d, p[-1]), f"défausse parité paire:{d}"
        return (d, p[0]), f"défausse parité impaire:{d}"
    return None


def carte_coupe(rangs, prefere, deux):
    """En menant une couleur que le partenaire coupe : haute (7 et plus) pour la plus chère des deux autres couleurs
    hors atout, basse pour la moins chère. (rang, sens) ou None."""
    p = sorted((r for r in rangs if petite(r)), key=lambda r: VALEUR[r])
    if prefere == deux[0]:
        h = [r for r in p if VALEUR[r] >= HAUTE]
        return (h[-1], f"coupe haute:{prefere}") if h else None
    b = [r for r in p if VALEUR[r] < HAUTE]
    return (b[0], f"coupe basse:{prefere}") if b else None


# ---------------------------------------------------------------- lire un signal (le partenaire, le modèle, les pensées)
def lire(rang, sens, couleur, den, c_menee=None, tenue_vue=""):
    """Ce que dit une carte du partenaire : sens « appel » (appel-refus sur notre couleur), « préférence »,
    « défausse », « coupe », « parité ». {"continuer": bool}, {"prefere": couleur}, {"refuse": couleur} ; {} si elle
    ne dit rien de ce qu'il veut (un honneur, la parité)."""
    if not petite(rang): return {}
    haute = VALEUR[rang] >= HAUTE
    if sens in ("appel", "attitude"):
        return {"continuer": haute}
    if sens == "préférence":
        deux = autres(den, couleur, couleur)
        return {"prefere": deux[0] if haute else deux[1]} if len(deux) == 2 else {}
    if sens == "défausse":
        return {"prefere": couleur} if haute else {"refuse": couleur}
    if sens == "coupe":                                    # la carte menée pour la coupe du partenaire
        deux = autres(den, couleur, couleur)
        return {"prefere": deux[0] if haute else deux[1]} if len(deux) == 2 else {}
    return {}


def phrase(nom, carte, sens, couleur, den, c_menee=None):
    """La phrase d'une pensée : « Est a fourni le ♥8, une grosse carte : il demande de continuer les ♥. »"""
    r = carte[1:] if len(carte) > 1 else ""
    m = lire(r.replace("10", "X"), sens, couleur, den, c_menee)
    c = carte[0]
    if sens in ("appel", "attitude") and m:
        if m["continuer"]: return f"{nom} a fourni le {carte}, une grosse carte : il demande de continuer à {c}."
        return f"{nom} a fourni le {carte}, sa plus petite : il demande de changer de couleur."
    if sens == "préférence" and m:
        return f"{nom} a fourni le {carte} : préférence pour {m['prefere']}."
    if sens == "coupe" and m:
        return f"{nom} mène le {carte} pour ma coupe : il demande le retour à {m['prefere']}."
    if sens == "défausse" and m:
        if m.get("prefere"): return f"{nom} défausse le {carte}, une grosse carte : appel direct à {c}."
        return f"{nom} défausse le {carte} : il ne veut pas de {c} (et donne sa parité)."
    return ""
