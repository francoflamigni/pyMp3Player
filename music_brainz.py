import musicbrainzngs

from difflib import SequenceMatcher
import time

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

    def setup_musicbrainz(self):
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
            while True:
                artists = musicbrainzngs.search_artists(
                    query=self.artist_name,
                    offset=offset,
                    limit=limit
                )
                for artist in artists['artist-list']:
                    if similar(artist['name'], self.artist_name):
                        self.album['artist'] = artist['name']
                        self.id_artist = artist['id']
                        return True

                if len(artists['artist-list']) < limit:
                    break
                offset += limit
        except Exception as e:
            self.errMes = e
        return False

    '''
    ricerca gli album dato l'id di un artista
    '''
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

    '''
    ritorna l'elenco delle tracce dato l'id di un album
    '''
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

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPlainTextEdit
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QBrush, QTextCharFormat, QColor, QFont, QFontMetrics

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

        self.setWindowTitle('info')
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

    if album_details is not None:
        AlbumInfoDlg.run(album_details, mi.get_album_detail_string)

    a = 0



