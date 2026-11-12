# -*- coding: utf-8 -*-
"""Fichier, Exporter : une séance Bridge Coach vers d'autres formats, écrits à côté de son .bc.json.

  PBN    les donnes (Bridgemate : Fichier, Importer ; la plupart des logiciels de bridge) : <nom>.pbn
  CSV    un tableau (les résultats des tables, les donnes ou les paires), séparé par des points-virgules, en UTF-8
         avec BOM et virgule décimale : Excel en français l'ouvre tel quel. <nom>-resultats.csv, -donnes.csv, -paires.csv
  Excel  un classeur .xlsx avec une feuille par tableau, plus la feuille « Séance » : <nom>.xlsx. Écrit ici même (un
         .xlsx est un zip de fichiers XML) : aucune bibliothèque à installer, ni chez vous ni chez les membres du club.

Les joueurs sont en initiales, comme dans les rapports ; noms=True ajoute les noms complets (pour vous seul).
"""
import os, csv, io, zipfile, datetime
from xml.sax.saxutils import escape

import rapport

SIEGES = ("N", "E", "S", "O")
NOM_SIEGE = {"N": "Nord", "E": "Est", "S": "Sud", "O": "Ouest"}
TABLEAUX = (("resultats", "Résultats"), ("donnes", "Donnes"), ("paires", "Paires"))


def base(c):
    return c[:-len(rapport.BC)] if c.endswith(rapport.BC) else os.path.splitext(c)[0]


def lire(c):
    return rapport.lire_bc(c)


# ---------------------------------------------------------------- les tableaux
def main_txt(m):
    """« - A9742 AX76 D984 » → « ♠ –  ♥ A9742  ♦ AX76  ♣ D984 »."""
    return "  ".join(f"{s} {'–' if x == '-' else x}" for s, x in zip("♠♥♦♣", (m or "- - - -").split()))


def recommande(data, n, donneur):
    """Le contrat recommandé de la donne (l'expert, sinon le coach), « 4♥ S », ou ""."""
    ans = data.get("analyses") or {}
    for q in ("expert", "standard"):
        a = ((ans.get(q) or {}).get("donnes") or {}).get(str(n)) or {}
        if a.get("enc"):
            try:
                from comparer import final
                c, decl, dbl = final(a["enc"], donneur)
                return "passe" if c == "passe" else f"{c}{'X' * dbl} {decl}"
            except Exception:
                return ""
    return ""


def tableau_donnes(data):
    tete = ["Donne", "Donneur", "Vulnérabilité"] + [NOM_SIEGE[s] for s in SIEGES] + [f"Points {s}" for s in SIEGES] \
        + ["Par", "Par N-S", "Contrat recommandé", "Thème"]
    lignes = []
    for d in data.get("donnes", []):
        par = d.get("par") or {}
        par_txt = (f"{par.get('contrat', '')}{'X' if par.get('contre') else ''} {par.get('declarant', '')} "
                   f"{par.get('resultat', '')}").strip() if par.get("contrat") else ""
        lignes.append([d["n"], NOM_SIEGE.get(d.get("donneur"), ""), d.get("vul", "")]
                      + [main_txt(d.get("mains", {}).get(s)) for s in SIEGES]
                      + [(d.get("hcp") or {}).get(s, "") for s in SIEGES]
                      + [par_txt, par.get("score_ns", ""), recommande(data, d["n"], d.get("donneur", "N")), d.get("theme", "")])
    return tete, lignes


def noms_de(data, paire):
    return " / ".join(j.get("nom") or j.get("initiales", "") for j in (data.get("joueurs") or {}).get(str(paire), []))


