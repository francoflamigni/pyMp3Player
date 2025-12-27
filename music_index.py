from profiler import checkpoint
import os

import copy
from PyQt6.QtCore import Qt, QEvent, QRect, QThreadPool, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon, QCursor, QAction, QFont
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QSplitter, QHBoxLayout, QWidget, QFileDialog, QLabel,
                             QApplication, QPushButton, QLineEdit, QListWidgetItem, QTabWidget,
                             QAbstractItemView, QMenu, QToolTip, QFrame, QStackedWidget, QGraphicsOpacityEffect,
                             QSizePolicy)

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


from PyQt6.QtWidgets import QStackedWidget
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QPoint, QParallelAnimationGroup


class SlidingStackedWidget(QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.duration = 400  # Millisecondi della transizione
        self.curve = QEasingCurve.Type.OutQuint  # Movimento fluido e naturale

class SlidingStackedWidget(QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.duration = 500  # Un po' più lento per godersi la dissolvenza
        self.curve = QEasingCurve.Type.OutCubic

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


from PyQt6.QtWidgets import QAbstractButton
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QPen, QBrush
from PyQt6.QtCore import Qt, QRectF, QPropertyAnimation, pyqtProperty

from PyQt6.QtWidgets import QAbstractButton
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QPen, QBrush
from PyQt6.QtCore import Qt, QRectF, QPropertyAnimation, pyqtProperty


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

        '''
        sidebar = QFrame()
        sidebar.setFixedWidth(15)  # Molto stretta per non rubare spazio
        sidebar.setStyleSheet("background-color: #FFFFFF; border-right: 1px solid #333;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)

        # Pulsanti della sidebar
        btn_page1 = QPushButton("♫")
        #btn_page1.setIcon(QIcon(get_resource_file(__file__, 'icone', 'cover.png')))
        btn_page1.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #555; /* Spento */
                border: none;
                font-size: 20px;
            }
            QPushButton:checked {
                color: #FF0000; /* Acceso (LED) */
                border-left: 3px solid #FF0000; /* Barretta laterale di stato */
            }        
        """)
        btn_page2 = QPushButton("⚙")
        sidebar_layout.addWidget(btn_page1)
        sidebar_layout.addWidget(btn_page2)
        sidebar_layout.addStretch()
        '''
        self.toggle_switch = HiFiToggle()
        # Colleghiamo il segnale alla transizione
        self.toggle_switch.toggled.connect(
            lambda checked: self.tab.slide_to_index(1 if checked else 0)
        )

        self.tab = SlidingStackedWidget() #QStackedWidget()
        #btn_page1.clicked.connect(lambda: self.tab.slide_to_index(0))
        #btn_page2.clicked.connect(lambda: self.tab.slide_to_index(1))

        #self.tab = QTabWidget(self)
        #self.tab.setTabPosition(QTabWidget.TabPosition.West)
        #self.tab.tabBarDoubleClicked.connect(self.play_playlist)
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
        self.playPlaylist.clicked.connect(lambda x: self.play_playlist(1))
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



        '''
        self.tab.addTab(self.pix, '')
        self.tab.setTabIcon(0, QIcon(get_resource_file(__file__, 'icone', 'cover.png')))
        self.tab.setTabToolTip(0, 'copertina')

        self.tab.addTab(wd, '')
        self.tab.setTabIcon(1, QIcon(get_resource_file(__file__, 'icone', 'playlist.png')))
        self.tab.setTabToolTip(1, 'playlist')
        '''
        '''
        self.h = QHBoxLayout()
        self.h.setContentsMargins(1, 1, 1, 1)
        self.h.addWidget(self.tab)
        self.h.addWidget(self.tracks)
        wd = QWidget()
        wd.setLayout(self.h)
        splitter2.addWidget(wd)
        '''

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
        if wd == self.artists: #nessuna azione nella lista artisti
            return
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
            if wd == self.albums: #se lista album it è l'elemento selezionato
                album = it.text()
                if not album:
                    return
                track = '' # track vuoto ad indicare tutte quelle dell'album
            else: #siamo nella lista tracce
                album = self.albums.selectedItems()
                if not album:
                    return
                if len(album) > 0:
                    album = album[0].text()
                track = it.text()

            ico = QIcon(get_resource_file(__file__, 'icone', 'playlist_add.png'))
            (ctx.addAction(ico, "Aggiunge alla playlist").
                 triggered.connect(lambda x: self.add_playlist(artist, album, track)))
            if wd == self.tracks:
                ico = QIcon(get_resource_file(__file__, 'icone', 'lyric.png'))
                ctx.addAction(ico, "Testo").triggered.connect(lambda x: lyric_song(artist, track, self.wparent))
            else:
                ctx.addAction("Informazioni").triggered.connect(lambda x: info_album(artist, album, self.wparent))
                if self.tracks.count():
                    trk = self.tracks.item(0).text()
                    try:
                        v = self.music.tracks.name[trk + '@' + album]
                        dir = os.path.dirname(v.file)
                        ico = QIcon(get_resource_file(__file__, 'icone', 'background.png'))
                        (ctx.addAction(ico, "Edit tag").
                         triggered.connect(lambda x: edit_album(artist, album, dir, self.wparent)))
                    except:
                        pass
                a = 0

        ctx.exec(p)

    def play_item(self, lst):
        if lst == self.albums:
            self.play_album()
        elif lst == self.tracks:
            self.play_song()

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

        tot_time = 0
        for p in vi:
            qi = QListWidgetItem(p.title)
            qi.setData(Qt.ItemDataRole.UserRole, p)
            qi.setToolTip(f"Artista: {p.artist} Album: {p.album} Traccia: {p.title}")
            self.plst.addItem(qi)
            tot_time += p.tm_sec

        '''
        for r in range(self.plst.count()):
            qi = self.plst.item(r)
            p = qi.data(Qt.ItemDataRole.UserRole)
            mes = f"Artista: {p.artist} Album: {p.album} Traccia: {p.title}"
            qi.setToolTip(mes)
            tot_time += p.tm_sec
        '''

        h = int(tot_time / 3600)
        m = int((tot_time - h * 3600) / 60)
        s = int(tot_time - h * 3600 - m * 60)
        tm = ''
        if h != 0:
            tm += str(h) + 'h '
        tm += str(m) + 'm ' + str(s) + 's'

        mes = 'playlist brani: ' + str(self.plst.count()) + ' durata: ' + tm
        self.playPlaylist.setToolTip( mes)
        self.switch_to_page(1)

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
            self.switch_to_page(0)

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
        try:
            alb = self.albums.selectedItems()[0].text()
            trk = self.tracks.selectedItems()[0].text()
            t = trk + '@' + alb
            tt = self.music.tracks.name[t]
            self.play_signal.emit([tt])
        except:
            pass

    def play_album(self):
        try:
            alb = self.albums.selectedItems()[0].text()
            trks = [self.tracks.item(row).text() for row in range(self.tracks.count())]

            v = [self.music.tracks.name[trk + '@' + alb] for trk in trks]
            self.play_signal.emit(v)
        except:
            pass

