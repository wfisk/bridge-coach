# -*- coding: utf-8 -*-
"""Les captures d'écran de l'aide (help/images/*.png), refaites d'un coup après un changement des écrans.

Un outil de développeur, lancé à la main. Il faut :
  1. un dossier de démonstration, avec des joueurs inventés (jamais vos vraies séances : les images vont sur GitHub) :
       .venv/bin/python -I src/simuler.py --aleatoire 6 <démo>/tournoi-du-club.json 24 2026
       BRIDGE_COACH_DONNEES=<démo> .venv/bin/python -I src/rapport.py <démo>/tournoi-du-club.json --importer "--titre=Tournoi du club (exemple)"
       puis l'analyse (--analyse-seule) et les rapports (--rapports), « Vous êtes » MARTIN Anne dans <démo>/etat.json ;
  2. l'application lancée sur ce dossier, dans le navigateur :
       BRIDGE_COACH_DONNEES=<démo> BRIDGE_COACH_PORT=8125 .venv/bin/python -I -X utf8 src/app.py --navigateur
  3. puis : .venv/bin/python -I -X utf8 src/captures_aide.py <démo> [nom de capture…]

Google Chrome, sans fenêtre (--headless), ouvre chaque page à 1200×850, deux fois plus fin (deviceScaleFactor 2), sur
la page voulue (etat.json « page », comme au lancement), clique ce qu'il faut et enregistre l'image. Le chemin du dossier
de démonstration est remplacé à l'écran par celui d'un utilisateur ordinaire.
"""
import asyncio, json, os, shutil, subprocess, sys, tempfile, time, urllib.request

import websockets

ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(os.path.dirname(ICI), "help", "images")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT_APP = int(os.environ.get("BRIDGE_COACH_PORT") or 8125)
PORT_CDP = 9333
LARGEUR, HAUTEUR = 1200, 850
CHEMIN_AFFICHE = "/Users/vous/Documents/bridge-coach-files"


class Chrome:
    def __init__(self, ws):
        self.ws = ws; self.n = 0

    async def __call__(self, methode, **params):
        self.n += 1; k = self.n
        await self.ws.send(json.dumps({"id": k, "method": methode, "params": params}))
        while True:
            r = json.loads(await self.ws.recv())
            if r.get("id") == k:
                if "error" in r: raise RuntimeError(f"{methode} : {r['error']}")
                return r.get("result", {})

    async def js(self, code):
        r = await self("Runtime.evaluate", expression=code, awaitPromise=True, returnByValue=True)
        return r.get("result", {}).get("value")


CLIQUER = """(function (texte, n) {
  var tous = Array.from(document.querySelectorAll('button, .q-btn, .q-item, .q-expansion-item__container > .q-item, .cursor-pointer, .q-tab, a'))
    .filter(function (e) { return e.offsetParent !== null && (e.innerText || '').trim().indexOf(texte) >= 0; });
  tous.sort(function (a, b) { return (a.innerText || '').length - (b.innerText || '').length; });
  var e = tous[n || 0];
  if (!e) return false;
  e.scrollIntoView({block: 'center'}); e.click(); return true;
})"""


async def cliquer(c, texte, n=0, attente=1.0):
    ok = await c.js(f"{CLIQUER}({json.dumps(texte)}, {n})")
    if not ok: print(f"  (pas trouvé : {texte})")
    await asyncio.sleep(attente)


async def masquer_chemins(c, demo):
    await c.js("""(function (a, b) {
      var w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      while (w.nextNode()) { var t = w.currentNode; if (t.nodeValue.indexOf(a) >= 0) t.nodeValue = t.nodeValue.split(a).join(b); }
    })(%s, %s)""" % (json.dumps(demo), json.dumps(CHEMIN_AFFICHE)))


def ecrire_etat(demo, **valeurs):
    f = os.path.join(demo, "etat.json")
    try: e = json.load(open(f, encoding="utf-8"))
    except Exception: e = {}
    e.update(valeurs)
    json.dump(e, open(f, "w", encoding="utf-8"), ensure_ascii=False)


