import io
import sys
#import wikipedia
import base64
import requests
from PyQt6.QtCore import Qt, QRunnable, QObject, QPoint, pyqtSignal
from PyQt6.QtWidgets import QAbstractItemView, QTableWidget, QMenu
from enum import Enum

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

        self.USER_AGENT = "IlTuoProgrammaDiTagging/1.0 (la_tua_email@example.com)"  # Usa il tuo vero User-Agent

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

        except requests.exceptions.RequestException:
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


