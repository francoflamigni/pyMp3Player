import os
import shutil
import hashlib
import psutil
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QTreeWidget,
                             QTreeWidgetItem, QLabel, QMessageBox, QFileDialog, QDialog)
from PyQt6.QtGui import QColor, QBrush, QPixmap, QPainter, QIcon

# ... (Import e funzioni ausiliarie precedenti) ...

from PyQt6.QtWidgets import QProgressDialog
from PyQt6.QtCore import Qt, QThread, pyqtSignal


class CopyWorker(QThread):
    """Worker thread per l'operazione di copia asincrona."""
    # Segnale: (byte_copiati, byte_totali)
    progress_updated = pyqtSignal(int, int)
    # Segnale: (successo_bool, messaggio_errore_str)
    finished = pyqtSignal(bool, str)

    def __init__(self, source_path, target_path, total_size):
        super().__init__()
        self.source_path = source_path
        self.target_path = target_path
        self.total_size = total_size
        self.bytes_copied = 0

    def run(self):
        try:
            # Assicurati che la cartella target esista (per copy_file_with_progress)
            os.makedirs(os.path.dirname(self.target_path), exist_ok=True)

            # Usiamo os.walk e shutil.copy2 per copiare file per file e tracciare i progressi
            for dirpath, dirnames, filenames in os.walk(self.source_path):
                # Ricrea la struttura della sottocartella in B
                relative_path = os.path.relpath(dirpath, self.source_path)
                target_dir = os.path.join(self.target_path, relative_path)
                os.makedirs(target_dir, exist_ok=True)

                for filename in filenames:
                    src_file = os.path.join(dirpath, filename)
                    dst_file = os.path.join(target_dir, filename)

                    # Copia il file e registra l'avanzamento
                    shutil.copy2(src_file, dst_file)
                    self.bytes_copied += os.path.getsize(src_file)

                    # Emetti il segnale di avanzamento
                    self.progress_updated.emit(self.bytes_copied, self.total_size)

            self.finished.emit(True, "")

        except Exception as e:
            self.finished.emit(False, str(e))
# --- Funzioni Ausiliarie ---

def get_folder_size(path):
    """Calcola la dimensione totale in byte di una cartella."""
    if not os.path.exists(path):
        return 0
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                # Usa os.path.getsize, gestendo i permessi
                total_size += os.path.getsize(fp)
            except OSError:
                pass  # Ignora file inaccessibili
    return total_size


def check_disk_space(target_path, required_size):
    """Verifica se c'è spazio sufficiente sulla partizione del target."""
    try:
        # Usa psutil per ottenere lo spazio libero sulla partizione
        disk_usage = psutil.disk_usage(os.path.abspath(target_path))
        available_space = disk_usage.free
        return available_space >= required_size
    except Exception:
        # Fallback se psutil fallisce o il percorso non è valido
        return False


