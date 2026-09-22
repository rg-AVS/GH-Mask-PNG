#!/usr/bin/env python3
"""maskmaker.py -- PNG to Hippotizer Masks.xml, in pure Python.

Nothing to build and nothing to install: the standard library decodes the
PNG (zlib), traces it and writes the XML. Run it from the window
(mask_gui.py) or straight from a shell:

    python3 gui/maskmaker.py "Star for Mask.png"

The mask is written as Masks.xml into the same folder as the image.

This is a second implementation of what src/mask/mask_trace.cpp does, which
is normally a smell -- it is here because the C++ is the thing that ships
inside the product and needs a compiler, and this is the thing an operator
runs on a show laptop that has neither. tests/test_maskmaker.py holds the
two to each other: same rings, same coordinates, pixel-identical renders.

ALPHA IS THE ONLY THING READ. The mask is whatever is not see-through; the
colours are never looked at. That is the point -- artwork is usually not
white, and the three shapes in testset/Shapes are all darker than mid-grey,
so anything that went on brightness would have found almost nothing. An
image with no transparency is rejected with a message saying so, rather than
quietly guessing from the picture and handing back a mask that could be the
exact inverse of what was drawn.

What it does, in order:
  1. Decode the alpha channel, and only the alpha channel.
  2. Threshold it: half-opaque or more is inside the mask.
  3. Trace the boundary along the grid lines BETWEEN pixels, so the shape
     covers exactly the pixels that crossed the threshold.
  4. Drop points that sit on a straight line, then smooth what is left.
  5. Write the rings out as <Shape> elements of corner nodes.

Outer edges and the holes inside them come out wound opposite ways, so a
hole cuts itself out under the nonzero fill rule with no special casing.
"""

import os
import re
import struct
import sys
import uuid
import zlib

THRESHOLD = 128        # at or above this, a pixel is inside the mask
SIMPLIFY = 1.0         # how far a traced edge may be straightened, in pixels
MIN_AREA = 4           # ignore traced specks smaller than this many pixels
DECL_W, DECL_H = 1024, 768   # what Hippotizer writes as xres/yres, always
GAMMA = 2.2            # what Hippotizer writes on a shape

CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
WITH_ALPHA = (4, 6)        # greyscale+alpha and RGBA; a palette may carry tRNS

NO_ALPHA = ("This PNG has no transparency in it, and transparency is the only thing "
            "we read. Save it with the shapes on a see-through background -- in "
            "Photoshop, hide the background layer and export as PNG-24 with "
            "Transparency ticked.")


class MaskError(Exception):
    """Something about the image stopped us. The message is for the operator."""


# --- PNG decoding ----------------------------------------------------------

def _read_chunks(path):
    try:
        data = open(path, "rb").read()
    except OSError as exc:
        raise MaskError("Could not open %s. %s" % (os.path.basename(path), exc.strerror))
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise MaskError("%s is not a PNG file." % os.path.basename(path))

    header, palette, transparency = None, None, None
    idat = bytearray()
    i = 8
    while i + 8 <= len(data):
        length = struct.unpack(">I", data[i:i + 4])[0]
        tag = data[i + 4:i + 8]
        body = data[i + 8:i + 8 + length]
        if tag == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif tag == b"PLTE":
            palette = body
        elif tag == b"tRNS":
            transparency = body
        elif tag == b"IDAT":
            idat += body
        elif tag == b"IEND":
            break
        i += 12 + length

    if header is None or not idat:
        raise MaskError("%s looks damaged -- no image data in it." % os.path.basename(path))
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error:
        raise MaskError("%s looks damaged -- its image data would not decompress."
                        % os.path.basename(path))
    return header, palette, transparency, raw


