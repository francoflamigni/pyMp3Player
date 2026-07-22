@echo off
echo [%DATE% %TIME%] Avvio creazione eseguibile con PyInstaller... >> "%~dp0status.log"

pyinstaller.exe --clean --noconfirm --windowed --noconsole --name Euterpe^
 --icon=..\icone\player.ico^
 --add-data="../icone/*;./icone/"^
 --add-data="../exe/;./exe/"^
 --add-data="../docs/;./docs/"^
 --paths="../exe"^
 --paths "C:/Users/franc/MySoft/pyMyLib/"^
 ../Player.py

  if %ERRORLEVEL% NEQ 0 (
    echo [%DATE% %TIME%] ERRORE: Creazione eseguibile fallita con codice %ERRORLEVEL%. >> "%~dp0status.log"
) else (
    echo [%DATE% %TIME%] SUCCESSO: Creazione eseguibile completata. >> "%~dp0status.log"
)
echo ---------------------------------------- >> "%~dp0status.log"