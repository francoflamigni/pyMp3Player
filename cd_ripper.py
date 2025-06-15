import sys
import os
import subprocess
import json
import requests
import threading
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QLabel, QLineEdit, QComboBox, QProgressBar,
    QTextEdit, QGroupBox, QSpinBox, QCheckBox, QFileDialog,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QTabWidget, QDialog
)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QFont, QIcon

dataex = """
{
  "streams": [
    {
      "index": 0,
      "codec_name": "pcm_s16le",
      "codec_long_name": "PCM signed 16-bit little-endian",
      "codec_type": "audio",
      "codec_tag_string": "[0][0][0][0]",
      "codec_tag": "0x00000000",
      "sample_fmt": "s16",
      "sample_rate": "44100",
      "channels": 2,
      "channel_layout": "stereo",
      "bits_per_raw_sample": "16",
      "r_frame_rate": "0/0",
      "avg_frame_rate": "0/0",
      "time_base": "1/44100",
      "start_pts": 0,
      "start_time": "0.000000",
      "duration_ts": 15552000,
      "duration": "352.653061",
      "bit_rate": "1411200",
      "disposition": {
        "default": 0,
        "dub": 0,
        "original": 0,
        "comment": 0,
        "lyrics": 0,
        "karaoke": 0,
        "forced": 0,
        "hearing_impaired": 0,
        "visual_impaired": 0,
        "clean_effects": 0,
        "attached_pic": 0,
        "timed_thumbnails": 0
      },
      "tags": {
        "title": "Track 01",
        "track": "1"
      }
    },
    {
      "index": 1,
      "codec_name": "pcm_s16le",
      "codec_long_name": "PCM signed 16-bit little-endian",
      "codec_type": "audio",
      "codec_tag_string": "[0][0][0][0]",
      "codec_tag": "0x00000000",
      "sample_fmt": "s16",
      "sample_rate": "44100",
      "channels": 2,
      "channel_layout": "stereo",
      "bits_per_raw_sample": "16",
      "r_frame_rate": "0/0",
      "avg_frame_rate": "0/0",
      "time_base": "1/44100",
      "start_pts": 15552000,
      "start_time": "352.653061",
      "duration_ts": 12441600,
      "duration": "282.222222",
      "bit_rate": "1411200",
      "disposition": {
        "default": 0,
        "dub": 0,
        "original": 0,
        "comment": 0,
        "lyrics": 0,
        "karaoke": 0,
        "forced": 0,
        "hearing_impaired": 0,
        "visual_impaired": 0,
        "clean_effects": 0,
        "attached_pic": 0,
        "timed_thumbnails": 0
      },
      "tags": {
        "title": "Track 02",
        "track": "2"
      }
    },
    {
      "index": 2,
      "codec_name": "pcm_s16le",
      "codec_long_name": "PCM signed 16-bit little-endian",
      "codec_type": "audio",
      "codec_tag_string": "[0][0][0][0]",
      "codec_tag": "0x00000000",
      "sample_fmt": "s16",
      "sample_rate": "44100",
      "channels": 2,
      "channel_layout": "stereo",
      "bits_per_raw_sample": "16",
      "r_frame_rate": "0/0",
      "avg_frame_rate": "0/0",
      "time_base": "1/44100",
      "start_pts": 28009344,
      "start_time": "635.120544",
      "duration_ts": 9979200,
      "duration": "226.394558",
      "bit_rate": "1411200",
      "disposition": {
        "default": 0,
        "dub": 0,
        "original": 0,
        "comment": 0,
        "lyrics": 0,
        "karaoke": 0,
        "forced": 0,
        "hearing_impaired": 0,
        "visual_impaired": 0,
        "clean_effects": 0,
        "attached_pic": 0,
        "timed_thumbnails": 0
      },
      "tags": {
        "title": "Track 03",
        "track": "3"
      }
    }
  ]
}
"""


