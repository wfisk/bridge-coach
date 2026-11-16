# -*- coding: utf-8 -*-
"""Une page « Donne n°N » du site de la FFB imprimée en PDF (2026-11-16 : un membre l'avait prise pour une feuille de
route) : les quatre mains, le donneur, la vulnérabilité, le « Score optimum » et la « Fiche ambulante » (les tables),
lus dans le PDF puis donnés à l'importeur des pages de la FFB (ffb_html.seance, pages=…), qui en fait la séance.

Le texte se lit avec pdfium, caractère par caractère (sa ligne de base : les lettres à jambage, comme le « q » de
« Dominique », restent dans leur mot). Les symboles de couleur ne sont pas du texte : de petits dessins de 10,5 points
(des « form XObjects » dont pdfium ne montre pas le contenu). Leur couleur se lit sur la page rendue : ♠ noir, ♥ rouge,
♦ orange (et moins rempli : le losange est plus fin), ♣ vert. Leur place dit à quoi ils servent : devant une ligne de
cartes (une chicane quand rien ne suit), à côté d'un contrat, devant une entame.

Un PDF peut tenir plusieurs donnes ; une donne peut finir sur la page suivante (la fiche ambulante continue, les noms
d'une table coupée en haut de la page suivante). Aucun nom de club n'est gardé, comme pour les pages HTML."""
import ctypes, os, re, sys

import pypdfium2 as pdfium
import pypdfium2.raw as raw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # -I : le dossier du script n'est pas dans le chemin
from ffb_html import DONNEUR, VUL, ErreurFFB, RANG_EN

RANGS = {"A", "R", "D", "V", "10", "9", "8", "7", "6", "5", "4", "3", "2"}
ECHELLE = 4                                                # le rendu pour lire la couleur des symboles
COLONNES = (("TABLE", "table"), ("NORD", "ns"), ("EST", "eo"), ("CONTR", "contrat"), ("DÉCL", "decl"), ("ENT", "entame"),
            ("RÉS", "res"), ("SCORE NS", "score_ns"), ("SCORE EO", "score_eo"), ("NOTE NS", "note_ns"), ("NOTE EO", "note_eo"))


class Mot:
    def __init__(self, texte, x0, x1, y, h):
        self.texte, self.x0, self.x1, self.y, self.h = texte, x0, x1, y, h      # y : la ligne de base, depuis le haut

    @property
    def xc(self): return (self.x0 + self.x1) / 2

    def __repr__(self): return f"{self.texte}@({self.x0:.0f},{self.y:.0f})"


class Symbole:
    def __init__(self, couleur, x0, y0, x1, y1):
        self.couleur, self.x0, self.y0, self.x1, self.y1 = couleur, x0, y0, x1, y1

    @property
    def yc(self): return (self.y0 + self.y1) / 2


# ---------------------------------------------------------------- lire une page
def mots(page):
    """Les mots de la page : des caractères voisins sur la même ligne de base."""
    H = page.get_size()[1]
    tp = page.get_textpage()
    out, cour = [], None
    for i in range(tp.count_chars()):
        c = tp.get_text_range(i, 1)
        if not c or c in "\x00\r\n": continue
        l, b, r, t = tp.get_charbox(i)
        ox, oy = ctypes.c_double(), ctypes.c_double()
        raw.FPDFText_GetCharOrigin(tp.raw, i, ox, oy)
        base = H - oy.value
        if c.isspace():
            if cour: out.append(cour); cour = None
            continue
        if cour and abs(base - cour.y) < 1.5 and l - cour.x1 < 2.5:
            cour.texte += c; cour.x1 = r
        else:
            if cour: out.append(cour)
            cour = Mot(c, l, r, base, t - b)
    if cour: out.append(cour)
    return out


def _couleur(rgb, rempli):
    """♠ ♥ ♦ ♣ d'après la couleur dominante du symbole et la part de sa case qu'il remplit."""
    r, g, b = rgb
    if g > r and g > b: return "♣"
    if r < 80 and g < 80 and b < 80: return "♠"
    if r > 150 and g < 70: return "♥"
    if r > 150 and g >= 70: return "♦"
    return "♦" if rempli < 0.44 else "♥"


