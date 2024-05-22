import eyed3
import os
from threading import Thread, Lock
from queue import Empty, Queue
import json
import glob
from utils import ts_date2
import hashlib
import time
import datetime

def find_last(path):
    f = os.path.join(path, '**')
    list_of_files = glob.glob(f, recursive=True)
    latest_file = max(list_of_files, key=os.path.getmtime)
    r = os.path.relpath(latest_file, path)
    v = os.path.getmtime(latest_file)
    t = ts_date2(v)
    return {r: v}
class Music:
    NO_INDEX = -1  # manca l'indice
    INDEX_LOADED = 0  # indice caricacato
    NO_FILE = 1  # la cartella indicata non contiene file
    NO_FOLDER = 2  # manca il nome della cartella o questa non è una cartella
    OLD_INDEX = 3  # indice presente ma non aggiornato
    def __init__(self, parent, path=''):
        self.parent = parent
        self.path = path
        self.print = None
        self.clear()

        self.nth = 12
        self.inp = Queue(self.nth)
        self.lock = Lock()

    def clear(self):
        self.artists = artists()
        self.albums = albums()
        self.tracks = tracks()
        self.album_artist = album_artist()
        self.album_track = album_track()

    def init(self, folder):
        if folder == '' or os.path.isdir(folder) is False:
            return Music.NO_FOLDER

        self.parent.ini.set('CONF', 'last_folder', folder)
        self.parent.ini.save()
        hash = hashlib.md5(folder.encode('utf-8')).hexdigest()

        self.clear()
        jf = os.path.join(folder, 'index.json')
        if os.path.isfile(jf) is False:
            return Music.NO_INDEX

        # trova il file modificato più di recente
        lst = list(find_last(folder).values())
        if len(lst) == 0:
            return Music.NO_FILES
        lst = lst[0]

        # trova la data di ultima modifica registrata
        lst_t = self.parent.ini.get('CONF', hash)
        if lst_t == '':
            return Music.NO_INDEX
        if float(lst) > float(lst_t):
            return Music.OLD_INDEX  # l'indice va rigenerato
        self.load(jf)
        self.path = folder
        return Music.INDEX_LOADED  # non ci sono state modifiche si può caricare l'indice

    def index(self, print, folder):
        if self.init(folder) is True:
            return
        if folder == '':
            return
        self.path = folder

        self.print = print
        self.searchers = []
        for i in range(self.nth):
            name = 'searcher {}'.format(i)
            searcher = Thread(target=self.process, args=(name,))
            searcher.start()
            self.searchers.append(searcher)

        self.print('Start')

        t0 = time.monotonic()
        self.get_mp3(self.path)

        for searcher in self.searchers:
            self.inp.put(('kill', ''))

        for searcher in self.searchers:
            searcher.join()

        t1 = time.monotonic()
        self.print('end ' + str(t1 - t0))

        jf = os.path.join(folder, 'index.json')
        self.save(jf)
        v = os.path.getmtime(jf)
        hash = hashlib.md5(folder.encode('utf-8')).hexdigest()
        self.parent.ini.set('CONF', hash, str(v))
        self.parent.ini.save()

    def process(self, nome):
        count = 0
        while True:
            try:
                t = self.inp.get(timeout=0.1)
                self.inp.task_done()
                if t[0] == 'kill':
                    break
                path = os.path.join(t[0], t[1])
                try:
                    brano = eyed3.load(path)
                    qq = brano.info.time_secs
                except:
                    continue
                if brano is not None and brano.tag is not None:
                    if brano.tag.title is None:
                        brano.tag.title, _ = os.path.splitext(t[1])
                    if brano.tag.album is None:
                        brano.tag.album = os.path.basename(t[0])
                    self.add_track(brano.tag, path, brano.info.time_secs)
                    count += 1
            except Empty:
                continue
        a = 0
    def get_mp3(self, path):
        for root, dirs, files in os.walk(path):
            self.print(root)
            for file in files:
                self.inp.put((root, file))

    def add_track(self, tag, path, time_secs):
        with self.lock:
            id_artist = self.artists.add(tag.artist)
            id_album = self.albums.add(tag, path)
            self.album_artist.add(id_album, id_artist)
            id_track = self.tracks.add(tag, time_secs)
            self.album_track.add(id_album, id_track)

    def get_artists(self):
        v = [a for a in self.artists.name.keys()]
        return v

    def find_albums(self, artist):
        if artist in self.artists.name.keys():
            id = self.artists.name[artist]
            albums_id = self.album_artist.find_albums(id)
            albums = self.albums.find(albums_id)
            return albums
        return []

    def find_tracks(self, album, art=''):
        tracks = []
        if album in self.albums.title.keys():
            alb = self.albums.title[album]
            tracks_id = self.album_track.find_tracks(alb.id)
            tracks = self.tracks.find(tracks_id, art)
        return tracks

    def find_artist_by_album(self, id):
        for t in self.album_artist.a_a:
            if id == t[0]:
                for k, v in self.artists.name.items():
                    if v == t[1]:
                        return k
        return None

    def find_pic(self, album):
        if album in self.albums.title.keys():
            alb = self.albums.title[album]
            brano = eyed3.load(alb.path)
            if len(brano.tag.images) > 0:
                return brano.tag.images[0].image_data
        return None

    def save(self, path):
        r = []
        r.append(self.artists.save())
        r.append(self.albums.save())
        r.append(self.album_artist.save())
        r.append(self.tracks.save())
        r.append(self.album_track.save())
        with open(path, 'w') as fp:
            json.dump(r, fp, indent=4)
        fp.close

    def load(self, path):
        with open(path, 'r') as fp:
            try:
                data = json.load(fp)
            except json.JSONDecodeError as js:
                return

            a = 0
        self.artists.load(data[0])
        self.albums.load(data[1])
        self.album_artist.load(data[2])
        self.tracks.load(data[3])
        self.album_track.load(data[4])

        fp.close

