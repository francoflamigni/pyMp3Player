from profiler import checkpoint

import os
import math
import time
from pyMyLib.utils import iniConf, get_resource_path_pathlib, get_resource_file

vlc_path = str(get_resource_path_pathlib(__file__, 'exe/vlc'))
os.environ['PYTHON_VLC_LIB_PATH'] = os.path.join(vlc_path, 'libvlc.dll')
import vlc

from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal, QRectF, QThread
from PyQt6.QtGui import QPixmap, QIcon, QPainter, QPen, QLinearGradient, QBrush, QColor
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QStyle, QPushButton, QLineEdit, QComboBox,
                             QFrame, QDial, QSlider, QGroupBox, QMessageBox, QGraphicsDropShadowEffect)

from pyMyLib.qtUtils import set_background, waitCursor
from dialogs import lyric_song, AppConfig
import scrobbler

def get_tm(secs):
    min = int(secs / 60)
    sec = int(secs) - int(min * 60)
    return "{:02.0F}:{:02.0F}".format(min, sec)


class MusicPlayerDlg(QDialog):
    Mode_None = 0  # nessuna selezione
    Mode_Music = 1  # mp3
    Mode_Radio = 2  #
    Mode_Cd = 3
    Mode_Play = 4
    Mode_Pause = 5
    next_song_signal = pyqtSignal(int)
    def __init__(self, parent):
        super(MusicPlayerDlg, self).__init__(parent)
        self.wparent = parent

        self.media = None
        self.is_paused = False
        self.tracks = []
        self.index = -1
        self.listplayer = None

        type = 'spectrum'
        args = ['--gain=40.0', '--no-video-title-show', '--audio-visual=visual']
        if type == 'spectrum':
            args.extend(['--effect-list=spectrum', '--visual-peaks'])
        elif type == 'vumeter':
            args.extend(['--effect-list=vuMeter'])
        elif type == 'scope':
            args.extend(['--effect-list=scope', '--visual-amp=2.0'])
        else:
            args.extend(['--effect-list=spectrometer', '--visual-amp=2.0'])
        self.instance = vlc.Instance(args) # Projectm,goom,visual,glspectrum,none}', '--logfile=vlc-log.txt'])
        self.mediaplayer = self.instance.media_player_new()

        self.mode = MusicPlayerDlg.Mode_None

        self.setObjectName("player_widget")
        set_background(self)

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_ui)

        ''' Parte superiore con copertina e spettro'''
        group_box = QGroupBox()
        group_box.setObjectName("HiFiGroup")

        group_box.setStyleSheet("""
            QGroupBox#HiFiGroup {
                /* 1. EFFETTO METALLO SATINATO (Gradiente Diagonale) */
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #e0e0e0, 
                    stop:0.2 #f5f5f5, 
                    stop:0.4 #bcbcbc, 
                    stop:0.6 #ffffff, 
                    stop:0.8 #9a9a9a, 
                    stop:1 #cccccc);

                /* 2. BORDO INCASSATO */
                border: 1px solid #333333;
                border-radius: 8px;
                margin-top: 2px; /* Spazio per il titolo che "galleggia" sul bordo */
                font-weight: bold;
            }

            /* 3. STILE DEL TITOLO (LED ROSSO) */
            QGroupBox#HiFiGroup::title {
                subcontrol-origin: margin;
                subcontrol-position: top center; /* Posiziona il titolo in alto al centro */
                padding: 0 10px;
                color: #FF0000;                  /* Rosso come il volume */
                font-family: 'Consolas';
                background-color: transparent;   /* Lo fa apparire sopra il metallo */
            }
        """)
        h3 = QHBoxLayout(group_box)
        self.videoframe = QFrame()
        self.videoframe.setStyleSheet("""
             QFrame {
                    border: 1px solid #FF0000;
                    border-radius: 8px;        /* Regola la stondatura qui */
                    background-color: transparent;
                    margin: 0px;               /* Rimuove l'offset esterno */
                    padding: 0px;              /* Rimuove lo spazio interno */
                }      
        """)
        self.videoframe.setMinimumSize(QSize(200, 200))
        self.cover = CoverLabel() #QLabel()
        self.cover.setStyleSheet("""
            QLabel {
                border: 1px solid #FF0000;
                border-radius: 8px;        /* Regola la stondatura qui */
                background-color: transparent;
                margin: 0px;               /* Rimuove l'offset esterno */
                padding: 0px;              /* Rimuove lo spazio interno */
            }
        """)
        # Carica il tuo vinile di default
        self.cover.setMinimumSize(QSize(200, 200))
        self.cover.setMaximumWidth(200)
        h3.addStretch()
        h3.addWidget(self.cover)
        h3.addStretch()
        h3.addWidget(self.videoframe)
        h3.addStretch()

        # control_frame note, play - pause- slider bar
        wdd = self.control_frame()

        # volume
        ctrl_height = 170
        vol = self.volume_ui(ctrl_height)

        # equalizzatore
        equalizer = Equalizer(parent.ini, self.mediaplayer, ctrl_height)

        h2 = QHBoxLayout()
        h2.addWidget(equalizer)
        h2.addWidget(vol)

        v2 = QVBoxLayout(self)
        v2.addWidget(group_box)
        v2.addWidget(wdd)
        v2.addLayout(h2)
        v2.setContentsMargins(2, 0, 2, 2)

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

        self.setStyleSheet("""
            QFrame#slFrame {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #e0e0e0, 
                    stop:0.2 #f5f5f5, 
                    stop:0.4 #bcbcbc, 
                    stop:0.6 #ffffff, 
                    stop:0.8 #9a9a9a, 
                    stop:1 #cccccc);
                border: 1px solid #333333;
                border-radius: 8px;
                margin-bottom: 0px;
                padding: 0px;
            }
        """)

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
        stopbutton.clicked.connect(self.stopB)

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
        self.lyricbutton.setIcon(QIcon(get_resource_file(__file__, 'icone', 'lyric.png')))
        self.lyricbutton.setToolTip('testo brano')
        self.lyricbutton.clicked.connect(self.songLyrics)

        self.titlebutton = QPushButton(self)
        self.titlebutton.setMaximumWidth(30)
        self.titlebutton.setIcon(QIcon(get_resource_file(__file__, 'icone', 'shazam.png')))
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
            if self.mode == MusicPlayerDlg.Mode_Cd:
                self.listplayer.pause()
            else:
                self.mediaplayer.pause()
            self.set_play_icon(MusicPlayerDlg.Mode_Play)
            self.is_paused = True
            self.timer.stop()
            self.animation_pause()
        else:
            if self.mode == MusicPlayerDlg.Mode_Cd:
                self.listplayer.play()
            else:
                if self.mediaplayer.play() == -1:
                    self.open_file()
                    return

                self.mediaplayer.play()
            self.set_play_icon(MusicPlayerDlg.Mode_Pause)
            self.timer.start()
            self.is_paused = False
            self.animation_play()

    def stopB(self):
        self.next_song_signal.emit(0)
        self.stop()

    def stop(self):
        # Stop player
        self.mediaplayer.stop()
        self.set_play_icon(MusicPlayerDlg.Mode_Play)
        self.mode = MusicPlayerDlg.Mode_None
        self.index = -1
        self.animation_pause()

    def skip(self, inc):
        self.mediaplayer.stop()
        if self.mode == MusicPlayerDlg.Mode_Music:
            self.inc_track_index(inc)
            self.play_song()
        else:
            self.inc_track_index(inc)
            if inc > 0:
                self.listplayer.next()
            else:
                self.listplayer.previous()
            self.update_ui()

    def volume_ui(self, ctrl_height):
        vc = VolumeControl(ctrl_height, self.mediaplayer.audio_get_volume())
        #vc.volumeDial.setValue(self.mediaplayer.audio_get_volume())
        vc.volumeDial.valueChanged.connect(self.set_volume)
        return vc

    def set_volume(self, volume):
        # Set the volume
        self.mediaplayer.audio_set_volume(volume)

    def open_cd(self, media_input):
        if self.mode != MusicPlayerDlg.Mode_None:
            self.stop()

        from music_brainz import CDinfo, CoverArtWorker
        cdi = CDinfo(media_input)
        self.tracks, cov = cdi.cd_to_internal()
        if cov:
            self.thread = QThread()
            file = r"c:\tmp\cov.jpg"

            # 2. Crea il Worker e sposta nel Thread
            self.worker = CoverArtWorker(cov, file)
            self.worker.moveToThread(self.thread)

            # 3. Collega i segnali
            self.thread.started.connect(self.worker.run)
            self.worker.signals.finished.connect(self.show_cover)

            # Collega la pulizia all'uscita del worker
            self.worker.signals.finished.connect(self.thread.quit)
            self.worker.signals.error.connect(self.thread.quit)
            self.thread.finished.connect(self.thread.deleteLater)
            self.worker.signals.finished.connect(self.worker.deleteLater)
            self.worker.signals.error.connect(self.worker.deleteLater)
            self.thread.start()

        self.gestisci_visualizzazione_cover()
        self.index = 0

        medialist = self.instance.media_list_new()
        device = f"cdda:///{media_input}:/"
        for i in (range(1, len(self.tracks) + 1)):  # the second value for range() can be set without problem also higher
            track = self.instance.media_new(device, (":cdda-track=" + str(i)))
            medialist.add_media(track)

        self.listplayer = self.instance.media_list_player_new()
        self.listplayer.set_media_player(self.mediaplayer)
        self.listplayer.set_media_list(medialist)
        self.mode = MusicPlayerDlg.Mode_Cd

        event_manager = self.mediaplayer.event_manager()
        event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self.on_track_end)

        self.mediaplayer.set_hwnd(int(self.videoframe.winId()))
        self.listplayer.play()
        self.set_play_icon(MusicPlayerDlg.Mode_Pause)
        self.timer.setInterval(500)
        self.timer.start()
        self.cover.clear()
        self.update_ui()

    def show_cover(self):
        self.cover.reset()
        file = r"c:\tmp\cov.jpg"
        pixmap = QPixmap()
        pixmap.load(file)

        # Scala l'immagine mantenendo le proporzioni
        self.cover.setPixmap(pixmap.scaled(self.cover.size(), Qt.AspectRatioMode.KeepAspectRatio))

    def on_track_end(self, event):
        if self.mode != MusicPlayerDlg.Mode_Cd:
            return
        idx = self.index + 1
        if idx < len(self.tracks):
            self.index = idx
        else:
            # il cd è finito
            self.listplayer = None
            self.mode = MusicPlayerDlg.Mode_None
        self.update_ui()

    def open_radio(self, url='', fav=''):
        if self.mode != MusicPlayerDlg.Mode_None:
            self.stop()

        self.url = url
        self.fav = fav

        # Set the title of the track as window title
        self.media = self.instance.media_new(url)
        if not self._play():
            QMessageBox.warning(self, "Attenzione", "Nessun segnale ricevuto")
            return False
        self.mode = MusicPlayerDlg.Mode_Radio
        self.timer.setInterval(5000)

        self.currentChanged(1)

        pic = scrobbler.get_thumbnail(self.fav)
        if pic is not None:
            self.cover.reset()
            qp = QPixmap()
            s2 = self.cover.size()
            if qp.loadFromData(pic):
                s1 = qp.width(), qp.height()
                #self.cover.setPixmap(qp.scaledToHeight(self.cover.height())) #, Qt.AspectRatioMode.KeepAspectRatio))
                self.cover.setPixmap(qp.scaled(self.cover.size(), Qt.AspectRatioMode.KeepAspectRatio))
        else:
            self.gestisci_visualizzazione_cover()

        return True

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
        #loudness = calculate_single_loudness(filename)
        self.t_time.setText(get_tm(self.tm))
        self.media = self.instance.media_new(filename)
        self._play()
        self.mode = MusicPlayerDlg.Mode_Music
        self.timer.setInterval(100)
        prg = f"( {self.index + 1} / {len(self.tracks)} )"
        tt = f"{self.tracks[self.index].artist} - {self.tracks[self.index].album} - {self.tracks[self.index].title} {prg}"
        self.add_note(tt)

        self.cover.reset()
        is_cover = self.wparent.get_track_pix(self.tracks[self.index].album,  self.tracks[self.index].artist, self.cover)
        if not is_cover:
            self.gestisci_visualizzazione_cover()

    def gestisci_visualizzazione_cover(self):
        # Carica il tuo vinile di default
        path_vinile = get_resource_file(__file__, 'icone', 'vinyl.png')
        self.cover.set_cover(QPixmap(path_vinile))
        self.cover.animation.start()

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
        waitCursor(True)
        state = self.mediaplayer.get_state()
        while not self.mediaplayer.is_playing():
            dt = time.monotonic() - tm0
            if dt > 10:
                self.add_note('timeout')
                self.stop()
                waitCursor()
                return False
            time.sleep(1.0)
        self.update_ui()
        waitCursor()
        self.animation_play()
        return True

    def animation_play(self):
        self.cover.animation.resume() if self.cover.animation.state() == QPropertyAnimation.State.Paused else self.cover.animation.start()

    def animation_pause(self):
        self.cover.animation.pause()

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
        if not self.mediaplayer.is_playing() and self.mode == MusicPlayerDlg.Mode_Music:
            self.timer.stop()

            # After the video finished, the play button stills shows "Pause",
            # which is not the desired behavior of a media player.
            # This fixes that "bug".
            if not self.is_paused and self.mode == MusicPlayerDlg.Mode_Music:  #da rivedere
                if self.index < len(self.tracks) - 1:
                    self.index += 1
                    self.play_song()
                else:
                    self.stop()
                    self.next_song_signal.emit(1)
        if self.mode == MusicPlayerDlg.Mode_Radio:
            self.radio_metadata()
        elif self.mode == MusicPlayerDlg.Mode_Music:
            tm = (self.tm * media_pos) / 1000
            self.rt_time.setText(get_tm(tm))
        elif self.mode == MusicPlayerDlg.Mode_Cd:
            self.tm = self.tracks[self.index].tm_sec
            self.t_time.setText(get_tm(self.tm))
            tm = (self.tm * media_pos) / 1000
            self.rt_time.setText(get_tm(tm))
            prg = f"( {self.index + 1} / {len(self.tracks)} )"
            tt = f"{self.tracks[self.index].artist} - {self.tracks[self.index].album} - {self.tracks[self.index].title} {prg}"
            self.add_note(tt)

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
        self.setMaximumHeight(150)
        #self.setMinimumHeight(120)
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
    def __init__(self, ini, mediaplayer, height=150):
        super().__init__()
        self.mediaplayer = mediaplayer
        self.ini = ini
        self.cmb = None
        self.eq = []
        self.freq = []
        self.setMaximumHeight(height)
        self.init_ui()
        self.equal_load()

    def init_equal(self):
        nf = vlc.libvlc_audio_equalizer_get_band_count()
        self.freq = [self.get_band(i) for i in range(nf)]
        self.cmb = QComboBox()
        self.cmb.addItems([str(vlc.libvlc_audio_equalizer_get_preset_name(i).decode('latin1'))
                      for i in range(vlc.libvlc_audio_equalizer_get_preset_count())])

        self.cmb.currentIndexChanged.connect(self.currentIndexChanged)
        self.cmb.setFixedHeight(20)
        self.cmb.setStyleSheet(
            """
            QComboBox {
                background: transparent;      /* Prende lo sfondo del QFrame sottostante */
                border: 0px solid #555555;    /* Un bordo sottile per definirla */
                padding-right: 20px;
                padding-bottom: 1px;
                margin-left: 5px;
                /* Blu Elettrico Neon - Massima saturazione */
                color: #4444FF;           
                font-family: 'Consolas';
                font-weight: bold;
                font-size: 16px;
                /* Effetto ombra per distaccare il testo dal metallo */
                qproperty-alignment: 'AlignCenter';
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border: none;             /* <--- QUESTO elimina la riga nera verticale */
                background: transparent;
            }
            QComboBox::down-arrow {
                /* Puoi personalizzare la freccia o lasciarla di sistema */
                image: none; 
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid transparent; /* Crea un triangolino pulito */
                margin-right: 5px;
            }
        """
        )
        self.equalizer = vlc.libvlc_audio_equalizer_new_from_preset(0)

    def init_ui(self):
        self.init_equal()
        nf = vlc.libvlc_audio_equalizer_get_band_count()
        self.eq = []

        he = QHBoxLayout()
        he.setContentsMargins(5, 5, 5, 5)
        he.setSpacing(7)
        for i in range(nf):
            eq = self.add_slider(i)
            #eq.setFixedHeight(180)
            self.eq.append(eq)
            he.addWidget(eq)

        he.setSizeConstraint(QHBoxLayout.SizeConstraint.SetMaximumSize)

        self.setStyleSheet("""
            QFrame {
                /* Effetto metallo satinato: gradiente con riflessi multipli */
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #e0e0e0, 
                    stop:0.2 #f5f5f5, 
                    stop:0.4 #bcbcbc, 
                    stop:0.6 #ffffff, 
                    stop:0.8 #9a9a9a, 
                    stop:1 #cccccc);

                border-style: solid;
                border-width: 1px;
                border-radius: 8px;
                border-color: #333333;

                /* Un leggero bordo interno per dare tridimensionalità */
                border-top: 1px solid #ffffff;
                border-left: 1px solid #ffffff;
            }
        """)

        hv = QVBoxLayout()
        hv.setContentsMargins(1, 1, 1, 1)
        hv.setSpacing(0)
        hv.addWidget(self.cmb)
        hv.addStretch()
        hv.addLayout(he)
        self.setLayout(hv) #he)

    def get_preset(self):
        return self.cmb

    def get_band(self, i):
        f = vlc.libvlc_audio_equalizer_get_band_frequency(i)
        s = str(int(f / 1000.)) + 'kHz' if f >= 1000. else str(int(f)) + 'Hz'
        return s

    def add_slider(self, i):
        eq = eqSlider(Qt.Orientation.Vertical, self, band=i)

        eq.sliderMoved.connect(lambda widget=eq: self.equal(widget))
        eq.sliderPressed.connect(lambda widget=eq: self.equal(widget))
        eq.sliderReleased.connect(lambda widget=eq: self.equal_sav(widget))

        v = self.equalizer.get_amp_at_index(i)
        eq.set_value(v)
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
        #ini = iniConf(AppConfig)
        eq_sav = self.ini.get('EQUALIZER')
        if eq_sav is None:
            eq_sav = {}

        v = self.cmb.currentIndex()
        eq_sav['preset'] = str(v)
        o = wid.objectName()
        v, band = wid.get_value()
        self.equalizer.set_amp_at_index(v, band)
        self.mediaplayer.set_equalizer(self.equalizer)

        eq_sav[o] = str(v)
        self.ini.set_sez('EQUALIZER', eq_sav)
        self.ini.save()

    def equal_load(self):
        #ini = iniConf(AppConfig)
        eq_sav = self.ini.get('EQUALIZER')
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
        border: 1px solid #333;
        /* Grigio antracite sfumato: non troppo scuro, non troppo chiaro */
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                                    stop:0 #444, 
                                    stop:0.5 #555, 
                                    stop:1 #444);
        height: 10px;
        border-radius: 5px;
    }

    QSlider::handle:horizontal {
        /* EFFETTO SFERA GRIGIA: 
           fx e fy al 35% spostano il riflesso della luce per dare l'effetto tondo 3D */
        background: qradialgradient(cx:0.5, cy:0.5, radius: 1.0, fx:0.35, fy:0.35, 
                                    stop:0 #ffffff,   /* Riflesso luce diretta */
                                    stop:0.5 #bcbcbc, /* Grigio medio corpo sfera */
                                    stop:1 #666666);  /* Grigio scuro per l'ombra ai bordi */
        
        border: 1px solid #888;
        width: 20px;
        height: 16px;
        /* Margine negativo per uscire dai 12px del groove (20-12)/2 = 4 */
        margin: -3px 0px; 
        border-radius: 10px;
        min-width: 20px;
        min-height: 20px;
    }

    QSlider::sub-page:horizontal {
        /* Gradiente "Neon": Blu profondo ai bordi e Azzurro quasi bianco al centro */
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
            stop:0 #002266, 
            stop:0.2 #0066ff, 
            stop:0.5 #b3d1ff,  /* Il "core" della luce */
            stop:0.8 #0066ff, 
            stop:1 #002266);
        
        /* Bordo esterno che simula il riflesso della luce */
        border: 1px solid #3385ff;
        border-radius: 5px;
    }

    """
    return QSS

def eq_slider_style():
    QSS = """
    QSlider {
        min-height: 120px;
        border: 10px;
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

class VolumeControl(QFrame):
    def __init__(self, height=150, vol = 0):
        super().__init__()
        self.setObjectName("VolumeContainer")
        self.setMaximumHeight(height)

        # Layout verticale
        layout = QVBoxLayout(self)
        layout.setSpacing(0)  # Spazio tra testo e dial
        #layout.setContentsMargins(10, 20, 10, 10)
        layout.setContentsMargins(0, 0, 0, 0)# Padding interno del bordo

        # 1. LA SCRITTA (Usiamo una QLabel invece del paintEvent)
        self.val_label = QLabel("- -")
        self.val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.val_label.setStyleSheet("""
            color: #FF0000; 
            font-family: 'Consolas'; 
            font-size: 24px; 
            font-weight: bold;
            background: back;
            border: 1px;
            border-radius: 8px;
            padding: 5px;
            margin-top: 10px;
            margin-left: 15px;
            margin-right: 15px;
            margin-bottom: 0px;
        """)

        # AGGIUNGIAMO UN VERO EFFETTO BAGLIORE (Glow)
        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(15)
        glow.setColor(QColor("#FF0000"))
        glow.setOffset(0, 0)
        self.val_label.setGraphicsEffect(glow)

        # 2. IL DIAL
        self.volumeDial = VolumeDial(vol=vol)
        # Aggiorna il testo della label quando muovi il dial
        self.volumeDial.valueChanged.connect(self.update_text)

        # Costruzione Layout
        layout.addWidget(self.val_label)
        layout.addStretch()  # Spinge il dial verso il basso
        layout.addWidget(self.volumeDial, alignment=Qt.AlignmentFlag.AlignCenter)

        # Stile del bordo (Ricorda il paintEvent per il QWidget!)
        self.setStyleSheet("""
            QFrame#VolumeContainer {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #e0e0e0, 
                    stop:0.2 #f5f5f5, 
                    stop:0.4 #bcbcbc, 
                    stop:0.6 #ffffff, 
                    stop:0.8 #9a9a9a, 
                    stop:1 #cccccc);
                border: 1px solid #333333;
                border-radius: 8px;
                margin-bottom: 0px;
                padding: 0px;
            }
        """)
        self.update_text(vol)

    @staticmethod
    def percentage_to_db(percentage):
        if percentage <= 0:
            return -80.0 # Considerato silenzio assoluto

        # Parametri per simulare un amplificatore reale
        # Range dinamico: 60 dB (da -60 a 0)
        # Questa formula "schiaccia" la parte bassa per dare più precisione
        # e fa sì che il 50% della manopola sia circa -30/-40 dB

        # Usiamo una costante di curvatura (k)
        # k = 2 è una buona simulazione di un potenziometro logaritmico
        k = 2
        normalized_val = (math.pow(10, k * percentage / 100.0) - 1) / (math.pow(10, k) - 1)

        if normalized_val <= 0: return -80.0

        db = 20 * math.log10(normalized_val)

        # Limitiamo il fondo scala a -60dB per non avere numeri troppo grandi
        return max(db, -60.0)

    def update_text(self, value):
        type = 'db'
        if type == 'db':
            db_val = self.percentage_to_db(value)
            db_text = f"{db_val:.1f} dB"
            '''
            db_text = f"{db_val:.1f} dB"
            if value <= 0:
                db_text = "-∞ dB"
            else:
                # Formula audio standard
                db_val = 20 * math.log10(value / 100.0)
                # Arrotondiamo a 1 decimale per un look professionale
                db_text = f"{db_val:.1f} dB"
            '''
        else:
            db_text = f"{value}%"
        self.val_label.setText(db_text)
        #print(f"value: {value}")

    def paintEvent(self, event):
        # Necessario per disegnare il bordo del QWidget
        from PyQt6.QtWidgets import QStyleOption, QStyle
        from PyQt6.QtGui import QPainter
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

class VolumeDial(QDial):
    def __init__(self, parent=None, vol=0):
        super().__init__(parent)

        self.setWrapping(False)
        self.setFixedWidth(140)
        self.setFixedHeight(140)
        self.setValue(vol)
        # Memorizziamo l'ultimo valore valido per evitare salti
        self.last_valid_value = self.value()

        # Questo forza Qt a usare un algoritmo di tracciamento più lineare
        self.setNotchTarget(3.0)

        self.setSingleStep(1)
        self.setPageStep(10)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        gap = 11
        outer_radius = min(width, height) / 2 - gap
        center = self.rect().center()

        # --- 1. TACCHE FITTE E CORTE ---
        pen_ticks = QPen(QColor("#777777"), 1)
        painter.setPen(pen_ticks)
        num_ticks = 51  # Tacche ogni 2%
        for i in range(num_ticks):
            painter.save()
            painter.translate(width / 2, height / 2)
            angle = 135 + (i * (270 / (num_ticks - 1)))
            painter.rotate(angle)
            # Tacche più corte (solo 5 pixel)
            painter.drawLine(int(outer_radius - 5), 0, int(outer_radius), 0)
            painter.restore()

        # --- 2. ARCO SOTTILE ---
        arc_rect = QRectF(width / 2 - outer_radius + gap, height / 2 - outer_radius + gap,
                          (outer_radius - gap) * 2, (outer_radius - gap) * 2)

        # Sfondo arco
        painter.setPen(QPen(QColor("#222222"), 2))
        painter.drawArc(arc_rect, -135 * 16, -270 * 16)

        # Progresso Cyan
        value_norm = (self.value() - self.minimum()) / (self.maximum() - self.minimum())
        pen_progress = QPen(QColor("#FF0000"), 3)
        painter.setPen(pen_progress)
        painter.drawArc(arc_rect, -135 * 16, int(value_norm * -270 * 16))

        # --- 3. MANOPOLA METALLIZZATA CON EFFETTO LUCE ---
        knob_rect = arc_rect.adjusted(10, 10, -10, -10)

        # Gradiente lineare per l'effetto metallo/luce
        gradient = QLinearGradient(knob_rect.topLeft(), knob_rect.bottomRight())
        gradient.setColorAt(0.0, QColor("#e0e0e0"))  # Luce
        gradient.setColorAt(0.5, QColor("#888888"))  # Mezzo tono
        gradient.setColorAt(1.0, QColor("#444444"))  # Ombra

        painter.setPen(QPen(QColor("#FF0000"), 1))
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(knob_rect)

        # Riflesso interno circolare per profondità
        inner_shadow_rect = knob_rect.adjusted(3, 3, -3, -3)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 50), 2))
        painter.drawArc(inner_shadow_rect, 45 * 16, 180 * 16)

        # --- 4. INDICATORE (PALLINO SCURO SU METALLO) ---
        painter.save()
        painter.translate(width / 2, height / 2)
        rotation = 135 + (value_norm * 270)
        painter.rotate(rotation)
        painter.setBrush(QBrush(QColor("#222222")))
        #painter.setPen(QPen(QColor("#00f0ff"), 1))  # Bordo cyan sottile
        painter.setPen(QPen(QColor("#FF0000"), 1))  # Cambiato da Cyan a Rosso
        painter.drawEllipse(int(knob_rect.width() / 2 - 18), -6, 12, 12)
        painter.restore()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._updateValueFromMouse(event.pos())
        # Chiamiamo comunque il super() se vogliamo mantenere
        # alcuni comportamenti standard (come il focus)
        super().mousePressEvent(event)

    # 2. Viene chiamato quando sposti il mouse tenendo premuto
    def mouseMoveEvent(self, event):
        # Durante il trascinamento, aggiorniamo continuamente il valore
        self._updateValueFromMouse(event.pos())
        # NOTA: Qui spesso NON si chiama super().mouseMoveEvent(event)
        # per evitare che il comportamento standard di Qt "litighi" con il tuo
        self.update()

    def _updateValueFromMouse(self, pos):

        width = self.width()
        height = self.height()
        dx = pos.x() - width / 2
        dy = pos.y() - height / 2

        angle_rad = math.atan2(dy, dx)
        angle_deg = (math.degrees(angle_rad) + 360) % 360

        # Trasliamo lo zero all'inizio del tuo arco (135°)
        adjusted_angle = (angle_deg - 135 + 360) % 360
        #print(f"adjusted_angle: {adjusted_angle}")

        # 1. GESTIONE ZONA MORTA (il vuoto di 90° in basso)
        # Se siamo tra 270 e 360, forziamo i limiti senza calcolare valori intermedi
        if adjusted_angle > 270:
            if adjusted_angle > 315:
                new_value = self.minimum()
            else:
                new_value = self.maximum()
        else:
            # 2. CALCOLO VALORE NORMALE
            percentage = adjusted_angle / 270.0
            new_value = int(self.minimum() + percentage * (self.maximum() - self.minimum()))

        #print(f"angle: {angle_deg} adjusted_angle: {adjusted_angle} new_value: {new_value}  last_valid: {self.last_valid_value}")

        # 3. FILTRO ANTI-SALTO (IL SEGRETO)
        # Se il salto è superiore al 50% dell'intero range,
        # probabilmente il mouse è passato velocemente sopra la zona morta.
        limit_range = self.maximum() - self.minimum()
        if abs(new_value - self.last_valid_value) > (limit_range * 0.5):
            # Ignoriamo il salto e manteniamo il limite più vicino
            if self.last_valid_value < (limit_range * 0.5):
                new_value = self.minimum()
            else:
                new_value = self.maximum()

        # 4. AGGIORNAMENTO
        #print(f"    final: {new_value}")
        self.last_valid_value = new_value
        self.blockSignals(True)
        self.setValue(new_value)
        self.blockSignals(False)
        self.valueChanged.emit(new_value)
        self.update()

    # IMPORTANTE: Rimuovi ogni interferenza dei metodi originali
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._updateValueFromMouse(event.pos())

    def mouseMoveEvent(self, event):
        self._updateValueFromMouse(event.pos())

