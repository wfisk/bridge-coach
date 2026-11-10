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

def txt(t): return suits(seats(t))

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
S_body = st("b", fontSize=9.6, leading=13.2, alignment=4)
S_notes = st("n", fontSize=9.4, leading=12.8)
S_h = st("h", fontName="DVB", fontSize=11, leading=14, textColor=colors.HexColor(GREEN), spaceBefore=5,
         spaceAfter=2, keepWithNext=1)
S_title = st("t", fontName="DVB", fontSize=20, leading=24)
S_sub = st("s", fontSize=9.5, leading=12, textColor=colors.HexColor(GREY))
S_hand = st("hd", fontSize=10.5, leading=14)
S_cell = st("c", fontSize=9, leading=11)
S_cellc = st("cc", fontSize=9.5, leading=12, alignment=1)
S_note = st("ni", fontName="DVI", fontSize=9, leading=11.5, textColor=colors.HexColor(GREY))

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
    def __init__(self, jouee=True): Flowable.__init__(self); self.jouee = jouee
    def wrap(self, aw, ah): self.width = aw; return aw, 66
    def draw(self):
        c = self.canv
        c.setFont("DVB", 8.5); c.setFillColor(colors.HexColor(GREY)); c.drawString(0, 56, "Entame")
        items = [("jouée à une table", 1, False), ("jouée à plusieurs tables", 2, False), ("recommandée", 0, True)]
        for i, (lab, n, reco) in enumerate(items):
            if reco is False and not self.jouee: continue
            y = 38 - i * 17; cx, cy = 9, y + 3
            if reco: c.setFillColor(LEAD_FILL); c.circle(cx, cy, 5.2, stroke=0, fill=1)
            if n:
                c.setStrokeColor(LEAD_INK); c.setLineWidth(0.9); c.circle(cx, cy, 5.2, stroke=1, fill=0)
                if n >= 2: c.circle(cx, cy, 7.4, stroke=1, fill=0)
            c.setFont("DV", 8.5); c.setFillColor(colors.HexColor(GREY)); c.drawString(22, y, lab)

def diagram_legende(d, a):
    t = Table([[diagram(d, a), Legende(bool(d["tables"]))]], colWidths=[12.6*cm, 5.0*cm])
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


def lignes_ensemble(donnes, an):
    """Une ligne par donne, vue de votre camp (de Nord-Sud si vous ne l'avez pas jouée) : {n, vous, reco, texte_reco,
    champ: (min, q1, médiane, q3, max)}. Les % du champ sont ceux des tables ; celui du contrat recommandé, son score au
    double mort face aux tables (comparer.pct_face_aux_tables)."""
    import statistics
    from comparer import table_recommandee
    out = []
    for d in donnes:
        tables = [t for t in d.get("tables") or [] if t.get("pct_ns") is not None]
        if len(tables) < 2: continue
        camp, t = moi.mon_camp(tables, MES)
        vue = lambda p: None if p is None else (p if camp != "EO" else 100 - p)
        pcts = sorted(vue(x["pct_ns"]) for x in tables)
        q1, med, q3 = statistics.quantiles(pcts, n=4, method="inclusive")
        reco = table_recommandee(d, (an.get("donnes") or {}).get(str(d["n"])) or {})
        dire = lambda x: "passe" if x["contrat"] == "passe" else \
            f"{x['contrat']} {SEAT[x['declarant']][0]} {x['resultat'] or '='}".replace("-", "−")
        cle = lambda x: "passe" if x["contrat"] == "passe" else (x["contrat"].rstrip("X"), x["declarant"])
        sens = sens_contrat(cle(t), cle(reco)) if t and reco and cle(t) != cle(reco) else None
        out.append(dict(n=d["n"], vous=vue(t["pct_ns"]) if t else None, reco=vue(reco.get("pct_ns")) if reco else None,
                        texte_vous=dire(t) if t else "", texte_reco=dire(reco) if reco else "", sens=sens,
                        champ=(pcts[0], q1, med, q3, pcts[-1])))
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


