pyinstaller.exe --clean --noconfirm --windowed --noconsole^
 --icon=..\icone\player.ico^
 --add-data="../icone/*;./icone/"^
 --add-data="../exe/;./exe/"^
 --paths="../exe"^
 ../Player.py