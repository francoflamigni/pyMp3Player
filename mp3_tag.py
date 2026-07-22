from PyQt6.QtCore import QObject, pyqtSignal
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from tinytag import TinyTag

import os
from threading import Thread, Lock
from queue import Empty, Queue
import json
import glob
from pyMyLib.utils import ts_date2, iniConf, find_last
import hashlib
import time
from collections import defaultdict

GENRE = [
    'Pop', 'Pop-Folk',
    'Rock', 'Hard Rock', 'Folk-Rock', 'Progressive Rock', 'Psychedelic Rock', 'Symphonic Rock',
    'Punk Rock', 'Rock & Roll', 'Classic Rock',
    'Beat', 'Heavy Metal', 'Folk', 'Celtic', 'Jazz', 'Acid Jazz', 'Blues', 'Gospel', 'Soul', 'Swing', 'New Wave',
    'Latin', 'Punk', 'Ethnic', 'Classical', 'Baroque', 'Opera', 'Chamber Music', 'Sonata', 'Symphony',
    'A Cappella', 'Country', 'Dance', 'Merengue', 'Salsa', 'Disco', 'Funk', 'Hip-Hop', 'Metal', 'New Age',
    'Rap', 'Reggae', 'Techno', 'Fusion', 'Musical', 'Audiobook', 'Soundtrack'
]

