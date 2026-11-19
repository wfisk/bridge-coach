# -*- coding: utf-8 -*-
"""La table dessinée : les plis, l'étui, les cartons d'enchères, les mains, le mort.
Les noms de la page (état, fonctions de tous les modules de l'interface) sont dans F (interface.commun) :
fenetre.construire les y range à chaque ouverture de la page."""
from interface.commun import *  # noqa: F401,F403 — les outils communs et F


def rangees_plis(p, places, garder):
    """Les plis gardés : une seule rangée par camp (l'utilisateur, 2026-11-11), la vôtre en bas, et celle d'un
    adversaire (le premier retenu par garder(x) : à gauche, sinon à droite ou en face ; jamais le mort), chacune avec
    son nombre de levées. Votre partenaire et le second adversaire n'en montrent pas."""
    vus, h = set(), ""
    for x, ou in sorted(zip(places, ("haut", "gauche", "droite", "bas")),
                        key=lambda xo: ("bas", "gauche", "droite", "haut").index(xo[1])):
        if not garder(x) or p.camp(x) in vus: continue
        h += F.plis_gardes(p, x, ou); vus.add(p.camp(x))
    return h


def plis_gardes(p, x, ou, compte=True):
    """Les cartes du joueur x retournées devant lui sur la table, près de son bord, dans l'ordre, chacune en partie sur
    la précédente, comme en duplicate : vers son partenaire si son camp a gagné le pli, en travers sinon."""
    plis = p.plis
    if plis and F.jeu.get("pli_vu") is plis[-1]: plis = plis[:-1]   # le pli encore sur la table n'est pas encore gardé ni compté
    gagne = lambda g: p.camp(g) == p.camp(x)
    if not any(gagne(g) for _, g in plis): return ""   # pas de « 0 » : la rangée d'un camp vient avec sa première levée (2026-11-13)
    cote = ou in ("gauche", "droite")
    forme = lambda g: ("couche" if gagne(g) else "") if cote else ("" if gagne(g) else "couche")
    ici = {"bas": "bottom:12px;left:50%;transform:translateX(-50%)", "haut": "top:12px;left:50%;transform:translateX(-50%)",
           "gauche": "left:12px;top:50%;transform:translateY(-50%)", "droite": "right:12px;top:50%;transform:translateY(-50%)"}[ou]
    return (f"<div class='plis-gardes{' colonne' if cote else ''}{'' if ou == 'bas' else ' adverse'}' style='position:absolute;{ici}' "
            f"title='Vert, vers le partenaire : pli gagné ; gris, en travers : pli perdu'>"
            + "".join(f"<div class='dos {forme(g)}{' gagne' if gagne(g) else ''}"
                      + ("' title='Voir le dernier pli' onclick=\"emitEvent('dernier_pli')\"" if k == len(plis) - 1 else "'")
                      + "></div>" for k, (_, g) in enumerate(plis))   # gagné : vert ; la dernière : voir le dernier pli
            + (F.compte_html(sum(gagne(g) for _, g in plis), ou, F.roule_depuis(p.camp(x))) if compte else "")
            + "</div>")      # au bout de chaque rangée : les levées de ce camp (l'utilisateur, 2026-11-11 : aussi pour la défense)


def roule_depuis(camp):
    """Depuis combien de secondes le compte de ce camp roule (None : il ne roule pas) : un autre rafraîchissement
    pendant ce temps reprend l'animation où elle en est, sans la recommencer."""
    m = F.jeu.get("compte_monte")
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


def carte_posee(c, r, ou=None, ecoule=None, premiere=False, bulle="", cote=""):
    """Une carte jouée, comme dans les mains ; ou : le côté d'où elle glisse quand elle vient d'être posée. premiere :
    la carte qui a commencé le pli, bordée de noir ; bulle : ce qu'en pensait le joueur, au survol (la Démo)."""
    anim = f" arrive-{ou}" if ou else ""
    if F.jeu.get("ramasse"): anim = f" vers-{F.jeu['ramasse']}"          # le pli ramassé, vers les plis gardés du gagnant
    elif F.jeu.get("gagnante") == (c, r): anim += " gagnante"           # la carte qui gagne le pli
    retard = f";animation-delay:-{ecoule:.2f}s" if ou else ""
    h = (f"<div data-c='{c}{r}' class='carte{' r' if c in '♥♦' else ''}{f' premiere p-{cote}' if premiere and cote else ''}{anim}' "
         f"style='margin:0{retard}'>{F.face(r)}<br/>{c}</div>")
    return f"<div class='carte-sens'>{h}<span class='bulle'>{bulle}</span></div>" if bulle else h


