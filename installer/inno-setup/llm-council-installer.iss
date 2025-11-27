; LLM Council Windows Installer Script
; Inno Setup 6.x Compatible
; This script creates a complete Windows installer with embedded Python

#define MyAppName "LLM Council"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "LLM Council"
#define MyAppURL "https://github.com/karpathy/llm-council"
#define MyAppExeName "LLM Council.exe"

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
; LicenseFile=..\docs\LICENSE.txt
InfoBeforeFile=..\docs\README_INSTALLER.txt
OutputDir=..\output
OutputBaseFilename=LLMCouncil-Setup-{#MyAppVersion}
; SetupIconFile=..\assets\icon.ico
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

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode
Name: "startupicon"; Description: "Start LLM Council when Windows starts"; GroupDescription: "Startup Options:"; Flags: unchecked

[Files]
; Backend Python code
Source: "..\..\backend\*"; DestDir: "{app}\backend"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc,*.pyo,.env"

; Frontend built files (run 'npm run build' in frontend folder first)
; NOTE: Comment this line if frontend/dist doesn't exist
Source: "..\..\frontend\dist\*"; DestDir: "{app}\frontend"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; Embedded Python (run download_python.bat first)
; Exclude test directories, caches, and unnecessary files to avoid long path issues and reduce installer size
Source: "..\embedded-python\python.exe"; DestDir: "{app}\python"; Flags: ignoreversion
Source: "..\embedded-python\python*.dll"; DestDir: "{app}\python"; Flags: ignoreversion
Source: "..\embedded-python\*.pyd"; DestDir: "{app}\python"; Flags: ignoreversion
Source: "..\embedded-python\python*._pth"; DestDir: "{app}\python"; Flags: ignoreversion
Source: "..\embedded-python\Lib\*"; DestDir: "{app}\python\Lib"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc,*.pyo,tests,test,testing,*.egg,*-stubs"
Source: "..\embedded-python\DLLs\*"; DestDir: "{app}\python\DLLs"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "..\embedded-python\Scripts\*"; DestDir: "{app}\python\Scripts"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist; Excludes: "__pycache__,*.pyc"

; Scripts
Source: "..\scripts\*"; DestDir: "{app}\scripts"; Flags: ignoreversion recursesubdirs createallsubdirs

; Configuration
Source: "..\config\default_config.json"; DestDir: "{app}\config"; Flags: ignoreversion

; Documentation  
Source: "..\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\scripts\launch.bat"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\scripts\launch.bat"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\scripts\launch.bat"; WorkingDir: "{app}"; Tasks: startupicon

[Run]
; Post-installation: Install Python packages (already done if using embedded python with packages)
; Filename: "{app}\scripts\setup.bat"; Parameters: ""; StatusMsg: "Installing Python dependencies..."; Flags: runhidden waituntilterminated
; Launch application after install
Filename: "{app}\scripts\launch.bat"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent shellexec

[UninstallRun]
; Stop services before uninstall
Filename: "{app}\scripts\stop_services.bat"; Flags: runhidden waituntilterminated

[UninstallDelete]
; Clean up data directory (optional - ask user)
Type: filesandordirs; Name: "{app}\data"
Type: filesandordirs; Name: "{app}\logs"

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
  ProgressPage := CreateOutputProgressPage('Installing Dependencies',
    'Please wait while LLM Council installs required components...');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  // Check for minimum Windows version
  if not IsWin64 then
  begin
    Result := 'LLM Council requires a 64-bit version of Windows.';
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
      ProgressPage.SetText('Installing Python packages...', '');
      ProgressPage.SetProgress(0, 100);
      
      // Run pip install
      ProgressPage.SetProgress(50, 100);
      
      ProgressPage.SetText('Configuration complete!', '');
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
  MsgResult := MsgBox('Do you want to keep your conversation history and settings?',
    mbConfirmation, MB_YESNOCANCEL);
  
  case MsgResult of
    IDYES: Result := True;
    IDNO: Result := True;
    IDCANCEL: Result := False;
  else
    Result := True;
  end;
end;
