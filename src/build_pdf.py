# -*- coding: utf-8 -*-
"""Construit le PDF d'analyse à partir des données du .bws et de l'analyse rédigée.

Usage : python3 build_pdf.py <nom>.bc.json analyse.json sortie.pdf

analyse.json :
{
  "titre_pied": "Analyse des donnes – entraînement du 23 octobre 2026 – Système SEF, marque IMP",   (facultatif)
  "donnes": {
    "6": {
      "enc":   [["–", "–", "2SA", "passe"], ["3♥", "passe", "3♠", "passe"], ...],   # grille Ouest/Nord/Est/Sud
      "notes": "explication des enchères recommandées",
      "plan":  "plan de jeu",
      "comm":  "commentaire sur les contrats joués",
      "encheres_corrigees": {"1": {"encheres": ["1♥", "passe", ...], "note": "pourquoi"}}   (facultatif)
      "entame":  {"joueur": "E", "carte": "♥X"},        # entame recommandée (cercle plein sur le diagramme)
      "defense": "commentaire sur l'entame et la défense",
      "auto":    true          # enchères, plan et entame calculés par le programme (facultatif) :
                               # les notes ne sont alors pas un avis de l'expert
    }, ...
  }
}
Dans les textes : N, S, E, O isolés et N-S / E-O sont écrits en toutes lettres automatiquement ;
<b>…</b> et <br/> sont acceptés ; ♥ et ♦ sont colorés en rouge.
Mise en page : chaque donne commence sur une nouvelle page, deux pages au maximum,
tailles de police fixes (ne jamais réduire).
"""
import sys, os, re, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import moi
TOURS = {}                       # donne -> « Tour 1 · table 4 · … » quand la séance décrit son mouvement (moi.tour_de)
MES = set()                     # les paires de l'utilisateur dans cette séance (moi.py) : leurs lignes sont surlignées
MARQUE_TXT = "IMP"              # la marque de la séance écrite (moi.marque), posée par main
DONNEES_SEANCE = {}             # la séance du rapport (pour le nom de votre paire en tête de la vue d'ensemble)
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph, Table, TableStyle, Spacer,
                                PageBreak, KeepTogether)
from reportlab.platypus.flowables import Flowable

def _font(name):
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", name)  # macOS : polices du projet
    hits = [local] if os.path.exists(local) else glob.glob(f"/usr/share/fonts/**/{name}", recursive=True)
    if not hits: raise SystemExit(f"Police {name} introuvable (installer fonts-dejavu)")
    return hits[0]
pdfmetrics.registerFont(TTFont("DV", _font("DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DVB", _font("DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DVI", _font("DejaVuSans-Oblique.ttf")))
registerFontFamily("DV", normal="DV", bold="DVB", italic="DVI", boldItalic="DVB")

RED, GREEN, INK, GREY = "#c0141c", "#1f5f3a", "#1d2430", "#555b66"
SEAT = {"N": "Nord", "S": "Sud", "E": "Est", "O": "Ouest"}

def suits(t):
    return t.replace("♥", f'<font color="{RED}">♥</font>').replace("♦", f'<font color="{RED}">♦</font>')

def seats(t):
    t = re.sub(r"\bN-S\b", "Nord-Sud", t); t = re.sub(r"\bE-O\b", "Est-Ouest", t)
    t = re.sub(r"(?<![\w♠♥♦♣])([NSEO])(?![\w♠♥♦♣'’])", lambda m: SEAT[m.group(1)], t)
    return t.replace("de Est", "d'Est").replace("de Ouest", "d'Ouest")

def couleur_devant(t):
    """« AR♣ » -> « ♣AR », « le R♠ » -> « le ♠R » : la couleur devant les cartes, comme partout ailleurs dans Bridge Coach
    (l'utilisateur, 2026-11-10). Les contrats (« 4♥ », « 3SA ») ne bougent pas."""
    return re.sub(r"(?<![\wÀ-ÿ♠♥♦♣])([ARDVX]+\d*)([♠♥♦♣])", r"\2\1", t)

def txt(t): return suits(seats(couleur_devant(t)))

MARQUE_AVIS = "<br/><b>Avis de l'expert :</b>"           # le jugement de Claude, après le texte du programme
MARQUE_COACH = "<br/><b>Le conseil du coach :</b>"       # celui du programme (Bridge Coach), avant l'avis de l'expert
# l'avis de l'expert seul est mis en valeur : ✦, fond vert pâle, trait vert ; le conseil du coach est du texte ordinaire,
# sa casquette et son titre en tête (fond None)
AVIS = {"coach": (MARQUE_COACH, "#1f5f3a", None), "expert": (MARQUE_AVIS, "#1f5f3a", "#e6efe9")}
GRILLE = {"reco": ("#e6efe9", "#9fb5a8"), "autre": ("#eef0f2", "#c3c8ce")}   # en-tête, cadre : les enchères recommandées
                                                                            # en vert ; celles du coach à côté, en gris


def decouper_avis(texte):
    """(texte du programme, conseil du coach, avis de l'expert) : les deux avis suivent le texte, le coach d'abord."""
    reste, _, expert = (texte or "").partition(MARQUE_AVIS)
    prog, _, coach = reste.partition(MARQUE_COACH)
    return prog, coach.strip(), expert.strip()

def st(name, **kw):
    b = dict(fontName="DV", textColor=colors.HexColor(INK)); b.update(kw); return ParagraphStyle(name, **b)
S_body = st("b", fontSize=10.5, leading=14.5, alignment=4)   # 10,5 pt : 9,6 était trop petit à lire (l'utilisateur, 2026-11-10)
S_notes = st("n", fontSize=10.2, leading=14)
S_h = st("h", fontName="DVB", fontSize=12, leading=15, textColor=colors.HexColor(GREEN), spaceBefore=5,
         spaceAfter=2, keepWithNext=1)
S_title = st("t", fontName="DVB", fontSize=20, leading=24)
S_sub = st("s", fontSize=10, leading=13, textColor=colors.HexColor(GREY))
S_hand = st("hd", fontSize=11, leading=14.5)
S_cell = st("c", fontSize=9.6, leading=11.8)
S_cellc = st("cc", fontSize=10, leading=12.6, alignment=1)
S_note = st("ni", fontName="DVI", fontSize=9.6, leading=12.2, textColor=colors.HexColor(GREY))

def hand_par(h, label, pts):
    lines = [f"{s}&nbsp;{'—' if p == '-' else p}" for s, p in zip("♠♥♦♣", h.split())]
    return Paragraph(suits(f'<font name="DVB" size="8.5" color="{GREY}">{label} · {pts} H</font><br/>' +
                           "<br/>".join(lines)), S_hand)

def compass(vul):
    cN = RED if vul in ("N-S", "Tous") else GREEN
    cE = RED if vul in ("E-O", "Tous") else GREEN
    t = Table([["", "N", ""], ["O", "", "E"], ["", "S", ""]], colWidths=[0.8*cm]*3, rowHeights=[0.8*cm]*3)
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "DVB", 11), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("BACKGROUND", (1, 0), (1, 0), colors.HexColor(cN)), ("BACKGROUND", (1, 2), (1, 2), colors.HexColor(cN)),
        ("BACKGROUND", (0, 1), (0, 1), colors.HexColor(cE)), ("BACKGROUND", (2, 1), (2, 1), colors.HexColor(cE)),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(INK))]))
    return t

LEAD_INK = colors.Color(0.23, 0.26, 0.31, alpha=0.85)    # gris anthracite (contours)
LEAD_FILL = colors.Color(0.23, 0.26, 0.31, alpha=0.28)   # même gris, transparent (entame recommandée)
SUITS = "♠♥♦♣"

class Main(Flowable):
    """Une main : titre puis quatre lignes de couleur, cartes dessinées une à une.
    marques = {(couleur, carte): {"tables": n, "reco": bool}}"""
    FS, LEAD, GAP = 10.5, 14, 2.6
    def __init__(self, h, label, pts, marques, align="left"):
        super().__init__(); self.h, self.label, self.pts, self.m, self.align = h.split(), label, pts, marques, align
    def _pad(self, mk):
        if not mk: return 0
        n = mk.get("tables", 0)
        return 3 + (2 if n >= 2 else 0) + (1.4 if mk.get("reco") and n else 0)
    def largeur(self):
        """Largeur réelle du bloc (titre et quatre lignes), pour l'aligner."""
        w = pdfmetrics.stringWidth(f"{self.label} · {self.pts} H", "DVB", 8.5)
        for s, cards in zip(SUITS, self.h):
            x = pdfmetrics.stringWidth(s, "DV", self.FS) + 4
            if cards == "-": x += pdfmetrics.stringWidth("—", "DV", self.FS)
            else:
                for card in cards:
                    p = self._pad(self.m.get((s, card)))
                    x += p + pdfmetrics.stringWidth(card, "DV", self.FS) + self.GAP + p
            w = max(w, x)
        return w
    def wrap(self, aw, ah):
        self.width = aw; self.height = self.LEAD * 5 + 6; return aw, self.height
    def draw(self):
        c = self.canv; bw = self.largeur()
        x0 = {"left": 6, "center": (self.width - bw) / 2, "right": self.width - bw - 6}[self.align]
        c.setFont("DVB", 8.5); c.setFillColor(colors.HexColor(GREY))
        c.drawString(x0, self.height - 10, f"{self.label} · {self.pts} H")
        for i, (s, cards) in enumerate(zip(SUITS, self.h)):
            y = self.height - self.LEAD * (i + 2) + 3.5
            red = s in "♥♦"
            c.setFont("DV", self.FS); c.setFillColor(colors.HexColor(RED if red else INK))
            c.drawString(x0, y, s)
            x = x0 + pdfmetrics.stringWidth(s, "DV", self.FS) + 4
            if cards == "-":
                c.setFillColor(colors.HexColor(INK)); c.drawString(x, y, "—"); continue
            for card in cards:
                w = pdfmetrics.stringWidth(card, "DV", self.FS)
                mk = self.m.get((s, card))
                pad = (3 + (2 if mk.get("tables", 0) >= 2 else 0) + (1.4 if mk.get("reco") and mk.get("tables", 0) else 0)) if mk else 0
                x += pad
                cx, cy, r = x + w / 2, y + self.FS * 0.36, 6.2
                if mk:
                    n = mk.get("tables", 0)
                    ro = r + (1.4 if mk.get("reco") and n else 0)   # blanc entre le disque et le contour
                    if mk.get("reco"):
                        c.setFillColor(LEAD_FILL); c.circle(cx, cy, r - 0.4, stroke=0, fill=1)
                    if n:
                        c.setStrokeColor(LEAD_INK); c.setLineWidth(0.9)
                        c.circle(cx, cy, ro, stroke=1, fill=0)
                        if n >= 2: c.circle(cx, cy, ro + 2.2, stroke=1, fill=0)
                c.setFillColor(colors.HexColor(INK))
                c.drawString(x, y, card)
                x += w + self.GAP + pad

def denomination(contrat):
    """'4♥X' -> '♥', '3SA' -> 'SA'"""
    return contrat.lstrip("1234567").rstrip("X")

def contrat_recommande(a):
    """(dénomination, déclarant) du contrat final de la séquence recommandée, ou None."""
    order = ["O", "N", "E", "S"]
    last = None; first = {}
    for r in a.get("enc", []):
        for j, b in enumerate(r):
            if b in ("", "–", "passe", "contre", "surcontre"): continue
            side = "NS" if order[j] in "NS" else "EO"
            last = (denomination(b), side); first.setdefault(last, order[j])
    return (last[0], first[last]) if last else None

def marques_entame(d, a):
    """Repères par joueur : {siège: {(couleur, carte): {...}}}"""
    nxt = {"N": "E", "E": "S", "S": "O", "O": "N"}
    m = {k: {} for k in "NESO"}
    def ajoute(siege, carte, cle):
        if not carte: return
        s, r = carte[0], carte[1:]
        if s not in SUITS or r not in d["mains"][siege].split()[SUITS.index(s)]:
            print(f"ATTENTION donne {d['n']} : entame {carte} absente de la main de {siege}"); return
        e = m[siege].setdefault((s, r), {"tables": 0, "reco": False})
        if cle == "reco": e["reco"] = True
        else: e["tables"] += 1
    rc = contrat_recommande(a)
    for t in d["tables"]:
        if not t.get("entame") or t["levees"] is None: continue
        meme = rc and denomination(t["contrat"]) == rc[0] and t["declarant"] == rc[1]
        if meme or not rc:
            ajoute(nxt[t["declarant"]], t["entame"], "table")
    reco = a.get("entame")
    if reco: ajoute(reco["joueur"], reco["carte"], "reco")
    return m

