# -*- coding: utf-8 -*-
"""Un seul appel au solveur double mort (endplay.dds) à la fois dans l'application.

L'application calcule en tâche de fond (la Démo d'avance, l'avis du coach, la revue de Revoir) pendant que la page en
demande d'autres : deux appels au solveur en même temps, depuis deux fils, ont fait planter le serveur (2026-11-18 :
« Sum 8 is not four », puis erreur de segmentation). Importer ce module (app.py le fait) enveloppe chaque fonction
d'endplay.dds dans un même verrou. Les modules du programme importent le solveur au moment de l'appel
(« from endplay.dds import solve_board » dans la fonction) : ils prennent la version enveloppée.
"""
import functools, threading

VERROU = threading.RLock()


def _enveloppe(f):
    @functools.wraps(f)
    def g(*a, **k):
        with VERROU:
            r = f(*a, **k)
            return list(r) if hasattr(r, "__next__") else r   # un générateur : tout lu sous le verrou
    g._verrou = True
    return g


def installer():
    import endplay.dds as dds
    for nom in ("analyse_all_plays", "analyse_all_starts", "analyse_play", "analyse_start", "calc_all_tables",
                "calc_dd_table", "par", "solve_all_boards", "solve_board"):
        f = getattr(dds, nom, None)
        if f is not None and not getattr(f, "_verrou", False):
            setattr(dds, nom, _enveloppe(f))


installer()
