#!/usr/bin/env python3
"""
Script per sincronizzare archivio musicale MP3 con interfaccia grafica PyQt6
Versione migliorata per gestire grandi archivi (10000+ files)
"""

import sys
import os
import hashlib
import shutil
import time
import logging
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QDialog, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QLineEdit,
                             QFileDialog, QTextEdit, QProgressBar, QMessageBox,
                             QGroupBox, QTabWidget, QListWidget, QCheckBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont, QColor

# Configura logging su file
log_file = f"music_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)


class ScanThread(QThread):
    """Thread per scansionare e comparare le directory senza bloccare la GUI"""
    progress = pyqtSignal(str)
    progress_value = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal(list, list, list)
    error = pyqtSignal(str)

    def __init__(self, dir_principale, dir_secondario):
        super().__init__()
        self.dir_principale = dir_principale
        self.dir_secondario = dir_secondario
        self._is_running = True

    def stop(self):
        self._is_running = False

    def calcola_hash_file(self, filepath: str) -> str:
        """Calcola l'hash MD5 di un file"""
        hash_md5 = hashlib.md5()
        try:
            with open(filepath, 'rb') as f:
                while chunk := f.read(65536):
                    if not self._is_running:
                        return ""
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logging.error(f"Errore hash {filepath}: {e}")
            return ""

    def scansiona_directory(self, root: str) -> Dict[str, str]:
        """Scansiona directory e restituisce dizionario dei file MP3"""
        files_dict = {}
        root_path = Path(root)

        try:
            for filepath in root_path.rglob("*.mp3"):
                if not self._is_running:
                    break
                percorso_relativo = filepath.relative_to(root_path)
                files_dict[str(percorso_relativo)] = str(filepath)
        except Exception as e:
            logging.error(f"Errore scansione {root}: {e}")
            self.error.emit(f"Errore scansione: {e}")

        return files_dict

    def run(self):
        try:
            self.progress.emit("🔍 Scansione archivio principale...")
            files_principale = self.scansiona_directory(self.dir_principale)
            if not self._is_running:
                return
            self.progress.emit(f"   Trovati {len(files_principale)} file MP3")
            logging.info(f"Principale: {len(files_principale)} files")

            self.progress.emit("🔍 Scansione archivio secondario...")
            files_secondario = self.scansiona_directory(self.dir_secondario)
            if not self._is_running:
                return
            self.progress.emit(f"   Trovati {len(files_secondario)} file MP3")
            logging.info(f"Secondario: {len(files_secondario)} files")

            self.progress.emit("📊 Analisi differenze in corso...")

            mancanti = []
            diversi = []
            extra = []

            # Trova file mancanti e diversi
            totale = len(files_principale)
            for idx, (rel_path, abs_path_principale) in enumerate(files_principale.items()):
                if not self._is_running:
                    return

                if idx % 100 == 0:
                    self.progress.emit(f"   Analizzati {idx}/{totale} file...")
                    self.progress_value.emit(idx, totale)

                if rel_path not in files_secondario:
                    mancanti.append((rel_path, abs_path_principale))
                else:
                    # Per file grandi, verifica prima la dimensione
                    try:
                        size_princ = os.path.getsize(abs_path_principale)
                        size_sec = os.path.getsize(files_secondario[rel_path])

                        if size_princ != size_sec:
                            diversi.append((rel_path, abs_path_principale, files_secondario[rel_path]))
                        else:
                            # Solo se le dimensioni sono uguali, verifica l'hash
                            hash_principale = self.calcola_hash_file(abs_path_principale)
                            hash_secondario = self.calcola_hash_file(files_secondario[rel_path])

                            if hash_principale and hash_secondario and hash_principale != hash_secondario:
                                diversi.append((rel_path, abs_path_principale, files_secondario[rel_path]))
                    except Exception as e:
                        logging.error(f"Errore confronto {rel_path}: {e}")
                        # In caso di errore, considera il file come diverso
                        diversi.append((rel_path, abs_path_principale, files_secondario[rel_path]))

            # Trova file extra
            for rel_path in files_secondario:
                if not self._is_running:
                    return
                if rel_path not in files_principale:
                    extra.append((rel_path, files_secondario[rel_path]))

            self.progress.emit("✅ Analisi completata!")
            logging.info(f"Mancanti: {len(mancanti)}, Diversi: {len(diversi)}, Extra: {len(extra)}")
            self.finished.emit(mancanti, diversi, extra)

        except Exception as e:
            error_msg = f"Errore durante la scansione: {str(e)}"
            logging.error(error_msg)
            self.error.emit(error_msg)


