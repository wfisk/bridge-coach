# -*- coding: utf-8 -*-
"""Ce que chaque donne vous coûte face au champ, en trois parts (le rapport « Vous face au champ », 2026-11-11).

Le repère n'est ni la meilleure table (elle vient souvent d'une erreur ailleurs) ni le par (enchères et jeu parfaits,
sacrifices contrés compris), mais le contrat recommandé, enchéri à la table sans voir les autres mains :

  enchères  la valeur du contrat recommandé (au double mort) moins celle de votre contrat (au double mort) ;
  carte     la valeur de votre contrat au double mort moins votre résultat réel : au jeu quand votre camp déclare,
            en défense (entame comprise) sinon. Le double mort devine toujours juste : la part n'est retenue que si
            une autre table du même contrat (même dénomination, même camp au jeu) a fait mieux, ou si personne d'autre
            ne l'a joué (« à revoir », pas « erreur ») ;
  le reste  ce qui vient des autres tables : leurs erreurs, ou une décision raisonnable qui n'a pas réussi.

Valeurs vues de votre camp, en IMP contre le datum des tables, ou en % face aux autres tables (match-points). Des
données seulement : le PDF (build_pdf.page_champ) les met en phrases, l'application pourra les montrer aussi.
"""
from bws_extract import imp
import classement, moi
from comparer import table_recommandee

SEUIL = {"IMP": 3, "MP": 15}          # une part plus petite ne vaut pas une ligne du paragraphe


def _camp(s): return "NS" if s in "NS" else "EO"


def _cle(t):
    """Le même contrat pour comparer le jeu : la dénomination et le camp qui la joue (niveau et contre à part)."""
    return None if t.get("contrat") in (None, "", "passe") else (t["contrat"][1:].rstrip("X"), _camp(t["declarant"]))


RANG = "♣♦♥♠"


def _rang(t):
    if t.get("contrat") in (None, "", "passe"): return -1
    c = t["contrat"].rstrip("X"); den = c[1:]
    return int(c[0]) * 5 + (4 if den == "SA" else RANG.index(den))


def _camp_du_plus_haut(a, b):
    """Le camp qui joue le plus haut des deux contrats (None si les deux sont des passes générales)."""
    x = max((a, b), key=_rang)
    return None if _rang(x) < 0 else _camp(x["declarant"])


def cout_donne(d, analyse, mes, marque="MP"):
    """Une donne que vous avez jouée : {n, camp, vous, encheres, carte, role, autres, mieux, reco, texte_reco, ...} ;
    vous = votre valeur (IMP ou %) vue de votre camp, encheres et carte = ce que chaque part vous coûte (positif : une
    perte), None quand on ne peut pas la mesurer ; carte_retenue : la part de la carte compte-t-elle (voir plus haut).
    None si vous n'avez pas joué la donne ou s'il n'y a pas d'autre table."""
    tables = [t for t in d.get("tables") or [] if not t.get("recommande")]
    camp, t = moi.mon_camp(tables, mes)
    if not t or len(tables) < 2 or not d.get("dm"): return None
    signe = 1 if camp == "NS" else -1
    autres = [x for x in tables if x is not t]
    if marque == "IMP":
        dat = classement.datum(tables)
        val = lambda ns: signe * imp(ns - dat)
    else:
        val = lambda ns: (lambda p: p if signe == 1 else 100 - p)(classement.pct_face(autres, ns))
    ns_reel = t.get("score_ns") or 0
    out = dict(n=d["n"], camp=camp, vous=val(ns_reel), table=t, encheres=None, carte=None, carte_retenue=False,
               role=None, reco=None)
    # votre contrat au double mort
    if t.get("contrat") in (None, "", "passe"):
        ns_dm = 0
    else:
        den = t["contrat"][1:].rstrip("X")
        lev_dm = d["dm"][den][t["declarant"]]
        ns_dm = classement.score_ns(d, t["contrat"], t["declarant"], lev_dm)
        out.update(levees=t.get("levees"), levees_dm=lev_dm, role="jeu" if _camp(t["declarant"]) == camp else "defense")
    out["valeur_dm"] = val(ns_dm)
    out["carte"] = out["valeur_dm"] - out["vous"]
    if out["role"] and out["carte"] > 0:
        memes = [x for x in autres if _cle(x) == _cle(t) and x.get("levees") is not None]
        if out["role"] == "jeu":
            mieux = [x for x in memes if x["levees"] > (t.get("levees") or 0)]
        else:
            mieux = [x for x in memes if x["levees"] < (t.get("levees") or 0)]
        out.update(memes=len(memes), mieux=len(mieux), carte_retenue=not memes or bool(mieux))
    # le contrat recommandé, au double mort
    reco = table_recommandee(d, analyse or {})
    if reco:
        out["reco"] = reco
        out["valeur_reco"] = val(reco["score_ns"])
        out["encheres"] = out["valeur_reco"] - val(ns_dm)
        # l'écart est à vous quand c'est votre camp qui a pris la décision : il joue le plus haut des deux contrats
        # (vous avez déclaré, poussé ou sacrifié ; l'autre camp, lui, n'a pas surenchéri), ou vous avez contré le leur.
        # Sinon il vient des enchères adverses (ils jouent plus haut ou plus bas que le recommandé) et va dans le reste
        out["encheres_a_vous"] = _camp_du_plus_haut(t, reco) == camp or \
            ("X" in (t.get("contrat") or "") and _camp(t["declarant"]) != camp)
    return out


