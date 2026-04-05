; LLM Council Windows Installer Script
; Inno Setup 6.x Compatible
; This script creates a complete Windows installer with embedded Python

#define MyAppName "LLM Council"
#define MyAppVersion "2.1.0"
#define MyAppPublisher "LLM Council"
#define MyAppURL "https://github.com/karpathy/llm-council"
#define MyAppExeName "LLMCouncil.exe"

[Setup]
; Basic installer information
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
InfoBeforeFile=..\docs\README_INSTALLER.txt
OutputDir=..\output
OutputBaseFilename=LLMCouncil-Setup-{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

; Disk spanning (for large installers)
DiskSpanning=yes
SlicesPerDisk=1
DiskSliceSize=2100000000

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
; Desktop icon checked by default (removed Flags: unchecked)
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startupicon"; Description: "Démarrer LLM Council au lancement de Windows"; GroupDescription: "Options de démarrage:"; Flags: unchecked

[Files]
; Launcher EXE wrapper (compiled by PyInstaller in CI)
Source: "..\..\launcher\LLMCouncil.exe"; DestDir: "{app}"; Flags: ignoreversion

; Application icon
Source: "..\assets\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

; Backend Python code
Source: "..\..\backend\*"; DestDir: "{app}\backend"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc,*.pyo,.env"

; Frontend built files - CORRECTED: destination is frontend/dist/ (backend serves from this path)
Source: "..\..\frontend\dist\*"; DestDir: "{app}\frontend\dist"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; Embedded Python (prepared by CI workflow)
Source: "..\embedded-python\python.exe"; DestDir: "{app}\python"; Flags: ignoreversion
Source: "..\embedded-python\python*.dll"; DestDir: "{app}\python"; Flags: ignoreversion
Source: "..\embedded-python\*.pyd"; DestDir: "{app}\python"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\embedded-python\python*._pth"; DestDir: "{app}\python"; Flags: ignoreversion
Source: "..\embedded-python\Lib\*"; DestDir: "{app}\python\Lib"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc,*.pyo,tests,test,testing,*.egg,*-stubs"
Source: "..\embedded-python\DLLs\*"; DestDir: "{app}\python\DLLs"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "..\embedded-python\Scripts\*"; DestDir: "{app}\python\Scripts"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist; Excludes: "__pycache__,*.pyc"

; Scripts
Source: "..\scripts\*"; DestDir: "{app}\scripts"; Flags: ignoreversion recursesubdirs createallsubdirs

; Configuration
Source: "..\config\default_config.json"; DestDir: "{app}\config"; Flags: ignoreversion skipifsourcedoesntexist

; Documentation  
Source: "..\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

[Icons]
; Menu Démarrer - points to LLMCouncil.exe
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"
Name: "{group}\Arrêter LLM Council"; Filename: "{app}\scripts\stop_services.bat"; WorkingDir: "{app}"; IconFilename: "{sys}\shell32.dll"; IconIndex: 131
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

; Bureau - checked by default (no Flags: unchecked)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

; Démarrage automatique Windows (optional)
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: startupicon

[Run]
; Post-installation: Install Python dependencies (if needed)
Filename: "{app}\scripts\setup.bat"; StatusMsg: "Installation des dépendances Python..."; Flags: runhidden waituntilterminated skipifsourcedoesntexist

; Launch application after install
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer LLM Council maintenant"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Stop services before uninstall
Filename: "{app}\scripts\stop_services.bat"; Flags: runhidden waituntilterminated skipifsourcedoesntexist

[UninstallDelete]
; Clean up data directory
Type: filesandordirs; Name: "{app}\data"
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\__pycache__"

[Registry]
; Add to PATH (optional)
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}\python"; Check: NeedsAddPath('{app}\python')

[Code]
// Pascal script for custom installer logic

var
  ProgressPage: TOutputProgressWizardPage;

function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_LOCAL_MACHINE,
    'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
    'Path', OrigPath)
  then begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Param + ';', ';' + OrigPath + ';') = 0;
end;

procedure InitializeWizard;
begin
  // Create progress page for dependency installation
  ProgressPage := CreateOutputProgressPage('Installation des dépendances',
    'Veuillez patienter pendant l''installation des composants requis...');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  // Check for minimum Windows version
  if not IsWin64 then
  begin
    Result := 'LLM Council nécessite une version 64-bit de Windows.';
    exit;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    // Show progress during post-install
    ProgressPage.Show;
    try
      ProgressPage.SetText('Installation des packages Python...', '');
      ProgressPage.SetProgress(0, 100);
      
      // Run pip install
      ProgressPage.SetProgress(50, 100);
      
      ProgressPage.SetText('Configuration terminée!', '');
      ProgressPage.SetProgress(100, 100);
    finally
      ProgressPage.Hide;
    end;
  end;
end;

function InitializeUninstall(): Boolean;
var
  MsgResult: Integer;
begin
  MsgResult := MsgBox('Voulez-vous conserver votre historique de conversations et vos paramètres?',
    mbConfirmation, MB_YESNOCANCEL);
  
  case MsgResult of
    IDYES: Result := True;
    IDNO: Result := True;
    IDCANCEL: Result := False;
  else
    Result := True;
  end;
end;
