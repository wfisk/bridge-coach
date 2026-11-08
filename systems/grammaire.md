# Grammaire des règles d'enchères

Référence du format de `systems/<système>/regles.yaml`, le fichier que le programme
lit (`src/regles.py`) pour choisir une enchère. Le fichier est en français ; les
accents sont facultatifs dans les conditions et les mots-clés.

Vérifier un fichier après l'avoir modifié :

    .venv/bin/python -I src/regles.py

Le programme lit le fichier, vérifie tous les exemples et signale chaque erreur en
français avec son numéro de ligne.

## 1. Les lettres

| Lettres | Sens |
|---|---|
| T K C P | les couleurs : trèfle, carreau, cœur, pique ; SA sans-atout |
| A R D V X | les honneurs : as, roi, dame, valet, dix |
| H, HL, HLD | les points (voir 3) |
| M, N | la plus longue majeure, la plus longue mineure de ma main |
| U, W | la couleur de l'ouvreur, la couleur du répondant |
| Y, Z | la couleur de l'intervenant, la couleur de son partenaire |
| UM, UN, WM, YM… | la majeure, la mineure nommée par ce joueur |
| S1 à S4 | le siège : rang dans le tour d'enchères, depuis le donneur |

Les joueurs se lisent depuis l'ouvreur, dans l'ordre des enchères : U l'ouvreur,
Y l'intervenant à sa gauche, W le répondant, Z le partenaire de l'intervenant
(en réveil après 1x – passe – passe). U et W sont partenaires, Y et Z aussi.

Les sièges N, E, S, O n'apparaissent pas dans les règles : une règle vaut quel que
soit le siège de l'ouvreur. Le donneur change à chaque donne (donne 1 Nord, 2 Est,
3 Sud, 4 Ouest…) ; S1 est toujours le donneur.

Lettres libres pour la suite : B E F G J Q. I et O sont évitées (confusion avec 1 et 0).

## 2. Les enchères

Une enchère s'écrit comme dans les rapports, avec les lettres : `1K`, `2SA`, `passe`,
`contre`. Elle peut nommer la couleur d'un joueur :

- `2U` deux dans la couleur de l'ouvreur (soutien) ; `3U` trois ;
- `2UM` deux dans la majeure de l'ouvreur ; `2Y` cue-bid de la couleur adverse ;
- `*P` le palier le plus bas à pique après la dernière enchère ; `*P+1` avec un saut ;
  `*U` le soutien le plus bas, quel que soit le palier de l'intervention. Une enchère
  relative au-delà de 7 est simplement sautée.

## 3. Les conditions

Une condition est un **contexte** suivi d'une **zone** : `P 5+`, `H 12-14`.

### Contextes

| Contexte | Mesure |
|---|---|
| `T`, `K`, `C`, `P` | la longueur de la couleur |
| `CP`, `TKCP` | chacune des couleurs citées |
| `M`, `N` | la plus longue majeure, la plus longue mineure |
| `U`, `W`, `Y`, `Z`, `UM`… | la longueur dans la couleur de ce joueur |
| `M+N`, `P+C` | la somme des longueurs |
| `H` | points d'honneur : A 4, R 3, D 2, V 1 |
| `H(K)`, `H(U)` | les points d'honneur de cette couleur seule : `U 4+, H(U) 5+` (AR, AD ou RD à la couleur de l'ouvreur) |
| `HL` | H + 1 point par carte au-delà de la 5e |
| `HLD` | points pour soutenir une couleur (voir ci-dessous) ; l'atout est la couleur de l'enchère, sinon il s'écrit `HLD(P)` ou `HLD(U)` |
| `S` | le siège (1 à 4) |

### HLD : les points pour soutenir

HLD sert à évaluer un soutien, la main qui sera le mort :

- H, les points d'honneur ;
- \+ les courtes hors atout : chicane 3, singleton 2, doubleton 1 ;
- \+ 1 par atout au-delà du 3e, **seulement avec un singleton ou une chicane** : le mort
  ne gagne des levées qu'en coupant. Une main 4-3-3-3, ou avec un simple doubleton, ne
  compte pas ses atouts en plus.

