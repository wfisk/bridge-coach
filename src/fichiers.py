# -*- coding: utf-8 -*-
"""Le fichier d'une séance Bridge Coach (.bc.json) : son nom, son titre, ce qu'on sait de lui, et ce qu'on en fait.

Le nom proposé commence par la date de la séance, puis quelques mots : 2026-11-05-tournoi-jeudi-apres-midi.bc.json.
Le titre est gardé dans le fichier (session.titre) : « Tournoi du jeudi 5 novembre 2026, après-midi ». Le fichier garde
aussi d'où il vient (source : le type, le nom et le chemin du fichier importé, sa date) et sa propre histoire
("fichier" : créé le, modifié le, avec quelle version, un court journal). Une fois importé, le fichier d'origine ne sert
plus : on ne le copie pas et on n'y revient pas (l'utilisateur, 2026-11-12).

Renommer, dupliquer et mettre à la corbeille emportent tout ce qui va avec la séance : ses essais de l'onglet Jouer
(-jeu.json), ses versions gardées, ses rapports PDF et le dossier préparé pour Claude.
"""
import os, re, json, glob, shutil, datetime, unicodedata

import rapport

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre",
        "décembre"]
NOMS_GENERIQUES = {"", "bridge game", "bridge coach", "session", "séance", "seance", "tournoi"}   # le nom par défaut de Bridgemate ne dit rien
JOURNAL_MAX = 60
PETITS_MOTS = {"du", "de", "des", "la", "le", "les", "d", "l", "en", "au", "aux", "et"}
# ce qui, à côté du .bc.json, porte le nom de la séance : les essais de Jouer, les anciens originaux et exports
SUITES = ["-jeu.json", "-paires.json", ".bws", ".pbn", ".pdf", ".json", ".csv", ".xlsx",
          "-resultats.csv", "-donnes.csv", "-paires.csv"]
QUOI_PDF = r"(?:analyse|a-revoir|comparaison|standard|expert|archive|diff|donne-\d+)"


def maintenant():
    return datetime.datetime.now().isoformat(timespec="seconds")


def version_programme():
    try:
        return open(os.path.join(rapport.RACINE, "VERSION"), encoding="utf-8").read().strip()
    except OSError:
        return ""


# ---------------------------------------------------------------- noms et titres
def slug(texte, longueur=48):
    """« Tournoi du Jeudi, après-midi » → « tournoi-du-jeudi-apres-midi » : sans accent, sans espace, en minuscules."""
    t = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    if len(t) > longueur: t = t[:longueur].rsplit("-", 1)[0]
    return t


def nettoyer_nom(nom):
    """Un nom de fichier tapé : sans .bc.json, sans accent ni espace ni caractère interdit."""
    nom = (nom or "").strip()
    if nom.lower().endswith(rapport.BC): nom = nom[:-len(rapport.BC)]
    return slug(nom, 80)


def date_longue(d):
    """date(2026, 11, 5) → « jeudi 5 novembre 2026 » (« 1er » pour le premier du mois)."""
    return f"{JOURS[d.weekday()]} {'1er' if d.day == 1 else d.day} {MOIS[d.month - 1]} {d.year}"


def moment(heure):
    """« 14:00 » → « après-midi » ; « 19:30 » → « soir » ; « 09:15 » → « matin » ; rien sans heure."""
    if not heure: return ""
    h = int(heure.split(":")[0])
    return "matin" if h < 12 else "après-midi" if h < 18 else "soir"


def date_de(data):
    """La date de la séance (datetime.date), lue dans session.date « JJ/MM/AAAA »."""
    try:
        j, m, a = data["session"]["date"].split("/")
        return datetime.date(int(a), int(m), int(j))
    except (KeyError, ValueError, AttributeError):
        return None


