@echo off
rem Installe Bridge Coach : environnement Python dans .venv et bibliotheques.
rem Le solveur de donnes (endplay) existe pour Python 3.9 a 3.13 : on cherche d'abord 3.12.
setlocal
cd /d "%~dp0"
set "PY="
for %%v in (3.12 3.13 3.11 3.10 3.9) do (
  if not defined PY (
    py -%%v -c "import sys" >nul 2>nul && set "PY=py -%%v"
  )
)
if not defined PY (
  python -c "import sys; sys.exit(0 if (3, 9) <= sys.version_info[:2] <= (3, 13) else 1)" >nul 2>nul && set "PY=python"
)
if not defined PY goto sans_python

:venv
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python -c "import sys; sys.exit(0 if (3, 9) <= sys.version_info[:2] <= (3, 13) else 1)" >nul 2>nul
  if errorlevel 1 (
    echo L ancien environnement utilise une version de Python qui ne convient pas : il est recree.
    rmdir /s /q .venv
  )
)
echo Python utilise : %PY%
if not exist .venv\Scripts\python.exe %PY% -m venv .venv
if not exist .venv\Scripts\python.exe goto echec
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 goto echec
rem Raccourci : cmd /c lance bridge-coach.bat, fenetre noire reduite ; un raccourci vers cmd s epingle,
rem pas un raccourci vers un .bat.
set "PS=$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK); $s.TargetPath=$env:ComSpec; $q=[char]34; $s.Arguments='/c '+$q+$env:ICI+'bridge-coach.bat'+$q; $s.WorkingDirectory=$env:ICI; $s.IconLocation=$env:ICI + 'src\icone.ico'; $s.WindowStyle=7; $s.Description='Bridge Coach'; $s.Save()"
set "ICI=%~dp0"
for /f "usebackq delims=" %%d in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"`) do set "BUREAU=%%d"
set "LNK=%BUREAU%\Bridge Coach.lnk"
powershell -NoProfile -Command "%PS%" && echo Raccourci cree sur le Bureau : Bridge Coach.
echo.
choice /c ON /m "Ajouter aussi Bridge Coach au menu Demarrer, pour l epingler a la barre des taches"
if errorlevel 2 goto fin
set "LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Bridge Coach.lnk"
powershell -NoProfile -Command "%PS%" && echo Bridge Coach est dans le menu Demarrer.
echo Pour la barre des taches, Windows demande un clic : menu Demarrer, Toutes les applications,
echo clic droit sur Bridge Coach, Plus, Epingler a la barre des taches.
:fin
echo.
echo Installation terminee. Double-cliquez sur Bridge Coach, sur le Bureau, pour ouvrir l application.
pause
exit /b 0

:sans_python
echo.
echo Bridge Coach a besoin de Python 3.12 (les versions 3.9 a 3.13 conviennent).
echo Le solveur de donnes ne fonctionne pas encore avec Python 3.14.
echo Python 3.12 s installe a cote d une autre version, sans la remplacer.
echo.
where winget >nul 2>nul
if errorlevel 1 goto manuel
choice /c ON /m "Installer Python 3.12 maintenant"
if errorlevel 2 goto manuel
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
py -3.12 -c "import sys" >nul 2>nul
if errorlevel 1 (
  echo Python 3.12 est installe : fermez cette fenetre et relancez installer.bat.
  pause
  exit /b 1
)
set "PY=py -3.12"
goto venv

:manuel
echo Telechargez Python 3.12, version Windows installer 64-bit, sur
echo https://www.python.org/downloads/windows/
echo puis relancez installer.bat.
pause
exit /b 1

:echec
echo L installation a echoue.
pause
exit /b 1
