import os.path
import time

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QSplitter, QHBoxLayout, QWidget, QFileDialog, QLineEdit,
                             QDateEdit, QListWidget, QApplication, QPushButton, QPlainTextEdit,
                             QStyle, QRadioButton, QLabel, QProgressBar, QCalendarWidget, QTabWidget)
from PyQt6.QtGui import QPixmap

from utils import exitBtn, center_in_parent
class MusicIndexDlg(QDialog):
    #dialogReady = pyqtSignal()
    def __init__(self, parent, music, last_folder):
        super(MusicIndexDlg, self).__init__(parent)

        self.setWindowTitle('Catalogo MP3')
        center_in_parent(self, parent, 700, 500)

        self.last_folder = last_folder

        self.music = music
        v = QVBoxLayout(self)
        self.prog = QLabel('')
        self.b1 = QPushButton('...', self)
        self.b1.setMaximumWidth(60)
        self.b1.clicked.connect(self.index)
        h0 = QHBoxLayout()
        h0.addWidget(self.prog)
        h0.addWidget(self.b1)
        self.artists = QListWidget(self)
        self.artists.setSortingEnabled(True)
        self.artists.addItem('artisti')
        self.artists.itemSelectionChanged.connect(self.artist_changed)

        self.albums = QListWidget(self)
        self.albums.setSortingEnabled(False)
        self.albums.addItem('album')
        self.albums.itemSelectionChanged.connect(self.album_changed)

        splitter1 = QSplitter(self)
        splitter1.setOrientation(Qt.Orientation.Horizontal)
        splitter1.addWidget(self.artists)
        splitter1.addWidget(self.albums)

        self.tracks = QListWidget(self)
        self.tracks.setSortingEnabled(False)
        self.tracks.addItem('tracce')
        self.tracks.doubleClicked.connect(self.play)

        splitter2 = QSplitter(self)
        splitter2.setOrientation(Qt.Orientation.Vertical)
        splitter2.addWidget(splitter1)
        self.pix = QLabel()
        self.pix.setMinimumSize(200, 200)
        h = QHBoxLayout()
        h.addWidget(self.pix)
        h.addWidget(self.tracks)
        wd = QWidget()
        wd.setLayout(h)
        splitter2.addWidget(wd)  #self.tracks)

        v.addLayout(h0)
        v.addWidget(splitter2)

    def artist_changed(self):
        items = self.artists.selectedItems()
        if len(items) > 0:
            self.albums.clear()
            t = items[0].text()
            albums = self.music.find_albums(t)
            for a in albums:
                self.albums.addItem(a)

    def album_changed(self):
        items = self.albums.selectedItems()
        if len(items) > 0:
            self.tracks.clear()
            t = items[0].text()
            tracks = self.music.find_tracks(t)
            pic = self.music.find_pic(t)
            qp = QPixmap()
            qp.loadFromData(pic)
            self.pix.setPixmap(qp.scaled(self.pix.size(), Qt.AspectRatioMode.KeepAspectRatio))

            self.tracks.addItems(a for a in tracks)
            #for a in tracks:
            #    self.tracks.addItem(a)

    '''
    def showEvent(self, event):
        super(MusicIndexDlg, self).showEvent(event)
        while self.isVisible() is False:
            time.sleep(0.1)
        QApplication.processEvents()
        time.sleep(2)

        self.dialogReady.emit()
    '''


    def index(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder', self.last_folder, options=QFileDialog.Option.DontUseNativeDialog)
        if folder != '':
            self.music.index(self.print, folder)
            v = self.music.get_artists()
            self.artists.clear()
            for a in v:
                self.artists.addItem(a)
        return

        self.music.index(self.print)
        self.print('Terminato')
        v = self.music.get_artists()
        for a in v:
            self.artists.addItem(a)

    def print(self, t):
        self.prog.setText(t)
        QApplication.processEvents()

    def play(self):
        alb = self.albums.selectedItems()[0].text()
        trk = self.tracks.selectedItems()[0].text()
        t = trk + '@' + alb
        tt = self.music.tracks.name[t]
        self.parent().open_file(tt['file'])

        a = 0

    @staticmethod
    def run(parent, music=None, last_folder=''):
        dlg = MusicIndexDlg(parent, music, last_folder)

        if dlg.exec() == 1:
            return 1
        return 0

    def Ok(self):
        self.done(1)

    def Annulla(self):
        self.done(0)

class RadioDlg(QDialog):
    def __init__(self, parent, dict):
        super(RadioDlg, self).__init__(parent)

        v = QVBoxLayout(self)
        self.list = QListWidget(self)
        v.addWidget(self.list)

        h = exitBtn(self)
        v.addLayout(h)

        for d in dict.keys():
            self.list.addItem(d)

    def Ok(self):
        self.done(1)

    def Annulla(self):
        self.done(0)

    @staticmethod
    def run(parent, dic):
        dlg = RadioDlg(parent, dic)
        if dlg.exec() == 1:
            items = dlg.list.selectedItems()
            if len(items) > 0:
                return items[0].text()
        return 0