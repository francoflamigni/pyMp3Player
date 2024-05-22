import os
import time

vlc_path = os.path.join(os.getcwd(), 'exe/VLC')
os.environ['PYTHON_VLC_LIB_PATH'] = os.path.join(vlc_path, 'libvlc.dll')

import vlc
import sys
import scrobbler

from PyQt6.QtWidgets import (QSlider, QHBoxLayout, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
            QApplication, QDial, QStyle, QTabWidget, QComboBox, QFrame, QSplitter, QLineEdit)
from PyQt6.QtGui import QIcon, QPainter, QPen, QShowEvent
from PyQt6.QtCore import Qt, QTimer

from utils import iniConf
from mp3_tag import Music
from dialogs import RadioDlg, MusicIndexDlg, slider_style, eq_slider_style

'''
https://streamurl.link/ per trovare stazioni radio
'''
def get_tm(secs):
    min = int(secs / 60)
    sec = int(secs) - int(min * 60)
    return "{:02.0F}:{:02.0F}".format(min, sec)
def ConfDir():
    baseDir = os.path.join(os.getenv('APPDATA'), 'MySoft')
    if os.path.exists(baseDir) is False:
        os.mkdir(baseDir)

    confDir = path = os.path.join(baseDir, 'music_player')
    if os.path.exists(confDir) is False:
        os.mkdir(confDir)
    return confDir


def ConfName(user=''):
    dir = ConfDir()
    base = 'music_player'
    if user != '':
        base += '_' + user
    name = os.path.join(dir, base + '.ini')
    return name

