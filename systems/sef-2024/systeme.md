# SEF 2024 (Système d'Enseignement Français)

Majeures 5e, marque IMP. Conventions jouées : voir `conventions.md`.
Les lignes **(à confirmer)** viennent de la mémoire, pas du livret FFB : à vérifier
dans `ffb/` avant de s'y fier.

## Ouvertures
- 1♣ : 12–21 H, 3+ trèfles **(à confirmer : cas des mineures 3-3 et 4-4)**
- 1♦ : 12–21 H, 4+ carreaux sauf exceptions **(à confirmer)**
- 1♥ / 1♠ : 12–21 H, 5+ cartes
- 1SA : 15–17 H, régulier **(à confirmer : avec une majeure 5e ?)**
- 2♣ : fort indéterminé **(à confirmer)**
- 2♦ : forcing de manche **(à confirmer)**
- 2♥ / 2♠ : faible, 6 cartes **(à confirmer : zone de points)**
- 2SA : 20–21 H, régulier **(à confirmer)**
- En troisième position : ouverture légère dès 8 H avec la règle des 20, ou à 10 H avec neuf cartes dans les
  majeures. Un deux faible ou un barrage reste prioritaire.
- En concurrence, après leur soutien (1♠ – passe – 2♠) : on intervient au palier de 3 avec six cartes et 11–16 H.
- En quatrième position : on ouvre à 12 H+, ou à 10–11 H avec une couleur de 6 cartes. Les autres mains de
  10–11 H sont limites : on les ouvre avec la règle des 15 (H + nombre de piques >= 15), sinon on passe.

## Réponses à 1♣ / 1♦
- Avec une majeure 4e et une mineure 5e : la majeure d'abord seulement avec 5–11 H ;
  avec un jeu forcing de manche, la couleur la plus longue d'abord
  (ex. 1♦ – 2♣ – … – 2♠).

## Redemande de l'ouvreur
- Deuxième couleur moins chère avec 18+ HL : saut dans cette couleur, forcing **(à confirmer)**.

## Redemande en concurrence
- Après 1x – 1y – (intervention) : 6+ cartes et 16–18 HL, saut dans sa couleur, comme sans intervention **(à confirmer)**.

## Quatrième couleur forcing
- Le répondant nomme la 4e couleur : 11+ H, forcing, souvent sans arrêt dans cette couleur
  (avec l'arrêt, il dirait SA). Écrit pour 1♣–1♥–1♠–2♦, 1♦–1♥–1♠–2♣, 1♣–1♦–1♠–2♥,
  1♦–1♥–2♣–2♠ et 1♦–1♠–2♣–2♥.
- L'ouvreur répond : 3 cartes dans la couleur du répondant (saut avec 15+), sinon SA avec
  l'arrêt (2SA 12–14, 3SA 15+), sinon il répète sa couleur.

## Après 1SA
- 2♣ : Stayman (`../conventions/stayman.md`)
- 2♦ / 2♥ : texas (`../conventions/texas.md`)
- 4SA : quantitatif

## Après 2SA
- 3♣ : Stayman **(à confirmer)**
- 3♦ / 3♥ : texas
- 4SA : quantitatif
- 4♣ / 4♦ : naturel, six cartes, 9–12 H : essai de chelem ; l'ouvreur répond par ses contrôles **(à confirmer)**

## Concurrence (toute la section est à confirmer)
Règles suivies par le moteur d'enchères (src/encheres/sef2024.py, étape 2).

### Intervention sur un barrage de 3
- Couleur naturelle avec six cartes, 10–17 H ; contre d'appel 15+ H court dans leur couleur **(à confirmer)**

### Intervention sur une ouverture à la couleur
- 1SA : 15–18 H, régulier, arrêt dans la couleur adverse
- Couleur au palier de 1 : 5+ cartes, 8–16 H (10+ si la couleur est pauvre)
- Couleur au palier de 2 : bonne 5e ou 6e, 11–16 H
- Saut faible : 6 cartes, 6–10 H
- Contre d'appel : 12+ H, court dans la couleur adverse, 3+ cartes dans les majeures non nommées ;
  ou 17+ H quelle que soit la forme (puis on nomme sa couleur)
- Réveil (après 1x – passe – passe) : mêmes enchères avec 3 points de moins
- Pas d'intervention au palier de 4, ni de réveil au-dessus du palier de 2 ; au palier de 3, 3 points de plus
- Sur 1SA : couleur 6e naturelle au palier de 2 (8+ H) ; contre = 15+ H, punitif

### Partenaire de l'intervenant
- Sur une intervention en majeure : soutien 7–10 DH au palier le plus bas, saut = barrage (4+ atouts),
  cue-bid de l'ouverture avec 11+ points (voir Cue-bids)
- Sur une intervention en mineure : soutien 7–10 DH, saut = invitation (11–12), 13+ fit forcing
- Sans fit : SA avec arrêt (1SA 8–11, 2SA 12–14, 3SA 15+) ou couleur 5e
- Sur un contre d'appel : meilleure couleur (majeure 4e d'abord) au palier le plus bas (0–8 H),
  saut avec 9–11 H, manche avec 12+ ; 1SA avec 6–9 H et un arrêt ; obligé de parler sauf si l'adversaire a enchéri

### Camp de l'ouvreur après une intervention
- Soutien : 6–10 DH au palier le plus bas, saut = invitation (11–12), manche en majeure avec 13+ et 3 cartes
  (avec 4 cartes et 13+ : cue-bid, voir Cue-bids)
