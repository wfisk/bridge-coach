# -*- coding: utf-8 -*-
"""L'application des rapports : une fenêtre, un bouton. Lancement : ./bridge-coach.sh

Elle ne fait que conduire rapport.py, dans un processus à part : l'analyse dure plusieurs minutes,
utilise tous les cœurs et n'a rien à faire dans le serveur de la fenêtre. Sa progression vient des
lignes que rapport.py écrit (« Donne 3 sur 24 », « Rapport prêt : … »).

    --navigateur   ouvre dans le navigateur plutôt que dans une fenêtre
    --sans-ouvrir  ne fait que servir la page (essais)
"""
import asyncio, datetime, glob, json, os, re, shutil, signal, subprocess, sys, tempfile, threading, time
import html as html_

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import carte, classement, donnes, edition, exporter, fichiers, fiche_conventions, jouer, maj, moi, question_expert, rapport
from nicegui import app, background_tasks, run, ui

if __name__ == "__mp_main__" and sys.platform == "darwin":  # la fenêtre : son processus s'appelle Python, le Dock garde Bridge Coach
    try:
        import webview.platforms.cocoa as _cocoa           # elle se déclare au Dock en se chargeant, ensuite on la retire
        _cocoa.BrowserView.app.setActivationPolicy_(1)
    except Exception:                                      # au pire, l'icône Python revient
        pass

TITRE = "Bridge Coach"
PORT = int(os.environ.get("BRIDGE_COACH_PORT") or 8123)    # un autre port : une seconde instance d'essai
LARGEUR_BARRE = 220                                        # la barre de gauche (Donnes, Jouer, Analyse) : « Donne 24 » et la barre de défilement
PART_ANALYSE = .85                                         # la part de la barre pour l'analyse, le reste pour les PDF
NB_PDF = 2                                                 # l'analyse, la comparaison
RAPPORTS = (("analyse", "Analyse", "enchères, entame, plan de jeu, conseil du coach et, si vous l'incluez, avis de l'expert"),
            ("a-revoir", "Donnes à revoir", "« Vous face au champ », puis seulement les donnes où vous pouviez faire mieux"),
            ("comparaison", "Comparaison", "le Coach face à l'Expert"))
TYPES_FICHIERS = ("Tournois (*.bws;*.pdf;*.pbn;*.json)", "Tous les fichiers (*.*)")
TYPES_SEANCES = ("Séances Bridge Coach (*.bc.json;*.json)", "Tous les fichiers (*.*)")
TYPES_BWS = ("Bridgemate ou feuille de route (*.bws;*.pdf)", "Tous les fichiers (*.*)")
TYPES_PBN = ("PBN (*.pbn)", "Tous les fichiers (*.*)")
TYPES_EXPERT = ("Analyse expert (*.json)", "Tous les fichiers (*.*)")   # pywebview : lettres et espaces seulement, pas d'apostrophe
SOURCES = {"bws": "Bridgemate", "feuille-de-route": "Feuille de route", "entrainement": "Entraînement",
           "saisie": "Donnes saisies", "simulation": "Simulation"}
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
        t.fraction = t.part * (k - 1) / n; t.texte = f"{t.mot} {k} sur {n}"
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
        m = re.match(r"(analyse|a-revoir|comparaison|standard|expert|diff)(?:-(.+))?\.pdf$", os.path.basename(f)[len(debut):])
        if not m or ".provisoire" in f: continue           # (« analyse 2.pdf » : une copie d'iCloud, pas un rapport)
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


GRIS_BARRE = "#f3f3f1"
LARGEUR_PANNEAU = 300                                     # la barre de droite de l'onglet Jouer
# le côté de la table de l'onglet Jouer, dans les unités du dessin : la table, les mains autour et les cartons forment un
# seul bloc, que JS_AJUSTE agrandit ou rétrécit pour remplir la place (ECHELLE_MAX) ; sur un grand écran ou une
# télévision, les cartes grandissent avec, la table garde la même proportion (l'utilisateur, 2026-11-11 : lire les cartes
# de loin, pas une grande table)
COTE_TABLE = "440px"
# pendant le jeu de la carte, avec le mort sur un côté (en défense) : une table rectangulaire, de la même hauteur, plus
# large de la colonne de la main du mort (vide : ses cartes sont sur la table). Les cartes gardent leur taille.
LARGEUR_TABLE_LARGE = f"calc({COTE_TABLE} + 84px)"
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
    var t = el.closest('.ajuste'), r = el.getBoundingClientRect();   // change d'échelle (JS_AJUSTE), rien ne bouge
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

JS_AJUSTE = """<script>
// La table de l'onglet Jouer rétrécit avec la fenêtre plutôt que d'ouvrir une barre de défilement : le bloc .ajuste
// garde sa taille naturelle et prend l'échelle qui le fait tenir dans la largeur de son parent et la hauteur de la fenêtre.
(function () {
  function ajuster() {
    document.querySelectorAll('.ajuste').forEach(function (el) {
      var parent = el.parentElement, w = el.offsetWidth, h = el.offsetHeight;
      if (!w || !h) return;
      var marge = parseFloat(getComputedStyle(parent).paddingTop) || 0;
      // la taille du texte (zoom de la page, --zoom) : la fenêtre compte en points d'écran, la page en points agrandis
      var z = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--zoom')) || 1;
      var haut = marge;
      for (var p = parent; p; p = p.offsetParent) haut += p.offsetTop;
      var e = Math.min(2.4, (parent.clientWidth - 16) / w, (window.innerHeight / z - haut - 24) / h);   // ECHELLE_MAX : jusqu'à 2,4 fois
      e = Math.max(e, 0.45);
      // pas de va-et-vient : agrandir fait parfois apparaître une barre de défilement, qui fait rétrécir, qui la fait
      // disparaître… (la table tremblait). On ne regrandit que d'un vrai pas ; un petit écart ne change rien.
      var avant = parseFloat(el.dataset.echelle || '0');
      if (avant && (Math.abs(e - avant) < 0.01 || (e > avant && e - avant < 0.06))) e = avant;
      // pendant une même donne, à fenêtre égale, la table ne grandit pas parce que les mains se vident (l'utilisateur,
      // 2026-11-11) : elle ne regrandit qu'à une autre donne ou quand la fenêtre change
      // (chaque redessin refait l'élément : la mémoire est dans la page, par donne et taille de fenêtre)
      var cle = (el.getAttribute('data-donne') || '') + '|' + parent.clientWidth + 'x' + window.innerHeight;   // la place, pas la fenêtre
      var memo = window.__echelleDonne || (window.__echelleDonne = {});
      if (memo[cle] && e > memo[cle]) e = memo[cle];
      memo[cle] = e;
      el.dataset.echelle = e;
      el.style.transform = 'scale(' + e + ')';
      el.style.setProperty('--echelle', e);                 // les bulles s'en défont : toujours à leur taille
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
.entree-barre.aide-sujet { height: auto; min-height: 32px; padding-top: 6px; padding-bottom: 6px; flex-shrink: 0; }   /* un sujet sur deux lignes ne déborde pas */
.carte { width: 55px; height: 79px; margin-right: -22px; padding: 3px 5px; background: #fff; border: 1px solid #b9c0c7;
  border-radius: 6px; font-size: 20px; line-height: 1.05; font-weight: 600; color: #1b1b1b; }   /* une seule taille partout :
   les mains, le mort, le pli (l'utilisateur, 2026-11-11) ; le bloc de la table grandit avec la fenêtre (JS_AJUSTE) */
.carte.r { color: #c0141c; }
.carte { position: relative; }
.carte .dm { position: absolute; left: -6px; top: -12px; min-width: 26px; padding: 1px 5px;   /* le coin visible, même recouverte */
  border-radius: 9px; font-size: 15px; font-weight: 800; color: #fff; text-align: center; line-height: 1.25; z-index: 2;
  box-shadow: 0 0 0 2px #fff; }   /* démonstration, double mort : les levées du déclarant avec cette carte */
.carte .dm.mieux { background: #1f6b45; } .carte .dm.moins { background: #c0141c; }
.carte.jouable { cursor: pointer; }   /* sans couleur : rien ne dit quelles cartes sont permises (comme à la table) */
.carte.secoue { animation: secoue .45s ease-in-out; border-color: #c62828; }   /* une carte qui ne peut pas être jouée */
@keyframes secoue { 0%, 100% { transform: translateX(0); } 20%, 60% { transform: translateX(-7px); } 40%, 80% { transform: translateX(7px); } }
.carte.jouable:hover { transform: translateY(-6px); }
.carte.terne { background: #eceae5; border-color: #cfd3d7; color: #9a9fa5; }   /* pas jouable : terne mais opaque,
   les cartes en dessous ne se voient pas au travers */
.carte.r.terne { color: #d6a3a6; }
.colonne-mort .carte { margin-right: 0; }
.colonne-mort > * + * { margin-top: -53px; }
.ligne-mort > :last-child .carte { margin-right: 0; }   /* le mort sur un côté : une ligne par couleur, chevauchée comme une main
   (chaque carte est seule dans son enveloppe : c'est la dernière enveloppe de la ligne qui compte) */
.nom-joueur { display: flex; align-items: center; gap: 6px; font-size: calc(15px / max(var(--echelle, 1), .75)); color: #4a4f57;
  white-space: nowrap; }   /* la table rapetisse (--echelle) : le nom grandit d'autant, d'un tiers au plus, pour rester lisible */
.nom-joueur.tour { color: #1b1b1b; font-weight: 700; text-decoration: underline 3px #1f6b45; text-underline-offset: 5px; }
.nom-joueur.tour.pense-doux { text-decoration: none; animation: doux 1.4s ease-in-out infinite; }   /* un robot réfléchit */
@keyframes carre-tourne { from { transform: rotate(var(--de)); } to { transform: rotate(var(--a)); } }
@keyframes carre-contre { from { transform: rotate(calc(-1 * var(--de))); } to { transform: rotate(calc(-1 * var(--a))); } }
.carre-tourne .txt-carre { display: inline-block; transform: rotate(calc(-1 * var(--a))); }
.carre-tourne.anime .txt-carre { animation: carre-contre 1.4s ease-in-out; animation-delay: var(--retard); }   /* le numéro et N E S O restent à l'endroit */
@keyframes doux { 50% { opacity: .45; } }
.nom-joueur .siege-lbl { font-weight: 800; letter-spacing: .5px; color: #2b2b2b; }   /* NORD, SUD… au-dessus du nom */
.nom-joueur.deux { display: block; line-height: 1.2; }   /* à l'ouest, aligné contre la table (à droite) */
.enc-sens { position: relative; cursor: pointer; text-decoration: underline dotted #9aa3ad; text-underline-offset: 4px; }
.enc-sens .bulle { display: none; position: absolute; top: calc(100% + 4px); left: 0; z-index: 30; width: 230px; padding: 8px 10px;
  background: #fff; border: 1px solid #cfd5db; border-radius: 8px; box-shadow: 0 4px 14px rgba(0,0,0,.18); text-align: left;
  font-size: 16px; line-height: 1.35; font-weight: 400; color: #2b2b2b; white-space: normal; }
.enc-sens.c1 .bulle { left: -60px; } .enc-sens.c2 .bulle { left: auto; right: -60px; } .enc-sens.c3 .bulle { left: auto; right: 0; }
.enc-sens:hover .bulle, .enc-sens.ouverte .bulle { display: block; }
.marque-alerte { display: inline-block; margin-left: 3px; padding: 0 4px; border-radius: 4px; background: #1565c0; color: #fff;
  font-size: 11px; font-weight: 700; line-height: 15px; vertical-align: 2px; }
.carte.gagnante { box-shadow: 0 0 0 2px #d9a400, 0 0 14px rgba(217,164,0,.55); transform: translateY(-3px);
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
  background: #fff; border: 1px solid #cfd5db; border-radius: 8px; box-shadow: 0 4px 14px rgba(0,0,0,.18);
  font-size: calc(16px / var(--echelle, 1)); line-height: 1.35; font-weight: 400; color: #2b2b2b; white-space: normal; }
  /* dans la table mise à l'échelle (JS_AJUSTE, --echelle), la bulle garde sa vraie taille : 16 px à l'écran */
.carte-sens:hover .bulle, .carte-sens.ouverte .bulle { display: block; }
.carte.vide { width: 22px; border: none; background: none; margin-right: 0; padding: 3px 0; color: #c9c7c1; }   /* une chicane : la couleur en gris pâle */
.eventail .groupe { margin-right: 26px; }
.eventail .groupe:last-child { margin-right: 16px; }
.groupe.colonne > :last-child .carte { margin-right: 0; }
.ajuste .carte { position: relative; z-index: 1; }      /* sur la table, les cartes passent au-dessus de l'étui en filigrane */
.groupe.colonne .dix { letter-spacing: -1px; }             /* le 10 tient dans la part visible de la carte */  /* sinon la ligne paraît plus courte : à gauche, elle passerait sous la table */
.dos { width: 32px; height: 46px; border-radius: 4px; border: 2px solid #fff; outline: 1px solid #c3cbd4;
  background: repeating-linear-gradient(45deg, #9aa8b8 0 3px, #b0bccA 3px 6px); }
.plis-gardes { display: flex; align-items: center; min-height: 30px; }
.plis-gardes .dos { width: 20px; height: 28px; border-width: 1px; border-radius: 3px; flex: none; }
.plis-gardes .dos.couche { width: 28px; height: 20px; }   /* comme en duplicate : vers le partenaire gagné, en travers perdu */
.plis-gardes .dos + .dos { margin-left: -9px; }           /* chaque carte posée en partie sur la précédente */
.plis-gardes .dos[onclick] { pointer-events: auto; cursor: pointer; }   /* la dernière carte : voir le dernier pli */
.plis-gardes .dos:not(.gagne) { background: #dcdfe2; outline-color: #b9bfc5; }   /* perdu : gris uni, pas le dos des mains cachées */
.plis-gardes .dos.gagne { background: repeating-linear-gradient(45deg, #2e7d32 0 3px, #5a9e5f 3px 6px); outline-color: #1f5e24; }
.plis-gardes.colonne { flex-direction: column; min-height: 0; min-width: 30px; }
.compte-plis { position: absolute; left: calc(100% + 8px); top: 50%; transform: translateY(-50%); min-width: 24px; height: 24px;
  padding: 0 6px; border-radius: 12px; background: #2e7d32; color: #fff; font-size: 15px; font-weight: 700; line-height: 24px;
  text-align: center; box-sizing: border-box; }   /* hors de la rangée : elle reste centrée */
.plis-gardes.colonne .dos + .dos { margin-left: 0; margin-top: -9px; }
.plis-gardes.colonne .compte-plis { left: 50%; top: calc(100% + 8px); transform: translateX(-50%); }   /* sous la colonne */
.compte-plis.autre { background: #c62828; }
/* la levée qui vient d'être gagnée : le cercle reste, l'ancien nombre monte et sort, le nouveau monte à sa place */
.compte-plis.roule { overflow: hidden; }
.compte-plis .pile { display: block; animation: compte-monte .45s ease-out forwards; }
.compte-plis .pile span { display: block; height: 24px; }
@keyframes compte-monte { from { transform: translateY(0); } to { transform: translateY(-24px); } }   /* les levées de l'autre camp en rouge, les vôtres en vert (l'utilisateur, 2026-11-11) */
.plis-gardes.adverse .dos.gagne { background: repeating-linear-gradient(45deg, #c62828 0 3px, #e06666 3px 6px); outline-color: #8e1b1b; }
.main-grande .groupe { margin-right: 30px; }
.main-grande .groupe:last-child { margin-right: 22px; }   /* juste ce que dépasse la dernière carte : le trait s'arrête avec elle */
/* à vous d'enchérir ou de jouer : les cartes à jouer (votre main, ou le mort quand vous en jouez) luisent en jaune ;
   ni les noms ni les mains des robots (l'utilisateur, 2026-11-11) */
.main-grande.a-vous, .mort-table.a-vous { filter: drop-shadow(0 0 6px rgba(242, 183, 5, .9)); }
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
.onglet.eteint { background: #d9d9d6 !important; color: #9a9a96 !important; }
.onglet.indice { background: #fff; color: #1f6b45; display: flex; align-items: center; gap: 2px; }
.sa { color: #2b2b2b; background: #eceff1; } .pique { color: #1f3fa0; background: #e3eaf8; }
.coeur { color: #c0141c; background: #fbe4e4; } .carreau { color: #c86a00; background: #fff0d6; }
.trefle { color: #1d7a35; background: #e1f2e5; }
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
.carton.bid { width: 84px; height: 50px; } .carton.bid .face { background: #fff; border: 1px solid #b8bfc6; }
.carton.bid .grand { position: absolute; right: 5px; top: 0; bottom: 0; display: flex; align-items: center;
  font-weight: 700; line-height: 1; }                     /* le niveau, la couleur à sa droite : « 1♦ » sur une ligne */
.carton.bid .grand b { font-size: 26px; } .carton.bid .grand i { font-style: normal; font-size: 24px; margin-left: 1px; }
.carton.bid .grand i.sa { font-size: 26px; font-weight: 700; background: none; margin-left: 1px; }   /* SA de la taille du chiffre */
.carton.bid.sa .grand { color: #2b2b2b; } .carton.bid.pique .grand { color: #1f3fa0; }
.carton.bid.coeur .grand { color: #c0141c; } .carton.bid.carreau .grand { color: #c86a00; }
.carton.bid.trefle .grand { color: #1d7a35; }
.carton.carre { width: 56px; height: 50px; }   /* même hauteur que les enchères */ .carton.carre .face { color: #fff; border: 2px solid #f1f1ec; }   /* le bord presque blanc sépare deux cartons pareils */
.carton .tab { position: absolute; left: -10px; top: 6px; width: 10px; min-height: 20px;
  border-radius: 3px 0 0 3px; background: inherit; border: 2px solid #f1f1ec; border-right: 0; }
.carton .tab.gauche { top: auto; bottom: 6px; }
.carton .base { position: absolute; right: 3px; top: 3px; bottom: 3px; width: 22px; display: flex; flex-direction: column;
  align-items: center; justify-content: space-between; font-weight: 800; line-height: 1; }
.carton .base b { writing-mode: vertical-rl; }            /* chaque lettre tournée : le mot se lit le long du bord droit */
.carton .base.mot { font-size: 13px; } .carton .base.croix { font-size: 22px; justify-content: space-around; }
.carton .base.croix b + b { margin-top: -2px; }
.carton.passe .face { background: #2e7d32; } .carton.contre .face { background: #c62828; }
.carton.surcontre .face { background: #1565c0; } .carton.stop .face { background: #c62828; }
.carton.alerte .face { background: #1565c0; }
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
.boite-encheres { background: #c0392b; border-radius: 12px; padding: 8px; }
.boite-encheres.en-attente { opacity: .45; pointer-events: none; filter: saturate(.5); }   /* pas votre tour : grisée */
.ratelier { background: #f4f5f6; border-radius: 6px; padding: 6px; display: flex; flex-direction: column; gap: 4px; }
.tirette { width: 46px; height: 30px; display: flex; align-items: center; justify-content: center; border-radius: 4px;
  font-size: 16px; font-weight: 700; border: 1px solid rgba(0,0,0,.18); cursor: pointer; }
.tirette:hover { filter: brightness(.93); transform: translateY(-2px); }
.tirette.vide { visibility: hidden; }
.tirette.depassee { background: #eeede9; color: #c2c0ba; border-color: #e2e0da; cursor: default; }   /* dépassée : en gris pâle */
.tirette.depassee:hover { filter: none; transform: none; }
.tirette.autres { width: auto; color: #555; background: #fff; font-weight: 600; font-size: 15px; color: #333; }
.compartiment { margin-top: 8px; background: #a93226; border-radius: 6px; padding: 6px 6px 6px; align-items: center; }
.onglet { position: relative; min-width: 58px; height: 38px; margin-top: 11px; padding: 0 6px; border-radius: 4px;
  font-size: 16px; font-weight: 700; color: #fff; display: flex; align-items: center; justify-content: center; cursor: pointer; }
.onglet[data-tab]::before { content: ""; position: absolute; top: -9px; right: 3px; height: 10px; min-width: 20px;
  padding: 0 3px; border-radius: 3px 3px 0 0; font-size: 8px; line-height: 12px; background: inherit; color: inherit; }
.compartiment > :last-child .onglet { min-width: 72px; }   /* le second rang : Stop et Alerte, sous Passe, X, XX */
.onglet.passe { background: #2e7d32; } .onglet.contre { background: #e53935; } .onglet.surcontre { background: #1565c0; }
.onglet.eteint { cursor: default; }
.onglet:not(.eteint):hover { filter: brightness(.93); transform: translateY(-2px); }   /* comme les cartons d'enchères au survol */
.onglet.stop { background: #c62828; border: 2px solid #fff; }   /* bordé de blanc : il se voit sur le rouge de la boîte */ .onglet.stop.pose { outline: 3px solid #f2b705; }
.onglet.alerte { background: #1565c0; } .onglet.alerte.pose { outline: 3px solid #f2b705; }
@keyframes pense { 50% { opacity: .35; } }
.pense { animation: pense 1s ease-in-out infinite; }
"""


