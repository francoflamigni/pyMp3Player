import musicbrainzngs

from pyMyLib.utils import get_resource_file
from difflib import SequenceMatcher
import time
from datetime import datetime

def similar(a, b, threshold=0.85):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() > threshold

def duration(s):
    tm = '0'
    try:
        t = int(s) / 1000
        m = int(t / 60)
        s = t % (m * 60)
        tm = f"{m}' {s:.1f}''"
    except:
        pass
    return tm

class MusicInfo:
    def __init__(self, artist_name, album_title):
        self.artist_name = artist_name
        self.album_title = album_title
        self.album = {}
        self.id_artist = None
        self.id_album = None
        self.errMes = ''
        self.finished = False
        self.setup_musicbrainz()

    @staticmethod
    def setup_musicbrainz():
        """Configure the MusicBrainz API client"""
        musicbrainzngs.set_useragent(
            "PythonMusicInfo",
            "0.1",
            "https://github.com/yourusername/pythonmusicinfo"
        )

    '''
    Ricerca artista dato il nome
    '''
    def get_artist(self):
        offset = 0
        limit = 100
        try:
            artists = musicbrainzngs.search_artists(
                query=self.artist_name,
                offset=offset,
                limit=limit
            )
            for artist in artists['artist-list']:
                if similar(artist['name'], self.artist_name):
                    self.album['artist'] = artist['name']
                    self.fill_artist(artist)
                    self.id_artist = artist['id']
                    return True
        except Exception as e:
            self.errMes = e
        return False

    def fill_artist(self, artist):
        try:
            if artist['type'] == 'Group':
                if artist['life-span']['end']:
                    self.album['info'] = f"{artist['begin-area']['name']} Dal {artist['life-span']['begin']} al {artist['life-span']['end']}"
                else:
                    self.album['info'] = f"{artist['begin-area']['name']} Dal {artist['life-span']['begin']}"
            else:
                if artist['life-span']['end']:
                    self.album['info'] = (f"Nato a {artist['begin-area']['name']} il {artist['life-span']['begin']} "
                                          f"Morto a {artist['end-area']['name']} il {artist['life-span']['end']}")
                else:
                    self.album['info'] = f"Nato a {artist['begin-area']['name']} il {artist['life-span']['begin']}"
        except:
            pass
        return

    ''' ricerca gli album dato l'id di un artista '''
    def get_album(self):
        offset = 0
        limit = 100
        try:
            while True:
                result = musicbrainzngs.browse_release_groups(
                    artist=self.id_artist,
                    includes=["release-group-rels"],
                    offset=offset,
                    limit=limit
                )
                for release in result["release-group-list"]:
                    if similar(release['title'], self.album_title, 0.70):
                        self.album['title'] = release['title']
                        self.album['date'] = release['first-release-date']
                        self.id_album = release['id']
                        return True

                if len(result["release-group-list"]) < limit:
                    break
                offset += limit
        except Exception as e:
            self.errMes = e

        return False

    ''' ritorna l'elenco delle tracce dato l'id di un album '''
    def get_tracks(self):
        limit = 100
        offset = 0
        try:
            while True:
                result = musicbrainzngs.browse_releases(
                    release_group=self.id_album,
                    includes=["artist-credits"],
                    offset=offset,
                    limit=limit
                )
                id = result["release-list"][0]['id']
                results = musicbrainzngs.get_release_by_id(id, includes=["recordings"], #"artist-credits"],
                                                           release_type="album", release_status="official")
                tracks = {}
                ml = results['release']['medium-list']
                for m in ml:
                    m1 = m['track-list']
                    for m2 in m1:
                        t = {}
                        t['duration'] = duration(m2['length'])
                        tracks[m2['recording']['title']] = t
                        a = 0
                self.album['tracks'] = tracks
                return True
        except Exception as e:
            self.errMes = e
        return False

    def find(self, work, t):
        n1 = 0
        n2 = len(work) -1
        if n2 < 0:
            return None
        while True:
            n = int((n1 + n2) / 2)
            w = work[n]
            if similar(w['title'], t):
                return w
            if t > w['title']:
                n1 = n
            else:
                n2 = n
            if n2 - n1 == 1:
                return None

    def get_tracks_info(self):
        limit = 100
        offset = 0
        works = []
        self.finished = True
        try:
            while True:
                result = musicbrainzngs.browse_works(
                    artist=self.id_artist,
                    includes=["release-rels", "artist-rels", "recording-rels"],
                    offset=offset,
                    limit=limit
                )
                works.extend(result["work-list"])
                # Check if there are more works to retrieve
                if len(result["work-list"]) < limit:
                    break
                offset += limit
        except Exception as e:
            self.errMes = e
            return False

        trk = self.album['tracks']
        for t in trk.keys():
            r = self.find(works, t)
            if r is None:
                continue
            if 'artist-relation-list' not in r.keys():
                continue
            artists = r['artist-relation-list']
            ar = {}
            for artist in artists:
                type = artist['type']
                if type in ar.keys():
                    ar[type] = ar[type] + ', ' + artist['artist']['name']
                else:
                    ar[artist['type']] = artist['artist']['name']
            trk[t]['author'] = ar
        return True

    def get_album_details(self):
        if self.finished:
            return False

        if self.id_artist is None:
            if not self.get_artist():
                return False
            if not self.get_album():
                return False
        elif 'tracks' not in self.album.keys():
            if not self.get_tracks():
                return False
        else:
            if not self.get_tracks_info():
                return False
        return  True

    def get_album_detail_string(self):
        if self.get_album_details():
            html = []
            html.append((f"Title: {self.album['title']}", 'red', 18))
            html.append((f"Artist: {self.album['artist']}", 'black', 14))
            html.append((f"Release date: {self.album['date']}", 'black', 12))
            html.append((f"Tracks:", 'black', 14))

            try:
                i = 1
                for t, val in self.album['tracks'].items():
                    html.append((f"   {i}: {t}  {val['duration']}", 'blu', 12))
                    try:
                        for kk, vv in val['author'].items():
                            html.append((f"     {kk}  {vv}", 'green', 8))
                    except Exception as e:
                        pass
                    i += 1
            except:
                pass
            return html
        return ''


    def get_genres_from_album(self) -> list[tuple[str, int]]:
        """Cerca il genere di un album su MusicBrainz e restituisce (genere, voto)."""

        # Passaggio 1: Ricerca del Gruppo di Pubblicazione (Release Group)
        try:
            # Cerchiamo l'album con l'artista specificato
            result = musicbrainzngs.search_release_groups(
                artist=self.artist_name,
                releasegroup=self.album_title
            )
        except musicbrainzngs.ResponseError as e:
            print(f"Errore di connessione a MusicBrainz: {e}")
            return []

        release_groups = result.get('release-group-list')

        if not release_groups:
            print(f"Nessun Gruppo di Pubblicazione trovato per '{self.artist_name}' - '{self.album_title}'.")
            return []

        # Prendiamo il risultato più probabile (il primo)
        rg_id = release_groups[0]['id']

        # Passaggio 2: Lookup per ottenere i generi
        try:
            # Usiamo l'MBID trovato e includiamo i generi
            rg_details = musicbrainzngs.get_release_group_by_id(
                rg_id,
                includes=['tags']
            )
        except musicbrainzngs.ResponseError as e:
            print(f"Errore durante il recupero dei dettagli (MBID: {rg_id}): {e}")
            return []

        # 3. Accesso ai dati
        # I generi si trovano ora nella lista 'tag-list'
        tags_data = rg_details.get('release-group', {}).get('tag-list', [])

        # Estrai il nome del tag e il suo conteggio (voto)
        genres_list = [(t['name'], int(t['count'])) for t in tags_data]

        # Ordina per voto decrescente
        genres_list.sort(key=lambda item: item[1], reverse=True)

        return genres_list

