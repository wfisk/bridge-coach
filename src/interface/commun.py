# -*- coding: utf-8 -*-
"""Ce que partagent les modules de l'interface : les imports, les constantes, l'état gardé (etat.json),
les travaux en arrière-plan (rapport.py), l'aide, les petits dessins HTML ; et F, les noms de la page."""
import asyncio, datetime, glob, json, os, re, shutil, signal, subprocess, sys, tempfile, threading, time, types
import html as html_

ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # src/
sys.path.insert(0, ICI)
import dds_verrou                                         # noqa: F401 — un seul appel au solveur double mort à la fois
import brouillon, carte, classement, quiz, donnes, edition, exporter, fichiers, fiche_conventions, jouer, maj, moi, palette, question_expert, rapport, systeme_vue
from nicegui import app, background_tasks, run, ui

TITRE = "Bridge Coach"
PORT = int(os.environ.get("BRIDGE_COACH_PORT") or 8123)    # un autre port : une seconde instance d'essai
CORBEILLE_SYSTEME = "Corbeille de Windows" if sys.platform == "win32" else "Corbeille du Mac"   # où va la corbeille vidée
DEV = maj.est_depot_git()
SYSTEME_DATA = systeme_vue.lire()                          # le système des robots (regles.yaml), lu une fois : lecture seule
SYSTEME_PAGES = ([("sy-vue", "Vue d'ensemble")] + [("sy-" + k, t) for k, t, _ in systeme_vue.familles(SYSTEME_DATA)]
                 + [("sy-entames", "Entames et signaux")] + [("sy-conv-" + k, t) for k, t, _ in systeme_vue.CONVENTIONS]
                 + [("systeme", "Votre fiche de conventions"), ("ecarts", "Écarts fiche / robots")])
SYSTEME_ANCRES = {systeme_vue.ancre(c): c for _, l in SYSTEME_DATA["sections"] for c, _, _ in l}
JS_SYSTEME = """<script>
// Système : « La suite : 1SA - 2T → » mène à cette séquence (l'événement systeme_vers, côté Python : aller_sequence)
document.addEventListener('click', function (e) {
  var s = e.target.closest && e.target.closest('.syst .suite[data-vers]');
  if (s) emitEvent('systeme_vers', s.getAttribute('data-vers'));
});
</script>"""
SYSTEME_GROUPES = {"sy-vue": "Les robots · SEF 2024", "sy-conv-" + systeme_vue.CONVENTIONS[0][0]: "Conventions",
                   "systeme": "Votre partenariat"}                                  # un dépôt Git : le développement (Réglages, Outils de développement)
LARGEUR_BARRE = 220                                        # la barre de gauche (Donnes, Jouer, Analyse) : « Donne 24 » et la barre de défilement
PART_ANALYSE = .85                                         # la part de la barre pour l'analyse, le reste pour les PDF
NB_PDF = 2                                                 # l'analyse, la comparaison
RAPPORTS = (("analyse", "Analyse", "enchères, entame, plan de jeu, conseil du coach et, si vous l'incluez, avis de l'expert"),
            ("a-revoir", "Donnes à revoir", "seulement les donnes où vous pouviez faire mieux, la plus coûteuse d'abord"),
            ("donnes", "Donnes", "les donnes choisies"),
            ("resume", "Version courte", "sans commentaires : résultats, enchères aux tables, enchères recommandées, double mort et par"),
            ("resume-a-revoir", "Version courte des donnes à revoir", "sans commentaires"),
            ("resume-donnes", "Version courte des donnes choisies", "sans commentaires"),
            ("comparaison", "Comparaison", "le Coach face à l'Expert"))
NIVEAUX = {"faits": "Version courte (sans commentaires)", "coach": "Le coach", "expert": "Le coach et l'expert"}   # Rapports, l'analyse
PAGES_EN_PLUS = (("noms", "Liste des joueurs", "les noms complets, en première page"),   # dans l'ordre du rapport (l'utilisateur,
                 ("champ", "Vous face au champ", "votre % donne par donne face aux autres tables, et où vous pouviez faire mieux"),   # 2026-11-13)
                 ("parcours", "Votre parcours", "tour par tour : la table, les donnes, les adversaires"),
                 ("synthese", "Synthèse des contrats", "une ligne par donne : le contrat recommandé et ce qu'ont joué les tables"),
                 ("comparaison", "Le Coach face à l'Expert", "un rapport à part, quand l'expert a analysé la séance"))
PAGES_DEFAUT = ["champ", "parcours", "synthese", "comparaison"]
TYPES_FICHIERS = ("Tournois (*.bws;*.pdf;*.pbn;*.json)", "Tous les fichiers (*.*)")
TYPES_SEANCES = ("Séances Bridge Coach (*.bc.json;*.json)", "Tous les fichiers (*.*)")
TYPES_BWS = ("Bridgemate feuille de route ou pages du site de la FFB (*.bws;*.pdf;*.html)", "Tous les fichiers (*.*)")
TYPES_PBN = ("PBN (*.pbn)", "Tous les fichiers (*.*)")
TYPES_EXPERT = ("Analyse expert (*.json)", "Tous les fichiers (*.*)")   # pywebview : lettres et espaces seulement, pas d'apostrophe
SOURCES = {"bws": "Bridgemate", "feuille-de-route": "Feuille de route", "entrainement": "Entraînement",
           "saisie": "Donnes saisies", "simulation": "Simulation", "ffb-html": "Site de la FFB",
           "ffb-pdf": "Site de la FFB (page imprimée en PDF)", "brouillon": "Brouillon"}
AIDE = os.path.join(rapport.RACINE, "help", "index.html")
IMAGES_AIDE = os.path.join(rapport.RACINE, "help", "images")   # les captures d'écran de l'aide, servies sous /aide-images/
GENERIQUE = ("Le rapport n'a pas pu être créé. Le détail est dans le fichier derniere-erreur.txt du dossier des rapports : "
             "vous pouvez le joindre à un signalement (Réglages, Un problème, une idée ?).")
GITHUB = "https://github.com/wfisk/bridge-coach"            # les signalements (issues) et les discussions du projet


class Travail:
    """Le rapport en cours : un seul à la fois, quelle que soit la page ouverte."""

    def __init__(self, part=PART_ANALYSE, mot="Analyse de la donne"):
        self.part = part; self.mot = mot                   # la part de la barre pour les donnes, le mot affiché
        self.proc = None; self.fraction = 0.0; self.texte = ""; self.erreur = ""; self.fini = False; self.annule = False
        self.prets = []; self.seance = None; self.fichier = None; self.notes = []
        self.genre = ""                                    # T : "analyse" (onglet Analyse) ou "rapports" (onglet Rapports)

    @property
    def actif(self): return self.proc is not None and not self.fini


T = Travail()                                              # les rapports
D = Travail(1.0, "Création de la donne")                   # les donnes
I = Travail(1.0, "Import")                                 # un import (le .bc.json seulement)


NOM_VERSION = {"Standard": "Coach", "Expert": "Expert"}   # l'analyse « standard » s'appelle « du coach » à l'écran

def lire_ligne(t, ligne):
    """Avance la progression selon une ligne de rapport.py."""
    m = re.match(r"Donne (\d+) sur (\d+)", ligne)
    if m:
        k, n = int(m[1]), int(m[2])
        t.fraction = t.part * (k - 1) / n; t.texte = f"{t.mot} {k} sur {n}"; t.n_donnes = n
        return
    m = re.match(r"Rapport prêt : (.+)", ligne)
    if m:
        t.prets.append(m[1].strip())
        t.fraction = t.part + (1 - t.part) * min(len(t.prets) / NB_PDF, 1); t.texte = "Écriture des rapports"
        return
    m = re.match(r"Fichier prêt : (.+)", ligne)
    if m: t.fichier = m[1].strip()
    m = re.match(r"Thème non trouvé : (.+)", ligne)
    if m: t.notes.append(m[1].strip())
    m = re.match(r"Temps : (.+)", ligne)                    # donnes.creer : où le temps est passé
    if m: noter_temps("Création des donnes, le détail : " + m[1].strip().replace(".", ","), 0, detail=True)


def message_erreur(sortie):
    """Ce qu'on montre : le message de rapport.py s'il en a écrit un, jamais une trace Python."""
    sortie = sortie.strip()
    if not sortie or "Traceback" in sortie: return GENERIQUE
    return sortie.splitlines()[-1] if len(sortie) > 300 else sortie


def rapports_de(chemin):
    """{niveau: [(pdf, paire)]} déjà produits pour cette séance : l'analyse une fois par paire (« -analyse-SS-AR.pdf »,
    initiales "" sans « Vous êtes »), les plus récentes d'abord. Seulement ceux de cette séance-ci : la date de la
    séance en tête du nom (deux séances « tournoi-jeudi » de dates différentes restent à part)."""
    ancien = {"expert": "analyse", "standard": "analyse", "diff": "comparaison"}   # les noms d'avant la 1.4, jusqu'aux rapports refaits
    d = fichiers.date_de(fichiers.entete(chemin))
    if not d: return {}
    debut = f"{d.isoformat()}-{rapport.nom_court(rapport.nom_seance(chemin))}-"
    trouves = {}
    for f in fichiers.pdfs(chemin):
        m = re.match(r"((?:releve|resume)-a-revoir|(?:(?:releve|resume)-)?donnes?-[\d-]+|analyse|a-revoir|releve|resume|comparaison"
                     r"|standard|expert|diff)(?:-(.+))?\.pdf$", os.path.basename(f)[len(debut):])
        if not m or ".provisoire" in f: continue           # (« analyse 2.pdf » : une copie d'iCloud, pas un rapport)
        m = [m[0], m[1].replace("releve", "resume"), m[2]] # « -releve » : l'ancien nom de la version courte (avant le 14/11)
        d_ = re.match(r"(resume-)?donnes?-([\d-]+)$", m[1])
        if d_:                                             # des donnes choisies : leurs numéros à la place des initiales
            trouves.setdefault((d_[1] or "") + "donnes", []).append((f, ", ".join(d_[2].strip("-").split("-"))))
        else:
            trouves.setdefault(m[1], []).append((f, (m[2] or "").replace("-", "/")))
    out = {}
    for quoi in [q for q, _, _ in RAPPORTS] + list(ancien):
        cle = ancien.get(quoi, quoi)
        if cle in out and quoi in ancien: continue
        if quoi in ("comparaison", "diff") or quoi in ancien:
            liste = [(f, "") for f, p in trouves.get(quoi, []) if not p]
        else:
            liste = trouves.get(quoi, [])
        if liste: out.setdefault(cle, []).extend(sorted(liste, key=lambda x: -os.path.getmtime(x[0])))
    return out


def date_lisible(chemin):
    d = datetime.date.fromisoformat(rapport.date_du_fichier(chemin))
    return d.strftime("%d/%m/%Y")


GRIS_BARRE = "var(--bc-tapis-100)"
LARGEUR_PANNEAU = 300                                     # la barre de droite de l'onglet Jouer
# le côté de la table de l'onglet Jouer, dans les unités du dessin : la table, les mains autour et les cartons forment un
# seul bloc de taille fixe, que le CSS (.cadre-table) agrandit ou rétrécit pour remplir la place (de 0,45 à 2,4 fois) ; sur un grand écran ou une
# télévision, les cartes grandissent avec, la table garde la même proportion (l'utilisateur, 2026-11-11 : lire les cartes
# de loin, pas une grande table)
COTE_TABLE = "440px"
# pendant le jeu de la carte, avec le mort sur un côté (en défense) : une table rectangulaire, de la même hauteur, plus
# large de la colonne de la main du mort (vide : ses cartes sont sur la table). Les cartes gardent leur taille.
LARGEUR_TABLE_LARGE = f"calc({COTE_TABLE} + 84px)"
CARTE_L, PAS_CARTE = 55, 33       # une carte (.carte, 55 px) et ce qu'en montre la suivante (55 − 22)
LIGNE_CARTES = 6                  # une ligne d'une main sur le côté : la place de six cartes, fixe ; au-delà, elles se serrent
LARGEUR_LIGNE = CARTE_L + (LIGNE_CARTES - 1) * PAS_CARTE
HAUT_MORT = 100                   # le mort étalé en haut ou en bas : la table plus haute de 100 px (140 avant le 13/11)
COTE_TABLE_PX, LARGEUR_TABLE_LARGE_PX = 440, 440 + 84   # les mêmes, en nombres (le pli en croix se décale de la différence / 2)
HAUTEUR_BARRE = 37                                        # la barre de menus du haut                                    # le gris clair des barres latérales, comme celle de Claude

JS_SUR_PAGE = """<script>
// L'aide, « Sur cette page » : un clic descend à la section (sous la barre du haut) ; en lisant, la section à l'écran est
// marquée (.lue). Sans changer l'adresse de la page : la fenêtre n'a pas de bouton « précédent ».
window.allerAide = function (id, net) {
  var h = document.getElementById(id);
  if (h) h.scrollIntoView({behavior: net ? 'auto' : 'smooth', block: 'start'});
  if (window.suivreAide) setTimeout(window.suivreAide, net ? 30 : 400);
  return false;
};
// Une capture de l'aide, cliquée : en grand, par-dessus la page ; un clic (ou Échap) la referme.
document.addEventListener('click', function (e) {
  var img = e.target.closest && e.target.closest('.aide figure img');
  var ouverte = document.querySelector('.image-aide-grande');
  if (ouverte) { ouverte.remove(); return; }
  if (!img) return;
  var d = document.createElement('div'); d.className = 'image-aide-grande';
  var g = document.createElement('img'); g.src = img.src; g.alt = img.alt; d.appendChild(g); document.body.appendChild(d);
});
document.addEventListener('keydown', function (e) {
  var o = document.querySelector('.image-aide-grande'); if (o && e.key === 'Escape') o.remove();
});
window.suivreAide = function () {
  function marquer() {
    var liens = document.querySelectorAll('.sur-page a[data-ancre]');
    if (!liens.length) return;
    var lue = liens[0].dataset.ancre;
    liens.forEach(function (a) {
      var h = document.getElementById(a.dataset.ancre);
      if (h && h.getBoundingClientRect().top < 140) lue = a.dataset.ancre;
    });
    if (window.innerHeight + window.scrollY >= document.body.scrollHeight - 4) lue = liens[liens.length - 1].dataset.ancre;
    liens.forEach(function (a) { a.classList.toggle('lue', a.dataset.ancre === lue); });
  }
  if (!window.__aideSuivie) { window.addEventListener('scroll', marquer, {passive: true}); window.__aideSuivie = true; }
  setTimeout(marquer, 50);
};
</script>"""

JS_SENS = """<script>
// Le sens d'une enchère de la grille : la bulle s'ouvre au survol (CSS) ; un clic la garde ouverte, un autre clic (sur elle
// ou ailleurs) la ferme. Utile au doigt, à la télécommande, et pour les mains moins sûres.
document.addEventListener('click', function (e) {
  var td = e.target.closest && e.target.closest('.enc-sens, .carte-sens');
  document.querySelectorAll('.enc-sens.ouverte, .carte-sens.ouverte').forEach(function (x) { if (x !== td) x.classList.remove('ouverte'); });
  if (td) td.classList.toggle('ouverte');
});
</script>"""

JS_GLISSE = """<script>
// Une carte qui change de place glisse de l'ancienne à la nouvelle : celle que vous jouez de votre main ou du mort vers la
// table, et celles qui se resserrent derrière elle. La page note où est chaque carte visible (data-c : couleur et rang) ;
// après chaque redessin, une carte déjà vue ailleurs part de là (la technique FLIP). Une carte d'une main cachée n'a pas
// de place connue : elle garde son glissement depuis le bord du joueur (arrive-*). Changer de donne oublie les places.
(function () {
  var places = new Map(), donne = null, envol = new Set(), calme = false, prevu = false;
  function ou(el) {                            // la place d'une carte dans la table, en unités de la table : quand la table
    var t = el.closest('.ajuste'), r = el.getBoundingClientRect();   // change d'échelle (.cadre-table), rien ne bouge
    if (!t) return {x: r.left, y: r.top, w: r.width};
    var c = t.getBoundingClientRect(), e = c.width / (t.offsetWidth || c.width) || 1;
    return {x: (r.left - c.left) / e, y: (r.top - c.top) / e, w: r.width};
  }
  function suivreVol() {                       // pendant le vol, la place notée est la place vue : un redessin repart d'ici
    envol.forEach(function (el) {
      if (!el.isConnected) { envol.delete(el); return; }
      places.set(el.getAttribute('data-c'), ou(el));
    });
    if (envol.size) requestAnimationFrame(suivreVol);
  }
  function noter() {
    prevu = false;
    var t = document.querySelector('.ajuste[data-donne]'), d = t ? t.getAttribute('data-donne') : null;
    if (d !== donne) { places.clear(); donne = d; }
    var vues = new Map(), vols = [];
    document.querySelectorAll('[data-c]').forEach(function (el) {
      var k = el.getAttribute('data-c');
      if (envol.has(el)) { vues.set(k, places.get(k)); return; }
      var avant = places.get(k);
      if (avant && !calme && /arrive-/.test(el.className)) {   // déjà vue ailleurs : pas de glissement depuis le bord,
        el.className = el.className.replace(/\s*arrive-\S+/g, ''); el.style.animationDelay = '';   // et il fausserait la mesure
      }
      var p = ou(el); if (!p.w) return;
      vues.set(k, p);
      if (!avant || calme) return;
      var dx = avant.x - p.x, dy = avant.y - p.y;               // en unités de la table : la translation de la carte
      if (Math.abs(dx) < 2 && Math.abs(dy) < 2) return;
      vols.push({el: el, dx: dx, dy: dy, d: Math.hypot(dx, dy)});
    });
    // au pas des cartes des défenseurs (arrive-* : 110 px en 0,5 s, ease-out) : 0,5 s au moins, plus pour un long trajet ;
    // toutes ensemble, le temps du plus long : les cartes qui se resserrent arrivent avec celle posée sur la table
    var duree = Math.min(800, Math.max(500, Math.max.apply(null, vols.map(function (v) { return v.d; }).concat([0])) * 4.5));
    vols.forEach(function (v) {
      var el = v.el;
      el.style.position = el.style.position || 'relative'; el.style.zIndex = 5;
      var a = el.animate([{transform: 'translate(' + v.dx + 'px,' + v.dy + 'px)'}, {transform: 'none'}],
                         {duration: duree, easing: 'ease-out'});
      envol.add(el);
      a.onfinish = a.oncancel = function () { envol.delete(el); el.style.zIndex = ''; };
    });
    places = vues; calme = false;
    if (vols.length) requestAnimationFrame(suivreVol);
  }
  function plusTard() { if (!prevu) { prevu = true; requestAnimationFrame(noter); } }
  window.addEventListener('resize', function () { calme = true; plusTard(); });   // la fenêtre change : rien ne vole
  document.addEventListener('DOMContentLoaded', function () {
    new MutationObserver(plusTard).observe(document.body, {childList: true, subtree: true});
    plusTard();
  });
})();
</script>"""

