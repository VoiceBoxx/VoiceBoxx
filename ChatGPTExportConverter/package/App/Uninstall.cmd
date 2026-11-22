@echo off
REM ChatGPT Export Converter @VERSION@ - uninstaller for copies installed with Install.cmd.
REM Archives you created are never touched.
REM
REM   Uninstall.cmd [/S] [/LOG "file"]
REM
REM   /S           Silent: no prompts, no pause.
REM   /LOG "file"  Log file. Default: %TEMP%\ChatGPTExportConverter-Uninstall.log
REM
REM Exit codes: 0 removed | 1 not an Install.cmd installation (MSI or portable copy) | 5 needs admin
REM             1618 the program is running
setlocal EnableExtensions DisableDelayedExpansion

if defined PROCESSOR_ARCHITEW6432 if exist "%SystemRoot%\Sysnative\cmd.exe" (
  "%SystemRoot%\Sysnative\cmd.exe" /d /c ""%~f0" %*"
  exit /b
)

set "APP=ChatGPT Export Converter"
set "EXE=ChatGPTExportConverter.exe"
set "ARP=Software\Microsoft\Windows\CurrentVersion\Uninstall\ChatGPTExportConverter"
set "APPKEY=Software\ChatGPTExportConverter"
set "SYS=%SystemRoot%\System32"
set "SILENT="
set "LOG=%TEMP%\ChatGPTExportConverter-Uninstall.log"
set "RC=0"
set "DEST=%~dp0"
set "DEST=%DEST:~0,-1%"

:args
if "%~1"=="" goto argsdone
if /i "%~1"=="/S"   (set "SILENT=1" & shift & goto args)
if /i "%~1"=="/Q"   (set "SILENT=1" & shift & goto args)
if /i "%~1"=="/LOG" (set "LOG=%~2"  & shift & shift & goto args)
shift & goto args
:argsdone

call :say "=== %APP% uninstall started %DATE% %TIME% (user: %USERDOMAIN%\%USERNAME%) from %DEST%"

if exist "%DEST%\INSTALLED-BY-MSI.txt" (
  call :say "ERROR: This copy was installed from the MSI. Remove it in Settings > Apps, or with msiexec /x."
  set "RC=1" & goto end
)
if not exist "%DEST%\%EXE%" goto notinstalled
if not exist "%DEST%\INSTALL-INFO.txt" goto notinstalled

set "Scope="
for /f "usebackq tokens=1,* delims==" %%A in ("%DEST%\INSTALL-INFO.txt") do set "%%A=%%B"
if /i "%Scope%"=="ALLUSERS" (
  set "MENU=%ProgramData%\Microsoft\Windows\Start Menu\Programs"
  set "DESK=%PUBLIC%\Desktop"
  set "HIVE=HKLM"
) else (
  set "MENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs"
  set "DESK=%USERPROFILE%\Desktop"
  set "HIVE=HKCU"
)

if "%HIVE%"=="HKLM" (
  "%SYS%\reg.exe" query "HKU\S-1-5-19" >nul 2>&1 || (
    call :say "ERROR: This is an all-users installation. Run Uninstall.cmd as administrator."
    set "RC=5" & goto end
  )
)

"%SYS%\tasklist.exe" /fi "imagename eq %EXE%" 2>nul | "%SYS%\find.exe" /i "%EXE%" >nul && (
  call :say "ERROR: %APP% is running. Close it, then run Uninstall.cmd again."
  set "RC=1618" & goto end
)

REM Only the shortcuts and registry entries for this installation's own scope.
del /f /q "%MENU%\%APP%.lnk" >nul 2>&1
del /f /q "%DESK%\%APP%.lnk" >nul 2>&1
"%SYS%\reg.exe" delete "%HIVE%\%ARP%" /f >nul 2>&1
"%SYS%\reg.exe" delete "%HIVE%\%APPKEY%" /f >nul 2>&1

REM Remove only the files this package installs; the folder itself goes only if it is then empty.
call :say "Removing program files from %DEST% ..."
cd /d "%TEMP%"
rd /s /q "%DEST%\_internal" 2>nul
for %%F in ("%EXE%" "ChatGPTExportConverter.ico" "CHANGELOG.txt" "VERSION.txt" "INSTALL-INFO.txt") do del /f /q "%DEST%\%%~F" >nul 2>&1
call :say "%APP% has been removed. === exit code 0"
if not defined SILENT pause
REM Leave the batch file before deleting it, then remove the folder if nothing else is in it.
(goto) 2>nul & del /f /q "%~f0" & rd "%DEST%" 2>nul & cmd /d /c exit 0

:notinstalled
call :say "ERROR: %DEST% was not installed with Install.cmd (portable copy?). Nothing was removed; delete the folder yourself if you no longer need it."
set "RC=1"
goto end

:end
call :say "=== finished, exit code %RC%"
if not defined SILENT pause
exit /b %RC%

:say
set "MSG=%~1"
setlocal EnableDelayedExpansion
echo(!MSG!
if defined LOG (>>"!LOG!" echo(!MSG!) 2>nul
endlocal
exit /b 0
