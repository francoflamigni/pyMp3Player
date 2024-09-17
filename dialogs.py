import os
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QTextCursor, QIcon, QCursor
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QSplitter, QHBoxLayout, QWidget, QFileDialog, QLabel, QStyle,
                             QListWidget, QApplication, QPushButton, QTableWidget, QLineEdit, QTableWidgetItem,
                             QHeaderView, QPlainTextEdit, QAbstractItemView, QMenu, QTabWidget, QListWidgetItem,
                             QCheckBox)

import scrobbler
from pyradios import RadioBrowser
from googletrans import Translator

from mp3_tag import Music

from pyMyLib.qtUtils import exitBtn, waitCursor, center_in_parent, set_background, yesNoMessage, informMessage
from pyMyLib.utils import iniConf


from threading import Thread
from myShazam import myShazam

'''
https://github.com/andreztz/pyradios/tree/main/pyradios
'''

class myList(QListWidget):
    def __init__(self, parent, txt=''):
        super().__init__(parent)
        self.wparent = parent
        self.itc = None
        if txt != '':
            self.addItem(txt)
        self.setMouseTracking(True)

    def setSelCur(self, it):
        if self.itc != it:
            self.itc = it

    def mouseMoveEvent(self, event):
        if self.hasFocus() is False:
            self.setFocus()
            self.unsetCursor()
            super(QListWidget, self).mouseMoveEvent(event)
            return

        it = self.itemAt(event.pos())
        if self.itc is not None:
            if it != self.itc:
                self.unsetCursor()
            else:
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        super(QListWidget, self).mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            it = self.itemAt(event.pos())
            if it is not None:
                p = self.mapToGlobal(event.pos())
                self.wparent.contextMenu(p, self, it)
        elif event.button() == Qt.MouseButton.LeftButton:
            it = self.itemAt(event.pos())
            if it == self.itc:
                try:
                    self.wparent.play_item(self)
                except:
                    pass
        super(QListWidget, self).mousePressEvent(event)


