from PyQt6.QtCore import Qt, pyqtSignal, QStringListModel, QTimer
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QSplitter, QWidget, QHeaderView, \
    QAbstractItemView, QTableWidgetItem, QStyle, QMenu, QTableWidget, QListWidgetItem, QCompleter, QGroupBox
from PyQt6.QtGui import QPixmap, QIcon, QAction

from pyMyLib.qtUtils import set_background, yesNoMessage, waitCursor
from pyMyLib.utils import get_resource_file
from utility import myList

'''
https://streamurl.link/ per trovare stazioni radio
'''

class RadioDlg(QDialog):
    radio_signal = pyqtSignal(str, str)
    def __init__(self, parent):
        super(RadioDlg, self).__init__(parent)
        self.ini = parent.ini
        self.wparent = parent
        self.x_aggiunta = False
        self.setObjectName("radio_widget")
        set_background(self)

        v = QVBoxLayout(self)
        v.setContentsMargins(1, 1, 1, 1)

        #h = QHBoxLayout()
        #h.setContentsMargins(1, 1, 1, 1)
        self.ed = QLineEdit(self)
        self.ed.returnPressed.connect(self.search)
        self.ed.setStyleSheet("""
            QLineEdit {
                /* Dai spazio a due icone (circa 50-60px) */
                padding-right: 55px; 
            }
        """)
        #h.addWidget(self.ed)

        # 1. Azione Cerca (Sempre visibile)
        icona_cerca = QIcon(get_resource_file(__file__, 'icone', 'search.png'))
        self.azione_cerca = QAction(icona_cerca, "Cerca", self)
        self.azione_cerca.triggered.connect(self.search)

        # 2. Azione Cancella (Inizialmente nascosta)
        icona_cancella = QIcon(get_resource_file(__file__, 'icone', 'delete.png'))  # Usa la tua icona X
        self.azione_cancella = QAction(icona_cancella, "Cancella", self)
        self.azione_cancella.setVisible(False)
        self.azione_cancella.triggered.connect(lambda: self.ed.clear())

        # Aggiunta alla QLineEdit (L'ordine di aggiunta determina la posizione)
        self.ed.addAction(self.azione_cerca, QLineEdit.ActionPosition.TrailingPosition)
        #self.ed.addAction(self.azione_cancella, QLineEdit.ActionPosition.TrailingPosition)
        self.azione_cancella.setVisible(False)

        # Collegamento per gestire la visibilità
        self.ed.textChanged.connect(self.gestisci_pulsante_clear)
        self.gestisci_pulsante_clear(self.ed.text())

        # Nel setup della tua UI
        self.ultime_ricerche = self.last_searches()  # Carica queste stringhe dal tuo ConfigParser
        self.completer_model = QStringListModel(self.ultime_ricerche)
        self.completer = QCompleter(self.completer_model, self)

        # Configurazione per mostrare subito i suggerimenti
        self.completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        # Applica alla tua QLineEdit (quella con la QAction per la lente)
        self.ed.setCompleter(self.completer)

        sp = QSplitter(self)
        sp.setOrientation(Qt.Orientation.Vertical)

        v1 = QVBoxLayout()
        v1.setContentsMargins(1, 1, 1, 1)
        v1.addWidget(self.ed)
        self.table = QTableWidget(self)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(lambda pos: self.contextMenu(pos, None, None) )
        v1.addWidget(self.table)

        w = QGroupBox() #QWidget()
        w.setLayout(v1)
        sp.addWidget(w)

        self.favorites = myList(self)

        self.favorites.setStyleSheet("""
                QListWidget {
                    background-color: #f5f5f5;
                    border: 1px solid #d0d0d0;
                    border-radius: 4px;
                    outline: none;
                }
                
                QListWidget::item {
                    background-color: transparent;
                    /* Riduciamo il padding verticale al minimo (2px sopra e sotto) */
                    padding: 2px 8px; 
                    /* Azzeriamo il margine per attaccare le righe */
                    margin: 0px;
                    color: #333333;
                    /* Un'altezza fissa opzionale se vuoi precisione assoluta */
                    min-height: 20px; 
                }
                
                QListWidget::item:hover {
                    background-color: #e8e8e8;
                    color: #FF0000;
                }
                
                QListWidget::item:selected {
                    background-color: #e0e0e0;
                    color: #FF0000;
                    /* Riduciamo lo spessore della barra laterale per non appesantire */
                    border-left: 2px solid #FF0000; 
                }            
          """)
        self.favorites.doubleClicked.connect(self.play)
        self.favorites.itemSelectionChanged.connect(self.favorite_changed)
        sp.addWidget(self.favorites)
        v.addWidget(sp)

        rd = self.ini.get('radio')
        if rd is not None:
            for key, val in rd.items():
                item = QListWidgetItem(key)
                item.setData(Qt.ItemDataRole.UserRole, val)
                self.favorites.addItem(item)
                try:
                    url = val.split('@')[0]
                    item.setToolTip(url)
                except:
                    pass

        QTimer.singleShot(0, lambda: self.azione_cancella.setVisible(bool(self.ed.text())))

    def gestisci_pulsante_clear(self, testo):
        if testo:
            # La aggiungiamo solo quando serve
            if not self.x_aggiunta:
                self.ed.addAction(self.azione_cancella, QLineEdit.ActionPosition.TrailingPosition)
                # IMPORTANTE: Se la aggiungi ora, finirà a sinistra della lente
                # se la lente era stata aggiunta per prima.
                self.x_aggiunta = True
            self.azione_cancella.setVisible(True)
        elif not testo and self.x_aggiunta:
            self.azione_cancella.setVisible(False)

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
            if a:
                self.update_last_searches()
            waitCursor()

    def load_icons(self, list):
        import scrobbler
        row = 0
        for l in list:
            if 'ref' in l['url']:
                continue
            im = scrobbler.get_thumbnail(l['favicon'])
            if im is not None:
                try:
                    qii = self.table.item(row, 1)
                    qp = QPixmap()
                    qp.loadFromData(im)
                    qii.setIcon(QIcon(qp))
                except:
                    continue
            row += 1

    def fill_table(self, rList):
        from threading import Thread
        self.table.setRowCount(0)
        if len(rList) == 0:
            return
        radios = []
        s = set()
        for l in rList:
            if 'ref' in l['url'] or l['url'] in s:
                continue
            if l['lastcheckok'] == 0:
                continue
            s.add(l['url'])
            r = RadioStation(l['name'], l['url'], None, l['country'], l['favicon'], l['bitrate'], l['codec'])
            radios.append(r)

        searcher = Thread(target=self.load_icons, args=(rList,))
        searcher.start()

        fields = ['Nome', 'icon', 'paese', 'codec', ' ']
        self.table.setColumnCount(len(fields))
        self.table.setHorizontalHeaderLabels(fields)
        self.table.cellClicked.connect(self.onCellClicked)

        horizontalHeader = self.table.horizontalHeader()
        horizontalHeader.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) #nome
        horizontalHeader.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed) #icona
        horizontalHeader.resizeSection(1, 30)
        horizontalHeader.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        #horizontalHeader.resizeSection(2, 80) #paese
        horizontalHeader.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        #horizontalHeader.resizeSection(3, 80)# codec
        horizontalHeader.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed) # pulsante play
        horizontalHeader.resizeSection(4, 30)
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
            self.table.setItem(numRows, 3, QTableWidgetItem(r.codec))

            qi1 = QTableWidgetItem()
            qi1.setIcon(self.style().standardIcon(getattr(QStyle.StandardPixmap, 'SP_MediaPlay')))
            self.table.setItem(numRows, 4, qi1)
            self.table.setColumnWidth(4, 10)

    def contextMenu(self, pos, wd, it):
        ctx = QMenu(self)
        if not wd:
            index = self.table.indexAt(pos)
            if not index.isValid():
                return  # Clic fuori dalle righe caricate

            row = index.row()
            it = self.table.item(row, 0)

            ctx.addAction("Aggiunge ai preferiti").triggered.connect(lambda x: self.add_favourites(it))
            ctx.exec(self.table.mapToGlobal(pos))
        else:
            ctx.addAction("Rimuove dai preferiti").triggered.connect(lambda x: self.del_favourites(it))
            ctx.exec(pos)

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
        if nc == 4:
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
        dat = self.favorites.selectedItems()[0].data(Qt.ItemDataRole.UserRole)
        #rad = self.favorites.selectedItems()[0].text()
        #rd = self.ini.get('radio')
        dat = dat.split('@')
        url = dat[0]
        fav = ''
        if len(dat) > 1:
            fav = dat[1]
        self.radio_signal.emit(url, fav)

    def last_searches(self):
        return self.ini.get('radio-searches', 'recent').split(',')

    def update_last_searches(self):
        txt = self.ed.text()
        if txt and txt not in self.ultime_ricerche:
            self.ultime_ricerche.insert(0, txt)
        if len(self.ultime_ricerche) > 4:
            self.ultime_ricerche = self.ultime_ricerche[:4]

        self.completer_model = QStringListModel(self.ultime_ricerche)
        self.completer.setModel(self.completer_model)

        slist = ",".join(self.ultime_ricerche)
        self.ini.set('radio-searches', 'recent', slist)
        self.ini.save()



class RadioStation:
    def __init__(self, name='', url='', ico=None, paese='', favicon='', bitrate=0, codec=''):
        self.name = name
        self.url = url
        self.ico = ico
        self.paese = paese
        self.favicon = favicon
        self.bitrate = bitrate
        self.codec = codec