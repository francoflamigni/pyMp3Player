from profiler import checkpoint
import io
import sys
import os
import base64
from PyQt6.QtCore import Qt, QRunnable, QObject, QPoint, pyqtSignal, QTimer, QEvent
from PyQt6.QtWidgets import QAbstractItemView, QTableWidget, QMenu, QApplication
from enum import Enum

def close_splash():
    import importlib
    if '_PYI_SPLASH_IPC' in os.environ and importlib.util.find_spec("pyi_splash"):
        import pyi_splash
        #pyi_splash.update_text('UI Loaded ...')
        pyi_splash.close()
        #log.info('Splash screen closed.')

def qpixmap_to_bytes(pixmap):
    from PIL import ImageQt
    """Converte un QPixmap in dati binari."""
    # Converte QPixmap in PIL Image
    qimage = pixmap.toImage()
    pil_image = ImageQt.fromqimage(qimage)

    # Salva in un buffer
    buffer = io.BytesIO()
    pil_image.save(buffer, format='PNG')
    return buffer.getvalue()

def resize_image_data(image_data, target_size=(400, 400), quality=85):
    from PIL import Image
    """
    Ridimensiona i dati dell'immagine mantenendo le proporzioni.

    Args:
        image_data: Dati binari dell'immagine
        target_size: Tuple (width, height) della dimensione target
        quality: Qualità JPEG (1-100)

    Returns:
        bytes: Dati dell'immagine ridimensionata in formato JPEG
    """
    try:
        # Carica l'immagine dai dati binari
        image = Image.open(io.BytesIO(image_data))

        # Converte in RGB se necessario (per PNG con trasparenza, etc.)
        if image.mode in ('RGBA', 'LA', 'P'):
            # Crea uno sfondo bianco per le immagini con trasparenza
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')

        # Calcola le nuove dimensioni mantenendo le proporzioni
        original_width, original_height = image.size
        target_width, target_height = target_size

        # Calcola il rapporto per mantenere le proporzioni
        ratio = min(target_width / original_width, target_height / original_height)

        new_width = int(original_width * ratio)
        new_height = int(original_height * ratio)

        # Ridimensiona l'immagine con un filtro di alta qualità
        resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Salva in un buffer come JPEG
        output_buffer = io.BytesIO()
        resized_image.save(output_buffer, format='JPEG', quality=quality, optimize=True)

        return output_buffer.getvalue()

    except Exception as e:
        raise Exception(f"Errore nel ridimensionamento dell'immagine: {e}")

def get_windows_flag():
    CREATE_NO_WINDOW = 0x08000000 if sys.platform == 'win32' else 0
    return CREATE_NO_WINDOW

def textwrap(txt, width=50):
    v = txt.split(' ')
    stri = ''
    l0 = 0
    for t in v:
        t1 = t.split('\n')
        if len(t1) == 1:
            stri += t + ' '
            if len(stri) > width + l0:
                stri += '\n'
                l0 = len(stri)
        else:
            first = True
            for t2 in t1:
                if first is False:
                    stri += '\n'
                else:
                    first = False
                stri += t2
            stri += ' '
            l0 = len(stri)

    return stri


# --- Modifica i segnali per passare l'HTML del tooltip ---
class WorkerSignals(QObject):
    """Definisce i segnali disponibili dal thread worker."""
    # Ora emettiamo la stringa HTML pronta per il tooltip
    result = pyqtSignal(str, QPoint)  # (HTML del tooltip, Posizione del cursore)
    finished = pyqtSignal()
    error = pyqtSignal(str)


