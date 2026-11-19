# -*- coding: utf-8 -*-
"""Jouer : la donne en cours, les enchères, la boîte à enchères, le magnétophone.
Les noms de la page (état, fonctions de tous les modules de l'interface) sont dans F (interface.commun) :
fenetre.construire les y range à chaque ouverture de la page."""
from interface.commun import *  # noqa: F401,F403 — les outils communs et F


def siege_de(d, k):
    return jouer.ROT[(jouer.ROT.index(d["donneur"]) + k) % 4]


def jeu_depart(c, d, siege=None, reprendre=True):
    """Ouvre la donne d : là où vous l'aviez laissée (enchères, cartes jouées : jouer.en_cours), sinon au début."""
    x = jouer.en_cours(base_seance(c), d["n"]) if reprendre else None
    if x:
        try:
            return F.jeu_reprendre(c, d, x)
        except Exception:
            pass                                       # un état illisible : la donne repart du début
    if not siege and place_jouer() == "joueur":        # comme un joueur de la séance : sa place à cette donne
        pj = moi.place_du_joueur(lire_seance(c), d, joueur_jouer())
        siege = pj["siege"] if pj else None
    siege = siege or jouer.siege_choisi(place_jouer(), d, lire_analyses(c))   # l'option choisie dans Options
    seq, ex, ind, al = jouer.avancer_alertes(d, [], siege)
    F.jeu.update(cle=(c, d["n"]), siege=siege, seq=seq, ex=ex, indice=ind, alertes=al, voir_indice=False, garde=False, d=d,
               affiche=0, vus=0, revele=False, pense=None, partie=None, pli_vu=None, revoir=None, msg="", garde_jeu=False, sans_jouer=False,
               attend=True)                            # les enchères partent quand vous appuyez sur « Commencer » (magneto)
    F.jeu_garder()


def jeu_commencer():
    """« Commencer » : les enchères du programme apparaissent une à une jusqu'à votre tour."""
    if not F.jeu.get("attend"): return
    F.jeu["attend"] = False; F.jeu_garder(); F.vue_jouer.refresh()   # gardé : en revenant, la donne est commencée
    background_tasks.create(F.reveler())


def jeu_au_debut(c, d):
    """⏮ : pendant le jeu de la carte, d'abord le début du jeu de la carte (les enchères restent) ; une seconde fois,
    ou pendant les enchères, la donne au début, avant les enchères (elles repartent avec ▶). Remplace « Reprendre le
    jeu de la carte » (l'utilisateur, 2026-11-11)."""
    p = F.jeu.get("partie")
    if p:
        joue = sum(len(pli) for pli, _ in p.plis) + len(p.pos.pli)
        depart = len(carte.Partie(d, p.contrat, p.decl, F.jeu["seq"], humain=F.jeu["siege"]).pos.jouees)   # l'entame du programme
        if joue > depart:
            F.carte_demarrer(d); return
    F.jeu_depart(c, d, F.jeu["siege"], reprendre=False); F.vue_jouer.refresh()


def jeu_reculer(c, d):
    """◀ : votre dernière enchère ou votre dernière carte reprise, avec ce que le programme a joué après elle. Au
    début du jeu de la carte : la fin des enchères ; avant votre première enchère : le début de la donne."""
    p, s = F.jeu["partie"], F.jeu["siege"]
    if F.jeu.get("pense") or F.jeu.get("pli_vu") or F.jeu["affiche"] < len(F.jeu["seq"]): return   # le programme réfléchit
    if p:
        cartes = [(cc, r) for pli, _ in p.plis for _x, cc, r in pli] + [(cc, r) for _x, cc, r in p.pos.pli]
        q = carte.Partie(d, p.contrat, p.decl, F.jeu["seq"], humain=s)
        debut = len(q.pos.jouees)                   # l'entame du programme, déjà posée
        miennes = []
        for k, x in enumerate(cartes[debut:], debut):
            if q.au_joueur(): miennes.append(k)
            q.poser(x)
        garde = cartes[:miennes[-1]] if miennes else []
        F.jeu_reprendre(c, d, dict(siege=s, seq=list(F.jeu["seq"]), cartes=[cc + r for cc, r in garde],
                                 pensees=[z for z in p.pensees if z.get("n", 0) < len(garde)]))
        F.jeu["garde_jeu"] = False
        if not F.jeu.get("partie"): F.jeu["depart_auto"] = (c, d["n"], len(F.jeu["seq"]))   # revenu aux enchères : pas de départ seul
    else:
        ks = [k for k in range(len(F.jeu["seq"])) if F.siege_de(d, k) == s]
        if not ks: F.jeu_au_debut(c, d); return
        seq, ex, ind, al = jouer.avancer_alertes(d, F.jeu["seq"][:ks[-1]], s)
        F.jeu.update(seq=seq, ex=ex, indice=ind, alertes=al, voir_indice=False, tout_voir=False, affiche=len(seq), garde=False,
                   sans_jouer=False, attend=False, note="")
    F.jeu_garder(); F.vue_jouer.refresh()


