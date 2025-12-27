from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QSplitter, QWidget, QHeaderView, \
    QAbstractItemView, QTableWidgetItem, QStyle, QMenu, QTableWidget
from PyQt6.QtGui import QPixmap, QIcon, QAction

from pyMyLib.qtUtils import set_background, yesNoMessage, waitCursor
from pyMyLib.utils import iniConf, get_resource_file
from dialogs import myList

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
    radio_signal = pyqtSignal(str, str)
    def __init__(self, parent):
        super(RadioDlg, self).__init__(parent)
        self.ini = parent.ini
        self.wparent = parent
        self.setObjectName("radio_widget")
        set_background(self)

        v = QVBoxLayout(self)

        h = QHBoxLayout()
        h.setContentsMargins(1, 1, 1, 1)
        self.ed = QLineEdit(self)
        self.ed.returnPressed.connect(self.search)
        h.addWidget(self.ed)

        icona_cerca = QIcon(get_resource_file(__file__, 'icone', 'search.png'))
        azione_cerca = QAction(icona_cerca, "Cerca", self)
        azione_cerca.triggered.connect(self.search)
        self.ed.addAction(
            azione_cerca,
            QLineEdit.ActionPosition.TrailingPosition  # Posizione a destra (Trailing)
        )

        sp = QSplitter(self)
        sp.setOrientation(Qt.Orientation.Vertical)

        v1 = QVBoxLayout()
        v1.setContentsMargins(1, 1, 1, 1)
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
        from pyradios import RadioBrowser
        src = self.ed.text()
        if len(src) > 0:
            waitCursor(True)
            rb = RadioBrowser()
            a = rb.search(name=src, name_exact=False, hidebroken=True,
                          limit=50,  # Limita i risultati per non bloccare la UI
                          order="clickcount",  # Mostra prima le più popolari (più probabile siano attive)
                          reverse=True
                          )
            self.fill_table(a)
            waitCursor()

    def load_icons(self, list):
        import scrobbler
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
        from threading import Thread
        self.table.setRowCount(0)
        if len(rList) == 0:
            return
        radios = []
        for l in rList:
            if 'ref' in l['url']:
                continue
            r = RadioStation(l['name'], l['url'], None, l['country'], l['favicon'], l['bitrate'], l['codec'])
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

        max_name_len = 40
        for r in radios:
            numRows = self.table.rowCount()

            self.table.insertRow(numRows)
            name = r.name
            if len(name) > max_name_len:
                name = name[:max_name_len]
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

        if len(k) > 0:
            if yesNoMessage('Sostituzione', 'Esiste già una emittente di nome ' + nome + ' sostituirla?'):
                self.del_favourites(k[0])
            else:
                return

        rd = self.ini.get('radio')
        if rd is None:
            rd = {}
        rd[nome] = r.url + '@' + r.favicon
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
            qi = self.table.item(nr, 0)
            dat = qi.data(Qt.ItemDataRole.UserRole)
            url = dat.url
            self.radio_signal.emit(url, dat.favicon)

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
        dat = rd[rad].split('@')
        url = dat[0]
        fav = ''
        if len(dat) > 1:
            fav = dat[1]
        self.radio_signal.emit(url, fav)

class RadioStation:
    def __init__(self, name='', url='', ico=None, paese='', favicon='', bitrate=0, codec=''):
        self.name = name
        self.url = url
        self.ico = ico
        self.paese = paese
        self.favicon = favicon
        self.bitrate = bitrate
        self.codec = codec