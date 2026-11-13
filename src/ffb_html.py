# -*- coding: utf-8 -*-
"""Les pages de résultats du site de la FFB (ffbridge.fr), enregistrées depuis le navigateur, en une séance Bridge Coach.

Le club publie ses tournois sur le site de la FFB ; on y enregistre (Fichier, Enregistrer sous… « page web ») :
  - chaque donne, « Donne n°N » : donneur, vulnérabilité, les quatre mains, la « Fiche ambulante » (une ligne par table :
    paires N-S et E-O, contrat, déclarant, entame, résultat, scores, notes) et le « Score optimum » (le double mort) ;
  - le classement N-S et E-O, et la page de chaque paire (« Position : A NS1 », sa feuille de route) : ils donnent le
    numéro de chaque paire, donc les tables et le mouvement.
Il suffit de choisir une de ces pages : toutes les pages du même tournoi dans le même dossier sont lues (le numéro de
séance de la FFB, dans l'adresse « …/sessions/404407 », les relie). Les pages sont seulement lues, comme du texte :
rien n'y est exécuté, et leurs dossiers « _files » ne sont pas ouverts.

Ce qui en sort : les tables Bridgemate (comme feuille_route.convertir), que bws_extract.construire calcule ensuite
(scores, %, IMP, paires, mouvement) ; seance(chemin) rend la séance entière, avec le % et le rang officiels des paires.
Les noms sont dans l'ordre de la FFB (son classement) : on ne sait pas qui était Nord ou Sud. Pas de licence, pas de nom
de club. Le double mort est calculé (endplay) et comparé à celui de la page.

    .venv/bin/python -I -X utf8 src/ffb_html.py dossier-ou-page.html sortie.json
"""
import datetime, json, os, re, sys
from html.parser import HTMLParser
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

VIDES = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
SIEGES = {"N": "N", "E": "E", "S": "S", "O": "W"}         # la page (français) -> Bridgemate
DONNEUR = {"nord": "N", "est": "E", "sud": "S", "ouest": "O"}
VUL = {"personne": "Personne", "nord - sud": "N-S", "est - ouest": "E-O", "tous": "Tous"}
COULEURS = ("spade", "heart", "diamond", "club")
DEN = {"S": "S", "H": "H", "D": "D", "C": "C", "NT": "NT"}
RANG_EN = str.maketrans({"R": "K", "D": "Q", "V": "J", "X": "T"})


class ErreurFFB(ValueError):
    pass


# ---------------------------------------------------------------- un petit arbre HTML (bibliothèque standard)
class Noeud:
    __slots__ = ("tag", "attrs", "enfants", "parent")

    def __init__(self, tag, attrs, parent=None):
        self.tag, self.attrs, self.enfants, self.parent = tag, dict(attrs), [], parent

    def texte(self):
        return " ".join(" ".join(e.texte() if isinstance(e, Noeud) else e for e in self.enfants).split())

    def tous(self, test=None):
        for e in self.enfants:
            if isinstance(e, Noeud):
                if test is None or test(e): yield e
                yield from e.tous(test)

    def ui(self, ident):
        """Le premier élément data-ui-id=ident, ou None."""
        return next(self.tous(lambda e: e.attrs.get("data-ui-id") == ident), None)

    def classes(self):
        return (self.attrs.get("class") or "").split()