# --- Worker Modificato ---
class WikipediaWorker(QRunnable):
    def __init__(self, artist_name, cursor_pos, lang="it"):
        super().__init__()
        self.artist_name = artist_name
        self.cursor_pos = cursor_pos
        self.signals = WorkerSignals()
        self.setAutoDelete(True)
        self.lang = lang

        self.USER_AGENT = "Euterpe/1.0 (contatto: tuaemail@esempio.it)"

    def run(self):
        import wikipedia
        wikipedia.set_lang(self.lang)

        try:
            # 1. OTTIENI URL IMMAGINE E RIASSUNTO (Codice precedente)
            #summary = wikipedia.summary(self.artist_name, sentences=5)
            #formatted_summary = textwrap(summary, width=50).replace("\n", "<br>")
            #self.signals.result.emit(formatted_summary, self.cursor_pos)

            tooltip_html = f"<b>{self.artist_name}</b><br><hr>"

            image_url = self._get_image_url()  # Metodo privato per l'URL immagine
            # 2. SCARICA E CONVERTI L'IMMAGINE (NUOVO)
            if image_url:
                base64_img_tag = self._get_base64_image_tag(image_url)
                if base64_img_tag:
                    tooltip_html += base64_img_tag + "<br>"
                    self.signals.result.emit(tooltip_html, self.cursor_pos)

            # 3. AGGIUNGI RIASSUNTO E FORMATTAZIONE
            summary = wikipedia.summary(self.artist_name, sentences=5)
            formatted_summary = textwrap(summary, width=50).replace("\n", "<br>")

            tooltip_html += formatted_summary

            self.signals.result.emit(tooltip_html, self.cursor_pos)

        except Exception as e:
            self.signals.error.emit(f"Errore nella gestione del tooltip: {e}")

        finally:
            self.signals.finished.emit()

    # --- Funzioni di supporto all'interno della classe Worker ---

    def _get_image_url(self):
        import requests
        """Ottiene l'URL dell'immagine da Wikipedia (codice che funziona ora)."""
        # [Codice esatto che ti ho fornito in precedenza per l'URL]
        S = requests.Session()
        S.headers.update({"User-Agent": self.USER_AGENT})

        URL = "https://it.wikipedia.org/w/api.php"
        PARAMS = {
            "action": "query", "format": "json", "prop": "pageimages",
            "titles": self.artist_name, "pithumbsize": 200  # Usa un thumbnail più piccolo
        }

        R = S.get(url=URL, params=PARAMS)
        R.raise_for_status()
        data = R.json()
        pages = data.get("query", {}).get("pages", {})
        page_id = next(iter(pages.keys()), None)

        if page_id and page_id != "-1":
            return pages[page_id].get("thumbnail", {}).get("source")
        return None

    def _get_base64_image_tag(self, url):
        import requests
        #import base64
        """Scarica l'immagine e la converte in un tag <img> Base64."""
        try:
            R = requests.get(url, headers={"User-Agent": self.USER_AGENT}, timeout=5)
            R.raise_for_status()

            # Tipo di immagine (presumiamo JPEG se l'URL non ha estensione)
            content_type = R.headers.get('Content-Type', 'image/jpeg')

            # Codifica il contenuto binario in Base64
            base64_encoded_data = base64.b64encode(R.content).decode('utf-8')

            # Crea il tag <img> con i dati incorporati
            return f'<img src="data:{content_type};base64,{base64_encoded_data}" style="max-width:200px; max-height:200px; display:block; margin:auto;">'

        except requests.exceptions.RequestException as e:
            return None  # Fallimento nel download dell'immagine
        except Exception:
            return None  # Altri errori

def ms_to_string(ms):
    tsecs = ms / 1000
    minutes = tsecs // 60
    secs = tsecs % 60
    return f"{minutes:02}:{secs:02}"

class Select(Enum):
    CK_ALL = 1
    CK_SEL = 2

