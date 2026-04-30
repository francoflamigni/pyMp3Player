import os.path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QTextCursor, QIcon, QCursor, QFontMetrics, QAction
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QSplitter, QHBoxLayout, QWidget, QStyle,
                             QListWidget, QPushButton, QTableWidget, QLineEdit, QTableWidgetItem, QHeaderView,
                             QPlainTextEdit, QAbstractItemView, QMenu, QLabel, QGroupBox, QComboBox, QFormLayout,
                             QSpinBox, QFileDialog, QCheckBox, QGridLayout)

from qtwidgets import Toggle
import scrobbler

from pyMyLib.qtUtils import exitBtn, center_in_parent, set_background, yesNoMessage, waitCursor
from pyMyLib.utils import iniConf, get_resource_file, ConfDir
from utility import AppContext

from threading import Thread

'''
https://github.com/andreztz/pyradios/tree/main/pyradios
'''

AppConfig = 'Euterpe'



def lyric_song(artist, track, ctx=None):
    from scrobbler import LyricsWorker
    ls = LyricsWorker(artist, track)
    txt = ls.song_text2()
    if len(txt) > 0:
        lyricsDlg.run(ctx, txt, track)

class myPlainText(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setReadOnly(True)
        self.slave = None

        self.last_position = self.verticalScrollBar().sliderPosition()
        self.verticalScrollBar().valueChanged.connect(self.handle_value_changed)
        self.cur = QTextCursor(self.document())

    def adjustWidthToContent(self, txt):
        # Ottieni il font del widget
        font = self.font()
        fm = QFontMetrics(font)

        # Trova la riga più lunga
        #text = self.toPlainText()
        lines = txt.split('\n')

        max_width = 0
        for line in lines:
            line_width = fm.horizontalAdvance(line)  # PyQt5 >= 5.11, usa width() per versioni precedenti
            max_width = max(max_width, line_width)

        # Aggiungi un margine extra (padding, scrollbar, ecc.)
        # Tipicamente: margini interni + scrollbar verticale + un po' di spazio extra
        extra_space = 40  # Puoi regolare questo valore

        optimal_width = max_width + extra_space

        # Imposta la larghezza del widget
        self.setFixedWidth(optimal_width)

    def setSlave(self, slave):
        self.slave = slave
        self.slave.setStyleSheet("""
        QPlainTextEdit {
            selection-background-color: yellow;
            selection-color: black;
        }
        """)
        self.slave.verticalScrollBar().valueChanged.connect(self.handle_value_changed2)

    def setText(self, txt):
        self.cur.movePosition(QTextCursor.MoveOperation.End)
        self.cur.insertText(txt)
        self.adjustWidthToContent(txt)

    def handle_value_changed(self, position):
        if self.slave is None:
            return
        self.slave.verticalScrollBar().setValue(position)

    def handle_value_changed2(self, position):
        self.verticalScrollBar().setValue(position)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)

        cursor = self.cursorForPosition(event.pos())
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        self.setTextCursor(cursor)

