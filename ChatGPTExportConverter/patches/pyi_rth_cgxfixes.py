# ChatGPT Export Converter 1.2.3 start-up fixes, run by the PyInstaller bootloader before app.py.
#
# High-DPI: the 1.2.2 build is not DPI-aware, so Windows bitmap-stretches the window on scaled
# displays (blurry text). Declare system DPI awareness, then scale the window sizes the program
# sets in pixels (geometry, minsize) by the display scale so the layout keeps its proportions.
import sys

if sys.platform == 'win32':
    def _cgx_dpi_fix():
        import ctypes
        import re
        import tkinter

        user32 = ctypes.windll.user32
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)      # PROCESS_SYSTEM_DPI_AWARE
        except Exception:
            try:
                user32.SetProcessDPIAware()
            except Exception:
                return
        try:
            dpi = user32.GetDpiForSystem()                     # Windows 10 1607+
        except Exception:
            hdc = user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)   # LOGPIXELSX
            user32.ReleaseDC(0, hdc)
        scale = (dpi or 96) / 96.0
        if scale < 1.05:
            return

        def _fit(widget, w, h):
            try:
                sw, sh = widget.winfo_screenwidth(), widget.winfo_screenheight()
            except Exception:
                return w, h
            return min(w, int(sw * 0.95)), min(h, int(sh * 0.9))

        orig_geometry = tkinter.Wm.wm_geometry
        orig_minsize = tkinter.Wm.wm_minsize

        def wm_geometry(self, newGeometry=None):
            if newGeometry:
                m = re.fullmatch(r'(\d+)x(\d+)(.*)', str(newGeometry))
                if m:
                    w, h = _fit(self, round(int(m.group(1)) * scale), round(int(m.group(2)) * scale))
                    newGeometry = '%dx%d%s' % (w, h, m.group(3))
            return orig_geometry(self, newGeometry)

        def wm_minsize(self, width=None, height=None):
            if width is not None and height is not None:
                width, height = _fit(self, round(width * scale), round(height * scale))
            return orig_minsize(self, width, height)

        tkinter.Wm.wm_geometry = tkinter.Wm.geometry = wm_geometry
        tkinter.Wm.wm_minsize = tkinter.Wm.minsize = wm_minsize

    try:
        _cgx_dpi_fix()
    except Exception:
        pass        # never stop the program from starting
    del _cgx_dpi_fix
