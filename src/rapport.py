# -*- coding: utf-8 -*-
"""Produit les PDF d'une séance en une seule commande.

Usage : ./rapport.sh [séance.bws] [--sans-analyse] [--avec-noms] [--avec-releve] [--importer]
--importer : seulement le fichier Bridge Coach (.bc.json), sans analyse ni rapport.
--rapports : seulement les PDF, depuis les analyses déjà enregistrées (après l'import d'une analyse de l'expert).
--analyse-seule : l'analyse standard, enregistrée dans la séance, sans les PDF (l'onglet Analyse ; les PDF se font
dans l'onglet Rapports, avec --rapports).
Toute séance devient d'abord un fichier Bridge Coach, <nom>.bc.json : tout ce que les rapports demandent
(la séance, les joueurs, les donnes, les résultats de chaque table). Il s'importe d'un .bws, d'une feuille
de route PDF de FFBClubNet (feuille_route.py : mains, contrats, entames et résultats, sans enchères ; le
double mort est calculé) ou d'une séance simulée ; un .bc.json se relit tel quel (l'ancien -donnes.json aussi).

Deux dossiers, réglés dans bridge-coach.ini : celui de Bridgemate, où le programme lit les .bws, et le dossier
de travail (seances/, rapports/), hors du dossier où le programme est installé. Le .ini est à une place fixe (dossier_des_reglages).

Sans fichier : liste les .bws du dossier de Bridgemate indiqué dans bridge-coach.ini,
les plus récents d'abord, dix à la fois ; on tape le numéro (Entrée = 1, le plus récent).

Rangement, un dossier par mois (date de la séance), sans sous-dossier par séance ; pas
d'espace dans les noms (remplacés par des tirets) :
  seances/AAAA-MM/   le nom d'origine (Bridgemate porte déjà la date) : <nom>.bws (copie),
                     <nom>.bc.json (la séance et ses analyses : "analyses" {"standard" : celle du programme,
                     refaite à chaque fois ; "expert" : celle rédigée par Claude}), versions/ (copies datées)
  rapports/AAAA-MM/  seulement les PDF, précédés de la date (l'ordre alphabétique suit les niveaux,
                     diff entre les deux analyses qu'il compare) :
                     <date>-<nom>-analyse.pdf (l'analyse du programme et le conseil du coach ; avec une analyse
                         rédigée par Claude, la sienne et l'avis de l'expert, le coach avant lui),
                     <date>-<nom>-archive.pdf (ce qui a été joué, sans conseil ; seulement avec --avec-releve),
                     <date>-<nom>-diff.pdf (programme et expert comparés, comparer.py ; seulement avec une analyse rédigée).
--sans-analyse : l'analyse sans l'avis de l'expert (l'option « Inclure l'avis de l'expert » de l'onglet Rapports).
Avant la 1.4, -standard.pdf et -expert.pdf : refaire les rapports les remplace par -analyse.pdf.

Les joueurs : dans le .bc.json, "joueurs" {paire: [{"initiales", "nom"}, …]}, le nom complet facultatif
(le .bws le donne ; une feuille de route n'a que ce que <nom>-paires.json apporte). Les rapports restent en
initiales ; --avec-noms ajoute une page d'ouverture avec les noms complets.
"""
import sys, os, re, json, shutil, subprocess, tempfile, time, atexit
ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(ICI)


sys.path.insert(0, ICI)                                # -I : le dossier du script n'est pas dans le chemin
from moi import dossier_des_reglages                   # un lieu fixe, propre à l'ordinateur (moi.py)


CONFIG = os.path.join(dossier_des_reglages(), "bridge-coach.ini")


def reglage(cle, defaut):
    """Une valeur de [dossiers] dans bridge-coach.ini ; le fichier peut ne pas exister encore."""
    import configparser
    c = configparser.ConfigParser(interpolation=None)
    c.read(CONFIG, encoding="utf-8")
    return os.path.expanduser(c.get("dossiers", cle, fallback=defaut))


# Les fichiers de l'utilisateur vivent hors du programme : jamais dans le dépôt git.
DONNEES = os.environ.get("BRIDGE_COACH_DONNEES") or reglage("fichiers", "~/Documents/bridge-coach-files")
RAPPORTS = os.path.join(DONNEES, "rapports")
BC = ".bc.json"                                           # le fichier Bridge Coach d'une séance
ANCIEN = "-donnes.json"                                   # son ancien nom, encore lu
VERSION = 1
SEANCES = os.path.join(DONNEES, "seances")
sys.path.insert(0, ICI)
from bws_extract import extraire, JOUEURS
from commentaires import commentaire
from encheres import encherir
from jeu import entame_et_defense, plan_de_jeu, apres_coup, LHO
import coups
import lignes
import multiprocessing


