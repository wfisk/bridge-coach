# -*- coding: utf-8 -*-
"""L'application des rapports : une fenêtre, un bouton. Lancement : ./bridge-coach.sh

Elle ne fait que conduire rapport.py, dans un processus à part : l'analyse dure plusieurs minutes,
utilise tous les cœurs et n'a rien à faire dans le serveur de la fenêtre. Sa progression vient des
lignes que rapport.py écrit (« Donne 3 sur 24 », « Rapport prêt : … »).

    --navigateur   ouvre dans le navigateur plutôt que dans une fenêtre
    --sans-ouvrir  ne fait que servir la page (essais)
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__mp_main__" and sys.platform == "darwin":  # la fenêtre : son processus s'appelle Python, le Dock garde Bridge Coach
    try:
        import webview.platforms.cocoa as _cocoa           # elle se déclare au Dock en se chargeant, ensuite on la retire
        _cocoa.BrowserView.app.setActivationPolicy_(1)
    except Exception:                                      # au pire, l'icône Python revient
        pass


from interface.commun import *  # noqa: F401,F403 — les outils communs (les essais y lisent app.x)
from interface import fenetre


@ui.page("/")
def page():
    fenetre.construire()


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
        from encheres import systeme, choisir_systeme
        from regles import systemes
        nom = lire_etat().get("systeme_robots")             # un autre système choisi (prêt : « pret: oui »), sinon le SEF 2024
        if nom and any(n == nom and pret for n, _t, _b, pret in systemes()): choisir_systeme(nom)
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
