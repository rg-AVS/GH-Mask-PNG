#!/usr/bin/env python3
"""test_maskmaker.py -- checks for gui/maskmaker.py, the pure-Python converter.

Two halves. The first needs nothing but Python: reading alpha out of every
PNG flavour, refusing images that have none, hole winding, the XML that comes
out, and the error messages. The second holds maskmaker to
src/mask/mask_trace.cpp -- same rings, pixel-identical renders -- and is
skipped if the C++ has not been built, since the whole point of maskmaker is
that it runs where there is no compiler.

    python3 tests/test_maskmaker.py
"""

import os
import shutil
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "gui"))
import maskmaker  # noqa: E402

FAILED = []
SKIPPED = []


def check(label, condition, detail=""):
    if condition:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s %s" % (label, detail))
        FAILED.append(label)


def skip(label, why):
    print("  SKIP  %s (%s)" % (label, why))
    SKIPPED.append(label)


def section(name):
    print("\n=== %s ===" % name)


# --- building test images --------------------------------------------------

def write_png(path, width, height, depth, colour, rows, palette=None, trns=None,
              interlace=0):
    """Writes a PNG with no row filtering, so the decoder is what is on trial."""
    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, depth, colour,
                                           0, 0, interlace)))
        if palette is not None:
            f.write(chunk(b"PLTE", bytes(palette)))
        if trns is not None:
            f.write(chunk(b"tRNS", bytes(trns)))
        f.write(chunk(b"IDAT", zlib.compress(raw)))
        f.write(chunk(b"IEND", b""))
    return path


def square_rows(width, height, box, value=255, background=0, channels=1, alpha_at=None,
                colour=None):
    """A solid rectangle, in whatever channel layout is asked for.

    With alpha_at set, the rectangle is carried by the ALPHA channel and the
    colour channels are whatever `colour` says -- deliberately dark by
    default, so any test that accidentally went on brightness would fail.
    """
    x0, y0, x1, y1 = box
    fill = colour if colour is not None else 20
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            inside = x0 <= x < x1 and y0 <= y < y1
            level = value if inside else background
            if channels == 1:
                row.append(level)
            elif alpha_at is None:
                row.extend([level] * channels)
            else:
                pixel = [fill] * channels
                pixel[alpha_at] = level
                row.extend(pixel)
        rows.append(row)
    return rows


def rings_of(xml_path):
    root = ET.parse(xml_path).getroot()
    return [[(float(n.get("PosX")), float(n.get("PosY"))) for n in shape.findall("Node")]
            for mask in root.findall("Mask") for shape in mask.findall("Shape")]


def canonical(ring):
    """A closed ring is the same ring whatever point it starts from."""
    start = min(range(len(ring)), key=lambda i: ring[i])
    return tuple(ring[start:] + ring[:start])


def area(ring):
    total = 0.0
    for i, (x, y) in enumerate(ring):
        nx, ny = ring[(i + 1) % len(ring)]
        total += x * ny - nx * y
    return total / 2.0


# --- the checks ------------------------------------------------------------

