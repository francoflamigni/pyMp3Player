import vlc
import sys
import os
import platform
from PyQt6.QtWidgets import (QSlider, QHBoxLayout, QMainWindow, QWidget, QFrame, QPushButton, QVBoxLayout,
        QFileDialog, QApplication, QDial, QStyle)
from PyQt6.QtGui import QPalette, QColor, QAction
from PyQt6.QtCore import Qt, QTimer

from mp3_tag import music_index
import multiprocessing
from config import ConfPath, iniConf

class Player(QMainWindow):
    def __init__(self, master=None):
        QMainWindow.__init__(self, master)
        self.setWindowTitle("Media Player")

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
        """Set up the user interface, signals & slots
        """
        self.widget = QWidget(self)
        self.setCentralWidget(self.widget)

        # In this widget, the video will be drawn
        if platform.system() == "Darwin":  # for MacOS
            self.videoframe = QFrame()
        else:
            self.videoframe = QFrame()

        self.palette = self.videoframe.palette()
        self.palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0))
        self.videoframe.setPalette(self.palette)
        self.videoframe.setAutoFillBackground(True)

        self.positionslider = QSlider(Qt.Orientation.Horizontal, self)
        self.positionslider.setObjectName('slipos')
        styles = "QSlider#slipos::handle  { background: red; border-radius: 5px }"
        self.positionslider.setStyleSheet(styles)

        self.positionslider.setToolTip("Position")
        self.positionslider.setMaximum(1000)
        self.positionslider.sliderMoved.connect(self.set_position)
        self.positionslider.sliderPressed.connect(self.set_position)

        self.hbuttonbox = QHBoxLayout()
        self.playbutton = QPushButton(self)
        self.playbutton.setIcon(self.style().standardIcon(getattr(QStyle.StandardPixmap, 'SP_MediaPlay')))
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
        self.vboxlayout.addWidget(self.videoframe)
        self.vboxlayout.addWidget(self.positionslider)
        self.vboxlayout.addLayout(self.hbuttonbox)
        self.vboxlayout.addLayout(h2)

        self.widget.setLayout(self.vboxlayout)

        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File")

        # Add actions to file menu
        index_action = QAction('Indice', self)
        open_action = QAction("play Mp3", self)
        radio_action = QAction('play radio', self)
        close_action = QAction("Close App", self)
        file_menu.addAction(index_action)
        file_menu.addAction(open_action)
        file_menu.addAction(radio_action)
        file_menu.addAction(close_action)

        open_action.triggered.connect(self.open_file)
        radio_action.triggered.connect(self.open_radio)
        index_action.triggered.connect(self.crea_index)
        close_action.triggered.connect(sys.exit)

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_ui)

    def play_pause(self):
        """Toggle play/pause status
        """
        if self.mediaplayer.is_playing():
            self.mediaplayer.pause()
            self.playbutton.setIcon(self.style().standardIcon(getattr(QStyle.StandardPixmap, 'SP_MediaPlay')))
            #self.playbutton.setText("Play")
            self.is_paused = True
            self.timer.stop()
        else:
            if self.mediaplayer.play() == -1:
                self.open_file()
                return

            self.mediaplayer.play()
            self.playbutton.setIcon(self.style().standardIcon(getattr(QStyle.StandardPixmap, 'SP_MediaPause')))
            #self.playbutton.setText("Pause")
            self.timer.start()
            self.is_paused = False

    def stop(self):
        """Stop player
        """
        self.mediaplayer.stop()
        self.playbutton.setIcon(self.style().standardIcon(getattr(QStyle.StandardPixmap, 'SP_MediaPlay')))

    def equal(self, wid):
        if isinstance(wid, QSlider) is True:
            o = wid.objectName()
            i = int(o[2:])
            #v1 = self.equalizer.get_amp_at_index(i)
            v = wid.value()
            self.equalizer.set_amp_at_index(v, i)
            v1 = self.equalizer.get_amp_at_index(i)

        a = 1

    def crea_index(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder', options=QFileDialog.Option.DontUseNativeDialog)
        if folder != '':
            mp3 = index_mp3()
            mp3.index(folder)

    def open_radio(self):
        a = iniConf(ConfPath())
        radios = a.get('radio')
        url = radios['abba']

        # Set the title of the track as window title
        self.media = self.instance.media_new(url)
        self._play()
        while not self.mediaplayer.is_playing():
            a = 1
        a = 2

    def open_file(self):
        """Open a media file in a MediaPlayer
        """
        ini = iniConf(ConfPath())
        dir = ini.get('mp3', 'dir')
        dialog_txt = "Choose Media File"
        filename = QFileDialog.getOpenFileName(self, dialog_txt, dir)
        if not filename:
            return

        # getOpenFileName returns a tuple, so use only the actual file name
        self.media = self.instance.media_new(filename[0])
        self._play()

    def _play(self):
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

        if platform.system() == "Linux":  # for Linux using the X Server
            self.mediaplayer.set_xwindow(int(self.videoframe.winId()))
        elif platform.system() == "Windows":  # for Windows
            self.mediaplayer.set_hwnd(int(self.videoframe.winId()))
        elif platform.system() == "Darwin":  # for MacOS
            self.mediaplayer.set_nsobject(int(self.videoframe.winId()))


        self.mediaplayer.set_hwnd(int(self.videoframe.winId()))

        self.play_pause()

    def set_volume(self, volume):
        """Set the volume
        """
        self.mediaplayer.audio_set_volume(volume)

    def set_position(self):
        """Set the movie position according to the position slider.
        """

        # The vlc MediaPlayer needs a float value between 0 and 1, Qt uses
        # integer variables, so you need a factor; the higher the factor, the
        # more precise are the results (1000 should suffice).

        # Set the media position to where the slider was dragged
        self.timer.stop()
        pos = self.positionslider.value()
        self.mediaplayer.set_position(pos / 1000.0)
        self.timer.start()

    def update_ui(self):
        """Updates the user interface"""

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

if __name__ == "__main__":
    multiprocessing.freeze_support()

    app = QApplication(sys.argv)
    player = Player()
    player.show()
    player.resize(640, 480)
    sys.exit(app.exec())