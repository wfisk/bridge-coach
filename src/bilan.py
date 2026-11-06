# -*- coding: utf-8 -*-
"""Bilan des enchères sur toutes les séances : où le Standard perd des IMP face à l'Expert.

Usage : .venv/bin/python -I src/bilan.py [sortie.pdf]      (par défaut rapports/bilan-encheres.pdf)

Lit chaque séance de seances/ (<nom>.bc.json) qui a une analyse experte (<nom>-expert.json) et une
analyse du programme (<nom>-standard.json). Pour chaque donne où les contrats diffèrent : les IMP du Standard
face à l'Expert au double mort (comme le -diff), le genre d'écart (chelem manqué, manche de trop…)
et l'étape où les enchères se séparent (ouverture, réponse, redemande…). Les totaux par genre et
par étape disent quoi travailler en premier ; la liste des donnes suit, les plus coûteuses d'abord.
"""
import sys, os, glob, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from build_pdf import S_body, S_h, S_title, S_sub, S_note, txt, suits, SENS, SEAT, sens_contrat, _grille, _groupe
from comparer import evaluer, meme_contrat, imp_standard, premier_ecart, sequence, cle_sens, resultat_dm, S_c, tableau
from rapport import SEANCES, RAPPORTS, BC, ANCIEN, remplacer

MANCHE = {"SA": 3, "♠": 4, "♥": 4, "♦": 5, "♣": 5}
ETAPES = ["Ouverture", "Réponse", "Redemande de l'ouvreur", "Deuxième enchère du répondant", "Suite (chelem…)",
          "Intervention et défense"]


def palier(r):
    """0 passe, 1 partielle, 2 manche, 3 petit chelem, 4 grand chelem."""
    if r["contrat"] == "passe": return 0
    n = int(r["contrat"][0])
    return 4 if n == 7 else 3 if n == 6 else 2 if n >= MANCHE[r["contrat"][1:]] else 1


def genre(a, c):
    """Le genre d'écart, vu du camp qui déclare chez l'Expert."""
    camp = lambda r: None if r["contrat"] == "passe" else r["decl"] in "NS"
    if camp(a) != camp(c): return "L'autre camp déclare"
    pa, pc = palier(a), palier(c)
    if pc >= 3 and pa < 3: return "Chelem manqué"
    if pa >= 3 and pc < 3: return "Chelem de trop"
    if pc == 2 and pa < 2: return "Manche manquée"
    if pa == 2 and pc < 2: return "Manche de trop"
    return "Autre contrat, même palier"


def etape(d, enc, k, s):
    """L'étape de l'enchère où les deux analyses se séparent, pour le joueur s (k-ième appel depuis le donneur)."""
    seq = sequence(enc, d["donneur"])
    rot = ["N", "E", "S", "O"]; i0 = rot.index(d["donneur"])
    qui = [rot[(i0 + j) % 4] for j in range(len(seq))]
    ouv = next((j for j, b in enumerate(seq) if b != "passe"), None)
    if ouv is None or k <= ouv: return ETAPES[0]
    camp = lambda x: x in "NS"
    if camp(s) != camp(qui[ouv]): return ETAPES[5]
    rang = sum(1 for j in range(ouv, k + 1) if camp(qui[j]) == camp(s))   # 1 ouverture, 2 réponse…
    return ETAPES[min(rang, 5) - 1]


def seances():
    """[(date, nom, données, standard, expert)] des séances qui ont les deux analyses."""
    out = []
    for f in sorted(glob.glob(os.path.join(SEANCES, "*", "*-expert.json"))):
        base = f[:-len("-expert.json")]
        seance = next((base + x for x in (BC, ANCIEN) if os.path.exists(base + x)), None)
        if not seance or not os.path.exists(base + "-standard.json"): continue
        data = json.load(open(seance))
        j, m, a = data["session"]["date"].split("/")
        out.append((f"{a}-{m}-{j}", os.path.basename(base), data, json.load(open(base + "-standard.json"))["donnes"],
                    json.load(open(f))["donnes"]))
    return sorted(out)


def ecarts():
    """Une ligne par donne où les contrats diffèrent, sur toutes les séances, et le compte des donnes."""
    lignes, n_donnes, par_seance = [], 0, []
    for date, nom, data, auto, expert in seances():
        perdu = 0; k_diff = 0
        for d in data["donnes"]:
            n = str(d["n"])
            if not (auto.get(n, {}).get("enc") and expert.get(n, {}).get("enc")): continue
            n_donnes += 1
            sans_entame = lambda x: {k: v for k, v in x.items() if k != "entame"}   # pas de double mort d'entame ici
            a, c = evaluer(d, sans_entame(auto[n]), {}), evaluer(d, sans_entame(expert[n]), {})
            if meme_contrat(a, c): continue
            ec = premier_ecart(auto[n]["enc"], expert[n]["enc"])
            x = imp_standard(a, c); perdu += x; k_diff += 1
            ligne = dict(date=date, nom=nom, n=d["n"], imp=x, genre=genre(a, c), a=a, c=c,
                         sens=sens_contrat(cle_sens(a), cle_sens(c)), etape="—", ecart="")
            if ec:
                k, _, _, s = ec
                avant = sequence(auto[n]["enc"], d["donneur"])[:k]
                ligne["etape"] = etape(d, auto[n]["enc"], k, s)
                ligne["ecart"] = (f"{SEAT[s]} après {' – '.join(avant)}" if avant else f"{SEAT[s]} en ouverture") + \
                    f" : {sequence(expert[n]['enc'], d['donneur'])[k]} / {sequence(auto[n]['enc'], d['donneur'])[k]}"
            lignes.append(ligne)
        par_seance.append((date, nom, k_diff, perdu))
    return lignes, n_donnes, par_seance


