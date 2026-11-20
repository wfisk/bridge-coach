# -*- coding: utf-8 -*-
"""L'onglet Système (l'utilisateur, 2026-11-16) : le système des robots, tel que le moteur le lit dans
systems/<système>/regles.yaml, rendu lisible et en lecture seule.

- les familles de la barre (Ouvertures, Après 1SA / 2SA…) regroupent les sections du fichier, repérées par ses
  intertitres (« # ------ réponses à 1SA… ») ;
- chaque séquence (« 1SA - 2T ») montre ses enchères possibles dans l'ordre où le robot les essaie (la première vraie
  l'emporte), ce qu'elles montrent, leur condition traduite en français (conditions()), leurs badges (convention,
  alerte, source, nature) et les mains d'exemple, vérifiées à chaque lecture du fichier ;
- une enchère dont la suite est décrite mène à sa séquence (suite()).

Ce qui n'est pas décrit dans le fichier, le moteur le joue avec ses règles générales (src/encheres/sef2024.py) :
la page le dit. Rien ici ne change ce que jouent les robots."""
import html, os, re
from ruamel.yaml import YAML

ICI = os.path.dirname(os.path.abspath(__file__))
SYSTEMES = os.path.join(os.path.dirname(ICI), "systems")
SYSTEME = "sef-2024"

COUL = {"T": "♣", "K": "♦", "C": "♥", "P": "♠"}
NOM_COUL = {"T": ("trèfle", "trèfles"), "K": ("carreau", "carreaux"), "C": ("cœur", "cœurs"), "P": ("pique", "piques")}
JOUEUR = {"U": "de l'ouvreur", "W": "du répondant", "Y": "de l'intervenant", "Z": "du partenaire de l'intervenant"}

# les familles de la barre : chaque intertitre du fichier va dans la première famille dont un mot-clé y figure
FAMILLES = (
    ("ouvertures", "Ouvertures", ("ouvertures",)),
    ("sa", "Après 1SA et 2SA", ("réponses à 1sa", "stayman", "2sa de l'ouvreur")),
    ("majeure", "Après 1♥ / 1♠", ("réponses à 1♥",)),
    ("mineure", "Après 1♣ / 1♦", ("réponses à 1♣", "réponses à 1♦", "1t - 1sa")),
    ("fortes", "Ouvertures fortes", ("ouvertures fortes", "2♣ – 2♦")),
    ("faibles", "Deux faibles, barrages", ("deux faibles",)),
    ("suite", "Suite des enchères", ("après une réponse", "après un soutien", "après 2sa ou 3sa", "après 1sa de l'ouvreur",
                                     "l'ouvreur a", "répondant", "4e couleur", "contrats atteints", "1m – 1sa")),
    ("interventions", "Interventions", ("intervention sur", "sur une ouverture de 1", "sur 1sa (directement)",
                                        "notre intervention", "intervenant", "bicolore", "en défense")),
    ("concurrence", "Quand ils interviennent", ("après une intervention adverse", "réponse après une intervention",
                                                 "après une intervention à la couleur", "le répondant a passé",
                                                 "quand ils interviennent")),
    ("contres", "Contres", ("contre d'appel", "spoutnik")),
)
AUTRES = ("autres", "Autres séquences")

NATURE = {"conclusion": "pour jouer", "invite": "invitation", "limite": "limite", "forcing": "forcing", "relais": "relais",
          "appel": "contre d'appel", "bicolore": "bicolore", "cue": "cue-bid", "spoutnik": "Spoutnik", "reveil": "réveil",
          "punitif": "punitif", "choix": "choix", "soutien_lent": "soutien lent", "drury": "Drury", "barrage": "barrage"}


