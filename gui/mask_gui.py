#!/usr/bin/env python3
"""mask_gui.py -- a small operator window for the mask tools.

Deliberately thin. Everything it does is in backend.py, which is plain
stdlib and covered by tests/test_backend.py; this file is layout, wiring and
a preview pane. Nothing here reimplements a conversion -- every button shells
out to the same binary you would run by hand, so the window and a build
script cannot disagree.

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
    from tkinter import filedialog, ttk
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
STATUS = {"ok": OK, "warn": WARN, "err": ERR, "muted": MUTED}

FONT = ("Segoe UI", 10) if sys.platform == "win32" else ("DejaVu Sans", 10)
MONO = ("Consolas", 9) if sys.platform == "win32" else ("DejaVu Sans Mono", 9)


class MaskGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hippotizer Mask Tools")
        self.configure(bg=BG)
        self.minsize(900, 640)

        self.work_dir = tempfile.mkdtemp(prefix="maskgui-")
        self.messages = queue.Queue()
        self._preview_ref = None      # Tk drops an image that nothing references

        self._build_style()
        self._build_layout()
        self.after(100, self._drain)
        self._check_tools()

    # --- appearance --------------------------------------------------------

    def _build_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")       # the only built-in theme that takes colours
        style.configure(".", background=BG, foreground=TEXT, fieldbackground=BG,
                        bordercolor=BORDER, font=FONT)
        style.configure("TFrame", background=BG)
        style.configure("TLabelframe", background=BG, bordercolor=BORDER, relief="solid",
                        borderwidth=1)
        style.configure("TLabelframe.Label", background=BG, foreground=TEXT, font=FONT + ("bold",))
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Heading.TLabel", font=(FONT[0], 13, "bold"))
        style.configure("TButton", background=PANEL, foreground=TEXT, bordercolor=BORDER,
                        focuscolor=ACCENT, padding=(12, 6), relief="flat")
        style.map("TButton", background=[("active", BORDER), ("pressed", PRIMARY)])
        style.configure("Primary.TButton", background=PRIMARY, foreground=TEXT)
        style.map("Primary.TButton", background=[("active", ACCENT), ("pressed", PRIMARY)])
        style.configure("TEntry", fieldbackground=BG_ALT, foreground=TEXT, bordercolor=BORDER,
                        insertcolor=TEXT, padding=4)
        style.configure("TCombobox", fieldbackground=BG_ALT, background=PANEL, foreground=TEXT,
                        arrowcolor=TEXT, bordercolor=BORDER, padding=4)
        style.map("TCombobox", fieldbackground=[("readonly", BG_ALT)],
                  foreground=[("readonly", TEXT)])
        style.configure("TCheckbutton", background=BG, foreground=TEXT, focuscolor=ACCENT)
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("TNotebook", background=BG, bordercolor=BORDER, tabmargins=(0, 4, 0, 0))
        style.configure("TNotebook.Tab", background=BG_ALT, foreground=MUTED, padding=(14, 8),
                        bordercolor=BORDER)
        style.map("TNotebook.Tab", background=[("selected", PANEL)], foreground=[("selected", TEXT)])
        style.configure("TScale", background=BG, troughcolor=BG_ALT)
        self.option_add("*TCombobox*Listbox.background", BG_ALT)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)

    # --- layout ------------------------------------------------------------

    def _build_layout(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=3, minsize=470)
        outer.columnconfigure(1, weight=2, minsize=320)
        outer.rowconfigure(0, weight=1)

        left = ttk.Frame(outer)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        tabs = ttk.Notebook(left)
        tabs.grid(row=0, column=0, sticky="new")
        tabs.add(self._tab_png_to_mask(tabs), text="  PNG to mask  ")
        tabs.add(self._tab_mask_to_png(tabs), text="  Mask to PNG  ")
        tabs.add(self._tab_compare(tabs), text="  Compare  ")
        tabs.add(self._tab_testset(tabs), text="  Test set  ")

        self.status = ttk.Label(left, text="Ready.", style="Muted.TLabel", wraplength=470,
                                justify="left")
        self.status.grid(row=1, column=0, sticky="new", pady=(12, 6))

        log_frame = ttk.LabelFrame(left, text="Output", padding=8)
        log_frame.grid(row=2, column=0, sticky="nsew")
        left.rowconfigure(2, weight=1)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log = tk.Text(log_frame, height=10, bg=BG_ALT, fg=TEXT, font=MONO,
                           relief="flat", wrap="word", insertbackground=TEXT,
                           highlightthickness=1, highlightbackground=BORDER)
        self.log.grid(row=0, column=0, sticky="nsew")
        bar = ttk.Scrollbar(log_frame, command=self.log.yview)
        bar.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=bar.set, state="disabled")
        for tag, colour in STATUS.items():
            self.log.tag_configure(tag, foreground=colour)

        right = ttk.LabelFrame(outer, text="Preview", padding=8)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.preview = tk.Label(right, bg=BG_ALT, text="Nothing rendered yet.", fg=MUTED,
                                font=FONT)
        self.preview.grid(row=0, column=0, sticky="nsew")
        self.preview_caption = ttk.Label(right, text="", style="Muted.TLabel", wraplength=300,
                                         justify="left")
        self.preview_caption.grid(row=1, column=0, sticky="ew", pady=(8, 0))

    # --- reusable rows -----------------------------------------------------

    def _file_row(self, parent, row, label, var, save=False, folder=False, types=None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        entry = ttk.Entry(parent, textvariable=var)
        entry.grid(row=row, column=1, sticky="ew", padx=8, pady=4)

        def browse():
            if folder:
                path = filedialog.askdirectory(title=label)
            elif save:
                path = filedialog.asksaveasfilename(title=label, defaultextension=".xml",
                                                    filetypes=types or [("XML", "*.xml")])
            else:
                path = filedialog.askopenfilename(title=label, filetypes=types or
                                                  [("PNG image", "*.png"), ("All files", "*.*")])
            if path:
                var.set(path)

        ttk.Button(parent, text="Browse", command=browse).grid(row=row, column=2, pady=4)
        parent.columnconfigure(1, weight=1)
        return entry

    def _mapping_row(self, parent, row, var):
        ttk.Label(parent, text="Coordinate mapping").grid(row=row, column=0, sticky="w", pady=4)
        box = ttk.Combobox(parent, textvariable=var, values=list(backend.MAPPINGS),
                           state="readonly")
        box.grid(row=row, column=1, sticky="ew", padx=8, pady=4)
        hint = ttk.Label(parent, style="Muted.TLabel", wraplength=430, justify="left",
                         text=backend.MAPPING_HELP[var.get()])
        hint.grid(row=row + 1, column=1, columnspan=2, sticky="w", padx=8)
        box.bind("<<ComboboxSelected>>",
                 lambda _e: hint.configure(text=backend.MAPPING_HELP[var.get()]))
        return box

    # --- tabs --------------------------------------------------------------

    def _tab_png_to_mask(self, parent):
        f = ttk.Frame(parent, padding=14)
        self.p2m_png = tk.StringVar()
        self.p2m_xml = tk.StringVar()
        self.p2m_map = tk.StringVar(value="native")
        self.p2m_threshold = tk.IntVar(value=128)
        self.p2m_simplify = tk.DoubleVar(value=1.0)
        self.p2m_invert_in = tk.BooleanVar()
        self.p2m_invert_mask = tk.BooleanVar()

        self._file_row(f, 0, "Image to trace", self.p2m_png)
        self._file_row(f, 1, "Save mask file as", self.p2m_xml, save=True)
        self._mapping_row(f, 2, self.p2m_map)

        ttk.Label(f, text="Edge threshold (0-255)").grid(row=4, column=0, sticky="w", pady=4)
        thr = ttk.Frame(f)
        thr.grid(row=4, column=1, columnspan=2, sticky="ew", padx=8)
        # Typeable as well as draggable -- a slider alone makes an exact value
        # (128) fiddly to hit, and this is a number people want to set exactly.
        ttk.Entry(thr, textvariable=self.p2m_threshold, width=6).pack(side="left")
        ttk.Scale(thr, from_=0, to=255, variable=self.p2m_threshold,
                  command=lambda v: self.p2m_threshold.set(int(float(v)))).pack(
                      side="left", fill="x", expand=True, padx=8)
        ttk.Label(f, text="Anything brighter than this becomes part of the mask.",
                  style="Muted.TLabel").grid(row=5, column=1, columnspan=2, sticky="w", padx=8)

        ttk.Label(f, text="Corner smoothing").grid(row=6, column=0, sticky="w", pady=4)
        ttk.Entry(f, textvariable=self.p2m_simplify, width=8).grid(row=6, column=1, sticky="w",
                                                                    padx=8, pady=4)
        ttk.Label(f, text="How far, in pixels, a traced edge may be straightened. "
                          "0 keeps every step exactly.",
                  style="Muted.TLabel", wraplength=430, justify="left").grid(
                      row=7, column=1, columnspan=2, sticky="w", padx=8)

        ttk.Checkbutton(f, text="Trace the dark areas instead of the bright ones",
                        variable=self.p2m_invert_in).grid(row=8, column=1, columnspan=2,
                                                          sticky="w", padx=8, pady=(10, 0))
        ttk.Checkbutton(f, text="Mark the mask inverted (cuts the shape out rather than keeping it)",
                        variable=self.p2m_invert_mask).grid(row=9, column=1, columnspan=2,
                                                            sticky="w", padx=8)

        buttons = ttk.Frame(f)
        buttons.grid(row=10, column=0, columnspan=3, sticky="ew", pady=(16, 0))
        ttk.Button(buttons, text="Convert to mask", style="Primary.TButton",
                   command=self._do_png_to_mask).pack(side="left")
        ttk.Button(buttons, text="Convert and check it cancels",
                   command=self._do_round_trip).pack(side="left", padx=8)
        return f

    def _tab_mask_to_png(self, parent):
        f = ttk.Frame(parent, padding=14)
        self.m2p_xml = tk.StringVar()
        self.m2p_dir = tk.StringVar()
        self.m2p_map = tk.StringVar(value="native")
        self.m2p_res = tk.StringVar(value="1920x1080")
        self.m2p_index = tk.StringVar()

        self._file_row(f, 0, "Mask file", self.m2p_xml, types=[("Masks.xml", "*.xml")])
        self._file_row(f, 1, "Save images into", self.m2p_dir, folder=True)
        self._mapping_row(f, 2, self.m2p_map)

        ttk.Label(f, text="Output size").grid(row=4, column=0, sticky="w", pady=4)
        res = ttk.Combobox(f, textvariable=self.m2p_res,
                           values=["1920x1080", "3840x1080", "3840x2160", "1024x768", "2560x1600"])
        res.grid(row=4, column=1, sticky="ew", padx=8, pady=4)
        ttk.Label(f, text="The size the mask will be used at. The file itself always says "
                          "1024x768, whatever it was drawn against.",
                  style="Muted.TLabel", wraplength=430, justify="left").grid(
                      row=5, column=1, columnspan=2, sticky="w", padx=8)

        ttk.Label(f, text="Only this mask number").grid(row=6, column=0, sticky="w", pady=4)
        ttk.Entry(f, textvariable=self.m2p_index, width=8).grid(row=6, column=1, sticky="w",
                                                                 padx=8, pady=4)
        ttk.Label(f, text="Leave empty to render every mask in the file.",
                  style="Muted.TLabel").grid(row=7, column=1, columnspan=2, sticky="w", padx=8)

        buttons = ttk.Frame(f)
        buttons.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(16, 0))
        ttk.Button(buttons, text="Render to PNG", style="Primary.TButton",
                   command=self._do_mask_to_png).pack(side="left")
        ttk.Button(buttons, text="Where do the shapes land?",
                   command=self._do_bounds).pack(side="left", padx=8)
        return f

    def _tab_compare(self, parent):
        f = ttk.Frame(parent, padding=14)
        self.cmp_a = tk.StringVar()
        self.cmp_b = tk.StringVar()
        self._file_row(f, 0, "First image", self.cmp_a)
        self._file_row(f, 1, "Second image", self.cmp_b)
        ttk.Label(f, text="Compares the two pixel for pixel and says whether they cancel. "
                          "Use it on an original and the mask rendered back from it.",
                  style="Muted.TLabel", wraplength=430, justify="left").grid(
                      row=2, column=1, columnspan=2, sticky="w", padx=8, pady=(4, 0))
        ttk.Button(f, text="Compare", style="Primary.TButton",
                   command=self._do_compare).grid(row=3, column=0, columnspan=3, sticky="w",
                                                   pady=(16, 0))
        return f

    def _tab_testset(self, parent):
        f = ttk.Frame(parent, padding=14)
        self.ts_dir = tk.StringVar(value=backend.default_testset_dir())
        self.ts_invert = tk.BooleanVar()
        self._file_row(f, 0, "Write the test set into", self.ts_dir, folder=True)
        ttk.Checkbutton(f, text="Mark every mask inverted",
                        variable=self.ts_invert).grid(row=1, column=1, columnspan=2, sticky="w",
                                                      padx=8, pady=(8, 0))
        ttk.Label(f, text="Writes nine images and one Masks.xml: the same shape at 1920x1080, "
                          "3840x1080 and 1024x768, each under all three candidate mappings. "
                          "Load a pair into Hippotizer and see which one lines up - that is "
                          "the mapping it really uses.",
                  style="Muted.TLabel", wraplength=430, justify="left").grid(
                      row=2, column=1, columnspan=2, sticky="w", padx=8, pady=(10, 0))
        buttons = ttk.Frame(f)
        buttons.grid(row=3, column=0, columnspan=3, sticky="w", pady=(16, 0))
        ttk.Button(buttons, text="Generate test set", style="Primary.TButton",
                   command=self._do_testset).pack(side="left")
        ttk.Button(buttons, text="Check it cancels here first",
                   command=self._do_check_testset).pack(side="left", padx=8)
        return f

    # --- running work off the UI thread ------------------------------------

    def _check_tools(self):
        missing = backend.missing_tools()
        if missing:
            self._say("The tools are not built yet: %s. Run 'make' in %s, then reopen this window."
                      % (", ".join(missing), backend.REPO_ROOT), "err")
        else:
            self._say("Ready. Start with the test set tab if you are chasing the "
                      "coordinate mapping.", "muted")

    def _say(self, text, level="muted"):
        self.status.configure(text=text, foreground=STATUS.get(level, MUTED))

    def _write(self, text, level=None):
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip() + "\n", level or ())
        self.log.see("end")
        self.log.configure(state="disabled")

    def _task(self, label, fn):
        """Runs fn on a worker thread so the window keeps repainting. Results
        come back through a queue -- Tk is not safe to touch from a thread."""
        self._say("%s..." % label, "muted")

        def work():
            try:
                self.messages.put(("done", label, fn()))
            except Exception as exc:                      # noqa: BLE001 - shown to the user
                self.messages.put(("error", label, exc))

        threading.Thread(target=work, daemon=True).start()

    def _drain(self):
        while True:
            try:
                kind, label, payload = self.messages.get_nowait()
            except queue.Empty:
                break
            if kind == "error":
                self._say("%s failed. %s" % (label, payload), "err")
                self._write(str(payload), "err")
            else:
                self._handle(label, payload)
        self.after(100, self._drain)

    def _handle(self, label, payload):
        if isinstance(payload, dict):
            message, level = backend.verdict(payload)
            self._say(message, level)
            self._write(payload.get("log", "") or payload.get("raw", ""))
            self._write(payload.get("raw", ""), level)
            if payload.get("render"):
                self._show_preview(payload["render"], "Rendered back from the mask.")
            source = payload.get("source_vs_render")
            if source:
                text, _ = backend.verdict(source)
                self._write("Against the original image: " + text)
            return
        self._say("%s finished." % label, "ok")
        self._write(str(payload))

    # --- button handlers ---------------------------------------------------

    def _need(self, **fields):
        for label, value in fields.items():
            if not value:
                self._say("Fill in %s first." % label, "warn")
                return False
        return True

    def _do_png_to_mask(self):
        png, xml = self.p2m_png.get(), self.p2m_xml.get()
        if not self._need(**{"the image to trace": png, "where to save the mask": xml}):
            return
        self._task("Converting", lambda: backend.png_to_mask(
            png, xml, self.p2m_map.get(), self.p2m_threshold.get(), self.p2m_simplify.get(),
            self.p2m_invert_in.get(), self.p2m_invert_mask.get()))

    def _do_round_trip(self):
        png = self.p2m_png.get()
        if not self._need(**{"the image to trace": png}):
            return
        self._task("Checking the round trip", lambda: backend.round_trip(
            png, self.work_dir, self.p2m_map.get(), self.p2m_threshold.get()))

    def _do_mask_to_png(self):
        xml, out = self.m2p_xml.get(), self.m2p_dir.get()
        if not self._need(**{"the mask file": xml, "where to save the images": out}):
            return
        try:
            width, height = (int(v) for v in self.m2p_res.get().lower().split("x"))
        except ValueError:
            self._say("Output size should look like 1920x1080.", "warn")
            return

        def work():
            text = backend.mask_to_png(xml, out, width, height, self.m2p_map.get(),
                                       self.m2p_index.get().strip() or None)
            first = next((line.split("  ")[0][6:] for line in text.splitlines()
                          if line.startswith("wrote ")), None)
            if first:
                self.after(0, lambda: self._show_preview(first, "%dx%d, %s mapping"
                                                         % (width, height, self.m2p_map.get())))
            return text

        self._task("Rendering", work)

    def _do_bounds(self):
        xml = self.m2p_xml.get()
        if not self._need(**{"the mask file": xml}):
            return
        try:
            width, height = (int(v) for v in self.m2p_res.get().lower().split("x"))
        except ValueError:
            width = height = None
        self._task("Reading bounds", lambda: backend.bounds(xml, width, height))

    def _do_compare(self):
        a, b = self.cmp_a.get(), self.cmp_b.get()
        if not self._need(**{"the first image": a, "the second image": b}):
            return
        diff = os.path.join(self.work_dir, "difference.png")

        def work():
            result = backend.compare(a, b, diff_out=diff)
            result["render"] = diff
            return result

        self._task("Comparing", work)

    def _do_testset(self):
        out = self.ts_dir.get()
        if not self._need(**{"a folder to write into": out}):
            return
        self._task("Generating the test set",
                   lambda: backend.generate_testset(out, self.ts_invert.get()))

    def _do_check_testset(self):
        out = self.ts_dir.get()
        if not self._need(**{"a folder to check": out}):
            return

        def work():
            lines = []
            for name in sorted(n for n in os.listdir(out) if n.endswith(".png")):
                stem = name[:-4]
                try:
                    index, res, mapping = stem.split("_")
                    width, height = (int(v) for v in res.split("x"))
                except ValueError:
                    continue
                dest = os.path.join(self.work_dir, "check", stem)
                os.makedirs(dest, exist_ok=True)
                backend.mask_to_png(os.path.join(out, "Masks.xml"), dest, width, height,
                                    mapping, str(int(index)))
                result = backend.compare(os.path.join(out, name), os.path.join(dest, name))
                lines.append("%-4s %-28s %s" % ("OK" if result["match"] else "FAIL", stem,
                                                 result["raw"].splitlines()[0]))
            return "\n".join(lines) or "No test-set images found in that folder."

        self._task("Checking the test set", work)

    # --- preview -----------------------------------------------------------

    def _show_preview(self, path, caption=""):
        """Tk 8.6 reads PNG natively, so no image library is needed. A preview
        is a convenience, never the result -- any failure here is reported and
        otherwise ignored."""
        try:
            image = tk.PhotoImage(file=path)
            step = max(1, -(-max(image.width(), 1) // 300), -(-max(image.height(), 1) // 300))
            if step > 1:
                image = image.subsample(step, step)
            self._preview_ref = image
            self.preview.configure(image=image, text="")
            self.preview_caption.configure(text="%s\n%s" % (os.path.basename(path), caption))
        except Exception as exc:                          # noqa: BLE001 - preview is optional
            self.preview.configure(image="", text="No preview available.")
            self.preview_caption.configure(text=str(exc))


def main():
    MaskGui().mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
