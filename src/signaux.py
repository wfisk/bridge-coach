# -*- coding: utf-8 -*-
"""La signalisation de la défense, en un seul endroit (systems/sef-2024/entames.md, les choix de l'utilisateur,
2026-11-11). Le défenseur qui signale (carte.Partie) et celui qui lit (carte.Partie, modele.Modele, les pensées)
passent par ces fonctions : un robot lit son partenaire comme il aurait signalé lui-même.

  - Sur l'entame (ou la couleur menée) du partenaire, la première carte : pair-impair. Impaire : continuez cette
    couleur. Paire : changez, et sa hauteur dit laquelle : paire haute la plus chère des deux autres couleurs, paire
    basse la moins chère.
  - En défausse : préférence de couleur. On défausse dans une couleur qu'on ne veut pas ; une carte haute demande la
    plus chère des deux autres couleurs, une basse la moins chère.
  - Quand le déclarant mène : la parité, grosse puis petite avec un nombre pair de cartes.
  - En donnant une coupe au partenaire : la hauteur de la carte demande le retour (haute : la plus chère des deux
    autres couleurs hors atout ; basse : la moins chère).

Ce que le défenseur veut (continuer, ou quelle couleur) ne vient pas d'une règle fixe sur ses honneurs : il le lit
dans ses donnes imaginées (carte.Partie.voeu), selon la situation. Les cartes sont en rangs anglais (« T » = 10) ou
français (« X ») : on ne regarde que les petites cartes, de 2 à 10.
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


# ---------------------------------------------------------------- donner un signal (le défenseur qui joue)
def carte_attitude(rangs, continuer, prefere=None, haute_vers=None):
    """La carte à fournir sur l'entame du partenaire parmi les rangs possibles (cartes également bonnes, de la même
    couleur) : impaire pour continuer ; paire pour changer, haute si prefere est la plus chère de haute_vers (les deux
    autres couleurs), basse sinon. (rang, sens) ou None quand aucune carte ne dit ce message."""
    p = [r for r in rangs if petite(r)]
    if continuer:
        imp = [r for r in p if impaire(r)]
        return (min(imp, key=lambda r: VALEUR[r]), "impair") if imp else None
    pairs = sorted((r for r in p if not impaire(r)), key=lambda r: VALEUR[r])
    if not pairs: return None
    if prefere and haute_vers and len(haute_vers) == 2:
        if prefere == haute_vers[0]:
            h = [r for r in pairs if VALEUR[r] >= HAUTE]
            if h: return h[-1], f"pair haut:{prefere}"
        else:
            b = [r for r in pairs if VALEUR[r] < HAUTE]
            if b: return b[0], f"pair bas:{prefere}"
    return pairs[0], "pair"


def carte_defausse(par_couleur, voeu_ordre, den, c_menee):
    """La défausse : dans la couleur la moins voulue (voeu_ordre : les couleurs de la plus voulue à la moins voulue)
    parmi celles où l'on a des petites cartes également bonnes (par_couleur : {couleur: [rangs]}), haute si l'on préfère
    la plus chère des deux autres couleurs, basse sinon. ((couleur, rang), sens) ou None."""
    for d in reversed(voeu_ordre):
        p = sorted((r for r in par_couleur.get(d, []) if petite(r)), key=lambda r: VALEUR[r])
        if not p: continue
        deux = autres(den, d, c_menee)
        if len(deux) < 2: return (d, p[0]), f"défausse:{d}"
        pref = next((c for c in voeu_ordre if c in deux), deux[0])
        haut, bas = [r for r in p if VALEUR[r] >= HAUTE], [r for r in p if VALEUR[r] < HAUTE]
        if pref == deux[0] and haut: return (d, haut[-1]), f"défausse haute:{d}:{pref}"
        if pref == deux[1] and bas: return (d, bas[0]), f"défausse basse:{d}:{pref}"
        continue                                           # cette couleur ne sait pas dire la préférence : une autre
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


def carte_parite(rangs, nombre):
    """La parité quand le déclarant mène : grosse avec un nombre pair, petite avec un nombre impair."""
    p = sorted((r for r in rangs if petite(r)), key=lambda r: VALEUR[r])
    if len(p) < 2: return None
    return (p[-1], "parité paire") if nombre % 2 == 0 else (p[0], "parité impaire")


# ---------------------------------------------------------------- lire un signal (le partenaire, le modèle, les pensées)
def lire(rang, sens, couleur, den, c_menee=None, tenue_vue=""):
    """Ce que dit une carte du partenaire, d'après sa situation : sens « attitude » (sur notre entame), « défausse »,
    « parité ». {"continuer": bool} ou {"prefere": couleur, "refuse": couleur} ou {"pair": bool} ; {} si elle ne dit
    rien (un honneur, ou une carte forcée). tenue_vue : les petites cartes de cette couleur encore inconnues de
    l'observateur ne servent pas ici (la hauteur est relative aux deux couleurs, pas à la tenue)."""
    if not petite(rang): return {}
    if sens == "attitude":
        if impaire(rang): return {"continuer": True}
        deux = autres(den, couleur, couleur)
        out = {"continuer": False}
        if len(deux) == 2: out["prefere"] = deux[0] if VALEUR[rang] >= HAUTE else deux[1]
        return out
    if sens == "défausse":
        deux = autres(den, couleur, c_menee)
        out = {"refuse": couleur}
        if len(deux) == 2: out["prefere"] = deux[0] if VALEUR[rang] >= HAUTE else deux[1]
        return out
    if sens == "coupe":                                    # la carte menée pour la coupe du partenaire
        deux = autres(den, couleur, couleur)
        return {"prefere": deux[0] if VALEUR[rang] >= HAUTE else deux[1]} if len(deux) == 2 else {}
    return {}


def phrase(nom, carte, sens, couleur, den, c_menee=None):
    """La phrase d'une pensée : « Est a fourni le ♥7, impair : il demande de continuer les ♥. »"""
    r = carte[1:] if len(carte) > 1 else ""
    m = lire(r.replace("10", "X"), sens, couleur, den, c_menee)
    c = carte[0]
    if sens == "attitude" and m:
        if m["continuer"]: return f"{nom} a fourni le {carte}, impair : il demande de continuer à {c}."
        return (f"{nom} a fourni le {carte}, pair : il demande de changer" +
                (f", pour {m['prefere']} ({'haut' if m['prefere'] == autres(den, c, c)[0] else 'bas'})." if m.get("prefere") else "."))
    if sens == "coupe" and m:
        return f"{nom} mène le {carte} pour ma coupe : il demande le retour à {m['prefere']}."
    if sens == "défausse" and m:
        t = f"{nom} défausse le {carte} : il ne veut pas de {c}"
        return t + (f", et préfère {m['prefere']}." if m.get("prefere") else ".")
    return ""