CSS_CARTES = """
/* Les mesures de la table (l'utilisateur, 2026-11-16) : une seule proportion, celle de la carte (55 de large, 2:3 comme une vraie, coin de 6 px),
   et une seule échelle d'espaces, comme Bootstrap (0,25 / 0,5 / 1 / 1,5 / 3 rem). Le tapis fait huit cartes de côté, une
   main sur un côté quatre cartes de large, son coin quatre coins de carte. */
:root { --sp-1: .25rem; --sp-2: .5rem; --sp-3: 1rem; --sp-4: 1.5rem; --sp-5: 3rem;
  --carte-l: 55px; --carte-h: calc(var(--carte-l) * 3 / 2); --carte-r: 6px;   /* 2:3 (l'utilisateur, 2026-11-16) */
  --table-cote: calc(8 * var(--carte-l)); --table-large: calc(var(--table-cote) + 84px); --haut-mort: 100px;
  --table-r: calc(4 * var(--carte-r)); }
/* La table de Jouer, Démo et Revoir : une boîte de taille fixe (--W × --H : le tapis le plus large, deux côtés, le tapis le
   plus haut, une rangée de cartes en haut et en bas), mise à l'échelle par le CSS seul de la place que lui laisse la
   fenêtre (.zone-table, un conteneur : 100cqw × 100cqh). tan(atan2(a, b)) donne le nombre a / b. Rien ne se mesure : la
   table ne change pas de taille quand les mains se vident (elle tremblait en fin de donne avec l'ancien script). */
@property --echelle { syntax: '<number>'; inherits: true; initial-value: 1; }
/* la colonne de la table remplit la fenêtre : 109 px = la barre du haut et la marge de la page (53) + les marges du bas (56) */
div:has(> .zone-table) { height: calc(100dvh / var(--zoom, 1) - 109px); }
.zone-table { flex: 1 1 0; min-height: 200px; container-type: size; overflow: hidden; --cotes: calc(2 * var(--carte-l)); }
.zone-table.ouverte { --cotes: calc(4 * var(--carte-l)); }   /* les mains des côtés visibles */
.cadre-table { --W: calc(var(--table-large) + 2 * var(--cotes) + 2 * var(--sp-2));
  --H: calc(var(--table-cote) + var(--haut-mort) + 2 * var(--carte-h) + 2 * var(--sp-3) + var(--sp-2));
  --echelle: clamp(.45, min(tan(atan2(100cqw, var(--W))), tan(atan2(100cqh, var(--H)))), 2.4);
  width: calc(var(--W) * var(--echelle)); height: calc(var(--H) * var(--echelle)); margin: 0 auto; }
.ajuste { width: var(--W); height: var(--H); transform: scale(var(--echelle)); transform-origin: 0 0; }
.grille-table { width: 100%; height: 100%; display: grid; align-items: center; column-gap: var(--sp-2); row-gap: var(--sp-3);
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); grid-template-rows: minmax(0, 1fr) auto auto; }
.grille-table > .rang-haut, .grille-table > .rang-bas { grid-column: 1 / 4; }
.grille-table > .rang-haut { align-self: end; }              /* la main du haut contre la table, l'espace libre au-dessus */
.grille-table > .rang-bas { align-self: start; }
.grille-table > .rang-bas.en-retrait { margin-top: var(--sp-2); }   /* votre main, un peu en retrait de la table */
.grille-table .nom-joueur.deux { white-space: normal; }      /* un long nom sur un côté passe à la ligne */
/* la place d'une main : une carte de haut au moins (un éventail de dos, 60 px de large, sur un côté), quatre rangées quand
   les mains des côtés sont visibles ; vide, elle garde sa taille */
.emplacement { display: flex; min-height: var(--carte-h); }
.main-cote { position: relative; }                       /* un côté : la main centrée sur la table, son nom au-dessus */
.main-cote > .nom-cote { position: absolute; bottom: calc(100% + var(--sp-1)); left: 0; }
.emplacement.haut { align-items: flex-end; } .emplacement.bas { align-items: flex-start; }
.emplacement.gauche, .emplacement.droite { min-width: 60px; align-items: center; }
.zone-table.ouverte .emplacement.gauche, .zone-table.ouverte .emplacement.droite {
  min-height: calc(4 * var(--carte-h) + 3 * var(--sp-1)); min-width: calc(4 * var(--carte-l)); }
::-webkit-scrollbar { width: 14px; height: 14px; background: transparent; }
::-webkit-scrollbar-thumb { background: var(--bc-tapis-300); border-radius: 7px; border: 2px solid transparent; background-clip: padding-box; }
::-webkit-scrollbar-thumb:hover { background-color: var(--bc-tapis-400); }
::-webkit-scrollbar-track, ::-webkit-scrollbar-corner { background: transparent; }
* { scrollbar-color: var(--bc-tapis-300) transparent; }
.entree-barre { width: 100%; justify-content: flex-start; border-radius: 8px; padding: 4px 12px; font-weight: 400;
  color: var(--bc-tapis-900); min-height: 32px; }
.entree-barre.choisie { background: var(--bc-tapis-200); font-weight: 600; }
.entree-barre .q-btn__content { text-align: left; justify-content: flex-start; line-height: 1.3; padding: 2px 0; }
.entree-barre.aide-sujet { height: auto; min-height: 32px; padding-top: 6px; padding-bottom: 6px; flex-shrink: 0; }   /* un sujet sur deux lignes ne déborde pas */
.carte { width: var(--carte-l); height: var(--carte-h); margin-right: -22px; padding: 3px 5px; background: var(--bc-blanc); border: 1px solid var(--bc-tapis-300);
  border-radius: 6px; font-size: 20px; line-height: 1.05; font-weight: 600; color: var(--bc-tapis-900); }   /* une seule taille partout :
   les mains, le mort, le pli (l'utilisateur, 2026-11-11) ; le bloc de la table grandit avec la fenêtre (.cadre-table) */
.carte.r { color: var(--bc-coeur-600); }
.carte { position: relative; }
.carte .dm { position: absolute; left: -6px; top: -12px; min-width: 26px; padding: 1px 5px;   /* le coin visible, même recouverte */
  border-radius: 9px; font-size: 15px; font-weight: 800; color: var(--bc-blanc); text-align: center; line-height: 1.25; z-index: 2;
  box-shadow: 0 0 0 2px var(--bc-blanc); }   /* démonstration, double mort : les levées du déclarant avec cette carte */
.carte .dm.mieux { background: var(--bc-trefle-700); } .carte .dm.moins { background: var(--bc-coeur-600); }
.carte.jouable { cursor: pointer; }
.tapis .carte:not(.jouable), .dos { cursor: default; }   /* une carte qu'on ne joue pas, une main de dos : rien ne s'y passe (2026-11-18) */   /* sans couleur : rien ne dit quelles cartes sont permises (comme à la table) */
.carte.secoue { animation: secoue .45s ease-in-out; border-color: var(--bc-coeur-600); }   /* une carte qui ne peut pas être jouée */
@keyframes secoue { 0%, 100% { transform: translateX(0); } 20%, 60% { transform: translateX(-7px); } 40%, 80% { transform: translateX(7px); } }
.carte.jouable:hover { transform: translateY(-6px); }
.tableau-seances { display: grid; width: 100%; align-items: center; column-gap: 12px; padding: 0 6px; min-height: 30px;   /* Ouvrir une séance, */
  grid-template-columns: 20px minmax(0, 1fr) 128px 112px 52px minmax(0, .6fr) 92px 28px; font-size: var(--fs-liste);   /* comme l'Explorateur */
  color: var(--bc-tapis-900); border: 1px solid transparent; }
.entete-seances { min-height: 30px; font-size: var(--fs-petit); color: var(--bc-tapis-700); border-bottom: 1px solid var(--bc-tapis-200); }
.entete-seances > * { padding: 0 2px; } .entete-seances > :hover { color: var(--bc-tapis-900); }
.entete-seances > .actif { font-weight: 700; color: var(--bc-tapis-900); }
.entete-seances > :nth-child(5), .entete-seances > :nth-child(7) { text-align: right; }
.ligne-seance { cursor: pointer; }
.liste-seances { container-type: inline-size; }
@container (max-width: 820px) {   /* texte grand ou fenêtre étroite : la colonne Type s'efface, le nom garde sa place */
  .liste-seances .tableau-seances { grid-template-columns: 20px minmax(0, 1fr) 128px 0 44px minmax(0, .6fr) 92px 28px; }
  .liste-seances .tableau-seances > :nth-child(4) { visibility: hidden; overflow: hidden; } }
.encheres-reco > :last-child { flex: 1 1 280px; min-width: 260px; }
.ligne-seance:hover { background: var(--bc-pique-50); border-color: var(--bc-pique-100); }   /* la ligne sous la souris */
.ligne-seance.ouverte { background: var(--bc-pique-100); border-color: var(--bc-pique-300); }   /* la séance ouverte : sélectionnée */
.ligne-seance .icone-seance { color: var(--bc-tapis-600); }
.ligne-seance .titre-seance { color: var(--bc-tapis-900); }
.groupe-seances { display: flex; align-items: center; gap: 4px; margin: 10px 0 2px; padding: 0 2px; font-size: var(--fs-texte);
  color: var(--bc-pique-800); }
.groupe-seances .trait { flex: 1; height: 1px; background: var(--bc-tapis-200); margin-left: 8px; }
.groupe-seances:hover { color: var(--bc-pique-600); }
.ligne-seance .poubelle { opacity: 0; transition: opacity .15s; }      /* la corbeille seulement sur la ligne survolée */
.ligne-seance:hover .poubelle, .ligne-seance .poubelle:focus-visible { opacity: 1; }
.carte.terne { background: var(--bc-tapis-100); border-color: var(--bc-tapis-200); color: var(--bc-tapis-400); }   /* pas jouable : terne mais opaque,
   les cartes en dessous ne se voient pas au travers */
.carte.r.terne { color: var(--bc-coeur-300); }
.colonne-mort .carte { margin-right: 0; }
.colonne-mort > * + * { margin-top: calc(26px - var(--carte-h)); }   /* chaque carte montre 26 px de la précédente (PAS_COLONNE) */
.ligne-mort > :last-child .carte { margin-right: 0; }   /* le mort sur un côté : une ligne par couleur, chevauchée comme une main
   (chaque carte est seule dans son enveloppe : c'est la dernière enveloppe de la ligne qui compte) */
.nom-joueur { display: flex; align-items: center; gap: 6px; font-size: calc(15px / max(var(--echelle, 1), .75)); color: var(--bc-tapis-800);
  white-space: nowrap; }   /* la table rapetisse (--echelle) : le nom grandit d'autant, d'un tiers au plus, pour rester lisible */
.nom-joueur.tour { color: var(--bc-tapis-900); font-weight: 700; text-decoration: underline 3px var(--bc-trefle-700); text-underline-offset: 5px; }
.nom-joueur.tour.pense-doux { text-decoration: none; animation: doux 1.4s ease-in-out infinite; }   /* un robot réfléchit */
@keyframes doux { 50% { opacity: .45; } }
.nom-joueur .siege-lbl { font-weight: 800; letter-spacing: .5px; color: var(--bc-tapis-900); }
/* à qui le tour : sa place et son nom ensemble sur un fond jaune plein, sans halo (le texte reste net ; l'utilisateur,
   2026-11-14). Le fond déborde de 8 px de chaque côté (marge négative) : le texte ne bouge pas quand il s'allume */
.nom-joueur { padding: 2px 8px; margin: 0 -8px; border-radius: 6px; transition: background .2s; }
.nom-joueur.a-jouer { background: var(--bc-jaune-200); color: var(--bc-tapis-900); }
.nom-joueur.a-jouer .siege-lbl { color: var(--bc-tapis-900); }
.nom-joueur.deux { display: block; line-height: 1.2; }   /* à l'ouest, aligné contre la table (à droite) */
.enc-sens { position: relative; cursor: pointer; text-decoration: underline dotted var(--bc-tapis-400); text-underline-offset: 4px; }
.enc-sens .bulle { display: none; position: absolute; top: calc(100% + 4px); left: 0; z-index: 30; width: 230px; padding: 8px 10px;
  background: var(--bc-blanc); border: 1px solid var(--bc-tapis-200); border-radius: 8px; box-shadow: 0 4px 14px rgba(0,0,0,.18); text-align: left;
  font-size: 16px; line-height: 1.35; font-weight: 400; color: var(--bc-tapis-900); white-space: normal; }
.enc-sens.c1 .bulle { left: -60px; } .enc-sens.c2 .bulle { left: auto; right: -60px; } .enc-sens.c3 .bulle { left: auto; right: 0; }
.enc-sens:hover .bulle, .enc-sens.ouverte .bulle { display: block; }
.marque-alerte { display: inline-block; margin-left: 3px; padding: 0 4px; border-radius: 4px; background: var(--bc-pique-700); color: var(--bc-blanc);
  font-size: 11px; font-weight: 700; line-height: 15px; vertical-align: 2px; }
.carte.gagnante { box-shadow: 0 0 0 2px var(--bc-jaune-400), 0 0 14px color-mix(in srgb, var(--bc-jaune-400) 55%, transparent); transform: translateY(-3px);
  transition: box-shadow .3s, transform .3s; }   /* la carte qui gagne le pli : une lueur dorée, discrète */
.carte.vers-bas { animation: vers-bas .45s ease-in forwards; } .carte.vers-haut { animation: vers-haut .45s ease-in forwards; }
.carte.vers-gauche { animation: vers-gauche .45s ease-in forwards; } .carte.vers-droite { animation: vers-droite .45s ease-in forwards; }
@keyframes vers-bas { to { transform: translateY(150px) scale(.3); opacity: 0; } }
@keyframes vers-haut { to { transform: translateY(-150px) scale(.3); opacity: 0; } }
@keyframes vers-gauche { to { transform: translateX(-170px) scale(.3); opacity: 0; } }
@keyframes vers-droite { to { transform: translateX(170px) scale(.3); opacity: 0; } }
/* la carte qui a commencé le pli : rien (bord noir puis petite flèche essayés, pas compris : l'utilisateur, 2026-11-11) */
.carte-sens { position: relative; cursor: help; }
.carte-sens .bulle { display: none; position: absolute; top: calc(100% + 6px); left: 50%; transform: translateX(-50%); z-index: 40;
  width: calc(240px / var(--echelle, 1)); padding: calc(8px / var(--echelle, 1)) calc(10px / var(--echelle, 1));
  background: var(--bc-blanc); border: 1px solid var(--bc-tapis-200); border-radius: 8px; box-shadow: 0 4px 14px rgba(0,0,0,.18);
  font-size: calc(16px / var(--echelle, 1)); line-height: 1.35; font-weight: 400; color: var(--bc-tapis-900); white-space: normal; }
  /* dans la table mise à l'échelle (.cadre-table, --echelle), la bulle garde sa vraie taille : 16 px à l'écran */
.carte-sens:hover .bulle, .carte-sens.ouverte .bulle { display: block; }
.carte.vide { width: 28px; border: none; background: none; margin-right: 0; padding: 4px 0 3px 6px; color: var(--bc-tapis-300); }   /* une chicane : la couleur
   en gris pâle, là où elle serait sur une carte, sous le rang (invisible) : alignée sur les autres couleurs (l'utilisateur, 2026-11-13) */
.carte.vide .rang-vide { visibility: hidden; }
.eventail .groupe { margin-right: 26px; }
.eventail .groupe:last-child { margin-right: 16px; }
.groupe.colonne .carte, .ligne-mort .carte { margin-right: var(--marge, -22px); }   /* serrer() : une longue couleur */
.groupe.colonne.serre .carte, .ligne-mort.serre .carte { font-size: 16px; padding-left: 3px; }
.groupe.colonne > :last-child .carte { margin-right: 0; }
.ajuste .carte { position: relative; z-index: 1; }      /* sur la table, les cartes passent au-dessus de l'étui en filigrane */
.groupe.colonne .dix { letter-spacing: -1px; }             /* le 10 tient dans la part visible de la carte */  /* sinon la ligne paraît plus courte : à gauche, elle passerait sous la table */
.dos { width: 32px; height: 46px; border-radius: 4px; border: 2px solid var(--bc-blanc); outline: 1px solid var(--bc-pique-200);
  background: repeating-linear-gradient(45deg, var(--bc-pique-300) 0 3px, var(--bc-pique-200) 3px 6px); }
.plis-gardes { display: flex; align-items: center; min-height: 30px; }
.plis-gardes .dos { width: 20px; height: 28px; border-width: 1px; border-radius: 3px; flex: none; }
.plis-gardes .dos.couche { width: 28px; height: 20px; }   /* comme en duplicate : vers le partenaire gagné, en travers perdu */
.plis-gardes .dos + .dos { margin-left: -9px; }           /* chaque carte posée en partie sur la précédente */
.plis-gardes .dos[onclick] { pointer-events: auto; cursor: pointer; }   /* la dernière carte : voir le dernier pli */
.plis-gardes .dos:not(.gagne) { background: var(--bc-tapis-200); outline-color: var(--bc-tapis-300); }   /* perdu : gris uni, pas le dos des mains cachées */
.plis-gardes .dos.gagne { background: repeating-linear-gradient(45deg, var(--bc-trefle-600) 0 3px, var(--bc-trefle-500) 3px 6px); outline-color: var(--bc-trefle-800); }
.plis-gardes.colonne { flex-direction: column; min-height: 0; min-width: 30px; }
.compte-plis { position: absolute; left: calc(100% + 8px); top: 50%; transform: translateY(-50%); min-width: 24px; height: 24px;
  padding: 0 6px; border-radius: 12px; background: var(--bc-trefle-600); color: var(--bc-blanc); font-size: 15px; font-weight: 700; line-height: 24px;
  text-align: center; box-sizing: border-box; }   /* hors de la rangée : elle reste centrée */
.plis-gardes.colonne .dos + .dos { margin-left: 0; margin-top: -9px; }
.plis-gardes.colonne .compte-plis { left: 50%; top: calc(100% + 8px); transform: translateX(-50%); }   /* sous la colonne */
.compte-plis.autre { background: var(--bc-coeur-600); }
/* la levée qui vient d'être gagnée : le cercle reste, l'ancien nombre monte et sort, le nouveau monte à sa place */
.compte-plis.roule { overflow: hidden; }
.compte-plis .pile { display: block; animation: compte-monte .45s ease-out forwards; }
.compte-plis .pile span { display: block; height: 24px; }
@keyframes compte-monte { from { transform: translateY(0); } to { transform: translateY(-24px); } }   /* les levées de l'autre camp en rouge, les vôtres en vert (l'utilisateur, 2026-11-11) */
.plis-gardes.adverse .dos.gagne { background: repeating-linear-gradient(45deg, var(--bc-coeur-600) 0 3px, var(--bc-coeur-500) 3px 6px); outline-color: var(--bc-coeur-800); }
.main-grande .groupe { margin-right: 30px; }
.main-grande .groupe:last-child { margin-right: 22px; }   /* juste ce que dépasse la dernière carte : le trait s'arrête avec elle */
/* à vous d'enchérir ou de jouer : les cartes à jouer (votre main, ou le mort quand vous en jouez) luisent en jaune ;
   ni les noms ni les mains des robots (l'utilisateur, 2026-11-11) */
.main-grande.a-vous, .mort-table.a-vous { filter: drop-shadow(0 0 6px color-mix(in srgb, var(--bc-jaune-300) 90%, transparent)); }
/* à qui le tour (vous ou un joueur du programme) : un petit triangle sur le bord de la table, tourné vers ce joueur */
.fleche-tour { position: absolute; width: 0; height: 0; z-index: 4; pointer-events: none; }
.fleche-tour.bas { bottom: -10px; left: 50%; transform: translateX(-50%); border: 9px solid transparent; border-bottom: 0;
  border-top: 10px solid var(--q-primary); }
.fleche-tour.haut { top: -10px; left: 50%; transform: translateX(-50%); border: 9px solid transparent; border-top: 0;
  border-bottom: 10px solid var(--q-primary); }
.fleche-tour.gauche { left: -10px; top: 50%; transform: translateY(-50%); border: 9px solid transparent; border-left: 0;
  border-right: 10px solid var(--q-primary); }
.fleche-tour.droite { right: -10px; top: 50%; transform: translateY(-50%); border: 9px solid transparent; border-right: 0;
  border-left: 10px solid var(--q-primary); }
.onglet.eteint { background: var(--bc-tapis-200) !important; color: var(--bc-tapis-400) !important; }
.onglet.indice { background: var(--bc-blanc); color: var(--bc-trefle-700); display: flex; align-items: center; gap: 2px; }
.sa { color: var(--bc-tapis-900); background: var(--bc-tapis-100); } .pique { color: var(--bc-pique-800); background: var(--bc-pique-100); }
.coeur { color: var(--bc-coeur-600); background: var(--bc-coeur-100); } .carreau { color: var(--bc-carreau-500); background: var(--bc-jaune-50); }
.trefle { color: var(--bc-trefle-600); background: var(--bc-trefle-100); }
/* les cartons d'enchères posés sur la table, comme de vrais cartons de boîte à enchères : dessinés à l'endroit pour qui les
   lit en face (.face), retournés pour celui qui les pose ; chaque joueur les pose de gauche à droite devant lui (.cadre,
   tourné selon sa place), le dernier sur le précédent : on voit encore la bande de droite (pour le lecteur) des autres */
.cadre { position: absolute; transform-origin: 0 100%; display: flex; align-items: flex-end; }
.pile { display: flex; align-items: flex-end; }
.carton { position: relative; flex: none; }
.carton .face { position: absolute; inset: 0; transform: rotate(180deg); border-radius: 5px;
  box-shadow: 0 0 3px rgba(0,0,0,.25); }   /* une ombre égale de tous côtés : les cadres tournent */
.carton.derniere .face { box-shadow: 0 0 9px 1px rgba(0,0,0,.32); }   /* la dernière enchère de chacun ressort un peu */
/* posés sur la table comme les vrais : tournés d'un quart de tour par rapport à la boîte. Vu du lecteur (.face) : les
   enchères plus larges que hautes, le niveau et la couleur sur la bande de droite ; PASS, X, XX presque carrés, le
   nom le long du bord droit, l'onglet (sans texte) sur le bord gauche. La bande de droite reste visible sous le suivant */
.carton.bid { width: 89px; height: 50px; }   /* 16:9 (l'utilisateur, 2026-11-16) */ .carton.bid .face { background: var(--bc-blanc); border: 1px solid var(--bc-tapis-300); }
.carton.bid .grand { position: absolute; right: 5px; top: 0; bottom: 0; display: flex; align-items: center;
  font-weight: 700; line-height: 1; }                     /* le niveau, la couleur à sa droite : « 1♦ » sur une ligne */
.carton.bid .grand b { font-size: 26px; } .carton.bid .grand i { font-style: normal; font-size: 24px; margin-left: 1px; }
.carton.bid .grand i.sa { font-size: 26px; font-weight: 700; background: none; margin-left: 1px; }   /* SA de la taille du chiffre */
.carton.bid.sa .grand { color: var(--bc-tapis-900); } .carton.bid.pique .grand { color: var(--bc-pique-800); }
.carton.bid.coeur .grand { color: var(--bc-coeur-600); } .carton.bid.carreau .grand { color: var(--bc-carreau-500); }
.carton.bid.trefle .grand { color: var(--bc-trefle-600); }
.carton.carre { width: 50px; height: 50px; }   /* carrés, avec leur onglet (l'utilisateur, 2026-11-16) */ .carton.carre .face { color: var(--bc-blanc); border: 2px solid var(--bc-tapis-100); }   /* le bord presque blanc sépare deux cartons pareils */
.carton .tab { position: absolute; left: -10px; top: 6px; width: 10px; min-height: 20px;
  border-radius: 3px 0 0 3px; background: inherit; border: 2px solid var(--bc-tapis-100); border-right: 0; }
.carton .tab.gauche { top: auto; bottom: 6px; }
.carton .base { position: absolute; right: 3px; top: 3px; bottom: 3px; width: 22px; display: flex; flex-direction: column;
  align-items: center; justify-content: space-between; font-weight: 800; line-height: 1; }
.carton .base b { writing-mode: vertical-rl; }            /* chaque lettre tournée : le mot se lit le long du bord droit */
.carton .base.mot { font-size: 13px; } .carton .base.croix { font-size: 22px; justify-content: space-around; }
.carton .base.croix b + b { margin-top: -2px; }
.carton.passe .face { background: var(--bc-trefle-600); } .carton.contre .face { background: var(--bc-coeur-600); }
.carton.surcontre .face { background: var(--bc-pique-700); } .carton.stop .face { background: var(--bc-coeur-600); }
.carton.alerte .face { background: var(--bc-pique-700); }
.carton:not(.derniere) .face { filter: saturate(.75) brightness(1.04) contrast(.88); }   /* les précédentes un peu effacées, sans cadre */
.cadre .a-part { margin-right: 14px; }      /* Stop et Alerte : posés à gauche de la rangée, pas parmi les enchères */
@keyframes tourne { from { transform: rotate(180deg); } to { transform: none; } }   /* la table, d'un demi-tour (TOURNE) */
.carton.arrive-bas, .carte.arrive-bas { animation: arrive-bas .5s ease-out; }
.carton.arrive-haut, .carte.arrive-haut { animation: arrive-haut .5s ease-out; }
.carton.arrive-gauche, .carte.arrive-gauche { animation: arrive-gauche .5s ease-out; }
.carton.arrive-droite, .carte.arrive-droite { animation: arrive-droite .5s ease-out; }
@keyframes arrive-bas { from { transform: translateY(110px); opacity: 0; } 30% { opacity: 1; } to { transform: none; } }
@keyframes arrive-haut { from { transform: translateY(-110px); opacity: 0; } 30% { opacity: 1; } to { transform: none; } }
@keyframes arrive-gauche { from { transform: translateX(-110px); opacity: 0; } 30% { opacity: 1; } to { transform: none; } }
@keyframes arrive-droite { from { transform: translateX(110px); opacity: 0; } 30% { opacity: 1; } to { transform: none; } }
.boite-encheres { background: var(--bc-coeur-600); border-radius: 12px; padding: 8px; }
.boite-encheres.en-attente { opacity: .45; pointer-events: none; filter: saturate(.5); }   /* pas votre tour : grisée */
.ratelier { background: var(--bc-pique-50); border-radius: 6px; padding: 6px; display: flex; flex-direction: column; gap: 4px; }
.tirette { width: 46px; height: 30px; display: flex; align-items: center; justify-content: center; border-radius: 4px;
  font-size: 16px; font-weight: 700; border: 1px solid rgba(0,0,0,.18); cursor: pointer; }
.tirette:hover { filter: brightness(.93); transform: translateY(-2px); }
.tirette.vide { visibility: hidden; }
.tirette.depassee { background: var(--bc-tapis-100); color: var(--bc-tapis-300); border-color: var(--bc-tapis-200); cursor: default; }   /* dépassée : en gris pâle */
.tirette.depassee:hover { filter: none; transform: none; }
.tirette.autres { width: auto; color: var(--bc-tapis-700); background: var(--bc-blanc); font-weight: 600; font-size: 15px; color: var(--bc-tapis-900); }
.compartiment { margin-top: 8px; background: var(--bc-coeur-700); border-radius: 6px; padding: 6px 6px 6px; align-items: center; }
.onglet { position: relative; min-width: 58px; height: 38px; margin-top: 11px; padding: 0 6px; border-radius: 4px;
  font-size: 16px; font-weight: 700; color: var(--bc-blanc); display: flex; align-items: center; justify-content: center; cursor: pointer; }
.onglet[data-tab]::before { content: ""; position: absolute; top: -9px; right: 3px; height: 10px; min-width: 20px;
  padding: 0 3px; border-radius: 3px 3px 0 0; font-size: 8px; line-height: 12px; background: inherit; color: inherit; }
.compartiment > :last-child .onglet { min-width: 72px; }   /* le second rang : Stop et Alerte, sous Passe, X, XX */
.onglet.passe { background: var(--bc-trefle-600); } .onglet.contre { background: var(--bc-coeur-500); } .onglet.surcontre { background: var(--bc-pique-700); }
.onglet.eteint { cursor: default; }
.onglet:not(.eteint):hover { filter: brightness(.93); transform: translateY(-2px); }   /* comme les cartons d'enchères au survol */
.onglet.stop { background: var(--bc-coeur-600); border: 2px solid var(--bc-blanc); }   /* bordé de blanc : il se voit sur le rouge de la boîte */ .onglet.stop.pose { outline: 3px solid var(--bc-jaune-300); }
.onglet.alerte { background: var(--bc-pique-700); } .onglet.alerte.pose { outline: 3px solid var(--bc-jaune-300); }
@keyframes pense { 50% { opacity: .35; } }
.pense { animation: pense 1s ease-in-out infinite; }
"""


