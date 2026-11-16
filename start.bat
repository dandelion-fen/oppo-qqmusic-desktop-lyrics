@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "%~dp0dist\QQPhoneLyrics\QQPhoneLyrics.exe" (
    start "" "%~dp0dist\QQPhoneLyrics\QQPhoneLyrics.exe"
    exit /b
)
python app.py
if errorlevel 1 pause