def calculate_md5(filepath, chunk_size=8192):
    """Calcola l'hash MD5 di un file."""
    hash_md5 = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            # Legge il file in blocchi per gestire file di grandi dimensioni
            for chunk in iter(lambda: f.read(chunk_size), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return None


# --- Classe Principale dell'Applicazione ---

class SyncApp(QDialog):
    def __init__(self, parent, folder=None):
        super().__init__(parent)
        self.setWindowTitle("PyQt6 Sync Tool (A -> B)")
        self.setGeometry(100, 100, 900, 600)

        self.root_A = folder  # Cartella di Riferimento
        self.root_B = None  # Cartella da Sincronizzare
        self.progress_dialog = None

        self._create_status_icons()  # Chiama questa funzione
        self._setup_ui()

    # NUOVA FUNZIONE per creare le icone
    def _create_status_icons(self):
        """Crea le icone dei pallini colorati per lo stato."""
        icon_size = 16

        # 🟢 Icona Verde (Presente/OK)
        pixmap_green = QPixmap(icon_size, icon_size)
        pixmap_green.fill(Qt.GlobalColor.transparent)
        painter_green = QPainter(pixmap_green)
        painter_green.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter_green.setBrush(QBrush(QColor("green")))
        painter_green.drawEllipse(1, 1, icon_size - 2, icon_size - 2)
        painter_green.end()
        self.icon_green = QIcon(pixmap_green)

        # 🔴 Icona Rossa (Mancante)
        pixmap_red = QPixmap(icon_size, icon_size)
        pixmap_red.fill(Qt.GlobalColor.transparent)
        painter_red = QPainter(pixmap_red)
        painter_red.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter_red.setBrush(QBrush(QColor("red")))
        painter_red.drawEllipse(1, 1, icon_size - 2, icon_size - 2)
        painter_red.end()
        self.icon_red = QIcon(pixmap_red)

        # 🟡 Icona Gialla/Arancione (MD5 Diverso)
        pixmap_yellow = QPixmap(icon_size, icon_size)
        pixmap_yellow.fill(Qt.GlobalColor.transparent)
        painter_yellow = QPainter(pixmap_yellow)
        painter_yellow.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter_yellow.setBrush(QBrush(QColor("orange")))  # Usiamo arancione
        painter_yellow.drawEllipse(1, 1, icon_size - 2, icon_size - 2)
        painter_yellow.end()
        self.icon_yellow = QIcon(pixmap_yellow)

    def _setup_ui(self):
        #central_widget = QWidget()
        #.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(self)

        # Selezione Cartelle
        path_layout = QHBoxLayout()
        self.label_A = QLabel("Root A (Riferimento): Non selezionata")
        if self.root_A:
            self.label_A.setText(self.root_A)
        self.label_B = QLabel("Root B (Target): Non selezionata")
        btn_select_A = QPushButton("Seleziona Root A")
        btn_select_B = QPushButton("Seleziona Root B")
        btn_load = QPushButton("Carica Primo Livello")

        path_layout.addWidget(self.label_A)
        path_layout.addWidget(btn_select_A)
        path_layout.addWidget(self.label_B)
        path_layout.addWidget(btn_select_B)
        path_layout.addWidget(btn_load)
        main_layout.addLayout(path_layout)

        # Tree Widget
        self.tree_widget = QTreeWidget()
        self.tree_widget.setColumnCount(3)
        self.tree_widget.setHeaderLabels(["Nome", "Stato", "Percorso"])
        self.tree_widget.setColumnWidth(0, 400)
        self.tree_widget.setColumnWidth(1, 50)
        self.tree_widget.setColumnWidth(2, 120)
        main_layout.addWidget(self.tree_widget)

        # Connessioni
        btn_select_A.clicked.connect(lambda: self.select_folder('A'))
        btn_select_B.clicked.connect(lambda: self.select_folder('B'))
        btn_load.clicked.connect(self.load_initial_structure)
        self.tree_widget.itemDoubleClicked.connect(self.handle_item_double_click)
        self.tree_widget.itemExpanded.connect(self.handle_item_expanded)

    def select_folder(self, root_type):
        """Apre la finestra di dialogo per selezionare la cartella."""
        directory = QFileDialog.getExistingDirectory(self, f"Seleziona Root {root_type}", self.root_A)
        if directory:
            if root_type == 'A':
                self.root_A = directory
                self.label_A.setText(f"Root A: {os.path.basename(directory)}")
            elif root_type == 'B':
                self.root_B = directory
                self.label_B.setText(f"Root B: {os.path.basename(directory)}")

    # --- Logica di Caricamento ---

    def load_initial_structure(self):
        """Carica le sottocartelle di primo livello di A e ne verifica l'esistenza in B."""
        if not self.root_A or not self.root_B:
            QMessageBox.warning(self, "Attenzione", "Selezionare entrambe le cartelle Root A e B.")
            return

        self.tree_widget.clear()

        try:
            # Filtra solo le directory di primo livello in A
            subdirs_A = [d for d in os.listdir(self.root_A)
                         if os.path.isdir(os.path.join(self.root_A, d))]
        except Exception as e:
            QMessageBox.critical(self, "Errore Lettura", f"Impossibile leggere Root A: {e}")
            return

        # Lista completa dei contenuti in B per verifica rapida
        contents_B = set(os.listdir(self.root_B))

        for subdir_name in subdirs_A:
            full_path_A = os.path.join(self.root_A, subdir_name)
            full_path_B = os.path.join(self.root_B, subdir_name)

            item = QTreeWidgetItem(self.tree_widget, [subdir_name, "", full_path_A])
            # Data(Ruolo, Valore) - memorizziamo i percorsi e lo stato nel ruolo 0 (Testo)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, full_path_A)  # Path A
            item.setData(0, Qt.ItemDataRole.UserRole + 2, full_path_B)  # Path B previsto

            #self._check_and_style_item(item, full_path_B, contents_B)
            self._check_and_style_item(item, full_path_B)

    def _check_and_style_item(self, item, path_B, check_status=None):
        """Verifica l'esistenza dell'elemento e applica l'icona colorata in base allo stato."""
        name = item.text(0)

        # Stato 'missing' implica che non esiste NESSUNA controparte
        is_missing = item.data(0, Qt.ItemDataRole.UserRole + 3) == "missing"

        # Se lo stato è già 'missing' (cioè la cartella B non esiste)
        if is_missing:
            # 🔴 Cartella NON corrisponde o non esiste affatto (Rosso)
            item.setIcon(0, self.icon_red)
            item.setText(1, "Mancante")
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator)
            return

        # Pre-analisi della sottocartella B per stabilire lo stato
        if check_status is None:
            # Calcola lo stato solo se è una cartella navigabile (non un nodo MP3)
            path_A = item.data(0, Qt.ItemDataRole.UserRole + 1)
            check_status = self.check_directory_status(path_A, path_B)

        if check_status == 'full_match':
            # 🟢 Cartella e contenuto corrispondono completamente (Verde)
            item.setIcon(0, self.icon_green)
            item.setText(1, "Presente")
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
            item.setData(0, Qt.ItemDataRole.UserRole + 3, "exists")

        elif check_status == 'partial_match':
            # 🟡 Contenuto parziale o differenze (Giallo/Arancione)
            item.setIcon(0, self.icon_yellow)
            item.setText(1, "Differenze Parziali")
            # *** AGGIUNGI O VERIFICA QUESTO: PERMETTE L'ESPANSIONE ***
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
            # *** AGGIUNGI O VERIFICA QUESTO: NUOVO STATO SALVATO ***
            item.setData(0, Qt.ItemDataRole.UserRole + 3, "partial")

        elif check_status == 'missing_all':
            # 🔴 Contenuto completamente mancante (Rosso)
            item.setIcon(0, self.icon_red)
            item.setText(1, "Contenuto Mancante")
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator)
            item.setData(0, Qt.ItemDataRole.UserRole + 3, "missing")
        # Rimuovi lo sfondo per tutti gli stati
        item.setBackground(0, QBrush(Qt.GlobalColor.transparent))

    def check_directory_status(self, path_A, path_B):
        """
        Controlla lo stato di sincronizzazione del contenuto di una cartella.
        Ritorna: 'full_match', 'partial_match', o 'missing_all'.
        """
        if not os.path.exists(path_B) or not os.path.isdir(path_B):
            return 'missing_all'  # La cartella B non esiste (stato Rosso attuale)

        # Se la cartella B esiste, analizziamo il contenuto
        has_missing = False
        has_present = False

        try:
            # Iteriamo sugli elementi di A
            contents_A = os.listdir(path_A)

            # Se la cartella A è vuota, consideriamo piena corrispondenza
            if not contents_A:
                return 'full_match'

            # Controlla l'esistenza di ogni elemento di A in B
            for name in contents_A:
                item_path_A = os.path.join(path_A, name)
                item_path_B = os.path.join(path_B, name)

                if os.path.exists(item_path_B):
                    has_present = True
                else:
                    has_missing = True

        except Exception:
            # Gestione errori di lettura, consideriamo parziale per cautela
            return 'partial_match'

        if has_missing and has_present:
            return 'partial_match'  # Alcuni ci sono, altri no (stato Giallo/Arancione)
        elif has_present and not has_missing:
            return 'full_match'  # Tutti gli elementi di A esistono in B (stato Verde)
        elif has_missing and not has_present:
            # Questo caso si verifica solo se os.listdir(path_A) non è vuoto
            # E se nessun elemento di A esiste in B (cioè B esiste ma è vuota o ha nomi diversi)
            return 'missing_all'

        # Fallback sicuro, se arriviamo qui e B esisteva, è una piena corrispondenza
        return 'full_match'

    # --- Interazione Utente (Click) ---

    def handle_item_double_click(self, item, column):
        """Gestisce il doppio click sull'elemento dell'albero."""
        state = item.data(0, Qt.ItemDataRole.UserRole + 3)
        path_A = item.data(0, Qt.ItemDataRole.UserRole + 1)
        path_B = item.data(0, Qt.ItemDataRole.UserRole + 2)

        if state == "missing":
            # Cartella Rossa: Offre la copia
            self.prompt_copy_folder(item)
        elif state == "exists":
            # Cartella Verde: Espandi o Collassa
            if not item.isExpanded():
                self.load_sub_structure(item, path_A, path_B)
                item.setExpanded(True)
            else:
                item.setExpanded(False)

    def handle_item_expanded(self, item):
        """Carica la struttura interna solo quando un elemento è espanso dall'utente (solo per il verde)."""
        state = item.data(0, Qt.ItemDataRole.UserRole + 3)

        # Verifichiamo lo stato, e che i figli non siano già stati caricati.
        # La condizione item.childCount() == 0 è fondamentale per evitare ricaricamenti inutili.
        if (state == "exists" or state == "partial") and item.childCount() == 0:
            path_A = item.data(0, Qt.ItemDataRole.UserRole + 1)
            path_B = item.data(0, Qt.ItemDataRole.UserRole + 2)

            # Chiama la logica di caricamento (che è la stessa che avevi prima)
            self.load_sub_structure(item, path_A, path_B)

    def load_sub_structure(self, parent_item, path_A, path_B):
        """Carica i contenuti del livello successivo e avvia la verifica MP3 se necessario."""
        parent_item.takeChildren()  # Rimuove i figli precedenti per ricaricare

        if not os.path.isdir(path_A): return

        sub_items_A = os.listdir(path_A)

        # 1. Check MP3 Level
        # Se tutti gli elementi sono file (e almeno uno è MP3) O sono sottocartelle
        is_mp3_level_candidate = all(os.path.isdir(os.path.join(path_A, d)) or d.lower().endswith('.mp3')
                                     for d in sub_items_A)

        if is_mp3_level_candidate and any(d.lower().endswith('.mp3') for d in sub_items_A):
            # Siamo in una cartella che contiene file MP3: avvia la verifica MD5
            self.check_mp3_md5(parent_item, path_A, path_B)
            return

        # 2. Iterazione standard delle sottocartelle
        contents_B = set(os.listdir(path_B)) if os.path.isdir(path_B) else set()

        for name in sub_items_A:
            full_path_A = os.path.join(path_A, name)
            full_path_B = os.path.join(path_B, name)

            if os.path.isdir(full_path_A):  # Iteriamo solo sulle sottocartelle
                child_item = QTreeWidgetItem(parent_item, [name, "", full_path_A])
                child_item.setData(0, Qt.ItemDataRole.UserRole + 1, full_path_A)
                child_item.setData(0, Qt.ItemDataRole.UserRole + 2, full_path_B)

                #self._check_and_style_item(child_item, full_path_B, contents_B)
                self._check_and_style_item(child_item, full_path_B)

    # --- Copia (Cartelle Rosse) ---

    def prompt_copy_folder(self, item):
        """Chiede conferma e avvia la copia con Progress Bar."""
        source_path = item.data(0, Qt.ItemDataRole.UserRole + 1)
        target_path = item.data(0, Qt.ItemDataRole.UserRole + 2)

        size_needed = get_folder_size(source_path)

        if not check_disk_space(os.path.dirname(target_path) or self.root_B, size_needed):
            QMessageBox.critical(self, "Errore di Spazio",
                                 f"Spazio insufficiente su disco ({size_needed / 1024 ** 3:.2f} GB necessari).")
            return

        reply = QMessageBox.question(self, 'Conferma Copia',
                                     f"Copiare la cartella **{item.text(0)}** ({size_needed / 1024 ** 2:.2f} MB)?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            # --- Avvio del Thread di Copia ---
            self.current_item_to_copy = item  # Memorizza l'elemento per l'aggiornamento finale

            # 1. Inizializza il Worker
            self.copy_worker = CopyWorker(source_path, target_path, size_needed)

            # 2. Connetti i segnali
            self.copy_worker.progress_updated.connect(self.update_progress_bar)
            self.copy_worker.finished.connect(self.copy_finished)

            # 3. Visualizza la Progress Dialog
            self.progress_dialog = QProgressDialog(
                f"Copia in corso: {item.text(0)}",
                "Annulla", 0, size_needed, self)
            self.progress_dialog.setWindowTitle("Copia File")
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress_dialog.show()

            # 4. Avvia il thread
            self.copy_worker.start()
    # --- Verifica MP3 (MD5) ---

    def check_mp3_md5(self, parent_item, path_A, path_B):
        """Esegue il controllo MD5 tra i file MP3 presenti in A e B."""
        mp3_files_A = {f: os.path.join(path_A, f) for f in os.listdir(path_A)
                       if f.lower().endswith('.mp3')}
        mp3_files_B = {f: os.path.join(path_B, f) for f in os.listdir(path_B)
                       if f.lower().endswith('.mp3')}

        # Mostra i risultati

        parent_item.takeChildren()  # Rimuovi elementi precedenti

        for filename, path_A in mp3_files_A.items():
            item = QTreeWidgetItem(parent_item, [filename])

            # 1. File mancante in B
            if filename not in mp3_files_B:
                item.setBackground(0, QBrush(QColor("red")))
                item.setText(1, "Mancante")
                continue

            path_B = mp3_files_B[filename]

            # 2. File presente, verifica MD5
            md5_A = calculate_md5(path_A)
            md5_B = calculate_md5(path_B)

            if md5_A == md5_B:
                # 🟢 MD5 Corrisponde
                item.setBackground(0, QBrush(QColor("green")))
                item.setText(1, "OK")
            else:
                # 🟠 MD5 NON Corrisponde (Giallo/Arancione per differenziare da 'Mancante')
                item.setBackground(0, QBrush(QColor("orange")))
                item.setText(1, "MD5 Diverso")


    def update_progress_bar(self, bytes_copied, total_size):
        """Aggiorna la progress bar dal segnale del worker."""
        if self.progress_dialog:
            self.progress_dialog.setValue(bytes_copied)
            # Puoi anche aggiornare il testo descrittivo
            self.progress_dialog.setLabelText(
                f"Copiati {bytes_copied / 1024 ** 2:.2f} MB di {total_size / 1024 ** 2:.2f} MB")

    def copy_finished(self, success, error_message):
        """Gestisce il risultato finale dell'operazione di copia."""
        # Chiudi la dialog
        if self.progress_dialog:
            self.progress_dialog.close()

        item = self.current_item_to_copy  # Recupera l'elemento copiato
        target_path = item.data(0, Qt.ItemDataRole.UserRole + 2)

        if success:
            item.takeChildren()

            # 2. Imposta lo stato iniziale (la cartella B ORA esiste)
            item.setData(0, Qt.ItemDataRole.UserRole + 3, "exists")

            # 3. Forza la riscrittura dello stile (L'icona diventerà Verde o Gialla)
            # Chiamiamo _check_and_style_item senza check_status, forzando l'analisi
            self._check_and_style_item(item, target_path)

            QMessageBox.information(self, "Copia Completata", f"Cartella **{item.text(0)}** copiata con successo.")
        else:
            QMessageBox.critical(self, "Errore di Copia", f"Errore durante la copia: {error_message}")

        # Pulisci i riferimenti al thread
        self.copy_worker = None
        self.current_item_to_copy = None