import random

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QAbstractItemView, QTableWidgetItem, QPushButton, \
    QHeaderView

from mp3_tag import Music

class GeneratorePesato:
    def __init__(self, attori):
        """
        attori: lista di dizionari {'nome': str, 'peso': float}
        """
        self.attori = attori
        self.totale = sum(a['peso'] for a in attori)

    def seleziona(self):
        """Seleziona un attore in base ai pesi"""
        # Genera un numero casuale tra 0 e il totale dei pesi
        casuale = random.random() * self.totale

        # Trova l'attore corrispondente
        for attore in self.attori:
            casuale -= attore['peso']
            if casuale <= 0:
                return attore['nome']

        # Fallback (non dovrebbe mai accadere)
        return self.attori[-1]['nome']

def get_casual(item):
    n = len(item) - 1
    casuale = int(random.random() * n)
    return item[casuale]

def Create_playlist(index: Music, preference, duration):
    gen = GeneratorePesato(preference)

    goon = True
    tot = 0
    play = []
    while goon:
        artist = gen.seleziona()
        if artist in index.artists.name.keys():
            albums = index.find_albums(artist)
            album = get_casual(albums)
            tracks = index.find_tracks(album.title, artist)
            track = get_casual(tracks)
            dur = index.tracks.name[track + '@' + album.title].tm_sec
            tot = tot + dur
            if tot > duration:
                goon = False
            else:
                play.append((artist, album.title, track))
            a =0

    return play

class PlayListDlg(QDialog):
    def __init__(self, parent, index: Music):
        super().__init__(parent)
        self.index = index
        self.setWindowTitle("Crea Playlist")
        self.setMinimumSize(300, 500)
        self.setup_ui()

    def setup_ui(self):
        vlayout = QVBoxLayout(self)
        self.table = QTableWidget(self)
        self.fields = ["Artista", "Peso"]
        self.table.setColumnCount(len(self.fields))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 60)

        self.table.setShowGrid(True)
        for artist in self.index.artists.name.keys():
            numRows = self.table.rowCount()
            self.table.insertRow(numRows)
            qi = QTableWidgetItem(artist)
            self.table.setItem(numRows, 0, qi)

        vlayout.addWidget(self.table)

        bt_crea = QPushButton()
        bt_crea.setText("Crea Playlist")
        bt_crea.clicked.connect(self.crea)

        vlayout.addWidget(bt_crea)

    def crea(self):
        numRows = self.table.rowCount()
        preferences = []
        for row in range(numRows):
            try:
                artist = self.table.item(row, 0).text()
                peso = self.table.item(row, 1).text()
                if peso:
                    preferences = preferences + [{'nome': artist, 'peso': int(peso)}]
            except:
                continue
        duration = 5400  # durata in secondi
        a = 0
        self.list = Create_playlist(self.index, preferences, duration)
        stat = {}
        for t in self.list:
            if t[0] in stat.keys():
                n = stat[t[0]]
                stat[t[0]] = n + 1
            else:
                stat[t[0]] = 1

        self.done(1)

    def get_playlist(self):
        return self.list


