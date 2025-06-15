import sys
import os
import re
import soundfile as sf
import lameenc
import numpy as np
from pathlib import Path
from mutagen import File
from mutagen.id3 import ID3NoHeaderError, ID3, TIT2, TPE1, TALB, TDRC, TCON, TRCK, TPE2, APIC
from mutagen.mp3 import MP3
import shutil

from PyQt6.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout,
                             QWidget, QPushButton, QTableWidget, QTableWidgetItem,
                             QFileDialog, QLabel, QLineEdit, QProgressBar, QMessageBox,
                             QGroupBox, QGridLayout, QHeaderView, QComboBox, QDialog,
                             QSplitter, QScrollArea, QSizePolicy)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QEvent, QSize
from PyQt6.QtGui import QFont, QPixmap, QResizeEvent
from PyQt6.QtCore import QByteArray


class AudioFile:
    """Classe per rappresentare un file audio con i suoi metadati."""

    def __init__(self, file_path):
        self.file_path = Path(file_path)
        self.original_title = ""
        self.generated_title = ""
        self.generated_track = ""
        self.artist = ""
        self.album = ""
        self.year = ""
        self.genre = ""
        self.track = ""
        self.duration = ""
        self.format_info = ""
        self.is_mp3 = False
        self.album_art = None  # Byte data della copertina

        self._extract_info()

    def _extract_info(self):
        """Estrae informazioni dal file."""
        try:
            # Controlla se è già MP3
            self.is_mp3 = self.file_path.suffix.lower() == '.mp3'

            if self.is_mp3:
                # Per MP3, usa mutagen per info di base
                mp3_file = MP3(str(self.file_path))
                self.duration = f"{mp3_file.info.length:.1f}s"
                self.format_info = f"MP3 - {mp3_file.info.bitrate}kbps"
            else:
                # Per altri formati, usa soundfile
                info = sf.info(str(self.file_path))
                self.duration = f"{info.duration:.1f}s"
                self.format_info = f"{info.format} - {info.samplerate}Hz"

            # Genera titolo dal filename
            self.generated_title, self.generated_track = self._clean_filename_to_title()

            # Estrai metadati esistenti
            self._extract_existing_tags()

        except Exception as e:
            print(f"Errore lettura {self.file_path.name}: {e}")

    def _clean_filename_to_title(self):
        """Converte il nome file in un titolo pulito."""
        filename = self.file_path.stem

        # Estrai il numero della traccia
        track_match = re.match(r'^(\d+)[\s\-\.]*', filename)
        track_number = str(int(track_match.group(1))) if track_match else ''

        title = re.sub(r'^\d+[\s\-\.]*', '', filename)  # Rimuovi numero traccia
        title = re.sub(r'[_\-]+', ' ', title)  # Sostituisci _ e - con spazi
        title = re.sub(r'\s+', ' ', title)  # Rimuovi spazi multipli
        title = title.strip().title()

        # Correzioni comuni
        title = re.sub(r'\bFt\b', 'ft.', title)
        title = re.sub(r'\bFeat\b', 'feat.', title)
        return title, track_number

    def _extract_existing_tags(self):
        """Estrae tag esistenti dal file."""
        try:
            audio_file = File(str(self.file_path))
            if audio_file and hasattr(audio_file, 'tags') and audio_file.tags:
                tags = audio_file.tags

                # Mappa tag comuni
                tag_mappings = {
                    'TIT2': 'original_title',
                    'TITLE': 'original_title',
                    'TPE1': 'artist',
                    'ARTIST': 'artist',
                    'TALB': 'album',
                    'ALBUM': 'album',
                    'TDRC': 'year',
                    'DATE': 'year',
                    'YEAR': 'year',
                    'TCON': 'genre',
                    'GENRE': 'genre',
                    'TRCK': 'track',
                    'TRACKNUMBER': 'track',
                    'TRACK': 'track'
                }

                for tag_key, attr_name in tag_mappings.items():
                    for key, value in tags.items():
                        if key.upper() == tag_key:
                            val = str(value[0]) if isinstance(value, list) and value else str(value)
                            setattr(self, attr_name, val)
                            break

                # Estrai copertina album (per MP3)
                if self.is_mp3:
                    self._extract_album_art(tags)

                # Estrai numero traccia dal filename se non presente nei tag
                if not self.track:
                    match = re.match(r'^(\d+)', self.file_path.stem)
                    if match:
                        self.track = match.group(1)

        except Exception as e:
            print(f"Errore estrazione tag da {self.file_path.name}: {e}")

    def _extract_album_art(self, tags):
        """Estrae la copertina dell'album dai tag ID3."""
        try:
            # Cerca tag APIC (Attached Picture)
            for key, value in tags.items():
                if key.startswith('APIC'):
                    self.album_art = value.data
                    break
        except Exception as e:
            print(f"Errore estrazione copertina: {e}")


