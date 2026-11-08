# Bridge Coach

Un entraîneur de bridge pour le club, en français, système SEF, marque IMP :

- **Analyser un tournoi** joué avec Bridgemate (le fichier `.bws`, ou la feuille de route PDF de FFBClubNet) : pour
  chaque donne, les enchères recommandées, l'entame, le plan de jeu, le double mort, et les résultats de toutes les
  tables ; puis des rapports PDF.
- **Jouer chaque donne contre le programme** : enchérir à sa place, puis jouer la carte comme déclarant ou en
  défense. Les trois autres joueurs sont des robots qui expliquent ce qu'ils pensent : pourquoi telle carte, ce
  qu'ils croient des mains cachées, leurs signaux ; à la fin, un résumé de la donne et ce que le programme aurait
  joué à votre place.
- **Créer des donnes d'entraînement** par thème (enchères ou jeu de la carte, trois niveaux), ou les taper à la
  main, avec un `.pbn` à importer dans Bridgemate pour les jouer au club.
- **L'analyse de l'expert** (facultatif) : la séance préparée pour Claude, qui rédige un avis sur chaque donne.

| Rapport | Contenu |
|---|---|
| `…-archive.pdf` | ce qui a été joué : mains, enchères et résultats des tables, double mort et par |
| `…-standard.pdf` | l'analyse du programme : enchères recommandées, entame, plan de jeu |
| `…-expert.pdf` | la même analyse, avec l'« Avis de l'expert » rédigé par Claude (seulement s'il existe) |
| `…-diff.pdf` | le programme et l'expert comparés, donne par donne |

Les rapports finissent par votre parcours dans la séance et une synthèse : une ligne par donne, le contrat
recommandé face à ce qui a été joué aux tables.

## Installer

Sur la page des versions, **https://github.com/wfisk/bridge-coach/releases/latest**, téléchargez l'installateur :

- **Windows 10 ou 11 (64 bits) :** `Bridge-Coach-Setup.exe`
- **Mac :** `Bridge-Coach.pkg`

Ouvrez-le et suivez les étapes. Comptez quelques minutes et une connexion à Internet : l'installateur ne contient
pas le programme, il télécharge sa dernière version, un Python qui lui est propre (il ne touche pas à un autre
Python de l'ordinateur) et ses bibliothèques, en vérifiant chaque fichier (voir **Sécurité**). Il faut 8 Go de
mémoire au minimum : le calcul des donnes peut occuper environ 4 Go.

- **Windows** affiche d'abord « Windows a protégé votre ordinateur » : cliquez sur **Informations
  complémentaires**, puis **Exécuter quand même** (pourquoi : voir **Sécurité**). Pas besoin de droits
  d'administrateur. Bridge Coach arrive sur le Bureau et dans le menu Démarrer ; pour l'épingler à la barre des
  tâches : menu Démarrer, clic droit sur **Bridge Coach**, **Plus**, **Épingler à la barre des tâches**.
- **Mac** refuse d'abord de l'ouvrir : **Réglages Système**, **Confidentialité et sécurité**, en bas **Ouvrir quand
  même**. Bridge Coach arrive dans Applications, avec un lien sur le Bureau. Au premier lancement, macOS demande
  l'accès au dossier Documents : **OK** (vos séances et rapports y sont).

Au premier lancement, onglet **Réglages**, page **Dossiers** : indiquez le dossier où Bridgemate enregistre ses
`.bws` (à vérifier dans Bridgemate Control Software), puis fermez et rouvrez Bridge Coach.

## Mettre à jour

Onglet **Réglages**, page **Mise à jour du programme**, **Rechercher une mise à jour**. S'il y en a une, **Mettre à
jour vers …** : Bridge Coach se ferme, télécharge la version nouvelle, vérifie son empreinte, la met en place et se
rouvre, en une minute environ. Les bibliothèques ne sont réinstallées que si la version nouvelle en demande
d'autres. Si quelque chose se passe mal, l'ancienne version est remise en place ; le compte rendu est dans
`bridge-coach-files/rapports/derniere-mise-a-jour.txt`.

Vos séances, rapports, analyses de l'expert et réglages ne changent pas. Seules les versions publiées sont
proposées (1.1.0, 1.2.0…), jamais le travail en cours. Inutile de retélécharger l'installateur.

## Sécurité

**Ce qui reste chez vous.** Vos séances, les noms des joueurs et vos rapports ne quittent jamais l'ordinateur :
Bridge Coach n'envoie rien sur Internet. L'application est une petite page web servie par l'ordinateur lui-même
(adresse 127.0.0.1) : un autre appareil du réseau, même au club, ne peut pas l'ouvrir. Pour l'analyse de l'expert,
c'est vous qui envoyez un fichier à Claude, et il ne contient que les donnes, les enchères, les résultats et les
initiales des joueurs : ni noms complets, ni club, ni le fichier d'origine de Bridgemate.

**Quand Bridge Coach se connecte.** Seulement pendant l'installation, et quand vous cliquez sur **Rechercher une
mise à jour** : il lit alors la page des versions sur GitHub, sans rien envoyer.

**Où télécharger.** Seulement sur la page des versions ci-dessus : jamais une pièce jointe d'e-mail, une clé USB
qui circule ou un autre site. Le code est public : chacun peut lire ce qu'il fait.

**Ce qui est vérifié.** Chaque fichier téléchargé est comparé à son empreinte SHA-256 (une sorte d'empreinte
digitale : un seul octet changé la change entièrement) ; un fichier qui ne correspond pas est refusé avant
d'être utilisé, et rien n'est installé :

| Téléchargé | Vérifié contre |
|---|---|
| le programme (`bridge-coach-1.1.0.zip`), à l'installation et à chaque mise à jour | le fichier `SHA256SUMS` publié avec la version |
| Python (version complète de python-build-standalone) | l'empreinte écrite dans le programme vérifié (`installer/python.txt`) |
| les bibliothèques (depuis PyPI, leur site officiel) | les empreintes de `requirements.txt`, pour chaque bibliothèque et celles qu'elles appellent |

Les versions de Python et des bibliothèques sont fixées : tout le monde reçoit celles qui ont été essayées. Une
version nouvelle, abîmée ou piratée n'arrive donc pas toute seule ; changer de version est une décision, essayée
avant d'être publiée.

**D'où viennent les installateurs.** Ils sont faits par GitHub Actions, à partir du code public, sur des machines de
GitHub, puis essayés par une installation complète sur Windows et sur Mac avant d'être publiés. Personne ne les
fabrique sur son ordinateur. Pour le vérifier soi-même (facultatif) :

- l'empreinte : `Get-FileHash Bridge-Coach-Setup.exe` dans PowerShell, `shasum -a 256 Bridge-Coach.pkg` dans le
  Terminal du Mac, à comparer avec la page de la version ;
- la provenance : `gh attestation verify Bridge-Coach.pkg --repo wfisk/bridge-coach` (l'outil `gh` de GitHub)
  confirme que le fichier a été fait par GitHub Actions à partir de ce dépôt.

L'empreinte de la page protège d'un téléchargement abîmé ou d'une copie venue d'ailleurs ; la provenance va plus
loin : signée par GitHub au moment de la fabrication, elle relie le fichier à ce dépôt et à la version exacte du
code.

**Pourquoi Windows et le Mac avertissent.** Les installateurs ne sont pas signés : la signature demande un
certificat payant (Windows) ou un compte de développeur Apple, qui ne se justifient pas pour un club. L'avertissement
dit seulement « éditeur inconnu », pas « programme dangereux ». L'antivirus peut beaucoup travailler pendant la
première analyse : c'est normal.

**Un doute, un problème ?** Ne lancez pas le fichier, et prévenez la personne qui s'occupe du programme.

## Désinstaller

- **Windows :** **Paramètres**, **Applications**, **Applications installées**, **Bridge Coach**, **Désinstaller**.
  Le programme, son Python et ses raccourcis partent.
- **Mac :** mettez à la corbeille **Bridge Coach** dans Applications, son lien sur le Bureau, et le dossier
  `~/Library/Application Support/Bridge Coach` (le programme, son Python et vos réglages).

Vos fichiers restent : `bridge-coach-files` dans vos Documents (séances, rapports, analyses de l'expert), et sous
Windows vos réglages (`%APPDATA%\Bridge Coach`). Supprimez-les vous-même si vous le voulez ; les analyses de
l'expert ne se recréent pas.

## Où sont les fichiers

| Quoi | Mac | Windows |
|---|---|---|
| Vos séances et rapports : **le dossier à sauvegarder** | `~/Documents/bridge-coach-files` | `Documents\bridge-coach-files` |
| Les fichiers de Bridgemate (lus, jamais modifiés) | le dossier des réglages | le dossier des réglages |
| Les réglages (`bridge-coach.ini`, `etat.json`) | `~/Library/Application Support/Bridge Coach` | `%APPDATA%\Bridge Coach` |
| Le programme et son Python | `~/Library/Application Support/Bridge Coach/programme` | `%LOCALAPPDATA%\Programs\Bridge Coach` |

Dans `bridge-coach-files` : `seances/AAAA-MM/` (chaque séance, `<séance>.bc.json`, avec une copie de l'original et
ses analyses ; `versions/` garde les états précédents), `rapports/AAAA-MM/` (les PDF), `documents/`. Les séances
(`.bc.json`) sont le plus précieux : elles contiennent l'analyse de l'expert, que le programme ne peut pas recréer.

## L'application

- **Fichier :** ouvrir une séance, importer un `.bws` ou une feuille de route, **Nouveau…** (une séance vide à
  remplir, ou des donnes d'entraînement par thème), exporter en PBN.
- **Donnes :** la séance, les joueurs, puis chaque donne : mains, enchères des tables, résultats ; modifier les
  donnes d'une séance d'entraînement.
- **Jouer :** enchérir à une place choisie (déclarant, défense, donneur…), le programme tenant les trois autres,
  puis jouer la carte ; l'**Indice** donne l'enchère ou la carte du système. Les pensées des robots sont dans la
  barre de droite, et **Revoir la donne avec les pensées** la rejoue carte par carte.
- **Analyse :** l'analyse du programme, et les étapes pour obtenir celle de l'expert ; chaque donne présentée
  comme dans le PDF.
- **Rapports :** les options (qui vous êtes, ordre joué, page des noms), **Créer les rapports**, puis les PDF.
- **Réglages :** les dossiers, la mise à jour.
- **Aide :** le mode d'emploi, en cinq parties.

Bridge Coach se rouvre sur la séance et la page où vous étiez, et sur une donne en cours de jeu.

## L'analyse de l'expert (facultatif)

Onglet **Analyse**, **Analyse expert** : Bridge Coach prépare un seul fichier,
`pour-claude/<séance>/…-pour-claude.json` dans votre dossier de travail (les consignes, la séance avec les
initiales seulement, l'analyse du programme, un exemple et les documents du système). Donnez-le à Claude sur
claude.ai ; il renvoie `…-expert.json`, que **Importer** vérifie avant de l'ajouter à la séance. Les enchères de
l'expert sont choisies à la table, sans regarder les autres mains ni le double mort ; les décisions serrées sont
signalées.

---

## Pour qui travaille sur le programme

### Installer depuis le code

Il faut Python 3.9 à 3.13 (le solveur de donnes, endplay, n'existe pas pour 3.14).

```
git clone https://github.com/wfisk/bridge-coach.git
cd bridge-coach
./installer.sh          # Mac ou Linux : .venv, bibliothèques, vérification des règles, application Bridge Coach
./bridge-coach.sh       # ouvre l'application
```

Sous Windows : `installer.bat` (il cherche Python 3.12, sinon propose `winget`), puis `bridge-coach.bat`
(`--navigateur` si la fenêtre ne s'ouvre pas : il manque alors le composant WebView2 de Microsoft). Une copie faite
avec `git clone` se met à jour par `git pull`, pas par le bouton des Réglages. Sur Mac, `./raccourci-mac.sh` refait
l'application dans Applications si le dossier change de place (`--dock` l'ajoute au Dock).

### En ligne de commande

```
./rapport.sh                          choisir parmi les .bws du dossier de Bridgemate (Entrée : le dernier)
./rapport.sh séance.bws               un fichier précis
./rapport.sh séance.bc.json           refaire les rapports d'une séance déjà importée
./rapport.sh séance.bws --avec-noms   avec une page du nom des joueurs
```

Une feuille de route PDF de FFBClubNet est acceptée aussi : elle donne les mains, les contrats, les entames et les
résultats, pas les enchères ; le double mort est calculé. Les sauvegardes FFBClubNet nommées `.bws` sont des
archives protégées par un mot de passe : il faut le vrai `.bws` de Bridgemate.

### Le système d'enchères

Les enchères, les entames et le jeu de la carte sont décrits dans `systems/` :

- `systems/sef-2024/regles.yaml` : les règles d'enchères que lit le programme (en français, couleurs T K C P,
  alertes comprises) ; la grammaire est dans `systems/grammaire.md` ;
- `systems/sef-2024/entames.yaml` : le choix de l'entame ; les signaux sont dans `entames.md` ;
- `systems/sef-2024/systeme.md`, `systems/technique/jeu-de-la-carte.md` : les explications.

Ces fichiers se modifient à la main ; leurs exemples sont vérifiés à chaque lecture, et une erreur est signalée
avec son numéro de ligne. Une règle n'est gardée que si elle gagne sur des donnes tirées au hasard, pas seulement
sur les séances du club.

### Publier une version

Le travail se fait sur `main` ; une version est une étiquette, numérotée X.Y.Z (1.1.0 : nouveautés ; 1.1.1 :
corrections).

```
./publier.sh 1.2.0 "Ce qui change, en une phrase"
```

Le script vérifie les tests, écrit `VERSION`, crée l'étiquette `v1.2.0` et l'envoie sur GitHub. GitHub Actions
(`.github/workflows/installateurs.yml`) fait alors l'archive du programme et les deux installateurs, les essaie par
une installation complète sur Windows et sur Mac, puis crée la version sur la page des versions avec `SHA256SUMS`
et l'attestation de provenance (environ dix minutes). Les mêmes essais tournent, sans rien publier, à chaque envoi
sur `main` qui touche `installer/` ou `requirements.txt`.

- **Les installateurs ne sont jamais dans le dépôt** : `.gitignore` écarte `dist/`, `*.exe`, `*.pkg`, `*.dmg`. Leurs
  sources sont dans `installer/` ; ils n'ont pas à être refaits pour une nouvelle version du programme.
- **Les bibliothèques :** la liste écrite à la main est `requirements.in` ; `requirements.txt` en est produit, avec
  les empreintes (la commande est en tête du fichier). **Python :** `installer/python.txt`.
- **Jamais dans le dépôt, qui est public :** les `.bws`, les séances, les rapports, `bridge-coach.ini`, ni aucun nom
  de joueur ou de club.
- **Le compte GitHub du responsable** doit avoir la double authentification : il protège tous ceux qui téléchargent.
