import asyncio

import musicbrainzngs

from pyMyLib.utils import get_resource_file
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
import time
from datetime import datetime

def similar(a, b, threshold=0.85):
    from difflib import SequenceMatcher
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

class AlbunInfo:
    def __init__(self, artist_name='', album_title='', album_info=[]):
        self.artist_name = artist_name
        self.album_title = album_title
        self.tracks_info = []

class MusicInfo(QObject):
    info_signal = pyqtSignal(int, AlbunInfo)
    def __init__(self, artist_name, album_title):
        super().__init__()
        self.album_info = AlbunInfo(artist_name, album_title)
        self.artist_name = artist_name
        self.album_title = album_title
        self.album = {}
        self.id_artist = None
        self.id_album = None
        self.errMes = ''
        self.finished = False
        self.setup_musicbrainz()

    def album_details2(self):
        from threading import Thread
        Thread(target=self._album_details, daemon=True).start()

    def _album_details(self):
        try:
            self.info_signal.emit(1, self.album_info)
            #res = self.get_release(self.album_info.artist_name, self.album_info.album_title)
            rg_search = musicbrainzngs.search_release_groups(
                artist=self.album_info.artist_name,
                release=self.album_info.album_title,
                limit=1)

            if not rg_search['release-group-list']:
                self.info_signal.emit({})
                return "Album non trovato."

            # 1. Ottieni il Release Group ID (già fatto nel tuo codice)
            rg_id = rg_search['release-group-list'][0]['id']

            # 2. Invece di browse_releases, usa get_release_group_by_id con include=["releases"]
            rg_details = musicbrainzngs.get_release_group_by_id(rg_id, includes=["releases"])

            # 3. Filtra manualmente la lista delle release per trovare quella ufficiale/originale
            releases = rg_details['release-group']['release-list']

            # Filtriamo per status 'Official' e cerchiamo la più vecchia se possibile
            official_releases = [r for r in releases if r.get('status') == 'Official']

            if not official_releases:
                # Se non ce ne sono di ufficiali, prendiamo la prima disponibile
                release_id = releases[0]['id']
            else:
                # Opzionale: potresti voler ordinare per data per prendere la prima stampa
                # Ma per ora prendiamo la prima della lista ufficiale
                release_id = official_releases[0]['id']

            # 4. Ora puoi procedere con la tua chiamata get_release_by_id
            release = musicbrainzngs.get_release_by_id(release_id,
                                                            includes=["recordings", "recording-level-rels",
                                                                      "work-rels"])
            tracks_info = self.album_info.tracks_info
            # Iteriamo sui supporti (CD1, CD2, ecc.) e sulle tracce
            for medium in release['release']['medium-list']:
                for track in medium['track-list']:
                    t = {
                        'recording_id': track['recording']['id'],
                        'title': track['recording']['title'],
                        'duration': track['recording']['length']
                    }
                    tracks_info.append(t)
                self.info_signal.emit(2, self.album_info)

                for t in tracks_info:
                    rec_details = musicbrainzngs.get_recording_by_id(t['recording_id'],
                            includes=["work-rels", "artist-rels"])

                    composers = []
                    lyricists = []
                    if 'work-relation-list' in rec_details['recording']:
                        for work_rel in rec_details['recording']['work-relation-list']:
                            work_id = work_rel['work']['id']

                            # Chiamata per ottenere i crediti dell'opera
                            work_data = musicbrainzngs.get_work_by_id(work_id, includes=["artist-rels"])

                            if 'artist-relation-list' in work_data['work']:
                                for artist_rel in work_data['work']['artist-relation-list']:
                                    role = artist_rel['type']
                                    name = artist_rel['artist']['name']

                                    if role == 'composer':
                                        composers.append(name)
                                    elif role == 'lyricist':
                                        lyricists.append(name)
                        self.info_signal.emit(3, self.album_info)
        except Exception as e:
            self.info_signal.emit(0, self.album_info)

        a = 0
        return

        releases = self.get_release(self.album_info.artist_name, self.album_info.album_title)
        self.get_tracks2(releases[0]['id1'])
        if not self.get_artist():
            self.info_signal.emit({})
            return
        if not self.get_album():
            self.info_signal.emit({})
            return
        self.info_signal.emit(self.album_info)
        if not self.get_tracks():
            self.info_signal.emit(self.album_info)
        if not self.get_tracks_info():
            self.info_signal.emit(self.album_info)

    @staticmethod
    def setup_musicbrainz():
        """Configure the MusicBrainz API client"""
        musicbrainzngs.set_useragent(
            "Euterpe",
            "1.5",
            "tuaemail@example.com"
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

    def get_tracks2(self, id):
        try:
            results = musicbrainzngs.get_release_by_id(id, includes=["recordings"],  # "artist-credits"],
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

        trk = self.album['tracks']
        #query = f"arid:{self.id_artist} AND work:'{self.album['title']}'"
        #ress = musicbrainzngs.search_works(query=query, includes=["artist-rels"], limit = limit, offset = 0)
        a = 0
        try:
            while True:
                result = musicbrainzngs.browse_works(
                    artist=self.id_artist,
                    includes=["release-rels", "artist-rels", "recording-rels"],
                    #includes=["artist-rels"],
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

        #releases = self.get_release()
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

    ''' testo html da info struttura '''
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

    def get_cover_info(self, release_id):
        # Usa get_image_list di musicbrainzngs
        image_data = musicbrainzngs.get_image_front(release_id)
        return image_data

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


    def detect_info_by_metadata(self, df, artist=None, album=None):
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
                return df

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
            return None
        except Exception as e:
            print(f"Errore ricerca: {e}")
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


from PyQt6.QtCore import QObject, pyqtSignal
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

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPlainTextEdit
from PyQt6.QtCore import QThread, pyqtSignal, QObject
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

def info_aa(info:AlbunInfo):
    a = 0

def brainz(artist, album):
    mi = MusicInfo(artist, album)
    mi.info_signal.connect(info_aa)
    mi.album_details2()
    t0 = time.monotonic()
    album_details = mi.get_album_detail_string()
    dt1 = time.monotonic() - t0

    if album_details:
        AlbumInfoDlg.run(album_details, mi.get_album_detail_string)

    a = 0

import requests
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

    def get_recording_credits(self, recording_id):
        """
        Recupera compositori e parolieri per una specifica registrazione.

        Args:
            recording_id: ID recording MusicBrainz

        Returns:
            dict: {'composers': [...], 'lyricists': [...]}
        """
        url = f"{self.mb_url}/recording/{recording_id}"

        params = {
            'inc': 'artist-credits+work-rels',
            'fmt': 'json'
        }

        try:
            self._wait_rate_limit()

            response = requests.get(
                url,
                params=params,
                headers=self.headers,
                timeout=10
            )

            if response.status_code != 200:
                return {'composers': [], 'lyricists': []}

            data = response.json()

            composers = []
            lyricists = []

            # Le info di compositori/parolieri sono nelle relations
            if 'relations' in data:
                for rel in data['relations']:
                    if rel.get('type') == 'performance' and 'work' in rel:
                        work = rel['work']

                        # Cerca nelle relations del work
                        if 'relations' in work:
                            for work_rel in work['relations']:
                                rel_type = work_rel.get('type')

                                if 'artist' in work_rel:
                                    artist_name = work_rel['artist'].get('name')

                                    if rel_type == 'composer' and artist_name:
                                        if artist_name not in composers:
                                            composers.append(artist_name)

                                    elif rel_type == 'lyricist' and artist_name:
                                        if artist_name not in lyricists:
                                            lyricists.append(artist_name)

            return {
                'composers': composers,
                'lyricists': lyricists
            }

        except Exception as e:
            return {'composers': [], 'lyricists': []}

    def get_album_info(self, release_id, include_credits=False):
        """
        Recupera TUTTE le informazioni dell'album.

        Include: recordings (tracklist con durate), artist-credits, release-groups

        Args:
            release_id: ID release MusicBrainz
            include_credits: Se True, recupera compositori/parolieri (più lento!)

        Returns:
            dict con tutte le info o None
        """

        #aa = self.get_recording_credits(release_id)
        url = f"{self.mb_url}/release/{release_id}"

        # inc= specifica cosa includere nella risposta
        params = {
            #'inc': 'recordings+artist-rels+release-rels+recording-rels+artist-credits+release-groups+labels+recording-level-rels+work-level-rels+work-rels',
            'inc': 'recordings+artist-credits+release-groups+labels',
            'fmt': 'json'
        }

        try:
            self._wait_rate_limit()

            response = requests.get(
                url,
                params=params,
                headers=self.headers,
                timeout=15
            )

            if response.status_code != 200:
                return None

            data = response.json()

            # Estrai informazioni
            album_info = {
                'release_id': release_id,
                'title': data.get('title', 'Unknown'),
                'artist': 'Unknown',
                'date': data.get('date', 'N/A'),
                'year': None,
                'country': data.get('country', 'N/A'),
                'label': None,
                'barcode': data.get('barcode'),
                'total_tracks': 0,
                'total_duration_ms': 0,
                'total_duration_formatted': '0:00',
                'tracks': []
            }

            # Estrai artista
            if 'artist-credit' in data and data['artist-credit']:
                artists = [ac['artist']['name'] for ac in data['artist-credit']
                           if 'artist' in ac]
                album_info['artist'] = ' & '.join(artists)

            # Estrai anno dalla data
            if album_info['date']:
                try:
                    album_info['year'] = int(album_info['date'].split('-')[0])
                except:
                    pass

            # Estrai label
            if 'label-info' in data and data['label-info']:
                labels = [li['label']['name'] for li in data['label-info']
                          if 'label' in li and 'name' in li['label']]
                if labels:
                    album_info['label'] = labels[0]

            # Estrai tracklist
            if 'media' in data:
                track_number = 1
                total_duration_ms = 0

                for medium in data['media']:
                    if 'tracks' in medium:
                        for track in medium['tracks']:
                            recording = track.get('recording', {})
                            recording_id = recording.get('id')

                            # Durata in millisecondi
                            duration_ms = recording.get('length')
                            duration_formatted = 'Unknown'

                            if duration_ms:
                                total_duration_ms += duration_ms
                                # Converti ms in mm:ss
                                seconds = duration_ms // 1000
                                minutes = seconds // 60
                                secs = seconds % 60
                                duration_formatted = f"{minutes}:{secs:02d}"

                            # Artista della traccia (può essere diverso dall'album)
                            track_artist = album_info['artist']
                            if 'artist-credit' in recording and recording['artist-credit']:
                                artists = [ac['artist']['name']
                                           for ac in recording['artist-credit']
                                           if 'artist' in ac]
                                if artists:
                                    track_artist = ' & '.join(artists)

                            # Inizializza crediti
                            composers = []
                            lyricists = []
                            writers = []

                            track_info = {
                                'number': track_number,
                                'title': recording.get('title', 'Unknown'),
                                'artist': track_artist,
                                'duration_ms': duration_ms,
                                'duration': duration_formatted,
                                'recording_id': recording_id,
                                'composers': composers if include_credits else None,
                                'lyricists': lyricists if include_credits else None,
                                'writers': writers if include_credits else None
                            }

                            album_info['tracks'].append(track_info)
                            track_number += 1
                album_info['total_tracks'] = len(album_info['tracks'])
                album_info['total_duration_ms'] = total_duration_ms

                # Formatta durata totale
                if total_duration_ms > 0:
                    total_seconds = total_duration_ms // 1000
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60

                    if hours > 0:
                        album_info['total_duration_formatted'] = f"{hours}:{minutes:02d}:{seconds:02d}"
                    else:
                        album_info['total_duration_formatted'] = f"{minutes}:{seconds:02d}"

            return album_info

        except Exception as e:
            print(f"Errore recupero info: {e}")
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


    def download_album_info(self, artist, album, include_credits=False):
        """
        Recupera informazioni complete dell'album cercando prima la release.

        Args:
            artist: Nome artista
            album: Nome album
            include_credits: Se True, include compositori/parolieri (più lento)

        Returns:
            dict con info complete o None
        """
        print(f"🔍 Cerco: {artist} - {album}")

        mi = MusicInfo(artist, album)
        releases1 = mi.get_release()

        # 1. Cerca release
        releases = self.search_release_fast(artist, album, limit=3)

        if not releases:
            print(f"  ✗ Release non trovata")
            return None

        release = releases[0]
        print(f"  📀 Release trovata: {release['title']} (ID: {release['id']})")

        # 2. Recupera info complete
        print(f"  📥 Recupero informazioni...")
        if include_credits:
            print(f"  📝 Include compositori e parolieri (può richiedere più tempo)")

        info = self.get_album_info(release['id'], include_credits=include_credits)

        if info:
            print(f"  ✅ Informazioni recuperate!")
            print(f"     Tracce: {info['total_tracks']}")
            print(f"     Durata: {info['total_duration_formatted']}")
        else:
            print(f"  ✗ Errore recupero informazioni")

        return info

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

