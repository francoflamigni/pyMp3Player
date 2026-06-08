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
        speaker = sc.default_speaker()
        # Iniziamo con 5 secondi
        current_secs = self.seconds

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
                if 'retryms' in out.keys():
                    current_secs = out['retryms'] / 1000
                    if current_secs <= 10:
                        self.found_song.emit({"Retry": f"{current_secs} seconds"})
                        continue

                if 'track' in out.keys():
                    data = {
                        'title': out['track']['title'],
                        'album': out['track']['sections'][0]['metadata'][0]['text'] if 'sections' in out[
                            'track'].keys() else '',
                        'artist': out['track']['subtitle']
                    }
                    self.found_song.emit(data)
                else:
                    self.found_song.emit({"Error": 'Non identificata'})
                return

    def _guess(self):
        retry = True
        secs = self.seconds
        while retry:
            audio_buffer = self.speaker_to_buffer(secs)
            if audio_buffer is None:
                self.found_song.emit({"Error": "No recording"})
                return

            try:
                # Eseguiamo il loop asincrono
                result = asyncio.run(self.identify_audio(audio_buffer))
                if 'retryms'in result.keys():
                    secs = result['retryms'] / 1000
                    if secs <= 10:
                        self.found_song.emit({"Retry": f"{secs} seconds"})
                        continue

                retry = False
                if 'track' in result.keys():
                    data = {
                        'title': result['track']['title'],
                        'album': result['track']['sections'][0]['metadata'][0]['text'] if 'sections' in result['track'].keys() else '',
                        'artist': result['track']['subtitle']
                    }
                    self.found_song.emit(data)
                else:
                    self.found_song.emit({"Error": 'Non identificata'})
            except Exception as e:
                retry = False
                self.found_song.emit({"Error": f"{str(e)}"})

    def guess(self):
        def run():
            # Crea un nuovo loop di eventi solo per questo thread
            asyncio.run(self.capture_and_recognize())

        Thread(target=run, daemon=True).start()
        #(target=self._guess, daemon=True).start()

    async def identify_audio(self, binary_data):
        # Shazamio accetta direttamente i bytes
        out = await self.shazam.recognize(data=binary_data)
        return out

    def speaker_to_buffer(self, secs):
        import soundcard as sc
        import io
        try:
            with sc.get_microphone(
                    id=str(sc.default_speaker().name), include_loopback=True
            ).recorder(samplerate=44100) as mic:
                data = mic.record(numframes=44100 * secs)

                # Invece di scrivere su disco, scriviamo in un buffer di memoria
                buffer = io.BytesIO()
                sf.write(buffer, data, 44100, format='WAV')
                return buffer.getvalue()  # Restituisce i byte del file WAV
        except Exception:
            return None
