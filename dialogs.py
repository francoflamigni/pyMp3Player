import os.path
import time

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QSplitter, QHBoxLayout, QWidget, QFileDialog, QLabel,
                             QListWidget, QApplication, QPushButton)
from PyQt6.QtGui import QPixmap

from utils import exitBtn, center_in_parent
class MusicIndexDlg(QDialog):
    def __init__(self, parent, music, last_folder):
        super(MusicIndexDlg, self).__init__(parent)
        self.parent = parent

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
        self.albums.doubleClicked.connect(self.play_album)

        splitter1 = QSplitter(self)
        splitter1.setOrientation(Qt.Orientation.Horizontal)
        splitter1.addWidget(self.artists)
        splitter1.addWidget(self.albums)

        self.tracks = QListWidget(self)
        self.tracks.setSortingEnabled(False)
        self.tracks.addItem('tracce')
        self.tracks.doubleClicked.connect(self.play_song)

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
        splitter2.addWidget(wd)

        v.addLayout(h0)
        v.addWidget(splitter2)
        if music.init(last_folder) is True:
            self.set_artists()
            self.print(last_folder)

    def artist_changed(self):
        items = self.artists.selectedItems()
        if len(items) > 0:
            self.albums.clear()
            self.tracks.clear()
            t = items[0].text()
            albums = self.music.find_albums(t)
            for a in albums:
                self.albums.addItem(a.title)

    def album_changed(self):
        items = self.albums.selectedItems()
        art = self.artists.selectedItems()
        if len(items) > 0:
            self.tracks.clear()
            t = items[0].text()
            if len(art) == 1:
                art_name = art[0].text()
            tracks = self.music.find_tracks(t, art_name)
            pic = self.music.find_pic(t)
            qp = QPixmap()
            qp.loadFromData(pic)
            self.pix.setPixmap(qp.scaled(self.pix.size(), Qt.AspectRatioMode.KeepAspectRatio))

            self.tracks.addItems(a for a in tracks)
            #for a in tracks:
            #    self.tracks.addItem(a)

    def set_artists(self):
        self.artists.clear()
        self.artists.addItems(a for a in self.music.get_artists())

    def index(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder', self.last_folder, options=QFileDialog.Option.DontUseNativeDialog)
        if folder != '':
            self.music.index(self.print, folder)
            self.set_artists()
            '''
            v = self.music.get_artists()
            self.artists.clear()
            for a in v:
                self.artists.addItem(a)
            '''

    def print(self, t):
        self.prog.setText(t)
        QApplication.processEvents()

    def play_song(self):
        alb = self.albums.selectedItems()[0].text()
        trk = self.tracks.selectedItems()[0].text()
        t = trk + '@' + alb
        tt = self.music.tracks.name[t]
        self.parent.open_file([tt])

    def play_album(self):
        sel_alb = self.albums.selectedItems()
        if sel_alb is None or len(sel_alb) == 0:
            return
        alb = sel_alb[0].text()
        trks = [self.tracks.item(row).text() for row in range(self.tracks.count())]
        '''
        for trk in trks:
            t = trk + '@' + alb
            tt = self.music.tracks.name[t]
        '''
        v = [self.music.tracks.name[trk + '@' + alb] for trk in trks]
        self.parent.open_file(v)
        #self.parent.open_file([tt])

        a = 0

class RadioDlg(QDialog):
    def __init__(self, parent, dict):
        super(RadioDlg, self).__init__(parent)
        self.radios = dict
        self.parent = parent

        #self.lab = QLabel('', self)
        v = QVBoxLayout(self)
        #v.addWidget(self.lab)
        self.list = QListWidget(self)
        self.list.doubleClicked.connect(self.play)
        v.addWidget(self.list)

        #h = exitBtn(self)
        #v.addLayout(h)

        if dict is not None:
            for d in dict.keys():
                self.list.addItem(d)

    '''
    def print(self, mes):
        self.lab.setText(mes)
        QApplication.processEvents()
    '''

    def play(self):
        rad = self.list.selectedItems()[0].text()
        url = self.radios[rad]
        self.parent.open_radio(url)

    '''
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
    '''

def slider_style():
    QSS = """
    QSlider {
        min-height: 20px;
    }

    QSlider::groove:horizontal {
        border: 0px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #888, stop:1 #ddd);
        height: 12px;
        border-radius: 10px;
    }

    QSlider::handle {
        background: qradialgradient(cx:0, cy:0, radius: 1.2, fx:0.35,
                                    fy:0.3, stop:0 #eef, stop:1 #002);
        height: 10px;
        width: 20px;
        border-radius: 10px;
    }

    QSlider::sub-page:horizontal {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00C, stop:1 #00C);
        border-top-left-radius: 7px;
        border-bottom-left-radius: 7px;
    }

    """
    return QSS

def eq_slider_style():
    QSS = """
    QSlider {
        min-height: 90px;
        border: 5px;
    }

    QSlider::groove:horizontal {
        border: 2px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #888, stop:1 #ddd);
        height: 6px;
        border-radius: 3px;
    }

    QSlider::handle {
        background: qradialgradient(cx:0, cy:0, radius: 1.2, fx:0.35,
                                    fy:0.3, stop:0 #eef, stop:1 #002);
        height: 4px;
        width: 2px;
        border-radius: 2px;
    }



    """
    return QSS