# ---------------------------------------------------------------- lire le fichier
def lire(systeme=SYSTEME):
    """{"definitions": {nom: condition}, "sections": [(intertitre, [(clé, [règle…], [exemple…])])]} dans l'ordre du
    fichier. Une règle : {"enchere", "si", "montre", "nature", "nom", "alerte", "source", "note"}."""
    f = os.path.join(SYSTEMES, systeme, "regles.yaml")
    texte = open(f, encoding="utf-8").read().replace("\t", "    ")
    y = YAML(typ="safe").load(texte)
    # l'intertitre de chaque clé : le dernier « # ---- titre » au-dessus d'elle
    titres, courant = {}, "Début"
    for ligne in texte.splitlines():
        m = re.match(r"#\s*-{5,}\s*(.+)$", ligne)
        if m: courant = m[1].strip(); continue
        m = re.match(r'^("?)([^"#:][^"]*?)\1:\s*(#.*)?$', ligne)
        if m and not ligne.startswith(" "): titres[m[2]] = courant
    sections = []
    for cle, liste in y.items():
        if cle in ("systeme", "definitions") or not isinstance(liste, list): continue
        regles, exemples = [], []
        for x in liste:
            if not isinstance(x, dict) or len(x) != 1: continue
            (k, v), = x.items()
            if k == "exemples": exemples = v or []; continue
            v = v or {}
            regles.append({"enchere": str(k), "si": v.get("si", ""), "montre": v.get("montre", ""), "nature": v.get("nature", ""),
                           "nom": v.get("nom", ""), "alerte": str(v.get("alerte", "")).lower() in ("oui", "true"),
                           "source": v.get("source", ""), "note": v.get("note", ""), "apres": v.get("apres", "")})
        t = titres.get(cle, "Autres")
        if not sections or sections[-1][0] != t: sections.append((t, []))
        sections[-1][1].append((str(cle), regles, exemples))
    return {"definitions": y.get("definitions") or {}, "sections": sections}


def famille_de(titre):
    t = titre.lower()
    for cle, _, mots in FAMILLES:
        if any(m in t for m in mots): return cle
    return AUTRES[0]


def familles(s):
    """[(clé, titre, [(intertitre, séquences)])] : les familles qui ont des séquences, dans l'ordre de FAMILLES."""
    par = {}
    for titre, seqs in s["sections"]:
        par.setdefault(famille_de(titre), []).append((titre, seqs))
    return [(k, t, par[k]) for k, t, _ in FAMILLES + (AUTRES + ((),),) if k in par]


# ---------------------------------------------------------------- les enchères
def enchere_html(e, adverse=False):
    """Un carton : « 2C » → 2♥ (rouge), « contre » → X ; une enchère générique (1M, 2U, *P) reste écrite."""
    e = str(e).strip()
    m = re.fullmatch(r"([1-7])([TKCP])", e)
    if m:
        rouge = " rouge" if m[2] in "CK" else ""
        return f"<span class='carton-s{rouge}{' adv' if adverse else ''}'>{m[1]}{COUL[m[2]]}</span>"
    lib = {"contre": "X", "surcontre": "XX", "passe": "Passe"}.get(e, e)
    return f"<span class='carton-s{' adv' if adverse else ''}' title='{html.escape(sens_enchere(e))}'>{html.escape(lib)}</span>"


def sens_enchere(e):
    """« 2U » → « 2 dans la couleur de l'ouvreur » ; « 1M » → « 1♥ ou 1♠ » ; « *P » → « le palier le plus bas à pique »."""
    m = re.fullmatch(r"([1-7])([MNx])", e)
    if m: return {"M": f"{m[1]}♥ ou {m[1]}♠", "N": f"{m[1]}♣ ou {m[1]}♦", "x": f"{m[1]} dans une couleur"}[m[2]]
    m = re.fullmatch(r"([1-7])([UWYZ])([MN]?)", e)
    if m: return f"{m[1]} dans la {'majeure' if m[3] == 'M' else 'mineure' if m[3] == 'N' else 'couleur'} {JOUEUR[m[2]]}"
    m = re.fullmatch(r"\*([TKCPUWYZ])(\+1)?", e)
    if m:
        c = NOM_COUL[m[1]][0] if m[1] in COUL else "la couleur " + JOUEUR[m[1]]
        return f"le palier le plus bas à {c}" + (", avec un saut" if m[2] else "")
    return ""


def jetons(cle):
    """« 1K (1P) - 2T » → [("1K", False), ("1P", True), ("2T", False)] ; « ouverture » → []."""
    if cle == "ouverture": return []
    out = []
    for t in re.findall(r"\([^)]*\)|[^\s\-()]+", cle):
        if t.startswith("("):
            out += [(x, True) for x in t[1:-1].split()]
        else: out.append((t, False))
    return out


