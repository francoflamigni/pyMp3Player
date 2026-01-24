import os
import shutil
import hashlib
import psutil
from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget, QProgressDialog,
                             QTreeWidgetItem, QLabel, QMessageBox, QFileDialog, QDialog, QStyledItemDelegate, QGroupBox,
                             QLineEdit)
from PyQt6.QtGui import QPixmap, QIcon, QColor, QBrush, QPainter, QFontMetrics, QAction
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRect

from pyMyLib.utils import get_resource_file

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
    if not path or not os.path.exists(path):
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

# --- Classe Delegate per colonna 1 ---
class TextBackgroundDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Mappa dei colori per gli stati
        self.state_colors = {
            "Mancante": QColor("#ffcccc"),  # Rosso tenue
            "missing": QColor("#ffcccc"),
            "Differenze Parziali": QColor("yellow"),
            "partial": QColor("orange"),
            "exists": QColor("lightgreen"),
        }

    def paint(self, painter: QPainter, option, index):
        # 1. Non modificare le colonne diverse dalla colonna "Stato" (Indice 1)
        if index.column() != 0:
            super().paint(painter, option, index)
            return

        qq = index.data(Qt.ItemDataRole.UserRole + 4)

        # CONDIZIONE: Se l'elemento HA figli, usa il disegno standard.
        if qq is None:
            super().paint(painter, option, index)
            return

        cq = index.data(Qt.ItemDataRole.UserRole + 3)

        # 2. Ottieni il testo e il colore
        text = index.data(Qt.ItemDataRole.DisplayRole)
        color = self.state_colors.get(cq, Qt.GlobalColor.white)


        # 3. Disegna il background standard della cella (bianco o quello di sistema)
        # Questo è essenziale per non sovrapporsi al colore di selezione
        style = option.widget.style()
        style.drawControl(style.ControlElement.CE_ItemViewItem, option, painter, option.widget)

        if color == Qt.GlobalColor.white:
            return

        # 4. Calcola la dimensione del testo
        metrics = QFontMetrics(painter.font())

        # L'area usata dal testo senza margini (circa)
        text_width = metrics.horizontalAdvance(text)
        text_height = metrics.height()

        # 5. Definisci il rettangolo di sfondo del testo
        # Center the text background horizontally and vertically in the cell rect

        # Aggiungi un piccolo margine attorno al testo
        padding = 3
        bg_width = text_width + 2 * padding
        bg_height = text_height + 2 * padding

        # Calcola la posizione x centrale e y centrale nella cella
        x_center = option.rect.x() #+ (option.rect.width() - bg_width) / 2
        y_center = option.rect.y() #+ (option.rect.height() - bg_height) / 2

        wd = min(bg_width, option.rect.width())

        background_rect = QRect(int(x_center), int(y_center), int(wd), int(bg_height))

        # 6. Disegna il rettangolo colorato
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.GlobalColor.transparent)  # Rimuovi il bordo
        painter.drawRect(background_rect)

        # 7. Disegna il testo
        # Devi usare l'area del background per centrare il testo correttamente
        #painter.setPen(option.palette.color(Qt.GlobalColor.black) ) # Imposta il colore del testo (es. nero)
        painter.setPen(Qt.GlobalColor.black)

        text_rect = background_rect.adjusted(padding, padding, -padding, -padding)  # Rimuove il padding dal bg rect
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft, text)

# --- Classe Principale dell'Applicazione ---

