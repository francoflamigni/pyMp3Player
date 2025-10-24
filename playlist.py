import random
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
