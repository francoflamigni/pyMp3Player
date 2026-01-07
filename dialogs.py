from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QTextCursor, QIcon, QCursor, QFontMetrics, QAction
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QSplitter, QHBoxLayout, QWidget, QStyle,
                             QListWidget, QPushButton, QTableWidget, QLineEdit, QTableWidgetItem, QHeaderView,
                             QPlainTextEdit, QAbstractItemView, QMenu, QLabel, QGroupBox, QComboBox, QFormLayout,
                             QSpinBox)

import scrobbler

from pyMyLib.qtUtils import exitBtn, center_in_parent, set_background, yesNoMessage, waitCursor
from pyMyLib.utils import iniConf, get_resource_file

from threading import Thread

'''
https://github.com/andreztz/pyradios/tree/main/pyradios
'''

AppConfig = 'Euterpe'



def lyric_song(artist, track, parent=None):
    from scrobbler import LyricsWorker
    ls = LyricsWorker(artist, track)
    txt = ls.song_text2()
    if len(txt) > 0:
        lyricsDlg.run(parent, txt, track)

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
    def __init__(self, parent, txt, track=''):
        from googletrans import Translator
        super(lyricsDlg, self).__init__(parent)
        self.wparent = parent
        self.txt = txt.lstrip()
        center_in_parent(self, parent, 600, 500)
        self.setWindowTitle(track)
        self.setWindowIcon(QIcon(get_resource_file(__file__, 'icone', 'lyric.png')))

        v = QVBoxLayout(self)
        self.h = QHBoxLayout()
        self.h.setContentsMargins(3, 3, 3, 3)
        self.h.setSpacing(5)
        self.txt_box = myPlainText(self)
        self.tr = Translator()
        lang = self.tr.detect(txt).lang
        self.app_lang = parent.ini.get('user', 'lang')
        self.tr_box = None

        self.txt_box.setText(self.txt)
        self.h.addWidget(self.txt_box)
        v.addLayout(self.h)

        if lang != self.app_lang:
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
    def run(parent, txt, track=''):
        dlg = lyricsDlg(parent, txt, track)
        dlg.exec()

class mySearch(QDialog):
    def __init__(self, parent, music, txt):
        super(mySearch, self).__init__(parent)
        center_in_parent(self, parent, 600, 400)
        self.setWindowTitle('Cerca')

        self.wparent = parent
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
        self.list.doubleClicked.connect(self.selection)

        v = QVBoxLayout(self)
        v.addLayout(h)
        v.addWidget(self.list)
        self.selected = None
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

    def selection(self):
        s = self.list.selectedItems()
        if len(s) > 0:
            self.selected = s[0].text()
            self.done(1)

    @staticmethod
    def run(parent, music, txt=''):
        dlg = mySearch(parent, music, txt)
        if dlg.exec() == 1:
            return dlg.selected
        return None

''' finestra principale per le opzioni e la configurazione'''
class ConfigBox(QDialog):
    def __init__(self, parent, ini:iniConf):
        super().__init__()
        self.ini = ini
        self.ini.config_read()
        lang = self.ini.get('user', 'lang')

        self.setWindowTitle('Preferenze')
        center_in_parent(self, parent, 200, 160)
        vb = QVBoxLayout(self)

        qf1 = QFormLayout(self)
        qf1.addWidget(QLabel('Lingua preferita'))
        self.c1 = QComboBox()
        self.c1.addItems(['IT', 'FR', 'EN', 'SP'])
        self.c1.setCurrentText(lang)
        qf1.addWidget(self.c1)
        tmout = self.ini.get('user', 'tmout')
        try:
            tmout = int(tmout)
        except:
            tmout = 0
        vb.addLayout(qf1)

        qf2 = QFormLayout(self)
        qf2.addWidget(QLabel('Timeout background'))
        self.maxidle = QSpinBox(self)
        self.maxidle.setRange(0, 300)
        self.maxidle.setValue(tmout)
        qf2.addWidget(self.maxidle)
        vb.addLayout(qf2)

        vb.addLayout(exitBtn(self))

    def accept(self):
        lang = self.c1.currentText()
        self.ini.set('user', 'lang', lang)
        tmout = str(self.maxidle.value())
        self.ini.set('user', 'tmout', tmout)
        self.ini.save()

        self.done(1)

    @staticmethod
    def run(parent, ini):
        return ConfigBox(parent, ini).exec()
