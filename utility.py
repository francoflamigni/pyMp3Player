from PyQt6.QtGui import QPixmap, QCursor, QColor, QIcon
from profiler import checkpoint
import io
import sys
import os
import base64
from PyQt6.QtCore import Qt, QRunnable, QObject, QPoint, pyqtSignal, QTimer, QEvent, QRect, QPropertyAnimation, \
    QEasingCurve
from PyQt6.QtWidgets import QAbstractItemView, QTableWidget, QMenu, QApplication, QLabel, QListWidget, QSizePolicy, \
    QGraphicsColorizeEffect, QDialog, QVBoxLayout, QWidget
from enum import Enum
from pyMyLib.utils import iniConf, get_resource_file
from pyMyLib.qtUtils import center_in_parent
from tempfile import TemporaryDirectory


def create_cursor(png_path, width=20, height=20, hotspot_x=10, hotspot_y=10):
    pixmap = QPixmap(png_path)
    scaled_pixmap = pixmap.scaled(width, height)
    return QCursor(scaled_pixmap, hotspot_x, hotspot_y)

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
    def __init__(self, artist_name, cursor_pos, lang="it", cache=None):
        super().__init__()
        self.artist_name = artist_name
        self.cursor_pos = cursor_pos + QPoint(150, 0)
        self.signals = WorkerSignals()
        self.setAutoDelete(True)
        self.lang = lang
        self.cache = cache
        self._is_cancelled = False

        self.USER_AGENT = "Euterpe/1.0 (contatto: tuaemail@esempio.it)"

        # Definisci uno stile CSS interno per pulire il codice
        self.style = """
        <style>
            .tooltip-container { font-family: sans-serif; width: 250px; padding: 10px; }
            .title { display: block; text-align: center; font-size: 18px; font-weight: bold; margin-top: 15px; }
            .img-wrapper { text-align: center; margin: 10px 0 0 0; }
            .summary-container { margin-top: 5px; min-height: 80px; font-size: 14px; } /* min-height evita il salto */
        </style>
        """
    def cancel(self):
        self._is_cancelled = True

    def assemble_html(self, img_tag, summary):

        tooltip_html = f"{self.style}<div class='tooltip-container'>"
        tooltip_html += f"<center><span class='title'>{self.artist_name}</span></center><hr>"
        if img_tag:
            tooltip_html += (f"""<div class='img-wrapper'>
                             <img src="data:{self.content_type};base64,{img_tag}" class="artist-img">
                             </div>""")

        # Creiamo il contenitore per il summary (vuoto per ora)
        if not summary:
            tooltip_html += "<div class='summary-container'><i>Caricamento biografia...</i></div></div>"
        else:
            # STEP 2: Aggiungi il summary reale
            clean_summary = textwrap(summary, width=50).replace("\n", "<br>")
            tooltip_html += f"<div class='summary-container'>{clean_summary}</div></div>"
        return tooltip_html

    def run(self):
        import wikipedia
        wikipedia.set_lang(self.lang)
        file_cache = f"{self.artist_name}.html"

        try:
            if self._is_cancelled: return
            # 1. Controllo Cache Immediato
            if self.cache:
                txt = self.cache.get(file_cache)
                if txt:
                    self.signals.result.emit(txt, self.cursor_pos)
                    return

            # 2. Raccolta Dati (senza emit intermedi)
            image_url = self._get_image_url()
            if self._is_cancelled: return
            img_tag = ""
            if image_url:
                img_tag = self._get_base64_image_tag(image_url)
            if self._is_cancelled: return
            full_html = self.assemble_html(img_tag, None)
            self.signals.result.emit(full_html, self.cursor_pos)

            summary = wikipedia.summary(self.artist_name, sentences=5)
            # Rimuovi textwrap se usi un div con larghezza fissa, il browser gestirà il wrap meglio

            # 3. Costruzione HTML Finale
            full_html = self.assemble_html(img_tag, summary)

            # 4. Singola Emissione
            self.signals.result.emit(full_html, self.cursor_pos)

            # 5. Salvataggio in Cache
            if self.cache:
                self.cache.set(file_cache, full_html)

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
            "titles": self.artist_name, "pithumbsize": 200, "redirects": 1  # Usa un thumbnail più piccolo
        }
        try:
            R = S.get(url=URL, params=PARAMS)
            R.raise_for_status()
            data = R.json()
            pages = data.get("query", {}).get("pages", {})
            page = next(iter(pages.values()), None)

            if page and "thumbnail" in page:
                return page["thumbnail"].get("source")
        except Exception as e:
            print(f"Errore API Wikipedia: {e}")
        return None

    def _get_base64_image_tag(self, url):
        import requests
        """Scarica l'immagine e la converte in un tag <img> Base64."""
        try:
            R = requests.get(url, headers={"User-Agent": self.USER_AGENT}, timeout=5)
            R.raise_for_status()

            # Tipo di immagine (presumiamo JPEG se l'URL non ha estensione)
            self.content_type = R.headers.get('Content-Type', 'image/jpeg')

            # Codifica il contenuto binario in Base64
            base64_encoded_data = base64.b64encode(R.content).decode('utf-8')

            return base64_encoded_data

            # Crea il tag <img> con i dati incorporati
            return f'<img src="data:{self.content_type};base64,{base64_encoded_data}" style="max-width:200px; max-height:200px; display:block; margin:auto; p align="center">'

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
        self.stop_idle_timer()
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

