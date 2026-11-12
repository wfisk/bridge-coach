# -*- coding: utf-8 -*-
"""« Demander à l'expert » : un petit fichier .ai.json par donne, à glisser dans la conversation de l'outil d'IA réglé
(Réglages, L'expert ; claude.ai par défaut), pour lui poser des questions sur cette donne.

Pendant la donne, le fichier ne contient que ce que voit le joueur (sa main, le mort une fois l'entame faite, les
enchères, les cartes jouées) : l'expert l'aide à raisonner comme à la table, sans lui dire les mains cachées. Après la
donne, tout : les quatre mains, le double mort, les analyses du coach et de l'expert, les résultats des tables.

Les joueurs n'y sont que par leurs initiales. Seule exception, voulue par l'utilisateur (2026-11-12) : le prénom réglé
dans Réglages, L'expert, pour que l'expert s'adresse à lui ; vide, rien.
"""
import json, os

import rapport

SIEGES = ("N", "E", "S", "O")
NOM = {"N": "Nord", "E": "Est", "S": "Sud", "O": "Ouest"}
DOCUMENTS = [("systems/sef-2024/systeme.md", "systeme.md"), ("systems/sef-2024/conventions.md", "conventions.md"),
             ("systems/conventions/blackwood-3041.md", "blackwood-3041.md"), ("systems/conventions/stayman.md", "stayman.md"),
             ("systems/conventions/texas.md", "texas.md"), ("systems/conventions/drury.md", "drury.md"),
             ("systems/sef-2024/entames.md", "entames.md"), ("systems/technique/jeu-de-la-carte.md", "jeu-de-la-carte.md")]
ADRESSE = "https://claude.ai/new"                          # l'outil d'IA par défaut (Réglages, L'expert)

CONSIGNE = """Tu es « l'expert » de Bridge Coach, un professeur de bridge patient et chaleureux. Tu parles avec {qui}, un
joueur ou une joueuse de club : réponds en français, en phrases courtes et simples ; explique chaque terme technique la
première fois.

Le fichier joint décrit une donne de bridge : « donne » (le donneur, la vulnérabilité, la marque, les mains que tu peux
voir), « encheres » (dans l'ordre, à partir du donneur), « jeu » (les cartes jouées, pli par pli), et « documents » : le
système joué (SEF 2024, systeme.md et les conventions), les règles d'entame et de défense (entames.md), la technique du
déclarant (jeu-de-la-carte.md). Le joueur est assis en {place}.
{moment}
Commence par saluer {qui_court} en une phrase, dis en une phrase ce que tu vois (la donne, où en sont les enchères ou le
jeu), puis demande-lui ce qu'il veut savoir. Ensuite, réponds à ses questions sur cette donne.

Règles : le système est celui de systeme.md ; une ligne marquée « (à confirmer) » ne s'emploie qu'en disant que c'est
incertain. Les cartes en français, A R D V X, les couleurs devant (« ♠AR »), les sièges Nord, Est, Sud, Ouest. Les
joueurs ne sont désignés que par leurs initiales : ne demande pas leur nom."""

PENDANT = """
La donne est EN COURS : tu ne connais que ce que le joueur voit. Ne devine pas les mains cachées au-delà de ce que disent
les enchères et les cartes jouées, ne parle pas de double mort, et ne lui donne pas « la » bonne carte d'emblée :
aide-le à raisonner comme à la table (compter les levées et les points, lire les enchères, faire un plan), puis donne
ton avis s'il le demande.
"""

APRES = """
La donne est FINIE : tu vois les quatre mains, le double mort (« dm » : levées de chaque déclarant dans chaque
dénomination), le par, les analyses du coach (le programme) et de l'expert quand il y en a une, et les résultats des
tables du club. Le joueur veut comprendre : ce qu'il fallait annoncer et jouer, ce qui a marché ailleurs, ce qu'il
peut retenir pour la prochaine fois. Juge les enchères comme à la table (d'après chaque main), puis dis après coup ce que
donnait la donne.
"""


def prenom_de(nom_complet):
    """« MARTIN Anne » → « Anne » ; « Anne Martin » → « Anne » : les mots qui ne sont pas en capitales."""
    mots = (nom_complet or "").split()
    autres = [m for m in mots if not m.isupper()]
    return (autres or mots[:1] or [""])[0]


def encheres(seq, donneur):
    """[{"joueur": "N", "enchere": "1♣"}…] à partir du donneur."""
    k = SIEGES.index(donneur)
    return [{"joueur": SIEGES[(k + i) % 4], "enchere": b} for i, b in enumerate(seq) if b]