- Soutien mineur avec 13+ H et un arrêt : 3SA **(à confirmer)**
- Contre Spoutnik : 6+ H, 4 cartes dans la ou les majeures non nommées
- Couleur 5e : au palier de 1 avec 6+ H, au palier de 2 avec 11+ H (forcing)
- SA avec arrêt : 1SA 8–10, 2SA 11–12, 3SA 13+
- Après 1SA – (intervention) : couleur 5e naturelle, 2SA 8–9 avec arrêt, 3SA 10+ avec arrêt
- L'ouvreur répond au Spoutnik par la majeure 4e (saut avec 16+), sinon SA avec arrêt, sinon sa couleur
- Partenaire muet : l'ouvreur répète une 6e, conclut la manche avec 7 cartes en majeure et 19+ HL,
  ou recontre (appel) avec 17+ court dans la couleur adverse

### Cue-bids (soutien et force)
Confirmé par le club : le cue-bid de la couleur adverse montre le soutien du partenaire et de la force.
Les zones viennent de fiches de clubs qui citent le SEF 2024, pas du livret : **(à confirmer dans `ffb/`)**.
Une fiche donne 11 H et non 13 pour le cue-bid du répondant ; le SEF 2024 p. 21 est cité pour 13.
- Répondant, ouverture en majeure : 4+ cartes de soutien, 13+ HLD, forcing de manche.
  Il ne promet pas de contrôle dans leur couleur. L'ouvreur dit la manche, ou répète au palier de 3 avec 15+ HL
  (arriver lentement montre des points en plus) ; le répondant conclut ou cherche le chelem.
- Répondant, ouverture en mineure : 12+ H, forcing de manche, dénie une majeure 4e non nommée.
  Soit il cherche l'arrêt pour jouer à SA, soit il a un beau fit mineur sans arrêt. L'ouvreur : 2SA avec l'arrêt et
  12–13 H, 3SA avec l'arrêt et 14+ H, sinon il répète sa mineure ; le répondant place la manche.
- Partenaire de l'intervenant, intervention en majeure : cue-bid de l'ouverture, 3+ cartes de fit, 11+ HLD ;
  avec un saut, 4+ atouts et 12+ HLD. L'intervenant répète sa couleur avec moins de 13 HL, saute avec une ouverture.
  L'avance s'arrête avec 11–12 points sur la répétition simple, dit la manche avec 13+.
- Ouvreur, après 1x – passe – 1M – (1y ou 2y) : cue-bid = 4 cartes de soutien, 18–19 H, régulier, puis la manche.
- Avant 3SA, les deux camps ayant parlé : sans arrêt dans leur seule couleur, le cue-bid demande l'arrêt.
  Le partenaire dit 3SA avec l'arrêt, sinon sa couleur la plus longue, et on joue la manche à la couleur.

Décrit dans le SEF 2024, pas encore joué par le moteur **(à confirmer)** :
- Sur intervention, 2SA du répondant = fit par 3 cartes exactement, 11–15 HLD (nouveauté 2024). Le moteur garde ici
  2SA naturel (11–12 H, arrêt) et le soutien à saut avec 3 cartes.
- Cue-bid du partenaire du contreur (forcing, fait décrire le contreur) ; Michaels et autres cue-bids bicolores
  de l'intervenant ; splinter dans leur couleur.

Ce ne sont pas les contrôles après un fit, qui cherchent le chelem : voir la section Chelem.

### Partielles disputées
- Loi des levées totales : avec un fit, on dispute jusqu'au palier (nombre d'atouts − 6), sans dépasser 3
  ; un palier de plus en vulnérabilité favorable, un de moins en défavorable

## Chelem : les contrôles
Confirmé par le club : après un fit, on nomme ses contrôles pour chercher le chelem. Le détail ci-dessous n'a pas de
source FFB dans ce dossier **(à confirmer dans `ffb/`)**.
- Quand : le fit est établi (les deux partenaires ont nommé la couleur, ou les longueurs montrées font huit cartes,
  comme après un Spoutnik), le camp a 28+ points, et une enchère reste disponible sous la manche.
- Fit pas encore établi : celui qui a déjà montré 11+ soutient en majeure au palier de 3, forcing, plutôt que de
  sauter à la manche (1♥ – 2♦ – 2♥ – 3♥). L'autre nomme un contrôle ou conclut.
- Un contrôle : l'as ou la chicane (premier tour), le roi ou le singleton (deuxième tour). Confirmé par le club : on
  nomme les contrôles dès le deuxième tour, sans attendre d'avoir montré les as. La nouvelle couleur montre le
  contrôle, pas une longueur ; elle est forcing.
- On nomme le contrôle le plus économique : sauter une couleur nie le contrôle dans cette couleur.
- Le partenaire : une couleur sautée qu'il ne tient pas non plus, il conclut à la manche, car deux levées rapides
  peuvent manquer. Moins de 28 points, il conclut aussi. Toutes les couleurs contrôlées et 29+ points ensemble,
  il demande les clés (Blackwood 3041). Sinon il nomme son contrôle suivant.
- Rien à nommer sous la manche : on conclut. Une couleur au-dessus de la manche n'est pas nommée.
- Un joueur qui a nommé un contrôle n'est pas limité par sa première zone : le partenaire compte sa vraie force.

- Quantitatif par défaut, même après un texas.
- Pour accepter une invitation à SA, une bonne couleur longue (deux des trois gros honneurs A R D) compte en plus :
  1 point en 5e, 2 en 6e, 3 en 7e ou plus **(à confirmer : estimation du programme, pas du SEF)**.
- Blackwood 3041 une fois le fit annoncé, ou quand 4SA suit une enchère au palier
  de 4 (`../conventions/blackwood-3041.md`).
