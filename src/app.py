# -*- coding: utf-8 -*-
"""L'application des rapports : une fenêtre, un bouton. Lancement : ./bridge-coach.sh

Elle ne fait que conduire rapport.py, dans un processus à part : l'analyse dure plusieurs minutes,
utilise tous les cœurs et n'a rien à faire dans le serveur de la fenêtre. Sa progression vient des
lignes que rapport.py écrit (« Donne 3 sur 24 », « Rapport prêt : … »).

    --navigateur   ouvre dans le navigateur plutôt que dans une fenêtre
    --sans-ouvrir  ne fait que servir la page (essais)
"""
import asyncio, datetime, glob, json, os, re, shutil, signal, subprocess, sys, tempfile, threading

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import carte, donnes, edition, jouer, maj, rapport
from nicegui import app, background_tasks, run, ui

if __name__ == "__mp_main__" and sys.platform == "darwin":  # la fenêtre : son processus s'appelle Python, le Dock garde Bridge Coach
    try:
        import webview.platforms.cocoa as _cocoa           # elle se déclare au Dock en se chargeant, ensuite on la retire
        _cocoa.BrowserView.app.setActivationPolicy_(1)
    except Exception:                                      # au pire, l'icône Python revient
        pass

TITRE = "Bridge Coach"
PORT = 8123
PART_ANALYSE = .85                                         # la part de la barre pour l'analyse, le reste pour les PDF
NB_PDF = 4
RAPPORTS = (("archive", "Relevé des donnes", "ce qui a été joué"), ("standard", "Analyse", "enchères, entame et plan de jeu"),
            ("expert", "Analyse de l'expert", "avec l'avis de l'expert"), ("diff", "Comparaison", "programme et expert"))
TYPES_FICHIERS = ("Tournois (*.bws;*.pdf;*.json)", "Tous les fichiers (*.*)")
TYPES_SEANCES = ("Séances Bridge Coach (*.bc.json;*.json)", "Tous les fichiers (*.*)")
TYPES_IMPORT = ("Bridgemate ou feuille de route (*.bws;*.pdf)", "Tous les fichiers (*.*)")
TYPES_EXPERT = ("Analyse expert (*.json)", "Tous les fichiers (*.*)")   # pywebview : lettres et espaces seulement, pas d'apostrophe
SOURCES = {"bws": "Bridgemate", "feuille-de-route": "Feuille de route", "entrainement": "Entraînement",
           "saisie": "Donnes saisies", "simulation": "Simulation"}
AIDE = os.path.join(rapport.RACINE, "help", "index.html")
GENERIQUE = "Le rapport n'a pas pu être créé. Le détail est dans le fichier derniere-erreur.txt du dossier des rapports."


class Travail:
    """Le rapport en cours : un seul à la fois, quelle que soit la page ouverte."""

    def __init__(self, part=PART_ANALYSE, mot="Analyse de la donne"):
        self.part = part; self.mot = mot                   # la part de la barre pour les donnes, le mot affiché
        self.proc = None; self.fraction = 0.0; self.texte = ""; self.erreur = ""; self.fini = False; self.annule = False
        self.prets = []; self.seance = None; self.fichier = None; self.notes = []

    @property
    def actif(self): return self.proc is not None and not self.fini


T = Travail()                                              # les rapports
D = Travail(1.0, "Création de la donne")                   # les donnes
I = Travail(1.0, "Import")                                 # un import (le .bc.json seulement)


def lire_ligne(t, ligne):
    """Avance la progression selon une ligne de rapport.py."""
    m = re.match(r"Donne (\d+) sur (\d+)", ligne)
    if m:
        k, n = int(m[1]), int(m[2])
        t.fraction = t.part * (k - 1) / n; t.texte = f"{t.mot} {k} sur {n}"
        return
    m = re.match(r"Rapport prêt : (.+)", ligne)
    if m:
        t.prets.append(m[1].strip())
        t.fraction = t.part + (1 - t.part) * min(len(t.prets) / NB_PDF, 1); t.texte = "Écriture des rapports"   # + le bilan
        return
    m = re.match(r"Fichier prêt : (.+)", ligne)
    if m: t.fichier = m[1].strip()
    m = re.match(r"Thème non trouvé : (.+)", ligne)
    if m: t.notes.append(m[1].strip())


def message_erreur(sortie):
    """Ce qu'on montre : le message de rapport.py s'il en a écrit un, jamais une trace Python."""
    sortie = sortie.strip()
    if not sortie or "Traceback" in sortie: return GENERIQUE
    return sortie.splitlines()[-1] if len(sortie) > 300 else sortie


def rapports_de(chemin):
    """{niveau: pdf} déjà produits pour cette séance."""
    nom = rapport.nom_court(rapport.nom_seance(chemin)); out = {}
    for quoi, _, _ in RAPPORTS:
        x = sorted(glob.glob(os.path.join(glob.escape(rapport.RAPPORTS), "*", f"*-{glob.escape(nom)}-{quoi}.pdf")))
        if x: out[quoi] = x[-1]
    return out


def date_lisible(chemin):
    d = datetime.date.fromisoformat(rapport.date_du_fichier(chemin))
    return d.strftime("%d/%m/%Y")


GRIS_BARRE = "#f3f3f1"
LARGEUR_PANNEAU = 300                                     # la barre de droite de l'onglet Jouer
# le côté de la table de l'onglet Jouer : ce que laissent la largeur (barres, mains des côtés) et la hauteur (mains du
# haut et du bas), 440px au moins : en dessous, toute la table rétrécit (JS_AJUSTE)
COTE_TABLE = "clamp(440px, min(100vw - 740px, 100vh - 375px), 640px)"
HAUTEUR_BARRE = 37                                        # la barre de menus du haut                                    # le gris clair des barres latérales, comme celle de Claude

JS_AJUSTE = """<script>
// La table de l'onglet Jouer rétrécit avec la fenêtre plutôt que d'ouvrir une barre de défilement : le bloc .ajuste
// garde sa taille naturelle et prend l'échelle qui le fait tenir dans la largeur de son parent et la hauteur de la fenêtre.
(function () {
  function ajuster() {
    document.querySelectorAll('.ajuste').forEach(function (el) {
      var parent = el.parentElement, w = el.offsetWidth, h = el.offsetHeight;
      if (!w || !h) return;
      var marge = parseFloat(getComputedStyle(parent).paddingTop) || 0;
      var haut = parent.getBoundingClientRect().top + window.scrollY + marge;
      var e = Math.min(1, parent.clientWidth / w, (window.innerHeight - haut - 8) / h);
      e = Math.max(e, 0.45);
      el.style.transform = 'scale(' + e + ')';
      el.style.marginLeft = Math.max(0, (parent.clientWidth - w * e) / 2) + 'px';
      parent.style.height = Math.ceil(h * e + marge) + 'px';
    });
  }
  var vus = new WeakSet(), ro = new ResizeObserver(ajuster);
  function suivre() {
    document.querySelectorAll('.ajuste').forEach(function (el) {
      if (!vus.has(el)) { vus.add(el); ro.observe(el); ro.observe(el.parentElement); }
    });
  }
  window.addEventListener('resize', ajuster);
  document.addEventListener('DOMContentLoaded', function () {
    new MutationObserver(function () { suivre(); ajuster(); }).observe(document.body, {childList: true, subtree: true});
    suivre(); ajuster();
  });
})();
</script>"""

CSS_CARTES = """
::-webkit-scrollbar { width: 14px; height: 14px; background: transparent; }
::-webkit-scrollbar-thumb { background: #cfcfcb; border-radius: 7px; border: 2px solid transparent; background-clip: padding-box; }
::-webkit-scrollbar-thumb:hover { background-color: #b5b5b0; }
::-webkit-scrollbar-track, ::-webkit-scrollbar-corner { background: transparent; }
* { scrollbar-color: #cfcfcb transparent; }
.entree-barre { width: 100%; justify-content: flex-start; border-radius: 8px; padding: 4px 12px; font-weight: 400;
  color: #2b2b2b; min-height: 32px; }
.entree-barre.choisie { background: #e4e3df; font-weight: 600; }
.entree-barre .q-btn__content { text-align: left; justify-content: flex-start; line-height: 1.3; padding: 2px 0; }
.carte { width: 46px; height: 66px; margin-right: -18px; padding: 3px 5px; background: #fff; border: 1px solid #b9c0c7;
  border-radius: 6px; font-size: 18px; line-height: 1.05; font-weight: 600; color: #1b1b1b; }
.carte.r { color: #c0141c; }
.carte.jouable { cursor: pointer; border-color: #1f6b45; }
.carte.jouable:hover { transform: translateY(-6px); }
.carte.terne { opacity: .45; }
.colonne-mort .carte { margin-right: 0; }
.colonne-mort > * + * { margin-top: -42px; }
.mort-table .carte { width: 42px; height: 60px; font-size: 17px; }
.mort-table .colonne-mort > * + * { margin-top: -42px; }   /* le mort sur la table : un peu plus serré, la table reste carrée */
.carte.vide { width: 22px; border: none; background: none; margin-right: 0; padding: 3px 0; }
.eventail .groupe { margin-right: 26px; }
.eventail .groupe:last-child { margin-right: 16px; }
.groupe.colonne .carte { width: 34px; height: 46px; margin-right: -15px; padding: 2px 4px; font-size: 15px; }
.dos { width: 32px; height: 46px; border-radius: 4px; border: 2px solid #fff; outline: 1px solid #c3cbd4;
  background: repeating-linear-gradient(45deg, #9aa8b8 0 3px, #b0bccA 3px 6px); }
.plis-gardes { display: flex; align-items: center; min-height: 30px; }
.plis-gardes .dos { width: 20px; height: 28px; border-width: 1px; border-radius: 3px; flex: none; }
.plis-gardes .dos.couche { width: 28px; height: 20px; }   /* comme en duplicate : vers le partenaire gagné, en travers perdu */
.plis-gardes .dos + .dos { margin-left: -9px; }           /* chaque carte posée en partie sur la précédente */
.plis-gardes.colonne { flex-direction: column; min-height: 0; min-width: 30px; }
.plis-gardes.colonne .dos + .dos { margin-left: 0; margin-top: -9px; }
.main-grande .carte { width: 55px; height: 79px; font-size: 20px; margin-right: -22px; }
.main-grande .groupe { margin-right: 30px; }
.main-grande.a-vous { filter: drop-shadow(0 0 6px rgba(242, 183, 5, .9)); }
.onglet.eteint { background: #d9d9d6 !important; color: #9a9a96 !important; }
.onglet.indice { background: #fff; color: #1f6b45; display: flex; align-items: center; gap: 2px; }
.sa { color: #2b2b2b; background: #eceff1; } .pique { color: #1f3fa0; background: #e3eaf8; }
.coeur { color: #c0141c; background: #fbe4e4; } .carreau { color: #c86a00; background: #fff0d6; }
.trefle { color: #1d7a35; background: #e1f2e5; }
.carton { position: relative; width: 72px; height: 46px; padding: 2px 6px; border: 1px solid #8e99a4; border-radius: 5px;
  font-size: 20px; font-weight: 700; box-shadow: 0 1px 2px rgba(0,0,0,.25); display: flex; align-items: flex-start;
  justify-content: flex-start; line-height: 1.1; }
.carton.passe { background: #2e7d32; border-color: #1f5e24; color: #fff; font-size: 17px; }
.carton.contre { background: #c62828; border-color: #8e1b1b; color: #fff; }
.carton.surcontre { background: #1565c0; border-color: #0d4a8f; color: #fff; }
.carton.recent { outline: 2px solid #f2b705; }
.carton:not(.derniere)::after { content: ""; position: absolute; inset: -1px; border-radius: 5px;
  background: rgba(255, 255, 255, .4); }   /* la dernière enchère de chacun en clair, les précédentes voilées */
.pile { display: flex; align-items: center; justify-content: center; min-height: 46px; min-width: 78px; }
.pile.vers-bas { flex-direction: column; } .pile.vers-bas .carton + .carton { margin-top: -19px; }
.pile.vers-haut { flex-direction: column-reverse; } .pile.vers-haut .carton { align-items: flex-end; }
.pile.vers-haut .carton + .carton { margin-bottom: -17px; }
.pile.vers-droite { flex-direction: row; } .pile.vers-droite .carton + .carton { margin-left: -22px; }
.pile.vers-gauche { flex-direction: row-reverse; } .pile.vers-gauche .carton { justify-content: flex-end; }
.pile.vers-gauche .carton + .carton { margin-right: -22px; }
.boite-encheres { background: #c0392b; border-radius: 12px; padding: 8px; }
.ratelier { background: #f4f5f6; border-radius: 6px; padding: 6px; display: flex; flex-direction: column; gap: 4px; }
.tirette { width: 40px; height: 26px; display: flex; align-items: center; justify-content: center; border-radius: 4px;
  font-size: 14px; font-weight: 700; border: 1px solid rgba(0,0,0,.18); cursor: pointer; }
.tirette:hover { filter: brightness(.93); transform: translateY(-2px); }
.tirette.vide { visibility: hidden; }
.tirette.autres { width: auto; color: #555; background: #fff; font-weight: 500; font-size: 13px; }
.compartiment { margin-top: 8px; background: #a93226; border-radius: 6px; padding: 6px 6px 4px; justify-content: center; }
.onglet { min-width: 44px; padding: 4px 8px; border-radius: 6px 6px 2px 2px; font-size: 14px; font-weight: 700; color: #fff;
  text-align: center; cursor: pointer; }
.onglet.passe { background: #2e7d32; } .onglet.contre { background: #e53935; } .onglet.surcontre { background: #1565c0; }
.onglet.eteint { cursor: default; }
@keyframes pense { 50% { opacity: .35; } }
.pense { animation: pense 1s ease-in-out infinite; }
"""


CSS_AIDE = """
.aide { font-size: 16px; line-height: 1.55; color: #222; }
.aide h1, .aide h2, .aide h3 { font-size: 16px; font-weight: 700; color: #1f6b45; margin: 1.4em 0 .4em; }
.aide p, .aide ul, .aide ol, .aide dl { margin: .6em 0; }
.aide ul { list-style: disc; padding-left: 1.4em; } .aide ol { list-style: decimal; padding-left: 1.4em; }
.aide li { margin-bottom: .4em; } .aide dt { font-weight: 600; margin-top: .7em; } .aide dd { margin: 0; }
.aide code { background: #e6efe9; padding: .1em .35em; border-radius: 4px; font-size: 15px; word-break: break-all; }
.aide .note { background: #e6efe9; border-left: 4px solid #1f6b45; padding: .7em 1em; margin: 1em 0; }
"""


def texte_aide():
    """Le corps de help/index.html, affiché dans la fenêtre ; son propre style est remplacé par CSS_AIDE."""
    try:
        t = open(AIDE, encoding="utf-8").read()
    except OSError:
        return "<p>Le fichier d'aide est introuvable.</p>"
    return re.search(r"<body>(.*)</body>", t, re.S)[1] if "<body>" in t else t


def sections_aide():
    """L'aide découpée en sections, une par titre <h2> : [(titre, html)] ; la première, l'introduction, s'appelle
    « Présentation »."""
    out = []
    for k, p in enumerate(re.split(r"(?=<h2>)", texte_aide())):
        if not p.strip(): continue
        m = re.search(r"<h2>(.*?)</h2>", p, re.S)
        out.append((re.sub(r"<[^>]+>", "", m[1]).strip() if m else "Présentation", p))
    return out