def titre_propose(data, genre, nom_source=""):
    """Le titre proposé : le nom donné par le fichier quand il dit quelque chose, sinon d'après la date et l'heure."""
    s = data.get("session", {}); d = date_de(data)
    jour = date_longue(d) if d else ""
    propre = (s.get("titre") or nom_source or "").strip()
    if propre.lower() in NOMS_GENERIQUES: propre = ""
    if genre in ("bws", "feuille-de-route") and not propre:
        mot = moment(s.get("heure"))
        plus = ", ".join(x for x in (mot, f"{s['tables']} tables" if s.get("tables") else "") if x)
        return f"Tournoi du {jour}" + (f" ({plus})" if plus else "")
    if genre == "pbn" and not propre: return f"Donnes du {jour}" if jour else "Donnes PBN"
    if genre == "simulation" and not propre: return f"Séance simulée du {jour}"
    if propre and jour and d.strftime("%Y") not in propre: return f"{propre} – {jour}"
    return propre or f"Séance du {jour}"


def nom_propose(data, titre, genre):
    """« 2026-11-05-tournoi-jeudi-apres-midi » : la date d'abord, puis quelques mots du titre (sans la date qu'il
    répète, sans le nombre de tables, sans les petits mots)."""
    d = date_de(data); t = titre or ""
    if d:
        t = t.replace(" – " + date_longue(d), "").replace(date_longue(d), JOURS[d.weekday()])
    t = re.sub(r"\(([^)]*)\)", lambda m: " ".join(x for x in m[1].split(",") if "table" not in x), t)
    mots = [m for m in slug(t, 80).split("-") if m and m not in PETITS_MOTS]
    reste = "-".join(mots)[:40].strip("-") or {"bws": "tournoi", "pbn": "donnes"}.get(genre, "seance")
    return f"{d.isoformat()}-{reste}" if d else reste


def entrainement(now, themes=()):
    """(titre, nom) d'une séance d'entraînement : « Entraînement du mardi 3 novembre 2026 – Squeeze, Impasse »,
    « 2026-11-03-entrainement-squeeze-impasse » ; sans thème (séance vide, donnes saisies) : la date seule."""
    from donnes import SAISIE, ALEATOIRE
    vrais = [t for t in dict.fromkeys(x.strip() for th in themes for x in th.split("+")) if t and t not in (SAISIE, ALEATOIRE)]
    jour = now.date() if isinstance(now, datetime.datetime) else now
    titre = f"Entraînement du {date_longue(jour)}"
    if vrais: titre += " – " + ", ".join(vrais)
    mots = [m for m in slug(" ".join(vrais), 80).split("-") if m and m not in PETITS_MOTS]
    reste = ""
    for m in mots:                                         # des mots entiers, une trentaine de lettres au plus
        if len(reste) + len(m) + 1 > 32: break
        reste += "-" + m
    nom = f"{jour:%Y-%m-%d}-entrainement" + reste
    return titre, nom


def nom_libre(dossier, nom, sauf=None):
    """nom, ou nom-2, nom-3… s'il est déjà pris dans ce dossier (sauf : le fichier qu'on remplace, qui ne compte pas)."""
    k, essai = 2, nom
    while True:
        c = os.path.join(dossier, essai + rapport.BC)
        if not os.path.exists(c) or (sauf and os.path.abspath(c) == os.path.abspath(sauf)): return essai
        essai = f"{nom}-{k}"; k += 1


def dossier_du_mois(data):
    d = date_de(data) or datetime.date.today()
    return os.path.join(rapport.SEANCES, d.strftime("%Y-%m"))


