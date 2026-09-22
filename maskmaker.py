#!/usr/bin/env python3
"""Turn a PNG into a Hippotizer Masks.xml.

Proof of concept. Pure standard library -- nothing to install, nothing to
build. Run it from the window (mask_gui.py) or straight from a shell:

    python3 maskmaker.py artwork.png

The mask is written as Masks.xml into the same folder as the image.

HOW IT WORKS
  1. Read the PNG's alpha channel. Only alpha -- the colours are never
     looked at, because artwork is usually not white and going on brightness
     would find the wrong thing, or the exact inverse of it.
  2. Anything at least half opaque is inside the mask.
  3. Walk the boundary between inside and outside pixels, along the grid
     lines BETWEEN them, and join those steps into closed rings.
  4. Throw away points that sit on a straight line, then smooth the rest.
  5. Write the rings out as <Shape> elements of corner nodes.

One mask unit is one pixel, and the origin is the middle of the image.
Hippotizer writes xres="1024" yres="768" into every file whatever the
artwork was drawn against, so that is a label, not a scale -- see
docs/COORDINATES.md.

Being a proof of concept, it checks nothing. It expects an 8-bit RGBA PNG
that is not interlaced, which is what "export PNG-24 with transparency" gives
you, and it will fall over on anything else rather than explain itself.
"""

import os
import struct
import sys
import uuid
import zlib

THRESHOLD = 128    # alpha at or above this is inside the mask
SMOOTHING = 1.0    # how far a traced edge may be straightened, in pixels
MIN_AREA = 4       # ignore traced specks smaller than this many pixels


# --- reading the PNG -------------------------------------------------------

def read_alpha(path):
    """Returns (width, height, one alpha byte per pixel)."""
    data = open(path, "rb").read()

    # A PNG is an 8-byte signature then a list of chunks, each one a length,
    # a four-letter tag, the data, and a checksum we do not need to look at.
    pixel_data = bytearray()
    at = 8
    while at < len(data):
        length = struct.unpack(">I", data[at:at + 4])[0]
        tag = data[at + 4:at + 8]
        if tag == b"IHDR":
            width, height = struct.unpack(">II", data[at + 8:at + 16])
        elif tag == b"IDAT":
            pixel_data += data[at + 8:at + 8 + length]
        at += 12 + length

    return width, height, unfilter_alpha(zlib.decompress(bytes(pixel_data)), width, height)


def paeth(left, up, up_left):
    """Of the three neighbours, the one closest to left + up - up_left."""
    guess = left + up - up_left
    to_left, to_up, to_up_left = (abs(guess - left), abs(guess - up),
                                  abs(guess - up_left))
    if to_left <= to_up and to_left <= to_up_left:
        return left
    return up if to_up <= to_up_left else up_left