def encheres_auto(d):
    """Grille Ouest/Nord/Est/Sud et explications des enchères calculées (moteur SEF, étape 1)."""
    r = encherir(d)
    k = ["O", "N", "E", "S"].index(d["donneur"])
    cells = ["–"] * k + r["encheres"]
    cells += [""] * (-len(cells) % 4)
    grille = [cells[i:i + 4] for i in range(0, len(cells), 4)]
    lignes = [f"<b>{s} {b}</b> : {x}" for s, b, x in r["explications"] if b != "passe" and x]
    if r["contrat"] != "passe":
        lignes.append(f"Contrat : <b>{r['contrat']} par {r['declarant']}</b>.")
    if r["statut"] != "complète": lignes.append(f"Séquence {r['statut']}.")
    lignes += r["notes"]
    import coach
    from build_pdf import MARQUE_COACH
    avec_coach = lambda texte, conseil: texte + (MARQUE_COACH + " " + conseil if conseil else "")   # le conseil du coach
    out = {"enc": grille, "notes": "<br/>".join(lignes)}   # les décisions serrées y sont déjà (« … convenait aussi »)
    if r["contrat"] != "passe" and d.get("mains"):         # entame, défense et plan de jeu (jeu.py)
        ed = entame_et_defense(d, r["contrat"], r["declarant"], r["encheres"])
        out.update(entame=ed["entame"],
                   defense=avec_coach(ed["defense"], coach.conseil_defense(d, r["contrat"], r["declarant"], ed["entame"], r["encheres"])),
                   plan=avec_coach("", coach.redaction_plan(d, r["contrat"], r["declarant"], ed["entame"], r["encheres"])),   # tout le plan : le coach
                   vues=cartes_vues(d, r["contrat"], r["declarant"], ed["entame"]))
    return out


def coach_pour_expert(d, a_exp, a_std):
    """L'analyse de l'expert d'une donne, avec le conseil du coach (pris dans l'analyse standard) avant chaque avis de
    l'expert, en plan et en défense : seulement si l'expert joue le même contrat, du même déclarant, avec la même entame,
    puisque le coach parle de ceux-là. L'analyse rangée ne change pas : c'est pour l'afficher."""
    from build_pdf import MARQUE_AVIS, MARQUE_COACH, decouper_avis
    from comparer import final
    if not (a_exp and a_std and a_exp.get("enc") and a_std.get("enc")): return a_exp
    out = dict(a_exp, enc_coach=a_std["enc"])              # les enchères du coach, montrées à côté quand elles diffèrent
    meme = final(a_exp["enc"], d["donneur"]) == final(a_std["enc"], d["donneur"]) and \
        (a_exp.get("entame") or {}).get("carte") == (a_std.get("entame") or {}).get("carte")
    if not meme: return out
    for k in ("plan", "defense"):
        coach = decouper_avis(a_std.get(k) or "")[1]
        texte = out.get(k) or ""
        if not coach or not texte or "Le conseil du coach" in texte: continue
        prog, _, avis = texte.partition(MARQUE_AVIS)
        if k == "plan": prog = ""                          # le plan du programme est tout entier dans le conseil du coach
        out[k] = prog + MARQUE_COACH + " " + coach + (MARQUE_AVIS + avis if avis else "")
    return out


def joindre(*textes):
    """Les textes non vides, sans répéter une phrase déjà dite."""
    out = []
    for t in textes:
        if t and t not in " ".join(out): out.append(t)
    return " ".join(out)


def entame_valide(d, decl, carte):
    """La carte est-elle dans la main de l'entameur (à gauche du déclarant) ? « ♦A », « ♠X »…"""
    try:
        return carte[1:] in d["mains"][LHO[decl]].split()["♠♥♦♣".index(carte[0])]
    except (KeyError, IndexError, ValueError):
        return False


def cartes_vues(d, contrat, decl, entame):
    """La dernière section d'une donne : ce que le contrat recommandé donne, toutes cartes vues."""
    if not entame_valide(d, decl, entame.get("carte", "")):    # une analyse mal écrite : on ne rejoue pas une carte absente
        print(f"ATTENTION donne {d['n']} : entame {entame.get('carte')} absente de la main de {LHO[decl]} "
              f"(l'entameur, à gauche de {decl}) : cartes vues sautées")
        return ""
    return " ".join(x for x in (apres_coup(d, contrat, decl, entame),
                                coups.phrase(d["mains"], contrat, decl, entame["carte"])) if x)