class SyncApp(QDialog):
    def __init__(self, parent, folder=None):
        super().__init__(parent)
        self.setWindowTitle("Sincronizza cartelle")
        self.setGeometry(100, 100, 900, 600)
        self.setWindowIcon(QIcon(get_resource_file(__file__, 'icone', 'folders_sync.png')))

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
        main_layout = QVBoxLayout(self)

        folders_groupBox = QGroupBox(self)
        folders_groupBox.setTitle("Cartelle da sincronizzare")
        # Selezione Cartelle
        path_layout = QHBoxLayout()
        folders_groupBox.setLayout(path_layout)
        self.label_A = QLineEdit() #QLabel("Riferimento: Non selezionata")
        self.label_A.setReadOnly(True)
        self.label_A.setMinimumWidth(400)
        if self.root_A:
            elide_path_center(self.label_A, self.root_A)
        else:
            self.label_A.setPlaceholderText("Riferimento: Non selezionato")
        icone_browse = QIcon(get_resource_file(__file__, 'icone', 'folder_open.png'))
        azione_browse1 = QAction(icone_browse, "browse", self)
        azione_browse1.triggered.connect(lambda: self.select_folder('A'))
        self.label_A.addAction(
            azione_browse1,
            QLineEdit.ActionPosition.LeadingPosition
        )

        self.label_B = QLineEdit() #QLabel("Destinazione: Non selezionata")
        self.label_B.setReadOnly(True)
        self.label_B.setMinimumWidth(400)
        self.label_B.setPlaceholderText("Destinazione: Non selezionata")
        azione_browse2 = QAction(icone_browse, "browse", self)
        azione_browse2.triggered.connect(lambda: self.select_folder('B'))
        self.label_B.addAction(
            azione_browse2,
            QLineEdit.ActionPosition.LeadingPosition
        )

        #btn_select_A = QPushButton("...")
        #btn_select_A.setMaximumWidth(40)
        #btn_select_B = QPushButton("...")
        #btn_select_B.setMaximumWidth(40)
        btn_load = QPushButton("Aggiorna")

        path_layout.addWidget(self.label_A)
        #path_layout.addWidget(btn_select_A)
        path_layout.addSpacing(20)
        path_layout.addWidget(self.label_B)
        #path_layout.addWidget(btn_select_B)
        path_layout.addStretch()
        path_layout.addWidget(btn_load)
        main_layout.addWidget(folders_groupBox)

        # Tree Widget
        self.tree_widget = QTreeWidget()
        self.tree_widget.setColumnCount(3)
        self.tree_widget.setHeaderLabels(["Nome", "Stato", "Percorso"])
        self.tree_widget.setColumnWidth(0, 400)
        self.tree_widget.setColumnWidth(1, 60)
        self.tree_widget.setColumnWidth(2, 120)
        main_layout.addWidget(self.tree_widget)

        self.state_delegate = TextBackgroundDelegate(self.tree_widget)
        # Applica il delegate alla colonna 1 (Stato)
        self.tree_widget.setItemDelegateForColumn(0, self.state_delegate)

        # Connessioni
        #btn_select_A.clicked.connect(lambda: self.select_folder('A'))
        #btn_select_B.clicked.connect(lambda: self.select_folder('B'))
        btn_load.clicked.connect(self.load_initial_structure)
        self.tree_widget.itemDoubleClicked.connect(self.handle_item_double_click)
        self.tree_widget.itemExpanded.connect(self.handle_item_expanded)

    def select_folder(self, root_type):
        """Apre la finestra di dialogo per selezionare la cartella."""
        directory = QFileDialog.getExistingDirectory(self, f"Seleziona Root {root_type}", self.root_A)
        if directory:
            if root_type == 'A':
                self.root_A = directory
                elide_path_center(self.label_A, f"Riferimento: {directory}")
                #self.label_A.setText(f"Riferimento: {directory}")
            elif root_type == 'B':
                self.root_B = directory
                elide_path_center(self.label_B, f"Riferimento: {directory}")
                #self.label_B.setText(f"Destinazione: {directory}")
            if self.root_A and self.root_B:
                self.load_initial_structure()


    # --- Logica di Caricamento ---

    def load_initial_structure(self):
        """Carica le sottocartelle di primo livello di A e ne verifica l'esistenza in B."""
        if not self.root_A or not self.root_B:
            QMessageBox.warning(self, "Attenzione", "Selezionare entrambe le cartelle.")
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

            # Verifica Corrispondenza in B
            if subdir_name in contents_B and os.path.isdir(full_path_B):
                # ... (Stato iniziale: exist)
                item.setData(0, Qt.ItemDataRole.UserRole + 3, "exists")
            else:
                # 🔴 Cartella NON corrisponde (Rosso)
                item.setData(0, Qt.ItemDataRole.UserRole + 3, "missing")  # ORA È QUI

            #self._check_and_style_item(item, full_path_B, contents_B)
            self._check_and_style_item(item, full_path_B)

    def _check_and_style_item(self, item, path_B, check_status=None):
        """Verifica l'esistenza dell'elemento e applica l'icona colorata in base allo stato."""
        current_state = item.data(0, Qt.ItemDataRole.UserRole + 3)

        is_missing_state = (current_state == "missing" or current_state == "missing_root" or
                            check_status == 'missing_all')
        if is_missing_state and not os.path.isdir(path_B):
            # 🔴 Cartella NON corrisponde o non esiste affatto (Rosso)
            item.setIcon(0, self.icon_red)
            item.setText(1, "Mancante")
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
            item.setData(0, Qt.ItemDataRole.UserRole + 3, "missing")
            item.setBackground(0, QBrush(Qt.GlobalColor.transparent))
            return

        # Pre-analisi della sottocartella B per stabilire lo stato
        if check_status is None and current_state != "missing":
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
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
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

        if path_A is None:
            # si tartta di un file
            p = item.parent()
            state = p.data(0, Qt.ItemDataRole.UserRole + 3)
            path_A = p.data(0, Qt.ItemDataRole.UserRole + 1)
            path_B = p.data(0, Qt.ItemDataRole.UserRole + 2)
            file = item.text(0)
            src_file = os.path.join(path_A, file)
            dst_file = os.path.join(path_B, file)
            if not os.path.exists(path_B):
                os.makedirs(path_B)
            ret = shutil.copy2(src_file, dst_file)
            di = save_expansion_state(self.tree_widget)
            self.load_initial_structure()
            restore_expansion_state(self.tree_widget, di)
            return

        if state == "missing" or state == 'partial':
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
        if (state == "exists" or state == "partial" or state == "missing") and item.childCount() == 0:
            path_A = item.data(0, Qt.ItemDataRole.UserRole + 1)
            path_B = item.data(0, Qt.ItemDataRole.UserRole + 2)

            # Chiama la logica di caricamento (che è la stessa che avevi prima)
            self.load_sub_structure(item, path_A, path_B)

    def load_sub_structure(self, parent_item, path_A, path_B):
        """Carica i contenuti del livello successivo e avvia la verifica MP3 se necessario."""
        parent_item.takeChildren()  # Rimuove i figli precedenti per ricaricare

        if not path_A or not os.path.isdir(path_A):
            return

        sub_items_A = os.listdir(path_A)

        # 1. Check MP3 Level
        # Se tutti gli elementi sono file (e almeno uno è MP3) O sono sottocartelle
        is_mp3_level_candidate = any(os.path.isdir(os.path.join(path_A, d)) or d.lower().endswith('.mp3')
                                     for d in sub_items_A)

        if is_mp3_level_candidate and any(d.lower().endswith('.mp3') for d in sub_items_A):
            # Siamo in una cartella che contiene file MP3: avvia la verifica MD5
            self.check_mp3_md5(parent_item, path_A, path_B)
            return

        # 2. Iterazione standard delle sottocartelle
        contents_B = set(os.listdir(path_B)) if os.path.isdir(path_B) else set()

        parent_state = parent_item.data(0, Qt.ItemDataRole.UserRole + 3)
        for name in sub_items_A:
            full_path_A = os.path.join(path_A, name)
            full_path_B = os.path.join(path_B, name)

            if os.path.isdir(full_path_A):  # Iteriamo solo sulle sottocartelle
                child_item = QTreeWidgetItem(parent_item, [name, "", full_path_A])
                child_item.setData(0, Qt.ItemDataRole.UserRole + 1, full_path_A)
                child_item.setData(0, Qt.ItemDataRole.UserRole + 2, full_path_B)

                if parent_state == "missing":
                    # Imposta inizialmente il figlio come 'missing' e chiama lo style
                    child_item.setData(0, Qt.ItemDataRole.UserRole + 3, "missing")
                    self._check_and_style_item(child_item, full_path_B)
                else:
                    # Altrimenti, calcola lo stato (Verde/Giallo/Rosso)
                    self._check_and_style_item(child_item, full_path_B)

                #self._check_and_style_item(child_item, full_path_B, contents_B)
                #self._check_and_style_item(child_item, full_path_B)

    # --- Copia (Cartelle Rosse) ---
    def prompt_copy_folder(self, item):
        """Chiede conferma e avvia la copia con Progress Bar."""
        source_path = item.data(0, Qt.ItemDataRole.UserRole + 1)
        target_path = item.data(0, Qt.ItemDataRole.UserRole + 2)

        size_needed = get_folder_size(source_path)

        basedir = os.path.dirname(target_path)
        if  os.path.exists(basedir) is False:
            os.makedirs(basedir)


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

        mp3_files_B = {}
        try:
            mp3_files_B = {f: os.path.join(path_B, f) for f in os.listdir(path_B)
                           if f.lower().endswith('.mp3')}
        except:
            pass

        # Mostra i risultati

        parent_item.takeChildren()  # Rimuovi elementi precedenti

        for filename, path_A in mp3_files_A.items():
            item = QTreeWidgetItem(parent_item, [filename])
            item.setData(0, Qt.ItemDataRole.UserRole + 4, "leaf")

            # 1. File mancante in B
            if filename not in mp3_files_B:
                item.setBackground(0, QBrush(QColor("red")))
                item.setForeground(0, QBrush(QColor("white")))
                item.setData(0, Qt.ItemDataRole.UserRole + 3, "missing")
                item.setText(1, "Mancante")
                continue

            path_B = mp3_files_B[filename]

            # 2. File presente, verifica MD5
            md5_A = calculate_md5(path_A)
            md5_B = calculate_md5(path_B)

            if md5_A == md5_B:
                # 🟢 MD5 Corrisponde
                item.setBackground(0, QBrush(QColor("green")))
                item.setForeground(0, QBrush(QColor("white")))
                item.setData(0, Qt.ItemDataRole.UserRole + 3, "exists")
                item.setText(1, "OK")
            else:
                # 🟠 MD5 NON Corrisponde (Giallo/Arancione per differenziare da 'Mancante')
                item.setBackground(0, QBrush(QColor("orange")))
                item.setForeground(0, QBrush(QColor("white")))
                item.setData(0, Qt.ItemDataRole.UserRole + 3, "partial")
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
        src_path = item.data(0, Qt.ItemDataRole.UserRole + 1)

        if success:
            item.takeChildren()

            # 2. Imposta lo stato iniziale (la cartella B ORA esiste)
            item.setData(0, Qt.ItemDataRole.UserRole + 3, "exists")

            # 3. Forza la riscrittura dello stile (L'icona diventerà Verde o Gialla)
            # Chiamiamo _check_and_style_item senza check_status, forzando l'analisi
            self._check_and_style_item(item, target_path)
            self.load_sub_structure(item, src_path, target_path)

            QMessageBox.information(self, "Copia Completata", f"Cartella **{item.text(0)}** copiata con successo.")
        else:
            QMessageBox.critical(self, "Errore di Copia", f"Errore durante la copia: {error_message}")


        # Pulisci i riferimenti al thread
        self.copy_worker = None
        self.current_item_to_copy = None


