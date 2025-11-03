import random
from typing import Set, Tuple

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QIntValidator, QIcon
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QAbstractItemView, QTableWidgetItem, QPushButton, \
    QHeaderView, QGroupBox, QLabel, QLineEdit, QSpinBox, QHBoxLayout

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
        artisti_pesati = [p['nome'] for p in preferences]
        pesi = [p['peso']for p in preferences]
        while durata_totale < durata_target and tentativi_falliti < max_tentativi and artisti_pesati:
            # 1. Seleziona artista in base al peso
            artista = random.choices(artisti_pesati, weights=pesi, k=1)[0]

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
            if durata_totale + durata_traccia > durata_target:
                # Se abbiamo già delle tracce, ci fermiamo
                break
            t = (artista, album.title, track)
            if t in self.tracce_usate:
                tentativi_falliti += 1
                continue

            # Aggiungi traccia alla playlist
            self.tracce_usate.add(t)
            durata_totale += durata_traccia
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
        self.setWindowIcon(QIcon(get_resource_file(__file__, 'icone', 'playlist.png')))
        self.setMinimumSize(300, 500)
        self.setup_ui()

    def setup_ui(self):
        vlayout = QVBoxLayout(self)
        self.table = QTableWidget(self)
        self.fields = ["Artista", "Peso"]
        self.table.setColumnCount(len(self.fields))
        self.table.setHorizontalHeaderLabels(self.fields)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 60)

        self.table.setShowGrid(True)
        for artist in self.index.artists.name.keys():
            numRows = self.table.rowCount()
            self.table.insertRow(numRows)
            qi = QTableWidgetItem(artist)
            self.table.setItem(numRows, 0, qi)

        vlayout.addWidget(self.table)
        self.dw = DurationWidget()
        vlayout.addWidget(self.dw)

        bt_crea = QPushButton()
        bt_crea.setText("Crea Playlist")
        bt_crea.clicked.connect(self.crea)

        vlayout.addWidget(bt_crea)

    def crea(self):
        numRows = self.table.rowCount()
        preferences = []
        for row in range(numRows):
            try:
                artist = self.table.item(row, 0).text()
                peso = self.table.item(row, 1).text()
                if peso:
                    preferences = preferences + [{'nome': artist, 'peso': int(peso)}]
            except:
                continue
        duration = self.dw.get_duration_seconds()
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


