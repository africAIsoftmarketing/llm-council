; LLM Council NSIS Installer Script
; Alternative to Inno Setup
; NSIS 3.x Compatible

!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"

; =====================
; General Settings
; =====================

Name "LLM Council"
OutFile "..\output\LLMCouncil-Setup-2.0.0.exe"
InstallDir "$PROGRAMFILES64\LLM Council"
InstallDirRegKey HKLM "Software\LLM Council" "InstallDir"
RequestExecutionLevel admin

; Version Information
!define VERSION "2.0.0"
!define PRODUCT_NAME "LLM Council"
!define PRODUCT_PUBLISHER "LLM Council"
!define PRODUCT_WEB_SITE "https://github.com/karpathy/llm-council"

VIProductVersion "2.0.0.0"
VIAddVersionKey "ProductName" "${PRODUCT_NAME}"
VIAddVersionKey "CompanyName" "${PRODUCT_PUBLISHER}"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "ProductVersion" "${VERSION}"
VIAddVersionKey "FileDescription" "LLM Council Installer"

; =====================
; Interface Settings
; =====================

!define MUI_ABORTWARNING
!define MUI_ICON "..\assets\icon.ico"
!define MUI_UNICON "..\assets\icon.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "..\assets\wizard.bmp"

; Welcome page
!insertmacro MUI_PAGE_WELCOME

; License page
!insertmacro MUI_PAGE_LICENSE "..\..\LICENSE"

; Directory page
!insertmacro MUI_PAGE_DIRECTORY

; Components page
!insertmacro MUI_PAGE_COMPONENTS

; Install files page
!insertmacro MUI_PAGE_INSTFILES

; Finish page
!define MUI_FINISHPAGE_RUN "$INSTDIR\LLM Council.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch LLM Council"
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Language
!insertmacro MUI_LANGUAGE "English"

; =====================
; Sections
; =====================

Section "LLM Council (required)" SecMain
    SectionIn RO
    
    SetOutPath "$INSTDIR"
    
    ; Main application files
    File /r "..\electron-app\dist\win-unpacked\*.*"
    
    ; Backend
    SetOutPath "$INSTDIR\backend"
    File /r "..\..\backend\*.*"
    
    ; Frontend
    SetOutPath "$INSTDIR\frontend"
    File /r "..\..\frontend\dist\*.*"
    
    ; Embedded Python
    SetOutPath "$INSTDIR\python"
    File /r "..\embedded-python\*.*"
    
    ; Scripts
    SetOutPath "$INSTDIR\scripts"
    File "..\scripts\*.bat"
    File "..\scripts\launcher.py"
    
    ; Config
    SetOutPath "$INSTDIR\config"
    File "..\config\default_config.json"
    
    ; Docs
    SetOutPath "$INSTDIR\docs"
    File "..\docs\*.txt"
    File "..\docs\*.md"
    
    ; Create data directories
    CreateDirectory "$INSTDIR\data"
    CreateDirectory "$INSTDIR\data\conversations"
    CreateDirectory "$INSTDIR\data\documents"
    
    ; Write registry keys
    WriteRegStr HKLM "Software\LLM Council" "InstallDir" "$INSTDIR"
    WriteRegStr HKLM "Software\LLM Council" "Version" "${VERSION}"
    
    ; Uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    
    ; Add/Remove Programs entry
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LLMCouncil" "DisplayName" "${PRODUCT_NAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LLMCouncil" "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LLMCouncil" "DisplayIcon" "$INSTDIR\LLM Council.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LLMCouncil" "DisplayVersion" "${VERSION}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LLMCouncil" "Publisher" "${PRODUCT_PUBLISHER}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LLMCouncil" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
    
    ; Get installed size
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LLMCouncil" "EstimatedSize" "$0"
    
    ; Run post-install setup
    DetailPrint "Installing Python dependencies..."
    nsExec::ExecToLog '"$INSTDIR\scripts\setup.bat"'
    
SectionEnd

Section "Desktop Shortcut" SecDesktop
    CreateShortCut "$DESKTOP\LLM Council.lnk" "$INSTDIR\LLM Council.exe"
SectionEnd

Section "Start Menu Shortcuts" SecStartMenu
    CreateDirectory "$SMPROGRAMS\LLM Council"
    CreateShortCut "$SMPROGRAMS\LLM Council\LLM Council.lnk" "$INSTDIR\LLM Council.exe"
    CreateShortCut "$SMPROGRAMS\LLM Council\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
SectionEnd

; =====================
; Descriptions
; =====================

LangString DESC_SecMain ${LANG_ENGLISH} "Core LLM Council application files (required)"
LangString DESC_SecDesktop ${LANG_ENGLISH} "Create a desktop shortcut"
LangString DESC_SecStartMenu ${LANG_ENGLISH} "Create Start Menu shortcuts"

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} $(DESC_SecMain)
    !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} $(DESC_SecDesktop)
    !insertmacro MUI_DESCRIPTION_TEXT ${SecStartMenu} $(DESC_SecStartMenu)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; =====================
; Uninstaller
; =====================

Section "Uninstall"
    ; Stop services first
    nsExec::ExecToLog '"$INSTDIR\scripts\stop_services.bat"'
    
    ; Remove files
    RMDir /r "$INSTDIR\backend"
    RMDir /r "$INSTDIR\frontend"
    RMDir /r "$INSTDIR\python"
    RMDir /r "$INSTDIR\scripts"
    RMDir /r "$INSTDIR\config"
    RMDir /r "$INSTDIR\docs"
    
    ; Ask about data
    MessageBox MB_YESNO "Do you want to keep your conversations and documents?" IDYES KeepData
    RMDir /r "$INSTDIR\data"
    KeepData:
    
    Delete "$INSTDIR\Uninstall.exe"
    Delete "$INSTDIR\*.*"
    RMDir "$INSTDIR"
    
    ; Remove shortcuts
    Delete "$DESKTOP\LLM Council.lnk"
    RMDir /r "$SMPROGRAMS\LLM Council"
    
    ; Remove registry
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LLMCouncil"
    DeleteRegKey HKLM "Software\LLM Council"
    
SectionEnd

; =====================
; Functions
; =====================

Function .onInit
    ; Check for 64-bit Windows
    ${If} ${RunningX64}
        SetRegView 64
    ${Else}
        MessageBox MB_OK|MB_ICONSTOP "LLM Council requires 64-bit Windows."
        Abort
    ${EndIf}
FunctionEnd