def mains_vues(d, siege, partie):
    """Les mains que voit le joueur : la sienne ; une fois l'entame faite, celle du mort (le déclarant tient les deux)."""
    vues = {siege}
    if partie is not None:
        vues.add(partie.humain)
        if partie.camp(partie.humain): vues.add(partie.decl)
        if partie.pos.jouees: vues.add(partie.mort())
    return {s: d["mains"][s] for s in SIEGES if s in vues}


def jeu_de(partie):
    """Les plis joués, chacun [{"joueur", "carte"}…] et son gagnant ; le pli en cours à la fin, sans gagnant."""
    if partie is None: return []
    plis = [{"cartes": [{"joueur": s, "carte": c + r} for s, c, r in pli], "gagnant": g} for pli, g in partie.plis]
    if partie.pos.pli: plis.append({"cartes": [{"joueur": s, "carte": c + r} for s, c, r in partie.pos.pli], "gagnant": None})
    return plis


def fichier(data, d, siege, seq, partie=None, apres=False, analyses=(None, None), prenom=""):
    """Le contenu du fichier .ai.json d'une question à l'expert sur la donne d."""
    import moi
    qui = prenom.strip() or "un joueur du club"
    texte = CONSIGNE.format(qui=qui, qui_court=prenom.strip() or "ton interlocuteur", place=NOM.get(siege, siege),
                            moment=APRES if apres else PENDANT)
    donne = {"numero": d["n"], "donneur": d["donneur"], "vulnerabilite": d.get("vul"),
             "marque": moi.MARQUES[moi.marque(data)], "place_du_joueur": siege,
             "mains": dict(d["mains"]) if apres else mains_vues(d, siege, partie),
             "notation_des_mains": "♠ ♥ ♦ ♣ dans cet ordre, « - » pour une chicane"}
    out = {"consigne": texte, "interlocuteur": prenom.strip() or None, "moment": "apres" if apres else "pendant",
           "donne": donne, "encheres": encheres(seq or [], d["donneur"]), "jeu": jeu_de(partie)}
    if partie is not None:
        faites, perdues = partie.levees()
        out["contrat"] = {"contrat": partie.contrat, "declarant": partie.decl,
                          "levees": {"camp_du_declarant": faites, "defense": perdues}}
    if apres:
        donne.update(points=d.get("hcp"), dm=d.get("dm"), par=d.get("par"))
        std, exp = analyses
        for cle, an in (("analyse_du_coach", std), ("analyse_de_l_expert", exp)):
            x = ((an or {}).get("donnes") or {}).get(str(d["n"]))
            if x: out[cle] = {k: v for k, v in x.items() if k in ("enc", "notes", "entame", "plan", "defense", "comm")}
        out["resultats_des_tables"] = [{k: t.get(k) for k in ("table", "nom_ns", "nom_eo", "contrat", "declarant", "entame",
                                                              "resultat", "score_ns", "pct_ns", "imp_ns")}
                                       for t in d.get("tables") or []]
    docs = {}
    for src, nom in DOCUMENTS:
        f = os.path.join(rapport.RACINE, src)
        if os.path.exists(f): docs[nom] = open(f, encoding="utf-8").read()
    out["documents"] = docs
    return out


def message(nom_fichier):
    """Le court message à coller avec le fichier : l'expert lit la consigne du fichier."""
    return f"Bonjour ! Lis le fichier joint, {nom_fichier}, et suis la consigne qu'il contient."


def ecrire(c, contenu, n, apres):
    """Écrit <dossier de travail>/pour-claude/<séance>/donne-<n>[-apres].ai.json ; renvoie son chemin."""
    import fichiers
    dossier = fichiers.dossier_claude(c)
    os.makedirs(dossier, exist_ok=True)
    f = os.path.join(dossier, f"donne-{n}{'-apres' if apres else ''}.ai.json")
    with open(f, "w", encoding="utf-8") as x: json.dump(contenu, x, ensure_ascii=False, indent=1)
    return f


def adresse_avec_message(adresse, texte):
    """claude.ai et ChatGPT acceptent le message dans l'adresse (?q=…) : il est déjà tapé en arrivant. Ailleurs, l'adresse
    telle quelle (le message est aussi copié, à coller)."""
    from urllib.parse import quote, urlparse
    hote = urlparse(adresse).netloc
    if hote.endswith("claude.ai") or hote.endswith("chatgpt.com"):
        return adresse + ("&" if "?" in adresse else "?") + "q=" + quote(texte)
    return adresse
