; Bridge-Coach-Setup.exe : l'installateur Windows, fait par Inno Setup 6 (GitHub Actions, .github/workflows/installateurs.yml).
;   iscc /DVersion=1.4 /DIcone=..\..\src\icone.ico installer\windows\bridge-coach.iss
; Il ne contient pas le programme : installer.ps1 prend la dernière version publiée sur GitHub et vérifie chaque
; téléchargement. Pas besoin de le refaire pour une nouvelle version de Bridge Coach.
; Sans droits d'administrateur : tout va dans %LOCALAPPDATA%\Programs\Bridge Coach. La désinstallation (Paramètres,
; Applications) retire ce dossier ; les séances (Documents) et les réglages (%APPDATA%\Bridge Coach) restent.
; La mise à jour du programme (src/maj.py) ne touche pas à .installeur, .python ni .venv.

#ifndef Version
  #define Version "1.0"
#endif
#ifndef Icone
  #define Icone "..\..\src\icone.ico"
#endif

[Setup]
AppId={{B43767D5-8686-4A7E-9C07-840BC82ABE02}
AppName=Bridge Coach
AppVersion={#Version}
AppVerName=Bridge Coach
AppPublisher=Bridge Coach
AppPublisherURL=https://github.com/wfisk/bridge-coach
AppSupportURL=https://github.com/wfisk/bridge-coach
DefaultDirName={localappdata}\Programs\Bridge Coach
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
UninstallFilesDir={app}\.installeur
UninstallDisplayIcon={app}\.installeur\icone.ico
SetupIconFile={#Icone}
OutputBaseFilename=Bridge-Coach-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[Messages]
fr.WelcomeLabel2=Bridge Coach va être installé sur cet ordinateur.%n%nL'installateur télécharge la dernière version du programme sur GitHub, avec Python et ses bibliothèques, et vérifie chaque fichier. Comptez quelques minutes et une connexion à Internet.

[Tasks]
Name: "bureau"; Description: "Mettre Bridge Coach sur le Bureau"

[Files]
Source: "installer.ps1"; Flags: dontcopy
Source: "{#Icone}"; DestDir: "{app}\.installeur"; DestName: "icone.ico"

[Icons]
; cmd /c lance bridge-coach.bat, fenêtre noire réduite. Le menu Démarrer permet d'épingler à la barre des tâches.
Name: "{userprograms}\Bridge Coach"; Filename: "{cmd}"; Parameters: "/c ""{app}\bridge-coach.bat"""; WorkingDir: "{app}"; IconFilename: "{app}\.installeur\icone.ico"; Flags: runminimized
Name: "{userdesktop}\Bridge Coach"; Filename: "{cmd}"; Parameters: "/c ""{app}\bridge-coach.bat"""; WorkingDir: "{app}"; IconFilename: "{app}\.installeur\icone.ico"; Flags: runminimized; Tasks: bureau

[Run]
Filename: "{cmd}"; Parameters: "/c ""{app}\bridge-coach.bat"""; WorkingDir: "{app}"; Description: "Ouvrir Bridge Coach"; Flags: postinstall nowait runminimized skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
// Le travail se fait avant la copie des fichiers : si un téléchargement ou une empreinte ne va pas, l'installation
// s'arrête ici avec un message, sans raccourci vers un programme absent.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
  PS: String;
begin
  Result := '';
  ExtractTemporaryFile('installer.ps1');
  PS := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
  if not Exec(PS, '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{tmp}\installer.ps1') +
              '" -Dossier "' + ExpandConstant('{app}') + '"', '', SW_SHOW, ewWaitUntilTerminated, Code) then
    Result := 'PowerShell n''a pas pu être lancé.'
  else if Code <> 0 then
    Result := 'L''installation de Bridge Coach a échoué. Le détail est dans le fichier ' +
              ExpandConstant('{%TEMP}\bridge-coach-installation.txt') + '.';
end;