CSS_AIDE = """
.aide { font-size: 16px; line-height: 1.55; color: var(--bc-tapis-900); }
.aide h1, .aide h2, .aide h3 { font-size: 16px; font-weight: 700; color: var(--bc-trefle-700); margin: 1.4em 0 .4em; line-height: 1.3; letter-spacing: normal; }
.aide > :first-child { margin-top: 0; }
.aide > h1:first-child, .aide > h2:first-child, .aide > h3:first-child { font-size: 18px; color: inherit; margin-top: 0; }   /* le titre de la section, comme celui des autres pages */
.aide p, .aide ul, .aide ol, .aide dl { margin: .6em 0; }
.aide ul { list-style: disc; padding-left: 1.4em; } .aide ol { list-style: decimal; padding-left: 1.4em; }
.aide li { margin-bottom: .4em; } .aide dt { font-weight: 600; margin-top: .7em; } .aide dd { margin: 0; }
.aide code { background: var(--bc-trefle-100); padding: .1em .35em; border-radius: 4px; font-size: var(--fs-liste); word-break: break-all; }
.aide .note { background: var(--bc-trefle-100); border-left: 4px solid var(--bc-trefle-700); padding: .7em 1em; margin: 1em 0; }
.aide h2 { font-size: 22px; color: var(--bc-tapis-900); margin: 0 0 .6em; }                  /* le titre de la page */
.aide h3 { font-size: 18px; margin-top: 1.8em; scroll-margin-top: 60px; }     /* une section : sous la barre du haut */
.aide p.intro { font-size: var(--fs-titre); color: var(--bc-tapis-900); }
.aide figure { margin: 1em 0 1.4em; }
.aide figure img { display: block; max-width: 100%; border: 1px solid var(--bc-tapis-200); border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.aide figcaption { font-size: var(--fs-liste); color: var(--bc-tapis-700); margin-top: .4em; }
.aide .etapes { counter-reset: e; list-style: none; padding-left: 0; }
.aide .etapes > li { counter-increment: e; position: relative; padding-left: 2.4em; margin-bottom: .8em; }
.aide .etapes > li::before { content: counter(e); position: absolute; left: 0; top: 0; width: 1.7em; height: 1.7em; border-radius: 50%;
  background: var(--bc-trefle-700); color: var(--bc-blanc); font-weight: 700; font-size: 14px; display: flex; align-items: center; justify-content: center; }
.aide .astuce { background: var(--bc-jaune-50); border-left: 4px solid var(--bc-jaune-400); padding: .7em 1em; margin: 1em 0; }
@media (max-width: 1000px) { .sur-page-place { display: none; } }   /* une fenêtre étroite : le texte d'abord */
.sur-page-place { width: 220px; align-self: stretch; }       /* la place de la colonne ; la liste, elle, reste fixe à l'écran */
.sur-page { position: fixed; top: 64px; width: 220px; max-height: calc(100vh / var(--zoom, 1) - 90px); overflow-y: auto; background: transparent; }
.aide figure img { cursor: zoom-in; }
.image-aide-grande { position: fixed; inset: 0; z-index: 9999; background: rgba(20,20,20,.82); display: flex; align-items: center;
  justify-content: center; cursor: zoom-out; padding: 24px; }
.image-aide-grande img { max-width: 100%; max-height: 100%; border-radius: 8px; background: var(--bc-blanc); box-shadow: 0 8px 30px rgba(0,0,0,.4); }
.sur-page a { display: block; font-size: var(--fs-liste); line-height: 1.35; color: var(--bc-tapis-800); text-decoration: none; padding: 5px 0 5px 12px;
  border-left: 2px solid var(--bc-pique-100); }
.sur-page a:hover { color: var(--bc-trefle-700); }
.sur-page a.lue { color: var(--bc-trefle-700); font-weight: 600; border-left-color: var(--bc-trefle-700); }
"""


def texte_aide():
    """Le corps de help/index.html, affiché dans la fenêtre ; son propre style est remplacé par CSS_AIDE."""
    try:
        t = open(AIDE, encoding="utf-8").read()
    except OSError:
        return "<p>Le fichier d'aide est introuvable.</p>"
    return re.search(r"<body>(.*)</body>", t, re.S)[1] if "<body>" in t else t


