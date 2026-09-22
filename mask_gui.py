#!/usr/bin/env python3
"""A window for maskmaker.py: pick a PNG, get a Masks.xml next to it.

    python3 mask_gui.py        (or, on Windows, double-click Make Mask.bat)

One button and one line of feedback. Nothing to configure, and nothing to
build -- the conversion is maskmaker.py, which is pure standard library.
Proof of concept, so it takes the image on trust: pass it an 8-bit RGBA PNG
and it makes mask data.
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maskmaker  # noqa: E402

# AV Studio house tokens, dark.
BG, BORDER, TEXT, MUTED = "#1E1E2E", "#3A3A4E", "#E8E8F0", "#9A9AB0"
PRIMARY, ACCENT, OK, ERR = "#2C3E50", "#3498DB", "#27AE60", "#C0392B"
FONT = ("Segoe UI", 10) if sys.platform == "win32" else ("DejaVu Sans", 10)


class MaskGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PNG to Hippotizer Mask")
        self.configure(bg=BG)
        self.minsize(520, 230)
        self.last_folder = ""

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

        frame = ttk.Frame(self, padding=28)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Pick a PNG with a see-through background. A Masks.xml "
                              "is written into the same folder.",
                  style="Lead.TLabel", wraplength=440, justify="left").grid(
                      row=0, column=0, sticky="w")
        ttk.Button(frame, text="Choose a PNG…", style="Primary.TButton",
                   command=self.choose).grid(row=1, column=0, sticky="w", pady=(22, 20))
        self.status = ttk.Label(frame, text="", style="Muted.TLabel", wraplength=440,
                                justify="left")
        self.status.grid(row=2, column=0, sticky="w")

    def say(self, text, colour=MUTED):
        self.status.configure(text=text, foreground=colour)

    def choose(self):
        png = filedialog.askopenfilename(title="Choose a PNG",
                                         initialdir=self.last_folder or None,
                                         filetypes=[("PNG image", "*.png"),
                                                    ("All files", "*.*")])
        if not png:
            return
        self.last_folder = os.path.dirname(png)   # so the next one opens here
        self.say("Converting…")
        self.update_idletasks()       # repaint before the conversion blocks (about a second)

        try:
            result = maskmaker.convert(png)
        except Exception as exc:      # noqa: BLE001 - better shown than thrown
            self.say(f"Could not convert that image. {exc}", ERR)
            return

        shapes = result["shapes"]
        self.say(f"Written to {result['xml']}  -  {shapes} shape{'' if shapes == 1 else 's'} "
                 f"from {result['width']} x {result['height']}.", OK)


if __name__ == "__main__":
    MaskGui().mainloop()
