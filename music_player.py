import os
import time

vlc_path = os.path.join(os.getcwd(), 'exe/VLC')
os.environ['PYTHON_VLC_LIB_PATH'] = os.path.join(vlc_path, 'libvlc.dll')
import vlc

from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QPixmap, QIcon, QPainter, QPen
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QStyle, QPushButton, QLineEdit, QComboBox,
                             QFrame,  QDial, QSlider)

from pyMyLib.qtUtils import set_background
from pyMyLib.utils import iniConf
from dialogs import lyric_song
import scrobbler

def get_tm(secs):
    min = int(secs / 60)
    sec = int(secs) - int(min * 60)
    return "{:02.0F}:{:02.0F}".format(min, sec)


class MusicPlayerDlg(QDialog):
    Mode_None = 0  # nessuna selezione
    Mode_Music = 1  # mp3
    Mode_Radio = 2  # radio
    Mode_Play = 3
    Mode_Pause = 4
    def __init__(self, parent):
        super(MusicPlayerDlg, self).__init__(parent)
        self.wparent = parent

        self.media = None
        self.is_paused = False
        self.tracks = []
        self.index = -1

        self.instance = vlc.Instance(['--gain=40.0', '--audio-visual=visual'] ) # Projectm,goom,visual,glspectrum,none}', '--logfile=vlc-log.txt'])
        self.mediaplayer = self.instance.media_player_new()

        self.mode = MusicPlayerDlg.Mode_None

        self.setObjectName("player_widget")
        set_background(self)

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_ui)

        ''' Parte superiore con copertina e spettro'''
        h3 = QHBoxLayout()
        self.videoframe = QFrame()
        self.videoframe.setMinimumSize(QSize(200, 200))
        self.cover = QLabel()
        self.cover.setMinimumSize(QSize(200, 200))
        self.cover.setMaximumWidth(200)
        h3.addStretch()
        h3.addWidget(self.cover)
        h3.addStretch()
        h3.addWidget(self.videoframe)
        h3.addStretch()

        # control_frame note, play - pause- slider bar
        wdd = self.control_frame()

        equalize_ctrl = Equalizer(self.mediaplayer)

        # volume
        vol = self.volume_ui(equalize_ctrl.get_preset())
        h2 = QHBoxLayout()
        h2.addWidget(equalize_ctrl)
        h2.addLayout(vol)

        v2 = QVBoxLayout(self)
        v2.addLayout(h3)
        v2.addWidget(wdd)
        v2.addLayout(h2)

    def position_slider_ui(self):
        self.positionslider = QSlider(Qt.Orientation.Horizontal, self)
        self.positionslider.setObjectName('slipos')
        self.positionslider.setStyleSheet(slider_style())
        self.positionslider.setToolTip("Position")
        self.positionslider.setMaximum(1000)
        self.positionslider.sliderMoved.connect(self.set_position)
        self.positionslider.sliderPressed.connect(self.set_position)
        self.rt_time = QLabel('', self)
        self.rt_time.setMaximumHeight(self.positionslider.height())
        self.rt_time.setMinimumWidth(30)
        self.t_time = QLabel('', self)
        self.t_time.setMaximumHeight(self.positionslider.height())
        self.t_time.setMinimumWidth(30)
        hs = QHBoxLayout()
        hs.setContentsMargins(1, 1, 1, 1)
        hs.addWidget(self.rt_time)
        hs.addWidget(self.positionslider)
        hs.addWidget(self.t_time)
        return hs

    def set_position(self):
        # Set the movie position according to the position slider.

        # The vlc MediaPlayer needs a float value between 0 and 1, Qt uses
        # integer variables, so you need a factor; the higher the factor, the
        # more precise are the results (1000 should suffice).

        # Set the media position to where the slider was dragged
        self.timer.stop()
        pos = self.positionslider.value()
        self.mediaplayer.set_position(pos / 1000.0)
        self.timer.start()

    def control_frame(self):
        # position slider e tempi totali e parziali
        hs = self.position_slider_ui()

        # play and stop buttons
        hbt = self.play_stop_ui()

        # information line
        self.note = QLineEdit(self)
        self.note.setReadOnly(True)
        self.note.setAlignment(Qt.AlignmentFlag.AlignLeft)

        wdd = QFrame()
        wdd.setObjectName('slFrame')

        wdd.setStyleSheet("QFrame#slFrame {background-color: rgb(220, 220, 220);"
                            "border-width: 1;"
                            "border-radius: 8;"
                            "border-style: solid;"
                            "border-color: rgb(10, 10, 10)}"
                        )

        v = QVBoxLayout()
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.note)
        v.addLayout(hs)
        v.addLayout(hbt)
        v.setSizeConstraint(QHBoxLayout.SizeConstraint.SetMaximumSize) #SetMaximumSize)

        wdd.setLayout(v)
        return wdd

    def play_stop_ui(self):
        self.playbutton = QPushButton(self)
        self.playbutton.setMaximumWidth(30)
        #self.set_play_icon(Player.Mode_Play)
        self.playbutton.clicked.connect(self.play_pause)

        stopbutton = QPushButton(self)
        stopbutton.setMaximumWidth(30)
        stopbutton.setIcon(self.style().standardIcon(getattr(QStyle.StandardPixmap, 'SP_MediaStop')))
        stopbutton.clicked.connect(self.stop)

        self.skipBackwardbutton = QPushButton()
        self.skipBackwardbutton.setMaximumWidth(30)
        self.skipBackwardbutton.setIcon(self.style().standardIcon(getattr(QStyle.StandardPixmap, 'SP_MediaSkipBackward')))
        self.skipBackwardbutton.clicked.connect(lambda: self.skip(-1))

        self.skipFarwardbutton = QPushButton()
        self.skipFarwardbutton.setMaximumWidth(30)
        self.skipFarwardbutton.setIcon(self.style().standardIcon(getattr(QStyle.StandardPixmap, 'SP_MediaSkipForward')))
        self.skipFarwardbutton.clicked.connect(lambda: self.skip(1))

        hbt = QHBoxLayout()
        hbt.addStretch()
        hbt.setContentsMargins(1, 1, 1, 1)
        hbt.addWidget(self.skipBackwardbutton)
        hbt.addWidget(self.playbutton)
        hbt.addWidget(stopbutton)
        hbt.addWidget(self.skipFarwardbutton)
        hbt.addStretch()

        self.lyricbutton = QPushButton(self)
        self.lyricbutton.setMaximumWidth(30)
        self.lyricbutton.setIcon(QIcon(os.path.join(os.getcwd(), 'icone/lyric.png')))
        self.lyricbutton.setToolTip('testo brano')
        self.lyricbutton.clicked.connect(self.songLyrics)

        self.titlebutton = QPushButton(self)
        self.titlebutton.setMaximumWidth(30)
        self.titlebutton.setIcon(QIcon(os.path.join(os.getcwd(), 'icone/shazam.png')))
        self.titlebutton.setToolTip('riconosce brano')
        self.titlebutton.clicked.connect(self.wparent.songTitle)
        hbt.addWidget(self.lyricbutton)
        hbt.addWidget(self.titlebutton)
        return hbt

    def songLyrics(self):
        if self.index >= 0:
            lyric_song(self.tracks[self.index].artist, self.tracks[self.index].title, self.wparent)

    def set_play_icon(self, type):
        if type == MusicPlayerDlg.Mode_Play:
            ic = 'SP_MediaPlay'
            tp = 'Play'
        else:
            ic = 'SP_MediaPause'
            tp = 'Pause'
        self.playbutton.setIcon(self.style().standardIcon(getattr(QStyle.StandardPixmap, ic)))
        self.playbutton.setToolTip(tp)

    def play_pause(self):
        # Toggle play/pause status
        if self.mediaplayer.is_playing():
            self.mediaplayer.pause()
            self.set_play_icon(MusicPlayerDlg.Mode_Play)
            self.is_paused = True
            self.timer.stop()
        else:
            if self.mediaplayer.play() == -1:
                self.open_file()
                return

            self.mediaplayer.play()
            self.set_play_icon(MusicPlayerDlg.Mode_Pause)
            self.timer.start()
            self.is_paused = False

    def stop(self):
        # Stop player
        self.mediaplayer.stop()
        self.set_play_icon(MusicPlayerDlg.Mode_Play)
        self.mode = MusicPlayerDlg.Mode_None
        self.index = -1

    def skip(self, inc):
        self.mediaplayer.stop()
        self.inc_track_index(inc)
        self.play_song()

    def volume_ui(self, cmb):
        '''
        n = vlc.libvlc_audio_equalizer_get_preset_count()
        a = vlc.libvlc_audio_equalizer_get_preset_name(0)
        self.cmb.addItems([str(vlc.libvlc_audio_equalizer_get_preset_name(i).decode('latin1'))
                      for i in range(vlc.libvlc_audio_equalizer_get_preset_count())])
        self.cmb.currentIndexChanged.connect(self.currentIndexChanged)
        '''

        self.volumeDial = QDial(self)
        self.volumeDial.setValue(self.mediaplayer.audio_get_volume())
        self.volumeDial.setToolTip("Volume")
        self.volumeDial.setNotchesVisible(True)
        self.volumeDial.setMaximumHeight(80)
        self.volumeDial.valueChanged.connect(self.set_volume)
        v3 = QVBoxLayout()
        v3.addWidget(cmb)  #self.cmb)
        v3.addWidget(self.volumeDial)
        return v3

    def set_volume(self, volume):
        # Set the volume
        self.mediaplayer.audio_set_volume(volume)

    def open_radio(self, url='', fav=''):
        if self.mode != MusicPlayerDlg.Mode_None:
            self.stop()

        self.url = url
        self.fav = fav

        # Set the title of the track as window title
        self.media = self.instance.media_new(url)
        self._play()
        self.mode = MusicPlayerDlg.Mode_Radio
        self.timer.setInterval(5000)

        self.currentChanged(1)

        pic = scrobbler.get_thumbnail(self.fav)
        if pic is not None:
            qp = QPixmap()
            s2 = self.cover.size()
            if qp.loadFromData(pic):
                s1 = qp.width(), qp.height()
                self.cover.setPixmap(qp.scaledToHeight(self.cover.height())) #, Qt.AspectRatioMode.KeepAspectRatio))
                self.cover.setPixmap(qp.scaled(self.cover.size(), Qt.AspectRatioMode.KeepAspectRatio))
        else:
            self.cover.clear()

    def open_file(self, tracks=None):
        if self.mode != MusicPlayerDlg.Mode_None:
            self.stop()

        if tracks is None or len(tracks) == 0:
            return

        self.tracks = tracks
        self.index = 0
        self.currentChanged(0)
        self.play_song()

    def play_song(self):
        self.tm = self.tracks[self.index].tm_sec
        filename = self.tracks[self.index].file
        self.t_time.setText(get_tm(self.tm))
        self.media = self.instance.media_new(filename)
        self._play()
        self.mode = MusicPlayerDlg.Mode_Music
        self.timer.setInterval(100)
        prg = f"( {self.index + 1} / {len(self.tracks)} )"
        tt = f"{self.tracks[self.index].artist} - {self.tracks[self.index].album} - {self.tracks[self.index].title} {prg}"
        self.add_note(tt)
        self.wparent.get_track_pix(self.tracks[self.index].album,  self.tracks[self.index].artist, self.cover)

    def inc_track_index(self, inc):
        if inc < 0:
            if self.index <= 0:
                return
        else:
            if self.index >= len(self.tracks) -1:
                return
        self.index += inc

    def _play(self):
        # Put the media in the media player
        self.mediaplayer.set_media(self.media)

        # Parse the metadata of the file
        self.media.parse()

        # Set the title of the track as window title
        self.setWindowTitle(self.media.get_meta(0))

        self.mediaplayer.set_hwnd(int(self.videoframe.winId()))

        self.play_pause()
        tm0 = time.monotonic()
        while not self.mediaplayer.is_playing():
            dt = time.monotonic() - tm0
            if dt > 10:
                self.add_note('timeout')
                self.stop()
                break
            pass
        self.update_ui()

    def currentChanged (self, index):
        if index == 1:
            ''' Modalità radio '''
            self.positionslider.hide()
            self.skipBackwardbutton.hide()
            self.skipFarwardbutton.hide()
            self.rt_time.clear()
            self.t_time.clear()
            self.add_note('')

        else:
            ''' Modalità player mp3 '''
            self.positionslider.show()
            self.skipBackwardbutton.show()
            self.skipFarwardbutton.show()
            self.add_note('')

    def add_note(self, txt):
        self.note.setText(txt)
        self.note.setToolTip(txt)
        self.note.setCursorPosition(0)

    def update_ui(self):
        # Updates the user interface

        # Set the slider's position to its corresponding media position
        # Note that the setValue function only takes values of type int,
        # so we must first convert the corresponding media position.
        media_pos = int(self.mediaplayer.get_position() * 1000)
        self.positionslider.setValue(media_pos)

        # No need to call this function if nothing is played
        if not self.mediaplayer.is_playing():
            self.timer.stop()

            # After the video finished, the play button stills shows "Pause",
            # which is not the desired behavior of a media player.
            # This fixes that "bug".
            if not self.is_paused and self.mode != MusicPlayerDlg.Mode_None:
                if self.index < len(self.tracks) - 1:
                    self.index += 1
                    self.play_song()
                else:
                    self.stop()
        if self.mode == MusicPlayerDlg.Mode_Radio:
            self.radio_metadata()
        elif self.mode == MusicPlayerDlg.Mode_Music:
            tm = (self.tm * media_pos) / 1000
            self.rt_time.setText(get_tm(tm))

    def radio_metadata(self):
        title = scrobbler.get_title(self.url)
        self.add_note(title)

