"""backend.py -- everything the GUI does that is not drawing.

Kept apart from mask_gui.py on purpose: this module imports nothing but the
standard library (no tkinter), so it runs and is tested headlessly, on a
build machine or over SSH, while the window code stays thin enough to read
in one sitting. tests/test_backend.py exercises it.

The GUI never reimplements any conversion -- it shells out to the same
binaries a developer would run by hand, so what you see in the window and
what you get in a build script cannot diverge.
"""

import os
import re
import struct
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPPINGS = ("native", "stretch", "fit")

# Plain-English one-liners for the mapping dropdown. The GUI shows these;
# the CLI flag value is the dict key.
MAPPING_HELP = {
    "native": "1 unit = 1 pixel at the image's own size (current best guess)",
    "stretch": "Units fill the declared 1024x768 box, squashed to fit",
    "fit": "Units fill the declared box, aspect kept, letterboxed",
}


class ToolError(Exception):
    """A tool ran and failed. The message is what it printed, unedited."""


def build_dir(root=REPO_ROOT):
    return os.path.join(root, "build")


def tool_path(name, root=REPO_ROOT):
    exe = name + (".exe" if os.name == "nt" else "")
    return os.path.join(build_dir(root), exe)


def missing_tools(root=REPO_ROOT):
    """Which binaries the GUI needs but cannot find. Empty list means ready."""
    needed = ("png2mask", "mask2png", "mask_diff", "gen_testset", "bounds_report")
    return [n for n in needed if not os.path.isfile(tool_path(n, root))]


