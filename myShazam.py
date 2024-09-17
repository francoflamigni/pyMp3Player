import soundcard as sc
import soundfile as sf
from shazamio import Shazam
from threading import Thread
import asyncio
import os


class myShazam:
    def __init__(self, bck, time=10):
        self.bck = bck
        self.nome = 'c:/temp/pippo.wav'
        self.seconds = time
        self.data = None
        try:
            os.remove(self.nome)
        except:
            pass

    def _guess(self):
        self.speaker()

        if not os.path.exists(self.nome):
            self.bck("errore no recording")
            return

        asyncio.run(self.identify_audio())

    def guess(self):
        searcher = Thread(target=self._guess)
        searcher.start()

    async def identify_audio(self):
        shazam = Shazam()
        try:
            out = await shazam.recognize(data=self.nome, proxy=None)
        except:
            out = 'errore'
        self.bck(out)

    def speaker(self):
        try:
            with sc.get_microphone(
                id=str(sc.default_speaker().name), include_loopback=True
            ).recorder(samplerate=44100) as speaker:
                self.data = speaker.record(numframes=44100 * self.seconds)
                sf.write(file=self.nome, data=self.data, samplerate=44100)
        except:
            a = 0
