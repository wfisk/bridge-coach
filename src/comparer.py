# -*- coding: utf-8 -*-
"""PDF comparant l'analyse du programme (-standard.json) et l'analyse experte.

Usage : python3 comparer.py <nom>.bc.json <nom>-standard.json <nom>-expert.json sortie-diff.pdf

Pour chaque donne : contrat recommandé (gagnant ou non au double mort, écart au par en IMP)
et entame recommandée (levées de la défense au double mort, comparées à la meilleure entame).
Page de synthèse (IMP du Standard face à l'Expert, le par en second), contrats et entames qui
diffèrent, puis les donnes où les deux analyses diffèrent : enchères côte à côte, le premier appel
qui diffère encadré, la main de ce joueur, la raison du programme et les notes de l'expert.
"""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak, KeepTogether)
from build_pdf import S_body, S_h, S_title, S_sub, S_cell, S_note, GREY, INK, txt, suits, bidding, st, page_noms, \
    SENS, SEAT, sens_contrat, rang_contrat, _grille, _groupe
from bws_extract import score, vul_of, imp
from jeu import levees_par_entame, LHO

EN = {"SA": "NT", "♠": "S", "♥": "H", "♦": "D", "♣": "C"}
ROT = ["N", "E", "S", "O"]; GRID = ["O", "N", "E", "S"]
NOMS = {"auto": "Standard", "claude": "Expert"}
FOND_CONTRAT = colors.HexColor("#f5c2b3"); ROUGE = colors.HexColor("#c0392b")   # contrats différents
FOND_ENTAME = colors.HexColor("#fbefb8")                                         # entames différentes
S_c = st("cc", fontSize=8.6, leading=10.5)
S_cb = st("cb", fontName="DVB", fontSize=8.6, leading=10.5)
S_h2 = ParagraphStyle("h2", parent=S_h, keepWithNext=0)            # titre suivi d'un long tableau qui peut se couper


def final(enc, donneur):
    """(contrat, déclarant, contre 0/1/2) de la grille Ouest/Nord/Est/Sud."""
    cells = [c for row in enc for c in row]
    seq = [c for c in cells[GRID.index(donneur):] if c not in ("", "–")]
    last = None; first = {}; dbl = 0; i0 = ROT.index(donneur)
    for k, b in enumerate(seq):
        who = ROT[(i0 + k) % 4]; side = "NS" if who in "NS" else "EO"
        if b == "contre": dbl = 1; continue
        if b == "surcontre": dbl = 2; continue
        m = re.fullmatch(r"([1-7])(♣|♦|♥|♠|SA)", b)
        if not m: continue
        last = (m[1], m[2], side); dbl = 0; first.setdefault((side, m[2]), who)
    if not last: return "passe", None, 0
    return last[0] + last[1], first[(last[2], last[1])], dbl


def evaluer(d, a, cache):
    """Contrat, levées au double mort, score N-S, écart au par et entame d'une analyse."""
    c, decl, dbl = final(a["enc"], d["donneur"])
    r = {"contrat": c, "decl": decl, "dbl": dbl, "texte": "passe"}
    if c == "passe":
        r.update(levees=None, gagne=True, ns=0)
    else:
        den = c[1:]; t = d["dm"][den][decl]; camp = "NS" if decl in "NS" else "EW"
        v = score(int(c[0]), EN[den], dbl, vul_of(d["vul"], camp), t)
        r.update(levees=t, gagne=t >= int(c[0]) + 6, ns=v if camp == "NS" else -v,
                 texte=f"{c}{'X' * dbl} {decl}")
    r["ecart"] = abs(imp(r["ns"] - par_pratique(d)))      # distance au par (pratique : petit chelem plutôt que grand)
    # entame : levées de la défense au double mort, comparées à la meilleure entame
    e = a.get("entame"); carte = e.get("carte") if isinstance(e, dict) else None
    r["entame"] = carte; r["entame_lev"] = r["entame_max"] = None
    if carte and c != "passe":
        cle = (c[1:], decl)
        if cle not in cache: cache[cle] = levees_par_entame(d["mains"], c[1:], decl)
        lev = cache[cle]
        if lev and carte in lev:
            r["entame_lev"], r["entame_max"] = lev[carte], max(lev.values())
    return r


