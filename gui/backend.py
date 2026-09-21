"""backend.py -- the one operation the window performs, and nothing else.

Kept apart from mask_gui.py so it can be tested without a display: this
module imports nothing but the standard library. tests/test_backend.py runs
it headless.

It never reimplements a conversion -- it shells out to build/png2mask, the
same binary a developer would run by hand, so the window and a build script
cannot disagree.
"""

import os
import re
import struct
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ToolError(Exception):
    """png2mask ran and failed. The message is what it printed, unedited."""


def tool_path(name="png2mask", root=REPO_ROOT):
    return os.path.join(root, "build", name + (".exe" if os.name == "nt" else ""))


def is_built(root=REPO_ROOT):
    return os.path.isfile(tool_path("png2mask", root))


def mask_path_for(png):
    """Where convert_beside will write, without doing anything."""
    return os.path.join(os.path.dirname(os.path.abspath(png)), "Masks.xml")


def convert_beside(png, root=REPO_ROOT):
    """Traces `png` and writes Masks.xml into the same folder as the image.

    Nothing is configurable. The image is taken at face value: whatever size
    it is, is the size the mask is for, and one mask unit is one pixel at
    that size.

    An existing Masks.xml is moved aside to Masks.backup.xml rather than
    asking -- but only once, so a hand-written file is never lost and
    reconverting the same folder never nags.
    """
    png = os.path.abspath(png)
    if not os.path.isfile(png):
        raise ToolError("%s is not there any more." % os.path.basename(png))

    width, height = png_size(png)
    xml = mask_path_for(png)
    backup = None
    if os.path.exists(xml):
        candidate = os.path.join(os.path.dirname(xml), "Masks.backup.xml")
        if not os.path.exists(candidate):
            os.replace(xml, candidate)
            backup = candidate

    if not is_built(root):
        raise ToolError("the tools are not built. Run 'make' in %s first." % root)
    name = os.path.splitext(os.path.basename(png))[0]
    proc = subprocess.run([tool_path("png2mask", root), png, xml, "--name", name],
                          cwd=root, capture_output=True, text=True)
    output = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        raise ToolError(output or "png2mask exited %d" % proc.returncode)

    shapes, nodes = parse_counts(output)
    return {"png": png, "xml": xml, "backup": backup, "width": width, "height": height,
            "shapes": shapes, "nodes": nodes, "raw": output}


def png_size(path):
    """Width and height from a PNG's IHDR, without decoding the image."""
    with open(path, "rb") as f:
        head = f.read(24)
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ToolError("%s is not a PNG file." % os.path.basename(path))
    return struct.unpack(">II", head[16:24])


def parse_counts(output):
    """Shape and point counts out of png2mask's summary line."""
    shapes = re.search(r"(\d+) shape\(s\)", output)
    nodes = re.search(r"(\d+) node\(s\)", output)
    return (int(shapes.group(1)) if shapes else 0,
            int(nodes.group(1)) if nodes else 0)
