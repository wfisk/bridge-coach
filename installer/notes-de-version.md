@NOTE@

Les fichiers à télécharger sont **en bas de cette page**, dans la partie **Assets** (cliquez sur *Assets* si elle est fermée). Choisissez votre cas ci-dessous. Ne prenez pas « Source code (zip) » ni « Source code (tar.gz) » : GitHub les ajoute tout seul, ils ne servent pas à installer.

Déjà installé ? Pas besoin de cette page : dans Bridge Coach, *Réglages*, *Mise à jour du programme*.

## Installer sur Windows (10 ou 11)

1. Dans **Assets**, cliquez sur **`Bridge-Coach-Setup.exe`** pour le télécharger.
2. Ouvrez le fichier téléchargé (dans le dossier *Téléchargements*).
3. Windows affiche « Windows a protégé votre ordinateur » (l'installateur n'est pas signé) : cliquez sur *Informations complémentaires*, puis *Exécuter quand même*.
4. Suivez l'installateur. Il télécharge le programme, Python et ses bibliothèques : comptez quelques minutes et une connexion à Internet.
5. Bridge Coach s'ouvre depuis l'icône du **Bureau** ou le menu **Démarrer**.

## Installer sur Mac

1. Dans **Assets**, cliquez sur **`Bridge-Coach.pkg`** pour le télécharger.
2. Ouvrez le fichier téléchargé (dans le dossier *Téléchargements*).
3. Le Mac refuse d'abord de l'ouvrir (développeur non identifié) : ouvrez *Réglages Système*, *Confidentialité et sécurité*, et cliquez sur *Ouvrir quand même* en bas de la page. Puis ouvrez de nouveau le fichier.
4. Suivez l'installateur (il demande le mot de passe du Mac). Il télécharge le programme, Python et ses bibliothèques : comptez quelques minutes et une connexion à Internet.
5. Bridge Coach s'ouvre depuis **Applications** ou l'icône du **Bureau**.

## Installer depuis le fichier zip (si l'installateur ne convient pas)

Pour les personnes à l'aise avec l'ordinateur : il faut d'abord **Python 3.9 à 3.13** (pas 3.14), depuis [python.org](https://www.python.org/downloads/).

1. Dans **Assets**, téléchargez **`bridge-coach-@VERSION@.zip`** (pas « Source code »).
2. Décompressez-le dans un dossier de votre choix, par exemple *Documents*.
3. Dans ce dossier :
   - **Windows** : double-cliquez sur `installer.bat`, puis, pour ouvrir Bridge Coach, sur `bridge-coach.bat`.
   - **Mac** : ouvrez le Terminal, tapez `cd ` puis glissez le dossier dans la fenêtre et appuyez sur Entrée ; ensuite `sh installer.sh`, puis, pour ouvrir Bridge Coach, `sh bridge-coach.sh` (l'installation propose aussi une icône dans Applications).

## Vérifier un téléchargement (facultatif)

L'installateur vérifie déjà l'empreinte de chaque fichier qu'il télécharge. Pour vérifier vous-même le fichier téléchargé, voici les empreintes SHA-256 de la version @VERSION@ (fichier `SHA256SUMS`) :

```
@SHA256SUMS@
```

Pour comparer :
- Windows, dans PowerShell : `Get-FileHash Bridge-Coach-Setup.exe`
- Mac, dans le Terminal : `shasum -a 256 Bridge-Coach.pkg`

Ces fichiers ont été faits par GitHub Actions à partir de ce dépôt, ce que prouve leur attestation : `gh attestation verify Bridge-Coach.pkg --repo wfisk/bridge-coach`