class CDinfo:
    def __init__(self, drive=''):
        self.drive = drive
        self.discid = None
        MusicInfo.setup_musicbrainz()

    def read_disc_id(self, device):
        import discid

        """
        Legge il DiscID dal CD

        Args:
            device: Percorso del dispositivo CD (None per default)

        Returns:
            dict: Informazioni sul disco
        """
        try:
            # Legge il disco
            if device:
                disc = discid.read(device)
            else:
                disc = discid.read()  # Usa il dispositivo default

            return {
                'id': disc.id,
                'freedb_id': disc.freedb_id,
                'tracks': disc.tracks,
                'sectors': disc.sectors,
                'length': disc.seconds,
                'mcn': disc.mcn,
                'track_count': len(disc.tracks),
                'track_details': [
                    {
                        'number': track.number,
                        'offset': track.offset,
                        'length': track.length,
                        'sectors': track.sectors
                    }
                    for track in disc.tracks
                ]
            }

        except discid.DiscError as e:
            print(f"Errore lettura disco: {e}")
            return None
        except Exception as e:
            print(f"Errore generico: {e}")
            return None

    def search_musicbrainz_by_discid(self, id):
        """
        Cerca informazioni su MusicBrainz usando il DiscID
        """

        try:
            # Cerca il release usando il DiscID
            result = musicbrainzngs.get_releases_by_discid(
                id,
                includes=['artists', 'recordings', 'release-groups']
            )

            if 'disc' in result and 'release-list' in result['disc']:
                releases = result['disc']['release-list']

                release_info = []
                for release in releases:
                    info = {
                        'id': release['id'],
                        'title': release.get('title', 'N/A'),
                        'date': release.get('date', 'N/A'),
                        'country': release.get('country', 'N/A'),
                        'barcode': release.get('barcode', 'N/A'),
                        'genre': release.get('genre', ''),
                        'artists': []
                    }

                    # Artisti
                    if 'artist-credit' in release:
                        for artist_credit in release['artist-credit']:
                            if isinstance(artist_credit, dict) and 'artist' in artist_credit:
                                info['artists'].append({
                                    'name': artist_credit['artist']['name'],
                                    'id': artist_credit['artist']['id']
                                })

                    # Tracce (se disponibili)
                    if 'medium-list' in release:
                        info['tracks'] = []
                        for medium in release['medium-list']:
                            if 'track-list' in medium:
                                for track in medium['track-list']:
                                    recording = track.get('recording', 'N/A')
                                    track_info = {
                                        'position': track.get('position', 'N/A'),
                                        'title': recording.get('title', 'N/A'),
                                        'length': track.get('length', 'N/A')
                                    }

                                    # Artista della traccia
                                    if 'artist-credit' in track:
                                        track_artists = []
                                        for artist_credit in track['artist-credit']:
                                            if isinstance(artist_credit, dict) and 'artist' in artist_credit:
                                                track_artists.append(artist_credit['artist']['name'])
                                        track_info['artists'] = track_artists

                                    info['tracks'].append(track_info)

                    release_info.append(info)

                return {
                    'discid': self.discid,
                    'releases': release_info
                }
            else:
                return {
                    'discid': self.discid,
                    'releases': [],
                    'message': 'Nessun release trovato per questo DiscID'
                }

        except musicbrainzngs.WebServiceError as e:
            print(f"Errore API MusicBrainz: {e}")
            return None
        except Exception as e:
            print(f"Errore ricerca: {e}")
            return None

    def detects_info(self, df):
        mb_info = self.search_musicbrainz_by_discid(df['id'])

        if mb_info and mb_info['releases']:
            print(f"Trovati {len(mb_info['releases'])} release:")

            for i, release in enumerate(mb_info['releases'], 1):
                df["album"] = f"{release['title']}"
                df["artisti"] =  f"{', '.join([a['name'] for a in release['artists']])}"

                anno = datetime.strptime(release['date'], "%Y-%m-%d").year
                df["anno"] = f"{anno}"
                df["genere"] = f"{release['genre']}"

                trk = df['tracce']
                if 'tracks' in release and release['tracks']:
                    for track in release['tracks']:
                        p =  track.get('position', '')
                        if p:
                            p = int(p) -1
                            tr = trk[p]
                            title = track.get('title', 'N/A')
                            tr['titolo'] = title
        return df

    def detects_tracs(self):

        MusicInfo.setup_musicbrainz()
        disc_info = self.read_disc_id(f"{self.drive}:")
        if not disc_info:
            return {}

        trks = []
        trk_start = float(0.)
        for track in disc_info['track_details']:
            start = trk_start
            lenght = float(track['length']) / 75.
            trk = {
                "traccia": f"{track['number']}",
                "durata": lenght,
                "start": start
            }
            trks.append(trk)
            start += lenght

        df = {
            "id": f"{disc_info['id']}",
            "numero tracce": f"{disc_info['track_count']}",
            "durata totale":  f"{disc_info['length']}",
            "tracce": trks
        }
        return self.detects_info(df)


    def search_musicbrainz_by_metadata(self, artist=None, album=None):
        """
        Cerca informazioni su MusicBrainz usando artista e/o titolo album

        Args:
            artist: Nome dell'artista
            album: Titolo dell'album

        Returns:
            dict: Informazioni sui release trovati
        """
        try:
            # Costruisce la query di ricerca
            query_parts = []
            if artist:
                query_parts.append(f'artist:"{artist}"')
            if album:
                query_parts.append(f'release:"{album}"')

            if not query_parts:
                return {
                    'releases': [],
                    'message': 'Specificare almeno artista o album'
                }

            query = ' AND '.join(query_parts)

            # Esegue la ricerca
            result = musicbrainzngs.search_releases(
                query=query,
                limit=10,  # Limita i risultati
                strict=False  # Ricerca fuzzy
            )

            if 'release-list' in result:
                releases = result['release-list']
                release_info = []

                for release in releases:
                    # Per ogni release trovato, ottiene i dettagli completi
                    detailed_release = musicbrainzngs.get_release_by_id(
                        release['id'],
                        includes=['artists', 'recordings', 'release-groups']
                    )

                    rel = detailed_release['release']
                    info = {
                        'id': rel['id'],
                        'title': rel.get('title', 'N/A'),
                        'date': rel.get('date', 'N/A'),
                        'country': rel.get('country', 'N/A'),
                        'barcode': rel.get('barcode', 'N/A'),
                        'score': release.get('ext:score', '0'),  # Score di matching
                        'artists': []
                    }

                    # Artisti
                    if 'artist-credit' in rel:
                        for artist_credit in rel['artist-credit']:
                            if isinstance(artist_credit, dict) and 'artist' in artist_credit:
                                info['artists'].append({
                                    'name': artist_credit['artist']['name'],
                                    'id': artist_credit['artist']['id']
                                })

                    # Tracce
                    if 'medium-list' in rel:
                        info['tracks'] = []
                        for medium in rel['medium-list']:
                            if 'track-list' in medium:
                                for track in medium['track-list']:
                                    recording = track.get('recording', {})
                                    track_info = {
                                        'position': track.get('position', 'N/A'),
                                        'title': recording.get('title', 'N/A'),
                                        'length': track.get('length', 'N/A')
                                    }

                                    # Artista della traccia
                                    if 'artist-credit' in track:
                                        track_artists = []
                                        for artist_credit in track['artist-credit']:
                                            if isinstance(artist_credit, dict) and 'artist' in artist_credit:
                                                track_artists.append(artist_credit['artist']['name'])
                                        track_info['artists'] = track_artists

                                    info['tracks'].append(track_info)

                    release_info.append(info)

                return {
                    'releases': release_info,
                    'count': len(release_info)
                }
            else:
                return {
                    'releases': [],
                    'message': 'Nessun release trovato'
                }

        except musicbrainzngs.WebServiceError as e:
            print(f"Errore API MusicBrainz: {e}")
            return None
        except Exception as e:
            print(f"Errore ricerca: {e}")
            return None