class lyricsDlg(QDialog):
    def __init__(self, appCtx, txt, track=''):
        #if not appCtx:
        #    a =0
        super(lyricsDlg, self).__init__(appCtx.mainWindow)
        from googletrans import Translator
        self.txt = txt.lstrip()
        center_in_parent(self, appCtx.mainWindow, 600, 500)
        self.setWindowTitle(track)
        self.setWindowIcon(QIcon(get_resource_file(__file__, 'icone', 'lyric.png')))

        v = QVBoxLayout(self)
        self.h = QHBoxLayout()
        self.h.setContentsMargins(3, 3, 3, 3)
        self.h.setSpacing(5)
        self.txt_box = myPlainText(self)
        self.tr = Translator()
        lang = self.tr.detect(txt).lang
        self.app_lang = appCtx.config.get('user', 'lang')
        self.tr_box = None

        self.txt_box.setText(self.txt)
        self.h.addWidget(self.txt_box)
        v.addLayout(self.h)

        if lang != self.app_lang.lower():
            self.bt = QPushButton(self)
            self.bt.setText('Traduci')
            self.bt.clicked.connect(self.traduci)
            v.addWidget(self.bt)

        self.adjustWindowSize()

    def traduci(self):
        self.tr_box = myPlainText(self)
        self.txt_box.setSlave(self.tr_box)
        self.h.addWidget(self.tr_box)
        txt1 = self.tr.translate(self.txt, self.app_lang)
        self.bt.hide()

        self.txt_box.selectionChanged.connect(self.sync)

        self.tr_box.setText(txt1.text)
        sz = self.size()
        sz.setWidth(sz.width() * 2)
        self.resize(sz)

    def adjustWindowSize(self):
        sz = self.size()
        width = self.txt_box.width()

        sz.setWidth(width +5)
        self.resize(sz)


    def sync(self):
        line_number = self.txt_box.textCursor().blockNumber()
        # Ottieni il cursore del documento
        cursor = self.txt_box.slave.textCursor()
        # Posizionarsi all'inizio del documento
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        # Scorrere fino alla riga desiderata
        for _ in range(line_number):
            cursor.movePosition(QTextCursor.MoveOperation.Down)

        # Selezionare la riga intera
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)

        # Impostare il cursore aggiornato nel QPlainTextEdit
        self.txt_box.slave.setTextCursor(cursor)

    @staticmethod
    def run(ctx, txt, track=''):
        dlg = lyricsDlg(ctx, txt, track)
        dlg.exec()

class mySearch(QDialog):
    def __init__(self, appCtx:AppContext, music, txt):
        super().__init__(appCtx.mainWindow)
        center_in_parent(self, appCtx.mainWindow, 600, 400)
        self.setWindowTitle('Cerca')

        self.music = music

        self.ed = QLineEdit(self)
        self.ed.setText(txt)
        icona_cerca = QIcon(get_resource_file(__file__, 'icone', 'search.png'))
        azione_cerca = QAction(icona_cerca, "Cerca", self)
        azione_cerca.triggered.connect(self.search)
        self.ed.addAction(
            azione_cerca,
            QLineEdit.ActionPosition.TrailingPosition  # Posizione a destra (Trailing)
        )

        self.ed.returnPressed.connect(self.search)
        h = QHBoxLayout()
        h.addWidget(self.ed)

        self.list = QListWidget(self)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        # Applica lo stile: Grigio per la selezione, Bianco per il testo
        self.list.setStyleSheet("""
            QListWidget::item:selected {
                background-color: #808080;  /* Grigio */
                color: white;               /* Scritta bianca */
            }
            QListWidget::item:selected:active {
                background-color: #696969;  /* Grigio leggermente più scuro quando attivo */
                outline: none;
            }
        """)
        self.list.doubleClicked.connect(self.selection)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.show_context_menu)

        v = QVBoxLayout(self)
        v.addLayout(h)
        v.addWidget(self.list)
        self.selected = None
        self.pls = None
        if txt:
            self.search()

    def search(self):
        txt = self.ed.text().lower()
        if len(txt) == 0:
            return
        mes = []
        waitCursor(True)

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
                if art:
                    mes.append(str(kk) + ' album: ' + art + ';' + a.title + '\n')
                    kk += 1
        a3 = [k for k in self.music.tracks.name.values() if k is not None and txt in k.title.lower()]
        if len(a3) > 0:
            for a in a3:
                if a.artist in self.music.artists.name.keys():
                    mes.append(str(kk) + ' traccia: ' + a.artist + ';' + a.album + ';' + a.title + '\n')
                    kk += 1

        self.list.clear()
        self.list.addItems(mes)
        waitCursor()

    def show_context_menu(self, position):
        # Ottieni gli item selezionati
        selected_items = self.list.selectedItems()
        if not selected_items:
            return

        menu = QMenu()

        # Esempio di azione con l'icona che abbiamo visto prima
        playlist_icon = QIcon(get_resource_file(__file__, 'icone', 'playlist_add.png'))
        playlist_action = menu.addAction(playlist_icon, f"Aggiunge alla Play list")

        # Esegui il menu e ottieni l'azione scelta
        action = menu.exec(self.list.mapToGlobal(position))

        if action == playlist_action:
            self.pls = []
            for item in selected_items:
                t = item.text()
                risultato = t.split(':', 1)[1].strip()
                if 'artista' in t.lower():
                    continue
                else:
                    r = risultato.split(';')
                    artista = r[0].strip()
                    album = r[1].strip()
                    traccia = ''
                    if 'traccia' in t:
                        traccia = r[2].strip()

                    self.pls.append((artista, album, traccia))
            self.done(1)

    def selection(self):
        s = self.list.selectedItems()
        if len(s) > 0:
            self.selected = s[0].text()
            self.done(1)

    @staticmethod
    def run(parent, music, txt=''):
        dlg = mySearch(parent, music, txt)
        if dlg.exec() == 1:
            return dlg.selected, dlg.pls
        return None, None

