; Inno Setup 6 — bộ cài CadastralValidatorPro
; Cài theo người dùng (không cần quyền quản trị) vào %LOCALAPPDATA%\Programs\CadastralValidatorPro
#define AppName "CadastralValidatorPro"
#ifndef AppVersion
  #define AppVersion "0.2.0"
#endif

[Setup]
AppId={{6B0F2C8E-4E2B-4D8B-9C1A-5A1C0D5C8F21}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=CadastralValidatorPro
AppPublisherURL=https://github.com/letunglam1992/CadastralValidatorPro
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist_installer
OutputBaseFilename=CadastralValidatorPro_Setup_{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\CadastralValidatorPro.exe
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tao bieu tuong tren Desktop"; GroupDescription: "Tuy chon:"

[Files]
Source: "..\dist\CadastralValidatorPro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\CadastralValidatorPro"; Filename: "{app}\CadastralValidatorPro.exe"
Name: "{group}\Macro VBA xuat DGN (thu muc)"; Filename: "{app}\_internal\scripts\microstation"
Name: "{group}\Huong dan xuat DGN"; Filename: "{app}\_internal\docs\huong_dan_xuat_DGN_bang_macro.md"
Name: "{group}\Go cai dat CadastralValidatorPro"; Filename: "{uninstallexe}"
Name: "{autodesktop}\CadastralValidatorPro"; Filename: "{app}\CadastralValidatorPro.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CadastralValidatorPro.exe"; Description: "Chay CadastralValidatorPro"; Flags: nowait postinstall skipifsilent