from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPlainTextEdit
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QBrush, QTextCharFormat, QColor, QFont, QFontMetrics, QIcon


class Worker(QThread):
    finished = pyqtSignal(list)  # Signal to notify when the task is done
    def __init__(self, fun):
        super().__init__()
        self.fun = fun
    def run(self):
        a = self.fun()
        if not a:
            a = []
        self.finished.emit(a)


class ResizingPlainTextEdit(QPlainTextEdit):
    def __init__(self, parent):
        super().__init__(parent)
        # Enable auto resize
        self.document().contentsChanged.connect(self.sizeChange)

        # Set some reasonable defaults
        self.setMinimumWidth(200)
        self.setMinimumHeight(50)

    def sizeChange(self):
        # Get the size of the document contents
        font_metrics = QFontMetrics(self.font())

        # Calculate width based on the longest line
        text = self.toPlainText()
        lines = text.split('\n')
        max_width = 0
        for line in lines:
            line_width = font_metrics.horizontalAdvance(line)
            max_width = max(max_width, line_width)

        # Calculate height based on number of lines and line height
        num_lines = len(lines)
        line_height = font_metrics.lineSpacing()
        total_height = num_lines * line_height

        # Add margins and extra space
        margins = self.contentsMargins()
        width = max_width + margins.left() + margins.right() + 30  # Extra space for scrollbar
        height = total_height + margins.top() + margins.bottom() + 15  # Extra padding

        # Add space for the document margins
        doc_margin = 8  # Approximate document margins
        width += doc_margin * 2
        height += doc_margin * 2

        # Set minimum sizes
        width = max(width, self.minimumWidth())
        height = max(height, self.minimumHeight())

        # Set size of the text edit
        self.setMinimumWidth(width)
        self.setMinimumHeight(height)