def pli_cartes(p, places, posees, derniere=None, ecoule=0, mort=None, bulles=None):
    """Les cartes du pli, chacune sur la table juste devant le joueur qui l'a posée, comme les cartons des enchères ;
    celle du mort aussi (mort : son siège, quand il est étalé sur la table : la croix évite ses cartes)."""
    haut, gauche, droite, bas = places
    cote = {haut: "haut", gauche: "gauche", droite: "droite", bas: "bas"}
    h = ""
    premier = next(iter(posees), None)              # posees suit l'ordre du pli : la première carte l'a commencé
    # les quatre cartes en croix serrée, au centre de la place libre (l'utilisateur, 2026-11-13 : alignées et près du
    # centre, pour les voir d'un coup d'œil), celle du mort aussi : le mort étalé en haut (en bas) prend le haut (le bas)
    # de la table, la croix descend (monte) ; sur un côté, elle s'en écarte de la moitié de la largeur ajoutée
    mort_ou = cote.get(mort)
    cx = {"gauche": f"calc(50% + {(LARGEUR_TABLE_LARGE_PX - COTE_TABLE_PX) // 2}px)",
          "droite": f"calc(50% - {(LARGEUR_TABLE_LARGE_PX - COTE_TABLE_PX) // 2}px)"}.get(mort_ou, "50%")
    cy = "50%"
    if mort_ou in ("haut", "bas"):                  # à mi-chemin entre le bas de la plus longue colonne du mort (au début de la
        longue = max(len(c.replace("-", "")) for c in p.d["mains"][mort].split())   # donne : la croix ne bouge pas quand le
        bas_mort = F.HAUT_NOM_MORT + F.CARTE_H + (longue - 1) * F.PAS_COLONNE              # mort se vide) et vos plis gardés
        milieu = (bas_mort + F.HAUTEUR_TABLE_HAUTE - F.BORD_PLIS) / 2                    # (l'utilisateur, 2026-11-13)
        cy = f"{milieu:.0f}px" if mort_ou == "haut" else f"{F.HAUTEUR_TABLE_HAUTE - milieu:.0f}px"
    ici_ = {"haut": f"left:{cx};top:calc({cy} - {F.CROIX_DY}px)", "bas": f"left:{cx};top:calc({cy} + {F.CROIX_DY}px)",
            "gauche": f"left:calc({cx} - {F.CROIX_DX}px);top:{cy}", "droite": f"left:calc({cx} + {F.CROIX_DX}px);top:{cy}"}
    for x, (c, r) in posees.items():
        vient = cote[x] if x == derniere else None
        ici = ici_[cote[x]] + ";transform:translate(-50%,-50%)"
        h += (f"<div style='position:absolute;{ici};z-index:3'>"
              f"{F.carte_posee(c, r, vient, ecoule, premiere=x == premier, bulle=(bulles or {}).get(x, ''), cote=cote[x])}</div>")
    return h


def pli_en_cours(p):
    """(posées {siège: (couleur, rang)}, le siège de la carte qui vient d'arriver ou None, depuis combien de temps)."""
    pli = F.jeu["pli_vu"][0] if F.jeu["pli_vu"] else p.pos.pli
    posees = {s: (c, r.translate(carte.FR)) for s, c, r in pli}
    n = len(p.pos.jouees)                          # une carte vient d'être posée : elle glisse depuis le bord du joueur
    if n > F.jeu.get("cartes_vues", 0): F.jeu["carte_arrive"] = (n, time.monotonic())
    F.jeu["cartes_vues"] = n
    n_, t_ = F.jeu.get("carte_arrive") or (0, 0)
    ecoule = time.monotonic() - t_
    return posees, (pli[-1][0] if pli and n_ == n and ecoule < .5 else None), ecoule


