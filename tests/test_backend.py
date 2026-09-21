#!/usr/bin/env python3
"""test_backend.py -- headless checks for gui/backend.py.

The GUI is split so this file can exist: everything below runs without a
display, so the window code stays the only untested part and it is kept
thin enough to review by eye.

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
    section("Tools are built")
    missing = backend.missing_tools(root)
    check("all binaries present", not missing, missing)
    if missing:
        print("\nbuild first: make")
        return 1

    section("PNG header reading")
    check("1920x1080", backend.png_size(os.path.join(root, "testset/01_1920x1080_native.png")) == (1920, 1080))
    check("3840x1080", backend.png_size(os.path.join(root, "testset/04_3840x1080_native.png")) == (3840, 1080))
    check("1024x768", backend.png_size(os.path.join(root, "testset/07_1024x768_native.png")) == (1024, 768))
    try:
        backend.png_size(os.path.join(root, "testset/MANIFEST.txt"))
        check("non-PNG is rejected", False)
    except backend.ToolError:
        check("non-PNG is rejected", True)

    section("mask_diff output parsing")
    parsed = backend.parse_diff("1024x768  max_diff=255  mean_diff=10.876  "
                                "pixels_over_tolerance=36905 (4.69271%)\nMISMATCH")
    check("max_diff", parsed["max_diff"] == 255, parsed)
    check("percent", abs(parsed["percent"] - 4.69271) < 1e-6, parsed)
    check("not a match", parsed["match"] is False, parsed)
    ok = backend.parse_diff("1024x768  max_diff=0  mean_diff=0  "
                            "pixels_over_tolerance=0 (0%)\nMATCH (within tolerance 0)")
    check("match detected", ok["match"] and ok["max_diff"] == 0, ok)
    sizes = backend.parse_diff("DIFFERENT SIZE  1024x768 vs 1920x1080")
    check("size mismatch detected", sizes["size_mismatch"], sizes)
    check("unparseable output survives", backend.parse_diff("nonsense")["raw"] == "nonsense")

    section("Verdict wording")
    check("match reads as cancelling", backend.verdict(ok)[1] == "ok")
    check("big difference reads as wrong", backend.verdict(parsed)[1] == "err")
    near = backend.parse_diff("1x1  max_diff=1  mean_diff=0.1  pixels_over_tolerance=1 (0.16%)\nMISMATCH")
    check("edge-only difference reads as near", backend.verdict(near)[1] == "warn")
    check("size mismatch reads as error", backend.verdict(sizes)[1] == "err")

    tmp = tempfile.mkdtemp(prefix="maskgui-test-")
    try:
        section("Round-trip, every mapping")
        for mapping in backend.MAPPINGS:
            work = os.path.join(tmp, mapping)
            res = backend.round_trip(os.path.join(root, "testset/01_1920x1080_native.png"),
                                     work, mapping=mapping, root=root)
            check("map=%s renders identically" % mapping, res["match"], res["raw"])
            check("map=%s wrote a mask" % mapping, os.path.isfile(res["mask_xml"]))

        section("Test set generation")
        out = os.path.join(tmp, "set")
        backend.generate_testset(out, root=root)
        pngs = sorted(f for f in os.listdir(out) if f.endswith(".png"))
        check("9 PNGs", len(pngs) == 9, pngs)
        check("Masks.xml written", os.path.isfile(os.path.join(out, "Masks.xml")))
        check("MANIFEST written", os.path.isfile(os.path.join(out, "MANIFEST.txt")))

        section("Each generated pair cancels")
        for png in pngs:
            name = png[:-4]
            index, res_txt, mapping = name.split("_")
            w, h = (int(v) for v in res_txt.split("x"))
            dest = os.path.join(tmp, "render", name)
            os.makedirs(dest, exist_ok=True)
            backend.mask_to_png(os.path.join(out, "Masks.xml"), dest, w, h,
                                mapping=mapping, index=str(int(index)), root=root)
            result = backend.compare(os.path.join(out, png), os.path.join(dest, png), root=root)
            check("%s cancels" % name, result["match"], result["raw"])

        section("Errors are reported, not swallowed")
        try:
            backend.png_to_mask(os.path.join(tmp, "nope.png"), os.path.join(tmp, "x.xml"), root=root)
            check("missing input raises", False)
        except backend.ToolError as e:
            check("missing input raises", "cannot open" in str(e).lower(), str(e))
        try:
            backend.png_to_mask(os.path.join(root, "testset/07_1024x768_native.png"),
                                os.path.join(tmp, "y.xml"), mapping="sideways", root=root)
            check("bad mapping raises", False)
        except backend.ToolError as e:
            check("bad mapping raises", "unknown mapping" in str(e), str(e))
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