class AlbumInfoDlg(QDialog):
    def __init__(self, album, run):
        super().__init__()
        self.album = album
        self.run = run
        self.initUI()

    def initUI(self):

        self.setWindowTitle('Album info')
        self.setWindowIcon(QIcon(get_resource_file(__file__, 'icone', 'album_info.png')))
        self.worker = Worker(self.run)  # Create the worker thread
        self.worker.finished.connect(self.update)

        v = QVBoxLayout(self)
        self.h = QHBoxLayout()
        self.txt_box = ResizingPlainTextEdit(self)

        self.update(self.album)

        self.h.addWidget(self.txt_box)
        v.addLayout(self.h)
        self.adjustSize()

    def update(self, mes):
        if mes:
            self.write_text(mes)
            self.worker.start()

    def write_text(self, lines):
        """Write multiple lines of text with different colors"""
        self.txt_box.clear()
        cursor = self.txt_box.textCursor()

        for line, color, font_size in lines:
            # Create a new text format with the specified color
            text_format = QTextCharFormat()
            text_format.setForeground(QBrush(QColor(color)))
            font = QFont()
            font.setPointSize(font_size)
            text_format.setFont(font)

            # Insert the text with the new format
            cursor.insertText(line, text_format)
            cursor.insertBlock()


    @staticmethod
    def run(album, run):
        dlg = AlbumInfoDlg(album, run)
        dlg.exec()

def brainz(artist, album):
    mi = MusicInfo(artist, album)
    t0 = time.monotonic()
    album_details = mi.get_album_detail_string()
    dt1 = time.monotonic() - t0

    if album_details:
        AlbumInfoDlg.run(album_details, mi.get_album_detail_string)

    a = 0