async def capture(c, nom, clip=None, selecteur=None):
    """clip : (x, y, largeur, hauteur) en pixels de la page ; selecteur : la boîte d'un élément (CSS)."""
    if selecteur:
        r = await c.js(f"(function(){{var e=document.querySelector({json.dumps(selecteur)}); if(!e) return null; "
                       f"var b=e.getBoundingClientRect(); return [b.left+scrollX, b.top+scrollY, b.width, b.height];}})()")
        if r: clip = [max(r[0] - 8, 0), max(r[1] - 8, 0), r[2] + 16, r[3] + 16]
    x, y, l, h = clip or (0, 0, LARGEUR, HAUTEUR)
    r = await c("Page.captureScreenshot", format="png", captureBeyondViewport=True,
                clip={"x": x, "y": y, "width": l, "height": h, "scale": 1})
    import base64
    os.makedirs(SORTIE, exist_ok=True)
    with open(os.path.join(SORTIE, nom + ".png"), "wb") as f: f.write(base64.b64decode(r["data"]))
    print(f"  {nom}.png")


async def ouvrir(c, demo, page, attente=3.0, **etat):
    """La page voulue au chargement : etat.json « page » (onglet, entrée, pages des onglets), puis l'adresse."""
    ecrire_etat(demo, page=page, **etat)
    await c("Page.navigate", url=f"http://127.0.0.1:{PORT_APP}/")
    await asyncio.sleep(attente)
    await masquer_chemins(c, demo)


def seance_demo(demo):
    import glob
    return sorted(glob.glob(os.path.join(demo, "seances", "*", "*tournoi*.bc.json")))[0]


# ---------------------------------------------------------------- les captures
async def c_fenetre(c, demo):
    await ouvrir(c, demo, {"onglet": "Donnes", "entree": "d3"}, seance=seance_demo(demo))
    await capture(c, "fenetre")


async def c_importer(c, demo):
    await ouvrir(c, demo, {"onglet": "Fichier", "fichier": "nouveau", "nouveau": "bws"})
    await cliquer(c, ".bws", attente=2.5)
    await masquer_chemins(c, demo)
    await capture(c, "importer", clip=(0, 0, LARGEUR, 640))


async def c_ouvrir(c, demo):
    await ouvrir(c, demo, {"onglet": "Fichier", "fichier": "ouvrir"}, seance=seance_demo(demo))
    await capture(c, "ouvrir", clip=(0, 0, LARGEUR, 520))


async def c_infos(c, demo):
    await ouvrir(c, demo, {"onglet": "Fichier", "fichier": "infos"}, seance=seance_demo(demo))
    await capture(c, "infos", clip=(0, 0, LARGEUR, 850))


async def c_exporter(c, demo):
    await ouvrir(c, demo, {"onglet": "Fichier", "fichier": "exporter"}, seance=seance_demo(demo))
    await capture(c, "exporter", clip=(0, 0, LARGEUR, 480))


async def c_donne(c, demo):
    await ouvrir(c, demo, {"onglet": "Donnes", "entree": "d5"}, seance=seance_demo(demo))
    await capture(c, "donne", clip=(0, 0, LARGEUR, 850))


async def c_jouer(c, demo):
    await ouvrir(c, demo, {"onglet": "Jouer", "entree": "d2"}, seance=seance_demo(demo), mode_jouer="jouer",
                 place_jouer="declarant", liste_cachee=False, attente=4)
    await capture(c, "jouer-depart")
    await cliquer(c, "play_arrow", attente=9)              # ▶ : les robots enchérissent jusqu'à vous
    await capture(c, "jouer-encheres")


async def c_demo(c, demo):
    await ouvrir(c, demo, {"onglet": "Jouer", "entree": "d4"}, seance=seance_demo(demo), mode_jouer="demo", attente=4)
    for _ in range(9):                                     # les enchères, l'entame et quelques cartes
        await c.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true}))")
        await asyncio.sleep(1.2)
    await capture(c, "demo")
    ecrire_etat(demo, mode_jouer="jouer")