from typing import List, Dict


def save_expansion_state(tree_widget: QTreeWidget) -> Dict[str, bool]:
    """
    Analizza il QTreeWidget e restituisce un dizionario
    {percorso_unico_nodo: True/False (aperto/chiuso)}.
    """
    state_map: Dict[str, bool] = {}

    def traverse_and_save(parent_item: QTreeWidgetItem | QTreeWidget, current_path: List[str]):
        """Funzione ricorsiva per attraversare l'albero."""

        # Iterazione su tutti gli elementi di primo livello (se parent_item è il QTreeWidget)
        # o sui figli dell'elemento (se parent_item è un QTreeWidgetItem)

        if isinstance(parent_item, QTreeWidget):
            item_count = parent_item.topLevelItemCount()
            get_item = parent_item.topLevelItem
        else:
            item_count = parent_item.childCount()
            get_item = parent_item.child

        for i in range(item_count):
            item = get_item(i)

            # Utilizza il testo della colonna 0 come parte del percorso
            item_name = item.text(0)

            # Costruisce la chiave unica (es: 'Root A/Subfolder 1/Subsub B')
            full_path_key = "/".join(current_path + [item_name])

            # Registra lo stato
            state_map[full_path_key] = item.isExpanded()

            # Se ha figli, continua la ricorsione
            if item.childCount() > 0:
                # Per garantire che la funzione di caricamento dinamico (lazy loading)
                # venga triggerata correttamente, un nodo deve essere espanso PRIMA
                # di poterne registrare lo stato dei figli, sebbene in questo contesto
                # registriamo lo stato attuale.

                # Se il nodo è espanso, carichiamo lo stato dei suoi figli.
                if item.isExpanded():
                    traverse_and_save(item, current_path + [item_name])

    # Avvia la traversata dal QTreeWidget stesso (root)
    traverse_and_save(tree_widget, [])
    return state_map