def tableau_resultats(data, noms=False):
    tete = ["Donne", "Table", "Paire N-S", "N-S", "Paire E-O", "E-O", "Contrat", "Déclarant", "Entame", "Résultat",
            "Levées", "Score N-S", "Score E-O", "% N-S", "% E-O", "IMP N-S", "Double mort"]
    if noms: tete[4:4] = ["Noms N-S"]; tete.insert(7, "Noms E-O")
    lignes = []
    for d in data.get("donnes", []):
        for t in d.get("tables") or []:
            sc = t.get("score_ns"); pct = t.get("pct_ns")
            l = [d["n"], t.get("table", ""), t.get("paire_ns", ""), t.get("nom_ns", ""), t.get("paire_eo", ""),
                 t.get("nom_eo", ""), t.get("contrat", ""), NOM_SIEGE.get(t.get("declarant"), t.get("declarant") or ""),
                 t.get("entame", ""), t.get("resultat", ""), t.get("levees", ""), sc if sc is not None else "",
                 -sc if isinstance(sc, (int, float)) else "", pct if pct is not None else "",
                 round(100 - pct, 1) if isinstance(pct, (int, float)) else "",
                 t.get("imp_ns", "") if t.get("imp_ns") is not None else "", t.get("dm", "") if t.get("dm") is not None else ""]
            if noms: l[4:4] = [noms_de(data, t.get("paire_ns"))]; l.insert(7, noms_de(data, t.get("paire_eo")))
            lignes.append(l)
    return tete, lignes


def tableau_paires(data, noms=False):
    tete = ["Paire", "Joueurs", "%", "IMP"] + (["Noms"] if noms else [])
    lignes = []
    paires = data.get("paires") or {}
    def rang(kv):                                          # le meilleur d'abord : le %, sinon les IMP
        v = kv[1].get("pct") if kv[1].get("pct") is not None else kv[1].get("imp")
        return (v is None, -(v or 0))
    for k, p in sorted(paires.items(), key=rang):
        l = [k, p.get("nom", ""), p.get("pct", "") if p.get("pct") is not None else "", p.get("imp", "") if p.get("imp") is not None else ""]
        if noms: l.append(noms_de(data, k))
        lignes.append(l)
    return tete, lignes


def tableau_seance(data, c):
    s = data.get("session", {}); src = data.get("source", {}); f = data.get("fichier") or {}
    import moi
    return ["", ""], [["Titre", s.get("titre", "")], ["Date", s.get("date", "")], ["Heure", s.get("heure", "")],
                      ["Tables", s.get("tables", "")], ["Marque", moi.MARQUES.get(moi.marque(data), "")],
                      ["Donnes", len(data.get("donnes", []))], ["Fichier", os.path.basename(c)],
                      ["Importée de", src.get("fichier", "")], ["Créée le", (f.get("cree_le") or src.get("importe") or "").replace("T", " ")],
                      ["Exportée le", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")]]


def tableau(data, quoi, noms=False):
    return {"resultats": lambda: tableau_resultats(data, noms), "donnes": lambda: tableau_donnes(data),
            "paires": lambda: tableau_paires(data, noms)}[quoi]()


# ---------------------------------------------------------------- PBN, CSV
def pbn(c):
    import donnes
    f = base(c) + ".pbn"
    with open(f, "w", encoding="utf-8") as x: x.write(donnes.pbn(lire(c)))
    return f


def nombre_fr(v):
    """12.5 → « 12,5 » : Excel en français lit la virgule décimale."""
    return str(v).replace(".", ",") if isinstance(v, float) else v


def csv_(c, quoi="resultats", noms=False):
    data = lire(c)
    tete, lignes = tableau(data, quoi, noms)
    if not lignes: raise ValueError("Ce tableau est vide pour cette séance : " +
                                    ("les donnes n'ont pas été jouées en tournoi." if quoi == "resultats" else "rien à exporter."))
    f = f"{base(c)}-{quoi}.csv"
    with open(f, "w", encoding="utf-8-sig", newline="") as x:
        w = csv.writer(x, delimiter=";")
        w.writerow(tete)
        for l in lignes: w.writerow([nombre_fr(v) for v in l])
    return f


# ---------------------------------------------------------------- Excel (.xlsx), sans bibliothèque
def colonne(i):
    """0 → A, 25 → Z, 26 → AA."""
    s = ""
    i += 1
    while i: i, r = divmod(i - 1, 26); s = chr(65 + r) + s
    return s


def cellule(ref, v, style=0):
    if isinstance(v, bool): v = "oui" if v else "non"
    s = f' s="{style}"' if style else ""
    if isinstance(v, (int, float)):
        return f'<c r="{ref}"{s}><v>{v}</v></c>'
    if v is None or v == "": return ""
    t = escape(str(v)).replace("\n", "&#10;")
    return f'<c r="{ref}" t="inlineStr"{s}><is><t xml:space="preserve">{t}</t></is></c>'


def feuille_xml(tete, lignes, entete=True):
    tout = ([tete] if entete else []) + lignes
    larg = [min(max(len(str(l[i])) if i < len(l) else 0 for l in tout) + 2, 60) for i in range(max(len(l) for l in tout))]
    x = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
         '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">']
    if entete:
        x.append('<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" '
                 'state="frozen"/></sheetView></sheetViews>')
    x.append("<cols>" + "".join(f'<col min="{i + 1}" max="{i + 1}" width="{max(w, 6)}" customWidth="1"/>'
                                for i, w in enumerate(larg)) + "</cols><sheetData>")
    for r, l in enumerate(tout, 1):
        style = lambda k: 1 if (entete and r == 1) or (not entete and k == 0) else 0
        x.append(f'<row r="{r}">' + "".join(cellule(f"{colonne(k)}{r}", v, style(k)) for k, v in enumerate(l)) + "</row>")
    x.append("</sheetData>")
    if entete and lignes: x.append(f'<autoFilter ref="A1:{colonne(len(tete) - 1)}{len(tout)}"/>')
    x.append("</worksheet>")
    return "".join(x)


STYLES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
          '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
          '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
          '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
          '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
          '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
          '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
          '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')