# ---------------------------------------------------------------- lire une source sans l'importer
def lire_source(chemin):
    """(le contenu de la séance, son genre, le nom qu'elle se donne) d'un fichier à importer, sans rien écrire.
    Le .bws est seulement lu, comme à l'import."""
    ext = os.path.splitext(chemin)[1].lower()
    if ext == ".pbn":
        import pbn
        return pbn.seance(chemin), "pbn", ""
    if ext == ".pdf":
        from feuille_route import convertir
        from bws_extract import construire
        T, _ = convertir(chemin)
        for r in T.get("Session", []):
            if isinstance(r.get("Date"), str): r["Date"] = datetime.datetime.fromisoformat(r["Date"])
        return construire(T), "feuille-de-route", ""
    if ext == ".json":
        from bws_extract import extraire
        return extraire(chemin), "simulation", ""
    from bws_extract import lire, construire
    rapport.verifier_fichier(chemin)
    T = lire(chemin)
    data = construire(T)
    s = (T.get("Session") or [{}])[0]
    if s.get("Time"): data["session"]["heure"] = s["Time"].strftime("%H:%M")
    return data, "bws", (s.get("Name") or "").strip()


def deja_importe(chemin):
    """Le .bc.json déjà importé de ce fichier (même nom de fichier d'origine), ou None."""
    base = os.path.basename(chemin)
    for c in rapport.glob_seances("*" + rapport.BC):
        if entete(c).get("source", {}).get("fichier") == base: return c
    return None


def proposer(chemin):
    """Ce qu'on propose avant d'importer : {"titre", "nom", "dossier", "deja" (le fichier déjà importé ou None),
    "genre", "date"}. Déjà importé : son titre et son nom restent proposés (le réimport le met à jour)."""
    data, genre, nom_source = lire_source(chemin)
    deja = deja_importe(chemin)
    dossier = dossier_du_mois(data)
    if deja:
        e = entete(deja)
        titre = e.get("session", {}).get("titre") or titre_propose(data, genre, nom_source)
        return dict(titre=titre, nom=os.path.basename(deja)[:-len(rapport.BC)], dossier=os.path.dirname(deja),
                    deja=deja, genre=genre, date=data["session"]["date"])
    titre = titre_propose(data, genre, nom_source)
    return dict(titre=titre, nom=nom_libre(dossier, nom_propose(data, titre, genre)), dossier=dossier, deja=None,
                genre=genre, date=data["session"]["date"])


# ---------------------------------------------------------------- l'en-tête du fichier
def nouvel_entete(data, genre, origine=None, titre=None, texte=None):
    """Le bloc "fichier" d'un fichier qui naît : créé maintenant, avec cette version ; la source (type, nom, chemin et
    date du fichier d'origine) ; le titre dans session.titre."""
    import datetime as dt
    src = {"type": genre, "fichier": os.path.basename(origine) if origine else "", "importe": maintenant()}
    if origine and os.path.isfile(origine):
        src["chemin"] = os.path.abspath(origine)
        src["date_fichier"] = dt.datetime.fromtimestamp(os.path.getmtime(origine)).isoformat(timespec="seconds")
    data["source"] = src
    if titre: data.setdefault("session", {})["titre"] = titre
    data["fichier"] = {"cree_le": maintenant(), "cree_avec": version_programme(), "journal": []}
    journal(data, texte or (f"Importée de {src['fichier']}" if src["fichier"] else "Créée"))


def journal(data, texte):
    """Une ligne de plus dans l'histoire du fichier (les JOURNAL_MAX dernières sont gardées)."""
    f = data.setdefault("fichier", {})
    j = f.setdefault("journal", [])
    j.append({"le": maintenant(), "quoi": texte})
    del j[:-JOURNAL_MAX]


_ENTETES = {}


def entete(c):
    """L'en-tête d'un .bc.json (source, session sans ses rondes, fichier), lu une fois par version du fichier ; {} s'il
    ne se lit pas."""
    try:
        cle = (c, os.path.getmtime(c))
    except OSError:
        return {}
    if cle not in _ENTETES:
        try:
            d = json.load(open(c, encoding="utf-8"))
            s = {k: v for k, v in d.get("session", {}).items() if k not in ("rondes", "mouvement")}
            _ENTETES[cle] = {"source": d.get("source") or {}, "session": s, "fichier": d.get("fichier") or {},
                             "n_donnes": len(d.get("donnes") or []), "n_paires": len(d.get("paires") or {}),
                             "a_completer": sum(1 for x in d.get("donnes") or [] if x.get("a_completer")),
                             "analyses": {k: (v or {}).get("fait_le") for k, v in (d.get("analyses") or {}).items()}}
        except (OSError, ValueError, AttributeError):
            _ENTETES[cle] = {}
    return _ENTETES[cle]