class _Lecteur(HTMLParser):
    IGNORES = {"script", "style", "svg", "noscript", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.racine = self.courant = Noeud("racine", {})
        self.ignore = 0

    def handle_starttag(self, tag, attrs):
        if self.ignore or tag in self.IGNORES:
            if tag in self.IGNORES: self.ignore += 1
            return
        n = Noeud(tag, attrs, self.courant)
        self.courant.enfants.append(n)
        if tag not in VIDES: self.courant = n

    def handle_startendtag(self, tag, attrs):
        if not self.ignore and tag not in self.IGNORES: self.courant.enfants.append(Noeud(tag, attrs, self.courant))

    def handle_endtag(self, tag):
        if tag in self.IGNORES:
            self.ignore = max(0, self.ignore - 1); return
        if self.ignore or tag in VIDES: return
        n = self.courant
        while n is not self.racine and n.tag != tag: n = n.parent
        if n is not self.racine: self.courant = n.parent      # une balise fermée sans ouverture est ignorée

    def handle_data(self, data):
        if not self.ignore and data.strip(): self.courant.enfants.append(data.replace("\xa0", " "))


def arbre(chemin):
    p = _Lecteur(); p.feed(open(chemin, encoding="utf-8", errors="replace").read()); p.close()
    return p.racine


# ---------------------------------------------------------------- reconnaître les pages
SESSION = re.compile(r"ffbridge\.fr/competitions/results/groups/\d+/sessions/(\d+)")


def reference(chemin):
    """« ffbridge-seance-404407 » : le tournoi de la FFB d'une page enregistrée, ou None (ce n'en est pas une)."""
    try:
        with open(chemin, encoding="utf-8", errors="replace") as f: debut = f.read(400_000)
    except OSError:
        return None
    m = SESSION.search(debut)
    return f"ffbridge-seance-{m[1]}" if m and "Fédération Française de Bridge" in debut else None


def pages_du_tournoi(chemin):
    """Les pages .html du même tournoi, dans le dossier de la page choisie (ou dans le dossier donné)."""
    dossier = chemin if os.path.isdir(chemin) else os.path.dirname(os.path.abspath(chemin))
    ref = None if os.path.isdir(chemin) else reference(chemin)
    if not os.path.isdir(chemin) and not ref:
        raise ErreurFFB(f"{os.path.basename(chemin)} n'est pas une page de résultats du site de la FFB.")
    pages = {}
    for f in sorted(os.listdir(dossier)):
        c = os.path.join(dossier, f)
        if not f.lower().endswith((".html", ".htm")) or not os.path.isfile(c): continue
        r = reference(c)
        if r: pages.setdefault(r, []).append(c)
    if not pages: raise ErreurFFB("Aucune page de résultats du site de la FFB dans ce dossier.")
    if ref is None:
        if len(pages) > 1:
            raise ErreurFFB("Ce dossier contient les pages de plusieurs tournois : choisissez une page du tournoi voulu.")
        ref = next(iter(pages))
    return ref, pages[ref]


# ---------------------------------------------------------------- les morceaux d'une page
def _suit(n):
    """La couleur d'un <ffb-suit-icon suit="S"> (ou de son icône), « NT » pour SA."""
    s = (n.attrs.get("suit") or "").upper()
    if s in DEN: return s
    for i in n.tous():
        for c in i.classes():
            if c in COULEURS: return "SHDC"[COULEURS.index(c)]
    return "NT" if "SA" in n.texte() else None


def contrat(td):
    """« 4 S », « 3 NT x », « PASS » (format Bridgemate), ou None pour une case vide."""
    t = td.texte().upper()
    if "PASSE" in t or t == "PASS": return "PASS"
    icone = next(td.tous(lambda e: e.tag == "ffb-suit-icon"), None)
    m = re.match(r"\s*([1-7])", t)
    if not icone or not m: return None
    den = _suit(icone)
    x = re.sub(r"[^X]", "", t.replace("SA", ""))
    return f"{m[1]} {den}" + {"": "", "X": " x", "XX": " xx"}[x]


def entame(td):
    """« D3 », « ST » (format Bridgemate) ; "" sans entame."""
    icone = next(td.tous(lambda e: e.tag == "ffb-suit-icon"), None)
    if not icone: return ""
    r = td.texte().replace("SA", "").strip().upper()
    r = "T" if r == "10" else r.translate(RANG_EN)
    return (_suit(icone) or "") + r if r else ""


def nombre(t):
    t = t.replace(" ", "").replace("%", "").replace(",", ".")
    try: return float(t)
    except ValueError: return None


def noms_equipe(n):
    """« DUPRÉ Anne - MARTIN Jean Paul » -> ["DUPRÉ Anne", "MARTIN Jean Paul"]."""
    spans = [s.texte().lstrip("- ").strip() for s in n.tous(lambda e: e.tag == "span")] if n else []
    spans = [s for s in spans if s]
    if len(spans) == 2: return spans
    return [x.strip() for x in re.split(r"\s+-\s+", n.texte() if n else "") if x.strip()]


def cle_noms(noms):
    return frozenset(" ".join(x.split()).upper() for x in noms)


def titre_page(racine):
    """(club, titre du tournoi) du bloc imprimé en tête de page."""
    ctx = next(racine.tous(lambda e: e.tag == "ffb-competitions-results-print-context"), None)
    ps = [p.texte() for p in ctx.tous(lambda e: e.tag == "p")] if ctx else []
    return (ps[0] if ps else ""), (ps[1] if len(ps) > 1 else "")


def lire_donne(racine):
    """La page d'une donne : {n, donneur, vul, mains {N: [♠, ♥, ♦, ♣]}, lignes [...], optimum {S: {♠…}}}, ou None."""
    num = racine.ui("board-number")
    if num is None or racine.ui("teams-board-scores-table") is None: return None
    n = int(re.sub(r"\D", "", num.texte()))
    donneur = DONNEUR.get((racine.ui("dealer") or Noeud("p", {})).texte().lower())
    vul = VUL.get(" ".join((racine.ui("vulnerability") or Noeud("p", {})).texte().lower().replace("-", " - ").split()))
    mains = {}
    for s in "NESO":
        main = []
        for c in COULEURS:
            bloc = racine.ui(f"player-{SIEGES[s]}-{c}")
            cartes = [x.texte() for x in bloc.tous(lambda e: "card" in e.classes())] if bloc else []
            main.append("".join("X" if x == "10" else x.upper() for x in cartes))
        mains[s] = main
    lignes = []
    corps = racine.ui("teams-board-scores-table-body")
    for tr in corps.tous(lambda e: e.tag == "tr"):
        cases = {td.attrs.get("id"): td for td in tr.tous(lambda e: e.tag == "td")}
        if "nsTeam" not in cases: continue
        dec = cases["declarer"].texte().strip().upper()
        lignes.append(dict(id=tr.attrs.get("id"), ns=noms_equipe(cases["nsTeam"]), eo=noms_equipe(cases["ewTeam"]),
                           contrat=contrat(cases["contract"]), declarant=dec[:1] if dec[:1] in "NESO" else "",
                           entame=entame(cases["lead"]), resultat=cases["result"].texte().strip(),
                           score_ns=nombre(cases["nsScore"].texte()), score_eo=nombre(cases["ewScore"].texte()),
                           note_ns=nombre(cases["nsNote"].texte())))
    optimum = {}
    grille = racine.ui("optimum-score-table-body")
    for tr in (grille.tous(lambda e: e.tag == "tr") if grille else []):
        cases = {td.attrs.get("id"): td.texte() for td in tr.tous(lambda e: e.tag == "td")}
        s = cases.get("declarer", "").strip().upper()[:1]
        if s in "NESO" and s:
            optimum[s] = {d: int(cases[k]) for k, d in (("S", "♠"), ("H", "♥"), ("D", "♦"), ("C", "♣"), ("NT", "SA"))
                          if cases.get(k, "").strip().isdigit()}
    return dict(n=n, donneur=donneur, vul=vul, mains=mains, lignes=lignes, optimum=optimum)


def lire_paires(racine):
    """Les paires d'une page de classement ou d'une page de paire : [(position « NS1 », noms, %, rang, ids des lignes)]."""
    out = []
    corps = racine.ui("ranking-body")
    for tr in (corps.tous(lambda e: e.tag == "tr") if corps else []):
        pos = tr.ui(tr.attrs.get("data-ui-id", "") + "-position")
        if pos is None: continue
        pct = tr.ui(tr.attrs["data-ui-id"] + "-sessionScore"); rang = tr.ui(tr.attrs["data-ui-id"] + "-rank")
        out.append((pos.texte(), noms_equipe(tr.ui(tr.attrs["data-ui-id"] + "-team")),
                    nombre(pct.texte()) if pct else None, int(re.sub(r"\D", "", rang.texte()) or 0) if rang else None, []))
    chapo = next(racine.tous(lambda e: e.tag == "ffb-competitions-results-team-chapo"), None)
    if chapo is not None:
        t = chapo.texte()
        m = re.search(r"Position\s*:\s*(.+?)\s*•", t)
        r = re.search(r"Rang\s*:\s*(\d+)\D+?avec\s*([\d,]+)", t)
        ids = [tr.attrs.get("id") for tr in (racine.ui("roadmap-table-body") or Noeud("x", {})).tous(lambda e: e.tag == "tr")
               if tr.attrs.get("id")]
        if m:
            out.append((m[1], noms_equipe(next(chapo.tous(lambda e: e.tag == "ffb-team-players"), None)),
                        nombre(r[2]) if r else None, int(r[1]) if r else None, ids))
    return [(re.sub(r"^[A-Z]\s+", "", p.strip()).replace(" ", ""), *reste) for p, *reste in out]


# ---------------------------------------------------------------- la séance
def lire_pages(chemin):
    """Toutes les pages du tournoi lues : (référence, club, titre, donnes, paires {position: {...}})."""
    ref, pages = pages_du_tournoi(chemin)
    club = titre = ""; donnes = {}; paires = {}
    for c in pages:
        r = arbre(c)
        cl, ti = titre_page(r)
        club, titre = club or cl, titre or ti
        d = lire_donne(r)
        if d:
            donnes[d["n"]] = d; continue
        for pos, noms, pct, rang, ids in lire_paires(r):
            p = paires.setdefault(pos, dict(noms=noms, pct=None, rang=None, ids=set()))
            if pct is not None: p["pct"] = pct
            if rang: p["rang"] = rang
            p["ids"].update(ids)
    if not donnes: raise ErreurFFB("Aucune page de donne (« Donne n°… ») de ce tournoi dans le dossier.")
    return ref, club, titre, [donnes[n] for n in sorted(donnes)], paires


def _date(titre):
    m = re.search(r"(\d\d)/(\d\d)/(\d{4})", titre)
    return f"{m[3]}-{m[2]}-{m[1]}" if m else None


def _positions(donnes, paires):
    """{(cote, clé des noms): numéro} : les numéros de la FFB (NS1, EO4) ; sans page de paire, dans l'ordre d'arrivée."""
    num = {}
    for pos, p in paires.items():
        m = re.fullmatch(r"(NS|EO)(\d+)", pos)
        if m: num[(m[1], cle_noms(p["noms"]))] = int(m[2])
    for d in donnes:                                     # une paire sans page : un numéro libre
        for l in d["lignes"]:
            for cote in ("ns", "eo"):
                k = (cote.upper(), cle_noms(l[cote]))
                if k not in num:
                    num[k] = max([v for (c, _), v in num.items() if c == cote.upper()] or [0]) + 1
    return num


def _mitchell(donnes, num):
    """(tours par donne {n: tour}, nombre de positions) si le mouvement est un Mitchell classique (la paire N-S k reste à
    la table k, les E-O montent, les étuis descendent) ; sinon None."""
    nns = max([v for (c, _), v in num.items() if c == "NS"] or [0]); neo = max([v for (c, _), v in num.items() if c == "EO"] or [0])
    npos = max(nns, neo)
    nums = [d["n"] for d in donnes]
    if not npos or max(nums) % npos: return None
    par_tour = max(nums) // npos
    for d in donnes:
        for l in d["lignes"]:
            t = num[("NS", cle_noms(l["ns"]))]; e = num[("EO", cle_noms(l["eo"]))]
            jeu = (d["n"] - 1) // par_tour + 1
            r = (jeu - t) % npos + 1
            if (t - r) % npos + 1 != e: return None
    return par_tour, npos


def convertir(chemin):
    """(tables Bridgemate, infos) : infos = {reference, club, titre, date, moment, paires, alertes}."""
    from feuille_route import double_mort, verifier
    ref, club, titre, donnes, paires = lire_pages(chemin)
    date = _date(titre)
    if not date: raise ErreurFFB("La date du tournoi n'est pas sur les pages.")
    alertes = []
    num = _positions(donnes, paires)
    mitch = _mitchell(donnes, num)
    HR, HE, RD, RE = [], [], [], []
    for d in donnes:
        b = d["n"]
        verifier(d)
        from bws_extract import donneur as donneur_de, vul as vul_de
        if d["donneur"] and d["donneur"] != donneur_de(b) or d["vul"] and d["vul"] != vul_de(b):
            alertes.append(f"Donne {b} : donneur ou vulnérabilité différents de l'étui habituel.")
        hr = dict(Section=1, Board=b)
        for s in "NESO":
            for coul, x in zip(("Spades", "Hearts", "Diamonds", "Clubs"), d["mains"][s]):
                hr[{"O": "West", "N": "North", "E": "East", "S": "South"}[s] + coul] = x.translate(RANG_EN)
        HR.append(hr)
        he = double_mort(d["mains"]); HE.append(dict(he, Section=1, Board=b))
        if d["optimum"]:                                 # le double mort calculé, contre celui de la page
            en = {"♠": "Spades", "♥": "Hearts", "♦": "Diamonds", "♣": "Clubs", "SA": "Notrump"}
            noms = {"N": "North", "E": "East", "S": "South", "O": "West"}
            ecarts = [f"{s} {den}" for s, v in d["optimum"].items() for den, lev in v.items() if he[noms[s] + en[den]] != lev]
            if ecarts: alertes.append(f"Donne {b} : double mort différent de la page de la FFB ({', '.join(ecarts)}).")
        for l in d["lignes"]:
            t = num[("NS", cle_noms(l["ns"]))]; e = num[("EO", cle_noms(l["eo"]))]
            rnd = ((b - 1) // mitch[0] + 1 - t) % mitch[1] + 1 if mitch else b
            if not mitch:
                RD.append(dict(Section=1, Table=t, Round=rnd, NSPair=t, EWPair=e, LowBoard=b, HighBoard=b))
            if l["contrat"] is None: continue            # une table sans résultat
            r = {"ID": len(RE) + 1, "Section": 1, "Table": t, "Round": rnd, "Board": b, "PairNS": t, "PairEW": e,
                 "Erased": False, "Contract": l["contrat"]}
            if l["contrat"] == "PASS":
                r.update({"NS/EW": "", "Result": "", "LeadCard": ""})
            else:
                r.update({"NS/EW": SIEGES[l["declarant"]], "Result": l["resultat"], "LeadCard": l["entame"]})
            RE.append(r)
    tables = max([v for (c, _), v in num.items() if c == "NS"] or [1])
    eos = {v for (c, _), v in num.items() if c == "EO"}; nss = {v for (c, _), v in num.items() if c == "NS"}
    if mitch:                                            # le mouvement entier : à chaque tour, les tables et leurs étuis
        par_tour, npos = mitch
        for rnd in range(1, npos + 1):
            for t in range(1, npos + 1):
                jeu = (t + rnd - 2) % npos + 1; e = (t - rnd) % npos + 1
                ns = t if t <= tables else None
                eo = e if e in eos else None
                if ns is None: continue                  # une table sans N-S : la paire E-O est au relais
                RD.append(dict(Section=1, Table=t, Round=rnd, NSPair=ns, EWPair=eo,
                               LowBoard=(jeu - 1) * par_tour + 1, HighBoard=jeu * par_tour))
    # tour 0 : chaque paire à sa table de départ, pour les noms (bws_extract.paires_initiales lit le premier tour) ;
    # sans donnes, il reste hors du mouvement (session.rondes)
    PN = []
    noms_de = {(c, v): k for (c, k), v in num.items()}
    for (cote, v), k in sorted(noms_de.items()):
        noms = (paires.get(f"{cote}{v}") or {}).get("noms") or \
               next(l[cote.lower()] for d in donnes for l in d["lignes"] if cle_noms(l[cote.lower()]) == k)
        for siege, nom in zip("NS" if cote == "NS" else "EW", noms):
            PN.append(dict(Section=1, Table=v, Direction=siege, Name=nom, Number="", Round=0))
    for v in sorted(nss | eos):
        RD.append(dict(Section=1, Table=v, Round=0, NSPair=v if v in nss else None, EWPair=v if v in eos else None,
                       LowBoard=None, HighBoard=None))
    T = dict(HandRecord=HR, HandEvaluation=HE, RoundData=RD, ReceivedData=RE, BiddingData=[], PlayerNumbers=PN,
             Section=[dict(ID=1, Letter="A", Tables=tables, Winners=2, ScoringType=1)],   # tournoi de paires FFB : en %
             Session=[dict(ID=1, Name=titre, Date=f"{date}T00:00:00")])
    moment = next((m for m in ("matin", "après-midi", "soir") if m in titre.lower()), "")
    return T, dict(reference=ref, club=club, titre=titre, date=date, moment=moment, paires=paires, num=num,
                   donnes=donnes, alertes=alertes, mitchell=bool(mitch))


def seance(chemin):
    """La séance (session, donnes, paires, alertes) des pages de la FFB, pour rapport.py ; les noms complets sont dans
    bws_extract.JOUEURS, comme pour un .bws."""
    from bws_extract import construire
    T, info = convertir(chemin)
    T["Session"][0]["Date"] = datetime.datetime.fromisoformat(T["Session"][0]["Date"])
    data = construire(T)
    s = data["session"]
    if info["moment"]: s["moment"] = info["moment"]
    s["marque"] = "MP"
    if not info["mitchell"]: s.pop("rondes", None)       # sans mouvement connu, pas de tours inventés
    # le % et le rang officiels de la FFB
    for (cote, k), v in info["num"].items():
        p = info["paires"].get(f"{cote}{v}")
        cle = f"{v}{cote}"
        if p and cle in data["paires"]:
            if p["pct"] is not None: data["paires"][cle]["pct"] = p["pct"]
            if p["rang"]: data["paires"][cle]["rang"] = p["rang"]
    # les scores et les notes de la page, contre ceux calculés
    pages = {d["n"]: d for d in info["donnes"]}
    for d in data["donnes"]:
        lignes = {(info["num"][("NS", cle_noms(l["ns"]))]): l for l in pages[d["n"]]["lignes"]}
        for t in d["tables"]:
            l = lignes.get(int(re.sub(r"\D", "", str(t["table"]))))
            if not l: continue
            sc = l["score_ns"] if l["score_ns"] is not None else -(l["score_eo"] or 0)
            if sc != t["score_ns"]:
                info["alertes"].append(f"Donne {d['n']}, table {t['table']} : score {t['score_ns']} calculé, {sc:g} sur la page.")
            if l["note_ns"] is not None and t["pct_ns"] is not None and abs(l["note_ns"] - t["pct_ns"]) > 0.1:
                t["pct_ns"] = l["note_ns"]                 # la note officielle (arbitrage, relais…)
    data["alertes"] = info["alertes"] + data.get("alertes", [])
    return data


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage : .venv/bin/python -I -X utf8 src/ffb_html.py dossier-ou-page.html sortie.json")
    data = seance(sys.argv[1])
    json.dump(data, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(data['donnes'])} donnes, {sum(len(d['tables']) for d in data['donnes'])} résultats : {sys.argv[2]}")
    for a in data["alertes"]: print("ALERTE :", a)


if __name__ == "__main__":
    main()
