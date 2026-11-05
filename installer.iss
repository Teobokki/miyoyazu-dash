#define MyVer "1.0.0"
[Setup]
AppId={{DD54B7E7-3FF7-4CC2-8A96-B562E8341B00}
AppName=MIYOYAZU DASH
AppVersion={#MyVer}
AppVerName=MIYOYAZU DASH {#MyVer}
AppPublisher=EX Inc./HYPERION DIGITAL
AppPublisherURL=https://github.com/Teobokki/miyoyazu-dash
AppCopyright=©2026 EX Inc./HYPERION DIGITAL ©2026
VersionInfoVersion=1.0.0
VersionInfoCompany=EX Inc./HYPERION DIGITAL
VersionInfoCopyright=©2026 EX Inc./HYPERION DIGITAL ©2026
VersionInfoProductName=MIYOYAZU DASH
VersionInfoDescription=MIYOYAZU DASH Setup
DefaultDirName={localappdata}\Programs\MIYOYAZU DASH
DefaultGroupName=MIYOYAZU DASH
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=MIYOYAZU-DASH-Setup-{#MyVer}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\MIYOYAZU DASH.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=force

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "dist\MIYOYAZU DASH\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\MIYOYAZU DASH"; Filename: "{app}\MIYOYAZU DASH.exe"
Name: "{group}\Uninstall MIYOYAZU DASH"; Filename: "{uninstallexe}"
Name: "{userdesktop}\MIYOYAZU DASH"; Filename: "{app}\MIYOYAZU DASH.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MIYOYAZU DASH.exe"; Description: "Launch MIYOYAZU DASH now"; Flags: nowait postinstall skipifsilent
