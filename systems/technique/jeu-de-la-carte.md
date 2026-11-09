# Jeu de la carte du déclarant

Principes suivis par `plan_de_jeu` dans `src/jeu.py`. Ils ne dépendent pas du
système d'enchères, d'où ce dossier à part. Le programme ne lit pas ce fichier :
toute modification ici doit être reportée dans `jeu.py` (et inversement).

**Le plan se fait à la table.** Il part de la main du déclarant, du mort, de l'entame et des
enchères, jamais des mains adverses ni du double mort. Il dit ce qu'il faut espérer, pas ce
qui arrive. Le double mort et le sort réel des impasses vont dans le commentaire, après coup
(`apres_coup`).

## Présentation
Le plan commence par le compte (« Compte : O déclarant à 3SA, entame ♣4. Levées sûres : … : 6 ; il
en faut 9. Avec des partages normaux : … : 8 levées. »), puis les étapes numérotées dans l'ordre de
jeu : premier pli, atout et coupes, couleur à affranchir avec l'honneur à jouer d'abord (celui de
la main courte) et ce que donnent le partage normal et le mauvais, couleurs à tirer en tête, enfin
les impasses (« Levée manquante », ou « En réserve » si le contrat n'en dépend pas). À sans-atout,
l'impasse dit qui reprend la main si elle perd. Les perdantes sont nommées (l'honneur s'il y en a
une, sinon « deux carreaux », « deux atouts »).

## Compter
- Levées sûres : nos cartes qui se suivent depuis l'as, dans la limite des tours.
- Partage normal : les cartes qui nous manquent sont distribuées en alternance aux deux
  adversaires (3-2 sur cinq cartes, la plus forte d'un côté, la suivante de l'autre) ; on joue
  la couleur tour par tour. Exemples : ARD82 face à V76, le X tombe (5 levées) ; AD face à 32,
  le R fait une levée, sauf impasse.
- Sans-atout : levées sûres, puis levées avec des partages normaux ; une couleur qui dépend
  d'une impasse ne compte que ses levées sûres (hors la couleur à affranchir).
- Couleur : perdantes de la main longue à l'atout (tours = sa longueur dans la couleur ;
  à l'atout, la plus longue des deux mains). Une perdante peut être coupée dans la main
  courte à l'atout quand elle y est plus courte, dans la limite de ses atouts.
- Ce compte ignore les communications et le tempo.

## Atout
- Le plan indique la longueur du fit et le partage qu'on espère (3-2 sur cinq cartes,
  2-2 ou 3-1 sur quatre).
- Purger les atouts si la main courte en garde assez pour les coupes prévues, sinon
  couper d'abord puis purger ; sans coupe : « faire tomber les atouts ».

## Impasses
- Fourchette (ex. AD) dans une main : on joue de l'autre main vers elle ; l'honneur
  manquant doit être dans la main qui joue avant la fourchette. Texte : « ♥ : jouer de O
  vers AD753 en E : l'impasse réussit si N, qui joue avant E, a le ♥R. »
- Ce que les enchères et l'entame disent de l'honneur (`placer`) : un adversaire qui a
  montré 8 H ou plus face à un partenaire qui n'a rien montré l'a plus probablement
  (« favorable », « défavorable ») ; s'il ne reste pas la place chez l'autre, il l'a.
- Double impasse : A et V dans une main, R et D dehors ; chaque honneur placé avant la
  fourchette est capturé.
