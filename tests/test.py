#!/usr/bin/env python3
"""Checks for maskmaker.py.

    python3 tests/test.py

Small on purpose -- this is a proof of concept, so these cover the shape of
the answer rather than every corner of the PNG spec.
"""

import os
import struct
import sys
import tempfile
import xml.etree.ElementTree as ET
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import maskmaker  # noqa: E402

FAILED = []


def check(label, condition, detail=""):
    print(("  PASS  " if condition else "  FAIL  ") + label + ("" if condition else " %s" % (detail,)))
    if not condition:
        FAILED.append(label)


def rgba_png(path, width, height, is_inside):
    """An unfiltered 8-bit RGBA PNG. The shape is dark on purpose: anything
    that went on colour instead of alpha would fail these."""
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            row.extend((20, 20, 20, 255 if is_inside(x, y) else 0))
        rows.append(b"\x00" + bytes(row))

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(b"".join(rows))))
        f.write(chunk(b"IEND", b""))
    return path


def same_ring(a, b):
    """A ring is the same ring whatever point it starts from."""
    def start_at_lowest(r):
        i = min(range(len(r)), key=lambda k: r[k])
        return tuple(r[i:] + r[:i])
    return start_at_lowest(list(a)) == start_at_lowest(list(b))


def main():
    tmp = tempfile.mkdtemp(prefix="maskmaker-test-")

    print("\n=== Tracing ===")
    png = rgba_png(os.path.join(tmp, "square.png"), 40, 30,
                   lambda x, y: 10 <= x < 30 and 5 <= y < 25)
    width, height, alpha = maskmaker.read_alpha(png)
    check("reads the size", (width, height) == (40, 30))
    rings = maskmaker.trace(alpha, width, height)
    check("one shape", len(rings) == 1, rings)
    check("four corners, not one point per pixel", len(rings[0]) == 4, rings[0])
    check("in the right place",
          same_ring(rings[0], [(10, 5), (30, 5), (30, 25), (10, 25)]), rings[0])

    png = rgba_png(os.path.join(tmp, "donut.png"), 40, 40,
                   lambda x, y: (5 <= x < 35 and 5 <= y < 35) and
                                not (15 <= x < 25 and 15 <= y < 25))
    width, height, alpha = maskmaker.read_alpha(png)
    rings = maskmaker.trace(alpha, width, height)
    check("a hole is its own ring", len(rings) == 2, rings)
    outer, inner = sorted(rings, key=lambda r: -abs(maskmaker.area(r)))
    check("the hole winds the other way", maskmaker.area(outer) * maskmaker.area(inner) < 0)
    check("the hole is the right size", abs(abs(maskmaker.area(inner)) - 100) < 1e-9)

    png = rgba_png(os.path.join(tmp, "clear.png"), 40, 30, lambda x, y: False)
    width, height, alpha = maskmaker.read_alpha(png)
    check("a see-through image traces to nothing", maskmaker.trace(alpha, width, height) == [])

    png = rgba_png(os.path.join(tmp, "speck.png"), 40, 30,
                   lambda x, y: x == 5 and y == 5)
    width, height, alpha = maskmaker.read_alpha(png)
    check("a single-pixel speck is ignored", maskmaker.trace(alpha, width, height) == [])

    print("\n=== The Masks.xml that comes out ===")
    folder = os.path.join(tmp, "show")
    os.makedirs(folder)
    png = rgba_png(os.path.join(folder, "Front Wall.png"), 40, 30,
                   lambda x, y: 10 <= x < 30 and 5 <= y < 25)
    result = maskmaker.convert(png)
    check("written beside the image", result["xml"] == os.path.join(folder, "Masks.xml"))
    mask = ET.parse(result["xml"]).getroot().find("Mask")
    check("declared 1024x768 whatever the image was",
          (mask.get("xres"), mask.get("yres")) == ("1024", "768"), mask.attrib)
    check("named after the image", mask.get("name") == "Front Wall", mask.attrib)
    node = mask.find("Shape").find("Node")
    check("a corner node keeps both handles on the point",
          node.get("InHandleX") == node.get("PosX") == node.get("OutHandleX"), node.attrib)
    corners = [(float(n.get("PosX")), float(n.get("PosY")))
               for n in mask.find("Shape").findall("Node")]
    check("origin is the middle of the image",
          same_ring(corners, [(-10.0, -10.0), (10.0, -10.0), (10.0, 10.0), (-10.0, 10.0)]),
          corners)

    print("\n=== The real artwork ===")
    for sample, shapes in (("testset/Shapes/PNG to MAsk.png", 3),
                           ("Ref/Star for Mask.png", 2)):
        import shutil
        folder = tempfile.mkdtemp(dir=tmp)
        shutil.copy(os.path.join(ROOT, sample), folder)
        result = maskmaker.convert(os.path.join(folder, os.path.basename(sample)))
        check("%s -> %d shapes" % (os.path.basename(sample), shapes),
              result["shapes"] == shapes, result)

    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILED:
        print("TESTS FAILED: %d" % len(FAILED))
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
