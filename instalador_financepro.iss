[Setup]
AppName=FinancePro
AppVersion=1.0
AppPublisher=FinancePro
DefaultDirName={autopf}\FinancePro
DefaultGroupName=FinancePro
OutputDir=.\instalador
OutputBaseFilename=FinancePro_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=logo.ico
[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Opções adicionais:"; Flags: unchecked

[Files]
Source: "dist\FinancePro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\FinancePro"; Filename: "{app}\FinancePro.exe"; IconFilename: "{app}\FinancePro.exe"
Name: "{autodesktop}\FinancePro"; Filename: "{app}\FinancePro.exe"; Tasks: desktopicon; IconFilename: "{app}\FinancePro.exe"

[Run]
Filename: "{app}\FinancePro.exe"; Description: "Abrir FinancePro agora"; Flags: nowait postinstall skipifsilent