def titre_de(c):
    """Le titre de la séance, ou son nom de fichier quand elle n'en a pas."""
    t = entete(c).get("session", {}).get("titre")
    return t or os.path.basename(c)[:-len(rapport.BC)] if c else ""


def proposer_pour(c):
    """Une séance d'avant les titres : (titre, nom) proposés, comme à l'import ; None quand elle a déjà un titre et un
    nom qui commence par la date."""
    data = rapport.lire_bc(c)
    s = data.get("session", {}); genre = (data.get("source") or {}).get("type", "")
    a_titre = bool(s.get("titre")) and not re.match(r"Entraînement \d{4}-\d\d-\d\d$", s["titre"])   # l'ancien titre automatique
    a_date = bool(re.match(r"\d{4}-\d\d-\d\d-", base(c)))
    if a_titre and a_date: return None
    if a_titre: titre = s["titre"]
    elif genre in ("entrainement", "saisie"):
        d = date_de(data); titre = entrainement(d or datetime.date.today(), s.get("themes") or [])[0]
    else: titre = titre_propose(data, genre)
    nom = base(c) if a_date else nom_libre(os.path.dirname(c), nom_propose(data, titre, genre))
    if genre in ("entrainement", "saisie") and not a_date:
        d = date_de(data)
        if d: nom = nom_libre(os.path.dirname(c), entrainement(d, s.get("themes") or [])[1])
    return titre, nom


def adopter(c, titre, nom):
    """Le titre et le nom proposés, d'un coup ; renvoie le nouveau chemin."""
    if titre and titre != entete(c).get("session", {}).get("titre"): changer_titre(c, titre)
    return renommer(c, nom) if nom != base(c) else c


def journal_seance(c, texte):
    """Une ligne au journal d'une séance déjà écrite (sans version gardée : rien d'autre ne change)."""
    data = rapport.lire_bc(c); journal(data, texte); rapport.ecrire_bc(data, c)


def changer_titre(c, titre):
    import edition
    titre = (titre or "").strip()
    if not titre: raise ValueError("Le titre ne peut pas être vide.")
    data = rapport.lire_bc(c)
    avant = data.get("session", {}).get("titre")
    if avant == titre: return
    data.setdefault("session", {})["titre"] = titre
    journal(data, f"Titre changé : « {avant} » → « {titre} »" if avant else f"Titre : « {titre} »")
    edition.enregistrer(c, data)


# ---------------------------------------------------------------- ce qui va avec la séance
def base(c):
    return os.path.basename(c)[:-len(rapport.BC)]


def pdfs(c):
    """Les rapports PDF de la séance : rapports/AAAA-MM/<date>-<nom court>-<quoi>[-SS-AR].pdf."""
    data = entete(c); d = date_de(data)
    if not d: return []
    debut = f"{d.isoformat()}-{rapport.nom_court(rapport.nom_seance(c))}-"
    motif = re.compile(re.escape(debut) + QUOI_PDF + r"(?:-[A-Za-z]+)*(?: \d+)?\.pdf$")
    dossier = os.path.join(rapport.RAPPORTS, d.strftime("%Y-%m"))
    return sorted(os.path.join(dossier, f) for f in (os.listdir(dossier) if os.path.isdir(dossier) else [])
                  if motif.match(f))


def dossier_claude(c):
    """<dossier de travail>/pour-claude/<nom du fichier> : ce qu'on prépare pour l'analyse de l'expert."""
    return os.path.join(rapport.DONNEES, "pour-claude", base(c))