class SyncThread(QThread):
    """Thread per sincronizzare i file con gestione errori migliorata"""
    progress = pyqtSignal(str)
    progress_value = pyqtSignal(int, int)
    file_synced = pyqtSignal(str, bool)  # filename, success
    finished = pyqtSignal(int, int, int)  # successi, fallimenti, totale

    def __init__(self, files_to_sync, dir_secondario, operation='copy', retry_count=3):
        super().__init__()
        self.files_to_sync = files_to_sync
        self.dir_secondario = dir_secondario
        self.operation = operation
        self.retry_count = retry_count
        self._is_running = True

    def stop(self):
        self._is_running = False

    def copia_file_con_retry(self, src, dst, rel_path):
        """Tenta di copiare un file con retry in caso di errore"""
        for tentativo in range(self.retry_count):
            if not self._is_running:
                return False

            try:
                # Crea directory di destinazione
                dst_dir = os.path.dirname(dst)
                os.makedirs(dst_dir, exist_ok=True)

                # Verifica che il file sorgente esista
                if not os.path.exists(src):
                    logging.error(f"File sorgente non esiste: {src}")
                    return False

                # Verifica spazio su disco
                stat = os.statvfs(dst_dir)
                free_space = stat.f_bavail * stat.f_frsize
                file_size = os.path.getsize(src)

                if free_space < file_size * 1.1:  # 10% di margine
                    logging.error(f"Spazio insufficiente per {rel_path}")
                    self.progress.emit(f"❌ ERRORE: Spazio insufficiente per {rel_path}")
                    return False

                # Copia il file
                shutil.copy2(src, dst)

                # Verifica che la copia sia riuscita
                if os.path.exists(dst):
                    src_size = os.path.getsize(src)
                    dst_size = os.path.getsize(dst)
                    if src_size == dst_size:
                        logging.info(f"Copiato con successo: {rel_path}")
                        return True
                    else:
                        logging.warning(f"Dimensione errata dopo copia: {rel_path}")
                        os.remove(dst)  # Rimuovi file corrotto

            except PermissionError as e:
                logging.error(f"Permesso negato per {rel_path}: {e}")
                self.progress.emit(f"❌ Permesso negato: {rel_path}")
                return False

            except OSError as e:
                logging.error(f"Errore OS per {rel_path} (tentativo {tentativo + 1}/{self.retry_count}): {e}")
                if tentativo < self.retry_count - 1:
                    time.sleep(0.5)  # Pausa prima del retry
                    continue

            except Exception as e:
                logging.error(f"Errore generico per {rel_path} (tentativo {tentativo + 1}/{self.retry_count}): {e}")
                if tentativo < self.retry_count - 1:
                    time.sleep(0.5)
                    continue

        return False

    def run(self):
        successi = 0
        fallimenti = 0
        totale = len(self.files_to_sync)
        ultimo_log = 0
        intervallo_log = 50  # Log ogni 50 file

        # Calcola dimensione totale per statistiche
        dimensione_totale = 0
        dimensione_processata = 0

        logging.info(f"Inizio sincronizzazione di {totale} file")
        self.progress.emit(f"Inizio sincronizzazione di {totale} file...")

        for idx, item in enumerate(self.files_to_sync):
            if not self._is_running:
                logging.info("Sincronizzazione interrotta dall'utente")
                break

            try:
                success = False
                file_size = 0

                if self.operation == 'delete':
                    rel_path, abs_path = item
                    try:
                        file_size = os.path.getsize(abs_path)
                        os.remove(abs_path)
                        # Rimuovi directory vuote
                        parent = os.path.dirname(abs_path)
                        if not os.listdir(parent):
                            os.rmdir(parent)
                        logging.info(f"Eliminato: {rel_path}")
                        success = True
                    except Exception as e:
                        logging.error(f"Errore eliminazione {rel_path}: {e}")

                else:
                    if len(item) == 2:
                        rel_path, src = item
                    else:
                        rel_path, src, _ = item

                    try:
                        file_size = os.path.getsize(src)
                    except:
                        pass

                    dst = os.path.join(self.dir_secondario, rel_path)

                    success = self.copia_file_con_retry(src, dst, rel_path)

                    # Log dettagliato solo ogni X file o se fallisce
                    if not success:
                        self.progress.emit(f"❌ [{idx + 1}/{totale}] FALLITO: {rel_path}")

                if success:
                    successi += 1
                    dimensione_processata += file_size
                else:
                    fallimenti += 1

                self.file_synced.emit(rel_path, success)
                self.progress_value.emit(idx + 1, totale)

                # Log ogni X file con statistiche
                if idx - ultimo_log >= intervallo_log or idx == totale - 1:
                    percentuale = ((idx + 1) / totale) * 100
                    dim_proc_mb = dimensione_processata / (1024 ** 2)

                    self.progress.emit(
                        f"📊 Progresso: {idx + 1}/{totale} file ({percentuale:.1f}%) | "
                        f"✓ {successi} | ❌ {fallimenti} | "
                        f"📦 {dim_proc_mb:.1f} MB processati"
                    )
                    ultimo_log = idx

                # Piccola pausa ogni 50 file per non sovraccaricare
                if idx % 50 == 0 and idx > 0:
                    time.sleep(0.1)

            except Exception as e:
                fallimenti += 1
                logging.error(f"Errore imprevisto durante sincronizzazione: {e}")
                self.progress.emit(f"❌ Errore imprevisto: {str(e)}")

        logging.info(f"Sincronizzazione completata: {successi} successi, {fallimenti} fallimenti su {totale}")
        self.finished.emit(successi, fallimenti, totale)


