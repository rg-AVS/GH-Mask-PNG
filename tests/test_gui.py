#!/usr/bin/env python3
"""test_gui.py -- exercises gui/mask_gui.py against a stand-in tkinter.

Covers the wiring, not the drawing: that the window builds, that choosing a
file runs a real conversion and puts Masks.xml beside the image, that an
existing mask file is not replaced without being asked, and that a bad image
is reported in words rather than as a traceback.

    python3 tests/test_gui.py
"""

import os
import shutil
import struct
import sys
import tempfile
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import faketk  # noqa: E402

faketk.install()                     # must happen before mask_gui is imported
sys.path.insert(0, os.path.join(ROOT, "gui"))
import backend    # noqa: E402
import mask_gui   # noqa: E402

from tkinter import filedialog, messagebox  # noqa: E402  (the stand-ins)

FAILED = []
SAMPLE = os.path.join(ROOT, "testset", "01_1920x1080_native.png")


def check(label, condition, detail=""):
    if condition:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s %s" % (label, detail))
        FAILED.append(label)


def section(name):
    print("\n=== %s ===" % name)


def settle(app, timeout=120.0):
    """Runs the queue drain by hand until the worker thread has reported."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not app.messages.empty():
            app._drain()
            return True
        time.sleep(0.05)
    return False


def black_png(path, width=64, height=64):
    """An all-black PNG, so the 'nothing to trace' path can be exercised."""
    raw = b"".join(b"\x00" + b"\x00" * width for _ in range(height))
    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw)))
        f.write(chunk(b"IEND", b""))
    return path


def main():
    section("The window builds")
    app = mask_gui.MaskGui()
    check("title is set", app.title() == "PNG to Hippotizer Mask", app.title())
    check("widgets were created", len(faketk.CREATED) > 8, len(faketk.CREATED))
    # Bound methods are new objects on each attribute access, so compare by
    # equality rather than identity.
    check("queue drain is scheduled", any(c == app._drain for _d, c, _a in faketk.SCHEDULED))
    check("tools were found", "not built" not in app.status.cget("text"),
          app.status.cget("text"))
    check("the button is available", "disabled" not in app.button.state())

    section("There is nothing to configure")
    for gone in ("p2m_map", "m2p_map", "p2m_threshold", "p2m_simplify", "ts_dir"):
        check("no %s field" % gone, not hasattr(app, gone))

    section("Cancelling the file picker does nothing")
    filedialog.answer = ""
    before = app.status.cget("text")
    app._choose()
    check("no work started", not app.busy)
    check("status unchanged", app.status.cget("text") == before)

    tmp = tempfile.mkdtemp(prefix="maskgui-test-")
    try:
        section("Choosing a PNG writes Masks.xml beside it")
        work = os.path.join(tmp, "show")
        os.makedirs(work)
        png = os.path.join(work, "Star for Mask.png")
        shutil.copy(os.path.join(ROOT, "Ref", "Star for Mask.png"), png)

        filedialog.answer = png
        messagebox.asked = []
        app._choose()
        check("button greys out while working", "disabled" in app.button.state())
        check("conversion reported", settle(app))
        check("button comes back", "disabled" not in app.button.state())
        check("Masks.xml is next to the image", os.path.isfile(os.path.join(work, "Masks.xml")))
        check("nothing asked on a fresh folder", messagebox.asked == [], messagebox.asked)
        check("reported as done", app.status.cget("foreground") == mask_gui.OK,
              app.status.cget("text"))
        check("details name the file", "Star for Mask.png" in app.details.cget("text"),
              app.details.cget("text"))
        check("details name the size", "1920 x 1080" in app.details.cget("text"),
              app.details.cget("text"))
        check("preview was set", app._preview_ref is not None)

        section("An existing Masks.xml is not replaced without asking")
        with open(os.path.join(work, "Masks.xml"), "w") as f:
            f.write("<Masks><!-- hand written --></Masks>")
        messagebox.asked = []
        messagebox.answer = False
        app._choose()
        check("it asked first", len(messagebox.asked) == 1, messagebox.asked)
        check("no work started", not app.busy)
        with open(os.path.join(work, "Masks.xml")) as f:
            kept = f.read()
        check("the existing file survived", "hand written" in kept)
        check("said so", "Left the existing mask alone." in app.status.cget("text"),
              app.status.cget("text"))

        messagebox.asked = []
        messagebox.answer = True
        app._choose()
        check("saying yes converts", settle(app))
        with open(os.path.join(work, "Masks.xml")) as f:
            replaced = f.read()
        check("the file was replaced", "hand written" not in replaced)

        section("An image with nothing in it says so")
        blank_dir = os.path.join(tmp, "blank")
        os.makedirs(blank_dir)
        filedialog.answer = black_png(os.path.join(blank_dir, "blank.png"))
        messagebox.answer = True
        app._choose()
        check("conversion reported", settle(app))
        check("warned, not errored", app.status.cget("foreground") == mask_gui.WARN,
              app.status.cget("text"))
        check("says what to do", "invert" in app.status.cget("text").lower(),
              app.status.cget("text"))

        section("A file that is not an image is reported in words")
        filedialog.answer = os.path.join(ROOT, "testset", "MANIFEST.txt")
        app._choose()
        check("failure reported", settle(app))
        check("shown as an error", app.status.cget("foreground") == mask_gui.ERR,
              app.status.cget("text"))
        check("no traceback in the message", "Traceback" not in app.status.cget("text"),
              app.status.cget("text"))
        check("button came back", "disabled" not in app.button.state())

        section("Preview never takes the window down")
        app._show_preview(os.path.join(ROOT, "testset", "MANIFEST.txt"))
        check("non-image handled", app.preview.cget("text") == "No preview available.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILED:
        print("TESTS FAILED: %d" % len(FAILED))
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
