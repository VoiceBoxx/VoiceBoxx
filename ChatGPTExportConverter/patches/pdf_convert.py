"""Optional .docx -> .pdf conversion through Microsoft Word or LibreOffice, when installed.

With either engine the PDF is a page-for-page copy of the Word file. The built-in ReportLab
renderer is used when neither is available.

1.2.3 (replaces the 1.2.2 module inside the frozen program):
- PowerShell is started by its full path, and soffice.exe is looked up only in absolute PATH
  entries and Program Files, never in the current directory (no search-order hijacking).
- Word: macros are force-disabled for the automation session, the timeout scales with the
  number of documents instead of a flat hour, and on timeout or error the WINWORD.EXE that this
  run started is ended too (COM starts Word outside our process tree).
"""
import glob
import os
import shutil
import subprocess
import tempfile

_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0   # CREATE_NO_WINDOW
_PER_DOC_TIMEOUT = 600      # seconds per document
_BASE_TIMEOUT = 120         # Word / LibreOffice start-up


def _auto_timeout(docx_paths, timeout):
    return timeout if timeout else _BASE_TIMEOUT + _PER_DOC_TIMEOUT * max(1, len(docx_paths))


def _system_exe(*parts):
    root = os.environ.get('SystemRoot') or os.environ.get('windir') or r'C:\Windows'
    return os.path.join(root, 'System32', *parts)


def _powershell():
    return _system_exe('WindowsPowerShell', 'v1.0', 'powershell.exe')


def find_soffice():
    """soffice from absolute PATH entries or Program Files; the current directory is never searched."""
    exe = 'soffice.exe' if os.name == 'nt' else 'soffice'
    for d in os.environ.get('PATH', '').split(os.pathsep):
        d = d.strip().strip('"')
        if d and os.path.isabs(d):
            p = os.path.join(d, exe)
            if os.path.isfile(p):
                return p
    if os.name != 'nt':
        p = shutil.which('soffice')
        return p if p and os.path.isabs(p) else None
    for root in (os.environ.get('ProgramFiles', r'C:\Program Files'),
                 os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')):
        hits = sorted(glob.glob(os.path.join(root, 'LibreOffice*', 'program', 'soffice.exe')))
        if hits:
            return hits[-1]
    return None


def has_word():
    if os.name != 'nt':
        return False
    try:
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, 'Word.Application\\CLSID'))
        return True
    except OSError:
        return False


def available_engines():
    eng = ['built-in']
    if has_word():
        eng.append('word')
    if find_soffice():
        eng.append('libreoffice')
    return eng


def _kill_pid(pid):
    if not pid:
        return
    try:
        subprocess.run([_system_exe('taskkill.exe'), '/PID', str(int(pid)), '/T', '/F'],
                       capture_output=True, timeout=30, creationflags=_NO_WINDOW)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass


def _run(cmd, timeout, env=None):
    """subprocess.run that, on timeout, ends the whole process tree. Returns None on timeout."""
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, creationflags=_NO_WINDOW)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_pid(proc.pid)
        proc.kill()
        try:
            proc.communicate(timeout=15)    # a surviving grandchild may still hold the pipes
        except subprocess.TimeoutExpired:
            pass
        return None
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)


_WORD_PS = r"""
$ErrorActionPreference = 'Stop'
$before = @(Get-Process -Name WINWORD -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
$w = New-Object -ComObject Word.Application
$new = @(Get-Process -Name WINWORD -ErrorAction SilentlyContinue | Where-Object { $before -notcontains $_.Id } | ForEach-Object { $_.Id })
if ($new.Count -ge 1) { Set-Content -LiteralPath $env:CGX_PIDFILE -Value $new[0] -Encoding ASCII }
$w.Visible = $false; $w.DisplayAlerts = 0
try { $w.AutomationSecurity = 3 } catch { }
try {
  foreach ($p in ($env:CGX_DOCX -split "`n")) {
    if (-not $p) { continue }
    $d = $w.Documents.Open($p, $false, $true)
    $d.Fields.Update() | Out-Null
    $out = [IO.Path]::ChangeExtension($p, '.pdf')
    $d.ExportAsFixedFormat($out, 17, $false, 0, 0, 1, 1, 0, $true, $true, 1)
    $d.Close(0)
  }
} finally { $w.Quit() }
"""


def via_word(docx_paths, timeout=None):
    """Convert with Word through PowerShell COM (no pywin32 needed). Fields (page numbers) are updated."""
    paths = [os.path.abspath(p) for p in docx_paths]
    fd, pidfile = tempfile.mkstemp(prefix='cgx-word-', suffix='.pid')
    os.close(fd)
    env = dict(os.environ, CGX_DOCX='\n'.join(paths), CGX_PIDFILE=pidfile)
    try:
        r = _run([_powershell(), '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', _WORD_PS],
                 _auto_timeout(paths, timeout), env=env)
        if r is None or r.returncode != 0:
            try:
                with open(pidfile, encoding='ascii', errors='ignore') as f:
                    _kill_pid(f.read().strip())
            except OSError:
                pass
            if r is None:
                raise RuntimeError('Word conversion timed out (Word may be showing a dialog); '
                                   'use the built-in PDF engine or open Word once interactively.')
            raise RuntimeError('Word conversion failed: ' + (r.stderr or r.stdout).strip()[-600:])
    finally:
        try:
            os.remove(pidfile)
        except OSError:
            pass
    return [os.path.splitext(p)[0] + '.pdf' for p in docx_paths]


def via_libreoffice(docx_paths, timeout=None):
    exe = find_soffice()
    if not exe:
        raise RuntimeError('LibreOffice not found')
    outs = []
    for p in docx_paths:
        outdir = os.path.dirname(os.path.abspath(p))
        r = _run([exe, '--headless', '--convert-to', 'pdf', '--outdir', outdir, p], _auto_timeout([p], timeout))
        if r is None:
            raise RuntimeError('LibreOffice conversion timed out: ' + os.path.basename(p))
        out = os.path.splitext(p)[0] + '.pdf'
        if r.returncode != 0 or not os.path.exists(out):
            raise RuntimeError('LibreOffice conversion failed: ' + (r.stderr or r.stdout).strip()[-600:])
        outs.append(out)
    return outs
