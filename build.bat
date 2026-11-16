@echo off
cd /d "%~dp0"
python -m PyInstaller --noconfirm --clean --windowed --onedir --name QQPhoneLyrics --add-data "tools;tools" app.py
pause
