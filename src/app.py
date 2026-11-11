# -*- coding: utf-8 -*-
"""L'application des rapports : une fenêtre, un bouton. Lancement : ./bridge-coach.sh

Elle ne fait que conduire rapport.py, dans un processus à part : l'analyse dure plusieurs minutes,
utilise tous les cœurs et n'a rien à faire dans le serveur de la fenêtre. Sa progression vient des
lignes que rapport.py écrit (« Donne 3 sur 24 », « Rapport prêt : … »).

    --navigateur   ouvre dans le navigateur plutôt que dans une fenêtre
    --sans-ouvrir  ne fait que servir la page (essais)
"""
import asyncio, datetime, glob, json, os, re, shutil, signal, subprocess, sys, tempfile, threading, time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import carte, donnes, edition, jouer, maj, moi, rapport
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
            ("comparaison", "Comparaison", "le Coach face à l'Expert"))
TYPES_FICHIERS = ("Tournois (*.bws;*.pdf;*.pbn;*.json)", "Tous les fichiers (*.*)")
TYPES_SEANCES = ("Séances Bridge Coach (*.bc.json;*.json)", "Tous les fichiers (*.*)")
TYPES_BWS = ("Bridgemate ou feuille de route (*.bws;*.pdf)", "Tous les fichiers (*.*)")
TYPES_PBN = ("PBN (*.pbn)", "Tous les fichiers (*.*)")
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
        self.genre = ""                                    # T : "analyse" (onglet Analyse) ou "rapports" (onglet Rapports)

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
    initiales "" sans « Vous êtes »), les plus récentes d'abord."""
    nom = rapport.nom_court(rapport.nom_seance(chemin)); out = {}
    ancien = {"expert": "analyse", "standard": "analyse", "diff": "comparaison"}   # les noms d'avant la 1.4, jusqu'aux rapports refaits
    base = os.path.join(glob.escape(rapport.RAPPORTS), "*", f"*-{glob.escape(nom)}-")
    for quoi in [q for q, _, _ in RAPPORTS] + list(ancien):
        cle = ancien.get(quoi, quoi)
        if cle in out and quoi in ancien: continue
        trouves = [(f, "") for f in glob.glob(base + f"{quoi}.pdf")]
        if quoi == "analyse":
            trouves += [(f, f[:-4].split("-analyse-", 1)[1].replace("-", "/")) for f in glob.glob(base + "analyse-*.pdf")
                        if ".provisoire" not in f]                 # « -analyse-SS-AR.pdf » : la paire SS/AR
        if trouves: out.setdefault(cle, []).extend(sorted(trouves, key=lambda x: -os.path.getmtime(x[0])))
    return out


def date_lisible(chemin):
    d = datetime.date.fromisoformat(rapport.date_du_fichier(chemin))
    return d.strftime("%d/%m/%Y")


GRIS_BARRE = "#f3f3f1"
LARGEUR_PANNEAU = 300                                     # la barre de droite de l'onglet Jouer
# le côté de la table de l'onglet Jouer : ce que laissent la largeur (barres, mains des côtés) et la hauteur (mains du
# haut et du bas), 420px au moins : en dessous, toute la table rétrécit (JS_AJUSTE)
COTE_TABLE = ("clamp(420px, min(100vw / var(--zoom, 1) - var(--reserve-l, 740px), 100vh / var(--zoom, 1) - var(--reserve-h, 420px)), "
              "var(--table-max, 640px))")   # les --reserve : ce que prennent les barres ; « table seule » les libère (app.appliquer_plein)   # --zoom : la taille du texte   # 420 : une main cachée en haut et la vôtre en bas
