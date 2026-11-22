@echo off
REM ChatGPT Export Converter @VERSION@ - installer (no MSI needed). See Deploy\ADMIN-GUIDE.md.
REM
REM   Install.cmd [/S] [/ALLUSERS | /CURRENTUSER] [/DESKTOP] [/LOG "file"]
REM
REM   /S            Silent: no prompts, no pause. Use this from Intune, ConfigMgr, GPO, PDQ, etc.
REM   /ALLUSERS     Install to %ProgramFiles% for every user (needs administrator / SYSTEM).
REM   /CURRENTUSER  Install to %LOCALAPPDATA%\Programs for the current user only (no admin needed).
REM                 Default: /ALLUSERS when elevated, otherwise /CURRENTUSER.
REM   /DESKTOP      Also create a desktop shortcut.
REM   /LOG "file"   Log file. Default: %TEMP%\ChatGPTExportConverter-Install.log
REM
REM Exit codes: 0 installed | 1 bad option or package incomplete | 5 /ALLUSERS without admin rights
REM             1603 files could not be copied | 1618 the program is running
REM             1638 an MSI-installed copy is already present (use msiexec instead)
setlocal EnableExtensions DisableDelayedExpansion

REM A 32-bit deployment agent would be redirected to "Program Files (x86)": relaunch as 64-bit.
if defined PROCESSOR_ARCHITEW6432 if exist "%SystemRoot%\Sysnative\cmd.exe" (
  "%SystemRoot%\Sysnative\cmd.exe" /d /c ""%~f0" %*"
  exit /b
)

set "APP=ChatGPT Export Converter"
set "EXE=ChatGPTExportConverter.exe"
set "ICO=ChatGPTExportConverter.ico"
set "VER=@VERSION@"
set "PUBLISHER=@PUBLISHER@"
set "SIZEKB=@SIZE_KB@"
set "ARP=Software\Microsoft\Windows\CurrentVersion\Uninstall\ChatGPTExportConverter"
set "APPKEY=Software\ChatGPTExportConverter"
set "SYS=%SystemRoot%\System32"
set "SRC=%~dp0App"
set "SILENT="
set "SCOPE="
set "DESKTOP="
set "LOG=%TEMP%\ChatGPTExportConverter-Install.log"
set "RC=0"

:args
if "%~1"=="" goto argsdone
if /i "%~1"=="/S"           (set "SILENT=1"          & shift & goto args)
if /i "%~1"=="/Q"           (set "SILENT=1"          & shift & goto args)
if /i "%~1"=="/ALLUSERS"    (set "SCOPE=ALLUSERS"    & shift & goto args)
if /i "%~1"=="/CURRENTUSER" (set "SCOPE=CURRENTUSER" & shift & goto args)
if /i "%~1"=="/DESKTOP"     (set "DESKTOP=1"         & shift & goto args)
if /i "%~1"=="/LOG"         (set "LOG=%~2"           & shift & shift & goto args)
if "%~1"=="/?" goto usage
if /i "%~1"=="/H" goto usage
echo Unknown option: %1
set "RC=1" & goto usage
:argsdone

call :say "=== %APP% %VER% install started %DATE% %TIME% (user: %USERDOMAIN%\%USERNAME%)"

if not exist "%SRC%\%EXE%" (
  call :say "ERROR: Program files not found next to Install.cmd. Extract the whole zip first, then run Install.cmd from the extracted folder."
  set "RC=1" & goto end
)
if not exist "%SRC%\_internal\python314.dll" (
  call :say "ERROR: The App\_internal folder is missing or incomplete. Extract the whole zip again."
  set "RC=1" & goto end
)

REM Elevation check that works even when the Server service is disabled.
set "ADMIN="
"%SYS%\reg.exe" query "HKU\S-1-5-19" >nul 2>&1 && set "ADMIN=1"
if not defined SCOPE (if defined ADMIN (set "SCOPE=ALLUSERS") else (set "SCOPE=CURRENTUSER"))

if "%SCOPE%"=="ALLUSERS" (
  if not defined ADMIN (
    call :say "ERROR: /ALLUSERS needs administrator rights. Run from an elevated prompt, or use /CURRENTUSER."
    set "RC=5" & goto end
  )
  set "DEST=%ProgramFiles%\%APP%"
  set "MENU=%ProgramData%\Microsoft\Windows\Start Menu\Programs"
  set "DESK=%PUBLIC%\Desktop"
  set "HIVE=HKLM"
) else (
  if /i "%USERNAME%"=="%COMPUTERNAME%$" (
    call :say "ERROR: /CURRENTUSER cannot be used from the SYSTEM account. Use /ALLUSERS, or run in the user's context."
    set "RC=1" & goto end
  )
  set "DEST=%LOCALAPPDATA%\Programs\%APP%"
  set "MENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs"
  set "DESK=%USERPROFILE%\Desktop"
  set "HIVE=HKCU"
)
call :say "Scope: %SCOPE%   Target: %DEST%"

