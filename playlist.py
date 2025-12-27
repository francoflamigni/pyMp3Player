import random
from typing import Set, Tuple

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIntValidator, QIcon
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QAbstractItemView, QTableWidgetItem, QPushButton, \
    QHeaderView, QGroupBox, QLabel, QLineEdit, QSpinBox, QHBoxLayout, QComboBox, QLayout

from pyMyLib.utils import get_resource_file

from mp3_tag import Music

class GeneratorePesato:
    def __init__(self, index):
        """
        attori: lista di dizionari {'nome': str, 'peso': float}
        """
        self.index = index
        self.tracce_usate: Set[Tuple[str, str, str]] = set()

    def plst(self, preferences, durata_target):
        playlist = []
        durata_totale = 0
        tentativi_falliti = 0
        max_tentativi = 100  # Evita loop infiniti
        max_tentativi_artista = 5
        artisti_pesati = [p['nome'] for p in preferences]
        pesi = [float(p['peso']) for p in preferences]
        tol_durata = 240
        if not artisti_pesati:
            return  self.tracce_usate
        while tentativi_falliti < max_tentativi and durata_totale < durata_target:
            # 1. Seleziona artista in base al peso
            artista = random.choices(artisti_pesati, weights=pesi, k=1)[0]

            tentativi_artista = max_tentativi_artista
            while tentativi_artista:
                tentativi_artista -= 1

                # 2. Seleziona album casuale
                albums = self.index.find_albums(artista)
                if not albums:
                    tentativi_falliti += 1
                    continue

                album = random.choice(albums)

                # 3. Seleziona traccia casuale non ancora usata
                tracks = self.index.find_tracks(album.title, artista)

                if not tracks:
                    tentativi_falliti += 1
                    continue

                track = random.choice(tracks)
                durata_traccia = self.index.tracks.name[track + '@' + album.title].tm_sec

                # Verifica se aggiungere la traccia supera la durata target
                d1 = durata_totale + durata_traccia
                if d1 < durata_target:
                    t = (artista, album.title, track)
                    if t in self.tracce_usate:
                        tentativi_falliti += 1
                        continue
                    self.tracce_usate.add(t)
                    durata_totale = d1
                    tentativi_artista = 0
                elif d1 > durata_target + tol_durata:
                    tentativi_falliti += 1
                    continue
                else:
                    tentativi_artista = 0

        return list(self.tracce_usate)

    def seleziona(self):
        """Seleziona un attore in base ai pesi"""
        # Genera un numero casuale tra 0 e il totale dei pesi
        casuale = random.random() * self.totale

        # Trova l'attore corrispondente
        for attore in self.attori:
            casuale -= attore['peso']
            if casuale <= 0:
                return attore['nome']

        # Fallback (non dovrebbe mai accadere)
        return self.attori[-1]['nome']


def Create_playlist(index: Music, preference, duration):
    gen = GeneratorePesato(index)
    play = gen.plst(preference, duration)
    return play


