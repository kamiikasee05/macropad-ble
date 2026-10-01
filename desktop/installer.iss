; Inno Setup script del configurador MacropadFX.
; Compilar:  ISCC.exe installer.iss
; Requiere:  dist\MacropadFX\  (generado por build.ps1 / PyInstaller).
;
; Instala SIN admin en %LOCALAPPDATA%\Programs\MacropadFX.
; Autostart OPCIONAL (checkbox desmarcado por defecto).

#define MyAppName "MacropadFX"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "KAMIIKASEE"
#define MyAppExeName "MacropadFX.exe"

[Setup]
AppId={{B7C4E1D2-9A3F-4E58-B6D1-2C7A5F8E0A93}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename={#MyAppName}-Setup-{#MyAppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el Escritorio"; GroupDescription: "Accesos directos:"; Flags: checkedonce
Name: "autostart"; Description: "Iniciar {#MyAppName} con Windows"; GroupDescription: "Opciones:"; Flags: unchecked

[Files]
Source: "dist\MacropadFX\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName} ahora"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
