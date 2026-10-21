; Instalador por usuario (sin permisos de administrador). Se compila con tools/build_exe.py,
; que pasa /DAppVersion=X.Y.Z.
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6B1F6C0E-5A3D-4E57-9C11-3F2A7D8E4B01}
AppName=Riven Stock
AppVersion={#AppVersion}
AppPublisher=Franh01
DefaultDirName={autopf}\Riven Stock
DefaultGroupName=Riven Stock
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=RivenStock-v{#AppVersion}-Setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\RivenStock.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
Source: "..\build\dist\RivenStock\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Riven Stock"; Filename: "{app}\RivenStock.exe"
Name: "{autodesktop}\Riven Stock"; Filename: "{app}\RivenStock.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\RivenStock.exe"; Description: "{cm:LaunchProgram,Riven Stock}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\RivenStock.exe"; Flags: nowait skipifnotsilent
