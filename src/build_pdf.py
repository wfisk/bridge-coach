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
MES = set()                     # les paires de l'utilisateur dans cette séance (moi.py) : leurs lignes sont surlignées
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

MARQUE_AVIS = "<br/><b>Avis de l'expert :</b>"

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

def results_table(d):
    P = lambda x: Paragraph(x, S_cell)
    beaucoup = len(d["tables"]) > 2
    entete = ["<b>Paires</b>", "<b>Contrat</b>", "<b>Entame</b>", "<b>Nord-Sud</b>", "<b>IMP N-S</b>"]
    if beaucoup: entete = ["<b>Table</b>"] + entete + ["<b>% N-S</b>"]
    rows = [[P(x) for x in entete]]; vous = []
    for t in moi.ordre(d["tables"], MES):  # du meilleur résultat au moins bon, vu de votre camp (moi.ordre)
        res = "=" if t["resultat"] in ("=", "") else t["resultat"]
        passe = t["contrat"] == "passe"
        jeu = "passe générale" if passe else f"<b>{t['contrat']} {SEAT[t['declarant']]}</b> {res}"
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

def bidding(rows_, w):
    rows = [[Paragraph(f"<b>{x}</b>", S_cellc) for x in ("Ouest", "Nord", "Est", "Sud")]]
    rows += [[Paragraph(suits(x), S_cellc) for x in r] for r in rows_]
    t = Table(rows, colWidths=[w]*4)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6efe9")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#9fb5a8")),
        ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
    return t

def bloc_avis(texte, largeur, style):
    """L'avis de l'expert : fond vert pâle (celui des en-têtes d'enchères) et trait vert à gauche."""
    tb = Table([[Paragraph(txt(f"<font color='{GREEN}'>✦</font> " + MARQUE_AVIS[5:] + " " + texte.strip()), style)]], colWidths=[largeur])
    tb.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e6efe9")),
                            ("LINEBEFORE", (0, 0), (0, -1), 2, colors.HexColor(GREEN)), ("LEFTPADDING", (0, 0), (-1, -1), 6),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    tb.hAlign = "LEFT"
    return tb


def avec_avis(texte):
    """Le texte du programme, puis l'avis de l'expert qui le suit après MARQUE_AVIS."""
    prog, _, avis = texte.partition(MARQUE_AVIS)
    return [Paragraph(txt(prog), S_body)] + ([Spacer(1, 2), bloc_avis(avis, 17.4*cm, S_body)] if avis else [])


def annexe(d, expliquer=True):
    if not d.get("dm"): return [Spacer(1, 1)]
    rows = [[Paragraph("", S_cellc)] + [Paragraph(f"<b>{x}</b>", S_cellc) for x in ("Nord", "Sud", "Est", "Ouest")]]
    for lab in ("SA", "♠", "♥", "♦", "♣"):
        rows.append([Paragraph(suits(f"<b>{lab}</b>"), S_cellc)] +
                    [Paragraph(str(d["dm"][lab][p]), S_cellc) for p in "NSEO"])
    dd = Table(rows, colWidths=[1.0*cm] + [1.6*cm]*4)
    dd.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6efe9")),
        ("BACKGROUND", (1, 1), (2, -1), colors.HexColor("#f6f8fb")), ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#9fb5a8")),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    p = d.get("par")
    if p is None:
        ptxt = "<b>Par :</b> passe générale (0)."
    else:
        camp = "Nord-Sud" if p["declarant"] in "NS" else "Est-Ouest"
        ptxt = (f"<b>Par :</b> {p['contrat']}{' contré' if p['contre'] else ''} par {SEAT[p['declarant']]} ({camp}), "
                f"{p['resultat']}, soit <b>{p['score_ns']:+d}</b> pour Nord-Sud.")
    expl = ("Le tableau donne le nombre de levées que chaque joueur réalise comme déclarant, cartes vues "
            "(double mort). Le par est le résultat obtenu si les deux camps enchérissent parfaitement.")
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
                "chaque joueur réalise comme déclarant, cartes vues (double mort). Le par est le résultat obtenu "
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
        doc._spans[self.n] = [self.canv.getPageNumber(), self.canv.getPageNumber()]