def rouge(t):
    """♥ et ♦ en rouge dans un texte déjà échappé (pas dans un attribut : title='…' garde ses symboles tels quels)."""
    return str(t).replace("♥", "<span class='rouge'>♥</span>").replace("♦", "<span class='rouge'>♦</span>")


def alternatives(cle):
    return [x.strip() for x in cle.split("|")]


def sequence_html(cle):
    """La séquence en cartons ; les enchères adverses en gris ; plusieurs séquences : l'une sous l'autre."""
    if cle == "ouverture": return "<span class='seq-libre'>Ouverture</span>"
    lignes = []
    for alt in alternatives(cle):
        lignes.append("<span class='seq'>" + " ".join(enchere_html(e, adv) for e, adv in jetons(alt))
                      + " <span class='carton-s attente'>?</span></span>")
    return "<br>".join(lignes)


def _norm(cle):
    return tuple(e for e, _ in jetons(cle)), tuple(a for _, a in jetons(cle))


def index(s):
    """{(enchères, adverses) : clé} pour chaque séquence décrite (chaque alternative d'une clé)."""
    ix = {}
    for _, seqs in s["sections"]:
        for cle, _, _ in seqs:
            for alt in alternatives(cle): ix[_norm(alt)] = cle
    return ix


def suite(ix, cle, enchere):
    """(la clé de la séquence qui suit cette enchère, cette séquence en texte), si elle est décrite (notre camp : sans
    enchère adverse entre), sinon None."""
    for alt in alternatives(cle) if cle != "ouverture" else [""]:
        e, a = _norm(alt) if alt else ((), ())
        k = ix.get((e + (enchere,), a + (False,)))
        if k and k != cle: return k, sequence_texte(list(zip(e + (enchere,), a + (False,))))
    return None


def sequence_texte(jetons_):
    """[("1SA", False), ("2T", False)] → « 1SA – 2♣ » ; les enchères adverses entre parenthèses."""
    def un(x, adv):
        m = re.fullmatch(r"([1-7])([TKCP])", x)
        t = f"{m[1]}{COUL[m[2]]}" if m else {"contre": "X", "surcontre": "XX", "passe": "passe"}.get(x, x)
        return f"({t})" if adv else t
    return " – ".join(un(x, a) for x, a in jetons_)


def ancre(cle):
    return "seq-" + re.sub(r"[^A-Za-z0-9]+", "-", cle).strip("-")


# ---------------------------------------------------------------- les conditions en français
def _zone(z, unite=""):
    """« 5+ » → « 5 ou plus » ; « 1- » → « 1 au plus » ; « 6-10 » → « 6 à 10 » ; « 1= » → « exactement 1 »."""
    neg = z.startswith("!"); z = z.lstrip("!")
    u = f" {unite}" if unite else ""
    if re.fullmatch(r"\d+\+", z): t = f"{z[:-1]}{u} ou plus"
    elif re.fullmatch(r"\d+-", z): t = f"{z[:-1]}{u} au plus"
    elif re.fullmatch(r"\d+-\d+", z): a, b = z.split("-"); t = f"{a} à {b}{u}"
    elif re.fullmatch(r"\d+=?", z): t = f"{z.rstrip('=')}{u}"
    else: return None
    return ("pas " + t) if neg else t


def _longueur(nom, z):
    """La longueur d'une couleur (nom : « à pique », « dans la couleur de l'ouvreur »)."""
    if z in ("0", "0="): return f"chicane {nom}"
    if z in ("1", "1="): return f"singleton {nom}"
    if z in ("2", "2="): return f"doubleton {nom}"
    if z == "1-": return f"singleton ou chicane {nom}"
    if z == "!1-": return f"ni singleton ni chicane {nom}"
    t = _zone(z, "cartes")
    return f"{t} {nom}" if t else None


def _nom_contexte(c):
    if c in COUL: return f"à {NOM_COUL[c][0]}"
    if c == "M": return "dans la majeure la plus longue"
    if c == "N": return "dans la mineure la plus longue"
    m = re.fullmatch(r"([UWYZ])([MN]?)", c)
    if m: return f"dans la {'majeure' if m[2] == 'M' else 'mineure' if m[2] == 'N' else 'couleur'} {JOUEUR[m[1]]}"
    if re.fullmatch(r"[TKCP]{2,4}", c): return "à " + " et à ".join(NOM_COUL[x][0] for x in c) + " (chacune)"
    return None