class ConversionWorker(QThread):
    """Worker thread per la conversione dei file."""
    progress = pyqtSignal(int)
    file_converted = pyqtSignal(str, bool)
    finished = pyqtSignal()

    def __init__(self, audio_files, output_folder, bitrate):
        super().__init__()
        self.audio_files = audio_files
        self.output_folder = Path(output_folder)
        self.bitrate = bitrate

    def run(self):
        """Esegue la conversione dei file."""
        total_files = len(self.audio_files)

        for i, audio_file in enumerate(self.audio_files):
            try:
                if audio_file.is_mp3:
                    # Per MP3, copia e aggiorna solo i tag
                    success = self._update_mp3_tags(audio_file)
                else:
                    # Per altri formati, converti
                    success = self._convert_file(audio_file)

                self.file_converted.emit(audio_file.file_path.name, success)

            except Exception as e:
                print(f"Errore elaborazione {audio_file.file_path.name}: {e}")
                self.file_converted.emit(audio_file.file_path.name, False)

            # Aggiorna progress
            progress_percent = int((i + 1) / total_files * 100)
            self.progress.emit(progress_percent)

        self.finished.emit()

    def _update_mp3_tags(self, audio_file):
        """Aggiorna solo i tag di un file MP3 esistente."""
        try:
            # Copia il file MP3 nella cartella di output
            output_file = self.output_folder / f"{audio_file.file_path.stem}.mp3"
            shutil.copy2(str(audio_file.file_path), str(output_file))

            # Aggiorna i tag
            self._add_tags(audio_file, output_file)
            return True

        except Exception as e:
            print(f"Errore aggiornamento tag MP3: {e}")
            return False

    def _convert_file(self, audio_file):
        """Converte un singolo file."""
        try:
            # Leggi audio
            data, samplerate = sf.read(str(audio_file.file_path))

            # Normalizza
            if data.dtype != 'float32':
                data = data.astype('float32')

            if data.max() > 1.0 or data.min() < -1.0:
                data = data / np.max(np.abs(data))

            data_int16 = (data * 32767).astype('int16')

            channels = 1 if data_int16.ndim == 1 else data_int16.shape[1]

            # Encoder
            encoder = lameenc.Encoder(
                rate=samplerate,
                channels=channels,
                bitrate=int(self.bitrate[:-1]),
                quality=2
            )

            # Converti
            mp3_data = encoder.encode(data_int16.tobytes())
            mp3_data += encoder.flush()

            # Salva MP3
            output_file = self.output_folder / f"{audio_file.file_path.stem}.mp3"
            with open(output_file, 'wb') as f:
                f.write(mp3_data)

            # Aggiungi tag
            self._add_tags(audio_file, output_file)

            return True

        except Exception as e:
            print(f"Errore conversione: {e}")
            return False

    def _add_tags(self, audio_file, mp3_file):
        """Aggiunge tag ID3 al file MP3."""
        try:
            try:
                id3_tags = ID3(str(mp3_file))
            except ID3NoHeaderError:
                id3_tags = ID3()

            # Usa il titolo originale se presente, altrimenti quello generato
            title = audio_file.original_title or audio_file.generated_title
            track = audio_file.track or audio_file.generated_track

            # Aggiungi tag
            if title:
                id3_tags.add(TIT2(encoding=3, text=title))
            if audio_file.artist:
                id3_tags.add(TPE1(encoding=3, text=audio_file.artist))
            if audio_file.album:
                id3_tags.add(TALB(encoding=3, text=audio_file.album))
            if audio_file.year:
                id3_tags.add(TDRC(encoding=3, text=audio_file.year))
            if audio_file.genre:
                id3_tags.add(TCON(encoding=3, text=audio_file.genre))
            if track:
                id3_tags.add(TRCK(encoding=3, text=track))

            # Rimuovi tutte le copertine esistenti prima di aggiungere quella nuova
            keys_to_remove = [key for key in id3_tags.keys() if key.startswith('APIC')]
            for key in keys_to_remove:
                del id3_tags[key]

            # Aggiungi la copertina se presente
            if audio_file.album_art:
                # Determina il tipo MIME dall'header dei dati
                mime_type = 'image/jpeg'  # default
                if audio_file.album_art.startswith(b'\x89PNG'):
                    mime_type = 'image/png'
                elif audio_file.album_art.startswith(b'GIF'):
                    mime_type = 'image/gif'
                elif audio_file.album_art.startswith(b'BM'):
                    mime_type = 'image/bmp'

                id3_tags.add(APIC(
                    encoding=3,
                    mime=mime_type,
                    type=3,  # Cover (front)
                    desc=u'Cover',
                    data=audio_file.album_art
                ))

            id3_tags.save(str(mp3_file))

        except Exception as e:
            print(f"Errore aggiunta tag: {e}")