class Cache:
    def __init__(self, ini:iniConf):
        self.ini = ini
        ini.get("cache")
        self.dir = ini.get("cache", "dir")
        if self.dir and not os.path.exists(self.dir):
            os.makedirs(self.dir, exist_ok=True)
        try:
            self.duration = int(ini.get("cache", "duration")) # giorni di validità della cacche
            self.max_size = int(ini.get("cache", "max_size")) #massima dimensione cache in mb
        except:
            self.duration = 0
            self.max_size = 0
        self.limite_secondi = time.time() - (self.duration * 86400)
        self.max_size_byte = self.max_size * 1024 * 1024

    def save(self, dir, duration, max_size):
        cs = {
            "dir": dir,
            "duration": str(duration),
            "max_size": str(max_size)
        }
        self.ini.set_sez("cache", cs)
        self.ini.save()

    def get(self, filename):
        txt = ''
        if not self.dir:
            return
        filepath = os.path.join(self.dir, filename)
        if not os.path.exists(filepath):
            return txt
        data_creazione = os.path.getctime(filepath)
        if data_creazione < self.limite_secondi:
            return txt
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
        return txt

    def set(self, filename, data):
        from win32_setctime import setctime
        if not self.dir:
            return
        filepath = os.path.join(self.dir, filename)
        self.ensure_space(len(data))
        with open(filepath, "w", encoding="utf-8") as f:
                f.write(data)
        data_creazione = os.path.getctime(filepath)
        setctime(filepath, time.time())
        data_creazione2 = os.path.getctime(filepath)
        a = 0

    """ verifica che non sia superato il limite della cache, """
    """ fa spazio rimuovendo i file con ultimo accesso più vecchio """
    def ensure_space(self, sz):
        lista, size = lista_file_per_ultimo_accesso(self.dir)
        while size + sz > self.max_size_byte:
            it = lista.pop(0)
            os.remove(os.path.join(self.dir, it))
            size -= it[2]
            if size < 0:
                size = 0

import time
def trova_file_creati_prima_di(cartella_root, giorni):
    file_scaduti = []

    # Calcoliamo il limite temporale: ora attuale meno (giorni * secondi in un giorno)
    limite_secondi = time.time() - (giorni * 86400)

    for root, dirs, files in os.walk(cartella_root):
        for nome_file in files:
            percorso_completo = os.path.join(root, nome_file)
            try:
                # st_ctime su Windows è la Creazione del file
                data_creazione = os.path.getctime(percorso_completo)

                if data_creazione < limite_secondi:
                    file_scaduti.append(percorso_completo)
            except OSError:
                continue

    return file_scaduti

