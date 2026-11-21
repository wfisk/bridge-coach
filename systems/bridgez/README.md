# BRIDGEZ (Université du Bridge)

Le système enseigné aux débutants par l'Université du Bridge (livre « BRIDGEZ »), aux enchères plus directes que le SEF.

## Comment il est fait
- Le SEF 2024 avec des conventions coupées : `sans: [Roudi, Drury, …]` dans `regles.yaml`, par leur nom dans le
  fichier du SEF (`nom:`). Les noms : Stayman, Texas, Roudi, Drury, Spoutnik, Bicolores, Landy, 4e couleur forcing,
  Blackwood. `tests/test_systemes.py` vérifie qu'une convention coupée n'est plus jouée.
- `regles.yaml` porte `base: sef-2024` : il n'écrit que ses différences. Une section (une séquence, comme `"1M"` ou
  `"1N - 1M - 1SA"`) écrite ici remplace celle du SEF ; le reste se joue comme le SEF 2024.
- Les entames et la signalisation : celles du SEF tant qu'il n'y a pas de `entames.yaml` ici.
- `pret: non` le cache aux joueurs ; on le passe à `oui` quand les différences sont écrites et vérifiées au banc.

## À faire, d'après le livre (photos des pages de résumé)
Rien n'est encore écrit : il faut le texte du livre, page par page, pour ne rien inventer. Les points à relever :
1. Les ouvertures : zones de points, majeure 5e ou 4e, 1SA (zone), deux faibles / deux forts, barrages.
2. Les réponses à 1 à la couleur (soutiens, nouvelles couleurs, SA), à 1SA (Stayman, texas ?), à 2SA.
3. Les redemandes de l'ouvreur et du répondant ; ce qui est forcing.
4. Les interventions, le contre d'appel, le réveil ; ce qu'on y enseigne en premier.
5. Le chelem (Blackwood à 4 ou 5 as ?), les conventions absentes (Roudi, Drury, Spoutnik… joués ou non).
6. Les entames et la signalisation.

Chaque différence écrite ici cite sa page (`source: BRIDGEZ p. N`).

## Banc (2026-11-21) : bridgez contre le SEF, 2 × 20 000 donnes
Le but n'est pas de battre le SEF mais de voir où les robots enchérissent mal quand une convention manque.
- `sans: [Roudi, Drury, Spoutnik, Bicolores, Landy, 4e couleur forcing]` : −1055 / −1138 IMP, 7,7 % des séquences
  changent. Le défaut : sans Spoutnik, rien ne remplace le contre après une intervention ; le répondant sans enchère
  naturelle passe, même avec 19 H (1♦ (2♠) passe) ou 6 piques et 10 H (1♦ (2♣) passe) : 74 donnes sur 20 000.
- La même liste en gardant Spoutnik : −761 / −812 IMP. Le reste (Drury : 3♠ direct ; bicolores : la couleur
  nommée seule ; Roudi ; Landy : passe sur 1SA avec 5-4 en majeures) est naturel et sans absurdité vue.
- Le résumé débutant de l'utilisateur (2026-11-21) diffère aussi du SEF des robots : 1M – 4M = 13-16 HLD avec 3+
  cartes (les robots disent 3♥) ; 1M – 2SA = 11-12 H et 1M – 3SA = 13-15 H réguliers (les robots disent 2♣) ;
  soutien d'une mineure avec 5 cartes ; nouvelle couleur au palier 2 : 12+ HL. Rien sur les interventions.
- **Choix de l'utilisateur (2026-11-21) : des enchères naturelles à la place du Spoutnik.** bridgez réécrit les
  réponses après une intervention (« 1M (1x) », « 1M (2x) | 1M (3x) », « 1N (1x) », « 1N (2x) | 1N (3x) ») et la
  redemande de l'ouvreur sur le contre (« 1x (1x) contre ») : contre punitif (10+ H, 5 cartes dans leur couleur, 4 sur
  une intervention au palier de 2), majeure 4e au palier 1 dès 6 HL, au palier 2 dès 12 HL, couleur 5e au palier 2
  dès 12 HL, au palier 3 dès 13 H, cue-bid 13+ H sans enchère naturelle. Tout est « à confirmer » (pas dans le résumé).
  Banc : −517 / −638 IMP (mieux que le Spoutnik gardé, −761 / −812). Le répondant ne passe plus avec 10+ H que sur
  26 donnes au lieu de 74 : des mains de 10-11 H avec une majeure 4e au palier 2, ou une longue couleur au palier 3.
- Reste à faire d'après le résumé : 1M – 4M = 13-16 HLD ; 1M – 2SA / 3SA réguliers ; soutien mineur avec 5 cartes.
