#define MyAppName "Pirustudios Launcher"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Pirustudios"
#define MyAppExeName "PirustudiosLauncher.exe"

[Setup]
AppId={{7D9E2A31-4C66-4B9D-9A3F-8B1D5C27E410}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Pirustudios Launcher
DefaultGroupName=Pirustudios Launcher
OutputDir=..\dist-installer
OutputBaseFilename=PirustudiosLauncher-Setup-1.0.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\launcher.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin

[Files]
Source: "..\dist\PirustudiosLauncher\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\PirustudiosAdmin\*"; DestDir: "{app}\admin"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\config.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist

[Icons]
Name: "{autodesktop}\Pirustudios Launcher"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Pirustudios Launcher"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Pirustudios Admin"; Filename: "{app}\admin\PirustudiosAdmin.exe"; WorkingDir: "{app}\admin"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir Pirustudios Launcher"; Flags: nowait postinstall skipifsilent
