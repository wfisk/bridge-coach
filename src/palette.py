# -*- coding: utf-8 -*-
"""La palette de Bridge Coach (l'utilisateur, 2026-11-16) : comme Bootstrap, quelques couleurs de base, chacune déclinée
en dix nuances (50 à 900), puis des noms de rôle (primary, success, danger…) qui pointent dedans ; le tout en variables
CSS (--bc-…), pour qu'une couleur ne se choisisse qu'ici.

Les couleurs de base viennent du bridge : la boîte à enchères à quatre couleurs (♣ vert, ♦ orange, ♥ rouge, ♠ bleu),
les cartons (PASS vert, X rouge, XX et ALERT bleus), l'étui (rouge vulnérable, vert non vulnérable), le tapis (un gris
chaud) et le jaune « à vous ». Un seul gris, chaud, comme le tapis.

Les nuances sont calculées en OKLCH : à un même pas, toutes les couleurs ont la même clarté perçue (le 600 du rouge est
aussi clair que le 600 du vert), si bien qu'une règle de contraste vaut pour toutes. Elles s'arrêtent avant le blanc et
le noir (une couleur y perdrait son identité) ; le blanc et le noir purs sont à part (--bc-blanc, --bc-noir). La couleur
de base garde sa valeur exacte, au pas dont la clarté est la plus proche.

La page /design de l'application (pour le développement, sans lien dans les menus) montre tout cela, avec le contraste
de chaque nuance et la carte des couleurs écrites aujourd'hui dans le code. Rien n'utilise encore ces variables."""
import math, os, re
from collections import Counter

PAS = (50, 100, 200, 300, 400, 500, 600, 700, 800, 900)
# la clarté OKLCH de chaque pas, la même pour toutes les couleurs
CLARTE = {50: .975, 100: .945, 200: .89, 300: .82, 400: .73, 500: .64, 600: .55, 700: .47, 800: .39, 900: .31}

# nom, couleur de base, d'où elle vient au bridge
BASES = (
    ("trefle", "#1d7a35", "Trèfle", "♣ de la boîte à enchères, carton PASS, camp non vulnérable"),
    ("coeur", "#c0141c", "Cœur", "♥ ♦ des cartes, carton X (contre), camp vulnérable"),
    ("pique", "#1f3fa0", "Pique", "♠ de la boîte à enchères, cartons XX et ALERT"),
    ("carreau", "#c86a00", "Carreau", "♦ de la boîte à enchères"),
    ("jaune", "#f2b705", "Jaune", "« À vous » : le joueur qui doit jouer, vos cartes à jouer"),
    ("tapis", "#f3efe7", "Tapis", "le tapis de la table, les barres, l'étui : le seul gris, chaud"),
)
NEUTRE = "tapis"
CHROMA_NEUTRE = .012                 # le gris chaud : un soupçon de la teinte du tapis, à tous les pas

# les rôles, comme Bootstrap : (nom, couleur de base, à quoi il sert) ; chaque rôle a aussi -bg-subtle (100),
# -border-subtle (200) et -text-emphasis (800), comme Bootstrap 5.3
ROLES = (
    ("primary", "trefle", "la couleur de l'application : boutons, titres, l'expert"),
    ("success", "trefle", "réussi, gagné, non vulnérable, PASS"),
    ("danger", "coeur", "perdu, vulnérable, contre, carte qui ne peut pas être jouée"),
    ("info", "pique", "alerte, surcontre, renseignement"),
    ("warning", "carreau", "attention, à vérifier ; « vous » dans les graphiques"),
    ("highlight", "jaune", "à qui le tour, vos cartes à jouer"),
)


# --- OKLab / OKLCH (Björn Ottosson) -----------------------------------------------------------------------------------
def _lin(c): return c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
def _gam(c): return 12.92 * c if c <= .0031308 else 1.055 * c ** (1 / 2.4) - .055


def hex_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3: h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb_hex(rgb): return "#" + "".join(f"{round(max(0, min(1, c)) * 255):02x}" for c in rgb)