def par_pratique(d):
    """Le score N-S du par ; quand le par est un grand chelem, celui du petit chelem dans la même dénomination,
    par le même déclarant : le grand chelem est rarement demandé, le petit fait déjà un bon score."""
    p = d.get("par")
    if not p: return 0
    m = re.fullmatch(r"7(SA|♠|♥|♦|♣)", p["contrat"])
    if not m or p["contre"]: return p["score_ns"]
    camp = "NS" if p["declarant"] in "NS" else "EW"
    v = score(6, EN[m[1]], 0, vul_of(d["vul"], camp), d["dm"][m[1]][p["declarant"]])
    return v if camp == "NS" else -v


def meme_contrat(a, c):
    """Même contrat final : palier, dénomination, déclarant et contre (3♥ et 3♥X diffèrent)."""
    return a["contrat"] == c["contrat"] and a["decl"] == c["decl"] and a["dbl"] == c["dbl"]


def autre_entame(a, c):
    """Entames différentes, comparées seulement quand le même joueur entame dans la même
    dénomination (sinon elles ne se comparent pas)."""
    return a["contrat"] != "passe" and a["contrat"][1:] == c["contrat"][1:] and a["decl"] == c["decl"] \
        and a["entame"] != c["entame"]


def sequence(enc, donneur):
    """Enchères depuis le donneur, à partir de la grille Ouest/Nord/Est/Sud."""
    cells = [c for row in enc for c in row]
    return [c for c in cells[GRID.index(donneur):] if c not in ("", "–")]


def cases(enc):
    """[(ligne, colonne, enchère)] de la grille Ouest/Nord/Est/Sud, sans les cases vides."""
    return [(i, j, x) for i, row in enumerate(enc) for j, x in enumerate(row) if x not in ("", "–")]


def premier_ecart(ea, ec):
    """Le premier appel où les enchères du Standard (ea) et de l'Expert (ec) diffèrent :
    (rang k, case du Standard, case de l'Expert, siège), ou None si l'une prolonge l'autre."""
    a, c = cases(ea), cases(ec)
    for k, (x, y) in enumerate(zip(a, c)):
        if x[2] != y[2]: return k, x[:2], y[:2], GRID[x[1]]
    return None


def raison_standard(d, an, k):
    """Pourquoi le programme a fait son k-ième appel : l'explication du moteur, recalculée ; None si
    le moteur ne redonne plus les mêmes enchères (analyse ancienne)."""
    from encheres import encherir
    r = encherir(d)
    if r["encheres"][:k + 1] != sequence(an["enc"], d["donneur"])[:k + 1]: return None
    return re.sub(r"\s+", " ", r["explications"][k][2])


def main_txt(d, s):
    m = d["mains"][s].split()
    return "&nbsp; ".join(f"{c}{'—' if p == '-' else p}" for c, p in zip("♠♥♦♣", m)) + f"&nbsp;·&nbsp;{d['hcp'][s]}&nbsp;H"


def par_texte(d):
    p = d.get("par")
    if not p: return "passe"
    g = "" if p["contre"] or p["contrat"][0] != "7" else f" (6{p['contrat'][1:]})"   # le par pratique
    return f"{p['contrat']}{'X' if p['contre'] else ''} {p['declarant']}{g}"


def negatif(n):
    """Levées en moins : la seule marque des tableaux, rien quand tout va bien (jamais en gras)."""
    return f"<font name='DV'>(−{-n})</font>"


def case_contrat(r):
    if r["contrat"] == "passe": return "passe"
    return r["texte"] if r["gagne"] else f"{r['texte']} {negatif(r['levees'] - int(r['contrat'][0]) - 6)}"


def case_entame(r):
    if not r["entame"]: return "–"
    if r["entame_lev"] is None: return r["entame"]
    perdu = r["entame_lev"] - r["entame_max"]
    return r["entame"] if perdu == 0 else f"{r['entame']} {negatif(perdu)}"