def lies(c):
    """{"voisins": [...], "versions": [...], "pdf": [...], "pour_claude": dossier ou None} : ce qui va avec la séance."""
    dossier, b = os.path.dirname(c), base(c)
    voisins = [os.path.join(dossier, b + s) for s in SUITES if os.path.isfile(os.path.join(dossier, b + s))]
    vs = glob.glob(os.path.join(glob.escape(os.path.join(dossier, "versions")), glob.escape(b) + "-v-*" + rapport.BC))
    vs += [f for f in glob.glob(os.path.join(glob.escape(os.path.join(dossier, "versions")), glob.escape(b) + "-*.json"))
           if re.match(re.escape(b) + r"-(standard|expert|expert-avant-.*)\.json$", os.path.basename(f))]
    pc = dossier_claude(c)
    return {"voisins": voisins, "versions": sorted(set(vs)), "pdf": pdfs(c), "pour_claude": pc if os.path.isdir(pc) else None}


def renommer(c, nouveau):
    """Donne un autre nom au fichier et à tout ce qui va avec ; renvoie le nouveau chemin. ValueError en français."""
    nouveau = nettoyer_nom(nouveau)
    if not nouveau: raise ValueError("Le nom ne peut pas être vide.")
    ancien = base(c)
    if nouveau == ancien: return c
    dossier = os.path.dirname(c)
    cible = os.path.join(dossier, nouveau + rapport.BC)
    if os.path.exists(cible): raise ValueError(f"Une séance s'appelle déjà {nouveau} : choisissez un autre nom.")
    tout = lies(c)
    d = date_de(entete(c))
    court_avant = rapport.nom_court(rapport.nom_seance(c))
    court_apres = rapport.nom_court(rapport.nom_seance(cible))
    data = rapport.lire_bc(c)
    journal(data, f"Renommée : {ancien} → {nouveau}")
    rapport.ecrire_bc(data, cible)
    os.remove(c)
    for f in tout["voisins"]:
        os.replace(f, os.path.join(dossier, nouveau + os.path.basename(f)[len(ancien):]))
    for f in tout["versions"]:
        os.replace(f, os.path.join(os.path.dirname(f), nouveau + os.path.basename(f)[len(ancien):]))
    if d:
        avant, apres = f"{d.isoformat()}-{court_avant}-", f"{d.isoformat()}-{court_apres}-"
        for f in tout["pdf"]:
            n = os.path.basename(f)
            if n.startswith(avant): os.replace(f, os.path.join(os.path.dirname(f), apres + n[len(avant):]))
    if tout["pour_claude"]:
        pc = dossier_claude(cible)
        if not os.path.exists(pc): os.replace(tout["pour_claude"], pc)
    return cible


def dupliquer(c, nom, titre):
    """Une copie de la séance sous un autre nom et un autre titre, ses analyses comprises (pas ses essais de Jouer ni
    ses rapports) ; renvoie son chemin."""
    nom = nettoyer_nom(nom)
    if not nom: raise ValueError("Le nom ne peut pas être vide.")
    cible = os.path.join(os.path.dirname(c), nom + rapport.BC)
    if os.path.exists(cible): raise ValueError(f"Une séance s'appelle déjà {nom} : choisissez un autre nom.")
    data = rapport.lire_bc(c)
    avant = data.get("session", {}).get("titre") or base(c)
    data.setdefault("session", {})["titre"] = (titre or "").strip() or f"{avant} (copie)"
    data["fichier"] = {"cree_le": maintenant(), "cree_avec": version_programme(), "journal": []}
    journal(data, f"Copie de « {avant} » ({base(c)})")
    rapport.ecrire_bc(data, cible)
    return cible


def proposer_copie(c):
    """(nom, titre) proposés pour une copie : « …-copie », « … (copie) »."""
    b = base(c); dossier = os.path.dirname(c)
    return nom_libre(dossier, b + "-copie"), f"{titre_de(c)} (copie)"