class MusicSyncGUI(QDialog):
    def __init__(self, parent, folder):
        super().__init__(parent)
        self.main_folder = folder
        self.mancanti = []
        self.diversi = []
        self.extra = []
        self.scan_thread = None
        self.sync_thread = None
        self.init_ui()
        self.log(f"📄 File di log: {log_file}")

    def init_ui(self):
        self.setWindowTitle("Sincronizzatore Archivio MP3 - Versione Avanzata")
        self.setGeometry(100, 100, 1100, 750)

        #central_widget = QWidget()
        #self.setCentralWidget(central_widget)
        layout = QVBoxLayout(self)

        # Sezione selezione directory
        dir_group = QGroupBox("Directory")
        dir_layout = QVBoxLayout()

        # Directory principale
        princ_layout = QHBoxLayout()
        princ_layout.addWidget(QLabel("Principale (sorgente):"))
        self.edit_principale = QLineEdit()
        princ_layout.addWidget(self.edit_principale)
        btn_principale = QPushButton("Sfoglia...")
        btn_principale.clicked.connect(self.seleziona_principale)
        princ_layout.addWidget(btn_principale)
        dir_layout.addLayout(princ_layout)
        self.edit_principale.setText(self.main_folder)

        # Directory secondaria
        sec_layout = QHBoxLayout()
        sec_layout.addWidget(QLabel("Secondaria (USB):"))
        self.edit_secondario = QLineEdit()
        sec_layout.addWidget(self.edit_secondario)
        btn_secondario = QPushButton("Sfoglia...")
        btn_secondario.clicked.connect(self.seleziona_secondario)
        sec_layout.addWidget(btn_secondario)
        dir_layout.addLayout(sec_layout)

        dir_group.setLayout(dir_layout)
        layout.addWidget(dir_group)

        # Opzioni
        options_layout = QHBoxLayout()
        self.cb_verify = QCheckBox("Verifica dopo copia")
        self.cb_verify.setChecked(True)
        options_layout.addWidget(self.cb_verify)
        options_layout.addStretch()
        layout.addLayout(options_layout)

        # Pulsante analisi
        self.btn_analizza = QPushButton("🔍 Analizza Differenze")
        self.btn_analizza.setFixedHeight(40)
        font = self.btn_analizza.font()
        font.setPointSize(11)
        font.setBold(True)
        self.btn_analizza.setFont(font)
        self.btn_analizza.clicked.connect(self.avvia_analisi)
        layout.addWidget(self.btn_analizza)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Label stato
        self.lbl_stato = QLabel("")
        self.lbl_stato.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_stato)

        # Tabs per i risultati
        self.tabs = QTabWidget()

        # Tab mancanti
        self.list_mancanti = QListWidget()
        self.tabs.addTab(self.list_mancanti, "File Mancanti (0)")

        # Tab diversi
        self.list_diversi = QListWidget()
        self.tabs.addTab(self.list_diversi, "File Diversi (0)")

        # Tab extra
        self.list_extra = QListWidget()
        self.tabs.addTab(self.list_extra, "File Extra (0)")

        # Tab log
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        font_mono = QFont("Courier New", 9)
        self.log_text.setFont(font_mono)
        self.tabs.addTab(self.log_text, "Log")

        layout.addWidget(self.tabs)

        # Pulsanti azione
        btn_layout = QHBoxLayout()

        self.btn_copia_mancanti = QPushButton("📥 Copia File Mancanti")
        self.btn_copia_mancanti.clicked.connect(self.copia_mancanti)
        self.btn_copia_mancanti.setEnabled(False)
        btn_layout.addWidget(self.btn_copia_mancanti)

        self.btn_aggiorna_diversi = QPushButton("🔄 Aggiorna File Diversi")
        self.btn_aggiorna_diversi.clicked.connect(self.aggiorna_diversi)
        self.btn_aggiorna_diversi.setEnabled(False)
        btn_layout.addWidget(self.btn_aggiorna_diversi)

        self.btn_elimina_extra = QPushButton("🗑️  Elimina File Extra")
        self.btn_elimina_extra.clicked.connect(self.elimina_extra)
        self.btn_elimina_extra.setEnabled(False)
        btn_layout.addWidget(self.btn_elimina_extra)

        self.btn_sincronizza_tutto = QPushButton("⚡ Sincronizza Tutto")
        self.btn_sincronizza_tutto.clicked.connect(self.sincronizza_tutto)
        self.btn_sincronizza_tutto.setEnabled(False)
        btn_layout.addWidget(self.btn_sincronizza_tutto)

        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.clicked.connect(self.stop_operation)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("background-color: #ff4444; color: white;")
        btn_layout.addWidget(self.btn_stop)

        layout.addLayout(btn_layout)

        self.log("✨ Benvenuto! Seleziona le directory e avvia l'analisi.")
        self.log("⚠️  Per archivi grandi (10000+ files) l'analisi può richiedere alcuni minuti.")

    def log(self, messaggio):
        """Aggiunge un messaggio al log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {messaggio}")
        self.log_text.ensureCursorVisible()

    def seleziona_principale(self):
        directory = QFileDialog.getExistingDirectory(self, "Seleziona Directory Principale")
        if directory:
            self.edit_principale.setText(directory)
            logging.info(f"Directory principale: {directory}")

    def seleziona_secondario(self):
        directory = QFileDialog.getExistingDirectory(self, "Seleziona Directory Secondaria (USB)")
        if directory:
            self.edit_secondario.setText(directory)
            logging.info(f"Directory secondaria: {directory}")

    def stop_operation(self):
        """Ferma l'operazione in corso"""
        if self.scan_thread and self.scan_thread.isRunning():
            self.log("⏹ Interruzione analisi...")
            self.scan_thread.stop()
        if self.sync_thread and self.sync_thread.isRunning():
            self.log("⏹ Interruzione sincronizzazione...")
            self.sync_thread.stop()

    def avvia_analisi(self):
        dir_principale = self.edit_principale.text()
        dir_secondario = self.edit_secondario.text()

        if not dir_principale or not dir_secondario:
            QMessageBox.warning(self, "Attenzione", "Seleziona entrambe le directory!")
            return

        if not os.path.isdir(dir_principale) or not os.path.isdir(dir_secondario):
            QMessageBox.critical(self, "Errore", "Una o entrambe le directory non esistono!")
            return

        # Disabilita pulsanti
        self.btn_analizza.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.lbl_stato.setText("Analisi in corso...")

        # Pulisci risultati precedenti
        self.list_mancanti.clear()
        self.list_diversi.clear()
        self.list_extra.clear()
        self.log("\n" + "=" * 70)
        self.log("🚀 Avvio analisi...")
        logging.info("=" * 70)
        logging.info("Avvio analisi")
        logging.info(f"Principale: {dir_principale}")
        logging.info(f"Secondario: {dir_secondario}")

        # Avvia thread di scansione
        self.scan_thread = ScanThread(dir_principale, dir_secondario)
        self.scan_thread.progress.connect(self.log)
        self.scan_thread.progress_value.connect(self.update_progress)
        self.scan_thread.finished.connect(self.analisi_completata)
        self.scan_thread.error.connect(self.analisi_errore)
        self.scan_thread.start()

    def update_progress(self, current, total):
        """Aggiorna la progress bar e lo stato"""
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setValue(current)
            # Aggiorna anche lo stato con il contatore
            if hasattr(self, 'lbl_stato'):
                operazione = self.lbl_stato.text().split(' in corso')[0]
                self.lbl_stato.setText(f"{operazione} in corso... ({current}/{total} - {percent}%)")

    def analisi_completata(self, mancanti, diversi, extra):
        self.mancanti = mancanti
        self.diversi = diversi
        self.extra = extra

        # Aggiorna liste
        for rel_path, _ in mancanti:
            self.list_mancanti.addItem(rel_path)

        for rel_path, _, _ in diversi:
            self.list_diversi.addItem(rel_path)

        for rel_path, _ in extra:
            self.list_extra.addItem(rel_path)

        # Aggiorna tab titles
        self.tabs.setTabText(0, f"File Mancanti ({len(mancanti)})")
        self.tabs.setTabText(1, f"File Diversi ({len(diversi)})")
        self.tabs.setTabText(2, f"File Extra ({len(extra)})")

        # Log riepilogo
        self.log(f"\n📊 RISULTATI:")
        self.log(f"   • File mancanti: {len(mancanti)}")
        self.log(f"   • File diversi: {len(diversi)}")
        self.log(f"   • File extra: {len(extra)}")

        # Riabilita pulsanti
        self.btn_analizza.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.lbl_stato.setText("")
        self.btn_copia_mancanti.setEnabled(len(mancanti) > 0)
        self.btn_aggiorna_diversi.setEnabled(len(diversi) > 0)
        self.btn_elimina_extra.setEnabled(len(extra) > 0)
        self.btn_sincronizza_tutto.setEnabled(len(mancanti) > 0 or len(diversi) > 0)

    def analisi_errore(self, errore):
        QMessageBox.critical(self, "Errore", errore)
        self.log(f"❌ {errore}")
        self.btn_analizza.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.lbl_stato.setText("")

    def copia_mancanti(self):
        if not self.mancanti:
            return

        risposta = QMessageBox.question(
            self, "Conferma",
            f"Copiare {len(self.mancanti)} file mancanti nella directory secondaria?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if risposta == QMessageBox.StandardButton.Yes:
            self.avvia_sincronizzazione(self.mancanti, 'copy')

    def aggiorna_diversi(self):
        if not self.diversi:
            return

        risposta = QMessageBox.question(
            self, "Conferma",
            f"Aggiornare {len(self.diversi)} file diversi sovrascrivendo quelli nella directory secondaria?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if risposta == QMessageBox.StandardButton.Yes:
            self.avvia_sincronizzazione(self.diversi, 'update')

    def elimina_extra(self):
        if not self.extra:
            return

        risposta = QMessageBox.warning(
            self, "⚠️ ATTENZIONE",
            f"Eliminare {len(self.extra)} file dalla directory secondaria?\n\n"
            f"Questi file NON sono presenti nella directory principale.\n"
            f"Questa operazione è IRREVERSIBILE!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if risposta == QMessageBox.StandardButton.Yes:
            self.avvia_sincronizzazione(self.extra, 'delete')

    def sincronizza_tutto(self):
        totale = len(self.mancanti) + len(self.diversi)
        if totale == 0:
            return

        risposta = QMessageBox.question(
            self, "Conferma Sincronizzazione Completa",
            f"Sincronizzare {totale} file?\n\n"
            f"• {len(self.mancanti)} file da copiare\n"
            f"• {len(self.diversi)} file da aggiornare\n\n"
            f"Questa operazione può richiedere molto tempo.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if risposta == QMessageBox.StandardButton.Yes:
            files_combinati = self.mancanti + self.diversi
            self.avvia_sincronizzazione(files_combinati, 'copy')

    def avvia_sincronizzazione(self, files, operation):
        # Verifica spazio disco prima di iniziare
        if operation in ['copy', 'update']:
            dir_secondario = self.edit_secondario.text()

            # Calcola spazio necessario
            spazio_necessario = 0
            for item in files:
                try:
                    if len(item) == 2:
                        _, src = item
                    else:
                        _, src, _ = item
                    spazio_necessario += os.path.getsize(src)
                except:
                    pass

            # Verifica spazio disponibile
            try:
                if sys.platform == 'win32':
                    # Windows: usa l'API Win32
                    import ctypes
                    free_bytes = ctypes.c_ulonglong(0)
                    ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                        ctypes.c_wchar_p(dir_secondario),
                        None,
                        None,
                        ctypes.pointer(free_bytes)
                    )
                    #ctypes.windll.kernel32.GetDiskFreeSpaceExW(...)
                    spazio_disponibile = free_bytes.value
                else:
                    # Linux/Mac: usa statvfs
                    stat = os.statvfs(dir_secondario)
                    spazio_disponibile = stat.f_bavail * stat.f_frsize

                spazio_necessario_gb = spazio_necessario / (1024 ** 3)
                spazio_disponibile_gb = spazio_disponibile / (1024 ** 3)

                self.log(f"\n💾 Verifica spazio disco:")
                self.log(f"   • Spazio necessario: {spazio_necessario_gb:.2f} GB")
                self.log(f"   • Spazio disponibile: {spazio_disponibile_gb:.2f} GB")

                # Margine di sicurezza del 5%
                if spazio_disponibile < spazio_necessario * 1.05:
                    spazio_mancante_gb = (spazio_necessario * 1.05 - spazio_disponibile) / (1024 ** 3)

                    QMessageBox.critical(
                        self, "⚠️ SPAZIO DISCO INSUFFICIENTE",
                        f"ATTENZIONE: Lo spazio su disco non è sufficiente!\n\n"
                        f"📊 Dettagli:\n"
                        f"• Spazio necessario: {spazio_necessario_gb:.2f} GB\n"
                        f"• Spazio disponibile: {spazio_disponibile_gb:.2f} GB\n"
                        f"• Mancano: {spazio_mancante_gb:.2f} GB\n\n"
                        f"Libera spazio sul disco secondario (USB) prima di procedere."
                    )
                    self.log(f"❌ OPERAZIONE ANNULLATA: Spazio insufficiente (mancano {spazio_mancante_gb:.2f} GB)")
                    return
                else:
                    self.log(
                        f"   ✓ Spazio sufficiente (margine: {(spazio_disponibile - spazio_necessario) / (1024 ** 3):.2f} GB)")

            except Exception as e:
                self.log(f"⚠️  Impossibile verificare spazio disco: {e}")
                risposta = QMessageBox.warning(
                    self, "Avviso",
                    f"Impossibile verificare lo spazio disco disponibile.\n\n"
                    f"Errore: {e}\n\n"
                    f"Vuoi procedere comunque?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if risposta != QMessageBox.StandardButton.Yes:
                    return

        self.disabilita_pulsanti()
        self.btn_stop.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(files))
        self.progress_bar.setValue(0)

        op_name = {'copy': 'Copia', 'update': 'Aggiornamento', 'delete': 'Eliminazione'}
        self.lbl_stato.setText(f"{op_name.get(operation, 'Operazione')} in corso...")

        self.log(f"\n🔄 Avvio {op_name.get(operation, 'operazione').lower()} di {len(files)} file...")

        dir_secondario = self.edit_secondario.text()
        self.sync_thread = SyncThread(files, dir_secondario, operation)
        self.sync_thread.progress.connect(self.log)
        self.sync_thread.progress_value.connect(self.update_progress)
        self.sync_thread.file_synced.connect(self.file_sincronizzato)
        self.sync_thread.finished.connect(self.sincronizzazione_completata)
        self.sync_thread.start()

    def file_sincronizzato(self, nome_file, success):
        """Aggiorna il contatore dei file sincronizzati"""
        pass  # Il log è già gestito dal thread

    def sincronizzazione_completata(self, successi, fallimenti, totale):
        self.log(f"\n{'=' * 70}")
        self.log(f"✅ Sincronizzazione completata!")
        self.log(f"   • Successi: {successi}/{totale}")
        if fallimenti > 0:
            self.log(f"   • ⚠️  Fallimenti: {fallimenti}/{totale}")
            self.log(f"   • Controlla il file di log per i dettagli: {log_file}")
        self.log(f"{'=' * 70}")

        self.progress_bar.setVisible(False)
        self.lbl_stato.setText("")
        self.abilita_pulsanti()
        self.btn_stop.setEnabled(False)

        # Messaggio finale
        if fallimenti > 0:
            QMessageBox.warning(
                self, "Sincronizzazione Completata con Errori",
                f"Operazione completata!\n\n"
                f"✓ Successi: {successi}/{totale}\n"
                f"✗ Fallimenti: {fallimenti}/{totale}\n\n"
                f"Controlla il file di log per i dettagli:\n{log_file}"
            )
        else:
            QMessageBox.information(
                self, "Sincronizzazione Completata",
                f"Operazione completata con successo!\n\n"
                f"✓ File elaborati: {successi}/{totale}\n\n"
                f"Vuoi rianalizzare per verificare lo stato aggiornato?"
            )

        # Chiedi se rianalizzare
        if fallimenti == 0:
            risposta = QMessageBox.question(
                self, "Rianalizzare?",
                "Vuoi rianalizzare le directory per verificare che tutto sia sincronizzato?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if risposta == QMessageBox.StandardButton.Yes:
                self.avvia_analisi()

    def disabilita_pulsanti(self):
        self.btn_analizza.setEnabled(False)
        self.btn_copia_mancanti.setEnabled(False)
        self.btn_aggiorna_diversi.setEnabled(False)
        self.btn_elimina_extra.setEnabled(False)
        self.btn_sincronizza_tutto.setEnabled(False)

    def abilita_pulsanti(self):
        self.btn_analizza.setEnabled(True)
        self.btn_copia_mancanti.setEnabled(len(self.mancanti) > 0)
        self.btn_aggiorna_diversi.setEnabled(len(self.diversi) > 0)
        self.btn_elimina_extra.setEnabled(len(self.extra) > 0)
        self.btn_sincronizza_tutto.setEnabled(len(self.mancanti) > 0 or len(self.diversi) > 0)

    def closeEvent(self, event):
        """Gestisce la chiusura della finestra"""
        if self.scan_thread and self.scan_thread.isRunning():
            risposta = QMessageBox.question(
                self, "Operazione in Corso",
                "Un'operazione è ancora in corso. Vuoi interromperla e chiudere?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if risposta == QMessageBox.StandardButton.Yes:
                self.stop_operation()
                self.scan_thread.wait()
                event.accept()
            else:
                event.ignore()
        elif self.sync_thread and self.sync_thread.isRunning():
            risposta = QMessageBox.question(
                self, "Sincronizzazione in Corso",
                "La sincronizzazione è ancora in corso. Vuoi interromperla e chiudere?\n\n"
                "ATTENZIONE: Interrompere potrebbe lasciare l'archivio in uno stato inconsistente!",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if risposta == QMessageBox.StandardButton.Yes:
                self.stop_operation()
                self.sync_thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)

    # Stile dell'applicazione
    app.setStyle('Fusion')

    window = MusicSyncGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()