def page(d, a, date, expliquer=True):
    el = [Marque(d["n"]), Paragraph(f"Donne n° {d['n']}", S_title),
          Paragraph(f"Donneur : <b>{SEAT[d['donneur']]}</b> &nbsp;·&nbsp; Vulnérable : <b>{seats(d['vul'])}</b> "
                    + (f"&nbsp;·&nbsp; Thème : <b>{d['theme']}</b> – marque IMP" if d.get("theme") else f"&nbsp;·&nbsp; Séance du {date} – marque IMP"), S_sub),
          Spacer(1, 2), diagram_legende(d, a)]
    if d["tables"]:
        el += [Paragraph("Résultats à la table", S_h)]
        rang = moi.votre_rang(d["tables"], MES, lambda t: f"{t['contrat']} {SEAT[t['declarant']]} {t['resultat']}".strip())
        if rang: el += [Paragraph(f"<font backColor='{moi.SURLIGNE}'>{suits(rang)}</font>", S_body), Spacer(1, 3)]
        el += [results_table(d), Paragraph("Enchères aux tables", S_h)]
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
        el.append(Paragraph("Enchères recommandées (SEF)", S_h))
        notes = a.get("notes", "")
        droite = Paragraph(txt(notes), S_notes) if a.get("auto") or not notes else bloc_avis(notes, 8.4*cm, S_notes)
        side = Table([[bidding(a["enc"], 2.1*cm), droite]], colWidths=[8.8*cm, 8.6*cm])
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
    """Page d'ouverture : les donnes où le contrat d'une table diffère du contrat recommandé. Une
    ligne par table, du plus petit contrat au plus grand : ses paires, son contrat, en rouge s'il
    est plus élevé et en bleu s'il est plus bas (SENS), son résultat. Dessous, les entames qui
    diffèrent, comparées seulement aux tables qui jouent dans la même dénomination."""
    if not any(x.get("enc") for x in an.get("donnes", {}).values()): return []   # archive : rien à comparer
    if not any(d["tables"] for d in data["donnes"]): return []    # donnes créées : aucune table à comparer
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from comparer import final                       # import tardif : comparer importe ce module
    P = lambda x, s=S_cell: Paragraph(x, s)
    S_centre = ParagraphStyle("centre", parent=S_cell, alignment=1)
    larg = min(_larg_paires([tb for d in data["donnes"] for tb in d["tables"]]), 3.1*cm)
    contrats = [[P("<b>N°</b>"), P("<b>Contrat recommandé</b>"), P("<b>Contrats aux tables</b>"), "", P("<b>Résultat</b>", S_centre)]]
    entames = [[P("<b>N°</b>"), P("<b>Contrat recommandé</b>"), P("<b>Contrats aux tables</b>"), "",
                P("<b>Entame recom.</b>", S_centre), P("<b>Entame jouée</b>", S_centre)]]
    st_c = [("SPAN", (2, 0), (3, 0)), ("LEFTPADDING", (4, 1), (4, -1), 19)]
    st_e = [("SPAN", (2, 0), (3, 0)), ("LEFTPADDING", (4, 1), (5, -1), 37)]
    fonds_c, fonds_e = [], []                        # les couleurs passent après les bandes
    n_sens = {k: 0 for k in SENS}; memes = []; N = 0; n_c = n_e = 0
    for d in data["donnes"]:
        a = an.get("donnes", {}).get(str(d["n"]), {})
        if not a.get("enc"): continue
        N += 1
        c, decl, dbl = final(a["enc"], d["donneur"])
        if c == "passe": reco = "passe générale"
        else:
            lev = d["dm"][c[1:]][decl]; marge = lev - int(c[0]) - 6      # rien si le contrat est juste
            levees = "" if marge == 0 else f" ({lev} lev.)" if marge > 0 else f" <font color='{ROUGE}'>({lev} lev.)</font>"
            reco = f"{c}{'X' * dbl} {SEAT[decl]}{levees}"
        e = a.get("entame"); carte = e.get("carte") if isinstance(e, dict) else None
        meme = "passe" if c == "passe" else (c + "X" * dbl, decl)
        autres, leads = [], []
        for tb in d["tables"]:
            cle = "passe" if tb["contrat"] == "passe" else (tb["contrat"], tb["declarant"])
            jeu = "passe générale" if cle == "passe" else f"<b>{cle[0]} {SEAT[cle[1]]}</b>"
            camp = None if cle == "passe" else "NS" if cle[1] in "NS" else "EO"
            ligne = (rang_contrat(tb["contrat"]), _paires(tb, camp), jeu)
            if cle != meme:
                sens = sens_contrat(cle, meme)
                autres.append(ligne + (sens, "" if cle == "passe" else _resultat(tb["resultat"])))
                if sens: n_sens[sens] += 1
            # l'entame : seulement dans la même dénomination que le contrat recommandé
            if carte and c != "passe" and cle != "passe" and tb["contrat"].rstrip("X")[1:] == c[1:] and tb.get("entame") != carte:
                leads.append(ligne + (tb.get("entame"),))
        if autres:
            autres.sort(key=lambda x: x[0]); debut = len(contrats)      # du plus petit contrat au plus grand
            for k, (_, paires, jeu, sens, res) in enumerate(autres):
                i = len(contrats)
                contrats.append([P(f"<b>{d['n']}</b>") if k == 0 else "", P(suits(reco)) if k == 0 else "",
                                 P(paires), P(suits(jeu)), P(res) if res else ""])
                if sens: fonds_c.append(("BACKGROUND", (2, i), (3, i), colors.HexColor(SENS[sens][0])))
            _groupe(st_c, debut, len(contrats) - 1, n_c % 2); n_c += 1
        else: memes.append(str(d["n"]))
        if leads:
            leads.sort(key=lambda x: x[0]); debut = len(entames)
            for k, (_, paires, jeu, jouee) in enumerate(leads):
                i = len(entames)
                entames.append([P(str(d["n"])) if k == 0 else "", P(suits(reco)) if k == 0 else "", P(paires), P(suits(jeu)),
                                P(suits(carte)) if k == 0 else "", P(suits(jouee))])
                fonds_e.append(("BACKGROUND", (5, i), (5, i), colors.HexColor(FOND_ENTAME)))
            _groupe(st_e, debut, len(entames) - 1, n_e % 2); n_e += 1
    corps = []
    if n_c: corps.append(_grille(contrats, [0.9*cm, 4.2*cm, larg, 10.6*cm - larg, 1.8*cm], st_c + fonds_c))
    if memes: corps += [Spacer(1, 4), Paragraph(f"Même contrat à toutes les tables : donnes {', '.join(memes)}.", S_body)]
    if n_e: corps += [Paragraph("Entames différentes, dans la même dénomination", S_h), Spacer(1, 2),
                      _grille(entames, [0.9*cm, 4.2*cm, larg, 6.0*cm - larg, 3.2*cm, 3.2*cm], st_e + fonds_e)]
    return [Paragraph("Synthèse : recommandé vs joué", S_title),
            Paragraph(f"{N} donnes · les contrats joués aux tables quand ils diffèrent du contrat recommandé", S_sub),
            Spacer(1, 4),
            Paragraph("Même camp : " + " ; ".join(
                          f"<font backColor='{SENS[k][0]}'> {SENS[k][1]} </font> ({n_sens[k]} tables)" for k in SENS) +
                      ". Sans couleur : l'autre camp joue, ou le partenaire joue le même contrat. Résultat : ce que la "
                      "table a fait. En gras : la paire qui joue le contrat. Contrat recommandé : ses levées au double "
                      "mort seulement si elles diffèrent du contrat, en rouge s'il chute.", S_note),
            Spacer(1, 4)] + corps + \
           [Spacer(1, 4), Paragraph(EXPLICATIONS, S_body)] + \
           [PageBreak()]


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
    global MES
    data = json.load(open(sys.argv[1])); an = json.load(open(sys.argv[2])); out = sys.argv[3]
    MES = moi.paires(data)
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
    doc = BaseDocTemplate(out, pagesize=A4, leftMargin=1.7*cm, rightMargin=1.7*cm, topMargin=1.5*cm, bottomMargin=1.5*cm,
                          title=f"Analyse des donnes – {date}", author="Claude")
    doc._spans = {}
    doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(1.7*cm, 1.5*cm, 17.6*cm, 26.7*cm, id="f")],
                                       onPage=footer, onPageEnd=suite)])
    story = synthese(data, an)                     # avec la page de synthèse, les explications y sont
    for d in data["donnes"]:
        story += page(d, an.get("donnes", {}).get(str(d["n"]), {}), date, expliquer=not story)
    doc.build(page_noms(data, sys.argv[4] if len(sys.argv) > 4 else None) + story[:-1])
    longues = {n: s[1] - s[0] + 1 for n, s in doc._spans.items() if s[1] - s[0] + 1 > 2}
    manquantes = [d["n"] for d in data["donnes"] if str(d["n"]) not in an.get("donnes", {})]
    print(f"PDF écrit : {out.replace('.provisoire.pdf', '.pdf')} ({doc.page} pages, {len(data['donnes'])} donnes)")
    if longues: print("ATTENTION, donnes de plus de deux pages :", longues)
    if manquantes: print("Donnes sans analyse rédigée :", manquantes)

if __name__ == "__main__":
    main()
