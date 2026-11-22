#!/usr/bin/env python3
"""Build the enterprise deployment package for ChatGPT Export Converter.

Takes the original release zip (which holds the PyInstaller build in App\\), lays the files in
../package over it, and produces:

  <out>/ChatGPTExportConverter-<ver>.zip          full package (standard forward-slash zip paths)
  <out>/ChatGPTExportConverter-<ver>-x64.msi      per-machine MSI (also inside the zip)
  <out>/*.sha256                                  checksums of the two files above

Needs: Python 3.10+, wixl + wixl-heat (msitools package), cairosvg (for the PNG icons).

  python3 build_package.py --source-zip ChatGPTExportConverter-1.2.2.zip --out dist
"""
import argparse
import datetime
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(os.path.dirname(HERE), "package")
NAME = "ChatGPTExportConverter"
UPGRADE_CODE = "{65CBA05F-E4ED-49B7-B781-4C000A27306F}"   # never change: ties all versions together
# A new ProductCode for every version (MSI major upgrade). Add a fresh GUID here before a release:
#   python3 -c "import uuid; print(str(uuid.uuid4()).upper())"
PRODUCT_CODES = {
    "1.2.3": "{DF5DD0DA-4998-4F67-B1A4-59D03E0DDAAF}",
}
TEXT_EXT = {".cmd", ".txt", ".md", ".ps1", ".svg"}
CRLF_EXT = {".cmd", ".txt", ".md", ".ps1"}
PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
# Files from the original package that this kit replaces.
REPLACED = {"Install.cmd", "READ ME FIRST.txt", "CHANGELOG.txt", "App/Uninstall.cmd", "App/CHANGELOG.txt"}


def extract_zip(path, dest):
    """Extract a zip whose names may use backslashes, refusing absolute or '..' paths."""
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            name = info.filename.replace("\\", "/")
            parts = [p for p in name.split("/") if p]
            if not parts or name.startswith("/") or ".." in parts or ":" in parts[0]:
                raise SystemExit(f"unsafe path in zip: {info.filename!r}")
            target = os.path.join(dest, *parts)
            if name.endswith("/"):
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)


