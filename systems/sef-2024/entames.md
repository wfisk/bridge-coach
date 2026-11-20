# SEF 2024 : entames et signalisation

Le choix de la couleur et de la carte d'entame est écrit dans `entames.yaml` (même syntaxe
de conditions que `regles.yaml`), que le programme lit (`src/entames.py`, appelé par
`jeu.entame_regle`) ; ce fichier-ci en donne les raisons. Modifier les deux ensemble. Le reste
(lecture des enchères, défense) est dans `src/jeu.py`. Les lignes **(à confirmer)**
n'ont pas été vérifiées dans le livret FFB ; les lignes **(pas encore dans le programme)**
décrivent la pratique sans que le programme l'applique.

## Lecture des enchères
- Une enchère à la couleur jusqu'à 3SA est prise pour naturelle, sauf le Stayman
  (2♣ sur 1SA, 3♣ sur 2SA), ses réponses, et les texas (2♦/2♥ sur 1SA, 3♦/3♥ sur 2SA).
  Au-dessus de 3SA (contrôles, réponses au Blackwood), les couleurs ne comptent pas.

## Choix de la couleur
1. La couleur du partenaire, s'il en a nommé une (sauf l'atout).
2. Contre un contrat à la couleur :
   - une séquence d'honneurs (AR, RD, DV, VX), même dans une couleur adverse ;
     de AR on entame l'as ;
   - sinon, au palier de 5 ou plus, une couleur menée par l'as (on entame l'as avant que le
     déclarant ne défausse), la plus longue ; sauf si l'on a une 4e meilleure sous le R ou la D
     d'une couleur de 4 cartes ou plus. Plus bas, on garde ses as : ni sous l'as, ni l'as ;
   - sinon un singleton (pas un honneur), pour couper, avec au moins deux atouts.
     Dans les séances simulées, seulement une fois sur trois.
3. Sinon la couleur la plus longue hors couleurs adverses (3 cartes au moins à la
   couleur, 4 à sans-atout) ; à longueur égale, à sans-atout une séquence, puis le plus
   d'honneurs (A=5, R=4, D=3, V=2, X=1). À la couleur, jamais sous un as.
- Contre un chelem à la couleur, encaisser un as d'abord (avant une séquence).
- Entame d'atout (passive, ou quand le mort doit couper) **(pas dans le programme)** : essayée
  quand le déclarant a nommé deux couleurs (avec ou sans soutien du mort), elle ne gagnait rien
  au double mort sur 1 700 contrats.

## Choix de la carte (SEF 2024, chapitre 11)
- Séquence : la tête (R de RD5, D de DV83) ; A de AR. À sans-atout, avec quatre cartes ou plus : le R
  de ARV (trois honneurs, le partenaire débloque) et la D de RD sans le V (la couleur n'est pas assez
  solide pour demander le déblocage).
- Singleton, doubleton : la plus haute.
- À sans-atout : honneur troisième, la carte du milieu (8 de D85) ; honneur quatrième ou plus, la
  4e meilleure ; trois petites, la plus haute ; quatre petites ou plus, la deuxième. Le 10 compte
  comme honneur avec 4 cartes ou plus (2 de X952), pas avec trois (X65 = trois petites).
- À l'atout, la petite carte donne la parité : avec un nombre impair de cartes, la plus petite
  (2 de 852, 5 de D85, 2 de R8532) ; avec quatre ou six petites, la deuxième ; avec un honneur
  quatrième, la 3e meilleure (5 de R852).
- Dans la couleur du partenaire (pair-impair) : l'as à la couleur, la plus haute du doubleton, la
  tête de séquence, la plus petite de trois cartes, la 4e meilleure avec un honneur quatrième, la
  deuxième de quatre petites.

## Pas de simulation
L'entame vient des règles seules. Une simulation au double mort ne convient pas à l'entame : elle
suppose que chacun joue ensuite cartes vues, et ne peut pas mesurer ce que vaut, à la table, une
entame dans la couleur du partenaire. Pour faire passer une autre entame avant une règle, on
ajoute une règle plus haut dans `entames.yaml`.

## Lecture des enchères pour le meneur (`lire_encheres`)
Points d'honneur (H) et longueurs minimales montrés par chaque joueur ; volontairement
large. Contrôle : les mains réelles doivent respecter la lecture (environ 98 % des mains
sur les séances essayées, y compris des donnes neuves jamais utilisées pour régler les
règles).
- Passe avant l'ouverture : 11 H au plus. Passe sur une ouverture de 1 du partenaire,
  sans intervention : 5 H au plus (pas après un barrage).