Exemples pour soutenir pique :

| Main | H | Courtes | Atouts en plus | HLD |
|---|---|---|---|---|
| RX9832 X9 A632 9 | 7 | 3 | 3 | 13 |
| R8632 D74 A632 5 | 9 | 2 | 2 | 13 |
| R832 D7 A632 V52 | 10 | 1 | 0 | 11 |
| R832 D74 A63 V52 | 10 | 0 | 0 | 10 |

C'est moins généreux que les points de distribution souvent enseignés en France et
proche du principe américain : la distribution ne compte que si elle promet des coupes
au mort. Le moteur actuel (`sef2024.py`) compte H + courtes, sans les atouts en plus.

### Zones

| Zone | Sens |
|---|---|
| `5+` | au moins 5 |
| `1-` | au plus 1 (comme `0-1`) |
| `6-10` | de 6 à 10 |
| `1` ou `1=` | exactement 1 |
| `!` devant la zone | le contraire, pour chaque couleur citée |

Chicane, singleton et doubleton s'écrivent avec les longueurs : `K 0`, `K 1`, `K 2`,
`K 1-` (singleton ou chicane).

Une seule zone par condition : pour deux zones, deux conditions (`TKCP !1-, TKCP !6+`).

### Autres conditions

| Écriture | Sens |
|---|---|
| `P >= C` | au moins autant de piques que de cœurs (aussi `>`, `=`, `<`, `<=`) ; `K > M` |
| `reg` / `irreg` | répartition régulière (4-3-3-3, 4-4-3-2, 5-3-3-2) ou non |
| `forme 5-4-2-2` | cette répartition, dans n'importe quel ordre |
| `levees 10+` | levées de jeu : par couleur, la longueur moins les A, R, D absents parmi les trois premières cartes |
| `regle des 20` | H + les deux plus longues couleurs >= 20 |
| `regle des 15` | H + nombre de piques >= 15 |
| `arret U` | un arrêt dans cette couleur : A, Rx, Dxx ou Vxxx |
| `bonne P` | 5 cartes avec deux honneurs parmi A R D V X, ou 6 cartes |
| `palier(U) 2-` | le palier le plus bas dans cette couleur, dans cette séquence, est 2 au plus |
| `fit(C) 9+` | mes cœurs + ceux que le partenaire a montrés (son minimum) : 9 ou plus ; `fit(Y) 8+` avec la couleur d'un joueur |
| `camp H 25+` | mes points + le minimum montré par le partenaire (aussi `camp HL`, `camp HLD(P)`) |
| `NN` `NV` `VN` `VV` | la vulnérabilité, nous puis eux (N : non vulnérable, V : vulnérable) : `NN` personne, `NV` favorable, `VN` défavorable, `VV` tous ; `(NN \|\| NV)` pour plusieurs. Aucune confusion avec N (la plus longue mineure), toujours suivie d'une zone |
| `vul nous` / `vul eux` | un seul camp compte : `vul nous` vaut `VN \|\| VV` (`non vul eux` : ils ne le sont pas) |
| `Y est C` | la couleur de l'intervenant est cœur (avec `non` : ce n'est pas cœur) |
| `non …` | le contraire d'une condition ou d'une parenthèse |
| un nom de `definitions` | sa condition, comme entre parenthèses ; une définition peut employer U W Y Z (elle est recalculée pour chaque séquence, et fausse là où elle n'a pas de sens) |

### Combiner

- La virgule veut dire **et** : `H 12+, P 5+`.
- `||` (ou `ou`) veut dire **ou** : `C 9+ || P 9+`.
- Les parenthèses groupent : `H 20+, (C 9+ || P 9+)`.
- Sans parenthèses, la virgule lie plus fort : `reg, H 15-17 || HL 25+` se lit
  `(reg, H 15-17) || HL 25+`.

### Exemples

| Condition | Sens |
|---|---|
| `P 5+, P >= C` | 5 piques au moins, pas plus de cœurs que de piques |
| `K 1-` | singleton ou chicane à carreau (splinter) |
| `TKCP !1-` | ni singleton ni chicane |
| `(T 1- \|\| K 1- \|\| C 1- \|\| P 1-)` | un singleton ou une chicane quelque part (`TKCP 1-` voudrait dire : partout) |
| `TKCP !1-, TKCP !6+` | de 2 à 5 cartes partout (accepte 5-4-2-2, contrairement à `reg`) |
| `M+N 9+, M 4+, N 4+` | bicolore majeure-mineure de 9 cartes |
| `U 3+, HLD 6-10` | soutien de l'ouvreur, 6 à 10 points |
| `H 20+, (C 9+ \|\| P 9+)` | 20 H et 9 cœurs ou 9 piques |
| `S 4, regle des 15` | en 4e position, avec la règle des 15 |
| `H 8-10 \|\| H 6-10, non VN` | barrage : 8 H en défavorable, 6 sinon |

## 4. Le fichier

```yaml
systeme: sef-2024

definitions:                     # conditions nommées, réutilisables
  ouvrable: "H 12+ || H 11, S 1-2, regle des 20 || H 11, S 3 || H 10-11, S 4, (regle des 15 || P 6+ || C 6+ || K 6+ || T 6+)"

ouverture:                       # les ouvertures
  - 1SA: { si: "reg, H 15-17, M 4-", montre: "15–17 H, régulier" }
  - 1P:  { si: "ouvrable, P 5+, P >= C", montre: "12–21 H, 5+ piques" }
  - passe: { montre: "pas d'ouverture" }
  - exemples:
      - { main: "AR5 D84 RV7 A962", position: 1, attendu: 1SA }

"1M":                            # réponses à 1♥ et à 1♠ (adversaires silencieux)
  - 2U:  { si: "U 3+, HLD 6-10", montre: "soutien simple" }
  - 2C:  { si: "C 5+", montre: "5+ cœurs, forcing", apres: 1P }
  - exemples:
      - { main: "R82 D75 RV73 X52", apres: 1C, attendu: 2U }
```

- **Séquence** : la clé donne les enchères depuis l'ouverture, séparées par des tirets
  ou des espaces. Les enchères adverses sont **entre parenthèses** et leurs passes sont
  sous-entendues ; nos passes s'écrivent, car elles changent le tour :

  | Clé | Situation |
  |---|---|
  | `"1K - 1C"` | 1♦ – 1♥, adversaires silencieux : redemande de l'ouvreur |
  | `"(1K)"` | ils ouvrent 1♦ : notre intervention |
  | `"(1K) passe"` | 1♦ – passe – passe : en réveil |
  | `"1K (1P)"` | partenaire ouvre 1♦, ils interviennent à 1♠ : notre réponse |
  | `"(1K) 1P (2K)"` | partenaire intervient à 1♠, ils soutiennent : nous avançons |

  Plusieurs clés pour une même liste : `"1M (2x) | 1M (3x)"`. Une clé générique ne
  produit que des enchères possibles : `"(1x) 1x"` donne `(1T) 1C`, pas `(1P) 1T`.
  `ouverture` pour les ouvertures. `M`, `N` ou `x` dans une clé la rend générique :
  `"1M"` vaut pour `1C` et `1P`, `"1N"` pour `1T` et `1K`, `"(1x)"` pour les quatre
  couleurs. Les rôles suivent les enchères : U est toujours l'ouvreur, même adverse ;
  quand ils ouvrent, nous sommes Y (l'intervenant) et Z (son partenaire).
- **Règles** : une par ligne, dans l'ordre de priorité ; on prend la première dont la
  condition est vraie. Sans `si`, la règle s'applique toujours (en fin de liste).
  Une enchère impossible dans la séquence (1P après 1P) est sautée.
- **Clés d'une règle** :
  - `si` la condition ;
  - `montre` ce que l'enchère montre, en français (repris dans les rapports) ;
  - `source` : SEF par défaut, `à confirmer` (pas vérifié dans le livret FFB), ou
    `SA` (emprunté au Standard American, faute de détail SEF) ;
  - `apres: 1P` réserve la règle à une séquence d'une clé générique ;
  - `nature` : `forcing`, `invite`, `conclusion`, `relais` (Stayman, texas), `barrage`…
  - `alerte` : `oui` pour une enchère que le partenaire alerte (4e couleur forcing, Spoutnik, Drury, 2SA bicolore… ;
    la liste est en tête de `regles.yaml`). L'onglet Jouer propose alors le bouton Alerte.
    Le moteur s'en sert pour la suite des enchères (par exemple, l'ouvreur de SA
    accepte ou refuse une invitation) ;
  - `note`, `nom`, `voir` : commentaires, nom d'une convention, renvoi vers
    `../conventions/…`.
- **Exemples** : en fin de liste, `- exemples:` puis une main par ligne (piques,
  cœurs, carreaux, trèfles), l'enchère attendue, et au besoin `position` (le siège)
  ou `apres` (une séquence d'une clé générique), `vul` (`NN`, `NV`, `VN` ou `VV`), `partenaire` (ce qu'il a montré : `"H 12, C 5"`). Ils sont vérifiés à chaque lecture :
  chaque fois qu'une donne réelle montre une règle en défaut, on ajoute sa main.

## 5. Le moteur et le fichier

Le moteur d'enchères (`src/encheres/`) consulte d'abord ce fichier : pour l'ouverture,
puis tant que les adversaires passent, il cherche la séquence de notre camp (`"1K - 1SA"`)
et prend la première règle vraie. Si la séquence n'est pas décrite, ou si aucune règle ne
convient, il garde son propre code Python. Chaque section ajoutée remplace donc une
partie du code, et les rapports en profitent tout de suite.

Ce qu'une règle montre (points, longueurs, main régulière) sert au moteur pour placer le
contrat ensuite. Écrire dans la condition ce que l'enchère montre vraiment, même quand
l'ordre des règles le rend évident :

- le minimum **et le maximum** de points d'une enchère limitée : `HL 11-15` et non
  `H 11+` pour une couleur répétée, sinon le partenaire ne sait pas s'il doit accepter une
  invitation ;
- la longueur promise : `T 6+` pour 1♣ – 1♦ – 2♣ (avec 5 trèfles l'ouvreur aurait dit
  autre chose), pour que le partenaire voie le fit ;
- une dernière règle sans ces précisions peut rattraper les mains rares (`H 11-17`).

Sans maximum (`H 12+`), la zone est ouverte : le moteur compte alors les points des
deux mains ensemble.

## 6. Erreurs

Toute erreur arrête la lecture avec un message en français et son numéro de ligne :

    ligne 39 : condition « C cinq+ » non comprise
    ligne 12 : « TKCP !1- !6+ » : une seule zone par condition ; écrire par exemple « TKCP !1-, TKCP !6+ »
    ligne 82 : « HLD 5- » : préciser l'atout, par exemple HLD(P)
    ligne 8 : « H 20+, (C 9+ || P 9+ » : parenthèse non fermée
    ligne 36 : clé inconnue « sii »

Les tabulations en début de ligne sont acceptées (remplacées par des espaces).

## 7. Entames (entames.yaml)

Même syntaxe (virgule, `||`, `non`, parenthèses), mais chaque condition porte sur une couleur
candidate du meneur : `partenaire`, `adverse` (nommée par le partenaire, par un adversaire),
`sequence`, `honneur`, `tete AR`, `longueur 4+`, `atouts 2+`. Les règles de `couleur` choisissent
la couleur, puis une liste de `carte` la carte (`tete`, `haute`, `basse`, `4e`, `2e`, `A`).
Le détail des clés est en tête de `sef-2024/entames.yaml`.

## 8. Pas encore dans la grammaire

- Honneurs précis : `C tete AR` ; as, clés et contrôles (`as 2+`, `cles 3`). La lettre
  A seule ne désigne jamais un as dans une condition.
