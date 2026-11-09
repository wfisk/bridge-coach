# SEF 2024 : séquences encore à écrire dans regles.yaml

Plan de travail, dans l'ordre. Chaque étape : écrire la section (en français, zones
complètes, longueurs montrées), ajouter des exemples, comparer au moteur sur des mains
au hasard, valider sur les deux séances et les 288 donnes neuves (écart moyen au par),
ne garder que ce qui ne dégrade pas, puis commit.

Mesure de départ (2 000 donnes au hasard, `couverture.py`) : 51 % des tours sans règle,
le moteur prend alors son code Python. Les fréquences guident l'ordre.

## 1. Constructif (adversaires silencieux)
- [x] 1.1 Redemande de l'ouvreur après 1M – 1SA (60)
- [x] 1.2 Suites après Stayman et texas : le répondant après 1SA – 2♣ – 2x, 1SA – 2♦ – 2♥,
      1SA – 2♥ – 2♠, et en 2SA (58)
- [x] 1.3 Le répondant après 1m – 1M – 1M' (44), 1M – 1SA – 2x (33), 1M – 2M – 3M (28)
- [x] 1.4 Réponses aux deux faibles et aux barrages : 2M (61), 3x (33) ; redemande
- [x] 1.5 Ouvertures fortes : 2♣ (relais 2♦, redemande), 2♦ forcing de manche (58, 42)

## 2. En défense, après la réponse adverse
- [x] 2.1 Quatrième position : (1m) passe (1M) (341), (1M) passe (2M) (88), (1M) passe (1SA) (74),
      (1M) passe (2m) (65), (1SA) passe (2x) (76) — surtout passe, plus les réveils utiles
- [x] 2.2 Suites de ces séquences au tour suivant
- [x] 2.3 Interventions sur 2x faible (2M) et sur 2SA ; réveil après un deux faible (en partie : réponse au contre du partenaire)