- Ouvertures : 1♣/1♦ 11–21 H, 3 cartes ; 1♥/1♠ 11–21 H, 5 cartes ; 1SA 15–17 et 2SA
  20–21 réguliers ; 2♣ fort (16 H ou plus, artificiel) ; 2♦ 20 H ou plus ; 2♥/2♠ 5–11 H,
  6 cartes ; barrage de 3 : 5–11 H, 7 cartes.
- Réponses : couleur au palier de 1 6 H et 4 cartes, au palier de 2 10 H (6 si l'on a
  passé), 2♣ possible avec 3 cartes et un jeu fort régulier **(à confirmer)** ; soutien 6 H, 3 cartes en majeure, 4 en mineure ; 1SA 6–10, 2SA 11–12, 3SA
  13–17. Sur 1SA : Stayman 8 H ou plus, texas 5 cartes dans la couleur du dessus,
  2SA 8–9, 3SA 10–15. Sur 2SA : 3SA 4–11. Sur 2♣ : 2♦ d'attente.
- Interventions : couleur 8–17 H, 5 cartes ; sur 1SA 6 cartes ; au palier de 3 ou plus
  5–16 H, 6 cartes ; 1SA 15–18 régulier ; contre d'appel 11 H, 8 en réveil ou après avoir
  passé.
