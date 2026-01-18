import os.path

from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QApplication

from profiler import checkpoint

# -*- coding: utf-8 -*-
import logging
import urllib.error
import urllib.parse
import urllib.request
import re
import struct
import time
#from lyricsgenius import Genius
logger = logging.getLogger(__package__)

formatter = logging.Formatter(
    "[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s"
)

from pyMyLib.qtUtils import waitCursor

null_handler = logging.NullHandler()
null_handler.setFormatter(formatter)
logger.addHandler(null_handler)


# this is the function you should call with the url to get all data sorted as a object in the return
def get_server_info(url):
    if url.endswith(".pls") or url.endswith("listen.pls?sid=1"):
        address = check_pls(url)
    else:
        address = url
    if isinstance(address, str):
        meta_interval = get_all_data(address)
    else:
        meta_interval = {"status": 0, "metadata": None}

    return meta_interval


def get_all_data(address):
    status = 0

    request = urllib.request.Request(address)
    user_agent = "iTunes/9.1.1"
    request.add_header("User-Agent", user_agent)
    request.add_header("icy-metadata", 1)
    try:
        response = urllib.request.urlopen(request, timeout=6)
        headers = dict(response.info())

        if "Server" in headers:
            shoutcast = headers["Server"]
        elif "X-Powered-By" in headers:
            shoutcast = headers["X-Powered-By"]
        elif "icy-notice1" in headers:
            shoutcast = headers["icy-notice2"]
        else:
            shoutcast = True

        if isinstance(shoutcast, bool):
            if shoutcast:
                status = 1
            else:
                status = 0
            metadata = False
        elif "SHOUTcast" in shoutcast:
            status = 1
            metadata = shoutcast_check(response, headers, False)
        elif "Icecast" or "137" or "StreamMachine" in shoutcast:
            status = 1
            metadata = shoutcast_check(response, headers, True)
        elif shoutcast:
            status = 1
            metadata = shoutcast_check(response, headers, True)
        else:
            metadata = False
        response.close()
        return {"status": status, "metadata": metadata}

    except urllib.error.HTTPError as e:
        logger.exception("    Error, HTTPError = ")

        return {"status": status, "metadata": None}

    except urllib.error.URLError as e:
        logger.exception("    Error, URLError: ")
        return {"status": status, "metadata": None}

    except Exception as err:
        logger.exception("    Error: ")
        return {"status": status, "metadata": None}


def check_pls(address):
    try:
        stream = None
        response = urllib.request.urlopen(address, timeout=2)
        for line in response:
            if line.startswith(b"File1="):
                stream = line.decode()

        response.close()
        if stream:
            return stream[6:].strip("\n")
        else:
            return False
    except Exception:
        return False


def shoutcast_check(response, headers, is_old):
    bitrate = None
    contenttype = None

    if "icy-br" in headers:
        if is_old:
            bitrate = headers["icy-br"].split(",")[0]
        else:
            bitrate = headers["icy-br"]
            bitrate = bitrate.rstrip()

    if "icy-metaint" in headers:
        icy_metaint_header = headers["icy-metaint"]
    else:
        icy_metaint_header = None

    if "Content-Type" in headers:
        contenttype = headers["Content-Type"].rstrip()
    elif "content-type" in headers:
        contenttype = headers["content-type"].rstrip()

    if icy_metaint_header:
        metaint = int(icy_metaint_header)
        read_buffer = metaint + 255
        content = response.read(read_buffer)

        start = "StreamTitle='"
        end = "';"

        try:
            title = (
                re.search(bytes("%s(.*)%s" % (start, end), "utf-8"), content[metaint:])
                .group(1)
                .decode("utf-8")
            )
            a = (
                re.sub("StreamUrl='.*?';", "", title)
                .replace("';", "")
                .replace("StreamUrl='", "")
            )
            title = re.sub("&artist=.*", "", title)
            title = re.sub("http://.*", "", title)
            title.rstrip()
        except Exception as err:
            logger.exception("songtitle error: ")
            title = content[metaint:].split(b"'")[1]

        return {"song": title, "bitrate": bitrate, "contenttype": contenttype}
    else:
        logger.debug('No metaint')
        return False


def strip_tags(text):
    finished = 0
    while not finished:
        finished = 1
        start = text.find("<")
        if start >= 0:
            stop = text[start:].find(">")
            if stop >= 0:
                text = text[:start] + text[start + stop + 1 :]
                finished = 0
    return text

def get_thumbnail(url):
    if len(url) > 0:
        try:
            im = urllib.request.urlopen(url).read()
            if "DOCTYPE" in str(im):
                return None
            return im

        except:
            pass
    return None