def categories_aide():
    """La catégorie de chaque page de l'aide, dans l'ordre des pages : le dernier <h1 class="categorie"> qui la précède
    (Démarrer, Revoir un tournoi, S'entraîner, Faire cours, Réglages et aide : l'utilisateur, 2026-11-12)."""
    corps = re.sub(r"<!--.*?-->", "", texte_aide(), flags=re.S)
    cat, out = "", []
    for m in re.finditer(r'<h1 class="categorie">(.*?)</h1>|<h2>', corps, re.S):
        if m[1] is not None: cat = re.sub(r"<[^>]+>", "", m[1]).strip()
        else: out.append(cat)
    return out


def sections_aide():
    """L'aide en pages : [(titre, html, [(ancre, titre de section)])], une page par <h2>, ses sections (<h3>) listées
    dans « Sur cette page », à droite. Les images (help/images/…) sont servies sous /aide-images/. Sans <h2> : une page."""
    corps = re.sub(r"<!--.*?-->", "", texte_aide(), flags=re.S).replace('src="images/', 'src="/aide-images/')
    corps = re.sub(r'<h1 class="categorie">.*?</h1>', "", corps, flags=re.S)   # les catégories rangent la barre de gauche
    out = []
    for k, bloc in enumerate(re.split(r"(?=<h2>)", corps)):
        m = re.match(r"<h2>(.*?)</h2>", bloc, re.S)
        if not m: continue
        titre = re.sub(r"<[^>]+>", "", m[1]).strip()
        sections = []
        def ancre(t, k=k):                              # l'id écrit dans l'aide (AIDE_POUR s'en sert), sinon un id fait
            sections.append((t[1] or f"aide-{k}-{len(sections)}", re.sub(r"<[^>]+>", "", t[2]).strip()))
            return f'<h3 id="{sections[-1][0]}">{t[2]}</h3>'
        html_page = re.sub(r'<h3(?: id="([^"]+)")?>(.*?)</h3>', ancre, bloc, flags=re.S)
        out.append((titre, html_page, sections))
    return out or [("Aide", corps, [])]


# L'aide selon la page, comme une table route → sujet : (onglet, page ou entrée, précision) → la section de l'aide (son id
# dans help/index.html). L'Aide du haut ouvre la section de la page où l'on est (section_aide, la clé la plus précise
# d'abord), les « ? » à côté des titres aussi. tests/test_app.py vérifie que chaque section existe dans l'aide.
AIDE_POUR = {
    ("Fichier",): "importer", ("Fichier", "nouveau", "bws"): "importer", ("Fichier", "nouveau", "pbn"): "importer-ailleurs",
    ("Fichier", "nouveau", "themes"): "themes", ("Fichier", "ouvrir"): "retrouver", ("Fichier", "infos"): "infos",
    ("Fichier", "exporter"): "exporter", ("Fichier", "dossier"): "fichiers",
    ("Donnes",): "donne", ("Donnes", "seance"): "parcours", ("Donnes", "joueurs"): "votre-table", ("Donnes", "saisie"): "taper",
    ("Jouer",): "encherir", ("Jouer", "options"): "encherir", ("Jouer", "classement"): "classement",
    ("Jouer", "encheres"): "encherir", ("Jouer", "carte"): "jouer-carte", ("Jouer", "defense"): "defendre",
    ("Jouer", "revoir"): "revoir", ("Jouer", "demo"): "cours",
    ("Analyse",): "lire-analyse", ("Analyse", "standard"): "lancer-analyse", ("Analyse", "expert"): "expert",
    ("Rapports",): "rapport", ("Rapports", "creer"): "rapport", ("Rapports", "seance"): "perdu",
    ("Réglages",): "reglages", ("Réglages", "affichage"): "taille", ("Réglages", "nom"): "votre-table",
    ("Réglages", "dossiers"): "reglages", ("Réglages", "sauvegarde"): "sauvegarde", ("Réglages", "maj"): "mise-a-jour",
    ("Réglages", "contact"): "signaler", ("Réglages", "expert"): "questions-expert", ("Système",): "systeme-robots", ("Fichier", "infos", "brouillon"): "brouillon", ("Système", "systeme"): "systeme",
}


NOUVEAUTES = os.path.join(rapport.RACINE, "help", "nouveautes.html")


def nouveautes(depuis, jusqua):
    """[(version, html)] des sections de help/nouveautes.html plus récentes que depuis, jusqu'à jusqua comprise."""
    return [(v, h) for v, _, h in toutes_nouveautes() if maj.cle(depuis) < maj.cle(v) <= maj.cle(jusqua)]


def toutes_nouveautes():
    """[(version, date « AAAA-MM-JJ » ou "", html)] de help/nouveautes.html, la plus récente d'abord."""
    try:
        t = open(NOUVEAUTES, encoding="utf-8").read()
    except OSError:
        return []
    out = [(v, d, h.strip()) for v, d, h in
           re.findall(r'<section data-version="([^"]+)"(?: data-date="([^"]*)")?>(.*?)</section>', t, re.S)]
    return sorted(out, key=lambda x: maj.cle(x[0]), reverse=True)


def date_en_mots(iso):
    """« 2026-11-12 » → « 12 novembre 2026 »."""
    try:
        d = datetime.date.fromisoformat(iso)
        return f"{'1er' if d.day == 1 else d.day} {fichiers.MOIS[d.month - 1]} {d.year}"
    except (ValueError, TypeError):
        return ""


def rappel_sauvegarde(n_seances, maintenant=None):
    """La phrase qui rappelle de sauvegarder (dernière sauvegarde il y a plus de 30 jours, ou jamais avec 3 séances ou
    plus), sinon None."""
    le = lire_etat().get("sauvegarde_le")
    maintenant = maintenant or datetime.datetime.now()
    if not le:
        return "Vos séances n'ont jamais été sauvegardées." if n_seances >= 3 else None
    try:
        jours = (maintenant - datetime.datetime.fromisoformat(le)).days
    except ValueError:
        return None
    if jours <= 30: return None
    return f"Votre dernière sauvegarde date de {jours // 7} semaines." if jours < 90 else \
        f"Votre dernière sauvegarde date de {jours // 30} mois."


def section_aide(*cle):
    """La section de l'aide pour cette page : la clé entière, sinon de moins en moins précise, sinon le début de l'aide."""
    for k in range(len(cle), 0, -1):
        if tuple(cle[:k]) in AIDE_POUR: return AIDE_POUR[tuple(cle[:k])]
    return "premiere-fois"


def titre_page(texte, ancre, classes="font-bold titre-page"):
    """Le titre d'une page et, à côté, un petit « ? » bleu qui ouvre l'aide à la bonne section (l'événement « aide »)."""
    with ui.row().classes("items-center gap-1 no-wrap"):
        ui.label(texte).classes(classes)
        ui.button(icon="help_outline", on_click=lambda: ui.run_javascript(f"emitEvent('aide', {json.dumps(ancre)})")) \
            .props("flat round dense size=sm").style("color:var(--bc-pique-600)").tooltip("L'aide de cette page")


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


TEMPS = "temps-de-calcul.txt"                              # dans le dossier des rapports, comme derniere-erreur.txt


def noter_temps(quoi, secondes, detail=False):
    """Une ligne dans temps-de-calcul.txt : ce qui a pris combien de temps sur cet ordinateur (l'utilisateur, 2026-11-18 :
    les ordinateurs Windows du club sont bien plus lents ; un membre peut joindre ce fichier). Seulement des durées,
    jamais une main ni un nom ; les 300 dernières lignes."""
    try:
        import platform
        f_ = os.path.join(rapport.RAPPORTS, TEMPS)
        os.makedirs(rapport.RAPPORTS, exist_ok=True)
        lignes = open(f_, encoding="utf-8").read().splitlines() if os.path.exists(f_) else []
        machine = f"{platform.system()} {platform.release()}, {os.cpu_count() or '?'} cœurs"
        if not lignes or not lignes[0].startswith("Bridge Coach"):
            lignes = [f"Bridge Coach {maj.version_locale()} · {machine}"] + lignes
        else:
            lignes[0] = f"Bridge Coach {maj.version_locale()} · {machine}"
        lignes.append(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} · {quoi}" + ("" if detail else " · " + f"{secondes:.1f} s".replace(".", ",")))
        lignes = lignes[:1] + lignes[1:][-300:]
        with open(f_, "w", encoding="utf-8") as f: f.write("\n".join(lignes) + "\n")
    except Exception:
        pass                                               # jamais d'arrêt pour un journal


def demarrer_travail(t, args):
    env = dict(os.environ)                                 # -X utf8 : Windows n'écrit pas en UTF-8 par défaut
    opts = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == "win32" else {"start_new_session": True}
    t.debut = time.monotonic(); t.n_donnes = 0
    t.proc = subprocess.Popen([sys.executable, "-I", "-X", "utf8", "-u"] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8",
                              errors="replace", env=env, cwd=rapport.RACINE, **opts)
    threading.Thread(target=suivre, args=(t.proc, t), daemon=True).start()


def lancer(chemin):
    """L'analyse standard seulement (rapport.py --analyse-seule) : les PDF se font dans l'onglet Rapports."""
    T.__init__(1.0); T.genre = "analyse"; T.seance = chemin; T.texte = "Lecture du fichier"
    demarrer_travail(T, [os.path.join(ICI, "rapport.py"), chemin, "--analyse-seule"])


def niveau_rapport():
    """Rapports, « L'analyse » (etat.json rapport_niveau) : faits, coach ou expert. Avant la 1.11, la case « Inclure
    l'avis de l'expert » (avec_expert) : décochée, c'était le coach."""
    e = lire_etat()
    # depuis le 13/11 : une seule case, « Sans l'analyse du coach ni de l'expert » ; sinon l'analyse la plus complète
    # (rapport.py prend le coach seul quand l'expert n'a rien écrit). Un ancien choix « coach » devient l'analyse.
    return "faits" if e.get("rapport_niveau") == "faits" else "expert"


def avec_expert():
    """L'avis de l'expert dans les PDF (« Imprimer cette donne » suit aussi le choix de l'onglet Rapports)."""
    return niveau_rapport() == "expert"


def pages_rapport():
    """Rapports, « Pages en plus » (etat.json rapport_pages) : champ, parcours, synthese, noms, comparaison."""
    p = lire_etat().get("rapport_pages")
    return [x for x in p if x in dict((k, 1) for k, _, _ in PAGES_EN_PLUS)] if isinstance(p, list) else list(PAGES_DEFAUT)


def args_rapports(quelles="toutes", nums=()):
    """Les options de rapport.py --rapports pour les choix de l'onglet Rapports : les donnes (toutes, « revoir » ou
    « choisir » avec leurs numéros), le niveau et les pages en plus (etat.json)."""
    a = [f"--niveau={niveau_rapport()}", "--pages=" + ",".join(pages_rapport())]
    if quelles == "revoir": a.append("--a-revoir")
    elif quelles == "choisir" and nums: a.append("--donnes=" + ",".join(str(n) for n in nums))
    return a


def lancer_rapports(chemin, quelles="toutes", nums=()):
    """Les PDF seulement, depuis les analyses enregistrées (rapport.py --rapports) : la barre avance rapport par rapport."""
    T.__init__(0.0, "Écriture des rapports"); T.genre = "rapports"; T.seance = chemin; T.texte = "Écriture des rapports"
    demarrer_travail(T, [os.path.join(ICI, "rapport.py"), chemin, "--rapports"] + args_rapports(quelles, nums))


def lancer_import(chemin, nom=None, titre=None):
    """L'import seul (rapport.py --importer), sous le nom et le titre choisis (--nom=, --titre=)."""
    I.__init__(1.0, "Import"); I.seance = chemin; I.texte = f"Import de {os.path.basename(chemin)}"
    demarrer_travail(I, [os.path.join(ICI, "rapport.py"), chemin, "--importer"] + ([f"--nom={nom}"] if nom else [])
                     + ([f"--titre={titre}"] if titre else []))


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
            _HEURES[c] = heure_de(d)
        return _INFOS[cle]
    except Exception:
        return date_lisible(c), ""


_HEURES = {}


def heure_de(d):
    """L'heure d'une séance, « 14:01 » : celle du tournoi (session.heure, d'un .bws) ; pour une séance faite dans Bridge
    Coach (entraînement, saisie, Brouillon), l'heure où elle a été créée ; sinon "" (l'utilisateur, 2026-11-18 : deux
    entraînements du même jour se distinguent)."""
    h = d.get("session", {}).get("heure")
    if h: return h
    if d.get("source", {}).get("type") in ("entrainement", "saisie", "brouillon"):
        c = (d.get("fichier") or {}).get("cree_le") or ""
        if "T" in c: return c.split("T")[1][:5]
    return ""


def heure_seance(c):
    """heure_de pour un fichier, lue avec infos_seance."""
    infos_seance(c)
    return _HEURES.get(c, "")


_RESUMES = {}


def resume_seance(c):
    """Ce que la liste d'Ouvrir une séance montre d'une séance, lu une fois par version du fichier : le nombre de donnes
    et de tables, l'analyse de l'expert, et votre % quand « Vous êtes » y joue (l'utilisateur, 2026-11-17 : retrouver
    sa séance d'un coup d'œil)."""
    try:
        qui = moi.nom() or lire_etat().get("mon_nom") or ""      # « Vous êtes », sinon « Votre nom » (Réglages)
        cle = (c, os.path.getmtime(c), qui)
        if cle not in _RESUMES:
            d = json.load(open(c, encoding="utf-8"))
            s = d.get("session") or {}
            donnes_ = [x for x in d.get("donnes") or [] if not x.get("a_completer")]
            pct = None
            for k in sorted(moi.paires(d, qui)) if qui else []:
                v = ((d.get("paires") or {}).get(k) or {}).get("pct")
                if isinstance(v, (int, float)): pct = v; break
            type_ = (d.get("source") or {}).get("type")
            titre = s.get("titre") or ""
            if not titre or re.match(r"Entraînement \d{4}-\d\d-\d\d$", titre):   # une ancienne séance : le titre proposé
                try: titre = fichiers.titre_propose(d, type_ or "")
                except Exception: titre = ""
            r = dict(titre=titre, court=titre_court(titre),donnes=len(donnes_), tables=s.get("tables") if type_ in ("bws", "feuille-de-route", "ffb-html", "ffb-pdf", "simulation") else None,
                     expert=bool(((d.get("analyses") or {}).get("expert") or {}).get("donnes")),
                     coach=bool(((d.get("analyses") or {}).get("standard") or {}).get("donnes")),
                     pct=pct, partenaire="", rang=None, paires=0, themes=s.get("themes") or [], moment=s.get("moment") or s.get("heure") or "",
                     marque=moi.MARQUES.get(moi.marque(d), "") if s.get("tables") else "",
                     modifie=(d.get("fichier") or {}).get("modifie_le") or "", rejouees=0)
            ps = d.get("paires") or {}
            mes = sorted(moi.paires(d, qui)) if qui else []
            if mes:                                        # votre partenaire, votre rang
                k = mes[0]; lic = moi.licence_de(qui)
                r["partenaire"] = next((j.get("nom") or j.get("initiales") or "" for j in (d.get("joueurs") or {}).get(k, [])
                                        if not moi.est(j, qui, lic)), "")
                cote = k[-2:] if k[-2:] in ("NS", "EO") else ""     # un Mitchell : deux classements, N-S et E-O
                pcts = [v.get("pct") for kk, v in ps.items() if isinstance(v.get("pct"), (int, float)) and kk.endswith(cote)]
                r["paires"] = len(pcts); r["cote"] = {"NS": " Nord-Sud", "EO": " Est-Ouest"}.get(cote, "")
                rg = (ps.get(k) or {}).get("rang")
                if isinstance(rg, (int, float)): r["rang"] = int(rg)
                elif pct is not None and pcts: r["rang"] = 1 + sum(1 for x in pcts if x > pct)
            try:
                es = jouer.lire_essais(base_seance(c))["donnes"]
                r["rejouees"] = sum(1 for v in es.values() if classement.dernier_fini(v))
            except Exception:
                pass
            _RESUMES[cle] = r
        return _RESUMES[cle]
    except Exception:
        return dict(titre="", court="", donnes=None, tables=None, expert=False, coach=False, pct=None, partenaire="", rang=None, paires=0,
                    themes=[], moment="", marque="", modifie="", rejouees=0)


_DATE_LONGUE = re.compile(r"\s*(?:\bdu\b|–|-)?\s*\b(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+\d{1,2}(?:er)?\s+"
                          r"(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4}",
                          re.IGNORECASE)


def titre_court(titre):
    """Le titre sans ce que la ligne d'Ouvrir une séance dit déjà (la date, le nombre de tables) :
    « Tournoi du vendredi 13 novembre 2026 (après-midi, 6 tables) » -> « Tournoi · après-midi »."""
    t = _DATE_LONGUE.sub("", titre or "")
    if t == (titre or ""): return titre or ""             # pas de date dans le titre : il reste tel quel
    t = t.replace(" – ", " · ")
    def parenthese(m):
        reste = [x.strip() for x in m[1].split(",") if x.strip() and "table" not in x]
        return (" · " + ", ".join(reste)) if reste else ""
    t = re.sub(r"\s*\(([^)]*)\)", parenthese, t)
    t = re.sub(r"\s{2,}", " ", t).strip(" –-·")
    return t or titre or ""


