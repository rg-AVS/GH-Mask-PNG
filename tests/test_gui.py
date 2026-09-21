#!/usr/bin/env python3
"""test_gui.py -- exercises gui/mask_gui.py against a stand-in tkinter.

Covers the wiring, not the drawing: that the window builds, that the fields
the handlers read are the ones the tabs write, that pressing a button with
nothing filled in gives a usable message instead of a traceback, and that a
real conversion runs end to end and lands in the right place.

    python3 tests/test_gui.py
"""

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import faketk  # noqa: E402

faketk.install()                     # must happen before mask_gui is imported
sys.path.insert(0, os.path.join(ROOT, "gui"))
import backend    # noqa: E402
import mask_gui   # noqa: E402

FAILED = []


def check(label, condition, detail=""):
    if condition:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s %s" % (label, detail))
        FAILED.append(label)


def section(name):
    print("\n=== %s ===" % name)


def settle(app, timeout=60.0):
    """Runs the queue drain by hand until the worker thread has reported."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not app.messages.empty():
            app._drain()
            return True
        time.sleep(0.05)
    return False


def main():
    section("The window builds")
    app = mask_gui.MaskGui()
    check("title is set", app.title() == "Hippotizer Mask Tools", app.title())
    check("widgets were created", len(faketk.CREATED) > 40, len(faketk.CREATED))
    # Bound methods are new objects on each attribute access, so compare by
    # equality rather than identity.
    check("queue drain is scheduled", any(c == app._drain for _d, c, _a in faketk.SCHEDULED))

    section("Defaults are sane")
    check("mapping defaults to native", app.p2m_map.get() == "native", app.p2m_map.get())
    check("threshold defaults to 128", app.p2m_threshold.get() == 128)
    check("every mapping has help text",
          all(m in backend.MAPPING_HELP for m in backend.MAPPINGS))
    check("test-set folder pre-filled", app.ts_dir.get().endswith("testset"), app.ts_dir.get())
    check("tools were found", "not built" not in app.status.cget("text"),
          app.status.cget("text"))

    section("Empty fields ask, they do not crash")
    for label, handler in (("PNG to mask", app._do_png_to_mask),
                           ("round trip", app._do_round_trip),
                           ("mask to PNG", app._do_mask_to_png),
                           ("bounds", app._do_bounds),
                           ("compare", app._do_compare)):
        handler()
        text = app.status.cget("text")
        check("%s asks for input" % label, text.startswith("Fill in"), text)

    section("Bad input is reported in words")
    app.m2p_xml.set(os.path.join(ROOT, "testset/Masks.xml"))
    app.m2p_dir.set(app.work_dir)
    app.m2p_res.set("lots")
    app._do_mask_to_png()
    check("bad size is explained", "1920x1080" in app.status.cget("text"),
          app.status.cget("text"))

    section("A real conversion runs end to end")
    app.p2m_png.set(os.path.join(ROOT, "testset/01_1920x1080_native.png"))
    app.p2m_xml.set(os.path.join(app.work_dir, "from_gui.xml"))
    app._do_png_to_mask()
    check("conversion reported", settle(app))
    check("mask file written", os.path.isfile(os.path.join(app.work_dir, "from_gui.xml")))
    check("status is not an error", app.status.cget("foreground") != mask_gui.ERR,
          app.status.cget("text"))

    section("The round-trip button reaches a verdict")
    app._do_round_trip()
    check("round trip reported", settle(app))
    check("verdict says it cancels", app.status.cget("foreground") == mask_gui.OK,
          app.status.cget("text"))
    check("preview was set", app._preview_ref is not None)

    section("Render reaches the preview")
    app.m2p_res.set("1920x1080")
    app.m2p_index.set("1")
    app._do_mask_to_png()
    check("render reported", settle(app))
    check("status is not an error", app.status.cget("foreground") != mask_gui.ERR,
          app.status.cget("text"))

    section("A failing tool surfaces its message")
    app.p2m_png.set(os.path.join(ROOT, "testset/MANIFEST.txt"))
    app._do_png_to_mask()
    check("failure reported", settle(app))
    check("shown as an error", app.status.cget("foreground") == mask_gui.ERR,
          app.status.cget("text"))

    section("Preview never takes the window down")
    app._show_preview(os.path.join(ROOT, "testset/MANIFEST.txt"), "not an image")
    check("non-image handled", app.preview.cget("text") == "No preview available.")

    print()
    if FAILED:
        print("TESTS FAILED: %d" % len(FAILED))
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