def total_par(lignes, cle, ordre):
    """[(valeur, donnes, IMP)] dans l'ordre donné, les valeurs absentes omises."""
    out = []
    for v in ordre:
        xs = [l for l in lignes if l[cle] == v]
        if xs: out.append((v, len(xs), sum(l["imp"] for l in xs)))
    return out


def imp_txt(x):
    v = "0" if x == 0 else f"{x:+d}".replace("-", "−")
    return f"<b>{v}</b>" if x > 0 else v


def main():
    sortie = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RAPPORTS, "bilan-encheres.pdf")
    lignes, n_donnes, par_seance = ecarts()
    if not par_seance: raise SystemExit("Aucune séance avec une analyse experte et une analyse du programme.")
    P = lambda x: Paragraph(txt(suits(x)), S_c)
    total = sum(l["imp"] for l in lignes)
    el = [Paragraph("Bilan des enchères", S_title),
          Paragraph(f"{len(par_seance)} séances · {n_donnes} donnes · le programme (Standard) face à l'analyse experte, "
                    "au double mort", S_sub), Spacer(1, 8),
          Paragraph(txt(f"Les contrats diffèrent sur <b>{len(lignes)}</b> donnes ; le Standard y "
                        f"{'gagne' if total > 0 else 'perd'} <b>{abs(total)} IMP</b> en tout face à l'Expert."), S_body),
          Spacer(1, 4)]

    def petit_tableau(titre, note, rows, largeurs):
        lignes_t = [[P("<b>" + x + "</b>") for x in rows[0]]] + [[P(str(x)) for x in r] for r in rows[1:]]
        return [Paragraph(titre, S_h), Paragraph(note, S_note), Spacer(1, 3), tableau(lignes_t, largeurs)]

    el += petit_tableau("Par séance", "IMP du Standard face à l'Expert sur les donnes où les contrats diffèrent.",
                        [("Séance", "Donnes", "IMP")] +
                        [(f"{d[8:]}/{d[5:7]}/{d[:4]} · {nom}", k, imp_txt(x)) for d, nom, k, x in par_seance],
                        [10.4, 3.4, 2.4])
    genres = ["Chelem manqué", "Chelem de trop", "Manche manquée", "Manche de trop", "Autre contrat, même palier",
              "L'autre camp déclare"]
    el += petit_tableau("Par genre d'écart", "Vu du camp qui déclare chez l'Expert : le palier de son contrat "
                        "face à celui du Standard.",
                        [("Genre", "Donnes", "IMP")] + [(g, k, imp_txt(x)) for g, k, x in total_par(lignes, "genre", genres)],
                        [10.4, 3.4, 2.4])
    el += petit_tableau("Par étape où les enchères se séparent", "Le premier appel qui diffère : à quelle enchère "
                        "de son camp le joueur se trouvait. C'est là que la règle ou le code est à revoir.",
                        [("Étape", "Donnes", "IMP")] +
                        [(g, k, imp_txt(x)) for g, k, x in total_par(lignes, "etape", ETAPES + ["—"])],
                        [10.4, 3.4, 2.4])

    el += [Paragraph("Les donnes, des plus coûteuses aux moins coûteuses", S_h),
           Paragraph("Le premier écart : le joueur, les enchères qui précèdent, puis l'appel de l'Expert / celui du "
                     "Standard. Couleurs du Standard comme dans le -diff : rouge plus haut, bleu plus bas, même camp.",
                     S_note), Spacer(1, 3)]
    rows = [[P(f"<b>{x}</b>") for x in ("Date", "N°", "Expert", "Standard", "Premier écart", "IMP")]]
    st_, fonds = [], []
    for l in sorted(lignes, key=lambda l: (l["imp"], l["date"], l["n"])):
        i = len(rows)
        rows.append([P(f"{l['date'][8:]}/{l['date'][5:7]}"), P(f"<b>{l['n']}</b>"), P(resultat_dm(l["c"])),
                     P(resultat_dm(l["a"])), P(l["ecart"]), P(imp_txt(l["imp"]))])
        if l["sens"]: fonds.append(("BACKGROUND", (3, i), (3, i), colors.HexColor(SENS[l["sens"]][0])))
        _groupe(st_, i, i, (i - 1) % 2)
    el.append(_grille(rows, [1.2 * cm, 1.0 * cm, 2.9 * cm, 2.9 * cm, 7.9 * cm, 1.4 * cm], st_ + fonds))

    def pied(cv, doc):
        cv.saveState(); cv.setFont("DV", 7.5); cv.setFillColor(colors.HexColor("#888"))
        cv.drawString(1.7 * cm, 1.0 * cm, "Bilan des enchères")
        cv.drawRightString(A4[0] - 1.7 * cm, 1.0 * cm, f"page {doc.page}"); cv.restoreState()
    provisoire = sortie[:-4] + ".provisoire.pdf"
    doc = SimpleDocTemplate(provisoire, pagesize=A4, leftMargin=1.7 * cm, rightMargin=1.7 * cm, topMargin=1.5 * cm,
                            bottomMargin=1.5 * cm, title="Bilan des enchères", author="Claude")
    doc.build(el, onFirstPage=pied, onLaterPages=pied)
    remplacer(provisoire, sortie)
    print(f"{len(par_seance)} séances, {len(lignes)} donnes différentes, {total:+d} IMP")


if __name__ == "__main__":
    main()
