import os
import sys

from PyQt6.QtWidgets import (QMainWindow, QStackedWidget, QVBoxLayout,
                             QApplication, QTabBar, QSplashScreen, QPushButton, QToolBar, QMenu)
from PyQt6.QtGui import QIcon, QPixmap, QCursor

from qframelesswindow import FramelessDialog, StandardTitleBar

from pyMyLib.qtUtils import informMessage, AddMenuItem
from pyMyLib.utils import iniConf, get_resource_file, get_resource_path_pathlib
from dialogs import RadioDlg, AppConfig
from music_index import MusicIndexDlg
from music_player import MusicPlayerDlg
from bluetooth import BluetoothManager

'''
https://streamurl.link/ per trovare stazioni radio
'''

INFO_MES = f'{AppConfig}\nMusic manager\nVersione 1.1.5\n02 Novembre 2025'

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

        self.splash = None

        f = get_resource_file(__file__, 'icone',  'splash.bmp')
        if os.path.isfile(f):
            self.splash = QSplashScreen(QPixmap(f))
            self.splash.show()

        self.create_ui()

        if self.splash is not None:
            self.splash.close()

        self.show()

    def show(self):
        QMainWindow.show(self)
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

        tool.addWidget(self.tb)

        return tool

    def tab_changed(self, index):
        self.tab.setCurrentIndex(index)

    def create_ui(self):
        v = QVBoxLayout(self)
        v.addSpacing(20)
        self.tab = QStackedWidget(self)

        self.dlg = MusicIndexDlg(self)
        self.tab.addWidget(self.dlg)

        rd = RadioDlg(self)
        self.tab.addWidget(rd)

        self.ply = MusicPlayerDlg(self)
        self.tab.addWidget(self.ply)

        v.addWidget(self.tab)

    def options(self):
        p = QCursor.pos()
        contextMenu = QMenu(self)
        actions = [
            AddMenuItem("Dispositivi Bluetooth", fun=self.bluetooth,
                            ico=get_resource_file(__file__, 'icone', 'Bluetooth.png')),
            AddMenuItem("Converti da altri formati", fun=self.convert,
                            ico=get_resource_file(__file__, 'icone', 'tag-edit.png')),
            AddMenuItem("CD ripper", fun=self.cd_ripper,
                            ico=get_resource_file(__file__, 'icone', 'cd_ripper.png')),
            AddMenuItem("Crea PlayList", fun=self.create_playlist),
            AddMenuItem("Sincronizza", fun=self.sync_folder),
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
        self.ply.open_radio(url, fav)
        self.tab.setCurrentIndex(2)
        self.tb.setCurrentIndex(2)

    def open_file(self, tracks=None):
        self.ply.open_file(tracks)
        self.tab.setCurrentIndex(2)
        self.tb.setCurrentIndex(2)

    def bluetooth(self):
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
        cr.exec()

    def sync_folder(self):
        from sync_folders import MusicSyncGUI
        msg = MusicSyncGUI(self, self.dlg.last_folder)
        msg.exec()

    def create_playlist(self):
        index = self.dlg.music

        from playlist import PlayListDlg
        plldlg = PlayListDlg(self, index)
        ret = plldlg.exec()
        if ret:
            lst = plldlg.get_playlist()
            self.dlg.clear_playlist()
            for t in lst:
                self.dlg.add_playlist(*t)

            self.dlg.tab.setCurrentIndex(1)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = Player()
    sys.exit(app.exec())