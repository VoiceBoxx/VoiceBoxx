# ChatGPT Export Converter: security and quality review

Package reviewed: **ChatGPTExportConverter-1.2.2.zip** (program file version 1.2.2)
Package produced: **@VERSION@** (same program file, new installers and scripts)
Review date: @DATE@

## Verdict

The program itself is low risk. It works offline, needs no admin rights, writes only the archive
you ask for, and handles untrusted file names safely. The problems were in the **packaging**. The
1.2.2 "silent install" hung deployment tools, the uninstaller could delete unrelated files, and
the program never showed up in Apps & Features or inventory. Package @VERSION@ fixes all of these.

Still open, because they need a rebuild from source or a certificate: the program is not
code-signed (F3), it starts PowerShell and LibreOffice by bare name (F5), the optional Word engine
can hang (F6), and the bundle includes libraries it doesn't use (F10).

## How the review was done

* **Program code.** I extracted the PyInstaller archive and disassembled the program's 10 Python
  modules (Python 3.14 bytecode): `app`, `converter`, `extract`, `attachments`, `layout`,
  `render_docx`, `render_pdf`, `pdf_convert`, `theme`, `version`. Then I traced every file write,
  process launch, registry access and network-capable import.
* **Executable.** I checked the PE header, manifest, version resource and icon resources.
* **Scripts and package layout.** I read `Install.cmd` and `Uninstall.cmd` line by line and checked
  the zip structure.
* **Not done.** Nothing ran on Windows; this was a static review. I did not do a CVE lookup on the
  bundled library versions, so check the versions under *Components* against your
  vulnerability-management feed.

## Findings