def oklab(h):
    r, g, b = (_lin(c) for c in hex_rgb(h))
    l = (.4122214708 * r + .5363325363 * g + .0514459929 * b) ** (1 / 3)
    m = (.2119034982 * r + .6806995451 * g + .1073969566 * b) ** (1 / 3)
    s = (.0883024619 * r + .2817188376 * g + .6299787005 * b) ** (1 / 3)
    return (.2104542553 * l + .7936177850 * m - .0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + .4505937099 * s,
            .0259040371 * l + .7827717662 * m - .8086757660 * s)


def oklch(h):
    L, a, b = oklab(h)
    return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def _rgb_lin(L, C, H):
    a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l = (L + .3963377774 * a + .2158037573 * b) ** 3
    m = (L - .1055613458 * a - .0638541728 * b) ** 3
    s = (L - .0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l - 3.3077115913 * m + .2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - .3413193965 * s,
            -.0041960863 * l - .7034186147 * m + 1.7076147010 * s)


def depuis_oklch(L, C, H):
    """La couleur sRGB la plus proche : la chroma baisse jusqu'à ce qu'elle tienne dans l'écran (même clarté, même teinte)."""
    for _ in range(40):
        rgb = _rgb_lin(L, C, H)
        if all(-1e-4 <= c <= 1 + 1e-4 for c in rgb): break
        C *= .93
    return rgb_hex(_gam(max(0, min(1, c))) for c in _rgb_lin(L, C, H))


def ecart(h1, h2):
    """La distance perçue entre deux couleurs (OKLab, × 100 : moins de 2 ne se voit guère)."""
    return 100 * math.dist(oklab(h1), oklab(h2))


# --- le contraste (WCAG) ----------------------------------------------------------------------------------------------
def luminance(h):
    r, g, b = (_lin(c) for c in hex_rgb(h))
    return .2126 * r + .7152 * g + .0722 * b


def contraste(h1, h2):
    a, b = sorted((luminance(h1), luminance(h2)), reverse=True)
    return (a + .05) / (b + .05)


# --- les échelles -----------------------------------------------------------------------------------------------------
def pas_de_base(h):
    """Le pas dont la clarté est la plus proche de celle de la couleur : elle y garde sa valeur exacte."""
    L = oklch(h)[0]
    return min(PAS, key=lambda p: abs(CLARTE[p] - L))


def echelle(nom, base):
    """Les dix nuances d'une couleur : même teinte, la clarté du pas ; la chroma de la base, qui s'éteint vers le clair
    (un 50 est à peine teinté) et un peu vers le sombre."""
    Lb, Cb, H = oklch(base)
    p0 = pas_de_base(base)
    out = {}
    for p in PAS:
        L = CLARTE[p]
        if nom == NEUTRE:
            C = CHROMA_NEUTRE
        elif L > Lb:
            C = Cb * ((1 - L) / (1 - Lb)) ** .9
        else:
            C = Cb * (L / Lb) ** .6
        out[p] = base.lower() if p == p0 else depuis_oklch(L, C, H)
    return out


def echelles():
    return {nom: echelle(nom, base) for nom, base, *_ in BASES}


def role_pas(nom_base):
    """Le pas du rôle : celui de la couleur de base (le tapis : 800, du texte sombre)."""
    base = dict((n, b) for n, b, *_ in BASES)[nom_base]
    return 800 if nom_base == NEUTRE else pas_de_base(base)