_TITRES_BWS = {}


def titre_bws(b):
    """(le titre lisible d'un tournoi Bridgemate, déjà importé ?), lu une fois par version du fichier ; le nom du
    fichier quand il ne se lit pas."""
    try:
        cle = (b, os.path.getmtime(b))
        if cle not in _TITRES_BWS:
            p = fichiers.proposer(b)
            _TITRES_BWS[cle] = (p["titre"], bool(p["deja"]))
        return _TITRES_BWS[cle]
    except (Exception, SystemExit):
        return os.path.basename(b), bool(deja_importe(b))


def deja_importe(bws):
    """Le .bc.json de ce fichier, s'il a déjà été importé (le nom du fichier d'origine gardé dans sa source, ou, pour
    une séance d'avant, le même nom) ; sinon None."""
    return fichiers.deja_importe(bws) or next((c for c in rapport.glob_seances(rapport.nom_seance(bws) + rapport.BC)), None)


def quand_iso(iso):
    """« 2026-11-12T07:53:32 » → « 12/11/2026 à 07:53 » ; rien sans date."""
    try:
        return datetime.datetime.fromisoformat(iso).strftime("%d/%m/%Y à %H:%M") if iso else ""
    except ValueError:
        return iso


def webview_save():
    """Le type « enregistrer sous » du dialogue de la fenêtre (pywebview, ancien et nouveau nom)."""
    import webview
    return webview.FileDialog.SAVE if hasattr(webview, "FileDialog") else webview.SAVE_DIALOG


def retenir_licence(*noms):
    """Retient la licence FFB des joueurs choisis (etat.json « licences », {nom: licence}) : moi.paires et
    moi.place_du_joueur les reconnaissent par elle. Aussi pour les noms déjà choisis avant la 1.9 (au lancement)."""
    noms = [n for n in noms if n]
    if not noms: return
    tous = moi.tous_les_joueurs(rapport.glob_seances("*" + rapport.BC))
    lic = dict(lire_etat().get("licences") or {})
    for n in noms:
        if tous.get(n): lic[n] = tous[n]
    if lic != (lire_etat().get("licences") or {}): ecrire_etat(licences=lic)


def url_expert():
    """L'adresse de l'outil d'IA (Réglages, L'expert), claude.ai par défaut."""
    return lire_etat().get("expert_url") or question_expert.ADRESSE


def nom_outil(url):
    """« https://claude.ai/new » → « claude.ai » : le site, pour le dire à l'écran."""
    from urllib.parse import urlparse
    return urlparse(url).netloc.replace("www.", "") or url


def prenom_expert():
    """Le prénom que l'expert peut employer : celui réglé (vide : aucun), sinon le prénom de « Votre nom »."""
    e = lire_etat()
    return e["expert_prenom"] if "expert_prenom" in e else question_expert.prenom_de(e.get("mon_nom") or "")


def montrer_fichier(chemin):
    """Le fichier, sélectionné dans le Finder (Mac) ou l'Explorateur (Windows)."""
    if sys.platform == "win32": subprocess.Popen(["explorer", "/select,", os.path.normpath(chemin)])
    else: subprocess.Popen(["open", "-R", chemin])


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


TAILLES = [(0.875, "Compacte"), (1.0, "Normale"), (1.25, "Grande")]   # Réglages, Taille du texte : le zoom de la page
# (l'utilisateur, 2026-11-17 : la taille normale est déjà grande ; une plus petite pour un petit écran, une plus grande ;
# « Très grande », 1,5, ne tenait pas sur un portable : lue comme « Grande »)


SEPARATEUR = "\u2014sep\u2014"                              # la ligne entre votre nom et les autres (options_joueurs)


def taille_texte():
    """La taille du texte choisie (etat.json « zoom ») : 0.875, 1 ou 1.25 ; l'ancienne « Très grande » (1.5) devient « Grande »."""
    z = lire_etat().get("zoom")
    if isinstance(z, (int, float)) and z > 1.25: return 1.25
    return z if z in [t for t, _ in TAILLES] else 1.0


VUL_TXT = {"Personne": "personne", "N-S": "Nord-Sud", "E-O": "Est-Ouest", "Tous": "tous"}


def seance_active():
    """La séance ouverte la dernière fois, si son fichier existe encore ; sinon None."""
    c = lire_etat().get("seance")
    return c if c and os.path.isfile(c) else None


def retenir(c):
    """La séance ouverte devient celle qu'on retrouve au prochain lancement."""
    ecrire_etat(seance=c)


def icone_panneau(cachee):
    """L'icône du bouton de la barre de gauche, comme celle de Claude : un carré arrondi, une colonne étroite à gauche,
    pleine quand la barre est montrée, vide quand elle est cachée (pas le ☰ d'un menu principal : l'utilisateur, 2026-11-13)."""
    plein = "" if cachee else "<rect x='4' y='5' width='5' height='14' rx='1' fill='currentColor' opacity='.35'/>"
    return ("<svg width='22' height='22' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' "
            "style='display:block'><rect x='3' y='4' width='18' height='16' rx='3'/>"
            f"<line x1='9.5' y1='4.5' x2='9.5' y2='19.5'/>{plein}</svg>")


def nom_html(nom, deux_lignes=False, droite=False, etat="", siege="", une_ligne=False):
    """Le nom d'un joueur près de ses cartes, discret (l'utilisateur, 2026-11-11 : pas de bandeau ni de photo) : une
    ligne en gris foncé."""
    import html as h_
    tete = f"<div class='siege-lbl'>{SIEGE[siege].upper()}</div>" if siege else ""   # la place, en gras, au-dessus du nom
    if une_ligne:                                        # le mort étalé en haut ou en bas : « OUEST Prénom NOM » sur une ligne,
        mots = (nom or "").split()                       # ses cartes centrées dessous ; le prénom d'abord, comme sur deux lignes
        k = next((i for i, m in enumerate(mots) if not m.isupper()), len(mots)) or 1
        nom = " ".join(mots[k:] + mots[:k])
        return (f"<div class='nom-joueur {etat}' style='text-align:center;white-space:nowrap'>"
                + (f"<span class='siege-lbl'>{SIEGE[siege].upper()}</span>" if siege else "")   # l'écart : le gap de .nom-joueur
                + f"{h_.escape(nom)}</div>")
    if deux_lignes:                                      # sur deux lignes : le prénom, puis le NOM (l'utilisateur, 2026-11-11)
        mots = (nom or "").split()
        k = next((i for i, m in enumerate(mots) if not m.isupper()), len(mots)) or 1
        bas, haut = " ".join(mots[:k]), " ".join(mots[k:])   # le prénom d'abord, le NOM dessous (se lit mieux : l'utilisateur)
        if not haut: haut, bas = bas, ""
        return (f"<div class='nom-joueur deux {etat}' style='text-align:{'right' if droite else 'left'}'>{tete}"
                + (f"<div>{h_.escape(haut)}</div>" if haut else "")
                + (f"<div>{h_.escape(bas)}</div>" if bas else "") + "</div>")
    return f"<div class='nom-joueur {etat}'>{h_.escape(nom or '')}</div>"


def joueur_jouer(data=None):
    """Option « Comme un joueur de la séance » : le nom choisi (etat.json joueur_jouer), sinon « Vous êtes », sinon
    « Votre nom »."""
    e = lire_etat()
    return e.get("joueur_jouer") or moi.nom() or e.get("mon_nom") or ""


def coach_arrete():
    """L'option de l'onglet Jouer : quand votre enchère ou votre carte n'est pas celle du coach, il vous arrête et vous
    dit la sienne et pourquoi, avant qu'elle soit jouée (l'utilisateur, 2026-11-18). Allumée par défaut."""
    return lire_etat().get("coach_arrete", True) is not False


def place_jouer():
    """L'option de l'onglet Jouer : la place que prend le joueur (jouer.PLACES), le déclarant par défaut."""
    m = lire_etat().get("place_jouer")
    return m if m in dict(jouer.PLACES) else "declarant"


def titre_fenetre(c):
    """« Bridge Coach – Tournoi du jeudi 5 novembre 2026 » : le titre de la séance, son nom de fichier quand elle n'en a
    pas ; sans séance, le nom du programme."""
    if not c: return TITRE
    t = fichiers.entete(c).get("session", {}).get("titre") if os.path.isfile(c) else None
    return f"{TITRE} – {t or os.path.basename(c)}"


def lancer_donnes(quotas):
    """quotas : [(thème, nombre de donnes)]."""
    D.__init__(1.0, "Création de la donne"); D.texte = "Préparation"
    demarrer_travail(D, [os.path.join(ICI, "donnes.py"), "--combiner"] + [f"{t}={k}" for t, k in quotas if k])


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
    if t is D and not proc.returncode and getattr(t, "debut", None):   # créer des donnes d'entraînement : le temps, par donne
        n = getattr(t, "n_donnes", 0) or 1
        noter_temps(f"Création de {n} donne{'s' if n > 1 else ''} d'entraînement (par donne)", (time.monotonic() - t.debut) / n)
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


AUTRE_FICHE = "Autre…"                      # Réglages › Votre système : écrire son propre choix


def rouge(t):
    """Cœurs et carreaux en rouge, pour le HTML."""
    return str(t).replace("♥", '<span style="color:var(--bc-coeur-600)">♥</span>').replace("♦", '<span style="color:var(--bc-coeur-600)">♦</span>')


def page_seance(data, c):
    """La séance, côté bridge (l'utilisateur, 2026-11-17 : « pas trop technique, pas de fichiers ») : son titre, quand,
    combien de tables et de donnes ; votre résultat et votre partenaire ; votre parcours ; le classement des paires ; la
    marque, corrigeable. Le fichier lui-même est dans Fichier, Infos."""
    s = data["session"]
    ui.label(s.get("titre") or f"Séance du {s['date']}").classes("font-bold titre-page")
    d0 = fichiers.date_de(data)
    quand = fichiers.date_longue(d0) if d0 else s.get("date", "")
    if s.get("moment"): quand += f", {s['moment']}"
    elif s.get("heure"): quand += " à " + str(s["heure"]).replace(":", " h ")
    faits = [quand]
    if s.get("tables"): faits.append(f"{s['tables']} tables" + (" en Mitchell" if s.get("mitchell") else ""))
    n_d = len(data["donnes"]); faits.append(f"{n_d} donne{'s' if n_d > 1 else ''}")
    ui.label(" · ".join(faits)).classes("text-base text-gray-700")
    if s.get("themes"): ui.label("Thèmes : " + ", ".join(s["themes"])).classes("text-base")
    if not s.get("tables"):
        ui.label("Des donnes d'entraînement : elles n'ont pas été jouées en tournoi.").classes("text-base text-gray-700")
    r = resume_seance(c)
    if r["pct"] is not None or r["partenaire"]:            # votre soirée, en une ligne
        h = "<b>Vous</b>" + (f" avec <b>{html_.escape(r['partenaire'])}</b>" if r["partenaire"] else "")
        if r["pct"] is not None: h += f" : <b>{r['pct']:.1f} %</b>".replace(".", ",")
        if r["rang"]: h += f", {r['rang']}{'re' if r['rang'] == 1 else 'e'}" + (f" sur {r['paires']} paires{r.get('cote', '')}" if r["paires"] else "")
        ui.html(f"<div style='font-size:var(--fs-titre);background:{moi.SURLIGNE};padding:8px 14px;border-radius:6px'>{h}</div>",
                sanitize=False).classes("mt-2")
    tours = moi.parcours(data)
    if tours:                                              # le mouvement : vos tours, tables et adversaires
        titre_section("Votre parcours")
        ui.table(columns=[{"name": k, "label": l, "field": k, "align": a} for k, l, a in
                          (("tour", "Tour", "right"), ("table", "Table", "right"), ("donnes", "Donnes", "left"),
                           ("adversaires", "Adversaires", "left"), ("pct", "Votre %", "right"))],
                 rows=tours, row_key="tour").props("flat dense").classes("text-base")
    classement_paires(data)
    if s.get("tables"):
        with ui.row().classes("items-center gap-3 mt-4"):   # lue à l'import, devinée sinon ; corrigeable ici
            ui.label("Marque").classes("text-base text-gray-700")
            choix_m = ui.toggle({"MP": "Match-points", "IMP": "IMP"}, value=moi.marque(data)).props("dense no-caps")
            devinee = ui.label("devinée d'après le nombre de tables").classes("text-base text-gray-600")
            devinee.set_visibility(not s.get("marque"))
            choix_m.on_value_change(lambda e: (changer_marque(c, e.value), devinee.set_visibility(False)))


def classement_paires(data):
    """Le classement de la séance : les paires par % (ou IMP), Nord-Sud et Est-Ouest à part en Mitchell ; la vôtre en
    jaune."""
    ps = data.get("paires") or {}
    if not ps or not any(isinstance(v.get("pct"), (int, float)) for v in ps.values()): return
    mes = {str(k) for k in moi.paires(data)}
    j = data.get("joueurs") or {}
    noms = lambda k: " – ".join(x.get("nom") or x.get("initiales", "") for x in j.get(k, [])) or (ps[k].get("nom") or k)
    cotes = [("NS", "Nord-Sud"), ("EO", "Est-Ouest")] if any(k.endswith(("NS", "EO")) for k in ps) else [("", "")]
    for cote, nom_c in cotes:
        ks = sorted((k for k in ps if k.endswith(cote) and isinstance(ps[k].get("pct"), (int, float))), key=lambda k: -ps[k]["pct"])
        if not ks: continue
        titre_section("Classement" + (f" {nom_c}" if nom_c else ""))
        h = ["<table style='border-collapse:collapse;font-size:var(--fs-texte)'><tr style='font-size:var(--fs-petit);color:var(--bc-tapis-700)'>"
             "<th style='text-align:right;padding:4px 10px'>Rang</th><th style='text-align:left;padding:4px 10px'>Paire</th>"
             "<th style='text-align:right;padding:4px 10px'>%</th></tr>"]
        for k in ks:
            rang = ps[k].get("rang") or (1 + sum(1 for x in ks if ps[x]["pct"] > ps[k]["pct"]))
            fond = f"background:{moi.SURLIGNE};" if k in mes else ""
            h.append(f"<tr style='{fond}border-top:1px solid var(--bc-tapis-100)'><td style='text-align:right;padding:4px 10px'>{rang}</td>"
                     f"<td style='padding:4px 10px'>{html_.escape(noms(k))}</td>"
                     f"<td style='text-align:right;padding:4px 10px'>{format(ps[k]['pct'], '.1f').replace('.', ',')} %</td></tr>")
        h.append("</table>")
        ui.html("".join(h), sanitize=False)


def changer_marque(c, marque):
    """La marque choisie sur la page Séance : gardée dans le .bc.json (session.marque, marque_choisie : un réimport la
    garde) ; les rapports la suivent à la prochaine création."""
    data = json.load(open(c, encoding="utf-8"))
    if (data.get("session") or {}).get("marque") == marque: return
    data["session"].update(marque=marque, marque_choisie=True)
    edition.enregistrer(c, data)
    ui.notify(f"Marque : {moi.MARQUES[marque]}. Les rapports la suivront à la prochaine création.")


def page_joueurs(data):
    titre_page("Joueurs", "votre-table")
    j = data.get("joueurs") or {}
    if not j:
        ui.label("Pas de joueurs dans cette séance : les donnes n'ont pas été jouées.").classes("text-base text-gray-700"); return
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
    return f'<div style="font-size:var(--fs-texte);line-height:1.35"><div style="color:var(--bc-tapis-700);font-weight:600;white-space:nowrap">{SIEGE[s]} · {d["hcp"][s]} H{don}</div>{lignes}</div>'


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


MANCHE = {"SA": 9, "♠": 10, "♥": 10, "♦": 11, "♣": 11}       # les levées d'une manche, par dénomination
FOND_MANCHE, FOND_CHELEM = "var(--bc-trefle-100)", "var(--bc-trefle-300)"


def dm_html(d):
    """Le double mort pour la barre de droite, sur toute sa largeur, comme la grille du PDF : levées par dénomination
    et par déclarant. Fond vert : une manche se gagne ; vert soutenu : un chelem ; cadre : le contrat du par."""
    if not d.get("dm"): return ""
    p = d.get("par") or {}
    par = (p["contrat"][1:].rstrip("X"), p.get("declarant")) if p.get("contrat") and p["contrat"] != "passe" else None
    cell = "padding:5px 0;text-align:center;border-top:1px solid var(--bc-pique-100)"
    def case(x, s):
        n = d["dm"][x][s]
        fond = FOND_CHELEM if n >= 12 else FOND_MANCHE if n >= MANCHE[x] else "var(--bc-pique-50)" if s in "NS" else ""
        cadre = ";box-shadow:inset 0 0 0 2px var(--bc-trefle-800);font-weight:700" if par == (x, s) else ""
        return f"<td style='{cell}{';background:' + fond if fond else ''}{cadre}'>{n}</td>"
    tete = "".join(f"<th style='padding:5px 0;text-align:center;font-weight:700'>{s}</th>" for s in ("Nord", "Sud", "Est", "Ouest"))
    corps = "".join(f"<tr><td style='{cell};font-weight:700'>{rouge(x)}</td>" + "".join(case(x, s) for s in "NSEO") + "</tr>"
                    for x in ("SA", "♠", "♥", "♦", "♣"))
    carre = lambda style: f"<span style='display:inline-block;width:11px;height:11px;border-radius:2px;vertical-align:-1px;margin:0 4px 0 0;{style}'></span>"
    legende = (f"<div style='font-size:var(--fs-texte);color:var(--bc-tapis-800);margin-top:4px;line-height:1.6'>{carre(f'background:{FOND_MANCHE}')}manche "
               f"&nbsp;{carre(f'background:{FOND_CHELEM}')}chelem &nbsp;{carre('box-shadow:inset 0 0 0 2px var(--bc-trefle-800)')}par</div>")
    return (f"<div style='font-size:var(--fs-texte);width:100%'><div style='font-weight:700;margin-bottom:4px'>Double mort</div>"
            f"<table style='width:100%;table-layout:fixed;border-collapse:collapse;background:var(--bc-blanc);border:1px solid var(--bc-tapis-400);"
            f"border-radius:6px;overflow:hidden'><colgroup><col style='width:16%'/></colgroup>"
            f"<tr style='background:var(--bc-trefle-100)'><th></th>{tete}</tr>{corps}</table>{legende}</div>")


