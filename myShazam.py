import soundfile as sf
import soundcard as sc
import io
from PyQt6.QtCore import pyqtSignal, QObject
from threading import Thread
import asyncio

class myShazam(QObject):
    found_song = pyqtSignal(dict)
    def __init__(self, time=3):
        super().__init__()
        from shazamio import Shazam
        self.shazam = Shazam()
        try:
            speaker = sc.default_speaker()
            # Proviamo a leggere il sample rate, altrimenti usiamo 44100 come fallback
            mic = sc.get_microphone(speaker.name, include_loopback=True)
            self.fs = int(mic.samplerate)
        except Exception:
            self.fs = 44100

        self.seconds = time

    async def capture_and_recognize(self):
        try:
            speaker = sc.default_speaker()
        except Exception as e:
            self.found_song.emit({"Error": f"Nessun dispositivo audio attivo: {e}"})
            return

        # Iniziamo con 5 secondi
        current_secs = self.seconds

        try:
            with sc.get_microphone(id=str(speaker.name), include_loopback=True).recorder(samplerate=self.fs) as mic:
                while True:
                    print(f"In ascolto per {current_secs} secondi...")
                    data = mic.record(numframes=self.fs * current_secs)

                    # Conversione rapida in buffer
                    buffer = io.BytesIO()
                    sf.write(buffer, data, self.fs, format='WAV')
                    audio_bytes = buffer.getvalue()

                    # Interroga Shazam (operazione asincrona di rete)
                    out = await self.shazam.recognize(audio_bytes)
                    if 'retryms' in out:
                        current_secs = out['retryms'] / 1000
                        if current_secs <= 10:
                            self.found_song.emit({"Retry": f"{current_secs} seconds"})
                            continue

                    if 'track' in out:
                        track_info = out['track']
                        album_name = ''
                        sections = track_info.get('sections', [])
                        if sections and len(sections) > 0:
                            metadata = sections[0].get('metadata', [])
                            if metadata and len(metadata) > 0:
                                album_name = metadata[0].get('text', '')
                        data = {
                            'title': track_info.get('title', 'Sconosciuto'),
                            'album': album_name,
                            'artist': track_info.get('subtitle', 'Sconosciuto')
                        }
                        self.found_song.emit(data)
                    else:
                        self.found_song.emit({"Error": 'Non identificata'})
                    return
        except Exception as e:
            self.found_song.emit({"Error": f"Errore di registrazione o rete: {e}"})

    def guess(self):
        def run():
            # Crea un nuovo loop di eventi solo per questo thread
            asyncio.run(self.capture_and_recognize())

        Thread(target=run, daemon=True).start()