def ouvrir(chemin):
    """Ouvre un PDF, un dossier ou la page d'aide avec le programme habituel de l'ordinateur."""
    if sys.platform == "win32": os.startfile(chemin)
    else: subprocess.Popen(["open", chemin])


def ouvrir_reglages():
    """Les réglages, dans l'éditeur de texte de l'ordinateur."""
    if sys.platform == "win32": os.startfile(rapport.CONFIG)
    else: subprocess.Popen(["open", "-t", rapport.CONFIG])


def creation(f):
    """La date de création du fichier ; un Mac la donne à part, sous Windows c'est st_ctime."""
    st = os.stat(f)
    return getattr(st, "st_birthtime", st.st_ctime)


def demarrer_travail(t, args):
    env = dict(os.environ)                                 # -X utf8 : Windows n'écrit pas en UTF-8 par défaut
    opts = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == "win32" else {"start_new_session": True}
    t.proc = subprocess.Popen([sys.executable, "-I", "-X", "utf8", "-u"] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8",
                              errors="replace", env=env, cwd=rapport.RACINE, **opts)
    threading.Thread(target=suivre, args=(t.proc, t), daemon=True).start()


def lancer(chemin, noms):
    T.__init__(); T.seance = chemin; T.texte = "Lecture du fichier"
    demarrer_travail(T, [os.path.join(ICI, "rapport.py"), chemin] + (["--avec-noms"] if noms else []))


def lancer_rapports(chemin, noms):
    """Les PDF seulement, depuis les analyses enregistrées (rapport.py --rapports) : la barre avance rapport par rapport."""
    T.__init__(0.0, "Écriture des rapports"); T.seance = chemin; T.texte = "Écriture des rapports"
    demarrer_travail(T, [os.path.join(ICI, "rapport.py"), chemin, "--rapports"] + (["--avec-noms"] if noms else []))


def lancer_import(chemin):
    I.__init__(1.0, "Import"); I.seance = chemin; I.texte = f"Import de {os.path.basename(chemin)}"
    demarrer_travail(I, [os.path.join(ICI, "rapport.py"), chemin, "--importer"])


def seances_bc():
    """Les séances Bridge Coach (.bc.json), les plus récentes d'abord : date de la séance, puis création du fichier."""
    def cle(c):
        j, m, a = (infos_seance(c)[0].split("/") + ["", "", ""])[:3]
        return (a + m + j, creation(c))
    return sorted(rapport.glob_seances("*" + rapport.BC), key=cle, reverse=True)


_INFOS = {}


def infos_seance(c):
    """(date de la séance « JJ/MM/AAAA », sa source en clair) d'un .bc.json, lus une fois par version du fichier."""
    try:
        cle = (c, os.path.getmtime(c))
        if cle not in _INFOS:
            d = json.load(open(c, encoding="utf-8"))
            _INFOS[cle] = (d["session"]["date"], SOURCES.get(d.get("source", {}).get("type"), ""))
        return _INFOS[cle]
    except Exception:
        return date_lisible(c), ""


def deja_importe(bws):
    """Le .bc.json de ce fichier, s'il a déjà été importé ; sinon None."""
    nom = rapport.nom_seance(bws)
    return next((c for c in rapport.glob_seances(nom + rapport.BC)), None)


def exporter_pbn(chemin):
    """Le .pbn de la séance, à côté de son .bc.json ; renvoie son chemin."""
    data = json.load(open(chemin, encoding="utf-8"))
    base = chemin[:-len(rapport.BC)] if chemin.endswith(rapport.BC) else os.path.splitext(chemin)[0]
    with open(base + ".pbn", "w", encoding="utf-8") as f: f.write(donnes.pbn(data))
    return base + ".pbn"


ETAT = os.path.join(os.path.dirname(rapport.CONFIG), "etat.json")   # ce que l'application retient d'une fois sur l'autre


def lire_etat():
    try:
        x = json.load(open(ETAT, encoding="utf-8"))
        return x if isinstance(x, dict) else {}
    except Exception:
        return {}


def ecrire_etat(**valeurs):
    """Ajoute ou change des valeurs dans etat.json, sans toucher aux autres."""
    try:
        x = lire_etat(); x.update(valeurs)
        os.makedirs(os.path.dirname(ETAT), exist_ok=True)
        with open(ETAT, "w", encoding="utf-8") as f: json.dump(x, f, ensure_ascii=False)
    except OSError:
        pass


def seance_active():
    """La séance ouverte la dernière fois, si son fichier existe encore ; sinon None."""
    c = lire_etat().get("seance")
    return c if c and os.path.isfile(c) else None


def retenir(c):
    """La séance ouverte devient celle qu'on retrouve au prochain lancement."""
    ecrire_etat(seance=c)


def place_jouer():
    """L'option de l'onglet Jouer : la place que prend le joueur (jouer.PLACES), le déclarant par défaut."""
    m = lire_etat().get("place_jouer")
    return m if m in dict(jouer.PLACES) else "declarant"


def titre_fenetre(c):
    """« Bridge Coach – 1234567MULTI23102026S.bc.json » ; sans séance, le nom du programme."""
    return f"{TITRE} – {os.path.basename(c)}" if c else TITRE


def lancer_donnes(quotas):
    """quotas : [(thème, nombre de donnes)]."""
    D.__init__(1.0, "Création de la donne"); D.texte = "Préparation"
    demarrer_travail(D, [os.path.join(ICI, "donnes.py")] + [f"{t}={k}" for t, k in quotas if k])


def entrainements():
    """Les derniers fichiers de donnes créés."""
    x = rapport.glob_seances("entrainement-*" + rapport.BC)
    return sorted(x, reverse=True)[:5]


def suivre(proc, t):
    """Lit les lignes de rapport.py jusqu'à la fin ; les messages d'erreur à part."""
    erreurs = []
    fil = threading.Thread(target=lambda: erreurs.extend(proc.stderr), daemon=True); fil.start()
    for ligne in proc.stdout: lire_ligne(t, ligne)
    proc.wait(); fil.join(5)
    texte = "".join(erreurs)
    if proc.returncode and not t.annule:
        t.erreur = message_erreur(texte)
        os.makedirs(rapport.RAPPORTS, exist_ok=True)
        with open(os.path.join(rapport.RAPPORTS, "derniere-erreur.txt"), "w", encoding="utf-8") as f: f.write(texte)
    t.fini = True


def annuler(t=T):
    """Arrête le travail et ses processus de calcul."""
    if not t.actif: return
    t.annule = True
    if sys.platform == "win32": subprocess.run(["taskkill", "/F", "/T", "/PID", str(t.proc.pid)], capture_output=True)
    else: os.killpg(t.proc.pid, signal.SIGTERM)


def reglages():
    """(les séances trouvées, le dossier regardé). Pas de dossier : une liste vide, dite à l'écran."""
    rapport.preparer_donnees()
    d = rapport.dossier_configure()
    if not os.path.isdir(d): return [], d
    seances = {}                                           # un même fichier rangé deux fois ne compte qu'une fois
    for f in sorted(rapport.seances_du_dossier(d), key=creation, reverse=True): seances.setdefault(os.path.basename(f).lower(), f)
    return list(seances.values()), d


# ---------------------------------------------------------------- la séance ouverte, dans l'onglet Donnes
SIEGE = {"N": "Nord", "E": "Est", "S": "Sud", "O": "Ouest"}
_SEANCE = {}


def lire_seance(c):
    """Le contenu d'un fichier Bridge Coach (relu s'il a changé), ou None."""
    if not c or not (c.endswith(rapport.BC) or c.endswith(rapport.ANCIEN)) or not os.path.isfile(c): return None
    try:
        cle = (c, os.path.getmtime(c))
        if cle not in _SEANCE: _SEANCE.clear(); _SEANCE[cle] = json.load(open(c, encoding="utf-8"))
        return _SEANCE[cle]
    except Exception:
        return None


def rouge(t):
    """Cœurs et carreaux en rouge, pour le HTML."""
    return str(t).replace("♥", '<span style="color:#c0141c">♥</span>').replace("♦", '<span style="color:#c0141c">♦</span>')


def page_seance(data, c):
    s = data["session"]; src = data.get("source", {})
    ui.label(s.get("titre") or f"Séance du {s['date']}").classes("text-lg font-bold")
    lignes = [("Source", " – ".join(x for x in (SOURCES.get(src.get("type"), src.get("type", "")), src.get("fichier", "")) if x)),
              ("Importée le", (src.get("importe") or "").replace("T", " à ")),
              ("Donnes", str(len(data["donnes"]))),
              ("Tables", str(s.get("tables") or "aucune : donnes non jouées")),
              ("Sections", ", ".join(s.get("sections") or [])),
              ("Mouvement", "Mitchell" if s.get("mitchell") else "Howell ou tables fixes" if s.get("tables") else ""),
              ("Thèmes", ", ".join(s.get("themes") or [])),
              ("Fichier", c)]
    with ui.grid(columns="auto 1fr").classes("gap-x-6 gap-y-1 text-base"):
        for k, v in lignes:
            if v:
                ui.label(k).classes("text-gray-600"); ui.label(v).classes("break-all")


def page_joueurs(data):
    ui.label("Joueurs").classes("text-lg font-bold")
    j = data.get("joueurs") or {}
    if not j:
        ui.label("Pas de joueurs dans cette séance : les donnes n'ont pas été jouées.").classes("text-base text-gray-600"); return
    cle = lambda k: (len(re.sub(r"\D", "", k)), k)        # 2 avant 10
    rows = [{"paire": k, "initiales": "/".join(x.get("initiales", "") for x in v),
             "noms": " – ".join(x.get("nom", "") for x in v if x.get("nom")) or "—"} for k, v in sorted(j.items(), key=lambda x: cle(x[0]))]
    ui.table(columns=[{"name": "paire", "label": "Paire", "field": "paire", "align": "left"},
                      {"name": "initiales", "label": "Initiales", "field": "initiales", "align": "left"},
                      {"name": "noms", "label": "Noms", "field": "noms", "align": "left"}],
             rows=rows, row_key="paire").props("flat dense").classes("w-full")


def page_alertes(data):
    ui.label("Alertes de l'import").classes("text-lg font-bold")
    for a in data.get("alertes") or []: ui.label(a).classes("text-base")


def main_html(d, s):
    """Une main : le siège et ses points, puis une ligne par couleur."""
    cartes = d["mains"][s].split()
    lignes = "".join(f"<div>{rouge(c)}&nbsp;{'—' if x == '-' else x}</div>" for c, x in zip("♠♥♦♣", cartes))
    don = " · donneur" if d["donneur"] == s else ""
    return f'<div style="font-size:15px;line-height:1.35"><div style="color:#555;font-weight:600">{SIEGE[s]} · {d["hcp"][s]} H{don}</div>{lignes}</div>'


def mains_grille(d):
    """Les quatre mains autour de la table."""
    with ui.grid(columns="repeat(3, 150px)").classes("gap-2 items-center"):
        ui.label(""); ui.html(main_html(d, "N"), sanitize=False); ui.label("")
        ui.html(main_html(d, "O"), sanitize=False); ui.label(""); ui.html(main_html(d, "E"), sanitize=False)
        ui.label(""); ui.html(main_html(d, "S"), sanitize=False); ui.label("")


def par_html(d):
    p = d.get("par")
    return "" if not p else (f"<b>Par</b> : {rouge(p['contrat'])}{'X' if p.get('contre') else ''} "
                             f"{SIEGE.get(p['declarant'], p['declarant'])} {p.get('resultat', '')}, {p['score_ns']:+d} pour Nord-Sud")


def dm_html(d):
    """Le double mort en petit tableau, pour la barre de droite : levées par dénomination et par déclarant."""
    if not d.get("dm"): return ""
    tete = "".join(f"<th style='padding:1px 6px;text-align:center'>{s}</th>" for s in "NSEO")
    corps = "".join(f"<tr><td style='padding:1px 6px;font-weight:600'>{rouge(x)}</td>" +
                    "".join(f"<td style='padding:1px 6px;text-align:center'>{d['dm'][x][s]}</td>" for s in "NSEO") + "</tr>"
                    for x in ("SA", "♠", "♥", "♦", "♣"))
    return (f"<div style='font-size:15px'><div style='font-weight:700;margin-bottom:2px'>Double mort</div>"
            f"<table style='border-collapse:collapse;background:#fff;border-radius:8px'><tr><th></th>{tete}</tr>{corps}</table></div>")


def page_dm_par(d, par=True):
    """Le double mort et le par d'une donne complète."""
    if d.get("dm"):
        ui.label("Double mort : levées par déclarant").classes("text-base font-bold mt-2")
        tete = "".join(f"<th style='padding:2px 10px'>{SIEGE[s]}</th>" for s in "NSEO")
        corps = "".join(f"<tr><td style='padding:2px 10px;font-weight:600'>{rouge(x)}</td>" +
                        "".join(f"<td style='padding:2px 10px;text-align:center'>{d['dm'][x][s]}</td>" for s in "NSEO") + "</tr>"
                        for x in ("SA", "♠", "♥", "♦", "♣"))
        ui.html(sanitize=False, content=f"<table style='font-size:15px;border-collapse:collapse'><tr><th></th>{tete}</tr>{corps}</table>")
    if par and d.get("par"):
        ui.html(sanitize=False, content=f"<div style='font-size:15px'>{par_html(d)}</div>")


def page_donne(d):
    """Une donne dans l'onglet Donnes : les mains et les tables ; le nom, le donneur, la vulnérabilité et le par sont
    dans la barre de droite. Le double mort est dans l'onglet Analyse."""
    mains_grille(d)
    if d.get("tables"):
        ui.label("Aux tables").classes("text-base font-bold mt-2")
        rows = [{"k": str(i), "table": str(x.get("table", "")), "ns": x.get("nom_ns") or x.get("paire_ns", ""),
                 "eo": x.get("nom_eo") or x.get("paire_eo", ""), "contrat": x.get("contrat", ""),
                 "decl": SIEGE.get(x.get("declarant"), x.get("declarant") or ""), "res": x.get("resultat", ""),
                 "entame": x.get("entame") or "", "score": f"{x['score_ns']:+d}" if isinstance(x.get("score_ns"), int) else ""}
                for i, x in enumerate(d["tables"])]
        cols = [("table", "Table"), ("ns", "Nord-Sud"), ("eo", "Est-Ouest"), ("contrat", "Contrat"), ("decl", "Déclarant"),
                ("res", "Résultat"), ("entame", "Entame"), ("score", "Score N-S")]
        ui.table(columns=[{"name": k, "label": l, "field": k, "align": "left"} for k, l in cols], rows=rows, row_key="k") \
            .props("flat dense").classes("w-full")
        if any(x.get("encheres") for x in d["tables"]):
            ui.label("Les enchères aux tables").classes("text-base font-bold mt-2")
            with ui.row().classes("gap-6 items-start"):
                for x in d["tables"]:
                    if x.get("encheres"): ui.html(encheres_html(d, x), sanitize=False)


# ---------------------------------------------------------------- l'analyse, dans l'onglet Analyse
_ANALYSES = {}


def base_seance(c):
    """Le chemin d'une séance sans son extension : <dossier>/<nom>."""
    return c[:-len(rapport.BC)] if c.endswith(rapport.BC) else c[:-len(rapport.ANCIEN)] if c.endswith(rapport.ANCIEN) else c


