"""faketk.py -- a stand-in for tkinter, so mask_gui.py can be exercised on a
machine with no display (and no python3-tk, as on a bare build container).

It is not a Tk emulator. Widgets record their options and do nothing else.
What it does prove is the half of the window code that is ordinary
programming: that every widget is constructed with options it accepts, that
the variables the handlers read are the ones the fields write, that a button
with no input says so instead of raising, and that a real conversion is
reached and its result routed to the right place.

Anything that depends on Tk actually drawing -- fonts, geometry, whether the
preview image renders -- is not covered and cannot be, so the drawing code is
kept trivial and defensive.
"""

import sys
import types

CREATED = []          # every widget made, for the tests to inspect
SCHEDULED = []        # (delay_ms, callback) from after()


class _Var:
    def __init__(self, master=None, value=None, name=None):
        self._value = value if value is not None else self._default
    def get(self):
        return self._value
    def set(self, value):
        self._value = value


class StringVar(_Var):
    _default = ""


class IntVar(_Var):
    _default = 0


class DoubleVar(_Var):
    _default = 0.0


class BooleanVar(_Var):
    _default = False


class Widget:
    def __init__(self, master=None, **kw):
        self.master = master
        self.options = dict(kw)
        self.children = []
        self.bindings = {}
        CREATED.append(self)
        if isinstance(master, Widget):
            master.children.append(self)

    # Geometry and configuration are recorded, never acted on.
    def grid(self, **kw): self.options.update(kw)
    def pack(self, **kw): self.options.update(kw)
    def grid_configure(self, **kw): self.options.update(kw)
    def columnconfigure(self, *a, **kw): pass
    def rowconfigure(self, *a, **kw): pass
    def configure(self, **kw): self.options.update(kw)
    config = configure
    def cget(self, key): return self.options.get(key)
    def bind(self, sequence, func, add=None): self.bindings[sequence] = func
    def insert(self, *a, **kw): pass
    def see(self, *a, **kw): pass
    def tag_configure(self, *a, **kw): pass
    def yview(self, *a, **kw): pass
    def xview(self, *a, **kw): pass
    def set(self, *a, **kw): pass
    def get(self, *a, **kw): return ""
    def delete(self, *a, **kw): pass
    def focus_set(self): pass
    def winfo_children(self): return list(self.children)
    def state(self, statespec=None):
        """ttk's enable/disable. Recorded so tests can check the button is
        greyed out while a conversion is running."""
        if statespec is None:
            return tuple(self.options.get("_state", ()))
        current = set(self.options.get("_state", ()))
        for flag in statespec:
            current.discard(flag.lstrip("!"))
            if not flag.startswith("!"):
                current.add(flag)
        self.options["_state"] = tuple(sorted(current))
        return self.options["_state"]
    def add(self, child, **kw): self.children.append(child)
    def invoke(self):
        """Presses a button, the way a person would."""
        command = self.options.get("command")
        if command:
            return command()


class Tk(Widget):
    def __init__(self, *a, **kw):
        super().__init__(None, **kw)
        self._title = ""
    def title(self, text=None):
        if text is not None:
            self._title = text
        return self._title
    def minsize(self, *a): pass
    def update_idletasks(self): pass
    def update(self): pass
    def option_add(self, *a, **kw): pass
    def after(self, delay, callback=None, *args):
        if callback is not None:
            SCHEDULED.append((delay, callback, args))
        return "timer"
    def mainloop(self): pass
    def destroy(self): pass


class PhotoImage:
    def __init__(self, file=None, **kw):
        if file is None:
            raise ValueError("no file")
        with open(file, "rb") as f:
            if f.read(8) != b"\x89PNG\r\n\x1a\n":
                raise ValueError("not a PNG")
        self.file = file
    def width(self): return 1920
    def height(self): return 1080
    def subsample(self, x, y=None): return self


Frame = Label = Button = Entry = Text = Scrollbar = Checkbutton = Widget


def _make_ttk():
    mod = types.ModuleType("tkinter.ttk")
    for name in ("Frame", "Label", "Button", "Entry", "Combobox", "Checkbutton",
                 "Notebook", "Scrollbar", "Scale", "LabelFrame", "Separator"):
        setattr(mod, name, type(name, (Widget,), {}))

    class Style:
        def __init__(self, master=None): self.settings = {}
        def theme_use(self, name=None): return "clam"
        def configure(self, name, **kw): self.settings[name] = kw
        def map(self, name, **kw): pass
        def layout(self, *a, **kw): pass
    mod.Style = Style
    return mod


def _make_filedialog():
    mod = types.ModuleType("tkinter.filedialog")
    mod.askopenfilename = lambda **kw: ""
    mod.asksaveasfilename = lambda **kw: ""
    mod.askdirectory = lambda **kw: ""
    mod.answer = ""            # what the next askopenfilename returns
    mod.askopenfilename = lambda **kw: mod.answer
    return mod


def install():
    """Puts the stand-in where `import tkinter` will find it."""
    tk = types.ModuleType("tkinter")
    for name in ("Tk", "Widget", "Frame", "Label", "Button", "Entry", "Text",
                 "Scrollbar", "Checkbutton", "PhotoImage",
                 "StringVar", "IntVar", "DoubleVar", "BooleanVar"):
        setattr(tk, name, globals()[name])
    ttk = _make_ttk()
    filedialog = _make_filedialog()
    tk.ttk = ttk
    tk.filedialog = filedialog
    sys.modules["tkinter"] = tk
    sys.modules["tkinter.ttk"] = ttk
    sys.modules["tkinter.filedialog"] = filedialog
    return tk


def reset():
    CREATED.clear()
    SCHEDULED.clear()