def coups_tables(d):
    """Squeeze, mise en main, laisser-passer et coup à blanc dans les contrats les plus joués."""
    vus = {}
    for t in d.get("tables", []):
        e = t.get("entame") or None
        if not t.get("declarant") or not t.get("contrat", "")[:1].isdigit(): continue   # donne passée : pas de jeu
        if e and not entame_valide(d, t["declarant"], e): e = None   # entame mal saisie
        k = (t["contrat"], t["declarant"], e)
        vus[k] = vus.get(k, 0) + 1
    return joindre(*[coups.phrase(d["mains"], *k) for k, _ in sorted(vus.items(), key=lambda x: -x[1])[:2]])


def preparer_donnees():
    """Au premier lancement : les réglages et le dossier de l'utilisateur ; l'ancien rangement est mis à jour."""
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    migrer()
    os.makedirs(SEANCES, exist_ok=True); os.makedirs(RAPPORTS, exist_ok=True)
    if not os.path.exists(CONFIG): shutil.copy(os.path.join(RACINE, "bridge-coach.exemple.ini"), CONFIG)


def migrer():
    """Une fois : reports/ devient rapports/ (les PDF y passent) et chaque <nom>-donnes.json devient <nom>.bc.json,
    avec sa source et ses joueurs (<nom>-paires.json y est fondu puis retiré) ; les analyses rangées à part entrent
    dans leur .bc.json (fondre_analyses)."""
    ancien = os.path.join(DONNEES, "reports")
    if os.path.isdir(ancien):
        for r, _, fs in os.walk(ancien):
            for f in fs:
                if f == ".DS_Store": continue
                cible = os.path.join(RAPPORTS, os.path.relpath(os.path.join(r, f), ancien))
                os.makedirs(os.path.dirname(cible), exist_ok=True)
                os.replace(os.path.join(r, f), cible)
        shutil.rmtree(ancien, ignore_errors=True)
    for f in glob_seances("*" + ANCIEN):
        base = f[:-len(ANCIEN)]
        if os.path.exists(base + BC): continue
        data = json.load(open(f, encoding="utf-8"))
        source, origine = source_d_origine(base)
        entete(data, source, origine)
        paires = base + "-paires.json"
        if os.path.exists(paires): fondre_paires(data, json.load(open(paires, encoding="utf-8")))
        ecrire_bc(data, base + BC)
        os.remove(f)
        if os.path.exists(paires): os.remove(paires)
    fondre_analyses()


def source_d_origine(base):
    """(type, fichier) de l'original rangé à côté d'une séance : le .bws, la feuille de route .pdf (son nom peut
    avoir des espaces), sinon un entraînement ou une source inconnue."""
    nom = os.path.basename(base)
    if nom.startswith("entrainement-"): return "entrainement", nom
    for f in sorted(os.listdir(os.path.dirname(base))):
        ext = os.path.splitext(f)[1].lower()
        if ext in (".bws", ".pdf") and nom_seance(f) == nom:
            return ("bws" if ext == ".bws" else "feuille-de-route"), f
    return "inconnue", nom


def glob_seances(motif):
    import glob
    return sorted(glob.glob(os.path.join(glob.escape(SEANCES), "*", motif)))


def entete(data, source, fichier):
    """Le format, sa version et d'où vient la séance ; joueurs : la liste vide si rien n'est connu."""
    import datetime
    data["format"] = "bridge-coach"; data["version"] = VERSION
    data.setdefault("source", {"type": source, "fichier": fichier,
                               "importe": datetime.datetime.now().isoformat(timespec="seconds")})
    data.setdefault("joueurs", {})
    data.setdefault("alertes", [])
    for k, p in data.get("paires", {}).items():           # les initiales connues, sans nom complet
        if k not in data["joueurs"] and p.get("nom"):
            data["joueurs"][k] = [{"initiales": x} for x in p["nom"].split("/")]


def ecrire_bc(data, chemin):
    """Le fichier Bridge Coach, champs d'en-tête en premier, les analyses à la fin. Écrit sous un nom provisoire puis
    mis à sa place d'un coup : une coupure en cours d'écriture ne laisse jamais un fichier à moitié écrit."""
    tete = {k: data[k] for k in ("format", "version", "source", "session", "joueurs") if k in data}
    corps = dict(tete, **{k: v for k, v in data.items() if k not in tete and k != "analyses"})
    if data.get("analyses"): corps["analyses"] = data["analyses"]
    provisoire = chemin + ".provisoire"
    with open(provisoire, "w", encoding="utf-8") as f: json.dump(corps, f, ensure_ascii=False, indent=1)
    os.replace(provisoire, chemin)


# ---------------------------------------------------------------- les analyses, rangées dans le .bc.json
ANALYSES = ("standard", "expert")       # "standard" : celle du programme, refaite à chaque fois ; "expert" : celle de Claude


def lire_bc(chemin):
    return json.load(open(chemin, encoding="utf-8"))