def diagram(d, a=None):
    a = a or {}
    m, h, mk = d["mains"], d["hcp"], marques_entame(d, a)
    M = lambda k, lab, al: Main(m[k], lab, h[k], mk[k], al)
    t = Table([["", M("N", "Nord", "center"), ""],
               [M("O", "Ouest", "right"), compass(d["vul"]), M("E", "Est", "left")],
               ["", M("S", "Sud", "center"), ""]], colWidths=[4.3*cm, 3.4*cm, 4.3*cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 1), (1, 1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return t

class Legende(Flowable):
    """Légende des repères d'entame (verticale, à droite du diagramme). Sans tables, seule l'entame recommandée."""
    def __init__(self, jouee=True, reco=True): Flowable.__init__(self); self.jouee = jouee; self.reco = reco
    def wrap(self, aw, ah): self.width = aw; return aw, 66
    def draw(self):
        c = self.canv
        c.setFont("DVB", 8.5); c.setFillColor(colors.HexColor(GREY)); c.drawString(0, 56, "Entame")
        items = [("jouée à une table", 1, False), ("jouée à plusieurs tables", 2, False), ("recommandée", 0, True)]
        for i, (lab, n, reco) in enumerate(items):
            if (reco is False and not self.jouee) or (reco and not self.reco): continue   # les faits seulement : pas de recommandée
            y = 38 - i * 17; cx, cy = 9, y + 3
            if reco: c.setFillColor(LEAD_FILL); c.circle(cx, cy, 5.2, stroke=0, fill=1)
            if n:
                c.setStrokeColor(LEAD_INK); c.setLineWidth(0.9); c.circle(cx, cy, 5.2, stroke=1, fill=0)
                if n >= 2: c.circle(cx, cy, 7.4, stroke=1, fill=0)
            c.setFont("DV", 8.5); c.setFillColor(colors.HexColor(GREY)); c.drawString(22, y, lab)

def diagram_legende(d, a):
    t = Table([[diagram(d, a), Legende(bool(d["tables"]), bool(a.get("entame")))]], colWidths=[12.6*cm, 5.0*cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (0, 0), "TOP"), ("VALIGN", (1, 0), (1, 0), "BOTTOM"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return t

def diagram_old(d):
    m, h = d["mains"], d["hcp"]
    t = Table([["", hand_par(m["N"], "Nord", h["N"]), ""],
               [hand_par(m["O"], "Ouest", h["O"]), compass(d["vul"]), hand_par(m["E"], "Est", h["E"])],
               ["", hand_par(m["S"], "Sud", h["S"]), ""]], colWidths=[4.3*cm, 3.4*cm, 4.3*cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 1), (1, 1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return t

def nom(t, camp):
    """Initiales de la paire ('AB/CD') ou, à défaut, son numéro."""
    return t.get(f"nom_{camp}") or str(t[f"paire_{camp}"])

FOND_RECO = "#e6efe9"                 # la ligne du contrat recommandé : le vert pâle de l'avis de l'expert

# ---------------------------------------------------------------- la séance en un coup d'œil (première page)
VOUS_C, RECO_C = "#e67700", "#1f5f3a"      # vous : un rond orange plein ; le contrat recommandé : un losange vert plein (la couleur
                                            # de l'expert) ; une ligne relie les vôtres (pleine), une autre les siens (tirets).
                                            # L'orange reste distinct du vert pour toutes les vues des couleurs (OKLab 17,8+) ; le
                                            # rouge et le bleu pâles gardent leur seul sens : contrat plus haut, plus bas (SENS)
CHAMP_FOND, CHAMP_TRAIT, CHAMP_MED = "#eef0f2", "#b4bbc3", "#7a828c"   # le champ, en retrait : la boîte, ses moustaches, la médiane
PERTE_C, GAIN_C = "#e03131", "#1971c2"     # vous face au champ : la perte en rouge, le gain en bleu (OKLab 21,8+ pour toutes les vues)


def lignes_ensemble(donnes, an, imp=False):
    """Une ligne par donne, vue de votre camp (de Nord-Sud si vous ne l'avez pas jouée) : {n, vous, reco, texte_reco,
    champ: (min, q1, médiane, q3, max)}. Les % du champ sont ceux des tables ; celui du contrat recommandé, son score au
    double mort face aux tables (comparer.pct_face_aux_tables). imp=True : les IMP de chaque table contre le datum (imp_ns)
    au lieu des % ; le contrat recommandé n'a pas d'IMP (reco None)."""
    import statistics
    from comparer import table_recommandee
    out = []
    for d in donnes:
        cle_v = "imp_ns" if imp else "pct_ns"
        tables = [t for t in d.get("tables") or [] if t.get(cle_v) is not None]
        if len(tables) < 2: continue
        camp, t = moi.mon_camp(tables, MES)
        vue = lambda p: None if p is None else (p if camp != "EO" else (-p if imp else 100 - p))
        pcts = sorted(vue(x[cle_v]) for x in tables)
        q1, med, q3 = statistics.quantiles(pcts, n=4, method="inclusive")
        reco = table_recommandee(d, (an.get("donnes") or {}).get(str(d["n"])) or {})
        dire = lambda x: "passe" if x["contrat"] == "passe" else \
            f"{x['contrat']} {SEAT[x['declarant']][0]} {x['resultat'] or '='}".replace("-", "−")
        cle = lambda x: "passe" if x["contrat"] == "passe" else (x["contrat"].rstrip("X"), x["declarant"])
        sens = sens_contrat(cle(t), cle(reco)) if t and reco and cle(t) != cle(reco) else None
        meilleure = moi.ordre(tables, MES)[0]              # la meilleure table, vue de votre camp (de Nord-Sud sinon)
        out.append(dict(n=d["n"], vous=vue(t[cle_v]) if t else None, reco=vue(reco.get("pct_ns")) if reco and not imp else None,
                        texte_vous=dire(t) if t else "", texte_reco=dire(reco) if reco else "", sens=sens,
                        texte_meilleur=dire(meilleure), champ=(pcts[0], q1, med, q3, pcts[-1])))
    return out


def ecart_couleur(signe):
    """L'espace entre vous et le contrat recommandé : orange pâle quand vous êtes au-dessus, vert pâle en dessous."""
    c = colors.HexColor(VOUS_C if signe > 0 else RECO_C)
    return colors.Color(c.red, c.green, c.blue, alpha=.2 if signe > 0 else .16)


def couleur_ligne(qui):
    """La ligne qui relie les donnes : la couleur du symbole, un peu transparente pour laisser voir le champ."""
    c = colors.HexColor(VOUS_C if qui == "vous" else RECO_C)
    return colors.Color(c.red, c.green, c.blue, alpha=.55)


def symbole(D, qui, cx, y):
    """Vous : un rond creux, bord orange épais (2,5 pt) ; le contrat recommandé : un rond vert plein, cerclé de blanc
    (le plein et le creux les distinguent, même sans les couleurs : l'utilisateur, 2026-11-10)."""
    from reportlab.graphics.shapes import Circle
    if qui == "vous":
        D.add(Circle(cx, y, 4.0, fillColor=colors.white, strokeColor=colors.HexColor(VOUS_C), strokeWidth=2.5))
    else:
        D.add(Circle(cx, y, 4.2, fillColor=colors.HexColor(RECO_C), strokeColor=colors.white, strokeWidth=1.2))


def ligne_seance(L, imp=False):
    """La séance entière : votre % (celui de votre paire dans la séance, sinon la moyenne de vos donnes : c'est la même
    chose quand chaque donne compte autant), la moyenne du contrat recommandé sur les mêmes donnes, et le champ des
    paires (leur % de séance). None si vous n'avez joué aucune donne."""
    import statistics
    jouees = [r for r in L if r["vous"] is not None]
    if not jouees: return None
    if imp:                             # en IMP : la barre à votre moyenne par donne, le total écrit à droite
        total = sum(r["vous"] for r in jouees)
        return dict(vous=total / len(jouees), total=total, reco=None, champ=None)
    paires = DONNEES_SEANCE.get("paires") or {}
    officiel = next((p.get("pct") for k, p in paires.items() if k in MES and p.get("pct") is not None), None)
    vous = officiel if officiel is not None else sum(r["vous"] for r in jouees) / len(jouees)
    recos = [r["reco"] for r in jouees if r["reco"] is not None]
    pcts = sorted(p["pct"] for p in paires.values() if p.get("pct") is not None)
    champ = None
    if len(pcts) >= 2:
        q1, med, q3 = statistics.quantiles(pcts, n=4, method="inclusive"); champ = (pcts[0], q1, med, q3, pcts[-1])
    return dict(vous=vous, reco=sum(recos) / len(recos) if recos else None, champ=champ)


def chaine(D, x0, y, texte, police, taille, couleur=None, ancre="start"):
    """Un texte dans un dessin (reportlab.graphics), ♥ et ♦ en rouge comme partout dans les rapports (suits) : posé
    morceau par morceau, chacun à la suite du précédent."""
    from reportlab.graphics.shapes import String
    from reportlab.pdfbase.pdfmetrics import stringWidth
    couleur = couleur or colors.HexColor(INK)
    largeur = stringWidth(texte, police, taille)
    x = x0 - largeur if ancre == "end" else x0 - largeur / 2 if ancre == "middle" else x0
    for morceau in re.split(r"([♥♦])", texte):
        if not morceau: continue
        D.add(String(x, y, morceau, fontName=police, fontSize=taille,
                     fillColor=colors.HexColor(RED) if morceau in "♥♦" else couleur))
        x += stringWidth(morceau, police, taille)


class DessinLiens(Flowable):
    """Un dessin (reportlab.graphics) avec des liens : chaque zone (n, bas, haut), une bande sur toute la largeur, mène à
    l'ancre « donne<n> », le titre de la page de la donne. Cliquer sur une ligne de « Vous face au champ » ouvre sa donne."""
    def __init__(self, dessin, zones):
        super().__init__(); self.dessin, self.zones = dessin, zones
    def wrap(self, *a): return (self.dessin.width, self.dessin.height)
    def draw(self):
        from reportlab.graphics import renderPDF
        renderPDF.draw(self.dessin, self.canv, 0, 0)
        for n, bas, haut in self.zones:
            self.canv.linkRect("", f"donne{n}", (0, bas, self.dessin.width, haut), relative=1, thickness=0)


def page_champ(donnes, an, largeur=17.4*cm, tours=None, marque="MP", liens=None):
    """Vous face au champ : sur chaque donne, 50 % est la moyenne des tables ; la barre va de 50 % à votre pourcentage,
    à gauche en rouge ce que vous perdez face au champ, à droite en bleu ce que vous gagnez (PERTE_C, GAIN_C : l'utilisateur,
    2026-11-10) ; la boîte du champ derrière, pour situer l'écart. À droite votre %, votre contrat et le meilleur contrat
    pour vous. Puis la séance, et les donnes qui coûtent le plus.
    tours : {donne: moi.tour_infos} ; quand le mouvement est connu, chaque tour a sa ligne de titre (« Tour 1 · contre
    AP/EK », votre moyenne du tour à droite) et une bande sur deux est grisée ; un tour de relais tient en une ligne grise.
    Sans mouvement, une donne sur deux est grisée.
    marque "IMP" : le centre est 0 IMP (le datum), la barre va de 0 à vos IMP sur la donne (échelle ±12, au-delà la barre
    s'arrête au bord), les tours et la séance en totaux ; "MP" : les % comme plus haut.
    Un rond orange devant le numéro : une donne à revoir (couts.numeros_a_revoir, le tableau sous le dessin).
    liens : les numéros des donnes qui ont leur page dans ce rapport (None : toutes) ; les autres lignes ne mènent nulle part."""
    imp = marque == "IMP"
    BORNE = 12
    from reportlab.graphics.shapes import Drawing, Rect, Line, String
    L = [r for r in lignes_ensemble(donnes, an, imp=imp)]
    jouees = [r for r in L if r["vous"] is not None]
    if not jouees: return []
    centre = 0 if imp else 50
    G, X0, X1 = 1.3*cm, 1.3*cm, 11.0*cm
    C1, C0, C2 = 12.4*cm, 12.9*cm, 14.8*cm                 # votre % (aligné à droite), votre contrat, le contrat recommandé
    import couts
    bil = couts.bilan(donnes, an, MES, marque)
    valeur_reco = {c["n"]: c.get("valeur_reco") for c in bil["lignes"]}
    avec_reco = any(r["texte_reco"] for r in L)           # sans analyse (Rapports, « Les faits seulement ») : ni la colonne
    revoir = set(couts.numeros_a_revoir(bil)) if avec_reco else set()   # « Recommandé », ni les donnes à revoir
    for r in L:                                            # le recommandé et ce qu'il aurait marqué à votre table
        v_ = valeur_reco.get(r["n"])
        r["texte_meilleur"] = r["texte_reco"] + (f"  ({nombre_(v_, imp)})" if v_ is not None and r["texte_reco"] else "")
    seance = ligne_seance(L, imp=imp)
    tours = tours or {}
    par_tour = any(tours.get(r["n"]) for r in L)
    blocs = []                                             # [(infos du tour ou None, [lignes])] : les tours dans l'ordre du rapport
    for r in L:
        t = tours.get(r["n"]) if par_tour else None
        if par_tour and blocs and blocs[-1][0] == t: blocs[-1][1].append(r)
        else: blocs.append((t, [r]))
    hauteurs = []                                          # une ligne de titre par tour ; un relais n'a que son titre
    for t, rs in blocs:
        if t or par_tour: hauteurs.append(.62)            # une ligne de titre par tour, et pour les donnes non jouées
        if not (t and t["relais"] and all(r["vous"] is None for r in rs)): hauteurs += [1] * len(rs)
    h = min(.72*cm, 20.5*cm / (sum(hauteurs) + 2)); haut = .8*cm; ecart = .7*cm if seance else 0
    D = Drawing(largeur, haut + h * (sum(hauteurs) + (1 if seance else 0)) + ecart + .2*cm)
    x = (lambda p: X0 + (X1 - X0) * (max(-BORNE, min(BORNE, p)) + BORNE) / (2 * BORNE)) if imp else \
        (lambda p: X0 + (X1 - X0) * p / 100)
    Y = D.height - haut
    graduations = (-BORNE, -BORNE // 2, 0, BORNE // 2, BORNE) if imp else (0, 25, 50, 75, 100)
    legende = (lambda p: f"{p:+d}".replace("-", "−") if p else "0 IMP") if imp else (lambda p: f"{p} %")
    nombre = (lambda v: (f"{round(v):+d}" if round(v) else "0").replace("-", "−")) if imp else (lambda v: f"{v:.0f} %")
    perdu, gagne = colors.HexColor(PERTE_C), colors.HexColor(GAIN_C)   # rouge ce que vous perdez, bleu ce que vous gagnez
    fond = colors.HexColor("#f6f7f9")                      # les bandes, plus pâles que les boîtes du champ
    bas = Y - h * sum(hauteurs)
    for p in graduations:
        if p != centre: D.add(Line(x(p), 0, x(p), Y, strokeColor=colors.HexColor("#dfe3e7"), strokeWidth=.5))
    for p in graduations:
        D.add(String(x(p), Y + .25*cm, legende(p), fontName="DVB" if p == centre else "DV", fontSize=7.5,
                     fillColor=colors.HexColor(INK if p == centre else GREY), textAnchor="middle"))
    for t_, xx, anc in (("IMP" if imp else "%", C1, "end"), ("Vous", C0, "start")) + ((("Recommandé", C2, "start"),) if avec_reco else ()):
        D.add(String(xx, Y + .25*cm, t_, fontName="DVB", fontSize=7.5, fillColor=colors.HexColor(INK), textAnchor=anc))

    def rangée(y, nom, r, gras=False):
        police = "DVB" if gras else "DV"
        D.add(String(G - .3*cm, y - 2.6, nom, fontName="DVB", fontSize=8.5, fillColor=colors.HexColor(INK), textAnchor="end"))
        if r.get("n") in revoir:                           # une donne à revoir : un rond orange devant son numéro
            from reportlab.graphics.shapes import Circle
            D.add(Circle(.3*cm, y, 3.2, fillColor=colors.HexColor(VOUS_C), strokeColor=None))
        b = min(h * .5, .34*cm)
        if r.get("champ"):                                 # le champ, en retrait : moustaches et boîte
            mn, q1, med, q3, mx = r["champ"]
            D.add(Line(x(mn), y, x(mx), y, strokeColor=colors.HexColor(CHAMP_TRAIT), strokeWidth=.8))
            D.add(Rect(x(q1), y - b / 2, max(x(q3) - x(q1), 1), b, fillColor=colors.HexColor(CHAMP_FOND),
                       strokeColor=colors.HexColor(CHAMP_TRAIT), strokeWidth=.5, rx=1.5, ry=1.5))
        if r["vous"] is None:
            D.add(String(C1, y - 2.6, "–", fontName=police, fontSize=7.8, fillColor=colors.HexColor(GREY), textAnchor="end"))
            if r.get("texte_meilleur"):
                chaine(D, C2, y - 2.6, r["texte_meilleur"], police, 7.8)
            return
        v = r["vous"]; perte = v < centre
        D.add(Rect(min(x(v), x(centre)), y - b * .45, abs(x(v) - x(centre)), b * .9, fillColor=perdu if perte else gagne,
                   strokeColor=None, rx=1.5, ry=1.5))      # la barre : du centre (50 %, 0 IMP) à vous
        D.add(String(C1, y - 2.6, nombre(r.get("total", v)), fontName="DVB" if perte or gras else "DV", fontSize=7.8,
                     fillColor=colors.HexColor(INK), textAnchor="end"))
        if r.get("texte_vous"): chaine(D, C0, y - 2.6, r["texte_vous"], police, 7.8)   # ♥ ♦ en rouge
        if r.get("texte_meilleur"): chaine(D, C2, y - 2.6, r["texte_meilleur"], police, 7.8)

    yy = Y                                                 # le haut de la ligne suivante
    zones = []
    for k, (t, rs) in enumerate(blocs):
        relais = bool(t and t["relais"] and all(r["vous"] is None for r in rs))
        hb = h * ((.62 if t else 0) + (0 if relais else len(rs)))
        if par_tour and not t:                             # les donnes que vous n'avez pas jouées : une ligne de titre
            t = dict(tour=None, contre="", relais=False)
            hb = h * (.62 + len(rs))
        if t:
            if k % 2: D.add(Rect(0, yy - hb, largeur, hb, fillColor=fond, strokeColor=None))
            yt = yy - h * .31 - 2.4
            if relais:
                ns = [r["n"] for r in rs]
                quoi = f"donnes {ns[0]}–{ns[-1]}" if len(ns) > 1 else f"donne {ns[0]}"
                D.add(String(G - .3*cm, yt, f"Tour {t['tour']} · relais ({quoi})", fontName="DV", fontSize=7.5,
                             fillColor=colors.HexColor(GREY)))
            else:
                D.add(String(G - .3*cm, yt, "Donnes non jouées" if t["tour"] is None else
                             f"Tour {t['tour']}" + (f" · contre {t['contre']}" if t["contre"] else ""),
                             fontName="DVB", fontSize=7.5, fillColor=colors.HexColor(GREY)))
                vs = [r["vous"] for r in rs if r["vous"] is not None]
                if vs:                                     # votre moyenne du tour (le total en IMP), dans la colonne des %
                    D.add(String(C1, yt, f"total {nombre(sum(vs))}" if imp else f"moy. {sum(vs) / len(vs):.0f} %", fontName="DVB", fontSize=7.5,
                                 fillColor=colors.HexColor(GREY), textAnchor="end"))
            yy -= h * .62
        if relais: continue
        for r in rs:
            if liens is None or r["n"] in liens:
                zones.append((r["n"], yy - h, yy))          # la ligne entière mène à la page de la donne
            if not t and len([b_ for b_ in blocs[:k]]) % 2: D.add(Rect(0, yy - h, largeur, h, fillColor=fond, strokeColor=None))
            rangée(yy - h / 2, str(r["n"]), r)
            yy -= h
    if seance:
        D.add(Line(0, bas - ecart / 2, largeur, bas - ecart / 2, strokeColor=colors.HexColor("#c7ccd2"), strokeWidth=.5))
        rangée(bas - ecart - h / 2, "Séance", dict(seance, texte_vous="", texte_meilleur=""), gras=True)
    D.add(Line(x(centre), 0, x(centre), Y, strokeColor=colors.HexColor(INK), strokeWidth=1))   # le champ, au-dessus de tout
    return [Paragraph("Vous face au champ", S_title),
            Paragraph(txt("Marque en IMP : 0 est le datum de chaque donne (la moyenne des tables) ; en rouge les IMP que vous "
                          "perdez, en bleu ceux que vous gagnez (la barre s'arrête à ±12) ; la boîte grise montre le champ. "
                          "Les tours et la séance en totaux." + (" « Recommandé » : le contrat recommandé joué au double mort, et "
                          "ses IMP à votre table." if avec_reco else "") if imp else
                          "50 % est la moyenne des tables sur chaque donne : en rouge ce que vous perdez face au champ, "
                          "en bleu ce que vous gagnez ; la boîte grise montre le champ." + (" « Recommandé » : le contrat "
                          "recommandé joué au double mort, et son % à votre table." if avec_reco else ""))
                          + (f" <font color='{VOUS_C}'>●</font> : une donne à revoir (le tableau sous le dessin)." if revoir else ""), S_sub),
            Spacer(1, 8), DessinLiens(D, zones)] + ([KeepTogether(paragraphe_couts(bil, liens))] if avec_reco else []) + [PageBreak()]


def nombre_(v, imp):
    """Une valeur vue de votre camp : « +5 », « −3 » (IMP) ou « 62 % »."""
    if imp: return (f"{round(v):+d}" if round(v) else "0").replace("-", "−")
    return f"{v:.0f} %"


def paragraphe_couts(b, liens=None):
    """Où vous pouviez faire mieux (couts.bilan) : deux phrases (le résultat de la séance, le repère), puis le tableau
    « Donnes à revoir », une ligne par part coûteuse (les enchères, ou la carte), la plus coûteuse d'abord, chaque numéro
    menant à sa donne ; « Vous » est votre résultat, « Possible » ce qu'il aurait été avec cette part réussie. Puis vos
    meilleurs coups et le reste, une ligne chacun. En IMP, des IMP ; en match-points, des % de la donne.
    liens : les donnes qui ont leur page dans ce rapport (None : toutes) ; les autres numéros ne sont pas des liens."""
    import couts
    if not b["n"]: return []
    imp = b["marque"] == "IMP"; n = b["n"]
    signe = lambda v: (f"{v:+d}" if v else "0").replace("-", "−")
    une = lambda v: signe(round(v)) + ("" if imp else " points")                    # un écart sur une donne
    dire = lambda t: "passe générale" if t.get("contrat") in (None, "", "passe") else \
        f"{t['contrat']} {SEAT[t['declarant']]}"
    resu = lambda t: "" if t.get("contrat") in (None, "", "passe") else f" {t.get('resultat') or '='}".replace("-", "−")
    gagne = -b["perte"]
    liste = couts.a_revoir(b)
    out = [Spacer(1, 10), Paragraph("Où vous pouviez faire mieux", S_h)]
    debut = (f"Sur ces {n} donnes, vous {'gagnez' if gagne >= 0 else 'perdez'} "
             + (f"{abs(round(gagne))} IMP" if imp else f"{abs(gagne) / n:.1f} %".replace(".", ","))
             + " face au champ" + ("" if imp else f" (votre séance : {50 + gagne / n:.1f} %)".replace(".", ",")) + ". "
             "Le repère : le contrat recommandé, enchéri sans voir les autres mains (pas la meilleure table, qui doit "
             "souvent son score à une erreur ailleurs, ni le par). Le jeu de la carte n'est compté que si une autre table "
             "du même contrat a fait mieux : le double mort devine toujours juste.")
    out.append(Paragraph(txt(debut), S_avis))
    if liste:
        S_t = ParagraphStyle("rv", parent=S_cell, fontSize=10, leading=12.5)
        S_tb = ParagraphStyle("rvb", parent=S_t, fontName="DVB")
        S_tr = ParagraphStyle("rvr", parent=S_t, alignment=2)
        rows = [[Paragraph(x, S_tb if k < 3 else ParagraphStyle("rvbr", parent=S_tb, alignment=2))
                 for k, x in enumerate(("Donne", "Où", "Ce qui s'est passé", "Vous", "Possible"))]]
        for quoi, c, cout in liste:
            t_ = c["table"]
            if quoi == "encheres":
                ou = "Enchères"
                quoi_ = f"{dire(t_)} au lieu de {dire(c['reco'])} (au double mort)"
            else:
                ou = f"Jeu en {dire(t_)}" if c["role"] == "jeu" else f"Défense contre {dire(t_)}"
                if not c.get("memes"): cmp_ = "seule table dans ce contrat"
                elif c["memes"] == 1: cmp_ = "l'autre table a fait mieux"
                else: cmp_ = f"{c['mieux']} tables sur {c['memes']} mieux"
                quoi_ = f"{c['levees']} levées pour le déclarant ({c['levees_dm']} au double mort ; {cmp_})"
            num = f"<a href='#donne{c['n']}'><u>{c['n']}</u></a>" if liens is None or c["n"] in liens else str(c["n"])
            rows.append([Paragraph(num, S_tb), Paragraph(txt(ou), S_t),
                         Paragraph(txt(quoi_), S_t), Paragraph(nombre_(c["vous"], imp), S_tr),
                         Paragraph(nombre_(c["vous"] + cout, imp), S_tr)])
        tb = _grille(rows, [w * cm for w in (1.7, 4.9, 7.3, 1.6, 2.1)],
                     [("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f5f3")])])
        out += [Spacer(1, 4), Paragraph("Donnes à revoir", ParagraphStyle("rvh", parent=S_tb, fontSize=11, spaceAfter=3)),
                tb, Spacer(1, 6)]
    else:
        out.append(Paragraph(txt("<b>Donnes à revoir</b> : aucune ne vous coûte " + (f"{b['seuil']} IMP" if imp else
                                 f"{b['seuil']} points de %") + " ou plus, aux enchères ou au jeu de la carte."), S_avis))
    gains = b["gains"]
    if gains:
        L = []
        for quoi, c, v in gains:
            if quoi == "encheres": L.append(f"donne {c['n']}, {dire(c['table'])}{resu(c['table'])} plutôt que "
                                            f"{dire(c['reco'])} ({une(v)})")
            else: L.append(f"donne {c['n']}, {dire(c['table'])}{resu(c['table'])} : {c['levees']} levées au lieu de "
                           f"{c['levees_dm']} au double mort ({une(v)})")
        out.append(Paragraph(txt("<b>Vos meilleurs coups</b> : " + " ; ".join(L) + "."), S_avis))
    out.append(Paragraph(txt("<b>Le reste</b> de votre résultat vient des autres tables (leurs erreurs, ou des décisions "
                             "raisonnables qui n'ont pas réussi), des enchères adverses et des petits écarts."), S_avis))
    return out


def page_ensemble(donnes, an, largeur=17.4*cm, style="lignes"):
    """La première page quand vous avez choisi « Vous êtes » : pour chaque donne, dans l'ordre du rapport, votre %,
    celui du contrat recommandé joué au double mort, et le champ en boîte à moustaches (quartiles, médiane, extrêmes).
    style "lignes" : une ligne relie vos donnes, une autre celles du recommandé, l'espace entre elles en rouge ou vert pâle ;
    "haltere" (page 2, à essayer) : sur chaque donne, une barre épaisse entre vous et le recommandé, rouge ou verte."""
    from reportlab.graphics.shapes import Drawing, Rect, Line, Circle, Polygon, String
    L = lignes_ensemble(donnes, an)
    if not L or not any(x["vous"] is not None for x in L): return []
    import statistics
    from reportlab.pdfbase.pdfmetrics import stringWidth
    G, X0, X1 = 1.3*cm, 1.3*cm, 10.0*cm                     # les numéros, puis l'échelle de 0 à 100 %, puis deux colonnes
    V0, R0, LC = 10.75*cm, 14.0*cm, 3.0*cm                  # chacune : le contrat à gauche, le % à droite (largeur LC)
    seance = ligne_seance(L)                                # la dernière ligne : la séance entière, à part
    h = min(.72*cm, 20.5*cm / (len(L) + 2)); haut = .8*cm; ecart = .45*cm if seance else 0
    D = Drawing(largeur, haut + h * (len(L) + (1 if seance else 0)) + ecart + .2*cm)
    x = lambda p: X0 + (X1 - X0) * p / 100
    Y = D.height - haut
    for p in (0, 25, 50, 75, 100):                         # l'échelle : des traits légers, des % en haut
        D.add(Line(x(p), 0, x(p), Y, strokeColor=colors.HexColor("#dfe3e7" if p % 50 else "#c7ccd2"), strokeWidth=.5))
        D.add(String(x(p), Y + .25*cm, f"{p} %", fontName="DV", fontSize=7.5, fillColor=colors.HexColor(GREY), textAnchor="middle"))
    D.add(String(V0, Y + .25*cm, "Vous", fontName="DVB", fontSize=7.5, fillColor=colors.HexColor(INK)))
    D.add(String(R0, Y + .25*cm, "Recommandé", fontName="DVB", fontSize=7.5, fillColor=colors.HexColor(INK)))
    marques = []                                           # les symboles, posés à la fin : au-dessus des lignes et des boîtes

    def ligne(y, nom, r, gras=False):
        """Une ligne : son nom, le champ en boîte à moustaches, vos deux symboles (posés plus tard), les deux %."""
        D.add(String(G - .3*cm, y - 2.6, nom, fontName="DVB", fontSize=8.5, fillColor=colors.HexColor(INK), textAnchor="end"))
        if r["champ"]: boite(y, r["champ"])
        if r["reco"] is not None: marques.append(("reco", x(r["reco"]), y))
        if r["vous"] is not None: marques.append(("vous", x(r["vous"]), y))
        police = "DVB" if gras else "DV"
        ecrire = lambda xx, t_, ancre="start": chaine(D, xx, y - 2.6, t_, police, 7.8, ancre=ancre)
        if r.get("texte_vous"):                            # votre contrat : rouge plus haut, bleu plus bas que le recommandé
            if r.get("sens"):
                w = stringWidth(r["texte_vous"], police, 7.8)
                D.add(Rect(V0 - 2, y - 4.6, w + 4, 11, fillColor=colors.HexColor(SENS[r["sens"]][0]), strokeColor=None, rx=2, ry=2))
            ecrire(V0, r["texte_vous"])
        ecrire(V0 + LC, f"{r['vous']:.0f} %" if r["vous"] is not None else "–", "end")
        if r.get("texte_reco"): ecrire(R0, r["texte_reco"])   # son % se lit au losange : pas de chiffre (l'utilisateur)

    def boite(y, champ):
        mn, q1, med, q3, mx = champ; b = min(h * .5, .34*cm)
        D.add(Line(x(mn), y, x(mx), y, strokeColor=colors.HexColor(CHAMP_TRAIT), strokeWidth=1))      # les moustaches
        for v in (mn, mx): D.add(Line(x(v), y - b / 3, x(v), y + b / 3, strokeColor=colors.HexColor(CHAMP_TRAIT), strokeWidth=1))
        D.add(Rect(x(q1), y - b / 2, max(x(q3) - x(q1), 1), b, fillColor=colors.HexColor(CHAMP_FOND),
                   strokeColor=colors.HexColor(CHAMP_TRAIT), strokeWidth=.6, rx=1.5, ry=1.5))           # la boîte
        D.add(Line(x(med), y - b / 2, x(med), y + b / 2, strokeColor=colors.HexColor(CHAMP_MED), strokeWidth=1.4))

    for k, r in enumerate(L):
        y = Y - h * (k + .5)
        if k % 2: D.add(Rect(0, y - h / 2, largeur, h, fillColor=colors.HexColor("#f7f8f9"), strokeColor=None))
        ligne(y, str(r["n"]), r)
    if seance:                                             # la séance : un trait, puis sa ligne, en gras
        ys = Y - h * len(L) - ecart
        D.add(Line(0, ys + h / 2 + ecart / 2, largeur, ys + h / 2 + ecart / 2, strokeColor=colors.HexColor("#c7ccd2"), strokeWidth=.8))
        ys -= h / 2
        ligne(ys, "Séance", seance, gras=True)
    if style == "haltere":                                 # une haltère par donne : la barre entre vous et le recommandé
        for k, r in enumerate(L):
            if r["vous"] is None or r["reco"] is None or r["vous"] == r["reco"]: continue
            y = Y - h * (k + .5); c = ecart_couleur(r["vous"] - r["reco"])
            D.add(Line(x(r["vous"]), y, x(r["reco"]), y, strokeColor=colors.Color(c.red, c.green, c.blue, alpha=.55),
                       strokeWidth=6, strokeLineCap=1))
    for k in range(len(L) - 1 if style == "lignes" else 0):   # l'espace entre vos deux lignes : rouge pâle où vous êtes au-dessus
        a_, b_ = L[k], L[k + 1]                            # du recommandé, vert pâle où il est au-dessus de vous
        if None in (a_["vous"], a_["reco"], b_["vous"], b_["reco"]): continue
        y1, y2 = Y - h * (k + .5), Y - h * (k + 1.5)
        d1, d2 = a_["vous"] - a_["reco"], b_["vous"] - b_["reco"]
        A1, B1, A2, B2 = (x(a_["vous"]), y1), (x(a_["reco"]), y1), (x(b_["vous"]), y2), (x(b_["reco"]), y2)
        if d1 * d2 < 0:                                    # les lignes se croisent : deux morceaux, chacun sa couleur
            t = d1 / (d1 - d2); C = (A1[0] + (A2[0] - A1[0]) * t, y1 + (y2 - y1) * t)
            morceaux = [((A1, C, B1), d1), ((C, A2, B2), d2)]
        else:
            morceaux = [((A1, A2, B2, B1), d1 if d1 else d2)]
        for pts, signe in morceaux:
            if not signe: continue
            D.add(Polygon([v for pt in pts for v in pt], fillColor=ecart_couleur(signe), strokeColor=None))
    for qui, tirets in (("vous", None), ("reco", None)) if style == "lignes" else ():   # les lignes qui relient les donnes, pleines
        prec = None
        for k, r in enumerate(L):
            y = Y - h * (k + .5)
            if r[qui] is None: prec = None; continue
            if prec: D.add(Line(prec[0], prec[1], x(r[qui]), y, strokeColor=couleur_ligne(qui), strokeWidth=1.4,
                                strokeDashArray=tirets, strokeLineCap=1))
            prec = (x(r[qui]), y)
    for qui, cx, y in sorted(marques, key=lambda m: m[0] == "vous"): symbole(D, qui, cx, y)   # vous par-dessus
    leg = Drawing(largeur, .5*cm); yl = .22*cm                # la légende, au-dessus : symbole, bout de ligne, nom
    if style == "lignes": leg.add(Line(0, yl, .6*cm, yl, strokeColor=couleur_ligne("vous"), strokeWidth=1.4))
    symbole(leg, "vous", .3*cm, yl)
    leg.add(String(.8*cm, yl - 2.6, "Vous", fontName="DV", fontSize=8, fillColor=colors.HexColor(INK)))
    if style == "lignes": leg.add(Line(2.0*cm, yl, 2.6*cm, yl, strokeColor=couleur_ligne("reco"), strokeWidth=1.4))
    symbole(leg, "reco", 2.3*cm, yl)
    leg.add(String(2.8*cm, yl - 2.6, "Contrat recommandé, joué au double mort", fontName="DV", fontSize=8, fillColor=colors.HexColor(INK)))
    c = 9.0*cm; leg.add(Line(c, yl, c + 1.4*cm, yl, strokeColor=colors.HexColor(CHAMP_TRAIT), strokeWidth=1))
    leg.add(Rect(c + .35*cm, yl - 4, .7*cm, 8, fillColor=colors.HexColor(CHAMP_FOND), strokeColor=colors.HexColor(CHAMP_TRAIT), strokeWidth=.6))
    leg.add(Line(c + .7*cm, yl - 4, c + .7*cm, yl + 4, strokeColor=colors.HexColor(CHAMP_MED), strokeWidth=1.4))
    leg.add(String(c + 1.6*cm, yl - 2.6, "Le champ : quartiles, médiane, du plus bas au plus haut", fontName="DV", fontSize=8,
                   fillColor=colors.HexColor(INK)))
    paire = next((p.get("nom") for k, p in (DONNEES_SEANCE.get("paires") or {}).items() if k in MES and p.get("nom")), "")
    if style == "haltere":
        return [Paragraph("Vous face au contrat recommandé", S_title),
                Paragraph(txt("Sur chaque donne, la barre va de votre pourcentage à celui du contrat recommandé joué au double "
                              "mort : orange quand vous faites mieux, verte quand il fait mieux que vous."), S_sub),
                Spacer(1, 6), leg, Spacer(1, 4), D, PageBreak()]
    return [Paragraph("La séance en un coup d'œil", S_title),
            Paragraph(txt(f"Chaque ligne est une donne, dans l'ordre de ce rapport, vue de votre camp"
                          + (f" (votre paire : {paire})" if paire else "") + " : votre pourcentage, celui qu'aurait eu le "
                          "contrat recommandé joué au double mort face aux tables, et le champ, en boîte à moustaches. Une "
                          "donne que vous n'avez pas jouée se lit de Nord-Sud. À droite, votre contrat (en rouge s'il est plus "
                          "haut que le recommandé, du même camp, en bleu s'il est plus bas), votre pourcentage, et le contrat "
                          "recommandé. Dernière ligne, la séance : votre pourcentage, la moyenne du contrat recommandé sur les "
                          "donnes que vous avez jouées (le rond vert), et le champ des paires. Entre vos deux lignes, de l'orange "
                          "quand vous faites mieux que le contrat recommandé, du vert quand il fait mieux que vous."), S_sub),
            Spacer(1, 6), leg, Spacer(1, 4), D, PageBreak()]


def results_table(d, a=None):
    """Les tables, du meilleur résultat au moins bon vu de votre camp ; le contrat recommandé de l'analyse a y prend
    sa place (vert pâle, son résultat au double mort)."""
    from comparer import table_recommandee                 # import tardif : comparer importe ce module
    P = lambda x: Paragraph(x, S_cell)
    beaucoup = len(d["tables"]) > 2
    entete = ["<b>Paires</b>", "<b>Contrat</b>", "<b>Entame</b>", "<b>Nord-Sud</b>", "<b>IMP N-S</b>"]
    if beaucoup: entete = ["<b>Table</b>"] + entete + ["<b>% N-S</b>"]
    rows = [[P(x) for x in entete]]; vous = []
    reco = table_recommandee(d, a)
    avant = None; serre = len(d["tables"]) >= 15             # beaucoup de tables : des lignes plus serrées
    for t in moi.ordre(d["tables"] + ([reco] if reco else []), MES):   # du meilleur au moins bon, vu de votre camp
        res = "=" if t["resultat"] in ("=", "") else t["resultat"]
        cle = t.get("score_ns")                             # un petit blanc quand le score change (l'utilisateur, 2026-11-10) :
                                                            # 2♥ +1 et 3♥ = font le même score et restent ensemble
        if avant is not None and cle != avant:
            vous.append(("TOPPADDING", (0, len(rows)), (-1, len(rows)), 5 if serre else 6))
        avant = cle
        passe = t["contrat"] == "passe"
        jeu = "passe générale" if passe else f"<b>{t['contrat']} {SEAT[t['declarant']]}</b> {res}"
        if t.get("recommande"):
            row = [P("<i>Recommandé</i>"), P(suits(jeu)), P(suits(t["entame"])),
                   P(f"{t['score_ns']:+d}"), P("")]
            if beaucoup: row = [P("")] + row + [P(f"<i>{t['pct_ns']:.0f} %</i>" if t.get("pct_ns") is not None else "")]   # face aux tables
            rows.append(row); vous.append(("BACKGROUND", (0, len(rows) - 1), (-1, len(rows) - 1), colors.HexColor(FOND_RECO)))
            continue
        row = [P(_paires(t, None if passe else "NS" if t["declarant"] in "NS" else "EO")), P(suits(jeu)),
               P(suits(t["entame"])), P(f"{t['score_ns']:+d}"), P(f"{t['imp_ns']:+d}" if t["imp_ns"] else "0")]
        if beaucoup: row = [P(str(t["table"]))] + row + [P(f"{t['pct_ns']:.0f} %" if t.get("pct_ns") is not None else "")]
        rows.append(row)
        if moi.a_joue(t, MES): vous.append(("BACKGROUND", (0, len(rows) - 1), (-1, len(rows) - 1), colors.HexColor(moi.SURLIGNE)))
    larg = [1.5, 3.6, 3.3, 2.0, 2.3, 1.6, 1.6] if beaucoup else [4.4, 3.6, 2.0, 2.3, 2.0]
    tb = Table(rows, colWidths=[x*cm for x in larg], hAlign="LEFT")
    tb.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor(INK)),
        ("LINEBELOW", (0, -1), (-1, -1), 0.4, colors.HexColor("#aab")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 0.6 if serre else 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.6 if serre else 2)] + vous))
    return tb

def grille(donneur, bids):
    k = ["O", "N", "E", "S"].index(donneur)
    cells = ["–"] * k + bids; cells += [""] * (-len(cells) % 4)
    return [cells[i:i + 4] for i in range(0, len(cells), 4)]

def complete(bids):
    bids = list(bids)
    while len(bids) > 1 and bids[-1] == "passe": bids.pop()
    return ["passe"] * 4 if all(b == "passe" for b in bids) else bids + ["passe"] * 3

def bidding(rows_, w, qui="reco"):
    """La grille d'enchères ; en-tête vert pâle pour les enchères recommandées, gris pour celles du coach montrées à côté
    de celles de l'expert (GRILLE)."""
    rows = [[Paragraph(f"<b>{x}</b>", S_cellc) for x in ("Ouest", "Nord", "Est", "Sud")]]
    rows += [[Paragraph(suits(x), S_cellc) for x in r] for r in rows_]
    t = Table(rows, colWidths=[w]*4)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(GRILLE[qui][0])),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(GRILLE[qui][1])),
        ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
    return t

