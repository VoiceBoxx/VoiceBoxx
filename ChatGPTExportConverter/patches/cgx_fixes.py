"""ChatGPT Export Converter 1.2.7 fixes, applied at start-up by pyi_rth_cgxfixes.

1. Spacing in PDFs: ReportLab collapses runs of spaces, tabs and leading indentation, so text
   typed with aligned columns, indented lists or ASCII art lost its layout in the PDF (the Word
   files kept it). Spaces that matter are now kept as non-breaking spaces.
2. Markdown table alignment: ":---:" (centre) and "---:" (right) were ignored, so numeric columns
   were left-aligned in both Word and PDF. The alignment row is now honoured. Columns typed by hand
   with spaces (2+ lines with wide gaps) are shown in a fixed-width font so they line up.
3. Output folder: every run used ChatGPT_Archive_<owner>_<date>. A second conversion on the
   same day (another export, or two at once) wrote into the same folder, overwrote the master
   index and mixed the attachments. Each run now gets its own folder ("... (2)", "... (3)").
4. Page estimates: an embedded image or PDF page counted as a tenth of a page, so volumes came
   out up to 60% longer than the target. Attachments are now weighted by what they render as.
5. Several exports dropped on the program at once: the program silently did nothing. They are
   now converted one after another in a progress window (see batch()).
6. (1.2.8) Word "open saved file" links were URL-encoded twice and pointed at files that don't
   exist. "#" is kept out of output folder names.
"""
import os
import re
import sys
import types

_WS_LEAD = re.compile(r"(?m)^ +")
_WS_RUN = re.compile(r" {2,}")
# Same test the program's own parser (layout.md_blocks) uses for a table's separator row, so
# the alignment rows found here pair up one-to-one with the tables it builds.
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}")
_FENCE = re.compile(r"^\s*(```|~~~)")


# ---- 1. keep meaningful spaces in PDF paragraphs ------------------------------------------
def keep_spaces(s):
    if not s or not ("  " in s or "\t" in s or "\n " in s or s[0] == " "):
        return s
    s = s.replace("\t", "    ")
    s = _WS_LEAD.sub(lambda m: " " * len(m.group()), s)
    # first space stays breakable so long runs can still wrap; the rest keep their width
    return _WS_RUN.sub(lambda m: " " + " " * (len(m.group()) - 1), s)


def _patch_render_pdf(render_pdf):
    orig = render_pdf.esc

    def esc(s, base=None, mono=False):
        return orig(s if mono else keep_spaces(s), base, mono)

    esc.__doc__ = orig.__doc__
    render_pdf.esc = esc


