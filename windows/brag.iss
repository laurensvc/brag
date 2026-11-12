; Inno Setup script for BragSetup.exe; windows\build.ps1 passes the defines below.
; Installs per user (no admin prompt) to %LOCALAPPDATA%\Programs\Brag. Settings in %APPDATA%\Brag are kept on uninstall.
#if Ver < EncodeVer(6, 6, 0)
  #error Brag's installer needs Inno Setup 6.6 or newer (its dark style and background image)
#endif
#ifndef AppVersion
  #define AppVersion "0.0"
#endif
; The pictures windows\installer_art.py draws (build.ps1 runs it)
#ifndef ArtDir
  #define ArtDir "..\build\installer-art"
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
; Setup asks you to quit Brag before updating or uninstalling it (a silent update waits for it: InitializeSetup)
AppMutex={#Mutex}
; Brag's look: dark, on the page's wood, with gold trim (windows\installer_art.py)
WizardStyle=modern dark hidebevels
WizardBackImageFile={#ArtDir}\wizard-back.png
WizardImageFile={#ArtDir}\wizard-image.png
WizardSmallImageFile={#ArtDir}\wizard-small.png
WizardImageBackColor=#14110d
WizardSmallImageBackColor=none
; the Welcome page shows the crest picture and the pitch (the modern style leaves it out by default)
DisableWelcomePage=no
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Messages]
; The wording, with some Brag flavor. Names and placeholders: Inno Setup's Default.isl.
WelcomeLabel1=Welcome, adventurer
WelcomeLabel2=Brag posts your big WoW moments to Discord the moment they happen: level ups, epic loot, dungeon and raid runs, and yes, your deaths too.%n%nThis installs [name/ver]. It takes a few seconds and doesn't need admin rights.
WizardSelectTasks=A couple of choices
SelectTasksDesc=How should Brag start?
SelectTasksLabel2=Pick what you like, then click Next.
WizardReady=Ready to brag
ReadyLabel1=Everything's packed. Brag is ready to move in.
ReadyLabel2a=Click Install, or Back to change your choices.
ReadyLabel2b=Click Install.
WizardInstalling=Installing
InstallingLabel=Polishing the trophies and sharpening the captions...
FinishedHeadingLabel=Brag is installed!
FinishedLabelNoIcons=Brag waits in the tray next to the clock. Open it to connect Discord, then go do something worth bragging about.
FinishedLabel=Brag waits in the tray next to the clock. Open it to connect Discord, then go do something worth bragging about.
SetupAppRunningError=Brag is running. Quit it first: right-click its icon next to the clock and pick Quit. Then click OK.
UninstallAppRunningError=Brag is running. Quit it first: right-click its icon next to the clock and pick Quit. Then click OK.
ExitSetupMessage=Brag isn't installed yet. Leave anyway?%n%nYou can run this again any time.
ConfirmUninstall=Remove %1? Your Discord link and post history are kept, in case you come back.
UninstalledAll=%1 is removed. No more bragging... for now.

[Tasks]
; Only offered on a first install. On an update the player's current choice (the tray menu's "Start with
; Windows") stands: see [Registry] below.
Name: autostart; Description: "Start Brag with Windows, so it's always ready (it waits in the tray)"; Check: not IsUpdate
Name: desktopicon; Description: "Put Brag on the desktop"; Flags: unchecked

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
Filename: "{app}\Brag.exe"; Description: "Open Brag and connect Discord"; Flags: nowait postinstall skipifsilent
; Brag updating itself runs Setup silently with /RELAUNCH (desktop.py install_update): start the new Brag
Filename: "{app}\Brag.exe"; Flags: nowait; Check: Relaunch

[Code]
// Brag updating itself starts this Setup and then quits. Silent Setup waits for it to close (up to 20 seconds),
// before AppMutex would stop the update with "Brag is running".
function InitializeSetup: Boolean;
var
  I: Integer;
begin
  I := 0;
  while WizardSilent and CheckForMutexes('{#Mutex}') and (I < 80) do
  begin
    Sleep(250);
    I := I + 1;
  end;
  Result := True;
end;

// Setup was started with /RELAUNCH: Brag updating itself.
function Relaunch: Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), '/RELAUNCH') = 0 then
      Result := True;
end;

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
