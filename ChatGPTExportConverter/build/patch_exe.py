#!/usr/bin/env python3
"""Patch the frozen ChatGPTExportConverter.exe (PyInstaller 6, one-folder, Python 3.14).

Run with Python 3.14 (same bytecode magic as the frozen program). Changes:

  PYZ archive
    pdf_convert   replaced by ../patches/pdf_convert.py                       (F5, F6)
    attachments   safe_name() replaced by ../patches/attachments_safe_name.py (F12)
    version       __version__ set to --version
  Bootloader archive
    pyi_rth_cgxfixes  new start-up hook from ../patches/pyi_rth_cgxfixes.py   (F13)
  PE resources
    version info  FileVersion/ProductVersion = --version, adds CompanyName and LegalCopyright (F14)

  python3.14 patch_exe.py IN.exe OUT.exe --version 1.2.4 --company "VoiceBoxx"
  python3.14 patch_exe.py IN.exe --selftest     # proves the archive writer is byte-exact

Needs: pefile.
"""
import argparse
import datetime
import importlib.util
import marshal
import os
import struct
import sys
import types
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
PATCHES = os.path.join(os.path.dirname(HERE), "patches")
MAGIC = b"MEI\014\013\012\013\016"
COOKIE = "!8sIIII64s"
COOKIE_LEN = struct.calcsize(COOKIE)
ENTRY = "!IIIIBc"
ENTRY_LEN = struct.calcsize(ENTRY)


# ---------------------------------------------------------------- PyInstaller CArchive ----
def read_carchive(data):
    i = data.rfind(MAGIC)
    if i < 0:
        raise SystemExit("not a PyInstaller executable")
    _, pkglen, toc, toclen, pyver, pylib = struct.unpack(COOKIE, data[i:i + COOKIE_LEN])
    if i + COOKIE_LEN != len(data):
        raise SystemExit("data after the PyInstaller cookie (already signed?); patch the unsigned exe")
    start = i + COOKIE_LEN - pkglen
    entries, pos = [], start + toc
    while pos < start + toc + toclen:
        elen, off, clen, ulen, cflag, tc = struct.unpack(ENTRY, data[pos:pos + ENTRY_LEN])
        name = data[pos + ENTRY_LEN:pos + elen].rstrip(b"\0").decode("utf-8")
        entries.append({"name": name, "tc": tc, "cflag": cflag, "ulen": ulen,
                        "raw": data[start + off:start + off + clen]})
        pos += elen
    return data[:start], entries, pyver, pylib


def entry_data(e):
    return zlib.decompress(e["raw"]) if e["cflag"] else e["raw"]


def set_entry_data(e, payload):
    e["ulen"] = len(payload)
    e["raw"] = zlib.compress(payload, 9) if e["cflag"] else payload


def write_carchive(pe, entries, pyver, pylib):
    body, toc = bytearray(), bytearray()
    for e in entries:
        name = e["name"].encode("utf-8")
        elen = ENTRY_LEN + len(name) + 1
        elen += (-elen) % 16
        toc += struct.pack(ENTRY, elen, len(body), len(e["raw"]), e["ulen"], e["cflag"], e["tc"])
        toc += name + b"\0" * (elen - ENTRY_LEN - len(name))
        body += e["raw"]
    pkglen = len(body) + len(toc) + COOKIE_LEN
    cookie = struct.pack(COOKIE, MAGIC, pkglen, len(body), len(toc), pyver, pylib)
    return pe + bytes(body) + bytes(toc) + cookie


# ---------------------------------------------------------------------- PYZ archive -------
def read_pyz(data):
    if data[:4] != b"PYZ\0":
        raise SystemExit("bad PYZ magic")
    if data[4:8] != importlib.util.MAGIC_NUMBER:
        raise SystemExit("run this script with the same Python minor version as the frozen program (3.14)")
    tocoff = struct.unpack("!i", data[8:12])[0]
    toc = marshal.loads(data[tocoff:])
    first = min(v[1] for _, v in toc)
    raw = {name: (tc, data[off:off + ln]) for name, (tc, off, ln) in toc}
    return data[:first], [n for n, _ in toc], raw


def write_pyz(header, order, raw):
    out = bytearray(header)
    toc = []
    for name in order:
        tc, blob = raw[name]
        toc.append((name, (tc, len(out), len(blob))))
        out += blob
    tocoff = len(out)
    out += marshal.dumps(toc)
    out[8:12] = struct.pack("!i", tocoff)
    return bytes(out)


def pyz_code(raw, name):
    return marshal.loads(zlib.decompress(raw[name][1]))


def pyz_put(raw, name, code):
    raw[name] = (raw[name][0], zlib.compress(marshal.dumps(code), 9))


def compile_file(path, filename):
    with open(path, encoding="utf-8") as f:
        return compile(f.read(), filename, "exec", dont_inherit=True, optimize=0)