CASQUETTE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icones", "casquette.png")   # le coach (icones/)


def bloc_avis(texte, largeur, style, qui="expert"):
    """Un avis dans son bloc (AVIS) : son signe et le titre, fond pâle, trait à gauche dans sa couleur ; la casquette
    pour le coach, ✦ pour l'expert. qui : "coach" ou "expert"."""
    marque, trait, fond = AVIS[qui]
    signe = (f"<img src='{CASQUETTE}' width='17' height='10.6' valign='-1.5'/>" if qui == "coach" and os.path.exists(CASQUETTE)
             else f"<font color='{trait}'>✦</font>")
    if fond is None:                               # le coach : du texte ordinaire, sans fond ni trait
        return Paragraph(signe + " " + txt(marque[5:] + " " + texte.strip()), style)
    tb = Table([[Paragraph(signe + " " + txt(marque[5:] + " " + texte.strip()), style)]], colWidths=[largeur])
    tb.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(fond)),
                            ("LINEBEFORE", (0, 0), (0, -1), 2 if qui == "expert" else 0, colors.HexColor(trait if qui == "expert" else fond)), ("LEFTPADDING", (0, 0), (-1, -1), 6),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    tb.hAlign = "LEFT"
    return tb


S_avis = st("av", fontSize=10.5, leading=14.5, firstLineIndent=14, spaceAfter=4)   # aligné à gauche, 1re ligne en retrait
S_titre_avis = st("ta", fontName="DVB", fontSize=10, leading=13.5, spaceAfter=2)
NOUVEAU_PARAGRAPHE = {   # les phrases du coach qui ouvrent un paragraphe, et le groupe qu'elles commencent
    "chance": r"(Il faut |Contre une bonne défense)",
    "encheres": r"(Les enchères donnent |L'impasse à |Les impasses à |(Le |La |L')[♠♥♦♣]?[^ ]{0,3}[♠♥♦♣][ARDV] est plutôt|Main dangereuse)",
    "compte": r"(Nord|Sud|Est|Ouest|[NSEO]) compte :"}