def corbeille(c):
    """Met la séance et tout ce qui va avec dans <dossier de travail>/corbeille/<date et heure>-<nom>/ : rien n'est
    effacé, on peut la remettre à la main. Renvoie ce dossier."""
    tout = lies(c)
    cible = os.path.join(rapport.DONNEES, "corbeille", f"{datetime.datetime.now():%Y-%m-%d-%H%M%S}-{base(c)}")
    os.makedirs(cible)
    for f in [c] + tout["voisins"]: shutil.move(f, os.path.join(cible, os.path.basename(f)))
    if tout["versions"]:
        os.makedirs(os.path.join(cible, "versions"))
        for f in tout["versions"]: shutil.move(f, os.path.join(cible, "versions", os.path.basename(f)))
    if tout["pdf"]:
        os.makedirs(os.path.join(cible, "rapports"))
        for f in tout["pdf"]: shutil.move(f, os.path.join(cible, "rapports", os.path.basename(f)))
    if tout["pour_claude"]: shutil.move(tout["pour_claude"], os.path.join(cible, "pour-claude"))
    return cible


# ---------------------------------------------------------------- la corbeille : ce qu'on y a mis, et le remettre
def corbeille_dossier():
    return os.path.join(rapport.DONNEES, "corbeille")


def dans_la_corbeille():
    """[(dossier, titre, date de la séance « JJ/MM/AAAA », mise à la corbeille le « JJ/MM/AAAA à HH:MM »)], la plus
    récente d'abord."""
    out = []
    racine = corbeille_dossier()
    for n in sorted(os.listdir(racine) if os.path.isdir(racine) else [], reverse=True):
        d = os.path.join(racine, n)
        bc = [f for f in os.listdir(d) if f.endswith(rapport.BC)] if os.path.isdir(d) else []
        if not bc: continue
        e = entete(os.path.join(d, bc[0]))
        m = re.match(r"(\d{4})-(\d\d)-(\d\d)-(\d\d)(\d\d)\d\d-", n)
        quand = f"{m[3]}/{m[2]}/{m[1]} à {m[4]}:{m[5]}" if m else ""
        out.append((d, e.get("session", {}).get("titre") or bc[0][:-len(rapport.BC)], e.get("session", {}).get("date", ""), quand))
    return out


def remettre(dossier):
    """Remet une séance de la corbeille à sa place, avec ses rapports, ses versions et ses parties jouées ; renvoie
    son chemin. ValueError si une séance porte déjà ce nom."""
    bc = [f for f in os.listdir(dossier) if f.endswith(rapport.BC)]
    if not bc: raise ValueError("Ce dossier de la corbeille ne contient pas de séance.")
    data = rapport.lire_bc(os.path.join(dossier, bc[0]))
    d = date_de(data) or datetime.date.today()
    cible = os.path.join(rapport.SEANCES, d.strftime("%Y-%m"))
    c = os.path.join(cible, bc[0])
    if os.path.exists(c):
        raise ValueError(f"Une séance s'appelle déjà {bc[0][:-len(rapport.BC)]} : renommez-la d'abord (Fichier, Infos).")
    os.makedirs(cible, exist_ok=True)
    for f in os.listdir(dossier):
        p = os.path.join(dossier, f)
        if os.path.isfile(p) and f != bc[0]: shutil.move(p, os.path.join(cible, f))
    vs = os.path.join(dossier, "versions")
    if os.path.isdir(vs):
        os.makedirs(os.path.join(cible, "versions"), exist_ok=True)
        for f in os.listdir(vs): shutil.move(os.path.join(vs, f), os.path.join(cible, "versions", f))
    rs = os.path.join(dossier, "rapports")
    if os.path.isdir(rs):
        r = os.path.join(rapport.RAPPORTS, d.strftime("%Y-%m")); os.makedirs(r, exist_ok=True)
        for f in os.listdir(rs):
            if not os.path.exists(os.path.join(r, f)): shutil.move(os.path.join(rs, f), os.path.join(r, f))
    pc = os.path.join(dossier, "pour-claude")
    if os.path.isdir(pc) and not os.path.exists(dossier_claude(c)): shutil.move(pc, dossier_claude(c))
    journal(data, "Remise de la corbeille")
    rapport.ecrire_bc(data, c)
    os.remove(os.path.join(dossier, bc[0]))
    shutil.rmtree(dossier, ignore_errors=True)             # ce qui reste : des rapports en double, rien d'unique
    return c