def replace_const(code, pred, new):
    """Return code with every constant matching pred replaced (recursing into nested code)."""
    consts, hit = [], 0
    for c in code.co_consts:
        if pred(c):
            consts.append(new)
            hit += 1
        elif isinstance(c, types.CodeType):
            c2, h = replace_const(c, pred, new)
            consts.append(c2)
            hit += h
        else:
            consts.append(c)
    return code.replace(co_consts=tuple(consts)), hit


# ------------------------------------------------------------- PE version resource -------
def _node(key, value=b"", wtype=1, children=b"", value_len=None):
    k = (key + "\0").encode("utf-16-le")
    hdr_len = 6 + len(k)
    pad1 = (-hdr_len) % 4
    v = value + b"\0" * ((-len(value)) % 4) if children else value
    body = b"\0" * pad1 + v
    if children:
        body += b"\0" * ((-(hdr_len + len(body))) % 4) + children
    total = hdr_len + len(body)
    if value_len is None:
        value_len = len(value) // 2 if wtype == 1 else len(value)
    blob = struct.pack("<HHH", total, value_len, wtype) + k + body
    return blob + b"\0" * ((-len(blob)) % 4)


def build_version_info(old_fixed, version, strings):
    parts = [int(x) for x in version.split(".")] + [0] * 4
    ms, ls = (parts[0] << 16) | parts[1], (parts[2] << 16) | parts[3]
    fixed = bytearray(old_fixed)
    struct.pack_into("<IIII", fixed, 8, ms, ls, ms, ls)   # dwFileVersionMS/LS, dwProductVersionMS/LS
    table = b"".join(_node(k, (v + "\0").encode("utf-16-le"), 1) for k, v in strings)
    sfi = _node("StringFileInfo", b"", 1, _node("040904B0", b"", 1, table, 0), 0)
    vfi = _node("VarFileInfo", b"", 1, _node("Translation", struct.pack("<HH", 0x0409, 0x04B0), 0), 0)
    return _node("VS_VERSION_INFO", bytes(fixed), 0, sfi + vfi, 52)


def patch_version_resource(pe_bytes, version, company, copyright_):
    import pefile
    pe = pefile.PE(data=pe_bytes)
    ver = man = None
    for t in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        for n in t.directory.entries:
            for lang in n.directory.entries:
                if t.id == 16:
                    ver = lang.data.struct
                elif t.id == 24:
                    man = lang.data.struct
    rsrc = next(s for s in pe.sections if s.Name.rstrip(b"\0") == b".rsrc")
    # Expected layout (true for this build): version info, then manifest, then free space to
    # the end of .rsrc. Both are rewritten into that span.
    if not (ver and man and ver.OffsetToData + ver.Size == man.OffsetToData):
        raise SystemExit("unexpected resource layout; version info not patched")
    old = pe.get_data(ver.OffsetToData, ver.Size)
    old_fixed = old[40:92]
    if struct.unpack("<I", old_fixed[:4])[0] != 0xFEEF04BD:
        raise SystemExit("VS_FIXEDFILEINFO not found")
    old_strings = {k.decode(): v.decode() for fi in pe.FileInfo for e in fi
                   if hasattr(e, "StringTable") for st in e.StringTable for k, v in st.entries.items()}
    strings = [
        ("CompanyName", company),
        ("FileDescription", old_strings.get("FileDescription", "ChatGPT Export Converter")),
        ("FileVersion", version),
        ("InternalName", old_strings.get("InternalName", "ChatGPTExportConverter")),
        ("LegalCopyright", copyright_),
        ("OriginalFilename", old_strings.get("OriginalFilename", "ChatGPTExportConverter.exe")),
        ("ProductName", old_strings.get("ProductName", "ChatGPT Export Converter")),
        ("ProductVersion", version),
    ]
    new_ver = build_version_info(old_fixed, version, strings)
    manifest = pe.get_data(man.OffsetToData, man.Size)
    span_start = ver.OffsetToData
    span_end = rsrc.VirtualAddress + rsrc.SizeOfRawData
    man_rva = span_start + len(new_ver)
    man_rva += (-man_rva) % 8
    if man_rva + len(manifest) > span_end:
        raise SystemExit("not enough room in .rsrc for the new version info")
    blob = new_ver + b"\0" * (man_rva - span_start - len(new_ver)) + manifest
    off = pe.get_offset_from_rva(span_start)
    out = bytearray(pe.__data__)
    out[off:off + len(blob)] = blob
    pe2 = pefile.PE(data=bytes(out))
    for t in pe2.DIRECTORY_ENTRY_RESOURCE.entries:
        for n in t.directory.entries:
            for lang in n.directory.entries:
                if t.id == 16:
                    lang.data.struct.Size = len(new_ver)
                elif t.id == 24:
                    lang.data.struct.OffsetToData = man_rva
    s2 = next(s for s in pe2.sections if s.Name.rstrip(b"\0") == b".rsrc")
    s2.Misc_VirtualSize = max(s2.Misc_VirtualSize, man_rva + len(manifest) - s2.VirtualAddress)
    return bytes(pe2.write())