def atome(a, definitions=()):
    """Une condition simple en français, ou None (elle reste écrite telle quelle)."""
    a = a.strip(); m = None
    neg = a.startswith("non ")
    if neg:
        b = a[4:].strip()
        if b == "reg": return "main irrégulière"
        if b == "irreg": return "main régulière"
        m = re.fullmatch(r"forme (\d-\d-\d-\d)", b)
        if m: return f"pas de répartition {m[1]}"
        t = atome(b, definitions)
        return ("sauf " + t) if t else None
    if a in definitions: return f"<i title='{html.escape(str(definitions[a]))}'>{a}</i>"
    if a == "reg": return "main régulière"
    if a == "irreg": return "main irrégulière"
    if a in ("regle des 20", "règle des 20"): return "règle des 20"
    if a in ("regle des 15", "règle des 15"): return "règle des 15"
    if a in ("NN", "NV", "VN", "VV"):
        return {"NN": "personne vulnérable", "NV": "vulnérabilité favorable", "VN": "vulnérabilité défavorable",
                "VV": "tous vulnérables"}[a]
    if a == "vul nous": return "nous sommes vulnérables"
    if a == "vul eux": return "ils sont vulnérables"
    m = re.fullmatch(r"forme (\d-\d-\d-\d)", a)
    if m: return f"répartition {m[1]}"
    m = re.fullmatch(r"(H|HL|HLD)(?:\((\w+)\))? (!?[\d+\-=]+)", a)
    if m:
        t = _zone(m[3], {"H": "H", "HL": "points HL", "HLD": "points HLD"}[m[1]])
        if t and m[2]: t += f" (atout {NOM_COUL[m[2]][0] if m[2] in COUL else 'la couleur ' + JOUEUR.get(m[2], m[2])})"
        return t
    m = re.fullmatch(r"camp (H|HL|HLD)(?:\((\w+)\))? (!?[\d+\-=]+)", a)
    if m:
        t = _zone(m[3], {"H": "H", "HL": "points HL", "HLD": "points HLD"}[m[1]])
        return f"{t} à nous deux" if t else None
    m = re.fullmatch(r"S (!?[\d+\-=]+)", a)
    if m:
        z = m[1]
        if re.fullmatch(r"\d", z): return f"en {z}{'re' if z == '1' else 'e'} position"
        if re.fullmatch(r"\d-\d", z): return f"en position {z[0]} à {z[2]}"
        return "position " + (_zone(z) or z)
    if a == "TKCP !1-": return "ni singleton ni chicane"
    if a == "TKCP !6+": return "aucune couleur de 6 cartes"
    m = re.fullmatch(r"([TKCP]{2,4}) (!?[\d+\-=]+)", a)
    if m and m[1] != "TKCP":
        t = _zone(m[2].lstrip("!"), "cartes")
        return f"{'pas ' if m[2].startswith('!') else ''}{t} à " + " et à ".join(NOM_COUL[x][0] for x in m[1])
    m = re.fullmatch(r"([TKCP]|M|N) (!?\d+[+\-=]?|!?\d+-\d+)", a)
    if m and m[2] not in ("0", "0=", "1", "1=", "2", "2=", "1-", "!1-"):
        if m[1] in COUL:
            t = _zone(m[2].lstrip("!"), NOM_COUL[m[1]][1])
            return ("pas " + t) if m[2].startswith("!") else t
        z = m[2].lstrip("!"); q = "majeure" if m[1] == "M" else "mineure"
        if re.fullmatch(r"\d+-", z) and not m[2].startswith("!"):         # M 4- : aucune majeure de 5 cartes
            return f"pas de {q} de {int(z[:-1]) + 1} cartes"
        t = _zone(z, "cartes")
        return f"pas de {q} de {t}" if m[2].startswith("!") else f"une {q} de {t}"
    m = re.fullmatch(r"([TKCP]|[UWYZ][MN]?|[MN]|[TKCP]{2,4})\+([TKCP]|[UWYZ][MN]?|[MN]) (!?[\d+\-=]+)", a)
    if m: return f"{_zone(m[3], 'cartes')} {_nom_contexte(m[1])} et {_nom_contexte(m[2])} ensemble"
    m = re.fullmatch(r"([TKCP]{1,4}|[UWYZ][MN]?|M|N) (!?[\d+\-=]+)", a)
    if m:
        nom = _nom_contexte(m[1])
        return _longueur(nom, m[2]) if nom else None
    m = re.fullmatch(r"([TKCPMNUWYZ]{1,2}) (>=|<=|>|<|=) ([TKCPMNUWYZ]{1,2})", a)
    if m:
        x, y = (NOM_COUL[v][1] if v in COUL else {"M": "majeure", "N": "mineure"}.get(v, "couleur " + JOUEUR.get(v[0], v))
                for v in (m[1], m[3]))
        return {">=": f"au moins autant de {x} que de {y}", "<=": f"pas plus de {x} que de {y}", ">": f"plus de {x} que de {y}",
                "<": f"moins de {x} que de {y}", "=": f"autant de {x} que de {y}"}[m[2]]
    m = re.fullmatch(r"levees (!?[\d+\-=]+)", a)
    if m: return f"{_zone(m[1], 'levées de jeu')}"
    m = re.fullmatch(r"arret (\w+)", a)
    if m: return f"un arrêt {_nom_contexte(m[1]) or m[1]}"
    m = re.fullmatch(r"bonne (\w+)", a)
    if m: return f"une bonne couleur {_nom_contexte(m[1]) or m[1]}"
    m = re.fullmatch(r"fit\((\w+)\) (!?[\d+\-=]+)", a)
    if m: return f"{_zone(m[2], 'cartes')} {_nom_contexte(m[1]) or m[1]} à nous deux"
    m = re.fullmatch(r"([UWYZ]) est ([TKCP])", a)
    if m: return f"la couleur {JOUEUR[m[1]]} est {NOM_COUL[m[2]][0]}"
    m = re.fullmatch(r"palier\((\w+)\) (!?[\d+\-=]+)", a)
    if m: return f"palier {_zone(m[2]) or m[2]} {_nom_contexte(m[1]) or m[1]}"
    return None