def page_dm_par(d, par=True):
    """Le double mort et le par d'une donne complète."""
    if d.get("dm"):
        ui.label("Double mort : levées par déclarant").classes("text-base font-bold mt-2")
        tete = "".join(f"<th style='padding:2px 10px'>{SIEGE[s]}</th>" for s in "NSEO")
        corps = "".join(f"<tr><td style='padding:2px 10px;font-weight:600'>{rouge(x)}</td>" +
                        "".join(f"<td style='padding:2px 10px;text-align:center'>{d['dm'][x][s]}</td>" for s in "NSEO") + "</tr>"
                        for x in ("SA", "♠", "♥", "♦", "♣"))
        ui.html(sanitize=False, content=f"<table style='font-size:var(--fs-texte);border-collapse:collapse'><tr><th></th>{tete}</tr>{corps}</table>")
    if par and d.get("par"):
        ui.html(sanitize=False, content=f"<div style='font-size:var(--fs-texte)'>{par_html(d)}</div>")


def titre_donne(d, centre=True, plus=""):
    """La ligne de titre d'une donne, la même dans Donnes, Jouer et Analyse (l'utilisateur, 2026-11-17) : « Donne 1 »
    en gras, puis « Donneur : Nord · Vulnérabilité : personne » ; plus : un complément (le thème). Centrée au-dessus de
    la table de Jouer et, à la même place, au-dessus de la donne dans Donnes et Analyse (l'utilisateur, 2026-11-17 :
    « au même endroit sur chaque page ») ; centre=False la met à gauche."""
    with ui.row().classes("w-full gap-x-4 gap-y-1 items-baseline " + ("justify-center" if centre else "")):   # se replie, texte grand
        ui.label(f"Donne {d['n']}").classes("font-bold titre-page whitespace-nowrap")
        ui.html(f"<div style='font-size:var(--fs-titre);text-align:center'><span style='white-space:nowrap'>Donneur : <b>{SIEGE[d['donneur']]}</b></span> · "
                f"<span style='white-space:nowrap'>Vulnérabilité : <b>{VUL_TXT.get(d.get('vul'), d.get('vul', ''))}</b></span>{plus}</div>", sanitize=False)


def page_donne(d, mes=frozenset(), tour="", reco=None):
    """Une donne dans l'onglet Donnes : les mains et les tables ; le nom, le donneur, la vulnérabilité et le par sont
    dans la barre de droite. Le double mort est dans l'onglet Analyse. mes : vos paires (moi.paires), dont la ligne est
    surlignée. tour : « Tour 1 · table 4 · … » (moi.tour_de) quand la séance décrit son mouvement. reco : le contrat
    recommandé (comparer.table_recommandee), rangé parmi les tables sur fond vert pâle."""
    titre_donne(d, plus=f" · Thème : <b>{html_.escape(str(d['theme']))}</b>" if d.get("theme") else "")
    mains_grille(d)
    if d.get("origine"):                                   # une donne du Brouillon (ou d'une séance faite avec lui) : d'où elle vient
        o = d["origine"]
        ui.html(f"<div style='font-size:var(--fs-texte);color:var(--bc-tapis-700)'>Venue de la donne {o.get('n')} de <b>{html_.escape(str(o.get('titre', '')))}</b>"
                + (f" ({o['date']})" if o.get("date") else "") + "</div>", sanitize=False).classes("mt-2")
    if tour: ui.label(tour).classes("text-base text-gray-700 mt-2")
    if d.get("tables"):
        ui.label("Aux tables").classes("text-base font-bold mt-2")
        rang = moi.votre_rang(d["tables"], mes, lambda t: f"{t['contrat']} {SIEGE.get(t['declarant'], t['declarant'])} {t['resultat']}".strip())
        if rang: ui.html(f"<div style='font-size:var(--fs-texte);background:{moi.SURLIGNE};padding:2px 6px;border-radius:4px'>{rouge(rang)}</div>", sanitize=False)
        tableau_resultats(d, mes, reco)
        if any(x.get("encheres") for x in d["tables"]):
            ui.label("Les enchères aux tables").classes("text-base font-bold mt-2")
            encheres_tables(d)


def tableau_resultats(d, mes, reco):
    """Les tables, du meilleur résultat au moins bon vu de votre camp ; votre ligne en jaune, le contrat recommandé
    (reco) en vert pâle à sa place."""
    rows = [{"k": str(i), "table": str(x.get("table", "")), "ns": x.get("nom_ns") or x.get("paire_ns", ""),
             "eo": x.get("nom_eo") or x.get("paire_eo", ""), "contrat": rouge(x.get("contrat", "")),
             "decl": SIEGE.get(x.get("declarant"), x.get("declarant") or ""), "res": x.get("resultat", ""),
             "entame": rouge(x.get("entame") or ""), "score": f"{x['score_ns']:+d}" if isinstance(x.get("score_ns"), int) else "",
             "pct": f"{x['pct_ns']:.0f} %" if x.get("pct_ns") is not None else "",
             "moi": moi.a_joue(x, mes), "reco": bool(x.get("recommande"))}
            for i, x in enumerate(moi.ordre(d["tables"] + ([reco] if reco else []), mes))]   # le meilleur d'abord, vu de votre camp
    for x in rows:
        if x["reco"]: x.update(table="", ns="Recommandé", eo="")   # « Recommandé » seul, comme dans les PDF
    # des titres courts : le tableau tient en entier en 15 px
    cols = [("table", "Table"), ("ns", "N-S"), ("eo", "E-O"), ("contrat", "Contrat"), ("decl", "Décl."),
            ("res", "Rés."), ("entame", "Entame"), ("score", "Score N-S")] + \
           ([("pct", "% N-S")] if len(d["tables"]) > 2 else [])   # le recommandé : son % face aux tables
    tb = ui.table(columns=[{"name": k, "label": l, "field": k, "align": "left"} for k, l in cols], rows=rows, row_key="k") \
        .props(f"flat dense :table-row-style-fn=\"r => r.moi ? 'background:{moi.SURLIGNE}' : r.reco ? 'background:{FOND_RECO};font-style:italic' : ''\"").classes("w-full")   # votre table
    for k in ("contrat", "entame"):                         # cœurs et carreaux en rouge, comme dans le PDF
        tb.add_slot(f"body-cell-{k}", '<q-td :props="props"><span v-html="props.value"></span></q-td>')


def page_classement(c, data, aller_donne):
    """Le classement du tournoi rejoué (onglet Jouer, entrée Classement) : la ligne de la séance d'abord, en grand, puis
    donne par donne votre contrat, votre résultat à la carte, votre score, votre % (ou vos IMP) et le meilleur de la
    salle ; enfin les paires du club avec vous à votre place. Un clic sur une donne l'ouvre pour la rejouer."""
    cl = classement.classement(data, jouer.lire_essais(base_seance(c)))
    imp_ = cl["marque"] == "IMP"
    titre_page("Classement du tournoi rejoué", "classement")
    if not cl["a_compter"]:
        ui.label("Cette séance n'a pas de résultats de club : il n'y a pas de classement à faire.").classes("text-base text-gray-700")
        return
    # la même allure que Jouer (l'utilisateur, 2026-11-11) : des cartes blanches arrondies, le vert pour votre réussite,
    # le rouge pour ce qui est sous la moyenne (comme les levées de votre camp et de l'autre sur la table)
    bon = lambda v: v is not None and (v > 0 if imp_ else v >= 50)
    teinte = lambda v: "var(--bc-trefle-700)" if bon(v) else "var(--bc-coeur-600)"
    with ui.column().classes("gap-1 rounded-xl border border-gray-200 bg-white px-4 py-3 my-2 max-w-4xl"):
        if cl["rejouees"]:
            tot = cl.get("total")
            ui.label(classement.ligne_seance(cl)).style(f"font-size:var(--fs-ecran);font-weight:700;color:{teinte(tot) if tot is not None else 'var(--bc-tapis-900)'}")
        else:
            ui.label("Aucune donne rejouée jusqu'au bout pour l'instant.").style("font-size:var(--fs-grand);font-weight:700;color:var(--bc-tapis-900)")
            premiere_ = next((x["n"] for x in cl["lignes"] if x["etat"] == "a_rejouer"), None)
            if premiere_ is not None:                      # une invitation à commencer (l'utilisateur, 2026-11-11)
                ui.button(f"Commencer par la donne {premiere_}", icon="arrow_forward",
                          on_click=lambda n=premiere_: aller_donne(f"d{n}")).props("unelevated no-caps").classes("text-base mt-1")
        reste = cl["a_compter"] - cl["rejouees"]
        ui.label(f"Toutes les donnes rejouées ({cl['rejouees']})." if cl["complet"] else
                 f"{cl['rejouees']} donne{'s' if cl['rejouees'] > 1 else ''} rejouée{'s' if cl['rejouees'] > 1 else ''} sur "
                 f"{cl['a_compter']} : classement provisoire, encore {reste} à rejouer.").classes("text-base text-gray-700")
    ui.label("Chaque donne compte quand vous l'avez enchérie puis jouée jusqu'à la dernière levée (une passe générale "
             "compte aussi) ; c'est le dernier essai fini qui compte. " +
             ("Vos IMP se comptent contre la moyenne des tables du club (le datum), votre total par donne face à celui des paires."
              if imp_ else "Votre % se compte face aux tables du club, comme Bridgemate compte les points de match.") +
             " Un clic sur une donne l'ouvre.").classes("text-base text-gray-700 max-w-3xl")
    def contrat_txt(x):
        if x.get("contrat") == "passe": return "passe"
        return rouge(f"{x['contrat']} {SIEGE.get(x.get('declarant'), x.get('declarant') or '')}")
    rows = []
    for x in cl["lignes"]:
        r = dict(k=str(x["n"]), n=f"Donne {x['n']}", place="", contrat="", res="", score="", val="", meilleur="", fait=x["etat"] == "rejouee")
        if x["etat"] == "rejouee":
            m = x["meilleur"]
            r.update(place=SIEGE.get(x["siege"], x["siege"]), contrat=contrat_txt(x), res=x["resultat"].replace("-", "−"),
                     score=f"{x['score']:+d}".replace("-", "−"),
                     val=(f"<b style='color:{teinte(x['imp'] if imp_ else x['pct'])}'>"
                          + (f"{x['imp']:+d}".replace("-", "−") if imp_ else f"{classement.fr(x['pct'], 0)} %") + "</b>"),
                     meilleur=f"{contrat_txt(m)} {m['resultat']} ({m['score']:+d})".replace("-", "−"))
        elif x["etat"] == "a_rejouer":
            r.update(place="à rejouer")
        else:
            r.update(place="pas de table de club")
        rows.append(r)
    cols = [("n", "Donne"), ("place", "Votre place"), ("contrat", "Votre contrat"), ("res", "Rés."), ("score", "Votre score"),
            ("val", "IMP" if imp_ else "%"), ("meilleur", "Meilleur de la salle")]
    with ui.element("div").classes("w-full max-w-4xl rounded-xl border border-gray-200 bg-white p-2"):
      tb = ui.table(columns=[{"name": k, "label": l, "field": k, "align": "left"} for k, l in cols], rows=rows, row_key="k") \
        .props("flat dense :table-row-style-fn=\"r => r.fait ? 'cursor:pointer' : 'cursor:pointer;color:var(--bc-tapis-600);font-style:italic'\"") \
        .classes("w-full max-w-4xl classement")
    for k in ("contrat", "meilleur", "val"):
        tb.add_slot(f"body-cell-{k}", '<q-td :props="props"><span v-html="props.value"></span></q-td>')
    tb.on("rowClick", lambda e: aller_donne(f"d{e.args[1]['k']}"))
    if cl["paires"]:
        ui.label("Les paires du club" + (" (IMP par donne)" if imp_ else "")).classes("text-base font-bold mt-4")
        lignes = []
        for i, p in enumerate(cl["paires"]):                # le rang avec vous parmi elles : 1 + celles devant
            rang = 1 + sum(1 for q in cl["paires"] if q["valeur"] > p["valeur"] + 1e-9)
            v = (("+" if p["valeur"] >= 0 else "−") + classement.fr(abs(p["valeur"]), 2)) if imp_ else f"{classement.fr(p['valeur'])} %"
            lignes.append(dict(k=str(i), rang=classement.rang_txt(rang), nom=p["nom"] + (" (votre paire ce soir-là)" if p["la_votre"] else ""),
                               val=v, vous=p["vous"], la_votre=p["la_votre"]))
        with ui.element("div").classes("max-w-xl rounded-xl border border-gray-200 bg-white p-2"):
          ui.table(columns=[{"name": "rang", "label": "Rang", "field": "rang", "align": "left"},
                          {"name": "nom", "label": "Paire", "field": "nom", "align": "left"},
                          {"name": "val", "label": "IMP par donne" if imp_ else "%", "field": "val", "align": "left"}],
                 rows=lignes, row_key="k") \
            .props(f"flat dense :table-row-style-fn=\"r => r.vous ? 'background:{moi.SURLIGNE};font-weight:700' : r.la_votre ? 'font-weight:700' : ''\"") \
            .classes("max-w-xl classement")


def encheres_tables(d):
    """Les enchères des tables ; des tables aux mêmes enchères n'en font qu'une grille, « Tables 1, 2, 3, 4 », avec le
    résultat de chacune dessous, comme le PDF (l'utilisateur, 2026-11-17)."""
    groupes = {}
    for x in d["tables"]:
        if x.get("encheres"): groupes.setdefault(tuple(x["encheres"]), []).append(x)
    with ui.row().classes("gap-6 items-start"):
        for xs in groupes.values():
            ui.html(encheres_html(d, xs[0]) if len(xs) == 1 else encheres_groupe_html(d, xs), sanitize=False)


# ---------------------------------------------------------------- l'analyse, dans l'onglet Analyse
_ANALYSES = {}
FOND_RECO = "var(--bc-trefle-100)"                                      # la ligne du contrat recommandé (comme dans les PDF)


def recommandee(c, d):
    """Le contrat recommandé de la donne d comme une ligne des résultats : l'expert s'il l'a analysée, sinon le
    programme ; None sans analyse."""
    import comparer                                        # tardif : comparer charge reportlab
    std, exp = lire_analyses(c)
    for an in (exp, std):
        a = (an or {}).get("donnes", {}).get(str(d["n"]))
        if a and a.get("enc"): return comparer.table_recommandee(d, a)
    return None


def base_seance(c):
    """Le chemin d'une séance sans son extension : <dossier>/<nom>."""
    return c[:-len(rapport.BC)] if c.endswith(rapport.BC) else c[:-len(rapport.ANCIEN)] if c.endswith(rapport.ANCIEN) else c


def lire_analyses(c):
    """(analyse du programme, analyse de l'expert) de la séance, rangées dans son .bc.json ("analyses"), ou None."""
    try:
        cle = (c, os.path.getmtime(c))
        if cle not in _ANALYSES:
            ans = json.load(open(c, encoding="utf-8")).get("analyses") or {}
            _ANALYSES.clear(); _ANALYSES[cle] = tuple(ans.get(q) for q in rapport.ANALYSES)
        return _ANALYSES[cle]
    except (OSError, ValueError, TypeError):
        return None, None


def fait_le(an):
    """« 02/11/2026 à 20:49 » : quand l'analyse a été faite (ou importée), ou « – »."""
    try:
        return datetime.datetime.fromisoformat(an["fait_le"]).strftime("%d/%m/%Y à %H:%M")
    except (KeyError, TypeError, ValueError):
        return "–"


def quand(f):
    """« 02/11/2026 à 20:49 » : la date du fichier."""
    return datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime("%d/%m/%Y à %H:%M")