PARAGRAPHE_LONG = 150   # un paragraphe se ferme à la fin de la phrase qui lui fait passer cette longueur
FORCE = r"(Ordre :|Le coach |Si |Sinon|En défense|Ensuite)"
COURT = 60             # une idée nouvelle n'ouvre un paragraphe qu'après un paragraphe de cette longueur (sauf « Décision serrée »)


def paragraphes(texte):
    """Un avis en paragraphes courts, coupés à l'affichage (l'analyse rangée ne change pas) : au début des phrases qui
    ouvrent une idée (NOUVEAU_PARAGRAPHE, FORCE) quand le paragraphe a déjà COURT caractères, et sinon dès qu'un paragraphe passe PARAGRAPHE_LONG caractères."""
    phrases = re.split(r"(?<=[.)])\s+(?=[A-ZÀÂÉÈÊÎÔÛ])", texte.strip())
    out = []
    for ph in phrases:
        neuf = any(re.match(m, ph) for m in list(NOUVEAU_PARAGRAPHE.values()) + [FORCE])
        if out and ((neuf and len(out[-1]) >= COURT) or ph.startswith("Décision serrée") or len(out[-1]) >= PARAGRAPHE_LONG):
            out.append(ph)
        elif out: out[-1] += " " + ph
        else: out.append(ph)
    return out


