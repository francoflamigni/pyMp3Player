from profiler import checkpoint

import os
import sys

from PyQt6.QtWidgets import (QMainWindow, QStackedWidget, QVBoxLayout, QLabel,
                             QApplication, QTabBar, QSplashScreen, QPushButton, QToolBar, QMenu, QComboBox)
from PyQt6.QtGui import QIcon, QPixmap, QCursor, QAction, QColor, QPainter, QFont
from PyQt6.QtCore import Qt, QRect

from qframelesswindow import FramelessDialog, StandardTitleBar

from pyMyLib.qtUtils import informMessage, AddMenuItem, set_application_icon
from pyMyLib.utils import iniConf, get_resource_file, get_resource_path_pathlib

from dialogs import RadioDlg, AppConfig
from music_index import MusicIndexDlg
from music_player import MusicPlayerDlg
from utility import detect_cd_drives, close_splash
from mp3_tag import GENRE

'''
https://streamurl.link/ per trovare stazioni radio
'''

INFO_MES = f'{AppConfig}\nMusic manager\nVersione 1.5.1\n02 Novembre 2025'

class MyTitleBar(StandardTitleBar):
    def __init__(self, parent):
        super().__init__(parent)

        self.setTitle("Euterpe")
        self.setIcon(QIcon(get_resource_file(__file__, 'icone', 'player.ico')))
        self.maxBtn.hide()
        self.setDoubleClickEnabled(False)

        lay = self.layout()
        lay.insertSpacing(3, 5)

        tb = parent.createTabBar()
        lay.insertWidget(4, tb)

