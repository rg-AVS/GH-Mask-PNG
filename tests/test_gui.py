#!/usr/bin/env python3
"""test_gui.py -- exercises gui/mask_gui.py against a stand-in tkinter.

Covers the wiring, not the drawing: that the window builds, that choosing a
file runs a real conversion and puts Masks.xml beside the image, that it is
ready for the next one straight away, and that a bad image is reported in
words rather than as a traceback.

The conversion itself is gui/maskmaker.py and is tested separately.

    python3 tests/test_gui.py
"""

import os
import shutil
import struct
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import faketk  # noqa: E402

faketk.install()                     # must happen before mask_gui is imported
sys.path.insert(0, os.path.join(ROOT, "gui"))
import mask_gui   # noqa: E402

from tkinter import filedialog  # noqa: E402  (the stand-in)

FAILED = []


def check(label, condition, detail=""):
    if condition:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s %s" % (label, detail))
        FAILED.append(label)


def section(name):
    print("\n=== %s ===" % name)


def clear_png(path, width=64, height=64):
    """A fully see-through PNG, so the 'nothing to trace' path is exercised."""
    raw = b"".join(b"\x00" + bytes([20, 20, 20, 0]) * width for _ in range(height))

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw)))
        f.write(chunk(b"IEND", b""))
    return path


def main():
    section("The window builds")
    app = mask_gui.MaskGui()
    check("title is set", app.title() == "PNG to Hippotizer Mask", app.title())
    check("it is one button and one line", len(faketk.CREATED) <= 6, len(faketk.CREATED))
    check("the button is available", "disabled" not in app.button.state())
    check("nothing has to be built first", "not built" not in app.status.cget("text"),
          app.status.cget("text"))

    section("There is nothing to configure")
    for gone in ("p2m_map", "p2m_threshold", "p2m_simplify", "ts_dir", "preview", "details"):
        check("no %s" % gone, not hasattr(app, gone))

    section("Cancelling the file picker does nothing")
    filedialog.answer = ""
    app.choose()
    check("status stays empty", app.status.cget("text") == "", app.status.cget("text"))

    tmp = tempfile.mkdtemp(prefix="maskgui-test-")
    try:
        section("Choosing a PNG writes Masks.xml beside it")
        work = os.path.join(tmp, "show")
        os.makedirs(work)
        png = os.path.join(work, "Star for Mask.png")
        shutil.copy(os.path.join(ROOT, "Ref", "Star for Mask.png"), png)

        filedialog.answer = png
        app.choose()
        check("Masks.xml is next to the image", os.path.isfile(os.path.join(work, "Masks.xml")))
        check("reported as done", app.status.cget("foreground") == mask_gui.OK,
              app.status.cget("text"))
        check("the message names the file", os.path.join(work, "Masks.xml")
              in app.status.cget("text"), app.status.cget("text"))
        check("and what it found", "shape" in app.status.cget("text"), app.status.cget("text"))
        check("no backup mentioned on a fresh folder",
              "kept as" not in app.status.cget("text"), app.status.cget("text"))
        check("it remembers the folder for next time", app.last_folder == work,
              app.last_folder)


        section("An existing mask is kept and said so")
        with open(os.path.join(work, "Masks.xml"), "w") as f:
            f.write("<Masks><!-- hand written --></Masks>")
        filedialog.answer = png
        app.choose()
        check("it says where the old one went", "Masks.backup.xml" in app.status.cget("text"),
              app.status.cget("text"))
        with open(os.path.join(work, "Masks.backup.xml")) as f:
            check("the old one is intact", "hand written" in f.read())

        section("Straight on to the next one")
        again = os.path.join(work, "second.png")
        shutil.copy(os.path.join(ROOT, "testset", "07_1024x768_native.png"), again)
        filedialog.answer = again
        app.choose()
        check("the second conversion ran", "1024 x 768" in app.status.cget("text"),
              app.status.cget("text"))
        check("still reported as done", app.status.cget("foreground") == mask_gui.OK,
              app.status.cget("text"))

        section("An image with nothing in it says so")
        blank = os.path.join(tmp, "blank")
        os.makedirs(blank)
        filedialog.answer = clear_png(os.path.join(blank, "blank.png"))
        app.choose()
        check("warned, not errored", app.status.cget("foreground") == mask_gui.WARN,
              app.status.cget("text"))
        check("says why", "see-through" in app.status.cget("text").lower(),
              app.status.cget("text"))

        section("A PNG with no transparency says what to do about it")
        solid = os.path.join(tmp, "solid")
        os.makedirs(solid)
        shutil.copy(os.path.join(ROOT, "docs", "coordinate_mismatch_visual.png"),
                    os.path.join(solid, "solid.png"))
        filedialog.answer = os.path.join(solid, "solid.png")
        app.choose()
        check("shown as an error", app.status.cget("foreground") == mask_gui.ERR,
              app.status.cget("text"))
        check("names the fix", "see-through" in app.status.cget("text").lower()
              and "Photoshop" in app.status.cget("text"), app.status.cget("text"))
        check("no Masks.xml was written",
              not os.path.exists(os.path.join(solid, "Masks.xml")))

        section("A file that is not an image is reported in words")
        filedialog.answer = os.path.join(ROOT, "testset", "MANIFEST.txt")
        app.choose()
        check("shown as an error", app.status.cget("foreground") == mask_gui.ERR,
              app.status.cget("text"))
        check("no traceback in the message", "Traceback" not in app.status.cget("text"),
              app.status.cget("text"))
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