class MusicIndexDlg(QDialog):
    def __init__(self, parent):
        super(MusicIndexDlg, self).__init__(parent)
        self.wparent = parent
        self.shaz = False
        self.play_cur = False

        self.setWindowTitle('Catalogo MP3')
        center_in_parent(self, parent, 700, 500)
        self.setObjectName("mp3_widget")
        set_background(self)
        #self.setStyleSheet("QWidget#mp3_widget {background-color: #c0c0c0}")

        ini = iniConf('music_player')
        self.last_folder = ini.get('CONF', 'last_folder')

        self.music = Music(parent)
        v = QVBoxLayout(self)
        self.prog = QLabel('')

        self.b1 = QPushButton(self)
        self.b1.setIcon(QIcon(os.path.join(os.getcwd(), 'icone/folder_open.png')))
        self.b1.setMaximumWidth(30)
        self.b1.clicked.connect(self.index2)

        b2 = QPushButton(self)
        b2.setIcon(QIcon(os.path.join(os.getcwd(), 'icone/search.png')))
        b2.setMaximumWidth(30)
        b2.clicked.connect(self.search)

        b3 = QPushButton(self)
        b3.setIcon(QIcon(os.path.join(os.getcwd(), 'icone/config.png')))
        b3.setMaximumWidth(30)
        b3.clicked.connect(self.config)

        bi = QPushButton('?', self)
        bi.setMaximumWidth(30)
        bi.clicked.connect(self.info)

        h0 = QHBoxLayout()
        h0.addWidget(self.b1)
        h0.addWidget(self.prog)
        h0.addWidget(b2)
        h0.addWidget(b3)
        h0.addWidget(bi)

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
        self.tracks.itemSelectionChanged.connect(self.track_changed)
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
        self.tab.addTab(self.pix, '')
        self.tab.setTabIcon(0, QIcon(os.path.join(os.getcwd(), 'icone/cover.png')))
        self.tab.setTabToolTip(0, 'copertina')

        self.tab.addTab(self.plst, '')
        self.tab.setTabIcon(1, QIcon(os.path.join(os.getcwd(), 'icone/playlist.png')))
        self.tab.setTabToolTip(1, 'playlist')

        self.h = QHBoxLayout()
        self.h.addWidget(self.tab)
        self.h.addWidget(self.tracks)
        wd = QWidget()
        wd.setLayout(self.h)
        splitter2.addWidget(wd)

        v.addLayout(h0)
        v.addWidget(splitter2)
        self.res = self.music.init(self.last_folder)
        if self.res == self.music.INDEX_LOADED:
            self.set_artists()
        elif self.res == self.music.NO_FOLDER or self.res == self.music.NO_FILE:
            self.print('La cartella indicata non esiste o non contiene file')
        self.print(self.last_folder)

    def info(self):
        informMessage('Music Player\nGestione mp3\nVersione 1.3\n21 Giugno 2024', 'Music Player', 15, True, os.path.join(os.getcwd(), 'icone/pentagram.ico'))

    def config(self):
        configDlg.run(self)

    def play_playlist(self, index):
        if index == 0:
            return
        v = [self.plst.item(i).data(Qt.ItemDataRole.UserRole) for i in range(len(self.plst))]
        self.wparent.open_file(v)

    def contextMenu(self, p, wd, it):
        ctx = QMenu(self)
        if wd == self.artists:
            return
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

        ctx.exec(p)

    def play_item(self, lst):
        if lst == self.albums:
            self.play_album()
        elif lst == self.tracks:
            self.play_song()

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

        tot_time = 0
        for r in range(self.plst.count()):
            qi = self.plst.item(r)
            p = qi.data(Qt.ItemDataRole.UserRole)
            tot_time += p.tm_sec

        h = int(tot_time / 3600)
        m = int((tot_time - h * 3600) / 60)
        s = int(tot_time - h * 3600 - m * 60)
        tm = ''
        if h != 0:
            tm += str(h) + 'h '
        tm += str(m) + 'm ' + str(s) + 's'

        mes = 'playlist brani: ' + str(self.plst.count()) + ' durata: ' + tm
        self.tab.setTabToolTip(1, mes)


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

    ''' Cerca canzone artista album'''
    def search(self):
        sel = mySearch.run(self.wparent, self.music)
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


    def lyric_song(self):
        artists = self.artists.selectedItems()
        if len(artists) != 0:
            artist = artists[0].text()
            tracks = self.tracks.selectedItems()
            if len(tracks) != 0:
                track = tracks[0].text()
            elif self.wparent.tab.currentIndex() == 2:
                wd = self.wparent
                track = wd.tracks[wd.index].title
            txt = scrobbler.song_text(artist, track)
            if len(txt) > 0:
                lyricsDlg.run(self.wparent, txt, track)

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
        infoDlg.run(self.wparent, mes)
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
            self.albums.setSelCur(items[0])
            self.tracks.clear()
            trk_name = items[0].text()
            art_name = art[0].text()
            tracks = self.music.find_tracks(trk_name, art_name)
            self.get_track_pix(trk_name, art_name, self.pix)
            self.tracks.addItems(a for a in tracks)

    def get_track_pix(self, trk_name, art_name, pix):
        pic = self.music.find_pic(trk_name, art_name)
        if pic is not None:
            qp = QPixmap()
            if qp.loadFromData(pic):
                pix.setPixmap(qp.scaled(pix.size(), Qt.AspectRatioMode.KeepAspectRatio))
        else:
            pix.clear()

    def track_changed(self):
        items = self.tracks.selectedItems()
        if len(items) > 0:
            self.tracks.setSelCur(items[0])

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
        self.wparent.open_file([tt])

    def play_album(self):
        sel_alb = self.albums.selectedItems()
        if sel_alb is None or len(sel_alb) == 0:
            return
        alb = sel_alb[0].text()
        trks = [self.tracks.item(row).text() for row in range(self.tracks.count())]

        v = [self.music.tracks.name[trk + '@' + alb] for trk in trks]
        self.wparent.open_file(v)