async def c_analyse(c, demo):
    await ouvrir(c, demo, {"onglet": "Analyse", "entree": "d5", "version": "Standard"}, seance=seance_demo(demo))
    await capture(c, "analyse", clip=(0, 0, LARGEUR, 850))
    await ouvrir(c, demo, {"onglet": "Analyse", "entree": "expert"}, seance=seance_demo(demo))
    await capture(c, "expert", clip=(0, 0, LARGEUR, 850))


async def c_rapports(c, demo):
    await ouvrir(c, demo, {"onglet": "Rapports", "rapports": "creer"}, seance=seance_demo(demo))
    await capture(c, "rapports", clip=(0, 0, LARGEUR, 640))


async def c_themes(c, demo):
    await ouvrir(c, demo, {"onglet": "Fichier", "fichier": "nouveau", "nouveau": "themes"})
    await capture(c, "themes", clip=(0, 0, LARGEUR, 850))


async def c_reglages(c, demo):
    await ouvrir(c, demo, {"onglet": "Réglages", "reglages": "affichage"}, seance=seance_demo(demo))
    await capture(c, "taille-texte", clip=(0, 0, LARGEUR, 380))
    await ouvrir(c, demo, {"onglet": "Réglages", "reglages": "contact"}, seance=seance_demo(demo))
    await capture(c, "contact", clip=(0, 0, LARGEUR, 700))
    await ouvrir(c, demo, {"onglet": "Réglages", "reglages": "sauvegarde"}, seance=seance_demo(demo))
    await capture(c, "sauvegarde", clip=(0, 0, LARGEUR, 330))


def c_pdf(demo):
    """La première page du rapport d'analyse (« Vous face au champ »), en image."""
    import glob, pypdfium2
    pdfs = sorted(glob.glob(os.path.join(demo, "rapports", "*", "*-analyse*.pdf")))
    if not pdfs: print("  (pas de rapport : lancez rapport.py --rapports)"); return
    page = pypdfium2.PdfDocument(pdfs[0])[0]
    img = page.render(scale=2).to_pil()
    img.save(os.path.join(SORTIE, "rapport-champ.png"), optimize=True)
    print("  rapport-champ.png")


CAPTURES = {"fenetre": c_fenetre, "importer": c_importer, "ouvrir": c_ouvrir, "infos": c_infos, "exporter": c_exporter,
            "donne": c_donne, "jouer": c_jouer, "demo": c_demo, "analyse": c_analyse, "rapports": c_rapports,
            "themes": c_themes, "reglages": c_reglages}


async def principal(demo, noms):
    profil = tempfile.mkdtemp(prefix="chrome-aide-")
    chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                               "--no-default-browser-check", f"--remote-debugging-port={PORT_CDP}", f"--user-data-dir={profil}",
                               f"--window-size={LARGEUR},{HAUTEUR}", "about:blank"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                cibles = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT_CDP}/json/list")); break
            except OSError:
                time.sleep(.2)
        ws_url = next(t["webSocketDebuggerUrl"] for t in cibles if t["type"] == "page")
        async with websockets.connect(ws_url, max_size=50_000_000) as ws:
            c = Chrome(ws)
            await c("Page.enable"); await c("Runtime.enable")
            await c("Emulation.setDeviceMetricsOverride", width=LARGEUR, height=HAUTEUR, deviceScaleFactor=2, mobile=False)
            for nom in noms or list(CAPTURES):
                if nom == "pdf": continue
                print(nom); await CAPTURES[nom](c, demo)
    finally:
        chrome.terminate(); shutil.rmtree(profil, ignore_errors=True)
    if not noms or "pdf" in noms: c_pdf(demo)


if __name__ == "__main__":
    asyncio.run(principal(os.path.abspath(sys.argv[1]), sys.argv[2:]))