def _decouper(texte, sep):
    """Coupe au séparateur hors des parenthèses."""
    out, prof, cour, i = [], 0, "", 0
    while i < len(texte):
        if texte.startswith(sep, i) and prof == 0:
            out.append(cour); cour = ""; i += len(sep); continue
        c = texte[i]
        prof += (c == "(") - (c == ")")
        cour += c; i += 1
    out.append(cour)
    return [x.strip() for x in out]


def condition(texte, definitions=()):
    """Une condition entière en français : « , » → « et », « || » → « ou », les parenthèses gardées. Ce qui n'est pas
    reconnu reste écrit tel quel (en police de code)."""
    texte = str(texte or "").strip()
    if not texte: return "dans tous les autres cas"
    ou = _decouper(texte.replace(" ou ", " || "), "||")
    if len(ou) > 1: return " <b>ou</b> ".join(condition(x, definitions) for x in ou)
    et = _decouper(texte, ",")
    if len(et) > 1: return ", ".join(condition(x, definitions) for x in et)
    t = texte
    if t.startswith("non (") and t.endswith(")"): return "pas : (" + condition(t[5:-1], definitions) + ")"
    if t.startswith("(") and t.endswith(")"): return "(" + condition(t[1:-1], definitions) + ")"
    a = atome(t, definitions)
    return a if a else f"<code>{html.escape(t)}</code>"


# ---------------------------------------------------------------- une main d'exemple
def main_html(main):
    """« A765 AX43 A982 3 » (piques, cœurs, carreaux, trèfles) → ♠A765 ♥AX43 ♦A982 ♣3, cœurs et carreaux en rouge."""
    parts = str(main).split()
    out = []
    for c, r in zip("♠♥♦♣", parts + [""] * (4 - len(parts))):
        r = "—" if r in ("-", "") else r.replace("X", "10")
        coul = " class='rouge'" if c in "♥♦" else ""
        out.append(f"<span{coul}>{c}{r}</span>")
    return " ".join(out)