class ACTableWidget(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Abilita la policy che permette di mostrare il menu contestuale
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Connette il segnale emesso dalla policy a un metodo custom
        self.customContextMenuRequested.connect(self.show_context_menu)

        # (Opzionale) Imposta la selezione di righe intere se lavori con azioni massicce
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.setStyleSheet("""
            QTableWidget::item:selected {
                background-color: #3B82F6; /* Un blu acceso, ad esempio */
                color: white; 
                /* Rimuove il bordo standard di selezione (opzionale) */
                border: 0px; 
            }

            /* Gestisce il focus quando la tabella non è attiva (opzionale) */
            QTableWidget:focus {
                outline: none;
            }

        """)

    def show_context_menu(self, position: QPoint):
        # 1. Crea l'oggetto menu
        context_menu = QMenu(self)

        # 2. Definisci e aggiungi le azioni

        # Esempio 1: Check tutti gli elementi selezionati
        action_check_all = context_menu.addAction("✅ Check Tutti")
        action_check_all.triggered.connect(lambda: self.batch_check(type=Select.CK_ALL, state=Qt.CheckState.Checked))
        action_uncheck_all = context_menu.addAction("❌ Uncheck Tutti")
        action_uncheck_all.triggered.connect(
            lambda: self.batch_check(type=Select.CK_ALL, state=Qt.CheckState.Unchecked))

        action_check_sel = context_menu.addAction("✅ Check Selezionati")
        action_check_sel.triggered.connect(lambda: self.batch_check(type=Select.CK_SEL, state=Qt.CheckState.Checked))

        # Esempio 2: Deseleziona tutti gli elementi selezionati
        action_uncheck_sel = context_menu.addAction("❌ Uncheck Selezionati")
        action_uncheck_sel.triggered.connect(
            lambda: self.batch_check(type=Select.CK_SEL, state=Qt.CheckState.Unchecked))

        # Aggiungi un separatore per raggruppare le azioni
        context_menu.addSeparator()

        context_menu.exec(self.mapToGlobal(position))

    def batch_check(self, type=Select.CK_ALL, state=Qt.CheckState.Checked):
        if type == Select.CK_ALL:
            selected_rows = [i for i in range(self.rowCount())]
        else:
            selected_rows = [index.row() for index in self.selectedIndexes()]
        self.setUpdatesEnabled(False)
        for row in selected_rows:
            item = self.item(row, 0)
            if item is not None and (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                item.setCheckState(state)
        self.setUpdatesEnabled(True)


def detect_cd_drives():
    drives = []
    for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
        drive_path = f"{letter}:\\"
        if os.path.exists(drive_path):
            try:
                # Verifica se è un drive CD
                import win32file
                drive_type = win32file.GetDriveType(drive_path)
                if drive_type == win32file.DRIVE_CDROM:
                    import glob
                    file_trovati = glob.glob(f'{drive_path}*.cda')
                    if file_trovati:
                        drives.append(letter)
            except:
                # Fallback: aggiungi tutti i drive trovati
                drives.append(letter)
    return drives


def eject_cd(drive_letter):
    import ctypes
    import time
    """
    Espelle il CD/DVD usando l'API di Windows (winmm.dll).
    :param drive_letter: La lettera del drive da espellere (es. 'D', 'E').
    """

    # 1. Carica la funzione API di Windows
    # La funzione mciSendString invia comandi stringa al Media Control Interface
    mciSendString = ctypes.windll.winmm.mciSendStringA

    # 2. Definisce il nome alias dell'unità per l'API MCI
    device_alias = f"cd_{drive_letter}"

    # 3. Costruisce e invia i comandi

    # A) Apri/assegna l'unità CD all'alias
    # Comando: "open [drive_letter]: type cdaudio alias [alias]"
    open_command = f"open {drive_letter}: type cdaudio alias {device_alias}"

    # B) Espelli l'unità
    # Comando: "set [alias] door open"
    eject_command = f"set {device_alias} door open"

    # C) Chiudi/rilascia l'unità dall'alias
    # Comando: "close [alias]"
    close_command = f"close {device_alias}"

    # Esecuzione dei comandi
    try:
        # Apri
        mciSendString(open_command.encode('ascii'), None, 0, None)
        time.sleep(0.5)  # Breve pausa

        # Espelli
        error_code = mciSendString(eject_command.encode('ascii'), None, 0, None)

        # Verifica se l'espulsione è fallita (es. se non c'è disco)
        if error_code != 0:
            print(f"Attenzione: Impossibile espellere l'unità {drive_letter}: (Codice errore: {error_code}).")
            # Potresti aggiungere qui una gestione più dettagliata dell'errore

        # Chiudi/Rilascia
        mciSendString(close_command.encode('ascii'), None, 0, None)

    except Exception as e:
        print(f"Errore durante l'accesso al drive {drive_letter}: {e}")


class CDMonitor(QObject):
    """
    Monitora lo stato del lettore CD su Windows e emette segnali quando viene aperto o chiuso.
    """
    cd_aperto = pyqtSignal()
    cd_chiuso = pyqtSignal()

    def __init__(self, intervallo_ms=1000, lettera_drive='D'):
        super().__init__()
        self.lettera_drive = lettera_drive
        self.drive_path = f"{lettera_drive}:\\"
        self.stato_precedente = None
        self.drives = detect_cd_drives()

        # Configura il timer
        self.timer = QTimer()
        self.timer.setInterval(intervallo_ms)
        self.timer.timeout.connect(self._verifica_stato)

    def _verifica_stato(self):
        """Verifica lo stato corrente del lettore CD."""
        drives = detect_cd_drives()
        if len(drives) > len(self.drives):
            self.drives = drives
            self.cd_chiuso.emit()
            return
        elif len(drives) < len(self.drives):
            self.cd_aperto.emit()
            self.drives = drives
            return


        stato_corrente = self._leggi_stato_cd()

        # Emetti segnale solo se lo stato è cambiato
        if self.stato_precedente is not None and stato_corrente != self.stato_precedente:
            if stato_corrente:
                self.cd_aperto.emit()
            else:
                self.cd_chiuso.emit()

        self.stato_precedente = stato_corrente

    def _leggi_stato_cd(self):
        """
        Legge lo stato del lettore CD usando le API Windows.
        Ritorna True se aperto, False se chiuso.
        """
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32

            # Verifica che sia un drive CD-ROM
            drive_type = kernel32.GetDriveTypeW(self.drive_path)
            if drive_type != 5:  # 5 = DRIVE_CDROM
                return False

            # Tenta di leggere le informazioni del volume
            # Se fallisce, il vassoio è probabilmente aperto
            result = kernel32.GetVolumeInformationW(
                self.drive_path,
                None, 0,  # Volume name buffer
                None,  # Volume serial number
                None,  # Maximum component length
                None,  # File system flags
                None, 0  # File system name buffer
            )

            # result == 0 significa errore (vassoio aperto o nessun disco)
            # result != 0 significa successo (vassoio chiuso con disco)
            return result == 0

        except Exception as e:
            # In caso di errore, mantiene lo stato precedente
            return self.stato_precedente if self.stato_precedente is not None else False

    def start(self):
        """Avvia il monitoraggio del lettore CD."""
        # Inizializza lo stato corrente
        self.stato_precedente = self._leggi_stato_cd()
        self.timer.start()

    def stop(self):
        """Ferma il monitoraggio del lettore CD."""
        self.timer.stop()

class GlobalInputEventFilter(QObject):
    from PyQt6.QtCore import pyqtSignal
    # Segnale personalizzato per il movimento del mouse
    mouse_moved = pyqtSignal()

    def eventFilter(self, obj, event):
        # Cattura solo gli eventi di movimento del mouse
        if event.type() == QEvent.Type.MouseMove or event.type() == QEvent.Type.KeyPress:
            self.mouse_moved.emit()
            #print("Input event")

        # Restituisci False per non interferire con l'evento
        return False

class IdleTimeout:
    def __init__(self, parent, idle_time, timeout_fun):
        self.idle_timer = None
        self.idle_timeout = None
        self.timeout_fun = timeout_fun
        if idle_time != 0:
            self.idle_timer = QTimer()
            self.idle_timer.timeout.connect(self.timeout)
            self.global_event_filter = GlobalInputEventFilter(parent)
            QApplication.instance().installEventFilter(self.global_event_filter)
            self.global_event_filter.mouse_moved.connect(self.start_idle_timer)
            #self.installEventFilter(self)

            # Tempo di inattività in millisecondi (es: 5 minuti = 300000 ms)
            self.idle_timeout = idle_time * 60000 # trasforma minuti im msec

            # Avvia il timer
            self.start_idle_timer()

    def __del__(self):
        self.stop_idle_timer()

    def timeout(self):
        #self.stop_idle_timer()
        self.timeout_fun()

    def start_idle_timer(self):
        if self.idle_timeout != 0:
            """Avvia/Resetta il timer"""
            self.idle_timer.start(self.idle_timeout)

    def stop_idle_timer(self):
        try:
            self.idle_timer.timeout.disconnect()
            #self.idle_timer.stop()
        except:
            pass
