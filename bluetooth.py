import subprocess
import json
import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QListWidget,
                             QListWidgetItem, QGroupBox, QMessageBox, QSplitter, QDialog, QStatusBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

from utility import get_windows_flag

class BluetoothWorker(QThread):
    """Thread separato per operazioni Bluetooth che potrebbero bloccare l'UI"""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, operation, *args):
        super().__init__()
        self.operation = operation
        self.args = args

    def run(self):
        try:
            result = self.operation(*self.args)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class BluetoothAudioManager:
    """Gestisce connessione/disconnessione dispositivi audio Bluetooth via PowerShell"""

    @staticmethod
    def check_and_install_module():
        """Verifica e installa il modulo AudioDeviceCmdlets se necessario"""
        check_script = """
        if (!(Get-Module -ListAvailable -Name AudioDeviceCmdlets)) {
            Write-Output "NOT_INSTALLED"
        } else {
            Write-Output "INSTALLED"
        }
        """
        result = subprocess.run(
            ["powershell", "-Command", check_script],
            capture_output=True,
            text=True, creationflags=get_windows_flag()
        )

        if "NOT_INSTALLED" in result.stdout:
            install_script = """
            Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
            Install-Module -Name AudioDeviceCmdlets -Force -Scope CurrentUser -AllowClobber
            """
            subprocess.run(
                ["powershell", "-Command", install_script],
                check=True, creationflags=get_windows_flag()
            )
            return "INSTALLED"
        return "ALREADY_INSTALLED"

    @staticmethod
    def get_bluetooth_devices_real_status():
        """Ottiene lo stato REALE della connessione Bluetooth"""
        ps_script = """
        Add-Type -AssemblyName System.Runtime.WindowsRuntime
        $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
        Function Await($WinRtTask, $ResultType) {
            $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
            $netTask = $asTask.Invoke($null, @($WinRtTask))
            $netTask.Wait(-1) | Out-Null
            $netTask.Result
        }

        [Windows.Devices.Enumeration.DeviceInformation,Windows.Devices.Enumeration,ContentType=WindowsRuntime] | Out-Null
        [Windows.Devices.Bluetooth.BluetoothDevice,Windows.Devices.Bluetooth,ContentType=WindowsRuntime] | Out-Null

        $deviceSelector = [Windows.Devices.Bluetooth.BluetoothDevice]::GetDeviceSelector()
        $devices = Await ([Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync($deviceSelector)) ([Windows.Devices.Enumeration.DeviceInformationCollection])

        $result = @()
        foreach ($device in $devices) {
            try {
                $btDevice = Await ([Windows.Devices.Bluetooth.BluetoothDevice]::FromIdAsync($device.Id)) ([Windows.Devices.Bluetooth.BluetoothDevice])

                $result += [PSCustomObject]@{
                    Name = $device.Name
                    Connected = $btDevice.ConnectionStatus -eq 'Connected'
                    Address = if ($btDevice.BluetoothAddress) { 
                        '{0:X12}' -f $btDevice.BluetoothAddress 
                    } else { 
                        'N/A' 
                    }
                    DeviceId = $device.Id
                }
                $btDevice.Dispose()
            } catch {
                # Ignora dispositivi che non possono essere aperti
            }
        }
        $result | ConvertTo-Json
        """

        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10, creationflags=get_windows_flag()
        )

        if result.returncode == 0 and result.stdout.strip():
            try:
                devices = json.loads(result.stdout)
                if isinstance(devices, dict):
                    devices = [devices]
                return devices
            except json.JSONDecodeError:
                return []
        return []

    @staticmethod
    def get_audio_devices():
        """Ottiene la lista di tutti i dispositivi audio"""
        ps_script = """
        Get-AudioDevice -List | Select-Object Index, Name, Type, Default | ConvertTo-Json
        """
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=5, creationflags=get_windows_flag()
        )

        if result.returncode == 0 and result.stdout.strip():
            try:
                devices = json.loads(result.stdout)
                if isinstance(devices, dict):
                    devices = [devices]
                return devices
            except json.JSONDecodeError:
                return []
        return []

    '''
    @staticmethod
    def connect_bluetooth_device(device_name):
        """Connette un dispositivo Bluetooth per nome"""
        ps_script = f"""
        Add-Type -AssemblyName System.Runtime.WindowsRuntime
        $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {{ $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' }})[0]
        Function Await($WinRtTask, $ResultType) {{
            $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
            $netTask = $asTask.Invoke($null, @($WinRtTask))
            $netTask.Wait(-1) | Out-Null
            $netTask.Result
        }}

        [Windows.Devices.Enumeration.DeviceInformation,Windows.Devices.Enumeration,ContentType=WindowsRuntime] | Out-Null
        [Windows.Devices.Bluetooth.BluetoothDevice,Windows.Devices.Bluetooth,ContentType=WindowsRuntime] | Out-Null

        $deviceSelector = [Windows.Devices.Bluetooth.BluetoothDevice]::GetDeviceSelector()
        $devices = Await ([Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync($deviceSelector)) ([Windows.Devices.Enumeration.DeviceInformationCollection])

        $found = $false
        foreach ($device in $devices) {{
            if ($device.Name -like "*{device_name}*") {{
                $found = $true
                try {{
                    $btDevice = Await ([Windows.Devices.Bluetooth.BluetoothDevice]::FromIdAsync($device.Id)) ([Windows.Devices.Bluetooth.BluetoothDevice])

                    if ($btDevice.ConnectionStatus -eq 'Connected') {{
                        Write-Output "ALREADY_CONNECTED"
                    }} else {{
                        $services = Await ($btDevice.GetRfcommServicesAsync()) ([Windows.Devices.Bluetooth.Rfcomm.RfcommDeviceServicesResult])
                        if ($services.Services.Count -gt 0) {{
                            Write-Output "CONNECTED"
                        }} else {{
                            Write-Output "NO_SERVICES"
                        }}
                    }}
                    $btDevice.Dispose()
                    break
                }} catch {{
                    Write-Output "ERROR: $_"
                }}
            }}
        }}
        if (-not $found) {{
            Write-Output "NOT_FOUND"
        }}
        """

        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=15, creationflags=get_windows_flag()
        )

        return result.stdout.strip()
    '''

    @staticmethod
    def set_default_audio_device(device_name):
        """Imposta un dispositivo come predefinito per l'audio"""
        ps_script = f"""
        $device = Get-AudioDevice -List | Where-Object {{$_.Name -like "*{device_name}*"}}
        if ($device) {{
            Set-AudioDevice -Index $device.Index
            Write-Output "SET_DEFAULT"
        }} else {{
            Write-Output "NOT_FOUND"
        }}
        """
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=5, creationflags=get_windows_flag()
        )

        return result.stdout.strip()

    @staticmethod
    def open_bluetooth_settings():
        """Apre le impostazioni Bluetooth di Windows"""
        subprocess.run(["start", "ms-settings:bluetooth"], shell=True)

    @staticmethod
    def open_sound_settings():
        """Apre le impostazioni audio di Windows"""
        subprocess.run(["start", "ms-settings:sound"], shell=True)