def boutons_pas(debut, recul, avance=None, ok_debut=True, ok_recul=True, ok_avance=True, aide_recul="Un pas en arrière (←)",
                aide_avance="Un pas en avant (→)"):
    """Les mêmes trois boutons dans Jouer, Revoir et Démo (l'utilisateur, 2026-11-18 : un ▶ veut dire « lire tout
    seul », or rien ne joue tout seul ici) : ⏮ au début, ‹ un pas en arrière, › un pas en avant (une carte, une
    enchère). avance None : pas de ›."""
    with ui.row().classes("gap-2 items-center no-wrap"):
        ui.button(icon="skip_previous", on_click=debut).props("outline").tooltip("Au début").set_enabled(ok_debut)
        ui.button(icon="chevron_left", on_click=recul).props("outline").tooltip(aide_recul).set_enabled(ok_recul)
        if avance is not None:
            ui.button(icon="chevron_right", on_click=avance).props("unelevated").tooltip(aide_avance).set_enabled(ok_avance)


def magneto(c, d):
    """En haut de la barre de droite : ⏮ au début de la donne, ‹ reprendre votre dernière enchère ou carte ; une donne
    qui attend a « Commencer les enchères » (elles ne partent pas toutes seules : l'utilisateur, 2026-11-11)."""
    p = F.jeu["partie"]
    occupe = bool(F.jeu.get("pense") or F.jeu.get("pli_vu") or F.jeu["affiche"] < len(F.jeu["seq"]))
    rien = F.jeu.get("attend") and not p
    F.boutons_pas(lambda: F.jeu_au_debut(c, d), lambda: F.jeu_reculer(c, d), ok_debut=not rien and not occupe,
                ok_recul=not rien and not occupe, aide_recul="Reprendre votre dernière enchère ou votre dernière carte")
    if rien:                                       # la donne attend : un vrai bouton, pas un ▶ seul (l'utilisateur, 2026-11-18)
        ui.button("Commencer les enchères", icon="gavel", on_click=F.jeu_commencer).props("unelevated no-caps").classes("w-full")


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
    F.jeu.update(cle=(c, d["n"]), siege=x["siege"], seq=seq, ex=ex, indice=ind, alertes=al, voir_indice=False, garde=ind is None, d=d,
               affiche=len(seq), vus=len(seq), revele=False, pense=None, partie=p, pli_vu=None, revoir=None, msg="", garde_jeu=bool(p and p.fini()),
               sans_jouer=bool(x.get("sans_jouer")), attend=bool(x.get("attend")) and not x.get("cartes"))
    if F.jeu["attend"]: F.jeu["affiche"] = 0            # pas encore commencé : rien sur la table
    if p and not p.fini(): background_tasks.create(F.carte_defense())   # si le programme avait la main


