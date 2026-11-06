# -*- coding: utf-8 -*-
"""Construit le PDF d'analyse à partir des données du .bws et de l'analyse rédigée.

Usage : python3 build_pdf.py donnes.json analyse.json sortie.pdf

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
      "defense": "commentaire sur l'entame et la défense"
    }, ...
  }
}
Dans les textes : N, S, E, O isolés et N-S / E-O sont écrits en toutes lettres automatiquement ;
<b>…</b> et <br/> sont acceptés ; ♥ et ♦ sont colorés en rouge.
Mise en page : chaque donne commence sur une nouvelle page, deux pages au maximum,
tailles de police fixes (ne jamais réduire).
"""
import sys, re, json, glob
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
    hits = glob.glob(f"/usr/share/fonts/**/{name}", recursive=True)
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
    t = re.sub(r"(?<![\w♠♥♦♣])([NSEO])(?![\w♠♥♦♣])", lambda m: SEAT[m.group(1)], t)
    return t.replace("de Est", "d'Est").replace("de Ouest", "d'Ouest")

def txt(t): return suits(seats(t))

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
    """Légende des repères d'entame (verticale, à droite du diagramme)."""
    def wrap(self, aw, ah): self.width = aw; return aw, 66
    def draw(self):
        c = self.canv
        c.setFont("DVB", 8.5); c.setFillColor(colors.HexColor(GREY)); c.drawString(0, 56, "Entame")
        items = [("jouée à une table", 1, False), ("jouée aux deux tables", 2, False), ("recommandée", 0, True)]
        for i, (lab, n, reco) in enumerate(items):
            y = 38 - i * 17; cx, cy = 9, y + 3
            if reco: c.setFillColor(LEAD_FILL); c.circle(cx, cy, 5.2, stroke=0, fill=1)
            if n:
                c.setStrokeColor(LEAD_INK); c.setLineWidth(0.9); c.circle(cx, cy, 5.2, stroke=1, fill=0)
                if n >= 2: c.circle(cx, cy, 7.4, stroke=1, fill=0)
            c.setFont("DV", 8.5); c.setFillColor(colors.HexColor(GREY)); c.drawString(22, y, lab)

def diagram_legende(d, a):
    t = Table([[diagram(d, a), Legende()]], colWidths=[12.6*cm, 5.0*cm])
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