def pli_html(p, places, mort=None):
    """Le pli en cours, chaque carte devant le joueur qui l'a posée, et les plis gardés."""
    posees, derniere, ecoule = F.pli_en_cours(p)
    return (f"<div style='position:absolute;inset:0;pointer-events:none'>"
            f"{F.pli_cartes(p, places, posees, derniere, ecoule, mort)}"
            + F.rangees_plis(p, places, lambda x: x == places[3] or (p.camp(x) != p.camp(places[3]) and x != p.mort()))
            + "</div>")   # les vôtres, ceux des adversaires (pas du mort : il est étalé)


def etui(d, places, petit=False, pale=False):
    """L'étui de la donne au centre, comme un vrai étui : Nord et Sud toujours sur les petits côtés (debout quand
    Nord-Sud sont en haut et en bas, couché sinon), leurs bandes sur toute la largeur, Est et Ouest entre elles ;
    chaque nom se lit depuis sa place, en capitales, blanc sur rouge si son camp est vulnérable, sur vert sinon ; le
    donneur écrit « Donneur » en rouge ou vert sur blanc ; le joueur qui réfléchit clignote. pale : pendant le jeu de la
    carte, l'étui reste sur la table en filigrane, ses couleurs à peine plus foncées que la table (ETUI_PALE)."""
    v = d["vul"]; vul = lambda x: v == "Tous" or v == ("N-S" if x in "NS" else "E-O")
    l, L, h, f = (84, 149, 22, 12) if petit else F.ETUI      # l × L : l'étui (9:16), h : épaisseur des bandes
    haut, gauche, droite, bas = places
    debout = haut in "NS"
    W, H = (l, L) if debout else (L, l)
    if debout:                                            # grid-area : ligne, colonne, ligne de fin, colonne de fin
        place = {haut: "1 / 1 / 2 / 4", bas: "3 / 1 / 4 / 4", gauche: "2 / 1 / 3 / 2", droite: "2 / 3 / 3 / 4"}
    else:                                                 # Nord et Sud à gauche et à droite, Est-Ouest entre eux
        place = {gauche: "1 / 1 / 4 / 2", droite: "1 / 3 / 4 / 4", haut: "1 / 2 / 2 / 3", bas: "3 / 2 / 4 / 3"}
    P = F.ETUI_PALE
    def bande(x):
        teinte = (P["rouge"] if vul(x) else P["vert"]) if pale else "var(--bc-danger)" if vul(x) else "var(--bc-success)"
        blanc = P["fond"] if pale else "var(--bc-blanc)"
        if x == d["donneur"]:                             # le donneur : « Donneur » en couleur sur blanc
            nom, fond, encre = "Donneur", f"{blanc};border:2px solid {teinte}", P["encre"] if pale else teinte
        else:                                             # les autres : le nom en capitales, blanc sur la couleur
            nom, fond, encre = SIEGE[x].upper(), teinte, P["encre"] if pale else "var(--bc-blanc)"
        if x in (haut, bas):
            forme = "width:100%;height:100%;" + ("transform:rotate(180deg);" if x == haut else "")
        else:
            forme = "width:100%;height:100%;writing-mode:vertical-rl;" + ("transform:rotate(180deg);" if x == droite else "")   # le haut des lettres vers le centre, loin du lecteur
        return (f"<div class='{'pense' if F.jeu.get('pense') == x else ''}' style='grid-area:{place[x]};{forme}display:flex;"
                f"align-items:center;justify-content:center;border-radius:5px;font-size:{f}px;font-weight:700;color:{encre};"
                f"box-sizing:border-box;background:{fond}'>{nom}</div>")
    return (f"<div title='En rouge les camps vulnérables, en vert les autres' style='display:grid;box-sizing:border-box;"
            f"width:{W}px;height:{H}px;grid-template-columns:{h}px 1fr {h}px;grid-template-rows:{h}px 1fr {h}px;gap:4px;"
            f"padding:6px;border-radius:8px;" + (f"background:{P['fond']};border:1px solid {P['bord']}'>" if pale else
            "background:var(--bc-tapis-200);border:1px solid var(--bc-tapis-300);box-shadow:0 1px 2px rgba(0,0,0,.12)'>") +
            f"{bande(haut)}{bande(gauche)}{bande(droite)}{bande(bas)}</div>")