class CDInfoFetcher:
    """Classe per recuperare informazioni sui CD da database online"""

    def __init__(self):
        self.musicbrainz_url = "https://musicbrainz.org/ws/2"
        self.headers = {
            'User-Agent': 'CDRipper/1.0 (https://example.com/contact)'
        }

    def get_cd_info_by_discid(self, disc_id: str) -> Optional[Dict]:
        """Recupera informazioni del CD tramite disc ID"""
        try:
            url = f"{self.musicbrainz_url}/discid/{disc_id}"
            params = {
                'fmt': 'json',
                'inc': 'recordings+artist-credits'
            }

            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Errore nel recupero info CD: {e}")
        return None

    def search_cd_by_artist_title(self, artist: str, title: str) -> List[Dict]:
        """Cerca CD per artista e titolo"""
        try:
            url = f"{self.musicbrainz_url}/release"
            params = {
                'query': f'artist:"{artist}" AND release:"{title}"',
                'fmt': 'json',
                'limit': 10
            }

            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get('releases', [])
        except Exception as e:
            print(f"Errore nella ricerca CD: {e}")
        return []


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

                track_num = track['number']
                title = track['title']
                artist = track.get('artist', 'Unknown Artist')

                # Sanitizza il nome del file
                safe_title = self.sanitize_filename(f"{track_num:02d} - {artist} - {title}")
                output_file = os.path.join(self.output_dir, f"{safe_title}.mp3")

                self.status_updated.emit(f"Estraendo traccia {track_num}: {title}")

                # Comando ffmpeg per estrarre la traccia specifica
                cmd = [
                    'ffmpeg', '-y',
                    '-f', 'cdda',
                    '-i', f'\\\\.\\{self.cd_drive}:',
                    '-map', f'0:{track_num - 1}',
                    '-codec:a', 'libmp3lame',
                    '-b:a', self.quality,
                    '-metadata', f'title={title}',
                    '-metadata', f'artist={artist}',
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

    def __init__(self):
        super().__init__()
        self.cd_info_fetcher = CDInfoFetcher()
        self.ffmpeg_worker = None
        self.tracks_data = []

        self.setWindowTitle("CD Ripper con FFmpeg")
        self.setGeometry(100, 100, 1000, 700)

        self.init_ui()
        self.detect_cd_drives()

    def init_ui(self):
        """Inizializza l'interfaccia utente"""
        #central_widget = QWidget()
        #self.setCentralWidget(central_widget)

        # Layout principale
        main_layout = QVBoxLayout(self)

        # Crea tabs
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)

        # Tab 1: Configurazione
        config_tab = QWidget()
        tab_widget.addTab(config_tab, "Configurazione")
        self.setup_config_tab(config_tab)

        # Tab 2: Tracce
        tracks_tab = QWidget()
        tab_widget.addTab(tracks_tab, "Tracce")
        self.setup_tracks_tab(tracks_tab)

        # Pannello di controllo
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)

        # Barra di progresso e status
        self.progress_bar = QProgressBar()
        self.status_label = QLabel("Pronto")

        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.status_label)

    def setup_config_tab(self, tab):
        """Configura il tab delle impostazioni"""
        layout = QVBoxLayout(tab)

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
        self.search_btn = QPushButton("Cerca Info")
        self.search_btn.clicked.connect(self.search_cd_info)

        search_layout.addWidget(QLabel("Artista:"))
        search_layout.addWidget(self.artist_edit)
        search_layout.addWidget(QLabel("Album:"))
        search_layout.addWidget(self.album_edit)
        search_layout.addWidget(self.search_btn)

        metadata_layout.addLayout(search_layout)

        layout.addWidget(metadata_group)

        layout.addStretch()

    def setup_tracks_tab(self, tab):
        """Configura il tab delle tracce"""
        layout = QVBoxLayout(tab)

        # Pulsanti controllo tracce
        tracks_control_layout = QHBoxLayout()
        self.detect_tracks_btn = QPushButton("Rileva Tracce")
        self.detect_tracks_btn.clicked.connect(self.detect_tracks)

        tracks_control_layout.addWidget(self.detect_tracks_btn)
        tracks_control_layout.addStretch()

        layout.addLayout(tracks_control_layout)

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
        self.cd_drive_combo.addItem('e')
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

    def browse_output_dir(self):
        """Seleziona directory di output"""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Seleziona Directory Output",
            self.output_dir_edit.text()
        )
        if dir_path:
            self.output_dir_edit.setText(dir_path)

    def search_cd_info(self):
        """Cerca informazioni del CD online"""
        artist = self.artist_edit.text().strip()
        album = self.album_edit.text().strip()

        if not artist or not album:
            QMessageBox.warning(self, "Attenzione", "Inserisci artista e album per la ricerca")
            return

        # Esegui ricerca in thread separato
        threading.Thread(target=self._search_cd_info_thread, args=(artist, album)).start()
        self.status_label.setText("Ricerca informazioni CD...")

    def _search_cd_info_thread(self, artist: str, album: str):
        """Thread per la ricerca delle informazioni CD"""
        try:
            releases = self.cd_info_fetcher.search_cd_by_artist_title(artist, album)
            if releases:
                # Prendi il primo risultato
                release = releases[0]
                # Qui potresti implementare una finestra di selezione
                # Per ora usa il primo risultato
                self.status_label.setText("Informazioni CD trovate")
            else:
                self.status_label.setText("Nessuna informazione trovata")
        except Exception as e:
            self.status_label.setText(f"Errore nella ricerca: {e}")

    def detect_tracks(self):
        """Rileva le tracce dal CD"""
        if not self.cd_drive_combo.currentText():
            QMessageBox.warning(self, "Attenzione", "Seleziona un drive CD")
            return

        drive = self.cd_drive_combo.currentText()
        self.status_label.setText("Rilevamento tracce...")

        # Esegui rilevamento in thread separato
        threading.Thread(target=self._detect_tracks_thread, args=(drive,)).start()

    def _detect_tracks_thread(self, drive: str):
        """Thread per il rilevamento delle tracce"""
        try:
            # Usa ffprobe per ottenere informazioni sulle tracce
            cmd = [
                'ffprobe',  '-f', 'libcdio', '-i', f'{drive}:', '-print_format', 'json', '-show_streams'
                ]

            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)

            if result.returncode == 0 or True:
                data = json.loads(dataex) #result.stdout)
                streams = data.get('streams', [])

                # Filtra solo stream audio
                audio_streams = [s for s in streams if s.get('codec_type') == 'audio']

                # Popola la lista delle tracce
                self.tracks_data = []
                for i, stream in enumerate(audio_streams):
                    track = {
                        'number': i + 1,
                        'title': f'Track {i + 1:02d}',
                        'artist': self.artist_edit.text() or 'Unknown Artist',
                        'duration': stream.get('duration', 'Unknown'),
                        'selected': True
                    }
                    self.tracks_data.append(track)

                # Aggiorna la tabella nel thread principale
                self.update_tracks_table()
                self.status_label.setText(f"Rilevate {len(self.tracks_data)} tracce")
            else:
                self.status_label.setText("Errore nel rilevamento tracce")

        except Exception as e:
            self.status_label.setText(f"Errore: {e}")

    def update_tracks_table(self):
        """Aggiorna la tabella delle tracce"""
        self.tracks_table.setRowCount(len(self.tracks_data))

        for row, track in enumerate(self.tracks_data):
            # Checkbox selezione
            checkbox = QCheckBox()
            checkbox.setChecked(track['selected'])
            self.tracks_table.setCellWidget(row, 0, checkbox)

            # Numero traccia
            self.tracks_table.setItem(row, 1, QTableWidgetItem(str(track['number'])))

            # Titolo (editabile)
            title_item = QTableWidgetItem(track['title'])
            self.tracks_table.setItem(row, 2, title_item)

            # Artista (editabile)
            artist_item = QTableWidgetItem(track['artist'])
            self.tracks_table.setItem(row, 3, artist_item)

            # Durata
            duration = track['duration']
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

        # Crea directory se non esiste
        os.makedirs(output_dir, exist_ok=True)

        # Aggiorna dati tracce dalla tabella
        selected_tracks = []
        for row in range(self.tracks_table.rowCount()):
            checkbox = self.tracks_table.cellWidget(row, 0)
            if checkbox.isChecked():
                track = self.tracks_data[row].copy()
                track['title'] = self.tracks_table.item(row, 2).text()
                track['artist'] = self.tracks_table.item(row, 3).text()
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


def main():
    """Funzione principale"""
    app = QApplication(sys.argv)

    # Imposta stile moderno
    app.setStyle('Fusion')

    window = CDRipperMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()