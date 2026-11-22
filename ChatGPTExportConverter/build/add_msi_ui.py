#!/usr/bin/env python3
"""Add a setup wizard to the MSI that wixl builds (wixl cannot author dialogs).

Without dialogs, double-clicking the MSI showed only a brief "Preparing to install" box. The UAC
prompt then opened behind other windows (a flashing shield on the taskbar), so the installer
seemed to do nothing, and a successful install ended without any message.

This adds the standard Windows Installer UI tables (the same design as WiX's WixUI_Minimal):

  Welcome (Install, with the admin shield) -> Progress -> Finished (option to start the program)
  Maintenance (Repair / Remove) when it is already installed
  Cancel confirmation, "cancelled" and "failed" pages, and the error dialog for installer messages

The program icon is shown on every page. Silent installs (/qn, /qb) never show these dialogs, so
deployment behaviour is unchanged.

  python3 add_msi_ui.py package.msi path/to/app.ico
"""
import os
import subprocess
import sys
import tempfile

APP = "ChatGPT Export Converter"
W, H = 370, 270                      # standard wizard size in dialog units
BTN_Y, BTN_W, BTN_H = 243, 56, 17

# Control attribute bits
VIS, EN = 1, 2
TRANSPARENT = 65536
NOPREFIX = 131072
SHIELD = 8388608                     # msidbControlAttributesElevationShield
PROGRESS95 = 65536
ICON48 = 1 + 1048576 + 6291456       # visible + FixedSize + IconSize48
TXT = VIS | EN | TRANSPARENT | NOPREFIX
BTN = VIS | EN
# Dialog attribute bits
MODAL = 1 | 2                        # visible + modal
MODELESS = 1                         # visible only (progress page)
ERROR_DLG = 65536 | MODAL

TITLE = "{\\UIFontTitle}"

dialogs, controls, events, conditions, mappings = [], [], [], [], []


def dialog(name, title, first, default, cancel, attrs=MODAL, w=W, h=H):
    dialogs.append((name, 50, 50, w, h, attrs, title, first, default, cancel))


def ctl(dlg, name, typ, x, y, w, h, attrs, prop="", text="", nxt=""):
    controls.append((dlg, name, typ, x, y, w, h, attrs, prop, text, nxt, ""))


def ev(dlg, control, event, arg, cond="1", order=1):
    events.append((dlg, control, event, arg, cond, order))


def page(dlg, heading, body, body_h=120):
    """Common page layout: icon, heading, body text, line above the buttons."""
    ctl(dlg, "Icon", "Icon", 20, 20, 32, 32, ICON48, text="AppIconBin")
    ctl(dlg, "Heading", "Text", 64, 22, 290, 26, TXT, text=TITLE + heading)
    if body:
        ctl(dlg, "Body", "Text", 64, 54, 290, body_h, TXT, text=body)
    ctl(dlg, "Line", "Line", 0, 234, W, 0, VIS)


# ---- Welcome ------------------------------------------------------------------------------
dialog("WelcomeDlg", f"{APP} Setup", "Install", "Install", "Cancel")
page("WelcomeDlg", f"Install {APP} [ProductVersion]",
     f"This installs {APP} for all users of this computer, in:\r\n[INSTALLDIR]\r\n\r\n"
     "Click Install to continue. Windows will ask for administrator permission.\r\n\r\n"
     "The program works offline and makes no network connections.")
ctl("WelcomeDlg", "Install", "PushButton", 236, BTN_Y, BTN_W, BTN_H, BTN | SHIELD, text="&Install", nxt="Cancel")
ctl("WelcomeDlg", "Cancel", "PushButton", 304, BTN_Y, BTN_W, BTN_H, BTN, text="Cancel", nxt="Install")
ev("WelcomeDlg", "Install", "EndDialog", "Return")
ev("WelcomeDlg", "Cancel", "SpawnDialog", "CancelDlg")

# ---- Maintenance (already installed) ------------------------------------------------------
dialog("MaintenanceDlg", f"{APP} Setup", "Remove", "Remove", "Cancel")
page("MaintenanceDlg", f"{APP} [ProductVersion] is installed",
     "Repair puts back missing or damaged program files.\r\n"
     "Remove uninstalls the program.\r\n\r\n"
     "Archives you have created are never touched.")