def tapis_encheres(d, places, vues=None):
    """Les enchères posées devant chaque joueur, comme les cartons d'une boîte à enchères ; la dernière ressort.
    vues : les enchères à montrer (la démonstration) ; sinon celles de la donne jouée."""
    demo_ = vues is not None
    if vues is None: vues = F.jeu["seq"][:F.jeu["affiche"]]
    devant = {x: [] for x in "NESO"}
    for k, b in enumerate(vues): devant[F.siege_de(d, k)].append(b)
    dernier = F.siege_de(d, len(vues) - 1) if vues else None
    if len(vues) > F.jeu.get("vus", 0): F.jeu["arrive"] = (len(vues), time.monotonic())   # un carton vient d'être posé
    F.jeu["vus"] = len(vues)
    n_, t_ = F.jeu.get("arrive") or (0, 0)
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
            tab, corps = {"passe": ("PASS", f"<span class='base mot'>{F.lettres('PASS')}</span>"),   # PASS, même en France
                          "contre": ("X", "<span class='base croix'><b>X</b></span>"),
                          "surcontre": ("XX", f"<span class='base croix'>{F.lettres('XX')}</span>")}[b]
            face = f"<span class='tab'></span>{corps}"   # l'onglet sans texte : rien à choisir dans une boîte ici
            cls = f" carre {b}" + cls
        else:
            n, den = b[0], b[1:]
            c = F.COUL_BOITE.get(den, "sa")
            face = (f"<span class='grand'><b>{n}</b>"
                    f"<i class='{'sa' if den == 'SA' else ''}'>{den}</i></span>")
            cls = f" bid {c}" + cls
        marge = f";margin-left:-{F.LARGEUR_CARTON[avant] - F.VU_CARTON[avant]}px" if avant else ""   # le carton d'avant en dépasse de VU_CARTON
        return f"<div class='carton{cls}' style='z-index:{k + 1}{marge}{retard}'><div class='face'>{face}</div></div>"
    def a_part(x):
        """Stop et Alerte : posés devant le joueur, à gauche de sa rangée, pas parmi les enchères."""
        out = ""
        if demo_: return out
        if x == F.jeu["siege"] and F.jeu.get("stop"):
            out += "<div class='carton carre stop a-part derniere'><div class='face'><span class='tab gauche'></span><span class='base mot'>"+F.lettres('STOP')+"</span></div></div>"
        vu = F.jeu.get("affiche", len(F.jeu.get("seq") or [])) - 1
        par_robot = (vu >= 0 and vu in set(F.jeu.get("alertes") or []) and vu < len(F.jeu.get("ex") or [])
                     and PART_[F.jeu["ex"][vu][0]] == x and x != F.jeu["siege"])   # le robot partenaire de l'enchère conventionnelle
        if (x == F.jeu["siege"] and F.jeu.get("alerte")) or par_robot:
            out += "<div class='carton carre alerte a-part derniere'><div class='face'><span class='tab'></span><span class='base mot'>"+F.lettres('ALERT')+"</span></div></div>"
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
            f"<div style='position:absolute;left:50%;top:50%;transform:translate(-50%,-50%)'>{F.etui(d, places)}</div></div>")


def carte_el(coul, r, jouables, sur_clic):
    rouge_ = " r" if coul in "♥♦" else ""
    ok = jouables is not None and (coul, r) in jouables
    m = F.marques_dm.get((coul, r))
    badge = f"<span class='dm {'mieux' if m[1] else 'moins'}'>{m[0]}</span>" if m else ""
    tremble = " secoue" if F.jeu.get("secoue") == (coul, r) else ""
    el = ui.html(f"<div data-c='{coul}{r}' class='carte{rouge_}{' jouable' if ok else ' terne' if jouables is not None else ''}{tremble}'>{F.face(r)}<br/>{coul}{badge}</div>",
                 sanitize=False)
    if ok: el.on("click", lambda x=(coul, r): sur_clic(x))


