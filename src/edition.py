# -*- coding: utf-8 -*-
"""Une séance créée dans Bridge Coach se modifie donne par donne : chaque changement est enregistré tout de suite
dans son .bc.json, et la version précédente est gardée dans versions/ (une copie au plus toutes les 10 minutes,
les 20 dernières), pour revenir en arrière.

Une donne en cours de saisie est enregistrée telle quelle, marquée "a_completer" ; quand ses 52 cartes sont posées,
le double mort, les points et le par sont calculés (donnes.donne_complete). Seules les séances faites dans
Bridge Coach (entraînement, donnes saisies) se modifient. Une donne changée perd son analyse standard, et son
analyse de l'expert est mise de côté (copie datée) : les autres donnes gardent les leurs.
"""
import datetime, glob, json, os, random, re, shutil

import rapport
from donnes import SAISIE, SIEGES, VUL16, donne_complete, nom_entrainement
from jeu import ORDRE

COULEURS = "♠♥♦♣"
MODIFIABLES = ("entrainement", "saisie")
ECART_VERSIONS = 600                                       # secondes entre deux copies gardées
NB_VERSIONS = 20
POINTS = {"A": 4, "R": 3, "D": 2, "V": 1}


def lire(c):
    return json.load(open(c, encoding="utf-8"))


def nouvelle_seance(maintenant=None):
    """Une séance vide, « Entraînement 2026-11-03 » (entrainement-2026-11-03.bc.json, l'heure en plus si ce nom est pris),
    à remplir donne par donne ; renvoie le chemin de son .bc.json."""
    now = maintenant or datetime.datetime.now()
    rapport.preparer_donnees()
    dossier = os.path.join(rapport.SEANCES, now.strftime("%Y-%m"))
    os.makedirs(dossier, exist_ok=True)
    nom = nom_entrainement(dossier, now)
    data = dict(session=dict(date=now.strftime("%d/%m/%Y"), tables=0, sections=["A"], mitchell=False,
                             titre=f"Entraînement {now.strftime('%Y-%m-%d')}"), donnes=[], paires={}, alertes=[])
    rapport.entete(data, "saisie", nom)
    chemin = os.path.join(dossier, nom + rapport.BC)
    rapport.ecrire_bc(data, chemin)
    return chemin


def modifiable(c):
    """(True, "") si la séance se modifie ; sinon (False, la raison en français)."""
    try:
        data = lire(c)
    except (OSError, ValueError):
        return False, "Cette séance n'est pas lisible."
    if data.get("source", {}).get("type") not in MODIFIABLES:
        return False, "Les donnes d'un tournoi sont celles qui ont été jouées : elles ne se modifient pas."
    return True, ""


def a_analyse_expert(c, n):
    """La donne n a-t-elle une analyse de l'expert ?"""
    f = c[:-len(rapport.BC)] + "-expert.json"
    try:
        return str(n) in json.load(open(f, encoding="utf-8")).get("donnes", {})
    except (OSError, ValueError):
        return False


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
    """Les analyses des donnes changées ne sont plus justes (renumeroter : {ancien: nouveau}) : la standard est retirée ;
    celle de l'expert aussi, après une copie datée du fichier (-expert-avant-<date-heure>.json), puisqu'elle ne se
    refait pas toute seule."""
    base = c[:-len(rapport.BC)]
    for suite, garder in (("-standard.json", False), ("-expert.json", True)):
        f = base + suite
        if not os.path.exists(f): continue
        an = json.load(open(f, encoding="utf-8"))
        avant = an.get("donnes", {})
        d = {k: v for k, v in avant.items() if int(k) not in nums}
        if renumeroter: d = {str(renumeroter[int(k)]): v for k, v in d.items() if int(k) in renumeroter}
        if d == avant: continue                            # rien ne change pour ce fichier
        if garder:
            shutil.copy(f, base + f"-expert-avant-{datetime.datetime.now().strftime('%Y-%m-%d-%H%M%S')}.json")
        an["donnes"] = d
        json.dump(an, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


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
    """Retire la donne ; les suivantes prennent le numéro d'avant (leur donneur et leur vulnérabilité ne changent pas)."""
    data = lire(c)
    data["donnes"] = [d for d in data["donnes"] if d["n"] != n]
    ancien = {}
    for k, d in enumerate(sorted(data["donnes"], key=lambda d: d["n"]), 1):
        ancien[d["n"]] = k; d["n"] = k
    enregistrer(c, data); oublier_analyse(c, {n}, ancien)
