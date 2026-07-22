import os.path

import musicbrainzngs

from pyMyLib.utils import get_resource_file
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QThread, QEvent
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QLabel, QFrame, QScrollArea
from PyQt6.QtGui import QBrush, QTextCharFormat, QColor, QFont, QFontMetrics, QIcon, QPalette

import time
from datetime import datetime
from pyMyLib.qtUtils import center_in_parent
import requests

def similar(a, b, threshold=0.85):
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() > threshold

def duration(s, ms=False):
    tm = '0'
    try:
        t = int(s)
        if ms:
            t = t // 1000
        m = int(t / 60)
        s = t % 60
        tm = f"{m}' {s:02d}''"
    except:
        pass
    return tm

def to_sec(time_str):
    if not isinstance(time_str, str):
        return 0
    clean_str = time_str.replace('"', '').replace("'", " ").strip()

    # Dividiamo la stringa in una lista di sottostringhe
    parts = clean_str.split()

    try:
        if len(parts) >= 2:
            return (int(parts[0]) * 60) + int(parts[1])
        elif len(parts) == 1:
            return int(parts[0])  # Solo secondi o minuti se manca il resto
    except ValueError:
        pass

    return 0

class MusicInfo(QObject):
    info_signal = pyqtSignal(str, str)
    def __init__(self, artist_name, album_title, cache):
        super().__init__()
        self.cache = cache
        self.artist_name = artist_name
        self.album_title = album_title
        self.album = {}
        self.id_artist = None
        self.id_album = None
        self.errMes = ''
        self.setup_musicbrainz()

    @staticmethod
    def setup_musicbrainz():
        """Configure the MusicBrainz API client"""
        musicbrainzngs.set_useragent(
            "Euterpe",
            "1.5",
            "mario.flamigni@gmail.com"
        )

    ''' Ricerca artista dato il nome '''
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
                    self._fill_artist(artist)
                    self.id_artist = artist['id']
                    return True
        except Exception as e:
            print(f"get_artist error: {e}")
            self.errMes = e
        return False

    def _fill_artist(self, artist):
        # Estrazione sicura
        life_span = artist.get('life-span', {})
        begin_area = artist.get('begin-area', {}).get('name', 'Luogo sconosciuto')
        end_area = artist.get('end-area', {}).get('name', 'Luogo sconosciuto')
        begin = life_span.get('begin', 'Data sconosciuta')
        end = life_span.get('end', '')

        if artist.get('type') == 'Group':
            if end:
                self.album['info'] = f"{begin_area} Dal {begin} al {end}"
            else:
                self.album['info'] = f"{begin_area} Dal {begin}"
        else:
            if end:
                self.album['info'] = f"Nato a {begin_area} il {begin} Morto a {end_area} il {end}"
            else:
                self.album['info'] = f"Nato a {begin_area} il {begin}"

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
            print(f"get_album error: {e}")
            self.errMes = e

        return False


    def get_release(self, artist_name, album_title):
        try:
            releases = musicbrainzngs.search_release_groups(
                query=f'artist:"{artist_name}" AND releasegroup:"{album_title}"',
                offset=0,
                limit=5
            )
            return [{
                'id': r['id'],
                'title': r.get('title'),
                'date': r.get('first-release-date'),
                'artist': r.get('artist-credit')[0]['name'],
                'id1':  r.get('release-list')[0]['id'],
            } for r in releases['release-group-list']]
        except Exception as e:
            return []
        a = 0


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
                release_list = result.get("release-list", [])
                if not release_list:
                    return False  # Nessuna release trovata
                id = release_list[0]['id']

                results = musicbrainzngs.get_release_by_id(id, includes=["recordings"], #"artist-credits"],
                                                           release_type="album", release_status="official")
                tracks = []
                ml = results['release'].get('medium-list', [])
                for m in ml:
                    m1 = m.get('track-list', [])
                    for m2 in m1:
                        t = {
                            'title': m2['recording'].get('title', 'Titolo Sconosciuto'),
                            'duration' : duration(m2.get('length', 0), True),
                            'autors' : {}
                        }
                        tracks.append(t)
                self.album['tracks'] = tracks
                return True
        except Exception as e:
            print(f"get_tracks error: {e}")
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

        try:
            while True:
                time.sleep(1)
                result = musicbrainzngs.browse_works(
                    artist=self.id_artist,
                    includes=["release-rels", "artist-rels", "recording-rels"],
                    offset=offset,
                    limit=limit
                )
                works.extend(result.get("work-list", []))
                # Check if there are more works to retrieve
                if len(result.get("work-list", [])) < limit:
                    break
                offset += limit
        except Exception as e:
            print(f"get_tracks_info error: {e}")
            self.errMes = e
            return False

        trk_list = self.album.get('tracks', [])
        for track_dict in trk_list:
            r = self.find(works, track_dict['title'])
            if r is None:
                continue
            if 'artist-relation-list' not in r.keys():
                continue
            artists = r['artist-relation-list']
            ar = {}
            for artist in artists:
                type_art = artist.get('type', 'Unknown')
                if type_art in ar:
                    ar[type_art] = ar[type_art] + ', ' + artist['artist']['name']
                else:
                    ar[type_art] = artist['artist']['name']
            track_dict['author'] = ar
        return True

    def get_album_details(self):
        self.album_info_html()  # per stampare i dati dell'mp3
        if self.get_artist():
            self.album_info_html()

            if self.get_album():
                self.album_info_html()

                if self.get_tracks():
                    self.album_info_html()

                    if self.get_tracks_info():
                        import json
                        self.album_info_html(True)
                        if self.cache:
                            self.cache.set(f"{self.artist_name}@{self.album_title}.info",
                                           json.dumps(self.album, ensure_ascii=False, indent=4))
                        return True
        self.album_info_html(True)
        return False

    def get_html_mes(self, color, size, mes, pos='left', indent=0):
        return f'''<p style="font-family: Arial; color: {color}; font-size: {size}px; text-align: {pos}; text-indent: {indent}px;" >
        {mes}
        </P>'''

    ''' testo html da info struttura '''
    def album_info_html(self, final=False):
        hr_style = f"border: 0; height: 2px; background-color: white; width: 80%;"
        html1 = []

        color = 'green' if not final else 'red'
        html1.append(self.get_html_mes(color, 26, f"Titolo: {self.album['title']}", pos='center'))
        html1.append(self.get_html_mes('white', 20, f"Artista: {self.album['artist']}", pos='center'))
        html1.append(self.get_html_mes('yellow', 14, f"Pubblicato il: {self.album['date']}", pos='center'))
        html1.append(f'<hr style="{hr_style}">')
        html1.append(self.get_html_mes('white', 18, f"Tracce:"))

        html2 = []
        try:
            i = 1
            tot = 0
            for i, track_dict in enumerate(self.album.get('tracks', []), start=1):
                t_title = track_dict['title']
                t_dur = track_dict['duration']
                html2.append(self.get_html_mes('lightblue', 16,
                    f'<span style="color: white;">{i}:</span> {t_title}  <span style="color: white;">{t_dur}</span>', indent=12))
                tot += to_sec(t_dur)
                try:
                    for kk, vv in track_dict.get('author', []).items():
                        html2.append(self.get_html_mes('lightgreen', 12, f"     {kk}  {vv}", indent=18))
                except Exception as e:
                    pass
                i += 1
            html1.insert(3, self.get_html_mes('cyan', 14, f"Durata: {duration(tot)}", pos='center'))
        except Exception as e:
            pass
        self.info_signal.emit('\n'.join(html1), '\n'.join(html2))


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
            dict: Informazioni sul disco: id, n settori offset e start di ogni traccia
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
                    info = self.decode_release(release)
                    release_info.append(info)
                return release_info
            else:
                return []

        except musicbrainzngs.WebServiceError as e:
            print(f"Errore API MusicBrainz: {e}")
            return None
        except Exception as e:
            print(f"Errore ricerca: {e}")
            return None

    ''' Ricerca metadati sul cd artitsta, titolo e titoli tracce '''
    def detects_info_by_id(self, df):
        mb_info = self.search_musicbrainz_by_discid(df['id'])

        if mb_info:
            self.integrateinfo(df, mb_info)

        return df

    def integrateinfo(self, df, releases, id=0):
        for i, release in enumerate(releases):
            df["album"] = f"{release['title']}"
            df["artisti"] = f"{', '.join([a['name'] for a in release['artists']])}"
            df['idr'] = f"{release['id']}"

            try:
                anno = datetime.strptime(release['date'], "%Y-%m-%d").year
            except:
                anno = release['date']
            df["anno"] = f"{anno}"
            df["genere"] = f"{release.get('genre', '')}"

            # Tracce (se disponibili)
            if 'mediums' in release:
                for medium in release['mediums']:
                    if id != 0 and medium['id'] != id:
                        continue

                    trk = df['tracce']
                    df["album"] = f"{medium['title']}"
                    if 'tracks' in medium and medium['tracks']:
                        for track in medium['tracks']:
                            p =  track.get('position', '')
                            if p:
                                p = int(p) -1
                                if p >= len(trk):
                                    continue
                                tr = trk[p]
                                tr['titolo'] = track.get('title', 'N/A')
                                tr['length'] =  track.get('length', 'N/A')
                                tr['position'] = p

                            # Artista della traccia
                                if 'artists' in track:
                                    track_artists = []
                                    for artist_credit in track['artists']:
                                        if isinstance(artist_credit, dict) and 'artist' in artist_credit:
                                            track_artists.append(artist_credit['artist']['name'])
                                        else:
                                            track_artists.append(artist_credit)
                                    tr['artists'] = track_artists
                    break


    def cd_to_internal(self):
        res = self.detects_tracks()
        df = self.detects_info_by_id(res)
        from mp3_tag import track
        trks = []
        if df:
            for i, t in enumerate(df['tracce']):
                tk = track(title=t.get('titolo', ''), album=df.get('album', ''), artist=df.get('artisti', ''), id=0, file='', num=t['traccia'], tm_sec=t['durata'], genre='')
                trks.append(tk)
        return trks, df.get('idr', '')

    ''' individua il numero di tracce, la loro durata e l'offset iniziale se disponibili anche i titoli'''
    def detects_tracks(self):

        MusicInfo.setup_musicbrainz()
        disc_info = self.read_disc_id(f"{self.drive}:")
        if not disc_info:
            return {}

        tot_sec = disc_info['sectors']
        trks = []
        total_length = float(disc_info['length'])
        pre_gap = 0
        for i, track in enumerate(disc_info['track_details']):
            if i == 0:
                pre_gap = float(track['offset'])
            start = (float(track['offset']) - pre_gap) / 75.
            lenght = float(track['length']) / 75.
            if i == len(disc_info['track_details']) - 1:
                sec_utili = tot_sec - pre_gap
                dur_tot = int(sec_utili / 75.)
                lenght = int(lenght)
                start = dur_tot - lenght - 0.5
                a = 0

            trk = {
                "traccia": f"{track['number']}",
                "durata": lenght,
                "start": start
            }
            trks.append(trk)

        df = {
            "id": f"{disc_info['id']}",
            "numero tracce": f"{disc_info['track_count']}",
            "durata totale":  f"{disc_info['length']}",
            "tracce": trks
        }
        return df


    def detect_info_by_metadataX(self, df, artist=None, album=None):
        """
        Cerca informazioni su MusicBrainz usando artista e/o titolo album

        Args:
            artist: Nome dell'artista
            album: Titolo dell'album

        Returns:
            dict: Informazioni sui release trovati
        """

        release_info = []
        try:
            # Costruisce la query di ricerca
            query_parts = []
            if artist:
                query_parts.append(f'artist:"{artist}"')
            if album:
                query_parts.append(f'release:"{album}"')

            if not query_parts:
                return df

            query = ' AND '.join(query_parts)

            # Esegue la ricerca

            result = musicbrainzngs.search_releases(
                query=query,
                limit=10,  # Limita i risultati
                strict=False  # Ricerca fuzzy
            )


            '''
            result = musicbrainzngs.search_releases(
                artist=artist,
                release=album,
                limit=10
            )
            '''

            if 'release-list' in result:
                releases = result['release-list']
                #release_info = []

                for rel in releases:
                      # Per ogni release trovato, ottiene i dettagli completi
                    detailed_release = musicbrainzngs.get_release_by_id(
                        rel['id'],
                        includes=['artists', 'recordings', 'release-groups']
                    )

                    release = detailed_release['release']
                    info = self.decode_release(release)
                    release_info.append(info)

                if df:
                    self.integrateinfo(df, release_info)
                    return df
                else:
                    ID_ARTISTA = release_info[0]['artists'][0]['id']
                    ID_RELEASE = release_info[0]['id']
                    query = f"arid:{ID_ARTISTA} "#AND reid:{ID_RELEASE}"
                    try:
                        ress = musicbrainzngs.search_works(query=query, limit=100, offset=0)
                    except Exception as e:
                        b = 1
                    a = 0
            else:
                return df
        except musicbrainzngs.WebServiceError as e:
            print(f"Errore API MusicBrainz: {e}")
            if release_info:
                if df:
                    self.integrateinfo(df, release_info)
                    return df
                else:
                    ID_ARTISTA = release_info[0]['artists'][0]['id']
                    ID_RELEASE = release_info[0]['id']
                    query = f"arid:{ID_ARTISTA} "#AND reid:{ID_RELEASE}"
                    try:
                        ress = musicbrainzngs.search_works(query=query, limit=100, offset=0)
                    except Exception as e:
                        b = 1
                    a = 0
            return None
        except Exception as e:
            print(f"Errore ricerca: {e}")
            return None

    import time  # Assicurati di importarlo all'inizio del file

    def detect_info_by_metadata(self, df, artist=None, album=None):
        """
        Cerca informazioni su MusicBrainz usando artista e/o titolo album

        Args:
            artist: Nome dell'artista
            album: Titolo dell'album
            df: Oggetto dati (es. DataFrame) da aggiornare

        Returns:
            df aggiornato con le info, oppure df originale se non trova nulla
        """
        # 1. COSTRUZIONE DELLA QUERY
        query_parts = []
        if artist: query_parts.append(f'artist:"{artist}"')
        if album:  query_parts.append(f'release:"{album}"')

        if not query_parts:
            return df

        query = ' AND '.join(query_parts)
        release_info = []

        # 2. CHIAMATE API CON RATE LIMITING PREVENTIVO
        try:
            result = musicbrainzngs.search_releases(
                query=query,
                limit=10,
                strict=False
            )

            if 'release-list' in result:
                for rel in result['release-list']:
                    # PAUSA CRITICA: previene il blocco 'UNEXPECTED_EOF_WHILE_READING'
                    #time.sleep(1)

                    detailed_release = musicbrainzngs.get_release_by_id(
                        rel['id'],
                        includes=['artists', 'recordings', 'release-groups']
                    )

                    release = detailed_release['release']
                    info = self.decode_release(release)
                    release_info.append(info)

        except musicbrainzngs.WebServiceError as e:
            # Se capita un errore, lo notifichiamo ma continuiamo con i dati parziali raccolti
            print(f"Errore API MusicBrainz parziale: {e}")
        except Exception as e:
            print(f"Errore ricerca generico: {e}")
            return None

        # 3. ELABORAZIONE DATI (Eseguita una volta sola, fuori dal try/except)
        if not release_info:
            return df  # Ritorna df intatto se non abbiamo trovato nulla

        if df is not None:
            # Se df esiste, lo integriamo
            self.integrateinfo(df, release_info)
            return df
        else:
            # Se df non esiste, procediamo con la ricerca works
            ID_ARTISTA = release_info[0]['artists'][0]['id']
            work_query = f"arid:{ID_ARTISTA}"

            try:
                # Altra pausa prima di una nuova chiamata API
                #time.sleep(1)
                ress = musicbrainzngs.search_works(query=work_query, limit=100, offset=0)
                # Aggiungi qui la logica per gestire 'ress' se necessario
            except Exception as e:
                print(f"Errore durante search_works: {e}")

            # Cosa dovrebbe ritornare il metodo in questo caso? (Opzionale: return ress)
            return None


    def decode_release(self, release):
        info = {
            'id': release['id'],
            'title': release.get('title', 'N/A'),
            'date': release.get('date', 'N/A'),
            'country': release.get('country', 'N/A'),
            'barcode': release.get('barcode', 'N/A'),
            'genre': release.get('genre', ''),
            #'score': release.get('ext:score', '0'),  # Score di matching
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
            info['mediums'] = []
            for medium in release['medium-list']:
                try:
                    id = medium['disc-list'][0]['id']
                except:
                    id = 0
                m_info = {
                    'id': id,
                    'title': medium.get('title', release['title']),
                    'tracks': []
                }

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

                        m_info['tracks'].append(track_info)
                    info['mediums'].append(m_info)
        return info


class CoverArtSignals(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

class CoverArtWorker(QObject):
    def __init__(self, release_id, save_path, parent=None):
        super().__init__(parent)
        self.signals = CoverArtSignals()
        self.release_id = release_id
        self.save_path = save_path

    def run(self):
        import requests
        """Metodo che esegue il lavoro bloccante (download)."""

        # 1. Costruisce l'URL CAA
        caa_url = f"https://coverartarchive.org/release/{self.release_id}/front"

        try:
            # 2. Effettua la richiesta HTTP
            # Usiamo un timeout per prevenire blocchi indefiniti
            response = requests.get(caa_url, stream=True, timeout=10)

            # Se la richiesta fallisce (es. 404 Not Found se manca la copertina)
            if response.status_code != 200:
                self.signals.error.emit(
                    f"Copertina non trovata (Status Code: {response.status_code})."
                )
                return

            # 3. Salva il contenuto binario nel file
            with open(self.save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # 4. Successo: emetti il percorso del file salvato
            self.signals.finished.emit(self.save_path)

        except requests.exceptions.RequestException as e:
            # 5. Errore: emetti il messaggio d'errore
            self.signals.error.emit(
                f"Errore di rete durante il download: {e}"
            )
        except Exception as e:
            self.signals.error.emit(
                f"Errore imprevisto: {e}"
            )

class Worker(QThread):
    finished = pyqtSignal(bool)  # Signal to notify when the task is done
    def __init__(self, fun):
        super().__init__()
        self.fun = fun
    def run(self):
        self.finished.emit(self.fun())


class HtmlInfoDlg(QDialog):
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent)
        self.parent = parent
        self.initUI()
        self.initWorker(kwargs)

    def initWorker(self, args):
        pass

    def initUI(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setWindowOpacity(0.0)
        # Layout principale della finestra
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.lab1 = QLabel(self)
        self.lab1.setStyleSheet("""
                    background-color: #333; 
                    color: white; 
                    padding: 15px; 
                    border: none;
                """)

        # 1. Creiamo la Scroll Area
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Limiti della finestra
        self.scroll.setMinimumWidth(400)
        self.scroll.setMaximumWidth(600)
        self.scroll.setMinimumHeight(400)
        self.scroll.setMaximumHeight(600)  # Oltre questo appare lo scroll
        self.scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #555;
                background-color: #333;
            }

            QScrollBar:vertical {
                border: none;
                background: #222;       /* Colore del binario */
                width: 10px;            /* Larghezza della barra */
                margin: 0px 0px 0px 0px;
            }

            QScrollBar::handle:vertical {
                background: #555;       /* Colore della maniglia */
                min-height: 20px;
                border-radius: 5px;     /* Rende la barra arrotondata */
            }

            QScrollBar::handle:vertical:hover {
                background: #777;       /* Colore quando ci passi sopra il mouse */
            }

            /* Rimuove i pulsanti freccia sopra e sotto per un look più moderno */
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        # 2. Creiamo la Label che starà dentro lo scroll
        self.content_label = QLabel()
        self.content_label.setTextFormat(Qt.TextFormat.RichText)
        self.content_label.setWordWrap(True)
        self.content_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        # Stile scuro come avevi chiesto
        self.content_label.setStyleSheet("""
                    background-color: #333; 
                    color: white; 
                    padding: 15px; 
                    border: none;
                """)

        # 3. Assembliamo: Label -> ScrollArea -> Layout Finestra
        self.scroll.setWidget(self.content_label)
        v.addWidget(self.lab1)
        v.addWidget(self.scroll)
        self.hide()

    def mousePressEvent(self, event):
        self.close()
        super().mousePressEvent(event)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow():
                #print("1")
                a = 1
            else:
                #print("0")
                a = 0
        super().changeEvent(event)

    def completed(self, res):
        pass

    def update(self, html1, html2):
        if html1:
            self.setWindowOpacity(1.0)
            # Imposta il testo HTML
            self.lab1.setText(html1)
            self.content_label.setText(html2)

            # Chiedi alla finestra di adattarsi al nuovo contenuto
            self.adjustSize()

            # Centra la finestra (usando la tua funzione esterna)
            center_in_parent(self, self.parent)
            self.show()


class AlbumInfoDlg(HtmlInfoDlg):
    @staticmethod
    def run(parent, artist, album, tracks, cache):
        mi = MusicInfo(artist, album.title, cache)
        mi.cache = cache
        mi.parent = parent

        mi.album['title'] = album.title
        mi.album['artist'] = artist
        mi.album['date'] = album.year
        mi.album['tracks'] = []
        for t in tracks:
            mi.album['tracks'].append({
                'title': t.title,
                'duration': duration(t.tm_sec),
                'author': {}
            })
        AlbumInfoDlg(parent, info_music=mi).exec()

    def initWorker(self, kwargs):
        mi = kwargs.get('info_music')
        mi.info_signal.connect(self.update)
        if mi.cache:
            import json
            dati = mi.cache.get( f"{mi.album['artist']}@{mi.album['title']}.info")
            if dati:
                mi.album = json.loads(dati)
                mi.album_info_html(True)
                return

        self.worker = Worker(mi.get_album_details)  # Create the worker thread
        self.worker.finished.connect(self.completed)
        self.worker.start()


class CoverDownloader(QObject):
    cover_ready = pyqtSignal(str, bytes)
    def __init__(self, app='euterpe', ver='1.5', mail='luigi.collini@gmail.com', rate_limit=1.0):
        super().__init__()
        self.headers = {
            'User-Agent': f'{app}/{ver} ( {mail} )',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        self.mb_url = "https://musicbrainz.org/ws/2"
        self.caa_url = "https://coverartarchive.org"
        self.rate_limit = rate_limit
        self.last_mb_request = 0

    def _wait_rate_limit(self):
        """Rispetta il rate limit per MusicBrainz."""
        elapsed = time.time() - self.last_mb_request
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_mb_request = time.time()

    def search_release_fast(self, artist, album, limit=1):
        """
        Ricerca veloce usando l'endpoint search diretto.
        Restituisce solo il release ID, niente altro.
        """
        # Query Lucene ottimizzata
        query = f'artist:"{artist}" AND release:"{album}"'

        url = f"{self.mb_url}/release"
        params = {
            'query': query,
            'limit': limit,  # Solo il primo risultato!
            'fmt': 'json'
        }

        try:
            response = requests.get(
                url,
                params=params,
                headers=self.headers,
                timeout=10
            )

            if response.status_code != 200:
                return None

            data = response.json()
            releases = data.get('releases', [])

            if not releases:
                return None

            # Ritorna solo l'ID
            return [{
                'id': r['id'],
                'title': r.get('title'),
                'score': int(r.get('ext:score', 0))
            } for r in releases]

        except Exception as e:
            print(f"Errore ricerca: {e}")
            return None

    def get_cover(self, release_id, size='500'):
        """
        Download diretto da Cover Art Archive.
        NO rate limiting, NO autenticazione.
        """
        url = f"{self.caa_url}/release/{release_id}/front"
        if size:
            url = f"{url}/-{size}"

        response = requests.get(
            url,
            headers=self.headers,
            timeout=15,
            allow_redirects=True,
            stream=True
        )

        if response.status_code != 200:
            return None

        # Verifica dimensione
        #if len(response.content) < 1000:
        #    return None

        return response.content

    def download_cover(self, artist='', album='', id='', size='500'):
        from threading import Thread
        Thread(target=self._download_cover, args=(artist, album, id), daemon=True).start()

    def _download_cover(self, artist, album, id, size='500'):

        start = time.time()

        t1 = time.time()
        if artist and album:
            try:
                # 1. Ricerca release ID
                release = self.search_release_fast(artist, album)
                if not release or len(release) == 0:
                    elapsed = time.time() - start
                    print(f"  ? Release non trovata ({elapsed:.2f}s)")
                    self.cover_ready.emit("Errore release non trovata", b"")
                    return None

                release_id = release[0]['id']
                t2 = time.time()
                if not release:
                    elapsed = time.time() - start
                    print(f"  ? Release non trovata ({elapsed:.2f}s)")
                    self.cover_ready.emit("Errore release non trovata", b"")
                    return None
            except Exception as e:
                self.cover_ready.emit("Errore release non trovata", b"")
                return None
        elif id:
            release_id = id
        else:
            self.cover_ready.emit("Dati incompleti", b"")
            return None

        try:
            #release_id = release[0]['id']
            data =  self.get_cover(release_id, size)
            if data:
                self.cover_ready.emit("", data)
            else:
                self.cover_ready.emit("Errore", b"")
        except Exception as e:
            self.cover_ready.emit(f"{e}", b"")
            return None