class artists:
    def __init__(self):
        self.name = {}
        self.id = 0

    def add(self, nome):
        if nome in self.name.keys():
            return self.name[nome]

        self.id += 1
        self.name[nome] = self.id
        return self.id

    def save(self):
        return json.dumps(self.name, indent=4)

    def load(self, dic):
        self.name = json.loads(dic)
        a = 0

class track:
    def __init__(self, title='', album='', artist='', id=0, file='', num=0, tm_sec=0.):
        self.title = title
        self.album = album
        self.artist = artist
        self.id = id
        self.file = file
        self.num = num
        self.tm_sec = tm_sec

    def set(self, value):
        self.title = value['title']
        self.album = value['album']
        self.artist = value['artist']
        self.id = value['id']
        self.file = value['file']
        self.num = value['num']
        self.tm_sec = value['tm_sec']


class tracks:
    def __init__(self):
        self.name = {}
        self.id = 0

    def add(self, tag, time_secs):
        #tag.title, tag.album, tag.artist, tag.file_info.name, tag.track_num.count, time_secs
        #if title is None or album is None:
        #    a = 0
        nome = tag.title + '@' + tag.album
        if nome in self.name.keys():
            return self.name[nome].id

        self.id += 1
        self.name[nome] = track(tag.title, tag.album, tag.artist, self.id, tag.file_info.name, tag.track_num.count, time_secs)
        return self.id

    def find(self, ids, art=''):
        tr = [v for v in self.name.values() if v.id in ids]
        if tr[0].num is not None:
            tr.sort(key=lambda x: x.num)
        return [t.title for t in tr if art in t.artist]
    def size(self):
        return len(self.name)

    def save(self):
        return json.dumps({i: j.__dict__ for i, j in self.name.items()}, indent=4)

    def load(self, dic):
        dd = json.loads(dic)
        for key, value in dd.items():
            trk = track()
            trk.set(value)
            self.name[key] = trk
        a = 0


class album:
    def __init__(self, title='', year=0, id=0, path=''):
        self.title = title
        self.year = year
        self.id = id
        self.path = path

    def set(self, value):
        self.title = value['title']
        self.year = value['year']
        self.id = value['id']
        self.path = value['path']

    def save(self, fp):
        jstr = json.dumps({'title': self.title, 'year': self.year, 'id': self.id, 'path': self.path})


class albums:
    def __init__(self):
        self.title = {}
        self.id = 0

    def add(self, tag, path):
        title = tag.album
        if title in self.title.keys():
            return self.title[title].id

        self.id += 1

        year = 1900
        try:
            year = tag.recording_date.year
        except:
            if isinstance(tag.recording_date, int):
                year = tag.recording_date

        #path = os.path.dirname(path)
        self.title[title] = album(title, year, self.id, path) #tag.recording_date
        return self.id

    def find(self, ids):
        albums = [v for v in self.title.values() if v.id in ids]
        if albums[0].year is not None:
            albums.sort(key=lambda x: x.year)
        return albums

    def save(self):
        for i, j in self.title.items():
            a = i
            b = j.__dict__
            c = 0
        return json.dumps({i:j.__dict__ for i, j in self.title.items()}, indent=4)

    def load(self, dic):
        dd = json.loads(dic)
        for key, value in dd.items():
            alb = album()
            alb.set(value)
            self.title[key] = alb


class album_artist:
    def __init__(self):
        self.a_a = []

    def add(self, album, artist):
        t = (album, artist)
        if t not in self.a_a:
            self.a_a.append(t)

    def find_albums(self, id):
        v = [q[0] for q in self.a_a if q[1] == id]
        return v

    def save(self):
        return json.dumps(self.a_a, indent=4)

    def load(self, lst):
        self.a_a = json.loads(lst)



class album_track:
    def __init__(self):
        self.a_t = []

    def add(self, album, trck):
        t = (album, trck)
        if t not in self.a_t:
            self.a_t.append(t)

    def find_tracks(self, album_id):
        v = [t[1] for t in self.a_t if t[0] == album_id]
        return v

    def save(self):
        return json.dumps(self.a_t, indent=4)

    def load(self, lst):
        self.a_t = json.loads(lst)

'''
def music_index(folderpath):
    m = music(folderpath)
    MusicIndexDlg.run(None, m)

    a = 0
'''