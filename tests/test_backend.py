#!/usr/bin/env python3
"""test_backend.py -- headless checks for gui/backend.py.

    python3 tests/test_backend.py
"""

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gui"))
import backend  # noqa: E402

FAILED = []


def check(label, condition, detail=""):
    if condition:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s %s" % (label, detail))
        FAILED.append(label)


def section(name):
    print("\n=== %s ===" % name)


def main():
    root = backend.REPO_ROOT
    section("The tool is built")
    check("png2mask found", backend.is_built(root), backend.tool_path("png2mask", root))
    if not backend.is_built(root):
        print("\nbuild first: make")
        return 1

    section("PNG header reading")
    check("1920x1080", backend.png_size(os.path.join(root, "testset/01_1920x1080_native.png"))
          == (1920, 1080))
    check("3840x1080", backend.png_size(os.path.join(root, "testset/04_3840x1080_native.png"))
          == (3840, 1080))
    try:
        backend.png_size(os.path.join(root, "testset/MANIFEST.txt"))
        check("non-PNG is rejected", False)
    except backend.ToolError as e:
        check("non-PNG is rejected", "not a PNG" in str(e), str(e))

    section("Reading png2mask's summary")
    check("counts parse", backend.parse_counts("x, 2 shape(s), 37 node(s))") == (2, 37))
    check("counts survive nonsense", backend.parse_counts("nothing here") == (0, 0))

    tmp = tempfile.mkdtemp(prefix="maskgui-test-")
    try:
        work = os.path.join(tmp, "show")
        os.makedirs(work)
        png = os.path.join(work, "shape.png")
        shutil.copy(os.path.join(root, "testset/01_1920x1080_native.png"), png)

        section("convert_beside writes next to the image")
        check("mask_path_for agrees", backend.mask_path_for(png)
              == os.path.join(work, "Masks.xml"))
        result = backend.convert_beside(png, root=root)
        check("Masks.xml is in the image's folder",
              result["xml"] == os.path.join(work, "Masks.xml") and os.path.isfile(result["xml"]))
        check("reported the image size", (result["width"], result["height"]) == (1920, 1080),
              result)
        check("traced the three rings", result["shapes"] == 3, result)
        check("counted the points", result["nodes"] == 14, result)
        check("nothing backed up on a fresh folder", result["backup"] is None, result)

        section("An existing mask is kept, once")
        with open(result["xml"], "w") as f:
            f.write("<Masks><!-- hand written --></Masks>")
        second = backend.convert_beside(png, root=root)
        check("the old file was moved aside", second["backup"]
              == os.path.join(work, "Masks.backup.xml"), second)
        with open(second["backup"]) as f:
            check("and it is the hand-written one", "hand written" in f.read())
        with open(second["xml"]) as f:
            check("the new mask replaced it", "<Shape" in f.read())

        third = backend.convert_beside(png, root=root)
        check("a later run does not clobber the backup", third["backup"] is None, third)
        with open(os.path.join(work, "Masks.backup.xml")) as f:
            check("the hand-written file is still safe", "hand written" in f.read())

        section("Failures are reported, not swallowed")
        try:
            backend.convert_beside(os.path.join(tmp, "not-there.png"), root=root)
            check("missing file raises", False)
        except backend.ToolError as e:
            check("missing file raises", "not there" in str(e), str(e))
        try:
            backend.convert_beside(os.path.join(root, "testset/MANIFEST.txt"), root=root)
            check("non-PNG raises", False)
        except backend.ToolError as e:
            check("non-PNG raises", "not a PNG" in str(e), str(e))
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