def symboles(page):
    """Les symboles de couleur de la page (les petits dessins de 6 à 14 points), avec leur couleur."""
    H = page.get_size()[1]
    img = None
    out = []
    for i in range(raw.FPDFPage_CountObjects(page.raw)):
        o = raw.FPDFPage_GetObject(page.raw, i)
        if raw.FPDFPageObj_GetType(o) != raw.FPDF_PAGEOBJ_FORM: continue
        l, b, r, t = (ctypes.c_float() for _ in range(4))
        raw.FPDFPageObj_GetBounds(o, l, b, r, t)
        x0, x1, y0, y1 = l.value, r.value, H - t.value, H - b.value
        if not (6 <= x1 - x0 <= 14 and 6 <= y1 - y0 <= 14): continue
        if img is None: img = page.render(scale=ECHELLE).to_pil().convert("RGB")
        case = img.crop((int(x0 * ECHELLE), int(y0 * ECHELLE), int(x1 * ECHELLE), int(y1 * ECHELLE)))
        px = [p for p in case.getdata() if sum(p) < 600]
        if not px: continue
        m = [sum(p[k] for p in px) / len(px) for k in range(3)]
        out.append(Symbole(_couleur(m, len(px) / (case.size[0] * case.size[1])), x0, y0, x1, y1))
    return out


def lignes(ms, tol=3.0):
    """Les mots rangés par lignes (même ligne de base), de haut en bas, chacune de gauche à droite."""
    out = []
    for m in sorted(ms, key=lambda m: (m.y, m.x0)):
        if out and abs(out[-1][0].y - m.y) < tol: out[-1].append(m)
        else: out.append([m])
    return [sorted(l, key=lambda m: m.x0) for l in out]


def texte_ligne(l):
    return " ".join(m.texte for m in l)


# ---------------------------------------------------------------- une donne
def _entete(ms):
    """(numéro, club, titre, donneur, vul) depuis le haut de la page, ou None si ce n'est pas une page « Donne n° »."""
    ls = lignes(ms)
    k = next((i for i, l in enumerate(ls) if re.match(r"Donne\s*n\s*°\s*\d+", texte_ligne(l))), None)
    if k is None: return None
    n = int(re.search(r"(\d+)\s*$", re.match(r"Donne\s*n\s*°\s*\d+", texte_ligne(ls[k]))[0])[1])
    club = texte_ligne(ls[k + 1]) if k + 1 < len(ls) else ""
    titre = texte_ligne(ls[k + 2]) if k + 2 < len(ls) else ""

    def apres(etiquette):
        """Le texte sous une étiquette (« Donneur », « Vulnérabilité ») : les lignes suivantes, dans sa colonne."""
        m = next((m for m in ms if m.texte.lower().startswith(etiquette)), None)
        if not m: return ""
        sous = [x for x in ms if m.y + 3 < x.y < m.y + 30 and x.x1 > m.x0 - 30 and x.x0 < m.x1 + 30]
        return texte_ligne(sorted(sous, key=lambda x: (round(x.y), x.x0)))
    donneur = DONNEUR.get(apres("donneur").split(" ")[0].lower()) if apres("donneur") else None
    v = " ".join(apres("vulnérabilité").lower().replace("-", " - ").split())
    return n, club, titre, donneur, VUL.get(v)


def _mains(ms, syms, bas_mains):
    """{N, E, S, O: [♠, ♥, ♦, ♣]} : quatre colonnes de quatre symboles au-dessus de la fiche ambulante."""
    cols = {}
    for s in syms:
        if s.y0 >= bas_mains or s.x0 > 280: continue
        cols.setdefault(round(s.x0), []).append(s)
    mains = []
    for x, ss in cols.items():
        ss.sort(key=lambda s: s.y0)
        while len(ss) >= 4:                                # une colonne peut porter deux mains (Nord et Sud)
            bloc, ss = ss[:4], ss[4:]
            if [s.couleur for s in bloc] != list("♠♥♦♣") or bloc[3].y0 - bloc[0].y0 > 80: continue
            rangees = []
            for s in bloc:
                ligne = sorted((m for m in ms if abs((m.y - m.h / 2) - s.yc) < 6 and m.x0 > s.x1), key=lambda m: m.x0)
                cartes, bord = [], s.x1
                for m in ligne:
                    if m.texte.upper() not in RANGS or m.x0 - bord > 20: break
                    cartes.append("X" if m.texte == "10" else m.texte.upper()); bord = m.x1
                rangees.append("".join(cartes))
            mains.append((x, bloc[0].y0, rangees))
    if len(mains) != 4: raise ErreurFFB(f"Les quatre mains ne se lisent pas sur la page ({len(mains)} trouvées).")
    mains.sort(key=lambda m: m[1])
    nord, sud = mains[0], mains[-1]
    ouest, est = sorted(mains[1:3], key=lambda m: m[0])
    return {"N": nord[2], "O": ouest[2], "E": est[2], "S": sud[2]}


