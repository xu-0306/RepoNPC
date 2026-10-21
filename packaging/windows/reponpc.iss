; Build with /DAppVersion=<pyproject version> /DBuildRoot=<onedir path>
; /DOutputRoot=<installer output directory>. No generated recipe is required.
#ifndef AppVersion
  #error AppVersion must be supplied from pyproject.toml
#endif
#if AppVersion == ""
  #error AppVersion must not be empty
#endif
#ifndef BuildRoot
  #error BuildRoot must be supplied
#endif
#if BuildRoot == ""
  #error BuildRoot must not be empty
#endif
#ifndef OutputRoot
  #error OutputRoot must be supplied
#endif
#if OutputRoot == ""
  #error OutputRoot must not be empty
#endif
#if !FileExists(BuildRoot + "\RepoNPC.exe")
  #error BuildRoot must contain the built RepoNPC.exe launcher
#endif

; The launcher owns {localappdata}\RepoNPC\data, including secrets and models.
; Setup and uninstall only manage the separate program directory and shortcuts.
[Setup]
AppId={{9B5F80E7-BE26-49B4-9939-9F85D69FF4EC}
AppName=RepoNPC
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\RepoNPC
DefaultGroupName=RepoNPC
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible and not arm64
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.22000
OutputDir={#OutputRoot}
OutputBaseFilename=RepoNPC-Setup-{#AppVersion}
Uninstallable=yes
UninstallDisplayIcon={app}\RepoNPC.exe
RestartApplications=no
Compression=lzma2
SolidCompression=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#BuildRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\RepoNPC"; Filename: "{app}\RepoNPC.exe"; WorkingDir: "{app}"
Name: "{group}\RepoNPC（正式模式）"; Filename: "{app}\RepoNPC.exe"; Parameters: "--profile production"; WorkingDir: "{app}"
Name: "{autodesktop}\RepoNPC"; Filename: "{app}\RepoNPC.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\RepoNPC.exe"; WorkingDir: "{app}"; Description: "Open RepoNPC"; Flags: postinstall nowait skipifsilent unchecked