def analyse_de(chemin, quoi):
    """L'analyse "standard" ou "expert" de la séance ({"systeme", "donnes": {…}, "fait_le"…}), ou None."""
    try:
        return (lire_bc(chemin).get("analyses") or {}).get(quoi)
    except (OSError, ValueError):
        return None


def ecrire_analyse(chemin, quoi, an, dater=True):
    """Range l'analyse dans le .bc.json (None la retire). Le fichier d'avant est d'abord copié dans versions/ :
    toujours pour l'analyse de l'expert, qui ne se refait pas ; au plus toutes les 10 minutes sinon. dater : "fait_le"
    devient maintenant (False quand on retire seulement des donnes, comme après une donne modifiée)."""
    import datetime, edition
    edition.garder_version(chemin, force=quoi == "expert")
    data = lire_bc(chemin); ans = data.setdefault("analyses", {})
    if an is None:
        ans.pop(quoi, None)
    else:
        an = dict(an)
        if dater or "fait_le" not in an: an["fait_le"] = datetime.datetime.now().isoformat(timespec="seconds")
        ans[quoi] = an
    ecrire_bc(data, chemin)


def fondre_analyses():
    """Une fois : les anciens <nom>-standard.json et <nom>-expert.json entrent dans leur .bc.json ; eux et les copies
    -expert-avant-<date>.json vont dans versions/, sous leur nom (rien n'est effacé)."""
    import datetime, glob
    for c in glob_seances("*" + BC):
        base = c[:-len(BC)]
        vieux = [(q, base + f"-{q}.json") for q in ANALYSES if os.path.exists(base + f"-{q}.json")]
        avant = glob.glob(glob.escape(base) + "-expert-avant-*.json")
        if not vieux and not avant: continue
        data = lire_bc(c); ans = data.setdefault("analyses", {})
        for q, f in vieux:
            if q in ans: continue
            try:
                an = json.load(open(f, encoding="utf-8"))
            except ValueError:
                continue                                    # illisible : il part dans versions/ tel quel
            an.setdefault("fait_le", datetime.datetime.fromtimestamp(os.path.getmtime(f)).isoformat(timespec="seconds"))
            ans[q] = an
        if not ans: data.pop("analyses")
        ecrire_bc(data, c)
        rangement = os.path.join(os.path.dirname(c), "versions")
        os.makedirs(rangement, exist_ok=True)
        for f in [f for _, f in vieux] + avant:
            os.replace(f, os.path.join(rangement, os.path.basename(f)))


def noms_complets(data):
    """{paire: [nom, nom]} pour --avec-noms : seulement les paires dont les deux noms sont connus."""
    return {k: [j["nom"] for j in v] for k, v in data.get("joueurs", {}).items()
            if v and all(j.get("nom") for j in v)}


def dossier_configure():
    """Le dossier de Bridgemate, où chercher les .bws. Le programme ne fait qu'y lire : il travaille sur une copie.
    Un chemin relatif part du dossier de l'utilisateur."""
    d = reglage("bridgemate", "~/Documents/bridgemate-files")
    return d if os.path.isabs(d) else os.path.join(DONNEES, d)


def date_du_fichier(f):
    """Pour le tri : la date que porte le nom (Bridgemate : …23102026… = 23/10/2026 ; ou AAAA-MM-JJ),
    sinon la date du fichier."""
    import datetime
    nom = os.path.basename(f)
    m = re.search(r"(\d{4})-(\d\d)-(\d\d)", nom)
    if m: return f"{m[1]}-{m[2]}-{m[3]}"
    for m in re.finditer(r"(?=(\d\d)(\d\d)(20\d\d))", nom):     # JJMMAAAA
        try: return datetime.date(int(m[3]), int(m[2]), int(m[1])).isoformat()
        except ValueError: pass
    return datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d")


def seances_du_dossier(dossier):
    """Les .bws du dossier, sous-dossiers compris, du plus récent au plus ancien."""
    return sorted((os.path.join(r, f) for r, _, fs in os.walk(dossier) for f in fs if f.lower().endswith(".bws")),
                  key=lambda f: (date_du_fichier(f), os.path.getmtime(f)), reverse=True)


def nom_seance(chemin):
    """Le nom de la séance dans seances/ et rapports/ : sans extension, sans date en tête, sans espace."""
    base = os.path.basename(chemin)
    for ext in (BC, ANCIEN, ".json", ".bws", ".pdf"):    # .bc.json, séance.bws, séance simulée .json, feuille de route .pdf
        if base.lower().endswith(ext): base = base[:-len(ext)]; break
    base = re.sub(r"^\d{4}-\d\d-\d\d-", "", base)        # déjà rangée : pas de date en double
    return re.sub(r"\s+", "-", base.strip())               # pas d'espace dans les noms de fichier