class eqSlider(QSlider):
    def __init__(self, *args, band, **kwargs):
        super().__init__(*args, **kwargs)
        self.wparent = args[1]
        self.freq = self.wparent.freq[band]
        self.band = band
        self.setObjectName(f"eq{band}")
        self.setStyleSheet(eq_slider_style())
        self.setMaximumHeight(110)
        self.setRange(-20, 20)
        self.setTickInterval(5)
        self.setTickPosition(QSlider.TickPosition.TicksBothSides)

    def paintEvent(self, event):
        super().paintEvent(event)
        qp = QPainter(self)
        sz = self.size()
        ti = self.tickInterval()
        interval = self.maximum() - self.minimum()
        nt = interval / ti

        len = 3
        bd = 5

        dy = (sz.height() - 2 * bd) / nt
        y = int(bd + (nt / 2) * dy)

        qp.setPen(QPen(Qt.GlobalColor.red, 3))
        qp.drawLine(0, y, len, y)
        qp.drawLine(sz.width(), y, sz.width() - len, y)

    def set_tip(self, val):
        self.setToolTip(f"{self.freq} {val}db")

    def set_value(self, val):
        self.setValue(int(val))
        self.setToolTip(f"{self.freq} {val}db")

    def get_value(self):
        v = self.value()
        self.setToolTip(f"{self.freq} {v}db")
        return v, self.band