def resultat_dm(r):
    """« 4♠ N = », « 3SA S +1 », ou « 4♥ O −1 » en rouge : le contrat et ses levées au double mort."""
    if r["contrat"] == "passe": return "passe générale"
    m = r["levees"] - int(r["contrat"][0]) - 6
    if m < 0: return f"{r['texte']} <font color='#c0392b'>−{-m}</font>"
    return f"{r['texte']} {'=' if m == 0 else f'+{m}'}"


def camp_de(r):
    return None if r["contrat"] == "passe" else "NS" if r["decl"] in "NS" else "EO"


def imp_standard(a, c):
    """IMP du Standard face à l'Expert, au double mort, vus du camp qui déclare chez l'Expert (sinon chez le
    Standard) : positif, le Standard fait mieux ; négatif, il fait moins bien."""
    camp = camp_de(c) or camp_de(a) or "NS"
    x = imp(a["ns"] - c["ns"])
    return x if camp == "NS" else -x


def cle_sens(r):
    return "passe" if r["contrat"] == "passe" else (r["contrat"] + "X" * r["dbl"], r["decl"])


def tableau(lignes, largeurs, entete=1):
    t = Table(lignes, colWidths=[w * cm for w in largeurs], repeatRows=entete)
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor(INK)),
                           ("LINEBELOW", (0, -1), (-1, -1), 0.8, colors.HexColor("#1f3f8f")),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f5f3")]),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    return t


