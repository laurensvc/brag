; Inno Setup script for BragSetup.exe; windows\build.ps1 passes the defines below.
; Installs per user (no admin prompt) to %LOCALAPPDATA%\Programs\Brag. Settings in %APPDATA%\Brag are kept on uninstall.
#ifndef AppVersion
  #define AppVersion "0.0"
#endif
#define AppGuid "{6B0F8E2A-5C1D-4E7B-9A43-B7A2D51C9E10}"
; Shared with companion\desktop.py (RUN_KEY, RUN_VALUE, MUTEX), which this script can't import: keep both in step.
#define RunKey "Software\Microsoft\Windows\CurrentVersion\Run"
#define RunValue "Brag"
#define Mutex "BragCompanion"

[Setup]
AppId={#StringChange(AppGuid, "{", "{{")}
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
; Setup asks you to quit Brag before updating or uninstalling it
AppMutex={#Mutex}
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
; Only offered on a first install. On an update the player's current choice (the tray menu's "Start with
; Windows") stands: see [Registry] below.
Name: autostart; Description: "Start Brag when Windows starts (it waits in the tray)"; Check: not IsUpdate
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
; The startup entry is the one the tray menu's "Start with Windows" sets.
; First install: written if the player ticks the task. Update: rewritten (new path) only if it's already on.
; Uninstall: removed either way.
Root: HKCU; Subkey: "{#RunKey}"; ValueType: string; ValueName: "{#RunValue}"; ValueData: """{app}\Brag.exe"" --tray"; Tasks: autostart
Root: HKCU; Subkey: "{#RunKey}"; ValueType: string; ValueName: "{#RunValue}"; ValueData: """{app}\Brag.exe"" --tray"; Check: IsUpdate and AutostartIsOn
Root: HKCU; Subkey: "{#RunKey}"; ValueType: none; ValueName: "{#RunValue}"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\Brag.exe"; Description: "Open Brag"; Flags: nowait postinstall skipifsilent

[Code]
// Brag is already installed for this user: an update, not a first install.
function IsUpdate: Boolean;
begin
  Result := RegValueExists(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppGuid}_is1', 'UninstallString');
end;

// "Start with Windows" is on right now (set by an earlier install or the tray menu).
function AutostartIsOn: Boolean;
begin
  Result := RegValueExists(HKCU, '{#RunKey}', '{#RunValue}');
end;