def lire_analyses(c):
    """(analyse du programme, analyse de l'expert) de la séance : les fichiers -standard.json et -expert.json, ou None."""
    base = base_seance(c); out = []
    for suite in ("-standard.json", "-expert.json"):
        f = base + suite
        try:
            cle = (f, os.path.getmtime(f))
            if cle not in _ANALYSES: _ANALYSES[cle] = json.load(open(f, encoding="utf-8"))
            out.append(_ANALYSES[cle])
        except (OSError, ValueError):
            out.append(None)
    return tuple(out)


def quand(f):
    """« 02/11/2026 à 20:49 » : la date du fichier."""
    return datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime("%d/%m/%Y à %H:%M")


def lien_pdf(f, nom, detail):
    """Un rapport : son nom comme un lien qui l'ouvre, ce qu'il contient, le fichier et sa date."""
    with ui.column().classes("gap-0"):
        ui.label(nom).classes("text-base text-primary underline cursor-pointer").on("click", lambda f=f: ouvrir(f))
        ui.html(f"<div class='text-sm text-gray-600'>{detail} · <span style='word-break:break-all'>{os.path.basename(f)}</span> · "
                f"<span style='white-space:nowrap'>{quand(f)}</span></div>", sanitize=False)


def page_analyse_resume(data, an, fichier, expert):
    """La page « Analyse standard » ou « Analyse expert » : ce qui existe, sur combien de donnes, et de quand."""
    n = len(data["donnes"])
    k = sum(1 for x in (an or {}).get("donnes", {}).values() if x.get("enc"))
    if expert:
        lignes = [("État", f"{k} donnes sur {n} ; elle l'emporte sur l'analyse standard, donne par donne" if an
                   else "aucune analyse de l'expert pour cette séance")]
    else:
        lignes = [("État", f"{k} donnes sur {n}" if an else "pas encore faite : « Lancer l'analyse »")]
    if an:
        lignes += [("Faite le", quand(fichier)), ("Système", an.get("systeme", "sef-2024")), ("Fichier", os.path.basename(fichier))]
    with ui.grid(columns="auto 1fr").classes("gap-x-6 gap-y-1 text-base"):
        for a, b in lignes:
            ui.label(a).classes("text-gray-600"); ui.label(b).classes("break-all")
    if expert:
        ui.label("L'analyse de l'expert est rédigée par Claude, d'après les règles du projet ; le programme ne la modifie "
                 "jamais.").classes("text-sm text-gray-600")
    else:
        ui.label("« Lancer l'analyse » refait l'analyse standard et les rapports PDF (onglet Rapports).").classes("text-sm text-gray-600")


# ---------------------------------------------------------------- l'analyse de l'expert, demandée à Claude sur le web
POUR_CLAUDE = [("systems/sef-2024/systeme.md", "systeme.md"), ("systems/sef-2024/conventions.md", "conventions.md"),
               ("systems/conventions/blackwood-3041.md", "blackwood-3041.md"), ("systems/conventions/stayman.md", "stayman.md"),
               ("systems/conventions/texas.md", "texas.md"), ("systems/conventions/drury.md", "drury.md"),
               ("systems/sef-2024/entames.md", "entames.md"),
               ("systems/sef-2024/entames.yaml", "entames.yaml"), ("systems/technique/jeu-de-la-carte.md", "jeu-de-la-carte.md")]

CONSIGNE = """Tu es l'expert de Bridge Coach, un programme qui analyse les séances de bridge d'un club français.
Écris l'analyse experte de la séance jointe, {nom}.bc.json, et rends-la dans un seul fichier JSON à télécharger,
nommé {nom}-expert.json. Réponds en français.

Les fichiers joints :
- {nom}.bc.json : la séance (mains, donneur, vulnérabilité, résultats et enchères de chaque table, double mort « dm », par) ;
- {nom}-standard.json : l'analyse du programme, ton point de départ (même format que celui à rendre) ;
- exemple_analyse.json : une analyse experte complète d'une autre séance, le style et le niveau de détail attendus ;
- systeme.md et les conventions (blackwood-3041.md, stayman.md, texas.md, drury.md) : le système SEF 2024 joué ;
- entames.md et entames.yaml : les règles d'entame et de défense ; jeu-de-la-carte.md : la technique du déclarant.

Les règles, à suivre strictement :
1. Les enchères recommandées (« enc ») se choisissent à la table : chaque enchère d'après la main du joueur et les
   enchères précédentes seulement, comme un joueur à la table. Ne regarde ni les autres mains, ni le double mort
   (« dm »), ni le par, ni les résultats des tables. Ne choisis jamais entre deux enchères raisonnables parce que
   l'une réussit au double mort. Quand deux enchères se défendaient, « notes » le dit dans une phrase qui commence
   par « Décision serrée : », avec l'autre enchère et pourquoi celle choisie est préférée.
2. Le système est celui de systeme.md. Une ligne marquée « (à confirmer) » ne s'emploie qu'en disant que le
   traitement est incertain.
3. L'entame et la défense (« entame », « defense ») viennent de la main de l'entameur et des enchères seulement,
   d'après entames.yaml et entames.md : jamais d'une simulation au double mort.
4. Le plan de jeu (« plan ») ne voit que les mains du déclarant et du mort, l'entame et les enchères.
5. Dans « plan » et « defense », garde le texte du programme (le {nom}-standard.json) puis ajoute
   <br/><b>Avis de l'expert :</b> et trois ou quatre phrases de jugement que le programme n'a pas : pourquoi le plan
   marche, la main dangereuse, l'ordre de jeu ; cherche un laisser-passer, une élimination, un squeeze ou un coup.
6. « notes » : l'avis de l'expert sur les enchères. « comm » : le commentaire après coup ; le double mort y est
   permis, pour dire ce que le contrat donne et ce qui aurait marché.
7. Les joueurs : par leurs initiales seulement (« AB/CD »), jamais leur nom ; aucun nom de club. Les cartes en
   français : A R D V X ; les couleurs ♠ ♥ ♦ ♣ ; les sièges N, S, E, O.

Le format du fichier rendu (celui de exemple_analyse.json) :
{{"titre_pied": "Analyse des donnes – séance du {date} – Système SEF, marque IMP",
 "systeme": "sef-2024",
 "note_encheres": "Enchères recommandées choisies à la table (sans double mort).",
 "donnes": {{"1": {{"enc": [["–", "1♠", "passe", "2♦"], ["passe", "…", "…", "…"]],
                   "notes": "…", "entame": {{"joueur": "E", "carte": "♣R"}}, "defense": "…", "plan": "…", "comm": "…"}},
            "2": {{…}}}}}}
« enc » : la grille Ouest, Nord, Est, Sud, une ligne de quatre par tour, « – » avant le donneur, « passe »,
« contre », « surcontre », « 1SA »… ; « entame.joueur » : N, E, S ou O. Une clé par donne, toutes les donnes.
L'entame part toujours du joueur à gauche du déclarant de « enc » (le premier de son camp à avoir nommé la dénomination
du contrat), et sa carte est dans la main de ce joueur : vérifie-le pour chaque donne, l'import refuse sinon.

Si la réponse est trop longue pour un seul message, fais les donnes par groupes (par exemple 1 à 8, puis 9 à 16…),
chaque groupe dans un fichier JSON complet au même format : ils s'importent l'un après l'autre.
"""


def preparer_pour_claude(c):
    """Le dossier pour-claude/<nom>/ du dossier de travail : la séance, l'analyse du programme, le système, l'exemple et
    la consigne (CONSIGNE.txt). Renvoie (dossier, consigne)."""
    nom = rapport.nom_seance(c); base = base_seance(c)
    dossier = os.path.join(rapport.DONNEES, "pour-claude", nom)
    shutil.rmtree(dossier, ignore_errors=True); os.makedirs(dossier)
    shutil.copy(c, os.path.join(dossier, nom + rapport.BC))
    if os.path.exists(base + "-standard.json"): shutil.copy(base + "-standard.json", os.path.join(dossier, nom + "-standard.json"))
    for src, dst in POUR_CLAUDE:
        f = os.path.join(rapport.RACINE, src)
        if os.path.exists(f): shutil.copy(f, os.path.join(dossier, dst))
    ex = os.path.join(rapport.DONNEES, "documents", "exemple_analyse_2026-10-23.json")
    if os.path.exists(ex): shutil.copy(ex, os.path.join(dossier, "exemple_analyse.json"))
    date = (lire_seance(c) or {}).get("session", {}).get("date", "")
    consigne = CONSIGNE.format(nom=nom, date=date)
    with open(os.path.join(dossier, "CONSIGNE.txt"), "w", encoding="utf-8") as f: f.write(consigne)
    return dossier, consigne


