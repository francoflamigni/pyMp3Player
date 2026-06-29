import os
import sys

from PyQt6.QtWidgets import (QMainWindow, QStackedWidget, QVBoxLayout, QLabel,
                             QApplication, QTabBar, QPushButton, QToolBar, QMenu, QComboBox, QDialog, QSplashScreen)
from PyQt6.QtGui import QIcon, QCursor, QAction, QColor, QPixmap
from PyQt6.QtCore import Qt, QTimer, QEasingCurve, QPropertyAnimation
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from qframelesswindow import FramelessDialog, StandardTitleBar

from pyMyLib.qtUtils import informMessage, AddMenuItem, set_application_icon, FinestraManuale
from pyMyLib.utils import iniConf, get_resource_file, get_resource_path_pathlib

from dialogs import AppConfig, Version, ReleaseDate
from utility import AppContext

from music_index import MusicIndexDlg
from music_player import MusicPlayerDlg
from music_radio import RadioDlg
from utility import detect_cd_drives, close_splash, Cache
from mp3_tag import GENRE
from contextlib import contextmanager

INFO_MES = f'{AppConfig}\nMusic manager\nVersione {Version}\n{ReleaseDate}'

class MyTitleBar(StandardTitleBar):
    def __init__(self, parent):
        super().__init__(parent)

        self.setTitle("Euterpe")
        self.setIcon(QIcon(get_resource_file(__file__, 'icone', 'player.ico')))
        self.maxBtn.hide()
        self.setDoubleClickEnabled(False)

        altezza_barra = self.height()
        self.closeBtn.setFixedSize(altezza_barra, altezza_barra)

        self.closeBtn.setIcon(get_resource_file(__file__, 'icone', 'off.svg'))
        self.closeBtn.setHoverColor(Qt.GlobalColor.red)
        self.closeBtn.setPressedColor(Qt.GlobalColor.red)
        self.closeBtn.setHoverBackgroundColor(QColor(0, 0, 0, 0))  #Qt.GlobalColor.white)  #QColor(232, 17, 35))
        self.closeBtn.setPressedBackgroundColor(QColor(0, 0, 0, 120))

        self.minBtn.clicked.disconnect()
        self.minBtn.clicked.connect(self.minimize_with_animation)

        lay = self.layout()
        lay.insertSpacing(3, 5)

        tb = parent.createTabBar()
        lay.insertWidget(4, tb)

    def minimize_with_animation(self):
        win = self.window()
        QApplication.processEvents()
        pos_prima_di_minimiz = win.pos()

        # Animazione della window opacity (funziona sempre)
        self.anim = QPropertyAnimation(win, b"windowOpacity")
        self.anim.setDuration(600)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        def on_finished():
            win.hide()

            win.showMinimized()
            # Ripristina l'opacità per quando la finestra viene ripristinata
            win.setWindowOpacity(1.0)
            win.move(pos_prima_di_minimiz)

        self.anim.finished.connect(on_finished)
        self.anim.start()