ctl("MaintenanceDlg", "Repair", "PushButton", 168, BTN_Y, BTN_W, BTN_H, BTN | SHIELD, text="&Repair", nxt="Remove")
ctl("MaintenanceDlg", "Remove", "PushButton", 236, BTN_Y, BTN_W, BTN_H, BTN | SHIELD, text="Re&move", nxt="Cancel")
ctl("MaintenanceDlg", "Cancel", "PushButton", 304, BTN_Y, BTN_W, BTN_H, BTN, text="Cancel", nxt="Repair")
ev("MaintenanceDlg", "Repair", "ReinstallMode", "ecmus", order=1)
ev("MaintenanceDlg", "Repair", "Reinstall", "ALL", order=2)
ev("MaintenanceDlg", "Repair", "EndDialog", "Return", order=3)
ev("MaintenanceDlg", "Remove", "Remove", "ALL", order=1)
ev("MaintenanceDlg", "Remove", "EndDialog", "Return", order=2)
ev("MaintenanceDlg", "Cancel", "SpawnDialog", "CancelDlg")

# ---- Progress (modeless, shown while the installation runs) -------------------------------
dialog("ProgressDlg", f"{APP} Setup", "Cancel", "Cancel", "Cancel", attrs=MODELESS)
page("ProgressDlg", f"Setting up {APP}", "Please wait. This takes less than a minute.", body_h=20)
ctl("ProgressDlg", "ActionText", "Text", 64, 100, 290, 12, TXT)
ctl("ProgressDlg", "ProgressBar", "ProgressBar", 64, 116, 290, 12, VIS | PROGRESS95, text="Progress")
ctl("ProgressDlg", "Cancel", "PushButton", 304, BTN_Y, BTN_W, BTN_H, BTN, text="Cancel", nxt="Cancel")
ev("ProgressDlg", "Cancel", "SpawnDialog", "CancelDlg")
mappings += [("ProgressDlg", "ActionText", "ActionText", "Text"),
             ("ProgressDlg", "ProgressBar", "SetProgress", "Progress")]

# ---- Finished -----------------------------------------------------------------------------
dialog("ExitDlg", f"{APP} Setup", "Finish", "Finish", "Finish")
page("ExitDlg", "Setup completed", "")
hidden_txt = EN | TRANSPARENT | NOPREFIX          # shown by ControlCondition below
ctl("ExitDlg", "TxtInstalled", "Text", 64, 54, 290, 60, hidden_txt,
    text=f"{APP} [ProductVersion] is installed. Start it from the Start menu.")
ctl("ExitDlg", "TxtRepaired", "Text", 64, 54, 290, 60, hidden_txt,
    text=f"{APP} [ProductVersion] has been repaired.")
ctl("ExitDlg", "TxtRemoved", "Text", 64, 54, 290, 60, hidden_txt,
    text=f"{APP} has been removed. Archives you created were not touched.")
ctl("ExitDlg", "Launch", "CheckBox", 64, 120, 290, 14, VIS | EN, prop="LAUNCHAPP",
    text=f"&Start {APP} now", nxt="Finish")
ctl("ExitDlg", "Finish", "PushButton", 304, BTN_Y, BTN_W, BTN_H, BTN, text="&Finish", nxt="Launch")
ev("ExitDlg", "Finish", "DoAction", "LaunchApp", 'LAUNCHAPP = 1 AND NOT Installed', order=1)
ev("ExitDlg", "Finish", "EndDialog", "Return", order=2)
conditions += [
    ("ExitDlg", "TxtInstalled", "Show", "NOT Installed"),
    ("ExitDlg", "TxtRepaired", "Show", 'Installed AND NOT (REMOVE = "ALL")'),
    ("ExitDlg", "TxtRemoved", "Show", 'REMOVE = "ALL"'),
    ("ExitDlg", "Launch", "Hide", "Installed"),
]

