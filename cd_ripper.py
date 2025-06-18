import sys
import os
import subprocess
import requests
from pathlib import Path
from typing import List, Dict
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QProgressBar,
    QGroupBox, QCheckBox, QFileDialog, QDialog,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt, QMetaObject, Q_ARG
from music_brainz import CDinfo

class FFmpegWorker(QThread):
    """Worker thread per le operazioni ffmpeg"""

    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    finished_track = pyqtSignal(int, str)  # track_number, filename
    error_occurred = pyqtSignal(str)

    def __init__(self, cd_drive: str, tracks: List[Dict], output_dir: str, quality: str):
        super().__init__()
        self.cd_drive = cd_drive
        self.tracks = tracks
        self.output_dir = output_dir
        self.quality = quality
        self.is_running = True

    def stop(self):
        self.is_running = False

    def run(self):
        try:
            total_tracks = len(self.tracks)

            for i, track in enumerate(self.tracks):
                if not self.is_running:
                    break

                track_num = int(track['traccia'])
                title = track['title']
                artist = track.get('artisti', 'Unknown Artist')
                album = track.get('album', 'Unknown Album')
                anno = track.get('anno', 'Unknown Anno')

                # Sanitizza il nome del file
                safe_title = self.sanitize_filename(f"{track_num:02d} - {title}")
                output_file = os.path.join(self.output_dir, f"{safe_title}.mp3")

                self.status_updated.emit(f"Estraendo traccia {track_num}: {title}")

                # Comando ffmpeg per estrarre la traccia specifica
                cmd = [
                    'ffmpeg', '-y',
                    '-f', 'libcdio',
                    '-i', f'{self.cd_drive}:',
                    '-c:a', 'libmp3lame',
                    '-ss', f'{track["start"]}',
                    '-t', f'{track["durata"]}',
                    '-b:a', self.quality,
                    '-metadata', f'title={title}',
                    '-metadata', f'artist={artist}',
                    '-metadata', f'album={album}',
                    '-metadata', f'year={anno}',
                    '-metadata', f'track={track_num}',
                    output_file
                ]

                # Esegui ffmpeg
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True,
                    universal_newlines=True
                )

                stdout, stderr = process.communicate()

                if process.returncode == 0:
                    self.finished_track.emit(track_num, output_file)
                    progress = int((i + 1) / total_tracks * 100)
                    self.progress_updated.emit(progress)
                else:
                    self.error_occurred.emit(f"Errore nell'estrazione traccia {track_num}: {stderr}")

        except Exception as e:
            self.error_occurred.emit(f"Errore generale: {str(e)}")

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

    def __init__(self):
        super().__init__()
        self.ffmpeg_worker = None
        self.tracks_data = []

        self.setWindowTitle("CD Ripper con FFmpeg")
        self.setGeometry(100, 100, 1000, 700)

        self.init_ui()
        self.detect_cd_drives()
        self.tracks_detected.connect(self.update_tracks_table)

    def init_ui(self):
        """Inizializza l'interfaccia utente"""
        #central_widget = QWidget()
        #self.setCentralWidget(central_widget)

        # Layout principale
        main_layout = QVBoxLayout(self)

        self.setup_config_tab(main_layout)

        # Pannello di controllo
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)

        # Barra di progresso e status
        self.progress_bar = QProgressBar()
        self.status_label = QLabel("Pronto")

        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.status_label)

    def setup_config_tab(self, layout):
        """Configura il tab delle impostazioni"""
        #layout = QVBoxLayout(tab)

        # Gruppo CD Drive
        cd_group = QGroupBox("Drive CD")
        cd_layout = QHBoxLayout(cd_group)

        self.cd_drive_combo = QComboBox()
        self.refresh_drives_btn = QPushButton("Aggiorna")
        self.refresh_drives_btn.clicked.connect(self.detect_cd_drives)

        cd_layout.addWidget(QLabel("Drive:"))
        cd_layout.addWidget(self.cd_drive_combo)
        cd_layout.addWidget(self.refresh_drives_btn)

        layout.addWidget(cd_group)

        # Gruppo Output
        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout(output_group)

        # Directory output
        dir_layout = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setText(str(Path.home() / "Music" / "Ripped CDs"))
        self.browse_btn = QPushButton("Sfoglia...")
        self.browse_btn.clicked.connect(self.browse_output_dir)

        dir_layout.addWidget(QLabel("Directory:"))
        dir_layout.addWidget(self.output_dir_edit)
        dir_layout.addWidget(self.browse_btn)

        # Qualità
        quality_layout = QHBoxLayout()
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["128k", "192k", "256k", "320k"])
        self.quality_combo.setCurrentText("192k")

        quality_layout.addWidget(QLabel("Qualità MP3:"))
        quality_layout.addWidget(self.quality_combo)
        quality_layout.addStretch()

        output_layout.addLayout(dir_layout)
        output_layout.addLayout(quality_layout)

        layout.addWidget(output_group)

        # Gruppo Metadata
        metadata_group = QGroupBox("Informazioni Album")
        metadata_layout = QVBoxLayout(metadata_group)

        # Ricerca automatica
        search_layout = QHBoxLayout()
        self.artist_edit = QLineEdit()
        self.album_edit = QLineEdit()
        self.anno_edit = QLineEdit()

        search_layout.addWidget(QLabel("Artista:"))
        search_layout.addWidget(self.artist_edit)
        search_layout.addWidget(QLabel("Album:"))
        search_layout.addWidget(self.album_edit)
        search_layout.addWidget(QLabel("Anno:"))
        search_layout.addWidget(self.anno_edit)
        #search_layout.addWidget(self.search_btn)

        metadata_layout.addLayout(search_layout)

        layout.addWidget(metadata_group)

        # Tabella tracce
        self.tracks_table = QTableWidget()
        self.tracks_table.setColumnCount(5)
        self.tracks_table.setHorizontalHeaderLabels([
            "Seleziona", "N°", "Titolo", "Artista", "Durata"
        ])

        header = self.tracks_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.tracks_table)


    def create_control_panel(self):
        """Crea il pannello di controllo"""
        panel = QGroupBox("Controlli")
        layout = QHBoxLayout(panel)

        self.start_btn = QPushButton("Avvia Ripping")
        self.start_btn.clicked.connect(self.start_ripping)

        self.stop_btn = QPushButton("Ferma")
        self.stop_btn.clicked.connect(self.stop_ripping)
        self.stop_btn.setEnabled(False)

        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        layout.addStretch()

        return panel

    def detect_cd_drives(self):
        """Rileva i drive CD disponibili"""
        self.cd_drive_combo.clear()
        # Su Windows, cerca drive da D a Z
        for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
            drive_path = f"{letter}:\\"
            if os.path.exists(drive_path):
                try:
                    # Verifica se è un drive CD
                    import win32file
                    drive_type = win32file.GetDriveType(drive_path)
                    if drive_type == win32file.DRIVE_CDROM:
                        self.cd_drive_combo.addItem(letter)
                except:
                    # Fallback: aggiungi tutti i drive trovati
                    self.cd_drive_combo.addItem(letter)
        self.detect_tracks()

    def browse_output_dir(self):
        """Seleziona directory di output"""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Seleziona Directory Output",
            self.output_dir_edit.text()
        )
        if dir_path:
            self.output_dir_edit.setText(dir_path)

    def detect_tracks(self):
        drive = self.cd_drive_combo.currentText()
        cdi = CDinfo(drive)
        df = cdi.detects_tracs()
        self.update_tracks_table(df)

    def update_tracks_table(self, tracks_data=None):
        """Aggiorna la tabella delle tracce"""
        if tracks_data is not None:
            self.tracks_data = tracks_data
        self.artist_edit.setText(tracks_data.get("artisti", ""))
        self.album_edit.setText(tracks_data.get("titolo", ""))
        self.anno_edit.setText(tracks_data.get("data", ""))

        self.tracks_table.setRowCount(len(self.tracks_data['tracce']))

        for row, track in enumerate(self.tracks_data['tracce']):
            # Checkbox selezione
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            self.tracks_table.setCellWidget(row, 0, checkbox)

            # Numero traccia
            self.tracks_table.setItem(row, 1, QTableWidgetItem(str(track['traccia'])))

            # Titolo (editabile)
            title = track.get('title', f"Traccia-{row + 1:}")
            title_item = QTableWidgetItem(title)
            self.tracks_table.setItem(row, 2, title_item)

            # Artista (editabile)
            artista = tracks_data.get('artisti', "")
            artist_item = QTableWidgetItem(artista)
            self.tracks_table.setItem(row, 3, artist_item)

            # Durata
            duration = track['durata']
            if isinstance(duration, (int, float)):
                duration = f"{int(duration // 60)}:{int(duration % 60):02d}"
            self.tracks_table.setItem(row, 4, QTableWidgetItem(str(duration)))

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

        output_dir = os.path.join(output_dir, f"{self.tracks_data['artisti']}")
        output_dir = os.path.join(output_dir, f"{self.tracks_data['titolo']}")
        # Crea directory se non esiste
        os.makedirs(output_dir, exist_ok=True)

        # Aggiorna dati tracce dalla tabella
        selected_tracks = []
        tracks = self.tracks_data['tracce']
        date_object = datetime.strptime( self.tracks_data['data'], "%Y-%m-%d")
        anno = date_object.year
        for row in range(self.tracks_table.rowCount()):
            checkbox = self.tracks_table.cellWidget(row, 0)
            if checkbox.isChecked():
                track = tracks[row].copy()
                #track['title'] = self.tracks_table.item(row, 2).text()
                #track['artist'] = self.tracks_table.item(row, 3).text()
                track['artisti'] = self.tracks_data['artisti']
                track['album'] = self.tracks_data['titolo']
                track['anno'] = anno
                selected_tracks.append(track)

        if not selected_tracks:
            QMessageBox.warning(self, "Attenzione", "Seleziona almeno una traccia")
            return

        # Avvia worker thread
        self.ffmpeg_worker = FFmpegWorker(
            self.cd_drive_combo.currentText(),
            selected_tracks,
            output_dir,
            self.quality_combo.currentText()
        )

        # Connetti segnali
        self.ffmpeg_worker.progress_updated.connect(self.progress_bar.setValue)
        self.ffmpeg_worker.status_updated.connect(self.status_label.setText)
        self.ffmpeg_worker.finished_track.connect(self.on_track_finished)
        self.ffmpeg_worker.error_occurred.connect(self.on_error)
        self.ffmpeg_worker.finished.connect(self.on_ripping_finished)

        # Aggiorna UI
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)

        # Avvia thread
        self.ffmpeg_worker.start()

    def stop_ripping(self):
        """Ferma il processo di ripping"""
        if self.ffmpeg_worker:
            self.ffmpeg_worker.stop()
            self.status_label.setText("Arresto in corso...")

    def on_track_finished(self, track_num: int, filename: str):
        """Chiamato quando una traccia è completata"""
        self.status_label.setText(f"Completata traccia {track_num}: {os.path.basename(filename)}")

    def on_error(self, error_msg: str):
        """Chiamato in caso di errore"""
        QMessageBox.critical(self, "Errore", error_msg)

    def on_ripping_finished(self):
        """Chiamato quando il ripping è completato"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setValue(100)
        self.status_label.setText("Ripping completato!")

        QMessageBox.information(self, "Completato", "Ripping del CD completato con successo!")