def page_analyse_resume(data, an, expert):
    """La page « Analyse standard » ou « Analyse expert » : ce qui existe, sur combien de donnes, et de quand."""
    n = len(data["donnes"])
    k = sum(1 for x in (an or {}).get("donnes", {}).values() if x.get("enc"))
    if expert:
        lignes = [("État", f"{k} donnes sur {n} ; elle l'emporte sur l'analyse du coach, donne par donne" if an
                   else "aucune analyse de l'expert pour cette séance")]
    else:
        lignes = [("État", f"{k} donnes sur {n}" if an else "pas encore faite : « Lancer l'analyse »")]
    if an:
        lignes += [("Faite le", fait_le(an)), ("Système", an.get("systeme", "sef-2024"))]
    with ui.grid(columns="auto 1fr").classes("gap-x-6 gap-y-1 text-base"):
        for a, b in lignes:
            ui.label(a).classes("text-gray-700"); ui.label(b).classes("break-all")
    if expert:
        ui.label("L'analyse de l'expert est rédigée par Claude, d'après les règles du projet ; le programme ne la modifie "
                 "jamais.").classes("text-base text-gray-700")
    else:
        ui.label("« Lancer l'analyse » refait l'analyse du coach ; vous la lisez ici, donne par donne. Les rapports PDF "
                 "se font ensuite dans l'onglet Rapports.").classes("text-base text-gray-700")


# ---------------------------------------------------------------- l'analyse de l'expert, demandée à Claude sur le web
POUR_CLAUDE = [("systems/sef-2024/systeme.md", "systeme.md"), ("systems/sef-2024/conventions.md", "conventions.md"),
               ("systems/conventions/blackwood-3041.md", "blackwood-3041.md"), ("systems/conventions/stayman.md", "stayman.md"),
               ("systems/conventions/texas.md", "texas.md"), ("systems/conventions/drury.md", "drury.md"),
               ("systems/sef-2024/entames.md", "entames.md"),
               ("systems/sef-2024/entames.yaml", "entames.yaml"), ("systems/technique/jeu-de-la-carte.md", "jeu-de-la-carte.md")]

CONSIGNE = """Tu es l'expert de Bridge Coach, un programme qui analyse les séances de bridge d'un club français.
Écris l'analyse experte de la séance du fichier joint, {nom}.ai.json, et rends-la dans un seul fichier
JSON à télécharger, nommé {nom}-expert.json. Réponds en français.

Le fichier joint rassemble tout :
- « seance » : la séance (mains, donneur, vulnérabilité, résultats et enchères de chaque table, double mort « dm », par) ;
  les joueurs n'y sont que par leurs initiales ;
- « analyse_standard » : l'analyse du programme, ton point de départ (même format que celui à rendre) ;
- « exemple_analyse » : une analyse experte complète d'une autre séance, le style et le niveau de détail attendus ;
- « documents » : systeme.md et les conventions (blackwood-3041.md, stayman.md, texas.md, drury.md), le système
  SEF 2024 joué ; entames.md et entames.yaml, les règles d'entame et de défense ; jeu-de-la-carte.md, la technique
  du déclarant ;
- « consigne » : ce texte.

Les règles, à suivre strictement :
1. Les enchères recommandées (« enc ») se choisissent à la table : chaque enchère d'après la main du joueur et les
   enchères précédentes seulement, comme un joueur à la table. Ne regarde ni les autres mains, ni le double mort
   (« dm »), ni le par, ni les résultats des tables. Ne choisis jamais entre deux enchères raisonnables parce que
   l'une réussit au double mort. Quand deux enchères se défendaient, « notes » le dit dans une phrase qui commence
   par « Décision serrée : », avec l'autre enchère et pourquoi celle choisie est préférée.
   Chaque enchère doit se lire comme la lirait un partenaire de club, pas seulement mener au bon contrat : fixe
   l'atout avant de nommer des contrôles (par exemple 1♥ – 2♦ – 2SA – 3♥, forcing, puis 4♣ / 4♦) ; une couleur
   nommée deux fois montre une longueur, jamais « fit et contrôle ». Quand tu gardes la séquence du coach
   (« analyse_standard »), vérifie-la enchère par enchère et réécris celle qu'un partenaire comprendrait mal.
2. Le système est celui de systeme.md. Une ligne marquée « (à confirmer) » ne s'emploie qu'en disant que le
   traitement est incertain.
3. L'entame et la défense (« entame », « defense ») viennent de la main de l'entameur et des enchères seulement,
   d'après entames.yaml et entames.md : jamais d'une simulation au double mort.
4. Le plan de jeu (« plan ») ne voit que les mains du déclarant et du mort, l'entame et les enchères.
5. Dans « plan » et « defense », garde le texte du programme (« analyse_standard ») tel quel, avec « Le conseil du
   coach » (c'est le programme qui parle : ne le change pas), puis ajoute <br/><b>Avis de l'expert :</b>. Ton avis est un
   commentaire du conseil du coach, pas un autre plan : commence par dire en une phrase si le coach a raison, puis
   complète ou corrige ce qu'il dit (« Le coach a raison : … », « Le coach oublie que … », « Le coach se trompe sur … »).
   Ce qu'il faut ajouter : une erreur de compte, une meilleure ligne, l'ordre de jeu, la main dangereuse, la défense qui
   bat la ligne (vérifie ton plan contre ta propre défense), un laisser-passer, une élimination, un squeeze ou un coup.
   Ne répète pas ce que le coach a dit. S'il a raison sur tout : « Le coach a raison. » suffit, avec au besoin le détail
   qui compte. Quand ton contrat n'est pas celui du programme (même joué par l'autre camp), garde quand même le conseil du
   coach tel quel : il parle de son contrat à lui. Ton avis le dit d'abord (« Le coach joue 4♥ ; je joue 3♥ : … »), juge
   ce qui reste vrai dans son conseil, puis donne seulement ce qui change pour ton contrat : le compte, l'ordre de jeu,
   l'impasse ou le coup qui compte, en quelques phrases ; jamais un plan complet qui répète le sien.
6. « notes » : l'avis de l'expert sur les enchères. « comm » : le commentaire après coup ; le double mort y est
   permis, pour dire ce que le contrat donne et ce qui aurait marché.
7. La marque de la séance est en « IMP » ou en « match-points » (« seance.session.marque » : {marque}). Juge les
   enchères et le jeu pour cette marque : en match-points, une levée de mieux compte autant qu'une manche, 3SA vaut
   souvent mieux que 4 en majeure, contrer une partielle adverse peut payer ; en IMP, assurer le contrat et demander la
   manche passent d'abord (le jeu de sécurité, les manches vulnérables).
8. Les joueurs : par leurs initiales seulement (« AB/CD »), jamais leur nom ; aucun nom de club. Les cartes en
   français : A R D V X ; les couleurs ♠ ♥ ♦ ♣, toujours devant les cartes (« ♣AR », « ♠R », jamais « AR♣ ») ;
   les sièges N, S, E, O.

Le format du fichier rendu (celui de « exemple_analyse ») :
{{"titre_pied": "Analyse des donnes – séance du {date} – Système SEF, marque {marque}",
 "systeme": "sef-2024",
 "note_encheres": "Enchères recommandées choisies à la table (sans double mort).",
 "donnes": {{"1": {{"mains": {{"N": "…", "E": "…", "S": "…", "O": "…"}},
                   "enc": [["–", "1♠", "passe", "2♦"], ["passe", "…", "…", "…"]],
                   "notes": "…", "entame": {{"joueur": "E", "carte": "♣R"}}, "defense": "…", "plan": "…", "comm": "…"}},
            "2": {{…}}}}}}
« mains » : les quatre mains de la donne, recopiées telles quelles de « seance » : l'import vérifie que l'analyse va
bien sur la donne qui a ces cartes (une séance du même tournoi, créée depuis un autre fichier, peut numéroter autrement).
« enc » : la grille Ouest, Nord, Est, Sud, une ligne de quatre par tour, « – » avant le donneur, « passe »,
« contre », « surcontre », « 1SA »… ; « entame.joueur » : N, E, S ou O. Une clé par donne, toutes les donnes.
L'entame part toujours du joueur à gauche du déclarant de « enc » (le premier de son camp à avoir nommé la dénomination
du contrat), et sa carte est dans la main de ce joueur : vérifie-le pour chaque donne, l'import refuse sinon.

Si la réponse est trop longue pour un seul message, fais les donnes par groupes (par exemple 1 à 8, puis 9 à 16…),
chaque groupe dans un fichier JSON complet au même format : ils s'importent l'un après l'autre.
"""


def nom_pour_claude(data):
    """Le nom donné à la séance chez Claude : « seance-du-2026-11-07 ». Rien du nom d'origine, qui peut contenir le
    numéro du club (les fichiers Bridgemate le portent)."""
    try:
        j, m, a = (data or {})["session"]["date"].split("/")
        return f"seance-du-{a}-{m}-{j}"
    except (KeyError, ValueError):
        return "seance"


def seance_pour_claude(data):
    """La séance telle qu'elle part chez Claude : sans les analyses, sans la source (nom du fichier d'origine), sans
    titre ; les joueurs par leurs initiales seulement (les noms complets restent sur l'ordinateur)."""
    out = {k: v for k, v in data.items() if k not in ("analyses", "source", "joueurs", "session", "fichier")}   # "fichier" : son journal nomme l'original
    out["session"] = {k: v for k, v in data.get("session", {}).items() if k in ("date", "tables", "sections", "mitchell")}
    out["session"]["marque"] = moi.MARQUES[moi.marque(data)]       # IMP ou match-points : l'expert juge pour cette marque
    out["joueurs"] = {k: [{"initiales": j.get("initiales", "")} for j in v] for k, v in data.get("joueurs", {}).items()}
    return out


def preparer_pour_claude(c):
    """Un seul fichier à donner à Claude, <dossier de travail>/pour-claude/<nom>/<seance-du-…>.ai.json : la
    séance sans les noms (seance_pour_claude), l'analyse standard, l'exemple, les documents du système et la consigne.
    Renvoie (dossier, consigne)."""
    data = lire_seance(c) or {}
    nom = nom_pour_claude(data)
    dossier = fichiers.dossier_claude(c)                  # par nom de fichier : deux « tournoi-jeudi » de dates différentes restent à part
    shutil.rmtree(dossier, ignore_errors=True); os.makedirs(dossier)
    consigne = CONSIGNE.format(nom=nom, date=data.get("session", {}).get("date", ""), marque=moi.MARQUES[moi.marque(data)])
    documents = {}
    for src, dst in POUR_CLAUDE:
        f = os.path.join(rapport.RACINE, src)
        if os.path.exists(f): documents[dst] = open(f, encoding="utf-8").read()
    ex = os.path.join(rapport.DONNEES, "documents", "exemple_analyse_2026-10-23.json")
    tout = {"consigne": consigne, "seance": seance_pour_claude(data),
            "analyse_standard": {k: v for k, v in (lire_analyses(c)[0] or {}).items() if k != "fait_le"},
            "exemple_analyse": json.load(open(ex, encoding="utf-8")) if os.path.exists(ex) else None,
            "documents": documents}
    with open(os.path.join(dossier, nom + ".ai.json"), "w", encoding="utf-8") as f:
        json.dump(tout, f, ensure_ascii=False, indent=1)
    return dossier, consigne


def importer_expert(c, chemin):
    """Range l'analyse de l'expert rendue par Claude : vérifiée, fondue donne par donne dans le .bc.json de la séance
    (la version d'avant du fichier est gardée dans versions/). Renvoie le message à montrer ; ValueError avec un message en français si elle ne va pas."""
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
    sans_mains = []
    for k, a in donnes_.items():
        if k not in nums: raise ValueError(f"La donne {k} n'est pas dans cette séance : est-ce la bonne séance ?")
        mains_ = a.get("mains") if isinstance(a, dict) else None
        if isinstance(mains_, dict) and mains_:              # les cartes de l'analyse sont-elles celles de la donne ?
            ici = seance[k].get("mains") or {}
            autres_ = [x for x in "NESO" if _cartes(mains_.get(x)) != _cartes(ici.get(x))]
            if autres_:
                raise ValueError(f"Donne {k} : les cartes de l'analyse ne sont pas celles de cette séance (main de "
                                 f"{SIEGE[autres_[0]]} différente). L'analyse a été écrite pour une autre donne ou une autre "
                                 "numérotation : rien n'a été importé.")
        else:
            sans_mains.append(k)
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
    donnes_ = {k: ({x: y for x, y in a.items() if x != "mains"} if isinstance(a, dict) else a)   # les mains ont servi à
               for k, a in donnes_.items()}                                                    # la vérification
    ancien = rapport.analyse_de(c, "expert") or {}
    fusion = dict(ancien, **{k: v for k, v in neuf.items() if k != "donnes"})
    fusion["donnes"] = dict(ancien.get("donnes", {}), **donnes_)
    fusion.setdefault("systeme", "sef-2024")
    rapport.ecrire_analyse(c, "expert", fusion)              # le fichier d'avant est gardé dans versions/
    return (f"{len(donnes_)} donne{'s' if len(donnes_) > 1 else ''} importée{'s' if len(donnes_) > 1 else ''} ; l'analyse de "
            f"l'expert couvre maintenant {len(fusion['donnes'])} donnes sur {len(nums)}."
            + (" Les cartes de chaque donne sont vérifiées." if not sans_mains else
               f" Attention : sans les mains dans l'analyse, les cartes n'ont pas pu être vérifiées (donne"
               f"{'s' if len(sans_mains) > 1 else ''} {', '.join(sorted(sans_mains, key=int))})."))


def _cartes(main):
    """Une main (« AX93 X64 V8 RV62 », le 10 en X ou 10) comme un ensemble de cartes, pour comparer deux fichiers."""
    if not isinstance(main, str): return None
    parts = main.replace("10", "X").split()
    return frozenset((i, r) for i, p in enumerate(parts) for r in ("" if p in ("-", "—") else p))


PART_ = {"N": "S", "S": "N", "E": "O", "O": "E"}


def sens_public(texte):
    """Le sens d'une enchère sans la main de celui qui l'a faite, pour un joueur dont on ne voit pas les cartes :
    « 11 H, quatre piques, singleton cœur : 13+ points, fit différé ; HLD 14 = … » -> « 13+ points, fit différé ».
    Ôte la description de la main avant le premier « : », le calcul « ; HLD … » et la phrase « … convenait aussi ».
    « 3 clés (3041 : 3 ou 0) » -> « 3 ou 0 clés (3041) » ; « réponse au Blackwood 3041 : 3 clés (3 ou 0) » -> « Réponse au
    Blackwood 3041 : 3 ou 0 clés »."""
    t = (texte or "").strip()
    t = re.sub(r"\.\s+[^.]*convenait aussi.*$", "", t)
    t = re.sub(r"\s*;\s*HLD.*$", "", t)
    m = re.match(r"^\d clés? \(3041 : ([^)]+)\)(.*)$", t)
    if m: return f"{m[1]} clés (3041){m[2]}"
    m = re.match(r"^(réponse au Blackwood 3041 : )\d clés? \(([^)]+)\)(.*)$", t)    # le nombre exact ne se voit pas
    if m: t = f"{m[1]}{m[2]} clés{m[3]}"
    tete, sep, reste = t.partition(" : ")
    if sep and re.search(r"\d+ H\b|\b(deux|trois|quatre|cinq|six|sept|huit|singleton|chicane|cartes à|fit à|points ensemble|"
                         r"couleurs contrôlées)\b", tete):
        t = reste
    return t[:1].upper() + t[1:] if t else t


def grille_html(enc, vul=None, qui=None, sens=None):
    """Une grille d'enchères Ouest Nord Est Sud (lignes d'une analyse, standard ou expert). vul : la vulnérabilité de
    la donne ; chaque place est alors soulignée d'un trait épais, rouge si vulnérable, vert sinon. qui : "coach" ou
    "expert", l'en-tête au fond de qui recommande ces enchères (build_pdf.AVIS), comme dans le PDF.
    sens : {rang dans la séquence: (siège, texte, alertée)} ; une enchère qui a un sens s'ouvre en bulle au survol, et
    reste ouverte d'un clic (JS_SENS) ; une enchère alertée porte un petit « A » bleu (l'utilisateur, 2026-11-11 : le sens
    sur l'enchère elle-même, plutôt qu'une liste à part)."""
    trait = lambda s: "" if vul is None else \
        f";width:25%;border-bottom:6px solid {'var(--bc-coeur-600)' if vul == 'Tous' or vul == ('N-S' if s in 'NS' else 'E-O') else 'var(--bc-trefle-600)'}"
    fond = ""
    if qui:                                       # "reco" : vert pâle, les enchères recommandées ; "autre" : gris, celles du coach
        from build_pdf import GRILLE
        fond = f";background:{GRILLE[qui][0]}"
    tete = "".join(f"<th style='padding:2px 10px;text-align:center{trait(s)}{fond}'>{SIEGE[s]}</th>" for s in "ONES")
    import html as h_
    debut = sum(1 for c in (enc[0] if enc else []) if c == "–")      # les cases avant le donneur
    def case(i, c):
        x = (sens or {}).get(i - debut) if c not in ("", "–", "?") else None
        if not x or not (x[1] or x[2]):
            return f"<td style='padding:1px 10px;text-align:center'>{rouge(c)}</td>"
        siege, texte, alerte = x
        a = ""                                    # pas de « A » : le carton Alerte ne reste pas sur la table (l'utilisateur, 2026-11-18)
        bulle = (f"<b>{'Alerte — ' if alerte else ''}{SIEGE[siege]} {rouge(c)}</b>" + (f" : {rouge(h_.escape(texte))}" if texte else ""))
        cote = f" c{i % 4}"                                     # la colonne : la bulle reste dans la grille
        return (f"<td class='enc-sens{cote}' style='padding:1px 10px;text-align:center'>{rouge(c)}{a}"
                f"<span class='bulle'>{bulle}</span></td>")
    corps = "".join("<tr>" + "".join(case(ri * 4 + ci, c) for ci, c in enumerate(r)) + "</tr>" for ri, r in enumerate(enc))
    large = "" if vul is None else ";width:100%;table-layout:fixed"          # quatre colonnes égales
    return f"<table style='border-collapse:collapse;font-size:16px{large}'><tr>{tete}</tr>{corps}</table>"