def run(name, args, root=REPO_ROOT):
    """Runs one tool. Returns its combined output; raises ToolError on failure."""
    path = tool_path(name, root)
    if not os.path.isfile(path):
        raise ToolError("%s is not built yet. Run 'make' in %s first." % (name, root))
    proc = subprocess.run([path] + [str(a) for a in args],
                          cwd=root, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0 and name != "mask_diff":
        raise ToolError(out.strip() or ("%s exited %d" % (name, proc.returncode)))
    return out.strip()


# --- individual operations -------------------------------------------------

def png_to_mask(png, xml, mapping="native", threshold=128, simplify=1.0,
                invert_input=False, invert_mask=False, append=False,
                name=None, root=REPO_ROOT):
    args = [png, xml, "--map", mapping, "--threshold", int(threshold), "--simplify", simplify]
    if invert_input:
        args.append("--invert-input")
    if invert_mask:
        args.append("--invert-mask")
    if append:
        args.append("--append")
    if name:
        args += ["--name", name]
    return run("png2mask", args, root)


def mask_to_png(xml, out_dir, width, height, mapping="native", index=None, root=REPO_ROOT):
    args = [xml, out_dir, "--res", "%dx%d" % (width, height), "--map", mapping]
    if index:
        args += ["--mask", index]
    return run("mask2png", args, root)


def compare(png_a, png_b, tolerance=0, diff_out=None, root=REPO_ROOT):
    """Compares two PNGs. Returns a dict, not a string, so the GUI can colour it."""
    args = [png_a, png_b, "--tolerance", int(tolerance)]
    if diff_out:
        args += ["--out", diff_out]
    out = run("mask_diff", args, root)
    return parse_diff(out)


def generate_testset(out_dir, invert_mask=False, root=REPO_ROOT):
    os.makedirs(out_dir, exist_ok=True)
    args = [out_dir]
    if invert_mask:
        args.append("--invert-mask")
    return run("gen_testset", args, root)


def bounds(xml, width=None, height=None, all_maps=True, root=REPO_ROOT):
    args = [xml]
    if width and height:
        args += ["--res", "%dx%d" % (width, height)]
    if all_maps:
        args.append("--all-maps")
    return run("bounds_report", args, root)


def round_trip(png, work_dir, mapping="native", threshold=128, root=REPO_ROOT):
    """PNG -> mask -> PNG -> mask -> PNG, then compares the two renders.

    Comparing the first render against the ORIGINAL would always show a
    difference, because a hard threshold throws away the source's antialiased
    edge. What actually matters is that a mask, once rendered, survives the
    trip unchanged -- so the check is run twice and the two renders compared.
    """
    w, h = png_size(png)
    os.makedirs(work_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(png))[0]
    safe = re.sub(r"[ /\\:]", "_", base)

    pass1 = os.path.join(work_dir, "pass1")
    pass2 = os.path.join(work_dir, "pass2")
    os.makedirs(pass1, exist_ok=True)
    os.makedirs(pass2, exist_ok=True)

    xml_a = os.path.join(work_dir, "roundtrip_a.xml")
    xml_b = os.path.join(work_dir, "roundtrip_b.xml")

    log = [png_to_mask(png, xml_a, mapping, threshold, simplify=0, name=base, root=root)]
    log.append(mask_to_png(xml_a, pass1, w, h, mapping, root=root))
    rendered1 = os.path.join(pass1, safe + ".png")
    log.append(png_to_mask(rendered1, xml_b, mapping, threshold, simplify=0, name=base, root=root))
    log.append(mask_to_png(xml_b, pass2, w, h, mapping, root=root))
    rendered2 = os.path.join(pass2, safe + ".png")

    result = compare(rendered1, rendered2, root=root)
    result["log"] = "\n".join(log)
    result["render"] = rendered1
    result["mask_xml"] = xml_a
    result["source_vs_render"] = compare(png, rendered1, root=root)
    return result


# --- helpers ---------------------------------------------------------------

def png_size(path):
    """Width and height from a PNG's IHDR, without decoding the image."""
    with open(path, "rb") as f:
        head = f.read(24)
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ToolError("%s is not a PNG file." % os.path.basename(path))
    return struct.unpack(">II", head[16:24])


def parse_diff(output):
    """Turns mask_diff's line into fields. Unparseable output is not an error --
    it still comes back under 'raw' so the GUI can show it verbatim."""
    # "MATCH" is a substring of "MISMATCH", so the negative has to be ruled
    # out first and the positive anchored to the start of its own line.
    size_mismatch = "DIFFERENT SIZE" in output
    mismatch = size_mismatch or "MISMATCH" in output
    matched = (not mismatch) and re.search(r"^MATCH\b", output, re.M) is not None
    result = {"raw": output, "match": matched, "size_mismatch": size_mismatch,
              "max_diff": None, "mean_diff": None, "pixels_over": None, "percent": None}
    m = re.search(r"max_diff=(\d+)\s+mean_diff=([\d.eE+-]+)\s+"
                  r"pixels_over_tolerance=(\d+)\s+\(([\d.eE+-]+)%\)", output)
    if m:
        result["max_diff"] = int(m.group(1))
        result["mean_diff"] = float(m.group(2))
        result["pixels_over"] = int(m.group(3))
        result["percent"] = float(m.group(4))
    return result


def verdict(result):
    """A sentence a person can act on, plus which status colour to show it in."""
    if result.get("size_mismatch"):
        return "The two images are different sizes, so they cannot be compared.", "err"
    if result.get("match"):
        return "They cancel exactly - every pixel matches.", "ok"
    pct = result.get("percent")
    if pct is None:
        return "Could not read the comparison result.", "warn"
    if pct < 1.0:
        return ("Nearly identical - %.3f%% of pixels differ, which is the "
                "antialiased edge a hard threshold cannot keep." % pct), "warn"
    return ("They do not cancel - %.2f%% of pixels differ. The mapping is "
            "probably wrong for this image." % pct), "err"


def default_testset_dir(root=REPO_ROOT):
    return os.path.join(root, "testset")


if __name__ == "__main__":
    # Enough of a CLI to sanity-check the module without the window.
    missing = missing_tools()
    print("build dir:", build_dir())
    print("missing tools:", missing or "none")
    if len(sys.argv) > 1:
        print(png_size(sys.argv[1]))
