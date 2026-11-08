@NOTE@

## Installer Bridge Coach

Téléchargez seulement depuis cette page :

- **Windows** (10 ou 11) : `Bridge-Coach-Setup.exe`
- **Mac** : `Bridge-Coach.pkg`

L'installateur ne contient pas le programme : il télécharge la dernière version ici, avec Python et ses
bibliothèques, et vérifie l'empreinte de chaque fichier. Comptez quelques minutes et une connexion à Internet.

**Windows** affiche d'abord « Windows a protégé votre ordinateur » (l'installateur n'est pas signé) : cliquez sur
*Informations complémentaires*, puis *Exécuter quand même*.

**Mac** refuse d'abord de l'ouvrir (développeur non identifié) : ouvrez *Réglages Système*, *Confidentialité et
sécurité*, et cliquez sur *Ouvrir quand même* en bas de la page.

Déjà installé ? Pas besoin de cette page : *Réglages*, *Mise à jour du programme*, dans Bridge Coach.

## Vérifier un téléchargement (facultatif)

Empreintes SHA-256 de la version @VERSION@ (fichier `SHA256SUMS`) :

```
@SHA256SUMS@
```

Pour comparer :
- Windows, dans PowerShell : `Get-FileHash Bridge-Coach-Setup.exe`
- Mac, dans le Terminal : `shasum -a 256 Bridge-Coach.pkg`

Ces fichiers ont été faits par GitHub Actions à partir de ce dépôt, ce que prouve leur attestation :
`gh attestation verify Bridge-Coach.pkg --repo wfisk/bridge-coach`