class Player(FramelessDialog):
    def __init__(self, splash=None):
        from tempfile import TemporaryDirectory
        super().__init__()

        self.setTitleBar(MyTitleBar(self))
        self.setResizeEnabled(False)

        os.environ["PATH"] += os.pathsep + str(get_resource_path_pathlib(__file__, 'exe'))

        ini = iniConf(AppConfig, case_sensitive=True)
        cache = Cache(ini)
        self.appCtx = AppContext(ini, cache, tmpObj=TemporaryDirectory, mainW=self)
        #self.file_da_riprodurre = file_da_riprodurre
        self.splash = splash

        # Imposta lo sfondo nero e, opzionalmente, il testo bianco per leggibilità
        self.setObjectName("MainFrame")
        self.setStyleSheet("""
            #MainFrame {
                background-color: white;
                border: 1px black;
            }
        """)

        self.background_mode = False
        self.create_ui()

        self.init_server()

        #self.Install_idle_fun()
        self.show()
        self.Install_idle_fun()

    def init_server(self):
        self.server_name = AppConfig
        self.server = QLocalServer(self)

        # Se il server esiste già da una sessione crashata, lo puliamo
        QLocalServer.removeServer(self.server_name)

        if self.server.listen(self.server_name):
            self.server.newConnection.connect(self.gestisci_nuova_connessione)

    def gestisci_nuova_connessione(self):
        """Viene chiamato quando una SECONDA istanza tenta di aprirsi."""
        socket = self.server.nextPendingConnection()
        if socket.waitForReadyRead(1000):
            # Legge il percorso del file inviato dall'altra istanza
            path = socket.readAll().data().decode('utf-8')
            self.carica_brano(path)
            # Porta la finestra in primo piano
            self.activateWindow()
            self.raise_()
        socket.close()

    def carica_brano(self, path):
        try:
            b = self.dlg.music._load_tag(path)
            from mp3_tag import track
            t = track(title=b['titolo'], album=b['album'], artist=b['artista'],
                      id=0, file=path, num=0, tm_sec=b['durata_sec'], genre=b['genere'])
            self.open_file([t])
        except Exception as e:
            print(f"Errore caricamento brano: {e}")
            informMessage(f"Impossibile riprodurre il file:\n{path}", 'Errore File', 10, False)

    def set_windows_animations(self, enabled=True):
        import sys
        if sys.platform != "win32":
            return  # Esce silenziosamente se non siamo su Windows
        import ctypes
        from ctypes import wintypes
        # DWMWA_TRANSITIONS_FORCEDISABLED = 3
        DWMWA_TRANSITIONS_FORCEDISABLED = 3
        value = ctypes.c_int(0 if enabled else 1)  # 1 per disabilitare
        hwnd = int(self.window().winId())

        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_TRANSITIONS_FORCEDISABLED,
            ctypes.byref(value),
            ctypes.sizeof(value)
        )

    def Install_idle_fun(self):
        from utility import IdleTimeout
        self.idle_timer = None
        idle_time = self.appCtx.config.get('user', 'tmout')
        clic_exit = self.appCtx.config.get('user', 'clic_exit')
        clic_exit = False  if clic_exit == '' or clic_exit != '1' else True

        try:
            idle_time = int(idle_time)
        except:
            idle_time = 0
        if idle_time != 0:
            self.idle_timer = IdleTimeout(self, idle_time, self.idle_background, clic_exit)

    def show(self):
        QMainWindow.show(self)
        self.raise_()  # Porta in primo piano
        self.activateWindow()  # Attiva la finestra
        self.setWindowState(
            self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        QApplication.processEvents()
        if self.splash:
            self.splash.finish(self)
        #close_splash()

        self.dlg.process()

    def createTabBar(self):
        tool = QToolBar()

        bt = QPushButton(self)
        bt.setIcon(QIcon(get_resource_file(__file__, 'icone', 'menu.png')))
        bt.setMaximumWidth(30)
        bt.clicked.connect(self.options)
        tool.addWidget(bt)
        #tool.addSeparator()
        spacer_fixed = QLabel()
        spacer_fixed.setFixedWidth(30) # Imposta una larghezza fissa di 50px
        tool.addWidget(spacer_fixed)

        self.tb = QTabBar()
        self.tb.addTab('')
        self.tb.setTabIcon(0, QIcon(get_resource_file(__file__, 'icone', 'music_archive.png')))
        self.tb.setTabToolTip(0, 'archivio musicale')
        self.tb.addTab('')
        self.tb.setTabIcon(1, QIcon(get_resource_file(__file__, 'icone', 'radio.png')))
        self.tb.setTabToolTip(1, 'Radio')
        self.tb.addTab('')
        self.tb.setTabIcon(2, QIcon(get_resource_file(__file__, 'icone', 'stereo.png')))
        self.tb.setTabToolTip(2, 'player')
        self.tb.currentChanged.connect(self.tab_changed)
        path_icona_freccia = get_resource_file(__file__, 'icone', 'background.png').replace('\\', '/')
        self.tb.setStyleSheet("""
            QTabBar {
                background: transparent;
                border: none;
            }
            
            QTabBar::tab {
                background: #f0f0f0; /* Grigio chiaro come la tua barra */
                border: 1px solid #d0d0d0;
                /* Rendi i bordi laterali condivisi per evitare linee doppie */
                margin-right: -1px; 
                padding: 4px;
                min-width: 20px;
                border-radius: 0px; /* Iniziamo da un rettangolo pulito */
                text-align: center;
            }
            
            /* Arrotonda solo il primo tab a sinistra */
            QTabBar::tab:first {
                border-top-left-radius: 4px;
                border-bottom-left-radius: 4px;
            }
            
            /* Arrotonda solo l'ultimo tab a destra */
            QTabBar::tab:last {
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
                margin-right: 0px;
            }
            
            /* Rimuove lo spazio extra che Qt riserva per il testo anche se è vuoto */
            QTabBar::tab:only-with-icon {
                margin: 0px;
            }
            
            /* Stile tab NON selezionato */
            QTabBar::tab:!selected {
                color: #888;
                background: #e8e8e8;
            }
            
            /* Stile tab selezionato */
            QTabBar::tab:selected {
                background: white;
                /* Invece del bordo blu su tutto il perimetro, usiamo solo una linea */
                border-bottom: 3px solid #FF0000; /* Rosso Euterpe */
                color: black;
            }
            
            QTabBar::tab:hover:!selected {
                background: #f8f8f8;
                border-bottom: 2px solid #0000FF;
                border-top: 2px solid #0000FF;
            }        
        """)

        tool.addWidget(self.tb)
        spacer_fixed2 = QLabel()
        spacer_fixed2.setFixedWidth(30) # Imposta una larghezza fissa di 50px
        tool.addWidget(spacer_fixed2)

        self.genre_combo = QComboBox()

        self.genre_combo.setStyleSheet(f"""
            QComboBox {{
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 1px 18px 1px 5px;
                background-color: #fafafa;;
            }}
            
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #d0d0d0; /* Linea di separazione */
            }}
        
            QComboBox::down-arrow {{
                image: url({path_icona_freccia});
                width: 12px;  /* Regola la dimensione dell'icona */
                height: 12px;
            }}          
            
            /* Il menu che scende (molto importante per l'estetica) */
            QComboBox QAbstractItemView {{
                border: 1px solid #d0d0d0;
                selection-background-color: #FF0000;
                background-color: white;
                outline: none;
            }}        
        """)
        v = [""]
        v.extend((GENRE))
        self.genre_combo.addItems(v)
        self.genre_combo.currentIndexChanged.connect(self.filter_genre)
        self.combo_action = tool.addWidget(self.genre_combo)

        return tool

    def tab_changed(self, index):
        visible = False if index != 0 else True
        self.combo_action .setVisible(visible)
        self.tab.setCurrentIndex(index)

    def filter_genre(self, index):
        gen = self.genre_combo.currentText()
        self.dlg.filter(gen)

    def create_ui(self):
        v = QVBoxLayout(self)
        v.addSpacing(20)
        self.tab = QStackedWidget(self)

        self.dlg = MusicIndexDlg(self.appCtx)
        self.dlg.play_signal.connect(self.open_file)
        self.tab.addWidget(self.dlg)

        rd = RadioDlg(self.appCtx)
        rd.radio_signal.connect(self.open_radio)
        self.tab.addWidget(rd)

        self.ply = MusicPlayerDlg(self.appCtx)
        self.tab.addWidget(self.ply)

        v.addWidget(self.tab)

    def options(self):
        p = QCursor.pos()
        contextMenu = QMenu(self)
        drives = detect_cd_drives()
        cd = None
        if drives:
            cd = QMenu("Riproduci CD", self)
            cd.setIcon(QIcon(get_resource_file(__file__, 'icone', 'cd_play.png')))
            for d in drives:
                d1 = QAction(d, self)
                d1.triggered.connect(lambda checked, drive_letter=d: self._open_cd(drive_letter))
                cd.addAction(d1)
        actions = [
            AddMenuItem("Dispositivi Bluetooth", fun=self.bluetooth,
                            ico=get_resource_file(__file__, 'icone', 'Bluetooth.png')),
            AddMenuItem("Converti da altri formati", fun=self.convert,
                            ico=get_resource_file(__file__, 'icone', 'tag-edit.png')),
            AddMenuItem("CD ripper", fun=self.cd_ripper,
                            ico=get_resource_file(__file__, 'icone', 'cd_ripper.png')),
            AddMenuItem("Crea PlayList", fun=self.create_playlist,
                        ico=get_resource_file(__file__, 'icone', 'create_playlist.png')
                        ),
            AddMenuItem("Riproduci CD", fun=cd, enab=drives,
                        ico=get_resource_file(__file__, 'icone', 'cd_play.png')),

            AddMenuItem("Background", fun=self.background, enab=not self.background_mode,
                        ico=get_resource_file(__file__, 'icone', 'background.png')),

            AddMenuItem("Sincronizza", fun=self.sync_folder,
                        ico=get_resource_file(__file__, 'icone', 'folders_sync.png')),
            AddMenuItem("Preferenze", fun=self.preference,
                        ico=get_resource_file(__file__, 'icone', 'preferences.png')),
            AddMenuItem("Aiuto", fun=self.help,
                        ico=get_resource_file(__file__, 'icone', 'help.png')),
            AddMenuItem("Informazioni", fun=self.info,
                        ico=get_resource_file(__file__, 'icone', 'about.png'))
        ]
        contextMenu.addActions(actions)
        contextMenu.exec(p)

    def get_track_pix(self, album, artist, cover):
        return self.dlg.get_track_pix(album, artist, cover)

    ''' Chiama Shazam per avere il titolo'''
    def songTitle(self):
        wd = self.tab.widget(0)
        wd.find_song()

    def open_radio(self, url='', fav=''):
        if self.ply.open_radio(url, fav):
            self._set_player_mode()

    def open_file(self, tracks=None, ply_lst=False):
        self.background(True) #forza l'uscita dalla modalità background
        self.ply.open_file(tracks, ply_lst)
        self._set_player_mode()

    def open_cd(self, drive):
        self.ply.open_cd(drive)
        self._set_player_mode()

    def _set_player_mode(self):
        self.tab.setCurrentIndex(2)
        self.tb.setCurrentIndex(2)

    def _open_cd(self, drive):
        QTimer.singleShot(100, lambda: self.open_cd(drive))

    def idle_background(self, t_mode):
        if t_mode:
            self.background(True)
            return
        if not self.background_mode and self.ply.mode == self.ply.Mode_None :
            self.background()

    def background(self, reset=False):
        if self.background_mode or reset:
            self.background_mode = False
            self.titleBar.setTitle("Euterpe")
            self.setWindowOpacity(1.)
            try:
                self.ply.next_song_signal.disconnect(self._background)
                self.ply.stop()
            except:
                pass
        else:
            self.close_modal()
            self.background_mode = True
            self.titleBar.setTitle("Euterpe\U0001F535")
            self.setWindowOpacity(0.7)
            self.ply.next_song_signal.connect(self._background)
            self._background(1)
            self._set_player_mode()

    def _background(self, index):
        if index == 0:
            self.background(True) # forza l'uscita dal background mode

        import random
        from scrobbler import Speaker
        if self.background_mode:
            spk = self.appCtx.config.get('speaker')
            if not spk:
                spk = {}
            gender = spk.get('gender', 'Donna')
            volume = spk.get('volume', '50')
            mi = self.dlg.music.tracks.name
            if not mi:
                print("Libreria vuota. Impossibile avviare il background.")
                self.background(True)  # Forza l'uscita
                return
            key = random.choice(list(mi.keys()))
            mstr = mi[key]
            annuncio = Speaker(gender, self.appCtx.tmpDir).pronuncia(','.join([mstr.artist, mstr.album, mstr.title]), volume)

            v = []
            if annuncio:
                import copy
                ann = copy.deepcopy(mi[key])
                ann.file = annuncio
                v.append(ann)
            v.append(mi[key])
            self.ply.open_file(v)

    def close_modal(self):
        top_widgets = QApplication.topLevelWidgets()

        for widget in top_widgets:
            # Controlla se il widget è una QDialog e se è modale
            if isinstance(widget, QDialog) and widget.isModal():
                # .reject() è meglio di .close() per i dialoghi perché
                # simula la pressione del tasto ESC o il tasto "Annulla"
                widget.reject()

    @contextmanager
    def suspend_background_mode(self):
        # ===== PARTE 1: Eseguita quando ENTRA nel 'with' =====

        if self.background_mode:
            self.background(True) #se background lo disabilita
        if self.idle_timer:
            self.idle_timer.stop_idle_timer() # Ferma l'idle timer'

        try:
            yield  # ← PAUSA QUI: esegue il codice nel 'with'

        finally:
            if self.idle_timer:
                # ===== PARTE 2: Eseguita quando ESCE dal 'with' =====
                self.idle_timer.restart_idle_timer()

    def bluetooth(self):
        from bluetooth import BluetoothManager
        with self.suspend_background_mode():
            bt = BluetoothManager()
            bt.exec()

    def info(self):
        informMessage(INFO_MES, 'Εὐτέρπη', 12, True, get_resource_file(__file__, 'icone', 'pentagram.png'))

    def convert(self):
        from format_convert import AudioConverter
        with self.suspend_background_mode():
            ac = AudioConverter()
            ac.exec()

    def cd_ripper(self):
        from cd_ripper import CDRipperMainWindow
        with self.suspend_background_mode():
            cr = CDRipperMainWindow(self.appCtx)
            cr.play_signal.connect(self.ply.open_cd)
            cr.exec()

    def sync_folder(self):
        from sync_folders import SyncApp
        with self.suspend_background_mode():
            msg = SyncApp(self, self.dlg.last_folder)
            msg.exec()

    def preference(self):
        from dialogs import ConfigBox
        with self.suspend_background_mode():
            if ConfigBox.run(self, self.appCtx.config) == 1:
                self.Install_idle_fun()
    def help(self):
        FinestraManuale.run(self, get_resource_file(__file__, 'docs', 'Euterpe guida utente.htm'))

    def create_playlist(self):
        index = self.dlg.music

        from playlist import PlayListDlg
        with self.suspend_background_mode():
            ret, lst = PlayListDlg.run(self, index)
            #ret = plldlg.exec()
            if ret and lst:
                self.dlg.setPlaylist(lst)

    def closeEvent(self, event):
        self.server.close()  # Smette di accettare nuove connessioni
        QLocalServer.removeServer(self.server_name)
        self.appCtx.temp_dir_obj.cleanup()
        super().closeEvent(event)

    '''
    def get_generi(self):
        from collections import defaultdict
        musica = self.dlg.music
        art_gen = defaultdict(set)
        for t in musica.tracks.name.values():
            if t.genre:
                art_gen[t.artist].add(t.genre)
    '''


if __name__ == "__main__":
    app = QApplication(sys.argv)
    set_application_icon(app, f'Mysoft.{AppConfig}.v1', get_resource_file(__file__, 'icone', 'player.ico'))

    has_file = len(sys.argv) > 1

    if has_file:
        socket = QLocalSocket()
        socket.connectToServer(AppConfig)

        if socket.waitForConnected(200):
            percorso_file = sys.argv[1]
            if os.path.exists(percorso_file) and (
                    percorso_file.lower().endswith(".mp3") or percorso_file.lower().endswith(".flac")):
                socket.write(sys.argv[1].encode('utf-8'))
                socket.waitForBytesWritten(500)
                socket.disconnectFromServer()
                sys.exit(0)

    pixmap = QPixmap( get_resource_file(__file__, 'icone', 'splash.bmp') )  # Carica la tua immagine
    splash = QSplashScreen(pixmap)
    splash.show()
    app.processEvents()

    file_da_riprodurre = None
    '''
    if len(sys.argv) > 1:
        percorso_file = sys.argv[1]
        if os.path.exists(percorso_file) and (percorso_file.lower().endswith(".mp3") or percorso_file.lower().endswith(".flac")):
            file_da_riprodurre = percorso_file
    '''

    player = Player(splash)
    #splash.finish(player)
    if has_file:
        player.carica_brano(sys.argv[1])
    sys.exit(app.exec())