# ---- Cancelled ----------------------------------------------------------------------------
dialog("UserExitDlg", f"{APP} Setup", "Finish", "Finish", "Finish")
page("UserExitDlg", "Setup was cancelled",
     f"{APP} was not installed or changed. Run setup again whenever you are ready.")
ctl("UserExitDlg", "Finish", "PushButton", 304, BTN_Y, BTN_W, BTN_H, BTN, text="&Finish", nxt="Finish")
ev("UserExitDlg", "Finish", "EndDialog", "Exit")

# ---- Failed -------------------------------------------------------------------------------
dialog("FatalErrorDlg", f"{APP} Setup", "Finish", "Finish", "Finish")
page("FatalErrorDlg", "Setup failed",
     f"{APP} could not be set up, and nothing was changed.\r\n\r\n"
     "To see why, run this in a Command Prompt, then look for \"Return value 3\" in install.log:\r\n\r\n"
     "msiexec /i \"[OriginalDatabase]\" /l*v \"%TEMP%\\install.log\"")
ctl("FatalErrorDlg", "Finish", "PushButton", 304, BTN_Y, BTN_W, BTN_H, BTN, text="&Finish", nxt="Finish")
ev("FatalErrorDlg", "Finish", "EndDialog", "Exit")

# ---- Cancel confirmation ------------------------------------------------------------------
dialog("CancelDlg", f"{APP} Setup", "No", "No", "No", w=260, h=85)
ctl("CancelDlg", "Text", "Text", 20, 15, 220, 30, TXT, text="Are you sure you want to cancel setup?")
ctl("CancelDlg", "Yes", "PushButton", 72, 57, 56, 17, BTN, text="&Yes", nxt="No")
ctl("CancelDlg", "No", "PushButton", 132, 57, 56, 17, BTN, text="&No", nxt="Yes")
ev("CancelDlg", "Yes", "EndDialog", "Exit")
ev("CancelDlg", "No", "EndDialog", "Return")

# ---- Error dialog for installer messages (ErrorDialog property) ---------------------------
# Windows Installer fills ErrorText and shows/positions only the buttons each message needs.
dialog("ErrorDlg", "[ProductName] Setup", "ErrorText", "O", "C", attrs=ERROR_DLG, w=270, h=105)
ctl("ErrorDlg", "ErrorText", "Text", 48, 15, 205, 60, VIS | EN | NOPREFIX, text="Information text")
ctl("ErrorDlg", "ErrorIcon", "Icon", 15, 15, 24, 24, 1 + 1048576 + 4194304, text="AppIconBin")
for b, label, result in (("Y", "&Yes", "ErrorYes"), ("A", "&Abort", "ErrorAbort"), ("C", "&Cancel", "ErrorCancel"),
                         ("I", "&Ignore", "ErrorIgnore"), ("N", "&No", "ErrorNo"), ("O", "&OK", "ErrorOk"),
                         ("R", "&Retry", "ErrorRetry")):
    ctl("ErrorDlg", b, "PushButton", 100, 80, 56, 17, BTN, text=label)
    ev("ErrorDlg", b, "EndDialog", result)


# ------------------------------------------------------------------------------- writer ---
def esc(v):
    # IDT encoding: tab separates columns; CR -> \x11, LF -> \x19.
    return str(v).replace("\r", "\x11").replace("\n", "\x19")


def write_idt(folder, name, cols, types, keys, rows):
    with open(os.path.join(folder, f"{name}.idt"), "w", encoding="cp1252", newline="\r\n") as f:
        f.write("\t".join(cols) + "\n" + "\t".join(types) + "\n" + "\t".join([name] + keys) + "\n")
        for r in rows:
            f.write("\t".join(esc(v) for v in r) + "\n")


def read_rows(msi, table):
    out = subprocess.run(["msiinfo", "export", msi, table], capture_output=True, check=True,
                         encoding="cp1252").stdout.replace("\r\n", "\n")
    lines = out.split("\n")
    return lines[0].split("\t"), lines[1].split("\t"), lines[2].split("\t")[1:], \
        [l.split("\t") for l in lines[3:] if l]