# ---------------------------------------------------------------- la page d'une famille
CSS = """
.syst { font-size: 16px; color: var(--bc-tapis-900); max-width: 980px; }
/* les titres d'un document sous le titre de la page (22) : 18 comme une section, puis 16 (l'utilisateur, 2026-11-17) */
.syst.aide h1, .syst.aide h2 { font-size: var(--fs-titre); color: var(--bc-trefle-800); margin: 1.2em 0 .4em; line-height: 1.3; }
.syst.aide h3, .syst.aide h4 { font-size: var(--fs-texte); color: var(--bc-tapis-900); font-weight: 700; margin: 1em 0 .3em; }
.syst .carton-s { display: inline-flex; align-items: center; justify-content: center; min-width: 40px; height: 28px;
  padding: 0 var(--sp-2); border-radius: 5px; border: 1px solid var(--bc-tapis-300); background: var(--bc-blanc);
  font-weight: 700; font-size: 16px; color: var(--bc-tapis-900); white-space: nowrap; }
.syst .carton-s.rouge, .rouge { color: var(--bc-coeur-600); }   /* ♥ ♦ en rouge, partout où rouge() les met */
.syst .carton-s.adv { background: var(--bc-tapis-100); color: var(--bc-tapis-600); font-weight: 600; }
.syst .carton-s.attente { border-style: dashed; color: var(--bc-tapis-400); }
.syst .seq { display: inline-flex; gap: var(--sp-1); align-items: center; flex-wrap: wrap; }
.syst .sequence { border: 1px solid var(--bc-tapis-200); border-radius: 12px; padding: var(--sp-3); margin: 0 0 var(--sp-3);
  background: var(--bc-blanc); scroll-margin-top: 80px; }
.syst .sequence.vise { border-color: var(--bc-trefle-600); box-shadow: 0 0 0 2px var(--bc-trefle-200); }
.syst .regle { display: grid; grid-template-columns: 64px minmax(0, 1fr) auto; gap: var(--sp-3); align-items: start;
  padding: var(--sp-2) 0; border-top: 1px solid var(--bc-tapis-200); }
.syst .montre { font-size: 17px; }
.syst .cond { font-size: 15px; color: var(--bc-tapis-700); margin-top: 2px; }
.syst .cond code { font-size: 14px; background: var(--bc-tapis-100); padding: 0 4px; border-radius: 4px; }
.syst .badges { display: flex; gap: var(--sp-1); flex-wrap: wrap; justify-content: flex-end; }
.syst .badge { font-size: 13px; padding: 2px 8px; border-radius: 6px; white-space: nowrap; font-weight: 600; }
.syst .b-conv { background: var(--bc-pique-100); color: var(--bc-pique-800); }
.syst .b-alerte { background: var(--bc-pique-800); color: var(--bc-blanc); }
.syst .b-conf { background: var(--bc-jaune-100); color: var(--bc-jaune-800); }
.syst .b-sa { background: var(--bc-carreau-100); color: var(--bc-carreau-800); }
.syst .b-nat { background: var(--bc-tapis-100); color: var(--bc-tapis-700); font-weight: 400; }
.syst .suite { font-size: 14px; color: var(--bc-trefle-700); cursor: pointer; text-decoration: underline; margin-top: 2px;
  display: inline-block; }
.syst .exemples { margin-top: var(--sp-2); padding: var(--sp-2) var(--sp-3); background: var(--bc-tapis-50); border-radius: 8px;
  font-size: 15px; }
.syst .exemples div { margin: 2px 0; }
.syst h3 { font-size: 18px; font-weight: 700; margin: var(--sp-4) 0 var(--sp-2); }
.syst .note { font-size: 14px; color: var(--bc-tapis-700); font-style: italic; }
"""