from threading import Thread, Event
class GetRadioInfo(QObject):
    radio_info_msg = pyqtSignal(str)
    def __init__(self, url, timeout):
        super().__init__()
        self.url = url
        self.timer = QTimer()
        self.timeout = timeout
        #self.running = False
        self.stop_event = Event()
        self.th = None

    def start(self):
        self.th = Thread(target=self.get_title, daemon=True)
        #self.running = True
        self.th.start()

    def stop(self):
        self.stop_event.set()

    def get_title(self):
        while not self.stop_event.is_set():
            title = ''
            try:
                # Aggiungiamo un timeout alla urlopen per evitare blocchi infiniti
                request = urllib.request.Request(self.url, headers={'Icy-MetaData': '1'})
                with urllib.request.urlopen(request, timeout=5) as response:
                    metaint = response.headers.get('icy-metaint')

                    if metaint:
                        metaint = int(metaint)
                        # Leggiamo i dati necessari per trovare il titolo
                        for _ in range(5):  # Riduciamo i tentativi per velocità
                            response.read(metaint)  # Salta i dati audio

                            # Leggi il byte della lunghezza (va moltiplicato per 16)
                            res = response.read(1)
                            if not res: break

                            metadata_length = struct.unpack('B', res)[0] * 16
                            if metadata_length > 0:
                                metadata = response.read(metadata_length).rstrip(b'\0')
                                m = re.search(br"StreamTitle='([^']*)';", metadata)
                                if m:
                                    raw_title = m.group(1)
                                    # Gestione decodifica intelligente
                                    try:
                                        title = raw_title.decode('utf-8')
                                    except UnicodeDecodeError:
                                        title = raw_title.decode('latin1', errors='replace')

                                    if title:
                                        break

                    # Chiudendo il blocco 'with', la connessione viene rilasciata
            except Exception as e:
                print(f"Errore recupero info radio: {e}")
                title = "Info non disponibile"

            # Invia il segnale (se title è vuoto, invia stringa vuota)
            self.radio_info_msg.emit(title)

            # Attesa intelligente: si interrompe subito se chiami stop_event.set()
            self.stop_event.wait(timeout=self.timeout / 1000.0)

    """
    def get_title(self):
        while not self.stop_event.is_set():
            title = ''
            request = urllib.request.Request(self.url, headers={'Icy-MetaData': 1})  # request metadata
            try:
                response = urllib.request.urlopen(request)
            except:
                self.radio_info_msg.emit(title)
                continue

            metas = response.headers.get('icy-metaint', '')
            if not metas:
                self.radio_info_msg.emit(title)
                continue

            metaint = int(metas)
            for _ in range(10):  # # title may be empty initially, try several times
                response.read(metaint)  # skip to metadata
                metadata_length = struct.unpack('B', response.read(1))[0] * 16  # length byte
                metadata = response.read(metadata_length).rstrip(b'\0')
                # extract title from the metadata
                m = re.search(br"StreamTitle='([^']*)';", metadata)
                if m:
                    title = m.group(1)
                    if title:
                        break

            if isinstance(title, str) is False:
                encoding = 'latin1'  # default: iso-8859-1 for mp3 and utf-8 for ogg streams
                title = title.decode(encoding, errors='replace')
            self.radio_info_msg.emit(title)
            self.stop_event.wait(timeout=self.timeout / 1000.)
    """
class LyricsWorker(QObject):
    finished = pyqtSignal(str)
    def __init__(self, artist, song):
        super().__init__()
        self.artist = artist
        self.song_title = song
        self.token = '820kVTvq2j69BfzKyrC8Viw6aa3HewHKUnps85vjvYLRuS3YjVeEktkWsbUdzwLI'

        """
        clientID = 'vMXGN9eXhW_1JqnbqVGumj5wPK9b3y3rgCAZzxEqM2Hvkt-3p58cP4iYxFxhDVPV'
        secret = 'zk23Q4-jYVg5XlSy74b8O2HCHBFdSplOngNByVkM2V6oz38Bf3tdNc0hKw29A9eJVHWooKkSEMpiPenLXSBGsg'
        token = '820kVTvq2j69BfzKyrC8Viw6aa3HewHKUnps85vjvYLRuS3YjVeEktkWsbUdzwLI'
        """
    def _song_text(self):
        from lyricsgenius import Genius

        txt = ''

        api = Genius(self.token, verbose=False, timeout=10,
                            remove_section_headers=False, skip_non_songs=True, response_format='dom')

        try:
            #art = api.search_artist(artist, max_songs=0)
            song = api.search_song(self.song_title, self.artist, None, False)
            if song is not None:
                txt = song.lyrics
                txt = re.sub(r'.*(?=[\[{])', r'\n', txt)

                lines = txt.strip().split('\n')
                lines[-1] = re.sub(r'embed', '', lines[-1], flags=re.IGNORECASE)
                lines[-1] = re.sub(r'You might.*', '', lines[-1], flags=re.IGNORECASE)
                lines[-1] = re.sub(r'\d+$', '', lines[-1])
                lines[0] = re.sub(r'.*lyrics', '', lines[0], flags=re.IGNORECASE)
                txt =  '\n'.join(lines)

                a = 0
        except ConnectionError as err:
            txt = f"Connection error: {err}"
        except Exception as er1:
            txt = f"Error: {er1}"

        self.finished.emit(txt)
        return txt

    def song_text(self):
        Thread(target=self._song_text, daemon=True).start()

    def song_text2(self):
        waitCursor(True)
        t = self._song_text()
        waitCursor()
        return t

