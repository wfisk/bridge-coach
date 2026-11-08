# Installe Bridge Coach dans un dossier : lancé par Bridge-Coach-Setup.exe (bridge-coach.iss) avant la copie de ses
# fichiers, dans une fenêtre qui montre où il en est. Rien du programme n'est dans l'installateur : il prend la dernière
# version publiée sur GitHub et vérifie chaque téléchargement par son empreinte SHA-256 :
#   1. l'archive du programme (bridge-coach-X.Y.zip), contre le SHA256SUMS publié avec elle ;
#   2. Python, contre l'empreinte écrite dans installer/python.txt de l'archive vérifiée ;
#   3. les bibliothèques, contre les empreintes de requirements.txt (pip --require-hashes).
# Essai sans GitHub (le build de GitHub Actions) : -Zip archive.zip -Sommes SHA256SUMS -SansPause
param(
    [Parameter(Mandatory = $true)][string]$Dossier,
    [string]$Zip = "",
    [string]$Sommes = "",
    [switch]$SansPause
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'          # la barre de progression de PowerShell 5 ralentit les téléchargements
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Depot = 'wfisk/bridge-coach'
$Tmp = Join-Path $env:TEMP ("bridge-coach-" + [guid]::NewGuid().ToString('N'))
$Journal = Join-Path $env:TEMP 'bridge-coach-installation.txt'
New-Item -ItemType Directory -Force $Tmp | Out-Null
Start-Transcript -Path $Journal -Force | Out-Null
$Host.UI.RawUI.WindowTitle = 'Installation de Bridge Coach'

function Etape($texte) { Write-Host ''; Write-Host $texte -ForegroundColor Cyan }
function Telecharger($url, $fichier) { Invoke-WebRequest -Uri $url -OutFile $fichier -UseBasicParsing -UserAgent 'Bridge-Coach' }
function Verifier($fichier, $attendu) {
    $h = (Get-FileHash -Algorithm SHA256 -LiteralPath $fichier).Hash.ToLower()
    if ($h -ne $attendu.ToLower()) {
        throw "empreinte incorrecte pour $(Split-Path -Leaf $fichier) : le fichier téléchargé n'est pas celui qui a été publié. Rien n'a été installé."
    }
}
function Lancer($programme, [string[]]$arguments) {
    & $programme @arguments
    if ($LASTEXITCODE -ne 0) { throw "$(Split-Path -Leaf $programme) a échoué (code $LASTEXITCODE)." }
}

$code = 0
try {
    Etape '1/5  Dernière version de Bridge Coach'
    if (-not $Zip) {
        $version = Invoke-RestMethod -Uri "https://api.github.com/repos/$Depot/releases/latest" -UserAgent 'Bridge-Coach'
        $a = $version.assets | Where-Object { $_.name -like 'bridge-coach-*.zip' } | Select-Object -First 1
        $s = $version.assets | Where-Object { $_.name -eq 'SHA256SUMS' } | Select-Object -First 1
        if (-not $a -or -not $s) { throw "la version $($version.tag_name) n'a pas d'archive vérifiable sur GitHub." }
        Write-Host "Version $($version.tag_name)"
        $Zip = Join-Path $Tmp $a.name
        $Sommes = Join-Path $Tmp 'SHA256SUMS'
        Telecharger $a.browser_download_url $Zip
        Telecharger $s.browser_download_url $Sommes
    }
    $nom = Split-Path -Leaf $Zip
    $ligne = Get-Content -LiteralPath $Sommes | Where-Object { ((($_ -split '\s+')[1]) -replace '^\*', '') -eq $nom } | Select-Object -First 1
    if (-not $ligne) { throw "$nom n'a pas d'empreinte publiée." }
    Verifier $Zip (($ligne -split '\s+')[0])
    Write-Host 'Empreinte vérifiée.'

    Etape '2/5  Mise en place du programme'
    $ext = Join-Path $Tmp 'programme'
    Expand-Archive -LiteralPath $Zip -DestinationPath $ext
    $haut = @(Get-ChildItem -Force $ext)
    $source = if ($haut.Count -eq 1 -and $haut[0].PSIsContainer) { $haut[0].FullName } else { $ext }
    if (-not (Test-Path (Join-Path $source 'src\app.py'))) { throw "l'archive ne contient pas le programme." }
    New-Item -ItemType Directory -Force $Dossier | Out-Null
    # une installation précédente est remplacée en entier ; .installeur (désinstallation, icône) reste.
    # Les fichiers de l'utilisateur sont ailleurs (Documents, et ses réglages dans %APPDATA%\Bridge Coach).
    Get-ChildItem -Force -LiteralPath $Dossier | Where-Object { $_.Name -ne '.installeur' } | Remove-Item -Recurse -Force
    Get-ChildItem -Force -LiteralPath $source | Move-Item -Destination $Dossier
    Write-Host $Dossier

    Etape '3/5  Python'
    $py = Get-Content -LiteralPath (Join-Path $Dossier 'installer\python.txt') | Where-Object { $_ -match '^windows-x86_64\s' } | Select-Object -First 1
    if (-not $py) { throw "installer\python.txt ne dit pas quel Python prendre pour Windows." }
    $p = $py -split '\s+'
    $tgz = Join-Path $Tmp 'python.tar.gz'
    Telecharger $p[2] $tgz
    Verifier $tgz $p[1]
    Write-Host 'Empreinte vérifiée.'
    Lancer "$env:SystemRoot\System32\tar.exe" @('-xzf', $tgz, '-C', $Tmp)     # celui de Windows : un autre tar lirait C: comme un serveur
    Move-Item (Join-Path $Tmp 'python') (Join-Path $Dossier '.python')

    Etape '4/5  Bibliothèques (quelques minutes)'
    Lancer (Join-Path $Dossier '.python\python.exe') @('-m', 'venv', (Join-Path $Dossier '.venv'))
    $venv = Join-Path $Dossier '.venv\Scripts\python.exe'
    Lancer $venv @('-m', 'pip', 'install', '--disable-pip-version-check', '--no-warn-script-location', '--require-hashes', '-r', (Join-Path $Dossier 'requirements.txt'))

    Etape '5/5  Vérification'
    Push-Location $Dossier
    try { Lancer $venv @('-I', '-X', 'utf8', '-c', "import sys; sys.path.insert(0, 'src'); import rapport, donnes, edition, app; print('Le programme se charge.')") }
    finally { Pop-Location }
    Write-Host ''
    Write-Host 'Installation terminée.' -ForegroundColor Green
}
catch {
    $code = 1
    Write-Host ''
    Write-Host "L'installation a échoué : $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Le détail est dans $Journal"
    if (-not $SansPause) { Read-Host 'Appuyez sur Entrée pour fermer cette fenêtre' | Out-Null }
}
finally {
    Stop-Transcript | Out-Null
    Remove-Item -Recurse -Force -LiteralPath $Tmp -ErrorAction SilentlyContinue
}
exit $code
