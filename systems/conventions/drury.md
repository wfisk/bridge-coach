# Drury fitté (SEF 2024, p. 20)

Après une ouverture de 1♥ ou 1♠ en 3e ou 4e position, le partenaire a déjà passé. Avec un fit et une main
proche de l'ouverture, le soutien limite à 3M serait risqué face à une ouverture parfois légère : il dit 2♣.

## Le répondant (main passée)
- 2♣ : artificiel et fitté (alerté) :
  - trois atouts et 11+ HLD ;
  - ou quatre atouts et 11+ HLD dans un jeu sans singleton ni chicane.
  Rien à voir avec les trèfles. Une main passée n'a pas 13 H : jamais le fit différé (forcing de manche).
- Avec moins (6–10 HLD), le soutien simple à 2M ; avec 5 atouts et une courte, la fermeture à 4M reste possible.
- Quatre atouts, une courte et 11+ HLD : le soutien limite à 3M **(à confirmer)** : le SEF réserve le Splinter aux
  cinq atouts après Passe.

## L'ouvreur
- 2M : ouverture faible, pour s'arrêter là.
- 2♦ : enchère ambiguë avec un espoir de manche (alertée).
- 3M : enchère de chelem.
- 4M : enchère de conclusion.
- Autre : enchère naturelle promettant au moins l'ouverture (le moteur ne s'en sert pas encore).

Les zones de points sont celles du moteur, le SEF ne les chiffre pas **(à confirmer)** : 2M jusqu'à 12 HL,
2♦ 13–14 HL, 4M 15–17 HL, 3M 18+ HL.

## Le répondant après 2♦
- 2M avec trois atouts ;
- 3M avec quatre atouts.

Puis l'ouvreur **(à confirmer)** : sur 2M, la manche avec 14 HL, sinon passe ; sur 3M (neuf atouts), la manche.

## Le répondant après 3M
Il montre un contrôle (cue-bid) ou conclut à 4M ; l'ouvreur cherche le chelem (Blackwood) quand le compte y est.

Le moteur : regles.yaml, « 1M » (2♣ quand le joueur est au siège 1 ou 2, donc a passé), « 1M - 2N » (réponses de
l'ouvreur au siège 3 ou 4), « 1C - 2T - 2K », « 1P - 2T - 2K », les deux suites après 2M et 3M, et
« 1C - 2T - 3C | 1P - 2T - 3P ». encheres.DRURY_PLACE : après Drury, pas de recherche de chelem, sauf après le 3M
de l'ouvreur. Variantes non retenues : Drury inversé, 2♦ Drury à quatre atouts.