def mort_etale(cartes, jouables, sur_clic, atout, cote="haut", posee="", a_vous=False):
    """Le mort étalé comme à la table : une colonne par couleur, la plus forte carte en haut, l'atout à gauche
    (à la droite du mort), puis les couleurs en alternant noir et rouge. Sur un côté (cote « gauche » ou « droite »),
    une ligne par couleur, la plus forte carte vers le mort, l'atout toujours à sa droite. posee : la carte que le
    mort vient de jouer, juste à côté de ses cartes, du côté du centre ; a_vous : c'est à vous de jouer du mort (souligné)."""
    posee = ""                                     # sa carte jouée est dans le pli en croix (pli_cartes, 2026-11-13)
    autres = [c for c in F.ORDRE_MAIN if c != atout]
    ordre = ([atout] if atout in F.ORDRE_MAIN else []) + autres
    if cote in ("gauche", "droite"):
        if cote == "gauche": ordre = ordre[::-1]          # le mort à gauche regarde vers la droite : sa droite est en bas
        with ui.row().classes("no-wrap items-center gap-3"):
            if cote == "droite" and posee: ui.html(posee, sanitize=False)
            with ui.column().classes("gap-1 mort-table mort-cote " + ("items-start" if cote == "gauche" else "items-end")
                                     + " a-vous" * a_vous):
                for coul in ordre:
                    style, serre = F.serrer(len(cartes.get(coul, "")))   # une longue couleur se serre, comme dans une main
                    with ui.row().classes("no-wrap gap-0 ligne-mort" + serre).style(style):
                        rangs = list(cartes.get(coul, "")) or [None]
                        if cote == "droite": rangs = rangs[::-1]    # à droite, la plus forte contre le bord
                        for r in rangs:
                            if r is None: ui.html(f"<div class='carte vide'><span class='rang-vide'>A</span><br/>{coul}</div>", sanitize=False)
                            else: F.carte_el(coul, r, jouables, sur_clic)
            if cote == "gauche" and posee: ui.html(posee, sanitize=False)
        return
    with ui.column().classes("items-center gap-3"):
        if cote == "bas" and posee: ui.html(posee, sanitize=False)   # le mort en bas (la démonstration) : sa carte vers le centre
        with ui.row().classes("no-wrap items-start gap-3 mort-table" + " a-vous" * a_vous):
            for coul in ordre:
                with ui.column().classes("gap-0 colonne-mort"):
                    if not cartes.get(coul):
                        ui.html(f"<div class='carte vide'><span class='rang-vide'>A</span><br/>{coul}</div>", sanitize=False)
                    for r in cartes.get(coul, ""):
                        F.carte_el(coul, r, jouables, sur_clic)
        if posee and cote != "bas": ui.html(posee, sanitize=False)


def serrer(n):
    """Une ligne d'une main sur le côté : (style, classe). Sa largeur est fixe, celle de LIGNE_CARTES cartes ; au-delà,
    les cartes se chevauchent davantage, et leurs chiffres rapetissent quand il ne reste que peu de place (« serre »)."""
    if n <= LIGNE_CARTES: return "", ""
    pas = (LARGEUR_LIGNE - CARTE_L) / (n - 1)
    return f"--marge:{pas - CARTE_L:.1f}px", " serre" * (pas < 26)


def largeur_main(cartes, grande):
    """La largeur d'une main en ligne : chaque couleur 55 px + 33 par carte de plus (chaque carte déborde de −22 px,
    .carte), l'espace entre les couleurs et ce que dépasse la dernière."""
    groupes = [len(v) for v in cartes.values() if v]
    if not groupes: return 0
    g, fin = (30, 22) if grande else (26, 16)
    return sum(CARTE_L + (n - 1) * PAS_CARTE - 22 for n in groupes) + (len(groupes) - 1) * g + fin


def eventail(cartes, jouables=None, sur_clic=None, colonnes=False, grande=False, a_vous=False, cote="", depart=None):
    """Une main en cartes : {couleur: rangs français du plus fort au plus faible}. En ligne, un petit espace entre les
    couleurs ; en colonnes (une main sur le côté), une couleur par ligne. jouables : les cartes cliquables ;
    grande : votre main, plus grande, qui luit quand c'est à vous.
    Place fixe (l'utilisateur, 2026-11-13 : rien ne doit bouger pendant qu'on joue) : sur un côté, chaque ligne a la
    largeur de six cartes, alignée à gauche ; en haut ou en bas, la main garde la
    largeur de sa main au début de la donne (depart), centrée, et les cartes jouées se resserrent depuis la gauche
    (l'utilisateur, 2026-11-13 : au début, la main centrée)."""
    cls = " main-grande" * grande + " a-vous" * (grande and a_vous)
    contre = ""                     # alignées à gauche aussi pour le joueur de gauche : plus lisible (l'utilisateur, 2026-11-13)
    with (ui.column().classes("gap-1") if colonnes else
          ui.row().classes("no-wrap items-end gap-0 eventail" + cls).style(f"min-width:{F.largeur_main(depart or cartes, grande)}px")):
        for coul in F.ORDRE_MAIN:
            rangs = cartes.get(coul, "")
            if colonnes and not rangs:
                with ui.row().classes("no-wrap gap-0").style(f"width:{LARGEUR_LIGNE}px;{contre}"):
                    ui.html(f"<div class='carte vide'><span class='rang-vide'>A</span><br/>{coul}</div>", sanitize=False)
                continue
            if not rangs: continue                         # une chicane en ligne : rien, pas même une marge
            style, serre = F.serrer(len(rangs)) if colonnes else ("", "")
            with ui.row().classes("no-wrap gap-0 groupe" + (" colonne" if colonnes else "") + serre) \
                    .style((f"width:{LARGEUR_LIGNE}px;{contre}{style}") if colonnes else ""):
                for r in rangs: F.carte_el(coul, r, jouables, sur_clic)


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