class tableMenu(QTableWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.wparent = parent

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            p = event.pos()
            it = self.itemAt(p)
            self.wparent.contextMenu(self.mapToGlobal(p), self, it)
        super(QTableWidget, self).mousePressEvent(event)


class RadioDlg(QDialog):
    def __init__(self, parent):
        super(RadioDlg, self).__init__(parent)
        self.ini = parent.ini
        self.wparent = parent
        self.setObjectName("radio_widget")
        set_background(self)
        #self.setStyleSheet("QWidget#radio_widget {background-color: black}")

        v = QVBoxLayout(self)

        h = QHBoxLayout()
        self.ed = QLineEdit(self)
        b0 = QPushButton(self)
        b0.setIcon(QIcon(os.path.join(os.getcwd(), 'icone/search.png')))
        b0.clicked.connect(self.search)
        self.ed.returnPressed.connect(self.search)
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

        self.favorites = myList(self)
        self.favorites.doubleClicked.connect(self.play)
        self.favorites.itemSelectionChanged.connect(self.favorite_changed)
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
            r = RadioStation(l['name'], l['url'], None, l['country'], l['favicon'])
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

    def contextMenu(self, p, wd, it):
        if it is None:
            return
        ctx = QMenu(self)
        if wd == self.table:
            #it = self.table.itemAt( self.table.mapFromGlobal(p))
            if it.column() != 0:
                it = self.table.item(it.row(), 0)
            ctx.addAction("Aggiunge ai preferiti").triggered.connect(lambda x: self.add_favourites(it))
        else:
            #it = self.favorites.itemAt(p)
            ctx.addAction("Rimuove dai preferiti").triggered.connect(lambda x: self.del_favourites(it))

        ctx.exec(p)

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

        if rd is None:
            rd = {}
        rd[nome] = r.url + ',' + r.favicon
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
            b.open_radio(url, dat.favicon)

    def favorite_changed(self):
        items = self.favorites.selectedItems()
        if len(items) > 0:
            self.favorites.setSelCur(items[0])

    def play_item(self, lst):
        if lst == self.favorites:
            self.play()
    def play(self):
        rad = self.favorites.selectedItems()[0].text()
        rd = self.ini.get('radio')
        dat = rd[rad].split(',')
        url = dat[0]
        fav = ''
        if len(dat) > 1:
            fav = dat[1]
        self.wparent.open_radio(url, fav)

class RadioStation:
    def __init__(self, name='', url='', ico=None, paese='', favicon=''):
        self.name = name
        self.url = url
        self.ico = ico
        #self.bitrate = bitrate
        self.paese = paese
        self.favicon = favicon


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
        self.wparent = parent
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
        self.wparent = parent
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
        self.setWindowTitle('Cerca')

        self.wparent = parent
        self.music = music

        self.ed = QLineEdit(self)
        b1 = QPushButton(self)
        b1.setIcon(QIcon(os.path.join(os.getcwd(), 'icone/search.png')))
        b1.setMaximumWidth(50)
        b1.clicked.connect(self.search)
        self.ed.returnPressed.connect(self.search)
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

class configDlg(QDialog):
    def __init__(self, parent):
        super(configDlg, self).__init__(parent)
        self.wparent = parent

        v = QVBoxLayout(self)
        ini = iniConf('music_player')
        md = ini.get('MAIN', 'splittermode')
        self.ui_mode = QCheckBox('Modo Splitter', self)
        if md == '1':
            self.ui_mode.setCheckState(Qt.CheckState.Checked)
        else:
            self.ui_mode.setCheckState(Qt.CheckState.Unchecked)
        v.addWidget(self.ui_mode)
        v.addLayout(exitBtn(self))

    def accept(self):
        v = '0'
        if self.ui_mode.isChecked():
            v = '1'

        ini = iniConf('music_player')
        s = ini.get('MAIN')
        if s is None:
            s = {}
        s['splittermode'] = v
        ini.set_sez('MAIN', s)
        ini.save()

        self.done(1)

    #def Annulla(self):
    #    self.done(0)
    @staticmethod
    def run(parent):
        dlg = configDlg(parent).exec()

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