def classeur(feuilles):
    """feuilles : [(nom, xml)] → le contenu d'un .xlsx (bytes)."""
    n = len(feuilles)
    types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="xml" ContentType="application/xml"/>'
             '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
             '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
             + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
                       'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, n + 1))
             + '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>')
    wb = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
          + "".join(f'<sheet name="{escape(nom)}" sheetId="{i}" r:id="rId{i}"/>' for i, (nom, _) in enumerate(feuilles, 1))
          + '</sheets></workbook>')
    wb_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
               + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                         f'Target="worksheets/sheet{i}.xml"/>' for i in range(1, n + 1))
               + f'<Relationship Id="rId{n + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
               'Target="styles.xml"/></Relationships>')
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", types); z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", wb); z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/styles.xml", STYLES)
        for i, (_, xml) in enumerate(feuilles, 1): z.writestr(f"xl/worksheets/sheet{i}.xml", xml)
    return out.getvalue()


def excel(c, noms=False):
    """<nom>.xlsx : Séance, Donnes, Résultats et Paires (les feuilles vides en moins)."""
    data = lire(c)
    tete, lignes = tableau_seance(data, c)
    feuilles = [("Séance", feuille_xml(tete, lignes, entete=False))]
    for quoi, titre in (("donnes", "Donnes"), ("resultats", "Résultats"), ("paires", "Paires")):
        t, l = tableau(data, quoi, noms)
        if l: feuilles.append((titre, feuille_xml(t, l)))
    f = base(c) + ".xlsx"
    provisoire = f + ".provisoire"
    with open(provisoire, "wb") as x: x.write(classeur(feuilles))
    os.replace(provisoire, f)                              # Excel peut l'avoir ouvert : on le dit dans l'application
    return f


FORMATS = (("pbn", "PBN", "les donnes, pour Bridgemate (Fichier, Importer) et les logiciels de bridge"),
           ("csv", "CSV", "un tableau, pour un tableur ou un autre programme"),
           ("excel", "Excel", "un classeur .xlsx : la séance, les donnes, les résultats et les paires"))


def exporter(c, format_, quoi="resultats", noms=False):
    """Écrit l'export choisi à côté de la séance ; renvoie son chemin. ValueError avec un message en français."""
    if format_ == "pbn": return pbn(c)
    if format_ == "csv": return csv_(c, quoi, noms)
    if format_ == "excel": return excel(c, noms)
    raise ValueError(f"Format inconnu : {format_}")
