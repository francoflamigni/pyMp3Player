import os

import copy
import time

from PyQt6.QtCore import (Qt, QRect, QThreadPool, pyqtSignal, QRectF, QPropertyAnimation, pyqtProperty,
                          QEasingCurve, QPoint, QParallelAnimationGroup)
from PyQt6.QtGui import QPixmap, QIcon, QAction, QFont, QEnterEvent, QPainter, QColor, QLinearGradient, QPen
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QSplitter, QHBoxLayout, QWidget, QFileDialog, QLabel,
                             QApplication, QPushButton, QLineEdit, QListWidgetItem, QAbstractButton,
                             QAbstractItemView, QMenu, QToolTip, QGraphicsOpacityEffect, QStackedWidget,
                             QSizePolicy)

from mp3_tag import Music

from pyMyLib.qtUtils import set_background, yesNoMessage
from pyMyLib.utils import get_resource_file
from sync_folders import get_folder_size

from dialogs import lyric_song, mySearch
from utility import myList, AppContext, human_size

def edit_album(artist, album, dir, parent=None):
    from format_convert import AudioConverter
    ac = AudioConverter(dir)
    ac.exec()

def printable_duration(duration):
    h = int(duration / 3600)
    m = int((duration - h * 3600) / 60)
    s = int(duration - h * 3600 - m * 60)
    tm = ''
    if h != 0:
        tm += str(h) + 'h '
    tm += str(m) + 'm ' + str(s) + 's'
    return tm