def majuscule(texte):
    """La première lettre en capitale, balises sautées : l'expert continue parfois « Avis de l'expert : » en minuscule."""
    return re.sub(r"^(\s*(?:<[^>]+>\s*)*)([a-zà-ÿ])", lambda m: m.group(1) + m.group(2).upper(), texte)


def colonne_avis(qui, texte, largeur):
    """Un avis, son titre seul sur sa ligne puis ses paragraphes, première ligne en retrait ; l'expert dans son bloc vert."""
    marque, trait, fond = AVIS[qui]
    signe = (f"<img src='{CASQUETTE}' width='17' height='10.6' valign='-1.5'/>" if qui == "coach" and os.path.exists(CASQUETTE)
             else f"<font color='{trait}'>✦</font>")
    el = [Paragraph(signe + " " + marque[5:].replace(" :", ""), S_titre_avis)]
    el += [Paragraph(txt(p_), S_avis) for p_ in paragraphes(majuscule(texte))]
    if fond is None: return el
    tb = Table([[el]], colWidths=[largeur])
    tb.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(fond)),
                            ("LINEBEFORE", (0, 0), (0, -1), 2 if qui == "expert" else 0, colors.HexColor(trait if qui == "expert" else fond)), ("LEFTPADDING", (0, 0), (-1, -1), 7),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    tb.hAlign = "LEFT"
    return [tb]


BANDE = "#f1f2f4"   # le fond gris pâle du plan de jeu, sur toute la largeur (l'utilisateur, 2026-11-10)


def bande(elements, largeur=17.6*cm, deborde=6):
    """Une section sur une bande gris pâle (BANDE), titre compris, qui déborde de deborde points de chaque côté pour
    entourer un peu le bloc de l'expert (le cadre fait 17,6 cm, dont 6 points de marge de chaque côté). Un élément par ligne : la bande peut se couper entre deux pages."""
    els = [e for e in elements if not isinstance(e, Spacer)]
    lignes = [[e] for e in els]
    if len(lignes) > 1: lignes[:2] = [[[els[0], els[1]]]]   # le titre et la première ligne ensemble : jamais un titre seul en bas de page
    tb = Table(lignes, colWidths=[largeur])   # la largeur du cadre : le texte reste aligné sur le reste
    tb.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(BANDE)),
                            ("LEFTPADDING", (0, 0), (-1, -1), deborde), ("RIGHTPADDING", (0, 0), (-1, -1), deborde),
                            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                            ("TOPPADDING", (0, 0), (0, 0), 0), ("BOTTOMPADDING", (0, -1), (-1, -1), deborde),
                            ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    tb.hAlign = "CENTER"
    return tb


