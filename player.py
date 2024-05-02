import time

import vlc
import sys
import os
import re
import struct
import urllib.request as urllib2

from PyQt6.QtWidgets import (QSlider, QHBoxLayout, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
            QFileDialog, QApplication, QDial, QStyle, QTabWidget)
from PyQt6.QtGui import QPalette, QColor, QAction
from PyQt6.QtCore import Qt, QTimer

from utils import iniConf
from mp3_tag import music
from dialogs import RadioDlg, MusicIndexDlg

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

class Player(QMainWindow):
    Mode_None = 0
    Mode_Music = 1
    Mode_Radio = 2
    Mode_Play = 3
    Mode_Pause = 4
    def __init__(self, master=None):
        QMainWindow.__init__(self, master)
        self.setWindowTitle("Media Player")
        self.ini = iniConf(ConfName())
        self.mode = Player.Mode_None

        cwd = os.getcwd()
        os.environ["PATH"] += os.pathsep + os.path.join(cwd, 'exe')

        # Create a basic vlc instance
        self.instance = vlc.Instance(['--gain=8.0'])

        self.media = None

        # Create an empty vlc media player
        self.mediaplayer = self.instance.media_player_new()

        self.is_paused = False

        self.equalizer = vlc.AudioEqualizer()
        self.equalizer.set_amp_at_index(0, 0)  # 60 Hz
        self.equalizer.set_amp_at_index(5, 1)  # 170 Hz
        self.equalizer.set_amp_at_index(0, 2)  # 310 Hz
        self.equalizer.set_amp_at_index(0, 3)  # 600 Hz
        self.equalizer.set_amp_at_index(0, 4)  # 1 kHz
        self.equalizer.set_amp_at_index(-5, 5)  # 3 kHz
        self.equalizer.set_amp_at_index(0, 6)  # 6 kHz
        self.equalizer.set_amp_at_index(0, 7)  # 12 kHz
        self.mediaplayer.set_equalizer(self.equalizer)

        self.create_ui()

    def add_slider(self, i, he):
        eq = QSlider(Qt.Orientation.Vertical, self)
        eq.setObjectName('eq' + str(i))
        eq.sliderMoved.connect(lambda widget=eq: self.equal(widget))
        eq.sliderPressed.connect(lambda widget=eq: self.equal(widget))
        eq.setMaximumHeight(110)
        eq.setRange(-20, 20)
        v = self.equalizer.get_amp_at_index(i)
        eq.setValue(v)
        he.addWidget(eq)
        return eq

    def create_equalizer(self):
        self.eq = []
        he = QHBoxLayout()
        for i in range(8):
            eq = self.add_slider(i, he)
            self.eq.append(eq)
        return he

    def create_ui(self):
        self.widget = QWidget(self)
        self.setCentralWidget(self.widget)

        last_folder = self.ini.get('CONF', 'last_folder')
        self.tab = QTabWidget(self)
        dlg = MusicIndexDlg(self, music(self), last_folder)
        self.tab.addTab(dlg, 'Mp3')

        radios = self.ini.get('radio')
        if radios == '':
            radios = None
        self.rd = RadioDlg(self, radios)
        self.tab.addTab(self.rd, 'Radio')
        # In this widget, the video will be drawn

        #self.videoframe = QFrame()

        '''
        if platform.system() == "Darwin":  # for MacOS
            self.videoframe = QFrame()
        else:
            self.videoframe = QFrame()


        self.palette = self.videoframe.palette()
        self.palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0))
        self.videoframe.setPalette(self.palette)
        self.videoframe.setAutoFillBackground(True)
        '''

        self.note = QLabel('', self)
        self.positionslider = QSlider(Qt.Orientation.Horizontal, self)
        self.positionslider.setObjectName('slipos')
        styles = "QSlider#slipos::handle  { background: red; border-radius: 5px }"
        self.positionslider.setStyleSheet(styles)

        hs = QHBoxLayout()
        self.positionslider.setToolTip("Position")
        self.positionslider.setMaximum(1000)
        self.positionslider.sliderMoved.connect(self.set_position)
        self.positionslider.sliderPressed.connect(self.set_position)
        self.rt_time = QLabel('', self)
        hs.addWidget(self.rt_time)
        hs.addWidget(self.positionslider)
        self.t_time = QLabel('', self)
        hs.addWidget(self.t_time)

        self.hbuttonbox = QHBoxLayout()
        self.playbutton = QPushButton(self)
        #self.playbutton.setIcon(self.style().standardIcon(getattr(QStyle.StandardPixmap, 'SP_MediaPlay')))
        self.set_play_icon(Player.Mode_Play)
        self.hbuttonbox.addWidget(self.playbutton)
        self.playbutton.clicked.connect(self.play_pause)

        self.stopbutton = QPushButton(self)
        self.stopbutton.setIcon(self.style().standardIcon(getattr(QStyle.StandardPixmap, 'SP_MediaStop')))
        self.hbuttonbox.addWidget(self.stopbutton)
        self.stopbutton.clicked.connect(self.stop)
        self.hbuttonbox.addStretch(1)

        h = self.create_equalizer()
        h2 = QHBoxLayout()

        self.volumeDial = QDial(self)
        self.volumeDial.setValue(self.mediaplayer.audio_get_volume())
        self.volumeDial.setToolTip("Volume")
        self.volumeDial.setNotchesVisible(True)
        self.volumeDial.setMaximumHeight(80)

        self.volumeDial.valueChanged.connect(self.set_volume)
        h2.addLayout(h)
        h2.addWidget(self.volumeDial)

        self.vboxlayout = QVBoxLayout()
        #dlg.show()
        self.vboxlayout.addWidget(self.tab)
        self.vboxlayout.addWidget(self.note)
        #self.vboxlayout.addWidget(self.videoframe)
        self.vboxlayout.addLayout(hs)
        self.vboxlayout.addLayout(self.hbuttonbox)
        self.vboxlayout.addLayout(h2)

        self.widget.setLayout(self.vboxlayout)

        #menu_bar = self.menuBar()

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_ui)


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
        """Toggle play/pause status
        """
        if self.mediaplayer.is_playing():
            self.mediaplayer.pause()
            #self.playbutton.setIcon(self.style().standardIcon(getattr(QStyle.StandardPixmap, 'SP_MediaPlay')))
            self.set_play_icon(Player.Mode_Play)
            self.is_paused = True
            self.timer.stop()
        else:
            if self.mediaplayer.play() == -1:
                self.open_file()
                return

            self.mediaplayer.play()
            #self.playbutton.setIcon(self.style().standardIcon(getattr(QStyle.StandardPixmap, 'SP_MediaPause')))
            self.set_play_icon(Player.Mode_Pause)
            self.timer.start()
            self.is_paused = False

    def stop(self):
        """Stop player
        """
        self.mediaplayer.stop()
        #self.playbutton.setIcon(self.style().standardIcon(getattr(QStyle.StandardPixmap, 'SP_MediaPlay')))
        self.set_play_icon(Player.Mode_Play)
        self.mode = Player.Mode_None

    def equal(self, wid):
        if isinstance(wid, QSlider) is True:
            o = wid.objectName()
            i = int(o[2:])
            #v1 = self.equalizer.get_amp_at_index(i)
            v = wid.value()
            self.equalizer.set_amp_at_index(v, i)
            v1 = self.equalizer.get_amp_at_index(i)

    def open_radio(self, url=''):
        if self.mode != Player.Mode_None:
            self.stop()

        if url == '':
            a = iniConf(ConfName())
            radios = a.get('radio')
            qq = RadioDlg.run(self, radios)
            url = radios[qq]

        self.url = url

        # Set the title of the track as window title
        self.media = self.instance.media_new(url)
        self._play()
        self.mode = Player.Mode_Radio
        self.timer.setInterval(5000)

        while not self.mediaplayer.is_playing():
            pass
        a = 2

    def open_file(self, tracks=None):
        if self.mode != Player.Mode_None:
            self.stop()

        if tracks is None:
            ini = iniConf(ConfName())
            dir = ini.get('mp3', 'dir')
            dialog_txt = "Choose Media File"
            filename = QFileDialog.getOpenFileName(self, dialog_txt, dir)
            if not filename:
                return
            filename = filename[0]
        else:
            filename = tracks[0].file

        self.tm = tracks[0].tm_sec
        self.t_time.setText(get_tm(self.tm))
        # getOpenFileName returns a tuple, so use only the actual file name
        self.media = self.instance.media_new(filename)
        self._play()
        self.mode = Player.Mode_Music
        self.timer.setInterval(100)
        self.note.setText(tracks[0].artist + ' - ' + tracks[0].album + ' - ' + tracks[0].title)


    def _play(self):
        self.update_ui()
        # Put the media in the media player
        self.mediaplayer.set_media(self.media)

        # Parse the metadata of the file
        self.media.parse()

        # Set the title of the track as window title
        self.setWindowTitle(self.media.get_meta(0))

        # The media player has to be 'connected' to the QFrame (otherwise the
        # video would be displayed in it's own window). This is platform
        # specific, so we must give the ID of the QFrame (or similar object) to
        # vlc. Different platforms have different functions for this

        '''
        if platform.system() == "Linux":  # for Linux using the X Server
            self.mediaplayer.set_xwindow(int(self.videoframe.winId()))
        elif platform.system() == "Windows":  # for Windows
            self.mediaplayer.set_hwnd(int(self.videoframe.winId()))
        elif platform.system() == "Darwin":  # for MacOS
            self.mediaplayer.set_nsobject(int(self.videoframe.winId()))
        '''


        self.mediaplayer.set_hwnd(self.winId()) #int(self.videoframe.winId()))

        self.play_pause()

    def radio_metadata(self):
        encoding = 'latin1'  # default: iso-8859-1 for mp3 and utf-8 for ogg streams
        request = urllib2.Request(self.url, headers={'Icy-MetaData': 1})  # request metadata
        response = urllib2.urlopen(request)
        metaint = int(response.headers['icy-metaint'])
        title = ''
        for _ in range(10):  # # title may be empty initially, try several times
            response.read(metaint)  # skip to metadata
            metadata_length = struct.unpack('B', response.read(1))[0] * 16  # length byte
            metadata = response.read(metadata_length).rstrip(b'\0')
            # extract title from the metadata
            m = re.search(br"StreamTitle='([^']*)';", metadata)
            if m:
                title = m.group(1)
                if title:
                    break

        self.note.setText(title.decode(encoding, errors='replace'))

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
            if not self.is_paused:
                self.stop()
        if self.mode == player.Mode_Radio:
            self.radio_metadata()
        elif self.mode == player.Mode_Music:
            tm = (self.tm * media_pos) / 1000
            self.rt_time.setText(get_tm(tm))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = Player()
    player.show()
    player.resize(640, 480)
    sys.exit(app.exec())