# ---------------------------------------------------------------- la sauvegarde
def nom_sauvegarde():
    return f"bridge-coach-sauvegarde-{datetime.datetime.now():%Y-%m-%d}.zip"


def sauvegarder(cible):
    """Un .zip de vos séances (seances/, sans les copies de versions/ ni les originaux), et du dossier documents/ :
    ce que Bridge Coach ne peut pas refaire (l'analyse de l'expert surtout). Les PDF se refont : ils n'y sont pas.
    Renvoie le nombre de séances sauvegardées."""
    import zipfile
    n = 0
    provisoire = cible + ".provisoire"
    with zipfile.ZipFile(provisoire, "w", zipfile.ZIP_DEFLATED) as z:
        for racine in (rapport.SEANCES, os.path.join(rapport.DONNEES, "documents")):
            for r, ds, fs in os.walk(racine):
                ds[:] = [x for x in ds if x != "versions"]
                for f in fs:
                    if f.startswith(".") or f.endswith((".bws", ".provisoire")): continue
                    p = os.path.join(r, f)
                    z.write(p, os.path.relpath(p, rapport.DONNEES))
                    if f.endswith(rapport.BC): n += 1
    os.replace(provisoire, cible)
    return n


# ---------------------------------------------------------------- les licences des séances importées avant la 1.9
def original_de(c):
    """Le .bws d'origine d'une séance, s'il est encore là : là où il était à l'import, à côté de la séance (les imports
    d'avant la 1.7 en gardaient une copie), ou dans le dossier de Bridgemate sous son nom. Seulement lu."""
    src = entete(c).get("source") or {}
    if src.get("type") != "bws": return None
    nom = src.get("fichier") or ""
    candidats = [src.get("chemin"), os.path.join(os.path.dirname(c), nom), os.path.join(os.path.dirname(c), base(c) + ".bws")]
    try:
        d = rapport.dossier_configure()
        candidats += [os.path.join(r, f) for r, _, fs in os.walk(d) for f in fs if f == nom] if nom and os.path.isdir(d) else []
    except Exception:
        pass
    return next((x for x in candidats if x and os.path.isfile(x)), None)


def ajouter_licences(c):
    """Ajoute à une séance Bridgemate d'avant la 1.9 le numéro de licence FFB de ses joueurs, lu dans son .bws d'origine
    (par le nom de chaque joueur). Renvoie le nombre de joueurs complétés (0 : rien à faire, ou pas d'original)."""
    data = rapport.lire_bc(c)
    joueurs = data.get("joueurs") or {}
    if not joueurs or any(j.get("licence") for v in joueurs.values() for j in v): return 0
    bws = original_de(c)
    if not bws: return 0
    from bws_extract import lire, licence_ffb
    try:
        T = lire(bws)
    except Exception:
        return 0
    par_nom = {}
    for r in T.get("PlayerNumbers") or []:
        lic = licence_ffb(r.get("Number"))
        if r.get("Name") and lic: par_nom.setdefault(r["Name"].strip().lower(), lic)
    n = 0
    for v in joueurs.values():
        for j in v:
            lic = par_nom.get((j.get("nom") or "").strip().lower())
            if lic: j["licence"] = lic; n += 1
    if n:
        journal(data, f"Licences des joueurs ajoutées ({n})")
        rapport.ecrire_bc(data, c)
    return n
