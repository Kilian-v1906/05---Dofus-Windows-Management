; Inno Setup Script pour Dofus Organizer
; Nécessite Inno Setup 6 (gratuit: https://jrsoftware.org/isdl.php ou 'winget install JRSoftware.InnoSetup')

#define MyAppName "Dofus Organizer"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Kilian"
#define MyAppExeName "DofusOrganizer.exe"

[Setup]
AppId={{D0F050A1-8899-4A9B-B03F-9B1D8FE90271}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Permet une installation propre sans droits administrateurs obligatoires (dans %LOCALAPPDATA%\Programs)
PrivilegesRequired=lowest
OutputDir=release
OutputBaseFilename=DofusOrganizer_Setup_v{#MyAppVersion}
SetupIconFile=assets\icon\dwm.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

; Ferme automatiquement l'application si elle est en cours d'exécution avant mise à jour ou désinstallation
CloseApplications=yes
CloseApplicationsFilter=*.exe
RestartApplications=no

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Copie l'ensemble des fichiers générés par PyInstaller
Source: "dist\DofusOrganizer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icon\dwm.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icon\dwm.ico"; Tasks: desktopicon

[Run]
Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Filename: "{app}\{#MyAppExeName}"; Flags: nowait postinstall skipifsilent
