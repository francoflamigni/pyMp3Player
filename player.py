import os
import sys

from PyQt6.QtWidgets import (QMainWindow, QStackedWidget, QVBoxLayout,
                             QApplication, QTabBar, QSplashScreen, QPushButton, QToolBar, QMenu)
from PyQt6.QtGui import QIcon, QPixmap, QCursor

from qframelesswindow import FramelessDialog, StandardTitleBar

from pyMyLib.qtUtils import informMessage
from pyMyLib.utils import iniConf
from dialogs import RadioDlg, AppConfig
from music_index import MusicIndexDlg
from music_player import MusicPlayerDlg
from bluetooth import BluetoothManager

'''
https://streamurl.link/ per trovare stazioni radio
'''

INFO_MES = f'{AppConfig}\nMusic manager\nVersione 1.1.3\n18 Maggio 2025'

class MyTitleBar(StandardTitleBar):
    def __init__(self, parent):
        super().__init__(parent)

        self.setTitle("Euterpe")
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

        os.environ["PATH"] += os.pathsep + os.path.join(os.getcwd(), 'exe')

        self.ini = iniConf(AppConfig)

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
        sz = self.dlg.prog.size()
        sz.setWidth(100)
        self.dlg.prog.setFixedSize(sz)

        self.dlg.process()

    def createTabBar(self):
        tool = QToolBar()

        bt = QPushButton(self)
        bt.setIcon(QIcon(os.path.join(os.getcwd(), 'icone/menu.png')))
        bt.setMaximumWidth(30)
        bt.clicked.connect(self.options)
        tool.addWidget(bt)

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

        '''
        bt = QPushButton(self)
        bt.setIcon(QIcon(os.path.join(os.getcwd(), 'icone/bluetooth.png')))
        bt.setMaximumWidth(30)
        bt.clicked.connect(self.bluetooth)
        tool.addWidget(bt)

        bi = QPushButton('?', self)
        bi.setMaximumWidth(30)
        bi.clicked.connect(self.info)
        tool.addWidget(bi)
        '''
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

        contextMenu.addAction("Dispositivi Bluetooth").triggered.connect(self.bluetooth)
        contextMenu.addAction("Converti da altri formati").triggered.connect(self.convert)
        contextMenu.addAction("CD ripper").triggered.connect(self.cd_ripper)
        contextMenu.addAction("Informazioni").triggered.connect(self.info)
        contextMenu.exec(p)

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

    def bluetooth(self):
        bt = BluetoothManager()
        bt.exec()


    def info(self):
        informMessage(INFO_MES, 'Εὐτέρπη', 15, True, os.path.join(os.getcwd(), 'icone/pentagram.png'))

    def convert(self):
        from format_convert import AudioConverter
        ac = AudioConverter()
        ac.exec()

    def cd_ripper(self):
        from cd_ripper import CDRipperMainWindow
        cr = CDRipperMainWindow()
        cr.exec()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = Player()
    sys.exit(app.exec())