class DurationWidget(QGroupBox):
    """Widget per l'impostazione di una durata in ore e minuti."""

    # Segnale emesso quando la durata cambia (valore in secondi)
    durationChanged = pyqtSignal(int)

    def __init__(self, title="Durata", parent=None):
        super().__init__(title, parent)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Configura l'interfaccia utente."""
        layout = QHBoxLayout()

        # Campo ore
        self.hours_label = QLabel("Ore:")
        self.hours_edit = QLineEdit()
        self.hours_edit.setMaximumWidth(50)
        self.hours_edit.setText("0")
        self.hours_edit.setValidator(QIntValidator(0, 999))

        # Campo minuti
        self.minutes_label = QLabel("Minuti:")

        # SpinBox per incrementare/decrementare i minuti
        self.minutes_spin = QSpinBox()
        self.minutes_spin.setMinimum(-1)
        self.minutes_spin.setMaximum(60)
        self.minutes_spin.setValue(0)
        self.minutes_spin.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows)
        self.minutes_spin.setWrapping(False)

        # Aggiungi widgets al layout
        layout.addWidget(self.hours_label)
        layout.addWidget(self.hours_edit)
        layout.addWidget(self.minutes_label)
        #layout.addWidget(self.minutes_edit)
        layout.addWidget(self.minutes_spin)
        layout.addStretch()

        self.setLayout(layout)

    def _connect_signals(self):
        """Connette i segnali dei widget."""
        self.hours_edit.textChanged.connect(self._on_hours_changed)
        #self.minutes_edit.textChanged.connect(self._on_minutes_changed)
        self.minutes_spin.valueChanged.connect(self._on_spin_changed)

    def _on_hours_changed(self, text):
        """Gestisce il cambio del valore delle ore."""
        if text == "":
            return
        self._emit_duration_changed()

    def _on_minutes_changed(self, text):
        """Gestisce il cambio del valore dei minuti."""
        if text == "":
            return

        # Verifica congruenza (0-59)
        try:
            minutes = int(text)
            if minutes > 59:
                #self.minutes_edit.setText("59")
                minutes = 59
            elif minutes < 0:
                #self.minutes_edit.setText("0")
                minutes = 0

            # Sincronizza con lo spin box
            self.minutes_spin.blockSignals(True)
            self.minutes_spin.setValue(minutes)
            self.minutes_spin.blockSignals(False)

        except ValueError:
            pass

        self._emit_duration_changed()

    def _on_spin_changed(self, value):
        """Gestisce il cambio del valore dello spin box."""
        current_minutes = self.get_minutes()
        current_hours = self.get_hours()

        # Calcola la differenza
        diff = value - current_minutes

        # Calcola nuovi valori
        new_minutes = current_minutes + diff
        new_hours = current_hours

        # Gestisce overflow/underflow
        while new_minutes >= 60:
            new_minutes -= 60
            new_hours += 1

        while new_minutes < 0 and new_hours > 0:
            new_minutes += 60
            new_hours -= 1

        # Assicura che non si vada sotto zero
        if new_hours < 0:
            new_hours = 0
            new_minutes = 0

        # Aggiorna i valori
        self.hours_edit.blockSignals(True)
        #self.minutes_edit.blockSignals(True)

        self.hours_edit.setText(str(new_hours))
        #self.minutes_edit.setText(str(new_minutes))

        # Reset dello spin box al nuovo valore dei minuti
        self.minutes_spin.blockSignals(True)
        self.minutes_spin.setValue(new_minutes)
        self.minutes_spin.blockSignals(False)

        self.hours_edit.blockSignals(False)
        #self.minutes_edit.blockSignals(False)

        self._emit_duration_changed()

    def _emit_duration_changed(self):
        """Emette il segnale di cambio durata."""
        self.durationChanged.emit(self.get_duration_seconds())

    def get_hours(self):
        """Ritorna le ore impostate."""
        try:
            return int(self.hours_edit.text()) if self.hours_edit.text() else 0
        except ValueError:
            return 0

    def get_minutes(self):
        """Ritorna i minuti impostati."""
        try:
            return int(self.minutes_spin.text()) if self.minutes_spin.text() else 0
        except ValueError:
            return 0

    def set_hours(self, hours):
        """Imposta le ore."""
        self.hours_edit.setText(str(max(0, hours)))

    def set_minutes(self, minutes):
        """Imposta i minuti."""
        minutes = max(0, min(59, minutes))
        #self.minutes_edit.setText(str(minutes))
        self.minutes_spin.setValue(minutes)

    def get_duration_seconds(self):
        """Ritorna la durata totale in secondi."""
        hours = self.get_hours()
        minutes = self.get_minutes()
        return hours * 3600 + minutes * 60

    def set_duration_seconds(self, seconds):
        """Imposta la durata da un valore in secondi."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        self.set_hours(hours)
        self.set_minutes(minutes)

class PlayListDlg(QDialog):
    def __init__(self, parent, index: Music):
        super().__init__(parent)
        self.index = index
        self.setWindowTitle("Crea Playlist")
        self.setWindowIcon(QIcon(get_resource_file(__file__, 'icone', 'create_playlist.png')))
        self.setMinimumSize(300, 500)

        self.combo_options = [" ", "\U00002B50", "\U00002B50\U00002B50", "\U00002B50\U00002B50\U00002B50",
                              "\U00002B50\U00002B50\U00002B50\U00002B50",
                              "\U00002B50\U00002B50\U00002B50\U00002B50\U00002B50"]
        self.current_combo = None  # Tiene traccia del combo box attivo
        self._current_row = -1
        #self._current_col = -1
        self.setup_ui()

    def setup_ui(self):
        vlayout = QVBoxLayout(self)
        self.table = QTableWidget(self)
        self.fields = ["Artista", "Preferenza"]
        self.table.setColumnCount(len(self.fields))
        self.table.setHorizontalHeaderLabels(self.fields)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 120)
        self.table.cellClicked.connect(self.handle_cell_clicked)

        self.table.setShowGrid(True)
        for artist in self.index.artists.name.keys():
            numRows = self.table.rowCount()
            self.table.insertRow(numRows)
            qi = QTableWidgetItem(artist)
            self.table.setItem(numRows, 0, qi)
        self.table.sortItems(0, Qt.SortOrder.AscendingOrder)

        vlayout.addWidget(self.table)
        self.dw = DurationWidget()
        vlayout.addWidget(self.dw)

        bt_crea = QPushButton()
        bt_crea.setText("Crea Playlist")
        bt_crea.clicked.connect(self.crea)

        vlayout.addWidget(bt_crea)
        self.setup_geometry()
        #self.layout().setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

    def setup_geometry(self):
        # 1. Adattiamo le colonne al contenuto
        # Colonna 0 (es. numero o icona) e Colonna 1 (testo lungo)
        #self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        #self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

        # 2. Calcoliamo la larghezza totale necessaria
        # Sommiamo la larghezza delle colonne + intestazione verticale (se visibile)
        v_header_width = self.table.verticalHeader().width() if self.table.verticalHeader().isVisible() else 0
        total_width = v_header_width + self.table.columnWidth(0) + self.table.columnWidth(1) + 50

        # 3. Impostiamo le dimensioni della TABELLA
        self.table.setFixedWidth(total_width)
        self.table.setFixedHeight(500)  # <--- IMPOSTA QUI L'ALTEZZA VERTICALE CHE DESIDERI

        # 4. Forziamo la DIALOG ad adattarsi alla tabella
        # Rimuoviamo i margini del layout per non avere bordi vuoti
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

    def handle_cell_clicked(self, row, column):

        # Rimuovi l'editor precedente prima di crearne uno nuovo
        self.remove_current_editor()

        # Vogliamo l'editor solo sulla COLONNA 1 (la seconda)
        if column != 1:
            return

        # 1. Ottieni il testo corrente della cella
        current_item = self.table.item(row, column)
        current_text = current_item.text() if current_item else ""

        # 2. Crea e configura il QComboBox
        combo = QComboBox(self)
        combo.addItems(self.combo_options)

        # 3. Imposta l'elemento corrente (se presente nella lista)
        index = combo.findText(current_text)
        if index >= 0:
            combo.setCurrentIndex(index)

        # 4. Connetti il segnale per chiudere il combo e salvare il valore
        # Usiamo activated/currentIndexChanged per l'evento di selezione
        combo.currentIndexChanged.connect(
            lambda index: self.save_and_remove_editor(row, column, combo)
        )
        self._current_row = row

        # 5. Inserisci il combo box nella cella e traccia il riferimento
        self.table.setCellWidget(row, column, combo)
        self.current_combo = combo
        combo.showPopup()

    def save_and_remove_editor(self, row, column, combo):
        """Salva il valore selezionato e rimuove il combo box."""

        new_text = combo.currentText()

        # 1. Rimuovi il QComboBox dalla cella
        self.table.removeCellWidget(row, column)
        self._current_row = -1
        self.current_combo = None

        # 2. Aggiorna il valore della cella
        # Devi creare un nuovo QTableWidgetItem se la cella è vuota,
        # altrimenti aggiorna quello esistente

        new_item = self.table.item(row, column)
        if new_item is None:
            new_item = QTableWidgetItem(new_text)
            self.table.setItem(row, column, new_item)
        else:
            new_item.setText(new_text)

    def remove_current_editor(self):
        """Rimuove il combo box attivo (necessario se l'utente clicca altrove)."""
        if self.current_combo is not None:
            # Il QComboBox viene rimosso dal layout della cella
            self.table.removeCellWidget(self._current_row, 1)
            self.current_combo.deleteLater()
            self.current_combo = None
            self._current_row = -1

    def crea(self):
        numRows = self.table.rowCount()
        preferences = []
        for row in range(numRows):
            try:
                artist = self.table.item(row, 0).text()
                ps = self.table.item(row, 1).text()
                peso = len(ps)
                if peso:
                    preferences = preferences + [{'nome': artist, 'peso': int(peso)}]
            except:
                continue
        duration = self.dw.get_duration_seconds()
        if not duration:
            self.dw.hours_edit.setFocus()
            self.dw.hours_edit.selectAll()
            return
        a = 0
        self.list = Create_playlist(self.index, preferences, duration)
        if self.list:
            stat = {}
            for t in self.list:
                if t[0] in stat.keys():
                    n = stat[t[0]]
                    stat[t[0]] = n + 1
                else:
                    stat[t[0]] = 1

            self.done(1)

    def get_playlist(self):
        return self.list