def jeu_garder():
    """Garde la donne en cours telle quelle (jouer.garder_en_cours) : on la retrouve en revenant, même plus tard."""
    if not F.jeu.get("cle"): return
    c, n = F.jeu["cle"]; p = F.jeu.get("partie")
    cartes = [cc + r for pli, _ in p.plis for _x, cc, r in pli] + [cc + r for _x, cc, r in p.pos.pli] if p else []
    try:
        jouer.garder_en_cours(base_seance(c), n, dict(siege=F.jeu["siege"], seq=list(F.jeu["seq"]), cartes=cartes,
                              reclame=bool(p and p.reclame), gagnes=p.pos.gagnes if p else 0, sans_jouer=bool(F.jeu.get("sans_jouer")),
                              pensees=list(p.pensees) if p else [], attend=bool(F.jeu.get("attend") and not p)))
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
    if F.jeu["revele"]: return
    F.jeu["revele"] = True
    try:
        while F.jeu["affiche"] < len(F.jeu["seq"]):
            if F.jeu["seq"][F.jeu["affiche"]] is not None and F.siege_de(F.jeu["d"], F.jeu["affiche"]) == F.jeu["siege"]:
                F.jeu["affiche"] += 1; continue             # la vôtre : tout de suite
            F.jeu["pense"] = F.siege_de(F.jeu["d"], F.jeu["affiche"]); F.vue_jouer.refresh()
            await asyncio.sleep(F.reflexion(F.jeu["ex"], F.jeu["affiche"]))
            F.jeu["affiche"] += 1; F.jeu["pense"] = None; F.vue_jouer.refresh()
    finally:
        F.jeu["revele"] = False


def sens_jouer(jusqu_a=None):
    """{rang: (siège, sens, alertée)} des enchères de la donne en cours, pour grille_html. Pour un joueur dont vous ne
    voyez pas les cartes, seulement ce que l'enchère montre, pas sa main (sens_public ; l'utilisateur, 2026-11-18)."""
    al = set(F.jeu.get("alertes") or [])
    vus = F.sieges_vus()
    return {k: (x, (t_ or "") if x in vus else sens_public(t_ or ""), k in al) for k, (x, b, t_) in enumerate(F.jeu["ex"][:jusqu_a])}


def sieges_vus():
    """Les mains que le joueur voit dans Jouer : la sienne ; le mort une fois l'entame faite ; toutes à la fin."""
    vus = {F.jeu.get("siege") or "S"}
    p = F.jeu.get("partie")
    if p:
        if p.fini(): return set("NESO")
        if p.pos.jouees: vus.update((p.decl, PART_[p.decl]) if F.jeu.get("siege") in (p.decl, PART_[p.decl]) else (PART_[p.decl],))
    return vus


def saut(d, b):
    """L'enchère b saute-t-elle un palier ? (plus haut que le plus bas possible dans sa dénomination)"""
    if not b[:1].isdigit(): return False
    possibles = [int(x[0]) for x in jouer.legales(F.jeu["seq"], d["donneur"]) if x[1:] == b[1:]]
    return bool(possibles) and int(b[0]) > min(possibles)


def avis_enchere(b, k, ex):
    """L'avis du coach quand votre enchère b n'est pas la sienne, ou None : sa propre enchère et ce qu'elle montre, ce
    que la vôtre montrerait, et si la décision était serrée (le texte de sa règle nomme votre enchère)."""
    ind = F.jeu.get("indice") or {}
    sienne = ind.get("enchere")
    if not sienne or sienne == b: return None
    texte = ind.get("texte") or ""
    sens = next((t_ for x, bb, t_ in ex[k:k + 1] if t_), "")
    sens = re.sub(r"^votre enchère\s*:\s*", "", sens)        # « votre enchère : pas d'ouverture » -> « pas d'ouverture »
    nom = lambda e: {"passe": "Passe", "contre": "Contre", "surcontre": "Surcontre"}.get(e, e)
    serree = (any(m in texte for m in ("convenait aussi", "était possible", "Décision serrée"))
              and (nom(b) in texte or b in texte))
    pourquoi = f"Le coach dirait <b>{rouge(nom(sienne))}</b> : {rouge(texte)}"
    votre = f"Votre <b>{rouge(nom(b))}</b>" + (f" montrerait : {rouge(sens)}." if sens else " n'est pas dans le système du coach ici.")
    tete = "Décision serrée : le coach hésitait avec votre enchère." if serree else "Le coach aurait dit autre chose."
    return dict(genre="enchere", mien=b, coach=sienne, serree=serree, tete=tete, lignes=[pourquoi, votre],
                ou=(F.jeu.get("cle"), len(F.jeu["seq"])), nom_mien=nom(b), nom_coach=nom(sienne))