def restore_expansion_state(tree_widget: QTreeWidget, state_map: Dict[str, bool]):
    """
    Ripristina lo stato di espansione dei nodi del QTreeWidget in base a state_map.
    """

    def traverse_and_restore(parent_item: QTreeWidgetItem | QTreeWidget, current_path: List[str]):
        """Funzione ricorsiva per attraversare e ripristinare."""

        if isinstance(parent_item, QTreeWidget):
            item_count = parent_item.topLevelItemCount()
            get_item = parent_item.topLevelItem
        else:
            item_count = parent_item.childCount()
            get_item = parent_item.child

        for i in range(item_count):
            item = get_item(i)
            item_name = item.text(0)

            # Ricostruisce la chiave e cerca lo stato
            full_path_key = "/".join(current_path + [item_name])

            if full_path_key in state_map:
                should_be_expanded = state_map[full_path_key]

                # Applica lo stato di espansione
                item.setExpanded(should_be_expanded)

                # Se il nodo è stato aperto e ha figli, continuiamo la ricorsione.
                # Questo è cruciale per la tua applicazione di sync, dove l'espansione
                # di solito attiva il caricamento dinamico (`load_sub_structure`).
                if should_be_expanded and item.childCount() > 0:
                    traverse_and_restore(item, current_path + [item_name])

                # NOTA: Se il tuo sistema di sync usa il lazy loading (come nel codice fornito),
                # l'istruzione item.setExpanded(True) dovrebbe triggerare il segnale itemExpanded,
                # che a sua volta carica i figli (se non già caricati).

    # Avvia il ripristino
    traverse_and_restore(tree_widget, [])


