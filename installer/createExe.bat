pyinstaller.exe --clean --noconfirm --windowed --splash ../icone/splash.bmp --noconsole --name Euterpe^
 --collect-all scipy^
 --icon=..\icone\player.ico^
 --add-data="../icone/*;./icone/"^
 --add-data="../exe/;./exe/"^
 --paths="../exe"^
 ../Player.py