def main():
    data = json.load(open(sys.argv[1]))
    auto = json.load(open(sys.argv[2]))["donnes"]; claude = json.load(open(sys.argv[3]))["donnes"]
    out = sys.argv[4]; date = data["session"]["date"]
    res = []
    for d in data["donnes"]:
        n = str(d["n"])
        if not (auto.get(n, {}).get("enc") and claude.get(n, {}).get("enc")): continue
        cache = {}
        res.append((d, evaluer(d, auto[n], cache), evaluer(d, claude[n], cache)))
    if not res: raise SystemExit("Aucune donne avec des enchères dans les deux analyses.")
    N = len(res)

    differents = [(d, a, c) for d, a, c in res if not meme_contrat(a, c)]
    total = sum(imp_standard(a, c) for _, a, c in differents)
    meme_c = N - len(differents)
    meme_e = sum(a["entame"] == c["entame"] for _, a, c in res if meme_contrat(a, c))
    el = [Paragraph("Comparaison des analyses", S_title),
          Paragraph(f"Séance du {date} · {N} donnes · analyse du programme et analyse experte, "
                    "jugées au double mort", S_sub), Spacer(1, 8),
          Paragraph("Synthèse", S_h)]
    bilan = (f"le Standard {'gagne' if total > 0 else 'perd'} <b>{abs(total)} IMP</b> face à l'Expert" if total
             else "le Standard et l'Expert font jeu égal")
    el.append(Paragraph(txt(
        f"Même contrat et même déclarant : <b>{meme_c}/{N}</b> ; parmi eux, même entame : <b>{meme_e}/{meme_c}</b>. "
        f"Sur les {len(differents)} donnes où les contrats diffèrent, {bilan}, au double mort." if differents else
        f"Même contrat et même déclarant sur les {N} donnes ; même entame : <b>{meme_e}/{N}</b>."), S_body))
    lignes = [[Paragraph(f"<b>{x}</b>", S_c) for x in ("", "Contrats au par", "Écart moyen au par")]]
    for k, nom in ((1, "claude"), (0, "auto")):
        rs = [x[1 + k] for x in res]
        lignes.append([Paragraph(f"<b>{NOMS[nom]}</b>", S_c),
                       Paragraph(f"{sum(r['ecart'] == 0 for r in rs)}/{N}", S_c),
                       Paragraph(f"{sum(r['ecart'] for r in rs) / N:.1f} IMP", S_c)])
    el += [Spacer(1, 4), tableau(lignes, [4.4, 3.4, 3.4]), Spacer(1, 4), Paragraph(txt(
        "Le par est le meilleur score des deux camps au double mort, sacrifices contrés compris : un repère, pas un "
        "objectif. Quand c'est un grand chelem, l'écart se compte au petit chelem : le grand est rarement demandé. Ni l'une ni l'autre analyse n'a été jouée : contrats et entames sont jugés au double mort, cartes "
        "vues, après coup, sans les chances réelles à la table."), S_note)]
    P = lambda x, s=S_c: Paragraph(x, s)
    S_d = ParagraphStyle("droite", parent=S_c, alignment=2)
    contrats = [[P("<b>N°</b>"), P("<b>Par</b>"), P("<b>Expert</b>"), P("<b>Standard</b>"), P("<b>IMP</b>", S_d)]]
    st_c, fonds = [], []; n_sens = {k: 0 for k in SENS}; memes = []
    for d, a, c in res:
        if meme_contrat(a, c): memes.append(str(d["n"])); continue
        i = len(contrats); x = imp_standard(a, c)
        v = "0" if x == 0 else f"{x:+d}".replace("-", "−")
        contrats.append([P(f"<b>{d['n']}</b>"), P(txt(suits(par_texte(d)))), P(txt(suits(resultat_dm(c)))),
                         P(txt(suits(resultat_dm(a)))), P(f"<b>{v}</b>" if x > 0 else v, S_d)])
        sens = sens_contrat(cle_sens(a), cle_sens(c))
        if sens: fonds.append(("BACKGROUND", (3, i), (3, i), colors.HexColor(SENS[sens][0]))); n_sens[sens] += 1
        _groupe(st_c, i, i, (i - 1) % 2)
    el.append(Paragraph("Contrats : Standard face à l'Expert", S_h2))
    el.append(Paragraph("Même camp : " + " ; ".join(
        f"<font backColor='{SENS[k][0]}'> {('Standard plus haut' if k == 'plus' else 'Standard plus bas')} </font> ({n_sens[k]})" for k in SENS) +
        ". Sans couleur : l'autre camp joue, ou le partenaire joue le même contrat. Après chaque contrat, ses levées au "
        "double mort : = juste fait, +1 une levée de mieux, −1 en rouge une de chute. IMP : ce que le Standard gagne (+) "
        "ou perd (−) face à l'Expert, au double mort, pour le camp qui déclare chez l'Expert ; en gras quand le Standard fait mieux.", S_note))
    el.append(Spacer(1, 3))
    if len(contrats) > 1:
        el.append(_grille(contrats, [1.0 * cm, 3.4 * cm, 4.9 * cm, 4.9 * cm, 1.6 * cm], st_c + fonds))
        el.append(Paragraph(txt(f"Sur ces {len(contrats) - 1} donnes, le Standard {'gagne' if total > 0 else 'perd'} "
                                f"<b>{abs(total)} IMP</b> en tout face à l'Expert." if total else
                                f"Sur ces {len(contrats) - 1} donnes, le Standard et l'Expert font jeu égal."), S_body))
    if memes: el.append(Paragraph(f"Même contrat, même déclarant : donnes {', '.join(memes)}.", S_body))

    entames = [[P("<b>N°</b>"), P("<b>Contrat</b>"), P("<b>Expert</b>"), P("<b>Standard</b>")]]
    st_e, fonds_e = [], []; memes_e = []
    for d, a, c in res:
        if a["contrat"] == "passe" or a["contrat"][1:] != c["contrat"][1:] or a["decl"] != c["decl"]: continue
        if a["entame"] == c["entame"]: memes_e.append(str(d["n"])); continue
        i = len(entames)
        entames.append([P(f"<b>{d['n']}</b>"), P(txt(suits(c["texte"] if c["contrat"] == a["contrat"] else f"{c['texte']} / {a['texte']}"))),
                        P(suits(case_entame(c))), P(suits(case_entame(a)))])
        fonds_e.append(("BACKGROUND", (3, i), (3, i), FOND_ENTAME)); _groupe(st_e, i, i, (i - 1) % 2)
    el.append(Paragraph("Entames : Standard face à l'Expert", S_h2))
    el.append(Paragraph("Seulement quand le même joueur entame dans la même dénomination. Entre parenthèses, au double "
                        "mort : les levées que la défense perd face à la meilleure entame ; rien si l'entame est la meilleure. "
                        "Les entames sont choisies à la table, sans voir les autres mains.", S_note))
    el.append(Spacer(1, 3))
    if len(entames) > 1: el.append(_grille(entames, [1.0 * cm, 4.6 * cm, 4.6 * cm, 4.6 * cm], st_e + fonds_e))
    if memes_e: el.append(Paragraph(f"Même entame : donnes {', '.join(memes_e)}.", S_body))

    diff = [(d, a, c) for d, a, c in res if not meme_contrat(a, c) or autre_entame(a, c)]
    if diff:
        el += [PageBreak(), Paragraph("Donnes où les analyses diffèrent", S_h)]
    for d, a, c in diff:
        etiq = ""
        sens = None if meme_contrat(a, c) else sens_contrat(cle_sens(a), cle_sens(c))
        if sens: etiq += f" <font backColor='{SENS[sens][0]}'> Standard plus {'haut' if sens == 'plus' else 'bas'} </font>"
        elif not meme_contrat(a, c): etiq += " <font backColor='#e4e4e4'> contrat différent </font>"
        if autre_entame(a, c): etiq += " <font backColor='#fbefb8'> entame différente </font>"
        bloc = [Paragraph(f"<b>Donne n° {d['n']}</b> · par : {txt(suits(par_texte(d)))}{etiq}", S_body), Spacer(1, 2)]
        n = str(d["n"]); ec = premier_ecart(auto[n]["enc"], claude[n]["enc"])
        colonnes = []
        for nom, r, an in (("claude", c, claude), ("auto", a, auto)):
            info = f"{resultat_dm(r)} au double mort, écart au par {r['ecart']} IMP"
            if nom == "auto" and sens: info = f"<font backColor='{SENS[sens][0]}'>{resultat_dm(r)}</font>" + info[len(resultat_dm(r)):]
            if r["entame"]: info += f" · entame {case_entame(r)}"
            grille = bidding(an[n]["enc"], 2.05 * cm)
            if ec:                                         # le premier appel qui diffère, encadré
                i, j = ec[2] if nom == "claude" else ec[1]
                grille.setStyle(TableStyle([("BOX", (j, i + 1), (j, i + 1), 1.4, colors.HexColor(INK))]))
            colonnes.append([Paragraph(f"<b>{NOMS[nom]}</b>", S_cell), Spacer(1, 1), grille, Spacer(1, 1),
                             Paragraph(txt(suits(info)), S_cell)])
        t = Table([colonnes], colWidths=[8.8 * cm, 8.8 * cm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        bloc.append(t)
        if ec:
            k, _, _, s = ec
            avant = sequence(auto[n]["enc"], d["donneur"])[:k]
            ex, st_ = sequence(claude[n]["enc"], d["donneur"])[k], sequence(auto[n]["enc"], d["donneur"])[k]
            situ = f"après {' – '.join(avant)}" if avant else "en ouverture"
            pourquoi = raison_standard(d, auto[n], k)
            lignes = [f"<b>Premier écart</b> : {SEAT[s]}, {situ} : Expert <b>{ex}</b>, Standard <b>{st_}</b>. "
                      f"Main de {SEAT[s]} : {main_txt(d, s)}."]
            if pourquoi: lignes.append(f"<b>Standard {st_}</b> : {pourquoi}")
            if claude[n].get("notes"): lignes.append(f"<b>Expert</b> : {claude[n]['notes']}")
            bloc += [Spacer(1, 3)] + [Paragraph(suits(x), S_c) for x in lignes]
        el.append(KeepTogether(bloc + [Spacer(1, 10)]))

    def pied(cv, doc):
        cv.saveState(); cv.setFont("DV", 7.5); cv.setFillColor(colors.HexColor("#888"))
        cv.drawString(1.7 * cm, 1.0 * cm, f"Comparaison des analyses – séance du {date}")
        cv.drawRightString(A4[0] - 1.7 * cm, 1.0 * cm, f"page {doc.page}"); cv.restoreState()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=1.7 * cm, rightMargin=1.7 * cm, topMargin=1.5 * cm,
                            bottomMargin=1.5 * cm, title=f"Comparaison des analyses – {date}", author="Claude")
    el = page_noms(data, sys.argv[5] if len(sys.argv) > 5 else None) + el
    doc.build(el, onFirstPage=pied, onLaterPages=pied)
    print(f"PDF écrit : {out.replace('.provisoire.pdf', '.pdf')} ({doc.page} pages, {N} donnes comparées, {len(diff)} différentes)")


if __name__ == "__main__":
    main()