- 8 cartes : impasse ; 9 cartes : on tire en tête pour la dame ou le valet, avec
  A R V face à quatre cartes : 53 % contre 45 % (l'impasse au roi reste proposée).
- Pas d'impasse si l'autre main n'a aucune carte pour jouer vers la fourchette.

## Déclarant simulé (`lignes.py`)
Le plan ne se contente pas de compter : il essaie la donne. Sur 40 donnes imaginées, fidèles aux
enchères et à l'entame, un déclarant simulé joue toute la main. À chaque carte, il imagine 12 mondes
fidèles à ce qui a été joué (cartes vues, défausses), résout chacun et garde la carte qui gagne le
contrat le plus souvent ; il ne voit jamais les mains adverses de la donne essayée. La défense joue au
double mort. Le déclarant simulé décide alors du plan :
- l'ordre des étapes est celui où il attaque les couleurs ; la ligne carte par carte n'est pas donnée,
  car elle diverge dès le 2e pli d'une donne imaginée à l'autre, alors que l'ordre des couleurs tient ;
- coupes ou atouts d'abord : ce qu'il fait dans au moins 60 % des essais, sinon le compte tranche ;
- une impasse qu'il tente dans au moins 40 % des essais n'est plus « en réserve », elle a son étape ;
- une coupe qu'il joue et que le compte ne dit pas a son étape ;
- « Essai à la table » : un mot (presque sûr, probable, ouvert, difficile, très difficile) et le taux
  arrondi à 10 %, l'ordre le plus joué, ce qui décide (partage ou place d'un honneur, s'il change le taux
  d'au moins 30 points, avec 5 donnes de chaque côté), les impasses tentées.
- Quand tous les mondes disent que plusieurs cartes gagnent, le double mort se moque de l'ordre, pas la
  table : le déclarant prend alors le jeu sûr (tirer les atouts adverses, ne pas couper sans besoin), tant que
  la défense peut encore avoir des atouts. Ses atouts tombés, il joue pour le plus de levées : le mort coupe les
  perdantes du déclarant.
  Sans cette règle, il coupait au hasard et n'annonçait que 60 % pour un grand chelem de 14 levées.
- Ne pas comparer deux lignes carte par carte au double mort : toutes les impasses y seraient
  devinées juste, et sembleraient gratuites. Ici, chaque décision se prend sur des mondes variés.
- Limites : la défense parfaite est sévère ; le déclarant suppose qu'il pourra deviner plus tard,
  ce qui le rend un peu optimiste ; 40 donnes donnent un ordre de grandeur (±15 points), pas une précision.
- Banc d'essai sur la donne elle-même : `src/essai_jeu.py`. Deux séances : 45 contrats gagnés sur 52 possibles,
  0,7 levée sous le double mort. 150 donnes nouvelles (`--aleatoire`) : 89 sur 107, 0,8 levée sous le double
  mort ; le taux annoncé tient (annoncé 8 %, réel 15 % ; 36 %, 28 % ; 62 %, 57 % ; 81 %, 67 % ; 98 %, 98 %).

## Défausses
Dans un contrat à la couleur, les cartes maîtresses de la main courte à l'atout qui dépassent la
longueur de la main longue donnent une défausse, comptée en moins des perdantes.

## Fin du plan
- Sans-atout avec moins de levées sûres qu'il n'en faut : affranchir la couleur qui en
  rapporte le plus, avec le partage espéré.
- Levées sûres suffisantes : « ne pas prendre de risque ».
- Il faut une impasse : « Il faut réussir une impasse. »
- Il manque des levées même si les impasses réussissent : « compter sur la défense, ou
  limiter la chute ».

## Premier pli et laisser-passer (`coups.premier_pli`, à la table)
Sur 60 donnes imaginées par le déclarant (voir plus bas), chaque carte du mort est jouée au
double mort, puis, le joueur suivant ayant fourni, le choix de prendre ou non. On garde le plus
petit du mort et on prend, sauf si un autre choix est nettement meilleur (test de McNemar). À sans-atout, avec un seul arrêt, le plan rappelle la règle de 7 : 7 moins nos
cartes dans la couleur = tours à laisser passer.

## Préparer un squeeze (`menaces`, `phrase_squeeze`, à la table)
Rien que le déclarant, le mort, l'entame et les enchères. Le plan propose un squeeze si :
- il manque exactement une levée avec des partages normaux ;
- deux menaces dans deux couleurs hors atout : notre plus haute carte non maîtresse sous un
  seul honneur adverse, ou la dernière carte d'une couleur de quatre cartes ou plus ;
- une menace a sa rentrée (une carte maîtresse dans sa couleur) ;
- un adversaire peut garder les deux : deux menaces dans la même main exigent qu'il joue avant
  elle, et les enchères ne doivent pas désigner l'autre.
Le plan dit combien de levées céder d'abord pour n'en perdre plus qu'une. Puis 60 donnes
imaginées (`donnes_du_declarant`) : le déclarant et le mort tels quels, le reste fidèle aux
enchères et à l'entame. On joue chacune au double mort et on cherche un squeeze ; sous 5 %, le
plan n'en parle pas. La fréquence est un peu optimiste : DDS voit tout.

## Préparer une élimination (`cadre_elimination`, `phrase_elimination`, à la table)
Rien que le déclarant, le mort, l'entame et les enchères, à la couleur. Le cadre demande :
- il manque une ou deux levées avec des partages normaux ;
- une couleur clé, que la défense doit ouvrir pour nous : une impasse, une fourchette des deux
  côtés (AV2 face à RX3), ou deux honneurs avec un honneur adverse entre eux (AX2 face à V86) ;
- toutes les autres couleurs traitées : éliminées (gagnantes puis coupes) ou rendues (celles où
  nous avons une perdante) ;
- assez d'atouts pour purger, couper et garder au moins un atout : la coupe et défausse.
Ce cadre ne suffit pas. Sur 40 donnes imaginées (`donnes_du_declarant`), `coups.jouer_ligne` joue
deux fois la même ligne : atouts, couleurs à éliminer, couleurs rendues, couleur clé, dans cet
ordre ou avec la couleur clé tout de suite après les atouts. Le déclarant suit des règles, sans
regarder les mains adverses ; la défense joue au double mort ; seules les dernières cartes se
jouent au double mort des deux côtés. Le plan n'en parle que si le contrat gagne nettement plus
souvent avec l'élimination (test de McNemar). Les pourcentages sont prudents : défense parfaite,
déclarant simple. Sur 1 099 contrats à la couleur tirés au hasard, 57 cadres, 2 conseils ;
aucun sur les séances de 2026-10. Le cas est rare : rien à la table ne le prouve plus souvent.

## Cartes vues (`coups.py`, `jeu.apres_coup`)
Dernière section de chaque donne, après coup seulement : le double mort du contrat recommandé,
les impasses et les couleurs tirées en tête telles qu'elles se présentaient, et les coups.
Le programme joue quelques lignes du double mort et teste chaque position :
- Laisser-passer (la défense a mené) ou coup à blanc (nous avons mené) : le camp du déclarant
  peut prendre le pli et gagne au moins une levée à ne pas le faire.
- Mise en main : un défenseur prend la main sur un pli mené par le déclarant, et le déclarant
  ferait moins de levées s'il menait lui-même, de l'une ou l'autre main.
- Squeeze : le défenseur doit défausser, chaque défausse affranchit une levée, dans au moins
  deux couleurs, et le déclarant fait plus que ce que donnent ses couleurs jouées seules.
Non détectés : squeeze double, coupes en l'air, coups de la défense.

## Pas encore dans jeu.py
- Communications et ordre des couleurs (entrées, déblocage).
- À la table : coup à blanc et placement de main à sans-atout (seulement après coup, dans
  `coups.py`) ; squeeze double, squeeze sur l'atout.
- Impasses indirectes (vers un R ou une D seconde), impasse au V avec AR-X.
- Jeu de sécurité, choix entre deux lignes selon les probabilités.