def importer_expert(c, chemin):
    """Range l'analyse de l'expert rendue par Claude : vérifiée, fondue donne par donne dans <nom>-expert.json (l'ancienne
    version est gardée, datée). Renvoie le message à montrer ; ValueError avec un message en français si elle ne va pas."""
    try:
        neuf = json.load(open(chemin, encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError("Ce fichier n'est pas un fichier JSON lisible.")
    donnes_ = neuf.get("donnes") if isinstance(neuf, dict) else None
    if not isinstance(donnes_, dict) or not donnes_:
        raise ValueError("Ce fichier ne contient pas d'analyse de donnes (il manque « donnes »).")
    seance = {str(d["n"]): d for d in (lire_seance(c) or {}).get("donnes", [])}
    nums = set(seance)
    from comparer import final
    for k, a in donnes_.items():
        if k not in nums: raise ValueError(f"La donne {k} n'est pas dans cette séance : est-ce la bonne séance ?")
        enc = a.get("enc") if isinstance(a, dict) else None
        if not (isinstance(enc, list) and enc and all(isinstance(r, list) and len(r) == 4 for r in enc)):
            raise ValueError(f"Donne {k} : les enchères (« enc ») ne sont pas une grille de quatre colonnes.")
        e = a.get("entame")
        contrat, decl, _ = final(enc, seance[k].get("donneur", "N")) if isinstance(e, dict) else ("passe", None, 0)
        if contrat != "passe":                             # l'entame part de la gauche du déclarant, avec une carte de sa main
            bon = rapport.LHO[decl]
            if e.get("joueur") != bon or not rapport.entame_valide(seance[k], decl, e.get("carte", "")):
                raise ValueError(f"Donne {k} : d'après les enchères, {contrat} est joué par {SIEGE[decl]} et c'est "
                                 f"{SIEGE[bon]} qui entame, avec une carte de sa main ; l'analyse donne l'entame "
                                 f"{e.get('carte')} à {SIEGE.get(e.get('joueur'), e.get('joueur'))}. Demandez à Claude de corriger cette donne.")
    cible = base_seance(c) + "-expert.json"
    ancien = {}
    if os.path.exists(cible):
        ancien = json.load(open(cible, encoding="utf-8"))
        shutil.copy(cible, base_seance(c) + f"-expert-avant-{datetime.datetime.now().strftime('%Y-%m-%d-%H%M%S')}.json")
    fusion = dict(ancien, **{k: v for k, v in neuf.items() if k != "donnes"})
    fusion["donnes"] = dict(ancien.get("donnes", {}), **donnes_)
    fusion.setdefault("systeme", "sef-2024")
    with open(cible, "w", encoding="utf-8") as f: json.dump(fusion, f, ensure_ascii=False, indent=1)
    return (f"{len(donnes_)} donne{'s' if len(donnes_) > 1 else ''} importée{'s' if len(donnes_) > 1 else ''} ; l'analyse de "
            f"l'expert couvre maintenant {len(fusion['donnes'])} donnes sur {len(nums)}.")


def grille_html(enc, vul=None):
    """Une grille d'enchères Ouest Nord Est Sud (lignes du -standard.json ou du -expert.json). vul : la vulnérabilité de
    la donne ; chaque place est alors soulignée d'un trait épais, rouge si vulnérable, vert sinon."""
    trait = lambda s: "" if vul is None else \
        f";width:25%;border-bottom:6px solid {'#c0141c' if vul == 'Tous' or vul == ('N-S' if s in 'NS' else 'E-O') else '#2e7d32'}"
    tete = "".join(f"<th style='padding:2px 10px;text-align:center{trait(s)}'>{SIEGE[s]}</th>" for s in "ONES")
    corps = "".join("<tr>" + "".join(f"<td style='padding:1px 10px;text-align:center'>{rouge(c)}</td>" for c in r) + "</tr>" for r in enc)
    large = "" if vul is None else ";width:100%;table-layout:fixed"          # quatre colonnes égales
    return f"<table style='border-collapse:collapse;font-size:15px{large}'><tr>{tete}</tr>{corps}</table>"


def page_analyse(d, a, repli, version):
    """L'analyse d'une donne : enchères recommandées, entame et défense, plan de jeu, commentaire, cartes vues."""
    from build_pdf import txt                              # sièges en toutes lettres, cœurs et carreaux en rouge
    texte = lambda x: ui.html(f"<div style='font-size:15px;line-height:1.5'>{txt(x)}</div>", sanitize=False)
    mains_grille(d)                                        # le nom de la donne et la version sont dans la barre de droite
    ui.label("Enchères recommandées").classes("text-base font-bold mt-2")
    ui.html(grille_html(a["enc"]), sanitize=False)
    if a.get("notes"): texte(a["notes"])
    e = a.get("entame")
    if isinstance(e, dict) and e.get("carte"):
        ui.label("Entame et défense").classes("text-base font-bold mt-2")
        texte(f"<b>{SIEGE.get(e.get('joueur'), e.get('joueur', ''))}</b> entame {e['carte']}." + (f"<br/>{a['defense']}" if a.get("defense") else ""))
    if a.get("plan"):
        ui.label("Plan de jeu").classes("text-base font-bold mt-2"); texte(a["plan"])
    comm = a.get("comm") or repli.get("comm")
    if comm:
        ui.label("Commentaire").classes("text-base font-bold mt-2"); texte(comm)
    vues = a.get("vues") or repli.get("vues")
    if vues:
        ui.label("Cartes vues").classes("text-base font-bold mt-2"); texte(vues)


def encheres_html(d, x):
    """Les enchères d'une table, en grille Ouest Nord Est Sud à partir du donneur, avec le contrat et l'entame."""
    k = "ONES".index(d["donneur"])
    cases = ["–"] * k + list(x["encheres"])
    cases += [""] * (-len(cases) % 4)
    tete = "".join(f"<th style='padding:2px 10px;text-align:center'>{SIEGE[s]}</th>" for s in "ONES")
    corps = "".join("<tr>" + "".join(f"<td style='padding:1px 10px;text-align:center'>{rouge(c)}</td>" for c in cases[i:i + 4]) + "</tr>"
                    for i in range(0, len(cases), 4))
    titre = f"Table {x.get('table', '')} · {x.get('nom_ns') or x.get('paire_ns', '')} – {x.get('nom_eo') or x.get('paire_eo', '')}"
    fin = f"{rouge(x.get('contrat', ''))} {SIEGE.get(x.get('declarant'), '')} {x.get('resultat', '')}" + \
          (f", entame {rouge(x['entame'])}" if x.get("entame") else "")
    avis = "" if x.get("encheres_ok", True) else f"<div style='color:#c0141c'>{x.get('encheres_msg', '')}</div>"
    return (f"<div style='font-size:15px'><div style='font-weight:600'>{titre}</div>"
            f"<table style='border-collapse:collapse;margin:2px 0'><tr>{tete}</tr>{corps}</table><div>{fin}</div>{avis}</div>")


@ui.page("/")
def page():
    ui.colors(primary="#1f6b45")
    ui.add_css("body, .q-layout, .q-page, .q-page-container, .q-tab-panels, .q-tab-panel { background: #fff; } "   # une page toute blanche
               "body { font-size: 16px; } .q-btn { text-transform: none; }" + CSS_AIDE + CSS_CARTES)
    ui.add_head_html(JS_AJUSTE)
    seances, dossier = reglages()
    deja = seances_bc()
    choix = {"chemin": T.seance or seance_active() or (deja[0] if deja else None)}
    ui.page_title(titre_fenetre(choix["chemin"]))
    vue = {"entree": "seance"}                             # l'entrée choisie dans la barre latérale de l'onglet Donnes

    @ui.refreshable
    def vue_seance():
        c = choix["chemin"]; data = lire_seance(c)
        if not data:
            with ui.column().classes("w-full max-w-xl mx-auto"):
                ui.label("Aucune séance ouverte.").classes("text-base")
                ui.label("Fichier, Ouvrir une séance… pour en ouvrir une ; Fichier, Nouveau… pour créer des donnes.").classes("text-base text-gray-600")
            return
        if vue["entree"] not in dict(entrees_de(data)): vue["entree"] = "seance"
        with ui.column().classes("w-full gap-3 min-w-0"):
            e = vue["entree"]
            ok, _ = edition.modifiable(c)
            if e == "seance":
                page_seance(data, c)
                if data.get("alertes"): page_alertes(data)
                if ok: page_versions(c)
            elif e == "joueurs": page_joueurs(data)
            elif e == "alertes": page_alertes(data)
            else:
                d = next(d for d in data["donnes"] if f"d{d['n']}" == e)
                if ok and (d.get("a_completer") or vue.get("edition") == d["n"]):
                    editeur_donne(c, d)                    # une donne à compléter s'ouvre déjà en modification
                else:
                    with ui.column().classes("w-full gap-3").style(f"padding-right:{LARGEUR_PANNEAU}px"):
                        page_donne(d)
                    with panneau_droit(d):
                        if ok: ui.button("Modifier la donne", icon="edit", on_click=lambda n=d["n"]: modifier(c, n)).props("outline").classes("w-full")

    @ui.refreshable
    def vue_analyse():
        c = choix["chemin"]; data = lire_seance(c)
        if not data: return
        std, exp = lire_analyses(c)
        e = entree_effective(data)
        if e == "standard":
            ui.label(f"Analyse standard · séance du {data['session']['date']}").classes("text-lg font-bold")
            page_analyse_resume(data, std, base_seance(c) + "-standard.json", False); return
        if e == "expert":
            ui.label(f"Analyse expert · séance du {data['session']['date']}").classes("text-lg font-bold")
            page_analyse_resume(data, exp, base_seance(c) + "-expert.json", True)
            etapes_expert(c); return
        d = next((x for x in data["donnes"] if f"d{x['n']}" == e), None)
        if d is None: return
        n = str(d["n"])
        versions = [v for v, a in (("Standard", std), ("Expert", exp)) if a and (a.get("donnes") or {}).get(n, {}).get("enc")]
        if not versions:
            ui.label(f"Donne {d['n']}").classes("text-lg font-bold")
            ui.label("Pas encore d'analyse : « Analyse standard », puis « Lancer l'analyse ».").classes("text-base text-gray-600"); return
        if vue.get("version") not in versions: vue["version"] = "Expert" if "Expert" in versions else versions[0]
        a = (exp if vue["version"] == "Expert" else std)["donnes"][n]
        repli = (std or {}).get("donnes", {}).get(n, {})   # l'expert reprend du programme ce qu'il n'écrit pas (cartes vues…)
        with ui.column().classes("w-full gap-3").style(f"padding-right:{LARGEUR_PANNEAU}px"):
            page_analyse(d, a, repli, vue["version"])
        with panneau_droit(d, par=False):
            if len(versions) > 1:                           # Standard | Expert, deux moitiés égales
                ui.toggle(versions, value=vue["version"], on_change=lambda ev: (vue.update(version=ev.value), vue_analyse.refresh())) \
                    .props("no-caps spread toggle-color=primary").classes("w-full")
            else:
                ui.label(f"Analyse {vue['version'].lower()}").classes("text-base font-bold")
            c_, decl = jouer.contrat(jouer.sequence(a["enc"], d["donneur"]), d["donneur"])
            lignes = [f"<b>Contrat recommandé</b> : {rouge(c_) if decl else 'passe générale'}" + (f" {SIEGE[decl]}" if decl else "")]
            e_ = a.get("entame")
            if isinstance(e_, dict) and e_.get("carte"):
                lignes.append(f"<b>Entame</b> : {rouge(e_['carte'])} ({SIEGE.get(e_.get('joueur'), e_.get('joueur', ''))})")
            if d.get("par"): lignes.append(par_html(d))
            ui.html("<div style='font-size:15px;line-height:1.6'>" + "<br/>".join(lignes) + "</div>", sanitize=False)
            if d.get("dm"): ui.html(dm_html(d), sanitize=False)

    def panneau_droit(d=None, par=True):
        """La barre de droite d'une donne, la même dans Donnes, Jouer et Analyse : même largeur, même gris, le nom de la
        donne en haut ; avec d, l'étui (donneur, vulnérabilité), le thème et le par. Renvoie la colonne, à remplir."""
        col = ui.column().classes("gap-3 p-4 overflow-y-auto").style(
            f"position:fixed;top:{HAUTEUR_BARRE}px;right:0;bottom:0;width:{LARGEUR_PANNEAU}px;background:{GRIS_BARRE};"
            "border-left:1px solid #dcdcd8;z-index:1;overflow-x:hidden")
        if d is not None:
            with col:
                ui.label(f"Donne {d['n']}").classes("text-lg font-bold")
                with ui.row().classes("w-full justify-center"):
                    ui.html(etui(d, ("N", "O", "E", "S"), petit=True), sanitize=False)
                if d.get("theme"): ui.label(f"Thème : {d['theme']}").classes("text-sm text-gray-600")
                if par and d.get("par"): ui.html(f"<div style='font-size:15px'>{par_html(d)}</div>", sanitize=False)
        return col

    jeu = {"cle": None}                                   # la donne en cours dans l'onglet Jouer

    def siege_de(d, k):
        return jouer.ROT[(jouer.ROT.index(d["donneur"]) + k) % 4]

    def jeu_depart(c, d, siege=None):
        siege = siege or jouer.siege_choisi(place_jouer(), d, lire_analyses(c))   # l'option choisie dans Options
        seq, ex, ind = jouer.avancer(d, [], siege)
        jeu.update(cle=(c, d["n"]), siege=siege, seq=seq, ex=ex, indice=ind, voir_indice=False, garde=False, d=d,
                   affiche=0, revele=False, pense=None, partie=None, pli_vu=None, msg="", garde_jeu=False, sans_jouer=False)
        background_tasks.create(reveler())

    async def reveler():
        """Les enchères du programme apparaissent une à une, avec un temps de réflexion."""
        if jeu["revele"]: return
        jeu["revele"] = True
        try:
            while jeu["affiche"] < len(jeu["seq"]):
                if jeu["seq"][jeu["affiche"]] is not None and siege_de(jeu["d"], jeu["affiche"]) == jeu["siege"]:
                    jeu["affiche"] += 1; continue             # la vôtre : tout de suite
                jeu["pense"] = siege_de(jeu["d"], jeu["affiche"]); vue_jouer.refresh()
                await asyncio.sleep(0.9)
                jeu["affiche"] += 1; jeu["pense"] = None; vue_jouer.refresh()
        finally:
            jeu["revele"] = False

    async def jeu_annonce(d, b):
        if jeu["affiche"] < len(jeu["seq"]) or b not in jouer.legales(jeu["seq"], d["donneur"]): return
        seq, ex, ind = await run.io_bound(jouer.avancer, d, jeu["seq"] + [b], jeu["siege"])
        jeu.update(seq=seq, ex=ex, indice=ind, voir_indice=False, tout_voir=False, affiche=jeu["affiche"] + 1); vue_jouer.refresh()
        await reveler()

    def jeu_suivante(data, d):
        ns = [x["n"] for x in data["donnes"] if not x.get("a_completer")]
        k = ns.index(d["n"]); aller(f"d{ns[(k + 1) % len(ns)]}")

    COUL_BOITE = {"SA": "sa", "♠": "pique", "♥": "coeur", "♦": "carreau", "♣": "trefle"}   # les couleurs des cartons

    def boite_encheres(d):
        """Les enchères encore possibles, à partir du palier le plus bas, quatre paliers au plus ; le dernier bouton,
        « … », montre les autres. Les enchères dépassées ne s'affichent pas."""
        ok = jouer.legales(jeu["seq"], d["donneur"])
        niveaux = sorted({int(b[0]) for b in ok if b[0].isdigit()})
        tout = jeu.get("tout_voir") or len(niveaux) <= 4
        montres = niveaux if tout else niveaux[:4]
        with ui.element("div").classes("boite-encheres"):              # une boîte à enchères : les cartons debout, derrière
            with ui.element("div").classes("ratelier"):
                for n in montres:
                    with ui.row().classes("gap-1 no-wrap"):
                        for den in jouer.DENOMS:                  # ♣ ♦ ♥ ♠ SA : l'ordre des enchères
                            b = f"{n}{den}"
                            if b in ok:
                                ui.html(f"<div class='tirette {COUL_BOITE[den]}'>{n}{den}</div>", sanitize=False) \
                                    .on("click", lambda b=b: jeu_annonce(d, b))
                            else:
                                ui.html("<div class='tirette vide'></div>", sanitize=False)
                if not tout:
                    ui.html("<div class='tirette autres'>… les autres enchères</div>", sanitize=False) \
                        .on("click", lambda: (jeu.update(tout_voir=True), vue_jouer.refresh()))
            with ui.row().classes("gap-1 no-wrap compartiment"):         # devant : Passe, X, XX
                for b, nom in (("passe", "Passe"), ("contre", "X"), ("surcontre", "XX")):
                    el = ui.html(f"<div class='onglet {b}{'' if b in ok else ' eteint'}'>{nom}</div>", sanitize=False)
                    if b in ok: el.on("click", lambda b=b: jeu_annonce(d, b))
                ui.html("<div class='onglet indice' title='Ce que dirait le système'><span class='material-icons' "
                        "style='font-size:16px'>lightbulb</span>Indice</div>", sanitize=False) \
                    .on("click", lambda: (jeu.update(voir_indice=True), vue_jouer.refresh()))

    # ---------------------------------------------------------------- le jeu de la carte
    def carte_demarrer(d):
        c_, decl = jouer.contrat(jeu["seq"], d["donneur"])
        jeu.update(partie=carte.Partie(d, c_, decl, jeu["seq"]), pli_vu=None, msg="", garde_jeu=False)
        vue_jouer.refresh(); background_tasks.create(carte_defense())

    async def carte_poser(x):
        """Pose une carte ; si elle termine le pli, le pli reste un instant sous les yeux."""
        p = jeu["partie"]; avant = len(p.plis)
        p.poser(x); jeu["msg"] = ""
        if len(p.plis) > avant:
            jeu["pli_vu"] = p.plis[-1]; vue_jouer.refresh()
            await asyncio.sleep(1.3)
            jeu["pli_vu"] = None
        vue_jouer.refresh()

    async def carte_defense():
        """Les défenseurs jouent, chacun après un temps de réflexion, jusqu'au tour du déclarant ou du mort."""
        p = jeu["partie"]
        while p and not p.fini() and not p.camp(p.au_trait()) and jeu["partie"] is p:
            jeu["pense"] = p.au_trait(); vue_jouer.refresh()
            x, _ = await asyncio.gather(run.io_bound(p.carte_defense), asyncio.sleep(0.8))
            jeu["pense"] = None
            await carte_poser(x)

    async def carte_jouer(x):
        p = jeu["partie"]
        if not p or jeu["pense"] or jeu["pli_vu"] or p.fini() or x not in p.legales(): return
        await carte_poser(x)
        await carte_defense()

    async def carte_indice():
        p = jeu["partie"]
        if not p or p.fini(): return
        jeu["msg"] = "Le programme cherche…"; vue_jouer.refresh()
        x = await run.io_bound(p.indice)
        jeu["msg"] = f"Le programme jouerait {carte.carte_fr(*x)} ({SIEGE[p.au_trait()]})."; vue_jouer.refresh()

    async def carte_reclamer():
        p = jeu["partie"]
        if not p or p.fini(): return
        ok = await run.io_bound(p.reclamer)
        jeu["msg"] = "" if ok else "Pas encore : la défense peut faire au moins une levée de plus."
        vue_jouer.refresh()

    def plis_gardes(p, x, ou):
        """Les cartes du joueur x retournées devant lui sur la table, près de son bord, dans l'ordre, chacune en partie sur
        la précédente, comme en duplicate : vers son partenaire si son camp a gagné le pli, en travers sinon."""
        if not p.plis: return ""
        cote = ou in ("gauche", "droite")
        gagne = lambda g: p.camp(g) == p.camp(x)
        forme = lambda g: ("couche" if gagne(g) else "") if cote else ("" if gagne(g) else "couche")
        ici = {"bas": "bottom:12px;left:50%;transform:translateX(-50%)", "haut": "top:12px;left:50%;transform:translateX(-50%)",
               "gauche": "left:12px;top:50%;transform:translateY(-50%)", "droite": "right:12px;top:50%;transform:translateY(-50%)"}[ou]
        return (f"<div class='plis-gardes{' colonne' if cote else ''}' style='position:absolute;{ici}' "
                f"title='Vers le partenaire : pli gagné ; en travers : pli perdu'>"
                + "".join(f"<div class='dos {forme(g)}'></div>" for _, g in p.plis) + "</div>")

    def pli_html(p, places):
        """Le pli en cours, chaque carte devant le joueur qui l'a posée."""
        pli = jeu["pli_vu"][0] if jeu["pli_vu"] else p.pos.pli
        posees = {s: (c, r.translate(carte.FR)) for s, c, r in pli}
        D = 62                                         # chaque carte à la même distance du centre, donc de son bord
        def case(s, x, y):                             # la carte posée, comme dans les mains, au milieu de son côté
            if s not in posees: return ""
            c, r = posees[s]
            return (f"<div class='carte{' r' if c in '♥♦' else ''}' style='position:absolute;left:calc(50% + {x}px);"
                    f"top:calc(50% + {y}px);transform:translate(-50%,-50%);margin:0;z-index:3'>{face(r)}<br/>{c}</div>")
        haut, gauche, droite, bas = places
        return (f"<div style='position:absolute;inset:0;pointer-events:none'>"
                f"{case(haut, 0, -D)}{case(bas, 0, D)}{case(gauche, -D, 0)}{case(droite, D, 0)}"
                + "".join(plis_gardes(p, x, ou) for x, ou in zip(places, ("haut", "gauche", "droite", "bas"))
                          if x == jeu["siege"] or not p.camp(x)) + "</div>")   # l'étui est dans la barre de droite

    def etui(d, places, petit=False):
        """L'étui de la donne au centre, comme un vrai étui : Nord et Sud toujours sur les petits côtés (debout quand
        Nord-Sud sont en haut et en bas, couché sinon), leurs bandes sur toute la largeur, Est et Ouest entre elles ;
        chaque nom se lit depuis sa place, en capitales, blanc sur rouge si son camp est vulnérable, sur vert sinon ; le
        donneur écrit « Donneur » en rouge ou vert sur blanc ; le joueur qui réfléchit clignote."""
        v = d["vul"]; vul = lambda x: v == "Tous" or v == ("N-S" if x in "NS" else "E-O")
        l, L, h, f = (84, 149, 22, 12) if petit else ETUI      # l × L : l'étui (9:16), h : épaisseur des bandes
        haut, gauche, droite, bas = places
        debout = haut in "NS"
        W, H = (l, L) if debout else (L, l)
        if debout:                                            # grid-area : ligne, colonne, ligne de fin, colonne de fin
            place = {haut: "1 / 1 / 2 / 4", bas: "3 / 1 / 4 / 4", gauche: "2 / 1 / 3 / 2", droite: "2 / 3 / 3 / 4"}
        else:                                                 # Nord et Sud à gauche et à droite, Est-Ouest entre eux
            place = {gauche: "1 / 1 / 4 / 2", droite: "1 / 3 / 4 / 4", haut: "1 / 2 / 2 / 3", bas: "3 / 2 / 4 / 3"}
        def bande(x):
            teinte = "#c0141c" if vul(x) else "#2e7d32"
            if x == d["donneur"]:                             # le donneur : « Donneur » en couleur sur blanc
                nom, fond, encre = "Donneur", f"#fff;border:2px solid {teinte}", teinte
            else:                                             # les autres : le nom en capitales, blanc sur la couleur
                nom, fond, encre = SIEGE[x].upper(), teinte, "#fff"
            if x in (haut, bas):
                forme = "width:100%;height:100%;" + ("transform:rotate(180deg);" if x == haut else "")
            else:
                forme = "width:100%;height:100%;writing-mode:vertical-rl;" + ("transform:rotate(180deg);" if x == droite else "")   # le haut des lettres vers le centre, loin du lecteur
            return (f"<div class='{'pense' if jeu.get('pense') == x else ''}' style='grid-area:{place[x]};{forme}display:flex;"
                    f"align-items:center;justify-content:center;border-radius:5px;font-size:{f}px;font-weight:700;color:{encre};"
                    f"box-sizing:border-box;background:{fond}'>{nom}</div>")
        return (f"<div title='En rouge les camps vulnérables, en vert les autres' style='display:grid;box-sizing:border-box;"
                f"width:{W}px;height:{H}px;grid-template-columns:{h}px 1fr {h}px;grid-template-rows:{h}px 1fr {h}px;gap:4px;"
                f"padding:6px;border-radius:8px;background:#e4e7eb;border:1px solid #c8ced5;box-shadow:0 1px 2px rgba(0,0,0,.12)'>"
                f"{bande(haut)}{bande(gauche)}{bande(droite)}{bande(bas)}</div>")

    ETUI = (135, 240, 30, 14)    # les côtés de l'étui (9:16), l'épaisseur des bandes, le texte

    def tapis_encheres(d, places):
        """Les enchères posées devant chaque joueur, comme les cartons d'une boîte à enchères ; la dernière ressort."""
        vues = jeu["seq"][:jeu["affiche"]]
        devant = {x: [] for x in "NESO"}
        for k, b in enumerate(vues): devant[siege_de(d, k)].append(b)
        dernier = siege_de(d, len(vues) - 1) if vues else None
        def carton(b, recent, k, derniere=False):
            cls = {"passe": " passe", "contre": " contre", "surcontre": " surcontre"}.get(b) or " " + COUL_BOITE.get(b[1:], "sa")
            cls += " derniere" * derniere
            texte = {"passe": "Passe", "contre": "X", "surcontre": "XX"}.get(b, b)
            return f"<div class='carton{cls}{' recent' if recent else ''}' style='z-index:{k + 1}'>{texte}</div>"
        def pile(x, sens, ou):
            """Les cartons d'un joueur empilés, le dernier dessus : on voit encore le haut des précédents. Chaque pile est
            au milieu de son bord de la table, à la même distance du bord pour les quatre joueurs."""
            bs = devant[x]
            cartons = "".join(carton(b, x == dernier and k == len(bs) - 1, k, k == len(bs) - 1) for k, b in enumerate(bs))
            return f"<div class='pile {sens}' style='position:absolute;{ou}'>{cartons}</div>"
        haut, gauche, droite, bas = places
        bord = 18                                          # la distance au bord de la table
        return (f"<div style='position:absolute;inset:0'>"
                f"{pile(haut, 'vers-droite', f'top:{bord}px;left:50%;transform:translateX(-50%)')}"
                f"{pile(bas, 'vers-droite', f'bottom:{bord}px;left:50%;transform:translateX(-50%)')}"
                f"{pile(gauche, 'vers-bas', f'left:{bord}px;top:50%;transform:translateY(-50%)')}"
                f"{pile(droite, 'vers-bas', f'right:{bord}px;top:50%;transform:translateY(-50%)')}"
                f"<div style='position:absolute;left:50%;top:50%;transform:translate(-50%,-50%)'>{etui(d, places)}</div></div>")

    ORDRE_MAIN = "♠♥♣♦"                                    # noir, rouge, noir, rouge

    face = lambda r: "10" if r == "X" else r              # sur une carte à jouer, le dix s'écrit 10 (X dans les textes)

    def carte_el(coul, r, jouables, sur_clic):
        rouge_ = " r" if coul in "♥♦" else ""
        ok = jouables is not None and (coul, r) in jouables
        el = ui.html(f"<div class='carte{rouge_}{' jouable' if ok else ' terne' if jouables is not None else ''}'>{face(r)}<br/>{coul}</div>",
                     sanitize=False)
        if ok: el.on("click", lambda x=(coul, r): sur_clic(x))

    def mort_etale(cartes, jouables, sur_clic, atout):
        """Le mort étalé comme à la table : une colonne par couleur, la plus forte carte en haut, l'atout à gauche
        (à la droite du mort), puis les couleurs en alternant noir et rouge."""
        autres = [c for c in ORDRE_MAIN if c != atout]
        ordre = ([atout] if atout in ORDRE_MAIN else []) + autres
        with ui.row().classes("no-wrap items-start gap-3 mort-table"):
            for coul in ordre:
                with ui.column().classes("gap-0 colonne-mort"):
                    if not cartes.get(coul):
                        ui.html(f"<div class='carte vide'>{rouge(coul)}</div>", sanitize=False)
                    for r in cartes.get(coul, ""):
                        carte_el(coul, r, jouables, sur_clic)

    def eventail(cartes, jouables=None, sur_clic=None, colonnes=False, grande=False, a_vous=False):
        """Une main en cartes : {couleur: rangs français du plus fort au plus faible}. En ligne, un petit espace entre les
        couleurs ; en colonnes (une main sur le côté), une couleur par ligne. jouables : les cartes cliquables ;
        grande : votre main, plus grande, qui luit quand c'est à vous."""
        cls = " main-grande" * grande + " a-vous" * (grande and a_vous)
        with (ui.column().classes("gap-1") if colonnes else ui.row().classes("no-wrap items-end gap-0 eventail" + cls)):
            for coul in ORDRE_MAIN:
                rangs = cartes.get(coul, "")
                if colonnes and not rangs:
                    ui.html(f"<div class='carte vide'>{rouge(coul)}</div>", sanitize=False); continue
                with ui.row().classes("no-wrap gap-0 groupe" + (" colonne" if colonnes else "")):
                    for r in rangs: carte_el(coul, r, jouables, sur_clic)

    def dos(ou, n):
        """Une main cachée : n dos de cartes en éventail fermé, tenu par le joueur (les cartes tournent autour du coin
        qu'il tient) ; l'éventail est tourné vers le centre de la table."""
        if n <= 0: return
        m = (n - 1) / 2
        cartes = "".join(f"<div class='dos' style='position:absolute;left:19px;top:10px;transform-origin:50% 100%;"
                         f"transform:rotate({(k - m) * 4:.1f}deg)'></div>" for k in range(n))
        tour = {"haut": 180, "gauche": 90, "droite": -90}.get(ou, 0)
        l, h = (60, 70) if ou in ("gauche", "droite") else (70, 60)   # la place prise, une fois l'éventail tourné
        ui.html(f"<div style='position:relative;width:{l}px;height:{h}px'><div style='position:absolute;left:50%;top:50%;"
                f"width:70px;height:60px;transform:translate(-50%,-50%) rotate({tour}deg)'>{cartes}</div></div>", sanitize=False)

    def table(d, places, contenu, centre=None, sur_table=()):
        """La table, une grande surface vert clair : l'étui, les cartons, le pli et le mort posé dessus ; les mains des
        joueurs autour. contenu(siège, position) dessine une place ; sur_table : les positions posées sur la table (le mort)."""
        haut, gauche, droite, bas = places
        with ui.element("div").classes("w-full").style("overflow:hidden;padding-top:8px"), \
                ui.element("div").classes("ajuste").style("width:max-content;transform-origin:0 0"):   # rétrécit avec la fenêtre (JS_AJUSTE)
            with ui.grid(columns="1fr auto 1fr").classes("items-center gap-x-2 gap-y-4"):   # les mains des côtés contre la table
                with ui.column().classes("items-center").style("grid-column: 1 / 4"):
                    if "haut" not in sur_table: contenu(haut, "haut")
                with ui.column().classes("items-end"): contenu(gauche, "gauche")
                with ui.column().classes("items-center gap-4").style(       # la table, carrée comme une vraie, à la taille de la fenêtre
                        f"width:{COTE_TABLE};background:#f3efe7;border:1px solid #e3dccf;border-radius:28px;padding:12px 16px;"
                        "aspect-ratio:1 / 1;justify-content:space-between;position:relative"):
                    if "haut" in sur_table: contenu(haut, "haut")
                    if centre: centre()
                    if "bas" in sur_table: contenu(bas, "bas")
                with ui.column().classes("items-start"): contenu(droite, "droite")
                with ui.column().classes("items-center").style(
                        "grid-column: 1 / 4" + ("" if "bas" in sur_table else ";margin-top:12px")):
                    if "bas" not in sur_table: contenu(bas, "bas")             # votre main, un peu en retrait de la table

    def mains_fr(d, x):
        return dict(zip(carte.COULEURS, ("" if m == "-" else m for m in d["mains"][x].split())))

    def vue_carte(c, d, data, places):
        """Le jeu de la carte : la table et le pli au centre ; le panneau de droite est dessiné par vue_jouer."""
        p = jeu["partie"]; s = jeu["siege"]; part = jouer.PART[s]
        tour = p.au_trait()
        cliquable = not p.fini() and not jeu["pense"] and not jeu["pli_vu"] and p.camp(tour)

        def contenu(x, ou):
            if p.camp(x) or p.fini():
                with ui.column().classes("gap-1 " + ("items-center" if ou in ("haut", "bas") else "")):
                    if not p.fini():
                        cartes = {k: "".join(r.translate(carte.FR) for r in v) for k, v in p.pos.reste[x].items()}
                        jouables = {(k, r.translate(carte.FR)) for k, r in p.legales()} if cliquable and tour == x else None
                        clic = lambda y: carte_jouer((y[0], y[1].translate(carte.EN)))
                        if x == p.mort(): mort_etale(cartes, jouables, clic, p.den)
                        else: eventail(cartes, jouables, clic, colonnes=ou in ("gauche", "droite"), grande=x == s)   # les cartes jouables ont déjà leur bord
            elif not p.fini():                               # un adversaire : sa main cachée, en éventail fermé
                dos(ou, sum(len(v) for v in p.pos.reste[x].values()))
        table(d, places, contenu, lambda: ui.html(pli_html(p, places), sanitize=False),
              sur_table=[ou for x, ou in zip(places, ("haut", "gauche", "droite", "bas")) if x == p.mort() and not p.fini()])

    @ui.refreshable
    def vue_jouer():
        c = choix["chemin"]; data = lire_seance(c)
        if not data:
            ui.label("Aucune séance ouverte : Fichier, Ouvrir une séance…").classes("text-base"); return
        es = entrees_de(data) if sur_jouer() else []
        if not es: return
        e = entree_effective(data)
        if e == "options":
            ui.label("Options").classes("text-lg font-bold")
            ui.label("La place que vous jouez").classes("text-base font-bold mt-2")
            ui.label("Le déclarant est celui de la séquence recommandée (l'analyse de l'expert, sinon la standard, sinon "
                     "les enchères du programme). Le choix vaut pour toutes les donnes et reste d'une fois sur l'autre.") \
                .classes("text-base text-gray-600 max-w-2xl")
            def changer(ev):
                ecrire_etat(place_jouer=ev.value); jeu["cle"] = None   # la prochaine donne ouverte prend la nouvelle place
            ui.radio(dict(jouer.PLACES), value=place_jouer(), on_change=changer).classes("text-base")
            ui.label("En défense, vous enchérissez ; le jeu de la carte en défense viendra plus tard.").classes("text-sm text-gray-600")
            return
        d = next(x for x in data["donnes"] if f"d{x['n']}" == e)
        if jeu["cle"] != (c, d["n"]): jeu_depart(c, d)
        s = jeu["siege"]; part = jouer.PART[s]
        gauche, droite = jouer.ROT[(jouer.ROT.index(s) + 1) % 4], jouer.ROT[(jouer.ROT.index(s) + 3) % 4]
        places = (part, gauche, droite, s)               # vos cartes toujours en bas ; la table et l'étui tournent avec vous
        attente = jeu["affiche"] < len(jeu["seq"])
        fini = jeu["indice"] is None and not attente
        p = jeu["partie"]
        c_, decl = jouer.contrat(jeu["seq"], d["donneur"]) if fini else ("passe", None)
        a_jouer = fini and not p and c_ != "passe" and jouer.camp(decl) == jouer.camp(s) and not jeu.get("sans_jouer")
        montrer = (fini and not a_jouer and not p) or (p and p.fini())

        with ui.row().classes("w-full no-wrap items-start gap-4").style(f"padding-right:{LARGEUR_PANNEAU}px"):
            with ui.column().classes("grow min-w-0 gap-2"):              # la table
                if p:
                    vue_carte(c, d, data, places)
                else:
                    def contenu(x, ou):
                        if x == s or montrer:
                            eventail(mains_fr(d, x), colonnes=ou in ("gauche", "droite"), grande=x == s,
                                     a_vous=x == s and not fini and not attente)
                        else: dos(ou, 13)
                    table(d, places, contenu, lambda: ui.html(tapis_encheres(d, places), sanitize=False))
            with panneau_droit():                                                         # la barre de droite : l'essentiel
                ui.label(f"Donne {d['n']}").classes("text-lg font-bold")
                ui.label(f"Vous jouez {SIEGE[s]}").classes("text-sm text-gray-600")
                if p and not p.fini():                          # pendant le jeu, les cartons sont rangés : l'étui reste sur la table
                    with ui.row().classes("w-full justify-center"):
                        ui.html(etui(d, places, petit=True), sanitize=False)
                    with ui.expansion("Revoir les enchères").props("dense header-class='text-primary text-sm px-1'").classes("w-full"):
                        ui.html(grille_html(jouer.grille(jeu["seq"], d["donneur"]), d["vul"])
                                .replace("border-collapse:collapse", "border-collapse:separate;border-spacing:4px 0"), sanitize=False)
                else:
                    with ui.element("div").classes("w-full rounded-xl border border-gray-200 bg-white p-2"):
                        vues = jeu["seq"] if p else jeu["seq"][:jeu["affiche"]]
                        ui.html(grille_html(jouer.grille(vues, d["donneur"], not fini and not attente and not p), d["vul"])
                                .replace("border-collapse:collapse", "border-collapse:separate;border-spacing:4px 0"), sanitize=False)
                        autres = [(x, b, t_) for x, b, t_ in jeu["ex"][:jeu["affiche"]] if x != s and t_]
                        if autres:                                  # un petit lien sous la grille
                            with ui.expansion("Le sens des enchères").props("dense header-class='text-primary text-sm px-1'") \
                                    .classes("w-full mt-1"):
                                for x, b, t_ in autres:
                                    ui.html(f"<div style='font-size:14px'><b>{SIEGE[x]} {rouge(b)}</b> : {rouge(t_)}</div>", sanitize=False)
                if p:
                    vous, defense = p.levees()
                    ui.label(f"{p.contrat} par {SIEGE[p.decl]}").classes("text-base font-bold")
                    ui.label(f"Levées : vous {vous}, la défense {defense}").classes("text-base")
                    if not p.fini():
                        with ui.row().classes("gap-2"):
                            ui.button("Indice", icon="lightbulb", on_click=lambda: carte_indice()).props("outline dense no-caps")
                            ui.button("Réclamer", icon="done_all", on_click=lambda: carte_reclamer()).props("outline dense no-caps")
                        if jeu["msg"]: ui.label(jeu["msg"]).classes("text-sm")
                    if p.plis:
                        with ui.expansion(f"Plis joués ({len(p.plis)})", icon="list").props("dense").classes("w-full text-sm"):
                            for k, (pli, g) in enumerate(p.plis, 1):
                                ui.html(f"<div style='font-size:14px'>Pli {k} : " + " · ".join(f"{SIEGE[x][0]} {rouge(carte.carte_fr(cc, r))}" for x, cc, r in pli)
                                        + f" — {SIEGE[g]}</div>", sanitize=False)
                elif not fini and not attente:
                    boite_encheres(d)
                    if jeu["voir_indice"]:
                        ui.html(f"<div style='font-size:15px'>Le système dirait <b>{rouge(jeu['indice']['enchere'])}</b> : "
                                f"{rouge(jeu['indice']['texte'])}</div>", sanitize=False)
                elif a_jouer:
                    ui.button(f"Jouer {c_} par {SIEGE[decl]}", icon="style", on_click=lambda: carte_demarrer(d)).classes("w-full")
                    ui.button("Voir les mains sans jouer", on_click=lambda: (jeu.update(sans_jouer=True), vue_jouer.refresh())).props("flat no-caps dense")
                elif fini and c_ != "passe" and jouer.camp(decl) != jouer.camp(s):
                    ui.label("Votre camp défend : le jeu en défense viendra plus tard.").classes("text-sm text-gray-600")

        if fini and not jeu["garde"]:
            jouer.enregistrer(base_seance(c), d["n"], s, jeu["seq"], d["donneur"]); jeu["garde"] = True; barre_seance.refresh()
        if p:
            if p.fini():
                g, ecart, dm = p.resultat()
                texte = "fait tout juste" if ecart == 0 else f"fait avec {ecart} de mieux" if ecart > 0 else f"chute de {-ecart}"
                ui.html(f"<div style='font-size:16px;margin-top:8px'><b>{g} levées</b> : {rouge(p.contrat)} {texte}. "
                        f"Au double mort, le contrat donne {dm} levées.</div>", sanitize=False)
                if not jeu["garde_jeu"]:
                    jouer.completer_jeu(base_seance(c), d["n"], [carte.carte_fr(cc, r) for pli, _ in p.plis for _x, cc, r in pli], g)
                    jeu["garde_jeu"] = True
                with ui.row().classes("gap-3 mt-2"):
                    ui.button("Rejouer la carte", icon="replay", on_click=lambda: carte_demarrer(d)).props("outline")
                    ui.button("Recommencer les enchères", icon="restart_alt", on_click=lambda: (jeu_depart(c, d, s), vue_jouer.refresh())).props("outline")
                    ui.button("Donne suivante", icon="arrow_forward", on_click=lambda: jeu_suivante(data, d))
                mains_grille(d)
                comparaison(c, d, data, s)
            return
        if montrer: comparaison(c, d, data, s)

    def comparaison(c, d, data, s):
        """Le contrat du joueur face aux analyses, les séquences, le double mort."""
        r = jouer.comparer(d, jeu["seq"], s, lire_analyses(c))
        ui.label("Votre contrat face aux analyses").classes("text-base font-bold mt-4")
        lignes = []
        nom_contrat = lambda texte: re.sub(r" ([NESO])$", lambda m: " " + SIEGE[m[1]], texte)
        for x in r["lignes"]:
            m = x["marge"]; res = "" if x["levees"] is None else ("=" if m == 0 else f"+{m}" if m > 0 else f"<span style='color:#c0141c'>−{-m}</span>")
            i = "" if x["imp"] is None else ("0" if x["imp"] == 0 else f"{x['imp']:+d}".replace("-", "−"))
            lignes.append(f"<tr><td style='padding:2px 12px;font-weight:600'>{x['nom']}</td><td style='padding:2px 12px'>{rouge(nom_contrat(x['texte']))}</td>"
                          f"<td style='padding:2px 12px;text-align:center'>{res}</td><td style='padding:2px 12px;text-align:right'>{i}</td></tr>")
        ui.html("<table style='font-size:15px;border-collapse:collapse'><tr><th></th><th style='padding:2px 12px;text-align:left'>Contrat</th>"
                "<th style='padding:2px 12px'>Double mort</th><th style='padding:2px 12px'>IMP pour vous</th></tr>" + "".join(lignes) + "</table>",
                sanitize=False)
        ui.label("IMP pour vous : ce que votre contrat gagne (+) ou perd (−) face à celui de l'analyse, au double mort.").classes("text-sm text-gray-600")
        if r["ecart"]:
            k = r["ecart"]
            ui.html(f"<div style='font-size:15px;margin-top:6px'>Première différence : <b>{SIEGE[k['siege']]}</b> dit {rouge(k['vous'])}, "
                    f"l'analyse {k['nom'].lower()} {rouge(k['reference'])}.</div>", sanitize=False)
        with ui.row().classes("gap-8 items-start mt-2"):
            for x in r["lignes"]:
                with ui.column().classes("gap-0"):
                    ui.label(x["nom"]).classes("text-base font-bold")
                    ui.html(grille_html(jouer.grille(x["seq"], d["donneur"])), sanitize=False)
        page_dm_par(d)
        if jeu["partie"]: return                         # après le jeu, les boutons sont au-dessus
        with ui.row().classes("gap-3 mt-3"):
            ui.button("Recommencer", icon="replay", on_click=lambda: (jeu_depart(c, d, s), vue_jouer.refresh())).props("outline")
            ui.button("Donne suivante", icon="arrow_forward", on_click=lambda: jeu_suivante(data, d))

    def page_versions(c):
        """Les versions gardées d'une séance modifiable, pour revenir en arrière."""
        vs = edition.versions(c)
        ui.label("Versions précédentes").classes("text-base font-bold mt-4")
        ui.label("Chaque modification est enregistrée aussitôt. Une copie de la séance est gardée avant les changements, "
                 "au plus toutes les 10 minutes (les 20 dernières).").classes("text-sm text-gray-600")
        if not vs: ui.label("Aucune pour l'instant.").classes("text-sm text-gray-600")
        for v in vs[:20]:
            try: nb = len(edition.lire(v)["donnes"])
            except Exception: nb = 0
            with ui.row().classes("items-center gap-4"):
                ui.label(f"{quand(v)} · {nb} donne{'s' if nb > 1 else ''}").classes("text-base")
                ui.button("Restaurer", on_click=lambda v=v: restaurer(c, v)).props("flat dense no-caps")

    def restaurer(c, v):
        edition.restaurer(c, v); ui.notify("Version restaurée ; la version d'avant est gardée elle aussi.")
        vue_seance.refresh(); barre_seance.refresh(); vue_analyse.refresh()

    def editeur_donne(c, d):
        """La donne d'une séance modifiable : les quatre mains en champs (une couleur par champ), enregistrées à chaque
        changement ; donneur, vulnérabilité, compléter au hasard, supprimer."""
        n = d["n"]
        with ui.row().classes("w-full items-center justify-between no-wrap"):
            ui.label(f"Donne {n}").classes("text-lg font-bold")
            ui.button("Terminer", icon="check", on_click=lambda: terminer()).props("outline")
        with ui.row().classes("items-center gap-4"):
            ui.select({s: SIEGE[s] for s in "NESO"}, value=d["donneur"], label="Donneur",
                      on_change=lambda e: (edition.regler(c, n, donneur=e.value), maj(), resultat.refresh())).classes("w-32")
            ui.select(["Personne", "N-S", "E-O", "Tous"], value=d["vul"], label="Vulnérabilité",
                      on_change=lambda e: (edition.regler(c, n, vul=e.value), maj(), resultat.refresh())).classes("w-36")
        ui.label("Tapez les cartes de chaque couleur (A R D V X 9 … 2, ou 10) ; une couleur vide est une chicane. "
                 "Tout est enregistré dès que vous quittez un champ.").classes("text-sm text-gray-600")
        tetes = {}

        def main_ed(s):
            with ui.column().classes("gap-1"):
                tetes[s] = ui.label("").classes("text-sm font-bold text-gray-600")
                for k, coul in enumerate("♠♥♦♣"):
                    v = d["mains"][s].split()[k]
                    champ = ui.input(value="" if v == "-" else v).props(f'dense outlined prefix="{coul}"').classes("w-44")
                    champ.on("blur", lambda e, s=s, k=k, champ=champ: poser(s, k, champ))
                    champ.on("keydown.enter", lambda e, s=s, k=k, champ=champ: poser(s, k, champ))

        with ui.grid(columns="repeat(3, 190px)").classes("gap-3 items-start mt-2"):
            ui.label(""); main_ed("N"); ui.label("")
            main_ed("O"); centre = ui.label("").classes("text-sm text-gray-600 whitespace-pre-line self-center"); main_ed("E")
            ui.label(""); main_ed("S"); ui.label("")
        msg = ui.label("").classes("text-base text-red-800")
        with ui.row().classes("gap-3 mt-1"):
            ui.button("Compléter au hasard", icon="casino", on_click=lambda: completer()).props("outline")
            ui.button("Supprimer la donne", icon="delete", on_click=lambda: demander_suppression(c, n)).props("outline color=red")

        @ui.refreshable
        def resultat():                                   # le par seulement : le double mort est dans l'onglet Analyse
            dd = edition.donne_de(edition.lire(c), n)
            if dd.get("par"): ui.html(f"<div style='font-size:15px'>{par_html(dd)}</div>", sanitize=False)
        resultat()

        def maj():
            dd = edition.donne_de(edition.lire(c), n)
            nb, doubles, restantes = edition.etat(dd)
            for s in "NESO":
                k = len(edition.cartes(dd["mains"][s]))
                tetes[s].text = f"{SIEGE[s]} · {edition.points(dd['mains'][s])} H · {k} carte{'s' if k > 1 else ''}"
            centre.text = "Donne complète" if nb == 52 and not doubles else \
                f"{52 - nb} cartes à placer :\n" + "\n".join(f"{c_} {' '.join(r) or '—'}" for c_, r in restantes.items())
            msg.text = ("En double : " + ", ".join(f"{c_}{r}" for c_, r in doubles)) if doubles else msg.text

        def poser(s, k, champ):
            avant = edition.donne_de(edition.lire(c), n).get("a_completer", False)
            try:
                v = edition.poser_couleur(c, n, s, k, champ.value)
                champ.value = "" if v == "-" else v; msg.text = ""
            except ValueError as ex:
                msg.text = f"{SIEGE[s]}, {'♠♥♦♣'[k]} : {ex}"
            maj()
            if avant != edition.donne_de(edition.lire(c), n).get("a_completer", False):   # complète, ou plus complète
                resultat.refresh(); barre_seance.refresh()

        def completer():
            try:
                edition.completer_au_hasard(c, n)
            except ValueError as ex:
                msg.text = str(ex); return
            vue_seance.refresh(); barre_seance.refresh()
        maj()

    def modifier(c, n):
        """« Modifier la donne » : si elle a une analyse de l'expert, on prévient d'abord qu'elle sera mise de côté."""
        if edition.a_analyse_expert(c, n):
            confirmation_m.n = n; confirmation_m.open()
        else:
            vue["edition"] = n; vue_seance.refresh()

    def modifier_quand_meme():
        confirmation_m.close(); vue["edition"] = confirmation_m.n; vue_seance.refresh()

    def terminer():
        vue["edition"] = None; vue_seance.refresh(); barre_seance.refresh(); vue_analyse.refresh()

    def demander_suppression(c, n):
        confirmation.n = n; confirmation_texte.text = f"Supprimer la donne {n} ? Les donnes suivantes prendront le numéro d'avant."
        confirmation.open()

    def supprimer():
        c, n = choix["chemin"], confirmation.n
        confirmation.close()
        edition.supprimer_donne(c, n)
        data = lire_seance(c)
        reste = [d["n"] for d in data["donnes"]] if data else []
        vue["entree"] = f"d{min(n, max(reste))}" if reste else "seance"
        vue_seance.refresh(); barre_seance.refresh(); vue_analyse.refresh()

    def ajouter():
        n = edition.ajouter_donne(choix["chemin"])
        aller(f"d{n}"); vue["edition"] = n

    def creer_vide():
        c = edition.nouvelle_seance()
        n = edition.ajouter_donne(c)
        choisir(c); onglets.set_value(o_donnes); aller(f"d{n}")

    def sur_analyse():
        return onglets.value in (o_analyse, "Analyse")

    def sur_jouer():
        return onglets.value in (o_jouer, "Jouer")

    def sur_aide():
        return onglets.value in (o_aide, "Aide")

    vue_aide = {"k": 0}                                   # la section de l'aide montrée

    def voir_aide(k):
        vue_aide["k"] = k; page_aide.refresh(); barre_seance.refresh()
        ui.run_javascript("window.scrollTo(0, 0)")

    @ui.refreshable
    def page_aide():
        s = sections_aide()
        ui.html(s[min(vue_aide["k"], len(s) - 1)][1], sanitize=False).classes("aide w-full pb-8")

    def entrees_de(data):
        """Les entrées de la barre latérale : la séance, puis (onglet Donnes) les joueurs et les alertes, puis chaque donne."""
        if sur_jouer():                                   # Jouer : les donnes seules, et celles déjà enchéries
            faits = jouer.lire_essais(base_seance(choix["chemin"]))["donnes"]
            return [("options", "Options")] + [(f"d{d['n']}", f"Donne {d['n']}" + (" · enchérie" if faits.get(str(d["n"])) else ""))
                                                for d in data["donnes"] if not d.get("a_completer")]
        haut = [("standard", "Analyse standard"), ("expert", "Analyse expert")] if sur_analyse() else \
            [("seance", "Séance"), ("joueurs", "Joueurs")]   # toujours deux entrées : Donne 1 à la même hauteur partout
        return haut + [(f"d{d['n']}", f"Donne {d['n']}") for d in data["donnes"]]

    expert_msg = {"texte": "", "faute": False}

    def etapes_expert(c):
        """Les étapes pour obtenir l'analyse de l'expert de Claude, sur le web (claude.ai)."""
        nom = rapport.nom_seance(c)
        ui.label("Obtenir l'analyse de l'expert avec Claude").classes("text-base font-bold mt-4")
        ui.label("L'analyse de l'expert est écrite par Claude (claude.ai, dans votre navigateur). Comptez une "
                 "conversation par séance ; pour 24 donnes, Claude peut répondre en plusieurs fois.").classes("text-sm text-gray-600")
        etape = lambda k, texte: ui.html(f"<div style='font-size:16px'><b>{k}.</b> {texte}</div>", sanitize=False)
        with ui.column().classes("gap-3 max-w-2xl"):
            etape(1, "Préparez les fichiers : Bridge Coach met dans un dossier tout ce dont Claude a besoin (la séance, "
                     "l'analyse standard, le système, un exemple et la consigne), puis ouvre ce dossier.")
            ui.button("Préparer les fichiers pour Claude", icon="folder_open", on_click=lambda: preparer_expert(c)).props("outline")
            etape(2, "Ouvrez <b>claude.ai</b> dans votre navigateur et commencez une nouvelle conversation.")
            ui.button("Ouvrir claude.ai", icon="open_in_new", on_click=lambda: ouvrir("https://claude.ai/new")).props("outline")
            etape(3, "Glissez tous les fichiers du dossier dans la conversation.")
            etape(4, "Copiez la consigne, collez-la dans la conversation, puis envoyez.")
            ui.button("Copier la consigne", icon="content_copy", on_click=lambda: copier_consigne(c)).props("outline")
            etape(5, f"Claude écrit le fichier <code>{nom}-expert.json</code> : téléchargez-le avec le bouton sous sa réponse. "
                     "S'il répond en plusieurs fois, téléchargez chaque fichier.")
            etape(6, "Importez le fichier téléchargé (un par un s'il y en a plusieurs). L'analyse précédente de l'expert "
                     "est gardée, datée, et les donnes s'ajoutent.")
            ui.button("Importer l'analyse de l'expert…", icon="file_download", on_click=lambda: choisir_expert()).props("outline")
            etape(7, "Mettez les rapports PDF à jour : ils reprennent l'analyse de l'expert, sans refaire l'analyse standard.")
            ui.button("Mettre à jour les rapports", icon="picture_as_pdf", on_click=lambda: maj_rapports()).props("outline")
            if expert_msg["texte"]:
                ui.label(expert_msg["texte"]).classes("text-base " + ("text-red-800" if expert_msg["faute"] else "text-primary") + " break-all")

    def maj_rapports():
        if T.actif or D.actif or I.actif or not choix["chemin"]: return
        vu["fini"] = None; faute.text = ""
        lancer_rapports(choix["chemin"], noms.value)
        resultats.refresh(); montrer_controles()

    def preparer_expert(c):
        try:
            dossier, _ = preparer_pour_claude(c)
            expert_msg.update(texte=f"Fichiers prêts dans {dossier}", faute=False); ouvrir(dossier)
        except Exception:
            expert_msg.update(texte="Les fichiers n'ont pas pu être préparés.", faute=True)
        vue_analyse.refresh()

    def copier_consigne(c):
        date = (lire_seance(c) or {}).get("session", {}).get("date", "")
        ui.clipboard.write(CONSIGNE.format(nom=rapport.nom_seance(c), date=date))
        ui.notify("Consigne copiée : collez-la dans la conversation avec Claude.")

    def importer_expert_de(chemin):
        try:
            expert_msg.update(texte=importer_expert(choix["chemin"], chemin), faute=False)
        except ValueError as ex:
            expert_msg.update(texte=str(ex), faute=True)
        vue_analyse.refresh(); barre_seance.refresh(); resultats.refresh()

    async def choisir_expert():
        if not app.native.main_window: return envoi_x.run_method("pickFiles")
        try:
            r = await app.native.main_window.create_file_dialog(allow_multiple=False, file_types=TYPES_EXPERT)
        except Exception as ex:                            # jamais un clic sans effet : le message s'affiche
            expert_msg.update(texte=f"La fenêtre de choix de fichier ne s'est pas ouverte ({ex}).", faute=True); vue_analyse.refresh(); return
        if r: importer_expert_de(r[0])

    async def recu_x(e):
        cible = os.path.join(tempfile.mkdtemp(prefix="expert-"), os.path.basename(e.file.name))
        await e.file.save(cible)
        importer_expert_de(cible)

    def entree_effective(data):
        """L'entrée montrée : celle choisie si elle existe dans cet onglet, sinon la première."""
        es = entrees_de(data)
        if vue["entree"] in dict(es): return vue["entree"]
        return es[1][0] if sur_jouer() and len(es) > 1 else es[0][0]     # Jouer : la première donne, pas les options

    def montrer_controles():
        """« Lancer l'analyse » : sur la page Analyse standard, ou partout pendant qu'une analyse tourne."""
        try: controles
        except NameError: return                           # la page se construit encore : l'onglet change avant la barre
        data = lire_seance(choix["chemin"])
        controles.set_visibility(bool(data) and (T.actif or (sur_analyse() and entree_effective(data) == "standard")))

    def aller(k):
        vue["entree"] = k; vue["edition"] = None; barre_seance.refresh(); vue_seance.refresh(); vue_analyse.refresh(); vue_jouer.refresh(); montrer_controles()

    @ui.refreshable
    def barre_seance():
        if sur_aide():                                    # l'aide : une entrée par section
            for k, (titre, _) in enumerate(sections_aide()):
                ui.button(titre, on_click=lambda k=k: voir_aide(k)).props("flat no-caps align=left dense color=grey-10") \
                    .classes("entree-barre text-left" + (" choisie" if k == vue_aide["k"] else ""))
            return
        data = lire_seance(choix["chemin"])
        if not data: return
        a_finir = {f"d{d['n']}" for d in data["donnes"] if d.get("a_completer")}
        es = entrees_de(data); haut = [x for x in es if not x[0].startswith("d")]
        for k, (cle, nom) in enumerate(es):
            if cle in a_finir: nom += " · à compléter"
            choisie = cle == entree_effective(data)            # comme la barre de Claude : un fond un peu plus soutenu
            ui.button(nom, on_click=lambda k=cle: aller(k)).props("flat no-caps align=left dense color=grey-10") \
                .classes("entree-barre" + (" choisie" if choisie else ""))
            if k == len(haut) - 1:                            # deux places en haut, puis un trait : Donne 1 ne bouge pas
                for _ in range(2 - len(haut)): ui.element("div").classes("entree-barre")
                ui.separator().classes("my-2")
        if not sur_analyse() and not sur_jouer() and edition.modifiable(choix["chemin"])[0]:
            ui.button("Ajouter une donne", icon="add", on_click=lambda: ajouter()).props("flat no-caps align=left dense no-wrap") \
                .classes("entree-barre mt-2 text-primary")

    def montrer_barre():
        """La barre latérale : sur les onglets Donnes, Jouer et Analyse quand une séance est ouverte, et sur l'aide."""
        tiroir.set_value(sur_aide() or (onglets.value in (o_donnes, "Donnes", o_jouer, "Jouer", o_analyse, "Analyse")
                                        and lire_seance(choix["chemin"]) is not None))   # l'aide a toujours sa barre
    vu = {"fini": None}; vu_d = {"fini": None}; vu_i = {"fini": None}

    with ui.header(elevated=False).classes("bg-white text-primary px-2 py-0 border-b border-gray-300"):   # la barre de menus
        with ui.row().classes("w-full items-center justify-between no-wrap"):
            with ui.button("Fichier").props("flat no-caps dense").classes("px-3"):
                with ui.menu():
                    ui.menu_item("Nouveau…", on_click=lambda: nouveau_fichier())
                    ui.menu_item("Ouvrir une séance…", on_click=lambda: (liste.refresh(), dialogue.open()))
                    ui.menu_item("Importer…", on_click=lambda: (liste_i.refresh(), dialogue_i.open()))
                    ui.menu_item("Exporter en PBN…", on_click=lambda: exporter())
                    ui.separator()
                    ui.menu_item("Ouvrir le dossier de travail", on_click=lambda: ouvrir(rapport.DONNEES))
            with ui.tabs().props("no-caps dense inline-label align=left active-color=primary indicator-color=primary").classes("text-gray-700 grow") as onglets:   # les onglets, dans la barre
                o_donnes = ui.tab("Donnes")
                o_jouer = ui.tab("Jouer")
                o_analyse = ui.tab("Analyse")
                o_rapports = ui.tab("Rapports")
                o_reglages = ui.tab("Réglages")
                o_aide = ui.tab("Aide").classes("hidden")          # la page d'aide : montrée par le bouton de droite
                o_nouveau = ui.tab("Nouveau").classes("hidden")    # Fichier, Nouveau… : la page de création des donnes
            aide = ui.button("Aide", on_click=lambda: onglets.set_value(o_aide)).props("flat no-caps dense").classes("px-3")
            onglets.on_value_change(lambda e: (aide.classes(add="bg-green-50 font-bold") if e.value in (o_aide, "Aide")
                                               else aide.classes(remove="bg-green-50 font-bold"), montrer_barre(), barre_seance.refresh(),
                                               vue_analyse.refresh(), vue_jouer.refresh(), montrer_controles()))

    with ui.left_drawer(value=False, fixed=True, bordered=True).props("width=200 behavior=desktop") \
            .classes("p-2 gap-0").style(f"background:{GRIS_BARRE}") as tiroir:      # la barre latérale de des onglets Donnes et Analyse : bord gauche, toute la hauteur
        barre_seance()

    with ui.column().classes("w-full px-6 pt-4 pb-6 gap-0"):

        with ui.tab_panels(onglets, value=o_donnes, animated=False).classes("w-full"):
            with ui.tab_panel(o_donnes).classes("px-0"):
                @ui.refreshable
                def nouveau():
                    neuf = next((b for b in reglages()[0] if not deja_importe(b)), None)
                    if not neuf or I.actif: return
                    with ui.row().classes("w-full max-w-xl items-center justify-between no-wrap bg-green-50 rounded px-3 py-2 mb-3"):
                        with ui.column().classes("gap-0"):
                            ui.label(f"Nouveau tournoi dans Bridgemate, du {date_lisible(neuf)}").classes("text-base")
                            ui.label(os.path.basename(neuf)).classes("text-sm text-gray-600 break-all")
                        ui.button("Importer", on_click=lambda b=neuf: importer(b)).classes("shrink-0")
                nouveau()
                barre_i = ui.linear_progress(value=0, show_value=False).props("size=16px rounded indeterminate").classes("max-w-xl")
                texte_i = ui.label("").classes("text-base")
                faute_i = ui.label("").classes("text-base text-red-800")
                vue_seance()

            with ui.tab_panel(o_jouer).classes("px-0"):
                vue_jouer()

            with ui.tab_panel(o_analyse).classes("px-0 gap-3"):
                with ui.column().classes("w-full gap-3 pb-3 border-b border-gray-200") as controles:   # fixe : la barre y avance
                    with ui.row().classes("w-full items-center gap-4 no-wrap"):
                        creer = ui.button("Lancer l'analyse", icon="play_arrow", on_click=lambda: demarrer()).classes("text-base px-6")
                        noms = ui.checkbox("Ajouter une page avec le nom des joueurs aux rapports")
                    barre = ui.linear_progress(value=0, show_value=False).props("size=16px rounded").classes("max-w-xl")
                    texte = ui.label("").classes("text-base")
                    stop = ui.button("Annuler", on_click=annuler).props("outline")
                    faute = ui.label("").classes("text-base text-red-800")
                vue_analyse()

            with ui.tab_panel(o_rapports).classes("px-0 gap-4 max-w-xl mx-auto"):
                @ui.refreshable
                def resultats():
                    c = choix["chemin"]
                    if not c: ui.label("Aucune séance ouverte.").classes("text-base"); return
                    if T.actif: ui.label("Analyse en cours : les rapports arrivent à la fin.").classes("text-base text-gray-600"); return
                    prets = rapports_de(c)
                    ui.label(f"Rapports de la séance du {infos_seance(c)[0]}").classes("text-lg font-bold")
                    if not prets:
                        ui.label("Pas encore de rapport : lancez l'analyse dans l'onglet Analyse.").classes("text-base text-gray-600")
                    for quoi, nom, detail in RAPPORTS:
                        if quoi in prets: lien_pdf(prets[quoi], nom, detail)
                    bilan = os.path.join(rapport.RAPPORTS, "bilan-encheres.pdf")
                    if os.path.exists(bilan):
                        ui.label("Toutes les séances").classes("text-base font-bold mt-4")
                        lien_pdf(bilan, "Bilan des enchères", "où le programme perd des IMP face à l'expert")
                    if prets:
                        ui.button("Ouvrir le dossier des rapports", on_click=lambda p=prets[next(iter(prets))]: ouvrir(os.path.dirname(p))) \
                            .props("flat no-caps").classes("mt-2 px-0")
                resultats()

            with ui.tab_panel(o_reglages).classes("px-0 gap-5 max-w-xl mx-auto"):
                for titre, chemin in (("Dossier de Bridgemate : les fichiers .bws, lus sans être modifiés", dossier),
                                      ("Dossier de travail : vos séances et vos rapports", rapport.DONNEES),
                                      ("Programme Bridge Coach : là où il est installé", rapport.RACINE)):
                    with ui.row().classes("w-full items-center justify-between no-wrap"):
                        with ui.column().classes("gap-0"):
                            ui.label(titre).classes("text-base")
                            ui.label(chemin).classes("text-sm text-gray-600 break-all")
                        if os.path.isdir(chemin):
                            ui.button("Ouvrir", on_click=lambda c=chemin: ouvrir(c)).props("outline").classes("shrink-0")
                        else:
                            ui.label("Dossier introuvable").classes("text-sm text-red-800 shrink-0")
                ui.button("Modifier les réglages", on_click=ouvrir_reglages).classes("w-full text-base py-3")
                ui.label("Après une modification : enregistrez, puis fermez et rouvrez Bridge Coach.").classes("text-sm text-gray-600")

                ui.separator().classes("my-2")
                ui.label(f"Bridge Coach, version {maj.version_locale()}").classes("text-base font-bold")
                with ui.row().classes("items-center gap-3"):
                    ui.button("Rechercher une mise à jour", on_click=lambda: chercher_maj()).props("outline")
                    bouton_maj = ui.button("", on_click=lambda: lancer_maj()).props("unelevated")
                    bouton_maj.set_visibility(False)
                etat_maj = ui.label("Bridge Coach ne contacte GitHub que si vous cliquez ; il n'envoie rien.").classes("text-sm text-gray-600")
                journal = os.path.join(rapport.RAPPORTS, maj.JOURNAL)
                if os.path.exists(journal):
                    lignes_j = [x for x in open(journal, encoding="utf-8").read().splitlines() if x.strip()]
                    if lignes_j:
                        quand = datetime.datetime.fromtimestamp(os.path.getmtime(journal)).strftime("%d/%m/%Y")
                        ui.label(f"Dernière mise à jour, le {quand} : {lignes_j[0]} — {lignes_j[-1]}").classes("text-sm text-gray-600")

            with ui.tab_panel(o_aide).classes("px-0 max-w-xl mx-auto"):   # une page comme les autres : un onglet la quitte
                page_aide()                                    # une section à la fois, choisie dans la barre de gauche

            with ui.tab_panel(o_nouveau).classes("px-0 max-w-xl mx-auto"):   # Fichier, Nouveau… : une page, comme l'aide
                ui.label("Nouvelle séance").classes("text-lg font-bold")
                ui.label("Une séance vide, « Entraînement » et la date du jour, à remplir donne par donne : vous tapez les mains "
                         "dans l'onglet Donnes, et le programme peut compléter au hasard ce qui manque.").classes("text-base text-gray-600")
                ui.button("Créer une séance vide", icon="add", on_click=lambda: creer_vide()).classes("text-base mb-4")
                ui.separator()
                ui.label("Ou tirer des donnes au hasard, par sorte de main").classes("text-base font-bold mt-4")
                ui.label("Choisissez combien de donnes de chaque sorte avec − et +, 36 en tout au plus. Le programme les cherche, "
                         "les mélange et en fait une séance.").classes("text-base text-gray-600")
                quotas = {x: 0 for x in donnes.themes_tries()}
                total = lambda: sum(quotas.values())

                def changer(x, k):
                    quotas[x] = max(0, quotas[x] + k) if total() + k <= 36 else quotas[x]
                    liste_themes.refresh(); creer_d.set_enabled(total() > 0 and not (T.actif or D.actif or I.actif))

                @ui.refreshable
                def liste_themes():
                    with ui.grid(columns=2).classes("w-full gap-x-8 gap-y-0 mt-2"):
                        for x, k in quotas.items():
                            with ui.row().classes("items-center justify-between no-wrap"):
                                ui.label(x).classes("text-base" + (" font-bold text-primary" if k else ""))
                                with ui.row().classes("items-center no-wrap gap-0"):
                                    ui.button(icon="remove", on_click=lambda x=x: changer(x, -1)).props("flat round dense").set_enabled(k > 0)
                                    ui.label(str(k)).classes("w-7 text-center text-base" + (" font-bold" if k else " text-gray-400"))
                                    ui.button(icon="add", on_click=lambda x=x: changer(x, 1)).props("flat round dense").set_enabled(total() < 36)
                    n = total()
                    ui.label(f"Total : {n} donne{'s' if n > 1 else ''}" if n else "Total : aucune donne pour l'instant").classes("text-base mt-2")
                liste_themes()
                with ui.column().classes("w-full gap-4"):
                    creer_d = ui.button("Créer le fichier Bridge Coach", icon="casino", on_click=lambda: demarrer_donnes()).classes("text-base")
                    barre_d = ui.linear_progress(value=0, show_value=False).props("size=16px rounded")
                    texte_d = ui.label("").classes("text-base")
                    stop_d = ui.button("Annuler", on_click=lambda: annuler(D)).props("outline")
                    faute_d = ui.label("").classes("text-base text-red-800")

                    @ui.refreshable
                    def fichier_cree():
                        if not D.fichier or D.actif: return
                        ui.label("Donnes créées").classes("text-base font-bold")
                        ui.label(os.path.basename(D.fichier)).classes("text-sm text-gray-600 break-all")
                        if D.notes:
                            ui.label("Tirées au hasard faute de temps : " + " ; ".join(D.notes) + ".").classes("text-sm text-red-800")
                        with ui.row().classes("gap-3"):
                            ui.button("Analyser ces donnes", on_click=lambda: analyser_donnes())
                            ui.button("Ouvrir le dossier", on_click=lambda: ouvrir(os.path.dirname(D.fichier))).props("outline")
                        ui.label("Le fichier .pbn du dossier s'importe dans Bridgemate : Fichier, Importer.").classes("text-sm text-gray-600")
                    fichier_cree()

    with ui.dialog() as dialogue, ui.card().classes("w-full max-w-lg"):
        ui.label("Ouvrir une séance").classes("text-base font-bold")
        @ui.refreshable
        def liste():
            tout = seances_bc()
            if not tout: ui.label("Aucune séance pour l'instant : Fichier, Importer…").classes("text-sm text-gray-600")
            for c in tout[:15]:
                date, source = infos_seance(c)
                ui.button(f"{date}  –  {source + ' – ' if source else ''}{rapport.nom_seance(c)}", on_click=lambda c=c: choisir(c)) \
                    .props("flat align=left no-caps").classes("w-full")
        liste()
        ui.label("Ou une séance Bridge Coach (.bc.json) ailleurs sur l'ordinateur :")
        envoi = ui.upload(on_upload=lambda e: recu(e), auto_upload=True, max_files=1).props('accept=".json"').classes("hidden")
        ui.button("Choisir un fichier…", on_click=lambda: parcourir()).props("outline")
        ui.button("Fermer", on_click=dialogue.close).props("flat")

    with ui.dialog() as dialogue_i, ui.card().classes("w-full max-w-lg"):
        ui.label("Importer un tournoi").classes("text-base font-bold")
        ui.label("Le fichier devient une séance Bridge Coach ; le fichier d'origine n'est pas modifié.").classes("text-sm text-gray-600")
        @ui.refreshable
        def liste_i():
            bws = reglages()[0][:10]
            if not bws: ui.label(f"Aucun fichier .bws dans {dossier}.").classes("text-sm text-gray-600")
            for b in bws:
                fait = " (déjà importé)" if deja_importe(b) else ""
                ui.button(f"{date_lisible(b)}  –  {os.path.basename(b)}{fait}", on_click=lambda b=b: importer(b)) \
                    .props("flat align=left no-caps").classes("w-full")
        liste_i()
        ui.label("Ou un fichier ailleurs sur l'ordinateur (.bws de Bridgemate, feuille de route .pdf de FFBClubNet) :")
        envoi_i = ui.upload(on_upload=lambda e: recu_i(e), auto_upload=True, max_files=1).props('accept=".bws,.pdf"').classes("hidden")
        ui.button("Choisir un fichier…", on_click=lambda: parcourir_i()).props("outline")
        ui.button("Fermer", on_click=dialogue_i.close).props("flat")

    with ui.dialog() as confirmation_m, ui.card().classes("w-full max-w-md"):
        ui.label("Cette donne a une analyse de l'expert. Si vous la modifiez, cette analyse est mise de côté (gardée dans "
                 "une copie datée) : il faudra la redemander à Claude pour cette donne. Les autres donnes gardent la leur.").classes("text-base")
        with ui.row().classes("gap-3 justify-end w-full"):
            ui.button("Annuler", on_click=lambda: confirmation_m.close()).props("flat")
            ui.button("Modifier quand même", icon="edit", on_click=lambda: modifier_quand_meme())

    with ui.dialog() as confirmation, ui.card().classes("w-full max-w-md"):
        confirmation_texte = ui.label("").classes("text-base")
        with ui.row().classes("gap-3 justify-end w-full"):
            ui.button("Annuler", on_click=lambda: confirmation.close()).props("flat")
            ui.button("Supprimer", icon="delete", on_click=lambda: supprimer()).props("color=red")

    envoi_x = ui.upload(on_upload=lambda e: recu_x(e), auto_upload=True, max_files=1).props('accept=".json"').classes("hidden")

    with ui.dialog() as dialogue_e, ui.card().classes("w-full max-w-lg"):
        ui.label("Exporter en PBN").classes("text-base font-bold")
        msg_e = ui.label("").classes("text-sm break-all")
        ui.label("Le .pbn s'importe dans Bridgemate (Fichier, Importer) et se lit dans la plupart des logiciels de bridge.").classes("text-sm text-gray-600")
        with ui.row().classes("gap-3"):
            exporte = {"f": None}
            ui.button("Ouvrir le dossier", on_click=lambda: exporte["f"] and ouvrir(os.path.dirname(exporte["f"]))).props("outline")
            ui.button("Fermer", on_click=dialogue_e.close).props("flat")

    def montrer_titre():
        t_ = titre_fenetre(choix["chemin"])
        ui.page_title(t_)                                  # l'onglet du navigateur
        if app.native.main_window:                         # la barre de titre de la fenêtre
            try: app.native.main_window.set_title(t_)
            except Exception: pass

    def nouveau_fichier():
        """Fichier, Nouveau… : plus de séance ouverte (la séance retenue ne change qu'à la création de la nouvelle)."""
        choix["chemin"] = None; montrer_titre(); expert_msg.update(texte="", faute=False)
        vue_seance.refresh(); barre_seance.refresh(); vue_analyse.refresh(); resultats.refresh()
        onglets.set_value(o_nouveau); montrer_barre(); montrer_controles()

    maj_vue = {"version": None}

    async def chercher_maj():
        if maj.est_depot_git():
            etat_maj.text = "Ce dossier est une copie Git du programme : mettez-le à jour avec git pull."; return
        etat_maj.text = "Recherche sur GitHub…"; bouton_maj.set_visibility(False)
        try:
            v = await run.io_bound(maj.derniere_version)
        except Exception:
            etat_maj.text = "GitHub ne répond pas : vérifiez la connexion à Internet, puis réessayez."; return
        if not v or maj.cle(v) <= maj.cle(maj.version_locale()):
            etat_maj.text = f"Bridge Coach est à jour (version {maj.version_locale()})."; return
        maj_vue["version"] = v
        etat_maj.text = (f"La version {v} est disponible. Bridge Coach va se fermer, se mettre à jour en une minute environ, "
                         "puis se rouvrir. Vos séances, vos rapports et vos réglages ne changent pas.")
        bouton_maj.text = f"Mettre à jour vers {v}"; bouton_maj.set_visibility(True)

    def lancer_maj():
        v = maj_vue["version"]
        if not v: return
        if any(x.actif for x in (T, D, I)):
            etat_maj.text = "Un calcul est en cours : attendez qu'il se termine, puis recommencez."; return
        opts = {"creationflags": 0x00000008 | 0x00000200} if sys.platform == "win32" else {"start_new_session": True}
        subprocess.Popen([sys.executable, "-I", "-X", "utf8", os.path.join(ICI, "maj.py"), "--appliquer", v,
                          "--attendre", str(os.getpid()), "--journal", rapport.RAPPORTS], cwd=rapport.RACINE,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **opts)
        etat_maj.text = "Bridge Coach se ferme pour la mise à jour, puis se rouvre tout seul."
        ui.timer(1.5, app.shutdown, once=True)

    def choisir(c):
        choix["chemin"] = c; dialogue.close(); faute.text = ""
        retenir(c); montrer_titre(); vue["entree"] = "seance"; vue.pop("version", None); expert_msg.update(texte="", faute=False); vue_seance.refresh(); barre_seance.refresh(); montrer_barre(); montrer_controles()
        resultats.refresh(); vue_analyse.refresh()
        if onglets.value not in (o_donnes, o_analyse, o_rapports, "Donnes", "Analyse", "Rapports"): onglets.set_value(o_donnes)

    def importer(b):
        if T.actif or D.actif or I.actif: return
        dialogue_i.close(); vu_i["fini"] = None; faute_i.text = ""
        onglets.set_value(o_donnes)
        lancer_import(b); nouveau.refresh()

    def exporter():
        c = choix["chemin"]
        if not c or not c.endswith(rapport.BC):
            ui.notify("Ouvrez d'abord une séance (Fichier, Ouvrir une séance…)."); return
        try:
            f = exporter_pbn(c)
        except Exception:
            ui.notify("Cette séance ne peut pas être exportée."); return
        msg_e.text = f"Exporté : {f}"; exporte["f"] = f
        dialogue_e.open()

    async def parcourir_i():
        if not app.native.main_window: return envoi_i.run_method("pickFiles")
        dialogue_i.close()
        r = await app.native.main_window.create_file_dialog(allow_multiple=False, file_types=TYPES_IMPORT)
        if r: importer(r[0])

    async def recu_i(e):
        cible = os.path.join(tempfile.mkdtemp(prefix="import-"), os.path.basename(e.file.name))
        await e.file.save(cible)
        importer(cible)

    async def parcourir():
        """Dans la fenêtre, le dialogue de l'ordinateur : celui d'une page n'y s'ouvre pas. Le navigateur garde le sien."""
        if not app.native.main_window: return envoi.run_method("pickFiles")
        dialogue.close()
        r = await app.native.main_window.create_file_dialog(allow_multiple=False, file_types=TYPES_SEANCES)
        if r: choisir(r[0])

    async def recu(e):
        """Le fichier choisi arrive par la page : on le garde sous son nom, dans un dossier provisoire."""
        cible = os.path.join(tempfile.mkdtemp(prefix="rapports-"), os.path.basename(e.file.name))
        await e.file.save(cible)
        choisir(cible)

    def demarrer_donnes():
        if T.actif or D.actif or I.actif or not 1 <= total() <= 36: return
        vu_d["fini"] = None; faute_d.text = ""
        lancer_donnes(list(quotas.items()))
        fichier_cree.refresh()

    def analyser_donnes():
        choisir(D.fichier); onglets.set_value(o_analyse)

    def demarrer():
        if T.actif or D.actif or I.actif or not choix["chemin"]: return
        vu["fini"] = None; faute.text = ""
        lancer(choix["chemin"], noms.value)
        resultats.refresh(); montrer_controles()

    def rafraichir():
        actif_i = I.actif
        barre_i.set_visibility(actif_i); texte_i.set_visibility(actif_i)
        if actif_i: texte_i.text = I.texte
        if I.fini and vu_i["fini"] is not I.proc:          # l'import vient de finir : la séance s'ouvre
            vu_i["fini"] = I.proc
            faute_i.text = "" if I.annule else I.erreur
            if I.fichier and not I.erreur: choisir(I.fichier)
            nouveau.refresh()
        actif = T.actif; occupe = actif or actif_i         # un travail à la fois
        creer.set_enabled(not occupe and not D.actif and bool(choix["chemin"])); stop.set_visibility(actif)
        actif_d = D.actif
        creer_d.set_enabled(not occupe and not actif_d and total() > 0); stop_d.set_visibility(actif_d)
        barre_d.set_visibility(actif_d); texte_d.set_visibility(actif_d)
        if actif_d: barre_d.set_value(round(D.fraction, 3)); texte_d.text = D.texte
        if D.fini and vu_d["fini"] is not D.proc:
            vu_d["fini"] = D.proc
            faute_d.text = "" if D.annule else D.erreur
            fichier_cree.refresh()
            if D.fichier and not D.erreur and not D.annule:   # la nouvelle séance s'ouvre, comme une séance vide
                choisir(D.fichier); onglets.set_value(o_donnes)
                if D.notes: ui.notify("Tirées au hasard faute de temps : " + " ; ".join(D.notes) + ".", multi_line=True, timeout=10000)
        barre.set_visibility(actif); texte.set_visibility(actif)
        if actif: barre.set_value(round(T.fraction, 3)); texte.text = f"{T.texte} · {int(T.fraction * 100)} %"
        if T.fini and vu["fini"] is not T.proc:            # le travail vient de finir : une seule fois
            vu["fini"] = T.proc
            faute.text = T.erreur
            if T.annule: faute.text = ""
            resultats.refresh(); vue_analyse.refresh(); montrer_controles()

    ui.timer(.4, rafraichir)
    ui.timer(.5, lambda: montrer_titre(), once=True)
    montrer_barre(); montrer_controles()       # la fenêtre naît avec le titre du programme seul
    rafraichir()


@app.get("/devant")
async def devant():
    """Un clic sur l'icône du Dock remet la fenêtre devant les autres."""
    if app.native.main_window:
        app.native.main_window.restore()
        app.native.main_window.show()
        app.native.main_window.set_always_on_top(True)     # pywebview n'a pas de « mettre devant » : l'aller-retour le fait
        app.native.main_window.set_always_on_top(False)
    return {}


def principal():
    fenetre = "--navigateur" not in sys.argv and "--sans-ouvrir" not in sys.argv
    if fenetre:
        try:
            import webview                                 # noqa: F401
        except ImportError:
            fenetre = False
    opts = dict(native=True, window_size=(1200, 850)) if fenetre else dict(show="--sans-ouvrir" not in sys.argv)
    app.on_shutdown(lambda: (annuler(T), annuler(D), annuler(I)))
    # 127.0.0.1 : seul cet ordinateur joint l'application ; sans fenêtre, NiceGUI ouvrirait sinon le port à tout le réseau
    ui.run(title=TITRE, host="127.0.0.1", port=PORT, reload=False, show_welcome_message=False, favicon="♠", language="fr", **opts)


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    principal()