CSS_AIDE = """
.aide { font-size: 16px; line-height: 1.55; color: #222; }
.aide h1, .aide h2, .aide h3 { font-size: 16px; font-weight: 700; color: #1f6b45; margin: 1.4em 0 .4em; line-height: 1.3; letter-spacing: normal; }
.aide > :first-child { margin-top: 0; }
.aide > h1:first-child, .aide > h2:first-child, .aide > h3:first-child { font-size: 18px; color: inherit; margin-top: 0; }   /* le titre de la section, comme celui des autres pages */
.aide p, .aide ul, .aide ol, .aide dl { margin: .6em 0; }
.aide ul { list-style: disc; padding-left: 1.4em; } .aide ol { list-style: decimal; padding-left: 1.4em; }
.aide li { margin-bottom: .4em; } .aide dt { font-weight: 600; margin-top: .7em; } .aide dd { margin: 0; }
.aide code { background: #e6efe9; padding: .1em .35em; border-radius: 4px; font-size: 15px; word-break: break-all; }
.aide .note { background: #e6efe9; border-left: 4px solid #1f6b45; padding: .7em 1em; margin: 1em 0; }
.aide h2 { font-size: 22px; color: #222; margin: 0 0 .6em; }                  /* le titre de la page */
.aide h3 { font-size: 18px; margin-top: 1.8em; scroll-margin-top: 60px; }     /* une section : sous la barre du haut */
.aide p.intro { font-size: 17px; color: #333; }
.aide figure { margin: 1em 0 1.4em; }
.aide figure img { display: block; max-width: 100%; border: 1px solid #dfe3e6; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.aide figcaption { font-size: 15px; color: #555; margin-top: .4em; }
.aide .etapes { counter-reset: e; list-style: none; padding-left: 0; }
.aide .etapes > li { counter-increment: e; position: relative; padding-left: 2.4em; margin-bottom: .8em; }
.aide .etapes > li::before { content: counter(e); position: absolute; left: 0; top: 0; width: 1.7em; height: 1.7em; border-radius: 50%;
  background: #1f6b45; color: #fff; font-weight: 700; font-size: 14px; display: flex; align-items: center; justify-content: center; }
.aide .astuce { background: #fff8e1; border-left: 4px solid #e0a800; padding: .7em 1em; margin: 1em 0; }
@media (max-width: 1000px) { .sur-page-place { display: none; } }   /* une fenêtre étroite : le texte d'abord */
.sur-page-place { width: 220px; align-self: stretch; }       /* la place de la colonne ; la liste, elle, reste fixe à l'écran */
.sur-page { position: fixed; top: 64px; width: 220px; max-height: calc(100vh / var(--zoom, 1) - 90px); overflow-y: auto; background: transparent; }
.aide figure img { cursor: zoom-in; }
.image-aide-grande { position: fixed; inset: 0; z-index: 9999; background: rgba(20,20,20,.82); display: flex; align-items: center;
  justify-content: center; cursor: zoom-out; padding: 24px; }
.image-aide-grande img { max-width: 100%; max-height: 100%; border-radius: 8px; background: #fff; box-shadow: 0 8px 30px rgba(0,0,0,.4); }
.sur-page a { display: block; font-size: 15px; line-height: 1.35; color: #444; text-decoration: none; padding: 5px 0 5px 12px;
  border-left: 2px solid #e3e7ea; }
.sur-page a:hover { color: #1f6b45; }
.sur-page a.lue { color: #1f6b45; font-weight: 600; border-left-color: #1f6b45; }
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
    ("Réglages", "contact"): "signaler", ("Réglages", "expert"): "questions-expert", ("Réglages", "systeme"): "systeme",
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


def titre_page(texte, ancre, classes="text-lg font-bold"):
    """Le titre d'une page et, à côté, un petit « ? » bleu qui ouvre l'aide à la bonne section (l'événement « aide »)."""
    with ui.row().classes("items-center gap-1 no-wrap"):
        ui.label(texte).classes(classes)
        ui.button(icon="help_outline", on_click=lambda: ui.run_javascript(f"emitEvent('aide', {json.dumps(ancre)})")) \
            .props("flat round dense size=sm").style("color:#1976d2").tooltip("L'aide de cette page")


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


def lancer(chemin):
    """L'analyse standard seulement (rapport.py --analyse-seule) : les PDF se font dans l'onglet Rapports."""
    T.__init__(1.0); T.genre = "analyse"; T.seance = chemin; T.texte = "Lecture du fichier"
    demarrer_travail(T, [os.path.join(ICI, "rapport.py"), chemin, "--analyse-seule"])


def avec_expert():
    """L'option « Inclure l'avis de l'expert » de l'onglet Rapports (etat.json, oui par défaut)."""
    return lire_etat().get("avec_expert", True)


def lancer_rapports(chemin, noms, revoir=False):
    """Les PDF seulement, depuis les analyses enregistrées (rapport.py --rapports) : la barre avance rapport par rapport."""
    T.__init__(0.0, "Écriture des rapports"); T.genre = "rapports"; T.seance = chemin; T.texte = "Écriture des rapports"
    demarrer_travail(T, [os.path.join(ICI, "rapport.py"), chemin, "--rapports"] + (["--avec-noms"] if noms else [])
                     + ([] if avec_expert() else ["--sans-analyse"]) + (["--a-revoir"] if revoir else []))


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
        return _INFOS[cle]
    except Exception:
        return date_lisible(c), ""


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


TAILLES = [(1.0, "Normale"), (1.25, "Grande"), (1.5, "Très grande")]   # Réglages, Taille du texte : le zoom de la page


SEPARATEUR = "\u2014sep\u2014"                              # la ligne entre votre nom et les autres (options_joueurs)


def taille_texte():
    """La taille du texte choisie (etat.json « zoom ») : 1, 1.25 ou 1.5."""
    z = lire_etat().get("zoom")
    return z if z in [t for t, _ in TAILLES] else 1.0


VUL_TXT = {"Personne": "personne", "N-S": "Nord-Sud", "E-O": "Est-Ouest", "Tous": "tous"}


def seance_active():
    """La séance ouverte la dernière fois, si son fichier existe encore ; sinon None."""
    c = lire_etat().get("seance")
    return c if c and os.path.isfile(c) else None


def retenir(c):
    """La séance ouverte devient celle qu'on retrouve au prochain lancement."""
    ecrire_etat(seance=c)


def nom_html(nom, deux_lignes=False, droite=False, etat="", siege=""):
    """Le nom d'un joueur près de ses cartes, discret (l'utilisateur, 2026-11-11 : pas de bandeau ni de photo) : une
    ligne en gris foncé."""
    import html as h_
    tete = f"<div class='siege-lbl'>{SIEGE[siege].upper()}</div>" if siege else ""   # la place, en gras, au-dessus du nom
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
    return e.get("joueur_jouer") or e.get("moi") or e.get("mon_nom") or ""


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
                ui.label(k).classes("text-gray-700"); ui.label(v).classes("break-all")
        ui.label("Marque").classes("text-gray-700")          # lue à l'import, devinée sinon ; corrigeable ici
        with ui.row().classes("items-center gap-3"):
            choix_m = ui.toggle({"MP": "Match-points", "IMP": "IMP"}, value=moi.marque(data)).props("dense no-caps")
            devinee = ui.label("devinée d'après le nombre de tables").classes("text-base text-gray-600")
            devinee.set_visibility(not s.get("marque"))
            choix_m.on_value_change(lambda e: (changer_marque(c, e.value), devinee.set_visibility(False)))


def changer_marque(c, marque):
    """La marque choisie sur la page Séance : gardée dans le .bc.json (session.marque, marque_choisie : un réimport la
    garde) ; les rapports la suivent à la prochaine création."""
    data = json.load(open(c, encoding="utf-8"))
    if (data.get("session") or {}).get("marque") == marque: return
    data["session"].update(marque=marque, marque_choisie=True)
    edition.enregistrer(c, data)
    ui.notify(f"Marque : {moi.MARQUES[marque]}. Les rapports la suivront à la prochaine création.")
    tours = moi.parcours(data)
    if tours:                                              # le mouvement : vos tours, tables et adversaires
        ui.label(f"Parcours de {moi.qui_parcourt(data)}").classes("text-base font-bold mt-4")
        ui.table(columns=[{"name": k, "label": l, "field": k, "align": a} for k, l, a in
                          (("tour", "Tour", "right"), ("table", "Table", "right"), ("donnes", "Donnes", "left"),
                           ("adversaires", "Adversaires", "left"), ("pct", "Votre %", "right"))],
                 rows=tours, row_key="tour").props("flat dense").classes("text-base")


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


MANCHE = {"SA": 9, "♠": 10, "♥": 10, "♦": 11, "♣": 11}       # les levées d'une manche, par dénomination
FOND_MANCHE, FOND_CHELEM = "#d7ecd9", "#9fd1a8"


def dm_html(d):
    """Le double mort pour la barre de droite, sur toute sa largeur, comme la grille du PDF : levées par dénomination
    et par déclarant. Fond vert : une manche se gagne ; vert soutenu : un chelem ; cadre : le contrat du par."""
    if not d.get("dm"): return ""
    p = d.get("par") or {}
    par = (p["contrat"][1:].rstrip("X"), p.get("declarant")) if p.get("contrat") and p["contrat"] != "passe" else None
    cell = "padding:5px 0;text-align:center;border-top:1px solid #e3e7ea"
    def case(x, s):
        n = d["dm"][x][s]
        fond = FOND_CHELEM if n >= 12 else FOND_MANCHE if n >= MANCHE[x] else "#f6f8fb" if s in "NS" else ""
        cadre = ";box-shadow:inset 0 0 0 2px #1f5f3a;font-weight:700" if par == (x, s) else ""
        return f"<td style='{cell}{';background:' + fond if fond else ''}{cadre}'>{n}</td>"
    tete = "".join(f"<th style='padding:5px 0;text-align:center;font-weight:700'>{s}</th>" for s in ("Nord", "Sud", "Est", "Ouest"))
    corps = "".join(f"<tr><td style='{cell};font-weight:700'>{rouge(x)}</td>" + "".join(case(x, s) for s in "NSEO") + "</tr>"
                    for x in ("SA", "♠", "♥", "♦", "♣"))
    carre = lambda style: f"<span style='display:inline-block;width:11px;height:11px;border-radius:2px;vertical-align:-1px;margin:0 4px 0 0;{style}'></span>"
    legende = (f"<div style='font-size:15px;color:#3f4651;margin-top:4px;line-height:1.6'>{carre(f'background:{FOND_MANCHE}')}manche "
               f"&nbsp;{carre(f'background:{FOND_CHELEM}')}chelem &nbsp;{carre('box-shadow:inset 0 0 0 2px #1f5f3a')}par</div>")
    return (f"<div style='font-size:15px;width:100%'><div style='font-weight:700;margin-bottom:4px'>Double mort</div>"
            f"<table style='width:100%;table-layout:fixed;border-collapse:collapse;background:#fff;border:1px solid #9fb5a8;"
            f"border-radius:6px;overflow:hidden'><colgroup><col style='width:16%'/></colgroup>"
            f"<tr style='background:#e6efe9'><th></th>{tete}</tr>{corps}</table>{legende}</div>")


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


def page_donne(d, mes=frozenset(), tour="", reco=None):
    """Une donne dans l'onglet Donnes : les mains et les tables ; le nom, le donneur, la vulnérabilité et le par sont
    dans la barre de droite. Le double mort est dans l'onglet Analyse. mes : vos paires (moi.paires), dont la ligne est
    surlignée. tour : « Tour 1 · table 4 · … » (moi.tour_de) quand la séance décrit son mouvement. reco : le contrat
    recommandé (comparer.table_recommandee), rangé parmi les tables sur fond vert pâle."""
    mains_grille(d)
    if tour: ui.label(tour).classes("text-base text-gray-700 mt-2")
    if d.get("tables"):
        ui.label("Aux tables").classes("text-base font-bold mt-2")
        rang = moi.votre_rang(d["tables"], mes, lambda t: f"{t['contrat']} {SIEGE.get(t['declarant'], t['declarant'])} {t['resultat']}".strip())
        if rang: ui.html(f"<div style='font-size:15px;background:{moi.SURLIGNE};padding:2px 6px;border-radius:4px'>{rouge(rang)}</div>", sanitize=False)
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
    teinte = lambda v: "#1f6b45" if bon(v) else "#c62828"
    with ui.column().classes("gap-1 rounded-xl border border-gray-200 bg-white px-4 py-3 my-2 max-w-4xl"):
        if cl["rejouees"]:
            tot = cl.get("total")
            ui.label(classement.ligne_seance(cl)).style(f"font-size:24px;font-weight:700;color:{teinte(tot) if tot is not None else '#222'}")
        else:
            ui.label("Aucune donne rejouée jusqu'au bout pour l'instant.").style("font-size:20px;font-weight:700;color:#222")
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
        .props("flat dense :table-row-style-fn=\"r => r.fait ? 'cursor:pointer' : 'cursor:pointer;color:#777;font-style:italic'\"") \
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
    with ui.row().classes("gap-6 items-start"):
        for x in d["tables"]:
            if x.get("encheres"): ui.html(encheres_html(d, x), sanitize=False)


# ---------------------------------------------------------------- l'analyse, dans l'onglet Analyse
_ANALYSES = {}
FOND_RECO = "#e6efe9"                                      # la ligne du contrat recommandé (comme dans les PDF)


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


def lien_pdf(f, nom, detail):
    """Un rapport : son nom comme un lien qui l'ouvre, ce qu'il contient, le fichier et sa date."""
    with ui.column().classes("gap-0"):
        ui.label(nom).classes("text-base text-primary underline cursor-pointer").on("click", lambda f=f: ouvrir(f))
        ui.html(f"<div class='text-base text-gray-700'>{detail} · <span style='word-break:break-all'>{os.path.basename(f)}</span> · "
                f"<span style='white-space:nowrap'>{quand(f)}</span></div>", sanitize=False)


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
    ancien = rapport.analyse_de(c, "expert") or {}
    fusion = dict(ancien, **{k: v for k, v in neuf.items() if k != "donnes"})
    fusion["donnes"] = dict(ancien.get("donnes", {}), **donnes_)
    fusion.setdefault("systeme", "sef-2024")
    rapport.ecrire_analyse(c, "expert", fusion)              # le fichier d'avant est gardé dans versions/
    return (f"{len(donnes_)} donne{'s' if len(donnes_) > 1 else ''} importée{'s' if len(donnes_) > 1 else ''} ; l'analyse de "
            f"l'expert couvre maintenant {len(fusion['donnes'])} donnes sur {len(nums)}.")


def grille_html(enc, vul=None, qui=None, sens=None):
    """Une grille d'enchères Ouest Nord Est Sud (lignes d'une analyse, standard ou expert). vul : la vulnérabilité de
    la donne ; chaque place est alors soulignée d'un trait épais, rouge si vulnérable, vert sinon. qui : "coach" ou
    "expert", l'en-tête au fond de qui recommande ces enchères (build_pdf.AVIS), comme dans le PDF.
    sens : {rang dans la séquence: (siège, texte, alertée)} ; une enchère qui a un sens s'ouvre en bulle au survol, et
    reste ouverte d'un clic (JS_SENS) ; une enchère alertée porte un petit « A » bleu (l'utilisateur, 2026-11-11 : le sens
    sur l'enchère elle-même, plutôt qu'une liste à part)."""
    trait = lambda s: "" if vul is None else \
        f";width:25%;border-bottom:6px solid {'#c0141c' if vul == 'Tous' or vul == ('N-S' if s in 'NS' else 'E-O') else '#2e7d32'}"
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
        a = "<span class='marque-alerte' title='Alerte'>A</span>" if alerte else ""
        bulle = (f"<b>{'Alerte — ' if alerte else ''}{SIEGE[siege]} {rouge(c)}</b>" + (f" : {rouge(h_.escape(texte))}" if texte else ""))
        cote = f" c{i % 4}"                                     # la colonne : la bulle reste dans la grille
        return (f"<td class='enc-sens{cote}' style='padding:1px 10px;text-align:center'>{rouge(c)}{a}"
                f"<span class='bulle'>{bulle}</span></td>")
    corps = "".join("<tr>" + "".join(case(ri * 4 + ci, c) for ci, c in enumerate(r)) + "</tr>" for ri, r in enumerate(enc))
    large = "" if vul is None else ";width:100%;table-layout:fixed"          # quatre colonnes égales
    return f"<table style='border-collapse:collapse;font-size:16px{large}'><tr>{tete}</tr>{corps}</table>"


VERT, ROUGE_VUL, ENCRE = "#1f5f3a", "#c0141c", "#3b424f"      # les couleurs du PDF (build_pdf)


CASQUETTE_SVG = ("<svg viewBox='0 0 128 80' width='21' height='13' style='vertical-align:-1px'>"   # comme icones/casquette.png
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
    ui.html(f"<div style='font-size:16px;font-weight:700;color:{VERT};margin-top:14px'>{t}</div>", sanitize=False)


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
        double = f"box-shadow:0 0 0 2px #fff,0 0 0 3.3px {ENCRE};" if m["tables"] > 1 else ""
        fond = "background:rgba(59,66,79,.28);" if m["reco"] else ""
        return (f"<span style='display:inline-block;min-width:21px;height:21px;line-height:19px;text-align:center;border-radius:50%;"
                f"margin:0 2px;{bord}{double}{fond}'>{txt}</span>")
    def main(siege):
        lignes = "".join(f"<div>{rouge(c)}&nbsp;" + ("—" if x == "-" else "".join(carte(siege, c, y) for y in x)) + "</div>"
                         for c, x in zip(SUITS, d["mains"][siege].split()))
        don = " · donneur" if d["donneur"] == siege else ""
        return f"<div style='font-size:15px;line-height:1.5'><div style='color:#555;font-weight:600;white-space:nowrap'>{SIEGE[siege]} · {d['hcp'][siege]} H{don}</div>{lignes}</div>"
    v = d.get("vul", "Personne")
    c_ns = ROUGE_VUL if v in ("N-S", "Tous") else VERT; c_eo = ROUGE_VUL if v in ("E-O", "Tous") else VERT
    case = lambda t, c: f"<div style='background:{c};color:#fff;font-weight:700;display:flex;align-items:center;justify-content:center'>{t}</div>"
    rose = (f"<div style='display:grid;grid-template:repeat(3,30px)/repeat(3,30px);border:1px solid #1d2430;width:92px'>"
            f"<div></div>{case('N', c_ns)}<div></div>{case('O', c_eo)}<div></div>{case('E', c_eo)}<div></div>{case('S', c_ns)}<div></div></div>")
    rond = lambda style: f"<span style='display:inline-block;width:14px;height:14px;border-radius:50%;vertical-align:middle;margin-right:8px;{style}'></span>"
    legende = "<div style='font-size:15px;color:#3f4651;line-height:1.9;white-space:nowrap'><div style='font-weight:700'>Entame</div>"
    if d.get("tables"):
        legende += (f"<div>{rond(f'border:1.3px solid {ENCRE}')}jouée à une table</div>"
                    f"<div>{rond(f'border:1.3px solid {ENCRE};box-shadow:0 0 0 2px #fff,0 0 0 3.3px {ENCRE}')}jouée à plusieurs tables</div>")
    legende += f"<div>{rond('background:rgba(59,66,79,.28)')}recommandée</div></div>"
    grille = (f"<div style='display:grid;grid-template-columns:150px 100px 150px;align-items:center;gap:6px 10px'>"
              f"<div></div><div style='grid-column:2/4'>{main('N')}</div>"
              f"<div style='justify-self:end'>{main('O')}</div><div style='justify-self:center'>{rose}</div><div>{main('E')}</div>"
              f"<div></div><div style='grid-column:2/4'>{main('S')}</div></div>")
    return f"<div style='display:flex;flex-wrap:wrap;align-items:flex-end;gap:8px 24px'>{grille}{legende}</div>"   # la légende passe dessous si la place manque


def avec_avis_html(texte):
    """Le texte du programme, puis le conseil du coach et l'avis de l'expert, chacun dans son bloc, comme le PDF."""
    from build_pdf import txt, decouper_avis
    prog, coach, expert = decouper_avis(texte)
    h = f"<div>{txt(prog)}</div>" if prog.strip() else ""
    for qui, avis in (("coach", coach), ("expert", expert)):
        if avis: h += bloc_avis_html(qui, avis)
    return h


def page_analyse(d, a, repli, version, data=None, c=None, replis=None, retenir=lambda: None):
    """L'analyse d'une donne, dans l'ordre et l'allure de sa page du PDF : titre, mains et repères d'entame, résultats
    à la table (votre rang et le contrat recommandé ; le tableau complet replié), enchères recommandées et leur avis,
    plan de jeu, entame et défense, commentaire, cartes vues. Le double mort et le par sont dans la barre de droite.
    replis : {"tables": ouvert ?, "encheres": ouvert ?}, gardé d'une donne à l'autre ; retenir() l'enregistre."""
    replis = replis if replis is not None else {}
    def repli_(cle, titre, icone):
        def change(e): replis[cle] = e.value; retenir()
        return ui.expansion(titre, icon=icone, value=bool(replis.get(cle)), on_value_change=change) \
            .classes("w-full text-base").props("dense")
    from build_pdf import txt
    data = data or {}
    html = lambda h, style="": ui.html(f"<div style='font-size:15px;line-height:1.5;{style}'>{h}</div>", sanitize=False).classes("w-full")
    vul = {"Personne": "Personne", "Tous": "Tous", "N-S": "Nord-Sud", "E-O": "Est-Ouest"}.get(d.get("vul"), d.get("vul", ""))
    ui.label(f"Donne n° {d['n']}").classes("text-lg font-bold")
    sous = f"Donneur : <b>{SIEGE[d['donneur']]}</b> · Vulnérable : <b>{vul}</b>" + (f" · Thème : <b>{d['theme']}</b>" if d.get("theme") else "")
    tour = moi.tour_de(data, d["n"]) if data else ""
    html(sous + (f"<br/>{tour}" if tour else ""), "color:#555b66;margin-top:-6px")
    ui.html(diagramme_html(d, a), sanitize=False).classes("mt-2")
    if d.get("tables"):                                     # les résultats : l'essentiel en vue, le tableau replié
        titre_section("Résultats à la table")
        mes = moi.paires(data) if data else set()
        rang = moi.votre_rang(d["tables"], mes, lambda t: f"{t['contrat']} {SIEGE.get(t['declarant'], t['declarant'])} {t['resultat']}".strip())
        if rang: html(rouge(rang), f"background:{moi.SURLIGNE};padding:2px 6px;border-radius:4px")
        import comparer
        reco = comparer.table_recommandee(d, a)
        if reco and reco["contrat"] != "passe":
            camp, _ = moi.mon_camp(d["tables"], mes); signe = -1 if camp == "EO" else 1
            sc = lambda t: signe * t["score_ns"]
            mieux = sum(1 for t in d["tables"] if sc(t) > sc(reco)); pareil = sum(1 for t in d["tables"] if sc(t) == sc(reco))
            vu = "vu de votre camp" if camp else "vu de Nord-Sud"
            html(f"Contrat recommandé, au double mort : <b>{rouge(reco['contrat'])} {SIEGE[reco['declarant']]} {reco['resultat']}</b>, "
                 f"{reco['score_ns']:+d} pour Nord-Sud · {mieux} table{'s' if mieux > 1 else ''} ont fait mieux, {pareil} autant, "
                 f"{len(d['tables']) - mieux - pareil} moins bien ({vu})", f"background:{FOND_RECO};padding:2px 6px;border-radius:4px;margin-top:4px")
        with repli_("tables", f"Les {len(d['tables'])} tables", "table_rows"):
            tableau_resultats(d, mes, reco)
        if any(x.get("encheres") for x in d["tables"]):
            with repli_("encheres", "Enchères aux tables", "view_list"):
                encheres_tables(d)
    titre_section("Enchères recommandées")
    notes = a.get("notes", "")
    expert = not (a.get("auto") or version == "Standard")
    with ui.row().classes("w-full no-wrap items-start gap-6"):
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
    if a.get("plan"):
        titre_section("Plan de jeu"); html(avec_avis_html(a["plan"]))
    e = a.get("entame")
    if (isinstance(e, dict) and e.get("carte")) or a.get("defense"):
        titre_section("Entame et défense")
        h = f"<b>Entame recommandée :</b> {txt(e['carte'])} ({SIEGE.get(e.get('joueur'), e.get('joueur', ''))})." if isinstance(e, dict) and e.get("carte") else ""
        html(h + (avec_avis_html(a["defense"]) if a.get("defense") else ""))
    comm = a.get("comm") or repli.get("comm")
    if comm:
        titre_section("Commentaire sur les contrats joués" if d.get("tables") else "Commentaire"); html(txt(comm))
    vues = a.get("vues") or repli.get("vues")
    if vues:
        titre_section("Cartes vues (après coup)"); html(txt(vues))


def pensee_html(t, ouvert=True):
    """Une pensée (carte.texte_pensee) : qui joue quoi, pourquoi, et ce qu'il croit des mains cachées."""
    h = f"<div style='font-size:15px;font-weight:700'>{rouge(t['titre'])}</div>"
    if t["raison"]: h += f"<div style='font-size:16px;margin-top:2px'>{rouge(t['raison'])}</div>"
    if t.get("plan"):
        h += f"<div style='font-size:15px;margin-top:4px'><b>Son plan :</b> {rouge(t['plan'])}</div>"
    if t["croyance"]:
        h += ("<div style='font-size:15px;color:#3f4651;margin-top:4px'><b>Ce qu'il croit :</b>"
              + "".join(f"<div>{rouge(x)}</div>" for x in t["croyance"]) + "</div>")
    return f"<div style='background:#e6efe9;border-left:3px solid #1f5f3a;padding:6px 8px;border-radius:4px'>{h}</div>"


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
               "body { font-size: 16px; } .q-btn { text-transform: none; } "
               # lisible de loin (des joueurs âgés, un écran de télévision en cours) : le contenu qui change en grand ; les
               # libellés fixes que chacun connaît (onglets, barres latérales, boutons) gardent leur taille (le choix de l'utilisateur)
               ".q-table th, .q-table td { font-size: 15px !important; padding: 4px 6px !important; } .q-table th { font-weight: 700; }"
               ".classement th, .classement td { font-size: 17px !important; padding: 6px 10px !important; }" + CSS_AIDE + CSS_CARTES)
    ui.add_head_html(JS_AJUSTE + JS_GLISSE + JS_SENS + JS_SUR_PAGE)
    z = taille_texte()
    ui.add_head_html(f"<style>:root {{ zoom: {z}; --zoom: {z}; }}</style>")   # la taille du texte choisie dans Réglages
    seances, dossier = reglages()
    deja = seances_bc()
    choix = {"chemin": T.seance or seance_active() or (deja[0] if deja else None)}
    ui.page_title(titre_fenetre(choix["chemin"]))
    PAGE = lire_etat().get("page") or {}                    # la page ouverte à la dernière fermeture (retenir_page)
    vue = {"entree": PAGE.get("entree") or "seance"}       # l'entrée choisie dans la barre latérale de l'onglet Donnes
    if PAGE.get("version"): vue["version"] = PAGE["version"]   # Standard | Expert, dans l'onglet Analyse
    replis = dict(PAGE.get("replis") or {})                # Analyse : « Les … tables » et « Enchères aux tables » ouverts ou non

    @ui.refreshable
    def vue_seance():
        c = choix["chemin"]; data = lire_seance(c)
        if not data:
            with ui.column().classes("w-full max-w-xl mx-auto"):
                ui.label("Aucune séance ouverte.").classes("text-base")
                ui.label("Fichier, Ouvrir une séance pour en ouvrir une ; Fichier, Nouveau pour en créer une : depuis un tournoi "
                         "Bridgemate, un fichier PBN, ou des donnes d'entraînement.").classes("text-base text-gray-700")
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
            elif not any(f"d{x['n']}" == e for x in data["donnes"]):   # Options, Classement de l'onglet Jouer : la séance
                page_seance(data, c)
            else:
                d = next(d for d in data["donnes"] if f"d{d['n']}" == e)
                if ok and (d.get("a_completer") or vue.get("edition") == d["n"]):
                    editeur_donne(c, d)                    # une donne à compléter s'ouvre déjà en modification
                else:
                    with ui.column().classes("w-full gap-3").style(f"padding-right:{LARGEUR_PANNEAU}px"):
                        page_donne(d, moi.paires(data), moi.tour_de(data, d["n"]), recommandee(choix["chemin"], d))
                    with panneau_droit(d):
                        if ok: ui.button("Modifier la donne", icon="edit", on_click=lambda n=d["n"]: modifier(c, n)).props("outline").classes("w-full")

    @ui.refreshable
    def vue_analyse():
        c = choix["chemin"]; data = lire_seance(c)
        if not data: return
        std, exp = lire_analyses(c)
        e = entree_effective(data)
        if e == "standard":
            ui.label(f"Analyse du coach · séance du {data['session']['date']}").classes("text-lg font-bold")
            page_analyse_resume(data, std, False); return
        if e == "expert":
            ui.label(f"Analyse expert · séance du {data['session']['date']}").classes("text-lg font-bold")
            page_analyse_resume(data, exp, True)
            etapes_expert(c); return
        d = next((x for x in data["donnes"] if f"d{x['n']}" == e), None)
        if d is None: return
        n = str(d["n"])
        versions = [v for v, a in (("Standard", std), ("Expert", exp)) if a and (a.get("donnes") or {}).get(n, {}).get("enc")]
        if not versions:
            ui.label(f"Donne {d['n']}").classes("text-lg font-bold")
            ui.label("Pas encore d'analyse : « Analyse du coach », puis « Lancer l'analyse ».").classes("text-base text-gray-700"); return
        if vue.get("version") not in versions: vue["version"] = "Expert" if "Expert" in versions else versions[0]
        a = (exp if vue["version"] == "Expert" else std)["donnes"][n]
        if vue["version"] == "Expert":                    # le conseil du coach avant l'avis de l'expert (même contrat)
            a = rapport.coach_pour_expert(d, a, (std or {}).get("donnes", {}).get(n))
        repli = (std or {}).get("donnes", {}).get(n, {})   # l'expert reprend du programme ce qu'il n'écrit pas (cartes vues…)
        with ui.column().classes("w-full gap-3").style(f"padding-right:{LARGEUR_PANNEAU}px"):
            page_analyse(d, a, repli, vue["version"], data, c, replis, retenir_page)
        with panneau_droit(d, par=False):
            if len(versions) > 1:                           # Standard | Expert, deux moitiés égales
                ui.toggle({v: NOM_VERSION[v] for v in versions}, value=vue["version"], on_change=lambda ev: (vue.update(version=ev.value), vue_analyse.refresh(), retenir_page())) \
                    .props("no-caps spread toggle-color=primary").classes("w-full")
            else:
                ui.label("Analyse " + NOM_VERSION[vue['version']].lower().replace("coach", "du coach").replace("expert", "de l'expert")).classes("text-base font-bold")
            c_, decl = jouer.contrat(jouer.sequence(a["enc"], d["donneur"]), d["donneur"])
            lignes = [f"<b>Contrat recommandé</b> : {rouge(c_) if decl else 'passe générale'}" + (f" {SIEGE[decl]}" if decl else "")]
            e_ = a.get("entame")
            if isinstance(e_, dict) and e_.get("carte"):
                lignes.append(f"<b>Entame</b> : {rouge(e_['carte'])} ({SIEGE.get(e_.get('joueur'), e_.get('joueur', ''))})")
            if d.get("par"): lignes.append(par_html(d))
            ui.html("<div style='font-size:15px;line-height:1.6'>" + "<br/>".join(lignes) + "</div>", sanitize=False)
            if d.get("dm"): ui.html(dm_html(d), sanitize=False).classes("w-full")
            with ui.column().classes("w-full gap-2 mt-3"):    # de l'analyse à la table, ou sur papier pour un cours
                ui.button("Rejouer cette donne", icon="play_arrow", on_click=lambda: rejouer_donne(d)).props("outline no-caps").classes("w-full")
                ui.button("Imprimer cette donne", icon="print", on_click=lambda: imprimer_donne(c, d)) \
                    .props("outline no-caps").classes("w-full").set_enabled(not (T.actif or D.actif or I.actif))
                ui.button("Demander à l'expert", icon="forum", on_click=lambda: demander_expert(c, d, True, analyse=True)) \
                    .props("outline no-caps").classes("w-full")

    question = {"f": None, "message": ""}

    def demander_expert(c, d, apres, analyse=False):
        """Écrit le fichier de la question (question_expert), copie le court message, et montre les trois gestes."""
        data = lire_seance(c) or {}
        p_ = None if analyse else (jeu.get("partie") if jeu.get("cle") == (c, d["n"]) else None)
        siege = (siege_pour(c, d) or "S") if analyse else jeu.get("siege") or "S"
        seq = [] if analyse else jeu["seq"] if apres else jeu["seq"][:jeu.get("affiche", len(jeu["seq"]))]
        contenu = question_expert.fichier(data, d, siege, seq, p_, apres, lire_analyses(c) if apres else (None, None),
                                          prenom_expert())
        try:
            question["f"] = question_expert.ecrire(c, contenu, d["n"], apres)
        except OSError:
            ui.notify("Le fichier pour l'expert n'a pas pu être écrit.", type="negative"); return
        question["message"] = question_expert.message(os.path.basename(question["f"]))
        ui.clipboard.write(question["message"])
        fenetre_question.refresh(); question_d.open()

    qui_ = {"noms": [], "choix": None}

    def demander_qui(c):
        """Après le premier import, une fois : « Qui utilise Bridge Coach ? », parmi les joueurs de ce tournoi."""
        data = lire_seance(c) or {}
        noms_ = sorted({(j.get("nom") or "").strip() for v in (data.get("joueurs") or {}).values() for j in v} - {""}, key=str.lower)
        ecrire_etat(qui_demande=True)
        if not noms_: return
        qui_.update(noms=noms_, choix=None); fenetre_qui.refresh(); qui_d.open()

    def c_est_moi():
        n_ = qui_["choix"]
        if not n_: return
        ecrire_etat(mon_nom=n_); retenir_licence(n_)
        if not moi.nom(): ecrire_etat(moi=n_)
        qui_d.close(); vue_seance.refresh(); resultats.refresh()
        try: ma_licence.refresh(); choix_moi.set_options(options_joueurs(moi.nom()), value=moi.nom() or "")
        except NameError: pass
        ui.notify(f"Bonjour {question_expert.prenom_de(n_)} ! Vos tables sont maintenant surlignées.")

    def imprimer_fiche():
        """La fiche en PDF (documents/fiche-de-conventions.pdf), ouverte : de là on l'imprime ou on l'envoie."""
        try:
            f_ = fiche_conventions.pdf()
        except Exception:
            ui.notify("La fiche n'a pas pu être écrite.", type="negative"); return
        ouvrir(f_)
        ui.notify(f"La fiche est ouverte : imprimez-la depuis là. Elle est gardée dans {f_}", multi_line=True, timeout=8000)

    def remettre_fiche():
        fiche_conventions.tout_remettre(); remettre_fiche_d.close()
        ui.notify("Toutes les lignes sont revenues au système de Bridge Coach.")
        ui.navigate.reload()

    def rejouer_donne(d):
        """Analyse → Jouer, sur la même donne, au début de ses enchères."""
        jeu["mode"] = "jouer"; ecrire_etat(mode_jouer="jouer")
        onglets.set_value(o_jouer); aller(f"d{d['n']}")

    def imprimer_donne(c, d):
        """La page de cette donne seule, en PDF (rapport.py --rapports --donne=N), ouverte dès qu'elle est prête."""
        if T.actif or D.actif or I.actif: return
        T.__init__(0.0, "Impression"); T.genre = "imprimer"; T.seance = c; T.texte = f"Donne {d['n']} : préparation de la page"
        demarrer_travail(T, [os.path.join(ICI, "rapport.py"), c, "--rapports", f"--donne={d['n']}"]
                         + ([] if avec_expert() else ["--sans-analyse"]))
        ui.notify(f"La donne {d['n']} se prépare : le PDF s'ouvre dans un instant.")

    def carre_donne(d):
        """Le petit carré de la donne, comme sur le site de la FFB : le numéro au centre, N E S O sur les côtés, rouges si
        le camp est vulnérable, verts sinon ; le côté du donneur comme sur l'étui : blanc, bordé de sa couleur, avec « D »."""
        v = d.get("vul", "Personne"); vul = lambda x: v == "Tous" or v == ("N-S" if x in "NS" else "E-O")
        coul = lambda x: "#c0141c" if vul(x) else "#2e7d32"
        cote = {"N": "top:0;left:14px;right:14px;height:14px", "S": "bottom:0;left:14px;right:14px;height:14px",
                "O": "left:0;top:14px;bottom:14px;width:14px", "E": "right:0;top:14px;bottom:14px;width:14px"}
        h = "<div style='position:relative;width:60px;height:60px;background:#e9ece9;border-radius:6px;flex:none'>"
        for x in "NESO":                                  # le donneur comme sur l'étui : blanc, bordé de sa couleur, « D »
            fond, encre, texte = (f"#fff;box-sizing:border-box;border:2px solid {coul(x)}", coul(x), "D") if x == d["donneur"] \
                else (coul(x), "#fff", x)
            h += (f"<div style='position:absolute;{cote[x]};background:{fond};color:{encre};font-size:10px;font-weight:800;"
                  f"display:flex;align-items:center;justify-content:center'><span class='txt-carre'>{texte}</span></div>")
        h += ("<div style='position:absolute;left:16px;top:16px;width:28px;height:28px;background:#fff;border-radius:3px;"
              f"display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:800'>"
              f"<span class='txt-carre'>{d['n']}</span></div></div>")   # txt-carre : reste à l'endroit quand le carré tourne
        return h

    def panneau_droit(d=None, par=True):
        """La barre de droite d'une donne, la même dans Donnes, Jouer et Analyse : même largeur, même gris, le nom de la
        donne en haut ; avec d, l'étui (donneur, vulnérabilité), le thème et le par. Renvoie la colonne, à remplir."""
        col = ui.column().classes("gap-3 p-4 overflow-y-auto").style(
            f"position:fixed;top:var(--haut-panneau, {HAUTEUR_BARRE}px);right:0;bottom:0;width:{LARGEUR_PANNEAU}px;background:{GRIS_BARRE};"
            "border-left:1px solid #dcdcd8;z-index:1;overflow-x:hidden")
        if d is not None:
            with col:
                ui.label(f"Donne {d['n']}").classes("text-lg font-bold")
                with ui.row().classes("w-full justify-center"):
                    ui.html(etui(d, ("N", "O", "E", "S"), petit=True), sanitize=False)
                if d.get("theme"): ui.label(f"Thème : {d['theme']}").classes("text-base text-gray-700")
                if par and d.get("par"): ui.html(f"<div style='font-size:15px'>{par_html(d)}</div>", sanitize=False)
        return col

    jeu = {"cle": None, "mode": lire_etat().get("mode_jouer") or "jouer"}   # la donne en cours dans l'onglet Jouer ; Jouer | Démonstration (gardé)

    def siege_de(d, k):
        return jouer.ROT[(jouer.ROT.index(d["donneur"]) + k) % 4]

    def jeu_depart(c, d, siege=None, reprendre=True):
        """Ouvre la donne d : là où vous l'aviez laissée (enchères, cartes jouées : jouer.en_cours), sinon au début."""
        x = jouer.en_cours(base_seance(c), d["n"]) if reprendre else None
        if x:
            try:
                return jeu_reprendre(c, d, x)
            except Exception:
                pass                                       # un état illisible : la donne repart du début
        if not siege and place_jouer() == "joueur":        # comme un joueur de la séance : sa place à cette donne
            pj = moi.place_du_joueur(lire_seance(c), d, joueur_jouer())
            siege = pj["siege"] if pj else None
        siege = siege or jouer.siege_choisi(place_jouer(), d, lire_analyses(c))   # l'option choisie dans Options
        seq, ex, ind, al = jouer.avancer_alertes(d, [], siege)
        jeu.update(cle=(c, d["n"]), siege=siege, seq=seq, ex=ex, indice=ind, alertes=al, voir_indice=False, garde=False, d=d,
                   affiche=0, vus=0, revele=False, pense=None, partie=None, pli_vu=None, revoir=None, msg="", garde_jeu=False, sans_jouer=False,
                   attend=True)                            # les enchères partent quand vous appuyez sur « Commencer » (magneto)
        jeu_garder()

    def jeu_commencer():
        """« Commencer » : les enchères du programme apparaissent une à une jusqu'à votre tour."""
        if not jeu.get("attend"): return
        jeu["attend"] = False; jeu_garder(); vue_jouer.refresh()   # gardé : en revenant, la donne est commencée
        background_tasks.create(reveler())

    def jeu_au_debut(c, d):
        """⏮ : pendant le jeu de la carte, d'abord le début du jeu de la carte (les enchères restent) ; une seconde fois,
        ou pendant les enchères, la donne au début, avant les enchères (elles repartent avec ▶). Remplace « Reprendre le
        jeu de la carte » (l'utilisateur, 2026-11-11)."""
        p = jeu.get("partie")
        if p:
            joue = sum(len(pli) for pli, _ in p.plis) + len(p.pos.pli)
            depart = len(carte.Partie(d, p.contrat, p.decl, jeu["seq"], humain=jeu["siege"]).pos.jouees)   # l'entame du programme
            if joue > depart:
                carte_demarrer(d); return
        jeu_depart(c, d, jeu["siege"], reprendre=False); vue_jouer.refresh()

    def jeu_reculer(c, d):
        """◀ : votre dernière enchère ou votre dernière carte reprise, avec ce que le programme a joué après elle. Au
        début du jeu de la carte : la fin des enchères ; avant votre première enchère : le début de la donne."""
        p, s = jeu["partie"], jeu["siege"]
        if jeu.get("pense") or jeu.get("pli_vu") or jeu["affiche"] < len(jeu["seq"]): return   # le programme réfléchit
        if p:
            cartes = [(cc, r) for pli, _ in p.plis for _x, cc, r in pli] + [(cc, r) for _x, cc, r in p.pos.pli]
            q = carte.Partie(d, p.contrat, p.decl, jeu["seq"], humain=s)
            debut = len(q.pos.jouees)                   # l'entame du programme, déjà posée
            miennes = []
            for k, x in enumerate(cartes[debut:], debut):
                if q.au_joueur(): miennes.append(k)
                q.poser(x)
            garde = cartes[:miennes[-1]] if miennes else []
            jeu_reprendre(c, d, dict(siege=s, seq=list(jeu["seq"]), cartes=[cc + r for cc, r in garde],
                                     pensees=[z for z in p.pensees if z.get("n", 0) < len(garde)]))
            jeu["garde_jeu"] = False
            if not jeu.get("partie"): jeu["depart_auto"] = (c, d["n"], len(jeu["seq"]))   # revenu aux enchères : pas de départ seul
        else:
            ks = [k for k in range(len(jeu["seq"])) if siege_de(d, k) == s]
            if not ks: jeu_au_debut(c, d); return
            seq, ex, ind, al = jouer.avancer_alertes(d, jeu["seq"][:ks[-1]], s)
            jeu.update(seq=seq, ex=ex, indice=ind, alertes=al, voir_indice=False, tout_voir=False, affiche=len(seq), garde=False,
                       sans_jouer=False, attend=False, note="")
        jeu_garder(); vue_jouer.refresh()

    def magneto(c, d):
        """Les commandes d'un magnétoscope, en haut de la barre de droite : ⏮ au début de la donne, ◀◀ reprendre votre
        dernière enchère ou carte, ▶ commencer (les enchères ne partent pas toutes seules : l'utilisateur, 2026-11-11)."""
        p = jeu["partie"]
        occupe = bool(jeu.get("pense") or jeu.get("pli_vu") or jeu["affiche"] < len(jeu["seq"]))
        rien = jeu.get("attend") and not p
        with ui.row().classes("gap-2 items-center no-wrap"):
            ui.button(icon="skip_previous", on_click=lambda: jeu_au_debut(c, d)).props("outline") \
                .tooltip("Au début du jeu de la carte, puis de la donne" if jeu.get("partie") else "Au début de la donne").set_enabled(not rien and not occupe)
            ui.button(icon="fast_rewind", on_click=lambda: jeu_reculer(c, d)).props("outline") \
                .tooltip("Reprendre votre dernière enchère ou votre dernière carte").set_enabled(not rien and not occupe)
            if rien:
                ui.button(icon="play_arrow", on_click=jeu_commencer).props("unelevated").tooltip("Commencer les enchères")
            else:
                ui.button(icon="play_arrow").props("outline").set_enabled(False)

    def jeu_reprendre(c, d, x):
        """La donne telle qu'elle était : enchères refaites par le moteur, puis les cartes reposées une à une."""
        seq, ex, ind, al = jouer.avancer_alertes(d, x["seq"], x["siege"])
        p = None
        if x.get("cartes"):
            c_, decl = jouer.contrat(seq, d["donneur"])
            p = carte.Partie(d, c_, decl, seq, humain=x["siege"])
            for k in x["cartes"][1 if p.pos.jouees else 0:]: p.poser((k[0], k[1:]))   # l'entame du programme est déjà posée
            if x.get("reclame"): p.reclame = True; p.pos.gagnes = x.get("gagnes", p.pos.gagnes)
            p.pensees = list(x.get("pensees") or [])       # ce que pensaient les joueurs, gardé avec la donne
        jeu.update(cle=(c, d["n"]), siege=x["siege"], seq=seq, ex=ex, indice=ind, alertes=al, voir_indice=False, garde=ind is None, d=d,
                   affiche=len(seq), vus=len(seq), revele=False, pense=None, partie=p, pli_vu=None, revoir=None, msg="", garde_jeu=bool(p and p.fini()),
                   sans_jouer=bool(x.get("sans_jouer")), attend=bool(x.get("attend")) and not x.get("cartes"))
        if jeu["attend"]: jeu["affiche"] = 0            # pas encore commencé : rien sur la table
        if p and not p.fini(): background_tasks.create(carte_defense())   # si le programme avait la main

    def jeu_garder():
        """Garde la donne en cours telle quelle (jouer.garder_en_cours) : on la retrouve en revenant, même plus tard."""
        if not jeu.get("cle"): return
        c, n = jeu["cle"]; p = jeu.get("partie")
        cartes = [cc + r for pli, _ in p.plis for _x, cc, r in pli] + [cc + r for _x, cc, r in p.pos.pli] if p else []
        try:
            jouer.garder_en_cours(base_seance(c), n, dict(siege=jeu["siege"], seq=list(jeu["seq"]), cartes=cartes,
                                  reclame=bool(p and p.reclame), gagnes=p.pos.gagnes if p else 0, sans_jouer=bool(jeu.get("sans_jouer")),
                                  pensees=list(p.pensees) if p else [], attend=bool(jeu.get("attend") and not p)))
        except OSError:
            pass

    def reflexion(ex, k):
        """Le temps de réflexion d'un joueur avant son enchère : 0,9 s d'ordinaire, plus long plus on monte (1,5 s au
        palier de 3 et pour un contre, 1,9 s à la manche, 2,6 s au chelem) ; 1,3 s de plus quand une autre enchère
        convenait aussi (le texte de la règle le dit)."""
        b, t_ = (ex[k][1], ex[k][2] or "") if k < len(ex) else ("passe", "")
        serree = "convenait aussi" in t_ or "était possible" in t_ or "Décision serrée" in t_
        palier = int(b[0]) if b[:1].isdigit() else 0
        pause = 2.6 if palier >= 6 else 1.9 if palier >= 4 else 1.5 if palier == 3 or b in ("contre", "surcontre") else 0.9
        return pause + (1.3 if serree else 0)               # une décision serrée : encore un peu plus

    async def reveler():
        """Les enchères du programme apparaissent une à une, avec un temps de réflexion."""
        if jeu["revele"]: return
        jeu["revele"] = True
        try:
            while jeu["affiche"] < len(jeu["seq"]):
                if jeu["seq"][jeu["affiche"]] is not None and siege_de(jeu["d"], jeu["affiche"]) == jeu["siege"]:
                    jeu["affiche"] += 1; continue             # la vôtre : tout de suite
                jeu["pense"] = siege_de(jeu["d"], jeu["affiche"]); vue_jouer.refresh()
                await asyncio.sleep(reflexion(jeu["ex"], jeu["affiche"]))
                jeu["affiche"] += 1; jeu["pense"] = None; vue_jouer.refresh()
        finally:
            jeu["revele"] = False

    def sens_jouer(jusqu_a=None):
        """{rang: (siège, sens, alertée)} des enchères de la donne en cours, pour grille_html."""
        al = set(jeu.get("alertes") or [])
        return {k: (x, t_ or "", k in al) for k, (x, b, t_) in enumerate(jeu["ex"][:jusqu_a])}

    def saut(d, b):
        """L'enchère b saute-t-elle un palier ? (plus haut que le plus bas possible dans sa dénomination)"""
        if not b[:1].isdigit(): return False
        possibles = [int(x[0]) for x in jouer.legales(jeu["seq"], d["donneur"]) if x[1:] == b[1:]]
        return bool(possibles) and int(b[0]) > min(possibles)

    async def jeu_annonce(d, b):
        if jeu["affiche"] < len(jeu["seq"]) or b not in jouer.legales(jeu["seq"], d["donneur"]): return
        notes = []                                          # l'entraînement à l'alerte et au Stop
        k = len(jeu["seq"])
        seq, ex, ind, al = await run.io_bound(jouer.avancer_alertes, d, jeu["seq"] + [b], jeu["siege"])
        if k in al and not jeu.get("alerte"):              # une enchère artificielle sans le carton Alerte : reprise
            sens = next((t_ for x, bb, t_ in ex[k:k + 1] if t_), "")
            jeu["note"] = (f"{b} est une enchère artificielle" + (f" ({sens})" if sens else "") +
                           " : posez d'abord le carton Alerte, puis votre enchère.")
            vue_jouer.refresh(); return
        if jeu.get("alerte") and k not in al: notes.append(f"{b} n'est pas une enchère artificielle : pas besoin d'alerter.")
        if saut(d, b) and not jeu.get("stop"): notes.append(f"{b} est un saut : on pose d'abord le Stop.")
        elif jeu.get("stop") and not saut(d, b): notes.append("Le Stop annonce un saut ; cette enchère n'en est pas un.")
        jeu.update(note=" ".join(notes), stop=False, alerte=False)
        jeu.update(seq=seq, ex=ex, indice=ind, alertes=al, voir_indice=False, tout_voir=False, affiche=jeu["affiche"] + 1); vue_jouer.refresh()
        jeu_garder()
        await reveler()

    def ordre_jouer(data):
        """Les donnes dans l'ordre où les jouer : celui où le joueur choisi les a jouées (Options), sinon par numéro."""
        donnes = data["donnes"]
        if place_jouer() == "joueur" and lire_etat().get("ordre_joueur"):
            donnes = moi.ordre_des_donnes(data, moi.paires(data, joueur_jouer()))
        return [x["n"] for x in donnes if not x.get("a_completer")]

    def jeu_suivante(data, d):
        if jeu.get("mode") != "jouer":                  # la donne suivante s'ouvre pour être jouée (choisie dans la liste : le mode reste)
            jeu["mode"] = "jouer"; ecrire_etat(mode_jouer="jouer")
        ns = ordre_jouer(data)
        k = ns.index(d["n"]); aller(f"d{ns[(k + 1) % len(ns)]}")

    COUL_BOITE = {"SA": "sa", "♠": "pique", "♥": "coeur", "♦": "carreau", "♣": "trefle"}   # les couleurs des cartons

    def boite_encheres(d, actif=True):
        """Les enchères encore possibles, à partir du palier le plus bas, quatre paliers au plus ; le dernier bouton,
        « … », montre les autres. Les enchères dépassées ne s'affichent pas. actif=False : pendant que les autres
        enchérissent, la boîte reste là, grisée (l'utilisateur, 2026-11-11 : la barre ne saute pas à chaque tour)."""
        seq_v = jeu["seq"][:jeu["affiche"]]               # les enchères déjà montrées, pas celles que les robots vont dire
        ok = jouer.legales(seq_v, d["donneur"])          # grisée, la boîte ne se clique pas (.en-attente : pointer-events)
        rang = lambda b: int(b[0]) * 5 + jouer.DENOMS.index(b[1:])
        # comme une vraie boîte (l'utilisateur, 2026-11-11) : votre dernière enchère et tous les cartons en dessous sont
        # sortis (posés sur la table) ; ceux que les enchères des autres ont dépassés restent, en gris pâle
        miennes = [b for k, b in enumerate(seq_v) if siege_de(d, k) == jeu["siege"] and b and b[:1].isdigit()]
        sortis = rang(miennes[-1]) if miennes else 0
        legaux = sorted({int(b[0]) for b in ok if b[0].isdigit()})
        if not legaux: return
        presents = [n for n in range(1, 8) if any(rang(f"{n}{den}") > sortis for den in jouer.DENOMS)]
        niveaux = [n for n in presents if n >= legaux[0] - 1]   # au plus un palier tout en gris au-dessus des cartons
        tout = jeu.get("tout_voir") or len(niveaux) <= 4
        montres = niveaux if tout else niveaux[:4]
        with ui.element("div").classes("boite-encheres" + ("" if actif else " en-attente")):   # une boîte : les cartons debout, derrière
            with ui.element("div").classes("ratelier"):
                for n in montres:
                    with ui.row().classes("gap-1 no-wrap"):
                        for den in jouer.DENOMS:                  # ♣ ♦ ♥ ♠ SA : l'ordre des enchères
                            b = f"{n}{den}"
                            if b in ok:
                                ui.html(f"<div class='tirette {COUL_BOITE[den]}'>{n}{den}</div>", sanitize=False) \
                                    .on("click", lambda b=b: jeu_annonce(d, b))
                            elif rang(b) > sortis:              # dépassée par les autres : encore dans la boîte, en gris
                                ui.html(f"<div class='tirette depassee'>{n}{den}</div>", sanitize=False)
                            else:
                                ui.html("<div class='tirette vide'></div>", sanitize=False)
                if not tout:
                    ui.html("<div class='tirette autres'>… les autres enchères</div>", sanitize=False) \
                        .on("click", lambda: (jeu.update(tout_voir=True), vue_jouer.refresh()))
            with ui.column().classes("gap-1 compartiment"):             # devant : Passe, X, XX, chacun avec son onglet
              with ui.row().classes("gap-1 no-wrap justify-center w-full"):
                for b, nom, tab in (("passe", "PASS", "PASS"), ("contre", "X", "X"), ("surcontre", "XX", "XX")):
                    el = ui.html(f"<div class='onglet {b}{'' if b in ok else ' eteint'}' data-tab='{tab}'>{nom}</div>", sanitize=False)
                    if b in ok: el.on("click", lambda b=b: jeu_annonce(d, b))
              # Stop et Alerte : dans la boîte aussi, sur un second rang (l'utilisateur, 2026-11-11) : ce ne sont pas des enchères
              with ui.row().classes("gap-1 no-wrap justify-center w-full"):
                ui.html(f"<div class='onglet stop{' pose' if jeu.get('stop') else ''}' data-tab='S' title='Avant un saut'>STOP</div>", sanitize=False) \
                    .on("click", lambda: (jeu.update(stop=not jeu.get("stop")), vue_jouer.refresh()))
                # Alerte : posée avant votre enchère artificielle (l'utilisateur, 2026-11-11) ; sans elle, l'enchère est reprise
                ui.html(f"<div class='onglet alerte{' pose' if jeu.get('alerte') else ''}' data-tab='A' "
                        "title='Avant une enchère artificielle'>ALERT</div>", sanitize=False) \
                    .on("click", lambda: (jeu.update(alerte=not jeu.get("alerte")), vue_jouer.refresh()))

    # ---------------------------------------------------------------- le jeu de la carte
    def carte_demarrer(d):
        c_, decl = jouer.contrat(jeu["seq"], d["donneur"])
        jeu.update(partie=carte.Partie(d, c_, decl, jeu["seq"], humain=jeu["siege"]), pli_vu=None, revoir=None, msg="", garde_jeu=False, sans_jouer=False)
        jeu_garder(); vue_jouer.refresh(); background_tasks.create(carte_defense())

    async def carte_poser(x):
        """Pose une carte ; si elle termine le pli, le pli reste un instant sous les yeux."""
        p = jeu["partie"]; avant = len(p.plis)
        p.poser(x); jeu["msg"] = ""; jeu_garder()
        if len(p.plis) > avant:                      # le pli complet : la carte gagnante luit doucement, puis les quatre cartes
            pli, g = p.plis[-1]                      # vont vers les plis gardés du camp gagnant (l'utilisateur, 2026-11-11)
            jeu["gagnante"] = next(((cc, r.translate(carte.FR)) for x_, cc, r in pli if x_ == g), None)
            jeu["pli_vu"] = p.plis[-1]; vue_jouer.refresh()
            await asyncio.sleep(1.1)
            places = jeu.get("places") or ()               # vers le joueur qui a gagné le pli (le mort aussi) : c'est ainsi
            jeu["ramasse"] = dict(zip(places, ("haut", "gauche", "droite", "bas"))).get(g, "bas")   # qu'on voit qui l'a gagné
            vue_jouer.refresh()
            await asyncio.sleep(.45)
            jeu.update(pli_vu=None, ramasse=None, gagnante=None, compte_monte=(p.camp(g), time.monotonic()))   # le pli arrive : le compte roule
        vue_jouer.refresh()

    async def carte_defense():
        """Le programme joue les autres places (les défenseurs, ou le déclarant et son mort quand vous défendez), chacun
        après un temps de réflexion, jusqu'à votre tour."""
        p = jeu["partie"]
        while p and not p.fini() and not p.au_joueur() and jeu["partie"] is p:
            jeu["pense"] = p.au_trait(); vue_jouer.refresh()
            pause = 0.4 if len(p.legales()) == 1 else 1.3 if not p.pos.pli else 0.8   # forcée : vite ; une entame : on réfléchit
            x, _ = await asyncio.gather(run.io_bound(p.carte_robot), asyncio.sleep(pause))
            if getattr(p, "difficile", False): await asyncio.sleep(1.4)   # la bonne carte ne s'imposait pas : il hésite
            jeu["pense"] = None
            await carte_poser(x)

    async def carte_jouer(x):
        p = jeu["partie"]
        if not p or jeu["pense"] or jeu["pli_vu"] or p.fini() or not p.au_joueur(): return
        if x not in p.legales():                       # interdite : la carte tremble et reste dans la main
            entame = p.pos.pli[0][1] if p.pos.pli else None
            mort = p.au_trait() == p.mort() and not p.en_defense()
            jeu["secoue"] = (x[0], x[1].translate(carte.FR))
            jeu["msg"] = ((f"Le mort a du {entame} : il doit fournir. Choisissez une autre carte du mort." if mort else
                           f"Vous avez du {entame} : vous devez fournir.") if entame else "Cette carte ne peut pas être jouée.")
            vue_jouer.refresh()
            await asyncio.sleep(.7); jeu["secoue"] = None
            return
        jeu["msg"] = ""
        p.pensees.append(p.pensee(p.au_trait(), x, humain=True))   # votre carte, pour la relecture
        await carte_poser(x)
        await carte_defense()

    async def carte_indice():
        p = jeu["partie"]
        if not p or p.fini(): return
        jeu["msg"] = "Le coach cherche…"; vue_jouer.refresh()
        s_ = p.au_trait()
        def calcul():
            x_ = p.indice()
            z = p.pensee(s_, x_)                              # son calcul : pourquoi cette carte plutôt qu'une autre
            return x_, carte.justification(z, p.decl), z.get("plan") or ""
        x, pourquoi, plan = await run.io_bound(calcul)
        jeu["msg"] = f"Le coach jouerait {carte.carte_fr(*x)} ({SIEGE[s_]})."
        jeu["indice_pourquoi"] = (pourquoi, plan)              # le pourquoi : en cliquant sur l'indice (une fenêtre)
        vue_jouer.refresh()

    async def carte_reclamer():
        p = jeu["partie"]
        if not p or p.fini(): return
        ok = await run.io_bound(p.reclamer)
        if ok: jeu_garder()
        jeu["msg"] = "" if ok else "Pas encore : la défense peut faire au moins une levée de plus."
        vue_jouer.refresh()

    def rangees_plis(p, places, garder):
        """Les plis gardés : une seule rangée par camp (l'utilisateur, 2026-11-11), la vôtre en bas, et celle d'un
        adversaire (le premier retenu par garder(x) : à gauche, sinon à droite ou en face ; jamais le mort), chacune avec
        son nombre de levées. Votre partenaire et le second adversaire n'en montrent pas."""
        vus, h = set(), ""
        for x, ou in sorted(zip(places, ("haut", "gauche", "droite", "bas")),
                            key=lambda xo: ("bas", "gauche", "droite", "haut").index(xo[1])):
            if not garder(x) or p.camp(x) in vus: continue
            h += plis_gardes(p, x, ou); vus.add(p.camp(x))
        return h

    def plis_gardes(p, x, ou, compte=True):
        """Les cartes du joueur x retournées devant lui sur la table, près de son bord, dans l'ordre, chacune en partie sur
        la précédente, comme en duplicate : vers son partenaire si son camp a gagné le pli, en travers sinon."""
        plis = p.plis
        if plis and jeu.get("pli_vu") is plis[-1]: plis = plis[:-1]   # le pli encore sur la table n'est pas encore gardé ni compté
        if not plis: return ""
        cote = ou in ("gauche", "droite")
        gagne = lambda g: p.camp(g) == p.camp(x)
        forme = lambda g: ("couche" if gagne(g) else "") if cote else ("" if gagne(g) else "couche")
        ici = {"bas": "bottom:12px;left:50%;transform:translateX(-50%)", "haut": "top:12px;left:50%;transform:translateX(-50%)",
               "gauche": "left:12px;top:50%;transform:translateY(-50%)", "droite": "right:12px;top:50%;transform:translateY(-50%)"}[ou]
        return (f"<div class='plis-gardes{' colonne' if cote else ''}{'' if ou == 'bas' else ' adverse'}' style='position:absolute;{ici}' "
                f"title='Vert, vers le partenaire : pli gagné ; gris, en travers : pli perdu'>"
                + "".join(f"<div class='dos {forme(g)}{' gagne' if gagne(g) else ''}"
                          + ("' title='Voir le dernier pli' onclick=\"emitEvent('dernier_pli')\"" if k == len(plis) - 1 else "'")
                          + "></div>" for k, (_, g) in enumerate(plis))   # gagné : vert ; la dernière : voir le dernier pli
                + (compte_html(sum(gagne(g) for _, g in plis), ou, roule_depuis(p.camp(x))) if compte else "")
                + "</div>")      # au bout de chaque rangée : les levées de ce camp (l'utilisateur, 2026-11-11 : aussi pour la défense)

    def roule_depuis(camp):
        """Depuis combien de secondes le compte de ce camp roule (None : il ne roule pas) : un autre rafraîchissement
        pendant ce temps reprend l'animation où elle en est, sans la recommencer."""
        m = jeu.get("compte_monte")
        if not m or m[0] != camp: return None
        e = time.monotonic() - m[1]
        return e if e < .45 else None

    def compte_html(n, ou, roule=None):
        """Le cercle des levées d'un camp ; roule (secondes écoulées) : il vient d'en gagner une, le nombre monte de n-1 à n."""
        r = roule is not None and n
        cls = "compte-plis" + ("" if ou == "bas" else " autre") + (" roule" if r else "")
        txt = (f"<span class='pile' style='animation-delay:-{roule:.2f}s'><span>{n - 1}</span><span>{n}</span></span>"
               if r else str(n))
        return f"<div class='{cls}' title='Les levées de ce camp'>{txt}</div>"

    BORD_PLI = 54          # une carte jouée : sur la table, devant son joueur, au-delà de ses plis gardés (12 + 30 px)
    ICI_PLI = {"haut": f"top:{BORD_PLI}px;left:50%;transform:translateX(-50%)",
               "bas": f"bottom:{BORD_PLI}px;left:50%;transform:translateX(-50%)",
               "gauche": f"left:{BORD_PLI}px;top:50%;transform:translateY(-50%)",
               "droite": f"right:{BORD_PLI}px;top:50%;transform:translateY(-50%)"}

    def carte_posee(c, r, ou=None, ecoule=None, premiere=False, bulle="", cote=""):
        """Une carte jouée, comme dans les mains ; ou : le côté d'où elle glisse quand elle vient d'être posée. premiere :
        la carte qui a commencé le pli, bordée de noir ; bulle : ce qu'en pensait le joueur, au survol (la Démo)."""
        anim = f" arrive-{ou}" if ou else ""
        if jeu.get("ramasse"): anim = f" vers-{jeu['ramasse']}"          # le pli ramassé, vers les plis gardés du gagnant
        elif jeu.get("gagnante") == (c, r): anim += " gagnante"           # la carte qui gagne le pli
        retard = f";animation-delay:-{ecoule:.2f}s" if ou else ""
        h = (f"<div data-c='{c}{r}' class='carte{' r' if c in '♥♦' else ''}{f' premiere p-{cote}' if premiere and cote else ''}{anim}' "
             f"style='margin:0{retard}'>{face(r)}<br/>{c}</div>")
        return f"<div class='carte-sens'>{h}<span class='bulle'>{bulle}</span></div>" if bulle else h

    def pli_cartes(p, places, posees, derniere=None, ecoule=0, mort=None, bulles=None):
        """Les cartes du pli, chacune sur la table juste devant le joueur qui l'a posée, comme les cartons des enchères ;
        celle du mort (mort : son siège, quand il est étalé sur la table) est dessinée à côté de ses cartes (mort_etale)."""
        haut, gauche, droite, bas = places
        cote = {haut: "haut", gauche: "gauche", droite: "droite", bas: "bas"}
        h = ""
        premier = next(iter(posees), None)              # posees suit l'ordre du pli : la première carte l'a commencé
        mort_ou = cote.get(mort)                        # le mort étalé en haut (ou en bas) : ses colonnes descendent sur la table,
        decale = {"haut": "top:64%", "bas": "top:36%"}.get(mort_ou)   # les cartes des côtés plus bas (plus haut), sous la sienne
        for x, (c, r) in posees.items():
            if x == mort: continue
            vient = cote[x] if x == derniere else None
            ici = ICI_PLI[cote[x]]
            if decale and cote[x] in ("gauche", "droite"): ici = ici.replace("top:50%", decale)
            h += (f"<div style='position:absolute;{ici};z-index:3'>"
                  f"{carte_posee(c, r, vient, ecoule, premiere=x == premier, bulle=(bulles or {}).get(x, ''), cote=cote[x])}</div>")
        return h

    def pli_en_cours(p):
        """(posées {siège: (couleur, rang)}, le siège de la carte qui vient d'arriver ou None, depuis combien de temps)."""
        pli = jeu["pli_vu"][0] if jeu["pli_vu"] else p.pos.pli
        posees = {s: (c, r.translate(carte.FR)) for s, c, r in pli}
        n = len(p.pos.jouees)                          # une carte vient d'être posée : elle glisse depuis le bord du joueur
        if n > jeu.get("cartes_vues", 0): jeu["carte_arrive"] = (n, time.monotonic())
        jeu["cartes_vues"] = n
        n_, t_ = jeu.get("carte_arrive") or (0, 0)
        ecoule = time.monotonic() - t_
        return posees, (pli[-1][0] if pli and n_ == n and ecoule < .5 else None), ecoule

    def pli_html(p, places, mort=None):
        """Le pli en cours, chaque carte devant le joueur qui l'a posée, et les plis gardés."""
        posees, derniere, ecoule = pli_en_cours(p)
        return (f"<div style='position:absolute;inset:0;pointer-events:none'>"
                f"{pli_cartes(p, places, posees, derniere, ecoule, mort)}"
                + rangees_plis(p, places, lambda x: x == places[3] or (p.camp(x) != p.camp(places[3]) and x != p.mort()))
                + "</div>")   # les vôtres, ceux des adversaires (pas du mort : il est étalé)

    def etui(d, places, petit=False, pale=False):
        """L'étui de la donne au centre, comme un vrai étui : Nord et Sud toujours sur les petits côtés (debout quand
        Nord-Sud sont en haut et en bas, couché sinon), leurs bandes sur toute la largeur, Est et Ouest entre elles ;
        chaque nom se lit depuis sa place, en capitales, blanc sur rouge si son camp est vulnérable, sur vert sinon ; le
        donneur écrit « Donneur » en rouge ou vert sur blanc ; le joueur qui réfléchit clignote. pale : pendant le jeu de la
        carte, l'étui reste sur la table en filigrane, ses couleurs à peine plus foncées que la table (ETUI_PALE)."""
        v = d["vul"]; vul = lambda x: v == "Tous" or v == ("N-S" if x in "NS" else "E-O")
        l, L, h, f = (84, 149, 22, 12) if petit else ETUI      # l × L : l'étui (9:16), h : épaisseur des bandes
        haut, gauche, droite, bas = places
        debout = haut in "NS"
        W, H = (l, L) if debout else (L, l)
        if debout:                                            # grid-area : ligne, colonne, ligne de fin, colonne de fin
            place = {haut: "1 / 1 / 2 / 4", bas: "3 / 1 / 4 / 4", gauche: "2 / 1 / 3 / 2", droite: "2 / 3 / 3 / 4"}
        else:                                                 # Nord et Sud à gauche et à droite, Est-Ouest entre eux
            place = {gauche: "1 / 1 / 4 / 2", droite: "1 / 3 / 4 / 4", haut: "1 / 2 / 2 / 3", bas: "3 / 2 / 4 / 3"}
        P = ETUI_PALE
        def bande(x):
            teinte = (P["rouge"] if vul(x) else P["vert"]) if pale else "#c0141c" if vul(x) else "#2e7d32"
            blanc = P["fond"] if pale else "#fff"
            if x == d["donneur"]:                             # le donneur : « Donneur » en couleur sur blanc
                nom, fond, encre = "Donneur", f"{blanc};border:2px solid {teinte}", P["encre"] if pale else teinte
            else:                                             # les autres : le nom en capitales, blanc sur la couleur
                nom, fond, encre = SIEGE[x].upper(), teinte, P["encre"] if pale else "#fff"
            if x in (haut, bas):
                forme = "width:100%;height:100%;" + ("transform:rotate(180deg);" if x == haut else "")
            else:
                forme = "width:100%;height:100%;writing-mode:vertical-rl;" + ("transform:rotate(180deg);" if x == droite else "")   # le haut des lettres vers le centre, loin du lecteur
            return (f"<div class='{'pense' if jeu.get('pense') == x else ''}' style='grid-area:{place[x]};{forme}display:flex;"
                    f"align-items:center;justify-content:center;border-radius:5px;font-size:{f}px;font-weight:700;color:{encre};"
                    f"box-sizing:border-box;background:{fond}'>{nom}</div>")
        return (f"<div title='En rouge les camps vulnérables, en vert les autres' style='display:grid;box-sizing:border-box;"
                f"width:{W}px;height:{H}px;grid-template-columns:{h}px 1fr {h}px;grid-template-rows:{h}px 1fr {h}px;gap:4px;"
                f"padding:6px;border-radius:8px;" + (f"background:{P['fond']};border:1px solid {P['bord']}'>" if pale else
                "background:#e4e7eb;border:1px solid #c8ced5;box-shadow:0 1px 2px rgba(0,0,0,.12)'>") +
                f"{bande(haut)}{bande(gauche)}{bande(droite)}{bande(bas)}</div>")

    ETUI = (135, 240, 30, 14)    # les côtés de l'étui (9:16), l'épaisseur des bandes, le texte
    TOURNE = 1.4                 # secondes : la table tourne d'un demi-tour quand le déclarant que vous jouez passe devant vous
    # l'étui en filigrane pendant le jeu de la carte : quelques nuances de la table (#f3efe7), sans rouge ni vert
    ETUI_PALE = {"fond": "#ece6db", "bord": "#e2dacc", "rouge": "#e0d8ca", "vert": "#e0d8ca", "encre": "#b3a796"}

    LARGEUR_CARTON = {"bid": 84, "carre": 56}             # .carton.bid, .carton.carre
    VU_CARTON = {"bid": 58, "carre": 36}                   # ce qui dépasse d'un carton recouvert : son indice, ou son onglet

    lettres = lambda m: "".join(f"<b>{c}</b>" for c in m)   # un mot écrit tout le long du bord du carton

    def tapis_encheres(d, places, vues=None):
        """Les enchères posées devant chaque joueur, comme les cartons d'une boîte à enchères ; la dernière ressort.
        vues : les enchères à montrer (la démonstration) ; sinon celles de la donne jouée."""
        demo_ = vues is not None
        if vues is None: vues = jeu["seq"][:jeu["affiche"]]
        devant = {x: [] for x in "NESO"}
        for k, b in enumerate(vues): devant[siege_de(d, k)].append(b)
        dernier = siege_de(d, len(vues) - 1) if vues else None
        if len(vues) > jeu.get("vus", 0): jeu["arrive"] = (len(vues), time.monotonic())   # un carton vient d'être posé
        jeu["vus"] = len(vues)
        n_, t_ = jeu.get("arrive") or (0, 0)
        ecoule = time.monotonic() - t_                       # la table se redessine souvent : le glissement reprend où il en était
        nouveau = n_ == len(vues) and ecoule < .5
        def carton(b, recent, k, derniere=False, avant=None):
            """Un carton, dessiné à l'endroit pour qui le lit en face : la bande de droite (le niveau et la couleur, ou le
            nom) reste visible sous le carton suivant ; Passe, X et XX sont presque carrés, avec leur onglet."""
            cls = " derniere" * derniere + " recent" * recent
            retard = ""
            if recent and nouveau:                           # depuis le bord du joueur (le cadre est tourné vers lui)
                cls += " arrive-bas"; retard = f";animation-delay:-{ecoule:.2f}s"
            if b in ("passe", "contre", "surcontre"):        # le nom écrit le long de la base, l'onglet en haut à droite
                tab, corps = {"passe": ("PASS", f"<span class='base mot'>{lettres('PASS')}</span>"),   # PASS, même en France
                              "contre": ("X", "<span class='base croix'><b>X</b></span>"),
                              "surcontre": ("XX", f"<span class='base croix'>{lettres('XX')}</span>")}[b]
                face = f"<span class='tab'></span>{corps}"   # l'onglet sans texte : rien à choisir dans une boîte ici
                cls = f" carre {b}" + cls
            else:
                n, den = b[0], b[1:]
                c = COUL_BOITE.get(den, "sa")
                face = (f"<span class='grand'><b>{n}</b>"
                        f"<i class='{'sa' if den == 'SA' else ''}'>{den}</i></span>")
                cls = f" bid {c}" + cls
            marge = f";margin-left:-{LARGEUR_CARTON[avant] - VU_CARTON[avant]}px" if avant else ""   # le carton d'avant en dépasse de VU_CARTON
            return f"<div class='carton{cls}' style='z-index:{k + 1}{marge}{retard}'><div class='face'>{face}</div></div>"
        def a_part(x):
            """Stop et Alerte : posés devant le joueur, à gauche de sa rangée, pas parmi les enchères."""
            out = ""
            if demo_: return out
            if x == jeu["siege"] and jeu.get("stop"):
                out += "<div class='carton carre stop a-part derniere'><div class='face'><span class='tab gauche'></span><span class='base mot'>"+lettres('STOP')+"</span></div></div>"
            if x == jeu["siege"] and jeu.get("alerte"):
                out += "<div class='carton carre alerte a-part derniere'><div class='face'><span class='tab'></span><span class='base mot'>"+lettres('ALERT')+"</span></div></div>"
            return out
        def pile(x, ou):
            """Les cartons d'un joueur, posés de gauche à droite devant lui, retournés (à l'endroit pour son partenaire,
            qui les lit de droite à gauche), le dernier dessus. La rangée part d'un point fixe, à la même distance du bord
            pour les quatre joueurs : un carton de plus s'ajoute au bout, les autres ne bougent pas. Le cadre est dessiné
            comme pour le joueur du bas, puis tourné vers la place du joueur (origine : le coin bas-gauche de la rangée)."""
            bs = devant[x]
            forme = lambda b: "carre" if b in ("passe", "contre", "surcontre") else "bid"
            cartons = "".join(carton(b, x == dernier and k == len(bs) - 1, k, k == len(bs) - 1, forme(bs[k - 1]) if k else None)
                              for k, b in enumerate(bs))
            sep = a_part(x)
            dec = 120 + (86 if sep else 0)                   # Stop ou Alerte posé : la rangée commence un peu plus à gauche
            pos = {"bas": f"left:calc(50% - {dec}px);bottom:{bord}px",
                   "haut": f"left:calc(50% + {dec}px);bottom:calc(100% - {bord}px);transform:rotate(180deg)",
                   "gauche": f"left:{bord}px;bottom:calc(50% + {dec}px);transform:rotate(90deg)",
                   "droite": f"left:calc(100% - {bord}px);bottom:calc(50% - {dec}px);transform:rotate(-90deg)"}[ou]
            return f"<div class='cadre' style='{pos}'>{sep}<div class='pile'>{cartons}</div></div>"
        haut, gauche, droite, bas = places
        bord = 24                                          # la distance au bord de la table (l'onglet dépasse un peu)
        return (f"<div style='position:absolute;inset:0'>"
                f"{pile(haut, 'haut')}{pile(bas, 'bas')}{pile(gauche, 'gauche')}{pile(droite, 'droite')}"
                f"<div style='position:absolute;left:50%;top:50%;transform:translate(-50%,-50%)'>{etui(d, places)}</div></div>")
                # l'étui au centre pendant les enchères seulement ; pendant le jeu de la carte, la table reste libre (l'utilisateur)

    ORDRE_MAIN = "♠♥♣♦"                                    # noir, rouge, noir, rouge

    face = lambda r: "<span class='dix'>10</span>" if r == "X" else r   # sur une carte à jouer, le dix s'écrit 10 (X dans les textes)

    marques_dm = {}                                       # démonstration : {(couleur, rang fr): (levées, meilleure ?)}

    def carte_el(coul, r, jouables, sur_clic):
        rouge_ = " r" if coul in "♥♦" else ""
        ok = jouables is not None and (coul, r) in jouables
        m = marques_dm.get((coul, r))
        badge = f"<span class='dm {'mieux' if m[1] else 'moins'}'>{m[0]}</span>" if m else ""
        tremble = " secoue" if jeu.get("secoue") == (coul, r) else ""
        el = ui.html(f"<div data-c='{coul}{r}' class='carte{rouge_}{' jouable' if ok else ' terne' if jouables is not None else ''}{tremble}'>{face(r)}<br/>{coul}{badge}</div>",
                     sanitize=False)
        if ok: el.on("click", lambda x=(coul, r): sur_clic(x))

    def mort_etale(cartes, jouables, sur_clic, atout, cote="haut", posee="", a_vous=False):
        """Le mort étalé comme à la table : une colonne par couleur, la plus forte carte en haut, l'atout à gauche
        (à la droite du mort), puis les couleurs en alternant noir et rouge. Sur un côté (cote « gauche » ou « droite »),
        une ligne par couleur, la plus forte carte vers le mort, l'atout toujours à sa droite. posee : la carte que le
        mort vient de jouer, juste à côté de ses cartes, du côté du centre ; a_vous : c'est à vous de jouer du mort (souligné)."""
        autres = [c for c in ORDRE_MAIN if c != atout]
        ordre = ([atout] if atout in ORDRE_MAIN else []) + autres
        if cote in ("gauche", "droite"):
            if cote == "gauche": ordre = ordre[::-1]          # le mort à gauche regarde vers la droite : sa droite est en bas
            with ui.row().classes("no-wrap items-center gap-3"):
                if cote == "droite" and posee: ui.html(posee, sanitize=False)
                with ui.column().classes("gap-1 mort-table mort-cote " + ("items-start" if cote == "gauche" else "items-end")
                                         + " a-vous" * a_vous):
                    for coul in ordre:
                        with ui.row().classes("no-wrap gap-0 ligne-mort"):
                            rangs = list(cartes.get(coul, "")) or [None]
                            if cote == "droite": rangs = rangs[::-1]    # à droite, la plus forte contre le bord
                            for r in rangs:
                                if r is None: ui.html(f"<div class='carte vide'>{coul}</div>", sanitize=False)
                                else: carte_el(coul, r, jouables, sur_clic)
                if cote == "gauche" and posee: ui.html(posee, sanitize=False)
            return
        with ui.column().classes("items-center gap-3"):
            if cote == "bas" and posee: ui.html(posee, sanitize=False)   # le mort en bas (la démonstration) : sa carte vers le centre
            with ui.row().classes("no-wrap items-start gap-3 mort-table" + " a-vous" * a_vous):
                for coul in ordre:
                    with ui.column().classes("gap-0 colonne-mort"):
                        if not cartes.get(coul):
                            ui.html(f"<div class='carte vide'>{coul}</div>", sanitize=False)
                        for r in cartes.get(coul, ""):
                            carte_el(coul, r, jouables, sur_clic)
            if posee and cote != "bas": ui.html(posee, sanitize=False)

    def eventail(cartes, jouables=None, sur_clic=None, colonnes=False, grande=False, a_vous=False):
        """Une main en cartes : {couleur: rangs français du plus fort au plus faible}. En ligne, un petit espace entre les
        couleurs ; en colonnes (une main sur le côté), une couleur par ligne. jouables : les cartes cliquables ;
        grande : votre main, plus grande, qui luit quand c'est à vous."""
        cls = " main-grande" * grande + " a-vous" * (grande and a_vous)
        with (ui.column().classes("gap-1") if colonnes else ui.row().classes("no-wrap items-end gap-0 eventail" + cls)):
            for coul in ORDRE_MAIN:
                rangs = cartes.get(coul, "")
                if colonnes and not rangs:
                    ui.html(f"<div class='carte vide'>{coul}</div>", sanitize=False); continue
                if not rangs: continue                         # une chicane en ligne : rien, pas même une marge
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

    def table(d, places, contenu, centre=None, sur_table=(), tour=None):
        """La table, une grande surface vert clair : l'étui, les cartons, le pli et le mort posé dessus ; les mains des
        joueurs autour. contenu(siège, position) dessine une place ; sur_table : les positions posées sur la table (le mort) ;
        tour : le siège qui doit enchérir ou jouer, montré par un petit triangle sur le bord de la table, de son côté."""
        haut, gauche, droite, bas = places
        large = "gauche" in sur_table or "droite" in sur_table          # le mort sur un côté : la table en 16:9
        haute = "haut" in sur_table or "bas" in sur_table               # le mort en haut ou en bas : la table plus haute que large
        forme = (f"width:{LARGEUR_TABLE_LARGE};height:{COTE_TABLE};" if large else
                 f"width:{COTE_TABLE};height:calc({COTE_TABLE} + 140px);" if haute else f"width:{COTE_TABLE};aspect-ratio:1 / 1;")
        with ui.element("div").classes("w-full").style("overflow:hidden;padding-top:8px"), \
                ui.element("div").classes("ajuste").style("width:max-content;transform-origin:0 0") \
                    .props(f'data-donne="{d["n"]}-{bas}"'):             # rétrécit avec la fenêtre (JS_AJUSTE) ; JS_GLISSE
            ecoule = time.monotonic() - jeu.get("tourne", -99)   # la table qui tourne : le demi-tour reprend où il en était
            tourne = f"animation:tourne {TOURNE}s ease-in-out;animation-delay:-{ecoule:.2f}s" if ecoule < TOURNE else ""
            noms = jeu.get("noms") or {}
            v = d["vul"]; vul = lambda x: v == "Tous" or v == ("N-S" if x in "NS" else "E-O")
            def place(x, ou):                            # sa place (NORD…) et son nom (s'il est connu), discrets, près de sa main
                nom_x = noms.get(x, "")
                # à qui le tour : son nom et ses cartes luisent en jaune, vous comme les robots (l'utilisateur, 2026-11-11 :
                # ni triangle, ni soulignement, ni gras)
                etat = ""; qui = ""
                if ou in ("haut", "bas"):                # sur la même ligne : pas de hauteur en plus (en haut, aligné en haut)
                    with ui.row().classes(("items-start" if ou == "haut" else "items-center") + " no-wrap gap-3" + qui):
                        ui.html(nom_html(nom_x, deux_lignes=True, droite=True, etat=etat, siege=x), sanitize=False)   # Prénom / NOM, contre la main
                        contenu(x, ou)
                elif ou in sur_table:                    # le mort étalé sur un côté de la table : son nom dessous, loin du pli
                    with ui.column().classes("items-start gap-1" + qui):
                        contenu(x, ou); ui.html(nom_html(nom_x, deux_lignes=True, etat=etat, siege=x), sanitize=False)
                else:                                    # au-dessus de la main, aligné à gauche sur ses cartes
                    with ui.column().classes("items-start gap-1" + qui):
                        ui.html(nom_html(nom_x, deux_lignes=True, etat=etat, siege=x), sanitize=False); contenu(x, ou)
            with ui.grid(columns="auto auto auto" if large else "1fr auto 1fr").style(tourne) \
                    .classes("items-center gap-x-2 gap-y-4"):            # les mains des côtés contre la table
                with ui.column().classes("items-center").style("grid-column: 1 / 4"):
                    if "haut" not in sur_table: place(haut, "haut")
                with ui.column().classes("items-end"):
                    if "gauche" not in sur_table: place(gauche, "gauche")
                with ui.column().classes("items-center gap-4").style(       # la table, carrée comme une vraie, à la taille de la fenêtre
                        f"{forme}background:#f3efe7;border:1px solid #e3dccf;border-radius:28px;padding:12px 16px;"
                        "justify-content:space-between;position:relative"):
                    if "haut" in sur_table: place(haut, "haut")
                    for ou, x in (("gauche", gauche), ("droite", droite)):   # le mort d'un côté : sur la table, contre son bord
                        if ou in sur_table:
                            with ui.element("div").style(f"position:absolute;{'left' if ou == 'gauche' else 'right'}:14px;"
                                                         "top:50%;transform:translateY(-50%);z-index:2"):
                                place(x, ou)
                    if centre: centre()
                    # plus de triangle sur le bord de la table : seules vos cartes luisent quand c'est à vous (.a-vous)
                    if "bas" in sur_table: place(bas, "bas")
                with ui.column().classes("items-start"):
                    if "droite" not in sur_table: place(droite, "droite")
                with ui.column().classes("items-center").style(
                        "grid-column: 1 / 4" + ("" if "bas" in sur_table else ";margin-top:12px")):
                    if "bas" not in sur_table: place(bas, "bas")             # votre main, un peu en retrait de la table

    def mains_fr(d, x):
        return dict(zip(carte.COULEURS, ("" if m == "-" else m for m in d["mains"][x].split())))

    def vue_carte(c, d, data, places):
        """Le jeu de la carte : la table et le pli au centre ; le panneau de droite est dessiné par vue_jouer."""
        p = jeu["partie"]; s = places[3]; part = jouer.PART[s]   # le siège du bas : le vôtre, ou le déclarant que vous jouez
        tour = p.au_trait()
        cliquable = not p.fini() and not jeu["pense"] and not jeu["pli_vu"] and p.au_joueur(tour)
        voit = lambda x: p.fini() or x == s or (x == p.mort() and p.pos.jouees) or (p.camp(x) and not p.en_defense())

        def contenu(x, ou):
            if voit(x):
                with ui.column().classes("gap-1 " + ("items-center" if ou in ("haut", "bas") else "")):
                    if not p.fini():
                        cartes = {k: "".join(r.translate(carte.FR) for r in v) for k, v in p.pos.reste[x].items()}
                        # toutes les cartes de la main se cliquent, comme à la table : rien ne dit lesquelles sont permises
                        # (l'utilisateur, 2026-11-11) ; une carte interdite tremble (carte_jouer)
                        jouables = ({(k, r) for k, v in cartes.items() for r in v} if cliquable and tour == x else None)
                        clic = lambda y: carte_jouer((y[0], y[1].translate(carte.EN)))
                        if x == p.mort():
                            posees, derniere, ecoule = pli_en_cours(p)
                            cr = posees.get(x)
                            mort_etale(cartes, jouables, clic, p.den, ou,
                                       carte_posee(*cr, ou if x == derniere else None, ecoule,
                                                   premiere=x == next(iter(posees), None), cote=ou) if cr else "",
                                       a_vous=cliquable and tour == x)
                        else: eventail(cartes, jouables, clic, colonnes=ou in ("gauche", "droite"), grande=x == s,
                                       a_vous=cliquable and tour == x)   # les cartes jouables ont déjà leur bord
            elif not p.fini():                               # un adversaire : sa main cachée, en éventail fermé
                dos(ou, sum(len(v) for v in p.pos.reste[x].values()))
        table(d, places, contenu, lambda: ui.html(pli_html(p, places, None if p.fini() else p.mort()), sanitize=False),
              sur_table=[ou for x, ou in zip(places, ("haut", "gauche", "droite", "bas")) if x == p.mort() and not p.fini()],
              tour=None if p.fini() or jeu["pli_vu"] else tour)

    def options_joueurs(*garder):
        """Le choix d'un joueur : « Aucun (tous les joueurs) », puis votre nom (Réglages, « Votre nom »), une ligne de
        séparation, puis tous les autres, par ordre alphabétique. garder : des noms à montrer même s'ils ne sont plus
        dans les séances."""
        noms_ = moi.tous_les_noms(rapport.glob_seances("*" + rapport.BC))
        noms_ += [x for x in garder if x and x not in noms_]
        mien = lire_etat().get("mon_nom")
        out = {"": "Aucun (tous les joueurs)"}
        if mien: out[mien] = f"{mien} (vous)"
        autres = sorted((x for x in noms_ if x != mien), key=str.lower)
        if mien and autres: out[SEPARATEUR] = "──────────"
        out.update({x: x for x in autres})
        return out

    def siege_pour(c, d):
        """Votre place à cette donne, comme dans Jouer : celle de la partie gardée, sinon celle que donne l'option
        d'Options (sans rien lancer : la Démo ne fait pas jouer les robots de votre partie)."""
        if jeu.get("cle") == (c, d["n"]) and jeu.get("siege"): return jeu["siege"]
        x = jouer.en_cours(base_seance(c), d["n"]) or {}
        if x.get("siege"): return x["siege"]
        if place_jouer() == "joueur":
            pj = moi.place_du_joueur(lire_seance(c), d, joueur_jouer())
            if pj: return pj["siege"]
        if place_jouer() in ("camp", "defense", "hasard"): return None     # tirée au sort : pas encore connue
        return jouer.siege_choisi(place_jouer(), d, lire_analyses(c))

    def donne_jouee(c, d):
        """La donne a-t-elle été jouée jusqu'au bout (sa dernière partie, gardée) ? Revoir n'a de sens qu'après."""
        x = jouer.en_cours(base_seance(c), d["n"]) or {}
        return bool(x.get("reclame") or len(x.get("cartes") or []) >= 52)

    def verdict(c, d, p):
        """La donne finie, en une ou deux lignes (l'utilisateur, 2026-11-11 : le moment où l'on apprend) : votre contrat
        face au contrat recommandé (l'Expert, sinon le Coach), au double mort, en IMP ; puis votre jeu de la carte face
        au double mort de votre contrat."""
        try:
            r = jouer.comparer(d, jeu["seq"], jeu["siege"], lire_analyses(c))
        except Exception:
            return ""
        lignes = r["lignes"]; moi_ = lignes[0]
        ref = next((x for x in lignes if x["nom"] == "Expert"), None) or next((x for x in lignes if x["nom"] == "Standard"), None)
        nom_c = lambda t: re.sub(r" ([NESO])$", lambda m_: " par " + SIEGE[m_[1]], t)
        out = []
        if ref:
            qui = "l'Expert" if ref["nom"] == "Expert" else "le Coach"
            if ref["texte"] == moi_["texte"]:
                out.append(f"Même contrat que {qui} : {rouge(nom_c(ref['texte']))}.")
            else:
                lev = f", {ref['levees']} levées au double mort" if ref.get("levees") is not None else ""
                i_ = ref.get("imp")
                gain = "" if i_ in (None, 0) else (f" — {abs(i_)} IMP de {'plus' if i_ > 0 else 'moins'} pour vous")   # vos IMP face à lui
                out.append(f"Recommandé par {qui} : <b>{rouge(nom_c(ref['texte']))}</b>{lev}{gain}.")
        if p:
            g_, _e, dm = p.resultat()
            vous = g_ if not p.en_defense() else 13 - g_
            dm_vous = dm if not p.en_defense() else 13 - dm
            if vous < dm_vous: out.append(f"Au jeu de la carte : {dm_vous - vous} levée{'s' if dm_vous - vous > 1 else ''} de moins que le double mort.")
            elif vous > dm_vous: out.append(f"Au jeu de la carte : {vous - dm_vous} levée{'s' if vous - dm_vous > 1 else ''} de plus que le double mort.")
            else: out.append("Au jeu de la carte : autant que le double mort.")
        return "<br>".join(out)

    def faute_de(p):
        """La première de vos cartes qui a coûté une levée au double mort (sinon de votre partenaire), son rang dans la donne, ou None ; calculée
        une fois, en arrière-plan, quand la donne finit (Revoir s'ouvre là)."""
        x = jeu.get("faute")
        if x and x[0] is p: return x[1]                   # (partie, rang de la carte, la carte qui gardait la levée)
        if not jeu.get("faute_calcul") is p:
            jeu["faute_calcul"] = p
            async def calcul():
                cartes = [(cc, r) for pli, _ in p.plis for _x, cc, r in pli]
                try:
                    a = await run.io_bound(carte.analyse_jeu, p.d, p.contrat, p.decl, cartes)
                    k = next((x_["k"] for x_ in a["cartes"] if x_["perte"] > 0 and p.au_joueur(x_["siege"])), None)
                    if k is None:                          # sinon la première levée perdue par votre camp (votre partenaire)
                        k = next((x_["k"] for x_ in a["cartes"]
                                  if x_["perte"] > 0 and p.camp(x_["siege"]) == p.camp(p.humain)), None)
                    mieux = await run.io_bound(carte.meilleure_carte, p.d, p.contrat, p.decl, cartes, k) if k is not None else None
                except Exception:
                    k = None; mieux = None
                jeu["faute"] = (p, k, mieux)
                if jeu.get("partie") is p: vue_jouer.refresh()
            background_tasks.create(calcul())
        return None

    def changer_mode(m):
        jeu.update(mode=m, revoir=0 if m == "revoir" else None); ecrire_etat(mode_jouer=m); vue_jouer.refresh()

    def tete_donne(d):
        """En haut de la barre de droite de Jouer : Jouer | Revoir | Démo (l'utilisateur, 2026-11-11). Revoir, la partie
        que vous avez jouée rejouée avec les commentaires des robots, s'ouvre une fois la donne jouée jusqu'au bout."""
        c = choix["chemin"]; m = mode_de(c, d)
        with ui.element("div").classes("inline-flex rounded overflow-hidden").style("box-shadow:0 1px 3px rgba(0,0,0,.18)"):
            for cle, nom in (("jouer", "Jouer"), ("revoir", "Revoir"), ("demo", "Démo")):
                b = ui.button(nom, on_click=lambda cle=cle: changer_mode(cle)) \
                    .props(("unelevated color=primary" if m == cle else "flat color=white text-color=grey-9") + " no-caps square") \
                    .classes("text-base")
                if cle == "revoir" and not donne_jouee(c, d):
                    b.set_enabled(False); b.tooltip("Jouez d'abord la donne jusqu'au bout")
                elif cle == "revoir":
                    b.tooltip("Votre partie, carte par carte, avec ce que pensaient les robots")

    def mode_de(c, d):
        """Le mode montré pour cette donne : Revoir seulement si elle a été jouée jusqu'au bout, sinon Jouer."""
        m = jeu.get("mode") or "jouer"
        return "jouer" if m == "revoir" and not donne_jouee(c, d) else m

    # ---------------------------------------------------------------- la démonstration (un cours sur grand écran)
    def demo_de(c, d):
        """La démonstration de la donne (demo.Demo), gardée tant qu'on reste sur la même donne."""
        if jeu.get("demo_cle") != (c, d["n"]):
            import demo
            jeu.update(demo=demo.Demo(d, lire_analyses(c)), demo_cle=(c, d["n"]), pas=0, demo_msg="")
        return jeu["demo"]

    async def demo_aller(k):
        """Va au pas k (0 : rien d'annoncé) ; une carte pas encore jouée est calculée (les robots réfléchissent)."""
        m = jeu.get("demo")
        if not m or jeu.get("demo_occupe"): return
        k = max(0, k)
        if k > m.n_pas():                                  # une carte de plus : le robot réfléchit
            j = k - m.n_encheres - 1
            if m.fini(): return
            q = m.position(len(m.cartes) - 1)
            jeu.update(demo_occupe=True, demo_msg=f"{SIEGE[q.au_trait()]} réfléchit…"); vue_jouer.refresh()
            try:
                ok = await run.io_bound(m.calculer, j)
            finally:
                jeu.update(demo_occupe=False, demo_msg="")
            if not ok: k = m.n_pas()
        jeu["pas"] = min(k, m.n_pas()); vue_jouer.refresh()

    async def demo_essayer(m, j, x):
        """Double mort : l'enseignant joue une autre carte à la place de la carte j + 1 ; la suite repart de là."""
        try: m.essayer(j, x)
        except ValueError: return
        jeu["pas"] = m.n_encheres + j + 2; vue_jouer.refresh()

    COULEUR_TOUCHE = {"T": "♣", "K": "♦", "C": "♥", "P": "♠", "S": "SA"}   # trèfle, carreau, cœur, pique, sans-atout

    async def encheres_clavier(cle):
        """Enchérir au clavier, dans Jouer : un chiffre puis T K C P S (1 puis C = 1♥), Entrée = passe, X = contre,
        R = surcontre, Échap efface le chiffre tapé. Le chiffre attendu s'affiche sous la boîte (jeu["clavier"])."""
        if jeu.get("partie") or jeu.get("attend") or not jeu.get("d") or (jeu.get("mode") or "jouer") != "jouer": return
        d = jeu["d"]; k = cle.upper() if len(cle) == 1 else cle
        appel = None
        if k.isdigit() and "1" <= k <= "7":
            jeu["clavier"] = k; vue_jouer.refresh(); return
        if k == "Escape" and jeu.get("clavier"):
            jeu["clavier"] = None; vue_jouer.refresh(); return
        if k in COULEUR_TOUCHE and jeu.get("clavier"): appel = jeu["clavier"] + COULEUR_TOUCHE[k]
        elif k == "Enter": appel = "passe"
        elif k == "X": appel = "contre"
        elif k == "R": appel = "surcontre"
        if not appel: return
        jeu["clavier"] = None
        if appel not in jouer.legales(jeu["seq"], d["donneur"]):
            jeu["note"] = f"{appel} n'est pas possible ici."; vue_jouer.refresh(); return
        await jeu_annonce(d, appel)

    async def demo_touche(e):
        """Le clavier : ← → (et Page précédente / suivante d'une télécommande de présentation) dans la démonstration ;
        les enchères au clavier dans Jouer (encheres_clavier)."""
        if not e.action.keydown or not sur_jouer(): return
        cle = e.key.name if hasattr(e.key, "name") else str(e.key)
        if jeu.get("mode") != "demo": return await encheres_clavier(cle)
        if not jeu.get("demo"): return
        if cle in ("ArrowRight", "PageDown"): await demo_aller(jeu.get("pas", 0) + 1)
        elif cle in ("ArrowLeft", "PageUp"): await demo_aller(jeu.get("pas", 0) - 1)

    def vue_demo(c, d, data):
        """Les quatre mains ouvertes, le déclarant en bas ; l'enseignant avance (→) et recule (←) dans les enchères recommandées,
        puis dans le jeu de la carte des robots ; la barre de droite dit ce que pense le joueur du pas montré. Double
        mort : sous chaque carte jouable, les levées du déclarant ; un clic sur une carte l'essaie."""
        m = demo_de(c, d)
        k = max(0, min(jeu.get("pas", 0), m.n_pas())); jeu["pas"] = k
        # les onglets prennent les flèches quand ils ont le focus : on le leur ôte, ← → restent à la démonstration
        ui.run_javascript("var a = document.activeElement; if (a && a.closest && a.closest('.q-tabs')) a.blur()")
        bas = siege_pour(c, d) or m.decl or "S"             # la même place en bas que dans Jouer et Revoir (l'utilisateur, 2026-11-11)
        if m.decl and bas == jouer.PART[m.decl] and k > m.n_encheres:
            bas = m.decl                                    # le mort n'est jamais en bas : dès l'entame, le déclarant passe devant vous
        vu = jeu.get("demo_bas_vu")                          # et la table tourne d'un demi-tour, comme dans Jouer
        if vu and vu[:2] == (c, d["n"]) and vu[2] != bas: jeu["tourne"] = time.monotonic(); jeu["carre_avant"] = vu[2]
        jeu["demo_bas_vu"] = (c, d["n"], bas); jeu["carre_bas"] = bas
        places = (jouer.PART[bas], jouer.ROT[(jouer.ROT.index(bas) + 1) % 4], jouer.ROT[(jouer.ROT.index(bas) + 3) % 4], bas)
        en_jeu = k > m.n_encheres                          # une carte au moins est jouée
        j = k - m.n_encheres - 1                           # la dernière carte montrée
        q = m.position(j) if m.decl and k >= m.n_encheres else None
        marques_dm.clear()
        voir_dm = jeu.get("demo_dm") and q is not None and not q.fini()
        if voir_dm:
            v = m.dm(j)
            if v:
                best = (max if q.camp(q.au_trait()) else min)(v.values())
                marques_dm.update({(x[0], x[1].translate(carte.FR)): (t, t == best) for x, t in v.items()})
        jouables = set(marques_dm) if voir_dm else None
        clic = lambda y: demo_essayer(m, j, (y[0], y[1].translate(carte.EN)))
        with ui.row().classes("w-full no-wrap items-start gap-4").style(f"padding-right:{LARGEUR_PANNEAU}px"):
            with ui.column().classes("grow min-w-0 gap-2 relative"):
                def interrupteur_dm():                   # dès la fin des enchères : sous chaque carte jouable, le double mort
                    if m.decl and k >= m.n_encheres:
                        ui.switch("Double mort", value=bool(jeu.get("demo_dm")),
                                  on_change=lambda ev: (jeu.update(demo_dm=ev.value), vue_jouer.refresh())).classes("text-base") \
                            .tooltip("Sous chaque carte jouable : les levées du déclarant au double mort (en vert la meilleure). "
                                     "Un clic sur une carte l'essaie.")
                outils_table(d, extra=interrupteur_dm)
                if q is None or not en_jeu:                 # les enchères : les mains entières, les cartons sur la table
                    def contenu(x, ou):
                        if q is not None and voir_dm and x == q.au_trait():   # l'entame au double mort
                            eventail(mains_fr(d, x), jouables, clic, colonnes=ou in ("gauche", "droite"), grande=x == bas)
                        else:
                            eventail(mains_fr(d, x), colonnes=ou in ("gauche", "droite"), grande=x == bas)
                    table(d, places, contenu, lambda: ui.html(tapis_encheres(d, places, m.seq[:k]), sanitize=False),
                          tour=None if k >= m.n_encheres else jouer.ROT[(jouer.ROT.index(d["donneur"]) + k) % 4])
                else:
                    pli = q.pos.pli or (q.plis[-1][0] if q.plis else [])
                    posees = {x: (cc, r_.translate(carte.FR)) for x, cc, r_ in pli}
                    bulles = {}                                 # au survol d'une carte du pli : pourquoi celle-là
                    for idx in range((j // 4) * 4, j + 1):
                        z = m.pensees[idx]
                        bulles[z["siege"]] = (f"<b>{SIEGE[z['siege']]} {'entame' if idx == 0 else 'joue'} {rouge(z['carte'])}</b><br>"
                                              + (rouge(z["entame"]) if z.get("entame") else
                                                 "La carte essayée : les robots reprennent de là." if z.get("essai") else
                                                 rouge(carte.justification(z, m.decl))))
                    def centre():
                        ui.html(f"<div style='position:absolute;inset:0;pointer-events:none'><div style='position:absolute;left:50%;top:50%;"
                                f"transform:translate(-50%,-50%);z-index:0'></div>"
                                f"{pli_cartes(q, places, posees, mort=q.mort(), bulles=bulles)}"
                                + rangees_plis(q, places, lambda x: x != q.mort())   # les plis gardés, comme dans Jouer (pas le mort)
                                + "</div>", sanitize=False)
                    tour = None if q.fini() else q.au_trait()
                    def contenu(x, ou):
                        reste = {kk: "".join(r_.translate(carte.FR) for r_ in vv) for kk, vv in q.pos.reste[x].items()}
                        jx = jouables if x == tour else None
                        if x == q.mort():
                            mort_etale(reste, jx, clic, q.den, ou,
                                       carte_posee(*posees[x], premiere=x == next(iter(posees), None), bulle=bulles.get(x, ""), cote=ou)
                                       if x in posees else "")
                        else:
                            eventail(reste, jx, clic, colonnes=ou in ("gauche", "droite"), grande=x == bas)
                    table(d, places, contenu, centre,
                          sur_table=[ou for x, ou in zip(places, ("haut", "gauche", "droite", "bas")) if x == q.mort()],
                          tour=tour)
            with panneau_droit():
                appliquer_plein()
                tete_donne(d)
                fin = m.fini() and k >= m.n_pas()
                # les mêmes boutons de magnétoscope que Jouer (magneto), au même endroit ; ici ⏮ le début, ◀◀ un pas en
                # arrière, ▶ un pas en avant (l'utilisateur, 2026-11-11 : la même allure, pas forcément le même sens)
                with ui.row().classes("gap-2 items-center no-wrap"):
                    ui.button(icon="skip_previous", on_click=lambda: demo_aller(0)).props("outline") \
                        .tooltip("Au début").set_enabled(k > 0 and not jeu.get("demo_occupe"))
                    ui.button(icon="fast_rewind", on_click=lambda: demo_aller(k - 1)).props("outline") \
                        .tooltip("Un pas en arrière (flèche ←)").set_enabled(k > 0 and not jeu.get("demo_occupe"))
                    ui.button(icon="play_arrow", on_click=lambda: demo_aller(k + 1)).props("unelevated") \
                        .tooltip("Un pas en avant (flèche →)").set_enabled(not fin and not jeu.get("demo_occupe"))
                src = {"expert": "de l'Expert", "standard": "du Coach", "moteur": "du moteur"}[m.source]
                n_ = min(k, m.n_encheres); i0 = jouer.ROT.index(d["donneur"])
                grille_demo = lambda: ui.html(grille_html(jouer.grille(m.seq[:n_], d["donneur"]), d.get("vul"),
                                              sens={i: (jouer.ROT[(i0 + i) % 4], m.explications[i] if i < len(m.explications) else "", False)
                                                    for i in range(n_)})
                                              .replace("border-collapse:collapse", "border-collapse:separate;border-spacing:4px 0"),
                                              sanitize=False)
                if jeu.get("demo_msg"): ui.label(jeu["demo_msg"]).classes("text-base pense")
                if k <= m.n_encheres:                       # les enchères : la grille seule, sur sa carte blanche (l'utilisateur,
                    with ui.element("div").classes("w-full rounded-xl border border-gray-200 bg-white p-2"):   # 2026-11-11)
                        grille_demo()
                    if k == m.n_encheres and m.notes and m.decl:     # la fin des enchères : l'avis de qui les recommande
                        ui.html(f"<div style='font-size:16px'><b>L'avis {src} :</b> {rouge(m.notes)}</div>", sanitize=False)
                    if k == m.n_encheres and not m.decl:
                        ui.label("La donne se passe : rien à montrer au jeu de la carte.").classes("text-base")

                else:                                       # le jeu de la carte : les enchères restent (elles disent le contrat),
                    with ui.element("div").classes("w-full rounded-xl border border-gray-200 bg-white p-2"):   # où l'on en est,
                        grille_demo()                                                                          # le double mort
                    # les cartes du pli et leur raison : sur la table, au survol de chaque carte (l'utilisateur, 2026-11-11 :
                    # pas de répétition dans la barre)
        marques_dm.clear()

    plein = {"on": False}                                 # Jouer, « table seule » : sans les barres ni les onglets
    ui.keyboard(on_key=demo_touche, ignore=["input", "select", "textarea"])   # la démonstration : ← → au clavier

    with ui.dialog() as fen_pli, ui.card().classes("items-center"):   # le dernier pli, dans une fenêtre : la table ne change pas
        @ui.refreshable
        def contenu_pli():
            x = jeu.get("pli_montre")
            if not x: return
            pli, g = x
            places = jeu.get("places") or ("N", "O", "E", "S")
            cartes_ = {s_: (cc, r.translate(carte.FR)) for s_, cc, r in pli}
            premier = pli[0][0] if pli else None
            def nom(s_):                                  # « Samir SAYEGH » : le prénom d'abord, comme à la table
                n_ = (jeu.get("noms") or {}).get(s_)
                if not n_: return SIEGE[s_]
                m_ = n_.split(); k_ = next((i for i, w in enumerate(m_) if not w.isupper()), len(m_)) or 1
                return " ".join(m_[k_:] + m_[:k_])
            def case(s_, ou):
                cc, r = cartes_.get(s_, ("", ""))
                h = (f"<div data-c='' class='carte{' r' if cc in '♥♦' else ''}{' gagnante' if s_ == g else ''}"
                     f"{f' premiere p-{ou}' if s_ == premier else ''}' style='margin:0'>{face(r)}<br/>{cc}</div>") if cc else ""
                return (f"<div style='display:flex;flex-direction:column;align-items:center;gap:4px'>"
                        f"<div style='font-size:15px;color:#4a4f57'>{nom(s_)}</div>{h}</div>")
            ui.label("Le dernier pli").classes("text-lg font-bold")
            ui.html("<div style='display:grid;grid-template-columns:repeat(3,auto);gap:10px 18px;align-items:center;justify-items:center'>"
                    f"<div></div>{case(places[0], 'haut')}<div></div>"
                    f"{case(places[1], 'gauche')}<div></div>{case(places[2], 'droite')}"
                    f"<div></div>{case(places[3], 'bas')}<div></div></div>", sanitize=False)
            ui.label(f"Gagné par {nom(g)}.").classes("text-base text-gray-700")
            ui.button("Fermer", on_click=fen_pli.close).props("flat no-caps")
        contenu_pli()

    def dernier_pli(_=None):
        """Un clic sur la dernière carte des plis gardés : le dernier pli dans une fenêtre, posé comme à la table, la carte
        gagnante dorée (l'utilisateur, 2026-11-11 : sans toucher aux cartes de la table)."""
        p = jeu.get("partie")
        if jeu.get("mode") != "jouer" or not p or not p.plis: return    # la partie de Jouer (Revoir, Démo : leurs flèches)
        jeu["pli_montre"] = p.plis[-1]; contenu_pli.refresh(); fen_pli.open()
    ui.on("dernier_pli", dernier_pli)

    def appliquer_plein():
        """La place que prennent les barres, pour la taille de la table (COTE_TABLE). Table seule : sans les onglets ni la
        barre de gauche ; la barre de droite reste (la boîte à enchères, les commandes ; le choix de l'utilisateur)."""
        if not plein["on"]: l, h, m, t = 740, 420, 640, f"{HAUTEUR_BARRE}px"
        else: l, h, m, t = 440, 330, 820, "0px"           # sans les onglets : la barre de droite monte en haut
        ui.run_javascript(f"var r = document.documentElement.style; r.setProperty('--reserve-l', '{l}px'); "
                          f"r.setProperty('--haut-panneau', '{t}'); "
                          f"r.setProperty('--reserve-h', '{h}px'); r.setProperty('--table-max', '{m}px'); "
                          "setTimeout(function () { window.dispatchEvent(new Event('resize')); }, 50)")

    def basculer_plein():
        plein["on"] = not plein["on"]
        entete.set_value(not plein["on"]); montrer_barre(); vue_jouer.refresh()

    def outils_table(d, extra=None):
        """Au-dessus de la table, sur sa ligne : la donne, son donneur et sa vulnérabilité (ôtés de la barre de droite pour
        lui laisser la place ; le petit carré de la FFB aussi : il répétait l'étui), et à droite « table seule » (sans les
        barres). Les cartes grandissent avec la place (l'utilisateur, 2026-11-11)."""
        with ui.row().classes("w-full gap-x-4 gap-y-1 items-center").style(   # remontée : le titre à la même distance du haut
                "margin-bottom:-8px;white-space:nowrap"):   # pas de marge négative en haut : le panneau rognait le carré
            if lire_etat().get("liste_cachee"):            # la liste cachée : un petit signe discret au bord gauche pour la rouvrir
                ui.button(icon="keyboard_double_arrow_right", on_click=lambda: basculer_liste(False)) \
                    .props("flat dense round size=sm color=grey-6") \
                    .style(f"position:fixed;left:4px;top:{HAUTEUR_BARRE + 10}px;z-index:5").tooltip("Montrer la liste des donnes")
            # le carré tourne comme la table : la place du bas en bas ; quand la table fait son demi-tour, il le fait avec elle
            angle = {"S": 0, "O": -90, "N": 180, "E": 90}
            bas_c = jeu.get("carre_bas") or "S"
            a1 = angle.get(bas_c, 0); a0 = angle.get(jeu.get("carre_avant") or bas_c, a1)
            if a1 - a0 > 180: a0 += 360
            if a0 - a1 > 180: a0 -= 360
            ecoule = time.monotonic() - jeu.get("tourne", -99)
            anim = (f"animation:carre-tourne {TOURNE}s ease-in-out;animation-delay:-{ecoule:.2f}s;" if ecoule < TOURNE and a0 != a1 else "")
            ui.html(f"<div class='carre-tourne{' anime' if anim else ''}' style='zoom:.75;margin:6px 4px;--de:{a0}deg;--a:{a1}deg;"
                    f"--retard:-{ecoule:.2f}s;transform:rotate({a1}deg);{anim}'>"
                    f"{carre_donne(d)}</div>", sanitize=False)
            # le carré de la donne (comme la FFB), et les mots (l'utilisateur, 2026-11-11 : il y a la place)
            ui.label(f"Donne {d['n']}").classes("text-xl font-bold")
            ui.html(f"<div style='font-size:17px'>Donneur : <b>{SIEGE[d['donneur']]}</b> · "
                    f"Vulnérabilité : <b>{VUL_TXT.get(d.get('vul'), d.get('vul', ''))}</b></div>", sanitize=False)
            if place_jouer() == "joueur":                  # comme un joueur de la séance : son tour, ses adversaires
                pj = jeu.get("place_joueur")
                if pj:                                     # les noms sont près des mains
                    if pj.get("tour"): ui.html(f"<div style='font-size:17px'>Tour <b>{pj['tour']}</b></div>", sanitize=False)
                else:
                    ui.html(f"<div style='font-size:17px;color:#6b6b6b'>{joueur_jouer()} n'a pas joué cette donne</div>", sanitize=False)
            with ui.row().classes("items-center gap-3 no-wrap ml-auto"):   # à droite ; à la ligne s'il manque de place
                if extra: extra()                          # Démo : le double mort, au-dessus de la table
                pass                                       # plus de bouton plein écran : la liste se cache depuis elle-même

    @ui.refreshable
    def vue_jouer():
        c = choix["chemin"]; data = lire_seance(c)
        if not data:
            ui.label("Aucune séance ouverte : Fichier, Ouvrir une séance").classes("text-base"); return
        es = entrees_de(data) if sur_jouer() else []
        if not es: return
        e = entree_effective(data)
        if e == "options":
            titre_page("Options", "encherir")
            with ui.row().classes("items-center gap-2"):          # le système des robots, sur la fiche de conventions
                ui.label("Les robots jouent le SEF 2024.").classes("text-base text-gray-700")
                ui.button("Votre fiche de conventions", icon="description",
                          on_click=lambda: (onglets.set_value(o_reglages), voir_page("Réglages", "systeme"))).props("flat dense no-caps")
            ui.label("La place que vous jouez").classes("text-base font-bold mt-2")
            ui.label("Le déclarant est celui de la séquence recommandée (l'analyse de l'expert, sinon la standard, sinon "
                     "les enchères du coach). Le choix vaut pour toutes les donnes et reste d'une fois sur l'autre.") \
                .classes("text-base text-gray-700 max-w-2xl")
            def repartir():
                jeu["cle"] = None                            # les donnes repartent du début, à la nouvelle place
                x = jouer.lire_essais(base_seance(c))
                if x.pop("en_cours", None) is not None:
                    json.dump(x, open(jouer.fichier_jeu(base_seance(c)), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            def changer(ev):
                if ev.value is None: return                   # l'autre liste de choix qui se vide
                ecrire_etat(place_jouer=ev.value); repartir(); barre_seance.refresh(); vue_jouer.refresh()
            places_ = dict(jouer.PLACES); cle1 = next(iter(places_))   # « comme un joueur » en premier, ses réglages juste dessous
            ui.radio({cle1: places_[cle1]}, value=place_jouer() if place_jouer() == cle1 else None, on_change=changer).classes("text-base")
            if place_jouer() == "joueur":                    # quel joueur, et dans quel ordre
                noms_seance = sorted({j["nom"].strip() for v in (data.get("joueurs") or {}).values() for j in v
                                      if (j.get("nom") or "").strip()}, key=str.lower)
                if not noms_seance:
                    ui.label("Cette séance ne garde pas le nom des joueurs : le choix n'est pas possible.").classes("text-base text-gray-700")
                else:
                    actuel = joueur_jouer() if joueur_jouer() in noms_seance else noms_seance[0]
                    mien = lire_etat().get("mon_nom")
                    opts = ({mien: f"{mien} (vous)", SEPARATEUR: "──────────"} if mien in noms_seance else {})
                    opts.update({x: x for x in noms_seance if x != mien})
                    def choisir_joueur(ev):
                        if ev.value == SEPARATEUR: ev.sender.value = joueur_jouer(); return
                        ecrire_etat(joueur_jouer=ev.value); retenir_licence(ev.value); repartir(); barre_seance.refresh(); vue_jouer.refresh()
                    with ui.column().classes("gap-2 ml-8 max-w-md"):
                        ui.select(opts, value=actuel, with_input=True, on_change=choisir_joueur).classes("w-full") \
                            .props("outlined dense") \
                            .props(":option-disable=\"o => typeof o.label === 'string' && o.label.startsWith('───')\"")
                        ui.checkbox("Dans l'ordre où ce joueur a joué les donnes", value=bool(lire_etat().get("ordre_joueur")),
                                    on_change=lambda ev: (ecrire_etat(ordre_joueur=ev.value), vue_jouer.refresh())).classes("text-base")
                        ui.label("Tour après tour : « Donne suivante », à la fin de chaque donne, suit cet ordre ; les donnes qu'il "
                                 "n'a pas jouées viennent à la fin, jouées à la place du déclarant. Au-dessus des cartes : le nom "
                                 "des quatre joueurs de sa table.").classes("text-base text-gray-700")
                        premiere = (ordre_jouer(data) or [None])[0]
                        if premiere is not None:
                            ui.button(f"Aller à la première donne (donne {premiere})", icon="arrow_forward",
                                      on_click=lambda n=premiere: aller(f"d{n}")).props("unelevated no-caps").classes("text-base mt-1")
            ui.radio({k: v for k, v in places_.items() if k != cle1}, value=place_jouer() if place_jouer() != cle1 else None,
                     on_change=changer).classes("text-base")
            ui.label("Quand l'autre camp gagne le contrat, vous jouez la carte en défense : les robots tiennent le déclarant, "
                     "son mort et votre partenaire.").classes("text-base text-gray-700")
            return
        if e == "classement":
            page_classement(c, data, aller); return
        d = next(x for x in data["donnes"] if f"d{x['n']}" == e)
        if mode_de(c, d) == "demo":                      # la démonstration, pour un cours : une vue à part
            pj = moi.place_du_joueur(data, d, joueur_jouer()) if place_jouer() == "joueur" else None
            jeu["noms"] = (pj or {}).get("noms") or {}; jeu["place_joueur"] = pj
            vue_demo(c, d, data); return
        if jeu["cle"] != (c, d["n"]): jeu_depart(c, d)
        pj = moi.place_du_joueur(data, d, joueur_jouer()) if place_jouer() == "joueur" else None
        jeu["noms"] = (pj or {}).get("noms") or {}; jeu["place_joueur"] = pj
        s = jeu["siege"]; part = jouer.PART[s]
        p = jeu["partie"]
        # vos cartes toujours en bas ; la table et l'étui tournent avec vous. Vous tenez le déclarant et son mort, et vous
        # avez enchéri de la place du mort : pendant le jeu de la carte, le déclarant passe devant vous (la table tourne)
        bas = p.decl if p and not p.en_defense() and s == p.mort() else s
        vu = jeu.get("bas_vu")                           # (séance, donne, siège du bas) au dessin d'avant
        if vu and vu[:2] == (c, d["n"]) and vu[2] != bas and p and not p.pos.jouees[1:]:
            jeu["tourne"] = time.monotonic(); jeu["carre_avant"] = vu[2]   # le début du jeu de la carte : la table tourne d'un demi-tour
        jeu["bas_vu"] = (c, d["n"], bas); jeu["bas"] = bas; jeu["carre_bas"] = bas
        gauche, droite = jouer.ROT[(jouer.ROT.index(bas) + 1) % 4], jouer.ROT[(jouer.ROT.index(bas) + 3) % 4]
        places = (jouer.PART[bas], gauche, droite, bas); jeu["places"] = places
        attente = jeu["affiche"] < len(jeu["seq"])
        fini = jeu["indice"] is None and not attente
        if mode_de(c, d) == "revoir" and p and p.fini():   # Revoir : votre partie, carte par carte, avec les pensées
            if jeu.get("revoir") is None: jeu["revoir"] = 0
            vue_revoir(c, d, data, places, p); return
        c_, decl = jouer.contrat(jeu["seq"], d["donneur"]) if fini else ("passe", None)
        a_jouer = fini and not p and c_ != "passe" and not jeu.get("sans_jouer")   # au déclarant ou en défense
        montrer = (fini and not a_jouer and not p) or (p and p.fini())

        with ui.row().classes("w-full no-wrap items-start gap-4").style(f"padding-right:{LARGEUR_PANNEAU}px"):
            with ui.column().classes("grow min-w-0 gap-2 relative"):     # la table
                outils_table(d)
                if p:
                    vue_carte(c, d, data, places)
                else:
                    def contenu(x, ou):
                        if x == s or montrer:
                            eventail(mains_fr(d, x), colonnes=ou in ("gauche", "droite"), grande=x == s,
                                     a_vous=x == s and not fini and not attente and not jeu.get("attend"))
                        else: dos(ou, 13)
                    table(d, places, contenu, lambda: ui.html(tapis_encheres(d, places), sanitize=False),
                          tour=None if jeu.get("attend") else jeu["pense"] if attente else (s if not fini else None))
            with panneau_droit():                                                         # la barre de droite : l'essentiel
                appliquer_plein()
                tete_donne(d)
                magneto(c, d)
                # la grille des enchères, toujours ouverte sur sa carte blanche, même pendant le jeu (elle dit le contrat) ;
                # l'étui n'est plus que sur la table (l'utilisateur, 2026-11-11 : pas deux fois)
                with ui.element("div").classes("w-full rounded-xl border border-gray-200 bg-white p-2"):
                    vues = jeu["seq"] if p else jeu["seq"][:jeu["affiche"]]
                    ui.html(grille_html(jouer.grille(vues, d["donneur"], not fini and not attente and not p), d["vul"],
                                        sens=sens_jouer(len(vues)))
                            .replace("border-collapse:collapse", "border-collapse:separate;border-spacing:4px 0"), sanitize=False)
                if p:
                    if not p.fini():
                        with ui.row().classes("gap-2"):
                            ui.button("Indice", icon="lightbulb", on_click=lambda: carte_indice()).props("outline dense no-caps")
                            if not p.en_defense():
                                ui.button("Réclamer", icon="done_all", on_click=lambda: carte_reclamer()).props("outline dense no-caps") \
                                    .tooltip("Réclamer : vous annoncez que vous ferez toutes les levées qui restent, sans les jouer. "
                                             "Le coach vérifie, cartes vues : si la défense peut en faire une, la donne continue.")
                        if jeu["msg"] and jeu["msg"].startswith("Le coach jouerait") and jeu.get("indice_pourquoi"):
                            pq, plan_ = jeu["indice_pourquoi"]       # comme les enchères de la grille : survol ou clic
                            bulle = rouge(pq) + (f"<div style='margin-top:6px'><b>Son plan :</b> {rouge(plan_)}</div>" if plan_ else "")
                            ui.html(f"<div class='enc-sens c0' style='display:inline-block;font-size:16px;text-align:left'>"
                                    f"{rouge(jeu['msg'])}<span class='bulle'>{bulle}</span></div>", sanitize=False)
                        elif jeu["msg"]: ui.label(jeu["msg"]).classes("text-base")
                    # pas de pensées des robots pendant le jeu : à la table, on n'entend pas les autres réfléchir (et elles
                    # disent ce qu'ils croient des mains cachées ; l'utilisateur, 2026-11-11). Elles restent pour « Revoir la
                    # donne avec les pensées », après la donne, et pour la Démo
                elif jeu.get("attend"):
                    ui.label("Appuyez sur ▶ pour commencer : les enchères partent du donneur.").classes("text-base text-gray-700")
                elif not fini and attente:                      # les autres enchérissent : la boîte reste, grisée
                    boite_encheres(d, actif=False)
                elif not fini and not attente:
                    boite_encheres(d)
                    with ui.row().classes("w-full"):             # sous la boîte, à gauche : son texte se lit juste dessous
                        ui.button("Masquer l'indice" if jeu["voir_indice"] else "Indice", icon="lightbulb",
                                  on_click=lambda: (jeu.update(voir_indice=not jeu["voir_indice"]), vue_jouer.refresh())) \
                            .props(("unelevated" if jeu["voir_indice"] else "outline") + " dense no-caps")
                    if jeu["voir_indice"]:                      # comme les enchères de la grille : le sens au survol ou d'un clic
                        ui.html(f"<div class='enc-sens c0' style='display:inline-block;font-size:16px;text-align:left'>"
                                f"Le coach dirait <b>{rouge(jeu['indice']['enchere'])}</b>"
                                f"<span class='bulle'>{rouge(jeu['indice']['texte'])}</span></div>", sanitize=False)
                    if jeu.get("note"):
                        ui.html(f"<div style='font-size:15px;color:#8a5a00'>{rouge(jeu['note'])}</div>", sanitize=False)
                    if jeu.get("clavier"):                      # un chiffre tapé au clavier : la couleur est attendue
                        ui.label(f"Au clavier : {jeu['clavier']}… puis T, K, C, P ou S (Échap pour effacer)").classes("text-base text-primary")
                    else:
                        ui.label("Au clavier : 1 puis T K C P S (1♣ … 1SA), Entrée passe, X contre, R surcontre.") \
                            .classes("text-sm text-gray-600")
                elif a_jouer:                                   # les enchères finies : le jeu de la carte part tout seul, comme à
                    ui.label(f"{'Vous jouez' if jouer.camp(decl) == jouer.camp(s) else 'Vous défendez contre'} {c_} par {SIEGE[decl]} : "
                             "le jeu de la carte commence…").classes("text-base")      # la table (l'utilisateur, 2026-11-11)
                    ui.button("Voir les mains sans jouer", on_click=lambda: (jeu.update(sans_jouer=True), jeu_garder(), vue_jouer.refresh())) \
                        .props("flat no-caps dense")
                    cle_ = (c, d["n"], len(jeu["seq"]))
                    if jeu.get("depart_auto") != cle_:
                        jeu["depart_auto"] = cle_
                        async def depart(cle_=cle_):
                            await asyncio.sleep(1.8)
                            if (jeu.get("cle") == cle_[:2] and len(jeu["seq"]) == cle_[2] and not jeu.get("partie")
                                    and not jeu.get("sans_jouer") and jeu.get("mode") == "jouer"):
                                carte_demarrer(d)
                        background_tasks.create(depart())
                if (p and p.fini()) or (montrer and not p):     # la donne finie : la suite, en haut de la barre (pas sous la table)
                    with ui.column().classes("w-full gap-2 mt-2"):
                        if p:
                            g_, ecart_, _dm = p.resultat()
                            fait = "fait tout juste" if ecart_ == 0 else f"fait avec {ecart_} de mieux" if ecart_ > 0 else f"chute de {-ecart_}"
                            ui.html(f"<div style='font-size:16px'><b>{g_} levées</b> : {rouge(p.contrat)} {fait}.</div>", sanitize=False)
                        ui.button("Donne suivante", icon="arrow_forward", on_click=lambda: jeu_suivante(data, d)) \
                            .props("unelevated no-caps").classes("w-full text-base")
                        v = verdict(c, d, p)                        # en deux lignes : face au contrat recommandé, et au jeu
                        if v: ui.html(f"<div style='font-size:16px;line-height:1.4'>{v}</div>", sanitize=False)
                        if p:                                       # Revoir, ouvert là où vous avez perdu une levée
                            f_ = faute_de(p)
                            ui.button("Voir pourquoi" if f_ is not None else "Revoir la donne", icon="replay",
                                      on_click=lambda f_=f_: (changer_mode("revoir"), jeu.update(revoir=f_ or 0), vue_jouer.refresh())) \
                                .props("outline no-caps").classes("w-full text-base")
                if not jeu.get("attend"):                       # une question sur la donne, à l'outil d'IA réglé (Réglages, L'expert)
                    fin_ = bool((p and p.fini()) or (montrer and not p))
                    ui.button("Demander à l'expert", icon="forum", on_click=lambda fin_=fin_: demander_expert(c, d, fin_)) \
                        .props("outline no-caps").classes("w-full text-base mt-2") \
                        .tooltip("Une question sur cette donne : ce que vous voyez" + ("" if fin_ else ", sans les mains cachées"))

        if fini and not jeu["garde"]:
            jouer.enregistrer(base_seance(c), d["n"], s, jeu["seq"], d["donneur"]); jeu["garde"] = True; barre_seance.refresh()
        # la donne finie : rien sous la table (l'utilisateur, 2026-11-11) ; le résultat et « Donne suivante » sont dans la
        # barre, le résumé dans Revoir à la dernière carte
        if p and p.fini() and not jeu["garde_jeu"]:
            jouer.completer_jeu(base_seance(c), d["n"], [carte.carte_fr(cc, r) for pli, _ in p.plis for _x, cc, r in pli],
                                p.resultat()[0])
            jeu["garde_jeu"] = True

    def resume_de(d, p):
        """Le résumé écrit de la donne jouée (carte.resume_donne), calculé une fois."""
        if jeu.get("resume_de") is not p:
            try:
                tout = [(cc, r_) for pli, _ in p.plis for _x, cc, r_ in pli]
                jeu["resume"] = carte.resume_donne(d, p.contrat, p.decl, p.humain, tout, p.pensees, p.resultat()[0])
            except Exception:
                jeu["resume"] = []
            jeu["resume_de"] = p
        return jeu.get("resume") or []

    def vue_revoir(c, d, data, places, p):
        """La donne rejouée carte par carte : les quatre mains telles qu'elles étaient, le pli en cours, et ce que
        pensait le joueur de la carte montrée (◀ ▶). Votre carte : ce que le programme aurait joué à votre place."""
        cartes = [(cc, r_) for pli, _ in p.plis for _x, cc, r_ in pli]
        k = max(0, min(jeu["revoir"], len(cartes) - 1)); jeu["revoir"] = k
        q = carte.Partie(d, p.contrat, p.decl, p.encheres, humain=p.humain)
        for x in cartes[len(q.pos.jouees):k + 1]: q.poser(x)
        pli = q.pos.pli or (q.plis[-1][0] if q.plis else [])
        posees = {x: (cc, r_.translate(carte.FR)) for x, cc, r_ in pli}
        def centre():
            ui.html(f"<div style='position:absolute;inset:0;pointer-events:none'><div style='position:absolute;left:50%;top:50%;"
                    f"transform:translate(-50%,-50%);z-index:0'></div>{pli_cartes(q, places, posees, mort=q.mort())}"
                    + rangees_plis(q, places, lambda x: x != q.mort())
                    + "</div>", sanitize=False)
        def contenu(x, ou):
            reste = {kk: "".join(r_.translate(carte.FR) for r_ in v) for kk, v in q.pos.reste[x].items()}
            if x == q.mort(): mort_etale(reste, None, None, q.den, ou,
                                         carte_posee(*posees[x], premiere=x == next(iter(posees), None), cote=ou) if x in posees else "")
            else: eventail(reste, colonnes=ou in ("gauche", "droite"), grande=x == jeu["siege"])
        with ui.row().classes("w-full no-wrap items-start gap-4").style(f"padding-right:{LARGEUR_PANNEAU}px"):
            with ui.column().classes("grow min-w-0 gap-2"):
                outils_table(d)
                table(d, places, contenu, centre,
                      sur_table=[ou for x, ou in zip(places, ("haut", "gauche", "droite", "bas")) if x == q.mort()])
            with panneau_droit():
                appliquer_plein()
                tete_donne(d)
                with ui.row().classes("gap-2 items-center no-wrap"):   # les mêmes boutons que Jouer et Démo (magneto)
                    ui.button(icon="skip_previous", on_click=lambda: (jeu.update(revoir=0), vue_jouer.refresh())).props("outline") \
                        .tooltip("À la première carte").set_enabled(k > 0)
                    ui.button(icon="fast_rewind", on_click=lambda: (jeu.update(revoir=k - 1), vue_jouer.refresh())).props("outline") \
                        .tooltip("Une carte en arrière").set_enabled(k > 0)
                    ui.button(icon="play_arrow", on_click=lambda: (jeu.update(revoir=k + 1), vue_jouer.refresh())).props("unelevated") \
                        .tooltip("Une carte en avant").set_enabled(k < len(cartes) - 1)
                ui.label(f"{p.contrat} par {SIEGE[p.decl]} · carte {k + 1} sur {len(cartes)} · pli {k // 4 + 1}").classes("text-base font-bold")
                if k == len(cartes) - 1 and resume_de(d, p):  # la fin du film : le résumé de la donne
                    with ui.element("div").classes("w-full").style(
                            "background:#f6f8fb;border:1px solid #dfe5ea;border-radius:6px;padding:8px 10px"):
                        ui.label("Résumé de la donne").classes("text-base font-bold")
                        for ligne in resume_de(d, p):
                            ui.html(f"<div style='font-size:15px;margin-top:4px'>{rouge(ligne)}</div>", sanitize=False)
                f_ = jeu.get("faute")                           # la carte qui a coûté la levée : le dire, et ce qui la gardait
                if f_ and f_[0] is p and f_[1] == k:
                    ui.html(f"<div style='font-size:16px;background:#fdecea;border-left:3px solid #c62828;padding:6px 8px;"
                            f"border-radius:4px'>Ici, <b>{rouge(carte.carte_fr(*cartes[k]))}</b> a coûté une levée"
                            + (f" : <b>{rouge(f_[2])}</b> la gardait." if f_[2] else ".") + "</div>", sanitize=False).classes("w-full")
                z = next((z for z in p.pensees if z["n"] == k), None)
                if z:                                           # court, comme dans la Démo ; le détail derrière « Plus »
                    t_ = carte.texte_pensee(z, p.decl)
                    court = t_["raison"] if z["humain"] else carte.justification(z, p.decl)
                    ui.html(pensee_html(dict(titre=t_["titre"], raison=court, croyance=[], plan="")), sanitize=False).classes("w-full")
                    if t_.get("croyance") or t_.get("plan") or (not z["humain"] and t_["raison"] != court):
                        with ui.expansion("Plus").props("dense header-class='text-primary text-base px-1'").classes("w-full"):
                            ui.html(pensee_html(t_), sanitize=False).classes("w-full")
                if z and z["humain"] and not z.get("avis"):     # votre carte : ce que le programme aurait fait
                    async def avis(z=z):
                        jeu["msg"] = "Le coach réfléchit…"; vue_jouer.refresh()
                        z["avis"] = await run.io_bound(carte.avis_programme, d, p.contrat, p.decl, p.encheres, p.humain, cartes, k)
                        jeu["msg"] = ""; jeu_garder(); vue_jouer.refresh()
                    ui.button("Qu'aurait joué le coach ?", icon="psychology", on_click=avis).props("outline dense no-caps")
                    if jeu.get("msg"): ui.label(jeu["msg"]).classes("text-base")
                elif k == 0: ui.html(pensee_html(dict(titre=f"{SIEGE[carte.LHO[p.decl]]} entame {carte.carte_fr(*cartes[0])}",
                                                      raison="L'entame suit les règles du système (entames.yaml).", croyance=[])),
                                     sanitize=False).classes("w-full")

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
        ui.label("IMP pour vous : ce que votre contrat gagne (+) ou perd (−) face à celui de l'analyse, au double mort.").classes("text-base text-gray-700")
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
        # « Donne suivante » et les autres boutons de fin : dans la barre de droite (vue_jouer), jamais sous le contenu

    def page_versions(c):
        """Les versions gardées d'une séance modifiable, pour revenir en arrière."""
        vs = edition.versions(c)
        ui.label("Versions précédentes").classes("text-base font-bold mt-4")
        ui.label("Chaque modification est enregistrée aussitôt. Une copie de la séance est gardée avant les changements, "
                 "au plus toutes les 10 minutes (les 20 dernières).").classes("text-base text-gray-700")
        if not vs: ui.label("Aucune pour l'instant.").classes("text-base text-gray-700")
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
                 "Tout est enregistré dès que vous quittez un champ.").classes("text-base text-gray-700")
        tetes = {}

        def main_ed(s):
            with ui.column().classes("gap-1"):
                tetes[s] = ui.label("").classes("text-base font-bold text-gray-700")
                for k, coul in enumerate("♠♥♦♣"):
                    v = d["mains"][s].split()[k]
                    champ = ui.input(value="" if v == "-" else v).props(f'dense outlined prefix="{coul}"').classes("w-44")
                    champ.on("blur", lambda e, s=s, k=k, champ=champ: poser(s, k, champ))
                    champ.on("keydown.enter", lambda e, s=s, k=k, champ=champ: poser(s, k, champ))

        with ui.grid(columns="repeat(3, 190px)").classes("gap-3 items-start mt-2"):
            ui.label(""); main_ed("N"); ui.label("")
            main_ed("O"); centre = ui.label("").classes("text-base text-gray-700 whitespace-pre-line self-center"); main_ed("E")
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

    vue_aide = {"k": int(PAGE.get("aide") or 0)}          # la section de l'aide montrée

    PAGES = {"Fichier": [("nouveau", "Nouveau"), ("ouvrir", "Ouvrir une séance"),   # (Importer : une des trois façons de Nouveau)
                         ("infos", "Infos"), ("exporter", "Exporter…"), ("dossier", "Ouvrir le dossier de travail")],
             "Rapports": [("creer", "Créer les rapports"), ("seance", "Rapports de la séance")],   # (le bilan : bilan.py, à la main)
             "Réglages": [("nom", "Votre nom"), ("systeme", "Votre système"), ("affichage", "Taille du texte"), ("expert", "L'expert"),
                          ("dossiers", "Dossiers"), ("sauvegarde", "Sauvegarder mes séances"),
                          ("maj", "Mise à jour et nouveautés"), ("contact", "Un problème, une idée ?")]}     # la barre de gauche de ces onglets
    # les intertitres de la barre de Réglages : vous, vos séances, le programme (l'utilisateur, 2026-11-12 : un peu d'ordre)
    GROUPES_PAGES = {"Réglages": {"nom": "Vous", "dossiers": "Vos séances", "maj": "Le programme"}}
    vue_page = {"Fichier": "nouveau" if PAGE.get("fichier") == "importer" else
                           PAGE.get("fichier") if PAGE.get("fichier") in ("nouveau", "ouvrir", "infos", "exporter", "dossier") else "ouvrir",
                "Rapports": PAGE.get("rapports") if PAGE.get("rapports") in ("creer", "seance") else "creer",
                "Réglages": PAGE.get("reglages") if PAGE.get("reglages") in ("affichage", "nom", "systeme", "dossiers", "expert", "sauvegarde", "maj", "contact") else
                    "maj" if PAGE.get("reglages") == "nouveautes" else "affichage"}

    facon = {"k": PAGE.get("nouveau") if PAGE.get("nouveau") in ("bws", "pbn", "themes") else   # Fichier, Nouveau : la façon choisie
             ("bws" if PAGE.get("fichier") == "importer" else "themes")}

    sauve = {"fait": "", "faute": ""}                     # Réglages, Sauvegarder mes séances
    a_importer = {"chemin": None, "prop": None, "titre": "", "nom": "", "nom_touche": False, "lecture": False, "faute": ""}

    def retenir_page():
        """La page ouverte (onglet, entrée de la barre, version de l'analyse, page de l'aide) : rouverte au prochain lancement."""
        o = onglets.value; nom = o if isinstance(o, str) else o.props.get("name", "Donnes")
        ecrire_etat(page={"onglet": nom, "entree": vue.get("entree"), "version": vue.get("version"), "aide": vue_aide["k"],
                          "fichier": vue_page["Fichier"], "rapports": vue_page["Rapports"], "reglages": vue_page["Réglages"],
                          "nouveau": facon["k"], "replis": replis})

    def onglet_a_pages():
        """« Fichier », « Rapports » ou « Réglages » quand l'un d'eux est ouvert, sinon None."""
        for nom, o in (("Fichier", o_fichier), ("Rapports", o_rapports), ("Réglages", o_reglages)):
            if onglets.value in (o, nom): return nom
        return None

    def montrer_pages():
        """Chaque onglet à pages montre la page choisie dans sa barre."""
        try: pages_ui
        except NameError: return                           # la page se construit encore
        for nom, cles in PAGES.items():
            for cle, _ in cles:
                if cle in pages_ui: pages_ui[cle].set_visibility(vue_page[nom] == cle)   # (celles déjà construites)

    def voir_page(nom, cle):
        vue_page[nom] = cle; montrer_pages(); barre_seance.refresh(); retenir_page()
        if cle == "seance": resultats.refresh()
        if nom == "Fichier": rafraichir_fichier()
        if cle == "contact": fichier_erreur.refresh()

    def rafraichir_fichier():
        """Les pages de Fichier se mettent à jour quand on y vient : les séances, les .bws, la séance à exporter."""
        try: liste.refresh(); liste_i.refresh(); a_exporter.refresh(); page_infos.refresh()
        except NameError: pass                             # la page se construit encore

    def voir_aide(k):
        vue_aide["k"] = k; page_aide.refresh(); barre_seance.refresh(); retenir_page()
        ui.run_javascript("window.scrollTo(0, 0)")

    def cle_aide():
        """Où l'on est, pour AIDE_POUR : (onglet, page ou entrée, précision)."""
        o = onglets.value; nom = o if isinstance(o, str) else o.props.get("name", "")
        if nom in ("Fichier", "Rapports", "Réglages"):
            pg = vue_page[nom]
            return (nom, pg, facon["k"]) if (nom, pg) == ("Fichier", "nouveau") else (nom, pg)
        e = vue.get("entree") or ""
        if nom == "Jouer":
            if e in ("options", "classement"): return (nom, e)
            m = jeu.get("mode") or "jouer"
            if m in ("revoir", "demo"): return (nom, m)
            p_ = jeu.get("partie")
            if p_: return (nom, "defense" if p_.en_defense() else "carte")
            return (nom, "encheres")
        if nom == "Analyse": return (nom, e if e in ("standard", "expert") else "donne")
        if nom == "Donnes":
            if e in ("seance", "joueurs"): return (nom, e)
            c = choix["chemin"]
            return (nom, "saisie") if c and e.startswith("d") and edition.modifiable(c)[0] else (nom, "donne")
        return (nom,)

    def ouvrir_aide(ancre=None):
        """L'aide, ouverte à la section voulue (sinon celle de la page où l'on est) : sa page, puis on y descend."""
        if not ancre and onglets.value in (o_aide, "Aide"): return   # déjà dans l'aide : on y reste
        ancre = ancre or section_aide(*cle_aide())
        k = next((i for i, (_, _, secs) in enumerate(sections_aide()) if ancre in [a for a, _ in secs]), vue_aide["k"])
        vue_aide["k"] = k
        if onglets.value not in (o_aide, "Aide"): onglets.set_value(o_aide)
        page_aide.refresh(); barre_seance.refresh(); retenir_page()
        ui.run_javascript(f"setTimeout(function () {{ window.allerAide && window.allerAide({json.dumps(ancre)}, true); }}, 120)")

    @ui.refreshable
    def page_aide():
        """Une page de l'aide, et à droite « Sur cette page » : ses sections, sur le même fond que le texte ; un clic
        y descend, la section lue est marquée en lisant (JS_SUR_PAGE)."""
        s_ = sections_aide(); cats = categories_aide()
        k_ = min(vue_aide["k"], len(s_) - 1)
        titre, h, sections = s_[k_]
        if k_ < len(cats) and cats[k_]: ui.label(cats[k_]).classes("text-sm text-gray-600 uppercase tracking-wide")
        with ui.row().classes("w-full no-wrap items-start gap-10"):
            ui.html(h, sanitize=False).classes("aide pb-24").style("flex:1 1 auto;min-width:0;max-width:46em")
            if sections:
                with ui.element("div").classes("sur-page-place shrink-0"), ui.column().classes("sur-page gap-0"):   # reste à l'écran
                    ui.label("Sur cette page").classes("text-sm font-bold text-gray-700 mb-2")
                    for ancre_, t_ in sections:
                        ui.html(f'<a href="#{ancre_}" data-ancre="{ancre_}" onclick="return allerAide(\'{ancre_}\')">{html_.escape(t_)}</a>',
                                sanitize=False)
        ui.run_javascript("window.suivreAide && window.suivreAide()")

    def entrees_de(data):
        """Les entrées de la barre latérale : la séance, puis (onglet Donnes) les joueurs et les alertes, puis chaque donne."""
        if sur_jouer():                                   # Jouer : les donnes seules, et celles déjà enchéries
            faits = jouer.lire_essais(base_seance(choix["chemin"]))["donnes"]
            donnes = data["donnes"]                   # par numéro, toujours (l'ordre joué : Options et « Donne suivante »)
            return [("options", "Options"), ("classement", "Classement")] + [(f"d{d['n']}", f"Donne {d['n']}" + (" · jouée" if classement.dernier_fini(faits.get(str(d["n"])))
                                                                                       else " · enchérie" if faits.get(str(d["n"])) else ""))
                                                for d in donnes if not d.get("a_completer")]
        haut = [("standard", "Analyse du coach"), ("expert", "Analyse expert")] if sur_analyse() else \
            [("seance", "Séance"), ("joueurs", "Joueurs")]   # toujours deux entrées : Donne 1 à la même hauteur partout
        return haut + [(f"d{d['n']}", f"Donne {d['n']}") for d in data["donnes"]]

    expert_msg = {"texte": "", "faute": False}

    def etapes_expert(c):
        """Les étapes pour obtenir l'analyse de l'expert de Claude, sur le web (claude.ai)."""
        nom = nom_pour_claude(lire_seance(c))
        ui.label("Obtenir l'analyse de l'expert avec Claude").classes("text-base font-bold mt-4")
        ui.label("L'analyse de l'expert est écrite par Claude (claude.ai, dans votre navigateur). Comptez une "
                 "conversation par séance ; pour 24 donnes, Claude peut répondre en plusieurs fois.").classes("text-base text-gray-700")
        etape = lambda k, texte: ui.html(f"<div style='font-size:16px'><b>{k}.</b> {texte}</div>", sanitize=False)
        with ui.column().classes("gap-3 max-w-2xl"):
            etape(1, "Préparez le fichier : Bridge Coach met dans un seul fichier tout ce dont Claude a besoin (la séance, "
                     "l'analyse du coach, le système, un exemple et la consigne), puis ouvre son dossier. Les joueurs n'y "
                     "sont que par leurs initiales : les noms complets ne quittent pas l'ordinateur.")
            ui.button("Préparer le fichier pour Claude", icon="folder_open", on_click=lambda: preparer_expert(c)).props("outline")
            etape(2, f"Ouvrez <b>{html_.escape(nom_outil(url_expert()))}</b> dans votre navigateur et commencez une nouvelle conversation.")
            ui.button("Ouvrir l'expert", icon="open_in_new", on_click=lambda: ouvrir(url_expert())).props("outline")
            etape(3, f"Glissez le fichier <code>{nom}.ai.json</code> dans la conversation.")
            etape(4, "Copiez la consigne, collez-la dans la conversation, puis envoyez.")
            ui.button("Copier la consigne", icon="content_copy", on_click=lambda: copier_consigne(c)).props("outline")
            etape(5, f"Claude écrit le fichier <code>{nom}-expert.json</code> : téléchargez-le avec le bouton sous sa réponse. "
                     "S'il répond en plusieurs fois, téléchargez chaque fichier.")
            etape(6, "Importez le fichier téléchargé (un par un s'il y en a plusieurs). Les donnes s'ajoutent à l'analyse "
                     "de l'expert, rangée dans la séance ; la version d'avant est gardée dans versions/.")
            ui.button("Importer l'analyse de l'expert…", icon="file_download", on_click=lambda: choisir_expert()).props("outline")
            etape(7, "Lisez-la ici, donne par donne. Pour les rapports PDF : l'onglet Rapports, « Créer les rapports ».")
            ui.button("Aller aux rapports", icon="picture_as_pdf", on_click=lambda: onglets.set_value(o_rapports)).props("outline")
            if expert_msg["texte"]:
                ui.label(expert_msg["texte"]).classes("text-base " + ("text-red-800" if expert_msg["faute"] else "text-primary") + " break-all")

    def maj_rapports():
        if T.actif or D.actif or I.actif or not choix["chemin"]: return
        vu["fini"] = None; faute.text = ""; faute_r.text = ""; fait_a.text = ""
        lancer_rapports(choix["chemin"], noms.value, revoir.value)
        resultats.refresh(); montrer_controles()

    def preparer_expert(c):
        try:
            dossier, _ = preparer_pour_claude(c)
            expert_msg.update(texte=f"Fichier prêt dans {dossier}", faute=False); ouvrir(dossier)
        except Exception:
            expert_msg.update(texte="Le fichier n'a pas pu être préparé.", faute=True)
        vue_analyse.refresh()

    def copier_consigne(c):
        date = (lire_seance(c) or {}).get("session", {}).get("date", "")
        ui.clipboard.write(CONSIGNE.format(nom=nom_pour_claude(lire_seance(c)), date=date, marque=moi.MARQUES[moi.marque(lire_seance(c) or {})]))
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
        if sur_jouer():                                   # Jouer : la première donne, pas les options ni le classement
            return next((k for k, _ in es if k.startswith("d")), es[0][0])
        return es[0][0]

    def montrer_controles():
        """« Lancer l'analyse » : sur la page Analyse standard, ou partout pendant qu'une analyse tourne."""
        try: controles
        except NameError: return                           # la page se construit encore : l'onglet change avant la barre
        data = lire_seance(choix["chemin"])
        controles.set_visibility(bool(data) and ((T.actif and T.genre == "analyse") or (sur_analyse() and entree_effective(data) == "standard")))

    def aller(k):
        vue["entree"] = k; vue["edition"] = None; montrer_barre(); barre_seance.refresh(); vue_seance.refresh(); vue_analyse.refresh(); vue_jouer.refresh(); montrer_controles()
        retenir_page()

    @ui.refreshable
    def barre_seance():
        if onglet_a_pages():                              # Rapports, Réglages : une entrée par page
            nom = onglet_a_pages()
            for k_, (cle, titre) in enumerate(PAGES[nom]):
                groupe = GROUPES_PAGES.get(nom, {}).get(cle)
                if groupe:                                  # l'intertitre d'un groupe de pages, petit et discret
                    ui.label(groupe).classes("text-xs text-gray-600 uppercase font-bold px-2 " + ("mt-1" if k_ == 0 else "mt-4")) \
                        .style("letter-spacing:.06em")
                ui.button(titre, on_click=lambda c=cle: voir_page(nom, c)).props("flat no-caps align=left dense color=grey-10") \
                    .classes("entree-barre text-left" + (" choisie" if vue_page[nom] == cle else ""))
            return
        if sur_aide():                                    # l'aide : une entrée par page (peu de pages, plus longues)
            cats, avant = categories_aide(), None
            for k, (titre, _, _) in enumerate(sections_aide()):
                cat = cats[k] if k < len(cats) else ""
                if cat and cat != avant:                     # l'intertitre de la catégorie, comme dans Réglages
                    ui.label(cat).classes("text-xs text-gray-600 uppercase font-bold px-2 " + ("mt-1" if avant is None else "mt-4")) \
                        .style("letter-spacing:.06em")
                avant = cat
                ui.button(titre, on_click=lambda k=k: voir_aide(k)).props("flat no-caps align=left dense color=grey-10") \
                    .classes("entree-barre aide-sujet text-left" + (" choisie" if k == vue_aide["k"] else ""))
            return
        data = lire_seance(choix["chemin"])
        if not data: return
        a_finir = {f"d{d['n']}" for d in data["donnes"] if d.get("a_completer")}
        es = entrees_de(data); haut = [x for x in es if not x[0].startswith("d")]
        if sur_jouer():                                   # cacher la liste, pour donner la place à la table
            with ui.row().classes("w-full justify-end -mb-2"):
                ui.button(icon="keyboard_double_arrow_left", on_click=lambda: basculer_liste(True)) \
                    .props("flat dense round size=sm color=grey-7").tooltip("Cacher la liste des donnes")
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

    def basculer_liste(cachee):
        """La liste des donnes de Jouer, cachée ou montrée (gardé dans etat.json : d'une donne à l'autre, d'une fois sur
        l'autre ; l'utilisateur, 2026-11-11)."""
        ecrire_etat(liste_cachee=cachee); montrer_barre(); vue_jouer.refresh()

    def montrer_barre():
        """La barre latérale : sur les onglets Donnes, Jouer et Analyse quand une séance est ouverte ; toujours sur
        Rapports, Réglages et l'aide."""
        if plein["on"] and sur_jouer(): tiroir.set_value(False); return   # Jouer, table seule
        if sur_jouer() and str(vue.get("entree") or "").startswith("d") and lire_etat().get("liste_cachee"):
            tiroir.set_value(False); return                # Jouer, une donne : la liste cachée par vous (« « » en haut de la liste)
        tiroir.set_value(sur_aide() or bool(onglet_a_pages()) or (onglets.value in (o_donnes, "Donnes", o_jouer, "Jouer", o_analyse, "Analyse")
                                        and lire_seance(choix["chemin"]) is not None))   # l'aide a toujours sa barre
    vu = {"fini": None}; vu_d = {"fini": None}; vu_i = {"fini": None}

    with ui.header(elevated=False).classes("bg-white text-primary px-2 py-0 border-b border-gray-300") as entete:   # la barre de menus
        with ui.row().classes("w-full items-center justify-between no-wrap"):
            with ui.tabs().props("no-caps dense inline-label align=left active-color=primary indicator-color=primary").classes("text-gray-700 grow") as onglets:   # les onglets, dans la barre
                o_fichier = ui.tab("Fichier")                     # une page, comme Rapports et Réglages : sa barre à gauche
                o_donnes = ui.tab("Donnes")
                o_jouer = ui.tab("Jouer")
                o_analyse = ui.tab("Analyse")
                o_rapports = ui.tab("Rapports")
                o_reglages = ui.tab("Réglages")
                o_aide = ui.tab("Aide").classes("hidden")          # la page d'aide : montrée par le bouton de droite
            with ui.button(on_click=lambda: ouvrir_aide()).props("flat no-caps dense").classes("px-3") as aide:   # l'aide de la page ouverte
                with ui.row().classes("items-center gap-1 no-wrap"):   # une icône de couleur : l'aide se voit (l'utilisateur, 2026-11-12)
                    ui.icon("help", size="22px").style("color:#1976d2")
                    ui.label("Aide")
            onglets.on_value_change(lambda e: (aide.classes(add="bg-green-50 font-bold") if e.value in (o_aide, "Aide")
                                               else aide.classes(remove="bg-green-50 font-bold"), montrer_barre(), barre_seance.refresh(),
                                               vue_analyse.refresh(), vue_jouer.refresh(), montrer_controles(), retenir_page(),
                                               e.value in (o_fichier, "Fichier") and rafraichir_fichier()))

    with ui.left_drawer(value=False, fixed=True, bordered=True).props(f"width={LARGEUR_BARRE} behavior=desktop") \
            .classes("p-2 gap-0").style(f"background:{GRIS_BARRE}") as tiroir:      # la barre latérale de des onglets Donnes et Analyse : bord gauche, toute la hauteur
        barre_seance()

    with ui.column().classes("w-full px-0 pt-0 pb-6 gap-0"):   # la marge de la page seule (16 px), comme les barres (l'utilisateur)

        with ui.tab_panels(onglets, value=o_donnes, animated=False).classes("w-full"):
            with ui.tab_panel(o_donnes).classes("px-0"):
                @ui.refreshable
                def nouveau():
                    neuf = next((b for b in reglages()[0] if not deja_importe(b)), None)
                    if not neuf or I.actif: return
                    with ui.row().classes("w-full max-w-xl items-center justify-between no-wrap bg-green-50 rounded px-3 py-2 mb-3"):
                        with ui.column().classes("gap-0"):
                            ui.label(f"Nouveau tournoi dans Bridgemate, du {date_lisible(neuf)}").classes("text-base")
                            ui.label(os.path.basename(neuf)).classes("text-base text-gray-700 break-all")
                        ui.button("Importer…", on_click=lambda b=neuf: preparer_import(b)).classes("shrink-0")
                nouveau()
                barre_i = ui.linear_progress(value=0, show_value=False).props("size=16px rounded indeterminate").classes("max-w-xl")
                texte_i = ui.label("").classes("text-base")
                faute_i = ui.label("").classes("text-base text-red-800")
                vue_seance()

            with ui.tab_panel(o_jouer).classes("px-0 pt-0"):   # en haut, la marge de gauche seulement (l'utilisateur, 2026-11-11)
                vue_jouer()

            with ui.tab_panel(o_analyse).classes("px-0 gap-3"):
                with ui.column().classes("w-full gap-3 pb-3 border-b border-gray-200") as controles:   # fixe : la barre y avance
                    with ui.row().classes("w-full items-center gap-4 no-wrap"):
                        creer = ui.button("Lancer l'analyse", icon="play_arrow", on_click=lambda: demarrer()).classes("text-base px-6")
                    barre = ui.linear_progress(value=0, show_value=False).props("size=16px rounded").classes("max-w-xl")
                    texte = ui.label("").classes("text-base")
                    stop = ui.button("Annuler", on_click=annuler).props("outline")
                    faute = ui.label("").classes("text-base text-red-800")
                    fait_a = ui.label("").classes("text-base text-primary")
                vue_analyse()

            pages_ui = {}
            with ui.tab_panel(o_rapports).classes("px-0 pt-0 gap-4 max-w-xl"):
                with ui.column().classes("w-full gap-2") as pages_ui["creer"]:   # les options, puis « Créer les rapports »
                    titre_page("Créer les rapports", "rapport")
                    ui.label("Vous êtes").classes("text-base")
                    actuel = moi.nom()

                    def choisir_moi(e):
                        if e.value == SEPARATEUR: e.sender.value = moi.nom() or ""; return   # la ligne de séparation
                        ecrire_etat(moi=e.value or None); retenir_licence(e.value); vue_seance.refresh()
                    choix_moi = ui.select(options_joueurs(actuel), value=actuel or "", with_input=True, on_change=choisir_moi) \
                        .classes("w-full").props("outlined dense") \
                        .props(":option-disable=\"o => typeof o.label === 'string' && o.label.startsWith('───')\"")   # la ligne ne se choisit pas
                    ui.label("Votre table est surlignée dans les tableaux des résultats : dans l'onglet Donnes tout de suite, dans les "
                             "rapports quand ils sont refaits.").classes("text-base text-gray-700")
                    ui.checkbox("Les donnes dans l'ordre où vous les avez jouées", value=moi.ordre_joue(),
                                on_change=lambda e: ecrire_etat(ordre_joue=e.value)).classes("text-base")
                    ui.label("Quand la séance décrit votre parcours (tour, table, adversaires) ; sinon par numéro.").classes("text-base text-gray-700 -mt-2")
                    ui.checkbox("Inclure l'avis de l'expert", value=avec_expert(),
                                on_change=lambda e: ecrire_etat(avec_expert=e.value)).classes("text-base")
                    ui.label("Quand Claude a rédigé l'analyse de la séance (onglet Analyse, « Analyse expert ») : son avis, en "
                             "vert, après le conseil du coach.").classes("text-base text-gray-700 -mt-2")
                    noms = ui.checkbox("Ajouter une page avec le nom des joueurs").classes("text-base")
                    revoir = ui.checkbox("Seulement les donnes à revoir").classes("text-base")
                    ui.label("Quand « Vous êtes » est choisi : « Vous face au champ », puis seulement les donnes où vous "
                             "pouviez faire mieux, la plus coûteuse d'abord. Un rapport à part : l'analyse complète reste.") \
                        .classes("text-base text-gray-700 -mt-2")
                    creer_r = ui.button("Créer les rapports", icon="picture_as_pdf", on_click=lambda: maj_rapports()).classes("text-base px-6 mt-2")
                    besoin_r = ui.label("").classes("text-base text-gray-700")
                    barre_r = ui.linear_progress(value=0, show_value=False).props("size=16px rounded")
                    texte_r = ui.label("").classes("text-base")
                    stop_r = ui.button("Annuler", on_click=annuler).props("outline")
                    faute_r = ui.label("").classes("text-base text-red-800")

                @ui.refreshable
                def resultats():
                    c = choix["chemin"]
                    if not c: ui.label("Aucune séance ouverte.").classes("text-base"); return
                    prets = rapports_de(c)
                    ui.label(f"Rapports de la séance du {infos_seance(c)[0]}").classes("text-lg font-bold")
                    if not prets:
                        ui.label("Pas encore de rapport : « Créer les rapports », dans la barre de gauche.").classes("text-base text-gray-700")
                    for quoi, nom, detail in RAPPORTS:
                        for f, pour in prets.get(quoi, []):        # l'analyse : une par paire (ses initiales)
                            lien_pdf(f, f"{nom} pour {pour}" if pour else nom, detail)
                    if prets:
                        ui.button("Ouvrir le dossier des rapports", on_click=lambda p=prets[next(iter(prets))][0][0]: ouvrir(os.path.dirname(p))) \
                            .props("flat no-caps").classes("mt-2 px-0")

                with ui.column().classes("w-full gap-2") as pages_ui["seance"]:
                    resultats()

            with ui.tab_panel(o_reglages).classes("px-0 pt-0 gap-5 max-w-xl"):
              with ui.column().classes("w-full gap-3") as pages_ui["affichage"]:
                titre_page("Taille du texte", "taille")
                ui.label("Agrandit toute la fenêtre : le texte, les cartes et les tableaux. « Grande » ou « Très grande » "
                         "pour un grand écran, une télévision en cours, ou si vous voyez moins bien. Le choix est gardé.") \
                    .classes("text-base text-gray-700")

                def changer_taille(z):
                    ecrire_etat(zoom=z); boutons_taille.refresh()
                    if sur_jouer(): vue_jouer.refresh()            # A− A+ à côté de la table
                    ui.run_javascript(f"document.documentElement.style.zoom = {z}; "
                                      f"document.documentElement.style.setProperty('--zoom', {z}); window.dispatchEvent(new Event('resize'))")

                @ui.refreshable
                def boutons_taille():
                    with ui.row().classes("gap-3"):
                        for z, nom in TAILLES:
                            ui.button(nom, on_click=lambda z=z: changer_taille(z)) \
                                .props("unelevated" if z == taille_texte() else "outline").classes("text-base px-4")
                boutons_taille()

              with ui.column().classes("w-full gap-3") as pages_ui["nom"]:
                titre_page("Votre nom", "votre-table")
                ui.label("Qui utilise Bridge Coach sur cet ordinateur : choisissez votre nom tel que la FFB l'écrit, dans la liste "
                         "des joueurs de vos tournois. Bridge Coach vous reconnaît ensuite par votre numéro de licence, même si "
                         "votre nom est écrit autrement d'un tournoi à l'autre.").classes("text-base text-gray-700")

                def choisir_mon_nom(e):
                    if e.value == SEPARATEUR: e.sender.value = lire_etat().get("mon_nom") or ""; return
                    ecrire_etat(mon_nom=e.value or None); retenir_licence(e.value)
                    if e.value and not moi.nom(): ecrire_etat(moi=e.value); vue_seance.refresh()   # « Vous êtes » vide : c'est vous
                    choix_moi.set_options(options_joueurs(moi.nom()), value=moi.nom() or "")
                    ma_licence.refresh()
                noms_tous = {"": "Inconnu (pas de nom)"} | {x: x for x in moi.tous_les_noms(rapport.glob_seances("*" + rapport.BC))}
                if lire_etat().get("mon_nom") and lire_etat()["mon_nom"] not in noms_tous: noms_tous[lire_etat()["mon_nom"]] = lire_etat()["mon_nom"]
                ui.select(noms_tous, value=lire_etat().get("mon_nom") or "", with_input=True, on_change=choisir_mon_nom) \
                    .classes("w-full").props("outlined dense")
                @ui.refreshable
                def ma_licence():
                    n_ = lire_etat().get("mon_nom")
                    if not n_:                              # facultatif : sans nom, l'utilisateur est « inconnu »
                        ui.html("<div style='font-size:16px'>Vous êtes : <b>inconnu</b>.</div>", sanitize=False)
                        ui.label("C'est facultatif. Sans nom, Bridge Coach marche aussi : vos tables ne sont simplement pas "
                                 "surlignées.").classes("text-base text-gray-700"); return
                    lic_ = moi.licence_de(n_)
                    ui.html(f"<div style='font-size:16px'>Vous êtes <b>{html_.escape(n_)}</b>" +
                            (f", licence FFB <b>{lic_}</b>.</div>" if lic_ else ".</div>"), sanitize=False)
                    if not lic_:
                        ui.label("Licence inconnue : elle viendra avec le prochain tournoi Bridgemate importé où vous avez joué.") \
                            .classes("text-base text-gray-700")
                    ui.label("Votre licence et les noms des joueurs restent sur cet ordinateur : rien de cela ne part chez l'expert "
                             "ni ailleurs.").classes("text-sm text-gray-600")
                ma_licence()

              with ui.column().classes("w-full gap-5") as pages_ui["dossiers"]:
                titre_page("Dossiers", "reglages")
                for titre, chemin in (("Dossier de Bridgemate : les fichiers .bws, lus sans être modifiés", dossier),
                                      ("Dossier de travail : vos séances et vos rapports", rapport.DONNEES),
                                      ("Programme Bridge Coach : là où il est installé", rapport.RACINE)):
                    with ui.row().classes("w-full items-center justify-between no-wrap"):
                        with ui.column().classes("gap-0"):
                            ui.label(titre).classes("text-base")
                            ui.label(chemin).classes("text-base text-gray-700 break-all")
                        if os.path.isdir(chemin):
                            ui.button("Ouvrir", on_click=lambda c=chemin: ouvrir(c)).props("outline").classes("shrink-0")
                        else:
                            ui.label("Dossier introuvable").classes("text-base text-red-800 shrink-0")
                ui.button("Modifier les réglages", on_click=ouvrir_reglages).classes("w-full text-base py-3")
                ui.label("Après une modification : enregistrez, puis fermez et rouvrez Bridge Coach.").classes("text-base text-gray-700")

              with ui.column().classes("w-full gap-2") as pages_ui["systeme"]:   # Réglages, Votre système : la fiche de conventions
                titre_page("Votre système", "systeme")
                ui.label("Votre fiche de conventions, à imprimer ou à garder en PDF pour un partenaire. Chaque ligne part de ce "
                         "que joue Bridge Coach (SEF 2024) : changez ce que votre paire joue autrement. Ce qui est écrit ici "
                         "ne change pas ce que jouent les robots.").classes("text-base text-gray-700")
                fiche_ = fiche_conventions.lire()
                joueurs_in = ui.input("Les joueurs", value=fiche_.get("joueurs") or "",
                                      placeholder="Par exemple : MARTIN Anne et BERNARD Henri").props("outlined").classes("w-full text-base")
                joueurs_in.on("blur", lambda: fiche_conventions.changer_entete(joueurs=joueurs_in.value))
                with ui.row().classes("gap-3 mt-1"):
                    ui.button("Imprimer ou garder en PDF", icon="print", on_click=lambda: imprimer_fiche()).props("unelevated")
                    ui.button("Tout remettre comme Bridge Coach", icon="restart_alt", on_click=lambda: remettre_fiche_d.open()).props("flat")
                def lignes_texte(section_, lignes_):
                    """Une section de lignes à réécrire (le système, les entames, la signalisation)."""
                    ui.label(section_).classes("text-base font-bold mt-4")
                    for cle_, titre_l, defaut_, incertain_ in lignes_:
                        val_, change_ = fiche_conventions.valeur(cle_, fiche_)
                        with ui.row().classes("w-full items-start no-wrap gap-3"):
                            ui.html(rouge(html_.escape(titre_l)), sanitize=False).classes("text-base font-bold pt-2 shrink-0").style("width:190px")
                            with ui.column().classes("grow gap-0"):
                                zone = ui.textarea(value=val_).props("outlined dense autogrow").classes("w-full text-base")
                                with ui.row().classes("items-center gap-2"):
                                    a_verifier = ui.label("à vérifier").classes("text-sm").style("color:#8a5a00") \
                                        .tooltip("Le système de Bridge Coach n'est pas sûr de cette ligne : relisez-la")
                                    change_lbl = ui.label("changé").classes("text-sm text-primary font-bold")
                                    retour = ui.button("Revenir à Bridge Coach", icon="undo").props("flat dense no-caps size=sm")
                                def montrer_etat(cle=cle_, inc=incertain_, av=a_verifier, ch=change_lbl, rt=retour):
                                    c_ = fiche_conventions.valeur(cle)[1]
                                    av.set_visibility(inc and not c_); ch.set_visibility(c_); rt.set_visibility(c_)
                                def enregistrer_ligne(cle=cle_, z=zone, m=montrer_etat):
                                    fiche_conventions.changer(cle, z.value); m()
                                def revenir(cle=cle_, z=zone, d=defaut_, m=montrer_etat):
                                    fiche_conventions.changer(cle, ""); z.value = d; m()
                                zone.on("blur", enregistrer_ligne); retour.on_click(revenir)
                                montrer_etat()

                lignes_texte(*fiche_conventions.MODELE[0])        # le système en une ligne
                ui.label("Conventions d'enchères").classes("text-base font-bold mt-4")
                ui.label("Oui ou Non pour chacune : au départ, ce que joue Bridge Coach.").classes("text-base text-gray-700")
                for cle_, nom_c, desc_c, defaut_c, incertain_c in fiche_conventions.CONVENTIONS:
                    oui_, change_c = fiche_conventions.convention(cle_, fiche_)
                    with ui.row().classes("w-full items-center no-wrap gap-3 py-1").style("border-bottom:1px solid #eceff1"):
                        with ui.column().classes("grow gap-0"):
                            ui.html(f"<b>{rouge(html_.escape(nom_c))}</b>", sanitize=False).classes("text-base")
                            ui.html(rouge(html_.escape(desc_c)), sanitize=False).classes("text-sm text-gray-600")
                        av_c = ui.label("à vérifier").classes("text-sm shrink-0").style("color:#8a5a00") \
                            .tooltip("Bridge Coach n'est pas sûr de jouer cette convention comme la FFB : vérifiez")
                        ch_c = ui.label("changé").classes("text-sm text-primary font-bold shrink-0") \
                            .tooltip("Bridge Coach dit " + ("Oui" if defaut_c else "Non"))
                        bascule = ui.toggle({True: "Oui", False: "Non"}, value=oui_).props("no-caps dense toggle-color=primary").classes("shrink-0")
                        def montrer_c(cle=cle_, inc=incertain_c, av=av_c, ch=ch_c):
                            c_ = fiche_conventions.convention(cle)[1]
                            av.set_visibility(inc and not c_); ch.set_visibility(c_)
                        bascule.on_value_change(lambda e, cle=cle_, m=montrer_c: (fiche_conventions.choisir_convention(cle, e.value), m()))
                        montrer_c()
                for section_, lignes_ in fiche_conventions.MODELE[1:]:   # le jeu de la carte
                    lignes_texte(section_, lignes_)
                ui.label("Nos accords particuliers").classes("text-base font-bold mt-4")
                accords_in = ui.textarea(value=fiche_.get("accords") or "", placeholder="Ce qui n'est pas dans la fiche : une convention "
                                         "à vous, une exception, un rappel…").props("outlined autogrow").classes("w-full text-base")
                accords_in.on("blur", lambda: fiche_conventions.changer_entete(accords=accords_in.value))

              with ui.column().classes("w-full gap-3") as pages_ui["expert"]:   # Réglages, L'expert : l'outil d'IA et le prénom
                titre_page("L'expert", "questions-expert")
                ui.label("L'expert est un outil d'intelligence artificielle, sur Internet : Claude (claude.ai) par défaut, ou un "
                         "autre que vous préférez. Il écrit l'analyse de l'expert et répond à vos questions sur une donne "
                         "(« Demander à l'expert », dans Jouer et Analyse).").classes("text-base text-gray-700")
                adresse_in = ui.input("Adresse de l'outil", value=url_expert()).props("outlined").classes("w-full text-base")
                adresse_in.on("blur", lambda: ecrire_etat(expert_url=adresse_in.value.strip() or question_expert.ADRESSE))
                ui.label("Par exemple https://claude.ai/new ou https://chatgpt.com").classes("text-sm text-gray-600")
                prenom_in = ui.input("Le prénom que l'expert peut employer", value=prenom_expert()).props("outlined").classes("w-full text-base")
                prenom_in.on("blur", lambda: ecrire_etat(expert_prenom=prenom_in.value.strip()))
                ui.label("L'expert vous saluera par ce prénom. C'est le seul nom qui part chez lui : les autres joueurs n'y sont "
                         "que par leurs initiales. Laissez vide pour rester anonyme.").classes("text-base text-gray-700")

              with ui.column().classes("w-full gap-3") as pages_ui["sauvegarde"]:   # Réglages, Sauvegarder mes séances
                titre_page("Sauvegarder mes séances", "sauvegarde")
                ui.label("Un seul fichier .zip avec toutes vos séances : leurs donnes, leurs résultats, vos parties jouées et "
                         "surtout les analyses de l'expert, qui ne se refont pas. Les rapports PDF n'y sont pas : ils se refont "
                         "en un clic. Gardez ce fichier ailleurs que sur l'ordinateur : une clé USB, un disque, un dossier en "
                         "ligne.").classes("text-base text-gray-700")
                ui.button("Sauvegarder mes séances…", icon="save", on_click=lambda: sauvegarder_()).props("unelevated").classes("self-start")
                @ui.refreshable
                def etat_sauvegarde():
                    e = lire_etat()
                    if sauve["faute"]: ui.label(sauve["faute"]).classes("text-base text-red-800")
                    if sauve["fait"]:
                        ui.label(sauve["fait"]).classes("text-base text-primary break-all")
                        ui.button("Montrer dans le dossier", icon="folder_open", on_click=lambda: montrer_fichier(e["sauvegarde_chemin"])).props("outline")
                    elif e.get("sauvegarde_le"):
                        ui.label(f"Dernière sauvegarde le {quand_iso(e['sauvegarde_le'])}.").classes("text-base text-gray-700")
                    else:
                        ui.label("Aucune sauvegarde faite pour l'instant.").classes("text-base text-gray-700")
                etat_sauvegarde()

              with ui.column().classes("w-full gap-3") as pages_ui["contact"]:   # Réglages, Un problème, une idée ?
                titre_page("Un problème, une idée ?", "signaler")
                ui.label("Bridge Coach se discute sur GitHub, le site où vit son programme. Il faut un compte GitHub, gratuit, "
                         "pour écrire ; tout le monde peut lire. Écrivez en français.").classes("text-base text-gray-700")
                for titre_, texte_, lien_, icone_ in (
                        ("Signaler un problème", "Quelque chose ne marche pas, un message d'erreur, un résultat faux : dites ce que "
                         "vous faisiez, ce que vous attendiez et ce qui s'est passé.", GITHUB + "/issues/new", "bug_report"),
                        ("Proposer une idée, poser une question, discuter", "Une amélioration, une façon de faire, une question "
                         "sur le bridge ou sur le programme : les discussions sont ouvertes à tous.", GITHUB + "/discussions", "forum")):
                    with ui.row().classes("w-full items-start gap-3 no-wrap p-3").style("border:2px solid #e3e7ea;border-radius:10px"):
                        ui.icon(icone_, size="26px").classes("text-primary")
                        with ui.column().classes("gap-1 grow"):
                            ui.label(titre_).classes("text-base font-bold")
                            ui.label(texte_).classes("text-base text-gray-700")
                            ui.button("Ouvrir dans le navigateur", icon="open_in_new", on_click=lambda l=lien_: ouvrir(l)).props("outline").classes("self-start")
                            ui.label(lien_).classes("text-sm text-gray-600 break-all")
                ui.label(f"Donnez aussi le numéro de version : {maj.version_locale()}, et votre système "
                         f"({'Windows' if sys.platform == 'win32' else 'Mac'}).").classes("text-base text-gray-700")
                @ui.refreshable
                def fichier_erreur():
                    f_ = os.path.join(rapport.RAPPORTS, "derniere-erreur.txt")
                    if not os.path.exists(f_):
                        ui.label("Quand un calcul échoue, Bridge Coach en écrit le détail dans le fichier derniere-erreur.txt "
                                 "du dossier des rapports. Il n'y en a pas pour l'instant.").classes("text-base text-gray-700"); return
                    le_ = datetime.datetime.fromtimestamp(os.path.getmtime(f_)).strftime("%d/%m/%Y à %H:%M")
                    ui.html(f"<b>La dernière erreur</b> (le {le_}) est dans le fichier <b>derniere-erreur.txt</b>. Joignez-le à "
                            "votre signalement : glissez-le dans la case du message sur GitHub. Il ne contient que le détail "
                            "technique de l'erreur et des noms de dossiers de votre ordinateur, pas vos séances ni les noms "
                            "des joueurs ; ouvrez-le pour le vérifier si vous voulez.", sanitize=False).classes("text-base text-gray-700")
                    with ui.row().classes("gap-3"):
                        ui.button("Montrer le fichier", icon="folder_open", on_click=lambda: montrer_fichier(f_)).props("outline")
                        ui.button("L'ouvrir", icon="description", on_click=lambda: ouvrir(f_)).props("flat")
                fichier_erreur()
                ui.label("N'envoyez pas vos fichiers de séance (.bc.json) sur GitHub : ils contiennent les noms complets des "
                         "joueurs, et tout ce qu'on y dépose est public.").classes("text-base text-gray-700")

              with ui.column().classes("w-full gap-3") as pages_ui["maj"]:
                titre_page("Mise à jour et nouveautés", "mise-a-jour")
                ui.label(f"Bridge Coach, version {maj.version_locale()}").classes("text-base font-bold")
                with ui.row().classes("items-center gap-3"):
                    ui.button("Rechercher une mise à jour", on_click=lambda: chercher_maj()).props("outline")
                    bouton_maj = ui.button("", on_click=lambda: lancer_maj()).props("unelevated")
                    bouton_maj.set_visibility(False)
                etat_maj = ui.label("Bridge Coach ne contacte GitHub que si vous cliquez ; il n'envoie rien.").classes("text-base text-gray-700")
                journal = os.path.join(rapport.RAPPORTS, maj.JOURNAL)
                if os.path.exists(journal):
                    lignes_j = [x for x in open(journal, encoding="utf-8").read().splitlines() if x.strip()]
                    if lignes_j:
                        le = datetime.datetime.fromtimestamp(os.path.getmtime(journal)).strftime("%d/%m/%Y")   # pas « quand » : la fonction
                        ui.label(f"Dernière mise à jour, le {le} : {lignes_j[0]} — {lignes_j[-1]}").classes("text-base text-gray-700")
                ui.label("Ce qui a changé, version par version").classes("text-base font-bold mt-4")   # les nouveautés de chaque version
                installee = maj.version_locale()
                for k_, (v, d_, h) in enumerate(toutes_nouveautes()):
                    titre_v = f"Version {v}" + (f" · {date_en_mots(d_)}" if d_ else "") + ("  (la vôtre)" if maj.cle(v) == maj.cle(installee) else "")
                    with ui.expansion(titre_v, value=k_ == 0).classes("w-full").props("dense header-class='text-base font-bold'"):
                        ui.html(h, sanitize=False).classes("aide pb-2")

            montrer_pages()                                # chaque onglet à pages s'ouvre sur sa première page

            with ui.tab_panel(o_aide).classes("px-0 pt-0").style("max-width:1100px"):   # une page comme les autres : un onglet la quitte
                page_aide()                                    # une section à la fois, choisie dans la barre de gauche

            with ui.tab_panel(o_fichier).classes("px-0 pt-0 max-w-3xl") as panneau_fichier, \
                    ui.column().classes("w-full gap-0") as pages_ui["nouveau"]:   # Fichier : ses pages, la première Nouveau
                titre_page("Nouvelle séance", "importer")
                ui.html("Une séance Bridge Coach est un seul fichier, <b>.bc.json</b> : les donnes, les joueurs, les "
                        "résultats et les analyses. Trois façons d'en créer une :", sanitize=False).classes("text-base text-gray-700")
                FACONS = [("bws", "Importer un tournoi Bridgemate", "depuis le fichier .bws du tournoi", "table_restaurant"),
                          ("pbn", "Importer un fichier PBN", "des donnes de BBO, Funbridge, d'un autre logiciel…", "description"),
                          ("themes", "Créer des donnes d'entraînement", "sur des thèmes choisis, ou une séance vide", "school")]
                sections_n = {}

                def choisir_facon(k):
                    facon["k"] = k; cartes_facon.refresh()
                    for x, col in sections_n.items(): col.set_visibility(x == k)
                    retenir_page()

                @ui.refreshable
                def cartes_facon():
                    with ui.row().classes("w-full no-wrap gap-3 mt-2 mb-4 items-stretch"):   # trois cartes de même taille
                        for k, titre, sous, icone in FACONS:
                            choisi = facon["k"] == k
                            with ui.column().classes("gap-1 p-3 cursor-pointer").style(
                                    "flex:1 1 0;min-width:0;border-radius:10px;" + ("background:#eef4fb;border:2px solid #1976d2" if choisi else
                                                             "background:#fff;border:2px solid #e3e7ea")) \
                                    .on("click", lambda k=k: choisir_facon(k)):
                                with ui.row().classes("items-start no-wrap gap-2"):
                                    ui.icon(icone, size="22px").classes("text-primary" if choisi else "text-gray-600")
                                    ui.label(titre).classes("text-base font-bold")
                                ui.label(sous).classes("text-base text-gray-700")
                cartes_facon()

                @ui.refreshable
                def formulaire_import():
                    """Avant d'importer : le titre et le nom du fichier proposés, à changer si on veut (fichiers.proposer)."""
                    x = a_importer
                    if not x["chemin"]: return
                    with ui.column().classes("w-full gap-2 p-4 mb-4").style("border:2px solid #1976d2;border-radius:10px;background:#f7fafd"):
                        ui.label(f"Importer {os.path.basename(x['chemin'])}").classes("text-lg font-bold break-all")
                        if x["lecture"]:
                            ui.label("Lecture du fichier…").classes("text-base text-gray-700"); return
                        if x["faute"]:
                            ui.label(x["faute"]).classes("text-base text-red-800")
                            ui.button("Fermer", on_click=lambda: fermer_import()).props("flat"); return
                        p = x["prop"]
                        ui.label(f"Séance du {p['date']}").classes("text-base text-gray-700")
                        if p["deja"]:
                            ui.html(f"Déjà importé : <b>{html_.escape(fichiers.titre_de(p['deja']))}</b>. L'importer à nouveau met "
                                    "cette séance à jour ; ses analyses, ses parties jouées et les noms complets restent.",
                                    sanitize=False).classes("text-base text-gray-700")
                        titre_in = ui.input("Titre", value=x["titre"]).props("outlined").classes("w-full text-base")
                        nom_in = ui.input("Nom du fichier", value=x["nom"]).props("outlined suffix=.bc.json").classes("w-full text-base")
                        nom_in.set_enabled(not p["deja"])          # un réimport garde son fichier (Fichier, Infos le renomme)
                        aide = ui.label("").classes("text-base")

                        def verifier():
                            n = fichiers.nettoyer_nom(nom_in.value); x["nom"] = nom_in.value; x["titre"] = titre_in.value
                            pris = n and not p["deja"] and os.path.exists(os.path.join(p["dossier"], n + rapport.BC))
                            aide.text = ("Donnez un nom au fichier." if not n else
                                         f"Ce nom est déjà pris : {n}.bc.json" if pris else
                                         f"Enregistré sous : {n}.bc.json" if n != nom_in.value.strip() else "")
                            aide.classes(replace="text-base " + ("text-red-800" if (pris or not n) else "text-gray-700"))
                            ok.set_enabled(bool(n) and not pris and bool(titre_in.value.strip()))

                        def titre_change(e):
                            if not x["nom_touche"] and not p["deja"]:   # le nom suit le titre, tant qu'on ne l'a pas tapé
                                x["nom"] = fichiers.nom_libre(p["dossier"], fichiers.nom_propose(
                                    {"session": {"date": p["date"]}}, e.value, p["genre"]))
                                nom_in.value = x["nom"]           # (x["nom"] d'abord : nom_change n'y voit pas une frappe)
                            verifier()

                        def nom_change(_):
                            if nom_in.value != x["nom"]: x["nom_touche"] = True
                            verifier()
                        with ui.row().classes("gap-3"):
                            ok = ui.button("Importer" if not p["deja"] else "Importer à nouveau", icon="download",
                                           on_click=lambda: importer(x["chemin"], fichiers.nettoyer_nom(nom_in.value), titre_in.value.strip())) \
                                .props("unelevated")
                            ui.button("Annuler", on_click=lambda: fermer_import()).props("flat")
                        titre_in.on_value_change(titre_change); nom_in.on_value_change(nom_change)
                        verifier()
                formulaire_import()

                with ui.column().classes("w-full gap-0") as sections_n["themes"]:
                  ui.label("Choisissez des thèmes et combien de donnes de chacun ; sans thème, la séance est vide et vous tapez "
                           "les mains dans l'onglet Donnes. Les thèmes d'enchères et de jeu de la carte choisis ensemble sont "
                           "réunis dans les mêmes donnes. Elles sont créées dans une nouvelle séance .bc.json, avec un .pbn à côté "
                           "pour Bridgemate.").classes("text-base text-gray-700")
                  quotas = {x: 0 for x in donnes.themes_tries()}
                  niveaux = set(lire_etat().get("niveaux") or [1])   # les niveaux montrés, gardés d'une fois sur l'autre
                  total = lambda: sum(k for _, k in donnes.combiner([(t, k) for t, k in quotas.items() if k]))

                  def changer(x, k):
                      avant = quotas[x]; quotas[x] = max(0, quotas[x] + k)
                      if total() > 36: quotas[x] = avant          # 36 donnes au plus
                      liste_themes.refresh(); bouton_creer()

                  def basculer(n):
                      niveaux.symmetric_difference_update({n})
                      if not niveaux: niveaux.add(n)
                      ecrire_etat(niveaux=sorted(niveaux)); liste_themes.refresh()

                  def theme_ligne(x):
                      k = quotas[x]
                      with ui.row().classes("w-full items-center justify-between no-wrap"):
                          ui.label(x).classes("text-base" + (" font-bold text-primary" if k else ""))
                          with ui.row().classes("items-center no-wrap gap-0"):
                              ui.button(icon="remove", on_click=lambda x=x: changer(x, -1)).props("flat round dense").set_enabled(k > 0)
                              ui.label(str(k)).classes("w-7 text-center text-base" + (" font-bold" if k else " text-gray-400"))
                              ui.button(icon="add", on_click=lambda x=x: changer(x, 1)).props("flat round dense")

                  @ui.refreshable
                  def liste_themes():
                      with ui.row().classes("gap-2 mt-2"):            # les niveaux montrés
                          for n, nom in donnes.NIVEAUX.items():
                              ui.button(nom, on_click=lambda n=n: basculer(n)) \
                                  .props(("unelevated" if n in niveaux else "outline") + " dense no-caps rounded").classes("px-3")
                      with ui.row().classes("w-full no-wrap items-start gap-4 mt-2"):
                          for f, titre in donnes.FAMILLES.items():
                              with ui.column().classes("gap-0 grow basis-0 p-3").style(
                                      "background:#fff;border:1px solid #e3e7ea;border-radius:10px"):
                                  ui.label(titre).classes("text-base font-bold mb-1")
                                  caches = []
                                  for n, nom in donnes.NIVEAUX.items():
                                      ts = donnes.themes_de(f, n)
                                      vus = ts if n in niveaux else [t for t in ts if quotas[t]]   # un thème choisi reste visible
                                      if n not in niveaux and len(vus) < len(ts):
                                          m = len(ts) - len(vus)
                                          caches.append(f"{m} " + {1: "de 1re année", 2: "intermédiaire" + "s" * (m > 1),
                                                                   3: "avancé" + "s" * (m > 1)}[n])
                                      if not vus: continue
                                      ui.label(nom).classes("text-base text-gray-700 mt-2")
                                      for t in vus: theme_ligne(t)
                                  if caches: ui.label("Autres thèmes : " + ", ".join(caches)).classes("text-base text-gray-600 mt-2")
                      with ui.row().classes("w-full items-center justify-between no-wrap mt-2").style("max-width:50%"):
                          ui.label("Donnes au hasard").classes("text-base")
                          with ui.row().classes("items-center no-wrap gap-0"):
                              k = quotas[donnes.ALEATOIRE]
                              ui.button(icon="remove", on_click=lambda: changer(donnes.ALEATOIRE, -1)).props("flat round dense").set_enabled(k > 0)
                              ui.label(str(k)).classes("w-7 text-center text-base" + (" font-bold" if k else " text-gray-400"))
                              ui.button(icon="add", on_click=lambda: changer(donnes.ALEATOIRE, 1)).props("flat round dense")
                      choisis = donnes.combiner([(t, k) for t, k in quotas.items() if k])
                      n = total()
                      resume = " ; ".join(f"{t} {k}" for t, k in choisis)
                      ui.label(f"{n} donne{'s' if n > 1 else ''} : {resume}" if n else "Aucun thème choisi : la séance sera vide.") \
                          .classes("text-base mt-3 pt-2 w-full").style("border-top:1px solid #e3e7ea")
                  liste_themes()

                  def bouton_creer():
                      n = total()
                      creer_d.text = f"Créer {n} donne{'s' if n > 1 else ''}" if n else "Créer une séance vide"
                      creer_d.set_enabled(not (T.actif or D.actif or I.actif))

                  with ui.column().classes("w-full gap-4"):
                      creer_d = ui.button("Créer une séance vide", icon="add", on_click=lambda: demarrer_donnes() if total() else creer_vide()) \
                          .props("unelevated").classes("text-base self-start")
                      barre_d = ui.linear_progress(value=0, show_value=False).props("size=16px rounded")
                      texte_d = ui.label("").classes("text-base")
                      stop_d = ui.button("Annuler", on_click=lambda: annuler(D)).props("outline")
                      faute_d = ui.label("").classes("text-base text-red-800")

                      @ui.refreshable
                      def fichier_cree():
                          if not D.fichier or D.actif: return
                          ui.label("Donnes créées").classes("text-base font-bold")
                          ui.label(os.path.basename(D.fichier)).classes("text-base text-gray-700 break-all")
                          if D.notes:
                              ui.label("Tirées au hasard faute de temps : " + " ; ".join(D.notes) + ".").classes("text-base text-red-800")
                          with ui.row().classes("gap-3"):
                              ui.button("Analyser ces donnes", on_click=lambda: analyser_donnes())
                              ui.button("Ouvrir le dossier", on_click=lambda: ouvrir(os.path.dirname(D.fichier))).props("outline")
                          ui.label("Le fichier .pbn du dossier s'importe dans Bridgemate : Fichier, Importer.").classes("text-base text-gray-700")
                      fichier_cree()

    with panneau_fichier, ui.column().classes("w-full gap-2") as pages_ui["ouvrir"]:   # Fichier, Ouvrir une séance
        titre_page("Ouvrir une séance", "retrouver")
        faute_o = {"texte": ""}
        @ui.refreshable
        def liste():
            tout = seances_bc()
            if not tout: ui.label("Aucune séance pour l'instant : Fichier, Nouveau").classes("text-base text-gray-700")
            rappel = rappel_sauvegarde(len(tout))
            if rappel:                                     # une sauvegarde vieille d'un mois, ou jamais faite
                with ui.row().classes("w-full items-center justify-between no-wrap gap-3 px-3 py-2 mb-2") \
                        .style("background:#fff8e1;border-left:4px solid #e0a800;border-radius:6px"):
                    ui.label(rappel).classes("text-base")
                    ui.button("Sauvegarder", icon="save", on_click=lambda: (onglets.set_value(o_reglages), voir_page("Réglages", "sauvegarde"))) \
                        .props("outline").classes("shrink-0")
            mois = {}                                      # toutes les séances, par mois de la séance, le plus récent d'abord
            for c in tout:
                j, m, a_ = (infos_seance(c)[0].split("/") + ["", "", ""])[:3]
                mois.setdefault((a_, m), []).append(c)
            ouverte = os.path.abspath(choix["chemin"]) if choix["chemin"] else None
            ouvert = next((k for k, cs in mois.items() if ouverte in map(os.path.abspath, cs)), next(iter(mois), None))
            annee = None
            for (a_, m), cs in mois.items():
                if a_ != annee and len({k[0] for k in mois}) > 1:   # plusieurs années : l'année en tête de ses mois
                    annee = a_; ui.label(a_).classes("text-base font-bold text-gray-700 mt-2")
                nom_mois = (fichiers.MOIS[int(m) - 1].capitalize() + " " + a_) if m.isdigit() else "Sans date"
                with ui.expansion(f"{nom_mois} · {len(cs)} séance{'s' if len(cs) > 1 else ''}", value=(a_, m) == ouvert) \
                        .classes("w-full text-base").props("dense header-class='text-base font-bold'"):
                    for c in cs:                           # le titre, la date et d'où elle vient ; le nom du fichier en petit
                        date, source = infos_seance(c)
                        est = ouverte == os.path.abspath(c)
                        with ui.button(on_click=lambda c=c: choisir(c)).props("flat align=left no-caps").classes("w-full"):
                            with ui.column().classes("gap-0 items-start text-left"):
                                ui.label(fichiers.titre_de(c) + ("  · ouverte" if est else "")).classes("text-base font-bold")
                                ui.label(f"{date}  ·  {source + '  ·  ' if source else ''}{os.path.basename(c)}").classes("text-sm text-gray-600 break-all")
            jetees = fichiers.dans_la_corbeille()
            if jetees:                                     # la corbeille, repliée : on en remet une d'un clic
                with ui.expansion(f"Corbeille · {len(jetees)} séance{'s' if len(jetees) > 1 else ''}", icon="delete") \
                        .classes("w-full text-base mt-3").props("dense header-class='text-base text-gray-700'"):
                    ui.label("Rien n'y est effacé. « Remettre » replace la séance avec ses rapports et ses parties jouées.") \
                        .classes("text-base text-gray-700")
                    for d_, titre_, date_, quand_ in jetees:
                        with ui.row().classes("w-full items-center justify-between no-wrap gap-3 py-1"):
                            with ui.column().classes("gap-0"):
                                ui.label(titre_).classes("text-base font-bold")
                                ui.label(f"Séance du {date_} · mise à la corbeille le {quand_}").classes("text-sm text-gray-600")
                            ui.button("Remettre", icon="restore_from_trash", on_click=lambda d_=d_: remettre_(d_)).props("outline").classes("shrink-0")
                    ui.button("Ouvrir la corbeille", icon="folder_open", on_click=lambda: ouvrir(fichiers.corbeille_dossier())).props("flat")
            if faute_o["texte"]: ui.label(faute_o["texte"]).classes("text-base text-red-800")
        liste()
        ui.label("Ou une séance Bridge Coach (.bc.json) ailleurs sur l'ordinateur :").classes("text-base mt-2")
        envoi = ui.upload(on_upload=lambda e: recu(e), auto_upload=True, max_files=1).props('accept=".json"').classes("hidden")
        ui.button("Choisir un fichier…", on_click=lambda: parcourir()).props("outline")

    with pages_ui["nouveau"], ui.column().classes("w-full gap-2") as sections_n["bws"]:   # Nouveau, depuis un tournoi Bridgemate
        ui.html("Bridge Coach <b>importe</b> les données du tournoi (donnes, joueurs, enchères, résultats) dans une "
                "nouvelle séance <b>.bc.json</b>, sous un titre et un nom que vous choisissez. Le fichier .bws est seulement lu : "
                "Bridge Coach n'y écrit jamais, et la séance n'en a plus besoin ensuite.", sanitize=False).classes("text-base text-gray-700")
        ui.label("Les tournois du dossier de Bridgemate, les plus récents d'abord :").classes("text-base mt-1")
        @ui.refreshable
        def liste_i():
            bws = reglages()[0][:10]
            if not bws: ui.label(f"Aucun fichier .bws dans {dossier}.").classes("text-base text-gray-700")
            for b in bws:
                fait = " (déjà importé)" if deja_importe(b) else ""
                ui.button(f"{date_lisible(b)}  –  {os.path.basename(b)}{fait}", on_click=lambda b=b: preparer_import(b)) \
                    .props("flat align=left no-caps").classes("w-full")
        liste_i()
        ui.label("Ou un tournoi ailleurs sur l'ordinateur : un .bws, ou la feuille de route .pdf de FFBClubNet "
                 "(les mains et les résultats, sans les enchères).").classes("text-base mt-2")
        envoi_i = ui.upload(on_upload=lambda e: recu_i(e), auto_upload=True, max_files=1).props('accept=".bws,.pdf"').classes("hidden")
        ui.button("Choisir un fichier…", icon="folder_open", on_click=lambda: parcourir_i(TYPES_BWS, envoi_i)).props("outline").classes("self-start")

    with pages_ui["nouveau"], ui.column().classes("w-full gap-2") as sections_n["pbn"]:   # Nouveau, depuis un fichier PBN
        ui.html("Un fichier .pbn (Portable Bridge Notation) : les donnes d'un tournoi, de BBO, de Funbridge ou d'un autre "
                "logiciel. Bridge Coach <b>importe</b> les mains, le donneur et la vulnérabilité, et, quand le fichier les donne, "
                "le contrat, les enchères, l'entame et le résultat d'une table, dans une nouvelle séance <b>.bc.json</b>. Le "
                "fichier .pbn est seulement lu : Bridge Coach n'y écrit jamais, et la séance n'en a plus besoin ensuite.",
                sanitize=False).classes("text-base text-gray-700")
        envoi_p = ui.upload(on_upload=lambda e: recu_i(e), auto_upload=True, max_files=1).props('accept=".pbn"').classes("hidden")
        ui.button("Choisir un fichier .pbn…", icon="folder_open", on_click=lambda: parcourir_i(TYPES_PBN, envoi_p)).props("unelevated").classes("self-start")
    for x, col in sections_n.items(): col.set_visibility(x == facon["k"])

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

    with ui.dialog() as remettre_fiche_d, ui.card().classes("w-full max-w-md"):
        ui.label("Remettre toutes les lignes de la fiche comme les joue Bridge Coach ? Vos changements sont effacés ; les noms "
                 "des joueurs et vos accords particuliers restent.").classes("text-base")
        with ui.row().classes("gap-3 justify-end w-full"):
            ui.button("Annuler", on_click=lambda: remettre_fiche_d.close()).props("flat")
            ui.button("Tout remettre", icon="restart_alt", on_click=lambda: remettre_fiche()).props("color=red")

    with ui.dialog() as qui_d, ui.card().classes("w-full max-w-md gap-3"):   # après le premier import : qui êtes-vous ?
        @ui.refreshable
        def fenetre_qui():
            ui.label("Qui utilise Bridge Coach ?").classes("text-lg font-bold")
            ui.label("Si vous le voulez, choisissez votre nom parmi les joueurs de ce tournoi : vos tables seront surlignées "
                     "partout, et les rapports faits pour votre paire. C'est facultatif : sans nom, vous restez « inconnu ». "
                     "Vous pourrez le changer dans Réglages, Votre nom.").classes("text-base text-gray-700")
            ui.select({n: n for n in qui_["noms"]}, with_input=True, label="Votre nom",
                      on_change=lambda e: qui_.update(choix=e.value)).classes("w-full").props("outlined")
            with ui.row().classes("w-full justify-end gap-3"):
                ui.button("Rester inconnu", on_click=lambda: qui_d.close()).props("flat")
                ui.button("C'est moi", icon="check", on_click=lambda: c_est_moi()).props("unelevated")
        fenetre_qui()

    with ui.dialog() as question_d, ui.card().classes("w-full max-w-lg gap-3"):   # « Demander à l'expert » : trois gestes
        @ui.refreshable
        def fenetre_question():
            f_ = question["f"]
            if not f_: return
            ui.label("Demander à l'expert").classes("text-lg font-bold")
            ui.label("Bridge Coach a préparé la donne pour l'expert. Trois gestes :").classes("text-base")
            etape_ = lambda k, t: ui.html(f"<div style='font-size:16px'><b>{k}.</b> {t}</div>", sanitize=False)
            etape_(1, f"Ouvrez l'expert ({html_.escape(nom_outil(url_expert()))}) dans votre navigateur.")
            ui.button("Ouvrir l'expert", icon="open_in_new",
                      on_click=lambda: ouvrir(question_expert.adresse_avec_message(url_expert(), question["message"]))).props("unelevated")
            etape_(2, f"Glissez-y le fichier <b>{html_.escape(os.path.basename(f_))}</b> :")
            ui.button("Montrer le fichier", icon="folder_open", on_click=lambda: montrer_fichier(question["f"])).props("outline")
            etape_(3, "Collez le message (⌘V sur Mac, Ctrl+V sous Windows ; il est déjà copié), puis envoyez. L'expert vous "
                      "salue et vous demande ce que vous voulez savoir.")
            ui.html(f"<div style='font-size:15px;color:#555;background:#f3f3f1;padding:6px 10px;border-radius:6px'>"
                    f"{html_.escape(question['message'])}</div>", sanitize=False)
            with ui.row().classes("w-full justify-end"):
                ui.button("Fermer", on_click=lambda: question_d.close()).props("flat")
        fenetre_question()

    with ui.dialog() as corbeille_d, ui.card().classes("w-full max-w-md"):
        corbeille_texte = ui.label("").classes("text-base")
        with ui.row().classes("gap-3 justify-end w-full"):
            ui.button("Annuler", on_click=lambda: corbeille_d.close()).props("flat")
            ui.button("Mettre à la corbeille", icon="delete", on_click=lambda: mettre_a_la_corbeille()).props("color=red")

    envoi_x = ui.upload(on_upload=lambda e: recu_x(e), auto_upload=True, max_files=1).props('accept=".json"').classes("hidden")

    with panneau_fichier, ui.column().classes("w-full gap-3") as pages_ui["exporter"]:   # Fichier, Exporter…
        titre_page("Exporter la séance", "exporter")
        ui.label("Le fichier exporté est écrit à côté de la séance, dans le dossier de travail. La séance elle-même ne "
                 "change pas.").classes("text-base text-gray-700")
        exporte = {"f": None, "format": lire_etat().get("export_format") or "excel", "quoi": "resultats", "noms": False, "faute": ""}
        @ui.refreshable
        def a_exporter():
            c = choix["chemin"]
            if not c or not c.endswith(rapport.BC):
                ui.label("Aucune séance ouverte : Fichier, Ouvrir une séance.").classes("text-base"); return
            ui.label(f"Séance : {fichiers.titre_de(c)}").classes("text-base font-bold")
            with ui.column().classes("gap-2"):
                for k, nom, sous in exporter.FORMATS:          # le format : trois cartes, comme Nouveau
                    choisi = exporte["format"] == k
                    with ui.row().classes("items-center gap-3 p-3 cursor-pointer no-wrap w-full").style(
                            "border-radius:10px;" + ("background:#eef4fb;border:2px solid #1976d2" if choisi else
                                                     "background:#fff;border:2px solid #e3e7ea")) \
                            .on("click", lambda k=k: (exporte.update(format=k, f=None, faute=""), ecrire_etat(export_format=k), a_exporter.refresh())):
                        ui.icon("radio_button_checked" if choisi else "radio_button_unchecked", size="22px") \
                            .classes("text-primary" if choisi else "text-gray-600")
                        with ui.column().classes("gap-0"):
                            ui.label(nom).classes("text-base font-bold")
                            ui.label(sous).classes("text-base text-gray-700")
            if exporte["format"] == "csv":
                ui.toggle({k: v for k, v in exporter.TABLEAUX}, value=exporte["quoi"],
                          on_change=lambda e: exporte.update(quoi=e.value, f=None)).props("no-caps")
            if exporte["format"] in ("csv", "excel"):
                ui.checkbox("Avec les noms complets des joueurs (sinon les initiales, comme dans les rapports)", value=exporte["noms"],
                            on_change=lambda e: exporte.update(noms=e.value)).classes("text-base")
            ui.button("Exporter", icon="file_download", on_click=lambda: exporter_seance()).props("unelevated").classes("self-start mt-1")
            if exporte["faute"]: ui.label(exporte["faute"]).classes("text-base text-red-800")
            if exporte["f"] and os.path.dirname(exporte["f"]) == os.path.dirname(c):
                ui.label(f"Exporté : {os.path.basename(exporte['f'])}").classes("text-base break-all")
                with ui.row().classes("gap-3"):
                    if not exporte["f"].endswith(".pbn"):
                        ui.button("Ouvrir le fichier", icon="open_in_new", on_click=lambda: ouvrir(exporte["f"])).props("outline")
                    ui.button("Montrer dans le dossier", icon="folder_open", on_click=lambda: montrer_fichier(exporte["f"])).props("outline")
        a_exporter()

    with panneau_fichier, ui.column().classes("w-full gap-3") as pages_ui["infos"]:   # Fichier, Infos
        titre_page("Infos sur la séance", "infos")
        infos_ui = {"copie": False, "faute": "", "fait": ""}
        @ui.refreshable
        def page_infos():
            c = choix["chemin"]
            if not c or not c.endswith(rapport.BC) or not os.path.isfile(c):
                ui.label("Aucune séance ouverte : Fichier, Ouvrir une séance.").classes("text-base"); return
            try:
                data = rapport.lire_bc(c)
            except (OSError, ValueError):
                ui.label("Cette séance ne se lit pas.").classes("text-base text-red-800"); return
            s = data.get("session", {}); src = data.get("source") or {}; f = data.get("fichier") or {}
            lies_ = fichiers.lies(c)
            titre_in = ui.input("Titre", value=s.get("titre") or "").props("outlined").classes("w-full text-base")
            b_titre = ui.button("Enregistrer le titre", icon="check", on_click=lambda: changer_titre_(c, titre_in.value)).props("outline").classes("self-start")
            b_titre.set_enabled(False)
            titre_in.on_value_change(lambda e: b_titre.set_enabled(bool(e.value.strip()) and e.value.strip() != (s.get("titre") or "")))
            prop = fichiers.proposer_pour(c)                # une séance d'avant les titres : titre et nom proposés
            if prop:
                with ui.column().classes("w-full gap-1 p-3").style("border-radius:10px;background:#eef4fb"):
                    ui.label("Ce fichier date d'avant les titres. Bridge Coach propose :").classes("text-base")
                    ui.html(f"le titre <b>{html_.escape(prop[0])}</b><br/>et le nom <b>{html_.escape(prop[1])}.bc.json</b>",
                            sanitize=False).classes("text-base")
                    ui.button("Utiliser ces propositions", icon="auto_fix_high", on_click=lambda: adopter_(c, *prop)).props("unelevated").classes("self-start mt-1")

            def bloc(nom, lignes):
                lignes = [(k, v) for k, v in lignes if v not in (None, "", [])]
                if not lignes: return
                ui.label(nom).classes("text-base font-bold mt-2")
                with ui.grid(columns="170px 1fr").classes("w-full gap-x-4 gap-y-1 text-base"):   # les mêmes colonnes partout
                    for k, v in lignes:
                        ui.label(k).classes("text-gray-700"); ui.label(str(v)).classes("break-all")
            d = fichiers.date_de(data)
            cree = f.get("cree_le") or src.get("importe") or datetime.datetime.fromtimestamp(creation(c)).isoformat(timespec="seconds")
            bloc("Le fichier", [("Nom", os.path.basename(c)), ("Dossier", os.path.dirname(c)), ("Créé le", quand_iso(cree)),
                                ("Avec Bridge Coach", f.get("cree_avec")),
                                ("Modifié le", quand_iso(f.get("modifie_le") or datetime.datetime.fromtimestamp(os.path.getmtime(c)).isoformat(timespec="seconds")))])
            bloc("D'où elle vient", [("Source", SOURCES.get(src.get("type"), src.get("type"))),
                                     ("Fichier d'origine", src.get("fichier") if src.get("type") not in ("entrainement", "saisie") else ""),
                                     ("Il était dans", os.path.dirname(src["chemin"]) if src.get("chemin") else ""),
                                     ("Daté du", quand_iso(src.get("date_fichier"))),
                                     ("Importée le", quand_iso(src.get("importe")) if src.get("type") not in ("entrainement", "saisie") else "")])
            a_finir = sum(1 for x in data.get("donnes", []) if x.get("a_completer"))
            mes = moi.paires(data)
            bloc("La séance", [("Date", fichiers.date_longue(d) if d else s.get("date")), ("Heure", s.get("heure")),
                               ("Tables", s.get("tables") or "aucune : donnes non jouées"),
                               ("Mouvement", "Mitchell" if s.get("mitchell") else "Howell ou tables fixes" if s.get("tables") else ""),
                               ("Marque", moi.MARQUES.get(moi.marque(data))),
                               ("Donnes", f"{len(data.get('donnes', []))}" + (f", dont {a_finir} à compléter" if a_finir else "")),
                               ("Paires", len(data.get("paires") or {}) or ""),
                               ("Thèmes", ", ".join(s.get("themes") or [])),
                               ("Vous êtes", ("dans la paire " + ", ".join(sorted((data.get("paires") or {}).get(k, {}).get("nom") or k for k in mes)))
                                if mes else "")])
            ans = data.get("analyses") or {}
            joues = sum(1 for v in (jouer.lire_essais(base_seance(c)).get("donnes") or {}).values() if v)
            bloc("Le travail fait", [("Analyse du coach", quand_iso((ans.get("standard") or {}).get("fait_le"))),
                                     ("Analyse de l'expert", quand_iso((ans.get("expert") or {}).get("fait_le"))),
                                     ("Rapports PDF", len(lies_["pdf"]) or ""),
                                     ("Donnes rejouées", joues or ""),
                                     ("Versions gardées", len([v for v in lies_["versions"] if v.endswith(rapport.BC)]) or "")])

            ui.label("Le fichier").classes("text-base font-bold mt-3")
            with ui.row().classes("items-start gap-3 w-full no-wrap"):
                nom_in = ui.input("Nom du fichier", value=fichiers.base(c)).props("outlined suffix=.bc.json").classes("grow text-base")
                ui.button("Renommer", icon="drive_file_rename_outline", on_click=lambda: renommer_(c, nom_in.value)).props("outline").classes("mt-2")
            ui.label("Ses rapports, ses parties jouées et ses versions gardées suivent le nouveau nom.").classes("text-base text-gray-700")
            with ui.row().classes("gap-3"):
                ui.button("Dupliquer…", icon="content_copy", on_click=lambda: (infos_ui.update(copie=True), page_infos.refresh())).props("outline")
                ui.button("Montrer dans le dossier", icon="folder_open", on_click=lambda: montrer_fichier(c)).props("outline")
                ui.button("Mettre à la corbeille…", icon="delete", on_click=lambda: demander_corbeille(c)).props("outline color=red")
            if infos_ui["copie"]:
                n0, t0 = fichiers.proposer_copie(c)
                with ui.column().classes("w-full gap-2 p-3").style("border:2px solid #1976d2;border-radius:10px;background:#f7fafd"):
                    ui.label("Une copie de la séance, ses analyses comprises (pas ses parties jouées ni ses rapports) :").classes("text-base")
                    t_in = ui.input("Titre de la copie", value=t0).props("outlined").classes("w-full text-base")
                    n_in = ui.input("Nom du fichier", value=n0).props("outlined suffix=.bc.json").classes("w-full text-base")
                    with ui.row().classes("gap-3"):
                        ui.button("Créer la copie", icon="content_copy", on_click=lambda: dupliquer_(c, n_in.value, t_in.value)).props("unelevated")
                        ui.button("Annuler", on_click=lambda: (infos_ui.update(copie=False), page_infos.refresh())).props("flat")
            if infos_ui["faute"]: ui.label(infos_ui["faute"]).classes("text-base text-red-800")
            if infos_ui["fait"]: ui.label(infos_ui["fait"]).classes("text-base text-primary")
            j = list(reversed(f.get("journal") or []))
            if j:
                ui.label("Son histoire").classes("text-base font-bold mt-3")
                with ui.grid(columns="auto 1fr").classes("gap-x-6 gap-y-1 text-base"):
                    for x in j[:20]:
                        ui.label(quand_iso(x.get("le"))).classes("text-gray-700"); ui.label(x.get("quoi", "")).classes("break-all")
        page_infos()

    with panneau_fichier, ui.column().classes("w-full gap-2") as pages_ui["dossier"]:   # Fichier, Ouvrir le dossier de travail
        titre_page("Le dossier de travail", "fichiers")
        ui.label("Vos séances (seances), vos rapports (rapports) et les fichiers préparés pour Claude (pour-claude). "
                 "Il se change dans Réglages, Dossiers.").classes("text-base text-gray-700")
        ui.label(rapport.DONNEES).classes("text-base break-all")
        ui.button("Ouvrir le dossier de travail", icon="folder_open", on_click=lambda: ouvrir(rapport.DONNEES)).props("outline")
    montrer_pages()

    def montrer_titre():
        t_ = titre_fenetre(choix["chemin"])
        ui.page_title(t_)                                  # l'onglet du navigateur
        if app.native.main_window:                         # la barre de titre de la fenêtre
            try: app.native.main_window.set_title(t_)
            except Exception: pass

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
        choix["chemin"] = c; faute.text = ""
        retenir(c); montrer_titre(); vue["entree"] = "seance"; vue.pop("version", None); expert_msg.update(texte="", faute=False); vue_seance.refresh(); barre_seance.refresh(); montrer_barre(); montrer_controles()
        resultats.refresh(); vue_analyse.refresh()
        if onglets.value not in (o_donnes, o_analyse, o_rapports, "Donnes", "Analyse", "Rapports"): onglets.set_value(o_donnes)

    async def preparer_import(b):
        """Un fichier à importer : Fichier, Nouveau montre le titre et le nom proposés ; rien n'est écrit avant « Importer »."""
        if T.actif or D.actif or I.actif: return
        a_importer.update(chemin=b, prop=None, titre="", nom="", nom_touche=False, lecture=True, faute="")
        onglets.set_value(o_fichier); voir_page("Fichier", "nouveau")
        choisir_facon("pbn" if b.lower().endswith(".pbn") else "bws")
        formulaire_import.refresh()
        try:
            p = await run.io_bound(fichiers.proposer, b)
            a_importer.update(prop=p, titre=p["titre"], nom=p["nom"])
        except SystemExit as ex:
            a_importer["faute"] = str(ex)
        except Exception as ex:
            a_importer["faute"] = (f"{os.path.basename(b)} ne se lit pas : {ex}" if isinstance(ex, ValueError)
                                   else f"{os.path.basename(b)} ne se lit pas comme un tournoi.")
        a_importer["lecture"] = False
        formulaire_import.refresh()

    def fermer_import():
        a_importer.update(chemin=None, prop=None); formulaire_import.refresh()

    def importer(b, nom=None, titre=None):
        if T.actif or D.actif or I.actif: return
        vu_i["fini"] = None; faute_i.text = ""
        fermer_import()
        onglets.set_value(o_donnes)
        lancer_import(b, nom, titre); nouveau.refresh()

    def exporter_seance():
        c = choix["chemin"]
        if not c or not c.endswith(rapport.BC):
            ui.notify("Ouvrez d'abord une séance (Fichier, Ouvrir une séance)."); return
        exporte["faute"] = ""
        try:
            exporte["f"] = exporter.exporter(c, exporte["format"], exporte["quoi"], exporte["noms"])
            fichiers.journal_seance(c, f"Exportée : {os.path.basename(exporte['f'])}")
        except ValueError as ex:
            exporte["f"] = None; exporte["faute"] = str(ex)
        except PermissionError:
            exporte["f"] = None; exporte["faute"] = "Le fichier est ouvert dans un autre programme (Excel ?) : fermez-le, puis recommencez."
        except Exception:
            exporte["f"] = None; exporte["faute"] = "Cette séance ne peut pas être exportée."
        a_exporter.refresh()

    def apres_changement(c, message=""):
        """Après un renommage, une copie ou la corbeille : la séance ouverte, les listes et le titre de la fenêtre suivent."""
        infos_ui.update(copie=False, faute="", fait=message)
        if c: choisir(c)
        else:
            choix["chemin"] = None; retenir(None); montrer_titre(); vue["entree"] = "seance"
            vue_seance.refresh(); barre_seance.refresh(); montrer_barre(); montrer_controles(); resultats.refresh(); vue_analyse.refresh()
        onglets.set_value(o_fichier); voir_page("Fichier", "infos" if c else "ouvrir")

    def changer_titre_(c, titre):
        try:
            fichiers.changer_titre(c, titre)
        except ValueError as ex:
            infos_ui["faute"] = str(ex); page_infos.refresh(); return
        apres_changement(c, "Titre enregistré.")

    def renommer_(c, nom):
        if T.actif or D.actif or I.actif:
            infos_ui["faute"] = "Un calcul est en cours : attendez qu'il se termine."; page_infos.refresh(); return
        try:
            n = fichiers.renommer(c, nom)
        except ValueError as ex:
            infos_ui["faute"] = str(ex); page_infos.refresh(); return
        except OSError:
            infos_ui["faute"] = "Le fichier n'a pas pu être renommé (ouvert dans un autre programme ?)."; page_infos.refresh(); return
        apres_changement(n, f"Renommée : {os.path.basename(n)}")

    def adopter_(c, titre, nom):
        if T.actif or D.actif or I.actif:
            infos_ui["faute"] = "Un calcul est en cours : attendez qu'il se termine."; page_infos.refresh(); return
        try:
            n = fichiers.adopter(c, titre, nom)
        except (ValueError, OSError) as ex:
            infos_ui["faute"] = str(ex) if isinstance(ex, ValueError) else "Le fichier n'a pas pu être renommé."; page_infos.refresh(); return
        apres_changement(n, f"Titre et nom enregistrés : {os.path.basename(n)}")

    def dupliquer_(c, nom, titre):
        try:
            n = fichiers.dupliquer(c, nom, titre)
        except ValueError as ex:
            infos_ui["faute"] = str(ex); page_infos.refresh(); return
        apres_changement(n, "Copie créée : c'est elle qui est ouverte.")

    async def sauvegarder_():
        """Où l'écrire : la fenêtre demande (Documents par défaut) ; dans le navigateur, le dossier sauvegardes du dossier de travail."""
        sauve.update(fait="", faute="")
        nom_ = fichiers.nom_sauvegarde()
        if app.native.main_window:
            r = await app.native.main_window.create_file_dialog(dialog_type=webview_save(), directory=os.path.expanduser("~/Documents"),
                                                                 save_filename=nom_)
            if not r: return
            cible = r if isinstance(r, str) else r[0]
            if not cible.lower().endswith(".zip"): cible += ".zip"
        else:
            os.makedirs(os.path.join(rapport.DONNEES, "sauvegardes"), exist_ok=True)
            cible = os.path.join(rapport.DONNEES, "sauvegardes", nom_)
        try:
            n = await run.io_bound(fichiers.sauvegarder, cible)
        except OSError:
            sauve["faute"] = "La sauvegarde n'a pas pu être écrite à cet endroit : choisissez un autre dossier."
            etat_sauvegarde.refresh(); return
        ecrire_etat(sauvegarde_le=datetime.datetime.now().isoformat(timespec="seconds"), sauvegarde_chemin=cible)
        sauve["fait"] = f"{n} séance{'s' if n > 1 else ''} sauvegardée{'s' if n > 1 else ''} dans {cible}"
        etat_sauvegarde.refresh()

    def remettre_(d_):
        faute_o["texte"] = ""
        try:
            c = fichiers.remettre(d_)
        except (ValueError, OSError) as ex:
            faute_o["texte"] = str(ex) if isinstance(ex, ValueError) else "La séance n'a pas pu être remise."
            liste.refresh(); return
        choisir(c); onglets.set_value(o_fichier); voir_page("Fichier", "ouvrir")
        ui.notify(f"Séance remise : {fichiers.titre_de(c)}")

    def demander_corbeille(c):
        corbeille_texte.text = (f"Mettre « {fichiers.titre_de(c)} » à la corbeille, avec ses rapports, ses parties jouées et ses "
                                "versions gardées ? Rien n'est effacé : tout va dans le dossier corbeille du dossier de travail, "
                                "d'où vous pouvez le remettre.")
        corbeille_d.open()

    def mettre_a_la_corbeille():
        corbeille_d.close(); c = choix["chemin"]
        if not c: return
        if T.actif or D.actif or I.actif:
            infos_ui["faute"] = "Un calcul est en cours : attendez qu'il se termine."; page_infos.refresh(); return
        try:
            dossier_ = fichiers.corbeille(c)
        except OSError:
            infos_ui["faute"] = "La séance n'a pas pu aller à la corbeille (un fichier est ouvert ailleurs ?)."; page_infos.refresh(); return
        apres_changement(None)
        ui.notify(f"Séance mise à la corbeille : {dossier_}", multi_line=True, timeout=8000)

    async def parcourir_i(types, envoi):
        if not app.native.main_window: return envoi.run_method("pickFiles")
        r = await app.native.main_window.create_file_dialog(allow_multiple=False, file_types=types)
        if r: await preparer_import(r[0])

    async def recu_i(e):
        cible = os.path.join(tempfile.mkdtemp(prefix="import-"), os.path.basename(e.file.name))
        await e.file.save(cible)
        await preparer_import(cible)

    async def parcourir():
        """Dans la fenêtre, le dialogue de l'ordinateur : celui d'une page n'y s'ouvre pas. Le navigateur garde le sien."""
        if not app.native.main_window: return envoi.run_method("pickFiles")
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
        lancer_donnes([(t, k) for t, k in quotas.items() if k])
        fichier_cree.refresh()

    def analyser_donnes():
        choisir(D.fichier); onglets.set_value(o_analyse)

    def demarrer():
        if T.actif or D.actif or I.actif or not choix["chemin"]: return
        vu["fini"] = None; faute.text = ""; faute_r.text = ""; fait_a.text = ""
        lancer(choix["chemin"])
        resultats.refresh(); montrer_controles()

    def rafraichir():
        actif_i = I.actif
        barre_i.set_visibility(actif_i); texte_i.set_visibility(actif_i)
        if actif_i: texte_i.text = I.texte
        if I.fini and vu_i["fini"] is not I.proc:          # l'import vient de finir : la séance s'ouvre
            vu_i["fini"] = I.proc
            faute_i.text = "" if I.annule else I.erreur
            if I.fichier and not I.erreur:
                choisir(I.fichier)
                e_ = lire_etat()
                if not e_.get("mon_nom") and not e_.get("qui_demande"): demander_qui(I.fichier)   # une fois : qui êtes-vous ?
            nouveau.refresh()
        actif = T.actif; occupe = actif or actif_i         # un travail à la fois
        analyse_ = actif and T.genre == "analyse"; rapports_ = actif and T.genre == "rapports"
        creer.set_enabled(not occupe and not D.actif and bool(choix["chemin"])); stop.set_visibility(analyse_)
        standard_ = bool(choix["chemin"]) and bool(lire_analyses(choix["chemin"])[0])
        creer_r.set_enabled(not occupe and not D.actif and standard_); stop_r.set_visibility(rapports_)
        besoin_r.text = ("Aucune séance ouverte : Fichier, Ouvrir une séance" if not choix["chemin"] else
                         "" if standard_ else "Lancez d'abord l'analyse, dans l'onglet Analyse.")
        actif_d = D.actif
        creer_d.set_enabled(not occupe and not actif_d); stop_d.set_visibility(actif_d)
        barre_d.set_visibility(actif_d); texte_d.set_visibility(actif_d)
        if actif_d: barre_d.set_value(round(D.fraction, 3)); texte_d.text = D.texte
        if D.fini and vu_d["fini"] is not D.proc:
            vu_d["fini"] = D.proc
            faute_d.text = "" if D.annule else D.erreur
            fichier_cree.refresh()
            if D.fichier and not D.erreur and not D.annule:   # la nouvelle séance s'ouvre, comme une séance vide
                choisir(D.fichier); onglets.set_value(o_donnes)
                if D.notes: ui.notify("Tirées au hasard faute de temps : " + " ; ".join(D.notes) + ".", multi_line=True, timeout=10000)
        barre.set_visibility(analyse_); texte.set_visibility(analyse_)
        barre_r.set_visibility(rapports_); texte_r.set_visibility(rapports_)
        if actif:
            b, t_ = (barre, texte) if analyse_ else (barre_r, texte_r)
            b.set_value(round(T.fraction, 3)); t_.text = f"{T.texte} · {int(T.fraction * 100)} %"
        if T.fini and vu["fini"] is not T.proc:            # le travail vient de finir : une seule fois
            vu["fini"] = T.proc
            erreur = "" if T.annule else T.erreur
            if T.genre == "imprimer":                      # une donne à imprimer : son PDF s'ouvre
                if erreur: ui.notify(erreur, type="negative", multi_line=True)
                elif T.prets and not T.annule: ouvrir(T.prets[-1])
                resultats.refresh(); vue_analyse.refresh(); montrer_controles(); return
            if T.genre == "analyse":
                faute.text = erreur
                fait_a.text = "" if erreur or T.annule else "Analyse faite : lisez-la donne par donne. Les rapports PDF se font dans l'onglet Rapports."
            else:
                faute_r.text = erreur
                if not erreur and not T.annule: voir_page("Rapports", "seance")   # les rapports prêts : leur liste
            resultats.refresh(); vue_analyse.refresh(); montrer_controles()

    ui.on("aide", lambda e: ouvrir_aide(e.args if isinstance(e.args, str) else None))   # les « ? » des titres (titre_page)
    try:                                                   # un tournoi pas encore importé : son import s'ouvre, une fois par fichier
        neuf_bws = next((b for b in reglages()[0] if not deja_importe(b)), None)
    except OSError:
        neuf_bws = None
    if neuf_bws and lire_etat().get("bws_propose") != neuf_bws:
        ecrire_etat(bws_propose=neuf_bws)
        ui.timer(.6, lambda: preparer_import(neuf_bws), once=True)
    e0 = lire_etat()
    if not e0.get("licences_ajoutees"):                    # une fois : les séances d'avant la 1.9 reçoivent les licences
        for c_ in rapport.glob_seances("*" + rapport.BC):
            try: fichiers.ajouter_licences(c_)
            except Exception: pass
        ecrire_etat(licences_ajoutees=True)
    retenir_licence(e0.get("mon_nom"), e0.get("moi"), e0.get("joueur_jouer"))
    vue_v, version_ = lire_etat().get("version_vue"), maj.version_locale()
    if vue_v != version_:                                  # après une mise à jour, une fois : quoi de neuf (help/nouveautes.html)
        ecrire_etat(version_vue=version_)
        neuf = nouveautes(vue_v, version_) if vue_v else []   # (la première installation : rien à montrer)
        if neuf:
            with ui.dialog() as quoi_neuf, ui.card().classes("w-full max-w-lg gap-2"):
                titre_ = f"Quoi de neuf dans Bridge Coach {version_} ?"
                ui.label(titre_).classes("text-lg font-bold")
                for v, h in neuf:
                    if len(neuf) > 1: ui.label(f"Version {v}").classes("text-base font-bold text-gray-700 mt-1")
                    ui.html(h, sanitize=False).classes("aide")
                with ui.row().classes("gap-3 justify-end w-full mt-2"):
                    ui.button("Toutes les nouveautés", icon="history",
                              on_click=lambda: (quoi_neuf.close(), onglets.set_value(o_reglages), voir_page("Réglages", "maj"))).props("flat")
                    ui.button("C'est noté", on_click=lambda: quoi_neuf.close()).props("unelevated")
            ui.timer(1.0, quoi_neuf.open, once=True)
    ui.timer(.4, rafraichir)
    ui.timer(.5, lambda: montrer_titre(), once=True)
    depart = {"Fichier": o_fichier, "Jouer": o_jouer, "Analyse": o_analyse, "Rapports": o_rapports, "Réglages": o_reglages,
              "Aide": o_aide}.get(PAGE.get("onglet"))
    if depart: ui.timer(.05, lambda: onglets.set_value(depart), once=True)   # l'onglet de la dernière fois
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


def precharger():
    """Le système d'enchères (regles.yaml : 2 à 3 secondes à lire) chargé dès l'ouverture, pendant que vous regardez la
    première page : le premier clic sur Jouer n'attend plus."""
    try:
        from encheres import systeme
        systeme()
    except Exception:
        pass                                               # il sera lu au premier besoin, comme avant


def principal():
    fenetre = "--navigateur" not in sys.argv and "--sans-ouvrir" not in sys.argv
    if fenetre:
        try:
            import webview                                 # noqa: F401
        except ImportError:
            fenetre = False
    opts = dict(native=True, window_size=(1200, 850)) if fenetre else dict(show="--sans-ouvrir" not in sys.argv)
    app.on_shutdown(lambda: (annuler(T), annuler(D), annuler(I)))
    app.on_startup(lambda: threading.Thread(target=precharger, daemon=True).start())
    # 127.0.0.1 : seul cet ordinateur joint l'application ; sans fenêtre, NiceGUI ouvrirait sinon le port à tout le réseau
    if os.path.isdir(IMAGES_AIDE): app.add_static_files("/aide-images", IMAGES_AIDE)   # les captures de l'aide
    ui.run(title=TITRE, host="127.0.0.1", port=PORT, reload=False, show_welcome_message=False, favicon="♠", language="fr", **opts)


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    principal()