def avec_avis(texte):
    """Le texte du programme, puis le conseil du coach et l'avis de l'expert (essai du 10/11/2026) : le coach à gauche,
    l'expert à droite dans son bloc vert ; sans l'un des deux, l'autre prend toute la largeur."""
    prog, coach, expert = decouper_avis(texte)
    if prog.strip() and not coach:       # l'expert joue un autre contrat : le coach ne parle pas, le plan est celui de l'expert
        gauche = [Paragraph(f"<font color='{AVIS['expert'][1]}'>✦</font> L'expert", S_titre_avis)] + \
                 [Paragraph(txt(p_), S_avis) for p_ in paragraphes(prog)]
        if not expert: return [Spacer(1, 3)] + gauche + [Spacer(1, 4)]
        tb = Table([[gauche, colonne_avis("expert", expert, 8.5*cm)]], colWidths=[8.5*cm, 8.65*cm])
        tb.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (0, 0), 10), ("RIGHTPADDING", (1, 0), (1, 0), 0),
                                ("TOPPADDING", (0, 0), (-1, -1), 2)]))
        tb.hAlign = "LEFT"
        return [Spacer(1, 3), tb, Spacer(1, 4)]
    el = [Paragraph(txt(p_), S_avis) for p_ in paragraphes(prog)] if prog.strip() else []   # le plan du coach n'a pas de texte avant son bloc
    if coach and expert:
        tb = Table([[colonne_avis("coach", coach, 8.3*cm), colonne_avis("expert", expert, 8.5*cm)]], colWidths=[8.5*cm, 8.65*cm])
        tb.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (0, 0), 10), ("RIGHTPADDING", (1, 0), (1, 0), 0),
                                ("TOPPADDING", (0, 0), (-1, -1), 2)]))
        tb.hAlign = "LEFT"
        return el + [Spacer(1, 3), tb, Spacer(1, 4)]
    for qui, avis in (("coach", coach), ("expert", expert)):
        if avis: el += [Spacer(1, 3)] + colonne_avis(qui, avis, 17.4*cm)
    return el + [Spacer(1, 4)]


def annexe(d, expliquer=True, pieces=False):
    """Double mort et par, puis le tableau des tables. pieces=True : les morceaux pour la mise en page à deux colonnes
    (apres_coup) : {"dd": la grille, "par": la ligne du par, "tc": le tableau étroit des tables ou None}."""
    if not d.get("dm"): return None if pieces else [Spacer(1, 1)]
    rows = [[Paragraph("", S_cellc)] + [Paragraph(f"<b>{x}</b>", S_cellc) for x in ("Nord", "Sud", "Est", "Ouest")]]
    for lab in ("SA", "♠", "♥", "♦", "♣"):
        rows.append([Paragraph(suits(f"<b>{lab}</b>"), S_cellc)] +
                    [Paragraph(str(d["dm"][lab][p]), S_cellc) for p in "NSEO"])
    dd = Table(rows, colWidths=[1.0*cm] + [1.6*cm]*4)
    marques = []                        # fond vert : une manche ; vert soutenu : un chelem ; cadre : le contrat du par
    p_ = d.get("par") or {}
    par = (p_["contrat"][1:].rstrip("X"), p_.get("declarant")) if p_.get("contrat") and p_["contrat"] != "passe" else None
    for i, lab in enumerate(("SA", "♠", "♥", "♦", "♣"), 1):
        for j, x in enumerate("NSEO", 1):
            n = d["dm"][lab][x]
            if n >= 12 or n >= MANCHE[lab]:
                marques.append(("BACKGROUND", (j, i), (j, i), colors.HexColor("#9fd1a8" if n >= 12 else "#d7ecd9")))
            if par == (lab, x): marques.append(("BOX", (j, i), (j, i), 1.4, colors.HexColor(GREEN)))
    dd.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6efe9")),
        ("BACKGROUND", (1, 1), (2, -1), colors.HexColor("#f6f8fb")), ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#9fb5a8")),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)] + marques))
    p = d.get("par")
    if p is None:
        ptxt = "<b>Par :</b> passe générale (0)."
    else:
        camp = "Nord-Sud" if p["declarant"] in "NS" else "Est-Ouest"
        ptxt = (f"<b>Par :</b> {p['contrat']}{' contré' if p['contre'] else ''} par {SEAT[p['declarant']]} ({camp}), "
                f"{p['resultat']}, soit <b>{p['score_ns']:+d}</b> pour Nord-Sud.")
    expl = ("Le tableau donne le nombre de levées que chaque joueur réalise comme déclarant, cartes vues "
            "(double mort). Fond vert : une manche se gagne ; vert soutenu : un chelem ; cadre : le contrat du par. "
            "Le par est le résultat obtenu si les deux camps enchérissent parfaitement.")
    droite = [Paragraph(suits(ptxt), S_notes)] + ([Spacer(1, 6), Paragraph(expl, S_notes)] if expliquer else [])
    duo = Table([[dd, droite]], colWidths=[7.6*cm, 10.0*cm])
    duo.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (0, 0), 12)]))
    P = lambda x: Paragraph(x, S_cell)
    tr = [[P("<b>Tables</b>" if len(d["tables"]) > 2 else "<b>Table</b>"), P("<b>Contrat</b>"), P("<b>Levées faites</b>"), P("<b>Double mort</b>"),
           P("<b>Écart</b>"), P("<b>Écart au par (IMP)</b>")]]
    lignes = {}                         # tables identiques regroupées (même contrat, mêmes levées)
    for t in d["tables"]:
        if t["levees"] is None: continue
        cle = (t["contrat"], t["declarant"], t["levees"], t["dm"], t["ecart_par_imp"])
        lignes.setdefault(cle, []).append(t)
    for (contrat, decl, lev, dm, ecp), ts in sorted(lignes.items(), key=lambda x: (str(x[1][0]["table"]).rstrip("0123456789"), int(str(x[1][0]["table"]).lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ") or 0))):
        ec = "=" if lev == dm else f"{lev - dm:+d}"
        nom = _tables(ts).replace("Tables ", "").replace("Table ", "")
        tr.append([P(nom), P(suits(f"{contrat} {SEAT[decl]}")), P(str(lev)),
                   P(str(dm)), P(ec), P(f"{ecp:+d}".replace("-", "−") if ecp else "0")])
    if pieces:
        tc = None
        if len(tr) > 1:
            tc = Table([[P("<b>Tables</b>" if len(d["tables"]) > 2 else "<b>Table</b>"), P("<b>Contrat</b>"), P("<b>Lev.</b>"),
                         P("<b>DM</b>"), P("<b>Écart</b>"), P("<b>IMP / par</b>")]] + tr[1:],
                       colWidths=[2.2*cm, 1.9*cm, 0.9*cm, 0.8*cm, 1.1*cm, 1.4*cm], hAlign="LEFT")
            tc.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor(INK)),
                ("LINEBELOW", (0, -1), (-1, -1), 0.4, colors.HexColor("#aab")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
        return dict(dd=dd, par=Paragraph(suits(ptxt), S_notes), tc=tc)
    tt = Table(tr, colWidths=[2.6*cm, 3.2*cm, 2.4*cm, 2.4*cm, 1.6*cm, 3.4*cm], hAlign="LEFT")
    tt.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor(INK)),
        ("LINEBELOW", (0, -1), (-1, -1), 0.4, colors.HexColor("#aab")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    note = Paragraph("« Écart » : levées faites moins levées au double mort (+ : gagnée par le déclarant ou donnée "
                     "par la défense). « Écart au par » : ce que la table a gagné (+) ou perdu (−) pour Nord-Sud "
                     "par rapport au par, en IMP.", S_notes)
    if len(d["tables"]) > 2 and not expliquer:
        # plusieurs tables : le tableau des tables à côté de la grille, le par dessous (gain de place)
        tc = Table([[P("<b>Tables</b>"), P("<b>Contrat</b>"), P("<b>Lev.</b>"), P("<b>DM</b>"),
                     P("<b>Écart</b>"), P("<b>IMP / par</b>")]] + tr[1:],
                   colWidths=[2.5*cm, 2.0*cm, 1.0*cm, 0.9*cm, 1.2*cm, 1.6*cm], hAlign="LEFT")
        tc.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor(INK)),
            ("LINEBELOW", (0, -1), (-1, -1), 0.4, colors.HexColor("#aab")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
        cote = Table([[dd, tc]], colWidths=[7.6*cm, 10.0*cm])
        cote.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                  ("RIGHTPADDING", (0, 0), (0, 0), 12)]))
        return [KeepTogether([Paragraph("Double mort et par", S_h), cote, Spacer(1, 3),
                              Paragraph(suits(ptxt), S_notes)])]
    if not d["tables"]: return [KeepTogether([Paragraph("Double mort et par", S_h), duo])]
    # le titre reste avec la grille ; le tableau des tables peut suivre sur la page d'après
    return [KeepTogether([Paragraph("Double mort et par", S_h), duo]), Spacer(1, 6),
            KeepTogether([tt] + ([Spacer(1, 3), note] if expliquer else []))]


EXPLICATIONS = ("<b>Double mort et par</b> (en fin de chaque donne). Le tableau donne le nombre de levées que "
                "chaque joueur réalise comme déclarant, cartes vues (double mort). Fond vert : une manche se gagne ; vert soutenu : un "
                "chelem ; cadre : le contrat du par. Le par est le résultat obtenu "
                "si les deux camps enchérissent parfaitement. « Écart » : levées faites moins levées au double "
                "mort (+ : gagnée par le déclarant ou donnée par la défense). « Écart au par » (« IMP / par » quand il y a "
                "plusieurs tables) : ce que la table a gagné (+) ou perdu (−) pour Nord-Sud par rapport au par, "
                "en IMP. Avec plus de deux tables, « Lev. » : levées faites, « DM » : double mort.")

class Marque(Flowable):
    def __init__(self, n): super().__init__(); self.n = n
    def wrap(self, *a): return (0, 0)
    def draw(self):
        doc = self.canv._doctemplate
        doc._donne, doc._debut = self.n, self.canv.getPageNumber()
        if self.n is None: doc._donne = None; return     # Marque(None) : fin des donnes, plus de « (suite) »
        doc._spans[self.n] = [self.canv.getPageNumber(), self.canv.getPageNumber()]

