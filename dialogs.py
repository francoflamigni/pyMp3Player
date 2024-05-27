from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QTextCursor, QIcon
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QSplitter, QHBoxLayout, QWidget, QFileDialog, QLabel, QStyle,
                             QListWidget, QApplication, QPushButton, QTableWidget, QLineEdit, QTableWidgetItem,
                             QHeaderView, QPlainTextEdit, QAbstractItemView, QMenu, QTabWidget, QListWidgetItem)

import scrobbler
from pyradios import RadioBrowser
from googletrans import Translator

from mp3_tag import Music

from utils import center_in_parent, yesNoMessage, waitCursor
from threading import Thread
from myShazam import myShazam

'''
https://github.com/andreztz/pyradios/tree/main/pyradios
'''


def poll_radio(url):
    #sst = streamscrobbler()

    stationinfo = scrobbler.get_server_info(url)


    #metadata is the bitrate and current song
    metadata = stationinfo.get("metadata")

    # status is the integer to tell if the server is up or down, 0 means down, 1 up, 2 means up but also got metadata.
    status = stationinfo.get("status")


class myList(QListWidget):
    def __init__(self, parent, txt=''):
        super().__init__(parent)
        self.wparent = parent
        if txt != '':
            self.addItem(txt)
        self.setMouseTracking(True)

    def mouseMoveEvent(self, event):
        self.setFocus()
        super(QListWidget, self).mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.wparent.contextMenu(event.pos(), self)
        super(QListWidget, self).mousePressEvent(event)