""" ritorna i files in una cartella ordinati per ultimo accesso, da più vecchio al più nuovo """
def lista_file_per_ultimo_accesso(cartella_root):
    lista_file = []
    tot_size = 0
    for root, dirs, files in os.walk(cartella_root):
        for nome_file in files:
            percorso_completo = os.path.join(root, nome_file)
            try:
                # Recuperiamo il timestamp dell'ultimo accesso (st_atime)
                stat = os.stat(percorso_completo)

                # Creiamo la tupla con: (timestamp, dimensione_byte, percorso)
                dati_file = (
                    stat.st_atime,  # [0] Ultimo accesso
                    stat.st_size,  # [1] Dimensione in byte
                    percorso_completo  # [2] Percorso
                )
                tot_size += stat.st_size
                lista_file.append(dati_file)
            except OSError:
                # Ignora file bloccati o senza permessi
                continue

    # Ordiniamo la lista in base al primo elemento della tupla (il timestamp)
    # L'ordinamento di default è crescente: dal numero più piccolo (data più vecchia)
    lista_file.sort(key=lambda x: x[0])

    return lista_file, tot_size


class myList(QListWidget):
    play_signal = pyqtSignal(QListWidget)
    def __init__(self, parent, txt='', cursor=0):
        super().__init__(parent)
        self.itc = None
        if txt != '':
            self.addItem(txt)
        self.setMouseTracking(True)
        self.cursor = cursor

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda p: parent.contextMenu(p, self, self.itemAt(p)))

    def setSelCur(self, it):
        if self.itc != it:
            self.itc = it

    def mouseMoveEvent(self, event):
        #if not self.cursor:

        if self.hasFocus() is False:
            self.setFocus()
            self.unsetCursor()
            super(QListWidget, self).mouseMoveEvent(event)
            return

        if not self.cursor:
            it = self.itemAt(event.pos())
            x = event.pos().x()
            #print(x)
            if self.itc is not None:
                if it != self.itc or x > 50:
                    self.unsetCursor()
                else:
                    self.setCursor(create_cursor(get_resource_file(__file__, 'icone', 'play.png')))

        super(QListWidget, self).mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if not self.cursor and event.button() == Qt.MouseButton.LeftButton:
            it = self.itemAt(event.pos())
            x = event.pos().x()
            if it == self.itc and x <= 50:
                try:
                    self.unsetCursor()
                    self.play_signal.emit(self)
                except:
                    pass
            elif it != self.itc and x <= 50:
                self.setCursor(create_cursor(get_resource_file(__file__, 'icone', 'play.png')))
        super(QListWidget, self).mousePressEvent(event)


class CustomToolTip(QLabel):
    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setWordWrap(True)
        self.setFixedWidth(400)
        self.setStyleSheet("background-color: #333; color: white; border: 1px solid #555; padding: 10px;")

        # L'animazione agirà sulla geometria (posizione e dimensione)
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(250)  # Millisecondi (un quarto di secondo)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)