def regle_html(r, cle, ix, definitions):
    badges = []
    if r["nom"]: badges.append(f"<span class='badge b-conv'>{html.escape(str(r['nom']).strip().capitalize())}</span>")
    if r["alerte"]: badges.append("<span class='badge b-alerte'>Alerte</span>")
    src = str(r["source"]).lower()
    if "confirmer" in src: badges.append("<span class='badge b-conf' title='Pas encore vérifié dans le livret FFB'>À confirmer</span>")
    elif src == "sa": badges.append("<span class='badge b-sa' title='Emprunté au Standard américain'>Standard américain</span>")
    if r["nature"] in NATURE: badges.append(f"<span class='badge b-nat'>{NATURE[r['nature']]}</span>")
    k = suite(ix, cle, r["enchere"])
    lien = (f"<span class='suite' data-vers='{ancre(k[0])}'>La suite : {rouge(html.escape(k[1]))} →</span>" if k else "")
    note = f"<div class='note'>{rouge(html.escape(str(r['note'])))}</div>" if r["note"] else ""
    apres = f" <span class='note'>(seulement après {rouge(html.escape(sequence_texte(jetons(str(r['apres'])))))})</span>" if r["apres"] else ""
    montre = rouge(html.escape(str(r["montre"]))) or "&nbsp;"
    return (f"<div class='regle'><div>{enchere_html(r['enchere'])}</div>"
            f"<div><div class='montre'>{montre}{apres}</div><div class='cond'>{condition(r['si'], definitions)}</div>{note}{lien}</div>"
            f"<div class='badges'>{''.join(badges)}</div></div>")


def sequence_bloc(cle, regles, exemples, ix, definitions):
    ex = ""
    if exemples:
        lignes = []
        for e in exemples:
            if not isinstance(e, dict) or "main" not in e: continue
            plus = []
            if e.get("position"): plus.append(f"en {e['position']}{'re' if str(e['position']) == '1' else 'e'} position")
            if e.get("apres"): plus.append(f"après {rouge(html.escape(sequence_texte(jetons(str(e['apres'])))))}")
            if e.get("vul"): plus.append(atome(str(e["vul"])) or str(e["vul"]))
            if e.get("partenaire"): plus.append(f"partenaire : {rouge(html.escape(str(e['partenaire'])))}")
            lignes.append(f"<div>{main_html(e['main'])} → {enchere_html(e.get('attendu', ''))}"
                          + (f" <span class='note'>{', '.join(plus)}</span>" if plus else "") + "</div>")
        if lignes:
            ex = ("<div class='exemples'><div class='note'>Exemples, vérifiés à chaque lancement : avec cette main, le robot "
                  "fait cette enchère.</div>" + "".join(lignes) + "</div>")
    return (f"<div class='sequence' id='{ancre(cle)}'><div style='margin-bottom:var(--sp-2)'>{sequence_html(cle)}</div>"
            + "".join(regle_html(r, cle, ix, definitions) for r in regles) + ex + "</div>")


def page_famille(cle_famille, s=None):
    """Le HTML d'une famille : ses intertitres, puis chaque séquence."""
    s = s or lire()
    ix = index(s)
    defs = s["definitions"]
    for k, titre, sections in familles(s):
        if k != cle_famille: continue
        out = [f"<div class='syst'>"]
        out.append("<p class='note' style='font-style:normal;font-size:15px;margin:0 0 var(--sp-3)'>Pour chaque séquence, "
                   "les enchères dans l'ordre où le robot les essaie : il fait la première dont la condition est vraie. "
                   "Ce qui n'est pas décrit ici, il le joue avec ses règles générales.</p>")
        for t, seqs in sections:
            out.append(f"<h3>{rouge(html.escape(t[0].upper() + t[1:]))}</h3>")
            out += [sequence_bloc(c, r, e, ix, defs) for c, r, e in seqs]
        out.append("</div>")
        return "".join(out)
    return "<div class='syst'>Rien dans cette famille.</div>"


def famille_de_cle(cle, s=None):
    s = s or lire()
    for k, _, sections in familles(s):
        if any(c == cle for _, seqs in sections for c, _, _ in seqs): return k
    return None


def chercher(texte, s=None):
    """[(clé, famille)] : les séquences dont la clé, une enchère, un nom de convention ou ce qu'elle montre contient le
    texte (une séquence s'écrit aussi avec les symboles : « 1SA 2♣ »)."""
    s = s or lire()
    t = texte.strip().lower()
    if not t: return []
    for l, c in COUL.items(): t = t.replace(c.lower(), l.lower())
    t_seq = " ".join(re.findall(r"\(?[^\s\-]+\)?", t))
    out = []
    for k, _, sections in familles(s):
        for _, seqs in sections:
            for cle, regles, _ in seqs:
                c = cle.lower().replace(" - ", " ")
                if t_seq and t_seq in c or any(t in str(r["nom"]).lower() or t in str(r["montre"]).lower() for r in regles):
                    out.append((cle, k))
    return out