import edge_tts
import asyncio
class Speaker:
    def __init__(self, gender, tmp_dir):
        self.gender = 'Male' if gender.lower() == 'uomo' else 'Female'
        self.voce = ''
        self.tmp_dir = tmp_dir
        self.slang = {'it': 'IT',
                 'fr': 'FR',
                 'es': 'ES',
                 'de': 'DE',
                 'en': 'GB'}

    async def select_voce(self, gender='Female'):
        # Recupera tutte le voci disponibili
        voci = await edge_tts.VoicesManager.create()

        try:
            # Filtra per la lingua desiderata (es. "it" per italiano)
            voci_filtrate = voci.find(Locale=self.codice_lingua, Gender=self.gender)
            self.voce = voci_filtrate[0]['ShortName']
        except:
            self.voce = "it-IT-IsabellaNeural"

    def detect_lingua(self, frase):
        from langdetect import detect
        lingua_rilevata = detect(frase)
        if lingua_rilevata is None:
            lingua = "it"
        else:
            lingua = lingua_rilevata.lower()
        try:
            self.codice_lingua = f"{lingua}-{self.slang[lingua]}"
        except:
            self.codice_lingua = 'it-IT'

    def pronuncia(self, frase, volume="50"):
        vol = f"{int(volume):+}%"
        return asyncio.run(self._pronuncia(frase, vol))

    async def _pronuncia(self, frase, volume):
        if not self.voce:
            self.detect_lingua(frase)
            await self.select_voce()

        communicate = edge_tts.Communicate(frase.title(), self.voce, volume=volume)
        audio_data = b""

        # 1. Recupero i dati binari (MP3) in memoria
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]

        # Salva su disco
        file_out = os.path.join(self.tmp_dir, "Euterpe_output.mp3")
        with open(file_out, "wb") as f:
            f.write(audio_data)
        return file_out

"""
def leggi_stringa_offline2(testo: list):
    import pyttsx3
    from langdetect import detect  # Manteniamo langdetect
    try:
        lingua_rilevata = detect(testo[2])
        engine = pyttsx3.init(driverName='sapi5')

        # --- Selezione Intelligente della Voce ---
        voci = engine.getProperty('voices')
        voce_selezionata = None

        # Cerca una voce che corrisponda alla lingua rilevata
        for voce in voci:
            if voce.languages and lingua_rilevata.lower() in [l.split('-')[0].lower() for l in voce.languages]:
                voce_selezionata = voce
                break

        engine.setProperty('rate', 180)

        if voce_selezionata:
            print(f"Voce selezionata ({lingua_rilevata.upper()}): {voce_selezionata.name}")
            engine.setProperty('voice', voce_selezionata.id)
        else:
            print(f"Nessuna voce locale adatta trovata per la lingua {lingua_rilevata.upper()}.")

        # Sintesi e Riproduzione
        t = '.'.join(testo)
        engine.say(t)
        engine.runAndWait()
        engine.stop()

    except Exception as e:
        print(f"Errore: {e}")
"""
"""
def leggi_stringa_offline(testo: list):
    from gtts import gTTS
    from langdetect import detect
    import soundfile as sf
    import sounddevice as sd
    import os

    try:
        #lingua_rilevata = detect(testo[2])
        lingua_rilevata = detect(' '.join(testo))

        # Mappa codici lingua per gTTS
        mappa_lingue = {
            'en': 'en', 'it': 'it', 'es': 'es', 'fr': 'fr',
            'de': 'de', 'pt': 'pt', 'ru': 'ru', 'ja': 'ja',
            'zh-cn': 'zh-CN', 'ar': 'ar', 'hi': 'hi', 'ko': 'ko'
        }

        lingua_gtts = mappa_lingue.get(lingua_rilevata.lower(), 'en')
        #print(f"Lingua rilevata: {lingua_rilevata.upper()} -> gTTS: {lingua_gtts}")

        # Pronuncia ogni frase con pausa di 10ms
        for i, frase in enumerate(testo):
            QApplication.processEvents()
            filename = f"temp_audio_{i}.mp3"

            # Genera l'audio
            tts = gTTS(text=frase, lang=lingua_gtts, slow=False)
            tts.save(filename)

            # Leggi e riproduci l'audio
            data, samplerate = sf.read(filename)
            sd.play(data, samplerate)
            sd.wait()  # Aspetta che finisca la riproduzione

            # Rimuovi il file temporaneo
            os.remove(filename)

    except Exception as e:
        print(f"Errore: {e}")
"""