def ligne_seance(L):
    """La séance entière : votre % (celui de votre paire dans la séance, sinon la moyenne de vos donnes : c'est la même
    chose quand chaque donne compte autant), la moyenne du contrat recommandé sur les mêmes donnes, et le champ des
    paires (leur % de séance). None si vous n'avez joué aucune donne."""
    import statistics
    jouees = [r for r in L if r["vous"] is not None]
    if not jouees: return None
    paires = DONNEES_SEANCE.get("paires") or {}
    officiel = next((p.get("pct") for k, p in paires.items() if k in MES and p.get("pct") is not None), None)
    vous = officiel if officiel is not None else sum(r["vous"] for r in jouees) / len(jouees)
    recos = [r["reco"] for r in jouees if r["reco"] is not None]
    pcts = sorted(p["pct"] for p in paires.values() if p.get("pct") is not None)
    champ = None
    if len(pcts) >= 2:
        q1, med, q3 = statistics.quantiles(pcts, n=4, method="inclusive"); champ = (pcts[0], q1, med, q3, pcts[-1])
    return dict(vous=vous, reco=sum(recos) / len(recos) if recos else None, champ=champ)


def page_champ(donnes, an, largeur=17.4*cm):
    """Vous face au champ : sur chaque donne, 50 % est la moyenne des tables ; la barre va de 50 % à votre pourcentage,
    à gauche ce que vous perdez face au champ (orange plein), à droite ce que vous gagnez (orange pâle), l'écart écrit à
    droite en points ; la boîte du champ derrière, pour situer l'écart. Puis la séance, et les donnes qui coûtent le plus.
    Les pertes en rouge, les gains en bleu (PERTE_C, GAIN_C : l'utilisateur, 2026-11-10)."""
    from reportlab.graphics.shapes import Drawing, Rect, Line, String
    L = [r for r in lignes_ensemble(donnes, an)]
    jouees = [r for r in L if r["vous"] is not None]
    if not jouees: return []
    G, X0, X1 = 1.3*cm, 1.3*cm, 11.0*cm
    C0, C1, C2 = 11.6*cm, 14.4*cm, 17.2*cm                 # votre contrat, votre %, l'écart (les deux derniers à droite)
    seance = ligne_seance(L)
    h = min(.72*cm, 20.5*cm / (len(L) + 2)); haut = .8*cm; ecart = .45*cm if seance else 0
    D = Drawing(largeur, haut + h * (len(L) + (1 if seance else 0)) + ecart + .2*cm)
    x = lambda p: X0 + (X1 - X0) * p / 100
    Y = D.height - haut
    perdu, gagne = colors.HexColor(PERTE_C), colors.HexColor(GAIN_C)   # rouge ce que vous perdez, bleu ce que vous gagnez
    for p in (0, 25, 75, 100):
        D.add(Line(x(p), 0, x(p), Y, strokeColor=colors.HexColor("#dfe3e7"), strokeWidth=.5))
    for p in (0, 25, 50, 75, 100):
        D.add(String(x(p), Y + .25*cm, f"{p} %", fontName="DVB" if p == 50 else "DV", fontSize=7.5,
                     fillColor=colors.HexColor(INK if p == 50 else GREY), textAnchor="middle"))
    for t_, xx, anc in (("Vous", C0, "start"), ("%", C1, "end"), ("Écart", C2, "end")):
        D.add(String(xx, Y + .25*cm, t_, fontName="DVB", fontSize=7.5, fillColor=colors.HexColor(INK), textAnchor=anc))

    def rangée(y, nom, r, gras=False):
        police = "DVB" if gras else "DV"
        D.add(String(G - .3*cm, y - 2.6, nom, fontName="DVB", fontSize=8.5, fillColor=colors.HexColor(INK), textAnchor="end"))
        b = min(h * .5, .34*cm)
        if r.get("champ"):                                 # le champ, en retrait : moustaches et boîte
            mn, q1, med, q3, mx = r["champ"]
            D.add(Line(x(mn), y, x(mx), y, strokeColor=colors.HexColor(CHAMP_TRAIT), strokeWidth=.8))
            D.add(Rect(x(q1), y - b / 2, max(x(q3) - x(q1), 1), b, fillColor=colors.HexColor(CHAMP_FOND),
                       strokeColor=colors.HexColor(CHAMP_TRAIT), strokeWidth=.5, rx=1.5, ry=1.5))
        if r["vous"] is None:
            D.add(String(C1, y - 2.6, "–", fontName=police, fontSize=7.8, fillColor=colors.HexColor(GREY), textAnchor="end")); return
        v = r["vous"]; perte = v < 50
        D.add(Rect(min(x(v), x(50)), y - b * .45, abs(x(v) - x(50)), b * .9, fillColor=perdu if perte else gagne,
                   strokeColor=None, rx=1.5, ry=1.5))      # la barre : de 50 % à vous
        if r.get("texte_vous"):
            D.add(String(C0, y - 2.6, r["texte_vous"], fontName=police, fontSize=7.8, fillColor=colors.HexColor(INK)))
        D.add(String(C1, y - 2.6, f"{v:.0f} %", fontName=police, fontSize=7.8, fillColor=colors.HexColor(INK), textAnchor="end"))
        e = round(v - 50)
        D.add(String(C2, y - 2.6, ("+" if e > 0 else "") + str(e).replace("-", "−"), fontName="DVB" if perte or gras else "DV",
                     fontSize=7.8, fillColor=colors.HexColor(INK), textAnchor="end"))

    for k, r in enumerate(L):
        y = Y - h * (k + .5)
        if k % 2: D.add(Rect(0, y - h / 2, largeur, h, fillColor=colors.HexColor("#f7f8f9"), strokeColor=None))
        rangée(y, str(r["n"]), r)
    if seance:
        ys = Y - h * len(L) - ecart
        D.add(Line(0, ys + h / 2 + ecart / 2, largeur, ys + h / 2 + ecart / 2, strokeColor=colors.HexColor("#c7ccd2"), strokeWidth=.8))
        rangée(ys - h / 2, "Séance", dict(seance, texte_vous=""), gras=True)
    D.add(Line(x(50), 0, x(50), Y, strokeColor=colors.HexColor(INK), strokeWidth=1))   # le champ : 50 %, au-dessus de tout
    pires = sorted((r for r in jouees if r["vous"] < 50), key=lambda r: r["vous"])[:3]
    phrase = ("Les donnes qui vous coûtent le plus : " + ", ".join(f"{r['n']} ({round(r['vous'] - 50):d})".replace("-", "−")
                                                              for r in pires) + ".") if pires else "Aucune donne sous le champ."
    return [Paragraph("Vous face au champ", S_title),
            Paragraph(txt("Sur chaque donne, 50 % est la moyenne des tables. La barre va de 50 % à votre pourcentage : à "
                          "gauche, en rouge, ce que vous perdez face au champ ; à droite, en bleu, ce que vous gagnez. "
                          "L'écart est en points de pourcentage. " + phrase), S_sub),
            Spacer(1, 8), D, PageBreak()]


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
    D.add(String(R0, Y + .25*cm, "Recommandé (DM)", fontName="DVB", fontSize=7.5, fillColor=colors.HexColor(INK)))
    marques = []                                           # les symboles, posés à la fin : au-dessus des lignes et des boîtes

    def ligne(y, nom, r, gras=False):
        """Une ligne : son nom, le champ en boîte à moustaches, vos deux symboles (posés plus tard), les deux %."""
        D.add(String(G - .3*cm, y - 2.6, nom, fontName="DVB", fontSize=8.5, fillColor=colors.HexColor(INK), textAnchor="end"))
        if r["champ"]: boite(y, r["champ"])
        if r["reco"] is not None: marques.append(("reco", x(r["reco"]), y))
        if r["vous"] is not None: marques.append(("vous", x(r["vous"]), y))
        police = "DVB" if gras else "DV"
        ecrire = lambda xx, t_, ancre="start": D.add(String(xx, y - 2.6, t_, fontName=police, fontSize=7.8,
                                                            fillColor=colors.HexColor(INK), textAnchor=ancre))
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
    for t in moi.ordre(d["tables"] + ([reco] if reco else []), MES):   # du meilleur au moins bon, vu de votre camp
        res = "=" if t["resultat"] in ("=", "") else t["resultat"]
        passe = t["contrat"] == "passe"
        jeu = "passe générale" if passe else f"<b>{t['contrat']} {SEAT[t['declarant']]}</b> {res}"
        if t.get("recommande"):
            row = [P("<i>Recommandé" + (" (DM)" if not passe else "") + "</i>"), P(suits(jeu)), P(suits(t["entame"])),
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
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)] + vous))
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
                            ("LINEBEFORE", (0, 0), (0, -1), 2, colors.HexColor(trait)), ("LEFTPADDING", (0, 0), (-1, -1), 6),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    tb.hAlign = "LEFT"
    return tb