DATE = r"20\d\d-\d\d-\d\d"


def pour_membres(t):
    """Un document du système tel que le lit un membre (l'utilisateur, 2026-11-17) : sans ce qui sert au développement,
    les noms de fichiers et de fonctions, les dates de travail, les mesures du banc d'essai. Les règles et les
    « (à confirmer) » restent. Le fichier, lui, ne change pas : Claude le lit tel quel."""
    paras = re.split(r"\n[ \t]*\n", t)
    paras = [p for p in paras if p.lstrip().startswith("#") or not re.search(r"Modifier les deux ensemble|que le programme lit", p)]
    t = "\n\n".join(paras)
    t = re.sub(r"\s+dans\s+`ffb/`", "", t)                                      # « à vérifier dans ffb/ » : à vérifier
    t = re.sub(r"[^.\n]*:\s*voir\s+`[^`]+`\.?[ \t]*", "", t)                     # « Conventions jouées : voir conventions.md. »
    t = re.sub(r"\s*Pour faire passer[^.]*`[^`]+\.yaml`\.", "", t)
    t = re.sub(r"Le moteur : regles\.yaml[^.]*\.\s*", "", t)
    t = re.sub(r"[ \t]*\([^()]*(?:" + DATE + r"|src/|`)[^()]*\)", "", t)         # (2026-11-14), (`stayman.md`), (… src/x.py)
    t = re.sub(r"[ \t]*Mesuré le " + DATE + r"[^.]*\.", "", t)                   # les mesures du banc d'essai
    return re.sub(r"`([^`]+)`", r"\1", t)


def lire_doc(nom):
    """Un document du système (systeme.md, entames.md, conventions/stayman.md…), sans les liens relatifs ni les notes
    de développement (pour_membres)."""
    for f in (os.path.join(SYSTEMES, SYSTEME, nom), os.path.join(SYSTEMES, nom)):
        if os.path.exists(f):
            t = pour_membres(open(f, encoding="utf-8").read())
            return rouge(re.sub(r"\[([^\]]+)\]\([^)]+\.md\)", r"\1", t))   # ♥ ♦ en rouge, même dans le markdown
    return ""


CONVENTIONS = (("stayman", "Stayman", "conventions/stayman.md"), ("texas", "Texas", "conventions/texas.md"),
               ("blackwood", "Blackwood 3041", "conventions/blackwood-3041.md"), ("drury", "Drury", "conventions/drury.md"),
               ("roudi", "Roudi", "conventions/roudi.md"), ("bicolores", "Bicolores (Michaels)", "conventions/bicolores.md"),
               ("landy", "Défense contre 1SA", "conventions/landy.md"))


# le nom d'une page de convention → le « nom: » de ses règles dans regles.yaml (Blackwood : le code, pas de règle)
NOM_REGLES = {"stayman": "Stayman", "texas": "Texas", "drury": "Drury", "roudi": "Roudi", "bicolores": "Bicolores",
              "landy": "Landy"}


def regles_convention(cle, s=None):
    """Sous le texte d'une convention : les séquences du fichier de règles où les robots la jouent, avec leurs mains
    d'exemple vérifiées (2026-11-20 : montrer le système avec des mains, en nos mots). "" sans règle nommée."""
    nom = NOM_REGLES.get(cle)
    if not nom: return ""
    s = s or lire()
    ix = index(s); defs = s["definitions"]
    blocs = [sequence_bloc(c, r, e, ix, defs) for _, seqs in s["sections"] for c, r, e in seqs
             if any(str(x.get("nom") or "").strip().lower() == nom.lower() for x in r)]
    if not blocs: return ""
    return ("<div class='syst'><h3>Comme les robots la jouent</h3><p class='note' style='font-style:normal;font-size:15px;"
            "margin:0 0 var(--sp-3)'>Chaque séquence où la convention intervient, avec les mains d'exemple que le "
            "programme vérifie à chaque lancement.</p>" + "".join(blocs) + "</div>")


def compter(s=None):
    """(séquences, enchères décrites, exemples) : pour la vue d'ensemble."""
    s = s or lire()
    seqs = [x for _, l in s["sections"] for x in l]
    return len(seqs), sum(len(r) for _, r, _ in seqs), sum(len(e) for _, _, e in seqs)