class AudioConverter(QDialog):
    def __init__(self, folder=''):
        super().__init__()
        self.audio_files = []
        self.current_folder = folder
        self.init_ui()
        if folder:
            self.select_folder(folder)

    def init_ui(self):
        """Inizializza l'interfaccia utente."""
        self.setWindowTitle("Audio Tagger & Converter")
        self.setGeometry(100, 100, 1400, 800)

        # Layout principale con splitter
        #main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Pannello sinistro - controlli principali
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # Sezione selezione cartella
        folder_group = QGroupBox("Selezione Cartella")
        folder_layout = QHBoxLayout(folder_group)

        self.folder_label = QLabel("Nessuna cartella selezionata")
        self.folder_button = QPushButton("Scegli Cartella")
        self.folder_button.clicked.connect(self.select_folder)

        folder_layout.addWidget(self.folder_label)
        folder_layout.addWidget(self.folder_button)

        # Sezione informazioni globali
        global_group = QGroupBox("Informazioni Globali Album")
        global_layout = QGridLayout(global_group)

        global_layout.addWidget(QLabel("Artista:"), 0, 0)
        self.global_artist = QLineEdit()
        global_layout.addWidget(self.global_artist, 0, 1)

        global_layout.addWidget(QLabel("Album:"), 0, 2)
        self.global_album = QLineEdit()
        global_layout.addWidget(self.global_album, 0, 3)

        global_layout.addWidget(QLabel("Anno:"), 1, 0)
        self.global_year = QLineEdit()
        global_layout.addWidget(self.global_year, 1, 1)

        global_layout.addWidget(QLabel("Genere:"), 1, 2)
        self.global_genre = QLineEdit()
        global_layout.addWidget(self.global_genre, 1, 3)

        # Bottoni per applicare info globali
        apply_button = QPushButton("Applica Info Globali")
        apply_button.clicked.connect(self.apply_global_info)
        global_layout.addWidget(apply_button, 2, 0, 1, 4)

        # Tabella file
        self.table = QTableWidget()
        self.setup_table()

        # Sezione conversione
        conversion_group = QGroupBox("Conversione")
        conversion_layout = QHBoxLayout(conversion_group)

        conversion_layout.addWidget(QLabel("Bitrate:"))
        self.bitrate_combo = QComboBox()
        self.bitrate_combo.addItems(["128k", "192k", "256k", "320k"])
        self.bitrate_combo.setCurrentText("320k")
        conversion_layout.addWidget(self.bitrate_combo)

        conversion_layout.addStretch()

        self.output_button = QPushButton("Scegli Cartella Output")
        self.output_button.clicked.connect(self.select_output_folder)
        conversion_layout.addWidget(self.output_button)

        self.convert_button = QPushButton("Elabora Tutti")
        self.convert_button.clicked.connect(self.start_conversion)
        self.convert_button.setEnabled(False)
        conversion_layout.addWidget(self.convert_button)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        # Status label
        self.status_label = QLabel("Pronto")

        # Aggiungi tutto al layout sinistro
        left_layout.addWidget(folder_group)
        left_layout.addWidget(global_group)
        #left_layout.addWidget(self.table, 1)  # Espandi la tabella
        #left_layout.addWidget(conversion_group)
        #left_layout.addWidget(self.progress_bar)
        #left_layout.addWidget(self.status_label)

        # Pannello destro - visualizzazione copertina
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Gruppo copertina
        cover_group = QGroupBox("Copertina Album")
        cover_layout = QVBoxLayout(cover_group)

        # Scroll area per la copertina
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumWidth(300)
        scroll_area.setMaximumWidth(300)

        self.cover_label = QLabel("Nessuna copertina") #FixedSquareQLabel() #QLabel("Nessuna copertina")
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        #self.cover_label.setStyleSheet("border: 2px dashed #ccc; padding: 20px;")
        self.cover_label.setFixedSize(250, 250)
        #self.cover_label.setMaximumSize(250, 250)

        scroll_area.setWidget(self.cover_label)
        scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_layout.addWidget(scroll_area)

        # Bottoni per gestire copertina
        cover_buttons_layout = QHBoxLayout()

        self.load_cover_button = QPushButton("Carica Copertina")
        self.load_cover_button.clicked.connect(self.load_cover)
        cover_buttons_layout.addWidget(self.load_cover_button)

        self.remove_cover_button = QPushButton("Rimuovi Copertina")
        self.remove_cover_button.clicked.connect(self.remove_cover)
        self.remove_cover_button.setEnabled(False)
        cover_buttons_layout.addWidget(self.remove_cover_button)

        cover_layout.addLayout(cover_buttons_layout)
        right_layout.addWidget(cover_group)
        right_layout.addStretch()

        # Aggiungi pannelli al splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([1000, 400])  # Dimensioni relative

        v = QVBoxLayout(self)
        v.addWidget(splitter)
        v.addWidget(self.table, 1)
        v.addWidget(conversion_group)
        v.addWidget(self.progress_bar)
        v.addWidget(self.status_label)
        #main_layout.addWidget(splitter)

        # Variabili
        self.output_folder = ""
        self.current_cover_data = None
        self.table.installEventFilter(self)

        # Connetti selezione tabella a visualizzazione copertina
        self.table.itemSelectionChanged.connect(self.on_selection_changed)

    def setup_table(self):
        """Configura la tabella dei file."""
        headers = ["File", "Titolo", "Artista", "Album", "Anno", "Genere", "Traccia", "Durata", "Formato", "Tipo"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        # Configura header
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # File
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Titolo
        #header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Artista
        #header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # Album
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Anno
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # Traccia
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)  # Durata
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.ResizeToContents)  # Tipo

        # Abilita editing
        self.table.itemChanged.connect(self.on_item_changed)

    def select_folder(self, f):
        """Seleziona cartella con file audio."""
        if not f:
            folder = QFileDialog.getExistingDirectory(self, "Seleziona cartella con file audio")
        else:
            folder = f
        if folder:
            self.current_folder = folder
            self.folder_label.setText(folder)
            self.load_audio_files()

    def load_audio_files(self):
        """Carica file audio dalla cartella selezionata."""
        if not self.current_folder:
            return

        self.status_label.setText("Caricamento file in corso...")
        self.audio_files = []

        # Estensioni supportate
        extensions = ['.aif', '.aiff', '.flac', '.wav', '.m4a', '.mp3', '.wma']

        folder_path = Path(self.current_folder)
        for ext in extensions:
            for file_path in folder_path.glob(f"*{ext}"):
                self.audio_files.append(AudioFile(file_path))

        # Ordina per nome file
        self.audio_files.sort(key=lambda x: x.file_path.name)

        self.populate_table()
        self.status_label.setText(f"Caricati {len(self.audio_files)} file audio")

    def populate_table(self):
        """Popola la tabella con i file audio."""
        self.table.setRowCount(len(self.audio_files))

        for row, audio_file in enumerate(self.audio_files):
            # File (non editabile)
            item = QTableWidgetItem(audio_file.file_path.name)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, item)

            # Titolo (usa originale se presente, altrimenti generato)
            title = audio_file.original_title or audio_file.generated_title
            self.table.setItem(row, 1, QTableWidgetItem(title))

            # Altri campi editabili
            self.table.setItem(row, 2, QTableWidgetItem(audio_file.artist))
            self.table.setItem(row, 3, QTableWidgetItem(audio_file.album))
            self.table.setItem(row, 4, QTableWidgetItem(audio_file.year))
            self.table.setItem(row, 5, QTableWidgetItem(audio_file.genre))

            track = audio_file.track or audio_file.generated_track
            self.table.setItem(row, 6, QTableWidgetItem(track))

            # Durata e formato (non editabili)
            duration_item = QTableWidgetItem(audio_file.duration)
            duration_item.setFlags(duration_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 7, duration_item)

            format_item = QTableWidgetItem(audio_file.format_info)
            format_item.setFlags(format_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 8, format_item)

            # Tipo (MP3 o da convertire)
            tipo_item = QTableWidgetItem("MP3 (solo tag)" if audio_file.is_mp3 else "Da convertire")
            tipo_item.setFlags(tipo_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 9, tipo_item)

        self.display_cover(self.audio_files[0].album_art)

    def on_selection_changed(self):
        """Gestisce la selezione nella tabella per mostrare la copertina."""
        selected_rows = set(index.row() for index in self.table.selectedIndexes())
        if selected_rows and len(selected_rows) == 1:
            row = list(selected_rows)[0]
            if row < len(self.audio_files):
                audio_file = self.audio_files[row]
                self.display_cover(audio_file.album_art)
        else:
            self.display_cover(None)

    def display_cover(self, cover_data):
        """Mostra la copertina nell'area dedicata."""
        if cover_data:
            try:
                pixmap = QPixmap()
                pixmap.loadFromData(QByteArray(cover_data))

                # Scala l'immagine mantenendo le proporzioni
                self.cover_label.setPixmap(pixmap.scaled(self.cover_label.size(), Qt.AspectRatioMode.KeepAspectRatio))
                self.cover_label.setText("")
                self.remove_cover_button.setEnabled(True)

            except Exception as e:
                print(f"Errore visualizzazione copertina: {e}")
                self.cover_label.setText("Errore caricamento copertina")
                self.cover_label.setPixmap(QPixmap())
                self.remove_cover_button.setEnabled(False)
        else:
            self.cover_label.setText("Nessuna copertina")
            self.cover_label.setPixmap(QPixmap())
            self.remove_cover_button.setEnabled(False)

    def load_cover(self):
        """Carica una copertina da file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona copertina", "",
            "Immagini (*.jpg *.jpeg *.png *.bmp *.gif)"
        )

        if file_path:
            try:
                with open(file_path, 'rb') as f:
                    cover_data = f.read()

                self.current_cover_data = cover_data
                self.display_cover(cover_data)

                # Applica a tutti i file selezionati o a tutti se nessuno selezionato
                selected_rows = set(index.row() for index in self.table.selectedIndexes())
                if not selected_rows:
                    # Applica a tutti
                    for audio_file in self.audio_files:
                        audio_file.album_art = cover_data
                else:
                    # Applica solo ai selezionati
                    for row in selected_rows:
                        if row < len(self.audio_files):
                            self.audio_files[row].album_art = cover_data

                self.status_label.setText("Copertina caricata")

            except Exception as e:
                QMessageBox.warning(self, "Errore", f"Impossibile caricare la copertina: {e}")

    def remove_cover(self):
        """Rimuove la copertina dai file selezionati."""
        selected_rows = set(index.row() for index in self.table.selectedIndexes())
        if not selected_rows:
            # Rimuovi da tutti
            for audio_file in self.audio_files:
                audio_file.album_art = None
        else:
            # Rimuovi solo dai selezionati
            for row in selected_rows:
                if row < len(self.audio_files):
                    self.audio_files[row].album_art = None

        self.display_cover(None)
        self.status_label.setText("Copertina rimossa")

    def eventFilter(self, obj, event):
        """Gestisce eventi di tastiera della tabella."""
        if obj == self.table and event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Delete:
            rows = set(index.row() for index in self.table.selectedIndexes())
            rows_to_delete = sorted(list(rows), reverse=True)
            for row in rows_to_delete:
                self.table.removeRow(row)
                if 0 <= row < len(self.audio_files):
                    del self.audio_files[row]
            return False
        return super().eventFilter(obj, event)

    def on_item_changed(self, item):
        """Gestisce cambiamenti nella tabella."""
        row = item.row()
        col = item.column()

        if row < len(self.audio_files):
            audio_file = self.audio_files[row]
            value = item.text()

            # Mappa colonne agli attributi
            if col == 1:  # Titolo
                audio_file.original_title = value
            elif col == 2:  # Artista
                audio_file.artist = value
            elif col == 3:  # Album
                audio_file.album = value
            elif col == 4:  # Anno
                audio_file.year = value
            elif col == 5:  # Genere
                audio_file.genre = value
            elif col == 6:  # Traccia
                audio_file.track = value

    def apply_global_info(self):
        """Applica informazioni globali a tutti i file."""
        artist = self.global_artist.text().strip()
        album = self.global_album.text().strip()
        year = self.global_year.text().strip()
        genre = self.global_genre.text().strip()

        for row, audio_file in enumerate(self.audio_files):
            if artist and not audio_file.artist:
                audio_file.artist = artist
                self.table.setItem(row, 2, QTableWidgetItem(artist))

            if album and not audio_file.album:
                audio_file.album = album
                self.table.setItem(row, 3, QTableWidgetItem(album))

            if year and not audio_file.year:
                audio_file.year = year
                self.table.setItem(row, 4, QTableWidgetItem(year))

            if genre and not audio_file.genre:
                audio_file.genre = genre
                self.table.setItem(row, 5, QTableWidgetItem(genre))

        self.status_label.setText("Informazioni globali applicate")

    def select_output_folder(self):
        """Seleziona cartella di output."""
        folder = QFileDialog.getExistingDirectory(self, "Seleziona cartella di output")
        if folder:
            self.output_folder = folder
            self.output_button.setText(f"Output: {Path(folder).name}")
            self.convert_button.setEnabled(bool(self.audio_files))

    def start_conversion(self):
        """Avvia la conversione/elaborazione dei file."""
        if not self.output_folder:
            QMessageBox.warning(self, "Errore", "Seleziona una cartella di output")
            return

        if not self.audio_files:
            QMessageBox.warning(self, "Errore", "Nessun file da elaborare")
            return

        # Configura UI per conversione
        self.convert_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Elaborazione in corso...")

        # Avvia worker thread
        self.worker = ConversionWorker(
            self.audio_files,
            self.output_folder,
            self.bitrate_combo.currentText()
        )
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.file_converted.connect(self.on_file_converted)
        self.worker.finished.connect(self.on_conversion_finished)
        self.worker.start()

    def on_file_converted(self, filename, success):
        """Callback per file convertito."""
        status = "✓" if success else "✗"
        print(f"{status} {filename}")

    def on_conversion_finished(self):
        """Callback per conversione completata."""
        self.progress_bar.setVisible(False)