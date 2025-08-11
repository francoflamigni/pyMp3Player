import sys
import subprocess
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QListWidget, QListWidgetItem,
                             QSpacerItem, QSizePolicy, QDialog)
from PyQt6.QtCore import Qt, pyqtSignal

from pyMyLib.qtUtils import waitCursor

class DispositivoAudioItem(QWidget):
    connetti_signal = pyqtSignal(str)
    disconnetti_signal = pyqtSignal(str)

    def __init__(self, nome, stato, indirizzo_mac, bluetooth_manager, parent=None):
        super().__init__(parent)
        self.nome = nome
        self.stato = stato
        self.indirizzo_mac = indirizzo_mac
        self.bluetooth_manager = bluetooth_manager  # Memorizza il riferimento
        self.layout = QHBoxLayout()

        mes = f"<span style='font-size:12pt;'>{nome}:</span><span style='font-size:10pt; color:gray;'>({indirizzo_mac})</span>"
        self.nome_label = QLabel(mes)
        self.layout.addWidget(self.nome_label)

        #self.stato_label = QLabel(f"({stato})")
        #self.layout.addWidget(self.stato_label)

        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.layout.addItem(spacer)

        if stato.lower() != "yes":
            self.connetti_button = QPushButton("Connetti")
            self.connetti_button.clicked.connect(lambda: self.connetti_signal.emit(self.indirizzo_mac))
            self.layout.addWidget(self.connetti_button)
        else:
            self.disconnetti_button = QPushButton("Disconnetti")
            self.disconnetti_button.clicked.connect(lambda: self.disconnetti_signal.emit(self.indirizzo_mac))
            self.layout.addWidget(self.disconnetti_button)

        self.setLayout(self.layout)

        self.connetti_signal.connect(self.connetti_handler)
        self.disconnetti_signal.connect(self.disconnetti_handler)

    def connetti_handler(self, mac_address):
        if isinstance(self.bluetooth_manager, BluetoothManager):
            self.bluetooth_manager.connetti_dispositivo(mac_address)

    def disconnetti_handler(self, mac_address):
        if isinstance(self.bluetooth_manager, BluetoothManager):
            self.bluetooth_manager.disconnetti_dispositivo(mac_address)

class BluetoothManager(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gestione Dispositivi Audio Bluetooth")
        self.setGeometry(100, 100, 500, 300) # Aumenta la larghezza per i bottoni

        self.layout = QVBoxLayout(self)

        self.device_list_label = QLabel("Dispositivi Audio Bluetooth:")
        self.layout.addWidget(self.device_list_label)

        self.device_list_widget = QListWidget()
        self.layout.addWidget(self.device_list_widget)

        self.refresh_button = QPushButton("Aggiorna Elenco")
        self.refresh_button.clicked.connect(self.aggiorna_dispositivi)
        self.layout.addWidget(self.refresh_button)

        #self.setLayout(self.layout)

        self.aggiorna_dispositivi()
        #self.show()

    def esegui_comando_esterno(self, comando):
        try:
            risultato = subprocess.run(comando, capture_output=True, text=True, check=True, shell=True)
            return risultato.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"Errore comando esterno: {e}")
            print(f"Stdout: {e.stdout}")
            print(f"Stderr: {e.stderr}")
            return None
        except FileNotFoundError:
            print(f"Errore: Il comando '{comando[0]}' non è stato trovato. Assicurati che 'Bluetooth Command Line Tools' sia installato e nel PATH.")
            return None

    def aggiorna_dispositivi(self):
        waitCursor(True)
        self.device_list_widget.clear()
        comando = ["btdiscovery", "-i", "1", "-d", "%n%\t%c%\t%a%"]
        output = self.esegui_comando_esterno(comando)
        if output:
            for line in output.splitlines():
                line = line.strip()
                if line:
                    parts = line.split('\t')
                    if len(parts) == 3:
                        nome_dispositivo = parts[0].strip()
                        stato_connessione = parts[1].strip()
                        indirizzo_mac = parts[2].strip()
                        item_widget = DispositivoAudioItem(nome_dispositivo, stato_connessione, indirizzo_mac,
                                                           self)  # Passa 'self'
                        list_item = QListWidgetItem()
                        list_item.setSizeHint(item_widget.sizeHint())
                        self.device_list_widget.addItem(list_item)
                        self.device_list_widget.setItemWidget(list_item, item_widget)
        else:
            print("Nessun dispositivo Bluetooth trovato.")

        waitCursor()

    def connetti_dispositivo(self, indirizzo_mac):
        #s110b s111e
        '''Valori
        1101 no
        111e Microfono
        110e  no
        110d '''
        #comando = ["btcom", "-cs110b", "-b", indirizzo_mac] # Verifica la sintassi corretta con la tua versione di BT Tools
        comando = ["btcom", "-cs110d", "-cs110e", "-b", indirizzo_mac] # Verifica la sintassi corretta con la tua versione di BT Tools
        risultato = self.esegui_comando_esterno(comando)
        if risultato:
            print(f"Connessione a {indirizzo_mac}: {risultato}")
        self.aggiorna_dispositivi()

    def disconnetti_dispositivo(self, indirizzo_mac):
        comando = ["btcom", "-rs110b", "-b", indirizzo_mac] # Verifica la sintassi corretta con la tua versione di BT Tools
        risultato = self.esegui_comando_esterno(comando)
        if risultato:
            print(f"Disconnessione da {indirizzo_mac}: {risultato}")
        self.aggiorna_dispositivi()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BluetoothManager()
    window.show()
    sys.exit(app.exec())