; Inno Setup script for AFK Auto Clicker
; Build with:  ISCC.exe installer.iss   (or run build_installer.bat)

#define MyAppName "AFK Auto Clicker"
#ifndef MyAppVersion
  #define MyAppVersion "1.0"
#endif
#define MyAppPublisher "Krueger"
#define MyAppExe "AFKClicker.exe"

[Setup]
; A stable unique id so upgrades replace cleanly. Keep this GUID for all versions.
AppId={{B7E3F2A1-4C9D-4E8B-9A2F-1D6C5E7A3B40}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
; Per-user install -> no admin prompt, no install-mode chooser (good for a game tool).
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
LicenseFile=C:\autoclicker\release\AFKClicker\LICENSE.txt
SetupIconFile=C:\autoclicker\icon.ico
OutputDir=C:\autoclicker\release\installer
OutputBaseFilename=AFKClicker-Setup-v{#MyAppVersion}
VersionInfoVersion=1.0.0.0
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "C:\autoclicker\release\AFKClicker\AFKClicker.exe";  DestDir: "{app}"; Flags: ignoreversion
Source: "C:\autoclicker\release\AFKClicker\_internal\*";     DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "C:\autoclicker\release\AFKClicker\README.txt";      DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "C:\autoclicker\release\AFKClicker\LICENSE.txt";     DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}";                Filename: "{app}\{#MyAppExe}"
Name: "{group}\Uninstall {#MyAppName}";      Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";          Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[UninstallDelete]
Type: files; Name: "{%USERPROFILE}\.afk_autoclicker_v3.json"
Type: files; Name: "{%USERPROFILE}\.afk_autoclicker.json"

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent
