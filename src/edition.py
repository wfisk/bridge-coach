# -*- coding: utf-8 -*-
"""Une séance créée dans Bridge Coach se modifie donne par donne : chaque changement est enregistré tout de suite
dans son .bc.json, et la version précédente est gardée dans versions/ (une copie au plus toutes les 10 minutes,
les 20 dernières), pour revenir en arrière.

Une donne en cours de saisie est enregistrée telle quelle, marquée "a_completer" ; quand ses 52 cartes sont posées,
le double mort, les points et le par sont calculés (donnes.donne_complete). Seules les séances faites dans
Bridge Coach (entraînement, donnes saisies) se modifient. Une donne changée perd son analyse standard, et son
analyse de l'expert est retirée, après une copie du fichier dans versions/ : les autres donnes gardent les leurs.
"""
import datetime, glob, json, os, random, re, shutil

import rapport
from donnes import SAISIE, SIEGES, VUL16, donne_complete, nom_entrainement
from jeu import ORDRE

COULEURS = "♠♥♦♣"
MODIFIABLES = ("entrainement", "saisie", "brouillon")
ECART_VERSIONS = 600                                       # secondes entre deux copies gardées
NB_VERSIONS = 20
POINTS = {"A": 4, "R": 3, "D": 2, "V": 1}


def lire(c):
    return json.load(open(c, encoding="utf-8"))


def nouvelle_seance(maintenant=None):
    """Une séance vide, « Entraînement du mardi 3 novembre 2026 » (2026-11-03-entrainement.bc.json, -2 si ce nom est pris),
    à remplir donne par donne ; renvoie le chemin de son .bc.json."""
    now = maintenant or datetime.datetime.now()
    rapport.preparer_donnees()
    dossier = os.path.join(rapport.SEANCES, now.strftime("%Y-%m"))
    os.makedirs(dossier, exist_ok=True)
    titre, nom = nom_entrainement(dossier, now)
    data = dict(session=dict(date=now.strftime("%d/%m/%Y"), tables=0, sections=["A"], mitchell=False,
                             titre=titre), donnes=[], paires={}, alertes=[])
    rapport.entete(data, "saisie", nom)
    import fichiers
    fichiers.nouvel_entete(data, "saisie", None, titre, "Créée vide")
    chemin = os.path.join(dossier, nom + rapport.BC)
    rapport.ecrire_bc(data, chemin)
    return chemin


def modifiable(c):
    """(True, "") si la séance se modifie ; sinon (False, la raison en français)."""
    try:
        data = lire(c)
    except (OSError, ValueError):
        return False, "Cette séance n'est pas lisible."
    if data.get("source", {}).get("type") not in MODIFIABLES and not est_copie(data):
        return False, ("Séance importée : ses donnes sont celles qui ont été jouées. Dupliquez-la d'abord (Fichier, Infos, "
                       "Dupliquer…) pour modifier, réorganiser ou renuméroter la copie.")
    return True, ""


def est_copie(data):
    """Une copie faite dans Bridge Coach (Fichier, Infos, Dupliquer…) : elle se modifie, même copiée d'un tournoi."""
    f = data.get("fichier") or {}
    return bool(f.get("copie_de")) or any(str(x.get("quoi", "")).startswith("Copie de") for x in f.get("journal") or [])


def a_analyse_expert(c, n):
    """La donne n a-t-elle une analyse de l'expert ?"""
    return str(n) in (rapport.analyse_de(c, "expert") or {}).get("donnes", {})


# ---------------------------------------------------------------- enregistrer, et garder les versions
def dossier_versions(c):
    return os.path.join(os.path.dirname(c), "versions")


def versions(c):
    """Les versions gardées de la séance, de la plus récente à la plus ancienne."""
    nom = os.path.basename(c)[:-len(rapport.BC)]
    return sorted(glob.glob(os.path.join(glob.escape(dossier_versions(c)), nom + "-v-*" + rapport.BC)),
                  key=lambda f: (os.path.getmtime(f), f), reverse=True)


def garder_version(c, force=False):
    """Copie le fichier actuel dans versions/ avant qu'il change (au plus une copie toutes les 10 minutes)."""
    if not os.path.exists(c): return
    vs = versions(c)
    if vs and not force and (datetime.datetime.now().timestamp() - os.path.getmtime(vs[0])) < ECART_VERSIONS: return
    os.makedirs(dossier_versions(c), exist_ok=True)
    nom = os.path.basename(c)[:-len(rapport.BC)]
    base = os.path.join(dossier_versions(c), f"{nom}-v-{datetime.datetime.now().strftime('%Y-%m-%d-%H%M%S')}")
    cible, k = base + rapport.BC, 2
    while os.path.exists(cible): cible, k = f"{base}-{k}{rapport.BC}", k + 1   # deux copies dans la même seconde
    shutil.copy2(c, cible); os.utime(cible)                # la date de la copie : quand elle a été gardée
    for vieux in versions(c)[NB_VERSIONS:]: os.remove(vieux)


def enregistrer(c, data):
    garder_version(c)
    rapport.ecrire_bc(data, c)


def restaurer(c, version):
    """Remet une version gardée ; la version actuelle est gardée d'abord, pour pouvoir revenir."""
    garder_version(c, force=True)
    shutil.copy(version, c)


# ---------------------------------------------------------------- les donnes
def donne_de(data, n):
    return next(d for d in data["donnes"] if d["n"] == n)


def points(main):
    return sum(POINTS.get(x, 0) for x in main.replace("-", ""))


def cartes(main):
    """{(couleur, rang)} d'une main « AR6 - ADV6532 953 »."""
    return {(c, r) for c, p in zip(COULEURS, main.split()) for r in p if p != "-"}


def lire_couleur(texte):
    """Les rangs tapés pour une couleur, rangés et vérifiés : « r a 10 6 » -> « AR X6 » sans espace -> « ARX6 » ;
    vide ou « - » : chicane (« - »). Accepte aussi les lettres anglaises K Q J T. ValueError en français."""
    x = re.sub(r"[\s,.\-–]", "", (texte or "").upper()).replace("10", "X").translate(str.maketrans("KQJT", "RDVX"))
    if not x: return "-"
    faux = [r for r in x if r not in ORDRE]
    if faux: raise ValueError(f"« {faux[0]} » n'est pas une carte (A R D V X 9 … 2)")
    double = next((r for r in x if x.count(r) > 1), None)
    if double: raise ValueError(f"« {double} » est tapé deux fois")
    return "".join(sorted(x, key=ORDRE.index))


def etat(d):
    """(cartes posées, cartes en double [(couleur, rang)], cartes restantes {couleur: rangs}) d'une donne."""
    vues, doubles = set(), []
    for s in SIEGES:
        for x in cartes(d["mains"][s]):
            if x in vues: doubles.append(x)
            else: vues.add(x)
    restantes = {c: "".join(r for r in ORDRE if (c, r) not in vues) for c in COULEURS}
    return len(vues), doubles, restantes


def finir(d):
    """Après un changement : les points, et le double mort et le par si la donne est complète, sinon « à compléter »."""
    d["hcp"] = {s: points(d["mains"][s]) for s in SIEGES}
    n_cartes, doubles, _ = etat(d)
    complete = n_cartes == 52 and not doubles and all(len(cartes(d["mains"][s])) == 13 for s in SIEGES)
    for k in ("dm", "par"): d.pop(k, None)
    d.pop("a_completer", None)
    if complete:
        d.update({k: v for k, v in donne_complete(d["n"], d.get("theme") or SAISIE, d["mains"], True, d["donneur"], d["vul"]).items()
                  if k in ("dm", "hcp", "par")})
    else:
        d["a_completer"] = True
    return d


def oublier_analyse(c, nums, renumeroter=None):
    """Les analyses des donnes changées ne sont plus justes (renumeroter : {ancien: nouveau}) : retirées de la standard
    et de celle de l'expert ; pour l'expert, qui ne se refait pas toute seule, le fichier d'avant est d'abord copié
    dans versions/ (rapport.ecrire_analyse)."""
    for quoi in rapport.ANALYSES:
        an = rapport.analyse_de(c, quoi)
        if not an: continue
        avant = an.get("donnes", {})
        d = {k: v for k, v in avant.items() if int(k) not in nums}
        if renumeroter: d = {str(renumeroter[int(k)]): v for k, v in d.items() if int(k) in renumeroter}
        if d == avant: continue                            # rien ne change pour cette analyse
        rapport.ecrire_analyse(c, quoi, dict(an, donnes=d), dater=False)


def ajouter_donne(c):
    """Une donne vide à la fin ; donneur et vulnérabilité suivent son numéro, comme au club. Renvoie son numéro."""
    data = lire(c)
    n = max((d["n"] for d in data["donnes"]), default=0) + 1
    d = dict(n=n, donneur=SIEGES[(n - 1) % 4], vul=VUL16[(n - 1) % 16], mains={s: "- - - -" for s in SIEGES},
             tables=[], theme=SAISIE)
    data["donnes"].append(finir(d))
    enregistrer(c, data)
    return n


def poser_couleur(c, n, siege, k, texte):
    """Une couleur d'une main : enregistrée telle que tapée (rangée). Renvoie le texte rangé ; ValueError s'il est faux."""
    rangs = lire_couleur(texte)
    data = lire(c); d = donne_de(data, n)
    parts = d["mains"][siege].split()
    if parts[k] == rangs: return rangs
    parts[k] = rangs
    d["mains"][siege] = " ".join(parts)
    finir(d); enregistrer(c, data); oublier_analyse(c, {n})
    return rangs


def regler(c, n, donneur=None, vul=None):
    data = lire(c); d = donne_de(data, n)
    if donneur: d["donneur"] = donneur
    if vul: d["vul"] = vul
    finir(d); enregistrer(c, data); oublier_analyse(c, {n})


def completer_au_hasard(c, n, rnd=random):
    """Les cartes qui manquent sont données au hasard aux mains qui n'en ont pas 13. ValueError s'il y a des doublons ou
    une main de plus de 13 cartes."""
    data = lire(c); d = donne_de(data, n)
    _, doubles, restantes = etat(d)
    if doubles: raise ValueError("des cartes sont en double : corrigez-les d'abord")
    trop = [s for s in SIEGES if len(cartes(d["mains"][s])) > 13]
    if trop: raise ValueError(f"la main de {', '.join(trop)} a plus de 13 cartes")
    paquet = [(c_, r) for c_ in COULEURS for r in restantes[c_]]
    rnd.shuffle(paquet)
    for s in SIEGES:
        main = cartes(d["mains"][s])
        while len(main) < 13: main.add(paquet.pop())
        d["mains"][s] = " ".join("".join(sorted((r for c_, r in main if c_ == col), key=ORDRE.index)) or "-" for col in COULEURS)
    finir(d); enregistrer(c, data); oublier_analyse(c, {n})


def supprimer_donne(c, n):
    """Retire la donne ; les suivantes prennent le numéro d'avant, avec leurs analyses et leurs parties de Jouer (leur
    donneur et leur vulnérabilité ne changent pas, sauf si la séance les veut selon le numéro)."""
    data = lire(c)
    data["donnes"] = [d for d in data["donnes"] if d["n"] != n]
    ancien = {}
    for k, d in enumerate(sorted(data["donnes"], key=lambda d: d["n"]), 1):
        ancien[d["n"]] = k; d["n"] = k
    enregistrer(c, data); oublier_analyse(c, {n}, ancien); renumeroter_jeu(c, ancien, {n})
    if par_numero(c): appliquer_numero(c)


