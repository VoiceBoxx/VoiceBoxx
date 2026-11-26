# ChatGPT Export Converter @VERSION@: deployment guide for IT administrators

ChatGPT Export Converter turns a ChatGPT data export (the `.zip` that OpenAI emails a user) into
an archive of Word and PDF volumes. It is a self-contained, offline Windows desktop program. It
needs no Python or other runtime, makes no network connections, and needs no admin rights to run.

| | |
|---|---|
| Version | **@VERSION@** (MSI, Apps & Features, the .exe's FileVersion, the window and `--version` all agree) |
| Publisher | @PUBLISHER@ |
| Platform | Windows 10 or 11, **x64** |
| Disk space | about 45 MB, plus the archives users create |
| Install size (Apps & Features) | @SIZE_MB@ MB |
| MSI ProductCode | `@PRODUCTCODE@` (changes with every version) |
| MSI UpgradeCode | `@UPGRADECODE@` (never changes) |
| Detection key | `HKLM\SOFTWARE\ChatGPTExportConverter` `Version` = `@VERSION@` |
| Network | none: no outbound or inbound connections, no telemetry, no auto-update |
| Elevation | `asInvoker`: no UAC prompt when users run it |

---

## Contents

1. [Package contents](#1-package-contents)
2. [Choose a deployment method](#2-choose-a-deployment-method)
3. [MSI installer](#3-msi-installer)
4. [Install.cmd (script installer)](#4-installcmd-script-installer)
5. [Microsoft Intune](#5-microsoft-intune-win32-app)
6. [Configuration Manager (SCCM / MECM)](#6-configuration-manager-sccm--mecm)
7. [Group Policy](#7-group-policy)
8. [Other tools, RDS / AVD, and portable use](#8-other-tools-rds--avd-and-portable-use)
   * [Running from a network share](#running-from-a-network-share)
9. [Application control, SmartScreen and EDR](#9-application-control-smartscreen-and-edr)
10. [Network and firewall](#10-network-and-firewall)
11. [Data handling and privacy](#11-data-handling-and-privacy)
12. [Command-line use](#12-command-line-use)
13. [Upgrade, repair and uninstall](#13-upgrade-repair-and-uninstall)
14. [Verifying the package](#14-verifying-the-package)
15. [Logs and troubleshooting](#15-logs-and-troubleshooting)
16. [Known limitations](#16-known-limitations)

---

## 1. Package contents

```
ChatGPTExportConverter-@VERSION@\
  ChatGPTExportConverter-@VERSION@-x64.msi   MSI installer, per-machine (recommended)
  Install.cmd                          Script installer (per-user or per-machine, silent with /S)
  READ ME FIRST.txt                    End-user instructions
  CHANGELOG.txt   VERSION.txt
  App\                                 The program (also usable portable, as is)
    ChatGPTExportConverter.exe         Main program
    ChatGPTExportConverter.ico         Program icon (Start menu, desktop, Apps & Features)
    LICENSES\                          Full licence texts of the bundled open-source components
    Uninstall.cmd                      Uninstaller for Install.cmd installations
    _internal\                         Embedded Python runtime and libraries. Keep with the .exe
  Deploy\
    ADMIN-GUIDE.md                     This guide
    SECURITY-REVIEW.md                 Security and quality review, open items
    THIRD-PARTY-NOTICES.txt            Open-source components, versions and links
    SHA256SUMS.txt   Verify-Package.ps1               Integrity check
    Detect-ChatGPTExportConverter.ps1  Detection script for Intune / ConfigMgr
    New-AppLockerRules.ps1             AppLocker rule generator
    Icons\                             app.ico, logo.svg, logo-16.png ... logo-512.png
```

**Icons.** Every place the program appears uses the same icon: the .exe, the window title bar
and taskbar, the Start menu and desktop shortcuts, the Apps & Features entry (from both the MSI and
Install.cmd), and the MSI itself. For Company Portal or Software Center, upload
`Deploy\Icons\logo-512.png` (or `logo-256.png`).

## 2. Choose a deployment method

| Method | Scope | Best for | Silent | Shows in Apps & Features |
|---|---|---|---|---|
| **MSI** | all users (`%ProgramFiles%`) | Intune, ConfigMgr, GPO, PDQ, any MSI-aware tool | `/qn` | yes |
| **Install.cmd** | all users or one user | tools without MSI support, or per-user installs with no admin rights | `/S` | yes |
| **Portable `App` folder** | wherever you copy it | USB sticks, network shares, locked-down VDI images | n/a | no |

Choose **one** method per computer. They share the install folder, so each refuses to install over
the other: Install.cmd exits with 1638, and the MSI stops with a message (exit 1603 when silent).

## 3. MSI installer

Per-machine, x64, installs to `%ProgramFiles%\ChatGPT Export Converter`, and adds a Start menu
shortcut for all users. It does not need a reboot.

Double-clicking the MSI opens a setup wizard:

* **Welcome:** a **Create a desktop shortcut** option, checked by default.
* **Progress bar.**
* **Finished:** a **Start ChatGPT Export Converter now** option, checked by default. The
  program starts as the signed-in user.

Windows asks for administrator permission when you click Install.
If the program is already installed, the wizard offers Repair or Remove. Silent installs (`/qn`)
never show the wizard.

```bat
REM Install (silent, with verbose log)
msiexec /i "ChatGPTExportConverter-@VERSION@-x64.msi" /qn /norestart /l*v "%WINDIR%\Temp\ChatGPTExportConverter-@VERSION@-install.log"

REM Uninstall
msiexec /x @PRODUCTCODE@ /qn /norestart /l*v "%WINDIR%\Temp\ChatGPTExportConverter-uninstall.log"
```

* **Desktop shortcut.** Silent installs add it too (Public desktop). Leave it out with
  `DESKTOP_SHORTCUT=0`, for example
  `msiexec /i "ChatGPTExportConverter-@VERSION@-x64.msi" /qn DESKTOP_SHORTCUT=0`.
* **Install folder.** Override with `INSTALLDIR="D:\Apps\ChatGPT Export Converter"` if needed.
  Use a folder that standard users can't write to.
* **Upgrades.** Every version shares the same UpgradeCode. Installing a newer MSI removes the
  older one automatically (major upgrade), and installing an older MSI over a newer one is blocked.
* **Return codes.** 0 = success, 3010 = success with reboot required (not expected),
  1618 = another installation is in progress (retry). 1603 = fatal error: check the log.
* **Repair:** `msiexec /fa @PRODUCTCODE@ /qn`

## 4. Install.cmd (script installer)

```
Install.cmd [/S] [/ALLUSERS | /CURRENTUSER] [/NODESKTOP] [/LOG "file"]
```

| Switch | Meaning |
|---|---|
| `/S` | Silent: no prompts, no `pause`. **Always use this from deployment tools.** |
| `/ALLUSERS` | `%ProgramFiles%\ChatGPT Export Converter`, Start menu for all users. Needs admin or SYSTEM. |
| `/CURRENTUSER` | `%LOCALAPPDATA%\Programs\ChatGPT Export Converter`, no admin needed. Not allowed from SYSTEM. |
| *(neither)* | `/ALLUSERS` when elevated, otherwise `/CURRENTUSER` |
| `/NODESKTOP` | Don't create the desktop shortcut. By default one is created (on the Public desktop for all-users installs), as with the MSI. |
| `/LOG "file"` | Log file. Default `%TEMP%\ChatGPTExportConverter-Install.log`, which is `C:\Windows\Temp` under SYSTEM. |

| Exit code | Meaning |
|---|---|
| 0 | Installed (re-running repairs or updates in place) |
| 1 | Bad option, or the package is incomplete (not fully extracted) |
| 5 | `/ALLUSERS` without admin rights |
| 1603 | Files could not be copied (disk full, permissions, file locked) |
| 1618 | The program is running. Retry later (Intune retries 1618 automatically) |
| 1638 | An MSI installation is already present. Use msiexec instead |

What it changes:

* copies `App\` to the target folder
* writes `INSTALL-INFO.txt` there
* creates the Start menu and desktop shortcuts (no desktop shortcut with `/NODESKTOP`)
* writes the Apps & Features entry `HKLM|HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\ChatGPTExportConverter`
* writes `HKLM|HKCU\Software\ChatGPTExportConverter` (`Version`, `InstallMethod`, `InstallDir`)

It adds no services, scheduled tasks or file associations, and makes no PATH changes.

Shortcuts are created through PowerShell's `WScript.Shell` COM object. Under PowerShell
**Constrained Language Mode** (WDAC/AppLocker script enforcement), that step is blocked: the
install still succeeds and logs a warning. Use the MSI if you need the shortcut on those devices.

Silent uninstall (also stored as `QuietUninstallString`):

```bat
"%ProgramFiles%\ChatGPT Export Converter\Uninstall.cmd" /S
```

`Uninstall.cmd` returns 0 when the program is removed, 1 for an MSI or portable copy (nothing is
removed), 5 when an all-users install is run without admin rights, and 1618 when the program is running.

## 5. Microsoft Intune (Win32 app)

1. Wrap the package with the [Microsoft Win32 Content Prep Tool](https://learn.microsoft.com/intune/intune-service/apps/apps-win32-prepare):
   ```bat
   IntuneWinAppUtil.exe -c "C:\Pkg\ChatGPTExportConverter-@VERSION@" -s "ChatGPTExportConverter-@VERSION@-x64.msi" -o "C:\Pkg\out" -q
   ```
   Because the setup file is an MSI, Intune fills in the commands and the MSI detection rule for you.
2. **App information:** Publisher `@PUBLISHER@`. Logo: `Deploy\Icons\logo-512.png`.
3. **Program:**
   * Install: `msiexec /i "ChatGPTExportConverter-@VERSION@-x64.msi" /qn /norestart`
   * Uninstall: `msiexec /x @PRODUCTCODE@ /qn /norestart`
   * Install behavior: **System**. Device restart behavior: **No specific action**.
   * Return codes: keep the defaults (0, 1707, 3010, 1641, 1618).
4. **Requirements:** OS architecture **x64**; minimum OS Windows 10 (any supported release).
5. **Detection rules**, either of:
   * **MSI**, product code `@PRODUCTCODE@`, with a version check "Greater than or equal to"
     `@VERSION@`; or
   * **Custom script**: `Deploy\Detect-ChatGPTExportConverter.ps1`. Set "Run script as 32-bit
     process on 64-bit clients" = **No** and "Enforce signature check" = **No** (unless you sign it).
     This script also detects Install.cmd installs and keeps working after future upgrades.
6. **Supersedence (next version):** add the new app and supersede this one with "Uninstall
   previous version" = **No**, because the MSI upgrades in place.

**Install.cmd instead of the MSI** (for example, per-user available installs):

* Setup file: `Install.cmd`
* Install command: `Install.cmd /S /ALLUSERS` (System), or `Install.cmd /S /CURRENTUSER` with
  install behavior **User**
* Uninstall command: `cmd.exe /c ""%ProgramFiles%\ChatGPT Export Converter\Uninstall.cmd" /S"`
  (for User installs, use `%LOCALAPPDATA%\Programs\...` instead)
* Detection: the script above
* Return codes: add `1638 = Failed`

## 6. Configuration Manager (SCCM / MECM)

1. **Software Library > Applications > Create Application**, type **Windows Installer (\*.msi
   file)**, from the UNC path of the MSI. ConfigMgr reads the ProductCode and creates an MSI
   detection method.
2. **General information:** Publisher `@PUBLISHER@`, Software version `@VERSION@`.
   Icon: `Deploy\Icons\logo-512.png` (Software Center accepts up to 512 x 512).
3. **Deployment type:**
   * Installation program: `msiexec /i "ChatGPTExportConverter-@VERSION@-x64.msi" /qn /norestart`
   * Uninstall program: `msiexec /x @PRODUCTCODE@ /qn /norestart`
   * Installation behavior: **Install for system**. Logon requirement: **Whether or not a user is logged on**.
   * Requirements: Operating system, All Windows 10/11 (64-bit).
   * Detection: the generated MSI rule, or **Use a custom script** with `Detect-ChatGPTExportConverter.ps1`.
4. Distribute the content to your distribution points and deploy it to a collection as Required
   or Available.

## 7. Group Policy

Assign the MSI to computers:

1. Copy the MSI to a share that **Domain Computers** can read, for example
   `\\fs01\Software$\ChatGPTExportConverter\@VERSION@\`.
2. In a GPO: **Computer Configuration > Policies > Software Settings > Software installation >
   New > Package**, enter the **UNC** path (not a mapped drive), and choose **Assigned**.
3. It installs at the next restart. For a later version, add the new MSI to the same GPO and, on
   its **Upgrades** tab, mark it as upgrading this package. The MSI's major upgrade also handles
   this on its own.

If you prefer, a computer startup script can call
`msiexec /i "\\server\share\ChatGPTExportConverter-@VERSION@-x64.msi" /qn /norestart`. Running
it again is harmless.

There are no ADMX templates: the program has no settings to manage by policy.

## 8. Other tools, RDS / AVD, and portable use

* **PDQ Deploy, Tanium, ManageEngine, NinjaOne, ...:** use the MSI commands from section 3, or
  `Install.cmd /S /ALLUSERS`.
* **Remote Desktop Services / Azure Virtual Desktop / Citrix:** install per-machine (MSI) in
  the image or on the session host. The program stores no per-user state, so it needs no profile
  handling. Users on the same host can run it at the same time.
* **Portable:** copy the whole `App` folder anywhere and run `ChatGPTExportConverter.exe`. It
  writes nothing outside the output folder the user chooses. To remove it, delete the folder.
  On a network share, see [Running from a network share](#running-from-a-network-share).

### Running from a network share

Many users can run the same copy from a share at the same time:

* The program runs in place and never writes to its own folder: no settings, logs, caches or
  unpacked files.
* Each user only reads the program files, which Windows allows for any number of users at once.
* The optional Word PDF engine uses one small temporary file in each user's own `%TEMP%`.
* Each conversion creates its own output folder (`... (2)`, `... (3)`), so users converting into
  the same place never overwrite or mix each other's archives.

Set it up like this:

1. **Use a folder per version**, for example
   `\\server\apps\ChatGPTExportConverter\@VERSION@\`. Copy the whole `App` folder into it, so the
   `.exe` and `_internal` stay together.
2. **Permissions:** give users *Read & execute* only, on both the share and NTFS. Give *Modify*
   to administrators only. If users could write there, one person could replace a file and it
   would run for everyone.
3. **Shortcut:** point users at the full UNC path, not a mapped drive letter, which may differ
   between users. For example, a Group Policy Preferences shortcut to
   `\\server\apps\ChatGPTExportConverter\@VERSION@\ChatGPTExportConverter.exe` with the icon from
   `ChatGPTExportConverter.ico` in the same folder.
4. **Intranet zone:** add the file server to the *Local intranet* zone (Group Policy: *Site to
   Zone Assignment List*, value `1`). Otherwise Windows shows "Open File - Security Warning" each
   time, because the `.exe` is not signed. Signing it (section 9) also removes the prompt.
5. **Application control:** allow the UNC path in AppLocker or WDAC, or use hash rules from
   `Deploy\New-AppLockerRules.ps1` run against the share folder.

Things to know:

| Topic | What happens | What to do |
|---|---|---|
| Updating | While anyone has the program open, Windows locks its files, so they can't be replaced. | Copy the new version to a new folder (`...\1.2.8\`) and repoint the shortcut. Delete the old folder once nobody uses it. |
| Network interruption | The program loads parts of itself from the share as it runs. If the share disconnects during a conversion, that run stops with an error. | The user runs it again. Nothing else is affected, and no earlier archive is touched. |
| Start-up time | About 43 MB is read from the share the first time it starts. | Expect a few extra seconds on slow links; later starts use Windows' file cache. A local install (MSI) avoids this. |
| Where archives are saved | By default, next to the export. If a user opens an export stored on a shared drive, their private chat archive is saved there too, visible to anyone with access. | Tell users to keep exports on their own PC, or to choose a personal folder under **Save to folder** (`-o` on the command line). |
| Offline use | The program can't start without the share. | Use the MSI for laptops that work offline. |

For many users on one Remote Desktop / AVD host, a local per-machine install (MSI) on the host is
faster and more reliable than a share.

## 9. Application control, SmartScreen and EDR

**The .exe and .msi are not code-signed** (see SECURITY-REVIEW F3).

* **Mark of the Web.** If the zip was downloaded, Windows tags the extracted files. Remove the tag
  before you copy them to a share or wrap them:
  `Get-ChildItem -LiteralPath .\ChatGPTExportConverter-@VERSION@ -Recurse | Unblock-File`
* **SmartScreen.** Files installed by the MSI or Install.cmd under SYSTEM don't carry Mark of the
  Web, so users don't see "Windows protected your PC". The prompt only appears when someone
  double-clicks the downloaded files.
* **AppLocker.** On a reference machine, run
  `Deploy\New-AppLockerRules.ps1 -Path "C:\Program Files\ChatGPT Export Converter"` to generate
  hash rules (.exe, .dll, .pyd) and import the XML. Regenerate them for each new version. A path
  rule (`-RuleType Path`) is fine for `%ProgramFiles%`. Don't use path rules for per-user
  `%LOCALAPPDATA%` installs.
* **WDAC / App Control for Business.**
  ```powershell
  New-CIPolicy -Level Hash -Fallback FileName -UserPEs -ScanPath "C:\Program Files\ChatGPT Export Converter" -FilePath .\ChatGPTExportConverter-WDAC.xml
  ```
  Merge the result into your base policy with `Merge-CIPolicy`.
* **Defender ASR.** The rule "Block executable files from running unless they meet a prevalence,
  age, or trusted list criterion" can block a new, unsigned .exe. If it does, add a per-rule
  exclusion for `%ProgramFiles%\ChatGPT Export Converter\ChatGPTExportConverter.exe`.
* **Code signing (recommended).** Sign the .exe before you build the MSI, then sign the MSI:
  ```bat
  signtool sign /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com /n "Your Company" App\ChatGPTExportConverter.exe
  signtool sign /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com /n "Your Company" ChatGPTExportConverter-@VERSION@-x64.msi
  ```
  Simplest: let the build do both, in the right order, with
  `build_package.py --sign-pfx codesign.pfx --sign-password-env PFX_PASS` (source repository).
  If you sign by hand, rebuild the MSI and `SHA256SUMS.txt` afterwards. Test the signed .exe once,
  then switch AppLocker and WDAC to publisher rules.
* **EDR behaviour you may see:**
  * **Default `built-in` PDF engine:** no child processes.
  * **`word` engine:** the program starts hidden
    `%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -NonInteractive -Command ...`,
    which automates `WINWORD.EXE` through COM (macros disabled) to save PDFs. On a time-out it
    ends that Word instance with `taskkill`. Some EDR products flag
    this pattern, and PowerShell Constrained Language Mode blocks it (the program then reports
    a Word conversion error; use the built-in engine).
  * **`libreoffice` engine:** the program starts `soffice.exe --headless --convert-to pdf`, from
    Program Files or an absolute PATH folder only.

  The `word` and `libreoffice` engines only appear when that software is installed, and only run
  when a user selects them.

## 10. Network and firewall

The program makes **no network connections**. None of its own code imports networking modules,
and it has no update check or telemetry. No firewall rules, proxy settings or URL allow-lists are
needed. Since @VERSION@, OpenSSL isn't even included, so the program can't make TLS connections.

To enforce this, you can block it outbound:

```powershell
New-NetFirewallRule -DisplayName "ChatGPT Export Converter - block outbound" -Direction Outbound -Action Block `
  -Program "$env:ProgramFiles\ChatGPT Export Converter\ChatGPTExportConverter.exe"
```

## 11. Data handling and privacy

* **Input.** The user's ChatGPT export. This is personal data: full conversation history, uploaded
  files, images and voice recordings.
* **Output.** A folder `ChatGPT_Archive_<client>_<date>` with `.docx` and `.pdf` volumes and an
  `Attachments` folder. It contains the same personal data. By default it goes **next to the
  export** (often `Downloads`, or a OneDrive-synced folder). Users can choose another folder, or
  `-o` on the command line.
* **Nothing else is stored.** The program keeps no settings, history, cache or log, writes no
  registry keys, uses no temporary folder (built-in engine), and sends nothing anywhere. The
  window shows a reminder that the output is private.
* **Optional engines.** Word or LibreOffice may create their own temporary and profile files
  (for example `%APPDATA%\LibreOffice`), the same as normal use.
* **Policy considerations:**
  * Decide where archives may be stored, and whether DLP or sensitivity labels apply to them.
  * Check whether exports of personal AI-chat history are allowed on company devices at all.
  * If the output folder is synced (OneDrive Known Folder Move), the data goes to the company
    tenant.

## 12. Command-line use

```
ChatGPTExportConverter.exe --cli EXPORT.zip [-o OUTPUT_DIR] [--owner "Client Name - CMP#"]
        [--compiled YYYY-MM-DD] [--pages 300] [--no-branches] [--no-reasoning]
        [--no-images] [--no-tools] [--pdf-engine built-in|word|libreoffice]
ChatGPTExportConverter.exe --version
```

* `EXPORT` can be the export `.zip`, its extracted folder, or a `conversations*.json` file.
* `--owner` fills the **Client Name - CMP#** field shown on the covers and in "About this archive",
  for example `--owner "Acme Corp - CMP#12345"`. In the folder name, `#` is left out
  (`ChatGPT_Archive_Acme_Corp_-_CMP12345_<date>`).
* Each run writes a new folder `ChatGPT_Archive_<client>_<date>` under `-o` (default: next to the
  export). If that folder already exists, the run uses `... (2)`, `... (3)` and so on, so runs
  never overwrite or mix with each other, even in parallel.
* Started with two or more existing files or folders and no options (for example several exports
  dropped on the program), it converts them one after another in a progress window.
* `--pages` sets the pages per volume, from 100 to 5000 (default 300).
* Exit code: **0** = success, **1** = error (the message goes to stderr).
* It's a Windows GUI program, so `cmd` doesn't wait for it. In scripts, use:
  ```bat
  start "" /wait "%ProgramFiles%\ChatGPT Export Converter\ChatGPTExportConverter.exe" --cli "D:\in\export.zip" -o "D:\out"
  echo Exit code %errorlevel%
  ```
  ```powershell
  $p = Start-Process "$env:ProgramFiles\ChatGPT Export Converter\ChatGPTExportConverter.exe" `
       -ArgumentList '--cli','D:\in\export.zip','-o','D:\out' -Wait -PassThru -NoNewWindow
  $p.ExitCode
  ```

## 13. Upgrade, repair and uninstall

| | MSI | Install.cmd | Portable |
|---|---|---|---|
| Upgrade | Install the newer MSI (major upgrade) | Run the newer `Install.cmd /S` (mirrors over the old files) | Replace the folder |
| Repair | `msiexec /fa @PRODUCTCODE@ /qn` | Run `Install.cmd /S` again | Replace the folder |
| Uninstall | Settings > Apps, or `msiexec /x @PRODUCTCODE@ /qn` | Settings > Apps, or `Uninstall.cmd /S` | Delete the folder |
| User archives | never touched | never touched | never touched |

To move from Install.cmd to the MSI: run `Uninstall.cmd /S` first, then install the MSI.

**Upgrading from earlier versions.** 1.2.3 changed only the installers and still contained the
1.2.2 program. 1.2.4 is the fixed program, but its MSI had no setup window. 1.2.5 adds the setup
wizard and keeps the 1.2.4 program. 1.2.6 adds the desktop-shortcut and start-now options. 1.2.7 fixes layout, multiple-file
and page-count issues found in a design review. The
@VERSION@ MSI upgrades any of them in place, and
running the @VERSION@ `Install.cmd /S` updates a script install. In Intune or ConfigMgr, set up
@VERSION@ to supersede the earlier version (without uninstalling first). The full version history, with each
version's MSI ProductCode, is in `VERSION.txt`.

## 14. Verifying the package

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Deploy\Verify-Package.ps1
```

This checks every file against `Deploy\SHA256SUMS.txt` (exit code 0 = all match). The release
also has `.sha256` files next to the zip and the MSI. Check those with
`Get-FileHash .\ChatGPTExportConverter-@VERSION@.zip -Algorithm SHA256`.

## 15. Logs and troubleshooting

| Log | Where |
|---|---|
| MSI | wherever you pointed `/l*v` (nothing is logged without it) |
| Install.cmd | `%TEMP%\ChatGPTExportConverter-Install.log` (`C:\Windows\Temp` under SYSTEM), or `/LOG` |
| Uninstall.cmd | `%TEMP%\ChatGPTExportConverter-Uninstall.log`, or `/LOG` |
| Program | none. The GUI shows a report at the end, and `--cli` prints it to the console (redirect with `> report.txt 2>&1`) |

| Symptom | Cause and fix |
|---|---|
| Double-clicking the MSI seems to do nothing (1.2.4 only) | The 1.2.4 MSI had no setup window, and the administrator prompt opened behind other windows (look for a flashing shield on the taskbar). Use 1.2.5 or later, which has a setup wizard. |
| Install from Intune or ConfigMgr times out | `Install.cmd` used without `/S`. Add `/S`, or use the MSI. |
| Exit 1618 | The program is open on the device. It's retried automatically (Intune), or close it. |
| Exit 1638 from Install.cmd | The MSI version is installed. Use msiexec, or uninstall it first. |
| "Windows protected your PC" | Unsigned file with Mark of the Web. Use `Unblock-File` (section 9), deploy with the MSI, or sign it. |
| Blocked by AppLocker, WDAC or ASR | Add rules (section 9). Regenerate hash rules after each upgrade. |
| Installed but no Start menu shortcut (Install.cmd) | PowerShell Constrained Language Mode. See the log warning, and use the MSI. |
| "Open File - Security Warning" every time it starts from a share | The file server isn't in the Local intranet zone and the .exe is unsigned. Add the server to the zone, or sign the .exe (see [Running from a network share](#running-from-a-network-share)). |
| Can't update the copy on a share (files in use) | Someone has the program open. Use a new folder per version and repoint the shortcut ([Running from a network share](#running-from-a-network-share)). |
| Program won't start, missing DLL | The `_internal` folder isn't next to the .exe. Copy the whole `App` folder. |
| Word engine times out | Word is showing a hidden dialog (activation, first run). The program gives up after 2 min + 10 min per volume and closes that Word instance. Use the built-in engine, or open Word once interactively. |

## 16. Known limitations

* PDFs: right-to-left scripts (Arabic, Hebrew) are shown in the wrong order and Arabic letters
  unjoined; the Word files are correct. Emoji need Segoe UI Emoji (standard on Windows 10/11).
* For detection, use the MSI version, the Apps & Features `DisplayVersion`, or
  `HKLM\SOFTWARE\ChatGPTExportConverter\Version` (all @VERSION@).
* The .exe and .msi are not code-signed unless you build with your certificate (section 9).
* x64 only. ARM64 Windows runs it through x64 emulation, but this has not been tested.
* No per-user MSI. Use `Install.cmd /CURRENTUSER` for per-user installs.
* The fixed program, Install.cmd and the MSI were verified with automated tests (see
  SECURITY-REVIEW, "How the fixes were verified") but **have not yet been run on Windows. Test
  them in a pilot ring before broad deployment.**
* Open items for the next program release are listed in `SECURITY-REVIEW.md`.