def bilan(donnes, an, mes, marque="MP"):
    """La séance : {perte (votre total face au champ, positif : une perte), encheres, carte : [lignes retenues, la
    plus coûteuse d'abord], reste, n (donnes jouées), seuil, marque}. En MP, perte et reste sont des points de % sur
    l'ensemble des donnes (la somme des écarts à 50 %)."""
    centre = 0 if marque == "IMP" else 50
    seuil = SEUIL[marque]
    lignes = [c for d in donnes
              if (c := cout_donne(d, ((an or {}).get("donnes") or {}).get(str(d["n"])), mes, marque))]
    perte = sum(centre - c["vous"] for c in lignes)
    enc = sorted((c for c in lignes if c.get("encheres_a_vous") and (c["encheres"] or 0) >= seuil),
                 key=lambda c: -c["encheres"])
    carte = sorted((c for c in lignes if c["carte_retenue"] and c["carte"] >= seuil), key=lambda c: -c["carte"])
    reste = perte - sum(c["encheres"] for c in enc) - sum(c["carte"] for c in carte)
    # vos meilleurs coups : une part qui vous rapporte au moins le seuil (enchères à vous, ou la carte au-dessus du
    # double mort quand votre camp joue : en défense, un cadeau du déclarant n'est pas un coup à vous)
    # (une donne que vous perdez face au champ n'en est pas un, même sur un bon contrat chuté)
    gains = [("encheres", c, -c["encheres"]) for c in lignes
             if c.get("encheres_a_vous") and (c["encheres"] or 0) <= -seuil and c["vous"] >= centre]
    gains += [("carte", c, -c["carte"]) for c in lignes if c["role"] == "jeu" and c["carte"] <= -seuil and c["vous"] >= centre]
    gains.sort(key=lambda g: -g[2])
    return dict(perte=perte, encheres=enc, carte=carte, reste=reste, gains=gains[:3], n=len(lignes), seuil=seuil,
                marque=marque, lignes=lignes)


def a_revoir(b):
    """Les donnes à revoir de bilan(b), la plus coûteuse d'abord : [(quoi "encheres"|"carte", ligne, coût)], une donne
    pouvant y être deux fois (enchères et carte)."""
    out = [("encheres", c, c["encheres"]) for c in b["encheres"]] + [("carte", c, c["carte"]) for c in b["carte"]]
    return sorted(out, key=lambda x: -x[2])


def numeros_a_revoir(b):
    """Les numéros des donnes à revoir, dans l'ordre de a_revoir, chacun une fois."""
    vus = []
    for _, c, _ in a_revoir(b):
        if c["n"] not in vus: vus.append(c["n"])
    return vus
