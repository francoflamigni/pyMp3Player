from profiler import checkpoint
import os

import copy
from PyQt6.QtCore import Qt, QEvent, QRect, QThreadPool, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon, QCursor, QAction
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QSplitter, QHBoxLayout, QWidget, QFileDialog, QLabel,
                             QApplication, QPushButton, QLineEdit, QListWidgetItem, QTabWidget,
                             QAbstractItemView, QMenu, QToolTip)

from mp3_tag import Music

from pyMyLib.qtUtils import waitCursor, center_in_parent, set_background, yesNoMessage
from pyMyLib.utils import iniConf, get_resource_file

from dialogs import myList, lyric_song, mySearch, myPlainText, AppConfig


def info_album(artist, album, parent=None):
    #from music_brainz import CDinfo
    #cdi = CDinfo()
    #df = cdi.detect_info_by_metadata(None, artist, album)
    from music_brainz import brainz
    brainz(artist, album)

def edit_album(artist, album, dir, parent=None):
    from format_convert import AudioConverter
    ac = AudioConverter(dir)
    ac.exec()

class infoDlg(QDialog):
    def __init__(self, parent, txt):
        super(infoDlg, self).__init__(parent)
        self.wparent = parent
        self.txt = txt
        center_in_parent(self, parent, 300, 100)
        self.setWindowTitle('Shazam')
        self.setWindowIcon(QIcon(get_resource_file(__file__, 'icone', 'shazam.png')))

        v = QVBoxLayout(self)
        self.txt_box = myPlainText(self)

        self.txt_box.setText(txt)
        v.addWidget(self.txt_box)

    @staticmethod
    def run(parent, txt):
        dlg = infoDlg(parent, txt)
        dlg.exec()


