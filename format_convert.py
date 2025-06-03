import sys
import os
import soundfile as sf
import lameenc

from PyQt6.QtWidgets import (QApplication, QWidget, QPushButton, QFileDialog,
                             QVBoxLayout, QLabel, QProgressBar, QListWidget,
                             QListWidgetItem, QDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import numpy as np
from pyMyLib.utils import iniConf


from mutagen import File
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TCON, TRCK, TPE2, TPOS, APIC


class WorkerThread(QThread):
    """Thread per eseguire la conversione audio."""
    conversion_started = pyqtSignal(str)
    conversion_progress = pyqtSignal(int, int)  # current_file, total_files
    conversion_finished = pyqtSignal(str)
    conversion_error = pyqtSignal(str, str)  # filename, error_message

    def __init__(self, input_files, output_folder):
        super().__init__()
        self.input_files = input_files
        self.output_folder = output_folder
        self.is_running = True

    def run(self):
        num_files = len(self.input_files)
        for i, input_file in enumerate(self.input_files):
            if not self.is_running:
                break
            output_file = os.path.join(self.output_folder, os.path.basename(input_file).rsplit('.', 1)[0] + ".mp3")
            self.conversion_started.emit(os.path.basename(input_file))
            if self.convert_audio_to_mp3_with_tags(input_file, output_file):
                self.conversion_progress.emit(i + 1, num_files)
            else:
                # L'errore è già stato emesso in convert_single_audio
                pass
        self.conversion_finished.emit(self.output_folder)

    def stop(self):
        self.is_running = False


    '''
    def convert_single_audio(self, aiff_file, mp3_file, bitrate="320k"):
        """Converte un singolo file audio in MP3 usando soundfile e lameenc."""
        try:
            # Leggi il file AIFF
            data, samplerate = sf.read(aiff_file)
            print(f"Tipo di dati AIFF: {data.dtype}, Shape: {data.shape}")

            # Converti a float32 se necessario (normalizzato tra -1 e 1)
            if data.dtype != 'float32':
                data = data.astype('float32')

            # Assicurati che i dati siano nel range corretto [-1, 1]
            if data.max() > 1.0 or data.min() < -1.0:
                data = data / np.max(np.abs(data))
                print("Dati normalizzati nel range [-1, 1]")

            # Converti da float32 a int16 per lameenc
            # Moltiplica per 32767 (max int16) e converti a int16
            data_int16 = (data * 32767).astype('int16')
            print(f"Convertito a int16, range: [{data_int16.min()}, {data_int16.max()}]")

            # Determina il numero di canali
            if data_int16.ndim == 1:
                channels = 1
            else:
                channels = data_int16.shape[1]

            print(f"Campioni: {samplerate}, Canali: {channels}")

            # Crea l'encoder LAME
            encoder = lameenc.Encoder(
                rate=samplerate,
                channels=channels,
                bitrate=int(bitrate[:-1]),
                quality=2
            )

            # Opzionale: salva un WAV intermedio per debug
            #wav_intermediate = "intermediate.wav"
            #sf.write(wav_intermediate, data_int16, samplerate, format='WAV', subtype='PCM_16')
            #print(f"Salvato file intermedio (PCM_16): {wav_intermediate}")

            # Codifica in MP3
            mp3_data = encoder.encode(data_int16.tobytes())
            mp3_data += encoder.flush()

            # Salva il file MP3
            with open(mp3_file, 'wb') as f:
                f.write(mp3_data)

            # Pulisci il file intermedio
            #os.remove(wav_intermediate)

            print(f"Conversione completata: {aiff_file} -> {mp3_file}")
            return True

        except Exception as e:
            print(f"Errore durante la conversione: {e}")
            return False



    def convert_audio_to_mp3(self, input_file, mp3_file, bitrate="320k"):
        """Converte file audio (AIFF, FLAC, WAV, etc.) in MP3 usando soundfile e lameenc."""
        try:
            # Leggi il file audio (funziona per AIFF, FLAC, WAV, etc.)
            data, samplerate = sf.read(input_file)

            # Identifica il formato dal file
            file_format = input_file.split('.')[-1].upper()
            print(f"Conversione {file_format}: {input_file}")
            print(f"Tipo di dati: {data.dtype}, Shape: {data.shape}")

            # Converti a float32 se necessario (normalizzato tra -1 e 1)
            if data.dtype != 'float32':
                data = data.astype('float32')

            # Assicurati che i dati siano nel range corretto [-1, 1]
            if data.max() > 1.0 or data.min() < -1.0:
                data = data / np.max(np.abs(data))
                print("Dati normalizzati nel range [-1, 1]")

            # Converti da float32 a int16 per lameenc
            # Moltiplica per 32767 (max int16) e converti a int16
            data_int16 = (data * 32767).astype('int16')
            print(f"Convertito a int16, range: [{data_int16.min()}, {data_int16.max()}]")

            # Determina il numero di canali
            if data_int16.ndim == 1:
                channels = 1
            else:
                channels = data_int16.shape[1]

            print(f"Campioni: {samplerate}, Canali: {channels}")

            # Crea l'encoder LAME
            encoder = lameenc.Encoder(
                rate=samplerate,
                channels=channels,
                bitrate=int(bitrate[:-1]),
                quality=2
            )

            # Codifica in MP3
            mp3_data = encoder.encode(data_int16.tobytes())
            mp3_data += encoder.flush()

            # Salva il file MP3
            with open(mp3_file, 'wb') as f:
                f.write(mp3_data)

            print(f"Conversione completata: {input_file} -> {mp3_file}")
            return True

        except Exception as e:
            print(f"Errore durante la conversione di {input_file}: {e}")
            return False
    '''

    def convert_audio_to_mp3_with_tags(self, input_file, mp3_file, bitrate="320k"):
        """Converte file audio in MP3 conservando tutti i tag/metadati."""
        try:
            # STEP 1: Estrai i metadati dal file originale
            print(f"Estraendo metadati da: {input_file}")
            original_tags = self.extract_all_tags(input_file)

            # STEP 2: Converti l'audio (come prima)
            data, samplerate = sf.read(input_file)

            file_format = input_file.split('.')[-1].upper()
            print(f"Conversione {file_format}: {input_file}")
            print(f"Tipo di dati: {data.dtype}, Shape: {data.shape}")

            # Converti a float32 se necessario
            if data.dtype != 'float32':
                data = data.astype('float32')

            # Normalizza nel range [-1, 1]
            if data.max() > 1.0 or data.min() < -1.0:
                data = data / np.max(np.abs(data))
                print("Dati normalizzati nel range [-1, 1]")

            # Converti a int16 per lameenc
            data_int16 = (data * 32767).astype('int16')
            print(f"Convertito a int16, range: [{data_int16.min()}, {data_int16.max()}]")

            # Determina canali
            if data_int16.ndim == 1:
                channels = 1
            else:
                channels = data_int16.shape[1]

            print(f"Campioni: {samplerate}, Canali: {channels}")

            # Crea encoder LAME
            encoder = lameenc.Encoder(
                rate=samplerate,
                channels=channels,
                bitrate=int(bitrate[:-1]),
                quality=2
            )

            # Codifica in MP3
            mp3_data = encoder.encode(data_int16.tobytes())
            mp3_data += encoder.flush()

            # Salva il file MP3
            with open(mp3_file, 'wb') as f:
                f.write(mp3_data)

            # STEP 3: Trasferisci tutti i tag al file MP3
            print(f"Trasferendo {len(original_tags)} tag al file MP3...")
            self.transfer_tags_to_mp3(original_tags, mp3_file)

            print(f"Conversione completata con tag: {input_file} -> {mp3_file}")
            return True

        except Exception as e:
            print(f"Errore durante la conversione: {e}")
            return False


    def extract_all_tags(self, file_path):
        """Estrae tutti i tag/metadati dal file audio."""
        try:
            audio_file = File(file_path)
            if audio_file is None:
                print("Nessun tag trovato nel file")
                return {}

            tags = {}

            # Tag comuni per tutti i formati
            common_mappings = {
                # Vorbis/FLAC tags -> ID3 tags
                'TITLE': 'TIT2',
                'ARTIST': 'TPE1',
                'ALBUM': 'TALB',
                'DATE': 'TDRC',
                'YEAR': 'TDRC',
                'GENRE': 'TCON',
                'TRACKNUMBER': 'TRCK',
                'TRACK': 'TRCK',
                'ALBUMARTIST': 'TPE2',
                'DISCNUMBER': 'TPOS',
                'DISC': 'TPOS',
                # ID3v2 tags (già in formato corretto)
                'TIT2': 'TIT2',
                'TPE1': 'TPE1',
                'TALB': 'TALB',
                'TDRC': 'TDRC',
                'TCON': 'TCON',
                'TRCK': 'TRCK',
                'TPE2': 'TPE2',
                'TPOS': 'TPOS'
            }

            # Estrai tutti i tag
            for key, value in audio_file.tags.items() if hasattr(audio_file, 'tags') and audio_file.tags else []:
                key_upper = key.upper()

                # Mappa i tag comuni
                if key_upper in common_mappings:
                    id3_key = common_mappings[key_upper]
                    if isinstance(value, list):
                        tags[id3_key] = str(value[0]) if value else ""
                    else:
                        tags[id3_key] = str(value)
                else:
                    # Conserva anche tag non standard
                    tags[key] = str(value[0]) if isinstance(value, list) and value else str(value)

            # Estrai artwork se presente
            if hasattr(audio_file, 'pictures') and audio_file.pictures:
                # FLAC
                tags['ARTWORK'] = audio_file.pictures[0].data
            elif 'APIC:' in str(audio_file.tags) if hasattr(audio_file, 'tags') and audio_file.tags else False:
                # MP3 con artwork
                for key, value in audio_file.tags.items():
                    if key.startswith('APIC'):
                        tags['ARTWORK'] = value.data
                        break

            print(f"Estratti {len(tags)} tag: {list(tags.keys())}")
            return tags

        except Exception as e:
            print(f"Errore estrazione tag: {e}")
            return {}


    def transfer_tags_to_mp3(self, tags, mp3_file):
        """Trasferisce i tag al file MP3 usando ID3v2."""
        try:
            # Crea o carica i tag ID3
            try:
                id3_tags = ID3(mp3_file)
            except:
                id3_tags = ID3()

            # Mappa e aggiungi i tag
            for key, value in tags.items():
                if key == 'ARTWORK':
                    # Aggiungi artwork
                    id3_tags.add(APIC(
                        encoding=3,  # UTF-8
                        mime='image/jpeg',  # Assume JPEG
                        type=3,  # Cover (front)
                        desc='Cover',
                        data=value
                    ))
                    continue

                # Tag di testo standard
                if key == 'TIT2':
                    id3_tags.add(TIT2(encoding=3, text=value))
                elif key == 'TPE1':
                    id3_tags.add(TPE1(encoding=3, text=value))
                elif key == 'TALB':
                    id3_tags.add(TALB(encoding=3, text=value))
                elif key == 'TDRC':
                    id3_tags.add(TDRC(encoding=3, text=value))
                elif key == 'TCON':
                    id3_tags.add(TCON(encoding=3, text=value))
                elif key == 'TRCK':
                    id3_tags.add(TRCK(encoding=3, text=value))
                elif key == 'TPE2':
                    id3_tags.add(TPE2(encoding=3, text=value))
                elif key == 'TPOS':
                    id3_tags.add(TPOS(encoding=3, text=value))
                else:
                    # Per tag non standard, prova ad aggiungerli comunque
                    try:
                        # Crea un frame generico se possibile
                        frame_class = getattr(__import__('mutagen.id3', fromlist=[key]), key, None)
                        if frame_class:
                            id3_tags.add(frame_class(encoding=3, text=value))
                    except:
                        print(f"Tag non supportato ignorato: {key}")

            # Salva i tag nel file MP3
            id3_tags.save(mp3_file)
            print(f"Tag salvati in: {mp3_file}")

        except Exception as e:
            print(f"Errore trasferimento tag: {e}")


    # Funzione di utilità per verificare i tag
    def verify_tags(self, mp3_file):
        """Verifica i tag nel file MP3 creato."""
        try:
            audio_file = File(mp3_file)
            if audio_file and hasattr(audio_file, 'tags') and audio_file.tags:
                print(f"\nTag nel file MP3 '{mp3_file}':")
                for key, value in audio_file.tags.items():
                    print(f"  {key}: {value}")
            else:
                print(f"Nessun tag trovato in {mp3_file}")
        except Exception as e:
            print(f"Errore verifica tag: {e}")

class AudioConverter(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Converti Audio in MP3")
        self.setGeometry(100, 100, 400, 300)

        self.input_folder = None
        self.audio_files = []
        self.conversion_thread = None

        self.folder_button = QPushButton("Seleziona Cartella")
        self.folder_button.clicked.connect(self.select_folder)

        self.file_list_label = QLabel("File audio trovati:")
        self.file_list_widget = QListWidget()

        self.convert_button = QPushButton("Converti in MP3")
        self.convert_button.clicked.connect(self.start_conversion)
        self.convert_button.setEnabled(False)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)

        self.log_label = QLabel("Stato:")

        layout = QVBoxLayout()
        layout.addWidget(self.folder_button)
        layout.addWidget(self.file_list_label)
        layout.addWidget(self.file_list_widget)
        layout.addWidget(self.convert_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.log_label)
        self.setLayout(layout)

    def select_folder(self):
        ini = iniConf('music_player')
        last_folder = ini.get('CONF', 'last_folder')
        """Apre una dialog per selezionare la cartella di input."""
        folder = QFileDialog.getExistingDirectory(self, "Seleziona Cartella Audio", last_folder)
        if folder:
            self.input_folder = folder
            self.find_audio_files()

    def find_audio_files(self):
        """Trova i file audio non MP3 nella cartella selezionata."""
        self.audio_files = []
        self.file_list_widget.clear()
        audio_extensions = ['.aiff', '.wav', '.flac', '.ogg', '.m4a']
        for filename in os.listdir(self.input_folder):
            if any(filename.lower().endswith(ext) for ext in audio_extensions) and not filename.lower().endswith('.mp3'):
                self.audio_files.append(os.path.join(self.input_folder, filename))
                item = QListWidgetItem(filename)
                self.file_list_widget.addItem(item)

        if self.audio_files:
            self.convert_button.setEnabled(True)
            self.log_label.setText(f"Trovati {len(self.audio_files)} file audio da convertire.")
        else:
            self.convert_button.setEnabled(False)
            self.log_label.setText("Nessun file audio non MP3 trovato nella cartella.")

    def start_conversion(self):
        """Avvia la conversione audio in un thread separato."""
        if not self.audio_files:
            self.log_label.setText("Nessun file da convertire.")
            return

        #output_folder = os.path.join(self.input_folder, "mp3_converted")
        output_folder = self.input_folder
        os.makedirs(output_folder, exist_ok=True)

        self.convert_button.setEnabled(False)
        self.progress_bar.setRange(0, len(self.audio_files))
        self.progress_bar.setValue(0)
        self.log_label.setText("Inizio conversione...")

        self.conversion_thread = WorkerThread(self.audio_files, output_folder)
        self.conversion_thread.conversion_started.connect(self.update_status_start)
        self.conversion_thread.conversion_progress.connect(self.update_progress)
        self.conversion_thread.conversion_finished.connect(self.conversion_complete)
        self.conversion_thread.conversion_error.connect(self.show_error)
        self.conversion_thread.start()

    def update_status_start(self, filename):
        self.log_label.setText(f"Conversione in corso: {filename}")

    def update_progress(self, current, total):
        self.progress_bar.setValue(current)

    def conversion_complete(self, output_folder):
        self.log_label.setText(f"Conversione completata. I file MP3 sono in: {output_folder}")
        self.convert_button.setEnabled(True)
        self.conversion_thread = None

    def show_error(self, filename, error_message):
        self.log_label.setText(f"Errore durante la conversione di {filename}: {error_message}")
        self.convert_button.setEnabled(True)
        self.conversion_thread = None

    def closeEvent(self, event):
        """Gestisce la chiusura della finestra e ferma il thread se in esecuzione."""
        if self.conversion_thread and self.conversion_thread.isRunning():
            self.conversion_thread.stop()
            self.conversion_thread.wait()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    converter = AudioConverter()