def fix_checksum(data):
    """PE checksum over the whole file, archive included (as PyInstaller itself does)."""
    import pefile
    pe = pefile.PE(data=data, fast_load=True)
    out = bytearray(data)
    struct.pack_into("<I", out, pe.OPTIONAL_HEADER.get_file_offset() + 64, pe.generate_checksum())
    return bytes(out)


# ------------------------------------------------------------------------------ main -----
def patch(data, version, company, copyright_):
    pe, entries, pyver, pylib = read_carchive(data)
    if pyver != 314:
        raise SystemExit(f"frozen program is Python {pyver}, this patcher targets 3.14")
    names = [e["name"] for e in entries]

    pyz_e = next(e for e in entries if e["tc"] == b"z")
    header, order, raw = read_pyz(entry_data(pyz_e))

    pyz_put(raw, "pdf_convert", compile_file(os.path.join(PATCHES, "pdf_convert.py"), "pdf_convert.py"))

    att = pyz_code(raw, "attachments")
    patch_mod = compile_file(os.path.join(PATCHES, "attachments_safe_name.py"), "attachments.py")
    new_fn = next(c for c in patch_mod.co_consts if isinstance(c, types.CodeType) and c.co_name == "safe_name")
    old_fn = next(c for c in att.co_consts if isinstance(c, types.CodeType) and c.co_name == "safe_name")
    if new_fn.co_varnames[:2] != old_fn.co_varnames[:2] or new_fn.co_argcount != old_fn.co_argcount:
        raise SystemExit("safe_name signature changed in this build; review the patch")
    new_fn = new_fn.replace(co_firstlineno=old_fn.co_firstlineno)
    att, hits = replace_const(att, lambda c: c is old_fn, new_fn)
    assert hits == 1
    pyz_put(raw, "attachments", att)

    ver_code = pyz_code(raw, "version")
    old_v = next(c for c in ver_code.co_consts if isinstance(c, str) and c.count(".") == 2 and c.replace(".", "").isdigit())
    ver_code, hits = replace_const(ver_code, lambda c: c == old_v, version)
    assert hits == 1
    pyz_put(raw, "version", ver_code)

    set_entry_data(pyz_e, write_pyz(header, order, raw))

    hook = marshal.dumps(compile_file(os.path.join(PATCHES, "pyi_rth_cgxfixes.py"), "pyi_rth_cgxfixes.py"))
    if "pyi_rth_cgxfixes" in names:
        raise SystemExit("this exe is already patched")
    hook_e = {"name": "pyi_rth_cgxfixes", "tc": b"s", "cflag": 1, "ulen": 0, "raw": b""}
    set_entry_data(hook_e, hook)
    entries.insert(names.index("app"), hook_e)        # after the other hooks, before app.py

    pe = patch_version_resource(pe, version, company, copyright_)
    return fix_checksum(write_carchive(pe, entries, pyver, pylib)), old_v


def selftest(data):
    pe, entries, pyver, pylib = read_carchive(data)
    pyz_e = next(e for e in entries if e["tc"] == b"z")
    pyz = entry_data(pyz_e)
    header, order, raw = read_pyz(pyz)
    new = write_pyz(header, order, raw)
    a, b = struct.unpack("!i", pyz[8:12])[0], struct.unpack("!i", new[8:12])[0]
    # Module data must match byte for byte; the TOC may differ only in marshal's internal
    # reference flags, so it is compared by value.
    assert a == b and new[:a] == pyz[:a], "PYZ module data differs"
    assert marshal.loads(new[b:]) == marshal.loads(pyz[a:]), "PYZ TOC differs"
    assert write_carchive(pe, entries, pyver, pylib) == data, "CArchive rebuild differs"
    print(f"selftest OK: {len(entries)} archive entries rebuild byte-identical; "
          f"{len(order)} PYZ modules identical, TOC equal")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("exe")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--version")
    ap.add_argument("--company", default="VoiceBoxx")
    ap.add_argument("--copyright")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    data = open(a.exe, "rb").read()
    if a.selftest:
        return selftest(data)
    if not (a.out and a.version):
        ap.error("OUT and --version are required")
    copyright_ = a.copyright or f"Copyright (c) {datetime.date.today().year} {a.company}"
    out, old_v = patch(data, a.version, a.company, copyright_)
    with open(a.out, "wb") as f:
        f.write(out)
    print(f"patched {a.exe} ({old_v}) -> {a.out} ({a.version})")


if __name__ == "__main__":
    sys.exit(main())
