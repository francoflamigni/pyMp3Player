import os
import sys
import subprocess
import re
import time
from pathlib import Path
from typing import List, Dict

from PyQt6.QtGui import QIcon, QPixmap, QAction
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QComboBox, QProgressBar, QTableWidgetItem,
    QGroupBox, QFileDialog, QDialog, QMessageBox, QHeaderView, QSizePolicy, QGridLayout, QSplitter, QWidget, QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from music_brainz import CDinfo

from pyMyLib.utils import get_resource_file
from utility import CDMonitor, AppContext

class FFmpegWorker(QThread):
    """Worker thread per le operazioni ffmpeg"""

    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    finished_track = pyqtSignal(int, str)  # track_number, filename
    progress_track = pyqtSignal(int)
    status_track = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    ripping_finished = pyqtSignal()

    def __init__(self, cd_drive: str, tracks: List[Dict], output_dir: str, quality: str, cover_path: str=''):
        super().__init__()
        self.cd_drive = cd_drive
        self.tracks = tracks
        self.output_dir = output_dir
        self.quality = quality
        self.is_running = True
        self.current_process  = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.watch)
        self.last_time = 0
        self.cover_path = cover_path
        self.timer.start(1000)

    def watch(self):
        TIMEOUT = 20
        if self.last_time and self.current_process:
            elapsed = time.monotonic() - self.last_time
            if elapsed > TIMEOUT:
                self.current_process.terminate()

    def stop(self):
        self.is_running = False

        if self.current_process and self.current_process.poll() is None:
            # Assicurati che il processo sia ancora in esecuzione prima di tentare di terminarlo
            try:
                self.current_process.terminate()  # o .kill() per una terminazione più aggressiva
            except Exception as e:
                print(f"Errore durante la terminazione del processo: {e}")

    def converti_durata_in_secondi(self, log_string: str):
        # Cattura HH, MM, SS e i millisecondi (parte decimale)
        match = re.search(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})", log_string)

        if match:
            ore = int(match.group(1))
            minuti = int(match.group(2))
            secondi_interi = int(match.group(3))
            millisecondi_str = match.group(4)  # Cattura i due decimali

            # Converti i millisecondi (es. "72" -> 0.72)
            # Assumiamo che siano centesimi di secondo per due cifre dopo il punto
            millisecondi = float("0." + millisecondi_str) if millisecondi_str else 0.0

            # Calcola i secondi totali
            secondi_totali = (ore * 3600) + (minuti * 60) + secondi_interi + millisecondi
            return secondi_totali
        else:
            #print("Formato 'time=HH:MM:SS.ms' non trovato nella stringa fornita.")
            return None

    def run(self):
        try:
            total_tracks = len(self.tracks)

            for i, track in enumerate(self.tracks):
                if not self.is_running:
                    break

                track_num = int(track['traccia'])
                title = track['titolo']
                artist = track.get('artisti', 'Unknown Artist')
                album = track.get('album', 'Unknown Album')
                anno = track.get('anno', 'Unknown Anno')
                genere = track.get('genere', 'Unknown Genre')

                # Sanitizza il nome del file
                safe_title = self.sanitize_filename(f"{track_num:02d} - {title}")
                output_file = os.path.join(self.output_dir, f"{safe_title}.mp3")

                self.status_updated.emit(f"Estraendo traccia {track_num}: {title}")

                # Comando ffmpeg per estrarre la traccia specifica
                durata = track["durata"]
                offset = track["start"]
                cmd = [
                    'ffmpeg', '-y',
                    '-v', 'debug',
                    '-ss', f'{offset}',
                    '-f', 'libcdio',
                    '-i', f'{self.cd_drive}:',
                ]
                if self.cover_path:
                    cmd.extend(['-i', self.cover_path])
                cmd.extend([
                    '-t', f'{durata}',
                    '-c:a', 'libmp3lame',
                    '-b:a', self.quality,
                ])
                # Mappa gli stream
                if self.cover_path:
                    cmd.extend([
                        '-map', '0:a',  # Audio dal CD
                        '-map', '1:v',  # Video (immagine) dal file
                        '-c:v', 'mjpeg',  # Codec per l'immagine
                        '-disposition:v', 'attached_pic',  # Segna come copertina allegata
                    ])
                cmd.extend([
                    '-metadata', f'title={title}',
                    '-metadata', f'artist={artist}',
                    '-metadata', f'album={album}',
                    '-metadata', f'date={anno}',
                    '-metadata', f'track={track_num}',
                    '-metadata', f'genre={genere}',
                    output_file
                ])

                self.last_time = 0

                # Esegui ffmpeg
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, #PIPE,
                    universal_newlines=True,
                    encoding='utf-8',
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                self.current_process = process


                for line in iter(process.stdout.readline, ''):
                    self.last_time = time.monotonic()
                    if not self.is_running:
                        process.kill()
                        break
                    t = self.converti_durata_in_secondi(line.strip())
                    if t:
                        pc = int(100 * t / durata)
                        self.progress_track.emit(pc)
                        print(f"{t} sec")

                process.wait()  # Aspetta al massimo durata + 30 secondi

                self.current_process = None

                if not self.is_running:
                    continue  # Salta alla prossima traccia (o esci dal loop)

                if process.returncode == 0 or self.is_running:
                    self.finished_track.emit(track_num, output_file)
                    progress = int((i + 1) / total_tracks * 100)
                    self.progress_updated.emit(progress)
                else:
                    self.error_occurred.emit(f"Errore nell'estrazione traccia {track_num}")

        except Exception as e:
            self.error_occurred.emit(f"Errore generale: {str(e)}")

        finally:

            pass
        a = 0

    def sanitize_filename(self, filename: str) -> str:
        """Rimuove caratteri non validi dal nome del file"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename[:200]  # Limita lunghezza


class CDRipperMainWindow(QDialog):
    """Finestra principale dell'applicazione"""
    # Aggiungi questo segnale per comunicare tra thread
    tracks_detected = pyqtSignal(list)
    play_signal = pyqtSignal(str)

    def __init__(self, appCtx:AppContext):
        super().__init__()
        self.appCtx = appCtx
        self.ffmpeg_worker = None
        self.tracks_data = []
        self.cover_path = ''

        self.setWindowTitle("CD Ripper")
        self.setWindowIcon(QIcon(get_resource_file(__file__, 'icone', 'cd_ripper.png')))
        self.setGeometry(100, 100, 1500, 800)

        self.init_ui()
        self.init_cd_drives()
        self.tracks_detected.connect(self.update_tracks_table)

        self.monitor = CDMonitor(500, self.cd_drive_combo.currentText())
        self.monitor.cd_aperto.connect(self.on_cd_aperto)
        self.monitor.cd_chiuso.connect(self.on_cd_chiuso)
        self.monitor.start()

    def init_ui(self):
        """Inizializza l'interfaccia utente"""

        # Layout principale
        main_layout = QVBoxLayout(self)

        self.setup_config_tab(main_layout)

        # Barra di progresso e status
        self.progress_bar = QProgressBar()
        self.status_label = QLabel("Pronto")
        self.status_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.status_progress = QLabel()
        self.status_progress.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        h = QHBoxLayout()
        h.addWidget(self.status_label)
        h.addWidget(self.status_progress)

        main_layout.addWidget(self.progress_bar)
        main_layout.addLayout(h)

    def setup_config_tab(self, layout):
        """Configura il tab delle impostazioni"""
        #layout = QVBoxLayout(tab)
        hv = QHBoxLayout()

        # Gruppo CD Drive
        cd_group = QGroupBox("Drive CD")
        cd_layout = QHBoxLayout(cd_group)

        self.cd_drive_combo = QComboBox()
        self.refresh_drives_btn = QPushButton("Aggiorna")
        self.refresh_drives_btn.clicked.connect(self.init_cd_drives)
        self.eject_btn = QPushButton("Espelli")
        self.eject_btn.clicked.connect(self.eject)
        self.cd_drive_combo.currentIndexChanged.connect(self.detect_tracks)

        cd_layout.addWidget(QLabel("Drive:"))
        cd_layout.addWidget(self.cd_drive_combo)
        cd_layout.addWidget(self.refresh_drives_btn)
        cd_layout.addWidget(self.eject_btn)

        #layout.addWidget(cd_group)
        hv.addWidget(cd_group, stretch=1)

        # Gruppo Output
        output_group = QGroupBox("Output")
        output_layout = QHBoxLayout(output_group)

        # Directory output
        #dir_layout = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setText(str(Path.home() / "Music" / "Ripped CDs"))
        icone_browse = QIcon(get_resource_file(__file__, 'icone', 'folder_open.png'))
        azione_browse = QAction(icone_browse, "browse", self)
        azione_browse.triggered.connect(self.browse_output_dir)
        self.output_dir_edit.addAction(
            azione_browse,
            QLineEdit.ActionPosition.LeadingPosition
        )

        #self.browse_btn = QPushButton("Sfoglia...")
        #self.browse_btn.clicked.connect(self.browse_output_dir)

        output_layout.addWidget(QLabel("Directory:"))
        output_layout.addWidget(self.output_dir_edit)
        #output_layout.addWidget(self.browse_btn)
        hv.addWidget(output_group, stretch=2)

        # Qualità
        quality_group = QGroupBox("Quality")
        quality_layout = QHBoxLayout(quality_group)
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["128k", "192k", "256k", "320k"])
        self.quality_combo.setCurrentText("192k")

        self.start_btn = QPushButton("Avvia Ripping")
        self.start_btn.clicked.connect(self.start_ripping)

        self.stop_btn = QPushButton("Ferma")
        self.stop_btn.clicked.connect(self.stop_ripping)
        self.stop_btn.setEnabled(False)


        quality_layout.addWidget(QLabel("Qualità MP3:"))
        quality_layout.addWidget(self.quality_combo)
        quality_layout.addStretch()
        quality_layout.addWidget(self.start_btn)
        quality_layout.addWidget(self.stop_btn)

        #output_layout.addLayout(dir_layout)
       # output_layout.addLayout(quality_layout)

        #layout.addWidget(output_group)
        hv.addWidget(quality_group, stretch=2)
        layout.addLayout(hv)

        # Gruppo Metadata
        metadata_group = QGroupBox("Informazioni Album")
        #metadata_layout = QVBoxLayout(metadata_group)
        metadata_layout = QGridLayout()
        metadata_layout.setHorizontalSpacing(5)
        metadata_layout.setVerticalSpacing(25)

        # Ricerca automatica
        search_layout = QVBoxLayout(metadata_group)
        search_layout.setSpacing(10)

        self.artist_edit = QLineEdit()
        self.album_edit = QLineEdit()
        self.anno_edit = QLineEdit()
        self.genere_edit = QLineEdit()

        self.search_by_artist_button = QPushButton(self)
        self.search_by_artist_button.setText("Cerca")
        self.search_by_artist_button.clicked.connect(self.detect_tracks_byartist)

        self.cover = QLabel()
        self.cover.setMinimumWidth(250)
        self.cover.setMaximumWidth(250)
        self.cover.setMaximumHeight(250)
        self.cover.setStyleSheet("""
            QLabel {
                /* Definisce il bordo: Spessore | Stile | Colore */
                border: 2px solid blue; 

                /* Arrotonda gli angoli (opzionale) */
                border-radius: 5px; 

                /* Aggiunge del padding interno per separare il testo dal bordo (opzionale) */
                padding: 5px;
            }
        """)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        #scroll_area.setMinimumWidth(250)
        #scroll_area.setMaximumWidth(250)
        #scroll_area.setMaximumHeight(250)
        scroll_area.setWidget(self.cover)
        scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        metadata_layout.addWidget(QLabel("Artista:"), 0, 0)
        metadata_layout.addWidget(self.artist_edit, 0, 1)
        metadata_layout.addWidget(QLabel("Album:"), 1, 0)
        metadata_layout.addWidget(self.album_edit, 1, 1)
        metadata_layout.addWidget(QLabel("Anno:"), 2, 0)
        metadata_layout.addWidget(self.anno_edit, 2, 1)
        metadata_layout.addWidget(QLabel("Genere:"), 3, 0)
        metadata_layout.addWidget(self.genere_edit, 3, 1)

        search_layout.addLayout(metadata_layout)
        search_layout.addWidget(self.search_by_artist_button)
        search_layout.addWidget(self.cover, alignment=Qt.AlignmentFlag.AlignHCenter)
        #search_layout.addStretch()

        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.addWidget(metadata_group)

        # Tabella tracce
        from utility import ACTableWidget
        self.tracks_table = ACTableWidget()
        h_labels = ["Seleziona", "N°", "Titolo", "Artista", "Anno", "Genere", "Durata"]
        self.tracks_table.setColumnCount(len(h_labels))
        self.tracks_table.setHorizontalHeaderLabels(h_labels)

        header = self.tracks_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        sp.addWidget( self.tracks_table)
        sp.setSizes([200, 1100])

        layout.addWidget(sp, stretch=1)

    def play(self):
        sel = self.cd_drive_combo.currentText()
        self.play_signal.emit(sel)

    def init_cd_drives(self):
        from utility import detect_cd_drives
        sel = self.cd_drive_combo.currentText()
        self.cd_drive_combo.currentIndexChanged.disconnect(self.detect_tracks)
        self.cd_drive_combo.clear()
        """Rileva i drive CD disponibili"""
        for letter in detect_cd_drives():
            self.cd_drive_combo.addItem(letter)

        self.cd_drive_combo.setCurrentText(sel)
        if self.cd_drive_combo.count() > 0 and self.cd_drive_combo.currentText() != sel:
            self.cd_drive_combo.setCurrentIndex(0)
            self.detect_tracks()
            self.start_btn.setEnabled(True)
        if self.cd_drive_combo.count() == 0:
            self.clear_all()
            self.start_btn.setEnabled(False)
        self.cd_drive_combo.currentIndexChanged.connect(self.detect_tracks)

    def browse_output_dir(self):
        """Seleziona directory di output"""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Seleziona Directory Output",
            self.output_dir_edit.text()
        )
        if dir_path:
            self.output_dir_edit.setText(dir_path)

    def detect_tracks(self):
        cdi = CDinfo(self.cd_drive_combo.currentText())
        res = cdi.detects_tracks()
        df = cdi.detects_info_by_id(res)

        self.cover_download(df.get('idr', ''))
        self.update_tracks_table(df)
        self.start_btn.setEnabled(True)

    def detect_tracks_byartist(self):
        artist = self.artist_edit.text()
        album = self.album_edit.text()
        if artist and album:
            cdi = CDinfo(self.cd_drive_combo.currentText())
            res = cdi.detects_tracks()
            df = cdi.detect_info_by_metadata(res, artist, album)
            if df:
                self.cover_download(df.get('idr', ''))
                self.update_tracks_table(df)
            self.start_btn.setEnabled(True)

    def update_tracks_table(self, tracks_data=None):
        """Aggiorna la tabella delle tracce"""
        if tracks_data is not None:
            self.tracks_data = tracks_data

        self.artist_edit.setText(self.tracks_data.get("artisti", ""))
        self.album_edit.setText(self.tracks_data.get("album", ""))
        self.anno_edit.setText(self.tracks_data.get("anno", ""))
        self.genere_edit.setText(self.tracks_data.get("genere", ""))

        if 'tracce' in self.tracks_data.keys():
            self.tracks_table.setRowCount(len(self.tracks_data['tracce']))

            for row, track in enumerate(self.tracks_data['tracce']):
                # Checkbox selezione
                self._checkItem(row, checked=True)

                # Numero traccia
                self.tracks_table.setItem(row, 1, QTableWidgetItem(str(track['traccia'])))

                # Titolo (editabile)
                title = track.get('titolo', f"Traccia-{row + 1:}")
                title_item = QTableWidgetItem(title)
                self.tracks_table.setItem(row, 2, title_item)

                # Artista (editabile)
                artista = self.tracks_data.get('artisti', "")
                artist_item = QTableWidgetItem(artista)
                self.tracks_table.setItem(row, 3, artist_item)

                anno = self.tracks_data.get('anno', "")
                anno_item = QTableWidgetItem(anno)
                self.tracks_table.setItem(row, 4, anno_item)

                # Durata
                duration = track['durata']
                if isinstance(duration, (int, float)):
                    duration = f"{int(duration // 60)}:{int(duration % 60):02d}"
                self.tracks_table.setItem(row, 6, QTableWidgetItem(str(duration)))

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
        self.tracks_table.setItem(row, 0, check_item)

    def update_track_data(self):
        self.tracks_data['artisti'] = self.artist_edit.text()
        self.tracks_data['album'] = self.album_edit.text()
        self.tracks_data['anno'] = self.anno_edit.text()
        self.tracks_data['genere'] = self.genere_edit.text()

        for row in range(self.tracks_table.rowCount()):
            track = self.tracks_data['tracce'][row]
            track['titolo'] = self.tracks_table.item(row, 2).text()
            artista = self.tracks_table.item(row, 3).text()
            track['artisti'] = artista if artista else self.artist_edit.text()
            album =  self.tracks_data['album']
            track['album'] = album if album else self.album_edit.text()
            track['anno'] = self.tracks_data['anno']
            track['genere'] = self.tracks_data['genere']

    def on_cd_aperto(self):
        self.init_cd_drives()

    def on_cd_chiuso(self):
        self.init_cd_drives()

    def closeEvent(self, event):
        self.monitor.stop()
        event.accept()

    def clear_all(self):
        self.tracks_table.setRowCount(0)
        self.artist_edit.setText("")
        self.album_edit.setText("")
        self.anno_edit.setText("")
        self.genere_edit.setText("")
        self.display_cover("", b"")

    def start_ripping(self):
        """Avvia il processo di ripping"""
        # Validazioni
        if not self.cd_drive_combo.currentText():
            QMessageBox.warning(self, "Attenzione", "Seleziona un drive CD")
            return

        if not self.tracks_data:
            QMessageBox.warning(self, "Attenzione", "Rileva prima le tracce del CD")
            return

        output_dir = self.output_dir_edit.text()
        if not output_dir:
            QMessageBox.warning(self, "Attenzione", "Seleziona una directory di output")
            return

        self.update_track_data()
        output_dir = os.path.join(output_dir, f"{self.tracks_data['artisti']}".replace(':', '_'))
        output_dir = os.path.join(output_dir, f"{self.tracks_data['album']}".replace(':', '_'))
        # Crea directory se non esiste
        os.makedirs(output_dir, exist_ok=True)

        # Aggiorna dati tracce dalla tabella
        selected_tracks = []
        tracks = self.tracks_data['tracce']
        for row in range(self.tracks_table.rowCount()):
            if self.tracks_table.item(row, 0).checkState() == Qt.CheckState.Checked:
            #checkbox = self.tracks_table.cellWidget(row, 0)
            #if checkbox.isChecked():
                track = tracks[row].copy()
                track['artisti'] = self.tracks_data['artisti']
                track['album'] = self.tracks_data['album']
                track['anno'] = self.tracks_data['anno']
                track['genere'] = self.tracks_data['genere']
                selected_tracks.append(track)

        if not selected_tracks:
            QMessageBox.warning(self, "Attenzione", "Seleziona almeno una traccia")
            return

        # Avvia worker thread
        self.ffmpeg_worker = FFmpegWorker(
            self.cd_drive_combo.currentText(),
            selected_tracks,
            output_dir,
            self.quality_combo.currentText(),
            self.cover_path
        )

        # Connetti segnali
        self.ffmpeg_worker.progress_updated.connect(self.progress_bar.setValue)
        self.ffmpeg_worker.status_updated.connect(self.status_label.setText)
        self.ffmpeg_worker.finished_track.connect(self.on_track_finished)
        self.ffmpeg_worker.progress_track.connect(self.on_track_progress)
        self.ffmpeg_worker.error_occurred.connect(self.on_error)
        self.ffmpeg_worker.finished.connect(self.on_ripping_finished)
        self.ffmpeg_worker.ripping_finished.connect(self.on_ripping_finished)

        # Aggiorna UI
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.eject_btn.setEnabled(False)
        self.progress_bar.setValue(0)

        # Avvia thread
        self.monitor.stop()
        self.t0 = time.monotonic()
        self.ffmpeg_worker.start()

    def stop_ripping(self):
        """Ferma il processo di ripping"""
        if self.ffmpeg_worker:
            self.ffmpeg_worker.stop()
            self.status_label.setText("Arresto in corso...")
        self.monitor.start()

    def eject(self):
        from utility import eject_cd
        drive_to_eject = self.cd_drive_combo.currentText()
        if drive_to_eject:
            eject_cd(drive_to_eject)


    def on_track_finished(self, track_num: int, filename: str):
        """Chiamato quando una traccia è completata"""
        self.tracks_table.item(track_num - 1, 0).setCheckState(Qt.CheckState.Unchecked)
        #checkbox = self.tracks_table.cellWidget(track_num - 1, 0)
        #checkbox.setChecked(False)
        self.status_progress.setText("")
        self.status_label.setText(f"Completata traccia {track_num}: {os.path.basename(filename)}")

    def on_track_progress(self, progress: float):
        self.status_progress.setText(f"{progress:.0f}%")

    def on_error(self, error_msg: str):
        """Chiamato in caso di errore"""
        QMessageBox.critical(self, "Errore", error_msg)
        self.monitor.start()

    def on_ripping_finished(self):
        te = time.monotonic()
        """Chiamato quando il ripping è completato"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.eject_btn.setEnabled(True)

        is_interrupted = self.progress_bar.value() < 100
        if not is_interrupted:
            self.progress_bar.setValue(100)
            status_text = f"Ripping completato in {te - self.t0:.2f} secs"
            QMessageBox.information(self, "Completato", "Ripping del CD completato con successo!")
        else:
            status_text = f"Ripping interrotto in {te - self.t0:.2f} secs"
            self.progress_bar.setValue(self.progress_bar.value())  # Mantiene l'ultima percentuale
            QMessageBox.information(self, "Interrotto", "Ripping del CD interrotto dall'utente.")

        self.status_label.setText(status_text)
        self.status_progress.setText("")
        self.monitor.start()

    def cover_download(self, id):
        #QApplication.processEvents()
        from music_brainz import CoverDownloader
        cdi = CoverDownloader()
        cdi.cover_ready.connect(self.display_cover)
        self.cover.clear()
        cdi.download_cover(id=id)
        self.status_label.setText("Download in corso...")

    def display_cover(self, mes, data):
        """Mostra la copertina nell'area dedicata."""
        self.cover_path = ''
        if data:
            try:
                from utility import resize_image_data
                # Ridimensiona l'immagine
                resized_data = resize_image_data(
                    data,
                    target_size=(400, 400),
                    quality=85
                )
                pixmap = QPixmap()
                pixmap.loadFromData(resized_data)
                if pixmap.isNull():
                    self.status_label.setText("Immagine non valida o formato non supportato")
                    self.cover.setPixmap(QPixmap())
                    return

                # Scala l'immagine mantenendo le proporzioni
                self.cover.setPixmap(pixmap.scaled(self.cover.size(), Qt.AspectRatioMode.KeepAspectRatio))
                self.status_label.setText("Pronto")
                self.cover.setText("")
                self.cover_path = os.path.join(self.appCtx.tmpDir, "cover.png")
                with open(self.cover_path, "wb") as f:
                    f.write(resized_data)

            except Exception as e:
                print(f"Errore visualizzazione copertina: {e}")
                self.status_label.setText("Errore caricamento copertina")
                self.cover.setPixmap(QPixmap())
        else:
            self.status_label.setText("Nessuna copertina")
            self.cover.setPixmap(QPixmap())