def dir_size_kb(path):
    total = 0
    for root, _, files in os.walk(path):
        total += sum(os.path.getsize(os.path.join(root, f)) for f in files)
    return (total + 1023) // 1024


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_text(src, dst, subs):
    text = open(src, encoding="utf-8").read()
    for k, v in subs.items():
        text = text.replace(k, v)
    ext = os.path.splitext(dst)[1].lower()
    if ext == ".cmd" and not text.isascii():
        raise SystemExit(f"{src}: batch files must be plain ASCII")
    if ext in CRLF_EXT:
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    with open(dst, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def overlay_kit(stage, subs):
    for root, _, files in os.walk(KIT):
        for f in files:
            src = os.path.join(root, f)
            rel = os.path.relpath(src, KIT)
            dst = os.path.join(stage, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.splitext(f)[1].lower() in TEXT_EXT:
                write_text(src, dst, subs)
            else:
                shutil.copyfile(src, dst)


def render_pngs(svg, outdir):
    import cairosvg
    for s in PNG_SIZES:
        cairosvg.svg2png(url=svg, write_to=os.path.join(outdir, f"logo-{s}.png"),
                         output_width=s, output_height=s)


def build_msi(stage, version, publisher, msi_path, work, product_code):
    """Stage the files the MSI installs (App minus Uninstall.cmd) and run wixl."""
    msi_root = os.path.join(work, "msi")
    shutil.copytree(os.path.join(stage, "App"), msi_root,
                    ignore=shutil.ignore_patterns("Uninstall.cmd", "ChatGPTExportConverter.ico"))
    marker = os.path.join(work, "INSTALLED-BY-MSI.txt")
    with open(marker, "w", newline="\r\n") as f:
        f.write(f"ChatGPT Export Converter {version} was installed from the MSI.\n"
                f"Remove it in Settings > Apps, or with: msiexec /x {product_code} /qn\n"
                f"UpgradeCode: {UPGRADE_CODE}  (see Deploy\\ADMIN-GUIDE.md)\n")
    rel = sorted(os.path.relpath(os.path.join(r, f), work).replace(os.sep, "/")
                 for r, _, fs in os.walk(msi_root) for f in fs)
    heat = subprocess.run(
        ["wixl-heat", "--prefix", "msi/", "--directory-ref", "INSTALLDIR",
         "--var", "var.SourceDir", "--component-group", "AppFiles", "--win64"],
        input="\n".join(rel) + "\n", capture_output=True, text=True, check=True, cwd=work)
    files_wxs = os.path.join(os.path.dirname(work), "files.wxs")
    open(files_wxs, "w").write(heat.stdout)
    subprocess.run(
        ["wixl", "-a", "x64", "-o", msi_path,
         "-D", "Win64=yes", "-D", f"Version={version}", "-D", f"Publisher={publisher}", "-D", f"ProductCode={product_code}",
         "-D", f"SourceDir={msi_root}", "-D", f"MarkerFile={marker}",
         "-D", f"IconFile={os.path.join(stage, 'App', 'ChatGPTExportConverter.ico')}",
         os.path.join(HERE, "product.wxs"), files_wxs],
        check=True, cwd=work)


def write_checksums(stage, version):
    out = os.path.join(stage, "Deploy", "SHA256SUMS.txt")
    lines = [f"# SHA-256 of every file in ChatGPTExportConverter-{version}. Check with Deploy\\Verify-Package.ps1"]
    for root, dirs, files in os.walk(stage):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(root, f)
            if p == out:
                continue
            rel = os.path.relpath(p, stage).replace(os.sep, "\\")
            lines.append(f"{sha256(p)}  {rel}")
    with open(out, "w", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")


def make_zip(stage, zip_path):
    base = os.path.basename(stage)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for root, dirs, files in os.walk(stage):
            dirs.sort()
            for f in sorted(files):
                p = os.path.join(root, f)
                arc = base + "/" + os.path.relpath(p, stage).replace(os.sep, "/")
                z.write(p, arc)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source-zip", required=True, help="original ChatGPTExportConverter-1.2.2.zip")
    ap.add_argument("--out", default="dist")
    ap.add_argument("--version", default=open(os.path.join(KIT, "VERSION.txt")).read().split()[0])
    ap.add_argument("--publisher", default="VoiceBoxx")
    a = ap.parse_args()
    if a.version not in PRODUCT_CODES:
        raise SystemExit(f"add a ProductCode GUID for {a.version} to PRODUCT_CODES first")

    os.makedirs(a.out, exist_ok=True)
    stage = os.path.join(os.path.abspath(a.out), f"{NAME}-{a.version}")
    if os.path.exists(stage):
        shutil.rmtree(stage)

    with tempfile.TemporaryDirectory() as work:
        extract_zip(a.source_zip, work)
        tops = [d for d in os.listdir(work) if os.path.isdir(os.path.join(work, d))]
        if len(tops) != 1 or not os.path.isfile(os.path.join(work, tops[0], "App", f"{NAME}.exe")):
            raise SystemExit("source zip does not look like a ChatGPT Export Converter release")
        src = os.path.join(work, tops[0])
        shutil.copytree(src, stage,
                        ignore=lambda d, names: [n for n in names
                                                 if os.path.relpath(os.path.join(d, n), src).replace(os.sep, "/") in REPLACED])

        subs = {"@VERSION@": a.version, "@PUBLISHER@": a.publisher, "@UPGRADECODE@": UPGRADE_CODE,
                "@PRODUCTCODE@": PRODUCT_CODES[a.version],
                "@DATE@": datetime.date.today().isoformat(), "@SIZE_KB@": "0", "@SIZE_MB@": "0"}
        overlay_kit(stage, subs)
        kb = dir_size_kb(os.path.join(stage, "App"))
        subs.update({"@SIZE_KB@": str(kb), "@SIZE_MB@": str(round(kb / 1024))})
        overlay_kit(stage, subs)   # again, now that the installed size is known
        for f in ("CHANGELOG.txt", "VERSION.txt"):
            shutil.copyfile(os.path.join(stage, f), os.path.join(stage, "App", f))
        render_pngs(os.path.join(stage, "Deploy", "Icons", "logo.svg"), os.path.join(stage, "Deploy", "Icons"))

        msi_name = f"{NAME}-{a.version}-x64.msi"
        mwork = os.path.join(work, "_msi")
        os.makedirs(mwork)
        build_msi(stage, a.version, a.publisher, os.path.join(stage, msi_name), mwork,
                  PRODUCT_CODES[a.version])

    write_checksums(stage, a.version)
    zip_path = os.path.join(a.out, f"{NAME}-{a.version}.zip")
    make_zip(stage, zip_path)
    shutil.copyfile(os.path.join(stage, msi_name), os.path.join(a.out, msi_name))
    for p in (zip_path, os.path.join(a.out, msi_name)):
        with open(p + ".sha256", "w") as f:
            f.write(f"{sha256(p)}  {os.path.basename(p)}\n")
        print(f"{sha256(p)}  {p}")


if __name__ == "__main__":
    sys.exit(main())
