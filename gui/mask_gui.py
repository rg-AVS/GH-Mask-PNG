#!/usr/bin/env python3
"""mask_gui.py -- pick a PNG, get a Masks.xml next to it. That is the whole app.

One button, one line of feedback, nothing to configure. The image is taken at
face value: whatever size it is, is the size the mask is for. The tools in
build/ still expose every knob for when something needs pinning down.

    python3 gui/mask_gui.py        (or)   make gui

Needs tkinter, which ships with python.org and Windows Python. On Debian or
Ubuntu it is a separate package: apt install python3-tk.
"""

import os
import sys

try:
    import tkinter as tk
    from tkinter import filedialog, ttk
except ImportError:                                       # pragma: no cover - platform dependent
    sys.exit("This window needs tkinter, which is not installed.\n"
             "  Debian/Ubuntu:  sudo apt install python3-tk\n"
             "  Windows/macOS:  it ships with python.org and Windows Python\n"
             "The command-line tools in build/ work without it.")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backend  # noqa: E402

# AV Studio house tokens, dark.
BG, PANEL, BORDER, TEXT, MUTED = "#1E1E2E", "#2A2A3C", "#3A3A4E", "#E8E8F0", "#9A9AB0"
PRIMARY, ACCENT, OK, WARN, ERR = "#2C3E50", "#3498DB", "#27AE60", "#F39C12", "#C0392B"
FONT = ("Segoe UI", 10) if sys.platform == "win32" else ("DejaVu Sans", 10)


class MaskGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PNG to Hippotizer Mask")
        self.configure(bg=BG)
        self.minsize(520, 240)
        self._style()

        frame = ttk.Frame(self, padding=28)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Pick a PNG. A Masks.xml is written into the same folder.",
                  style="Lead.TLabel", wraplength=440, justify="left").grid(
                      row=0, column=0, sticky="w")
        self.button = ttk.Button(frame, text="Choose a PNG…", style="Primary.TButton",
                                 command=self.choose)
        self.button.grid(row=1, column=0, sticky="w", pady=(22, 20))
        self.status = ttk.Label(frame, text="", style="Muted.TLabel", wraplength=440,
                                justify="left")
        self.status.grid(row=2, column=0, sticky="w")

        if not backend.is_built():
            self.say("The tools are not built yet. Run 'make' in %s, then reopen this window."
                     % backend.REPO_ROOT, ERR)
            self.button.state(["disabled"])

    def _style(self):
        style = ttk.Style(self)
        style.theme_use("clam")       # the only built-in theme that takes colours
        style.configure(".", background=BG, foreground=TEXT, bordercolor=BORDER, font=FONT)
        style.configure("TFrame", background=BG)
        style.configure("Lead.TLabel", background=BG, foreground=TEXT, font=(FONT[0], 12))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("Primary.TButton", background=PRIMARY, foreground=TEXT,
                        bordercolor=BORDER, focuscolor=ACCENT, relief="flat",
                        padding=(20, 12), font=(FONT[0], 11))
        style.map("Primary.TButton", background=[("active", ACCENT), ("pressed", PRIMARY)])

    def say(self, text, colour=MUTED):
        self.status.configure(text=text, foreground=colour)

    def choose(self):
        png = filedialog.askopenfilename(title="Choose a PNG",
                                         filetypes=[("PNG image", "*.png"),
                                                    ("All files", "*.*")])
        if not png:
            return
        self.say("Converting…")
        self.update_idletasks()       # repaint before the conversion blocks (~0.2s)
        try:
            result = backend.convert_beside(png)
        except Exception as exc:                          # noqa: BLE001 - shown to the user
            self.say("Could not convert that image. %s" % exc, ERR)
            return

        if not result["shapes"]:
            self.say("Nothing in that image was bright enough to trace. If the shape is "
                     "dark on a light background, invert it and try again.", WARN)
            return
        note = "" if not result["backup"] else "  The mask that was there is kept as %s." % \
            os.path.basename(result["backup"])
        self.say("Written to %s  -  %d shape%s from %d x %d.%s"
                 % (result["xml"], result["shapes"], "" if result["shapes"] == 1 else "s",
                    result["width"], result["height"], note), OK)


if __name__ == "__main__":
    MaskGui().mainloop()
