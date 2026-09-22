#!/usr/bin/env python3
"""mask_gui.py -- pick a PNG, get a Masks.xml next to it, pick another.

Nothing to build and nothing to install. The conversion is maskmaker.py,
which is pure standard library, so this runs on a show laptop with a bare
Python on it.

    python3 gui/mask_gui.py        (or, on Windows, double-click Make Mask.bat)

One button, one line of feedback, nothing to configure. The mask is whatever
is not see-through in the image; its colours are never read. The image is
taken at face value besides: whatever size it is, is the size the mask is
for. The C++ tools in tools/ still expose every knob, for when something
needs pinning down -- but they are the plugin, not this.
"""

import os
import sys

try:
    import tkinter as tk
    from tkinter import filedialog, ttk
except ImportError:                                       # pragma: no cover - platform dependent
    sys.exit("This window needs tkinter, which is not installed.\n"
             "  Windows/macOS:  it ships with python.org and Windows Python\n"
             "  Debian/Ubuntu:  sudo apt install python3-tk\n"
             "Or convert from a shell instead:  python3 gui/maskmaker.py image.png")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maskmaker  # noqa: E402

# AV Studio house tokens, dark.
BG, BORDER, TEXT, MUTED = "#1E1E2E", "#3A3A4E", "#E8E8F0", "#9A9AB0"
PRIMARY, ACCENT, OK, WARN, ERR = "#2C3E50", "#3498DB", "#27AE60", "#F39C12", "#C0392B"
FONT = ("Segoe UI", 10) if sys.platform == "win32" else ("DejaVu Sans", 10)


class MaskGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PNG to Hippotizer Mask")
        self.configure(bg=BG)
        self.minsize(520, 230)
        self.last_folder = ""
        self._style()

        frame = ttk.Frame(self, padding=28)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Pick a PNG with a see-through background. A Masks.xml "
                               "is written into the same folder.",
                  style="Lead.TLabel", wraplength=440, justify="left").grid(
                      row=0, column=0, sticky="w")
        self.button = ttk.Button(frame, text="Choose a PNG…", style="Primary.TButton",
                                 command=self.choose)
        self.button.grid(row=1, column=0, sticky="w", pady=(22, 20))
        self.status = ttk.Label(frame, text="", style="Muted.TLabel", wraplength=440,
                                justify="left")
        self.status.grid(row=2, column=0, sticky="w")

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
                                         initialdir=self.last_folder or None,
                                         filetypes=[("PNG image", "*.png"),
                                                    ("All files", "*.*")])
        if not png:
            return
        self.last_folder = os.path.dirname(png)   # so the next one opens where this one was
        self.say("Converting…")
        self.update_idletasks()       # repaint before the conversion blocks (well under a second)
        try:
            result = maskmaker.convert(png)
        except maskmaker.MaskError as exc:
            self.say(str(exc), ERR)
            return
        except Exception as exc:                          # noqa: BLE001 - shown to the user
            self.say("Could not convert that image. %s" % exc, ERR)
            return

        if not result["shapes"]:
            self.say("Nothing in that image was solid enough to trace -- it is "
                     "see-through all over.", WARN)
            return
        note = "" if not result["backup"] else "  The mask that was there is kept as %s." % \
            os.path.basename(result["backup"])
        self.say("Written to %s  -  %d shape%s from %d x %d.%s"
                 % (result["xml"], result["shapes"], "" if result["shapes"] == 1 else "s",
                    result["width"], result["height"], note), OK)


if __name__ == "__main__":
    MaskGui().mainloop()