async def jeu_annonce(d, b, force=False, du_coach=False):
    if F.jeu["affiche"] < len(F.jeu["seq"]) or b not in jouer.legales(F.jeu["seq"], d["donneur"]): return
    F.jeu["avis_coach"] = None
    notes = []                                          # l'entraînement à l'alerte et au Stop
    k = len(F.jeu["seq"])
    seq, ex, ind, al = await run.io_bound(jouer.avancer_alertes, d, F.jeu["seq"] + [b], F.jeu["siege"])
    # l'Alerte, comme à la FFB : c'est le partenaire de celui qui fait l'enchère conventionnelle qui alerte. Votre
    # partenaire vient d'en faire une : le carton Alerte d'abord, avant toute enchère, même Passe (l'utilisateur,
    # 2026-11-18 : « le coach doit insister pour que le premier carton posé soit l'Alerte »). Vos propres enchères
    # conventionnelles, c'est le robot votre partenaire qui les alerte.
    kp = k - 2
    a_alerter = kp >= 0 and kp in set(F.jeu.get("alertes") or [])
    if du_coach and a_alerter: F.jeu["alerte"] = True    # « Prendre » l'enchère du coach : il pose l'Alerte pour vous,
    if du_coach and F.saut(d, b): F.jeu["stop"] = True     # et son Stop avant un saut
    if a_alerter and not F.jeu.get("alerte"):
        sens = sens_public(next((t_ for x, bb, t_ in F.jeu["ex"][kp:kp + 1] if t_), ""))
        F.jeu["note"] = (f"Votre partenaire a dit {F.jeu['seq'][kp]}" + (f" ({sens})" if sens else "") +
                       " : une enchère conventionnelle. C'est à vous de l'alerter : posez d'abord le carton Alerte, "
                       "puis votre enchère.")
        F.vue_jouer.refresh(); return
    if not force and coach_arrete():                    # pas l'enchère du coach : il vous arrête et dit pourquoi
        avis = F.avis_enchere(b, k, ex)
        if avis:
            F.jeu["avis_coach"] = avis; F.vue_jouer.refresh(); return
    if F.jeu.get("alerte") and not a_alerter:
        notes.append("L'Alerte est pour une enchère conventionnelle de votre partenaire, et la sienne ne l'était pas : "
                     "pas besoin d'alerter.")
    if F.saut(d, b) and not F.jeu.get("stop"): notes.append(f"{b} est un saut : on pose d'abord le Stop.")
    elif F.jeu.get("stop") and not F.saut(d, b): notes.append("Le Stop annonce un saut ; cette enchère n'en est pas un.")
    F.jeu.update(note=" ".join(notes), stop=False, alerte=False)
    F.jeu.update(seq=seq, ex=ex, indice=ind, alertes=al, voir_indice=False, tout_voir=False, affiche=F.jeu["affiche"] + 1); F.vue_jouer.refresh()
    F.jeu_garder()
    await F.reveler()


def ordre_jouer(data):
    """Les donnes dans l'ordre où les jouer : celui où le joueur choisi les a jouées (Options), sinon par numéro."""
    donnes = data["donnes"]
    if place_jouer() == "joueur" and lire_etat().get("ordre_joueur"):
        donnes = moi.ordre_des_donnes(data, moi.paires(data, joueur_jouer()))
    return [x["n"] for x in donnes if not x.get("a_completer")]


def jeu_suivante(data, d):
    if F.jeu.get("mode") != "jouer":                  # la donne suivante s'ouvre pour être jouée (choisie dans la liste : le mode reste)
        F.jeu["mode"] = "jouer"; ecrire_etat(mode_jouer="jouer")
    ns = F.ordre_jouer(data)
    k = ns.index(d["n"]); F.aller(f"d{ns[(k + 1) % len(ns)]}")