class MusicList(myList):
    def __init__(self, parent, show_tip=None, hide_tip=None, label='', cursor=0):
        super().__init__(parent, txt=label, cursor=cursor)
        self.my_tip = CustomToolTip()
        self.active_item = None  # Per sapere su quale riga siamo
        self.show_tip = show_tip
        self.hide_tip = hide_tip
        self.screen_height = QApplication.primaryScreen().size().height()

    def mouseMoveEvent(self, event):
        p = event.pos()
        if p.x() > 70:
            self.unsetCursor()
            self.nascondi_mio_tip()
            super().mouseMoveEvent(event)
            return
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        item = self.itemAt(event.pos())
        # Se il mouse è ancora sulla stessa riga, NON fare nulla (niente flicker!)
        if item == self.active_item:
            super().mouseMoveEvent(event)
            return

        # Se cambiamo riga o usciamo
        if item:
            self.nascondi_mio_tip()
            self.active_item = item
            p = event.globalPosition().toPoint()
            QTimer.singleShot(100, lambda: self.mostra_mio_tip(item.text(), p))
            #self.mostra_mio_tip(item.text(), p)
        else:
            self.nascondi_mio_tip()

    def mousePressEvent(self, event):
        self.nascondi_mio_tip()

        super().mouseMoveEvent(event)

    def mostra_mio_tip(self, txt, global_pos):
        cursor_pos = QCursor.pos()
        item = self.itemAt(self.mapFromGlobal(cursor_pos))
        if item is not None and item.text() == txt:
            self.my_tip.move(global_pos.x() + 30, global_pos.y() - 15)
            self.show_tip(txt, global_pos)


        # 3. Qui lanci il tuo WikipediaWorker.
        # Quando il worker emette il segnale, chiamerai self.my_tip.setText(html_wikipedia)
        # Il widget resterà visibile e il testo cambierà istantaneamente senza sparire!

    def leaveEvent(self, event):
        self.nascondi_mio_tip()
        self.unsetCursor()
        super().leaveEvent(event)

    def nascondi_mio_tip(self):
        self.active_item = None
        self.my_tip.hide()
        self.hide_tip()

    def show_tooltip_result(self, txt):
        # 1. Aggiorna il contenuto (ora con foto + testo)
        self.my_tip.setText(txt)

        # 2. Salva la posizione attuale del ToolTip (per non farlo saltare altrove)
        posizione_attuale = self.my_tip.pos()

        # 3. Chiedi a Qt di calcolare quanto spazio servirebbe ORA
        # Usiamo sizeHint() per sapere la dimensione ideale senza cambiare subito il widget
        dimensione_ideale = self.my_tip.sizeHint()

        # 4. Opzione A: Scatto istantaneo
        # self.my_tip.resize(dimensione_ideale)

        y0 = posizione_attuale.y()
        dy0 = dimensione_ideale.height()
        dy = y0 + dy0
        if dy > self.screen_height:
            ddy = dy - self.screen_height
            y0 -= ddy

        # 5. Opzione B: Animazione di crescita fluida verso la nuova dimensione
        self.my_tip.animation.stop()  # Ferma animazioni precedenti
        self.my_tip.animation.setStartValue(self.my_tip.geometry())
        self.my_tip.animation.setEndValue(QRect(
            posizione_attuale.x(),
           y0,
            self.my_tip.width(),  # Larghezza fissa
            dy0  # Nuova altezza calcolata
        ))
        self.my_tip.animation.start()



        self.my_tip.setText(txt)
        self.my_tip.show()

class ShazamButtonHandler:
    def __init__(self, button):
        self.button = None
        self.init(button)

    def init(self, button):
        #self.stop_blinking()
        self.button = button
        self.effect = QGraphicsColorizeEffect(self.button)
        self.effect.setColor(QColor("red"))
        self.effect.setStrength(0)  # Inizia invisibile (0 = colore originale)
        self.button.setGraphicsEffect(self.effect)

        # Timer per il lampeggio
        self.timer = QTimer()
        self.timer.timeout.connect(self._toggle_blink)
        self.is_red = False

    def start_blinking(self):
        self.timer.start(500)  # Lampeggia ogni 500ms

    def stop_blinking(self):
        self.timer.stop()
        self.effect.setStrength(0)  # Torna all'icona nera originale
        self.is_red = False

    def _toggle_blink(self):
        if self.is_red:
            self.effect.setStrength(0)  # Torna nero
        else:
            self.effect.setStrength(1)  # Diventa rosso
        self.is_red = not self.is_red

class songInfoDlg(QDialog):
    def __init__(self, parent, txt):
        from dialogs import myPlainText
        super().__init__(parent)
        self.txt = txt
        center_in_parent(self, parent, 300, 100)
        self.setWindowTitle('Shazam')
        self.setWindowIcon(QIcon(get_resource_file(__file__, 'icone', 'shazam.png')))

        v = QVBoxLayout(self)
        self.txt_box = myPlainText(self)

        self.txt_box.setText(txt)
        v.addWidget(self.txt_box)

    @staticmethod
    def run(parent, txt):
        dlg = songInfoDlg(parent, txt)
        dlg.exec()

class AppContext:
    def __init__(self, config:iniConf, cache:Cache, tmpObj:TemporaryDirectory, mainW:QWidget=None) -> None:
        self.config = config
        self.cache = cache
        self.temp_dir_obj = tmpObj()
        self.tmpDir = str( self.temp_dir_obj.name)
        self.mainWindow = mainW

def human_size(n: int) -> str:
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    i = 0
    while n >= 1024 and i < len(units)-1:
        n /= 1024
        i += 1
    return f"{n:3.1f} {units[i]}"