from typing import Optional

def calculate_single_loudness(file_path: str) -> Optional[float]:
    import soundfile as sf
    import pyloudnorm as pln
    """
    Funzione per la Fase 1: Calcola il loudness di un singolo file.
    """
    try:
        # Carica i dati audio con soundfile
        data, rate = sf.read(file_path, dtype='float32')

        # Misura il loudness con pyloudnorm
        meter = pln.Meter(rate, block_size=0.400)  # Block size 400ms per lo standard EBU R128
        loudness = meter.integrated_loudness(data)

        return loudness
    except Exception as e:
        print(f"Impossibile calcolare il loudness per {file_path}: {e}")
        return None


from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import QPropertyAnimation, pyqtProperty, Qt
from PyQt6.QtGui import QPixmap, QPainter


class CoverLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0
        self.original_pixmap = QPixmap()

        # Configuriamo l'animazione
        self.animation = QPropertyAnimation(self, b"angle")
        self.animation.setDuration(3000)  # Velocità di rotazione (3 secondi)
        self.animation.setStartValue(0)
        self.animation.setEndValue(360)
        self.animation.setLoopCount(-1)  # Loop infinito

    # Definiamo la proprietà "angle" per l'animatore
    @pyqtProperty(int)
    def angle(self):
        return self._angle

    @angle.setter
    def angle(self, value):
        self._angle = value
        self.update()  # Ridisegna la label ad ogni cambio di angolo

    def set_cover(self, pixmap):
        """Metodo per cambiare l'immagine (vinile o copertina vera)"""
        self.original_pixmap = pixmap
        self.update()

    def reset(self):
        self.animation.stop()
        self.original_pixmap  = QPixmap()

    def paintEvent(self, event):
        if self.original_pixmap.isNull():
            return super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Calcoliamo le dimensioni per mantenere l'aspetto quadrato
        side = min(self.width(), self.height())
        rect = self.original_pixmap.scaled(
            side, side,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        ).rect()

        # Portiamo il centro del disegno al centro della label
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self._angle)

        # Disegniamo l'immagine centrata rispetto al nuovo asse
        painter.drawPixmap(-side // 2, -side // 2, side, side, self.original_pixmap)
        painter.end()