class HoverLineEdit(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def enterEvent(self, event: QEnterEvent):
        # Prende il focus non appena il mouse entra nell'area del widget
        self.setFocus()
        super().enterEvent(event)


class SlidingStackedWidget(QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.duration = 500  # Un po' più lento per godersi la dissolvenza
        self.curve = QEasingCurve.Type.OutQuint #OutCubic

    def slide_to_index(self, index):
        if self.currentIndex() == index:
            return

        old_widget = self.currentWidget()
        new_widget = self.widget(index)
        direction = 1 if index > self.currentIndex() else -1
        width = self.width()

        # --- PREPARAZIONE OPACITÀ ---
        # Creiamo gli effetti di opacità per entrambi i widget
        eff_old = QGraphicsOpacityEffect(old_widget)
        eff_new = QGraphicsOpacityEffect(new_widget)
        old_widget.setGraphicsEffect(eff_old)
        new_widget.setGraphicsEffect(eff_new)

        # Il nuovo widget parte invisibile e fuori schermo
        new_widget.setGeometry(direction * width, 0, width, self.height())
        new_widget.show()
        new_widget.raise_()

        self.group = QParallelAnimationGroup()

        # --- ANIMAZIONI POSIZIONE (SLIDE) ---
        anim_pos_old = QPropertyAnimation(old_widget, b"pos")
        anim_pos_old.setDuration(self.duration)
        anim_pos_old.setEndValue(QPoint(-direction * (width // 2), 0)) # Esce solo a metà per effetto profondità
        self.group.addAnimation(anim_pos_old)

        anim_pos_new = QPropertyAnimation(new_widget, b"pos")
        anim_pos_new.setDuration(self.duration)
        anim_pos_new.setEndValue(QPoint(0, 0))
        self.group.addAnimation(anim_pos_new)

        # --- ANIMAZIONI OPACITÀ (FADE) ---
        anim_fade_old = QPropertyAnimation(eff_old, b"opacity")
        anim_fade_old.setDuration(self.duration)
        anim_fade_old.setStartValue(1.0)
        anim_fade_old.setEndValue(0.0)
        self.group.addAnimation(anim_fade_old)

        anim_fade_new = QPropertyAnimation(eff_new, b"opacity")
        anim_fade_new.setDuration(self.duration)
        anim_fade_new.setStartValue(0.0)
        anim_fade_new.setEndValue(1.0)
        self.group.addAnimation(anim_fade_new)

        # --- PULIZIA FINALE ---
        def cleanup():
            self.setCurrentIndex(index)
            # Rimuoviamo gli effetti per liberare risorse e permettere interazioni pulite
            old_widget.setGraphicsEffect(None)
            new_widget.setGraphicsEffect(None)

        self.group.finished.connect(cleanup)
        self.group.start()

class HiFiToggle(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Larghezza fissa a 15px, altezza ridotta a 40px
        self.setFixedSize(15, 90)
        # Forza il widget a non espandersi orizzontalmente
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCheckable(True)
        self._pos = 0.0

    @pyqtProperty(float)
    def pos(self): return self._pos

    @pos.setter
    def pos(self, p):
        self._pos = p
        self.update()

    def nextCheckState(self):
        super().nextCheckState()
        end = 1.0 if self.isChecked() else 0.0
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(150)  # Più veloce essendo piccola
        self.anim.setEndValue(end)
        self.anim.start()


    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        icon_area = 20  # Spazio riservato a ogni icona
        padding = 5  # <--- DISTANZA tra icona e slot nero

        # Calcoliamo lo slot centrale sottraendo icone e padding
        slot_y_start = icon_area + padding
        slot_h = h - (2 * (icon_area + padding))
        slot_rect = QRectF(1, slot_y_start, w - 2, slot_h)

        # 1. DISEGNO SLOT (Incasso)
        painter.setPen(QPen(QColor("#222222"), 1))
        painter.setBrush(QColor("#050505"))
        painter.drawRoundedRect(slot_rect, 3, 3)

        # 2. ICONE (Distanziate)
        font = QFont("Segoe UI Symbol", 9)
        painter.setFont(font)

        # Icona Superiore (Nota) - Disegnata nel suo spazio dedicato in alto
        color_top = QColor("#FF0000") if not self.isChecked() else QColor("#440000")
        painter.setPen(color_top)
        painter.drawText(QRectF(0, 0, w, icon_area), Qt.AlignmentFlag.AlignCenter, "♫")

        # Icona Inferiore (Lista) - Disegnata nel suo spazio dedicato in basso
        color_bottom = QColor("#FF0000") if self.isChecked() else QColor("#440000")
        painter.setPen(color_bottom)
        painter.drawText(QRectF(0, h - icon_area, w, icon_area), Qt.AlignmentFlag.AlignCenter, "≡")

        # 3. CORSA DELLA LEVETTA (Allineata allo slot)
        y_range = slot_h - (w - 2) - 4
        # La corsa ora parte dall'inizio dello slot (slot_y_start)
        y_pos = slot_y_start + 2 + (self._pos * y_range)
        knob_rect = QRectF(1, y_pos, w - 2, w - 2)
        # 4. GRADIENTE METALLICO
        grad = QLinearGradient(knob_rect.topLeft(), knob_rect.bottomRight())
        grad.setColorAt(0, QColor("#f0f0f0"))
        grad.setColorAt(0.5, QColor("#999999"))
        grad.setColorAt(1, QColor("#555555"))

        # 5. DISEGNO POMOLO
        painter.setPen(QPen(QColor("#111111"), 1))
        painter.setBrush(grad)
        painter.drawRoundedRect(knob_rect, 2, 2)

class MusicIndexDlg(QDialog):
    play_signal = pyqtSignal(list, bool)
    def __init__(self, appCtx:AppContext):
        super().__init__()
        self.appctx = appCtx
        self.play_cur = False
        self._current_worker = None
        self.artists_sav = None
        self.threadpool = QThreadPool()

        self.setObjectName("mp3_widget")
        set_background(self)

        ini = appCtx.config
        self.last_folder = ini.get('CONF', 'last_folder')

        self.music = Music(ini)
        v = QVBoxLayout(self)
        v.setContentsMargins(1, 1, 1, 1)
        v.setSpacing(0)

        self.prog = QLineEdit() #QLabel('')
        self.prog.setReadOnly(True)

        icone_folder = QIcon(get_resource_file(__file__, 'icone', 'folder_open.png'))
        azione_folder = QAction(icone_folder, "browse", self)
        azione_folder.triggered.connect(self.index2)
        self.prog.addAction(
            azione_folder,
            QLineEdit.ActionPosition.LeadingPosition
        )

        self.te = HoverLineEdit()
        self.te.textChanged.connect(self.list_search)
        self.te.returnPressed.connect(self.search)

        icona_cerca = QIcon(get_resource_file(__file__, 'icone', 'search.png'))
        azione_cerca = QAction(icona_cerca, "Cerca", self)
        azione_cerca.triggered.connect(self.search)
        self.te.addAction(
            azione_cerca,
            QLineEdit.ActionPosition.LeadingPosition #.TrailingPosition  # Posizione a destra (Trailing)
        )
        self.te.setClearButtonEnabled(True)
        stile_comune = """
            QLineEdit {
                height: 18px;       /* Forza un'altezza specifica */
                padding: 2px 5px;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QLineEdit:read-only {
                background-color: #e0e0e0; /* Grigio chiaro per il read-only */
            }
        """
        self.prog.setStyleSheet(stile_comune)
        self.te.setStyleSheet(stile_comune)

        h0 = QHBoxLayout()
        h0.addWidget(self.prog, stretch=1)
        h0.addSpacing(10)
        h0.addWidget(self.te, stretch=2)
        h0.addStretch()

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
        self.albums.play_item_signal.connect(self.play_item)

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
        self.tracks.play_item_signal.connect(self.play_item)

        splitter2 = QSplitter(self)
        splitter2.setOrientation(Qt.Orientation.Vertical)
        splitter2.setContentsMargins(0, 0, 0, 0)
        splitter2.addWidget(splitter1)

        self.toggle_switch = HiFiToggle()
        # Colleghiamo il segnale alla transizione
        self.toggle_switch.toggled.connect(
            lambda checked: self.tab.slide_to_index(1 if checked else 0)
        )

        self.tab = SlidingStackedWidget() #QStackedWidget()
        self.tab.setMaximumWidth(250)

        self.pix = QLabel()

        vl = QVBoxLayout()
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(1)
        self.plst = myList(self, cursor=1)
        self.plst.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.plst.setStyleSheet("""
            QListWidget::item:selected {
                background-color: #77FF77; /* Colore di sfondo della selezione */
                color: black;            /* Colore del testo della selezione */
            }
        """)
        self.playPlaylist = QPushButton(self)
        self.playPlaylist.setIcon(QIcon(get_resource_file(__file__, 'icone', 'play.png')))
        self.playPlaylist.clicked.connect(self.play_playlist)
        vl.addWidget(self.plst)
        vl.addWidget(self.playPlaylist)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(1)
        wd = QWidget(self)
        wd.setLayout(vl)

        self.tab.addWidget(self.pix)
        self.tab.addWidget(wd)

        wd1 = QWidget(self)
        hv = QHBoxLayout(wd1)
        hv.setContentsMargins(1, 0, 1, 1)
        hv.setSpacing(0)
        hv.addWidget(self.toggle_switch)
        hv.addWidget(self.tab)
        hv.addWidget(self.tracks)
        splitter2.addWidget(wd1)

        v.addLayout(h0)
        v.addWidget(splitter2)
        self.print(f"Loading {self.last_folder}")

        self.artists.installEventFilter(self)

        self.te.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def showEvent(self, event):
        super().showEvent(event)
        # Ogni volta che questa pagina viene mostrata, prendi il fuoco
        self.te.setFocus()

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

    def setPlaylist(self, songs_list):
        self.clear_playlist()
        for t in songs_list:
            self.add_playlist(*t)

        stat = {}
        for t in songs_list:
            if t[0] in stat.keys():
                n = stat[t[0]]
                stat[t[0]] = n + 1
            else:
                stat[t[0]] = 1
        lines = [f"{key}:\t{value}" for key, value in stat.items()]
        tip = f"{self.playlist_info()}\n{'\n'.join(lines)}"
        self.playPlaylist.setToolTip(tip)

        self.switch_to_page(1)

    def contextMenu(self, p, wd, it):
        pd = wd.mapToGlobal(p)
        ctx = QMenu(self)
        if wd == self.plst: #nella lista play list rimuove tutti o selezionati
            ico = QIcon(get_resource_file(__file__, 'icone', 'playlist_remove.png'))
            ctx.addAction(ico, "Rimuove tutti").triggered.connect(lambda x: self.remove_playlist('all'))
            ico = QIcon(get_resource_file(__file__, 'icone', 'remove_selected.png'))
            ctx.addAction(ico, "Rimuove selezionati").triggered.connect(lambda x: self.remove_playlist('selected'))
            ico = QIcon(get_resource_file(__file__, 'icone', 'shuffle.png'))
            ctx.addAction(ico, "Mischia").triggered.connect(self.scramble_playlist)
        else:
            artist = self.artists.selectedItems()
            if not artist: #l'artista deve essere selezionato
                return
            artist = artist[0].text()
            if wd == self.artists:  # nessuna azione nella lista artisti
                ctx.addAction("Informazioni").triggered.connect(
                    lambda checked=False, ar=artist: self.info_artist(ar))

            elif wd == self.albums: #se lista album it è l'elemento selezionato
                album = it.text()
                if not album:
                    return
                track = '' # track vuoto ad indicare tutte quelle dell'album
                tracks, alb = self.music.find_tracks_ext(album, artist)
            else: #siamo nella lista tracce
                album = self.albums.selectedItems()
                if not album:
                    return
                if len(album) > 0:
                    album = album[0].text()
                track = it.text()

            if wd != self.artists:
                ico = QIcon(get_resource_file(__file__, 'icone', 'playlist_add.png'))
                ctx.addAction(ico, "Aggiunge alla playlist").triggered.connect(lambda checked=False, a=artist, b=album, c=track: self.add_playlist(a, b, c))
                if wd == self.tracks:
                    ico = QIcon(get_resource_file(__file__, 'icone', 'lyric.png'))
                    ctx.addAction(ico, "Testo").triggered.connect(lambda checked=False, a=artist, t=track, c=self.appctx: lyric_song(a, t, c))
                else:
                    ctx.addAction("Informazioni").triggered.connect(lambda  checked=False, ar=artist, al=alb, tr=tracks: self.info_album(ar, al, tr))
                    if self.tracks.count():
                        trk = self.tracks.item(0).text()
                        try:
                            v = self.music.tracks.name[trk + '@' + album]
                            dir = os.path.dirname(v.file)
                            ico = QIcon(get_resource_file(__file__, 'icone', 'background.png'))
                            (ctx.addAction(ico, "Edit tags").
                             triggered.connect(lambda checked=False, ar=artist, al=album, d=dir: edit_album(ar, al, d, self)))
                        except:
                            pass

        if len(ctx.actions()) == 1:
            # Se c'è solo un'azione, eseguila immediatamente senza mostrare il menu
            ctx.actions()[0].trigger()
        elif len(ctx.actions()) > 1:
            ctx.exec(pd)

    def info_artist(self, artist):
        from utility import ArtistInfoDlg
        ArtistInfoDlg.run(self.appctx.mainWindow, artist, self.appctx.cache)

    def info_album(self, artist, album, tracks):
        from music_brainz import AlbumInfoDlg
        AlbumInfoDlg.run(self.appctx.mainWindow, artist, album, tracks)

    def clear_playlist(self):
        self.plst.clear()

    def switch_to_page(self, index):
        """Sincronizza lo StackedWidget e la Levetta"""

        # 1. Cambia la pagina con l'animazione slide
        self.tab.slide_to_index(index)

        # 2. Aggiorna la levetta
        # Blocchiamo i segnali per evitare che la levetta richiami
        # di nuovo slide_to_index in un ciclo infinito
        self.toggle_switch.blockSignals(True)

        # Se index è 0 (Cover) -> checked = False (Su)
        # Se index è 1 (List)  -> checked = True (Giù)
        self.toggle_switch.setChecked(index == 1)

        # 3. Forziamo l'animazione fisica della levetta (perché setChecked non chiama nextCheckState)
        end_val = 1.0 if index == 1 else 0.0
        self.toggle_switch.anim = QPropertyAnimation(self.toggle_switch, b"pos")
        self.toggle_switch.anim.setDuration(150)
        self.toggle_switch.anim.setEndValue(end_val)
        self.toggle_switch.anim.start()

        self.toggle_switch.blockSignals(False)

    def add_playlist(self, artist, album, track):
        if track != '':
            vi = [self.music.tracks.name[track + '@' + album]]
        else:
            trks = self.music.find_tracks(album, artist)
            vi = [self.music.tracks.name[trk + '@' + album] for trk in trks if trk]

        for p in vi:
            qi = QListWidgetItem(p.title)
            qi.setData(Qt.ItemDataRole.UserRole, p)
            qi.setToolTip(f"Artista: {p.artist} Album: {p.album} Traccia: {p.title}")
            self.plst.addItem(qi)

        self.playPlaylist.setToolTip(self.playlist_info())
        self.switch_to_page(1)

    def playlist_info(self):
        tot_time = 0
        for t in range(self.plst.count()):
            dat = self.plst.item(t).data(Qt.ItemDataRole.UserRole)
            tot_time += dat.tm_sec

        return f"\n\nPlaylist\n\nBrani: {self.plst.count()}\nDurata: {printable_duration(tot_time)}"

    def remove_playlist(self, type):
        if type == 'all':
            self.plst.clear()
        else:
            its = self.plst.selectedItems()
            rs = [self.plst.row(it) for it in its]
            for r in reversed(rs):
                self.plst.takeItem(r)
            a = 0

    def scramble_playlist(self):
        import random
        vi = [self.plst.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.plst.count())]
        self.plst.clear()
        random.shuffle(vi)
        for p in vi:
            qi = QListWidgetItem(p.title)
            qi.setData(Qt.ItemDataRole.UserRole, p)
            qi.setToolTip(f"Artista: {p.artist} Album: {p.album} Traccia: {p.title}")
            self.plst.addItem(qi)

    def library_info(self):
        sz = int(get_folder_size(self.last_folder))
        self.stat = f"""
                {len(self.music.artists.name)} Artisti\n
                {len(self.music.albums.title)} Album\n 
                {len(self.music.tracks.name)} Tracce\n
                {human_size(sz)} Su disco"""

    def process(self):
        t0 = time.monotonic()

        self.res = self.music.init(self.last_folder)
        if self.res == self.music.NO_FOLDER or self.res == self.music.NO_FILE:
            self.print('La cartella indicata non esiste o non contiene file')
            return
        elif self.res == Music.NO_INDEX or self.res == Music.OLD_INDEX:
            if not yesNoMessage('indice non valido', "vuoi rigenerare l'indice?"):
                return
            self.music.index(self.print, self.last_folder)
        '''
        elif self.res == self.music.INDEX_LOADED:
            self.artists_sav = copy.deepcopy(self.music.artists)
            self.set_artists()
        '''

        self.artists_sav = copy.deepcopy(self.music.artists)
        self.set_artists()

        t1 = time.monotonic()
        print(f"elaborazione: {(t1-t0):.2f}")
        self.library_info()

        self.prog.setToolTip(self.stat)
        self.print(self.last_folder)
        """
        elif self.res == Music.NO_INDEX or self.res == Music.OLD_INDEX:
            if yesNoMessage('indice non valido', "vuoi rigenerare l'indice?"):
                self.index(self.last_folder)
                self.library_info()
                self.prog.setToolTip(self.stat)
        """

    ''' Cerca canzone artista album'''
    def search(self):
        txt = self.te.text()

        sel, pls = mySearch.run(self.appctx, self.music, txt)
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
        elif pls:
            for p in pls:
                self.add_playlist(p[0], p[1], p[2])

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
            albums_title = [d.title for d in sorted(albums, key=lambda x: int(x.year))]
            self.albums.addItems(albums_title)

    def album_changed(self):
        albums = self.albums.selectedItems()
        artists = self.artists.selectedItems()
        if len(albums) > 0 and len(artists) > 0:
            self.albums.setSelCur(albums[0])
            self.tracks.clear()
            album_title = albums[0].text()
            artist_name = artists[0].text()
            tracks = self.music.find_tracks(album_title, artist_name)
            self.get_track_pix(album_title, artist_name, self.pix)
            self.tracks.addItems(a for a in tracks)
            self.switch_to_page(0)

    def get_track_pix(self, album_title, artist_name, pix):
        pic = self.music.find_pic(album_title, artist_name)
        if pic is not None:
            qp = QPixmap()
            if qp.loadFromData(pic):
                pix.setPixmap(qp.scaled(pix.size(), Qt.AspectRatioMode.KeepAspectRatio))
                return True
        else:
            pix.clear()
            return False

    def track_changed(self):
        items = self.tracks.selectedItems()
        if len(items) > 0:
            self.tracks.setSelCur(items[0])

    def set_artists(self):
        self.artists.clear()
        self.artists.addItems(a for a in self.music.get_artists())

    def index2(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder', self.last_folder,
                                                  options=QFileDialog.Option.ShowDirsOnly)
        if folder:
            self.last_folder = folder
            self.process()

    '''
    def index(self, folder=''):
        if folder != '':
            self.music.index(self.print, folder)
            self.artists_sav = copy.deepcopy(self.music.artists)
            self.set_artists()
    '''

    def print(self, t):
        self.prog.setText(t)
        QApplication.processEvents()

    def play_song(self):
        try:
            alb = self.albums.selectedItems()[0].text()
            trk = self.tracks.selectedItems()[0].text()
            t = trk + '@' + alb
            tt = self.music.tracks.name[t]
            self.play_signal.emit([tt], False)
        except:
            pass

    def play_album(self):
        try:
            alb = self.albums.selectedItems()[0].text()
            trks = [self.tracks.item(row).text() for row in range(self.tracks.count())]

            v = [self.music.tracks.name[trk + '@' + alb] for trk in trks]
            self.play_signal.emit(v, False)
        except:
            pass

    def play_playlist(self):
        v = [self.plst.item(i).data(Qt.ItemDataRole.UserRole) for i in range(len(self.plst))]
        self.play_signal.emit(v, True)

    def play_item(self, lst):
        if lst == self.albums:
            self.play_album()
        elif lst == self.tracks:
            self.play_song()

