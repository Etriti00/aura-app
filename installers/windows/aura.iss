; Aura -- Windows installer (Inno Setup 6)
; Produces AuraSetup.exe, a real install wizard with Start Menu and
; desktop shortcuts, uninstaller, and the Aura icon throughout.

#define AppName "Aura"
#define AppVersion GetEnv("AURA_VERSION")
#if AppVersion == ""
  #define AppVersion "2.6.0"
#endif
#define AppPublisher "Etrit Neziri"
#define AppURL "https://github.com/Etriti00/aura-app"
#define AppExe "Aura.exe"

[Setup]
AppId={{A1B2C3D4-0AE4-4AE4-A000-AURASALESAGENT}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputBaseFilename=AuraSetup
OutputDir=installer-out
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\..\assets\icons\aura_icon.ico
UninstallDisplayIcon={app}\{#AppExe}
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
; The PyInstaller onedir output is staged at installer-in\ by the CI job.
Source: "installer-in\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent
