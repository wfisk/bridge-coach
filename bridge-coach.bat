@echo off
rem Ouvre Bridge Coach. Option : --navigateur
cd /d "%~dp0"
.venv\Scripts\python -I -X utf8 src\app.py %*
if errorlevel 1 pause
