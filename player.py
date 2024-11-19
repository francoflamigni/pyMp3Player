import os
import sys

from PyQt6.QtWidgets import (QMainWindow, QStackedWidget, QVBoxLayout,
            QApplication, QTabBar, QSplashScreen, QPushButton, QToolBar)
from PyQt6.QtGui import QIcon, QPixmap

from qframelesswindow import FramelessDialog, StandardTitleBar

from pyMyLib.qtUtils import informMessage
from pyMyLib.utils import iniConf
from dialogs import RadioDlg, MusicIndexDlg, MusicPlayerDlg

'''
https://streamurl.link/ per trovare stazioni radio
'''

class MyTitleBar(StandardTitleBar):
    def __init__(self, parent):
        super().__init__(parent)

        self.setTitle("Media Player")
        self.setIcon(QIcon(os.path.join(os.getcwd(), 'icone/player.ico')))
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

        self.ini = iniConf('music_player')

        self.splash = None

        f = os.path.join(os.getcwd(),  './icone/splash.bmp')
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
        self.dlg.process()

    def createTabBar(self):
        tool = QToolBar()
        self.tb = QTabBar()
        self.tb.addTab('')
        self.tb.setTabIcon(0, QIcon(os.path.join(os.getcwd(), 'icone/mp3.png')))
        self.tb.setTabToolTip(0, 'Mp3')
        self.tb.addTab('')
        self.tb.setTabIcon(1, QIcon(os.path.join(os.getcwd(), 'icone/radio.png')))
        self.tb.setTabToolTip(1, 'Radio')
        self.tb.addTab('')
        self.tb.setTabIcon(2, QIcon(os.path.join(os.getcwd(), 'icone/stereo.png')))
        self.tb.setTabToolTip(2, 'player')
        self.tb.currentChanged.connect(self.tab_changed)
        tool.addWidget(self.tb)

        bi = QPushButton('?', self)
        bi.setMaximumWidth(30)
        bi.clicked.connect(self.info)
        #tool.
        tool.addWidget(bi)
        return tool

    def tab_changed(self, index):
        self.tab.setCurrentIndex(index)

    def create_ui(self):
        v = QVBoxLayout(self)
        v.addSpacing(20)
        self.tab = QStackedWidget(self)

        self.dlg = MusicIndexDlg(self)
        #self.dlg.setMinimumWidth(500)
        self.tab.addWidget(self.dlg)

        rd = RadioDlg(self)
        self.tab.addWidget(rd)

        self.ply = MusicPlayerDlg(self)
        self.tab.addWidget(self.ply)

        v.addWidget(self.tab)

    def get_track_pix(self, album, artist, cover):
        self.dlg.get_track_pix(album, artist, cover)

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

    def info(self):
        informMessage('Music Player\nGestione mp3\nVersione 1.1.1\n29 Ottobre 2024', 'Music Player', 15, True, os.path.join(os.getcwd(), 'icone/pentagram.ico'))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = Player()
    sys.exit(app.exec())