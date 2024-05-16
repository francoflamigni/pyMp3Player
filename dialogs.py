from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QSplitter, QHBoxLayout, QWidget, QFileDialog, QLabel, QStyle,
                             QListWidget, QApplication, QPushButton, QTableWidget, QLineEdit, QTableWidgetItem,
                             QHeaderView)

import scrobbler
from pyradios import RadioBrowser

from utils import center_in_parent

'''
https://github.com/andreztz/pyradios/tree/main/pyradios
'''
def poll_radio(url):
    #sst = streamscrobbler()

    stationinfo = scrobbler.get_server_info(url)


    ##metadata is the bitrate and current song
    metadata = stationinfo.get("metadata")

    ## status is the integer to tell if the server is up or down, 0 means down, 1 up, 2 means up but also got metadata.
    status = stationinfo.get("status")

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

    def set_artists(self):
        self.artists.clear()
        self.artists.addItems(a for a in self.music.get_artists())

    def index(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder', self.last_folder, options=QFileDialog.Option.DontUseNativeDialog)
        if folder != '':
            self.music.index(self.print, folder)
            self.set_artists()

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

        v = [self.music.tracks.name[trk + '@' + alb] for trk in trks]
        self.parent.open_file(v)


class RadioDlg(QDialog):
    def __init__(self, parent, dict):
        super(RadioDlg, self).__init__(parent)
        self.radios = dict
        self.wparent = parent

        v = QVBoxLayout(self)

        h = QHBoxLayout()
        lab = QLabel('Ricerca', self)
        self.ed = QLineEdit(self)
        b0 = QPushButton(self)
        b0.clicked.connect(self.search)
        h.addWidget(lab)
        h.addWidget(self.ed)
        h.addWidget(b0)

        sp = QSplitter(self)
        sp.setOrientation(Qt.Orientation.Vertical)

        v1 = QVBoxLayout()
        v1.addLayout(h)
        self.table = QTableWidget(self)
        v1.addWidget(self.table)

        w = QWidget()
        w.setLayout(v1)
        sp.addWidget(w)

        self.favorites = QListWidget(self)
        self.favorites.doubleClicked.connect(self.play)
        sp.addWidget(self.favorites)
        v.addWidget(sp)

        if dict is not None:
            for d in dict.keys():
                self.favorites.addItem(d)

    def search(self):
        src = self.ed.text()
        if len(src) > 0:
            rb = RadioBrowser()
            a = rb.search(name=src, name_exact=False, hidebroken=True)
            self.fill_table(a)

    def fill_table(self, list):
        self.table.setRowCount(0)
        self.wparent.stop()
        if len(list) == 0:
            return
        radios = []
        for l in list:
            if 'ref' in l['url']:
                continue
            f_icon = l['favicon']
            pix = scrobbler.get_thumbnail(f_icon)
            r = RadioStation(l['name'], l['url'], l['bitrate'], l['country'])
            radios.append(r)

        fields = ['Nome', 'bitrate', 'paese', ' ']
        self.table.setColumnCount(len(fields))
        self.table.setHorizontalHeaderLabels(fields)
        self.table.cellClicked.connect(self.onCellClicked)

        for r in radios:
            numRows = self.table.rowCount()

            self.table.insertRow(numRows)
            qi = QTableWidgetItem(r.name)
            qi.setData(Qt.ItemDataRole.UserRole, r)
            self.table.setItem(numRows, 0, qi)
            self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
            self.table.setItem(numRows, 1, QTableWidgetItem(r.bitrate))
            self.table.setItem(numRows, 2, QTableWidgetItem(r.paese))
            qi1 = QTableWidgetItem()
            qi1.setIcon(self.style().standardIcon(getattr(QStyle.StandardPixmap, 'SP_MediaPlay')))
            self.table.setItem(numRows, 3, qi1)
            self.table.setColumnWidth(3, 10)

    def onCellClicked(self, nr, nc):
        if nc == 3:
            b = self.wparent
            b.stop()
            qi = self.table.item(0, 0)
            dat = qi.data(Qt.ItemDataRole.UserRole)
            url = dat.url
            b.open_radio(url)

    def play(self):
        rad = self.favorites.selectedItems()[0].text()
        url = self.radios[rad]
        self.wparent.open_radio(url)

class RadioStation:
    def __init__(self, name='', url='', bitrate=0, paese=''):
        self.name = name
        self.url = url
        self.bitrate = bitrate
        self.paese = paese

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
