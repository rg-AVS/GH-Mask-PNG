#!/usr/bin/env python3
"""mask_gui.py -- pick a PNG, get a Masks.xml next to it. That is the whole app.

There is nothing to configure on purpose. The image is taken at face value:
whatever size it is, is the size the mask is for, and one mask unit is one
pixel at that size. The command-line tools in build/ still expose every knob
(other mappings, threshold, smoothing) for when something needs pinning down
-- this window is for the normal case.

    python3 gui/mask_gui.py        (or)   make gui

Needs tkinter, which ships with python.org and Windows Python. On Debian or
Ubuntu it is a separate package: apt install python3-tk.
"""

import os
import queue
import sys
import tempfile
import threading

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:                                       # pragma: no cover - platform dependent
    sys.exit("This window needs tkinter, which is not installed.\n"
             "  Debian/Ubuntu:  sudo apt install python3-tk\n"
             "  Windows/macOS:  it ships with python.org and Windows Python\n"
             "The command-line tools in build/ work without it.")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backend  # noqa: E402

# AV Studio house tokens, dark.
BG, BG_ALT, PANEL, BORDER = "#1E1E2E", "#252535", "#2A2A3C", "#3A3A4E"
TEXT, MUTED = "#E8E8F0", "#9A9AB0"
PRIMARY, ACCENT = "#2C3E50", "#3498DB"
OK, WARN, ERR = "#27AE60", "#F39C12", "#C0392B"

FONT = ("Segoe UI", 10) if sys.platform == "win32" else ("DejaVu Sans", 10)
MONO = ("Consolas", 9) if sys.platform == "win32" else ("DejaVu Sans Mono", 9)


class MaskGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PNG to Hippotizer Mask")
        self.configure(bg=BG)
        self.minsize(620, 520)

        self.preview_dir = tempfile.mkdtemp(prefix="maskgui-")
        self.messages = queue.Queue()
        self._preview_ref = None      # Tk drops an image that nothing references
        self.busy = False

        self._build_style()
        self._build_layout()
        self.after(100, self._drain)
        self._check_tools()

    # --- appearance --------------------------------------------------------

    def _build_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")       # the only built-in theme that takes colours
        style.configure(".", background=BG, foreground=TEXT, bordercolor=BORDER, font=FONT)
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("Heading.TLabel", background=BG, foreground=TEXT,
                        font=(FONT[0], 15, "bold"))
        style.configure("TButton", background=PANEL, foreground=TEXT, bordercolor=BORDER,
                        focuscolor=ACCENT, padding=(14, 8), relief="flat")
        style.map("TButton", background=[("active", BORDER), ("pressed", PRIMARY)])
        style.configure("Primary.TButton", background=PRIMARY, foreground=TEXT,
                        padding=(18, 10), font=(FONT[0], 11))
        style.map("Primary.TButton", background=[("active", ACCENT), ("pressed", PRIMARY)])

    # --- layout ------------------------------------------------------------

    def _build_layout(self):
        outer = ttk.Frame(self, padding=20)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(4, weight=1)

        ttk.Label(outer, text="PNG to Hippotizer mask",
                  style="Heading.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(outer, style="Muted.TLabel", wraplength=560, justify="left",
                  text="Pick an image. Its bright areas become the mask, and a Masks.xml "
                       "is written into the same folder as the image.").grid(
                           row=1, column=0, sticky="w", pady=(6, 0))

        self.button = ttk.Button(outer, text="Choose a PNG…", style="Primary.TButton",
                                 command=self._choose)
        self.button.grid(row=2, column=0, sticky="w", pady=(18, 0))

        self.status = ttk.Label(outer, text="", style="Muted.TLabel", wraplength=560,
                                justify="left")
        self.status.grid(row=3, column=0, sticky="ew", pady=(16, 12))

        panel = tk.Frame(outer, bg=BG_ALT, highlightthickness=1, highlightbackground=BORDER)
        panel.grid(row=4, column=0, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)

        self.details = tk.Label(panel, bg=BG_ALT, fg=TEXT, font=MONO, justify="left",
                                anchor="w", padx=14, pady=12, text="")
        self.details.grid(row=0, column=0, sticky="ew")

        self.preview = tk.Label(panel, bg=BG_ALT, fg=MUTED, font=FONT,
                                text="Nothing converted yet.")
        self.preview.grid(row=1, column=0, sticky="nsew", pady=(0, 12))

    # --- running work off the UI thread ------------------------------------

    def _check_tools(self):
        missing = backend.missing_tools()
        if missing:
            self._say("The tools are not built yet. Run 'make' in %s, then reopen this window."
                      % backend.REPO_ROOT, ERR)
            self.button.state(["disabled"])
        else:
            self._say("Ready.", MUTED)

    def _say(self, text, colour=MUTED):
        self.status.configure(text=text, foreground=colour)

    def _choose(self):
        if self.busy:
            return
        png = filedialog.askopenfilename(title="Choose a PNG",
                                         filetypes=[("PNG image", "*.png"),
                                                    ("All files", "*.*")])
        if not png:
            return

        # Overwriting someone's existing mask file is the one thing here worth
        # stopping for, so it is the one thing that gets a dialog.
        existing = backend.mask_path_for(png)
        if os.path.exists(existing):
            if not messagebox.askyesno(
                    "Replace the existing mask?",
                    "There is already a Masks.xml in that folder:\n\n%s\n\n"
                    "Replace it with a mask made from this image?" % existing):
                self._say("Left the existing mask alone.", MUTED)
                return

        self.busy = True
        self.button.state(["disabled"])
        self._say("Converting %s…" % os.path.basename(png), MUTED)

        def work():
            try:
                self.messages.put(("done", backend.convert_beside(
                    png, preview_dir=self.preview_dir)))
            except Exception as exc:                      # noqa: BLE001 - shown to the user
                self.messages.put(("error", exc))

        threading.Thread(target=work, daemon=True).start()

    def _drain(self):
        while True:
            try:
                kind, payload = self.messages.get_nowait()
            except queue.Empty:
                break
            self.busy = False
            self.button.state(["!disabled"])
            if kind == "error":
                self._say("Could not convert that image. %s" % payload, ERR)
                self.details.configure(text="")
                self._clear_preview("Nothing converted.")
            else:
                self._report(payload)
        self.after(100, self._drain)

    def _report(self, result):
        if not result["shapes"]:
            self._say("Nothing in that image was bright enough to trace. If the shape is "
                      "dark on a light background, invert it and try again.", WARN)
        else:
            self._say("Done. Masks.xml written next to the image.", OK)

        self.details.configure(text="\n".join((
            "Image     %s" % os.path.basename(result["png"]),
            "Size      %d x %d" % (result["width"], result["height"]),
            "Traced    %d shape%s, %d point%s" % (result["shapes"],
                                                   "" if result["shapes"] == 1 else "s",
                                                   result["nodes"],
                                                   "" if result["nodes"] == 1 else "s"),
            "Written   %s" % result["xml"],
        )))

        if result.get("preview"):
            self._show_preview(result["preview"])
        else:
            self._clear_preview("No preview available.")

    # --- preview -----------------------------------------------------------

    def _show_preview(self, path):
        """Tk 8.6 reads PNG natively, so no image library is needed. A preview
        is a convenience, never the result -- any failure here is ignored."""
        try:
            image = tk.PhotoImage(file=path)
            step = max(1, -(-image.width() // 420), -(-image.height() // 280))
            if step > 1:
                image = image.subsample(step, step)
            self._preview_ref = image
            self.preview.configure(image=image, text="")
        except Exception:                                 # noqa: BLE001 - preview is optional
            self._clear_preview("No preview available.")

    def _clear_preview(self, text):
        self._preview_ref = None
        self.preview.configure(image="", text=text)


def main():
    MaskGui().mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