- Ensuite : nouvelle couleur 4 cartes ; couleur répétée 5 cartes en majeure, 4 en
  mineure ; soutien du partenaire 3 cartes (2 s'il a répété sa couleur).
- Artificielles, sans longueur : Stayman et ses réponses (2♦ = pas de majeure), texas et
  leur acceptation (la couleur du texas compte ensuite comme montrée), 2♦ sur 2♣, 4e couleur forcing, enchère dans la couleur adverse.

## Lecture pour le meneur (`lecture_entame`)
À partir de sa main et des enchères seulement, le texte de défense ajoute :
- les points du partenaire : 40 moins les points du meneur et ceux montrés par les adversaires ;
- le style : contre un chelem, défense active ; à sans-atout, affranchir une longueur, sans ouvrir
  les couleurs adverses ; à la couleur, si le mort a montré une couleur annexe, prendre ses levées
  vite ; si le déclarant a deux couleurs et le mort soutient, rejouer atout ; sinon ne rien offrir ;

## Défense (commentaire du rapport)
- Le texte de défense donne l'entame et sa raison. Il ne
  parle jamais de la donne réelle : le meneur ne voit que sa main et les enchères.
- Après coup, dans le commentaire seulement (`apres_coup`) : le double mort du contrat
  recommandé après l'entame, les entames qui auraient fait mieux avec les cartes vues
  (« Avec les cartes vues, ♠V aurait fait mieux »), l'effet des entames des tables, et si les
  impasses du plan réussissent.

## Notre signalisation (SEF 2024 p. 83–85, développée ; l'utilisateur, 2026-11-20 ; src/signaux.py)
Le livre donne la base en une page ; nous la complétons là où il ne dit rien, chaque ajout marqué **(notre ajout)**
avec sa raison. Les signaux sont une convention du camp : ils figurent sur la feuille de conventions (Système). Les
robots signalent et lisent avec les mêmes règles : un défenseur lit son partenaire comme il aurait signalé lui-même.
Un signal ne se donne que parmi des cartes également bonnes : il ne coûte jamais de levée.

**Trois signaux** (SEF 2024 p. 83) :
- **L'appel-refus** : une grosse carte inutile demande au partenaire de continuer ; la plus petite dit non.
- **La parité** (le compte) : la plus petite avec un nombre impair de cartes ; une grosse puis une petite avec un
  nombre pair.
- **La préférence** : une grosse carte demande la plus chère des deux autres couleurs (jamais l'atout), une petite
  la moins chère.

**Quel sens a cette carte ?** La situation le dit, pas la carte (le coach l'explique dans l'Indice et dans Revoir,
carte.explication_signal) :

| La situation | Le sens de la petite carte |
|---|---|
| À sans-atout, le partenaire mène l'As ou la Dame | **Appel-refus** (livre) |
| À sans-atout, le partenaire mène le Roi | **Débloquer** un honneur (As, Dame ou Valet) ; sinon **parité** (livre) |
| À sans-atout, le partenaire mène une petite carte | **Parité** (livre) ; jouer d'abord pour la levée si on le peut |
| À la couleur, le partenaire mène l'As ou le Roi, le mort a trois petites cartes | **Appel-refus** (livre) |
| À la couleur, le partenaire mène l'As ou le Roi, le mort a un singleton | **Préférence** (livre) |
| À la couleur, le partenaire mène l'As ou le Roi, le mort a un doubleton ou un honneur | **Parité** (livre) |
| À la couleur, le partenaire mène une autre carte | **Parité** (livre) |
| Le déclarant (ou le mort) mène | **Parité** (livre) |
| Je défausse | **Parité** dans une couleur que je ne veux pas ; en urgence **appel direct** (livre) |
| Je mène une couleur que le partenaire coupe | **Préférence** pour le retour (notre ajout, éteint) |
| L'atout, ou un honneur | **Rien** |

Nos ajouts, là où le livre se tait :
- **Plus tard dans le coup (notre ajout)** : la même table vaut chaque fois que le partenaire mène une nouvelle
  couleur, pas seulement à l'entame. Raison : une seule règle à retenir.
- **Le premier signal seulement (notre ajout)** : on signale la première fois qu'on fournit dans une couleur ; la
  carte suivante suit la parité déjà donnée (grosse puis petite). Raison : un signal par couleur, lisible.
- **Grosse = 7 ou plus, petite = 6 ou moins (notre ajout)** : le partenaire ne voit pas nos autres petites cartes ;
  une frontière fixe se lit sans calcul. Avec 5-3 ou 9-8, aucune carte ne dit clairement le message : on fournit sans
  signal (la plus petite). Raison : pour les élèves, une carte ambiguë ne doit pas tromper.
- **Ce qu'on veut ne vient pas d'une règle fixe sur les honneurs** : selon la situation (longueur à sans-atout,
  doubleton pour couper, honneurs du mort placés devant les siens), le défenseur le lit dans ses donnes imaginées : si
  son partenaire avait la main, quelle couleur rapporterait le plus (carte.Partie.voeu). **« Continuez » seulement
  quand rejouer la couleur est vraiment le mieux** (carte.MARGE_CONTINUER) : quand le mort garde la couleur (son As
  sur le Roi du partenaire) ou la coupera, la petite carte dit « changez » (carte.Partie.regle_signal).
- **La défausse (notre ajout)** : on défausse dans la couleur qu'on veut le moins, et l'on y donne la parité avec ses
  petites cartes (6 ou moins, pour ne pas ressembler à un appel). L'appel direct (une grosse carte, 7 ou plus, de la
  couleur voulue) est réservé à l'urgence : une couleur qui rapporte au moins une levée de plus que les autres
  (carte.URGENCE_APPEL). Raison : le livre dit « en cas d'urgence » sans dire quand.
- **Le partenaire suit la demande** : quand il a la main, parmi ses cartes également bonnes, il joue la couleur
  demandée ; ses pensées le disent.
- **Les honneurs ne signalent pas** (ni A, R, D, V) : on ne lit que les cartes de 2 à 10.
- **À l'atout, rien** : ni appel ni parité dans la couleur d'atout (notre ajout ; le livre n'en parle pas).
- **En donnant une coupe au partenaire (notre ajout)** : la hauteur de la carte demande le retour, haute la plus chère
  des deux autres couleurs hors atout, basse la moins chère. Écrit (carte.PREF_COUPE) mais éteint : rare, et sans gain
  sur 600 donnes.

Jusqu'au 2026-11-20, les robots jouaient l'appel pair-impair (impaire = continuez) et la défausse de préférence
(Lavinthal), un choix du 2026-11-11 ; remplacés par la méthode du livre à la demande de l'utilisateur.

## Honneurs équivalents et habitudes classiques (2026-11-11 ; src/carte.py)
- **Honneurs équivalents** : en fournissant, le plus bas de cartes équivalentes (la dame de DV : elle nie le valet) ;
  en menant en cours de coup (pas à l'entame, qui suit les règles ci-dessus), le plus haut d'une séquence (le roi de
  RD ; une dame menée nie le roi). Le modèle des mains sait le lire (modele.LIRE_HONNEURS, « Ouest a
  fourni la dame ♥ : il n'a pas le valet ♥ ») mais cette lecture est éteinte : sans gain sur 600 donnes.
- **Les habitudes ne sont pas toujours justes** : second en main petit, troisième en main haut (la plus petite qui
  suffit), couvrir un honneur par un honneur (pas le premier de deux honneurs qui se suivent au mort). Le défenseur
  ne les suit que parmi les cartes que ses donnes imaginées jugent presque égales (autant de chutes, au plus 1/16 de
  levée de moins en moyenne) : quand les mondes disent autrement, les mondes gagnent.