def page(d, a, date, expliquer=True):
    el = [Marque(d["n"]), Paragraph(f"<a name='donne{d['n']}'/>Donne n° {d['n']}", S_title),   # cible des liens de « Vous face au champ »
          Paragraph(f"Donneur : <b>{SEAT[d['donneur']]}</b> &nbsp;·&nbsp; Vulnérable : <b>{seats(d['vul'])}</b> "
                    + (f"&nbsp;·&nbsp; Thème : <b>{d['theme']}</b> – marque {MARQUE_TXT}" if d.get("theme") else f"&nbsp;·&nbsp; Séance du {date} – marque {MARQUE_TXT}"), S_sub),
          Spacer(1, 2), diagram_legende(d, a)]
    if TOURS.get(d["n"]): el[3:3] = [Paragraph(suits(TOURS[d["n"]]), S_sub)]   # le tour, la table, les adversaires
    if d["tables"]:
        el += [Paragraph(f"<a name='res{d['n']}'/>Résultats à la table", S_h)]   # cible des liens de la synthèse
        rang = moi.votre_rang(d["tables"], MES, lambda t: f"{t['contrat']} {SEAT[t['declarant']]} {t['resultat']}".strip())
        if rang: el += [Paragraph(f"<font backColor='{moi.SURLIGNE}'>{suits(rang)}</font>", S_body), Spacer(1, 3)]
        el += [results_table(d, a), Paragraph("Enchères aux tables", S_h)]
    corr = a.get("encheres_corrigees", {})
    cells, notes = [], []
    groupes = {}                        # séquences identiques regroupées (utile à partir de 3 tables)
    absentes = []                       # tables sans enchères enregistrées
    for t in d["tables"]:
        c = corr.get(str(t["table"]))
        bids = c["encheres"] if c else t["encheres"]
        if not bids:
            if t["contrat"] != "passe": absentes.append(str(t["table"]))
            continue
        cle = tuple(complete(bids)) if len(d["tables"]) > 2 else t["table"]
        groupes.setdefault(cle, (complete(bids), []))[1].append(t)
        if c: notes.append(f"Table {t['table']} : {c['note']}")
        elif not t["encheres_ok"]: notes.append(f"Table {t['table']} : séquence enregistrée à vérifier ({t['encheres_msg']}).")
    titre = lambda ts: f"<b>Table{'s' if len(ts) > 1 else ''} {', '.join(str(x) for x in ts)}</b>"
    blocs = [(ts[0]["table"], [Paragraph(titre([t["table"] for t in ts]), S_cell), Spacer(1, 1),
                               bidding(grille(d["donneur"], bids), 2.15*cm)]) for bids, ts in groupes.values()]
    if absentes:                        # une case à sa place, pour ne pas sembler oubliée
        blocs.append((absentes[0], [Paragraph(titre(absentes), S_cell), Spacer(1, 1),
                                    Paragraph("enchères non enregistrées", S_note)]))
    num = lambda x: (str(x).rstrip("0123456789"), int(str(x)[len(str(x).rstrip("0123456789")):] or 0))
    cells = [c for _, c in sorted(blocs, key=lambda b: num(b[0]))]   # dans l'ordre des tables
    if absentes and not groupes and not notes:   # aucune table n'a ses enchères : une ligne suffit, au lieu du titre
        el[-1] = Paragraph(txt("<b>Enchères aux tables :</b> non enregistrées."), S_body); cells = []
    for i in range(0, len(cells), 2):
        row = cells[i:i + 2] + ([[]] if len(cells[i:i + 2]) == 1 else [])
        tb = Table([row], colWidths=[8.8*cm, 8.8*cm])
        tb.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        el += [tb, Spacer(1, 3)]
    for n in notes: el.append(Paragraph(txt(n), S_note))
    if a.get("enc"):
        el.append(Paragraph(f"<a name='reco{d['n']}'/>Enchères recommandées", S_h))
        notes = a.get("notes", "")
        expert = not (a.get("auto") or not notes or MARQUE_COACH in notes)
        if not expert:                                     # le programme : ses explications, puis le conseil du coach
            prog, coach, _ = decouper_avis(notes)
            droite = [Paragraph(txt(prog), S_notes)] + ([Spacer(1, 3), bloc_avis(coach, 8.4*cm, S_notes, "coach")] if coach else [])
        else: droite = colonne_avis("expert", notes, 8.4*cm)[0]        # l'expert : tout est son avis
        gauche = bidding(a["enc"], 2.1*cm)
        if expert and a.get("enc_coach") and a["enc_coach"] != a["enc"]:   # le coach enchérit autrement : ses enchères aussi
            legende = lambda qui, t: Paragraph(f"<font color='{AVIS[qui][1] if qui == 'expert' else INK}'><b>{t}</b></font>", S_notes)
            cas = f"<img src='{CASQUETTE}' width='15' height='9.4' valign='-1.5'/> " if os.path.exists(CASQUETTE) else ""
            gauche = [legende("coach", cas + "Le coach"), bidding(a["enc_coach"], 2.1*cm, "autre"), Spacer(1, 6),
                      legende("expert", "✦ L'expert"), gauche]       # le coach d'abord, comme dans le plan (l'utilisateur)
        side = Table([[gauche, droite]], colWidths=[8.8*cm, 8.6*cm])
        side.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                  ("RIGHTPADDING", (0, 0), (0, 0), 10)]))
        el.append(side)
    seul = a.get("plan") and (a.get("entame") or a.get("defense")) and \
        not any(MARQUE_AVIS in (a.get(k) or "") for k in ("plan", "defense"))
    if seul:                            # sans l'avis de l'expert : le plan et la défense côte à côte, chacun dans sa colonne
        def colonne(titre, texte, tete=()):           # (l'utilisateur, 2026-11-10)
            prog, coach, _ = decouper_avis(texte or "")
            el_ = [Paragraph(titre, S_h)] + list(tete) + [Paragraph(txt(p_), S_avis) for p_ in paragraphes(prog)] if prog.strip() \
                else [Paragraph(titre, S_h)] + list(tete)
            return el_ + (colonne_avis("coach", coach, 8.3*cm) if coach else [])
        e = a.get("entame")
        tete = [Paragraph(txt(f"<b>Entame recommandée :</b> {e['carte']} ({e['joueur']})."), S_titre_avis)] if e else []
        tb = Table([[colonne("Plan de jeu", a["plan"]), colonne("Entame et défense", a.get("defense"), tete)]],
                   colWidths=[8.5*cm, 8.7*cm])
        tb.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (0, 0), 0),
                                ("LEFTPADDING", (1, 0), (1, 0), 12), ("RIGHTPADDING", (0, 0), (0, 0), 12),
                                ("RIGHTPADDING", (1, 0), (1, 0), 0), ("LINEAFTER", (0, 0), (0, 0), 0.5, colors.HexColor("#d5d9de"))]))
        tb.hAlign = "LEFT"
        el += [Spacer(1, 6), bande([tb])]
    if a.get("plan") and not seul:
        el += [Spacer(1, 6), bande([Paragraph("Plan de jeu", S_h)] + avec_avis(a["plan"]))]
    if (a.get("entame") or a.get("defense")) and not seul:
        tete = [Paragraph("Entame et défense", S_h)]
        if a.get("entame"):
            e = a["entame"]
            tete.append(Paragraph(txt(f"<b>Entame recommandée :</b> {e['carte']} ({e['joueur']})."), S_body))
        suite = avec_avis(a["defense"]) if a.get("defense") else []
        el += [KeepTogether(tete + suite[:3])] + suite[3:]   # le titre suit son bloc : jamais seul en bas de page
    texte = lambda x: [Paragraph(txt(p_), S_avis) for p_ in paragraphes(x)]
    titre_comm = "Commentaire sur les contrats joués" if d["tables"] else "Commentaire"
    pc = None if expliquer else annexe(d, pieces=True)
    if pc is None:                      # la première donne (avec les explications) ou pas de double mort : l'ancienne mise en page
        if a.get("comm"): el += [Paragraph(titre_comm, S_h)] + texte(a["comm"])
        if a.get("vues"): el += [Paragraph("Cartes vues (après coup)", S_h)] + texte(a["vues"])
        return el + annexe(d, expliquer) + [PageBreak()]
    # après coup, deux sections comme « Plan de jeu » : un titre sur toute la largeur, puis deux colonnes, chaque texte à
    # côté de ses chiffres (l'utilisateur, 2026-11-10), sur fond blanc : « Commentaire », le tableau des tables à gauche ;
    # puis « Cartes vues », le double mort et le par à gauche.
    def rang(gauche, droite, largeurs=(8.4*cm, 8.9*cm)):
        tb = Table([[gauche, droite]], colWidths=list(largeurs))
        tb.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (0, 0), 10), ("RIGHTPADDING", (1, 0), (1, 0), 0),
                                ("TOPPADDING", (0, 0), (-1, -1), 2)]))
        tb.hAlign = "LEFT"
        return tb
    etiquette = lambda t_: Paragraph(t_, S_titre_avis)
    if a.get("comm"):                   # le commentaire d'abord, sur la bande grise (les sections alternent : plan gris,
                                        # défense blanc, commentaire gris, cartes vues blanc) ; le tableau des tables au double
                                        # mort n'y est plus : il répétait « Résultats à la table » (l'utilisateur, 2026-11-10)
        el += [Spacer(1, 6)] + ([Paragraph(titre_comm, S_h)] + texte(a["comm"]) if seul        # le plan est déjà gris
                                else [bande([Paragraph(titre_comm, S_h)] + texte(a["comm"]))])
    el += [Spacer(1, 4), KeepTogether([Paragraph("Cartes vues (après coup)", S_h),   # sur fond blanc : la grille ressort mieux
           rang([etiquette("Double mort et par"), pc["dd"], Spacer(1, 3), pc["par"]],
                [etiquette("Ce que donnait le contrat recommandé")] + texte(a["vues"]) if a.get("vues") else [])])]
    return el + [PageBreak()]

ROUGE = "#c0392b"
MANCHE = {"SA": 9, "♠": 10, "♥": 10, "♦": 11, "♣": 11}       # les levées d'une manche, par dénomination
# contrats de la synthèse : (fond, encre de la légende, légende)
SENS = {"plus": ("#f4a3a3", "contrat plus élevé que le recommandé"), "moins": ("#bcd7f3", "contrat plus bas")}
FOND_ENTAME = "#fbefb8"


def lire_contrat(c):
    """« 3♥X » -> (3, "♥", 1)."""
    return int(c[0]), c[1:].rstrip("X"), c.count("X")


def _paires(tb, camp):
    """« AB/CD – EF/GH », N-S d'abord, le camp donné ("NS" ou "EO") en gras."""
    ns, eo = (str(tb.get(f"nom_{x}") or tb[f"paire_{x}"]) for x in ("ns", "eo"))
    txt = f"<b>{ns}</b> – {eo}" if camp == "NS" else f"{ns} – <b>{eo}</b>" if camp == "EO" else f"{ns} – {eo}"
    return f"<font backColor='{moi.SURLIGNE}'>{txt}</font>" if moi.a_joue(tb, MES) else txt   # votre table


def _larg_paires(tables):
    """La largeur de la colonne des paires : la paire la plus longue, en gras d'un côté ou de l'autre."""
    w = lambda x, f="DV": pdfmetrics.stringWidth(x, f, S_cell.fontSize)
    noms = [[str(tb.get(f"nom_{x}") or tb[f"paire_{x}"]) for x in ("ns", "eo")] for tb in tables]
    return max([w(" – ") + w(a, "DVB") + w(b) for a, b in noms] + [w(" – ") + w(a) + w(b, "DVB") for a, b in noms]) + 6


def rang_contrat(c):
    """Pour trier les contrats du plus petit au plus grand : palier, puis ♣ ♦ ♥ ♠ SA ; la passe d'abord."""
    if c == "passe": return (0, 0)
    n, den, _ = lire_contrat(c)
    return (n, "♣♦♥♠S".index(den[0]))


def sens_contrat(jeu, reco):
    """« plus » ou « moins » : le contrat d'une table face au recommandé, sans compter le contre ;
    None : même palier et même dénomination, ou contrat joué par l'autre camp : plus haut ou plus
    bas n'y veut rien dire. jeu, reco : (contrat, déclarant), ou "passe"."""
    if "passe" not in (jeu, reco) and (jeu[1] in "NS") != (reco[1] in "NS"): return None
    a, b = (rang_contrat(x if x == "passe" else x[0]) for x in (jeu, reco))
    return "plus" if a > b else "moins" if a < b else None


def _resultat(r):
    """« = », « +1 » ou « −1 »."""
    return "=" if r in ("=", "", 0) else (r if isinstance(r, str) else f"{r:+d}").replace("-", "−")


def page_noms(data, chemin):
    """Page d'ouverture avec --avec-noms : les joueurs de chaque paire. Sans chemin : rien."""
    if not chemin: return []
    noms = json.load(open(chemin))
    cle = lambda k: (len(re.sub(r"\D", "", k)), k)         # 2 avant 10
    rows = [[Paragraph(f"<b>{x}</b>", S_cell) for x in ("Paire", "Initiales", "Joueurs")]]; vous = []
    for k in sorted(noms, key=cle):
        rows.append([Paragraph(k, S_cell), Paragraph(data.get("paires", {}).get(k, {}).get("nom", ""), S_cell),
                     Paragraph(" – ".join(noms[k]), S_cell)])
        if k in MES:                                       # la paire de « Vous êtes » en jaune, comme dans les résultats
            vous.append(("BACKGROUND", (0, len(rows) - 1), (-1, len(rows) - 1), colors.HexColor(moi.SURLIGNE)))
    tb = Table(rows, colWidths=[1.6*cm, 2.6*cm, 13.3*cm], repeatRows=1)
    tb.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor(INK)),
                            ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#c4cbd3"))] + vous))
    return [Paragraph("Joueurs", S_title), Paragraph(f"Séance du {data['session']['date']}", S_sub), Spacer(1, 8), tb, PageBreak()]


def page_parcours(data):
    """Le mouvement, quand la séance le décrit : une ligne par tour (table, donnes, adversaires, votre % moyen)."""
    tours = moi.parcours(data)
    if not tours: return []
    rows = [[Paragraph(f"<b>{x}</b>", S_cell) for x in ("Tour", "Table", "Donnes", "Adversaires", "% du tour")]]
    rows += [[Paragraph(str(t[k]), S_cell) for k in ("tour", "table", "donnes", "adversaires", "pct")] for t in tours]
    tb = Table(rows, colWidths=[1.4*cm, 1.6*cm, 2*cm, 5*cm, 2.2*cm], hAlign="LEFT")
    tb.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor(INK)),
                            ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#c4cbd3"))]))
    return [Paragraph(f"Parcours de {moi.qui_parcourt(data)}", S_h), tb, Spacer(1, 10)]