def boite_encheres(d, actif=True):
    """Les enchères encore possibles, à partir du palier le plus bas, quatre paliers au plus ; le dernier bouton,
    « … », montre les autres. Les enchères dépassées ne s'affichent pas. actif=False : pendant que les autres
    enchérissent, la boîte reste là, grisée (l'utilisateur, 2026-11-11 : la barre ne saute pas à chaque tour)."""
    seq_v = F.jeu["seq"][:F.jeu["affiche"]]               # les enchères déjà montrées, pas celles que les robots vont dire
    ok = jouer.legales(seq_v, d["donneur"])          # grisée, la boîte ne se clique pas (.en-attente : pointer-events)
    rang = lambda b: int(b[0]) * 5 + jouer.DENOMS.index(b[1:])
    # comme une vraie boîte (l'utilisateur, 2026-11-11) : votre dernière enchère et tous les cartons en dessous sont
    # sortis (posés sur la table) ; ceux que les enchères des autres ont dépassés restent, en gris pâle
    miennes = [b for k, b in enumerate(seq_v) if F.siege_de(d, k) == F.jeu["siege"] and b and b[:1].isdigit()]
    sortis = rang(miennes[-1]) if miennes else 0
    legaux = sorted({int(b[0]) for b in ok if b[0].isdigit()})
    if not legaux: return
    presents = [n for n in range(1, 8) if any(rang(f"{n}{den}") > sortis for den in jouer.DENOMS)]
    niveaux = [n for n in presents if n >= legaux[0] - 1]   # au plus un palier tout en gris au-dessus des cartons
    tout = F.jeu.get("tout_voir") or len(niveaux) <= 4
    montres = niveaux if tout else niveaux[:4]
    with ui.element("div").classes("boite-encheres" + ("" if actif else " en-attente")):   # une boîte : les cartons debout, derrière
        with ui.element("div").classes("ratelier"):
            for n in montres:
                with ui.row().classes("gap-1 no-wrap"):
                    for den in jouer.DENOMS:                  # ♣ ♦ ♥ ♠ SA : l'ordre des enchères
                        b = f"{n}{den}"
                        if b in ok:
                            ui.html(f"<div class='tirette {F.COUL_BOITE[den]}'>{n}{den}</div>", sanitize=False) \
                                .on("click", lambda b=b: F.jeu_annonce(d, b))
                        elif rang(b) > sortis:              # dépassée par les autres : encore dans la boîte, en gris
                            ui.html(f"<div class='tirette depassee'>{n}{den}</div>", sanitize=False)
                        else:
                            ui.html("<div class='tirette vide'></div>", sanitize=False)
            if not tout:
                ui.html("<div class='tirette autres'>… les autres enchères</div>", sanitize=False) \
                    .on("click", lambda: (F.jeu.update(tout_voir=True), F.vue_jouer.refresh()))
        with ui.column().classes("gap-1 compartiment"):             # devant : Passe, X, XX, chacun avec son onglet
          with ui.row().classes("gap-1 no-wrap justify-center w-full"):
            for b, nom, tab in (("passe", "PASS", "PASS"), ("contre", "X", "X"), ("surcontre", "XX", "XX")):
                el = ui.html(f"<div class='onglet {b}{'' if b in ok else ' eteint'}' data-tab='{tab}'>{nom}</div>", sanitize=False)
                if b in ok: el.on("click", lambda b=b: F.jeu_annonce(d, b))
          # Stop et Alerte : dans la boîte aussi, sur un second rang (l'utilisateur, 2026-11-11) : ce ne sont pas des enchères
          with ui.row().classes("gap-1 no-wrap justify-center w-full"):
            ui.html(f"<div class='onglet stop{' pose' if F.jeu.get('stop') else ''}' data-tab='S' title='Avant un saut'>STOP</div>", sanitize=False) \
                .on("click", lambda: (F.jeu.update(stop=not F.jeu.get("stop")), F.vue_jouer.refresh()))
            # Alerte : posée quand votre partenaire vient de faire une enchère conventionnelle, avant votre enchère
            # (la règle FFB : le partenaire alerte ; l'utilisateur, 2026-11-18)
            ui.html(f"<div class='onglet alerte{' pose' if F.jeu.get('alerte') else ''}' data-tab='A' "
                    "title='Votre partenaire a fait une enchère conventionnelle : alertez avant votre enchère'>ALERT</div>", sanitize=False) \
                .on("click", lambda: (F.jeu.update(alerte=not F.jeu.get("alerte")), F.vue_jouer.refresh()))


NOMS = ("siege_de", "jeu_depart", "jeu_commencer", "jeu_au_debut", "jeu_reculer", "boutons_pas", "magneto", "jeu_reprendre", "jeu_garder", "reflexion", "reveler", "sens_jouer", "sieges_vus", "saut", "avis_enchere", "jeu_annonce", "ordre_jouer", "jeu_suivante", "boite_encheres",)   # rangés dans F par fenetre.construire