class Player(FramelessDialog): #QMainWindow):
    def __init__(self, master=None):
        super().__init__()

        self.setTitleBar(MyTitleBar(self))
        self.setResizeEnabled(False)

        os.environ["PATH"] += os.pathsep + str(get_resource_path_pathlib(__file__, 'exe'))

        self.ini = iniConf(AppConfig)

        '''
        self.splash = None
        f = get_resource_file(__file__, 'icone',  'splash.bmp')
        if os.path.isfile(f):
            self.splash = create_fast_splash_pyqt6()
            #self.splash = QSplashScreen(QPixmap(f))
            self.splash.show()
        '''

        self.background_mode = False
        self.create_ui()

        close_splash()
        #if self.splash is not None:
        #    self.splash.close()

        self.Install_idle_fun()
        self.show()

    def Install_idle_fun(self):
        from utility import IdleTimeout
        self.idle_timer = None
        idle_time = self.ini.get('user', 'tmout')
        try:
            idle_time = int(idle_time)
        except:
            idle_time = 0
        if idle_time != 0:
            self.idle_timer = IdleTimeout(self, idle_time, self.idle_background)

    def show(self):
        QMainWindow.show(self)
        self.raise_()  # Porta in primo piano
        self.activateWindow()  # Attiva la finestra
        self.setWindowState(
            self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        QApplication.processEvents()
        sz = self.dlg.prog.size()
        sz.setWidth(100)
        self.dlg.prog.setFixedSize(sz)

        self.dlg.process()

    def createTabBar(self):
        tool = QToolBar()

        bt = QPushButton(self)
        bt.setIcon(QIcon(get_resource_file(__file__, 'icone', 'menu.png')))
        bt.setMaximumWidth(30)
        bt.clicked.connect(self.options)
        tool.addWidget(bt)
        #tool.addSeparator()
        spacer_fixed = QLabel()
        spacer_fixed.setFixedWidth(30) # Imposta una larghezza fissa di 50px
        tool.addWidget(spacer_fixed)

        self.tb = QTabBar()
        self.tb.addTab('')
        self.tb.setTabIcon(0, QIcon(get_resource_file(__file__, 'icone', 'mp3.png')))
        self.tb.setTabToolTip(0, 'Mp3')
        self.tb.addTab('')
        self.tb.setTabIcon(1, QIcon(get_resource_file(__file__, 'icone', 'radio.png')))
        self.tb.setTabToolTip(1, 'Radio')
        self.tb.addTab('')
        self.tb.setTabIcon(2, QIcon(get_resource_file(__file__, 'icone', 'stereo.png')))
        self.tb.setTabToolTip(2, 'player')
        self.tb.currentChanged.connect(self.tab_changed)
        self.tb.setStyleSheet("""
            QTabBar::tab {
                /* Aggiunge il bordo intorno alla scheda */
                border: 1px solid gray; 

                /* Spazio interno al testo della scheda */
                padding: 3px 3px; 

                /* Raggio per angoli arrotondati (solo in alto) */
                border-top-left-radius: 3px; 
                border-top-right-radius: 3px;
            }

            /* Rimuovi il bordo inferiore per creare l'illusione di connessione con il QTabWidget */
            QTabBar::tab:!selected {
                border-bottom-color: #C2C7CB; /* Stesso colore dello sfondo del QTabWidget/barra */
            }

            /* Stile della scheda selezionata */
            QTabBar::tab:selected {
                border-color: blue;
                border-bottom-color: white; /* Per far sembrare che sia attaccata alla pagina sottostante */
            }
        """)

        tool.addWidget(self.tb)
        spacer_fixed2 = QLabel()
        spacer_fixed2.setFixedWidth(30) # Imposta una larghezza fissa di 50px
        tool.addWidget(spacer_fixed2)

        self.genre_combo = QComboBox()

        self.genre_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid;  /* Spessore del bordo (ad esempio 2 pixel) */
                border-color: #555555; /* Colore del bordo (ad esempio un grigio scuro) */

                
                border-radius: 3px; /* Raggio per angoli arrotondati (opzionale) */

                /* Padding opzionale per evitare che il testo tocchi il bordo */
                padding: 2px 10px 2px 5px; 
            }
        """)

        v = [""]
        v.extend((GENRE))
        self.genre_combo.addItems(v)
        self.genre_combo.currentIndexChanged.connect(self.filter_genre)
        self.combo_action = tool.addWidget(self.genre_combo)

        return tool

    def tab_changed(self, index):
        visible = False if index != 0 else True
        self.combo_action .setVisible(visible)
        self.tab.setCurrentIndex(index)

    def filter_genre(self, index):
        gen = self.genre_combo.currentText()
        self.dlg.filter(gen)

    def create_ui(self):
        v = QVBoxLayout(self)
        v.addSpacing(20)
        self.tab = QStackedWidget(self)

        self.dlg = MusicIndexDlg(self)
        self.dlg.play_signal.connect(self.open_file)
        self.tab.addWidget(self.dlg)

        rd = RadioDlg(self)
        rd.radio_signal.connect(self.open_radio)
        self.tab.addWidget(rd)

        self.ply = MusicPlayerDlg(self)
        self.tab.addWidget(self.ply)

        v.addWidget(self.tab)

    def options(self):
        p = QCursor.pos()
        contextMenu = QMenu(self)
        drives = detect_cd_drives()
        cd = None
        if drives:
            cd = QMenu("Riproduci CD", self)
            cd.setIcon(QIcon(get_resource_file(__file__, 'icone', 'cd_play.png')))
            for d in drives:
                d1 = QAction(d, self)
                d1.triggered.connect(lambda checked, drive_letter=d: self.open_cd(drive_letter))
                cd.addAction(d1)
        actions = [
            AddMenuItem("Dispositivi Bluetooth", fun=self.bluetooth,
                            ico=get_resource_file(__file__, 'icone', 'Bluetooth.png')),
            AddMenuItem("Converti da altri formati", fun=self.convert,
                            ico=get_resource_file(__file__, 'icone', 'tag-edit.png')),
            AddMenuItem("CD ripper", fun=self.cd_ripper,
                            ico=get_resource_file(__file__, 'icone', 'cd_ripper.png')),
            AddMenuItem("Crea PlayList", fun=self.create_playlist,
                        ico=get_resource_file(__file__, 'icone', 'create_playlist.png')
                        ),
            AddMenuItem("Riproduci CD", fun=cd, enab=drives,
                        ico=get_resource_file(__file__, 'icone', 'cd_play.png')),

            AddMenuItem("Background", fun=self.background, enab=not self.background_mode,
                        ico=get_resource_file(__file__, 'icone', 'background.png')),

            AddMenuItem("Sincronizza", fun=self.sync_folder,
                        ico=get_resource_file(__file__, 'icone', 'folders_sync.png')),
            AddMenuItem("Preferenze", fun=self.preference,
                        ico=get_resource_file(__file__, 'icone', 'preferences.png')),
            AddMenuItem("Informazioni", fun=self.info)
        ]
        contextMenu.addActions(actions)
        contextMenu.exec(p)

    def get_track_pix(self, album, artist, cover):
        self.dlg.get_track_pix(album, artist, cover)

    ''' Chiama Shazam per avere il titolo'''
    def songTitle(self):
        wd = self.tab.widget(0)
        wd.find_song()

    def open_radio(self, url='', fav=''):
        if self.ply.open_radio(url, fav):
            self.tab.setCurrentIndex(2)
            self.tb.setCurrentIndex(2)

    def open_file(self, tracks=None):
        self.background(True)
        self.ply.open_file(tracks)
        self.tab.setCurrentIndex(2)
        self.tb.setCurrentIndex(2)

    def open_cd(self, drive):
        self.ply.open_cd(drive)
        self.tab.setCurrentIndex(2)
        self.tb.setCurrentIndex(2)

    def idle_background(self):
        if not self.background_mode and self.ply.mode == self.ply.Mode_None :
            self.background()

    def background(self, reset=False):
        if self.background_mode or reset:
            self.background_mode = False
            self.titleBar.setTitle("Euterpe")
            try:
                self.ply.next_song_signal.disconnect(self._background)
            except:
                pass
        else:
            self.background_mode = True
            self.titleBar.setTitle("Euterpe\U0001F535")
            self.ply.next_song_signal.connect(self._background)
            self._background(1)

    def _background(self, index):
        if index == 0:
            self.background(True) # forza l'uscita dal background mode

        import random
        from scrobbler import leggi_stringa_offline
        if self.background_mode:
            mi = self.dlg.music.tracks.name
            key = random.choice(list(mi.keys()))
            mstr = mi[key]
            leggi_stringa_offline([mstr.artist, mstr.album, mstr.title])
            self.ply.open_file([mi[key]])

    def bluetooth(self):
        from bluetooth import BluetoothManager
        bt = BluetoothManager()
        bt.exec()

    def info(self):
        informMessage(INFO_MES, 'Εὐτέρπη', 15, True, get_resource_file(__file__, 'icone', 'pentagram.png'))

    def convert(self):
        from format_convert import AudioConverter
        ac = AudioConverter()
        ac.exec()

    def cd_ripper(self):
        from cd_ripper import CDRipperMainWindow
        cr = CDRipperMainWindow()
        cr.play_signal.connect(self.ply.open_cd)
        cr.exec()

    def sync_folder(self):
        from sync_folders import SyncApp
        msg = SyncApp(self, self.dlg.last_folder)
        msg.exec()

    def preference(self):
        from dialogs import ConfigBox
        if ConfigBox.run(self, self.ini) == 1:
            self.Install_idle_fun()

    def create_playlist(self):
        #self.get_generi()
        index = self.dlg.music

        from playlist import PlayListDlg
        plldlg = PlayListDlg(self, index)
        ret = plldlg.exec()
        if ret:
            lst = plldlg.get_playlist()
            self.dlg.clear_playlist()
            for t in lst:
                self.dlg.add_playlist(*t)

            tip = self.dlg.tab.tabToolTip(1)
            stat = {}
            for t in lst:
                if t[0] in stat.keys():
                    n = stat[t[0]]
                    stat[t[0]] = n + 1
                else:
                    stat[t[0]] = 1
            lines = [f"{key}: {value}" for key, value in stat.items()]
            tip = f"{tip}\n {'\n'.join(lines)}"
            self.dlg.tab.setTabToolTip(1, tip)

            self.dlg.tab.setCurrentIndex(1)

    def get_generi(self):
        from collections import defaultdict
        musica = self.dlg.music
        art_gen = defaultdict(set)
        for t in musica.tracks.name.values():
            if t.genre:
                art_gen[t.artist].add(t.genre)
            a = 0
        b = 0


if __name__ == "__main__":
    app = QApplication(sys.argv)
    set_application_icon(app, f'Mysoft.{AppConfig}.v1', get_resource_file(__file__, 'icone', 'player.ico'))
    player = Player()
    sys.exit(app.exec())