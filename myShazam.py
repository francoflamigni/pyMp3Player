import soundcard as sc
import soundfile as sf
from PyQt6.QtCore import pyqtSignal, QObject
from pyMyLib.qtUtils import waitCursor
from shazamio import Shazam
from threading import Thread
import asyncio
import os

import tempfile

class myShazam(QObject):
    found_song = pyqtSignal(dict)
    def __init__(self, time=10):
        super().__init__()
        tmpdir = tempfile.mkdtemp()
        self.nome = os.path.join(tmpdir, 'test.wav')
        self.seconds = time
        self.data = None
        try:
            os.remove(self.nome)
        except:
            pass

    def _guess(self):
        self.speaker()

        if not os.path.exists(self.nome):
            self.found_song.emit("errore no recording")
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
        self.found_song.emit(out)
        waitCursor()

    def speaker(self):
        try:
            with sc.get_microphone(
                id=str(sc.default_speaker().name), include_loopback=True
            ).recorder(samplerate=44100) as speaker:
                self.data = speaker.record(numframes=44100 * self.seconds)
                sf.write(file=self.nome, data=self.data, samplerate=44100)
        except Exception as e:
            a = 0