def nom_court(nom):
    """Le nom de la séance dans rapports/, après la date mise en tête : sans la date qu'il contient, et
    l'heure qui la suit passe devant (entrainement-2026-11-01-224232 → 224232-entrainement)."""
    m = re.search(r"-?\d{4}-\d\d-\d\d(?:-(\d{6}))?(?=-|$)", nom)
    if not m: return nom
    reste = (nom[:m.start()] + nom[m.end():]).strip("-")
    return "-".join(x for x in (m[1], reste) if x) or nom


def choisir_seance():
    """Liste les .bws du dossier configuré (sous-dossiers compris), du plus récent au plus ancien,
    dix à la fois."""
    dossier = dossier_configure()
    if not os.path.isdir(dossier):
        raise SystemExit(f"Dossier introuvable : {dossier} (à régler dans {CONFIG})")
    fichiers = seances_du_dossier(dossier)
    if not fichiers:
        raise SystemExit(f"Aucun fichier .bws dans {dossier} (dossier réglé dans {CONFIG})")
    debut = 0
    while True:
        page = fichiers[debut:debut + 10]
        print(f"Fichiers .bws dans {dossier}, du plus récent au plus ancien :")
        for k, f in enumerate(page, 1):
            print(f"  {k:2}  {date_du_fichier(f)}  {os.path.relpath(f, dossier)}")
        suite = debut + 10 < len(fichiers)
        try:
            r = input(f"Numéro (1–{len(page)}, Entrée = 1{', s = suivants' if suite else ''}, q = quitter) : ").strip().lower()
        except EOFError:
            r = ""
        if r == "q": raise SystemExit(0)
        if r == "s" and suite: debut += 10; continue
        if r == "": return page[0]
        if r.isdigit() and 1 <= int(r) <= len(page): return page[int(r) - 1]
        print("Réponse non comprise.")


FICHIER_NOMS = []                                         # --avec-noms : le JSON provisoire des noms


def fondre_paires(data, paires):
    """<nom>-paires.json (feuille de route) : {"6": "AM/BD", …, "noms": {"6": ["nom", "nom"]}} : les initiales
    partout, et les noms complets dans "joueurs"."""
    noms = paires.get("noms", {})
    ini = {k: v for k, v in paires.items() if k != "noms"}
    for d in data["donnes"]:
        for t in d["tables"]:
            t["nom_ns"] = ini.get(str(t["paire_ns"]), t["nom_ns"])
            t["nom_eo"] = ini.get(str(t["paire_eo"]), t["nom_eo"])
    for k, p in data.get("paires", {}).items():
        p["nom"] = ini.get(k, p["nom"])
    joueurs = data.setdefault("joueurs", {})
    for k in set(ini) | set(noms):
        i = (ini.get(k) or "").split("/") if ini.get(k) else []
        n = noms.get(k, [])
        joueurs[k] = [dict({"initiales": i[x]} if x < len(i) else {}, **({"nom": n[x]} if x < len(n) else {}))
                      for x in range(max(len(i), len(n)))]


def joueurs_bws(data, complets):
    """Les joueurs d'une séance tirée d'un .bws : initiales de "paires", nom complet du .bws (en mémoire)."""
    out = {}
    for k, p in data.get("paires", {}).items():
        if not p.get("nom"): continue
        n = complets.get(k, [])
        out[k] = [dict({"initiales": x}, **({"nom": n[i]} if i < len(n) else {})) for i, x in enumerate(p["nom"].split("/"))]
    return out


def donnes_pretes(chemin):
    """Le contenu d'un fichier Bridge Coach (.bc.json, ou l'ancien -donnes.json), ou None pour un autre fichier. Une séance simulée est
    aussi un .json, mais sans "donnes" : ce sont les tables d'un .bws."""
    if not chemin.lower().endswith(".json"): return None
    try:
        data = json.load(open(chemin, encoding="utf-8"))
    except ValueError:
        raise SystemExit(f"{os.path.basename(chemin)} n'est pas un fichier de données lisible.")
    if not isinstance(data, dict) or "tables" in data: return None
    if data.get("donnes") == [] and "date" in data.get("session", {}):
        raise SystemExit("Cette séance n'a encore aucune donne : ajoutez-en dans l'onglet Donnes.")
    if not data.get("donnes") or "date" not in data.get("session", {}):
        raise SystemExit(f"{os.path.basename(chemin)} n'est pas un fichier de données lisible.")
    data.setdefault("alertes", [])
    return data