def elide_path_center(label: QLabel, path: str) -> str:
    """
    Applica l'elisione centrale al path se è troppo lungo per la QLabel.

    Args:
        label: L'oggetto QLabel di riferimento (per dimensioni e font).
        path: Il percorso completo del file o della cartella.

    Returns:
        Il percorso eliso o il percorso originale.
    """
    # 1. Ottieni la larghezza massima disponibile per il testo
    max_width = label.width() - 5  # Sottrae un piccolo margine di sicurezza (es. 5 pixel)

    # 2. Ottieni le metriche del font (necessarie per misurare il testo)
    font_metrics = QFontMetrics(label.font())

    # 3. Verifica se il path intero entra
    if font_metrics.horizontalAdvance(path) <= max_width:
        label.setText(path)  # Ritorna il path originale se è abbastanza corto

    # 4. Inizia l'elisione (se non entra)

    # Simboli di elisione e separator
    ellipses = "..."
    separator = os.path.sep  # Usa il separatore del sistema (es. '/' o '\')

    # Calcola lo spazio preso dai puntini
    ellipses_width = font_metrics.horizontalAdvance(ellipses)

    # Spazio rimanente per il testo
    available_text_width = max_width - ellipses_width

    # 5. Iterazione per trovare la lunghezza ottimale

    # Dividi il path in componenti (cartelle/nome file)
    parts = path.split(separator)

    start_parts = []
    end_parts = []

    current_width = 0

    # Aggiungi le parti dall'inizio finché non si supera la metà dello spazio disponibile
    for part in parts:
        part_with_sep = part + separator
        part_width = font_metrics.horizontalAdvance(part_with_sep)

        # Se superiamo la metà dello spazio disponibile, smettiamo di aggiungere all'inizio
        if current_width + part_width > available_text_width / 2 and len(start_parts) > 0:
            break

        start_parts.append(part)
        current_width += part_width

    # Rimuovi le parti già usate dall'inizio
    remaining_parts = parts[len(start_parts):]
    current_width = font_metrics.horizontalAdvance(separator.join(start_parts) + separator)

    # Aggiungi le parti dalla fine fino a quando non riempiamo lo spazio
    for part in reversed(remaining_parts):
        part_with_sep = separator + part
        part_width = font_metrics.horizontalAdvance(part_with_sep)

        # Controlla la larghezza totale
        if current_width + part_width + ellipses_width > max_width:
            break

        end_parts.insert(0, part)
        current_width += part_width

    # 6. Ricomponi il path eliso

    # Caso in cui il path è troppo corto per essere diviso in modo significativo
    if not end_parts and len(start_parts) < len(parts):
        # Se non siamo riusciti ad aggiungere nulla alla fine, forziamo l'elisione a destra (meno elegante)
        return font_metrics.elidedText(path, Qt.TextElideMode.ElideRight, max_width)

    start_text = separator.join(start_parts)
    end_text = separator.join(end_parts)

    if start_text and end_text:
        label.setText(f"{start_text}{separator}{ellipses}{separator}{end_text}")
        #return f"{start_text}{separator}{ellipses}{separator}{end_text}"
    else:
        # Questo caso dovrebbe catturare path molto lunghi, lo trattiamo con elisione semplice se il centro non funziona
        label.setText(font_metrics.elidedText(path, Qt.TextElideMode.ElideRight, max_width))
        #return font_metrics.elidedText(path, Qt.TextElideMode.ElideRight, max_width)