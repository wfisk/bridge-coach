# -*- coding: utf-8 -*-
"""Le Brouillon (l'utilisateur, 2026-11-16) : une séance permanente, toujours là, une seule, qu'on ne met pas à la
corbeille. On y ajoute des donnes de n'importe quelle séance (« Ajouter au Brouillon ») ; elle se joue, s'analyse et
s'imprime comme les autres. Pour garder le cours qu'on y a préparé : « Enregistrer sous… », une séance normale datée du
jour, puis le Brouillon peut être vidé.

Une donne ajoutée emporte ses mains, son donneur et sa vulnérabilité, son thème, son double mort et son par, les
analyses du coach et de l'expert, et d'où elle vient ("origine") ; pas les résultats des tables, qui n'ont de sens que
dans leur tournoi. Elle est dans <dossier de travail>/seances/brouillon/brouillon.bc.json."""
import copy, datetime, os

import rapport

NOM = "brouillon"
TITRE = "Brouillon"


def chemin():
    return os.path.join(rapport.SEANCES, NOM, NOM + rapport.BC)


def est_brouillon(c):
    return bool(c) and os.path.abspath(c) == os.path.abspath(chemin())


def assurer():
    """Le Brouillon, créé vide s'il n'existe pas encore ; renvoie son chemin."""
    c = chemin()
    if os.path.exists(c): return c
    import fichiers
    rapport.preparer_donnees()
    os.makedirs(os.path.dirname(c), exist_ok=True)
    now = datetime.datetime.now()
    data = dict(session=dict(date=now.strftime("%d/%m/%Y"), tables=0, sections=["A"], mitchell=False, titre=TITRE),
                donnes=[], paires={}, alertes=[])
    rapport.entete(data, "brouillon", NOM)
    fichiers.nouvel_entete(data, "brouillon", None, TITRE, "Créé")
    rapport.ecrire_bc(data, c)
    return c


def lire():
    return rapport.lire_bc(assurer())


def nombre():
    try: return len(lire()["donnes"])
    except (OSError, ValueError, KeyError): return 0


def _origine(c, n):
    """D'où vient une donne : le fichier de sa séance (sans extension), son numéro, le titre et la date de la séance."""
    import fichiers
    data = rapport.lire_bc(c); s = data.get("session") or {}
    return {"fichier": fichiers.base(c), "n": n, "titre": s.get("titre") or fichiers.base(c), "date": s.get("date", "")}


def numero_de(c, n):
    """Le numéro dans le Brouillon de la donne n de la séance c, ou None."""
    if est_brouillon(c): return n
    import fichiers
    b = fichiers.base(c)
    return next((d["n"] for d in lire()["donnes"] if (d.get("origine") or {}).get("fichier") == b
                 and (d.get("origine") or {}).get("n") == n), None)


def ajouter(c, n):
    """Ajoute la donne n de la séance c à la fin du Brouillon, avec ses analyses ; renvoie son numéro dans le Brouillon
    (celui qu'elle a déjà si elle y est)."""
    import edition
    deja = numero_de(c, n)
    if deja: return deja
    b = assurer()
    src = rapport.lire_bc(c)
    d = copy.deepcopy(next(x for x in src["donnes"] if x["n"] == n))
    data = rapport.lire_bc(b)
    nouveau = max((x["n"] for x in data["donnes"]), default=0) + 1
    for k in ("tables", "jouee", "resultats"): d.pop(k, None)
    d.update(n=nouveau, tables=[], origine=_origine(c, n))
    data["donnes"].append(d)
    for quoi in rapport.ANALYSES:                           # les analyses suivent la donne, dans le même enregistrement
        an = (src.get("analyses") or {}).get(quoi)
        e = (an or {}).get("donnes", {}).get(str(n))
        if not e: continue
        ans = data.setdefault("analyses", {})
        cible = ans.get(quoi) or {k: v for k, v in an.items() if k != "donnes"}
        ans[quoi] = dict(cible, donnes=dict(cible.get("donnes") or {}, **{str(nouveau): copy.deepcopy(e)}))
    edition.enregistrer(b, data)                           # une copie gardée au plus toutes les 10 minutes
    if edition.par_numero(b): edition.appliquer_numero(b)
    return nouveau


def retirer(c, n):
    """Retire du Brouillon la donne n de la séance c (ou la donne n du Brouillon lui-même)."""
    import edition
    k = numero_de(c, n)
    if k: edition.supprimer_donne(assurer(), k)


def vider():
    """Le Brouillon vide (sa version d'avant est gardée dans versions/, comme à chaque changement), ses parties de Jouer
    et ses analyses avec."""
    import edition
    b = assurer(); data = rapport.lire_bc(b)
    if not data["donnes"]: return
    data["donnes"] = []; data.pop("analyses", None)
    edition.garder_version(b, force=True)
    rapport.ecrire_bc(data, b)
    jeu = b[:-len(rapport.BC)] + "-jeu.json"
    if os.path.exists(jeu): os.remove(jeu)


def enregistrer_sous(nom, titre):
    """Le Brouillon devient une séance normale (donnes saisies, modifiable), datée du jour, dans seances/AAAA-MM/ ;
    renvoie son chemin. ValueError si le nom est vide ou pris. Le Brouillon, lui, ne change pas."""
    import fichiers
    nom = fichiers.nettoyer_nom(nom)
    if not nom: raise ValueError("Le nom ne peut pas être vide.")
    now = datetime.datetime.now()
    dossier = os.path.join(rapport.SEANCES, now.strftime("%Y-%m"))
    cible = os.path.join(dossier, nom + rapport.BC)
    if os.path.exists(cible): raise ValueError(f"Une séance s'appelle déjà {nom} : choisissez un autre nom.")
    data = lire()
    if not data["donnes"]: raise ValueError("Le Brouillon est vide : ajoutez-y d'abord des donnes.")
    data["session"] = dict(data.get("session") or {}, titre=(titre or "").strip() or nom, date=now.strftime("%d/%m/%Y"))
    data["source"] = dict(data.get("source") or {}, type="saisie", fichier=nom)
    data["fichier"] = {"cree_le": fichiers.maintenant(), "cree_avec": fichiers.version_programme(), "journal": []}
    fichiers.journal(data, f"Enregistrée depuis le Brouillon ({len(data['donnes'])} donnes)")
    os.makedirs(dossier, exist_ok=True)
    rapport.ecrire_bc(data, cible)
    return cible


def proposer():
    """(nom, titre) proposés pour « Enregistrer sous… » : « Cours du lundi 16 novembre 2026 », 2026-11-16-cours."""
    import fichiers
    now = datetime.datetime.now()
    jours = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
    titre = f"Cours du {jours[now.weekday()]} {now.day} {fichiers.MOIS[now.month - 1]} {now.year}"
    dossier = os.path.join(rapport.SEANCES, now.strftime("%Y-%m"))
    return fichiers.nom_libre(dossier, now.strftime("%Y-%m-%d") + "-cours"), titre