def unfilter_alpha(raw, width, height):
    """Undoes PNG row filtering, for the alpha channel only.

    Each row of `raw` starts with a filter byte saying how that row was
    encoded, then width * 4 bytes of R, G, B, A. Filtering only ever looks
    back one whole pixel (four bytes) or straight up one row, so each of the
    four channels is its own separate little stream -- which means we can
    pull out every fourth byte and undo the filtering on just those. Doing
    all four channels would be four times the work for three we throw away.
    """
    stride = width * 4
    alpha = bytearray(width * height)
    above = bytearray(width)
    at = 0

    for y in range(height):
        kind = raw[at]
        row = bytearray(raw[at + 1:at + 1 + stride][3::4])   # every fourth byte
        at += 1 + stride

        for x in range(width):
            left = row[x - 1] if x else 0
            up = above[x]
            up_left = above[x - 1] if x else 0
            if kind == 1:                                     # Sub
                row[x] = (row[x] + left) & 255
            elif kind == 2:                                   # Up
                row[x] = (row[x] + up) & 255
            elif kind == 3:                                   # Average
                row[x] = (row[x] + (left + up) // 2) & 255
            elif kind == 4:                                   # Paeth
                row[x] = (row[x] + paeth(left, up, up_left)) & 255
            # kind == 0 is None: the byte is already the value.

        alpha[y * width:(y + 1) * width] = row
        above = row

    return alpha


# --- finding the shapes ----------------------------------------------------

def boundary_steps(alpha, width, height):
    """Every one-pixel step along the edge between inside and outside.

    Each step runs along a grid line BETWEEN pixels, not through their
    centres, so the shape ends up covering exactly the pixels that were
    inside. The four steps below are wound so that the inside of the mask is
    always on the right of the direction of travel. That is what makes an
    outer edge and a hole inside it wind opposite ways, which in turn is what
    lets the hole cut itself out when the shape is filled.
    """
    steps = []
    for y in range(height):
        row = y * width
        for x in range(width):
            if alpha[row + x] < THRESHOLD:
                continue
            if y == 0 or alpha[row - width + x] < THRESHOLD:          # nothing above
                steps.append(((x, y), (x + 1, y)))
            if x == width - 1 or alpha[row + x + 1] < THRESHOLD:      # nothing right
                steps.append(((x + 1, y), (x + 1, y + 1)))
            if y == height - 1 or alpha[row + width + x] < THRESHOLD:  # nothing below
                steps.append(((x + 1, y + 1), (x, y + 1)))
            if x == 0 or alpha[row + x - 1] < THRESHOLD:              # nothing left
                steps.append(((x, y + 1), (x, y)))
    return steps


def join_into_rings(steps):
    """Chains the boundary steps end to end into closed rings.

    Follow a step to where it ends, find a step that starts there, repeat
    until we come back to where we started. Where two shapes touch corner to
    corner there are two steps leaving the same point and we take whichever
    comes first; both choices cover the same pixels.
    """
    leaving = {}
    for start, end in steps:
        leaving.setdefault(start, []).append(end)

    rings = []
    for first in list(leaving):
        while leaving.get(first):
            ring = []
            point = first
            while leaving.get(point):
                ring.append(point)
                point = leaving[point].pop()
            if len(ring) >= 4:
                rings.append(ring)
    return rings


def area(ring):
    """Twice the enclosed area, halved. Negative if the ring winds the other
    way round, which is how a hole tells itself apart from its parent."""
    total = 0
    for i, (x, y) in enumerate(ring):
        next_x, next_y = ring[(i + 1) % len(ring)]
        total += x * next_y - next_x * y
    return total / 2.0


# --- tidying the shapes ----------------------------------------------------

def drop_points_on_a_line(ring):
    """Removes points sitting exactly between their two neighbours.

    Loses nothing, and does most of the work: a traced rectangle arrives as
    one point per pixel of its perimeter and leaves as four corners.
    """
    kept = []
    for i, (x, y) in enumerate(ring):
        before_x, before_y = ring[i - 1]
        after_x, after_y = ring[(i + 1) % len(ring)]
        # Cross product: zero means the three points are in a straight line.
        if (x - before_x) * (after_y - before_y) - (y - before_y) * (after_x - before_x):
            kept.append((x, y))
    return kept


def distance_to_line(point, start, end):
    px, py = point
    ax, ay = start
    bx, by = end
    dx, dy = bx - ax, by - ay
    length = (dx * dx + dy * dy) ** 0.5
    if length < 1e-9:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    return abs(dy * (px - ax) - dx * (py - ay)) / length


def straighten(points, tolerance):
    """Douglas-Peucker on an open run of points.

    Keep the two ends. Find the point furthest from the line between them --
    if it is further than the tolerance, keep it and repeat on each half;
    if it is not, every point between the ends is close enough to the
    straight line to throw away.
    """
    if len(points) < 3:
        return points
    furthest = max(range(1, len(points) - 1),
                   key=lambda i: distance_to_line(points[i], points[0], points[-1]))
    if distance_to_line(points[furthest], points[0], points[-1]) <= tolerance:
        return [points[0], points[-1]]
    return (straighten(points[:furthest + 1], tolerance)[:-1] +
            straighten(points[furthest:], tolerance))


def smooth(ring, tolerance):
    """Douglas-Peucker on a closed ring.

    A ring has no ends to hold on to, so cut it at two opposite points and
    straighten each half as an open run.
    """
    ring = drop_points_on_a_line(ring)
    if tolerance <= 0 or len(ring) < 4:
        return ring

    opposite = max(range(1, len(ring)),
                   key=lambda i: (ring[i][0] - ring[0][0]) ** 2 +
                                 (ring[i][1] - ring[0][1]) ** 2)
    first_half = straighten(ring[:opposite + 1], tolerance)
    second_half = straighten(ring[opposite:] + [ring[0]], tolerance)
    return first_half[:-1] + second_half[:-1]


def trace(alpha, width, height):
    """The masked areas of an image, as rings of points in pixel coordinates."""
    rings = []
    for ring in join_into_rings(boundary_steps(alpha, width, height)):
        if abs(area(ring)) >= MIN_AREA:
            rings.append(smooth(ring, SMOOTHING))
    return rings


# --- writing Masks.xml -----------------------------------------------------

def masks_xml(rings, width, height, name):
    """The rings as a <Masks> document, in the shape Hippotizer writes.

    Every node is a corner: Hippotizer's format carries Bezier handles and a
    parallel feather path as well, and a shape traced from a raster has
    nothing to put in them, so they all get the point itself and Type="1".
    """
    half_width, half_height = width / 2.0, height / 2.0
    out = ["<Masks>",
           f'<Mask index="1" name="{name}" invert="false" alpha="false" Blur="0"'
           f' showpoints="false" xres="1024" yres="768">']

    for ring in rings:
        guid = str(uuid.uuid4()).upper()
        out.append(f'<Shape Level="255" guid="{{{guid}}}" angle="0" locked="false"'
                   f' Outline="false" linewidth="1" gamma="2.2" infill="false"'
                   f' hvmix="127" hblend="127" vblend="127">')
        for x, y in ring:
            # "%.15g" is how Hippotizer's own files are written.
            px = "%.15g" % (x - half_width)
            py = "%.15g" % (y - half_height)
            out.append(
                f'<Node PosX="{px}" PosY="{py}" InHandleX="{px}" InHandleY="{py}"'
                f' OutHandleX="{px}" OutHandleY="{py}" Type="1"'
                f' FeatherPosX="{px}" FeatherPosY="{py}"'
                f' FeatherInHandleX="{px}" FeatherInHandleY="{py}"'
                f' FeatherOutHandleX="{px}" FeatherOutHandleY="{py}" FeatherType="1"/>')
        out.append("</Shape>")

    out += ["</Mask>", "</Masks>", ""]
    return "\n".join(out)


# --- the whole job ---------------------------------------------------------

def convert(png):
    """Traces `png` and writes Masks.xml into the same folder as the image."""
    width, height, alpha = read_alpha(png)
    rings = trace(alpha, width, height)

    name = os.path.splitext(os.path.basename(png))[0]
    path = os.path.join(os.path.dirname(os.path.abspath(png)), "Masks.xml")
    with open(path, "w", newline="\n") as f:
        f.write(masks_xml(rings, width, height, name))

    return {"xml": path, "width": width, "height": height,
            "shapes": len(rings), "points": sum(len(r) for r in rings)}


if __name__ == "__main__":
    for image in sys.argv[1:]:
        r = convert(image)
        print(f"{os.path.basename(image)} -> {r['xml']}  "
              f"({r['shapes']} shape(s), {r['points']} point(s), "
              f"from {r['width']}x{r['height']})")