class Music(QObject):
    NO_INDEX = -1  # manca l'indice
    INDEX_LOADED = 0  # indice caricacato
    NO_FILE = 1  # la cartella indicata non contiene file
    NO_FOLDER = 2  # manca il nome della cartella o questa non è una cartella
    OLD_INDEX = 3  # indice presente ma non aggiornato
    artists_ready = pyqtSignal()
    def __init__(self, conf: iniConf, path=''):
        super().__init__()
        self.conf = conf
        self.path = path
        self.print = None
        self.clear()

        self.nth = 12
        self.inp = Queue(self.nth)
        self._anomalie = Queue(9000)
        self.lock = Lock()

    def clear(self):
        self.artists = artists()
        self.albums = albums()
        self.tracks = tracks()
        self.album_artist = album_artist()
        self.album_track = album_track()
        self.artist_genre = defaultdict(set)
        self.genre = set()

    def init(self, folder):
        if folder == '' or os.path.isdir(folder) is False:
            return Music.NO_FOLDER

        self.conf.set('CONF', 'last_folder', folder)
        self.conf.save()
        hash = hashlib.md5(folder.encode('utf-8')).hexdigest()

        self.clear()
        jf = os.path.join(folder, 'index.json')
        if os.path.isfile(jf) is False:
            return Music.NO_INDEX

        # trova il file modificato più di recente
        lst = list(find_last(folder).values())
        if len(lst) == 0:
            return Music.NO_FILE
        lst = lst[0]

        # trova la data di ultima modifica registrata
        lst_t = self.conf.get('CONF', hash)
        if lst_t == '':
            return Music.NO_INDEX
        if float(lst) > float(lst_t):
            return Music.OLD_INDEX  # l'indice va rigenerato

        self.load(jf)
        self.path = folder
        return Music.INDEX_LOADED  # non ci sono state modifiche si può caricare l'indice

    def index(self, print, folder):
        '''
        print('Attendi...')
        if self.init(folder) == Music.INDEX_LOADED:
            print(folder)
            return
        if folder == '':
            return
        '''
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
        self.conf.set('CONF', hash, str(v))
        self.conf.save()

    def get_generi(self):
        for t in self.tracks.name.values():
            if t.genre:
                self.genre.add(t.genre)
                self.artist_genre[t.artist].add(t.genre)

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
                    brano = self._load_tag(path)
                except Exception as e:
                    ext = os.path.splitext(path)[1].lower()
                    if ext == '.mp3' or ext == '.flac':
                        self._anomalie.put(path + ' tag error')
                    continue

                self.add_track(brano, path)
                count += 1
            except Empty:
                continue
            except Exception as e:
                a = 0
        a = 0
    def _load_tag(self, path):
        if path.endswith('.flac'):
            b = FLAC(path)
            brano = {
                'artista': b.get('artist', [''])[0],
                'album': b.get('album', [''])[0],
                'titolo': b.get('title', [''])[0],
                'anno': b.get('date', [''])[0][:4],
                'genere': b.get('genre', [''])[0],
                'numero': b.get('tracknumber', ['0'])[0].split('/')[0],
                'durata_sec': b.info.length,
                'filename': path,
            }
        else:
            # Esempio per 12.000 file
            tag = TinyTag.get(path)

            brano = {
                'artista': tag.artist,
                'album': tag.album,
                'titolo': tag.title,
                'anno': tag.year[:4] if tag.year else '',
                'genere': tag.genre,
                'numero': tag.track,
                'durata_sec': tag.duration,  # Durata in secondi (float)
                'filename': path,
            }

        mes = []
        if not brano['artista']:
            mes.append('no artist')
        if not brano['album']:
            mes.append('no album')
        if not brano['titolo']:
            mes.append('no title')
        if not brano['anno']:
            mes.append('no year')
        if not brano['numero']:
            mes.append('no num')
        a = 0
        if mes:
            mes.insert(0, path)
            mes = '\n'.join(mes)
            self._anomalie.put(mes)
            raise Exception(mes)
        return brano

    def get_mp3(self, path):
        last_update = 0
        for root, dirs, files in os.walk(path):
            now = time.monotonic()
            if now - last_update > 0.1:
                self.print(os.path.basename(root))
                last_update = now
            for file in files:
                self.inp.put((root, file))

    def add_track(self, tags, path):
        with self.lock:
            id_artist = self.artists.add(tags['artista'])
            id_album = self.albums.add(tags, path)
            self.album_artist.add(id_album, id_artist)
            id_track = self.tracks.add(tags)
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

    # ritorna l'oggetto traccia dato il titolo dell'a
    def find_tracks(self, album, art=''):
        tracks = []
        alb_art = album + '@' + art
        if alb_art in self.albums.title.keys():
            alb = self.albums.title[alb_art]
            tracks_id = self.album_track.find_tracks(alb.id)
            tracks = self.tracks.find(tracks_id, art)
        return tracks

    def find_tracks_ext(self, album, art=''):
        tracks = []
        alb = {}
        alb_art = album + '@' + art
        if alb_art in self.albums.title.keys():
            alb = self.albums.title[alb_art]
            tracks_id = self.album_track.find_tracks(alb.id)
            tracks = self.tracks.find_ext(tracks_id, art)
        return tracks, alb

    def find_artist_by_album(self, id_album):
        for t in self.album_artist.a_a:  # t[0] id album, t[1] id artista
            if id_album == t[0]:
                for k, v in self.artists.name.items():
                    if v == t[1]:
                        return k
        return None

    def find_pic(self, album, art=''):
        alb_art = album + '@' + art
        if alb_art in self.albums.title.keys():
            alb = self.albums.title[alb_art]
            return self.find_pic_by_file(alb.path.lower())
        return None

    def find_pic_by_file(self, path):
        img_data = None
        try:
            if path.endswith('.mp3'):
                audio = MP3(path)
                for key in audio.tags.keys():
                    if key.startswith('APIC'):
                        img_data = audio.tags[key].data
            elif path.endswith('.flac'):
                audio = FLAC(path)
                if audio.pictures:
                    img_data = audio.pictures[0].data
        except Exception as e:
            pass
        return img_data

    def save(self, path):
        data = {
            "artists": self.artists.save(),
            "albums": self.albums.save(),
            "tracks": self.tracks.save()
        }

        with open(path, 'w', encoding='utf-8') as fp:
            json.dump(data, fp, indent=4, ensure_ascii=False)
        #fp.close

    def load(self, path):
        with open(path, 'r', encoding='utf-8') as fp:
            try:
                data = json.load(fp)
            except json.JSONDecodeError as js:
                return

        self.artists.load(data.get("artists", {}))
        self.artists_ready.emit()
        self.albums.load(data.get("albums", {}))
        self.tracks.load(data.get("tracks", {}))

        # 2. Pulisci le relazioni
        self.album_artist.a_a.clear()
        self.album_track.a_t.clear()

        # 3. Ricostruisci le relazioni iterando sulle tracce appena caricate
        for track_key, trk in self.tracks.name.items():
            # Troviamo l'ID dell'artista
            art_id = self.artists.name.get(trk.artist)

            # Troviamo l'ID dell'album (ricorda che la chiave in albums.title è album@artista)
            album_key = f"{trk.album}@{trk.artist}"
            alb = self.albums.title.get(album_key)

            # Se entrambi esistono, ricreiamo i collegamenti
            if art_id is not None and alb is not None:
                self.album_artist.add(alb.id, art_id)
                self.album_track.add(alb.id, trk.id)

        self.get_generi()


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

    def filter(self, filt):
        dizionario_filtrato = {
            chiave: valore
            for chiave, valore in self.name.items()
            if chiave in filt
        }
        if dizionario_filtrato:
            self.name = dizionario_filtrato

    def save(self):
        return self.name #json.dumps(self.name, indent=4)

    def load(self, dic):
        #self.name = json.loads(dic)
        self.name = dic
        if self.name:
            self.id = max(self.name.values())

