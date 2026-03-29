#define MyAppName "Euterpe"
#define MyReleaseVersion "1"
#define MyAppVersion "1.5"
#define MyAppPublisher "Mysoft"
#define MyAppURL ""
#define MyAppExeName "Euterpe.exe"
#define MyBaseDir "C:\Users\franc\MySoft\PyMp3Player"

[Setup]
AppId={{FF49FD1A-5560-4A62-87D4-B96E2A27FF30}
AppName={#MyAppName}
AppVersion={#MyAppVersion}.{#MyReleaseVersion}
AppVerName={#MyAppName}-{#MyAppVersion}.{#MyReleaseVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={commonpf64}\{#MyAppPublisher}\
DefaultGroupName={#MyAppPublisher}\{#MyAppName}
OutputDir={#MyBaseDir}\setup
SourceDir={#MyBaseDir}
OutputBaseFilename={#MyAppName}_{#MyAppVersion}.{#MyReleaseVersion}_setup
ChangesAssociations=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64
; --- Personalizzazione Uninstaller ---
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} (Disinstalla)

; Grafica
SetupIconFile=.\icone\player.ico
WizardImageFile=.\icone\splash.bmp
WizardSmallImageFile=.\icone\splash_mini.bmp
Compression=lzma
SolidCompression=yes

UsePreviousAppDir=yes
WizardImageStretch=no

BackColor=$EBEAFC
BackColor2=$5BA17D
BackColorDirection=lefttoright
CloseApplications=yes 
MinVersion=6.1sp1

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Files]
Source: "{#MyBaseDir}\installer\dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "assoc_mp3"; Description: "Associa i file .mp3 a {#MyAppName}"; GroupDescription: "Associazioni file:"; Flags: checkedonce
Name: "assoc_flac"; Description: "Associa i file .flac a {#MyAppName}"; GroupDescription: "Associazioni file:"; Flags: checkedonce

[Registry]
; --- DEFINIZIONE PROGID UNIFICATO ---
Root: HKLM; Subkey: "Software\Classes\Euterpe.AssocFile.Audio"; ValueType: string; ValueName: ""; ValueData: "File Audio (Euterpe)"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Classes\Euterpe.AssocFile.Audio\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppName}\{#MyAppExeName},0"
Root: HKLM; Subkey: "Software\Classes\Euterpe.AssocFile.Audio\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppName}\{#MyAppExeName}"" ""%1"""

; --- REGISTRAZIONE ESTENSIONI (Collegate ai Task) ---
Root: HKLM; Subkey: "Software\Classes\.mp3\OpenWithProgids"; ValueType: string; ValueName: "Euterpe.AssocFile.Audio"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc_mp3
Root: HKLM; Subkey: "Software\Classes\.flac\OpenWithProgids"; ValueType: string; ValueName: "Euterpe.AssocFile.Audio"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc_flac

; --- CAPABILITIES (Necessarie per Windows 10/11) ---
Root: HKLM; Subkey: "Software\{#MyAppName}\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "{#MyAppName}"
Root: HKLM; Subkey: "Software\{#MyAppName}\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Player musicale leggero"
Root: HKLM; Subkey: "Software\{#MyAppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mp3"; ValueData: "Euterpe.AssocFile.Audio"; Tasks: assoc_mp3
Root: HKLM; Subkey: "Software\{#MyAppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".flac"; ValueData: "Euterpe.AssocFile.Audio"; Tasks: assoc_flac
Root: HKLM; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: "Software\{#MyAppName}\{#MyAppName}\Capabilities"; Flags: uninsdeletevalue

; --- APP PATHS ---
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#MyAppExeName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppName}\{#MyAppExeName}"; Flags: uninsdeletekey
[Run]
; Questo comando forza Windows a rinfrescare il database delle associazioni
Filename: "{app}\{#MyAppName}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppName}\{#MyAppExeName}"; IconIndex: 0
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"; IconIndex: 0
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppName}\{#MyAppExeName}"; Tasks: desktopicon; IconIndex: 0