def main():
    tmp = tempfile.mkdtemp(prefix="maskmaker-test-")
    try:
        section("Reading alpha, whatever the PNG flavour")
        want = canonical([(10, 5), (30, 5), (30, 25), (10, 25)])
        cases = [
            ("8-bit RGBA", dict(depth=8, colour=6,
                                rows=square_rows(40, 30, (10, 5, 30, 25),
                                                 channels=4, alpha_at=3))),
            ("8-bit grey+alpha", dict(depth=8, colour=4,
                                      rows=square_rows(40, 30, (10, 5, 30, 25),
                                                       channels=2, alpha_at=1))),
        ]
        for label, kw in cases:
            path = write_png(os.path.join(tmp, label.replace(" ", "_") + ".png"),
                             40, 30, **kw)
            width, height, alpha = maskmaker.read_alpha(path)
            rings = maskmaker.trace(alpha, width, height)
            check(label, len(rings) == 1 and canonical(rings[0]) == want, rings)

        # 16-bit RGBA: the high byte of each sample is what we read.
        rows16 = []
        for y in range(30):
            row = bytearray()
            for x in range(40):
                level = 255 if 10 <= x < 30 and 5 <= y < 25 else 0
                row.extend((0, 0, 20, 0, 20, 0, level, 0))   # dark colour, alpha last
            rows16.append(row)
        path = write_png(os.path.join(tmp, "rgba16.png"), 40, 30, 16, 6, rows16)
        width, height, alpha = maskmaker.read_alpha(path)
        check("16-bit RGBA", canonical(maskmaker.trace(alpha, width, height)[0]) == want)

        # Palette with tRNS: entry 0 is see-through, entry 1 is solid -- and
        # both are dark, so brightness would find nothing.
        rows = [bytearray(1 if 10 <= x < 30 and 5 <= y < 25 else 0 for x in range(40))
                for y in range(30)]
        path = write_png(os.path.join(tmp, "palette.png"), 40, 30, 8, 3, rows,
                         palette=[10, 10, 10, 20, 20, 20], trns=[0, 255])
        width, height, alpha = maskmaker.read_alpha(path)
        check("palette with tRNS", canonical(maskmaker.trace(alpha, width, height)[0]) == want)

        # 1 bit per pixel, packed eight to a byte, with tRNS.
        rows1 = []
        for y in range(30):
            bits = "".join("1" if 10 <= x < 30 and 5 <= y < 25 else "0" for x in range(40))
            rows1.append(bytearray(int(bits[i:i + 8].ljust(8, "0"), 2)
                                   for i in range(0, 40, 8)))
        path = write_png(os.path.join(tmp, "onebit.png"), 40, 30, 1, 3, rows1,
                         palette=[10, 10, 10, 20, 20, 20], trns=[0, 255])
        width, height, alpha = maskmaker.read_alpha(path)
        check("1 bit per pixel with tRNS",
              canonical(maskmaker.trace(alpha, width, height)[0]) == want)

        section("Colour is never read")
        # A dark shape on a see-through background, like real artwork. Anything
        # that went on brightness would find nothing here at all.
        path = write_png(os.path.join(tmp, "dark_on_clear.png"), 40, 30, 8, 6,
                         square_rows(40, 30, (10, 5, 30, 25), channels=4, alpha_at=3,
                                     colour=20))
        width, height, alpha = maskmaker.read_alpha(path)
        check("a dark shape on transparency is still found",
              canonical(maskmaker.trace(alpha, width, height)[0]) == want)

        # The same shape drawn white on an opaque white background: brightness
        # would see nothing, and alpha correctly refuses the file.
        path = write_png(os.path.join(tmp, "white_on_white.png"), 40, 30, 8, 6,
                         square_rows(40, 30, (10, 5, 30, 25), value=255, background=255,
                                     channels=4, alpha_at=3))
        try:
            maskmaker.read_alpha(path)
            check("an opaque image is refused", False, "no error raised")
        except maskmaker.MaskError as exc:
            check("an opaque image is refused", "nothing see-through" in str(exc), str(exc))

        section("Images with no alpha at all are refused")
        for label, kw in (("8-bit greyscale", dict(depth=8, colour=0,
                                                   rows=square_rows(40, 30, (10, 5, 30, 25)))),
                          ("8-bit RGB", dict(depth=8, colour=2,
                                             rows=square_rows(40, 30, (10, 5, 30, 25),
                                                              channels=3)))):
            path = write_png(os.path.join(tmp, "noalpha_" + label[-4:] + ".png"), 40, 30, **kw)
            try:
                maskmaker.read_alpha(path)
                check(label, False, "no error raised")
            except maskmaker.MaskError as exc:
                check(label, "no transparency" in str(exc) and "see-through" in str(exc),
                      str(exc))

        rows = [bytearray(1 if x > 20 else 0 for x in range(40)) for y in range(30)]
        path = write_png(os.path.join(tmp, "palette_notrns.png"), 40, 30, 8, 3, rows,
                         palette=[0, 0, 0, 255, 255, 255])
        try:
            maskmaker.read_alpha(path)
            check("palette without tRNS", False, "no error raised")
        except maskmaker.MaskError as exc:
            check("palette without tRNS", "no transparency" in str(exc), str(exc))

        section("Every row filter is undone correctly")
        # Same image written five times, each row using one filter type. RGBA,
        # so the per-channel unfilter is what is on trial, not a shortcut.
        plain = square_rows(40, 30, (10, 5, 30, 25), channels=4, alpha_at=3)
        span = 40 * 4
        for kind in range(5):
            encoded = []
            previous = bytearray(span)
            for row in plain:
                line = bytearray(span)
                for i in range(span):
                    left = row[i - 4] if i >= 4 else 0
                    up = previous[i]
                    upleft = previous[i - 4] if i >= 4 else 0
                    if kind == 0:
                        line[i] = row[i]
                    elif kind == 1:
                        line[i] = (row[i] - left) & 255
                    elif kind == 2:
                        line[i] = (row[i] - up) & 255
                    elif kind == 3:
                        line[i] = (row[i] - ((left + up) >> 1)) & 255
                    else:
                        guess = left + up - upleft
                        dl, du, dul = (abs(guess - left), abs(guess - up),
                                       abs(guess - upleft))
                        nearest = left if (dl <= du and dl <= dul) else (
                            up if du <= dul else upleft)
                        line[i] = (row[i] - nearest) & 255
                encoded.append(bytes([kind]) + bytes(line))
                previous = bytearray(row)

            def chunk(tag, data):
                body = tag + data
                return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

            path = os.path.join(tmp, "filter%d.png" % kind)
            with open(path, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n")
                f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", 40, 30, 8, 6, 0, 0, 0)))
                f.write(chunk(b"IDAT", zlib.compress(b"".join(encoded))))
                f.write(chunk(b"IEND", b""))
            width, height, alpha = maskmaker.read_alpha(path)
            rings = maskmaker.trace(alpha, width, height)
            check("filter type %d" % kind,
                  len(rings) == 1 and canonical(rings[0]) == want, rings)

        section("Tracing")
        # A square with a square hole: two rings, wound opposite ways.
        rows = []
        for y in range(40):
            row = bytearray()
            for x in range(40):
                solid = 5 <= x < 35 and 5 <= y < 35
                hole = 15 <= x < 25 and 15 <= y < 25
                row.extend((20, 20, 20, 255 if solid and not hole else 0))
            rows.append(row)
        path = write_png(os.path.join(tmp, "donut.png"), 40, 40, 8, 6, rows)
        width, height, alpha = maskmaker.read_alpha(path)
        rings = maskmaker.trace(alpha, width, height)
        check("a hole is traced as its own ring", len(rings) == 2, rings)
        if len(rings) == 2:
            outer, inner = sorted(rings, key=lambda r: -abs(area(r)))
            check("the hole winds the opposite way to its parent",
                  area(outer) * area(inner) < 0, (area(outer), area(inner)))
            check("the hole is the right size", abs(abs(area(inner)) - 100) < 1e-9,
                  area(inner))

        path = write_png(os.path.join(tmp, "clear.png"), 40, 30, 8, 6,
                         square_rows(40, 30, (0, 0, 0, 0), channels=4, alpha_at=3))
        width, height, alpha = maskmaker.read_alpha(path)
        check("a fully see-through image traces to nothing",
              maskmaker.trace(alpha, width, height) == [])

        path = write_png(os.path.join(tmp, "specks.png"), 40, 30, 8, 6,
                         square_rows(40, 30, (5, 5, 6, 6), channels=4, alpha_at=3))
        width, height, alpha = maskmaker.read_alpha(path)
        check("a single-pixel speck is ignored", maskmaker.trace(alpha, width, height) == [])

        path = write_png(os.path.join(tmp, "faint.png"), 40, 30, 8, 6,
                         square_rows(40, 30, (10, 5, 30, 25), value=100,
                                     channels=4, alpha_at=3))
        width, height, alpha = maskmaker.read_alpha(path)
        check("mostly see-through is not masked", maskmaker.trace(alpha, width, height) == [])
        check("the threshold is adjustable",
              len(maskmaker.trace(alpha, width, height, threshold=90)) == 1)
        check("inverting masks the see-through part instead",
              len(maskmaker.trace(alpha, width, height, invert=True)) == 1)

        section("Smoothing")
        square = [(10, 5), (30, 5), (30, 25), (10, 25)]
        check("a rectangle is four corners, not four hundred",
              len(maskmaker.simplify(square, 1.0)) == 4)
        staircase = [(0, 0), (1, 0), (1, 1), (2, 1), (2, 2), (10, 2), (10, 10), (0, 10)]
        check("smoothing removes points", len(maskmaker.simplify(staircase, 2.0))
              < len(staircase))
        check("lossless smoothing keeps the shape",
              len(maskmaker.simplify(staircase, 0)) == len(staircase))

        section("The Masks.xml that comes out")
        work = os.path.join(tmp, "show")
        os.makedirs(work)
        png = os.path.join(work, "Front Wall.png")
        write_png(png, 40, 30, 8, 6,
                  square_rows(40, 30, (10, 5, 30, 25), channels=4, alpha_at=3))
        result = maskmaker.convert(png)
        check("written beside the image", result["xml"] == os.path.join(work, "Masks.xml"))
        check("nothing backed up on a fresh folder", result["backup"] is None)
        root = ET.parse(result["xml"]).getroot()
        mask = root.find("Mask")
        check("declared 1024x768 whatever the image was",
              (mask.get("xres"), mask.get("yres")) == ("1024", "768"), mask.attrib)
        check("named after the image", mask.get("name") == "Front Wall", mask.attrib)
        check("not inverted by default", mask.get("invert") == "false")
        shape = mask.find("Shape")
        check("shape attributes match Hippotizer's",
              (shape.get("Level"), shape.get("gamma"), shape.get("hvmix")) ==
              ("255", "2.2", "127"), shape.attrib)
        node = shape.find("Node")
        check("corner node keeps both handles on the point",
              node.get("InHandleX") == node.get("PosX") == node.get("OutHandleX"),
              node.attrib)
        check("origin is the middle of the image",
              canonical(rings_of(result["xml"])[0]) ==
              canonical([(-10.0, -10.0), (10.0, -10.0), (10.0, 10.0), (-10.0, 10.0)]),
              rings_of(result["xml"]))
        check("a name with an & would not break the file",
              "&amp;" in maskmaker.build_xml([], 10, 10, "A & B"))

        section("An existing mask is kept, once")
        with open(result["xml"], "w") as f:
            f.write("<Masks><!-- hand written --></Masks>")
        second = maskmaker.convert(png)
        check("the old file was moved aside",
              second["backup"] == os.path.join(work, "Masks.backup.xml"), second)
        check("and it is the hand-written one",
              "hand written" in open(second["backup"]).read())
        third = maskmaker.convert(png)
        check("a later run does not clobber the backup", third["backup"] is None, third)
        check("the hand-written file is still safe",
              "hand written" in open(os.path.join(work, "Masks.backup.xml")).read())

        section("Bad input is explained, not raised")
        for label, path, wanted in (
                ("a text file", os.path.join(ROOT, "README.md"), "not a PNG"),
                ("a missing file", os.path.join(tmp, "nope.png"), "not there")):
            try:
                maskmaker.convert(path)
                check(label, False, "no error raised")
            except maskmaker.MaskError as exc:
                check(label, wanted in str(exc), str(exc))

        truncated = os.path.join(tmp, "truncated.png")
        with open(truncated, "wb") as f:
            f.write(open(os.path.join(tmp, "donut.png"), "rb").read()[:60])
        try:
            maskmaker.convert(truncated)
            check("a truncated file", False, "no error raised")
        except maskmaker.MaskError as exc:
            check("a truncated file", "damaged" in str(exc) or "shorter" in str(exc), str(exc))

        interlaced = write_png(os.path.join(tmp, "interlaced.png"), 40, 30, 8, 6,
                               square_rows(40, 30, (10, 5, 30, 25), channels=4, alpha_at=3),
                               interlace=1)
        try:
            maskmaker.convert(interlaced)
            check("an interlaced PNG", False, "no error raised")
        except maskmaker.MaskError as exc:
            check("an interlaced PNG says what to do", "interlac" in str(exc).lower()
                  and "re-save" in str(exc).lower(), str(exc))

        # --- held against the C++ ------------------------------------------
        section("Agrees with the C++ tracer")
        png2mask = os.path.join(ROOT, "build", "png2mask" + (".exe" if os.name == "nt" else ""))
        mask2png = os.path.join(ROOT, "build", "mask2png" + (".exe" if os.name == "nt" else ""))
        if not os.path.isfile(png2mask):
            skip("same rings as mask_trace.cpp", "C++ not built; run make")
            skip("pixel-identical renders", "C++ not built; run make")
        else:
            samples = ["testset/Shapes/PNG to MAsk.png",
                       "Ref/Star for Mask.png",
                       "testset/01_1920x1080_native.png",
                       "testset/04_3840x1080_native.png",
                       "testset/07_1024x768_native.png"]
            all_same = True
            all_pixels = True
            for sample in samples:
                pen = os.path.join(tmp, "cross", os.path.basename(sample))
                os.makedirs(os.path.dirname(pen), exist_ok=True)
                shutil.copy(os.path.join(ROOT, sample), pen)
                for stale in ("Masks.xml", "Masks.backup.xml"):
                    if os.path.exists(os.path.join(os.path.dirname(pen), stale)):
                        os.remove(os.path.join(os.path.dirname(pen), stale))

                mine = maskmaker.convert(pen)
                theirs = os.path.join(tmp, "cross", "cpp.xml")
                subprocess.run([png2mask, pen, theirs, "--name",
                                os.path.splitext(os.path.basename(sample))[0]],
                               capture_output=True, check=True)

                # A ring is the same ring whatever point it starts from, and the
                # two implementations walk the pixels in a different order, so
                # compare the rings themselves rather than their first node.
                a = sorted(canonical(r) for r in rings_of(mine["xml"]))
                b = sorted(canonical(r) for r in rings_of(theirs))
                if a != b:
                    all_same = False
                    print("        %s: %d rings vs %d" % (sample, len(a), len(b)))

                # The real proof: render both and compare every pixel.
                if os.path.isfile(mask2png):
                    width, height = mine["width"], mine["height"]
                    for which, xml in (("py", mine["xml"]), ("cpp", theirs)):
                        out = os.path.join(tmp, "cross", which)
                        os.makedirs(out, exist_ok=True)
                        subprocess.run([mask2png, xml, out, "--res", "%dx%d" % (width, height)],
                                       capture_output=True, check=True)
                    rendered = [os.path.join(tmp, "cross", w, os.listdir(
                        os.path.join(tmp, "cross", w))[0]) for w in ("py", "cpp")]
                    if open(rendered[0], "rb").read() != open(rendered[1], "rb").read():
                        all_pixels = False
                        print("        %s: renders differ" % sample)
                    for w in ("py", "cpp"):
                        shutil.rmtree(os.path.join(tmp, "cross", w))
            check("same rings as mask_trace.cpp", all_same)
            if os.path.isfile(mask2png):
                check("pixel-identical renders", all_pixels)
            else:
                skip("pixel-identical renders", "mask2png not built")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if SKIPPED:
        print("%d check(s) skipped." % len(SKIPPED))
    if FAILED:
        print("TESTS FAILED: %d" % len(FAILED))
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