def _unfilter(raw, height, stride, bpp, offset, step):
    """Undoes PNG row filtering for ONE channel.

    Filtering only ever looks back by exactly one pixel (`bpp` bytes) or up
    one row, so each channel's bytes form a self-contained stream. Pulling
    out just the channel that matters -- alpha, usually -- is what keeps this
    under a second in pure Python on a 4K-wide image instead of four times
    that.
    """
    count = len(range(offset, stride, step))
    out = bytearray(count * height)
    previous = bytearray(count)
    read = 0
    write = 0
    back = max(1, bpp // step)     # how many entries back one pixel is, in this stream

    for _row in range(height):
        kind = raw[read]
        read += 1
        line = bytearray(raw[read:read + stride][offset::step])
        read += stride
        if len(line) < count:
            raise MaskError("The image data is shorter than the header says it should be.")

        if kind == 1:
            for i in range(back, count):
                line[i] = (line[i] + line[i - back]) & 255
        elif kind == 2:
            for i in range(count):
                line[i] = (line[i] + previous[i]) & 255
        elif kind == 3:
            for i in range(count):
                left = line[i - back] if i >= back else 0
                line[i] = (line[i] + ((left + previous[i]) >> 1)) & 255
        elif kind == 4:
            for i in range(count):
                left = line[i - back] if i >= back else 0
                up = previous[i]
                upleft = previous[i - back] if i >= back else 0
                guess = left + up - upleft
                dl, du, dul = abs(guess - left), abs(guess - up), abs(guess - upleft)
                if dl <= du and dl <= dul:
                    nearest = left
                elif du <= dul:
                    nearest = up
                else:
                    nearest = upleft
                line[i] = (line[i] + nearest) & 255
        elif kind != 0:
            raise MaskError("The image uses an unknown row filter (%d)." % kind)

        out[write:write + count] = line
        write += count
        previous = line
    return out


def _unpack_bits(packed, width, height, depth):
    """Expands 1, 2 or 4 bit-per-pixel rows into one byte per pixel."""
    per_row = (width * depth + 7) // 8
    scale = 255 // ((1 << depth) - 1)
    mask = (1 << depth) - 1
    out = bytearray(width * height)
    for y in range(height):
        row = packed[y * per_row:(y + 1) * per_row]
        base = y * width
        for x in range(width):
            byte = row[(x * depth) // 8]
            shift = 8 - depth - ((x * depth) % 8)
            out[base + x] = ((byte >> shift) & mask) * scale
    return out


def read_alpha(path):
    """Returns (width, height, the alpha channel).

    The alpha channel is the whole story: what is solid is mask, what is
    see-through is not, and the colours are never read. An image that has no
    alpha, or an alpha channel that is opaque everywhere, has nothing to say
    and is refused rather than guessed at.
    """
    (width, height, depth, colour, _comp, _filt, interlace), palette, trns, raw = \
        _read_chunks(path)

    if interlace:
        raise MaskError("This PNG is interlaced. Re-save it without interlacing "
                        "(uncheck \"Interlaced\" in the export dialog).")
    if colour not in CHANNELS:
        raise MaskError("This PNG uses an image type we cannot read (colour type %d)." % colour)
    if depth not in (1, 2, 4, 8, 16):
        raise MaskError("This PNG uses %d bits per channel, which we cannot read." % depth)
    if colour not in WITH_ALPHA and not (colour == 3 and trns):
        raise MaskError(NO_ALPHA)
    if colour != 3 and depth < 8:
        raise MaskError("This PNG uses %d bits per channel, which we cannot read." % depth)

    channels = CHANNELS[colour]
    sample = max(1, depth // 8)
    bpp = max(1, channels * depth // 8)

    if colour == 3:
        # Palette: decode the index stream, then look each entry's alpha up.
        if palette is None:
            raise MaskError("This PNG says it uses a palette but does not include one.")
        if depth < 8:
            stride = (width * depth + 7) // 8
            scale = 255 // ((1 << depth) - 1)
            indices = bytearray(v // scale for v in _unpack_bits(
                _unfilter(raw, height, stride, 1, 0, 1), width, height, depth))
        else:
            indices = _unfilter(raw, height, width * sample, bpp, 0, sample)
        entries = len(palette) // 3
        table = bytes(trns[i] if i < len(trns) else 255 for i in range(entries))
        lookup = bytes(table[i] if i < entries else 255 for i in range(256))
        alpha = bytes(indices).translate(lookup)
    else:
        stride = width * channels * sample
        alpha = _unfilter(raw, height, stride, bpp, (channels - 1) * sample, bpp)

    # min() runs at C speed, so asking costs nothing even on a 4K frame.
    if min(alpha) == 255:
        raise MaskError("Every pixel in this PNG is solid -- there is nothing "
                        "see-through to cut around. " + NO_ALPHA)
    return width, height, alpha


# --- tracing ---------------------------------------------------------------

def _runs_per_row(pixels, width, height, threshold, invert):
    """Each row's stretches of masked pixels, as (start, end) column pairs.

    Thresholding with translate() and finding the stretches with a regular
    expression both run at C speed, which matters: doing it pixel by pixel in
    Python would be minutes on a 4K frame, and this is milliseconds.
    """
    inside, outside = (b"\x00", b"\x01") if invert else (b"\x01", b"\x00")
    table = outside * threshold + inside * (256 - threshold)
    flat = bytes(pixels).translate(table)
    pattern = re.compile(b"\x01+")
    return [[(m.start(), m.end()) for m in pattern.finditer(flat[y * width:(y + 1) * width])]
            for y in range(height)]


def _gaps(span, covered):
    """The parts of `span` that none of `covered` overlaps."""
    start, end = span
    out = []
    at = start
    for a, b in covered:
        if b <= at:
            continue
        if a >= end:
            break
        if a > at:
            out.append((at, min(a, end)))
        at = max(at, b)
        if at >= end:
            return out
    if at < end:
        out.append((at, end))
    return out


def _boundary_edges(rows):
    """Every grid-line step between a masked pixel and an unmasked one, wound
    so the mask stays on the right of travel. Outer rings then come out one
    way round and holes the other, which is what makes a hole cut itself out."""
    edges = []
    add = edges.append
    height = len(rows)
    for y, spans in enumerate(rows):
        above = rows[y - 1] if y > 0 else []
        below = rows[y + 1] if y + 1 < height else []
        for x0, x1 in spans:
            for a, b in _gaps((x0, x1), above):
                for x in range(a, b):
                    add(((x, y), (x + 1, y)))
            add(((x1, y), (x1, y + 1)))
            for a, b in _gaps((x0, x1), below):
                for x in range(b, a, -1):
                    add(((x, y + 1), (x - 1, y + 1)))
            add(((x0, y + 1), (x0, y)))
    return edges


def _chain(edges):
    """Links the boundary steps into closed rings."""
    outgoing = {}
    for index, (start, _end) in enumerate(edges):
        outgoing.setdefault(start, []).append(index)
    used = bytearray(len(edges))

    rings = []
    for first in range(len(edges)):
        if used[first]:
            continue
        ring = []
        current = first
        while current is not None and not used[current]:
            used[current] = 1
            (x0, y0), (x1, y1) = edges[current]
            ring.append((x0, y0))
            dx, dy = x1 - x0, y1 - y0
            # Where two pixels meet corner to corner, two steps leave the same
            # point. Turning as sharply right as possible keeps them as
            # separate regions; either choice covers the same pixels.
            preferred = ((-dy, dx), (dx, dy), (dy, -dx), (-dx, -dy))
            nxt = None
            for want in preferred:
                for candidate in outgoing.get((x1, y1), ()):
                    if used[candidate]:
                        continue
                    (ax, ay), (bx, by) = edges[candidate]
                    if (bx - ax, by - ay) == want:
                        nxt = candidate
                        break
                if nxt is not None:
                    break
            current = nxt
        if len(ring) >= 4:
            rings.append(ring)
    return rings


def _area(ring):
    total = 0
    for i, (x, y) in enumerate(ring):
        nx, ny = ring[(i + 1) % len(ring)]
        total += x * ny - nx * y
    return total / 2.0


def _drop_collinear(ring):
    """Removes points sitting exactly on the line between their neighbours.
    Lossless, and it is what turns a traced rectangle back into four corners."""
    if len(ring) < 3:
        return ring
    out = []
    for i, (x, y) in enumerate(ring):
        px, py = ring[i - 1]
        nx, ny = ring[(i + 1) % len(ring)]
        if (x - px) * (ny - py) - (y - py) * (nx - px):
            out.append((x, y))
    return out if len(out) >= 3 else ring


def _douglas_peucker(points, epsilon, keep, first, last):
    if last <= first + 1:
        return
    ax, ay = points[first]
    bx, by = points[last]
    dx, dy = bx - ax, by - ay
    length = (dx * dx + dy * dy) ** 0.5
    worst, worst_at = -1.0, first
    for i in range(first + 1, last):
        px, py = points[i]
        if length < 1e-9:
            distance = ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
        else:
            distance = abs(dy * (px - ax) - dx * (py - ay)) / length
        if distance > worst:
            worst, worst_at = distance, i
    if worst <= epsilon:
        return
    keep[worst_at] = True
    _douglas_peucker(points, epsilon, keep, first, worst_at)
    _douglas_peucker(points, epsilon, keep, worst_at, last)


def simplify(ring, epsilon):
    base = _drop_collinear(ring)
    if epsilon <= 0 or len(base) < 4:
        return base

    # Split the closed ring at its two most distant points so each half is an
    # open line Douglas-Peucker can handle normally.
    ax, ay = base[0]
    far = max(range(1, len(base)),
              key=lambda i: (base[i][0] - ax) ** 2 + (base[i][1] - ay) ** 2)
    keep = [False] * len(base)
    keep[0] = keep[far] = True
    _douglas_peucker(base, epsilon, keep, 0, far)

    tail = base[far:] + [base[0]]
    tail_keep = [False] * len(tail)
    tail_keep[0] = tail_keep[-1] = True
    _douglas_peucker(tail, epsilon, tail_keep, 0, len(tail) - 1)
    for i, wanted in enumerate(tail_keep[:-1]):
        if wanted:
            keep[(far + i) % len(base)] = True

    out = [point for point, wanted in zip(base, keep) if wanted]
    return out if len(out) >= 3 else base


def trace(pixels, width, height, threshold=THRESHOLD, invert=False,
          epsilon=SIMPLIFY, min_area=MIN_AREA):
    """The masked areas, as rings of points in pixel coordinates. `pixels` is
    the alpha channel: 255 is solid, 0 is see-through."""
    rows = _runs_per_row(pixels, width, height, threshold, invert)
    rings = []
    for ring in _chain(_boundary_edges(rows)):
        if abs(_area(ring)) >= min_area:
            rings.append(simplify(ring, epsilon))
    return rings


# --- writing Masks.xml -----------------------------------------------------

def _number(value):
    """Matches how the C++ writer formats a coordinate, so the two agree."""
    return "%.15g" % value


def _escape(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def build_xml(rings, width, height, name, index=1, invert=False, blur=0.0):
    """The rings as a <Masks> document, in the same shape Hippotizer writes.

    One unit is one pixel and the origin is the middle of the image. xres and
    yres are written as 1024x768 because that is what Hippotizer always puts
    there, whatever size the mask was drawn against.
    """
    half_w, half_h = width / 2.0, height / 2.0
    lines = ["<Masks>",
             '<Mask index="%s" name="%s" invert="%s" alpha="false" Blur="%s" '
             'showpoints="false" xres="%d" yres="%d">'
             % (index, _escape(name), "true" if invert else "false",
                _number(blur), DECL_W, DECL_H)]

    for ring in rings:
        lines.append('<Shape Level="255" guid="{%s}" angle="0" locked="false" Outline="false" '
                     'linewidth="1" gamma="%s" infill="false" hvmix="127" hblend="127" '
                     'vblend="127">' % (str(uuid.uuid4()).upper(), _number(GAMMA)))
        for x, y in ring:
            # A corner node keeps both handles on the point itself, which is
            # how Hippotizer writes a straight segment (Type="1").
            px, py = _number(x - half_w), _number(y - half_h)
            lines.append(
                '<Node PosX="%s" PosY="%s" InHandleX="%s" InHandleY="%s" OutHandleX="%s" '
                'OutHandleY="%s" Type="1" FeatherPosX="%s" FeatherPosY="%s" '
                'FeatherInHandleX="%s" FeatherInHandleY="%s" FeatherOutHandleX="%s" '
                'FeatherOutHandleY="%s" FeatherType="1"/>'
                % (px, py, px, py, px, py, px, py, px, py, px, py))
        lines.append("</Shape>")

    lines.append("</Mask>")
    lines.append("</Masks>")
    return "\n".join(lines) + "\n"


# --- the whole job ---------------------------------------------------------

def mask_path_for(png):
    """Where convert will write, without doing anything."""
    return os.path.join(os.path.dirname(os.path.abspath(png)), "Masks.xml")


def convert(png, threshold=THRESHOLD, epsilon=SIMPLIFY, invert_input=False,
            invert_mask=False):
    """Traces `png` and writes Masks.xml into the same folder as the image.

    An existing Masks.xml is moved aside to Masks.backup.xml rather than
    being replaced -- but only once, so a hand-written file is never lost and
    reconverting the same folder never nags.
    """
    png = os.path.abspath(png)
    if not os.path.isfile(png):
        raise MaskError("%s is not there any more." % os.path.basename(png))

    width, height, alpha = read_alpha(png)
    rings = trace(alpha, width, height, threshold, invert_input, epsilon)
    name = os.path.splitext(os.path.basename(png))[0]
    text = build_xml(rings, width, height, name, invert=invert_mask)

    xml = mask_path_for(png)
    backup = None
    if os.path.exists(xml):
        candidate = os.path.join(os.path.dirname(xml), "Masks.backup.xml")
        if not os.path.exists(candidate):
            os.replace(xml, candidate)
            backup = candidate
    with open(xml, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

    return {"png": png, "xml": xml, "backup": backup, "width": width, "height": height,
            "shapes": len(rings), "points": sum(len(r) for r in rings)}


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip().splitlines()[0])
        print("\nusage: %s image.png [more.png ...]" % os.path.basename(argv[0]))
        return 1
    failed = 0
    for png in argv[1:]:
        try:
            r = convert(png)
        except MaskError as exc:
            print("%s: %s" % (os.path.basename(png), exc))
            failed = 1
            continue
        print("%s -> %s  (%d shape(s), %d point(s), from %dx%d)"
              % (os.path.basename(png), r["xml"], r["shapes"], r["points"],
                 r["width"], r["height"]))
        if not r["shapes"]:
            print("   note: nothing in it was solid enough to trace.")
    return failed


if __name__ == "__main__":
    sys.exit(main(sys.argv))