if exist "%DEST%\INSTALLED-BY-MSI.txt" (
  call :say "ERROR: This computer already has the MSI version installed in %DEST%. Upgrade or remove it with msiexec."
  set "RC=1638" & goto end
)

"%SYS%\tasklist.exe" /fi "imagename eq %EXE%" 2>nul | "%SYS%\find.exe" /i "%EXE%" >nul && (
  call :say "ERROR: %APP% is running. Close it, then run Install.cmd again."
  set "RC=1618" & goto end
)

call :say "Copying files ..."
"%SYS%\robocopy.exe" "%SRC%" "%DEST%" /MIR /R:2 /W:2 /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
  call :say "ERROR: The files could not be copied to %DEST% (robocopy exit code %errorlevel%)."
  set "RC=1603" & goto end
)

REM Marker read by Uninstall.cmd: it only removes folders that Install.cmd created.
> "%DEST%\INSTALL-INFO.txt" (
  echo Version=%VER%
  echo Scope=%SCOPE%
  echo Method=Install.cmd
)

call :shortcut "%MENU%\%APP%.lnk"
if errorlevel 1 call :say "WARNING: The Start menu shortcut could not be created. Start the program from %DEST%\%EXE%"
if defined DESKTOP (
  call :shortcut "%DESK%\%APP%.lnk"
  if errorlevel 1 call :say "WARNING: The desktop shortcut could not be created."
)

REM Register in Settings > Apps / Programs and Features (also used by inventory and detection rules).
set "K=%HIVE%\%ARP%"
set "REGFAIL="
"%SYS%\reg.exe" add "%K%" /v DisplayName          /t REG_SZ    /d "%APP%" /f >nul || set "REGFAIL=1"
"%SYS%\reg.exe" add "%K%" /v DisplayVersion       /t REG_SZ    /d "%VER%" /f >nul || set "REGFAIL=1"
"%SYS%\reg.exe" add "%K%" /v Publisher            /t REG_SZ    /d "%PUBLISHER%" /f >nul || set "REGFAIL=1"
"%SYS%\reg.exe" add "%K%" /v DisplayIcon          /t REG_SZ    /d "%DEST%\%ICO%" /f >nul || set "REGFAIL=1"
"%SYS%\reg.exe" add "%K%" /v InstallLocation      /t REG_SZ    /d "%DEST%" /f >nul || set "REGFAIL=1"
"%SYS%\reg.exe" add "%K%" /v UninstallString      /t REG_SZ    /d "\"%DEST%\Uninstall.cmd\"" /f >nul || set "REGFAIL=1"
"%SYS%\reg.exe" add "%K%" /v QuietUninstallString /t REG_SZ    /d "\"%DEST%\Uninstall.cmd\" /S" /f >nul || set "REGFAIL=1"
"%SYS%\reg.exe" add "%K%" /v EstimatedSize        /t REG_DWORD /d %SIZEKB% /f >nul || set "REGFAIL=1"
"%SYS%\reg.exe" add "%K%" /v NoModify             /t REG_DWORD /d 1 /f >nul || set "REGFAIL=1"
"%SYS%\reg.exe" add "%K%" /v NoRepair             /t REG_DWORD /d 1 /f >nul || set "REGFAIL=1"
"%SYS%\reg.exe" add "%HIVE%\%APPKEY%" /v Version       /t REG_SZ /d "%VER%" /f >nul || set "REGFAIL=1"
"%SYS%\reg.exe" add "%HIVE%\%APPKEY%" /v InstallMethod /t REG_SZ /d "Install.cmd" /f >nul || set "REGFAIL=1"
"%SYS%\reg.exe" add "%HIVE%\%APPKEY%" /v InstallDir    /t REG_SZ /d "%DEST%" /f >nul || set "REGFAIL=1"
if defined REGFAIL call :say "WARNING: Could not write all Apps and Features / registry values."

call :say "Installed %APP% %VER% to %DEST%"
call :say "Remove it with Settings > Apps, or run Uninstall.cmd /S in %DEST%"
goto end

:usage
echo.
echo   Install.cmd [/S] [/ALLUSERS ^| /CURRENTUSER] [/DESKTOP] [/LOG "file"]
echo   See the top of Install.cmd or Deploy\ADMIN-GUIDE.md for details and exit codes.
goto end

:end
if defined LOG call :say "=== finished, exit code %RC%"
if not defined SILENT pause
exit /b %RC%

REM ---- subroutines ----------------------------------------------------------------------------
:say
set "MSG=%~1"
setlocal EnableDelayedExpansion
echo(!MSG!
if defined LOG (>>"!LOG!" echo(!MSG!) 2>nul
endlocal
exit /b 0

:shortcut
REM %1 = .lnk path. Values go through environment variables, so no path is ever parsed as code.
set "LNK=%~1"
"%SYS%\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; $s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK); $s.TargetPath=Join-Path $env:DEST $env:EXE; $s.WorkingDirectory=$env:DEST; $s.IconLocation=(Join-Path $env:DEST $env:ICO)+',0'; $s.Description='Convert a ChatGPT data export to a Word and PDF archive'; $s.Save()" >nul 2>&1
exit /b %errorlevel%