def variables():
    """{nom de variable: valeur} : les nuances, le blanc et le noir, les rôles."""
    v = {"--bc-blanc": "#ffffff", "--bc-noir": "#000000"}
    for nom, ech in echelles().items():
        for p, h in ech.items(): v[f"--bc-{nom}-{p}"] = h
    for role, nom, _ in ROLES:
        p = role_pas(nom)
        v[f"--bc-{role}"] = f"var(--bc-{nom}-{p})"
        v[f"--bc-{role}-bg-subtle"] = f"var(--bc-{nom}-100)"
        v[f"--bc-{role}-border-subtle"] = f"var(--bc-{nom}-200)"
        v[f"--bc-{role}-text-emphasis"] = f"var(--bc-{nom}-800)"
    v["--bc-light"] = f"var(--bc-{NEUTRE}-100)"
    v["--bc-dark"] = f"var(--bc-{NEUTRE}-900)"
    v["--bc-body-color"] = f"var(--bc-{NEUTRE}-900)"
    v["--bc-border-color"] = f"var(--bc-{NEUTRE}-200)"
    return v


def css():
    return "<style>:root { " + " ".join(f"{k}: {x};" for k, x in variables().items()) + " }</style>"


# --- les couleurs écrites aujourd'hui dans le code --------------------------------------------------------------------
HEX = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


def toutes_les_nuances():
    """[(variable, hex)] : les nuances, le blanc et le noir."""
    out = [("--bc-blanc", "#ffffff"), ("--bc-noir", "#000000")]
    for nom, ech in echelles().items():
        out += [(f"--bc-{nom}-{p}", h) for p, h in ech.items()]
    return out


def inventaire(fichiers=("app.py",)):
    """Les couleurs écrites en dur dans le code : [(hex, nombre, variable la plus proche, sa valeur, écart)], la plus
    employée d'abord. L'écart dit ce que changerait le passage à la palette (moins de 2 : rien de visible)."""
    ici = os.path.dirname(os.path.abspath(__file__))
    n = Counter()
    for f in fichiers:
        for h in HEX.findall(open(os.path.join(ici, f), encoding="utf-8").read()):
            h = h.lower()
            if len(h) == 4: h = "#" + "".join(c * 2 for c in h[1:])
            n[h] += 1
    nuances = toutes_les_nuances()
    out = []
    for h, k in n.most_common():
        var, val = min(nuances, key=lambda x: ecart(h, x[1]))
        out.append((h, k, var, val, ecart(h, val)))
    return out


# --- la page « Conception de l'interface » (Réglages, Outils de développement) ----------------------------------------
PRINCIPES = (
    ("Une seule proportion : la carte.", "Une carte à jouer fait 2:3 (55 × 82,5 px, coin de 6 px). Le tapis fait huit "
     "largeurs de carte, une main sur un côté quatre ; les coins sont des multiples du coin de la carte."),
    ("Une seule échelle d'espaces.", "Comme Bootstrap : 0,25 / 0,5 / 1 / 1,5 / 3 rem (<code>--sp-1</code> à <code>--sp-5</code>). Jamais 14 px ou "
     "26 px choisis à l'œil."),
    ("Les couleurs viennent du bridge.", "La boîte à enchères (♣ vert, ♦ orange, ♥ rouge, ♠ bleu), les cartons (PASS vert, "
     "X rouge, XX et ALERT bleus), l'étui (rouge vulnérable, vert non vulnérable), le tapis. Le code dit « danger », "
     "jamais « #c62828 »."),
    ("Un seul gris, chaud.", "Celui du tapis, du blanc cassé au presque noir."),
    ("La mise en page au CSS seul.", "Les tailles se connaissent d'avance : rien ne se mesure, rien ne tremble. La table est "
     "une boîte de taille fixe que le CSS met à l'échelle de la fenêtre."),
    ("Lisible de loin.", "Les joueurs sont surtout des seniors et l'écran peut être une télévision : ce qui change (enchères, "
     "résultats, explications) fait 15 à 16 px au moins, en gris foncé ; un texte tient le contraste AA (4,5:1)."),
)

ESPACES = (("--sp-1", ".25rem", 4), ("--sp-2", ".5rem", 8), ("--sp-3", "1rem", 16), ("--sp-4", "1.5rem", 24), ("--sp-5", "3rem", 48))
PROPORTIONS = (
    ("Carte à jouer", "2:3", 55, 82.5, "--carte-l × --carte-h, coin --carte-r"),
    ("Carton d'enchère", "16:9", 89, 50, ".carton.bid"),
    ("PASS, X, XX, STOP, ALERT", "1:1", 50, 50, ".carton.carre, avec son onglet"),
    ("Étui de la donne", "9:16", 135, 240, "debout ; couché quand Nord-Sud sont sur les côtés"),
    ("Tapis", "1:1", 440, 440, "--table-cote = 8 cartes ; plus large (+84) ou plus haut (+100) avec le mort"),
)