def verifier_fichier(chemin):
    """Un .bws est une base Access. Les sauvegardes de FFBClubNet portent aussi l'extension .bws,
    mais ce sont des archives 7-Zip protégées par un mot de passe : on le dit clairement."""
    if chemin.lower().endswith(".json"): return
    debut = open(chemin, "rb").read(32)
    if debut[:2] == b"7z":
        raise SystemExit(f"{os.path.basename(chemin)} n'est pas un vrai .bws : c'est une archive 7-Zip (sauvegarde "
                         "FFBClubNet), protégée par un mot de passe.\nIl faut le .bws d'origine de Bridgemate "
                         "Control Software, ou l'extraire de l'archive avec son mot de passe.")
    if b"Standard Jet DB" not in debut and b"Standard ACE DB" not in debut:
        raise SystemExit(f"{os.path.basename(chemin)} n'est pas un fichier Bridgemate (.bws) lisible.")


class Chrono:
    """Le temps de chaque étape de l'analyse, écrit dans rapports/derniere-analyse.txt : de quoi voir ce qui est lent
    sur un autre ordinateur (nombre de cœurs, mémoire, processus du solveur, repli sur un seul cœur)."""
    def __init__(self):
        self.debut = self.t = time.time(); self.etapes = []

    def etape(self, nom):
        maintenant = time.time(); self.etapes.append((nom, maintenant - self.t)); self.t = maintenant

    def ecrire(self, n):
        import datetime, platform
        self.etape("fin (rapport expert et comparaison)")
        total = time.time() - self.debut
        lignes_txt = [f"Analyse du {datetime.datetime.now():%d/%m/%Y %H:%M}", f"Système : {platform.platform()}",
                      f"Python : {platform.python_version()}", f"Cœurs : {os.cpu_count()}, mémoire : {lignes._memoire():.1f} Go, "
                      f"processus du solveur : {lignes.nb_processus()}",
                      "Repli sur un seul cœur : " + (", ".join(lignes.REPLIS) if lignes.REPLIS else "non"),
                      f"Total : {total / 60:.1f} min pour {n} donnes", ""]
        lignes_txt += [f"{nom:<40} {s:7.1f} s" for nom, s in self.etapes if s >= 0.05]
        try:
            os.makedirs(RAPPORTS, exist_ok=True)
            with open(os.path.join(RAPPORTS, "derniere-analyse.txt"), "w", encoding="utf-8") as f: f.write("\n".join(lignes_txt) + "\n")
        except OSError:
            pass