class MusicIndexDlg(QDialog):
    play_signal = pyqtSignal(list)
    def __init__(self, parent):
        super(MusicIndexDlg, self).__init__(parent)
        self.wparent = parent
        self.shaz = False
        self.play_cur = False
        self._current_worker = None
        self.artists_sav = None
        self.threadpool = QThreadPool()

        self.setObjectName("mp3_widget")
        set_background(self)

        ini = iniConf(AppConfig)
        self.last_folder = ini.get('CONF', 'last_folder')

        self.music = Music(parent.ini)
        v = QVBoxLayout(self)
        v.setContentsMargins(1, 1, 1, 1)
        self.prog = QLabel('')
        self.prog.setMinimumWidth(250)

        self.b1 = QPushButton(self)
        self.b1.setIcon(QIcon(get_resource_file(__file__, 'icone', 'folder_open.png')))
        self.b1.setMaximumWidth(30)
        self.b1.clicked.connect(self.index2)

        self.te = QLineEdit()
        self.te.setMinimumWidth(200)
        self.te.textChanged.connect(self.list_search)
        self.te.returnPressed.connect(self.search)

        icona_cerca = QIcon(get_resource_file(__file__, 'icone', 'search.png'))
        azione_cerca = QAction(icona_cerca, "Cerca", self)
        azione_cerca.triggered.connect(self.search)
        self.te.addAction(
            azione_cerca,
            QLineEdit.ActionPosition.TrailingPosition  # Posizione a destra (Trailing)
        )

        h0 = QHBoxLayout()
        h0.addWidget(self.b1)
        h0.addWidget(self.prog)
        h0.addSpacing(10)
        h0.addWidget(self.te)

        self.artists = myList(self, 'artisti', cursor=1)
        self.artists.setStyleSheet("""
            QListWidget::item:selected {
                background-color: #FFFF77; /* Colore di sfondo della selezione */
                color: black;            /* Colore del testo della selezione */
            }
        """)
        self.artists.setSortingEnabled(True)
        self.artists.itemSelectionChanged.connect(self.artist_changed)
        self.artists.setMinimumHeight(200)

        self.albums = myList(self, 'album')
        self.albums.setStyleSheet("""
              QListWidget::item:selected {
                  background-color: #77FFFF; /* Colore di sfondo della selezione */
                  color: black;            /* Colore del testo della selezione */
              }
          """)
        self.albums.setSortingEnabled(False)
        self.albums.itemSelectionChanged.connect(self.album_changed)
        self.albums.doubleClicked.connect(self.play_album)

        splitter1 = QSplitter(self)
        splitter1.setOrientation(Qt.Orientation.Horizontal)
        splitter1.setContentsMargins(0, 0, 0, 0)
        splitter1.addWidget(self.artists)
        splitter1.addWidget(self.albums)

        self.tracks = myList(self, 'tracce')
        self.tracks.setStyleSheet("""
              QListWidget::item:selected {
                  background-color: #FF77FF; /* Colore di sfondo della selezione */
                  color: black;            /* Colore del testo della selezione */
              }
          """)
        self.tracks.setMinimumWidth(250)
        self.tracks.setSortingEnabled(False)
        self.tracks.itemSelectionChanged.connect(self.track_changed)
        self.tracks.doubleClicked.connect(self.play_song)

        splitter2 = QSplitter(self)
        splitter2.setOrientation(Qt.Orientation.Vertical)
        splitter2.setContentsMargins(0, 0, 0, 0)
        splitter2.addWidget(splitter1)
        self.tab = QTabWidget(self)
        self.tab.setTabPosition(QTabWidget.TabPosition.West)
        self.tab.tabBarDoubleClicked.connect(self.play_playlist)
        self.tab.setMaximumWidth(250)

        self.pix = QLabel()

        vl = QVBoxLayout()
        self.plst = myList(self)
        self.plst.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        bp = QPushButton(self)
        bp.setIcon(QIcon(get_resource_file(__file__, 'icone', 'play.png')))
        bp.clicked.connect(lambda x: self.play_playlist(1))
        vl.addWidget(self.plst)
        vl.addWidget(bp)
        wd = QWidget(self)
        wd.setContentsMargins(0, 0, 0, 0)
        wd.setLayout(vl)

        self.tab.addTab(self.pix, '')
        self.tab.setTabIcon(0, QIcon(get_resource_file(__file__, 'icone', 'cover.png')))
        self.tab.setTabToolTip(0, 'copertina')

        self.tab.addTab(wd, '')
        self.tab.setTabIcon(1, QIcon(get_resource_file(__file__, 'icone', 'playlist.png')))
        self.tab.setTabToolTip(1, 'playlist')

        self.h = QHBoxLayout()
        self.h.setContentsMargins(1, 1, 1, 1)
        self.h.addWidget(self.tab)
        self.h.addWidget(self.tracks)
        wd = QWidget()
        wd.setLayout(self.h)
        splitter2.addWidget(wd)

        v.addLayout(h0)
        v.addWidget(splitter2)
        self.res = self.music.init(self.last_folder)
        if self.res == self.music.INDEX_LOADED:
            self.artists_sav = copy.deepcopy(self.music.artists)
            self.set_artists()
        elif self.res == self.music.NO_FOLDER or self.res == self.music.NO_FILE:
            self.print('La cartella indicata non esiste o non contiene file')
        self.print(self.last_folder)

        self.artists.installEventFilter(self)

    def eventFilter(self, obj, event):
        from utility import WikipediaWorker
        if event.type() == QEvent.Type.ToolTip and obj == self.artists:
            qp = QCursor.pos()  # Posizione globale del cursore
            p = self.artists.mapFromGlobal(qp)
            qi = self.artists.itemAt(p)

            if qi is not None:
                txt = qi.text()

                # 1. Annulla il worker precedente, se presente
                if self._current_worker is not None:
                     self._current_worker = None  # Rimuovi il riferimento

                # 2. Crea un nuovo worker per la richiesta attuale
                worker = WikipediaWorker(txt, qp)

                # 3. Connetti i segnali
                worker.signals.result.connect(self.show_tooltip_result)
                # Collega il segnale 'finished' per resettare il riferimento al worker
                worker.signals.finished.connect(self.worker_finished)

                # 4. Assegna il nuovo worker per il tracciamento e avvia il thread
                self._current_worker = worker
                self.threadpool.start(worker)

                # Ritorna True per indicare che abbiamo gestito l'evento
                # e prevenire il tooltip di default vuoto.
                return True

                # Per tutti gli altri eventi, usa il comportamento di default
        return super().eventFilter(obj, event)

    def show_tooltip_result(self, text, pos):
        """Slot chiamato quando il worker ha un risultato pronto."""

        QToolTip.showText(pos, text, self, QRect(), 60000)

    def worker_finished(self):
        """Slot chiamato quando un worker (qualsiasi) ha finito."""
        # Se il worker che ha finito è quello attualmente tracciato, resettalo.
        # (Opzionale: necessario solo se si volesse fare cleanup specifico)
        pass


    def list_search(self):
        txt = self.te.text()
        if not txt:
            self.artists.clearSelection()
            self.albums.clear()
            return
        items = self.artists.findItems(txt, Qt.MatchFlag.MatchContains)
        if items:
            items[0].setSelected(True)
            self.artists.scrollToItem(items[0])

    def play_playlist(self, index):
        if index == 0:
            return
        v = [self.plst.item(i).data(Qt.ItemDataRole.UserRole) for i in range(len(self.plst))]
        self.play_signal.emit(v)
        #self.wparent.open_file(v)

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
            if wd == self.tracks:
                ctx.addAction("Testo").triggered.connect(lambda x: lyric_song(artist, track, self.wparent))
            else:
                ctx.addAction("Informazioni").triggered.connect(lambda x: info_album(artist, album, self.wparent))
            if wd == self.albums:
                album = self.albums.selectedItems()
                if album and self.tracks.count():
                    album = album[0].text()
                    trk = self.tracks.item(0).text()
                    v = self.music.tracks.name[trk + '@' + album]
                    dir = os.path.dirname(v.file)
                    ctx.addAction("Edit").triggered.connect(lambda x: edit_album(artist, album, dir, self.wparent))
                a = 0

        ctx.exec(p)

    def play_item(self, lst):
        if lst == self.albums:
            self.play_album()
        elif lst == self.tracks:
            self.play_song()

    def clear_playlist(self):
        self.plst.clear()

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
            mes = f"Artista: {p.artist} Album: {p.album} Traccia: {p.title}"
            qi.setToolTip(mes)
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
        txt = self.te.text()

        sel = mySearch.run(self.wparent, self.music, txt)
        if sel:
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

    def find_song(self, time=5):
        from myShazam import myShazam
        if self.shaz:
            return
        self.shaz = True
        ms = myShazam(time=time)
        ms.found_song.connect(self._find_song)
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

    def filter(self, genere):
        self.music.artists = copy.deepcopy(self.artists_sav)
        if genere:
            g_a = self.get_generi_artist()
            if genere in g_a.keys():
                self.music.artists.filter(g_a[genere])
        self.set_artists()

    def get_generi_artist(self):
        from collections import defaultdict
        gen_art = defaultdict(set)
        for t in self.music.tracks.name.values():
            if t.genre:
                gen_art[t.genre].add(t.artist)
            a = 0
        return gen_art

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
            self.artists_sav = copy.deepcopy(self.music.artists)
            self.set_artists()

    def print(self, t):
        self.prog.setText(t)
        QApplication.processEvents()

    def play_song(self):
        alb = self.albums.selectedItems()[0].text()
        trk = self.tracks.selectedItems()[0].text()
        t = trk + '@' + alb
        tt = self.music.tracks.name[t]
        self.play_signal.emit([tt])
        #self.wparent.open_file([tt])

    def play_album(self):
        sel_alb = self.albums.selectedItems()
        if sel_alb is None or len(sel_alb) == 0:
            return
        alb = sel_alb[0].text()
        trks = [self.tracks.item(row).text() for row in range(self.tracks.count())]

        v = [self.music.tracks.name[trk + '@' + alb] for trk in trks]
        self.play_signal.emit(v)
        #self.wparent.open_file(v)