class BluetoothManager(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bluetooth Audio Manager")
        self.setMinimumSize(750, 300)

        # Check modulo PowerShell
        self.check_powershell_module()

        # Setup UI
        self.setup_ui()

        # Timer per refresh automatico
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_devices)
        self.refresh_timer.start(5000)  # Refresh ogni 5 secondi

        # Carica dispositivi iniziali
        self.refresh_devices()

    def check_powershell_module(self):
        """Verifica il modulo PowerShell all'avvio"""
        try:
            status = BluetoothAudioManager.check_and_install_module()
            if status == "INSTALLED":
                QMessageBox.information(
                    self,
                    "Modulo Installato",
                    "Il modulo AudioDeviceCmdlets è stato installato con successo!"
                )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Errore",
                f"Errore durante la verifica del modulo PowerShell:\n{str(e)}"
            )

    def setup_ui(self):
        """Configura l'interfaccia utente"""
        #central_widget = QWidget()
        #self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(self)

        # Titolo
        '''
        title_label = QLabel("🎧 Bluetooth Audio Manager")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        '''

        # Splitter per dividere Bluetooth e Audio
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Sezione Bluetooth ---
        bluetooth_group = QGroupBox("Dispositivi Bluetooth")
        bluetooth_layout = QVBoxLayout()

        self.bluetooth_list = QListWidget()
        self.bluetooth_list.itemClicked.connect(self.on_bluetooth_device_selected)
        bluetooth_layout.addWidget(self.bluetooth_list)

        ''''
        bt_buttons_layout = QHBoxLayout()
        self.btn_connect = QPushButton("🔗 Connetti")
        self.btn_connect.clicked.connect(self.connect_device)
        self.btn_connect.setEnabled(False)

        self.btn_disconnect = QPushButton("🔌 Disconnetti")
        self.btn_disconnect.clicked.connect(self.disconnect_device)
        self.btn_disconnect.setEnabled(False)

        bt_buttons_layout.addWidget(self.btn_connect)
        bt_buttons_layout.addWidget(self.btn_disconnect)
        bluetooth_layout.addLayout(bt_buttons_layout)
        '''

        bluetooth_group.setLayout(bluetooth_layout)
        splitter.addWidget(bluetooth_group)

        # --- Sezione Audio ---
        audio_group = QGroupBox("Dispositivi Audio")
        audio_layout = QVBoxLayout()

        self.audio_list = QListWidget()
        self.audio_list.itemClicked.connect(self.on_audio_device_selected)
        audio_layout.addWidget(self.audio_list)

        #self.btn_set_default = QPushButton("⭐ Imposta come Predefinito")
        #self.btn_set_default.clicked.connect(self.set_default_device)
        #self.btn_set_default.setEnabled(False)
        #audio_layout.addWidget(self.btn_set_default)

        audio_group.setLayout(audio_layout)
        splitter.addWidget(audio_group)

        main_layout.addWidget(splitter)

        # --- Barra di controllo inferiore ---
        control_layout = QHBoxLayout()

        self.btn_refresh = QPushButton("🔄 Aggiorna")
        self.btn_refresh.clicked.connect(self.refresh_devices)

        self.btn_bt_settings = QPushButton("⚙️ Impostazioni Bluetooth")
        self.btn_bt_settings.clicked.connect(BluetoothAudioManager.open_bluetooth_settings)

        self.btn_sound_settings = QPushButton("🔊 Impostazioni Audio")
        self.btn_sound_settings.clicked.connect(BluetoothAudioManager.open_sound_settings)

        control_layout.addWidget(self.btn_refresh)
        control_layout.addStretch()
        control_layout.addWidget(self.btn_bt_settings)
        control_layout.addWidget(self.btn_sound_settings)

        main_layout.addLayout(control_layout)

        # Status bar
        self.statusBar = QStatusBar(self)
        main_layout.addStretch(1)
        main_layout.addWidget(self.statusBar)
        self.statusBar.showMessage("Pronto")

    def refresh_devices(self):
        """Aggiorna la lista dei dispositivi"""
        self.statusBar.showMessage("Caricamento dispositivi...")
        self.btn_refresh.setEnabled(False)

        # Thread per Bluetooth
        self.bt_worker = BluetoothWorker(BluetoothAudioManager.get_bluetooth_devices_real_status)
        self.bt_worker.finished.connect(self.update_bluetooth_list)
        self.bt_worker.error.connect(self.on_error)
        self.bt_worker.start()

        # Thread per Audio
        self.audio_worker = BluetoothWorker(BluetoothAudioManager.get_audio_devices)
        self.audio_worker.finished.connect(self.update_audio_list)
        self.audio_worker.error.connect(self.on_error)
        self.audio_worker.start()

    def update_bluetooth_list(self, devices):
        """Aggiorna la lista dei dispositivi Bluetooth"""
        self.bluetooth_list.clear()

        if not devices:
            item = QListWidgetItem("Nessun dispositivo Bluetooth trovato")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.bluetooth_list.addItem(item)
            self.btn_refresh.setEnabled(True)
            self.statusBar().showMessage("Nessun dispositivo Bluetooth trovato")
            return

        for device in devices:
            status_icon = "🟢" if device['Connected'] else "⚪"
            status_text = "Connesso" if device['Connected'] else ""
            address = device['DeviceId'].rsplit('-', 1)[1]

            item = QListWidgetItem(f"{status_icon} {device['Name']} ({address})  {status_text}")
            item.setData(Qt.ItemDataRole.UserRole, device)
            self.bluetooth_list.addItem(item)

        self.btn_refresh.setEnabled(True)
        self.statusBar.showMessage(f"Trovati {len(devices)} dispositivi Bluetooth")

    def update_audio_list(self, devices):
        """Aggiorna la lista dei dispositivi audio"""
        self.audio_list.clear()

        if not devices:
            item = QListWidgetItem("Nessun dispositivo audio trovato")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.audio_list.addItem(item)
            return

        for device in devices:
            default_icon = "⭐" if device.get('Default') else "  "
            item = QListWidgetItem(f"{default_icon} [{device['Index']}] {device['Name']} ({device['Type']})")
            item.setData(Qt.ItemDataRole.UserRole, device)
            self.audio_list.addItem(item)

    def on_bluetooth_device_selected(self, item):
        """Gestisce la selezione di un dispositivo Bluetooth"""
        device = item.data(Qt.ItemDataRole.UserRole)
        if device:
            is_connected = device['Connected']
            self.btn_connect.setEnabled(not is_connected)
            self.btn_disconnect.setEnabled(is_connected)

    def on_audio_device_selected(self, item):
        """Gestisce la selezione di un dispositivo audio"""
        device = item.data(Qt.ItemDataRole.UserRole)
        if device:
            is_default = device.get('Default', False)
            self.btn_set_default.setEnabled(not is_default)

    '''
    def connect_device(self):
        """Connette il dispositivo Bluetooth selezionato"""
        current_item = self.bluetooth_list.currentItem()
        if not current_item:
            return

        device = current_item.data(Qt.ItemDataRole.UserRole)
        device_name = device['Name']

        self.statusBar.showMessage(f"Connessione a {device_name}...")
        self.btn_connect.setEnabled(False)

        worker = BluetoothWorker(BluetoothAudioManager.connect_bluetooth_device, device_name)
        worker.finished.connect(lambda result: self.on_connect_finished(device_name, result))
        worker.error.connect(self.on_error)
        worker.start()
    '''

    def on_connect_finished(self, device_name, result):
        """Gestisce il risultato della connessione"""
        if "CONNECTED" in result:
            QMessageBox.information(self, "Successo", f"Dispositivo '{device_name}' connesso!")
        elif "ALREADY_CONNECTED" in result:
            QMessageBox.information(self, "Info", f"Dispositivo '{device_name}' già connesso")
        elif "NOT_FOUND" in result:
            QMessageBox.warning(self, "Errore", f"Dispositivo '{device_name}' non trovato")
        elif "NO_SERVICES" in result:
            QMessageBox.warning(
                self,
                "Attenzione",
                f"Impossibile connettere '{device_name}' automaticamente.\n"
                "Prova tramite le impostazioni Bluetooth di Windows."
            )

        self.refresh_devices()

    '''
    def disconnect_device(self):
        """Disconnette il dispositivo (apre impostazioni)"""
        current_item = self.bluetooth_list.currentItem()
        if not current_item:
            return

        device = current_item.data(Qt.ItemDataRole.UserRole)

        reply = QMessageBox.question(
            self,
            "Disconnessione",
            f"Windows non permette la disconnessione programmatica.\n"
            f"Vuoi aprire le impostazioni Bluetooth per disconnettere '{device['Name']}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            BluetoothAudioManager.open_bluetooth_settings()
    '''

    def set_default_device(self):
        """Imposta il dispositivo audio come predefinito"""
        current_item = self.audio_list.currentItem()
        if not current_item:
            return

        device = current_item.data(Qt.ItemDataRole.UserRole)
        device_name = device['Name']

        self.statusBar.showMessage(f"Impostazione {device_name} come predefinito...")
        self.btn_set_default.setEnabled(False)

        worker = BluetoothWorker(BluetoothAudioManager.set_default_audio_device, device_name)
        worker.finished.connect(lambda result: self.on_set_default_finished(device_name, result))
        worker.error.connect(self.on_error)
        worker.start()

    def on_set_default_finished(self, device_name, result):
        """Gestisce il risultato dell'impostazione predefinita"""
        if "SET_DEFAULT" in result:
            QMessageBox.information(self, "Successo", f"'{device_name}' impostato come predefinito!")
        else:
            QMessageBox.warning(self, "Errore", f"Impossibile impostare '{device_name}' come predefinito")

        self.refresh_devices()

    def on_error(self, error_msg):
        """Gestisce gli errori"""
        QMessageBox.critical(self, "Errore", f"Si è verificato un errore:\n{error_msg}")
        self.btn_refresh.setEnabled(True)
        self.statusBar.showMessage("Errore durante l'operazione")


'''
def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Stile moderno

    window = BluetoothManager()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
'''