class track:
    def __init__(self, title='', album='', artist='', id=0, file='', num=0, tm_sec=0., genre=''):
        self.title = title
        self.album = album
        self.artist = artist
        self.id = id
        self.file = file
        self.num = num
        self.tm_sec = tm_sec
        self.genre = genre

    def set(self, value):
        self.title = value['title']
        self.album = value['album']
        self.artist = value['artist']
        self.id = value['id']
        self.file = value['file']
        self.num = value['num']
        self.tm_sec = value['tm_sec']
        self.genre = value.get('genre', '')


class tracks:
    def __init__(self):
        self.name = {}
        self.id = 0

    def add(self, tags):
        nome = tags['titolo'] + '@' + tags['album']
        if nome in self.name.keys():
            return self.name[nome].id

        self.id += 1
        genre = ''
        if tags['genere']:
            # L'attributo .name decodifica automaticamente il codice numerico
            # (es. 12 -> 'Other') o restituisce la stringa se non è numerico.
            genre = tags['genere']
        self.name[nome] = track(tags['titolo'], tags['album'], tags['artista'], self.id, tags['filename'], tags['numero'], tags['durata_sec'], genre)
        return self.id

    ''' Ritorna una lista di tracce dati i loro id '''
    def find(self, ids, art=''):
        tr = [v for v in self.name.values() if v.id in ids]
        #if tr[0].num is not None:
        tr.sort(key=lambda x: int(x.num) if (x.num and str(x.num).isdigit()) else 0)
        return [t.title for t in tr if art in t.artist]

    def find_ext(self, ids, art=''):
        tr = [v for v in self.name.values() if v.id in ids]
        #if tr[0].num is not None:
        tr.sort(key=lambda x: int(x.num) if (x.num and str(x.num).isdigit()) else 0)
        return [t for t in tr if art in t.artist]

    def size(self):
        return len(self.name)

    def save(self):
        return {i: j.__dict__ for i, j in self.name.items()} #json.dumps({i: j.__dict__ for i, j in self.name.items()}, indent=4)

    def load(self, data_dict):
        self.name.clear()

        for key, value in data_dict.items():
            trk = track()
            trk.set(value)
            self.name[key] = trk

        # Allinea il contatore degli ID alla traccia con ID più alto
        if self.name:
            self.id = max(trk.id for trk in self.name.values())

        '''
        dd = json.loads(dic)
        for key, value in dd.items():
            trk = track()
            trk.set(value)
            self.name[key] = trk
        a = 0
        '''


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

    #def save(self, fp):
    #    jstr = json.dumps({'title': self.title, 'year': self.year, 'id': self.id, 'path': self.path})


class albums:
    def __init__(self):
        self.title = {}
        self.id = 0

    def add(self, tags, path):
        title = tags['album'] + '@' + tags['artista']
        if title in self.title.keys():
            return self.title[title].id
        self.id += 1

        self.title[title] = album(tags['album'], tags['anno'], self.id, path)
        return self.id

    ''' Ritorna un elenco di album dato un elenco di id di album '''
    def find(self, ids):
        albums = [v for v in self.title.values() if v.id in ids]
        #if albums[0].year is not None:
        try:
            albums.sort(key=lambda x: int(x.year))
        except:
            pass
        return albums

    def save(self):
        return {i:j.__dict__ for i, j in self.title.items()} #json.dumps({i:j.__dict__ for i, j in self.title.items()}, indent=4)

    def load(self, data_dict):
        self.title.clear()  # Buona pratica per evitare rimasugli in memoria

        for key, value in data_dict.items():
            alb = album()
            alb.set(value)
            self.title[key] = alb

        # Allinea il contatore degli ID all'album con ID più alto
        if self.title:
            self.id = max(alb.id for alb in self.title.values())

        '''
        dd = json.loads(dic)
        for key, value in dd.items():
            alb = album()
            alb.set(value)
            self.title[key] = alb
        '''


class album_artist:
    def __init__(self):
        self.a_a = []

    def add(self, album, artist):
        t = (album, artist)
        if t not in self.a_a:
            self.a_a.append(t)

    ''' Ritorna gli id degli album del''artista individuato dal suo id'''
    def find_albums(self, id):
        v = [q[0] for q in self.a_a if q[1] == id]
        return v

    '''
    def save(self):
        return json.dumps(self.a_a, indent=4)

    def load(self, lst):
        self.a_a = json.loads(lst)
    '''



class album_track:
    def __init__(self):
        self.a_t = []

    def add(self, album, trck):
        t = (album, trck)
        if t not in self.a_t:
            self.a_t.append(t)

    ''' Ritorna tutte le tracce di un album'''
    def find_tracks(self, album_id):
        v = [t[1] for t in self.a_t if t[0] == album_id]
        return v

    '''
    def save(self):
        return json.dumps(self.a_t, indent=4)

    def load(self, lst):
        self.a_t = json.loads(lst)
    '''