class Equalizer(QFrame):
    def __init__(self, mediaplayer):
        super().__init__()
        self.mediaplayer = mediaplayer
        self.cmb = None
        self.eq = []
        self.freq = []
        self.init_ui()
        self.equal_load()

    def init_equal(self):
        nf = vlc.libvlc_audio_equalizer_get_band_count()
        self.freq = [self.get_band(i) for i in range(nf)]
        self.cmb = QComboBox(self)
        self.cmb.addItems([str(vlc.libvlc_audio_equalizer_get_preset_name(i).decode('latin1'))
                      for i in range(vlc.libvlc_audio_equalizer_get_preset_count())])

        self.cmb.currentIndexChanged.connect(self.currentIndexChanged)
        self.equalizer = vlc.libvlc_audio_equalizer_new_from_preset(0)

    def init_ui(self):
        self.init_equal()
        nf = vlc.libvlc_audio_equalizer_get_band_count()
        self.eq = []
        he = QHBoxLayout()
        he.setContentsMargins(5, 15, 5, 5)
        for i in range(nf):
            eq = self.add_slider(i, he)
            self.eq.append(eq)

        he.setSizeConstraint(QHBoxLayout.SizeConstraint.SetMaximumSize)

        self.setStyleSheet("QFrame {background-color: rgb(220, 255, 255);"
                         "border-width: 1;"
                         "border-radius: 8;"
                         "border-style: solid;"
                         "border-color: rgb(10, 10, 10)}"
                         )
        self.setLayout(he)

    def get_preset(self):
        return self.cmb

    def get_band(self, i):
        f = vlc.libvlc_audio_equalizer_get_band_frequency(i)
        s = str(int(f / 1000.)) + 'kHz' if f >= 1000. else str(int(f)) + 'Hz'
        return s

    def add_slider(self, i, he):
        eq = eqSlider(Qt.Orientation.Vertical, self, band=i)

        eq.sliderMoved.connect(lambda widget=eq: self.equal(widget))
        eq.sliderPressed.connect(lambda widget=eq: self.equal(widget))
        eq.sliderReleased.connect(lambda widget=eq: self.equal_sav(widget))

        v = self.equalizer.get_amp_at_index(i)
        eq.set_value(v)
        he.addWidget(eq)
        return eq

    ''' richiamato quando si clicca o si muove uno slider '''
    def equal(self, wid):
        if isinstance(wid, QSlider) is True:
            #o = wid.objectName()
            #i = int(o[2:])
            v, band = wid.get_value()
            self.equalizer.set_amp_at_index(v, band)
            self.mediaplayer.set_equalizer(self.equalizer)

    ''' richiamato quando si finisce di spostare uno slider '''
    def equal_sav(self, wid):
        ini = iniConf('music_player')
        eq_sav = ini.get('EQUALIZER')
        if eq_sav is None:
            eq_sav = {}

        v = self.cmb.currentIndex()
        eq_sav['preset'] = str(v)
        o = wid.objectName()
        v, band = wid.get_value()
        self.equalizer.set_amp_at_index(v, band)
        self.mediaplayer.set_equalizer(self.equalizer)

        eq_sav[o] = str(v)
        ini.set_sez('EQUALIZER', eq_sav)
        ini.save()

    def equal_load(self):
        ini = iniConf('music_player')
        eq_sav = ini.get('EQUALIZER')
        if eq_sav is None:
            return
        if 'preset' in eq_sav.keys():
            v = int(eq_sav['preset'])
            self.currentIndexChanged(v)
            self.cmb.setCurrentIndex(v)

        self.equalizer = vlc.libvlc_audio_equalizer_new_from_preset(0)
        self.mediaplayer.set_equalizer(self.equalizer)
        for i in range(len(self.eq)):
            eqi = self.eq[i]
            o = eqi.objectName()
            if o in eq_sav.keys():
                v = int(eq_sav[o])
                eqi.set_value(v)
                self.equalizer.set_amp_at_index(v, i)

    ''' è stato cambiato il preset della combo '''
    def currentIndexChanged(self, idx):
        self.equalizer = vlc.libvlc_audio_equalizer_new_from_preset(idx)
        self.mediaplayer.set_equalizer(self.equalizer)
        for i in range(len(self.eq)):
            v = self.equalizer.get_amp_at_index(i)
            self.eq[i].set_value(v)
            self.equal_sav(self.eq[i])

def slider_style():
    QSS = """
    QSlider {
        min-height: 20px;
    }

    QSlider::groove:horizontal {
        border: 0px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #888, stop:1 #ddd);
        height: 12px;
        border-radius: 10px;
    }

    QSlider::handle {
        background: qradialgradient(cx:0, cy:0, radius: 1.2, fx:0.35,
                                    fy:0.3, stop:0 #eef, stop:1 #002);
        height: 10px;
        width: 20px;
        border-radius: 10px;
    }

    QSlider::sub-page:horizontal {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00C, stop:1 #00C);
        border-top-left-radius: 7px;
        border-bottom-left-radius: 7px;
    }

    """
    return QSS

def eq_slider_style():
    QSS = """
    QSlider {
        min-height: 90px;
        border: 5px;
    }

    QSlider::groove:horizontal {
        border: 2px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #888, stop:1 #ddd);
        height: 6px;
        border-radius: 3px;
    }

    QSlider::handle {
        background: qradialgradient(cx:0, cy:0, radius: 1.2, fx:0.35,
                                    fy:0.3, stop:0 #eef, stop:1 #002);
        height: 4px;
        width: 2px;
        border-radius: 2px;
    }
    """
    return QSS
