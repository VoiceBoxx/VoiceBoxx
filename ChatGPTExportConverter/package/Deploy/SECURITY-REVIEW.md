# ChatGPT Export Converter: security and quality review

Package reviewed: **ChatGPTExportConverter-1.2.2.zip** (program 1.2.2)
Package produced: **@VERSION@** (fixed program, new installers and scripts)
Review date: @DATE@

## Verdict

The program is low risk. It works offline, needs no admin rights, writes only the archive you ask
for, and handles untrusted file names safely. Every one of its 44 native binaries is
byte-identical to the official python.org or PyPI build.

The review found 15 issues. **13 are fixed in @VERSION@.** The remaining two are:

* **F3, code signing:** needs your organisation's certificate. The build can now sign with one
  command.
* **F15, memory use:** accepted by design.

## How the review was done

* **Program code.** I extracted the PyInstaller archive and disassembled the program's 10 Python
  modules (Python 3.14 bytecode): `app`, `converter`, `extract`, `attachments`, `layout`,
  `render_docx`, `render_pdf`, `pdf_convert`, `theme`, `version`. Then I traced every file write,
  process launch, registry access and network-capable import.
* **Executable.** I checked the PE header, manifest, version resource and icon resources.
* **Provenance.** I compared every bundled `.dll`/`.pyd` with the official Python 3.14.10
  embeddable package and `tcltk.msi` from python.org, and with the official Windows wheels from
  PyPI (Pillow 13.0.0, lxml 6.1.3, charset-normalizer 3.5.2, pypdfium2 5.15.2). All 44 matched
  byte for byte, so nobody altered the native code.
* **Scripts and package layout.** I read `Install.cmd` and `Uninstall.cmd` line by line and checked
  the zip structure.

### How the fixes were verified

The program's source code was not available, so the fixes are applied to the built program by
`build/patch_exe.py`:

* `pdf_convert` is replaced.
* `safe_name()` in `attachments` is replaced.
* The version number is updated.
* A start-up hook is added for high-DPI displays.
* The version resource is rewritten.

Checks on the result:

* **The archive writer is exact.** Rebuilding the original program with no changes reproduces it
  byte for byte (`patch_exe.py --selftest`).
* **The program can read it.** The patched archive was read with PyInstaller's *own* archive
  reader taken from the program. All 624 modules load, and the hook runs before the program.
* **End-to-end conversion.** The program's real modules, loaded from the patched .exe, converted a
  test export on Python 3.14 with the same library versions. The test export included a branch, an
  image, a PDF and a `CON.txt` attachment. The output matched the original program apart from the
  intended fixes.
* **Removed libraries.** The same conversion, plus the imports made by the start-up hooks,
  succeeded with OpenSSL and AVIF blocked.
* **High-DPI hook.** Tested under a virtual display at simulated 100%, 150% and 200% Windows scaling.
* **LibreOffice engine and process handling.** The engine converted a real volume. A planted
  `soffice` in the current folder was ignored, and time-outs ended the process tree.
* **Not run on Windows.** Wine crashes in this build environment, so **neither the .exe nor the
  installers have been run on Windows yet. Pilot-test before broad deployment.** The Word engine
  needs Windows and Word, so it is untested too.

## Findings

