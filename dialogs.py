import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QTextCursor, QIcon, QCursor
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QSplitter, QHBoxLayout, QWidget, QStyle, QCheckBox,
                             QListWidget, QPushButton, QTableWidget, QLineEdit, QTableWidgetItem, QHeaderView,
                             QPlainTextEdit, QAbstractItemView, QMenu)

import scrobbler
from pyradios import RadioBrowser
from googletrans import Translator

from pyMyLib.qtUtils import exitBtn, center_in_parent, set_background, yesNoMessage
from pyMyLib.utils import iniConf, get_resource_file

from threading import Thread

'''
https://github.com/andreztz/pyradios/tree/main/pyradios
'''

AppConfig = 'Euterpe'

def create_cursor(png_path, width=20, height=20, hotspot_x=10, hotspot_y=10):
    pixmap = QPixmap(png_path)
    scaled_pixmap = pixmap.scaled(width, height)
    return QCursor(scaled_pixmap, hotspot_x, hotspot_y)

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
                self.setCursor(create_cursor(get_resource_file(__file__, 'icone', 'play.png')))

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
                    self.unsetCursor()
                    self.wparent.play_item(self)
                except:
                    pass
        super(QListWidget, self).mousePressEvent(event)

def lyric_song(artist, track, parent=None):
    txt = scrobbler.song_text(artist, track)
    if len(txt) > 0:
        lyricsDlg.run(parent, txt, track)

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

    def onCellClicked(self, nr, nc):
        if nc == 3:
            qi = self.table.item(0, 0)
            dat = qi.data(Qt.ItemDataRole.UserRole)
            url = dat.url
            self.wparent.open_radio(url, dat.favicon)

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
        super(lyricsDlg, self).__init__(parent)
        self.wparent = parent
        self.txt = txt.lstrip()
        center_in_parent(self, parent, 600, 500)
        self.setWindowTitle(track)

        v = QVBoxLayout(self)
        self.h = QHBoxLayout()
        self.txt_box = myPlainText(self)
        self.tr = Translator()
        lang = self.tr.detect(txt).lang

        self.txt_box.setText(self.txt)
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

        self.txt_box.selectionChanged.connect(self.sync)

        tr_box.setText(txt1.text)
        sz = self.size()
        sz.setWidth(sz.width() * 2)
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
        if txt:
            self.search()

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
    def run(parent, music, txt=''):
        dlg = mySearch(parent, music, txt)
        if dlg.exec() == 1:
            return dlg.selected
        return None

class configDlg(QDialog):
    def __init__(self, parent):
        super(configDlg, self).__init__(parent)
        self.wparent = parent

        v = QVBoxLayout(self)
        ini = iniConf(AppConfig)
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

        ini = iniConf(AppConfig)
        s = ini.get('MAIN')
        if s is None:
            s = {}
        s['splittermode'] = v
        ini.set_sez('MAIN', s)
        ini.save()

        self.done(1)

    @staticmethod
    def run(parent):
        dlg = configDlg(parent).exec()