def results_table(d):
    P = lambda x: Paragraph(x, S_cell)
    rows = [[P("<b>Paires</b>"), P("<b>Contrat</b>"), P("<b>Entame</b>"), P("<b>Nord-Sud</b>"), P("<b>IMP N-S</b>")]]
    for t in d["tables"]:
        res = "=" if t["resultat"] in ("=", "") else t["resultat"]
        rows.append([P(f"{t['paire_ns']}-{t['paire_eo']}"), P(suits(f"{t['contrat']} {SEAT[t['declarant']]} {res}")),
                     P(suits(t["entame"])), P(f"{t['score_ns']:+d}"), P(f"{t['imp_ns']:+d}" if t["imp_ns"] else "0")])
    tb = Table(rows, colWidths=[2.2*cm, 3.6*cm, 2.2*cm, 2.2*cm, 2.2*cm], hAlign="LEFT")
    tb.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor(INK)),
        ("LINEBELOW", (0, -1), (-1, -1), 0.4, colors.HexColor("#aab")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
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

def annexe(d):
    if not d.get("dm"): return Spacer(1, 1)
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
    duo = Table([[dd, [Paragraph(suits(ptxt), S_notes), Spacer(1, 6), Paragraph(expl, S_notes)]]], colWidths=[7.6*cm, 10.0*cm])
    duo.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (0, 0), 12)]))
    P = lambda x: Paragraph(x, S_cell)
    tr = [[P("<b>Table</b>"), P("<b>Contrat</b>"), P("<b>Levées faites</b>"), P("<b>Double mort</b>"),
           P("<b>Écart</b>"), P("<b>Écart au par (IMP)</b>")]]
    for t in d["tables"]:
        if t["levees"] is None: continue
        ec = "=" if t["levees"] == t["dm"] else f"{t['levees'] - t['dm']:+d}"
        tr.append([P(f"Table {t['table']}"), P(suits(f"{t['contrat']} {SEAT[t['declarant']]}")), P(str(t["levees"])),
                   P(str(t["dm"])), P(ec), P(f"{t['ecart_par_imp']:+d}" if t["ecart_par_imp"] else "0")])
    tt = Table(tr, colWidths=[1.8*cm, 3.6*cm, 2.6*cm, 2.6*cm, 1.6*cm, 3.4*cm], hAlign="LEFT")
    tt.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor(INK)),
        ("LINEBELOW", (0, -1), (-1, -1), 0.4, colors.HexColor("#aab")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    note = Paragraph("« Écart » : levées faites moins levées au double mort (+ : gagnée par le déclarant ou donnée "
                     "par la défense). « Écart au par » : ce que la table a gagné (+) ou perdu (−) pour Nord-Sud "
                     "par rapport au par, en IMP.", S_notes)
    return KeepTogether([Paragraph("Double mort et par", S_h), duo, Spacer(1, 6), tt, Spacer(1, 3), note])

class Marque(Flowable):
    def __init__(self, n): super().__init__(); self.n = n
    def wrap(self, *a): return (0, 0)
    def draw(self):
        doc = self.canv._doctemplate
        doc._donne, doc._debut = self.n, self.canv.getPageNumber()
        doc._spans[self.n] = [self.canv.getPageNumber(), self.canv.getPageNumber()]

def page(d, a, date):
    el = [Marque(d["n"]), Paragraph(f"Donne n° {d['n']}", S_title),
          Paragraph(f"Donneur : <b>{SEAT[d['donneur']]}</b> &nbsp;·&nbsp; Vulnérable : <b>{seats(d['vul'])}</b> "
                    f"&nbsp;·&nbsp; Séance du {date} – marque IMP", S_sub),
          Spacer(1, 2), diagram_legende(d, a), Paragraph("Résultats à la table", S_h), results_table(d),
          Paragraph("Enchères aux tables", S_h)]
    corr = a.get("encheres_corrigees", {})
    cells, notes = [], []
    for t in d["tables"]:
        c = corr.get(str(t["table"]))
        bids = c["encheres"] if c else t["encheres"]
        cells.append([Paragraph(f"<b>Table {t['table']}</b> (paires {t['paire_ns']}-{t['paire_eo']})", S_cell),
                      Spacer(1, 1), bidding(grille(d["donneur"], complete(bids)), 2.15*cm)])
        if c: notes.append(f"Table {t['table']} : {c['note']}")
        elif not t["encheres_ok"]: notes.append(f"Table {t['table']} : séquence enregistrée à vérifier ({t['encheres_msg']}).")
    for i in range(0, len(cells), 2):
        row = cells[i:i + 2] + ([[]] if len(cells[i:i + 2]) == 1 else [])
        tb = Table([row], colWidths=[8.8*cm, 8.8*cm])
        tb.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        el += [tb, Spacer(1, 3)]
    for n in notes: el.append(Paragraph(txt(n), S_note))
    if a.get("enc"):
        el.append(Paragraph("Enchères recommandées (SEF)", S_h))
        side = Table([[bidding(a["enc"], 2.1*cm), Paragraph(txt(a.get("notes", "")), S_notes)]], colWidths=[8.8*cm, 8.6*cm])
        side.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                  ("RIGHTPADDING", (0, 0), (0, 0), 10)]))
        el.append(side)
    if a.get("plan"):
        el += [Paragraph("Plan de jeu", S_h), Paragraph(txt(a["plan"]), S_body)]
    if a.get("entame") or a.get("defense"):
        el.append(Paragraph("Entame et défense", S_h))
        if a.get("entame"):
            e = a["entame"]
            el.append(Paragraph(txt(f"<b>Entame recommandée :</b> {e['carte']} ({e['joueur']})."), S_body))
        if a.get("defense"):
            el.append(Paragraph(txt(a["defense"]), S_body))
    if a.get("comm"):
        el += [Paragraph("Commentaire sur les contrats joués", S_h), Paragraph(txt(a["comm"]), S_body)]
    el += [annexe(d), PageBreak()]
    return el

def main():
    data = json.load(open(sys.argv[1])); an = json.load(open(sys.argv[2])); out = sys.argv[3]
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
    story = []
    for d in data["donnes"]:
        story += page(d, an.get("donnes", {}).get(str(d["n"]), {}), date)
    doc.build(story[:-1])
    longues = {n: s[1] - s[0] + 1 for n, s in doc._spans.items() if s[1] - s[0] + 1 > 2}
    manquantes = [d["n"] for d in data["donnes"] if str(d["n"]) not in an.get("donnes", {})]
    print(f"PDF écrit : {out} ({doc.page} pages, {len(data['donnes'])} donnes)")
    if longues: print("ATTENTION, donnes de plus de deux pages :", longues)
    if manquantes: print("Donnes sans analyse rédigée :", manquantes)

if __name__ == "__main__":
    main()