def table(d, places, contenu, centre=None, sur_table=(), tour=None, ouvert=True, clic=None):
    """La table, une grande surface vert clair : l'étui, les cartons, le pli et le mort posé dessus ; les mains des
    joueurs autour. contenu(siège, position) dessine une place ; sur_table : les positions posées sur la table (le mort) ;
    tour : le siège qui doit enchérir ou jouer. ouvert : des mains visibles sur les côtés (Démo, Revoir, les mains
    montrées) : les côtés ont la place de quatre cartes, sinon de deux (les mains cachées de Jouer). clic : un clic sur le
    tapis lui-même, hors des cartes qu'on joue (Revoir, Démo : un pas en avant ; Jouer : ramasser le pli fini).
    Le dessin est une boîte de taille fixe (CSS : .cadre-table, en largeurs de carte et en --sp-*) que le CSS met à
    l'échelle de la place disponible : sa taille ne dépend jamais des cartes qui restent (la table tremblait en fin de
    donne quand un script la mesurait ; l'utilisateur, 2026-11-16 : la mise en page au CSS seul)."""
    haut, gauche, droite, bas = places
    large = "gauche" in sur_table or "droite" in sur_table          # le mort sur un côté : la table en 16:9
    haute = "haut" in sur_table or "bas" in sur_table               # le mort en haut ou en bas : la table plus haute que large
    forme = ("width:var(--table-large);height:var(--table-cote);" if large else
             "width:var(--table-cote);height:calc(var(--table-cote) + var(--haut-mort));" if haute else
             "width:var(--table-cote);height:var(--table-cote);")
    with ui.element("div").classes("w-full zone-table" + (" ouverte" if ouvert else "")), \
            ui.element("div").classes("cadre-table"), \
            ui.element("div").classes("ajuste").props(f'data-donne="{d["n"]}-{bas}"'):   # JS_GLISSE : la donne
        ecoule = time.monotonic() - F.jeu.get("tourne", -99)   # la table qui tourne : le demi-tour reprend où il en était
        tourne = f"animation:tourne {F.TOURNE}s ease-in-out;animation-delay:-{ecoule:.2f}s" if ecoule < F.TOURNE else ""
        noms = F.jeu.get("noms") or {}
        v = d["vul"]; vul = lambda x: v == "Tous" or v == ("N-S" if x in "NS" else "E-O")
        def emplacement(x, ou):                      # la place d'une main, gardée même vide (.emplacement) : les noms et
            with ui.element("div").classes("emplacement " + ou):   # la table ne bougent pas quand les cartes s'en vont
                contenu(x, ou)
        def place(x, ou):                            # sa place (NORD…) et son nom (s'il est connu), discrets, près de sa main
            nom_x = noms.get(x, "")
            # à qui le tour : son nom et ses cartes luisent en jaune, vous comme les robots (l'utilisateur, 2026-11-11 :
            # ni triangle, ni soulignement, ni gras)
            etat = " a-jouer" if tour == x else ""; qui = ""   # à qui le tour : sa place (NORD…) sur fond jaune (2026-11-14)
            if ou in ("haut", "bas") and ou in sur_table:   # le mort étalé en haut (en bas) : ses cartes centrées sur la table,
                with ui.column().classes("items-center gap-1 w-full" + qui):   # son nom sur une ligne hors du tapis (nom_mort ;
                    contenu(x, ou)                                            # sous ses cartes, essayé et refusé le 2026-11-13)
            elif ou in ("haut", "bas"):               # « SUD Prénom NOM » sur une ligne, du côté extérieur : au-dessus des
                with ui.column().classes("items-center gap-1" + qui):   # cartes en haut (un peu d'espace sous le titre de la
                    if ou == "haut":                                    # page : il appartient à la table), dessous en bas
                        ui.html(nom_html(nom_x, etat=etat, siege=x, une_ligne=True), sanitize=False).style("margin-top:var(--sp-3)")
                    emplacement(x, ou)
                    if ou == "bas": ui.html(nom_html(nom_x, etat=etat, siege=x, une_ligne=True), sanitize=False)
            elif ou in sur_table:                    # le mort étalé sur un côté de la table : son nom hors du tapis, dans
                with ui.column().classes("items-start gap-1" + qui):   # la marge de ce côté (nom_mort, 2026-11-13)
                    contenu(x, ou)
            else:                                    # au-dessus de la main, aligné à gauche sur ses cartes ; la main seule
                with ui.element("div").classes("main-cote" + qui):   # centrée sur le milieu de la table, le nom posé
                    ui.html(nom_html(nom_x, deux_lignes=True, etat=etat, siege=x), sanitize=False).classes("nom-cote")   # juste
                    emplacement(x, ou)                                  # au-dessus (l'utilisateur, 2026-11-17)
        with ui.element("div").classes("grille-table").style(tourne):   # trois colonnes : la table au milieu, les côtés égaux
            def nom_mort(x):                         # le mort étalé en haut ou en bas : son nom hors du tapis, au-dessus
                ui.html(nom_html(noms.get(x, ""), siege=x, une_ligne=True, etat=" a-jouer" if tour == x else ""),
                        sanitize=False).style("margin-top:var(--sp-3)" if x == haut else "")   # (au-dessous) (2026-11-13)
            with ui.column().classes("items-center rang-haut"):
                if "haut" not in sur_table: place(haut, "haut")
                else: nom_mort(haut)
            with ui.column().classes("items-end"):
                if "gauche" not in sur_table: place(gauche, "gauche")
                else: ui.html(nom_html(noms.get(gauche, ""), deux_lignes=True, droite=True, siege=gauche,
                                       etat=" a-jouer" if tour == gauche else ""), sanitize=False)
            with ui.column().classes("items-center gap-4 tapis").style(       # la table, carrée comme une vraie, à la taille de la fenêtre
                    f"{forme}background:var(--bc-tapis-100);border:1px solid var(--bc-tapis-200);border-radius:var(--table-r);padding:var(--sp-3);"
                    "justify-content:space-between;position:relative;box-sizing:border-box"
                    + (";cursor:pointer" if clic else "")) as tapis_:
                if clic: tapis_.on("click.self", lambda: clic())   # le tapis seul : jamais une carte qu'on joue
                if "haut" in sur_table: place(haut, "haut")
                for ou, x in (("gauche", gauche), ("droite", droite)):   # le mort d'un côté : sur la table, contre son bord
                    if ou in sur_table:
                        with ui.element("div").style(f"position:absolute;{'left' if ou == 'gauche' else 'right'}:var(--sp-3);"
                                                     "top:50%;transform:translateY(-50%);z-index:2"):
                            place(x, ou)
                if centre: centre()
                # plus de triangle sur le bord de la table : seules vos cartes luisent quand c'est à vous (.a-vous)
                if "bas" in sur_table: place(bas, "bas")
            with ui.column().classes("items-start"):
                if "droite" not in sur_table: place(droite, "droite")
                else: ui.html(nom_html(noms.get(droite, ""), deux_lignes=True, siege=droite,
                                       etat=" a-jouer" if tour == droite else ""), sanitize=False)
            with ui.column().classes("items-center rang-bas" + ("" if "bas" in sur_table else " en-retrait")):
                if "bas" not in sur_table: place(bas, "bas")             # votre main, un peu en retrait de la table
                else: nom_mort(bas)


NOMS = ("rangees_plis", "plis_gardes", "roule_depuis", "compte_html", "carte_posee", "pli_cartes", "pli_en_cours", "pli_html", "etui", "tapis_encheres", "carte_el", "mort_etale", "serrer", "largeur_main", "eventail", "dos", "table",)   # rangés dans F par fenetre.construire