def main():
    msi, ico = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "Binary"))
        with open(ico, "rb") as src, open(os.path.join(d, "Binary", "AppIconBin.ico"), "wb") as dst:
            dst.write(src.read())

        write_idt(d, "Dialog", ["Dialog", "HCentering", "VCentering", "Width", "Height", "Attributes",
                                "Title", "Control_First", "Control_Default", "Control_Cancel"],
                  ["s72", "i2", "i2", "i2", "i2", "I4", "L128", "s50", "S50", "S50"], ["Dialog"], dialogs)
        write_idt(d, "Control", ["Dialog_", "Control", "Type", "X", "Y", "Width", "Height", "Attributes",
                                 "Property", "Text", "Control_Next", "Help"],
                  ["s72", "s50", "s20", "i2", "i2", "i2", "i2", "I4", "S72", "L0", "S50", "L50"],
                  ["Dialog_", "Control"], controls)
        write_idt(d, "ControlEvent", ["Dialog_", "Control_", "Event", "Argument", "Condition", "Ordering"],
                  ["s72", "s50", "s50", "s255", "S255", "I2"],
                  ["Dialog_", "Control_", "Event", "Argument", "Condition"], events)
        write_idt(d, "ControlCondition", ["Dialog_", "Control_", "Action", "Condition"],
                  ["s72", "s50", "s50", "s255"], ["Dialog_", "Control_", "Action", "Condition"], conditions)
        write_idt(d, "EventMapping", ["Dialog_", "Control_", "Event", "Attribute"],
                  ["s72", "s50", "s50", "s50"], ["Dialog_", "Control_", "Event"], mappings)
        write_idt(d, "TextStyle", ["TextStyle", "FaceName", "Size", "Color", "StyleBits"],
                  ["s72", "s32", "i2", "I4", "I2"], ["TextStyle"],
                  [("UIFontNormal", "Segoe UI", 9, "", ""), ("UIFontTitle", "Segoe UI", 13, "", 1)])
        write_idt(d, "CheckBox", ["Property", "Value"], ["s72", "S64"], ["Property"], [("LAUNCHAPP", "1")])
        write_idt(d, "Binary", ["Name", "Data"], ["s72", "v0"], ["Name"], [("AppIconBin", "AppIconBin.ico")])

        cols, types, keys, rows = read_rows(msi, "Property")
        have = {r[0] for r in rows}
        for k, v in (("DefaultUIFont", "UIFontNormal"), ("ErrorDialog", "ErrorDlg"), ("LAUNCHAPP", "1")):
            if k not in have:
                rows.append([k, v])
        write_idt(d, "Property", cols, types, keys, rows)

        cols, types, keys, rows = read_rows(msi, "InstallUISequence")
        rows += [["WelcomeDlg", "NOT Installed", "1297"],
                 ["MaintenanceDlg", "Installed AND NOT RESUME AND NOT Preselected", "1298"],
                 ["ProgressDlg", "", "1299"],
                 ["ExitDlg", "", "-1"], ["UserExitDlg", "", "-2"], ["FatalErrorDlg", "", "-3"]]
        write_idt(d, "InstallUISequence", cols, types, keys, rows)

        cols, types, keys, rows = read_rows(msi, "CustomAction")
        # Type 226 = 34 (run a command line, working dir = Directory) + 192 (async, don't wait).
        # It runs from the Finish button in the (non-elevated) UI process, so the program
        # starts as the user, not as administrator.
        rows.append(["LaunchApp", "226", "INSTALLDIR", '"[INSTALLDIR]ChatGPTExportConverter.exe"', ""])
        write_idt(d, "CustomAction", cols, types, keys, rows)

        tables = ["Binary", "TextStyle", "Dialog", "Control", "ControlEvent", "ControlCondition",
                  "EventMapping", "CheckBox", "Property", "InstallUISequence", "CustomAction"]
        cmd = ["msibuild", msi]
        for t in tables:
            cmd += ["-i", f"{t}.idt"]
        subprocess.run(cmd, check=True, cwd=d)
    print(f"added setup wizard: {len(dialogs)} dialogs, {len(controls)} controls")


if __name__ == "__main__":
    main()