def _aa(r):
    return f"<b>{r:.1f}</b>" + (" AA" if r >= 4.5 else " AA grand" if r >= 3 else "")


def html_page():
    """La page, en HTML : principes, puis les fondations (couleurs, rôles, espaces, proportions), puis les couleurs écrites
    aujourd'hui dans le code et la variable qui les remplacerait."""
    h = ["<div style='max-width:1100px;font-size:15px;color:var(--bc-tapis-900)'>"]
    h.append("<p style='margin:0 0 12px'>Les règles de l'interface et ses fondations, en variables CSS (<code>--bc-…</code>, "
             "<code>--sp-…</code>, <code>--carte-…</code>) : une couleur, un espace ou une taille se choisit ici, puis le code s'en sert. Cette page ne se "
             "montre que dans un dépôt Git (le développement), pas chez les membres.</p>")
    h.append("<h3 style='font-size:18px;font-weight:700;margin:16px 0 8px'>Principes</h3><ol style='list-style:decimal;padding-left:22px;margin:0'>")
    for t, x in PRINCIPES:
        h.append(f"<li style='margin-bottom:6px'><b>{t}</b> {x}</li>")
    h.append("</ol>")

    h.append("<h3 style='font-size:18px;font-weight:700;margin:24px 0 4px'>Fondations · Couleurs</h3>")
    h.append("<p style='margin:0 0 8px'>Dix nuances par couleur, de 50 (presque blanc) à 900 (presque noir), à la même clarté "
             "d'une couleur à l'autre (OKLCH). Encadrée : la couleur de base, gardée exacte. Sous chaque nuance, son contraste "
             "avec du texte blanc (B) et noir (N) ; AA : 4,5 au moins pour un texte courant, « AA grand » : 3, pour un grand "
             "texte.</p>")
    ech = echelles()
    for nom, base, titre, sens in BASES:
        p0 = pas_de_base(base)
        h.append(f"<div style='margin:14px 0 4px'><b style='font-size:16px'>{titre}</b> <code>--bc-{nom}-…</code> "
                 f"<span style='color:var(--bc-tapis-700)'>· base {base} au pas {p0} · {sens}</span></div>")
        h.append("<div style='display:grid;grid-template-columns:repeat(10,1fr);gap:4px'>")
        for p in PAS:
            c = ech[nom][p]
            texte = "#fff" if contraste(c, "#ffffff") >= contraste(c, "#000000") else "#000"
            bord = "outline:3px solid var(--bc-tapis-900);outline-offset:2px;" if p == p0 else ""
            h.append(f"<div><div style='{bord}background:var(--bc-{nom}-{p});color:{texte};border-radius:6px;height:56px;"
                     f"display:flex;align-items:flex-end;padding:4px 6px;font-weight:700'>{p}</div>"
                     f"<div style='font-size:12px;line-height:1.35;margin-top:3px'><code>{c}</code><br>"
                     f"B {_aa(contraste(c, '#ffffff'))}<br>N {_aa(contraste(c, '#000000'))}</div></div>")
        h.append("</div>")

    h.append("<h3 style='font-size:18px;font-weight:700;margin:24px 0 4px'>Fondations · Rôles</h3>")
    h.append("<p style='margin:0 0 8px'>Comme Bootstrap : le code nomme un rôle, pas une couleur. Chaque rôle a sa couleur, "
             "un fond léger (-bg-subtle, 100), un bord (-border-subtle, 200) et un texte appuyé (-text-emphasis, 800).</p>")
    h.append("<table style='border-collapse:collapse'>")
    for role, nom, sens in ROLES:
        p = role_pas(nom)
        h.append(f"<tr><td style='padding:6px 10px 6px 0'><code>--bc-{role}</code></td>"
                 f"<td style='padding:6px 10px'><span style='display:inline-block;width:56px;height:28px;border-radius:6px;"
                 f"vertical-align:middle;background:var(--bc-{role})'></span> {nom} {p}</td>"
                 f"<td style='padding:6px 10px'><span style='display:inline-block;padding:4px 10px;border-radius:6px;"
                 f"background:var(--bc-{role}-bg-subtle);border:1px solid var(--bc-{role}-border-subtle);"
                 f"color:var(--bc-{role}-text-emphasis);font-weight:600'>Un message {role}</span></td>"
                 f"<td style='padding:6px 10px;color:var(--bc-tapis-700)'>{sens}</td></tr>")
    h.append("</table>")

    h.append("<h3 style='font-size:18px;font-weight:700;margin:24px 0 4px'>Fondations · Espaces</h3>"
             "<div style='display:flex;gap:24px;align-items:flex-end'>")
    for v, rem, px in ESPACES:
        h.append(f"<div><div style='width:var({v});height:var({v});background:var(--bc-trefle-300)'></div>"
                 f"<div style='font-size:13px;margin-top:4px'><code>{v}</code><br>{rem} · {px} px</div></div>")
    h.append("</div>")

    h.append("<h3 style='font-size:18px;font-weight:700;margin:24px 0 4px'>Fondations · Proportions</h3>"
             "<div style='display:flex;gap:28px;align-items:flex-end;flex-wrap:wrap'>")
    for nom, r, l, ht, note in PROPORTIONS:
        k = .4 if l > 200 or ht > 200 else 1
        h.append(f"<div style='width:{max(110, l * k):.0f}px'><div style='width:{l * k:.0f}px;height:{ht * k:.0f}px;"
                 f"border:1px solid var(--bc-tapis-400);border-radius:6px;background:var(--bc-tapis-100)'></div>"
                 f"<div style='font-size:13px;margin-top:4px'><b>{nom}</b> · {r}<br>{l:g} × {ht:g} px<br>"
                 f"<span style='color:var(--bc-tapis-700)'>{note}</span></div></div>")
    h.append("</div>")

    inv = inventaire()
    h.append("<h3 style='font-size:18px;font-weight:700;margin:24px 0 4px'>Les couleurs écrites aujourd'hui dans le code</h3>")
    h.append(f"<p style='margin:0 0 8px'>src/app.py écrit {len(inv)} couleurs différentes en dur. Pour chacune, la nuance la "
             "plus proche de la palette : l'écart dit ce que changerait le passage (moins de 2 : invisible ; 5 et plus : un "
             "vrai changement, à décider). Rien n'est encore remplacé.</p>")
    h.append("<table style='border-collapse:collapse;font-size:14px'><tr style='text-align:left'><th style='padding:4px 8px'>"
             "Aujourd'hui</th><th style='padding:4px 8px'>Fois</th><th style='padding:4px 8px'>Deviendrait</th>"
             "<th style='padding:4px 8px'>Écart</th></tr>")
    pastille = lambda c: (f"<span style='display:inline-block;width:40px;height:20px;border-radius:4px;vertical-align:middle;"
                          f"background:{c};border:1px solid rgba(0,0,0,.15)'></span>")
    for c, n, var, val, e in inv:
        fort = "font-weight:700;color:var(--bc-danger-text-emphasis)" if e >= 5 else ""
        h.append(f"<tr style='border-top:1px solid var(--bc-tapis-200)'><td style='padding:3px 8px'>{pastille(c)} <code>{c}</code></td>"
                 f"<td style='padding:3px 8px'>{n}</td><td style='padding:3px 8px'>{pastille(val)} <code>{var}</code></td>"
                 f"<td style='padding:3px 8px;{fort}'>{e:.1f}</td></tr>")
    h.append("</table></div>")
    return "".join(h)