# pendant le jeu de la carte, avec le mort sur un côté (en défense) : une table rectangulaire, de la même hauteur, plus
# large de la colonne de la main du mort (vide : ses cartes sont sur la table). Les cartes gardent leur taille.
LARGEUR_TABLE_LARGE = f"calc({COTE_TABLE} + 84px)"
HAUTEUR_BARRE = 37                                        # la barre de menus du haut                                    # le gris clair des barres latérales, comme celle de Claude

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
      var e = Math.min(1, parent.clientWidth / w, (window.innerHeight / z - haut - 8) / h);
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
.entree-barre.aide-sujet { height: auto; min-height: 32px; padding-top: 6px; padding-bottom: 6px; flex-shrink: 0; }   /* un sujet sur deux lignes ne déborde pas */
.carte { width: 46px; height: 66px; margin-right: -18px; padding: 3px 5px; background: #fff; border: 1px solid #b9c0c7;
  border-radius: 6px; font-size: 18px; line-height: 1.05; font-weight: 600; color: #1b1b1b; }
.carte.r { color: #c0141c; }
.carte { position: relative; }
.carte .dm { position: absolute; left: -6px; top: -12px; min-width: 26px; padding: 1px 5px;   /* le coin visible, même recouverte
  border-radius: 9px; font-size: 15px; font-weight: 800; color: #fff; text-align: center; line-height: 1.25; z-index: 2;
  box-shadow: 0 0 0 2px #fff; }   /* démonstration, double mort : les levées du déclarant avec cette carte */
.carte .dm.mieux { background: #1f6b45; } .carte .dm.moins { background: #c0141c; }
.carte.jouable { cursor: pointer; border-color: #1f6b45; }
.carte.jouable:hover { transform: translateY(-6px); }
.carte.terne { background: #eceae5; border-color: #cfd3d7; color: #9a9fa5; }   /* pas jouable : terne mais opaque,
   les cartes en dessous ne se voient pas au travers */
.carte.r.terne { color: #d6a3a6; }
.colonne-mort .carte { margin-right: 0; }
.colonne-mort > * + * { margin-top: -42px; }
.mort-table .carte { width: 42px; height: 60px; font-size: 17px; }
.mort-table .colonne-mort > * + * { margin-top: -42px; }
.ligne-mort > :last-child .carte { margin-right: 0; }   /* le mort sur un côté : une ligne par couleur, chevauchée comme une main
   (chaque carte est seule dans son enveloppe : c'est la dernière enveloppe de la ligne qui compte) */
.carte.vide { width: 22px; border: none; background: none; margin-right: 0; padding: 3px 0; }
.eventail .groupe { margin-right: 26px; }
.eventail .groupe:last-child { margin-right: 16px; }
.groupe.colonne .carte { width: 34px; height: 46px; margin-right: -15px; padding: 2px 4px; font-size: 15px; }
.groupe.colonne > :last-child .carte { margin-right: 0; }
.ajuste .carte { position: relative; z-index: 1; }      /* sur la table, les cartes passent au-dessus de l'étui en filigrane */
.groupe.colonne .dix { letter-spacing: -2.5px; }           /* le 10 tient dans la part visible d'une petite carte */  /* sinon la ligne paraît plus courte : à gauche, elle passerait sous la table */
.dos { width: 32px; height: 46px; border-radius: 4px; border: 2px solid #fff; outline: 1px solid #c3cbd4;
  background: repeating-linear-gradient(45deg, #9aa8b8 0 3px, #b0bccA 3px 6px); }
.plis-gardes { display: flex; align-items: center; min-height: 30px; }
.plis-gardes .dos { width: 20px; height: 28px; border-width: 1px; border-radius: 3px; flex: none; }
.plis-gardes .dos.couche { width: 28px; height: 20px; }   /* comme en duplicate : vers le partenaire gagné, en travers perdu */
.plis-gardes .dos + .dos { margin-left: -9px; }           /* chaque carte posée en partie sur la précédente */
.plis-gardes .dos.gagne { background: repeating-linear-gradient(45deg, #2e7d32 0 3px, #5a9e5f 3px 6px); outline-color: #1f5e24; }
.plis-gardes.colonne { flex-direction: column; min-height: 0; min-width: 30px; }
.compte-plis { position: absolute; left: calc(100% + 8px); top: 50%; transform: translateY(-50%); min-width: 24px; height: 24px;
  padding: 0 6px; border-radius: 12px; background: #2e7d32; color: #fff; font-size: 15px; font-weight: 700; line-height: 24px;
  text-align: center; box-sizing: border-box; }   /* hors de la rangée : elle reste centrée */
.plis-gardes.colonne .dos + .dos { margin-left: 0; margin-top: -9px; }
.main-grande .carte { width: 55px; height: 79px; font-size: 20px; margin-right: -22px; }
.main-grande .groupe { margin-right: 30px; }
.main-grande .groupe:last-child { margin-right: 22px; }   /* juste ce que dépasse la dernière carte : le trait s'arrête avec elle */
/* à vous d'enchérir ou de jouer : les cartes à jouer (votre main, ou le mort quand vous en jouez) luisent en jaune */
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
.ratelier { background: #f4f5f6; border-radius: 6px; padding: 6px; display: flex; flex-direction: column; gap: 4px; }
.tirette { width: 46px; height: 30px; display: flex; align-items: center; justify-content: center; border-radius: 4px;
  font-size: 16px; font-weight: 700; border: 1px solid rgba(0,0,0,.18); cursor: pointer; }
.tirette:hover { filter: brightness(.93); transform: translateY(-2px); }
.tirette.vide { visibility: hidden; }
.tirette.autres { width: auto; color: #555; background: #fff; font-weight: 600; font-size: 15px; color: #333; }
.compartiment { margin-top: 8px; background: #a93226; border-radius: 6px; padding: 6px 6px 4px; justify-content: center; }
.onglet { position: relative; min-width: 58px; height: 38px; margin-top: 11px; padding: 0 6px; border-radius: 4px;
  font-size: 16px; font-weight: 700; color: #fff; display: flex; align-items: center; justify-content: center; cursor: pointer; }
.onglet[data-tab]::before { content: ""; position: absolute; top: -9px; right: 3px; height: 10px; min-width: 20px;
  padding: 0 3px; border-radius: 3px 3px 0 0; font-size: 8px; line-height: 12px; background: inherit; color: inherit; }
.a-cote { margin-top: 8px; justify-content: center; }     /* Stop et Alerte : hors de la boîte, ce ne sont pas des enchères */
.a-cote .onglet { height: 38px; min-width: 64px; }
.onglet.passe { background: #2e7d32; } .onglet.contre { background: #e53935; } .onglet.surcontre { background: #1565c0; }
.onglet.eteint { cursor: default; }
.onglet.stop { background: #c62828; } .onglet.stop.pose { outline: 3px solid #f2b705; }
.onglet.alerte { background: #1565c0; animation: pense 1.2s ease-in-out infinite; }
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
"""


def texte_aide():
    """Le corps de help/index.html, affiché dans la fenêtre ; son propre style est remplacé par CSS_AIDE."""
    try:
        t = open(AIDE, encoding="utf-8").read()
    except OSError:
        return "<p>Le fichier d'aide est introuvable.</p>"
    return re.search(r"<body>(.*)</body>", t, re.S)[1] if "<body>" in t else t


def sections_aide():
    """L'aide découpée en sujets : [(catégorie, titre, html)], un par titre <h3>, rangés sous la catégorie (<h2>) qui
    les précède. Sans <h2> ni <h3> (une ancienne aide) : un seul sujet."""
    corps = re.sub(r"<!--.*?-->", "", texte_aide(), flags=re.S)
    out = []
    for bloc in re.split(r"(?=<h2>)", corps):
        m = re.match(r"<h2>(.*?)</h2>", bloc, re.S)
        if not m: continue
        cat = re.sub(r"<[^>]+>", "", m[1]).strip()
        for p in re.split(r"(?=<h3>)", bloc[m.end():]):
            t = re.match(r"\s*<h3>(.*?)</h3>", p, re.S)
            if t: out.append((cat, re.sub(r"<[^>]+>", "", t[1]).strip(), p))
    return out or [("Aide", "Aide", corps)]


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


def lancer_rapports(chemin, noms):
    """Les PDF seulement, depuis les analyses enregistrées (rapport.py --rapports) : la barre avance rapport par rapport."""
    T.__init__(0.0, "Écriture des rapports"); T.genre = "rapports"; T.seance = chemin; T.texte = "Écriture des rapports"
    demarrer_travail(T, [os.path.join(ICI, "rapport.py"), chemin, "--rapports"] + (["--avec-noms"] if noms else [])
                     + ([] if avec_expert() else ["--sans-analyse"]))


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
    ui.label("Joueurs").classes("text-lg font-bold")
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
        lignes = [("État", f"{k} donnes sur {n} ; elle l'emporte sur l'analyse standard, donne par donne" if an
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
        ui.label("« Lancer l'analyse » refait l'analyse standard ; vous la lisez ici, donne par donne. Les rapports PDF "
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
    out = {k: v for k, v in data.items() if k not in ("analyses", "source", "joueurs", "session")}
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
    dossier = os.path.join(rapport.DONNEES, "pour-claude", rapport.nom_seance(c))
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


def grille_html(enc, vul=None, qui=None):
    """Une grille d'enchères Ouest Nord Est Sud (lignes d'une analyse, standard ou expert). vul : la vulnérabilité de
    la donne ; chaque place est alors soulignée d'un trait épais, rouge si vulnérable, vert sinon. qui : "coach" ou
    "expert", l'en-tête au fond de qui recommande ces enchères (build_pdf.AVIS), comme dans le PDF."""
    trait = lambda s: "" if vul is None else \
        f";width:25%;border-bottom:6px solid {'#c0141c' if vul == 'Tous' or vul == ('N-S' if s in 'NS' else 'E-O') else '#2e7d32'}"
    fond = ""
    if qui:                                       # "reco" : vert pâle, les enchères recommandées ; "autre" : gris, celles du coach
        from build_pdf import GRILLE
        fond = f";background:{GRILLE[qui][0]}"
    tete = "".join(f"<th style='padding:2px 10px;text-align:center{trait(s)}{fond}'>{SIEGE[s]}</th>" for s in "ONES")
    corps = "".join("<tr>" + "".join(f"<td style='padding:1px 10px;text-align:center'>{rouge(c)}</td>" for c in r) + "</tr>" for r in enc)
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
               ".q-table th, .q-table td { font-size: 15px !important; padding: 4px 6px !important; } .q-table th { font-weight: 700; }" + CSS_AIDE + CSS_CARTES)
    ui.add_head_html(JS_AJUSTE + JS_GLISSE)
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
            ui.label(f"Analyse standard · séance du {data['session']['date']}").classes("text-lg font-bold")
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
            ui.label("Pas encore d'analyse : « Analyse standard », puis « Lancer l'analyse ».").classes("text-base text-gray-700"); return
        if vue.get("version") not in versions: vue["version"] = "Expert" if "Expert" in versions else versions[0]
        a = (exp if vue["version"] == "Expert" else std)["donnes"][n]
        if vue["version"] == "Expert":                    # le conseil du coach avant l'avis de l'expert (même contrat)
            a = rapport.coach_pour_expert(d, a, (std or {}).get("donnes", {}).get(n))
        repli = (std or {}).get("donnes", {}).get(n, {})   # l'expert reprend du programme ce qu'il n'écrit pas (cartes vues…)
        with ui.column().classes("w-full gap-3").style(f"padding-right:{LARGEUR_PANNEAU}px"):
            page_analyse(d, a, repli, vue["version"], data, c, replis, retenir_page)
        with panneau_droit(d, par=False):
            if len(versions) > 1:                           # Standard | Expert, deux moitiés égales
                ui.toggle(versions, value=vue["version"], on_change=lambda ev: (vue.update(version=ev.value), vue_analyse.refresh(), retenir_page())) \
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
            if d.get("dm"): ui.html(dm_html(d), sanitize=False).classes("w-full")

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
                  f"display:flex;align-items:center;justify-content:center'>{texte}</div>")
        h += ("<div style='position:absolute;left:16px;top:16px;width:28px;height:28px;background:#fff;border-radius:3px;"
              f"display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:800'>{d['n']}</div></div>")
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
        siege = siege or jouer.siege_choisi(place_jouer(), d, lire_analyses(c))   # l'option choisie dans Options
        seq, ex, ind, al = jouer.avancer_alertes(d, [], siege)
        jeu.update(cle=(c, d["n"]), siege=siege, seq=seq, ex=ex, indice=ind, alertes=al, voir_indice=False, garde=False, d=d,
                   affiche=0, vus=0, revele=False, pense=None, partie=None, pli_vu=None, revoir=None, msg="", garde_jeu=False, sans_jouer=False)
        jeu_garder()
        background_tasks.create(reveler())

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
                   sans_jouer=bool(x.get("sans_jouer")))
        if p and not p.fini(): background_tasks.create(carte_defense())   # si le programme avait la main

    def jeu_garder():
        """Garde la donne en cours telle quelle (jouer.garder_en_cours) : on la retrouve en revenant, même plus tard."""
        if not jeu.get("cle"): return
        c, n = jeu["cle"]; p = jeu.get("partie")
        cartes = [cc + r for pli, _ in p.plis for _x, cc, r in pli] + [cc + r for _x, cc, r in p.pos.pli] if p else []
        try:
            jouer.garder_en_cours(base_seance(c), n, dict(siege=jeu["siege"], seq=list(jeu["seq"]), cartes=cartes,
                                  reclame=bool(p and p.reclame), gagnes=p.pos.gagnes if p else 0, sans_jouer=bool(jeu.get("sans_jouer")),
                                  pensees=list(p.pensees) if p else []))
        except OSError:
            pass

    def jeu_recommencer_encheres(c, d):
        jeu_depart(c, d, jeu["siege"], reprendre=False); vue_jouer.refresh()

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

    def alerte_due(d):
        """(rang, enchère, sens) de la dernière enchère du partenaire si elle s'alerte (« alerte: oui » dans regles.yaml :
        4e couleur forcing, Spoutnik, Drury, 2SA bicolore…), sinon None."""
        seq = jeu["seq"]; part = jouer.PART[jeu["siege"]]
        ks = [k for k in range(len(seq)) if siege_de(d, k) == part]
        if not ks or ks[-1] not in (jeu.get("alertes") or []): return None
        k = ks[-1]
        return k, seq[k], next((t_ for x, bb, t_ in jeu["ex"][k:k + 1] if t_), "")

    def saut(d, b):
        """L'enchère b saute-t-elle un palier ? (plus haut que le plus bas possible dans sa dénomination)"""
        if not b[:1].isdigit(): return False
        possibles = [int(x[0]) for x in jouer.legales(jeu["seq"], d["donneur"]) if x[1:] == b[1:]]
        return bool(possibles) and int(b[0]) > min(possibles)

    async def jeu_annonce(d, b):
        if jeu["affiche"] < len(jeu["seq"]) or b not in jouer.legales(jeu["seq"], d["donneur"]): return
        notes = []                                          # l'entraînement à l'alerte et au Stop
        a = alerte_due(d)
        if a and jeu.get("alerte_faite") != a[0]:
            notes.append(f"Votre partenaire a dit {a[1]} : une enchère artificielle, à alerter" + (f" ({a[2]})" if a[2] else "") + ".")
        if saut(d, b) and not jeu.get("stop"): notes.append(f"{b} est un saut : on pose d'abord le Stop.")
        elif jeu.get("stop") and not saut(d, b): notes.append("Le Stop annonce un saut ; cette enchère n'en est pas un.")
        jeu.update(note=" ".join(notes), stop=False)
        seq, ex, ind, al = await run.io_bound(jouer.avancer_alertes, d, jeu["seq"] + [b], jeu["siege"])
        jeu.update(seq=seq, ex=ex, indice=ind, alertes=al, voir_indice=False, tout_voir=False, affiche=jeu["affiche"] + 1); vue_jouer.refresh()
        jeu_garder()
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
            with ui.row().classes("gap-1 no-wrap compartiment"):         # devant : Passe, X, XX, chacun avec son onglet
                for b, nom, tab in (("passe", "PASS", "PASS"), ("contre", "X", "X"), ("surcontre", "XX", "XX")):
                    el = ui.html(f"<div class='onglet {b}{'' if b in ok else ' eteint'}' data-tab='{tab}'>{nom}</div>", sanitize=False)
                    if b in ok: el.on("click", lambda b=b: jeu_annonce(d, b))
        with ui.row().classes("gap-2 no-wrap a-cote"):                 # à côté de la boîte : Stop et Alerte, hors des enchères
            ui.html(f"<div class='onglet stop{' pose' if jeu.get('stop') else ''}' data-tab='S' title='Avant un saut'>STOP</div>", sanitize=False) \
                .on("click", lambda: (jeu.update(stop=not jeu.get("stop")), vue_jouer.refresh()))
            a = alerte_due(d)
            if a and jeu.get("alerte_faite") != a[0]:              # seulement quand l'enchère du partenaire s'alerte
                ui.html("<div class='onglet alerte' data-tab='A' title='Votre partenaire a fait une enchère artificielle'>ALERT</div>", sanitize=False) \
                    .on("click", lambda k=a[0]: (jeu.update(alerte_faite=k), vue_jouer.refresh()))

    # ---------------------------------------------------------------- le jeu de la carte
    def carte_demarrer(d):
        c_, decl = jouer.contrat(jeu["seq"], d["donneur"])
        jeu.update(partie=carte.Partie(d, c_, decl, jeu["seq"], humain=jeu["siege"]), pli_vu=None, revoir=None, msg="", garde_jeu=False, sans_jouer=False)
        jeu_garder(); vue_jouer.refresh(); background_tasks.create(carte_defense())

    async def carte_poser(x):
        """Pose une carte ; si elle termine le pli, le pli reste un instant sous les yeux."""
        p = jeu["partie"]; avant = len(p.plis)
        p.poser(x); jeu["msg"] = ""; jeu_garder()
        if len(p.plis) > avant:
            jeu["pli_vu"] = p.plis[-1]; vue_jouer.refresh()
            await asyncio.sleep(1.3)
            jeu["pli_vu"] = None
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
        if not p or jeu["pense"] or jeu["pli_vu"] or p.fini() or not p.au_joueur() or x not in p.legales(): return
        p.pensees.append(p.pensee(p.au_trait(), x, humain=True))   # votre carte, pour la relecture
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
        if ok: jeu_garder()
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
                f"title='Vert, vers le partenaire : pli gagné ; gris, en travers : pli perdu'>"
                + "".join(f"<div class='dos {forme(g)}{' gagne' if gagne(g) else ''}'></div>" for _, g in p.plis)   # gagné : vert
                + (f"<div class='compte-plis' title='Les levées de votre camp'>{sum(gagne(g) for _, g in p.plis)}</div>"
                   if ou == "bas" else "") + "</div>")      # devant vous : le nombre de levées gagnées, au bout de la rangée

    BORD_PLI = 54          # une carte jouée : sur la table, devant son joueur, au-delà de ses plis gardés (12 + 30 px)
    ICI_PLI = {"haut": f"top:{BORD_PLI}px;left:50%;transform:translateX(-50%)",
               "bas": f"bottom:{BORD_PLI}px;left:50%;transform:translateX(-50%)",
               "gauche": f"left:{BORD_PLI}px;top:50%;transform:translateY(-50%)",
               "droite": f"right:{BORD_PLI}px;top:50%;transform:translateY(-50%)"}

    def carte_posee(c, r, ou=None, ecoule=None):
        """Une carte jouée, comme dans les mains ; ou : le côté d'où elle glisse quand elle vient d'être posée."""
        anim = f" arrive-{ou}" if ou else ""
        retard = f";animation-delay:-{ecoule:.2f}s" if ou else ""
        return f"<div data-c='{c}{r}' class='carte{' r' if c in '♥♦' else ''}{anim}' style='margin:0{retard}'>{face(r)}<br/>{c}</div>"

    def pli_cartes(p, places, posees, derniere=None, ecoule=0, mort=None):
        """Les cartes du pli, chacune sur la table juste devant le joueur qui l'a posée, comme les cartons des enchères ;
        celle du mort (mort : son siège, quand il est étalé sur la table) est dessinée à côté de ses cartes (mort_etale)."""
        haut, gauche, droite, bas = places
        cote = {haut: "haut", gauche: "gauche", droite: "droite", bas: "bas"}
        h = ""
        for x, (c, r) in posees.items():
            if x == mort: continue
            vient = cote[x] if x == derniere else None
            h += f"<div style='position:absolute;{ICI_PLI[cote[x]]};z-index:3'>{carte_posee(c, r, vient, ecoule)}</div>"
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
                f"<div style='position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);z-index:0'>{etui(p.d, places, petit=True, pale=True)}</div>"
                f"{pli_cartes(p, places, posees, derniere, ecoule, mort)}"
                + "".join(plis_gardes(p, x, ou) for x, ou in zip(places, ("haut", "gauche", "droite", "bas"))
                          if x == places[3] or (p.camp(x) != p.camp(places[3]) and x != p.mort())) + "</div>")   # les vôtres, ceux des adversaires (pas du mort : il est étalé)

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
            a = alerte_due(d) if x == jeu["siege"] else None
            if a and jeu.get("alerte_faite") == a[0]:
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

    ORDRE_MAIN = "♠♥♣♦"                                    # noir, rouge, noir, rouge

    face = lambda r: "<span class='dix'>10</span>" if r == "X" else r   # sur une carte à jouer, le dix s'écrit 10 (X dans les textes)

    marques_dm = {}                                       # démonstration : {(couleur, rang fr): (levées, meilleure ?)}

    def carte_el(coul, r, jouables, sur_clic):
        rouge_ = " r" if coul in "♥♦" else ""
        ok = jouables is not None and (coul, r) in jouables
        m = marques_dm.get((coul, r))
        badge = f"<span class='dm {'mieux' if m[1] else 'moins'}'>{m[0]}</span>" if m else ""
        el = ui.html(f"<div data-c='{coul}{r}' class='carte{rouge_}{' jouable' if ok else ' terne' if jouables is not None else ''}'>{face(r)}<br/>{coul}{badge}</div>",
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
                                if r is None: ui.html(f"<div class='carte vide'>{rouge(coul)}</div>", sanitize=False)
                                else: carte_el(coul, r, jouables, sur_clic)
                if cote == "gauche" and posee: ui.html(posee, sanitize=False)
            return
        with ui.column().classes("items-center gap-3"):
            if cote == "bas" and posee: ui.html(posee, sanitize=False)   # le mort en bas (la démonstration) : sa carte vers le centre
            with ui.row().classes("no-wrap items-start gap-3 mort-table" + " a-vous" * a_vous):
                for coul in ordre:
                    with ui.column().classes("gap-0 colonne-mort"):
                        if not cartes.get(coul):
                            ui.html(f"<div class='carte vide'>{rouge(coul)}</div>", sanitize=False)
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
                    ui.html(f"<div class='carte vide'>{rouge(coul)}</div>", sanitize=False); continue
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
        forme = (f"width:{LARGEUR_TABLE_LARGE};height:{COTE_TABLE};" if large else f"width:{COTE_TABLE};aspect-ratio:1 / 1;")
        with ui.element("div").classes("w-full").style("overflow:hidden;padding-top:8px"), \
                ui.element("div").classes("ajuste").style("width:max-content;transform-origin:0 0") \
                    .props(f'data-donne="{d["n"]}-{bas}"'):             # rétrécit avec la fenêtre (JS_AJUSTE) ; JS_GLISSE
            ecoule = time.monotonic() - jeu.get("tourne", -99)   # la table qui tourne : le demi-tour reprend où il en était
            tourne = f"animation:tourne {TOURNE}s ease-in-out;animation-delay:-{ecoule:.2f}s" if ecoule < TOURNE else ""
            with ui.grid(columns="auto auto auto" if large else "1fr auto 1fr").style(tourne) \
                    .classes("items-center gap-x-2 gap-y-4"):            # les mains des côtés contre la table
                with ui.column().classes("items-center").style("grid-column: 1 / 4"):
                    if "haut" not in sur_table: contenu(haut, "haut")
                with ui.column().classes("items-end"):
                    if "gauche" not in sur_table: contenu(gauche, "gauche")
                with ui.column().classes("items-center gap-4").style(       # la table, carrée comme une vraie, à la taille de la fenêtre
                        f"{forme}background:#f3efe7;border:1px solid #e3dccf;border-radius:28px;padding:12px 16px;"
                        "justify-content:space-between;position:relative"):
                    if "haut" in sur_table: contenu(haut, "haut")
                    for ou, x in (("gauche", gauche), ("droite", droite)):   # le mort d'un côté : sur la table, contre son bord
                        if ou in sur_table:
                            with ui.element("div").style(f"position:absolute;{'left' if ou == 'gauche' else 'right'}:14px;"
                                                         "top:50%;transform:translateY(-50%);z-index:2"):
                                contenu(x, ou)
                    if centre: centre()
                    if tour in places:
                        ui.html(f"<div class='fleche-tour {dict(zip(places, ('haut', 'gauche', 'droite', 'bas')))[tour]}'></div>",
                                sanitize=False)
                    if "bas" in sur_table: contenu(bas, "bas")
                with ui.column().classes("items-start"):
                    if "droite" not in sur_table: contenu(droite, "droite")
                with ui.column().classes("items-center").style(
                        "grid-column: 1 / 4" + ("" if "bas" in sur_table else ";margin-top:12px")):
                    if "bas" not in sur_table: contenu(bas, "bas")             # votre main, un peu en retrait de la table

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
                        jouables = {(k, r.translate(carte.FR)) for k, r in p.legales()} if cliquable and tour == x else None
                        clic = lambda y: carte_jouer((y[0], y[1].translate(carte.EN)))
                        if x == p.mort():
                            posees, derniere, ecoule = pli_en_cours(p)
                            cr = posees.get(x)
                            mort_etale(cartes, jouables, clic, p.den, ou,
                                       carte_posee(*cr, ou if x == derniere else None, ecoule) if cr else "",
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

    def tete_donne(d):
        """En haut de la barre de droite de Jouer : la donne, son carré (comme sur le site de la FFB), donneur et
        vulnérabilité, puis le choix Jouer | Démonstration."""
        with ui.row().classes("w-full items-center justify-between no-wrap"):
            ui.label(f"Donne {d['n']}").classes("text-lg font-bold")
            ui.html(carre_donne(d), sanitize=False)
        ui.html(f"<div style='font-size:16px;line-height:1.5'>Donneur : <b>{SIEGE[d['donneur']]}</b><br>"
                f"Vulnérabilité : <b>{VUL_TXT.get(d.get('vul'), d.get('vul', ''))}</b></div>", sanitize=False)
        ui.toggle({"jouer": "Jouer", "demo": "Démonstration"}, value=jeu.get("mode") or "jouer",
                  on_change=lambda ev: (jeu.update(mode=ev.value), ecrire_etat(mode_jouer=ev.value), vue_jouer.refresh())) \
            .props("no-caps unelevated toggle-color=primary color=white text-color=grey-9").classes("text-base")

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

    async def demo_touche(e):
        """Flèches ← → (et Page précédente / suivante d'une télécommande de présentation) dans la démonstration."""
        if not e.action.keydown or jeu.get("mode") != "demo" or not sur_jouer() or not jeu.get("demo"): return
        cle = e.key.name if hasattr(e.key, "name") else str(e.key)
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
        bas = m.decl or "S"                                 # le déclarant en bas, son mort en face, comme dans un livre
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
                outils_table()
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
                    def centre():
                        ui.html(f"<div style='position:absolute;inset:0;pointer-events:none'><div style='position:absolute;left:50%;top:50%;"
                                f"transform:translate(-50%,-50%);z-index:0'>{etui(d, places, petit=True, pale=True)}</div>"
                                f"{pli_cartes(q, places, posees, mort=q.mort())}</div>", sanitize=False)
                    tour = None if q.fini() else q.au_trait()
                    def contenu(x, ou):
                        reste = {kk: "".join(r_.translate(carte.FR) for r_ in vv) for kk, vv in q.pos.reste[x].items()}
                        jx = jouables if x == tour else None
                        if x == q.mort():
                            mort_etale(reste, jx, clic, q.den, ou, carte_posee(*posees[x]) if x in posees else "")
                        else:
                            eventail(reste, jx, clic, colonnes=ou in ("gauche", "droite"), grande=x == bas)
                    table(d, places, contenu, centre,
                          sur_table=[ou for x, ou in zip(places, ("haut", "gauche", "droite", "bas")) if x == q.mort()],
                          tour=tour)
            with panneau_droit():
                appliquer_plein()
                tete_donne(d)
                if not m.decl:
                    ui.label("La donne se passe : rien à montrer au jeu de la carte.").classes("text-base")
                else:
                    src = {"expert": "de l'Expert", "standard": "du Coach", "moteur": "du moteur"}[m.source]
                    ui.html(f"<div style='font-size:16px'><b>{rouge(m.contrat)}</b> par {SIEGE[m.decl]} · enchères {src}</div>",
                            sanitize=False)
                # où l'on en est, et les flèches
                if k == 0: ou_txt = "Avant les enchères"
                elif k <= m.n_encheres: ou_txt = f"Enchère {k} sur {m.n_encheres}"
                else: ou_txt = f"Pli {j // 4 + 1} · carte {j % 4 + 1}"
                ui.label(ou_txt).classes("text-base font-bold")
                fin = m.fini() and k >= m.n_pas()
                with ui.row().classes("gap-2 no-wrap items-center"):
                    ui.button(icon="first_page", on_click=lambda: demo_aller(0)).props("outline").tooltip("Au début").set_enabled(k > 0)
                    ui.button(icon="chevron_left", on_click=lambda: demo_aller(k - 1)).props("outline size=lg") \
                        .tooltip("Reculer (flèche ←)").set_enabled(k > 0 and not jeu.get("demo_occupe"))
                    ui.button(icon="chevron_right", on_click=lambda: demo_aller(k + 1)).props("unelevated size=lg") \
                        .tooltip("Avancer (flèche →)").set_enabled(not fin and not jeu.get("demo_occupe"))
                if jeu.get("demo_msg"): ui.label(jeu["demo_msg"]).classes("text-base pense")
                if m.decl:
                    ui.switch("Double mort", value=bool(jeu.get("demo_dm")),
                              on_change=lambda ev: (jeu.update(demo_dm=ev.value), vue_jouer.refresh())).classes("text-base") \
                        .tooltip("Sous chaque carte jouable : les levées du déclarant au double mort. Un clic l'essaie.")
                # ce que pense le joueur du pas montré
                if 0 < k <= m.n_encheres:
                    e = m.etape(k - 1)
                    ui.html(f"<div style='font-size:16px'><b>{SIEGE[e['siege']]} : {rouge(e['appel'])}</b></div>"
                            + (f"<div style='font-size:16px;margin-top:2px'>{rouge(e['explication'])}</div>" if e["explication"] else ""),
                            sanitize=False)
                    if k == m.n_encheres and m.notes and m.decl:
                        ui.html(f"<div style='font-size:16px;margin-top:6px'><b>L'avis {src} :</b> {rouge(m.notes)}</div>", sanitize=False)
                elif en_jeu:
                    z = m.pensees[j]
                    if z.get("entame"):
                        ui.html(f"<div style='font-size:16px'>{rouge(z['entame'])}</div>", sanitize=False)
                    elif z.get("essai"):
                        ui.html(f"<div style='font-size:16px'><b>{SIEGE[z['siege']]} joue {rouge(z['carte'])}</b> : la carte "
                                "essayée. Les robots reprennent de là.</div>", sanitize=False)
                    else:
                        ui.html(pensee_html(carte.texte_pensee(z, m.decl)), sanitize=False).classes("w-full")
                if voir_dm and marques_dm:
                    qui = SIEGE[q.au_trait()]
                    ui.html(f"<div style='font-size:15px;color:#3f4651'>Double mort : sous chaque carte de {qui}, les levées "
                            f"du déclarant ({m.contrat[0]}{m.contrat[1:]} demande {int(m.contrat[0]) + 6}). En vert la "
                            "meilleure ; un clic sur une carte l'essaie.</div>", sanitize=False)
                if 0 < k:
                    with ui.expansion("Les enchères").props("dense header-class='text-primary text-sm px-1'").classes("w-full"):
                        ui.html(grille_html(jouer.grille(m.seq[:min(k, m.n_encheres)], d["donneur"]), d.get("vul")), sanitize=False)
        marques_dm.clear()

    plein = {"on": False}                                 # Jouer, « table seule » : sans les barres ni les onglets
    ui.keyboard(on_key=demo_touche, ignore=["input", "select", "textarea"])   # la démonstration : ← → au clavier

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

    def pas_taille(k):
        """A− / A+ à côté de la table : la taille du texte d'un cran, la même que dans Réglages."""
        tailles = [t for t, _ in TAILLES]
        i = max(0, min(len(tailles) - 1, tailles.index(taille_texte()) + k))
        changer_taille(tailles[i])

    def outils_table():
        """En haut à droite de la table : la taille du texte (A− A+) et « table seule » (sans les barres)."""
        z = taille_texte(); tailles = [t for t, _ in TAILLES]
        with ui.row().classes("w-full gap-1 no-wrap items-center justify-end").style("margin-bottom:-8px"):   # sa ligne à lui, au-dessus de la table
            ui.button("A−", on_click=lambda: pas_taille(-1)).props("flat dense no-caps color=grey-8") \
                .classes("text-base font-bold").tooltip("Texte plus petit").set_enabled(z > tailles[0])
            ui.button("A+", on_click=lambda: pas_taille(1)).props("flat dense no-caps color=grey-8") \
                .classes("text-lg font-bold").tooltip("Texte plus grand").set_enabled(z < tailles[-1])
            ui.button(icon="fullscreen_exit" if plein["on"] else "fullscreen", on_click=basculer_plein) \
                .props("flat dense round color=grey-8 size=lg") \
                .tooltip("Revenir aux onglets et à la liste des donnes" if plein["on"] else "Table seule : sans les onglets ni la liste des donnes")

    @ui.refreshable
    def vue_jouer():
        c = choix["chemin"]; data = lire_seance(c)
        if not data:
            ui.label("Aucune séance ouverte : Fichier, Ouvrir une séance").classes("text-base"); return
        es = entrees_de(data) if sur_jouer() else []
        if not es: return
        e = entree_effective(data)
        if e == "options":
            ui.label("Options").classes("text-lg font-bold")
            ui.label("La place que vous jouez").classes("text-base font-bold mt-2")
            ui.label("Le déclarant est celui de la séquence recommandée (l'analyse de l'expert, sinon la standard, sinon "
                     "les enchères du programme). Le choix vaut pour toutes les donnes et reste d'une fois sur l'autre.") \
                .classes("text-base text-gray-700 max-w-2xl")
            def changer(ev):
                ecrire_etat(place_jouer=ev.value); jeu["cle"] = None   # les donnes repartent du début, à la nouvelle place
                x = jouer.lire_essais(base_seance(c))
                if x.pop("en_cours", None) is not None:
                    json.dump(x, open(jouer.fichier_jeu(base_seance(c)), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            ui.radio(dict(jouer.PLACES), value=place_jouer(), on_change=changer).classes("text-base")
            ui.label("Quand l'autre camp gagne le contrat, vous jouez la carte en défense : le programme tient le déclarant, "
                     "son mort et votre partenaire.").classes("text-base text-gray-700")
            return
        d = next(x for x in data["donnes"] if f"d{x['n']}" == e)
        if jeu.get("mode") == "demo":                    # la démonstration, pour un cours : une vue à part
            vue_demo(c, d, data); return
        if jeu["cle"] != (c, d["n"]): jeu_depart(c, d)
        s = jeu["siege"]; part = jouer.PART[s]
        p = jeu["partie"]
        # vos cartes toujours en bas ; la table et l'étui tournent avec vous. Vous tenez le déclarant et son mort, et vous
        # avez enchéri de la place du mort : pendant le jeu de la carte, le déclarant passe devant vous (la table tourne)
        bas = p.decl if p and not p.en_defense() and s == p.mort() else s
        vu = jeu.get("bas_vu")                           # (séance, donne, siège du bas) au dessin d'avant
        if vu and vu[:2] == (c, d["n"]) and vu[2] != bas and p and not p.pos.jouees[1:]:
            jeu["tourne"] = time.monotonic()             # le début du jeu de la carte : la table tourne d'un demi-tour
        jeu["bas_vu"] = (c, d["n"], bas); jeu["bas"] = bas
        gauche, droite = jouer.ROT[(jouer.ROT.index(bas) + 1) % 4], jouer.ROT[(jouer.ROT.index(bas) + 3) % 4]
        places = (jouer.PART[bas], gauche, droite, bas)
        attente = jeu["affiche"] < len(jeu["seq"])
        fini = jeu["indice"] is None and not attente
        if p and p.fini() and jeu.get("revoir") is not None:   # la relecture, carte par carte, avec les pensées
            vue_revoir(c, d, data, places, p); return
        c_, decl = jouer.contrat(jeu["seq"], d["donneur"]) if fini else ("passe", None)
        a_jouer = fini and not p and c_ != "passe" and not jeu.get("sans_jouer")   # au déclarant ou en défense
        montrer = (fini and not a_jouer and not p) or (p and p.fini())

        with ui.row().classes("w-full no-wrap items-start gap-4").style(f"padding-right:{LARGEUR_PANNEAU}px"):
            with ui.column().classes("grow min-w-0 gap-2 relative"):     # la table
                outils_table()
                if p:
                    vue_carte(c, d, data, places)
                else:
                    def contenu(x, ou):
                        if x == s or montrer:
                            eventail(mains_fr(d, x), colonnes=ou in ("gauche", "droite"), grande=x == s,
                                     a_vous=x == s and not fini and not attente)
                        else: dos(ou, 13)
                    table(d, places, contenu, lambda: ui.html(tapis_encheres(d, places), sanitize=False),
                          tour=jeu["pense"] if attente else (s if not fini else None))
            with panneau_droit():                                                         # la barre de droite : l'essentiel
                appliquer_plein()
                tete_donne(d)
                ui.label(f"Vous jouez {SIEGE[s]}").classes("text-base text-gray-700")
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
                                    ui.html(f"<div style='font-size:16px'><b>{SIEGE[x]} {rouge(b)}</b> : {rouge(t_)}</div>", sanitize=False)
                if p:
                    vous, defense = p.levees()
                    ui.label(f"{p.contrat} par {SIEGE[p.decl]}").classes("text-base font-bold")
                    if p.en_defense(): ui.label(f"Levées : le déclarant {vous}, vous {defense}").classes("text-base")
                    else: ui.label(f"Levées : vous {vous}, la défense {defense}").classes("text-base")
                    if not p.fini():
                        with ui.row().classes("gap-2"):
                            ui.button("Indice", icon="lightbulb", on_click=lambda: carte_indice()).props("outline dense no-caps")
                            if not p.en_defense():
                                ui.button("Réclamer", icon="done_all", on_click=lambda: carte_reclamer()).props("outline dense no-caps")
                        if jeu["msg"]: ui.label(jeu["msg"]).classes("text-base")
                    robots = [z for z in p.pensees if not z["humain"]]
                    if robots and not p.fini():                 # ce que pense le dernier joueur du programme
                        ui.html(pensee_html(carte.texte_pensee(robots[-1], p.decl)), sanitize=False).classes("w-full")
                    if p.plis:
                        with ui.expansion(f"Plis joués ({len(p.plis)})", icon="list").props("dense").classes("w-full text-base"):
                            for k, (pli, g) in enumerate(p.plis, 1):
                                ui.html(f"<div style='font-size:16px'>Pli {k} : " + " · ".join(f"{SIEGE[x][0]} {rouge(carte.carte_fr(cc, r))}" for x, cc, r in pli)
                                        + f" — {SIEGE[g]}</div>", sanitize=False)
                elif not fini and not attente:
                    boite_encheres(d)
                    ui.button("Masquer l'indice" if jeu["voir_indice"] else "Indice", icon="lightbulb",
                              on_click=lambda: (jeu.update(voir_indice=not jeu["voir_indice"]), vue_jouer.refresh())) \
                        .props(("unelevated" if jeu["voir_indice"] else "outline") + " dense no-caps")   # sous la boîte, juste au-dessus de son texte
                    if jeu["voir_indice"]:
                        ui.html(f"<div style='font-size:15px'>Le système dirait <b>{rouge(jeu['indice']['enchere'])}</b> : "
                                f"{rouge(jeu['indice']['texte'])}</div>", sanitize=False)
                    a = alerte_due(d)
                    if a and jeu.get("alerte_faite") == a[0]:
                        ui.html(f"<div style='font-size:15px'><b>Alerte</b> : {rouge(a[1])} de votre partenaire"
                                + (f" — {rouge(a[2])}" if a[2] else "") + "</div>", sanitize=False)
                    if jeu.get("note"):
                        ui.html(f"<div style='font-size:15px;color:#8a5a00'>{rouge(jeu['note'])}</div>", sanitize=False)
                elif a_jouer:
                    ui.button(f"Jouer {c_} par {SIEGE[decl]}" if jouer.camp(decl) == jouer.camp(s) else f"Défendre contre {c_} par {SIEGE[decl]}",
                              icon="style", on_click=lambda: carte_demarrer(d)).classes("w-full")
                    ui.button("Voir les mains sans jouer", on_click=lambda: (jeu.update(sans_jouer=True), jeu_garder(), vue_jouer.refresh())).props("flat no-caps dense")
                if (p and not p.fini()) or (not p and not fini and any(siege_de(d, k) == s for k in range(len(jeu["seq"])))):   # revenir au début, en cours de route
                    with ui.column().classes("w-full gap-1 mt-3"):
                        if p:
                            ui.button("Reprendre le jeu de la carte", icon="replay", on_click=lambda: carte_demarrer(d)) \
                                .props("flat no-caps dense align=left").classes("text-sm")
                        ui.button("Recommencer les enchères", icon="restart_alt", on_click=lambda: jeu_recommencer_encheres(c, d)) \
                            .props("flat no-caps dense align=left").classes("text-sm")

        if fini and not jeu["garde"]:
            jouer.enregistrer(base_seance(c), d["n"], s, jeu["seq"], d["donneur"]); jeu["garde"] = True; barre_seance.refresh()
        if p:
            if p.fini():
                g, ecart, dm = p.resultat()
                texte = "fait tout juste" if ecart == 0 else f"fait avec {ecart} de mieux" if ecart > 0 else f"chute de {-ecart}"
                ui.html(f"<div style='font-size:16px;margin-top:8px;margin-right:{LARGEUR_PANNEAU}px'><b>{g} levées</b> : {rouge(p.contrat)} {texte}. "
                        f"Au double mort, le contrat donne {dm} levées.</div>", sanitize=False)
                if not jeu["garde_jeu"]:
                    jouer.completer_jeu(base_seance(c), d["n"], [carte.carte_fr(cc, r) for pli, _ in p.plis for _x, cc, r in pli], g)
                    jeu["garde_jeu"] = True
                if jeu.get("resume_de") is not p:            # le résumé écrit, une fois la donne finie
                    try:
                        tout = [(cc, r_) for pli, _ in p.plis for _x, cc, r_ in pli]
                        jeu["resume"] = carte.resume_donne(d, p.contrat, p.decl, p.humain, tout, p.pensees, g)
                    except Exception:
                        jeu["resume"] = []
                    jeu["resume_de"] = p
                if jeu.get("resume"):
                    with ui.element("div").classes("max-w-3xl mt-2").style(
                            f"background:#f6f8fb;border:1px solid #dfe5ea;border-radius:6px;padding:8px 12px;"
                            f"margin-right:{LARGEUR_PANNEAU}px"):
                        ui.label("Résumé de la donne").classes("text-base font-bold")
                        for ligne in jeu["resume"]:
                            ui.html(f"<div style='font-size:15px;margin-top:4px'>{rouge(ligne)}</div>", sanitize=False)
                with ui.row().classes("gap-3 mt-2"):
                    ui.button("Revoir la donne avec les pensées", icon="psychology",
                              on_click=lambda: (jeu.update(revoir=0), vue_jouer.refresh())).props("unelevated")
                    ui.button("Rejouer la carte", icon="replay", on_click=lambda: carte_demarrer(d)).props("outline")
                    ui.button("Recommencer les enchères", icon="restart_alt", on_click=lambda: jeu_recommencer_encheres(c, d)).props("outline")
                    ui.button("Donne suivante", icon="arrow_forward", on_click=lambda: jeu_suivante(data, d))
                mains_grille(d)
                comparaison(c, d, data, s)
            return
        if montrer: comparaison(c, d, data, s)

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
                    f"transform:translate(-50%,-50%);z-index:0'>{etui(d, places, petit=True, pale=True)}</div>{pli_cartes(q, places, posees, mort=q.mort())}</div>",
                    sanitize=False)
        def contenu(x, ou):
            reste = {kk: "".join(r_.translate(carte.FR) for r_ in v) for kk, v in q.pos.reste[x].items()}
            if x == q.mort(): mort_etale(reste, None, None, q.den, ou, carte_posee(*posees[x]) if x in posees else "")
            else: eventail(reste, colonnes=ou in ("gauche", "droite"), grande=x == jeu["siege"])
        with ui.row().classes("w-full no-wrap items-start gap-4").style(f"padding-right:{LARGEUR_PANNEAU}px"):
            with ui.column().classes("grow min-w-0 gap-2"):
                table(d, places, contenu, centre,
                      sur_table=[ou for x, ou in zip(places, ("haut", "gauche", "droite", "bas")) if x == q.mort()])
            with panneau_droit():
                ui.label(f"Donne {d['n']} · relecture").classes("text-lg font-bold")
                ui.label(f"{p.contrat} par {SIEGE[p.decl]} · carte {k + 1} sur {len(cartes)} · pli {k // 4 + 1}").classes("text-base text-gray-700")
                with ui.row().classes("gap-2"):
                    ui.button(icon="chevron_left", on_click=lambda: (jeu.update(revoir=k - 1), vue_jouer.refresh())).props("outline dense").set_enabled(k > 0)
                    ui.button(icon="chevron_right", on_click=lambda: (jeu.update(revoir=k + 1), vue_jouer.refresh())).props("unelevated dense").set_enabled(k < len(cartes) - 1)
                    ui.button("Fermer", on_click=lambda: (jeu.update(revoir=None), vue_jouer.refresh())).props("flat dense no-caps")
                z = next((z for z in p.pensees if z["n"] == k), None)
                if z: ui.html(pensee_html(carte.texte_pensee(z, p.decl)), sanitize=False).classes("w-full")
                if z and z["humain"] and not z.get("avis"):     # votre carte : ce que le programme aurait fait
                    async def avis(z=z):
                        jeu["msg"] = "Le programme réfléchit…"; vue_jouer.refresh()
                        z["avis"] = await run.io_bound(carte.avis_programme, d, p.contrat, p.decl, p.encheres, p.humain, cartes, k)
                        jeu["msg"] = ""; jeu_garder(); vue_jouer.refresh()
                    ui.button("Qu'aurait joué le programme ?", icon="psychology", on_click=avis).props("outline dense no-caps")
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
        if jeu["partie"]: return                         # après le jeu, les boutons sont au-dessus
        with ui.row().classes("gap-3 mt-3"):
            ui.button("Recommencer les enchères", icon="replay", on_click=lambda: jeu_recommencer_encheres(c, d)).props("outline")
            ui.button("Donne suivante", icon="arrow_forward", on_click=lambda: jeu_suivante(data, d))

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
                         ("exporter", "Exporter en PBN"), ("dossier", "Ouvrir le dossier de travail")],
             "Rapports": [("creer", "Créer les rapports"), ("seance", "Rapports de la séance")],   # (le bilan : bilan.py, à la main)
             "Réglages": [("affichage", "Taille du texte"), ("nom", "Votre nom"), ("dossiers", "Dossiers"), ("maj", "Mise à jour du programme")]}     # la barre de gauche de ces onglets
    vue_page = {"Fichier": "nouveau" if PAGE.get("fichier") == "importer" else
                           PAGE.get("fichier") if PAGE.get("fichier") in ("nouveau", "ouvrir", "exporter", "dossier") else "ouvrir",
                "Rapports": PAGE.get("rapports") if PAGE.get("rapports") in ("creer", "seance") else "creer",
                "Réglages": PAGE.get("reglages") if PAGE.get("reglages") in ("affichage", "nom", "dossiers", "maj") else "affichage"}

    facon = {"k": PAGE.get("nouveau") if PAGE.get("nouveau") in ("bws", "pbn", "themes") else   # Fichier, Nouveau : la façon choisie
             ("bws" if PAGE.get("fichier") == "importer" else "themes")}

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

    def rafraichir_fichier():
        """Les pages de Fichier se mettent à jour quand on y vient : les séances, les .bws, la séance à exporter."""
        try: liste.refresh(); liste_i.refresh(); a_exporter.refresh()
        except NameError: pass                             # la page se construit encore

    def voir_aide(k):
        vue_aide["k"] = k; page_aide.refresh(); barre_seance.refresh(); retenir_page()
        ui.run_javascript("window.scrollTo(0, 0)")

    @ui.refreshable
    def page_aide():
        s = sections_aide()
        cat, _, h = s[min(vue_aide["k"], len(s) - 1)]
        ui.label(cat).classes("text-sm text-gray-600 uppercase tracking-wide")   # la catégorie, au-dessus du sujet
        ui.html(h, sanitize=False).classes("aide w-full pb-8")

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
        nom = nom_pour_claude(lire_seance(c))
        ui.label("Obtenir l'analyse de l'expert avec Claude").classes("text-base font-bold mt-4")
        ui.label("L'analyse de l'expert est écrite par Claude (claude.ai, dans votre navigateur). Comptez une "
                 "conversation par séance ; pour 24 donnes, Claude peut répondre en plusieurs fois.").classes("text-base text-gray-700")
        etape = lambda k, texte: ui.html(f"<div style='font-size:16px'><b>{k}.</b> {texte}</div>", sanitize=False)
        with ui.column().classes("gap-3 max-w-2xl"):
            etape(1, "Préparez le fichier : Bridge Coach met dans un seul fichier tout ce dont Claude a besoin (la séance, "
                     "l'analyse standard, le système, un exemple et la consigne), puis ouvre son dossier. Les joueurs n'y "
                     "sont que par leurs initiales : les noms complets ne quittent pas l'ordinateur.")
            ui.button("Préparer le fichier pour Claude", icon="folder_open", on_click=lambda: preparer_expert(c)).props("outline")
            etape(2, "Ouvrez <b>claude.ai</b> dans votre navigateur et commencez une nouvelle conversation.")
            ui.button("Ouvrir claude.ai", icon="open_in_new", on_click=lambda: ouvrir("https://claude.ai/new")).props("outline")
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
        lancer_rapports(choix["chemin"], noms.value)
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
        return es[1][0] if sur_jouer() and len(es) > 1 else es[0][0]     # Jouer : la première donne, pas les options

    def montrer_controles():
        """« Lancer l'analyse » : sur la page Analyse standard, ou partout pendant qu'une analyse tourne."""
        try: controles
        except NameError: return                           # la page se construit encore : l'onglet change avant la barre
        data = lire_seance(choix["chemin"])
        controles.set_visibility(bool(data) and ((T.actif and T.genre == "analyse") or (sur_analyse() and entree_effective(data) == "standard")))

    def aller(k):
        vue["entree"] = k; vue["edition"] = None; barre_seance.refresh(); vue_seance.refresh(); vue_analyse.refresh(); vue_jouer.refresh(); montrer_controles()
        retenir_page()

    @ui.refreshable
    def barre_seance():
        if onglet_a_pages():                              # Rapports, Réglages : une entrée par page
            nom = onglet_a_pages()
            for cle, titre in PAGES[nom]:
                ui.button(titre, on_click=lambda c=cle: voir_page(nom, c)).props("flat no-caps align=left dense color=grey-10") \
                    .classes("entree-barre text-left" + (" choisie" if vue_page[nom] == cle else ""))
            return
        if sur_aide():                                    # l'aide : une entrée par section
            avant = None
            for k, (cat, titre, _) in enumerate(sections_aide()):
                if cat != avant:                              # le titre de la catégorie, puis ses sujets
                    ui.label(cat).classes("text-xs text-gray-600 uppercase tracking-wide font-bold px-2 " +
                                          ("mt-1" if avant is None else "mt-4")).style("letter-spacing:.06em")
                    avant = cat
                ui.button(titre, on_click=lambda k=k: voir_aide(k)).props("flat no-caps align=left dense color=grey-10") \
                    .classes("entree-barre aide-sujet text-left" + (" choisie" if k == vue_aide["k"] else ""))
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
        """La barre latérale : sur les onglets Donnes, Jouer et Analyse quand une séance est ouverte ; toujours sur
        Rapports, Réglages et l'aide."""
        if plein["on"] and sur_jouer(): tiroir.set_value(False); return   # Jouer, table seule
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
            aide = ui.button("Aide", on_click=lambda: onglets.set_value(o_aide)).props("flat no-caps dense").classes("px-3")
            onglets.on_value_change(lambda e: (aide.classes(add="bg-green-50 font-bold") if e.value in (o_aide, "Aide")
                                               else aide.classes(remove="bg-green-50 font-bold"), montrer_barre(), barre_seance.refresh(),
                                               vue_analyse.refresh(), vue_jouer.refresh(), montrer_controles(), retenir_page(),
                                               e.value in (o_fichier, "Fichier") and rafraichir_fichier()))

    with ui.left_drawer(value=False, fixed=True, bordered=True).props(f"width={LARGEUR_BARRE} behavior=desktop") \
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
                            ui.label(os.path.basename(neuf)).classes("text-base text-gray-700 break-all")
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
                    barre = ui.linear_progress(value=0, show_value=False).props("size=16px rounded").classes("max-w-xl")
                    texte = ui.label("").classes("text-base")
                    stop = ui.button("Annuler", on_click=annuler).props("outline")
                    faute = ui.label("").classes("text-base text-red-800")
                    fait_a = ui.label("").classes("text-base text-primary")
                vue_analyse()

            pages_ui = {}
            with ui.tab_panel(o_rapports).classes("px-0 pt-0 gap-4 max-w-xl"):
                with ui.column().classes("w-full gap-2") as pages_ui["creer"]:   # les options, puis « Créer les rapports »
                    ui.label("Créer les rapports").classes("text-lg font-bold")
                    ui.label("Vous êtes").classes("text-base")
                    actuel = moi.nom()

                    def choisir_moi(e):
                        if e.value == SEPARATEUR: e.sender.value = moi.nom() or ""; return   # la ligne de séparation
                        ecrire_etat(moi=e.value or None); vue_seance.refresh()
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
                ui.label("Taille du texte").classes("text-lg font-bold")
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
                ui.label("Votre nom").classes("text-lg font-bold")
                ui.label("Votre nom vient en premier dans le choix d'un joueur (« Vous êtes », dans Rapports), juste après "
                         "« Aucun », puis une ligne, puis les autres joueurs.").classes("text-base text-gray-700")

                def choisir_mon_nom(e):
                    if e.value == SEPARATEUR: e.sender.value = lire_etat().get("mon_nom") or ""; return
                    ecrire_etat(mon_nom=e.value or None)
                    if e.value and not moi.nom(): ecrire_etat(moi=e.value); vue_seance.refresh()   # « Vous êtes » vide : c'est vous
                    choix_moi.set_options(options_joueurs(moi.nom()), value=moi.nom() or "")
                noms_tous = {"": "—"} | {x: x for x in moi.tous_les_noms(rapport.glob_seances("*" + rapport.BC))}
                if lire_etat().get("mon_nom") and lire_etat()["mon_nom"] not in noms_tous: noms_tous[lire_etat()["mon_nom"]] = lire_etat()["mon_nom"]
                ui.select(noms_tous, value=lire_etat().get("mon_nom") or "", with_input=True, on_change=choisir_mon_nom) \
                    .classes("w-full").props("outlined dense")

              with ui.column().classes("w-full gap-5") as pages_ui["dossiers"]:
                ui.label("Dossiers").classes("text-lg font-bold")
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

              with ui.column().classes("w-full gap-3") as pages_ui["maj"]:
                ui.label("Mise à jour du programme").classes("text-lg font-bold")
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

            montrer_pages()                                # chaque onglet à pages s'ouvre sur sa première page

            with ui.tab_panel(o_aide).classes("px-0 pt-0 max-w-xl"):   # une page comme les autres : un onglet la quitte
                page_aide()                                    # une section à la fois, choisie dans la barre de gauche

            with ui.tab_panel(o_fichier).classes("px-0 pt-0 max-w-3xl") as panneau_fichier, \
                    ui.column().classes("w-full gap-0") as pages_ui["nouveau"]:   # Fichier : ses pages, la première Nouveau
                ui.label("Nouvelle séance").classes("text-lg font-bold")
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
        ui.label("Ouvrir une séance").classes("text-lg font-bold")
        @ui.refreshable
        def liste():
            tout = seances_bc()
            if not tout: ui.label("Aucune séance pour l'instant : Fichier, Nouveau").classes("text-base text-gray-700")
            for c in tout[:15]:
                date, source = infos_seance(c)
                ui.button(f"{date}  –  {source + ' – ' if source else ''}{rapport.nom_seance(c)}", on_click=lambda c=c: choisir(c)) \
                    .props("flat align=left no-caps").classes("w-full")
        liste()
        ui.label("Ou une séance Bridge Coach (.bc.json) ailleurs sur l'ordinateur :").classes("text-base mt-2")
        envoi = ui.upload(on_upload=lambda e: recu(e), auto_upload=True, max_files=1).props('accept=".json"').classes("hidden")
        ui.button("Choisir un fichier…", on_click=lambda: parcourir()).props("outline")

    with pages_ui["nouveau"], ui.column().classes("w-full gap-2") as sections_n["bws"]:   # Nouveau, depuis un tournoi Bridgemate
        ui.html("Bridge Coach <b>importe</b> les données du tournoi (donnes, joueurs, enchères, résultats) dans une "
                "nouvelle séance <b>.bc.json</b>. Le fichier .bws est seulement lu : Bridge Coach n'y écrit jamais, et la "
                "séance n'en a plus besoin ensuite (une copie est rangée avec elle).", sanitize=False).classes("text-base text-gray-700")
        ui.label("Les tournois du dossier de Bridgemate, les plus récents d'abord :").classes("text-base mt-1")
        @ui.refreshable
        def liste_i():
            bws = reglages()[0][:10]
            if not bws: ui.label(f"Aucun fichier .bws dans {dossier}.").classes("text-base text-gray-700")
            for b in bws:
                fait = " (déjà importé)" if deja_importe(b) else ""
                ui.button(f"{date_lisible(b)}  –  {os.path.basename(b)}{fait}", on_click=lambda b=b: importer(b)) \
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
                "fichier .pbn est seulement lu : Bridge Coach n'y écrit jamais (une copie est rangée avec la séance).",
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

    envoi_x = ui.upload(on_upload=lambda e: recu_x(e), auto_upload=True, max_files=1).props('accept=".json"').classes("hidden")

    with panneau_fichier, ui.column().classes("w-full gap-2") as pages_ui["exporter"]:   # Fichier, Exporter en PBN
        ui.label("Exporter en PBN").classes("text-lg font-bold")
        ui.label("Le .pbn s'importe dans Bridgemate (Fichier, Importer) et se lit dans la plupart des logiciels de bridge. "
                 "Il est écrit à côté de la séance.").classes("text-base text-gray-700")
        exporte = {"f": None}
        @ui.refreshable
        def a_exporter():
            c = choix["chemin"]
            if not c or not c.endswith(rapport.BC):
                ui.label("Aucune séance ouverte : Fichier, Ouvrir une séance.").classes("text-base"); return
            ui.label(f"Séance : {infos_seance(c)[0]} – {rapport.nom_seance(c)}").classes("text-base")
            ui.button("Exporter en PBN", icon="file_download", on_click=lambda: exporter()).classes("mt-1")
            if exporte["f"] and os.path.dirname(exporte["f"]) == os.path.dirname(c):
                ui.label(f"Exporté : {exporte['f']}").classes("text-base break-all")
                ui.button("Ouvrir le dossier", on_click=lambda: ouvrir(os.path.dirname(exporte["f"]))).props("outline")
        a_exporter()

    with panneau_fichier, ui.column().classes("w-full gap-2") as pages_ui["dossier"]:   # Fichier, Ouvrir le dossier de travail
        ui.label("Le dossier de travail").classes("text-lg font-bold")
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

    def importer(b):
        if T.actif or D.actif or I.actif: return
        vu_i["fini"] = None; faute_i.text = ""
        onglets.set_value(o_donnes)
        lancer_import(b); nouveau.refresh()

    def exporter():
        c = choix["chemin"]
        if not c or not c.endswith(rapport.BC):
            ui.notify("Ouvrez d'abord une séance (Fichier, Ouvrir une séance)."); return
        try:
            f = exporter_pbn(c)
        except Exception:
            ui.notify("Cette séance ne peut pas être exportée."); return
        exporte["f"] = f; a_exporter.refresh()

    async def parcourir_i(types, envoi):
        if not app.native.main_window: return envoi.run_method("pickFiles")
        r = await app.native.main_window.create_file_dialog(allow_multiple=False, file_types=types)
        if r: importer(r[0])

    async def recu_i(e):
        cible = os.path.join(tempfile.mkdtemp(prefix="import-"), os.path.basename(e.file.name))
        await e.file.save(cible)
        importer(cible)

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
            if I.fichier and not I.erreur: choisir(I.fichier)
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
            if T.genre == "analyse":
                faute.text = erreur
                fait_a.text = "" if erreur or T.annule else "Analyse faite : lisez-la donne par donne. Les rapports PDF se font dans l'onglet Rapports."
            else:
                faute_r.text = erreur
                if not erreur and not T.annule: voir_page("Rapports", "seance")   # les rapports prêts : leur liste
            resultats.refresh(); vue_analyse.refresh(); montrer_controles()

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
    ui.run(title=TITRE, host="127.0.0.1", port=PORT, reload=False, show_welcome_message=False, favicon="♠", language="fr", **opts)


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    principal()