def _optimum(ms, syms):
    """Le « Score optimum » : {N, S, E, O: {♣, ♦, ♥, ♠, SA: levées}}, ou {}."""
    titre = next((m for m in ms if m.texte == "Score"), None)
    if not titre: return {}
    tete = [s for s in syms if titre.y < s.y0 < titre.y + 40 and s.x0 > titre.x0 - 30]   # pas les mains, à gauche
    sa = next((m for m in ms if m.texte == "SA" and titre.y < m.y < titre.y + 40 and m.x0 > titre.x0), None)
    if len(tete) != 4 or not sa: return {}
    cols = [(s.couleur, (s.x0 + s.x1) / 2) for s in tete] + [("SA", sa.xc)]
    out = {}
    for l in lignes([m for m in ms if titre.y + 15 < m.y < titre.y + 150 and m.x0 > titre.x0 - 30]):
        if l[0].texte not in ("N", "S", "E", "O"): continue
        v = {}
        for m in l[1:]:
            if m.texte.isdigit():
                c = min(cols, key=lambda c: abs(c[1] - m.xc))
                v[c[0]] = int(m.texte)
        if len(v) == 5: out[l[0].texte] = v
    return out


def _bornes(ms):
    """Les colonnes de la fiche ambulante, d'après la ligne de titres : [(nom, début)], ou None sans fiche sur la page."""
    tete = next((l for l in lignes(ms) if texte_ligne(l).startswith("TABLE")), None)
    if not tete: return None, None
    t = texte_ligne(tete)
    bornes = []
    for mot, nom in COLONNES:
        m = next((m for m in tete if m.texte.upper().startswith(mot.split()[0]) and nom not in dict(bornes).values()
                  and (len(mot.split()) == 1 or mot.split()[1] in texte_ligne([x for x in tete if x.x0 >= m.x0][:3]))), None)
        if m: bornes.append((m.x0 - 8, nom))
    if "CONTR" not in t: return None, None
    return sorted(bornes), tete[0].y


def _colonne(bornes, x):
    nom = None
    for debut, n in bornes:
        if x >= debut: nom = n
    return nom


def _tables(pages):
    """Les lignes de la fiche ambulante sur les pages de la donne : [{ns, eo, contrat, declarant, entame, resultat,
    score_ns, score_eo, note_ns}] ; les noms coupés en bas d'une page continuent en haut de la suivante."""
    rangs = []
    for k_page, (ms, syms) in enumerate(pages):
        bornes, y_tete = _bornes(ms)
        if not bornes: continue
        corps = [m for m in ms if m.y > y_tete + 4]
        ancres = sorted((m for m in corps if _colonne(bornes, m.xc) == "contrat"
                         and re.fullmatch(r"[1-7]|passe|PASSE|Passe|PASS", m.texte)), key=lambda m: m.y)
        ancres = [a for k, a in enumerate(ancres) if not k or a.y - ancres[k - 1].y > 8]
        haut = ancres[0].y - 6 if ancres else 1e9
        if rangs:                                          # le haut de page : la fin des noms de la table d'avant
            for m in corps:
                if m.y < haut and _colonne(bornes, m.xc) in ("ns", "eo"): rangs[-1][_colonne(bornes, m.xc)].append((k_page, m))
        for k, a in enumerate(ancres):
            bas = ancres[k + 1].y - 6 if k + 1 < len(ancres) else 1e9
            bande = [m for m in corps if a.y - 6 <= m.y < bas]
            sur = [m for m in bande if abs(m.y - a.y) < 3]
            r = {"ns": [], "eo": []}
            for m in bande:
                c = _colonne(bornes, m.xc)
                if c in ("ns", "eo"): r[c].append((k_page, m))
            cell = lambda nom: [m for m in sur if _colonne(bornes, m.xc) == nom]
            sym = lambda nom: next((s for s in syms if abs(s.yc - (a.y - a.h / 2)) < 7 and _colonne(bornes, (s.x0 + s.x1) / 2) == nom), None)
            con = " ".join(m.texte for m in cell("contrat"))
            if re.match(r"pass", con, re.I): contrat = "PASS"
            else:
                m = re.match(r"([1-7])\s*(SA)?", con)
                s = sym("contrat")
                den = "NT" if m and m[2] else {"♠": "S", "♥": "H", "♦": "D", "♣": "C"}.get(s.couleur) if s else None
                x = re.sub(r"[^X]", "", con.upper().replace("SA", ""))
                contrat = f"{m[1]} {den}" + {"": "", "X": " x", "XX": " xx"}.get(x, "") if m and den else None
            dec = "".join(m.texte for m in cell("decl")).upper()[:1]
            s_ent = sym("entame"); rang = "".join(m.texte for m in cell("entame")).upper()
            entame = ({"♠": "S", "♥": "H", "♦": "D", "♣": "C"}[s_ent.couleur] + ("T" if rang == "10" else rang.translate(RANG_EN))
                      if s_ent and rang in RANGS else "")
            num = lambda nom: _nombre(" ".join(m.texte for m in cell(nom)))
            r.update(contrat=contrat, declarant=dec if dec in "NESO" and dec else "", entame=entame,
                     resultat="".join(m.texte for m in cell("res")).replace("–", "-").replace("−", "-"),
                     score_ns=num("score_ns"), score_eo=num("score_eo"), note_ns=num("note_ns"))
            rangs.append(r)
    out = []
    for r in rangs:
        noms = {}
        for c in ("ns", "eo"):
            t = " ".join(m.texte for _, m in sorted(r[c], key=lambda pm: (pm[0], round(pm[1].y), pm[1].x0)))   # page, puis ligne
            noms[c] = [x.strip() for x in re.split(r"\s+-\s+|\s+-$|^-\s+", " ".join(t.split())) if x.strip()]
        out.append(dict(id=None, ns=noms["ns"], eo=noms["eo"], **{k: v for k, v in r.items() if k not in ("ns", "eo")}))
    return out


