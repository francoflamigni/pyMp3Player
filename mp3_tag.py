import eyed3
import os
from threading import Thread, Lock
from queue import Empty, Queue
import json
import glob
from dialogs import MusicIndexDlg
from utils import ts_date2
import hashlib
from PyQt6.QtWidgets import QFileDialog

def find_last(path):
    f = os.path.join(path, '**')
    list_of_files = glob.glob(f, recursive=True)
    latest_file = max(list_of_files, key=os.path.getctime)
    r = os.path.relpath(latest_file, path)
    v = os.path.getctime(latest_file)
    t = ts_date2(v)
    return {r: v}
class music:
    def __init__(self, parent, path=''):
        self.parent = parent
        self.path = path
        self.print = None
        self.artists = artists()
        self.albums = albums()
        self.tracks = tracks()
        self.album_artist = album_artist()
        self.album_track = album_track()
        self.path = path
        self.nth = 12
        self.inp = Queue(self.nth)
        self.lock = Lock()
        last_folder = self.parent.ini.get('CONF', 'last_folder')

        MusicIndexDlg.run(parent, self, last_folder)

    def index(self, print, folder):
        #folder = QFileDialog.getExistingDirectory(self.parent, 'Select Folder', last_folder, options=QFileDialog.Option.DontUseNativeDialog)
        if folder == '':
            return
        self.path = folder
        self.parent.ini.set('CONF', 'last_folder', folder)
        self.parent.ini.save()
        jf = os.path.join(self.path, 'index.json')

        lst = list(find_last(self.path).values())
        if len(lst) > 0:
            lst = lst[0]
        hash = hashlib.md5(self.path.encode('utf-8')).hexdigest()
        lst_t = self.parent.ini.get('CONF', hash)
        if lst_t != '':
            if float(lst) <= float(lst_t):
                self.load(os.path.join(self.path, 'index.json'))
                return

        self.print = print
        self.searchers = []
        for i in range(self.nth):
            name = 'searcher {}'.format(i)
            searcher = Thread(target=self.process, args=(name,))
            searcher.start()
            self.searchers.append(searcher)

        self.print('Start')

        self.get_mp3(self.path)

        for searcher in self.searchers:
            self.inp.put(('kill', ''))

        for searcher in self.searchers:
            searcher.join()

        self.print('end')

        self.save(jf)
        v = os.path.getctime(jf)
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
                brano = eyed3.load(path)
                if brano is not None and brano.tag is not None:
                    if brano.tag.title is None:
                        brano.tag.title, _ = os.path.splitext(t[1])
                    if brano.tag.album is None:
                        brano.tag.album = os.path.basename(t[0])
                    self.add_track(brano.tag, path)
                    count += 1
            except Empty:
                continue
        a = 0
    def get_mp3(self, path):
        for root, dirs, files in os.walk(path):
            if self.tracks.size() > 200:
                return
            self.print(root)
            for file in files:
                a = 0
                self.inp.put((root, file))

            #for dir in dirs:
            #    self.get_mp3(os.path.join(root, dir))

    def add_track(self, tag, path):
        with self.lock:
            id_artist = self.artists.add(tag.artist)
            id_album = self.albums.add(tag.album, path)
            self.album_artist.add(id_album, id_artist)
            id_track = self.tracks.add(tag.title, tag.album, tag.file_info.name)
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

    def find_tracks(self, album):
        tracks = []
        if album in self.albums.title.keys():
            alb = self.albums.title[album]
            tracks_id = self.album_track.find_tracks(alb.id)
            tracks = self.tracks.find(tracks_id)
        return tracks

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
            data = json.load(fp)
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
        #return json.dumps({'Artists': self.name}, indent=4)
        return json.dumps(self.name, indent=4)

    def load(self, dic):
        self.name = json.loads(dic)
        a = 0

class track:
    def __init__(self, title, album, id, file):
        self.title = title
        self.album = album
        self.id = id
        self.file = file

    def set(self, value):
        self.title = value['title']
        self.id = value['id']
        self.path = value['path']

class tracks:
    def __init__(self):
        self.name = {}
        self.id = 0

    def add (self, title, album, filename):
        if title is None or album is None:
            a = 0
        nome = title + '@' + album
        if nome in self.name.keys():
            return self.name[nome].id

        self.id += 1
        self.name[nome] = track(title, album, self.id, filename)
        return self.id

    def find(self, ids):
        tracks = [k.split('@')[0] for k, v in self.name.items() if v['id'] in ids]
        return tracks
    def size(self):
        return len(self.name)

    def save(self):
        aa = json.dumps({i:j.__dict__ for i, j in self.name.items()}, indent=4)
        return json.dumps({i:j.__dict__ for i, j in self.name.items()}, indent=4)
        #return json.dumps(self.name, indent=4)


    def load(self, dic):
        dd = json.loads(dic)
        for key, value in dd.items():
            trk = track()
            trk.set(value)
            self.title[key] = trk
        a = 0
    def load(self, dic):
        self.name = json.loads(dic)

class album:
    def __init__(self, title='', id=0, path=''):
        self.title = title
        self.id = id
        self.path = path
    def set(self, value):
        self.title = value['title']
        self.id = value['id']
        self.path = value['path']

    def save(self, fp):
        jstr = json.dumps({'title': self.title, 'id': self.id, 'path': self.path})
class albums:
    def __init__(self):
        self.title = {}
        self.id = 0
    def add(self, title, path):
        if title in self.title.keys():
            return self.title[title].id

        self.id += 1
        self.title[title] = album(title, self.id, path)
        return self.id

    def find(self, ids):
        albums = [k for k, v in self.title.items() if v.id in ids]
        return albums

    def save(self):
        return json.dumps({i:j.__dict__ for i, j in self.title.items()}, indent=4)

    def load(self, dic):
        dd = json.loads(dic)
        for key, value in dd.items():
            alb = album()
            alb.set(value)
            self.title[key] = alb
        a = 0


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
        a = 0

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


def music_index(folderpath):
    m = music(folderpath)
    MusicIndexDlg.run(None, m)

    a = 0