# ---------------------------------------------------------------- l'ordre des donnes, et donneur / vulnérabilité selon le numéro
def renumeroter_jeu(c, ancien, retirees=()):
    """Les parties de l'onglet Jouer (<nom>-jeu.json) suivent les donnes : {ancien numéro: nouveau}."""
    f = c[:-len(rapport.BC)] + "-jeu.json"
    try:
        x = json.load(open(f, encoding="utf-8"))
    except (OSError, ValueError):
        return
    for cle in ("donnes", "en_cours"):
        v = x.get(cle)
        if isinstance(v, dict):
            x[cle] = {str(ancien[int(k)]): e for k, e in v.items() if k.isdigit() and int(k) in ancien and int(k) not in retirees}
    json.dump(x, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def renumeroter_analyses(c, ancien):
    """Les analyses (standard, expert) suivent les donnes : {ancien numéro: nouveau}."""
    for quoi in rapport.ANALYSES:
        an = rapport.analyse_de(c, quoi)
        if not an or not an.get("donnes"): continue
        d = {str(ancien[int(k)]): v for k, v in an["donnes"].items() if k.isdigit() and int(k) in ancien}
        if d != an["donnes"]: rapport.ecrire_analyse(c, quoi, dict(an, donnes=d), dater=False)


def deplacer(c, n, vers):
    """Met la donne n à la place vers (1 à N) ; les autres se décalent. Ses analyses et ses parties de Jouer la suivent.
    Renvoie les numéros dont le donneur ou la vulnérabilité a changé (séance selon le numéro), sinon []."""
    data = lire(c)
    ordre = [d["n"] for d in sorted(data["donnes"], key=lambda d: d["n"])]
    if n not in ordre: return []
    vers = max(1, min(len(ordre), vers))
    ordre.remove(n); ordre.insert(vers - 1, n)
    ancien = {a: k for k, a in enumerate(ordre, 1)}
    if all(a == k for a, k in ancien.items()): return []
    for d in data["donnes"]: d["n"] = ancien[d["n"]]
    data["donnes"].sort(key=lambda d: d["n"])
    enregistrer(c, data); renumeroter_analyses(c, ancien); renumeroter_jeu(c, ancien)
    return appliquer_numero(c) if par_numero(c) else []


def par_numero(c):
    """La séance veut-elle le donneur et la vulnérabilité de chaque donne selon son numéro (comme au club) ?"""
    try: return bool(lire(c).get("session", {}).get("donneur_par_numero"))
    except (OSError, ValueError): return False


def selon_numero(n):
    return SIEGES[(n - 1) % 4], VUL16[(n - 1) % 16]


def changeraient(c):
    """Les numéros des donnes dont le donneur ou la vulnérabilité changeraient selon le numéro."""
    return [d["n"] for d in lire(c)["donnes"] if (d["donneur"], d["vul"]) != selon_numero(d["n"])]


def appliquer_numero(c):
    """Donneur et vulnérabilité selon le numéro, pour chaque donne qui en change. Leur analyse n'est plus sûre :
    celle du coach est retirée (Analyse, « Lancer l'analyse » la refait) ; celle de l'expert, qui ne se refait pas
    toute seule, est gardée mais marquée « a_revoir ». Renvoie les numéros changés."""
    data = lire(c); changees = []
    for d in data["donnes"]:
        if (d["donneur"], d["vul"]) != selon_numero(d["n"]):
            d["donneur"], d["vul"] = selon_numero(d["n"]); finir(d); changees.append(d["n"])
    if not changees: return []
    enregistrer(c, data)
    std = rapport.analyse_de(c, "standard")
    if std and std.get("donnes"):
        rapport.ecrire_analyse(c, "standard", dict(std, donnes={k: v for k, v in std["donnes"].items() if int(k) not in changees}), dater=False)
    exp = rapport.analyse_de(c, "expert")
    if exp and any(str(n) in exp.get("donnes", {}) for n in changees):
        rapport.ecrire_analyse(c, "expert", dict(exp, donnes={k: (dict(v, a_revoir=True) if int(k) in changees else v)
                                                               for k, v in exp["donnes"].items()}), dater=False)
    return changees


def regler_par_numero(c, oui):
    """L'option de la séance (Fichier, Infos) ; oui : appliquée tout de suite. Renvoie les numéros changés."""
    data = lire(c)
    if bool(data.get("session", {}).get("donneur_par_numero")) == bool(oui): return []
    data.setdefault("session", {})["donneur_par_numero"] = bool(oui)
    enregistrer(c, data)
    return appliquer_numero(c) if oui else []
