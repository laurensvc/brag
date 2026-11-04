; Inno Setup script for BragSetup.exe; windows\build.ps1 passes the defines below.
; Installs per user (no admin prompt) to %LOCALAPPDATA%\Programs\Brag. Settings in %APPDATA%\Brag are kept on uninstall.
#ifndef AppVersion
  #define AppVersion "0.0"
#endif

[Setup]
AppId={{6B0F8E2A-5C1D-4E7B-9A43-B7A2D51C9E10}
AppName=Brag
AppVersion={#AppVersion}
AppVerName=Brag {#AppVersion}
AppPublisher=Brag
AppPublisherURL=https://github.com/laurensvc/brag
DefaultDirName={autopf}\Brag
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=BragSetup
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\Brag.exe
; desktop.py holds this mutex: Setup asks you to quit Brag before updating or uninstalling it
AppMutex=BragCompanion
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: autostart; Description: "Start Brag when Windows starts (it waits in the tray)"
Name: desktopicon; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; an update replaces the whole bundle, so no stale libraries are left behind
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\Brag"; Filename: "{app}\Brag.exe"
Name: "{autodesktop}\Brag"; Filename: "{app}\Brag.exe"; Tasks: desktopicon

[Registry]
; the same value the tray menu's "Start with Windows" sets; removed on uninstall either way
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Brag"; ValueData: """{app}\Brag.exe"" --tray"; Tasks: autostart
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "Brag"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\Brag.exe"; Description: "Open Brag"; Flags: nowait postinstall skipifsilent