| ID | Severity | Finding | Status in @VERSION@ |
|----|----------|---------|-----------------|
| F1 | **High** | The README documented `Install.cmd` as a "silent install", but it always ended with `pause` and paused on errors too. Run from Intune, ConfigMgr, GPO or PDQ as SYSTEM, it waits forever for a key press until the tool's timeout kills it. | **Fixed.** `/S` switch, exit codes and a log file. |
| F2 | **Medium** | `Uninstall.cmd` ran `rd /s /q` on whatever folder it was in. It also ships inside the portable `App` folder. If a user copied the App contents into a shared folder (for example `C:\Tools`) and ran it, that whole folder was deleted. | **Fixed.** It removes only the files the package installs, only where `INSTALL-INFO.txt` shows that Install.cmd created the folder, and removes the folder only when it's empty. |
| F3 | **Medium** | The executable (and now the MSI) is **not Authenticode-signed**. Expect SmartScreen warnings when a user starts it interactively, and you can't use AppLocker/WDAC publisher rules or the ASR "prevalence" exclusions that rely on signing. | **Open.** Sign with a company certificate (see the Admin guide, section 9). Use hash rules until then (`New-AppLockerRules.ps1`). |
| F4 | **Medium** | Install.cmd registered nothing, so installs were invisible in Settings > Apps, Programs and Features, Intune or ConfigMgr inventory, and there was no reliable detection rule. | **Fixed.** Writes the Apps & Features entry (with icon, version, publisher and silent uninstall command) and `HKLM\|HKCU\Software\ChatGPTExportConverter`. MSI also provided. |
| F5 | **Medium** | `pdf_convert.py` starts `powershell` by bare name (`subprocess.run(["powershell", ...])`) and finds LibreOffice with `shutil.which("soffice")`. On Windows, both can resolve to an executable in the **current directory** before `System32` or `PATH`. Someone who can plant `powershell.exe` or `soffice.exe` in the folder where the CLI is run gets code execution as that user. This only applies when the optional `word` or `libreoffice` engine is chosen or detected. | **Open (source change).** Use `%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe`, and search for soffice only under Program Files. Mitigation: keep the default `built-in` engine, and don't run the CLI from download folders. |
| F6 | Low | Word engine: Word is driven hidden through COM with a 3600-second timeout. If Word shows a dialog (activation, safe mode, a first-run prompt), the conversion hangs for up to an hour. When the timeout fires, only PowerShell is killed and `WINWORD.EXE` keeps running. | **Open (source change).** Shorter timeout, and end the Word process tree on timeout. |
| F7 | Low | The 1.2.2 zip stored paths with `\` separators, which the ZIP specification (APPNOTE 4.4.17) does not allow. Strict tools warn or create flat files with `\` in their names. | **Fixed.** Standard `/` paths. |
| F8 | Low | Started from a 32-bit deployment agent, Install.cmd copied the 64-bit program into `Program Files (x86)`. | **Fixed.** Relaunches itself through `Sysnative`. |
| F9 | Low | Uninstall.cmd deleted both the per-user and the all-users Start menu shortcuts whichever copy it was removing. | **Fixed.** Removes only its own scope's shortcuts. |
| F10 | Low (efficiency) | The bundle carries network and crypto libraries the program never uses: `libcrypto-3.dll`, `libssl-3.dll`, `_ssl`, `_socket`, `_asyncio`, `_overlapped`, `_multiprocessing`, and Pillow's 7.9 MB `_avif`. That's about 15 MB (25%) of unneeded code, more for vulnerability scanners to flag, and it lets the binary contradict its own "no network" claim. | **Open (build change).** Add PyInstaller `--exclude-module` entries (`ssl`, `_ssl`, `asyncio`, `multiprocessing`, `PIL.AvifImagePlugin`, ...) and test. |
| F11 | Low | Licence notices: only pypdfium2's licence files were included. BSD and MIT components (ReportLab, lxml, python-docx, Pillow, ...) require their notices to ship with the program. | **Partly fixed.** `THIRD-PARTY-NOTICES.txt` lists every component. The full texts should be collected at build time. |
| F12 | Low | Attachment names are sanitised, but Windows reserved device names (`CON`, `NUL`, `AUX`, `COM1`, ...) are not. An export attachment named `CON.txt` can fail to save on Windows 10. | **Open (source change).** Prefix reserved names, for example `_CON.txt`. |
| F13 | Info | The manifest doesn't declare DPI awareness, so the window looks blurry on scaled (125% and above) displays. | **Open (source change).** Add `<dpiAware>`/`<dpiAwareness>PerMonitorV2</dpiAwareness>` to the manifest. |
| F14 | Info | The version resource has no `CompanyName` or `LegalCopyright`, so inventory tools show a blank publisher for the .exe. The .exe still reports 1.2.2. | **Open (build change).** The MSI and Apps & Features entry carry publisher and version 1.2.3. |
| F15 | Info | Each `conversations*.json` is loaded into memory whole, and attachments are read whole from the zip without a size cap. Memory use grows with export size. Low risk, because the input is your own export from OpenAI. | **Accepted.** For very large exports (several GB), use a computer with plenty of RAM. |

## What's already done well

* **Exploit mitigations:** ASLR (high-entropy), DEP/NX and Control Flow Guard are enabled.
  The manifest requests `asInvoker`, so there's no UAC prompt, and it is `longPathAware`.
* **No network code** in any of the program's own modules: no `socket`, `urllib`, `http` or
  `ssl` use. No telemetry and no update check.
* **No settings stored:** the program writes no registry keys. Its only registry access is a
  read of `HKCR\Word.Application\CLSID`, to see whether Word is installed.
* **Safe handling of untrusted names:** attachment file names from the export lose path
  separators, `<>:"|?*` and control characters, and are length-capped. Zip members are read into
  memory and never extracted by path, so a malicious zip can't write outside the output folder
  ("zip-slip").
* **No command injection:** processes start with argument lists (no shell). The Word engine
  passes file paths to PowerShell in an environment variable rather than building them into the
  script text, and opens documents read-only.
* **No unpacking to %TEMP%:** it's a one-folder build, so it works under policies that block
  execution from the temporary folder.

## Components (as found in the build)

Python 3.14.10 · OpenSSL 3.5.9 · Tcl/Tk 9.0.4 · ReportLab 5.1.0 · python-docx 1.2.0 · lxml 6.1.3 ·
Pillow 13.0.0 · pypdfium2 5.15.2 (PDFium 159.0.8149) · charset-normalizer 3.5.2 ·
PyInstaller one-folder bootloader. See `THIRD-PARTY-NOTICES.txt`.

## Recommended source changes for the next program release (1.3.0)

1. Full paths for `powershell.exe` and `soffice.exe` (F5); kill the Word process tree on timeout (F6).
2. PyInstaller excludes for unused modules (F10). Add `CompanyName`/`LegalCopyright` to the version file (F14).
3. Manifest DPI awareness (F13). Reserved-name handling in `safe_name()` (F12).
4. Authenticode-sign the .exe and the .msi in the build pipeline (F3). Collect licence texts (F11).
5. Bump the program's `__version__` so the .exe and the package agree.