# subclass slider to highlight central tick
class eqSlider(QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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

class Player(QMainWindow):
    Mode_None = 0  # nessuna selezione
    Mode_Music = 1  # mp3
    Mode_Radio = 2  # radio
    Mode_Play = 3
    Mode_Pause = 4
    def __init__(self, master=None):
        QMainWindow.__init__(self, master)
        cwd = os.getcwd()

        self.setWindowTitle("Media Player")
        self.setWindowIcon(QIcon(os.path.join(cwd, 'icone/pentagram.ico')))

        self.ini = iniConf(ConfName())
        self.mode = Player.Mode_None

        # Create a basic vlc instance
        self.instance = vlc.Instance(['--gain=40.0', '--audio-visual=visual'] ) # Projectm,goom,visual,glspectrum,none}', '--logfile=vlc-log.txt'])

        self.media = None

        self.tracks = []
        self.index = -1

        # Create an empty vlc media player
        self.mediaplayer = self.instance.media_player_new()

        self.is_paused = False

        self.equalizer = vlc.libvlc_audio_equalizer_new_from_preset(0)

        nf = vlc.libvlc_audio_equalizer_get_band_count()
        self.freq = [self.get_band(i) for i in range(nf)]
        self.mediaplayer.set_equalizer(self.equalizer)

        self.create_ui()
        self.show()


    def show(self):
        QMainWindow.show(self)
        QApplication.processEvents()
        self.dlg.process()

    def get_band(self, i):
        f = vlc.libvlc_audio_equalizer_get_band_frequency(i)
        s = str(int(f / 1000.)) + 'kHz' if f >= 1000. else str(int(f)) + 'Hz'
        return s

    def add_slider(self, i, he):
        eq = eqSlider(Qt.Orientation.Vertical, self)
        eq.setObjectName('eq' + str(i))
        eq.setToolTip(str(self.freq[i]))
        eq.sliderMoved.connect(lambda widget=eq: self.equal(widget))
        eq.sliderPressed.connect(lambda widget=eq: self.equal(widget))
        eq.setStyleSheet(eq_slider_style())
        eq.setMaximumHeight(110)
        eq.setRange(-20, 20)
        eq.setTickInterval(5)
        eq.setTickPosition(QSlider.TickPosition.TicksBothSides)
        v = self.equalizer.get_amp_at_index(i)
        eq.setValue(int(v))
        he.addWidget(eq)
        return eq

    def equalizer_ui(self):
        nf = vlc.libvlc_audio_equalizer_get_band_count()
        self.eq = []
        he = QHBoxLayout()
        he.setContentsMargins(5, 15, 5, 5)
        for i in range(nf):
            eq = self.add_slider(i, he)
            self.eq.append(eq)

        he.setSizeConstraint(QHBoxLayout.SizeConstraint.SetMaximumSize)

        wd = QFrame()
        wd.setStyleSheet("QFrame {background-color: rgb(220, 255, 255);"
                            "border-width: 1;"
                            "border-radius: 8;"
                            "border-style: solid;"
                            "border-color: rgb(10, 10, 10)}"
                        )
        wd.setLayout(he)
        return wd

    def currentIndexChanged(self, v):
        self.equalizer = vlc.libvlc_audio_equalizer_new_from_preset(v)
        self.mediaplayer.set_equalizer(self.equalizer)
        for i in range(len(self.eq)):
            v = self.equalizer.get_amp_at_index(i)
            self.eq[i].setValue(int(v))
            a = 0


    def create_ui(self):
        self.widget = QWidget(self)
        self.setCentralWidget(self.widget)

        self.tab = QTabWidget(self)
        last_folder = self.ini.get('CONF', 'last_folder')
        self.dlg = MusicIndexDlg(self, Music(self), last_folder)
        self.dlg.setMinimumWidth(500)
        self.tab.addTab(self.dlg, 'Mp3')

        # radios = self.ini.get('radio')
        rd = RadioDlg(self)
        self.tab.addTab(rd, 'Radio')

        v1 = QVBoxLayout()
        self.note = QLineEdit(self) #QLabel('', self)
        self.note.setReadOnly(True)
        self.note.setAlignment(Qt.AlignmentFlag.AlignLeft)
        v1.addWidget(self.tab)
        #v1.addWidget(self.note)

        # position slider e tempi totali e parziali
        hs = self.position_slider_ui()

        # play and stop buttons
        hbt = self.play_stop_ui()

        # visual effects frame
        wdd = self.visual_effect_ui()

        vl0 = QVBoxLayout()
        vl0.setContentsMargins(0, 0, 0, 0)
        vl0.addWidget(self.note)
        vl0.addLayout(hs)
        vl0.addLayout(hbt)
        vl0.setSizeConstraint(QHBoxLayout.SizeConstraint.SetMaximumSize) #SetMaximumSize)

        wdd.setLayout(vl0)

        heq = self.equalizer_ui()

        # volume
        v3 = self.volume_ui()

        h2 = QHBoxLayout()
        h2.addWidget(heq)  #)addLayout(heq)
        h2.addLayout(v3)

        v4 = QHBoxLayout()
        self.videoframe = QFrame()
        self.videoframe.setMinimumHeight(200)
        self.videoframe.setMinimumWidth(200)

        p = self.sizePolicy()
        p.setHeightForWidth(True)
        self.setSizePolicy(p)
        v4.addStretch()
        v4.addWidget(self.videoframe)
        v4.addStretch()

        v2 = QVBoxLayout()
        v2.addLayout(v4)
        v2.addWidget(wdd)
        v2.addLayout(h2)

        ht = QSplitter()
        wd1 = QWidget()
        wd1.setLayout(v1)
        wd2 = QWidget()
        wd2.setLayout(v2)
        ht.addWidget(wd1)
        ht.addWidget(wd2)

        vt = QVBoxLayout()
        vt.addWidget(ht)

        self.widget.setLayout(vt)

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_ui)

        self.resize(1000, 400)

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

    def visual_effect_ui(self):
        wdd = QFrame()
        wdd.setObjectName('slFrame')

        wdd.setStyleSheet("QFrame#slFrame {background-color: rgb(220, 220, 220);"
                            "border-width: 1;"
                            "border-radius: 8;"
                            "border-style: solid;"
                            "border-color: rgb(10, 10, 10)}"
                        )
        return wdd

    def volume_ui(self):
        cmb = QComboBox(self)
        n = vlc.libvlc_audio_equalizer_get_preset_count()
        a = vlc.libvlc_audio_equalizer_get_preset_name(0)
        cmb.addItems([str(vlc.libvlc_audio_equalizer_get_preset_name(i).decode('latin1'))
                      for i in range(vlc.libvlc_audio_equalizer_get_preset_count())])
        cmb.currentIndexChanged.connect(self.currentIndexChanged)

        self.volumeDial = QDial(self)
        self.volumeDial.setValue(self.mediaplayer.audio_get_volume())
        self.volumeDial.setToolTip("Volume")
        self.volumeDial.setNotchesVisible(True)
        self.volumeDial.setMaximumHeight(80)
        self.volumeDial.valueChanged.connect(self.set_volume)
        v3 = QVBoxLayout()
        v3.addWidget(cmb)
        v3.addWidget(self.volumeDial)
        return v3

    def play_stop_ui(self):
        self.playbutton = QPushButton(self)
        self.playbutton.setMaximumWidth(30)
        self.set_play_icon(Player.Mode_Play)
        self.playbutton.clicked.connect(self.play_pause)

        self.stopbutton = QPushButton(self)
        self.stopbutton.setMaximumWidth(30)
        self.stopbutton.setIcon(self.style().standardIcon(getattr(QStyle.StandardPixmap, 'SP_MediaStop')))
        self.stopbutton.clicked.connect(self.stop)

        hbt = QHBoxLayout()
        hbt.addStretch()
        hbt.setContentsMargins(1, 1, 1, 1)
        hbt.addWidget(self.playbutton)
        hbt.addWidget(self.stopbutton)
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
        self.titlebutton.clicked.connect(self.songTitle)
        hbt.addWidget(self.lyricbutton)
        hbt.addWidget(self.titlebutton)
        return hbt

    def songLyrics(self):
        #if self.mode != Player.Mode_Music:
        #    return
        idx = self.tab.currentIndex()
        wd = self.tab.widget(0)
        wd.lyric_song()
        a = 0
    def songTitle(self):
        wd = self.tab.widget(0)
        wd.find_song()

    def currentChanged (self, index):
        if index == 1:
            self.positionslider.hide()
            self.rt_time.clear()
            self.t_time.clear()
            self.add_note('')

        else:
            self.positionslider.show()
            self.add_note('')

        a = 0
    def set_play_icon(self, type):
        if type == Player.Mode_Play:
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
            self.set_play_icon(Player.Mode_Play)
            self.is_paused = True
            self.timer.stop()
        else:
            if self.mediaplayer.play() == -1:
                self.open_file()
                return

            self.mediaplayer.play()
            self.set_play_icon(Player.Mode_Pause)
            self.timer.start()
            self.is_paused = False

    def stop(self):
        # Stop player
        self.mediaplayer.stop()
        self.set_play_icon(Player.Mode_Play)
        self.mode = Player.Mode_None
        self.index = -1

    def equal(self, wid):
        if isinstance(wid, QSlider) is True:
            o = wid.objectName()
            i = int(o[2:])
            #v1 = self.equalizer.get_amp_at_index(i)
            v = wid.value()
            self.equalizer.set_amp_at_index(v, i)
            self.mediaplayer.set_equalizer(self.equalizer)
            #v1 = self.equalizer.get_amp_at_index(i)

    def open_radio(self, url=''):
        if self.mode != Player.Mode_None:
            self.stop()

        self.url = url

        # Set the title of the track as window title
        self.media = self.instance.media_new(url)
        self._play()
        self.mode = Player.Mode_Radio
        self.timer.setInterval(5000)

        self.currentChanged(1)

    def open_file(self, tracks=None):
        if self.mode != Player.Mode_None:
            self.stop()

        if tracks is None or len(tracks) == 0:
            return

        self.tracks = tracks #copy.deepcopy(tracks)
        self.index = 0
        self.play_song()
        self.currentChanged(0)

    def play_song(self):
        self.tm = self.tracks[self.index].tm_sec
        filename = self.tracks[self.index].file
        self.t_time.setText(get_tm(self.tm))
        self.media = self.instance.media_new(filename)
        self._play()
        self.mode = Player.Mode_Music
        self.timer.setInterval(100)
        tt = self.tracks[self.index].artist + ' - ' + self.tracks[self.index].album + ' - ' + self.tracks[self.index].title
        self.add_note(tt)

    def add_note(self, txt):
        self.note.setText(txt)
        self.note.setToolTip(txt)
        self.note.setCursorPosition(0)


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

    def radio_metadata(self):
        title = scrobbler.get_title(self.url)
        self.add_note(title)

    def set_volume(self, volume):
        # Set the volume
        self.mediaplayer.audio_set_volume(volume)

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
            if not self.is_paused and self.mode != Player.Mode_None:
                if self.index < len(self.tracks) - 1:
                    self.index += 1
                    self.play_song()
                else:
                    self.stop()
        if self.mode == player.Mode_Radio:
            self.radio_metadata()
        elif self.mode == player.Mode_Music:
            tm = (self.tm * media_pos) / 1000
            self.rt_time.setText(get_tm(tm))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = Player()
    sys.exit(app.exec())