## 3. En concurrence, côté ouvreur
- [x] Cue-bids de soutien et de force (répondant, partenaire de l'intervenant, ouvreur 18–19 fitté) : voir `systeme.md`. Sur 4 000 donnes : +0,007 ± 0,013 IMP, 96 donnes concernées, aucun chelem de plus
- [x] 3.1 Le répondant après un contre d'appel : 1M (contre) (35), 1m (contre) (30) — les réponses ordinaires
      (le surcontre et les soutiens de barrage, essayés, coûtaient des points)
- [x] 3.2 Le répondant après 1m – 1M (1M') et autres interventions au 2e tour (31)
- [x] 3.3 Contre de l'adversaire sur nos deux faibles : 2M passe (contre) (28)

## 4. Chelem
- [x] 4.1 Blackwood 3041 : le moteur le déclenche partout, avant toute conclusion à la manche
      (`chelem()` dans encheres/__init__.py) ; réponses et suites restent dans le code
      (`reponse_blackwood`, `apres_blackwood`) car elles ne dépendent pas de la séquence
- [x] 4.2 Contrôles après un fit : `chelem()` les lance dès 28 points, `suite_controles()` les enchaîne, clés à 29+
      toutes couleurs contrôlées ; le fit se lit aussi sur les longueurs montrées, et `soutien_lent` (3M forcing) le
      montre avant la manche. Avec le saut 16–18 en concurrence et le cue-bid qui demande l'arrêt, sur 8 000 donnes :
      195 chelems au lieu de 125, 151 gagnés au lieu de 102, +0,035 IMP par donne (+0,021 et +0,049 sur les deux lots).
- [x] 4.3 SA quantitatifs et chelem à SA : 6SA avec 33+ H ensemble, 4SA quantitatif avec 31–32
      quand la zone du partenaire est bornée
      ; la couleur longue compte 1, 2 ou 3 points (5e, 6e, 7e) pour accepter : 7 à 10 contrats sur 4 000, neutre
      (−0,000 ± 0,010 et +0,004 ± 0,009), gardé pour les mains comme ♦ADV6532 face à 4SA
- [ ] 4.4 Ouverture de 2♣ sur les mains fortes irrégulières — en place avec HL 21–24 ; la
      condition `levees` existe, mais 2♣ sur levées de jeu n'a rien gagné (journal)

## 5. Conditions à ajouter à la grammaire
- [x] Vulnérabilité (`vul nous`, `vul eux`) pour les barrages et les interventions
- [x] Information du camp (`fit(Y) 9+`, `camp H 25+`) : dans la grammaire, le moteur passe
      ce que le partenaire a montré ; pas encore de règle qui s'en serve (essais ci-dessous)

## Journal
- 1.1–1.3 : 288 donnes neuves 5,07 → 5,00 IMP, 84 contrats au par (code : 83). Leçons :
  inviter avec 9–10 et un fit quand l'ouvreur répète (sinon des manches manquées) ;
  1SA « sans fit » exige une main sans singleton.
- Deux faibles : exiger deux honneurs dégradait le double mort (essayé, retiré) ; de même
  le soutien de barrage 2M – 3M (retiré).
- 1.4–1.5 : réponses aux deux faibles et barrages, relais 2♦ sur 2♣ et redemande, relais
  2♥ sur 2♦. Les suites du répondant après 2♣ – 2♦ – 2x coûtaient 0,07 IMP : retirées, le
  moteur garde son code (placement général) en attendant mieux.
- 2.1 : en quatrième position après leur réponse, on évite leurs deux couleurs ; 288 donnes
  neuves 5,00 → 4,99 IMP, 85 contrats au par (code : 83).
- 2.2, 2.3, 3.1 et 1.3 (suite) : 4,98 IMP, 85 au par, 203 contrats gagnants. Couverture :
  43 % des tours sans règle (51 % au départ).
- Contrats atteints (passe), réveils sur deux faible et barrage, 1SA adverse sur notre
  ouverture, l'ouvreur quand ils interviennent après notre réponse : 288 donnes neuves
  4,93 IMP, 87 au par, 212 gagnants — mieux que l'ancien code sur les trois mesures
  (4,94 ; 83 ; 205). Séance réelle 4,4 IMP (meilleur résultat), 6 tables 4,6.
  Attention aux rôles : dans 1♣ – 1♥ – (1♠), l'intervenant est Z (4e joueur), pas Y.

- 4.1 et 4.3 (contrôle du chelem avant la manche) : 1 440 donnes neuves pour l'étalonnage
  (`chelem/`, graines 7011–7040) : avec un fit de 8, le chelem gagne au double mort une fois
  sur deux dès 30 points (H du long + HLD du court). Seuil essayé de 29 à 33 sur le minimum du
  partenaire : 31 le meilleur. 5,05 → 4,95 IMP, 29 chelems demandés, 23 réussis ; les 288
  donnes de validation restent à 4,93 ; séance réelle inchangée (4,4 : ses chelems manqués sont
  un grand chelem, un 6SA à 28 H et un sacrifice).
- 5 (vulnérabilité) : `NN` `NV` `VN` `VV` (nous puis eux) et `vul nous` / `vul eux` dans la grammaire.
  Gardé : deux faibles, barrages et sauts faibles à 8–10 H en défavorable ; interventions
  au palier de 2 à 12+ H vulnérable. 1 440 donnes 4,953 → 4,931 IMP, 288 donnes
  4,927 → 4,910. Essayé et retiré : barrages à 4 avec 8 cartes (neutre), barrage à 3 avec
  6 cartes en mineure en favorable (−0,02), deux faibles à 5 H en favorable (neutre),
  interventions à 10 H non vulnérable (neutre).
- 5 (information du camp) : `fit(X)` et `camp`. Essayés et retirés : soutien « loi des
  levées » de l'avançant avec 9 atouts et 3–6 H, ou au saut avec 10 (1 440 donnes
  4,931 → 4,939) ; la clé `(1x) 2x (2x)` ajoutée à l'avance après leur soutien (neutre).
  Au double mort, disputer plus haut avec peu de points ne paie pas : les rares gains de
  partielle sont repris par les contres et les levées de chute.
- Écarts avec l'analyse experte du 23/10 (11 contrats différents) : quatre corrections, mesurées
  sur les 1 440 + 288 donnes neuves (4,920 / 4,882 au départ → 4,901 / 4,837 IMP) ; séance
  4,4 → 3,7 IMP, 9 contrats différents.
  - Gardé : une bonne couleur 5e (deux de A R D) vaut un point pour accepter une invitation à SA
    (code et règles « 1M - 2SA », « 1N - 2SA » : 13 H suffisent) ; contre d'appel fort (17+)
    sans singleton dans une majeure libre, sinon intervention au palier de 2 jusqu'à 18 H
    (au palier de 1 on reste à 16 : avec plus, contre puis couleur) ; saut à 3W de l'ouvreur
    avec 13+ H (sinon 2W) ; le contreur soutient la réponse du partenaire (HLD + 1 avec 4 atouts :
    21 pour la manche en majeure, 19 pour monter d'un palier ; 3 atouts seulement avec 20+).
  - Essayé et retiré : ouvrir 2♣ sur 9–10 levées de jeu avec 15–16 H. Mêlé au 2♣ fort, il
    abaisse la zone montrée et le répondant cesse de chercher manche et chelem (+0,10 IMP) ;
    en règle séparée, neutre. La condition `levees` reste dans la grammaire.
- 4e couleur forcing (11+ H, souvent sans arrêt) et les réponses de l'ouvreur, sur les cinq
  séquences les plus courantes : 1 440 donnes 4,901 → 4,897 IMP, validation inchangée (4,837).
- Après 2♣ – 2♦ – 2SA : le système de 2SA, deux points de moins (neutre, gardé). Les réponses du
  répondant à 2♣ – 2♦ – 2M / 3m (soutien, couleur, 2SA négatif, passe sur 3m faible) coûtaient
  0,02 à 0,10 IMP : la suite de l'ouvreur reste dans le code et ne suit pas ; retirées.
- 1♥ – 1♠ – 2♣/2♦ : le répondant (préférence, invitations, 4e couleur) et les réponses de
  l'ouvreur à la 4e couleur : 4,897 / 4,840 → 4,894 / 4,830 IMP.
- Mesure des pertes : couts.py attribue l'écart au par des donnes aux séquences jouées par le
  code ; la couverture brute (37 %) compte surtout des passes sans enjeu.
- Entames : `entames.yaml` lu par `src/entames.py` (couleur puis carte, conditions par couleur
  candidate). Mêmes entames que l'ancien code sur 50 000 mains au hasard, sauf 2 (toutes les
  couleurs possibles nommées par les adversaires : le fichier n'y entame plus un singleton).
  Rapport du 23/10 inchangé (même entame que l'expert 19/24).
- Ouvertures fortes, les deux joueurs (2♣ – 2♦ – couleur : réponses du répondant, redemande de
  l'ouvreur, suites) : 4,894 / 4,830 → 4,911 / 4,924 IMP ; majeures seules 4,899 / 4,872,
  mineures seules 4,906 / 4,882. Retiré : au double mort, le 3SA direct de l'ancien code paie
  mieux sur ces mains fortes qu'une séquence naturelle. Le surcontre et les soutiens de barrage
  après un contre d'appel ont déjà coûté deux fois : non repris.
- Entames : contre un chelem, l'as d'abord (3 entames changées, +2 levées, un contrat battu de
  plus) ; entame atout contre un bicolore essayée, sans gain (−2 levées, ou +2 et un contrat de
  moins battu).
- Séance à 6 tables : enchères expertes refaites à la table (15 contrats changés ; l'expert passe
  de 0,6 à 4,1 IMP, le programme 4,8 ; même contrat 14/24 au lieu de 10).
- Donnes 3 et 7 du 23/10 : 2SA bicolore mineur après leur soutien (1♥ – passe – 2♥ – 2SA) et
  réponse du partenaire ; l'intervenant répète une 6e avec 14+ H quand ils ont parlé après son
  partenaire. Neutre sur les donnes neuves (4,894 / 4,830), séance 3,7 → 3,6. Essayé et retiré :
  en concurrence, lire la montée au palier le plus bas comme une dispute de partielle et non une
  invitation (4,894 → 4,906).
- Vulnérabilité dans le code : loi des levées un palier plus haut en favorable, un plus bas en
  défavorable : 4,894 → 4,883 IMP (validation inchangée). Essayé et retiré : manche vulnérable
  avec un ou deux points de moins (4,919 et 4,903 : au double mort, ces manches chutent).
- Analyses expertes : « Décision serrée : … » quand deux enchères se défendaient (23/10 et
  séance à 6 tables).
- Écarts avec l'expert, entraînement du 01/11 (2026-11-02), mesurés sur 3 × 60 000 donnes neuves
  (double mort seulement là où les enchères diffèrent, contre la version précédente) :
  - Code : fit de 8+ dans la mineure du partenaire et 29+ points : 4 de la mineure, forcing, au lieu
    de 3SA, puis les contrôles (FIT_MINEUR). 3 000 et 5 000 donnes : +30 et +100 IMP.
  - Gardé : 2♣ – 2♦ – 2♥ – 2♠ avec quatre piques et deux cœurs au plus, l'ouvreur redit 3♥ avec six
    cœurs ; le reste au code. Premier essai avec trois cœurs et sans le 3♥ : −95 IMP (le fit cœur
    se perdait après 2SA). Le 3SA du répondant après la 4e couleur et le 2SA de l'ouvreur : 12+ H, ou
    11 H et quatre cartes à deux gros honneurs dans la couleur de l'ouvreur (`H(U) 5+`) ; sans les
    honneurs, la donne 7 du 01/11 chutait. Ensemble : +72, +112, +134 IMP.
  - Gardé : 2♣ – 2♦ – 2SA montre 22–23 H (le chelem se compte sur 22, pas 21) : +24, +41, +17 IMP.
    Essayé et retiré : 5-5 en majeures après 2♣ – 2♦ – 2SA (texas cœur puis 3♠, l'ouvreur choisit) :
    −22, −3, +1 IMP en plus ; la donne 18 du 01/11 seule le justifiait.
  - Essayés et retirés (réponses à 1M, 3 × 60 000 donnes) : 2 sur 1 dans une mineure 6e plus longue que
    les piques avec 11+ H, au lieu de 1♠ (−46, −26, +78 IMP) ; bicolore 6-5 à 9–10 H en 2 sur 1 au lieu
    de 1SA (+63, −21, −30). Les suites ne suivent pas : après 2♣ le répondant ne nomme pas ses piques,
    après 2♦ l'ouvreur 6-4 saute à 3♠ sans montrer ses cœurs (donnes 9 et 5 du 01/11).
- Chelems manqués (bilan-encheres.pdf : 10 donnes, −121 IMP sur 5 séances), le compte du chelem (`valeur_fit`),
  3 × 60 000 donnes neuves :
  - Gardé : quand le partenaire a montré autant d'atouts que moi (5+), mes courtes comptent (HLD) :
    +161, +147, +219 IMP (71 mieux, 28 moins bien). Donne 4 du 01/11 (2e séance) : 6♥ comme l'expert.
  - Gardé : la main longue à l'atout compte sa chicane 3 et son singleton 1 (`COURTES_LONG`) :
    {0:2, 1:1} +194, +189, +324 ; {0:3, 1:1} encore +93, +79, +27 au-dessus ; {0:3, 1:2} −388, −371, −319.
  - Seuil du chelem revu après ces comptes : 31 reste le meilleur (30 : −144 et +300 ; 32 : −565 et −413).
- Écarts des séances d'entraînement (2026-11-02), 3 × 60 000 donnes neuves :
  - Gardé (code) : l'ouvreur lit la majeure libre promise par le contre Spoutnik du fichier de règles
    (le contre n'y portait aucune longueur : 3SA au lieu du fit) : +809, +745, +868 IMP.
  - Gardé (code) : sur une invitation dans sa couleur, fit pas encore montré, la forme compte (valeur_fit) :
    +310, +270, +368.
  - Gardé (code) : vulnérable, l'invitation s'accepte un point plus bas ; une zone montrée large (12–21)
    se juge sur le total avec le partenaire : +1 317, +813, +1 308. Non vulnérable, la zone large perd
    (≈ −200) : elle reste au milieu de la zone.
  - Gardé : le soutien limite 3M avec trois atouts, sauf cinq piques sur 1♥ (1♠ d'abord) : −4, +31, +103.
    Essayé et retiré : quatre atouts exigés (−373, −371, −341 : la suite ne soutient pas plus tard).
  - Essayé et retiré : 1m – 1K – 1M, 3SA du répondant ouvert à 19+ H (+13, −84, +23), puis seulement
    régulier (−28, −30, −7) : le 4SA quantitatif qui suit coûte plus que la préférence passable.
  - Gardé : 1♥ – 2♣ – 2♦ – 2♠, quatre piques et 11+ H (−16, +8, +68). Essayés et retirés : avec lui, la
    mineure 6e d'abord au lieu de 1♠ (−79, −28, +130) ; l'ouvreur 6-4 nomme ses cœurs sur 1♠ – 2x
    (−53, +29, +14), et avec lui le bicolore 6-5 en 2 sur 1 (+19, +5, −2). Les mains 6-5 restent ainsi.
  - Trous du système, comblés « à confirmer » (choix de Claude, à valider) :
    - Gardé : sur 2SA, 4♣ / 4♦ naturels, six cartes et 9–12 H : essai de chelem, le partenaire répond par
      les contrôles (rare : −6, +24, +43 IMP ; 8–12 H et 10–12 H du même ordre).
    - Gardé : intervention naturelle sur un barrage de 3, six cartes, 10–17 H : +586, +333, +572 IMP dès
      12 H, encore +383, +222, +369 à 10 H. Plus bas gagne encore au double mort (8 H : +212, +248, +298),
      mais le moteur contre rarement pour punir : arrêté à 10 H. Avec aussi cinq cartes et 14 H, un peu moins.
    - Essayé et retiré : contre Spoutnik sur leur saut au palier de 3 (8 H : −182, −254, −121 ; 10 H :
      −64, −127, −25 ; 12 H neutre) ; reste dans le code, éteint (SPOUTNIK_3 = 0).
    - Essayé à nouveau et retiré : 5-5 en majeures après 2♣ – 2♦ – 2SA (−22, −16, −10).
- Audit (2026-11-02) : les règles qui partent souvent sans rien transmettre (condition en « ou ») —
  `completer()` dans encheres/__init__.py ajoute la longueur sous-entendue : Spoutnik, la majeure libre
  (+85, +44, +24) ; couleur répétée, une carte de plus, 5 à 6 (+20, +50, +4) ; contre d'appel, 3 cartes
  dans les majeures non nommées (+238, +46, +162). Ensemble : +356, +152, +190 IMP.
- Contre punitif général (`punir()`, filtre comme `chelem()`) : leur contrat à la couleur au palier de 3 ou plus,
  4+ atouts et deux levées d'atout, notre camp 20+ points ; le partenaire le laisse. +2 361, +2 498, +2 124 IMP
  (palier 2 : un peu plus, mais un contre au palier de 2 y est Spoutnik). Plus large gagne encore (18 points :
  +1 403 en plus ; une levée d'atout : +1 451) : ce sont les enchères de concurrence du moteur qui sont trop
  légères, pas le contre qui doit l'être. Seuils gardés : ceux du livre. Le banc d'essai punit désormais.
  `legal()` refuse un palier au-delà de 7 (« 10♠ » d'un calcul de palier).
- Drury (2026-11-02, demandé par l'utilisateur, conventions/drury.md, à confirmer) : main passée, 3+ atouts et
  10–12 HLD sur 1M en 3e ou 4e : 2♣ ; l'ouvreur 2M / 3M / 4M ; après Drury, pas de recherche de chelem
  (DRURY_PLACE). Neutre au double mort : −216, +14, +122 IMP ; gardé parce que c'est le système joué. Le moteur
  passe désormais le siège à toutes les règles (S 1-2 en réponse : main passée).
  Essayé et retiré : contrôles au palier de 3 au moins (−285, −385, −124) : le moins cher reste (CONTROLE_PALIER = 1).
- Concurrence remesurée avec le contre punitif (3 × 60 000 donnes) :
  - Intervention naturelle sur un barrage de 3 à 10 H confirmée : 12 H −364, −195, −350 ; 14 H et sans
    intervention, pire.
  - Loi des levées : sans palier de plus en favorable ni de moins en défavorable (LOI_FAV = LOI_DEF = 0) :
    +326, +363, +204 IMP ; garder le palier de moins seul, +193, +306, +162.
  - Interventions directes inchangées : au palier de 1 deux points de plus, neutre (+30, −98, −129) ; saut
    faible dès 8 H, −930, −1 111, −1 235 ; palier de 2 dès 12 H, −329, −111, −258.

## Déjà fait
Ouvertures ; réponses à 1x, 1SA, 2SA ; Stayman et texas (réponses de l'ouvreur) ;
redemandes de l'ouvreur et du répondant ; interventions directes et en réveil ;
le partenaire de l'intervenant ; l'ouvreur après une intervention ; réponses après
intervention ; 2SA bicolore mineur ; répondant après une réponse au palier de 2.

## Base rapprochée de l'expert (2026-10-31)
Différences de contrat classées par IMP sur les trois séances. Gardé après mesure sur donnes neuves
(étalonnage 4,883 → 4,860 environ, validation 4,830 inchangée ou mieux) : l'ouvreur passe sur
1M – 1SA jusqu'à 17 H régulier ; contre de réveil sur 1SA à 15+ H (au lieu de 12+) ; contre de
réveil à 12+ H après deux enchères adverses ; 3♥/3♠ forcing à 10+ H sur 1SA (2x) ; l'ouvreur passe
1SA avec 16 H ou moins après trois couleurs ; l'intervenant répète une couleur 7e. Le partenaire qui
soutient notre couleur à la manche compte pour 3 cartes dans la recherche du chelem.
Non retenu : 2♣ sur levées de jeu et 4♠ sur 3♠ en concurrence (déjà mesurés, ils coûtent).

## Élimination dans le plan (2026-10-31)
`jeu.cadre_elimination` cherche le cadre, `coups.chance_elimination` joue la ligne sur 40 donnes
imaginées contre la même ligne avec la couleur clé jouée tout de suite. 57 cadres sur 1 099 contrats
à la couleur tirés au hasard, 2 conseils ; aucun sur les trois séances. À revoir : la ligne du
déclarant est simple (pas d'impasse ailleurs, entrées limitées), ce qui peut cacher des cas.

## Réponses aux deux faibles et aux barrages (2026-11-09)
Banc nouveau : deux versions du moteur sur les mêmes donnes au hasard, écart au par (IMP) des donnes où les contrats
diffèrent. Gardé : 2M – 4M et 3M – 4M avec dix atouts ensemble (`fit(U) 10+`, loi des levées) : 20 000 donnes, 57
contrats changés, +38 IMP ; sur 3M, la manche dès 12 HLD avec deux atouts (au lieu de 15 ; 14 : +18, 13 : +29, 12 : +36,
11 : +35 ; graine 11 : 13 +44, 12 +46). Les deux ensemble : +136 IMP sur 20 000 donnes (graine 11). Donne réelle : 3♠
du 05/11 (n° 21), le partenaire A4 AX4 A9874 X95 dit maintenant 4♠.
Essayé et retiré : après 2♣ – 2♦ – 2M, le soutien à 3M forcing (3+ atouts, 6+ H) pour chercher le chelem, 4M restant
faible : +17 puis −15 IMP sur deux lots de 20 000 (neutre), bien que le 6♠ du 05/11 (n° 26) soit trouvé.
