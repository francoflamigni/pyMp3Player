import eyed3
import os
from threading import Thread, Lock
from queue import Empty, Queue
import time

class music:
    def __init__(self, path):
        self.path = path
        self.artisti = artists()
        self.albums = albums()
        self.track = tracks()
        self.album_artist = album_artist()
        self.album_track = album_track()
        self.path = path
        self.nth = 10
        self.inp = Queue(self.nth)
        #self.out = Queue(20)
        self.lock = Lock()

    def index(self):
        self.searchers = []
        for i in range(self.nth):
            name = 'searcher {}'.format(i)
            searcher = Thread(target=self.process, args=(name,))
            searcher.start()
            self.searchers.append(searcher)



        self.get_mp3(self.path)

        for searcher in self.searchers:
            searcher.join()

        a = 0
    def process(self, nome):
        a =0
        while True:
            t = self.inp.get(timeout=0.1)
            self.inp.task_done()
            brano = eyed3.load(os.path.join(t[0], t[1]))
            if brano is not None and brano.tag is not None:
                if brano.tag.title is None:
                    brano.tag.title, _ = os.path.splitext(t[1])
                if brano.tag.album is None:
                    brano.tag.album = os.path.basename(t[0])
                self.add_track(brano.tag)
                count = len(self.track)
    def get_mp3(self, path):
        for root, dirs, files in os.walk(path):
            for file in files:
                self.inp.put((root, file))

            for dir in dirs:
                self.get_mp3(os.path.join(root, dir))

    def add_track(self, tag):
        with self.lock:
            id_artist = self.artisti.add(tag.artist)
            id_album = self.albums.add(tag.album)
            self.album_artist.add(id_album, id_artist)
            id_track = self.track.add(tag.title, tag.album)
            self.album_track.add(id_album, id_track)

class artists:
    def __init__(self):
        self.name = {}
        self.id = 0
    def add(self, nome):
        if nome in self.name.keys():
            return self.name[nome]

        self.id += 1
        self.name[nome] = self.id
        return id


class tracks:
    def __init__(self):
        self.name = {}
        self.id = 0

    def add (self, title, album):
        if title is None or album is None:
            a = 0
        nome = title + '@' + album
        if nome in self.name.keys():
            return self.name[nome]

        self.id += 1
        self.name[nome] = self.id
        return id


class albums:
    def __init__(self):
        self.title = {}
        self.id = 0
    def add(self, title):
        if title in self.title.keys():
            return self.title[title]

        self.id += 1
        self.title[title] = self.id
        return id

class album_artist:
    def __init__(self):
        self.a_a = []
    def add(self, album, artist):
        t = (album, artist)
        if t not in self.a_a:
            self.a_a.append(t)

class album_track:
    def __init__(self):
        self.a_t = []
    def add(self, album, track):
        t = (album, track)
        if t not in self.a_t:
            self.a_t.append(t)
    def find_tracks(self, album):
        v = [t[1] for t in self.a_t if t[0] == album]
        return v





def music_index(folderpath):
    m = music(folderpath)
    t0 = time.monotonic()
    m.index()
    t1 = time.monotonic()
    dt = t1 - t0

    a = 0
