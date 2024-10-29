import os
#import time

#vlc_path = os.path.join(os.getcwd(), 'exe/VLC')
#os.environ['PYTHON_VLC_LIB_PATH'] = os.path.join(vlc_path, 'libvlc.dll')

#import vlc
import sys
#import scrobbler

from PyQt6.QtWidgets import (QToolBar, QHBoxLayout, QMainWindow, QWidget, QLabel, QStackedWidget, QVBoxLayout,
            QApplication, QTabBar, QSplashScreen, QPushButton, QTextEdit, QSplitter, QToolBar)
from PyQt6.QtGui import QIcon, QPainter, QPen, QPixmap
from PyQt6.QtCore import Qt

from qframelesswindow import FramelessDialog, StandardTitleBar

from pyMyLib.qtUtils import informMessage
from pyMyLib.utils import iniConf
from dialogs import RadioDlg, MusicIndexDlg, MusicPlayerDlg, slider_style, eq_slider_style

'''
https://streamurl.link/ per trovare stazioni radio
'''

class MyTitleBar(StandardTitleBar):
    def __init__(self, parent):
        super().__init__(parent)

        self.setTitle("Media Player")
        self.setIcon(QIcon(os.path.join(os.getcwd(), 'icone/player.ico')))
        self.maxBtn.hide()

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
        self.dlg.setMinimumWidth(500)
        self.tab.addWidget(self.dlg)


        rd = RadioDlg(self)
        self.tab.addWidget(rd)

        self.ply = MusicPlayerDlg(self)
        #self.tab.addTab(self.ply, '')
        self.tab.addWidget(self.ply)
        #self.tab.setTabIcon(2, QIcon(os.path.join(os.getcwd(), 'icone/stereo.png')))
        #self.tab.setTabToolTip(2, 'player')

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


class MyTitleBar2(StandardTitleBar):
    def __init__(self, parent):
        super().__init__(parent)

        self.setTitle('pippo')
        self.setIcon(QIcon(QPixmap('prova.ico')))

        tb = QToolBar()
        bt1 = QPushButton()
        bt1.setText("aa")
        #bt1.clicked.connect(parent.aaa)
        bt1.setMaximumWidth(35)
        bt1.setMaximumHeight(20)
        tb.addWidget(bt1)
        te = QTextEdit()
        te.setMaximumHeight(20)
        tb.addWidget(te)

        lay = self.layout()
        lay.insertSpacing(3, 5)

        #lay.insertWidget(4, tb)
        a =0


class MyDialog(FramelessDialog):
    def __init__(self):
        super().__init__()
        #cwd = os.getcwd()

        #self.setTitleBar(MyTitleBar(self))
        #self.titleBar.raise_()

        self.ini = iniConf('music_player')

        self.splash = None
        '''
        f = os.path.join(os.getcwd(),  './icone/splash.bmp')
        if os.path.isfile(f):
            self.splash = QSplashScreen(QPixmap(f))
            self.splash.show()
        '''

        self.create_ui()

        if self.splash is not None:
            self.splash.close()

        self.show()


    def create_ui(self):

        #self.setTitleBar2(MyTitleBar(self))
        #self.titleBar.raise_()
        v = QVBoxLayout(self)
        v.addSpacing(20)
        self.sp = QSplitter(self)
        self.sp.setOrientation(Qt.Orientation.Vertical)
        self.sp.addWidget(QTextEdit())

        v.addWidget(self.sp)
        self.show()
if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = Player()
    sys.exit(app.exec())