''' finestra principale per le opzioni e la configurazione'''
class ConfigBox(QDialog):
    def __init__(self, parent, ini:iniConf):
        super().__init__()
        self.ini = ini
        self.ini.config_read()
        lang = self.ini.get('user', 'lang')

        self.setWindowTitle('Preferenze')
        center_in_parent(self, parent, 260, 160)
        vb = QVBoxLayout(self)

        vg = QGridLayout()

        # cache
        cachebox = QGroupBox(self)
        cachebox.setTitle('Cache')
        vc = QVBoxLayout(cachebox)
        hc = QHBoxLayout()
        self.cache_dir = QLineEdit(self)
        icona_cerca = QIcon(get_resource_file(__file__, 'icone', 'search.png'))
        self.browse =  QAction(icona_cerca, 'Browse', self)
        self.browse.triggered.connect(self.cachepath)
        self.cache_dir.addAction(self.browse, QLineEdit.ActionPosition.TrailingPosition)
        hc.addWidget(QLabel('Cartella'))
        hc.addWidget(self.cache_dir)
        vc.addLayout(hc)
        hc = QHBoxLayout()
        hc.addWidget(QLabel('Giorni di validità'))
        self.cache_days = QLineEdit(self)
        hc.addWidget(self.cache_days)
        vc.addLayout(hc)
        hc = QHBoxLayout()
        hc.addWidget(QLabel('Dimensione massima MB'))
        self.cache_size = QLineEdit(self)
        hc.addWidget(self.cache_size)
        vc.addLayout(hc)

        #vb.addWidget(cachebox)
        vg.addWidget(cachebox, 0, 0)

        lang_box = QGroupBox(self)
        lang_box.setTitle('Lingua preferita')
        qf1 = QFormLayout(lang_box)

        self.c1 = QComboBox()
        self.c1.addItems(['IT', 'FR', 'EN', 'SP'])

        qf1.addWidget(self.c1)

        #vb.addWidget(lang_box)
        vg.addWidget(lang_box, 1, 0)

        timeout_box = QGroupBox(self)
        timeout_box.setTitle('Background')
        qf2 = QGridLayout(timeout_box)
        self.maxidle = QSpinBox(self)
        self.maxidle.setRange(0, 300)
        qf2.addWidget(QLabel("Timeout (sec.)"), 0, 0)
        qf2.addWidget(self.maxidle, 0, 1)
        self.clic_exit = Toggle(self)
        self.clic_exit.setMaximumSize(60, 30)
        qf2.addWidget(QLabel("Esce con un clic)"), 1, 0)
        qf2.addWidget(self.clic_exit, 1, 1)

        #vb.addWidget(timeout_box)
        vg.addWidget(timeout_box,0, 1)

        auto_gain_box = QGroupBox(self)
        auto_gain_box.setTitle("Regolazione automatica del volume")
        hs = QHBoxLayout(auto_gain_box)
        self.gain_msg = QLabel(self)
        hs.addWidget(self.gain_msg)
        self.gain = Toggle(self)
        self.gain.setMaximumSize(60, 30)
        self.gain.clicked.connect(self.gain_state)
        hs.addWidget(self.gain)

        #vb.addWidget(auto_gain_box)
        vg.addWidget(auto_gain_box, 1, 1)

        speaker_box = QGroupBox(self)
        speaker_box.setTitle('Annunciatore')
        vs = QVBoxLayout(speaker_box)
        hc = QHBoxLayout()
        hc.addWidget(QLabel('Genere'))
        self.c2 = QComboBox()
        self.c2.addItems(['Uomo', 'Donna'])
        hc.addWidget(self.c2)
        vs.addLayout(hc)
        hc = QHBoxLayout()
        hc.addWidget(QLabel('Volume'))
        self.speker_volume = QSpinBox(self)
        self.speker_volume.setRange(-100, +0)
        self.speker_volume.setSingleStep(10)
        hc.addWidget(self.speker_volume)
        vs.addLayout(hc)

        #vb.addWidget(speaker_box)
        vg.addWidget(speaker_box, 2, 0)

        vb.addLayout(vg)
        vb.addLayout(exitBtn(self))

        self.load_from_config()

    def load_from_config(self):
        lang = self.ini.get('user', 'lang')
        self.c1.setCurrentText(lang)

        tmout = self.ini.get('user', 'tmout')
        try:
            tmout = int(tmout)
        except:
            tmout = 0
        self.maxidle.setValue(tmout)

        clic_exit = self.ini.get('user', 'clic_exit')
        clic_exit = Qt.CheckState.Unchecked if clic_exit == '' or clic_exit == '0' else Qt.CheckState.Checked
        self.clic_exit.setCheckState(clic_exit)

        gain = self.ini.get('user', 'auto_gain')
        gain = Qt.CheckState.Unchecked if gain == '' or gain == '0' else Qt.CheckState.Checked
        self.gain.setCheckState(gain)
        self.gain_state()

        cache = self.ini.get('cache')
        if not cache:
            cachedir = os.path.join(ConfDir(AppConfig), 'cache')
            cache = {'dir': cachedir, 'max_size': 100, 'duration': 90}
        self.cache_dir.setText(cache['dir'])
        self.cache_days.setText(str(cache['duration']))
        self.cache_size.setText(str(cache['max_size']))

        speaker = self.ini.get('speaker')
        if not speaker:
            speaker = {'gender': 'Donna', 'volume': '0'}
        self.c2.setCurrentText(speaker['gender'])
        vol = speaker['volume']
        try:
            vol = int(vol)
        except:
            vol = 0
        self.speker_volume.setValue(vol)

    def cachepath(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder', self.cache_dir.text())

    def gain_state(self):
        if self.gain.isChecked():
            self.gain_msg.setText("Attivo")
        else:
            self.gain_msg.setText("Non Attivo")

    def accept(self):
        lang = self.c1.currentText()
        self.ini.set('user', 'lang', lang)
        tmout = str(self.maxidle.value())
        self.ini.set('user', 'tmout', tmout)
        clic_exit = 1 if self.clic_exit.isChecked() else 0
        self.ini.set('user', 'clic_exit', str(clic_exit))
        gain = 1 if self.gain.isChecked() else 0
        self.ini.set('user', 'auto_gain', str(gain))

        cs = {
            "dir": self.cache_dir.text(),
            "duration": str(self.cache_days.text()),
            "max_size": str(self.cache_size.text()),
        }
        self.ini.set_sez("cache", cs)

        spk = {
            "gender": self.c2.currentText(),
            "volume": str(self.speker_volume.value())
        }
        self.ini.set_sez("speaker", spk)

        self.ini.save()

        self.done(1)

    @staticmethod
    def run(parent, ini):
        return ConfigBox(parent, ini).exec()