| ID | Severity | Finding | Status in @VERSION@ |
|----|----------|---------|-----------------|
| F1 | **High** | The README called `Install.cmd` a "silent install", but it always ended with `pause` and paused on errors too. Deployment tools running it as SYSTEM hang until their timeout. | **Fixed.** `/S` switch, exit codes and a log file. |
| F2 | **Medium** | `Uninstall.cmd` ran `rd /s /q` on whatever folder it was in. It also ships in the portable `App` folder, so a copy kept in a shared folder could delete unrelated files. | **Fixed.** It removes only the files the package installs, only in folders that Install.cmd created, and removes the folder only when it's empty. |
| F3 | **Medium** | The .exe and .msi are **not Authenticode-signed**: expect SmartScreen warnings, and no AppLocker/WDAC publisher rules. | **Open, needs a certificate.** `build_package.py --sign-pfx` signs both (pipeline tested). Use hash rules until then (`New-AppLockerRules.ps1`). |
| F4 | **Medium** | Install.cmd registered nothing, so installs were invisible in Apps & Features, inventory and detection rules. | **Fixed.** Writes the Apps & Features entry (icon, version, publisher, silent uninstall) and `HKLM\|HKCU\Software\ChatGPTExportConverter`. MSI also provided. |
| F5 | **Medium** | `pdf_convert` started `powershell` by bare name and found LibreOffice with `shutil.which("soffice")`. On Windows, both can resolve to an executable planted in the current directory. | **Fixed.** `%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe`, and soffice only from Program Files or absolute PATH entries. |
| F6 | Low | Word engine: hidden Word with a flat 3600 s timeout. A Word dialog hung the conversion for an hour, and on timeout `WINWORD.EXE` kept running. | **Fixed.** The limit is 2 min + 10 min per document. The Word instance this run started is ended on timeout or error, and macros are force-disabled (`AutomationSecurity = 3`). LibreOffice's process tree is ended on timeout. File paths are passed newline-separated, so `;` in a path no longer breaks the list. |
| F7 | Low | The zip used `\` path separators (not allowed by the ZIP spec). | **Fixed.** |
| F8 | Low | Started from a 32-bit agent, Install.cmd installed into `Program Files (x86)`. | **Fixed.** Relaunches through `Sysnative`. |
| F9 | Low | Uninstall.cmd removed both per-user and all-users shortcuts. | **Fixed.** |
| F10 | Low (efficiency) | About 15 MB of unused native code: OpenSSL (`libcrypto-3.dll`, `libssl-3.dll`, `_ssl`, `_hashlib`) and Pillow `_avif`. | **Fixed.** Removed; the program folder went from 57 MB to 43 MB. `hashlib` uses the hash modules built into `python314.dll`. |
| F11 | Low | Only pypdfium2's licence files were shipped. BSD and MIT components require their notices. | **Fixed.** Full texts in `App\LICENSES`, taken from the official distributions. |
| F12 | Low | Windows reserved device names (`CON`, `NUL`, `COM1`, ...) were not handled in attachment names. | **Fixed.** Prefixed with `_`. Trailing dots and spaces after truncation are also removed. |
| F13 | Info | Not DPI-aware: blurry on scaled displays. | **Fixed.** A start-up hook declares system DPI awareness and scales the window size to match. |
| F14 | Info | No `CompanyName`/`LegalCopyright` in the version resource; the .exe said 1.2.2. | **Fixed.** FileVersion/ProductVersion @VERSION@ with publisher and copyright. The PE checksum is updated. |
| F15 | Info | Each `conversations*.json` and attachment is read into memory whole. | **Accepted.** The input is the user's own export, and a size cap would reject large legitimate exports. Use a computer with plenty of RAM for exports of several GB. |

## What was already done well

* **Exploit mitigations:** ASLR (high-entropy), DEP/NX and CFG are enabled. The manifest
  requests `asInvoker` and is `longPathAware`.
* **No network code** in the program's modules. No telemetry or update check.
* **No settings stored.** The only registry access is a read of `HKCR\Word.Application\CLSID`.
* **Safe handling of untrusted names:** separators and reserved characters are stripped and names
  are length-capped. Zip members are read into memory, never extracted by path, so no "zip-slip".
* **No command injection:** argument lists only, never a shell. Word gets its file paths through
  an environment variable and opens documents read-only.
* **No unpacking to %TEMP%** (one-folder build).

## Components (as shipped in @VERSION@)

Python 3.14.10 · Tcl/Tk 9.0.4 · ReportLab 5.1.0 · python-docx 1.2.0 · lxml 6.1.3 · Pillow 13.0.0 ·
pypdfium2 5.15.2 (PDFium 159.0.8149) · charset-normalizer 3.5.2 · PyInstaller bootloader.
OpenSSL is no longer included. I did not do a CVE lookup: check these versions against your
vulnerability-management feed.

## Recommendations for the program's maintainer

1. Get a code-signing certificate and build with `--sign-pfx` (F3).
2. Move the patches in `patches/` into the program's source, so the next PyInstaller build no
   longer needs `patch_exe.py`:
   * `pdf_convert.py`
   * `safe_name()`
   * the DPI hook, or DPI awareness declared in the manifest
   * PyInstaller `--exclude-module ssl` / `_hashlib` and `PIL.AvifImagePlugin`
   * `CompanyName`/`LegalCopyright` in the version file
