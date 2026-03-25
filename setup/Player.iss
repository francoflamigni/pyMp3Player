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
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={commonpf64}\{#MyAppPublisher}\
DefaultGroupName={#MyAppPublisher}\{#MyAppName}
OutputDir={#MyBaseDir}\setup
SourceDir={#MyBaseDir}
OutputBaseFilename={#MyAppName}_{#MyAppVersion}.{#MyReleaseVersion}_setup
ChangesAssociations=yes
PrivilegesRequiredOverridesAllowed=dialog

Compression=lzma
SolidCompression=yes
UninstallDisplayIcon={app}\{#MyAppName}\{#MyAppExeName}
UsePreviousAppDir=yes
WizardImageStretch=no
SetupIconFile=.\icone\player.ico
WizardImageFile=.\icone\splash.bmp
WizardSmallImageFile=.\icone\splash_mini.bmp

BackColor=$EBEAFC
BackColor2=$5BA17D
BackColorDirection=lefttoright
CloseApplications=yes 
MinVersion=6.1sp1
PrivilegesRequired=admin
ArchitecturesAllowed=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "Spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
 
[Files]
Source: "{#MyBaseDir}\installer\dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "assoc_mp3"; Description: "Associa i file .mp3 a Euterpe"; GroupDescription: "Associazioni file:"; Flags: checkedonce
Name: "assoc_flac"; Description: "Associa i file .flac a Euterpe"; GroupDescription: "Associazioni file:"; Flags: checkedonce

[Registry]
Root: HKCR; Subkey: ".mp3\OpenWithProgids"; ValueType: string; ValueName: "Euterpe.AssocFile.MP3"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc_mp3
Root: HKCR; Subkey: "Euterpe.AssocFile.MP3"; ValueType: string; ValueName: ""; ValueData: "File Audio MP3"; Flags: uninsdeletekey; Tasks: assoc_mp3
Root: HKCR; Subkey: "Euterpe.AssocFile.MP3\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppName}\{#MyAppExeName},0"; Tasks: assoc_mp3
Root: HKCR; Subkey: "Euterpe.AssocFile.MP3\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppName}\{#MyAppExeName}"" ""%1"""; Tasks: assoc_mp3

; --- ASSOCIAZIONE FLAC ---
Root: HKCR; Subkey: ".flac\OpenWithProgids"; ValueType: string; ValueName: "Euterpe.AssocFile.FLAC"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc_flac
Root: HKCR; Subkey: "Euterpe.AssocFile.FLAC"; ValueType: string; ValueName: ""; ValueData: "File Audio FLAC"; Flags: uninsdeletekey; Tasks: assoc_flac
Root: HKCR; Subkey: "Euterpe.AssocFile.FLAC\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"; Tasks: assoc_flac
Root: HKCR; Subkey: "Euterpe.AssocFile.FLAC\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: assoc_flac

[Run]
; Apri le impostazioni di Windows per completare l'associazione
Filename: "ms-settings:defaultapps"; Description: "Apri impostazioni per impostare Euterpe come app predefinita"; Flags: postinstall nowait skipifsilent runasoriginaluser; Tasks: assoc_mp3
Filename: "{app}\{#MyAppName}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppName}\{#MyAppExeName}"; IconIndex: 0
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"; IconIndex: 0
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppName}\{#MyAppExeName}"; Tasks: desktopicon; IconIndex: 0