# ---- 2. markdown table alignment -----------------------------------------------------------
def table_alignments(text):
    """Alignment lists for each markdown table in text, in order (code blocks skipped)."""
    out, in_code, prev = [], False, ""
    for line in (text or "").split("\n"):
        if _FENCE.match(line):
            in_code = not in_code
        elif not in_code and "|" in prev and _TABLE_SEP.match(line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            out.append(["c" if c.startswith(":") and c.endswith(":") else "r" if c.endswith(":") else "l"
                        for c in cells])
        prev = line
    return out


_GAP = re.compile(r"\S(?: {2,}|\t+) *\S")


def split_typed_tables(block):
    """Columns lined up by hand with spaces only line up in a fixed-width font. In a plain
    paragraph, each run of 2+ consecutive lines with gaps of 2+ spaces or tabs between words
    becomes a fixed-width (code-style) block; the other lines stay normal text."""
    if not (isinstance(block, dict) and block.get("t") == "p" and len(block.get("runs") or []) == 1
            and set(block["runs"][0]) == {"text"}):
        return [block]
    lines = block["runs"][0]["text"].split("\n")
    flags = [bool(_GAP.search(l)) for l in lines]
    if sum(flags) < 2:
        return [block]
    out, i = [], 0
    while i < len(lines):
        j = i
        while j < len(lines) and flags[j] == flags[i]:
            j += 1
        chunk = "\n".join(lines[i:j])
        if flags[i] and j - i >= 2:
            out.append({"t": "code", "text": chunk.expandtabs(4), "lang": None})
        elif out and out[-1].get("t") == "p":
            out[-1]["runs"][0]["text"] += "\n" + chunk
        else:
            out.append(dict(block, runs=[{"text": chunk}]))
        i = j
    return out


def _split_all(blocks):
    out = []
    for b in blocks:
        out.extend(split_typed_tables(b))
    return out


def _patch_layout(layout):
    orig = layout.md_blocks
    orig_message = layout.message

    def message(m, opts, export):
        blocks = orig_message(m, opts, export)
        for b in blocks or []:
            if isinstance(b, dict) and b.get("t") == "body" and isinstance(b.get("blocks"), list):
                b["blocks"] = _split_all(b["blocks"])
        return blocks

    message.__doc__ = orig_message.__doc__
    layout.message = message

    def md_blocks(text):
        blocks = _split_all(orig(text))
        aligns = iter(table_alignments(text))
        for b in blocks:
            if isinstance(b, dict) and b.get("t") == "table" and b.get("md"):
                al = next(aligns, None)
                if al is None:
                    break
                n = len(b.get("align") or b.get("header") or [])
                b["align"] = (al + ["l"] * n)[:n]
        return blocks

    md_blocks.__doc__ = orig.__doc__
    layout.md_blocks = md_blocks


# ---- 3. a separate output folder for every run ---------------------------------------------
def claim_folder(path):
    """Create path, or 'path (2)', 'path (3)', ... and return the one created.
    os.mkdir is atomic, so two conversions running at once can never get the same folder."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    for i in range(1, 1000):
        cand = path if i == 1 else "%s (%d)" % (path, i)
        try:
            os.mkdir(cand)
            return cand
        except FileExistsError:
            continue
    raise RuntimeError("Could not create an output folder next to " + path)


class _PathProxy:
    def __getattr__(self, name):
        return getattr(os.path, name)

    @staticmethod
    def join(*parts):
        if len(parts) == 2 and str(parts[1]).startswith("ChatGPT_Archive_"):
            # "#" (as in "CMP#12345") breaks links and some sync tools; keep it out of folder names
            return claim_folder(os.path.join(parts[0], str(parts[1]).replace("#", "")))
        return os.path.join(*parts)


class _OsProxy(types.ModuleType):
    path = _PathProxy()

    def __getattr__(self, name):
        return getattr(os, name)


def _patch_converter(converter):
    # converter builds the folder with os.path.join(base, "ChatGPT_Archive_...") and then
    # os.makedirs(folder, exist_ok=True); only that one join is redirected.
    converter.os = _OsProxy("os")


# ---- 4. page estimates that account for attachments ----------------------------------------
_CHARS_PER_PAGE = 2850.0


def attachment_pages(a):
    if not isinstance(a, dict) or not a.get("path"):
        return 0.0                         # not in the export: only a one-line placeholder
    kind, size = a.get("kind"), a.get("size") or 0
    if kind == "image":
        w, h = a.get("width") or 0, a.get("height") or 0
        return min(1.0, (h / w) * 0.72 + 0.08) if w and h else 0.5
    if kind == "pdf":
        return 2.4                         # first pages are shown as images (~0.8 page each)
    if kind == "text":
        return min(400, size / 40.0) / 55.0
    if kind == "docx":
        return min(3.0, size / 20000.0) + 0.3
    return 0.0


def _patch_extract(extract):
    orig = extract.estimate_pages

    def estimate_pages(c, include_branches=True):
        base = orig(c, include_branches)
        msgs = list(c.get("messages") or [])
        if include_branches:
            for br in c.get("branches") or []:
                msgs += br.get("messages", []) if isinstance(br, dict) else list(br or [])
        extra = 0.0
        for m in msgs:
            if isinstance(m, dict):
                extra += sum(attachment_pages(a) for a in m.get("attachments") or [])
        return base + extra

    estimate_pages.__doc__ = orig.__doc__
    extract.estimate_pages = estimate_pages


# ---- 6. Word attachment links ----------------------------------------------------------------
_PCT = re.compile(r"%[0-9A-Fa-f]{2}")


def _patch_render_docx(render_docx):
    # The "open saved file" line already passes an encoded URL, and the hyperlink writer encoded
    # it again ("002%2520-%2520photo.png"), so Word looked for a file that doesn't exist. Encode once.
    orig = render_docx.file_url

    def file_url(rel):
        return rel if _PCT.search(rel or "") else orig(rel)

    file_url.__doc__ = orig.__doc__
    render_docx.file_url = file_url


def apply():
    import extract, layout, converter, render_pdf, render_docx
    for fn, mod in ((_patch_render_pdf, render_pdf), (_patch_layout, layout),
                    (_patch_converter, converter), (_patch_extract, extract),
                    (_patch_render_docx, render_docx)):
        try:
            fn(mod)
        except Exception:
            pass                           # a failed fix must never stop the program


# ---- 5. several exports at once --------------------------------------------------------------
def dropped_exports(argv):
    """The paths, when the program was started with two or more existing files or folders
    (for example several exports dragged onto it), else None."""
    if len(argv) < 2 or any(a.startswith("-") for a in argv):
        return None
    return argv if all(os.path.exists(a) for a in argv) else None


def batch(paths):
    """Convert each export in turn, each into its own folder next to it, in a progress window."""
    import queue
    import threading
    import tkinter as tk
    from tkinter import ttk
    import converter
    import version

    q = queue.Queue()
    root = tk.Tk()
    root.title("ChatGPT Export Converter %s - %d exports" % (version.__version__, len(paths)))
    try:
        root.iconbitmap(os.path.join(getattr(sys, "_MEIPASS", ""), "assets", "app.ico"))
    except Exception:
        pass
    root.geometry("720x460")
    root.minsize(560, 360)
    frm = ttk.Frame(root, padding=12)
    frm.pack(fill="both", expand=True)
    head = ttk.Label(frm, text="Converting %d exports, one after another..." % len(paths))
    head.pack(anchor="w")
    bar = ttk.Progressbar(frm, maximum=len(paths))
    bar.pack(fill="x", pady=(8, 8))
    log = tk.Text(frm, height=16, wrap="word", state="disabled")
    log.pack(fill="both", expand=True)
    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(8, 0))
    close = ttk.Button(btns, text="Close", command=root.destroy, state="disabled")
    close.pack(side="right")
    folders = []

    def open_folders():
        for f in folders:
            try:
                os.startfile(f)
            except Exception:
                pass

    opener = ttk.Button(btns, text="Open output folders", command=open_folders, state="disabled")
    opener.pack(side="right", padx=(0, 8))

    def write(line):
        log.configure(state="normal")
        log.insert("end", line + "\n")
        log.see("end")
        log.configure(state="disabled")

    def work():
        ok = 0
        for i, src in enumerate(paths, 1):
            q.put(("log", "[%d/%d] %s" % (i, len(paths), src)))
            try:
                res = converter.convert(src, log=lambda m: q.put(("log", "    " + str(m))))
                folder = res.get("folder") if isinstance(res, dict) else None
                if folder:
                    folders.append(folder)
                q.put(("log", "    Done: " + (folder or "")))
                ok += 1
            except Exception as e:
                q.put(("log", "    FAILED: %s" % e))
            q.put(("step", i))
        q.put(("end", ok))

    def poll():
        try:
            while True:
                kind, val = q.get_nowait()
                if kind == "log":
                    write(val)
                elif kind == "step":
                    bar["value"] = val
                elif kind == "end":
                    head.configure(text="%d of %d exports converted." % (val, len(paths)))
                    close.configure(state="normal")
                    if folders:
                        opener.configure(state="normal")
                    return
        except queue.Empty:
            pass
        root.after(150, poll)

    threading.Thread(target=work, daemon=True).start()
    root.after(150, poll)
    root.mainloop()