def _grille(rows, largeurs, style):
    """Une table de la page de synthèse : filet sous l'en-tête, serrée."""
    tb = Table(rows, colWidths=largeurs, repeatRows=1)
    tb.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor(INK)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)] + style))
    return tb


def _groupe(style, debut, fin, bande):
    """Les lignes d'une donne : une bande pâle une fois sur deux, un filet dessous, jamais coupées."""
    if bande: style.append(("BACKGROUND", (0, debut), (-1, fin), colors.HexColor("#f2f5f3")))
    style += [("LINEBELOW", (0, fin), (-1, fin), 0.25, colors.HexColor("#c4cbd3")), ("NOSPLIT", (0, debut), (-1, fin))]


def synthese(data, an):
    """Page de fin : une ligne par donne. Le contrat recommandé, puis combien de tables l'ont joué, ont joué plus haut
    (rouge) ou plus bas (bleu) dans le même camp, ou ont laissé jouer l'autre camp ; votre contrat (coloré de même).
    Les enchères seulement : pas d'entame ici. Le contrat recommandé mène à ses enchères sur la page de la donne, les
    nombres à son tableau des résultats (liens internes du PDF)."""
    if not any(x.get("enc") for x in an.get("donnes", {}).values()): return []   # archive : rien à comparer
    if not any(d["tables"] for d in data["donnes"]): return []    # donnes créées : aucune table à comparer
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from comparer import final                       # import tardif : comparer importe ce module
    P = lambda x, s=S_cell: Paragraph(x, s)
    C = lambda x: P(x, S_cellc)
    vous_col = bool(MES)
    tete = ["N°", "Contrat recommandé", "Même", "Plus haut", "Plus bas", "Autre camp"] + (["Vous"] if vous_col else [])
    rows = [[P(f"<b>{x}</b>") if k < 2 else C(f"<b>{x}</b>") for k, x in enumerate(tete)]]
    style = []; bandes = [("VALIGN", (0, 0), (-1, -1), "MIDDLE")]         # les couleurs passent après les bandes
    tot = {"meme": 0, "plus": 0, "moins": 0, "autre": 0}; N = 0
    for d in data["donnes"]:
        a = an.get("donnes", {}).get(str(d["n"]), {})
        if not a.get("enc") or not d["tables"]: continue
        N += 1
        c, decl, dbl = final(a["enc"], d["donneur"])
        if c == "passe": reco = "passe générale"
        else:
            lev = d["dm"][c[1:]][decl]; marge = lev - int(c[0]) - 6      # rien si le contrat est juste
            levees = "" if marge == 0 else f" ({lev} lev.)" if marge > 0 else f" <font color='{ROUGE}'>({lev} lev.)</font>"
            reco = f"{c}{'X' * dbl} {SEAT[decl]}{levees}"
        meme = "passe" if c == "passe" else (c + "X" * dbl, decl)
        n = {"meme": 0, "plus": 0, "moins": 0, "autre": 0}; vous = None
        for tb in d["tables"]:
            cle = "passe" if tb["contrat"] == "passe" else (tb["contrat"], tb["declarant"])
            sens = None if cle == meme else sens_contrat(cle, meme)
            if sens: genre = sens
            elif cle == meme or "passe" in (cle, meme) or (cle[1] in "NS") == (meme[1] in "NS"): genre = "meme"
            else: genre = "autre"
            n[genre] += 1
            if moi.a_joue(tb, MES):
                jeu = "passe" if cle == "passe" else f"{tb['contrat']} {SEAT[tb['declarant']][0]} {_resultat(tb['resultat'])}"
                vous = (jeu, sens)
        for k in tot: tot[k] += n[k]
        i = len(rows)
        lien = lambda x, cible: f"<a href='#{cible}{d['n']}'>{x}</a>"          # liens internes du PDF
        nombre = lambda k: C(lien(f"<u>{n[k]}</u>", "res") if n[k] else "–")
        ligne = [P(lien(f"<b>{d['n']}</b>", "res")), P(lien(f"<u>{suits(reco)}</u>", "reco")), nombre("meme"), nombre("plus"),
                 nombre("moins"), nombre("autre")]
        if n["plus"]: style.append(("BACKGROUND", (3, i), (3, i), colors.HexColor(SENS["plus"][0])))
        if n["moins"]: style.append(("BACKGROUND", (4, i), (4, i), colors.HexColor(SENS["moins"][0])))
        if vous_col:
            ligne.append(C(suits(vous[0])) if vous else C("–"))
            if vous and vous[1]: style.append(("BACKGROUND", (6, i), (6, i), colors.HexColor(SENS[vous[1]][0])))
        rows.append(ligne)
        _groupe(bandes, i, i, (i - 1) % 2)
    larg = [0.9, 4.2, 1.6, 1.7, 1.6, 1.8] + ([2.6] if vous_col else [])
    larg = [x * 17.6 / sum(larg) for x in larg]
    tb = _grille(rows, [x * cm for x in larg], bandes + style)
    return [Paragraph("Synthèse : recommandé vs joué", S_title),
            Paragraph(f"{N} donnes · combien de tables ont joué le contrat recommandé, plus haut, plus bas, ou l'ont laissé "
                      f"à l'autre camp", S_sub),
            Spacer(1, 4),
            Paragraph("Même camp : " + " ; ".join(
                          f"<font backColor='{SENS[k][0]}'> {SENS[k][1]} </font> ({tot[k]} tables)" for k in SENS) +
                      ". « Même » : le contrat recommandé, par le déclarant ou son partenaire. « Autre camp » : l'autre camp "
                      "joue. Contrat recommandé : ses levées au double mort seulement si elles diffèrent du contrat, en rouge "
                      "s'il chute. Cliquez sur un contrat recommandé pour voir ses enchères, sur un nombre "
                      "pour le tableau des résultats de la donne.", S_note),
            Spacer(1, 4), tb,
            Spacer(1, 6), Paragraph(EXPLICATIONS, S_body), PageBreak()]


def _tables(tbs, total=None):
    """« Table 3 », « Tables 1–4, 6 », ou « Toutes les tables » (numéros consécutifs en plage)."""
    if total and len(tbs) == total > 1: return "Toutes les tables"
    nums = [tb["table"] for tb in tbs]
    if len(nums) == 1: return f"Table {nums[0]}"
    if not all(isinstance(x, int) for x in nums): return "Tables " + ", ".join(map(str, nums))
    plages, debut = [], None
    for k, x in enumerate(sorted(nums)):
        if debut is None: debut = prec = x
        elif x == prec + 1: prec = x
        else: plages.append((debut, prec)); debut = prec = x
    plages.append((debut, prec))
    return "Tables " + ", ".join(str(a) if a == b else f"{a}, {b}" if b == a + 1 else f"{a}–{b}" for a, b in plages)


def main():
    global MES, TOURS, MARQUE_TXT
    data = json.load(open(sys.argv[1])); an = json.load(open(sys.argv[2])); out = sys.argv[3]
    MES = moi.paires(data); DONNEES_SEANCE.update(data); MARQUE_TXT = moi.MARQUES[moi.marque(data)]
    TOURS = {d["n"]: moi.tour_de(data, d["n"]) for d in data["donnes"]}
    date = data["session"]["date"]
    faits = bool(an.get("faits"))                   # Rapports, « Les faits seulement » : ni coach ni expert à l'écran
    pied = an.get("titre_pied", f"{'Relevé' if faits else 'Analyse'} des donnes – séance du {date} – Système SEF, marque {moi.MARQUES[moi.marque(data)]}")
    pied = re.sub(r"marque (IMP|match-points)", f"marque {moi.MARQUES[moi.marque(data)]}", pied)   # la marque de la séance, pas celle d'une analyse
    def footer(c, doc):
        c.saveState(); c.setFont("DV", 7.5); c.setFillColor(colors.HexColor("#888"))
        c.drawString(1.7*cm, 1.0*cm, pied); c.drawRightString(A4[0] - 1.7*cm, 1.0*cm, f"page {doc.page}")
        c.restoreState()
    def suite(c, doc):
        n = getattr(doc, "_donne", None)
        if n is not None:
            doc._spans[n][1] = c.getPageNumber()
            if doc._debut != c.getPageNumber():
                c.saveState(); c.setFont("DVB", 12); c.setFillColor(colors.HexColor(INK))
                c.drawString(1.7*cm, A4[1] - 1.1*cm, f"Donne n° {n} (suite)"); c.restoreState()
    donnes = moi.ordre_des_donnes(data, MES) if moi.ordre_joue() else data["donnes"]   # Réglages : l'ordre joué
    tout = donnes                                   # « Vous face au champ » montre toujours toute la séance
    if an.get("a_revoir"):                          # Rapports, « Seulement les donnes à revoir » : celles du tableau, dans
        import couts                                # son ordre (la plus coûteuse d'abord), sans la synthèse de la séance
        nums = couts.numeros_a_revoir(couts.bilan(donnes, an, MES, moi.marque(data)))
        donnes = [next(d for d in tout if d["n"] == n) for n in nums]
        if not donnes: raise SystemExit("Aucune donne à revoir dans cette séance : rien à mettre dans ce rapport.")
    choix = an.get("choix") or ([an["seule"]] if an.get("seule") else None)
    seule = choix and len(choix) == 1               # Analyse, « Imprimer cette donne » : sa page seule, pour un cours
    if choix:                                       # Rapports, « Choisir les donnes » : celles-là, dans l'ordre du rapport
        donnes = [d for d in donnes if d["n"] in choix]
        if not donnes: raise SystemExit(f"Les donnes {', '.join(map(str, choix))} ne sont pas dans cette séance.")
    pages = set() if seule else set(an.get("pages") or ("champ", "parcours", "synthese"))   # les pages en plus
    vue = {"donnes": {}} if faits else an           # ce que montrent les pages : rien du coach ni de l'expert pour les faits
    synth = None if an.get("a_revoir") or choix or "synthese" not in pages or faits \
        else synthese(dict(data, donnes=donnes), an)  # avec la synthèse, les explications y sont

    def fabriquer(an):
        doc = BaseDocTemplate(out, pagesize=A4, leftMargin=1.7*cm, rightMargin=1.7*cm, topMargin=1.5*cm, bottomMargin=1.5*cm,
                              title=f"Analyse des donnes – {date}", author="Claude")
        doc._spans = {}
        doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(1.7*cm, 1.5*cm, 17.6*cm, 26.7*cm, id="f")],
                                           onPage=footer, onPageEnd=suite)])
        story = [] if "champ" not in pages else \
            page_champ(tout, vue, tours={d["n"]: moi.tour_infos(data, d["n"]) for d in data["donnes"]},
                       marque=moi.marque(data), liens={d["n"] for d in donnes})    # vous avez choisi « Vous êtes » : vous face au champ (la séance en
                                                            # un coup d'œil, page_ensemble, essayée puis écartée : l'utilisateur)
        for k, d in enumerate(donnes):
            story += page(d, vue.get("donnes", {}).get(str(d["n"]), {}), date, expliquer=not synth and k == 0)
        parcours = page_parcours(data) if "parcours" in pages else []   # à la fin : votre parcours, puis la synthèse
        fin = parcours + synth if synth else parcours + [PageBreak()] if parcours else []
        if fin: story += [Marque(None)] + fin
        doc.build((page_noms(data, sys.argv[4] if len(sys.argv) > 4 else None) if not seule else []) + story[:-1])
        return doc, {n: s[1] - s[0] + 1 for n, s in doc._spans.items() if s[1] - s[0] + 1 > 2}

    doc, longues = fabriquer(an)                   # deux pages par donne : un repère, pas une règle (l'utilisateur, 2026-11-09)
    manquantes = [d["n"] for d in data["donnes"] if str(d["n"]) not in an.get("donnes", {})]
    print(f"PDF écrit : {out.replace('.provisoire.pdf', '.pdf')} ({doc.page} pages, {len(donnes)} donnes)")
    if longues: print("ATTENTION, donnes de plus de deux pages :", longues)
    if manquantes and not faits: print("Donnes sans analyse rédigée :", manquantes)

if __name__ == "__main__":
    main()
