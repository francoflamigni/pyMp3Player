import subprocess
import re
import soundfile as sf

from pathlib import Path

from mutagen import File
from mutagen.id3 import ID3NoHeaderError, ID3, TIT2, TPE1, TALB, TDRC, TCON, TRCK, TPE2, APIC
from mutagen.mp3 import MP3
import shutil
from pyMyLib.utils import get_resource_file

from PyQt6.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout,
                             QWidget, QPushButton, QTableWidget, QTableWidgetItem,
                             QFileDialog, QLabel, QLineEdit, QProgressBar, QMessageBox,
                             QGroupBox, QGridLayout, QHeaderView, QComboBox, QDialog,
                             QSplitter, QScrollArea, QSizePolicy)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QEvent, QByteArray
from PyQt6.QtGui import QPixmap, QIcon
from utility import get_windows_flag

from enum import Enum

class Mode(Enum):
    TAG_EDIT = 1
    FORMAT_CONVERT = 2

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
            if output_file != audio_file.file_path:
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
            output_file = self.output_folder / f"{audio_file.file_path.stem}.mp3"

            # Converti con ffmpeg
            cmd = [
                'ffmpeg',
                '-i', str(audio_file.file_path),
                '-codec:a', 'libmp3lame',
                '-b:a', self.bitrate,  # es. "320k"
                '-q:a', '0',  # qualità massima VBR (se usi VBR)
                '-y',  # sovrascrivi se esiste
                str(output_file)
            ]

            subprocess.run(cmd, check=True, capture_output=True, text=True, creationflags=get_windows_flag())

            # Aggiungi tag
            self._add_tags(audio_file, output_file)

            return True
        except Exception as e:
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
        self.populating = False
        self.mode = Mode.TAG_EDIT
        self.init_ui()
        if folder:
            self.select_folder(folder)

    def init_ui(self):
        """Inizializza l'interfaccia utente."""
        self.setWindowTitle("Audio Tagger & Converter")
        self.setGeometry(100, 100, 1500, 800)
        self.setWindowIcon(QIcon(get_resource_file(__file__, 'icone', 'tag-edit.png')))

        # Sezione selezione cartella
        folder_group = self.setup_folder()

        # Sezione informazioni globali
        global_group = self.setup_global()

        # Gruppo copertina
        cover_group = self.setup_cover()

        # Pannello sinistro - controlli principali
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(global_group)
        left_layout.addWidget(cover_group)

        # Tabella file
        self.table = QTableWidget()
        #self.table = self.setup_table()

        # Layout principale con splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(self.table)
        splitter.setSizes([200, 1100])  # Dimensioni relative


        # Sezione conversione
        conversion_group = self.setup_conversion()

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        # Status label
        self.status_label = QLabel("Pronto")

        # Aggiungi tutto al layout sinistro
        #left_layout.addWidget(folder_group)
        #left_layout.addWidget(global_group)
        #left_layout.addWidget(self.table, 1)  # Espandi la tabella
        #left_layout.addWidget(conversion_group)
        #left_layout.addWidget(self.progress_bar)
        #left_layout.addWidget(self.status_label)

        # Pannello destro - visualizzazione copertina
        #right_widget = QWidget()
        #right_layout = QVBoxLayout(right_widget)


        #right_layout.addWidget(cover_group)
        #right_layout.addStretch()

        # Aggiungi pannelli al splitter
        #splitter.addWidget(left_widget)
        #splitter.addWidget(right_widget)

        v = QVBoxLayout(self)
        v.addWidget(folder_group)
        v.addWidget(splitter, stretch=1)

        #v.addWidget(self.table, 1)
        v.addWidget(conversion_group)
        v.addStretch()
        v.addWidget(self.progress_bar)
        v.addWidget(self.status_label)
        #main_layout.addWidget(splitter)

        # Variabili
        self.output_folder = ""
        self.current_cover_data = None
        self.table.installEventFilter(self)

        # Connetti selezione tabella a visualizzazione copertina
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.hide_conversion()

    def setup_conversion(self):
        conversion_group = QGroupBox("Conversione")
        conversion_layout = QHBoxLayout(conversion_group)
        conversion_layout.setContentsMargins(5, 5, 5, 5)

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

        conversion_group.setSizePolicy(QSizePolicy.Policy.Preferred,  # orizzontale
            QSizePolicy.Policy.Maximum  # verticale - altezza minima
        )
        return conversion_group

    def hide_conversion(self):
        hide = self.mode == Mode.FORMAT_CONVERT
        """Mostra o nasconde i controlli di conversione senza usare nuovi membri della classe"""
        # Trova il QGroupBox per nome
        for group in self.findChildren(QGroupBox, None):
            if group and group.title() == "Conversione":
                group.setVisible(hide)
                # Nascondi/mostra tutti i widget figli
                for widget in group.findChildren(QWidget):
                    widget.setVisible(hide)
                break

    def setup_folder(self):
        folder_group = QGroupBox("Selezione Cartella")
        folder_layout = QHBoxLayout(folder_group)
        folder_layout.setContentsMargins(5, 5, 5, 5)

        self.folder_label = QLabel("Nessuna cartella selezionata")
        self.folder_button = QPushButton("Scegli Cartella")
        self.folder_button.clicked.connect(self.select_folder)

        self.save_button = QPushButton("Salva")
        self.save_button.clicked.connect(self.save)

        folder_layout.addWidget(self.folder_label)
        folder_layout.addWidget(self.folder_button)
        folder_layout.addWidget(self.save_button)

        folder_group.setSizePolicy(QSizePolicy.Policy.Preferred,  # orizzontale
            QSizePolicy.Policy.Maximum  # verticale - altezza minima
        )
        return folder_group

    def setup_global(self):
        global_group = QGroupBox("Informazioni Globali Album")
        global_layout = QGridLayout(global_group)

        global_layout.addWidget(QLabel("Artista:"), 0, 0)
        self.global_artist = QLineEdit()
        global_layout.addWidget(self.global_artist, 0, 1)

        global_layout.addWidget(QLabel("Album:"), 1, 0)
        self.global_album = QLineEdit()
        global_layout.addWidget(self.global_album, 1, 1)

        global_layout.addWidget(QLabel("Anno:"), 2, 0)
        self.global_year = QLineEdit()
        global_layout.addWidget(self.global_year, 2, 1)

        global_layout.addWidget(QLabel("Genere:"), 3, 0)
        self.global_genre = QLineEdit()
        global_layout.addWidget(self.global_genre, 3, 1)

        # Bottoni per applicare info globali
        apply_button = QPushButton("Applica Info Globali")
        apply_button.clicked.connect(self.apply_global_info)
        global_layout.addWidget(apply_button, 4, 0, 1, 4)
        return global_group

    def setup_cover(self):
        cover_group = QGroupBox("Copertina Album")
        cover_layout = QVBoxLayout(cover_group)

        # Scroll area per la copertina
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumWidth(250)
        scroll_area.setMaximumWidth(250)

        self.cover_label = QLabel("Nessuna copertina")
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        #self.cover_label.setStyleSheet("border: 2px dashed #ccc; padding: 20px;")
        self.cover_label.setFixedSize(200, 200)
        #self.cover_label.setMaximumSize(250, 250)

        scroll_area.setWidget(self.cover_label)
        scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_layout.addWidget(scroll_area)

        # Bottoni per gestire copertina
        cover_buttons_layout = QHBoxLayout()

        self.load_cover_file_button = QPushButton("Da file")
        self.load_cover_file_button.clicked.connect(self.load_cover_from_file)
        cover_buttons_layout.addWidget(self.load_cover_file_button)

        self.load_cover_clip_button = QPushButton("Da clipboard")
        self.load_cover_clip_button.clicked.connect(self.load_cover_from_clipboard)
        cover_buttons_layout.addWidget(self.load_cover_clip_button)

        self.remove_cover_button = QPushButton("Rimuovi")
        self.remove_cover_button.clicked.connect(self.remove_cover)
        self.remove_cover_button.setEnabled(False)
        cover_buttons_layout.addWidget(self.remove_cover_button)

        cover_layout.addLayout(cover_buttons_layout)

        cover_group.setSizePolicy(QSizePolicy.Policy.Preferred,  # orizzontale
                                   QSizePolicy.Policy.Maximum  # verticale - altezza minima
                                   )
        return cover_group

    def setup_table(self):
        self.table.clear()
        """Configura la tabella dei file."""
        self.headers = []
        if self.mode == Mode.FORMAT_CONVERT:
            self.headers = ["Sel"]
        self.headers.extend(["File", "Titolo", "Artista", "Album", "Anno", "Genere", "Traccia", "Durata", "Formato"])
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)

        # Configura header
        tab_header = self.table.horizontalHeader()
        for i, header in enumerate(self.headers):
            if header != "Artista" and header != "Album":
                tab_header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)  # File

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

    def save(self):
        self.output_folder = self.current_folder
        self.start_conversion()
        a = 0

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
                audio = AudioFile(file_path)
                if audio.format_info != '':
                    self.audio_files.append(audio)

        count = 0
        for audio_file in self.audio_files:
            if audio_file.is_mp3:
                count += 1
        if count == len(self.audio_files):
            self.mode = Mode.TAG_EDIT
            self.save_button.setVisible(True)

        else:
            self.mode = Mode.FORMAT_CONVERT
            self.save_button.setVisible(False)

        self.hide_conversion()

        # Ordina per nome file
        self.audio_files.sort(key=lambda x: x.file_path.name)

        self.setup_table()
        self.populate_table()
        self.status_label.setText(f"Caricati {len(self.audio_files)} file audio")

    def _checkItem(self, row, checked=False):
        check_item = QTableWidgetItem()

        # 2. Imposta i flag: rende la cella selezionabile e checkable
        check_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)

        # 3. Imposta lo stato iniziale (Checked o Unchecked)
        if checked:
            check_item.setCheckState(Qt.CheckState.Checked)
        else:
            check_item.setCheckState(Qt.CheckState.Unchecked)

        # Inserisce l'oggetto checkbox nella prima colonna
        self.table.setItem(row, 0, check_item)

    def populate_table(self):
        self.populating = True
        """Popola la tabella con i file audio."""
        self.table.setRowCount(len(self.audio_files))

        off = 0
        if self.mode == Mode.FORMAT_CONVERT:
            off = 1

        for row, audio_file in enumerate(self.audio_files):
            if self.mode == Mode.FORMAT_CONVERT:
                self._checkItem(row)
            # File (non editabile)
            item = QTableWidgetItem(audio_file.file_path.name)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, off, item)

            # Titolo (usa originale se presente, altrimenti generato)
            title = audio_file.original_title or audio_file.generated_title
            self.table.setItem(row, off + 1, QTableWidgetItem(title))

            # Altri campi editabili
            self.table.setItem(row, off + 2, QTableWidgetItem(audio_file.artist))
            self.table.setItem(row, off + 3, QTableWidgetItem(audio_file.album))
            self.table.setItem(row, off + 4, QTableWidgetItem(audio_file.year))
            self.table.setItem(row, off + 5, QTableWidgetItem(audio_file.genre))

            track = audio_file.track or audio_file.generated_track
            self.table.setItem(row, off + 6, QTableWidgetItem(track))

            # Durata e formato (non editabili)
            duration_item = QTableWidgetItem(audio_file.duration)
            duration_item.setFlags(duration_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, off + 7, duration_item)

            format_item = QTableWidgetItem(audio_file.format_info)
            format_item.setFlags(format_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, off + 8, format_item)

            # Tipo (MP3 o da convertire)
            tipo_item = QTableWidgetItem("MP3 (solo tag)" if audio_file.is_mp3 else "Da convertire")
            tipo_item.setFlags(tipo_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
           # self.table.setItem(row, 10, tipo_item)

        if self.audio_files:
            self.display_cover(self.audio_files[0].album_art)

        self.populating = False

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

    def load_cover_from_file(self):
        """Carica una copertina da file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona copertina", "",
            "Immagini (*.jpg *.jpeg *.png *.bmp *.gif)"
        )

        if file_path:
            try:
                with open(file_path, 'rb') as f:
                    cover_data = f.read()

                #self.current_cover_data = cover_data
                self._load_cover(cover_data)
                '''
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
                '''

            except Exception as e:
                QMessageBox.warning(self, "Errore", f"Impossibile caricare la copertina: {e}")

    def load_cover_from_clipboard(self):
        from utility import qpixmap_to_bytes
        """Carica una copertina dal clipboard con ridimensionamento."""
        try:
            clipboard = QApplication.clipboard()

            # Controlla se c'è un'immagine nel clipboard
            if not clipboard.mimeData().hasImage():
                QMessageBox.information(self, "Info", "Nessuna immagine trovata nel clipboard")
                return

            # Ottieni l'immagine dal clipboard
            pixmap = clipboard.pixmap()
            if pixmap.isNull():
                QMessageBox.warning(self, "Errore", "Impossibile ottenere l'immagine dal clipboard")
                return

            # Converte QPixmap in dati binari
            image_data = qpixmap_to_bytes(pixmap)

            self._load_cover(image_data)

        except Exception as e:
            QMessageBox.warning(self, "Errore", f"Impossibile caricare dal clipboard: {e}")

    def _load_cover(self, image_data):
        from utility import resize_image_data
        # Ridimensiona l'immagine
        resized_data = resize_image_data(
            image_data,
            target_size=(400, 400),
            quality=85
        )
        self.current_cover_data = resized_data

        self.display_cover(resized_data)

        # Applica a tutti i file selezionati o a tutti se nessuno selezionato
        selected_rows = set(index.row() for index in self.table.selectedIndexes())
        if not selected_rows:
            # Applica a tutti
            for audio_file in self.audio_files:
                audio_file.album_art = resized_data
        else:
            # Applica solo ai selezionati
            for row in selected_rows:
                if row < len(self.audio_files):
                    self.audio_files[row].album_art = resized_data

        self.status_label.setText("Copertina caricata")

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
        if self.populating:
            return
        """Gestisce cambiamenti nella tabella."""
        row = item.row()
        col = item.column()

        off = 0 if self.mode == Mode.TAG_EDIT else 1

        if row < len(self.audio_files):
            audio_file = self.audio_files[row]
            value = item.text()

            # Mappa colonne agli attributi
            if col == off + 1:  # Titolo
                audio_file.original_title = value
            elif col == off + 2 :  # Artista
                audio_file.artist = value
            elif col == off + 3:  # Album
                audio_file.album = value
            elif col == off + 4:  # Anno
                audio_file.year = value
            elif col == off + 5:  # Genere
                audio_file.genre = value
            elif col == off + 6:  # Traccia
                audio_file.track = value

    def apply_global_info(self):
        """Applica informazioni globali a tutti i file."""
        artist = self.global_artist.text().strip()
        album = self.global_album.text().strip()
        year = self.global_year.text().strip()
        genre = self.global_genre.text().strip()

        off = 0 if self.mode == Mode.TAG_EDIT else 1

        for row, audio_file in enumerate(self.audio_files):
            if artist and not audio_file.artist or artist and artist != audio_file.artist:
                audio_file.artist = artist
                self.table.setItem(row, off + 2, QTableWidgetItem(artist))

            if album and not audio_file.album or album and album != audio_file.album:
                audio_file.album = album
                self.table.setItem(row, off + 3, QTableWidgetItem(album))

            if year and not audio_file.year:
                audio_file.year = year
                self.table.setItem(row, off + 4, QTableWidgetItem(year))

            if genre and not audio_file.genre:
                audio_file.genre = genre
                self.table.setItem(row, off + 5, QTableWidgetItem(genre))

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

        self.audio_toconvert = []
        if self.mode == Mode.TAG_EDIT:
            self.audio_toconvert = self.audio_files
        else:
            for i in range (self.table.rowCount()):
                ck = self.table.item(i, 0).checkState()
                if self.table.item(i, 0).checkState() == Qt.CheckState.Checked:
                    self.audio_toconvert.append(self.audio_files[i])

        if not self.audio_toconvert:
            QMessageBox.warning(self, "Errore", "Nessun file da elaborare")
            return

        # Configura UI per conversione
        self.convert_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Elaborazione in corso...")

        # Avvia worker thread
        self.worker = ConversionWorker(
            self.audio_toconvert,
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
        self.status_label.setText("Elaborazione terminata")