def main():
    lignes.PARALLELE = True                                # le déclarant simulé, sur tous les cœurs
    preparer_donnees()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sans = "--sans-analyse" in sys.argv; avec_noms = "--avec-noms" in sys.argv; importer = "--importer" in sys.argv
    rapports_seuls = "--rapports" in sys.argv; analyse_seule = "--analyse-seule" in sys.argv
    if not args: args = [choisir_seance()]
    if len(args) != 1 or not os.path.isfile(args[0]):
        raise SystemExit("Usage : ./rapport.sh [séance.bws] [--sans-analyse] [--avec-noms] [--avec-releve] [--importer] [--rapports] [--analyse-seule]")

    bws = os.path.abspath(args[0])
    source = {".bws": "bws", ".pdf": "feuille-de-route", ".json": "simulation"}.get(os.path.splitext(bws)[1].lower(), "inconnue")
    origine = os.path.basename(bws)
    if bws.lower().endswith(".pdf"):                    # feuille de route FFBClubNet : devient une séance JSON
        from feuille_route import convertir
        T, _ = convertir(bws)
        bws = os.path.join(tempfile.mkdtemp(), nom_seance(bws) + ".json")
        json.dump({"format": "tables Bridgemate (feuille de route FFBClubNet)", "tables": T},
                  open(bws, "w"), ensure_ascii=False)
    nom = nom_seance(bws)

    verifier_fichier(bws)
    pret = donnes_pretes(bws)
    data = pret or extraire(bws)
    j, m, a = data["session"]["date"].split("/")
    date = f"{a}-{m}-{j}"
    DATA = os.path.join(SEANCES, f"{a}-{m}"); SORTIE = os.path.join(RAPPORTS, f"{a}-{m}")
    if pret and bws.endswith(BC) and os.path.dirname(os.path.dirname(bws)) == os.path.abspath(SEANCES):
        DATA = os.path.dirname(bws); nom = os.path.basename(bws)[:-len(BC)]   # déjà rangée : elle reste où elle est, sous son nom
    os.makedirs(DATA, exist_ok=True); os.makedirs(SORTIE, exist_ok=True)
    fichier = lambda suite: os.path.join(DATA, nom + suite)   # seances : le nom d'origine, sans date
    donnes = seance = fichier(BC)                          # donnes peut devenir une copie provisoire ; seance reste le fichier
    if not pret:                                           # importée : le fichier Bridge Coach se fait ici
        data["joueurs"] = joueurs_bws(data, {str(k): v for k, v in JOUEURS.items()})
        entete(data, source, origine)
        if os.path.exists(donnes):                         # réimport : les noms complets déjà saisis restent
            avant = json.load(open(donnes, encoding="utf-8")).get("joueurs", {})
            for k, v in data["joueurs"].items():
                for j, w in zip(v, avant.get(k, [])):
                    if w.get("nom") and not j.get("nom"): j["nom"] = w["nom"]
            ans = json.load(open(donnes, encoding="utf-8")).get("analyses")
            if ans: data["analyses"] = ans                 # réimport : les analyses restent
    else:
        entete(data, "inconnue", origine)
    if os.path.exists(fichier("-paires.json")):           # feuille de route : initiales (et noms) à part
        fondre_paires(data, json.load(open(fichier("-paires.json"), encoding="utf-8")))
    if avec_noms:
        complets = noms_complets(data)
        if not complets: raise SystemExit("Les noms complets des joueurs ne sont pas disponibles pour cette séance.")
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)     # jamais dans seances/
        json.dump(complets, tmp, ensure_ascii=False); tmp.close()
        atexit.register(os.unlink, tmp.name)
        FICHIER_NOMS.append(tmp.name)
    if not pret:                                           # l'original, gardé à côté (le .bc.json suffit ensuite)
        copie = fichier(os.path.splitext(bws)[1].lower())
        if not (os.path.exists(copie) and os.path.samefile(bws, copie)):
            shutil.copy2(bws, copie)
    print(f"Séance : {donnes}")
    ecrire_bc(data, donnes)
    if importer:                                           # --importer : le fichier Bridge Coach seulement
        print(f"Fichier prêt : {donnes}", flush=True)
        return
    a_finir = [d["n"] for d in data["donnes"] if d.get("a_completer")]
    if a_finir:                                            # donnes en cours de saisie : ni analyse ni rapport
        print(f"Donnes à compléter, laissées de côté : {', '.join(map(str, a_finir))}")
        data["donnes"] = [d for d in data["donnes"] if not d.get("a_completer")]
        if not data["donnes"]: raise SystemExit("Aucune donne complète dans cette séance : complétez-en au moins une.")
        tmp = tempfile.NamedTemporaryFile("w", suffix=BC, delete=False)   # les rapports lisent ce fichier-ci
        json.dump(data, tmp, ensure_ascii=False); tmp.close(); atexit.register(os.unlink, tmp.name)
        donnes = tmp.name
    print(f"{len(data['donnes'])} donnes, séance du {data['session']['date']}, {data['session']['tables']} tables")
    for x in data["alertes"]: print("ALERTE :", x)

    # analyse automatique (enchères SEF + commentaire), toujours régénérée et enregistrée
    # vues : tout ce qui demande de voir les cartes, en dernière section (jamais dans le plan)
    chrono = Chrono()
    tables = {str(d["n"]): coups_tables(d) for d in data["donnes"]}
    chrono.etape("coups des tables (cartes vues)")
    if rapports_seuls:                                     # --rapports : les PDF depuis les analyses enregistrées
        auto = analyse_de(seance, "standard")
        if not auto:
            raise SystemExit("Pas encore d'analyse standard pour cette séance : lancez d'abord l'analyse.")
        manquent = [str(d["n"]) for d in data["donnes"] if str(d["n"]) not in auto.get("donnes", {})]
        if manquent:
            raise SystemExit(f"L'analyse standard manque pour {'la donne' if len(manquent) == 1 else 'les donnes'} "
                             f"{', '.join(manquent)} : relancez l'analyse standard.")
        print("Analyse standard reprise")
    else:
        auto = {"systeme": "sef-2024", "automatique": True, "donnes": {}}
        for k, d in enumerate(data["donnes"], 1):
            print(f"Donne {k} sur {len(data['donnes'])}", flush=True)   # l'application en fait sa barre de progression
            x = encheres_auto(d); n = str(d["n"])
            x["vues"] = joindre(x.get("vues"), tables[n])
            auto["donnes"][n] = dict(x, comm=commentaire(d))
            chrono.etape(f"donne {n}")
        ecrire_analyse(seance, "standard", auto)
        print(f"Analyse automatique rangée dans {os.path.basename(seance)}")
        if analyse_seule:                                  # --analyse-seule : l'analyse, sans les PDF (onglet Rapports)
            chrono.ecrire(len(data["donnes"])); print("Analyse prête", flush=True)
            return

    pdf = lambda quoi: os.path.join(SORTIE, f"{date}-{nom_court(nom)}-{quoi}.pdf")
    an = analyse_de(seance, "expert")
    redigee = bool(an and an.get("donnes"))
    # archive : ce qui a été joué, sans recommandation (le commentaire factuel reste)
    joue = {"titre_pied": f"Relevé des donnes – séance du {data['session']['date']}",
               "donnes": {n: {"comm": x["comm"], "vues": tables[n]} for n, x in auto["donnes"].items()}}
    if "--avec-releve" in sys.argv and any(d["tables"] for d in data["donnes"]):   # sur demande ; des donnes créées
        construire_pdf(donnes, joue, {"donnes": {}}, pdf("archive"))                # n'ont pas été jouées
    def anciens():                                         # avant la 1.4, deux rapports : -standard et -expert, que -analyse remplace
        for q in ("standard", "expert"):
            if os.path.exists(pdf(q)): os.remove(pdf(q))
    if sans or not redigee:                                # l'analyse du programme et le conseil du coach
        print("Sans l'avis de l'expert (--sans-analyse)" if sans and redigee
              else "Pas d'analyse de l'expert", ": l'analyse du programme seulement.")
        construire_pdf(donnes, {}, auto, pdf("analyse")); anciens()
        if not redigee:
            chrono.etape("rapports PDF"); chrono.ecrire(len(data["donnes"]))
            return
    else:                                                  # avec l'avis de l'expert : son analyse, et le coach avant lui
        from comparer import final
        for d in data["donnes"]:                           # les cartes vues du contrat de l'expert
            a = an["donnes"].get(str(d["n"]), {})
            if a.get("enc") and isinstance(a.get("entame"), dict):
                c, decl, dbl = final(a["enc"], d["donneur"])
                if c != "passe":
                    a["vues"] = joindre(cartes_vues(d, c + "X" * dbl, decl, a["entame"]), tables[str(d["n"])])
        std_d = auto.get("donnes") or {}
        an = dict(an, donnes={n: coach_pour_expert(next((d for d in data["donnes"] if str(d["n"]) == n), {"donneur": "N"}), x,
                                                   std_d.get(n)) for n, x in an["donnes"].items()})
        construire_pdf(donnes, an, auto, pdf("analyse")); anciens()
    chrono.etape("rapport d'analyse"); atexit.register(chrono.ecrire, len(data["donnes"]))
    sys.stdout.flush()
    provisoire = pdf("diff")[:-4] + ".provisoire.pdf"
    fauto, fexpert = (provisoire_json(analyse_de(seance, q)) for q in ANALYSES)   # comparer.py lit deux fichiers
    subprocess.run([sys.executable, "-I", "-X", "utf8", os.path.join(ICI, "comparer.py"), donnes, fauto, fexpert,
                    provisoire] + FICHIER_NOMS, check=True)
    remplacer(provisoire, pdf("diff"))
    subprocess.run([sys.executable, "-I", "-X", "utf8", os.path.join(ICI, "bilan.py")])   # toutes les séances : pas bloquant