class MusicIndexDlg(QDialog):
    def __init__(self, parent, music, last_folder):
        super(MusicIndexDlg, self).__init__(parent)
        self.parent = parent
        self.shaz = False

        self.setWindowTitle('Catalogo MP3')
        center_in_parent(self, parent, 700, 500)

        self.last_folder = last_folder

        self.music = music
        v = QVBoxLayout(self)
        self.prog = QLabel('')
        self.b1 = QPushButton('...', self)
        self.b1.setMaximumWidth(60)
        self.b1.clicked.connect(self.index2)

        b2 = QPushButton('search', self)
        b2.setMaximumWidth(60)
        b2.clicked.connect(self.search)

        h0 = QHBoxLayout()
        h0.addWidget(self.prog)
        h0.addWidget(self.b1)
        h0.addWidget(b2)

        self.artists = myList(self, 'artisti')
        self.artists.setSortingEnabled(True)
        self.artists.itemSelectionChanged.connect(self.artist_changed)

        self.albums = myList(self, 'album')
        self.albums.setSortingEnabled(False)
        self.albums.itemSelectionChanged.connect(self.album_changed)
        self.albums.doubleClicked.connect(self.play_album)

        splitter1 = QSplitter(self)
        splitter1.setOrientation(Qt.Orientation.Horizontal)
        splitter1.addWidget(self.artists)
        splitter1.addWidget(self.albums)

        self.tracks = myList(self, 'tracce')
        self.tracks.setSortingEnabled(False)
        self.tracks.doubleClicked.connect(self.play_song)

        splitter2 = QSplitter(self)
        splitter2.setOrientation(Qt.Orientation.Vertical)
        splitter2.addWidget(splitter1)
        self.tab = QTabWidget(self)
        self.tab.setTabPosition(QTabWidget.TabPosition.West)
        self.tab.tabBarDoubleClicked.connect(self.play_playlist)

        self.pix = QLabel()
        self.pix.setMinimumSize(200, 200)
        self.plst = myList(self)
        self.plst.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.plst.setMinimumSize(200, 200)
        self.tab.addTab(self.pix, 'cover')
        self.tab.addTab(self.plst, 'playlist')

        self.h = QHBoxLayout()
        self.h.addWidget(self.tab)
        self.h.addWidget(self.tracks)
        wd = QWidget()
        wd.setLayout(self.h)
        splitter2.addWidget(wd)

        v.addLayout(h0)
        v.addWidget(splitter2)
        self.res = music.init(last_folder)
        if self.res == music.INDEX_LOADED:
            self.set_artists()
        elif self.res == music.NO_FOLDER or self.res == music.NO_FILE:
            self.print('La cartella indicata non esiste o non contiene file')
        self.print(last_folder)

    def play_playlist(self, index):
        if index == 0:
            return
        v = [self.plst.item(i).data(Qt.ItemDataRole.UserRole) for i in range(len(self.plst))]
        self.parent.open_file(v)

    def contextMenu(self, p, wd):
        ctx = QMenu(self)
        if wd == self.artists:
            return
        it = wd.itemAt(p)
        if it is None:
            return
        p1 = wd.mapToGlobal(p)
        if wd == self.plst:
            ctx.addAction("Rimuove tutti").triggered.connect(lambda x: self.remove_playlist('all'))
            ctx.addAction("Rimuove selezionati").triggered.connect(lambda x: self.remove_playlist('selected'))
        else:
            artist = self.artists.selectedItems()
            if len(artist) > 0:
                artist = artist[0].text()
            if wd == self.albums:
                album = it.text()
                track = ''
            else:
                album = self.albums.selectedItems()
                if len(album) > 0:
                    album = album[0].text()
                track = it.text()
            ctx.addAction("Aggiunge alla playlist").triggered.connect(lambda x: self.add_playlist(artist, album, track))

        ctx.exec(p1)

    def add_playlist(self, artist, album, track):
        if track != '':
            vi = [self.music.tracks.name[track + '@' + album]]
        else:
            trks = self.music.find_tracks(album, artist)
            vi = [self.music.tracks.name[trk + '@' + album] for trk in trks if trk]

        for p in vi:
            qi = QListWidgetItem(p.title)
            qi.setData(Qt.ItemDataRole.UserRole, p)
            self.plst.addItem(qi)

        a = 0

    def remove_playlist(self, type):
        if type == 'all':
            self.plst.clear()
        else:
            its = self.plst.selectedItems()
            rs = [self.plst.row(it) for it in its]
            for r in reversed(rs):
                self.plst.takeItem(r)
            a = 0

    def process(self):
        if self.res == Music.NO_INDEX or self.res == Music.OLD_INDEX:
            if yesNoMessage('indice non valido', "vuoi rigenerare l'indice?"):
                self.index(self.last_folder)

    def search(self):
        sel = mySearch.run(self.parent, self.music)
        if sel is None:
            return
        if 'artista' in sel:
            a = sel.split(':')[1].strip()
            self._select_artist(a)
        elif 'album' in sel:
            a1 = sel.split(':')[1].strip()
            a2 = a1.split(';')
            artist = a2[0].strip()
            self._select_artist(artist)
            album = a2[1].strip()
            self._select_album(album)
        elif 'traccia' in sel:
            a1 = sel.split(':')[1].strip()
            a2 = a1.split(';')
            artist = a2[0].strip()
            self._select_artist(artist)
            album = a2[1].strip()
            self._select_album(album)
            track = a2[2].strip()
            self._select_track(track)

    def _select_artist(self, name):
        item = self.artists.findItems(name, Qt.MatchFlag.MatchContains)
        if item is not None and len(item) > 0:
            item[0].setSelected(True)
            self.artists.scrollToItem(item[0])

    def _select_album(self, name):
        item = self.albums.findItems(name, Qt.MatchFlag.MatchContains)
        if item is not None and len(item) > 0:
            item[0].setSelected(True)
            self.albums.scrollToItem(item[0])

    def _select_track(self, name):
        item = self.tracks.findItems(name, Qt.MatchFlag.MatchContains)
        if item is not None and len(item) > 0:
            item[0].setSelected(True)
            self.tracks.scrollToItem(item[0])

    '''
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_F2:
                self.lyric_song()
            elif key == Qt.Key.Key_F3:
                self.find_song()
        if event.type == QEvent.Type.MouseMove:
            self.artists.setFocus()
            #obj.setFocus()
            #obj.s
            a = 0

        return super(MusicIndexDlg, self).eventFilter(obj, event)
    '''

    def lyric_song(self):
        artists = self.artists.selectedItems()
        if len(artists) != 0:
            artist = artists[0].text()
            tracks = self.tracks.selectedItems()
            if len(tracks) != 0:
                track = tracks[0].text()
                txt = scrobbler.song_text(artist, track)
                if len(txt) > 0:
                    lyricsDlg.run(self.parent, txt, track)

    def find_song(self, time=5):
        if self.shaz:
            return
        self.shaz = True
        ms = myShazam(self._find_song, time=time)
        waitCursor(True)
        ms.guess()
    def _find_song(self, out):
        mes = ''
        if isinstance(out, dict):
            if 'track' in out.keys():
                tr = out['track']
                title = tr['title']
                artist = tr['subtitle']
                meta = tr['sections'][0]['metadata'][0]['text']
                mes = 'Artista: ' + artist + '\n'
                mes += 'Album: ' + meta + '\n'
                mes += 'Titolo: ' + title + '\n'
        elif isinstance(out, str):
            mes = out

        if len(mes) == 0:
            t = out['retryms'] / 1000
            if t < 10:
                self.shaz = False
                self.find_song(t)
                return
            mes = 'Non riconosciuta'

        waitCursor()
        infoDlg.run(self.parent, mes)
        self.shaz = False

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
        if len(items) > 0 and len(art) > 0:
            self.tracks.clear()
            trk_name = items[0].text()
            art_name = art[0].text()
            tracks = self.music.find_tracks(trk_name, art_name)
            pic = self.music.find_pic(trk_name, art_name)
            if pic is not None:
                qp = QPixmap()
                if qp.loadFromData(pic):
                    self.pix.setPixmap(qp.scaled(self.pix.size(), Qt.AspectRatioMode.KeepAspectRatio))
            else:
                self.pix.clear()

            self.tracks.addItems(a for a in tracks)

    def set_artists(self):
        self.artists.clear()
        self.artists.addItems(a for a in self.music.get_artists())

    def index2(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder', self.last_folder,
                                                  options=QFileDialog.Option.DontUseNativeDialog)
        self.index(folder)

    def index(self, folder=''):
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