def _nombre(t):
    t = t.replace(" ", "").replace("%", "").replace(",", ".").replace("—", "")
    try: return float(t)
    except ValueError: return None


def lire(chemin):
    """(référence, club, titre, donnes, paires {}) comme ffb_html.lire_pages : chaque donne du PDF."""
    try:
        doc = pdfium.PdfDocument(chemin)
    except Exception as ex:
        raise ErreurFFB("Ce PDF ne se lit pas.") from ex
    donnes, courante, club, titre = [], None, "", ""
    for k in range(len(doc)):
        page = doc[k]
        ms, syms = mots(page), symboles(page)
        e = _entete(ms)
        if e:                                              # une nouvelle donne commence sur cette page
            n, cl, ti, donneur, vul = e
            club, titre = club or cl, titre or ti
            bornes, y_tete = _bornes(ms)
            bas = y_tete - 20 if y_tete else 1e9
            fiche = next((m for m in ms if m.texte.startswith("Fiche")), None)
            if fiche: bas = min(bas, fiche.y - 10)
            courante = dict(n=n, donneur=donneur, vul=vul, mains=_mains(ms, syms, bas), optimum=_optimum(ms, syms), pages=[])
            donnes.append(courante)
        if courante is not None: courante["pages"].append((ms, syms))
    if not donnes: raise ErreurFFB("Ce PDF n'est pas une page « Donne n° » du site de la FFB.")
    for d in donnes:
        d["lignes"] = _tables(d.pop("pages"))
        for s, m in d["mains"].items():
            if sum(len(x) for x in m) != 13:
                raise ErreurFFB(f"Donne {d['n']} : la main de {s} n'a pas 13 cartes ({' '.join(x or '-' for x in m)}).")
    return "", club, titre, donnes, {}


def est_page_ffb(chemin):
    """Ce PDF est-il une page « Donne n° » du site de la FFB (et non une feuille de route FFBClubNet) ?"""
    try:
        doc = pdfium.PdfDocument(chemin)
        t = doc[0].get_textpage().get_text_range()
    except Exception:
        return False
    return bool(re.search(r"Donne\s*n\s*°\s*\d+", t)) and "Fiche ambulante" in t


def seance(chemin):
    """La séance Bridge Coach de ce PDF, par l'importeur des pages de la FFB."""
    import ffb_html
    return ffb_html.seance(chemin, pages=lire(chemin))


if __name__ == "__main__":
    import json
    _, club, titre, donnes, _ = lire(sys.argv[1])
    print(titre)
    for d in donnes:
        print(json.dumps({k: v for k, v in d.items() if k != "lignes"}, ensure_ascii=False))
        for l in d["lignes"]: print("  ", l)