def avec_avis(texte):
    """Le texte du programme, puis le conseil du coach et l'avis de l'expert, chacun dans son bloc."""
    prog, coach, expert = decouper_avis(texte)
    el = [Paragraph(txt(prog), S_body)] if prog.strip() else []   # le plan du coach n'a pas de texte avant son bloc
    for qui, avis in (("coach", coach), ("expert", expert)):
        if avis: el += ([Spacer(1, 2)] if el else []) + [bloc_avis(avis, 17.4*cm, S_body, qui)]
    return el


def annexe(d, expliquer=True):
    if not d.get("dm"): return [Spacer(1, 1)]
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
                   P(str(dm)), P(ec), P(f"{ecp:+d}" if ecp else "0")])
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
                     P("<b>Écart</b>"), P("<b>Par</b>")]] + tr[1:],
                   colWidths=[2.3*cm, 2.3*cm, 1.3*cm, 1.1*cm, 1.6*cm, 1.3*cm], hAlign="LEFT")
        tc.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor(INK)),
            ("LINEBELOW", (0, -1), (-1, -1), 0.4, colors.HexColor("#aab")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
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
                "mort (+ : gagnée par le déclarant ou donnée par la défense). « Écart au par » (« Par » quand il y a "
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
    el = [Marque(d["n"]), Paragraph(f"Donne n° {d['n']}", S_title),
          Paragraph(f"Donneur : <b>{SEAT[d['donneur']]}</b> &nbsp;·&nbsp; Vulnérable : <b>{seats(d['vul'])}</b> "
                    + (f"&nbsp;·&nbsp; Thème : <b>{d['theme']}</b> – marque IMP" if d.get("theme") else f"&nbsp;·&nbsp; Séance du {date} – marque IMP"), S_sub),
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
    for i in range(0, len(cells), 2):
        row = cells[i:i + 2] + ([[]] if len(cells[i:i + 2]) == 1 else [])
        tb = Table([row], colWidths=[8.8*cm, 8.8*cm])
        tb.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        el += [tb, Spacer(1, 3)]
    for n in notes: el.append(Paragraph(txt(n), S_note))
    if a.get("enc"):
        el.append(Paragraph(f"<a name='reco{d['n']}'/>Enchères recommandées (SEF)", S_h))
        notes = a.get("notes", "")
        expert = not (a.get("auto") or not notes or MARQUE_COACH in notes)
        if not expert:                                     # le programme : ses explications, puis le conseil du coach
            prog, coach, _ = decouper_avis(notes)
            droite = [Paragraph(txt(prog), S_notes)] + ([Spacer(1, 3), bloc_avis(coach, 8.4*cm, S_notes, "coach")] if coach else [])
        else: droite = bloc_avis(notes, 8.4*cm, S_notes)        # l'expert : tout est son avis
        gauche = bidding(a["enc"], 2.1*cm)
        if expert and a.get("enc_coach") and a["enc_coach"] != a["enc"]:   # le coach enchérit autrement : ses enchères aussi
            legende = lambda qui, t: Paragraph(f"<font color='{AVIS[qui][1] if qui == 'expert' else INK}'><b>{t}</b></font>", S_notes)
            cas = f"<img src='{CASQUETTE}' width='15' height='9.4' valign='-1.5'/> " if os.path.exists(CASQUETTE) else ""
            gauche = [legende("expert", "✦ L'expert"), gauche, Spacer(1, 6), legende("coach", cas + "Le coach"),
                      bidding(a["enc_coach"], 2.1*cm, "autre")]
        side = Table([[gauche, droite]], colWidths=[8.8*cm, 8.6*cm])
        side.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                  ("RIGHTPADDING", (0, 0), (0, 0), 10)]))
        el.append(side)
    if a.get("plan"):
        el += [Paragraph("Plan de jeu", S_h)] + avec_avis(a["plan"])
    if a.get("entame") or a.get("defense"):
        el.append(Paragraph("Entame et défense", S_h))
        if a.get("entame"):
            e = a["entame"]
            el.append(Paragraph(txt(f"<b>Entame recommandée :</b> {e['carte']} ({e['joueur']})."), S_body))
        if a.get("defense"):
            el += avec_avis(a["defense"])
    if a.get("comm"):
        el += [Paragraph("Commentaire sur les contrats joués" if d["tables"] else "Commentaire", S_h), Paragraph(txt(a["comm"]), S_body)]
    if a.get("vues"):
        el += [Paragraph("Cartes vues (après coup)", S_h), Paragraph(txt(a["vues"]), S_body)]
    el += annexe(d, expliquer) + [PageBreak()]
    return el

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
    rows = [[Paragraph(f"<b>{x}</b>", S_cell) for x in ("Paire", "Initiales", "Joueurs")]]
    for k in sorted(noms, key=cle):
        rows.append([Paragraph(k, S_cell), Paragraph(data.get("paires", {}).get(k, {}).get("nom", ""), S_cell),
                     Paragraph(" – ".join(noms[k]), S_cell)])
    tb = Table(rows, colWidths=[1.6*cm, 2.6*cm, 13.3*cm], repeatRows=1)
    tb.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor(INK)),
                            ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#c4cbd3"))]))
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
    global MES, TOURS
    data = json.load(open(sys.argv[1])); an = json.load(open(sys.argv[2])); out = sys.argv[3]
    MES = moi.paires(data); DONNEES_SEANCE.update(data)
    TOURS = {d["n"]: moi.tour_de(data, d["n"]) for d in data["donnes"]}
    date = data["session"]["date"]
    pied = an.get("titre_pied", f"Analyse des donnes – séance du {date} – Système SEF, marque IMP")
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
    synth = synthese(dict(data, donnes=donnes), an)  # avec la page de synthèse, les explications y sont

    def fabriquer(an):
        doc = BaseDocTemplate(out, pagesize=A4, leftMargin=1.7*cm, rightMargin=1.7*cm, topMargin=1.5*cm, bottomMargin=1.5*cm,
                              title=f"Analyse des donnes – {date}", author="Claude")
        doc._spans = {}
        doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(1.7*cm, 1.5*cm, 17.6*cm, 26.7*cm, id="f")],
                                           onPage=footer, onPageEnd=suite)])
        story = page_ensemble(donnes, an or {"donnes": {}})   # vous avez choisi « Vous êtes » : la séance en un coup d'œil
        if story: story += page_ensemble(donnes, an or {"donnes": {}}, style="haltere")   # page 2, à comparer (essai)
        if story: story += page_champ(donnes, an or {"donnes": {}})                          # page 3 : vous face au champ
        for k, d in enumerate(donnes):
            story += page(d, an.get("donnes", {}).get(str(d["n"]), {}), date, expliquer=not synth and k == 0)
        parcours = page_parcours(data)             # à la fin : votre parcours, puis la synthèse
        fin = parcours + synth if synth else parcours + [PageBreak()] if parcours else []
        if fin: story += [Marque(None)] + fin
        doc.build(page_noms(data, sys.argv[4] if len(sys.argv) > 4 else None) + story[:-1])
        return doc, {n: s[1] - s[0] + 1 for n, s in doc._spans.items() if s[1] - s[0] + 1 > 2}

    doc, longues = fabriquer(an)                   # deux pages par donne : un repère, pas une règle (l'utilisateur, 2026-11-09)
    manquantes = [d["n"] for d in data["donnes"] if str(d["n"]) not in an.get("donnes", {})]
    print(f"PDF écrit : {out.replace('.provisoire.pdf', '.pdf')} ({doc.page} pages, {len(data['donnes'])} donnes)")
    if longues: print("ATTENTION, donnes de plus de deux pages :", longues)
    if manquantes: print("Donnes sans analyse rédigée :", manquantes)

if __name__ == "__main__":
    main()