def provisoire_json(x):
    """Un fichier JSON provisoire, effacé à la sortie du programme ; renvoie son chemin."""
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(x, tmp, ensure_ascii=False); tmp.close(); atexit.register(os.unlink, tmp.name)
    return tmp.name


def construire_pdf(donnes, an, auto, pdf):
    """PDF de l'analyse an, complétée donne par donne par l'analyse automatique."""
    textes = an.setdefault("donnes", {})                   # le texte rédigé l'emporte
    for n, x in auto["donnes"].items():
        a = textes.setdefault(n, {})
        a.setdefault("comm", x["comm"])
        if "enc" not in a:                                 # enchères, entame et plan vont ensemble
            a.update({k: v for k, v in x.items() if k in ("enc", "notes", "entame", "defense", "plan", "vues")})
            a["auto"] = True                               # ses notes ne sont pas un avis de l'expert
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(an, tmp, ensure_ascii=False); tmp.close()
    sys.stdout.flush()
    # écrit sous un nom provisoire puis remplace le PDF d'un coup : avec Documents synchronisé
    # par iCloud, réécrire le fichier en place laissait parfois l'ancienne version
    provisoire = pdf[:-4] + ".provisoire.pdf"
    subprocess.run([sys.executable, "-I", "-X", "utf8", os.path.join(ICI, "build_pdf.py"), donnes, tmp.name, provisoire] + FICHIER_NOMS, check=True)
    os.unlink(tmp.name)
    remplacer(provisoire, pdf)


def remplacer(provisoire, pdf):
    """Met le PDF écrit sous un nom provisoire à sa place, d'un coup, et vérifie qu'il est à jour."""
    os.replace(provisoire, pdf)
    print(f"Rapport prêt : {pdf}", flush=True)
    if abs(os.path.getmtime(pdf) - time.time()) > 120:
        print(f"ATTENTION : {os.path.basename(pdf)} n'a pas été mis à jour (synchronisation iCloud ?)")


if __name__ == "__main__":
    multiprocessing.freeze_support()                       # Windows, si le programme est empaqueté un jour
    main()
