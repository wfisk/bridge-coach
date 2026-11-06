# Bridge Coach

Analyse des donnes d'un tournoi de bridge à partir du fichier `.bws` de Bridgemate :
rapports PDF en français, système SEF, marque IMP.

Pour chaque séance, le programme produit, dans `rapports/AAAA-MM/` :

| Rapport | Contenu |
|---|---|
| `…-archive.pdf` | ce qui a été joué : mains, enchères et résultats des tables, double mort et par |
| `…-standard.pdf` | l'analyse du programme : enchères recommandées, entame, plan de jeu |
| `…-expert.pdf` | la même analyse, avec l'« Avis de l'expert » rédigé par Claude (seulement s'il existe, voir plus bas) |
| `…-diff.pdf` | le programme et l'expert comparés, donne par donne |

Les rapports `standard` et `expert` commencent par une page de synthèse : contrat et entame
recommandés face à ce qui a été joué aux tables.

## Installation sur Mac

Il faut Python 3.9 ou plus récent (`python3 --version` pour vérifier).

1. Téléchargez le programme, par exemple dans vos Documents. Le dépôt est public : aucun compte GitHub n'est nécessaire.

   ```
   cd ~/Documents
   git clone https://github.com/wfisk/bridge-coach.git
   cd bridge-coach
   ```

2. Installez-le :

   ```
   ./installer.sh
   ```

   `installer.sh` crée un environnement Python dans `.venv/`, installe les bibliothèques
   (`requirements.txt`) et vérifie que les règles se lisent.

3. À la fin, `installer.sh` propose de créer l'application (réponse **O**, ou Entrée) : **Bridge Coach**
   apparaît dans le dossier Applications, avec un lien sur le Bureau. Il demande ensuite s'il faut aussi
   l'ajouter au **Dock** (réponse **o**). Plus tard, ou si le dossier du programme change de place :

   ```
   ./raccourci-mac.sh          (l'application et le Bureau, puis la question du Dock)
   ./raccourci-mac.sh --dock   (le Dock sans question)
   ```

   Au premier lancement, macOS peut demander l'accès au dossier Documents : cliquez sur OK.

### Où sont les fichiers sur Mac

| Quoi | Où |
|---|---|
| Le programme | `~/Documents/bridge-coach` : il va sur GitHub |
| Dossier de travail : vos séances et rapports | `~/Documents/bridge-coach-files` : `seances/`, `rapports/`, `documents/` |
| Les fichiers de Bridgemate | `~/Documents/bridgemate-files`, ou le dossier indiqué dans les réglages |
| Les réglages | `~/Library/Application Support/Bridge Coach/bridge-coach.ini` |

Vos fichiers ne vont jamais sur GitHub. Pour les sauvegarder, copiez `bridge-coach-files` : c'est le seul
dossier à garder, en particulier les fichiers `-expert.json`, que le programme ne peut pas recréer. Si le
dossier du programme change de place, relancez `./raccourci-mac.sh`.

## Installation sur Windows 10 ou 11

**Pas encore essayée sur un vrai PC Windows :** ces étapes sont écrites à partir du code. Il faut un PC
64 bits, et 8 Go de mémoire au minimum : le calcul peut occuper environ 4 Go en plus de Windows et de Bridgemate.

1. Python 3.12 : le solveur de donnes (endplay) existe pour Python 3.9 à 3.13, pas encore pour 3.14.
   `installer.bat` cherche lui-même une version qui convient, même si une autre, comme 3.14, est déjà
   installée : les deux vivent côte à côte. S'il n'en trouve pas, il propose d'installer Python 3.12 avec
   `winget` (réponse **O**). Sinon, installez-le depuis [python.org](https://www.python.org/downloads/windows/),
   version « Windows installer (64-bit) ».
2. Téléchargez le programme : sur la page GitHub du dépôt, **Code**, **Download ZIP**. Décompressez-le
   dans `Documents`, et renommez le dossier `bridge-coach`. Un dossier synchronisé par OneDrive peut gêner : si
   c'est le cas, placez-le directement dans `C:\bridge-coach`.
3. Double-cliquez sur `installer.bat` : il crée `.venv` et installe les bibliothèques, en quelques minutes.
   Windows peut d'abord afficher un avertissement : **Informations complémentaires**, puis **Exécuter quand même**.
   À la fin, il crée le raccourci **Bridge Coach** sur le Bureau, avec son icône.
4. Il propose aussi de l'ajouter au menu Démarrer (réponse **O**), pour l'épingler à la **barre des tâches** :
   Windows ne laisse pas un programme s'y épingler seul, il faut un clic. Menu Démarrer, **Toutes les
   applications**, clic droit sur **Bridge Coach**, **Plus**, **Épingler à la barre des tâches**.
5. Double-cliquez sur **Bridge Coach** sur le Bureau. Une fenêtre noire s'ouvre, réduite dans la barre des
   tâches : c'est le programme qui tourne, ne la fermez pas.
6. Dans l'onglet **Réglages**, cliquez sur **Modifier les réglages**, indiquez le dossier où Bridgemate
   enregistre ses fichiers, enregistrez, puis fermez et rouvrez l'application :

   ```ini
   bridgemate = C:\Bridgemate
   ```

   Ce chemin est un exemple : vérifiez le vrai dossier dans Bridgemate Control Software.

### Où sont les fichiers sur Windows

| Quoi | Où |
|---|---|
| Dossier de travail : vos séances et rapports | `Documents\bridge-coach-files` |
| Les réglages | `%APPDATA%\Bridge Coach\bridge-coach.ini` |

### Si quelque chose ne marche pas sous Windows

- **`python` n'est pas reconnu :** relancez l'installation de Python en cochant **Add python.exe to PATH**.
- **Python 3.14 seulement :** relancez `installer.bat` et acceptez l'installation de Python 3.12 ; un `.venv`
  créé avec 3.14 est supprimé et refait avec 3.12.
- **La fenêtre ne s'ouvre pas :** lancez `bridge-coach.bat --navigateur` depuis l'invite de commandes.
  L'application s'ouvre alors dans le navigateur. La fenêtre a besoin du composant Microsoft WebView2,
  présent sur Windows 11, et parfois absent de Windows 10.
- **Le rapport est très long :** branchez le chargeur et choisissez le mode d'alimentation **Meilleures
  performances**. Chaque analyse écrit `derniere-analyse.txt` dans `Documents\bridge-coach-files\rapports` : le temps
  de chaque donne, le nombre de cœurs, la mémoire et le nombre de processus du solveur. Envoyez ce fichier pour
  savoir ce qui ralentit.

## Mettre à jour

Une mise à jour ne remplace que le dossier du programme. Vos tournois, rapports et analyses expertes
(`bridge-coach-files`) et vos réglages restent où ils sont, sans changement.

**Windows**

1. Fermez Bridge Coach (et sa fenêtre noire).
2. Renommez le dossier du programme `bridge-coach` en `bridge-coach-ancien`.
3. Téléchargez la nouvelle version : sur la page GitHub du dépôt, **Code**, **Download ZIP**. Décompressez-la au
   même endroit et renommez le dossier `bridge-coach`.
4. Double-cliquez sur `installer.bat` : il refait `.venv` et les bibliothèques, en quelques minutes.
5. Ouvrez Bridge Coach. Le raccourci du Bureau marche toujours, puisque le dossier a gardé son nom et sa place.
6. Si tout va bien, supprimez `bridge-coach-ancien`. Sinon, supprimez le nouveau dossier et rendez à
   l'ancien son nom : vous retrouvez la version d'avant.

**Mac** (programme installé avec `git clone`)

1. Fermez Bridge Coach.
2. Dans le Terminal :

   ```
   cd ~/Documents/bridge-coach
   git pull
   ./installer.sh
   ```

   `installer.sh` garde `.venv`, ajoute les bibliothèques nouvelles s'il y en a et vérifie que les règles se lisent.
3. Ouvrez Bridge Coach. Si le dossier du programme a changé de place, relancez `./raccourci-mac.sh`.

Le dépôt est public : n'importe qui peut télécharger une nouvelle version, sans compte GitHub.

## Désinstaller

Bridge Coach ne s'inscrit pas dans le système : on le désinstalle en supprimant ses dossiers.

**Windows**

1. Le dossier du programme, `bridge-coach` (dans `Documents` ou `C:\bridge-coach`) : le programme et ses
   bibliothèques, environ 220 Mo.
2. Les réglages : le dossier `%APPDATA%\Bridge Coach` (à taper dans la barre d'adresse de l'Explorateur).
3. Le raccourci du Bureau et, s'il existe, celui du menu Démarrer (`%APPDATA%\Microsoft\Windows\Start Menu\Programs`) ;
   une icône épinglée : clic droit, **Détacher de la barre des tâches**.
4. Facultatif, vos fichiers : `Documents\bridge-coach-files` (tournois, donnes, rapports, analyses expertes).
   Les analyses expertes ne se recréent pas : gardez une copie si vous en avez besoin.
5. Facultatif, Python 3.12, si rien d'autre ne s'en sert : **Paramètres**, **Applications**, **Applications
   installées**. Ne touchez pas à une autre version, comme 3.14.
6. Facultatif, le cache des téléchargements : `%LOCALAPPDATA%\pip\Cache`, quelques dizaines de Mo.

**Mac**

1. `Bridge Coach` dans Applications, son alias sur le Bureau et, s'il y est, son icône du Dock (la glisser hors du Dock).
2. Le dossier du programme, `bridge-coach`.
3. Les réglages : `~/Library/Application Support/Bridge Coach`.
4. Facultatif, vos fichiers : `~/Documents/bridge-coach-files`, avec la même prudence.

## Sécurité

- **Téléchargez Bridge Coach seulement sur sa page GitHub,** https://github.com/wfisk/bridge-coach : jamais une
  pièce jointe d'e-mail ni un autre site. Le code y est public : chacun peut lire ce qu'il fait.
- **Vos données restent sur votre ordinateur.** Bridge Coach n'envoie rien sur Internet. L'application est une
  petite page web servie par l'ordinateur lui-même (adresse 127.0.0.1) : un autre appareil du réseau, même au
  club, ne peut pas l'ouvrir. Les fichiers ne partent que si vous les envoyez vous-même à Claude pour l'analyse
  experte.
- **L'installation, elle, télécharge :** Python (python.org ou Microsoft, par `winget`) et les bibliothèques de
  `requirements.txt` depuis PyPI, le site officiel des bibliothèques Python. Leurs versions sont fixées : tout le
  monde reçoit celles qui ont été essayées, et une version nouvelle, abîmée ou piratée, n'arrive pas toute seule.
- **Les avertissements de Windows sont normaux :** « Windows a protégé votre ordinateur » (SmartScreen) vient de ce
  que le programme n'est pas signé par un certificat payant ; **Informations complémentaires**, puis **Exécuter
  quand même**. L'antivirus peut beaucoup travailler pendant la première analyse. Sur Mac, la première ouverture
  demande l'accès au dossier Documents : OK.
- **Pour le responsable du dépôt :** la double authentification du compte GitHub protège tous ceux qui
  téléchargent le programme.

## L'application

```
./bridge-coach.sh
```

Une fenêtre : elle propose le dernier tournoi du dossier de Bridgemate réglé dans `bridge-coach.ini`, un bouton crée les
rapports, une barre suit la progression, puis des boutons ouvrent les PDF. « Autre tournoi… » permet
de choisir un autre fichier. L'onglet Donnes crée des donnes d'entraînement par thème, avec un `.pbn` à importer
dans Bridgemate. Elle n'a été essayée que sur Mac.

Pour l'ouvrir d'un clic : sur Mac, `./raccourci-mac.sh` crée l'application dans le dossier Applications, un lien
sur le Bureau, et l'ajoute au Dock si on le veut ; sur Windows, `installer.bat` crée le raccourci du Bureau et,
si on le veut, l'entrée du menu Démarrer à épingler à la barre des tâches.

## Utilisation en ligne de commande

```
./rapport.sh                  choisir parmi les .bws du dossier de Bridgemate
./rapport.sh séance.bws       un fichier précis
./rapport.sh séance.bws --avec-noms   ajoute une page avec le nom des joueurs
```

Une feuille de route PDF de FFBClubNet est acceptée aussi (`./rapport.sh "feuille.pdf"`) : elle
donne les mains, les contrats, les entames et les résultats, mais pas les enchères ; le double
mort est calculé par le programme. Les sauvegardes FFBClubNet nommées `.bws` sont des archives
protégées par un mot de passe : il faut le vrai `.bws` de Bridgemate.

Chaque séance devient d'abord un fichier Bridge Coach, `<séance>.bc.json`, rangé dans `seances/AAAA-MM/` :
la séance, les joueurs (initiales, et nom complet quand la source le donne), les donnes et les résultats
de chaque table. C'est tout ce qu'il faut aux rapports : `./rapport.sh <séance>.bc.json` les refait sans
le `.bws`. Le `.bws`, la feuille de route et les donnes de l'onglet Donnes ne sont que des sources qu'on importe.

Sans fichier, le programme liste les `.bws` du dossier de Bridgemate, les plus récents d'abord ;
Entrée choisit le dernier.

## Les dossiers

`bridge-coach.ini` indique deux dossiers ; le bouton Réglages de l'application l'ouvre :

- `bridgemate` (par défaut `~/Documents/bridgemate-files`) : où Bridgemate enregistre ses `.bws`.
  Le programme ne fait qu'y lire ;
- `fichiers`, le dossier de travail (par défaut `~/Documents/bridge-coach-files`, à part du programme) : les séances (`.bc.json`, avec l'original
  copié et les analyses) dans `seances/AAAA-MM/`, les PDF dans `rapports/AAAA-MM/`. Rien de tout cela ne va dans git.
  L'ancien rangement (`reports/`, `-donnes.json`) est mis à jour tout seul au premier lancement.

Le fichier de réglages reste à une place fixe, créé au premier lancement : sur Mac
`~/Library/Application Support/Bridge Coach/`, sous Windows `%APPDATA%\Bridge Coach\`.

## L'analyse experte (facultatif)

Le rapport `expert` est rédigé par Claude (Claude Code, d'Anthropic), ouvert dans le dossier
du projet. Il suffit de lui demander d'analyser la séance : le fichier `CLAUDE.md` lui donne
les consignes (système SEF, enchères choisies à la table sans regarder le double mort,
décisions serrées signalées). L'analyse est enregistrée dans
`~/Documents/bridge-coach-files/seances/AAAA-MM/<séance>-expert.json` ; `./rapport.sh` produit ensuite `expert` et `diff`.

## Le système d'enchères

Les enchères, les entames et le jeu de la carte sont décrits dans `systems/` :

- `systems/sef-2024/regles.yaml` : les règles d'enchères que lit le programme (en français,
  couleurs T K C P) ; la grammaire est dans `systems/grammaire.md` ;
- `systems/sef-2024/entames.yaml` : le choix de l'entame ;
- `systems/sef-2024/systeme.md`, `entames.md`, `systems/technique/jeu-de-la-carte.md` :
  les explications.

Ces fichiers se modifient à la main ; leurs exemples sont vérifiés à chaque lecture, et une
erreur est signalée avec son numéro de ligne.