VERT, ROUGE_VUL, ENCRE = "var(--bc-trefle-800)", "var(--bc-coeur-600)", "var(--bc-tapis-800)"      # les couleurs du PDF (build_pdf)


CASQUETTE_SVG = ("<svg viewBox='0 0 128 80' width='21' height='13' style='display:inline-block;vertical-align:-1px'>"   # comme icones/casquette.png
                 "<ellipse cx='90' cy='62' rx='34' ry='7' fill='#1f5f3a'/><path d='M8 60 A42 46 0 0 1 92 60 Z' fill='#1f5f3a'/>"
                 "<rect x='8' y='57' width='84' height='6' fill='#1f5f3a'/><circle cx='50' cy='14' r='5' fill='#1f5f3a'/>"
                 "<path d='M47 22 Q37 34 35 52' stroke='#e6efe9' stroke-width='3' fill='none'/>"
                 "<line x1='10' y1='60' x2='90' y2='60' stroke='#e6efe9' stroke-width='2'/></svg>")


def bloc_avis_html(qui, texte):
    """Un avis dans son bloc, comme le PDF (build_pdf.AVIS) : le conseil du coach en vert sous sa casquette, l'avis de
    l'expert dans son bloc vert avec ✦ (le seul mis en valeur)."""
    from build_pdf import AVIS, txt
    marque, trait, fond = AVIS[qui]
    signe = CASQUETTE_SVG if qui == "coach" else f"<span style='color:{trait}'>✦</span>"
    if fond is None:                              # le coach : du texte ordinaire, l'expert seul est mis en valeur
        return f"<div style='margin-top:4px'>{signe} {marque[5:]} {txt(texte.strip())}</div>"
    return (f"<div style='background:{fond};border-left:3px solid {trait};padding:4px 8px;margin-top:4px'>"
            f"{signe} {marque[5:]} {txt(texte.strip())}</div>")


def titre_section(t):
    """Un titre de section, comme dans le PDF : gras, vert."""
    ui.html(f"<div style='font-size:var(--fs-titre);font-weight:700;color:{VERT};margin-top:18px'>{t}</div>", sanitize=False)


def diagramme_html(d, a):
    """Les quatre mains autour de la rose des vents (rouge vulnérable, vert sinon), avec les repères d'entame du PDF :
    un rond par entame jouée à une table, deux à plusieurs tables, un fond gris pour l'entame recommandée."""
    import contextlib, io
    from build_pdf import marques_entame, SUITS
    with contextlib.redirect_stdout(io.StringIO()):          # ses avertissements vont au PDF, pas ici
        mk = marques_entame(d, a)
    def carte(siege, s, x):
        m = mk[siege].get((s, x)); txt = "10" if x == "X" else x
        if not m: return f"<span style='display:inline-block;min-width:13px;text-align:center'>{txt}</span>"
        bord = f"border:1.3px solid {ENCRE};" if m["tables"] else ""
        double = f"box-shadow:0 0 0 2px var(--bc-blanc),0 0 0 3.3px {ENCRE};" if m["tables"] > 1 else ""
        fond = "background:rgba(59,66,79,.28);" if m["reco"] else ""
        return (f"<span style='display:inline-block;min-width:21px;height:21px;line-height:19px;text-align:center;border-radius:50%;"
                f"margin:0 2px;{bord}{double}{fond}'>{txt}</span>")
    def main(siege):
        lignes = "".join(f"<div>{rouge(c)}&nbsp;" + ("—" if x == "-" else "".join(carte(siege, c, y) for y in x)) + "</div>"
                         for c, x in zip(SUITS, d["mains"][siege].split()))
        don = " · donneur" if d["donneur"] == siege else ""
        return f"<div style='font-size:var(--fs-texte);line-height:1.5'><div style='color:var(--bc-tapis-700);font-weight:600;white-space:nowrap'>{SIEGE[siege]} · {d['hcp'][siege]} H{don}</div>{lignes}</div>"
    v = d.get("vul", "Personne")
    c_ns = ROUGE_VUL if v in ("N-S", "Tous") else VERT; c_eo = ROUGE_VUL if v in ("E-O", "Tous") else VERT
    case = lambda t, c: f"<div style='background:{c};color:var(--bc-blanc);font-weight:700;display:flex;align-items:center;justify-content:center'>{t}</div>"
    rose = (f"<div style='display:grid;grid-template:repeat(3,30px)/repeat(3,30px);border:1px solid var(--bc-tapis-900);width:92px'>"
            f"<div></div>{case('N', c_ns)}<div></div>{case('O', c_eo)}<div></div>{case('E', c_eo)}<div></div>{case('S', c_ns)}<div></div></div>")
    rond = lambda style: f"<span style='display:inline-block;width:14px;height:14px;border-radius:50%;vertical-align:middle;margin-right:8px;{style}'></span>"
    legende = "<div style='font-size:var(--fs-liste);color:var(--bc-tapis-800);line-height:1.9;white-space:nowrap'><div style='font-weight:700'>Entame</div>"
    if d.get("tables"):
        legende += (f"<div>{rond(f'border:1.3px solid {ENCRE}')}jouée à une table</div>"
                    f"<div>{rond(f'border:1.3px solid {ENCRE};box-shadow:0 0 0 2px var(--bc-blanc),0 0 0 3.3px {ENCRE}')}jouée à plusieurs tables</div>")
    legende += f"<div>{rond('background:rgba(59,66,79,.28)')}recommandée</div></div>"
    grille = (f"<div style='display:grid;grid-template-columns:minmax(min-content,150px) 96px minmax(min-content,150px) 0;"
              f"align-items:center;gap:6px 8px'>"
              f"<div></div><div style='grid-column:2/4'>{main('N')}</div><div></div>"
              f"<div style='justify-self:end'>{main('O')}</div><div style='justify-self:center'>{rose}</div><div>{main('E')}</div><div></div>"
              f"<div></div><div style='grid-column:2/4'>{main('S')}</div><div></div></div>")
    return (f"<div style='display:flex;flex-wrap:wrap;align-items:flex-end;gap:8px 20px;max-width:100%;overflow-x:auto'>{grille}{legende}</div>")   # la légende en
                                                           # bas à droite, comme le PDF ; dessous quand la place manque (texte grand)


def colonne_avis_html(qui, texte):
    """Un avis comme dans le PDF (build_pdf.colonne_avis) : son titre seul sur sa ligne (la casquette du coach, le ✦ de
    l'expert), puis des paragraphes courts, première ligne en retrait ; l'expert dans son bloc vert."""
    from build_pdf import AVIS, txt, paragraphes, majuscule
    marque, trait, fond = AVIS[qui]
    signe = CASQUETTE_SVG if qui == "coach" else f"<span style='color:{trait}'>✦</span>"
    h = f"<div style='font-weight:700;margin-bottom:2px'>{signe} {marque[5:].replace(' :', '')}</div>"
    h += "".join(f"<p style='text-indent:1.2em;margin:0 0 6px'>{txt(x)}</p>" for x in paragraphes(majuscule(texte.strip())))
    if fond is None: return f"<div>{h}</div>"
    return f"<div style='background:{fond};border-left:3px solid {trait};padding:6px 10px;border-radius:2px'>{h}</div>"


def avec_avis_html(texte):
    """Le texte du programme, puis le conseil du coach et l'avis de l'expert, comme le PDF (build_pdf.avec_avis) : les
    deux côte à côte, le coach à gauche, l'expert à droite ; seul, un avis prend toute la largeur."""
    from build_pdf import txt, decouper_avis, paragraphes
    prog, coach, expert = decouper_avis(texte)
    if not prog.strip(): h = ""
    elif "<br" in prog: h = f"<div>{txt(prog)}</div>"      # des lignes déjà faites (les notes des enchères, une par appel)
    else: h = "".join(f"<p style='text-indent:1.2em;margin:0 0 6px'>{txt(x)}</p>" for x in paragraphes(prog))
    if coach and expert:
        return h + ("<div style='display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start'>"
                    f"{colonne_avis_html('coach', coach)}{colonne_avis_html('expert', expert)}</div>")
    return h + "".join(colonne_avis_html(q, x) for q, x in (("coach", coach), ("expert", expert)) if x)


BANDE_HTML = "background:var(--bc-tapis-50);border-radius:6px;padding:4px 16px 12px"   # la bande gris pâle du PDF (build_pdf.BANDE)


def page_analyse(d, a, repli, version, data=None, c=None, replis=None, retenir=lambda: None):
    """L'analyse d'une donne, dans l'ordre et l'allure de sa page du PDF : titre, mains et repères d'entame, résultats
    à la table (votre rang, le tableau avec le contrat recommandé), enchères aux tables, enchères recommandées et leur
    avis, plan de jeu et entame sur la bande grise, commentaire, cartes vues. Le double mort et le par sont dans la barre de droite.
    replis : {"tables": ouvert ?, "encheres": ouvert ?}, gardé d'une donne à l'autre ; retenir() l'enregistre."""
    replis = replis if replis is not None else {}
    from build_pdf import txt
    data = data or {}
    html = lambda h, style="": ui.html(f"<div style='font-size:var(--fs-texte);line-height:1.5;{style}'>{h}</div>", sanitize=False).classes("w-full")
    titre_donne(d, plus=f" · Thème : <b>{html_.escape(str(d['theme']))}</b>" if d.get("theme") else "")
    if a and a.get("a_revoir"):                             # donneur ou vulnérabilité changés depuis (edition.appliquer_numero)
        ui.html("<div style='font-size:var(--fs-texte);background:var(--bc-warning-bg-subtle);border-left:4px solid var(--bc-carreau-500);"
                "padding:6px 10px'>Le donneur ou la vulnérabilité de cette donne ont changé depuis l'analyse de l'expert : "
                "<b>à revoir</b>. Ses enchères et ses conseils peuvent ne plus convenir.</div>", sanitize=False).classes("w-full")
    tour = moi.tour_de(data, d["n"]) if data else ""
    if tour: html(tour, "color:var(--bc-tapis-700)")
    ui.html(diagramme_html(d, a), sanitize=False).classes("mt-2")
    if d.get("tables"):                                     # les résultats, ouverts comme dans le PDF (l'utilisateur, 2026-11-17)
        titre_section("Résultats à la table")
        mes = moi.paires(data) if data else set()
        rang = moi.votre_rang(d["tables"], mes, lambda t: f"{t['contrat']} {SIEGE.get(t['declarant'], t['declarant'])} {t['resultat']}".strip())
        if rang: html(rouge(rang), f"background:{moi.SURLIGNE};padding:2px 6px;border-radius:4px")
        import comparer
        tableau_resultats(d, mes, comparer.table_recommandee(d, a))
        if any(x.get("encheres") for x in d["tables"]):
            titre_section("Enchères aux tables")
            encheres_tables(d)
    titre_section("Enchères recommandées")
    notes = a.get("notes", "")
    expert = not (a.get("auto") or version == "Standard")
    with ui.row().classes("w-full items-start gap-6 encheres-reco"):   # les notes sous la grille quand la place manque
        if expert and a.get("enc_coach") and a["enc_coach"] != a["enc"]:   # le coach enchérit autrement : ses enchères aussi
            from build_pdf import AVIS
            ui.html(f"<div><div style='color:{ENCRE};font-weight:700;white-space:nowrap'>{CASQUETTE_SVG} Le coach</div>"   # le coach
                    f"{grille_html(a['enc_coach'], qui='autre')}"                                                         # d'abord
                    f"<div style='color:{AVIS['expert'][1]};font-weight:700;margin-top:10px'>✦ L'expert</div>{grille_html(a['enc'], qui='reco')}</div>",
                    sanitize=False).classes("shrink-0")
        else: ui.html(grille_html(a["enc"], qui="reco"), sanitize=False).classes("shrink-0")
        if notes:
            if a.get("auto") or version == "Standard": html(avec_avis_html(notes))   # avec le conseil du coach
            else: ui.html(bloc_avis_html("expert", notes), sanitize=False)
    # le plan de jeu et l'entame, sur la bande gris pâle du PDF : côte à côte quand seul le coach parle, l'un sous
    # l'autre (le coach à gauche, l'expert à droite) quand l'expert donne son avis (l'utilisateur, 2026-11-17)
    from build_pdf import decouper_avis
    e = a.get("entame")
    entame = (f"<div style='font-weight:700;margin-bottom:4px'>Entame recommandée : {txt(e['carte'])} "
              f"({SIEGE.get(e.get('joueur'), e.get('joueur', ''))}).</div>") if isinstance(e, dict) and e.get("carte") else ""
    morceaux = []
    if a.get("plan"): morceaux.append(("Plan de jeu", avec_avis_html(a["plan"])))
    if entame or a.get("defense"): morceaux.append(("Entame et défense", entame + (avec_avis_html(a["defense"]) if a.get("defense") else "")))
    avis_expert = any(decouper_avis(a.get(k) or "")[2] for k in ("plan", "defense"))
    titre_h = lambda t: f"<div style='font-size:var(--fs-titre);font-weight:700;color:{VERT};margin:10px 0 6px'>{t}</div>"
    if morceaux:
        if avis_expert or len(morceaux) == 1:
            for t, h in morceaux:
                ui.html(f"<div style='{BANDE_HTML};font-size:var(--fs-texte);line-height:1.5'>{titre_h(t)}{h}</div>",
                        sanitize=False).classes("w-full mt-4")
        else:
            ui.html(f"<div style='{BANDE_HTML};font-size:var(--fs-texte);line-height:1.5;display:grid;grid-template-columns:1fr 1fr;gap:0 24px'>"
                    + "".join(f"<div style='{'border-left:1px solid var(--bc-tapis-200);padding-left:20px' if i else ''}'>{titre_h(t)}{h}</div>"
                              for i, (t, h) in enumerate(morceaux)) + "</div>", sanitize=False).classes("w-full mt-4")
    comm = a.get("comm") or repli.get("comm")
    if comm:
        titre_section("Commentaire sur les contrats joués" if d.get("tables") else "Commentaire"); html(txt(comm))
    vues = a.get("vues") or repli.get("vues")
    if vues:
        from build_pdf import paragraphes
        titre_section("Cartes vues (après coup)")
        html("".join(f"<p style='text-indent:1.2em;margin:0 0 6px'>{txt(x)}</p>" for x in paragraphes(vues)))


def pensee_html(t, ouvert=True):
    """Une pensée (carte.texte_pensee) : qui joue quoi, pourquoi, et ce qu'il croit des mains cachées."""
    h = f"<div style='font-size:var(--fs-texte);font-weight:700'>{rouge(t['titre'])}</div>"
    if t["raison"]: h += f"<div style='font-size:16px;margin-top:2px'>{rouge(t['raison'])}</div>"
    if t.get("plan"):
        h += f"<div style='font-size:var(--fs-texte);margin-top:4px'><b>Son plan :</b> {rouge(t['plan'])}</div>"
    if t["croyance"]:
        h += ("<div style='font-size:var(--fs-texte);color:var(--bc-tapis-800);margin-top:4px'><b>Ce qu'il croit :</b>"
              + "".join(f"<div>{rouge(x)}</div>" for x in t["croyance"]) + "</div>")
    return f"<div style='background:var(--bc-trefle-100);border-left:3px solid var(--bc-trefle-800);padding:6px 8px;border-radius:4px'>{h}</div>"


def encheres_groupe_html(d, xs):
    """Plusieurs tables aux mêmes enchères : une grille, puis une ligne par table (son contrat, son résultat, son entame)."""
    h = encheres_html(d, xs[0])
    tete = "Tables " + ", ".join(str(x.get("table", "")) for x in sorted(xs, key=lambda x: str(x.get("table", ""))))
    h = re.sub(r"<div style='font-weight:600'>.*?</div>", f"<div style='font-weight:600'>{tete}</div>", h, count=1)
    lignes = "".join(f"<div>Table {x.get('table', '')} · {x.get('nom_ns') or x.get('paire_ns', '')} : {rouge(x.get('contrat', ''))} "
                     f"{SIEGE.get(x.get('declarant'), '')} {x.get('resultat', '')}"
                     + (f", entame {rouge(x['entame'])}" if x.get("entame") else "") + "</div>"
                     for x in sorted(xs, key=lambda x: str(x.get("table", ""))))
    return re.sub(r"</table><div>.*?</div>", lambda m: "</table>" + lignes, h, count=1, flags=re.S)


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
    avis = "" if x.get("encheres_ok", True) else f"<div style='color:var(--bc-coeur-600)'>{x.get('encheres_msg', '')}</div>"
    return (f"<div style='font-size:var(--fs-texte)'><div style='font-weight:600'>{titre}</div>"
            f"<table style='border-collapse:collapse;margin:2px 0'><tr>{tete}</tr>{corps}</table><div>{fin}</div>{avis}</div>")


F = types.SimpleNamespace()   # les noms de la page (état, fonctions), partagés par les modules de l'interface
