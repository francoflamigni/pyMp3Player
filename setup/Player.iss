#define MyAppName "Player"
#define MyReleaseVersion "1"
#define MyAppVersion "1.0"
#define MyAppPublisher "Mysoft"
#define MyAppURL ""
#define MyAppExeName "Player.exe"

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

Compression=lzma
SolidCompression=yes
UninstallDisplayIcon=.\icone\player.ico
UsePreviousAppDir=yes
WizardImageStretch=no
SetupIconFile=.\icone\player.ico
WizardImageFile=.\icone\splash.bmp
WizardSmallImageFile=.\icone\splash.bmp

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
 
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 0,6.1

[Files]
Source: "{#MyBaseDir}\installer\dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Registry]
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"; ValueType: String; ValueName: "{app}\{#MyAppName}\{#MyAppExeName}"; ValueData: "RUNASADMIN"; Flags: uninsdeletekeyifempty uninsdeletevalue;

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppName}\{#MyAppExeName}"; IconIndex: 0
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"; IconIndex: 0
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppName}\{#MyAppExeName}"; Tasks: desktopicon; IconIndex: 0

Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppName}\{#MyAppExeName}"; IconIndex: 0; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppName}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

