@echo off
REM Erstellt eine ausführbare .exe-Datei aus emoji_picker.py

REM Abhängigkeiten installieren
pip install --upgrade pip
pip install -r requirements.txt

REM Vorherige Builds entfernen
rmdir /s /q build
rmdir /s /q dist
del /q emoji_picker.spec


REM PyInstaller ausführen (mit clean und hidden-import für pyperclip und Icon als .ico)
pyinstaller --onefile --noconsole --add-data "tray_icon.png;." --add-data "emojis.json;." emoji_picker.py

REM Hinweis für den Nutzer
echo.
echo Fertig! Die .exe befindet sich im dist-Ordner.
pause