class tableMenu(QTableWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.parent.contextMenu(event.pos(), type='radios')
        super(QTableWidget, self).mousePressEvent(event)

class listMenu(QListWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.parent.contextMenu(event.pos(), type='favorites')
        super(QListWidget, self).mousePressEvent(event)

class RadioDlg(QDialog):
    def __init__(self, parent):
        super(RadioDlg, self).__init__(parent)
        self.ini = parent.ini
        self.wparent = parent

        v = QVBoxLayout(self)

        h = QHBoxLayout()
        lab = QLabel('Ricerca', self)
        self.ed = QLineEdit(self)
        b0 = QPushButton(self)
        b0.clicked.connect(self.search)
        self.ed.returnPressed.connect(self.search)
        h.addWidget(lab)
        h.addWidget(self.ed)
        h.addWidget(b0)

        sp = QSplitter(self)
        sp.setOrientation(Qt.Orientation.Vertical)

        v1 = QVBoxLayout()
        v1.addLayout(h)
        self.table = tableMenu(self)
        v1.addWidget(self.table)

        w = QWidget()
        w.setLayout(v1)
        sp.addWidget(w)

        self.favorites = listMenu(self)
        self.favorites.doubleClicked.connect(self.play)
        sp.addWidget(self.favorites)
        v.addWidget(sp)

        rd = self.ini.get('radio')
        if rd is not None:
            for d in rd.keys():
                self.favorites.addItem(d)

    def search(self):
        src = self.ed.text()
        if len(src) > 0:
            rb = RadioBrowser()
            a = rb.search(name=src, name_exact=False, hidebroken=True)
            self.fill_table(a)

    def load_icons(self, list):
        row = 0
        for l in list:
            if 'ref' in l['url']:
                continue
            im = scrobbler.get_thumbnail(l['favicon'])
            if im is not None:
                qii = self.table.item(row, 1)
                qp = QPixmap()
                qp.loadFromData(im)
                qii.setIcon(QIcon(qp))
            row += 1
        a = 0

    def fill_table(self, rList):
        self.table.setRowCount(0)
        if len(rList) == 0:
            return
        radios = []
        for l in rList:
            if 'ref' in l['url']:
                continue
            r = RadioStation(l['name'], l['url'], None, l['country'])
            radios.append(r)

        searcher = Thread(target=self.load_icons, args=(rList,))
        searcher.start()

        fields = ['Nome', 'icon', 'paese', ' ']
        self.table.setColumnCount(len(fields))
        self.table.setHorizontalHeaderLabels(fields)
        self.table.cellClicked.connect(self.onCellClicked)

        horizontalHeader = self.table.horizontalHeader()
        horizontalHeader.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        horizontalHeader.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        horizontalHeader.resizeSection(1, 30)
        horizontalHeader.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        horizontalHeader.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        horizontalHeader.resizeSection(3, 30)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)


        for r in radios:
            numRows = self.table.rowCount()

            self.table.insertRow(numRows)
            name = r.name
            if len(name) > 25:
                name = name[:25]
            qi = QTableWidgetItem(name)
            qi.setToolTip(r.url)
            qi.setData(Qt.ItemDataRole.UserRole, r)
            self.table.setItem(numRows, 0, qi)

            qii = QTableWidgetItem()
            if r.ico is not None:
                qp = QPixmap()
                qp.loadFromData(r.ico)
                qii.setIcon(QIcon(qp))
            self.table.setItem(numRows, 1, qii)
            self.table.setItem(numRows, 2, QTableWidgetItem(r.paese))
            qi1 = QTableWidgetItem()
            qi1.setIcon(self.style().standardIcon(getattr(QStyle.StandardPixmap, 'SP_MediaPlay')))
            self.table.setItem(numRows, 3, qi1)
            self.table.setColumnWidth(3, 10)

    def contextMenu(self, p, type='radios'):
        ctx = QMenu(self)
        if type == 'radios':
            it = self.table.itemAt(p)
            if it is None:
                return
            if it.column() != 0:
                it = self.table.item(it.row(), 0)
            ctx.addAction("Aggiunge ai preferiti").triggered.connect(lambda x: self.add_favourites(it))
            p1 = self.table.mapToGlobal(p)
        else:
            it = self.favorites.itemAt(p)
            ctx.addAction("Rimuove dai preferiti").triggered.connect(lambda x: self.del_favourites(it))
            p1 = self.favorites.mapToGlobal(p)

        ctx.exec(p1)

    def add_favourites(self, it):
        r = it.data(Qt.ItemDataRole.UserRole)
        if r is None:
            return
        nome = r.name
        k = self.favorites.findItems(nome, Qt.MatchFlag.MatchExactly)
        rd = self.ini.get('radio')

        if len(k) > 0:
            if yesNoMessage('Sostituzione', 'Esiste già una emittente di nome ' + nome + ' sostituirla?'):
                self.del_favourites(k[0])
            else:
                return

        rd[nome] = r.url
        self.ini.set_sez('radio', rd)
        self.ini.save()
        self.favorites.addItem(nome)
        a = 0

    def del_favourites(self, it):
        row = self.favorites.row(it)
        qi = self.favorites.takeItem(row)
        nome = qi.text()

        rd = self.ini.get('radio')
        del rd[nome]
        self.ini.set_sez('radio', rd)
        self.ini.save()
        a = 0

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
        rd = self.ini.get('radio')
        url = rd[rad]
        self.wparent.open_radio(url)

class RadioStation:
    def __init__(self, name='', url='', ico=None, paese=''):
        self.name = name
        self.url = url
        self.ico = ico
        #self.bitrate = bitrate
        self.paese = paese

class myPlainText(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setReadOnly(True)
        self.slave = None

        self.last_position = self.verticalScrollBar().sliderPosition()
        self.verticalScrollBar().valueChanged.connect(self.handle_value_changed)
        self.cur = QTextCursor(self.document())

    def setSlave(self, slave):
        self.slave = slave
    def setText(self, txt):
        self.cur.movePosition(QTextCursor.MoveOperation.End)
        self.cur.insertText(txt)
    def handle_value_changed(self, position):
        if self.slave is None:
            return
        self.slave.verticalScrollBar().setValue(position)

class lyricsDlg(QDialog):
    def __init__(self, parent, txt, track=''):
        super(lyricsDlg, self).__init__(parent)
        self.parent = parent
        self.txt = txt
        center_in_parent(self, parent, 600, 500)
        self.setWindowTitle(track)

        v = QVBoxLayout(self)
        self.h = QHBoxLayout()
        self.txt_box = myPlainText(self)
        self.tr = Translator()
        lang = self.tr.detect(txt).lang

        self.txt_box.setText(txt)
        self.h.addWidget(self.txt_box)
        v.addLayout(self.h)

        if lang != 'it':
            self.bt = QPushButton(self)
            self.bt.setText('Traduci')
            self.bt.clicked.connect(self.traduci)
            v.addWidget(self.bt)

    def traduci(self):
        tr_box = myPlainText(self)
        self.txt_box.setSlave(tr_box)
        self.h.addWidget(tr_box)
        txt1 = self.tr.translate(self.txt, 'it')
        self.bt.hide()

        tr_box.setText(txt1.text)
        sz = self.size()
        sz.setWidth(sz.width() * 2)
        self.resize(sz)
        a = 0

    @staticmethod
    def run(parent, txt, track=''):
        dlg = lyricsDlg(parent, txt, track)
        dlg.exec()


class infoDlg(QDialog):
    def __init__(self, parent, txt):
        super(infoDlg, self).__init__(parent)
        self.parent = parent
        self.txt = txt
        center_in_parent(self, parent, 300, 100)
        self.setWindowTitle('Shazam')

        v = QVBoxLayout(self)
        self.txt_box = myPlainText(self)

        self.txt_box.setText(txt)
        v.addWidget(self.txt_box)

    @staticmethod
    def run(parent, txt):
        dlg = infoDlg(parent, txt)
        dlg.exec()

class mySearch(QDialog):
    def __init__(self, parent, music):
        super(mySearch, self).__init__(parent)
        center_in_parent(self, parent, 600, 400)


        self.parent = parent
        self.music = music

        self.ed = QLineEdit(self)
        b1 = QPushButton('...', self)
        b1.setMaximumWidth(50)
        b1.clicked.connect(self.search)
        h = QHBoxLayout()
        h.addWidget(self.ed)
        h.addWidget(b1)

        self.list = QListWidget(self)
        self.list.doubleClicked.connect(self.selection)

        v = QVBoxLayout(self)
        v.addLayout(h)
        v.addWidget(self.list)
        self.selected = None

    def search(self):
        txt = self.ed.text().lower()
        if len(txt) == 0:
            return
        mes = []

        a1 = [k for k in self.music.artists.name.keys() if k is not None and txt in k.lower()]
        kk = 1
        if len(a1) > 0:
            for a in a1:
                mes.append(str(kk) + ' artista: ' + a + '\n')
                kk += 1
        a2 = [self.music.albums.title[k] for k in self.music.albums.title.keys() if k is not None and txt in k.lower()]
        if len(a2) > 0:
            for a in a2:
                art = self.music.find_artist_by_album(a.id)
                mes.append(str(kk) + ' album: ' + art + ';' + a.title + '\n')
                kk += 1
        a3 = [k for k in self.music.tracks.name.values() if k is not None and txt in k.title.lower()]
        if len(a3) > 0:
            for a in a3:
                mes.append(str(kk) + ' traccia: ' + a.artist + ';' + a.album + ';' + a.title + '\n')
                kk += 1

        self.list.clear()
        self.list.addItems(mes)


    def selection(self):
        s = self.list.selectedItems()
        if len(s) > 0:
            self.selected = s[0].text()
            self.done(1)

    @staticmethod
    def run(parent, music):
        dlg = mySearch(parent, music)
        if dlg.exec() == 1:
            return dlg.selected
        return None

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
