# PNG to Hippotizer mask

Turns a PNG into a Hippotizer `Masks.xml`. Proof of concept — two Python
files, standard library only. Nothing to install, nothing to build.

```sh
python3 mask_gui.py                        # the window
python3 maskmaker.py a.png b.png c.png     # or straight from a shell
```

On Windows, double-click **`Make Mask.bat`**.

Pick a PNG; a `Masks.xml` is written into the same folder as the image.

## The mask is whatever is not see-through

Only the alpha channel is read. The colours are never looked at.

That matters more than it sounds: the three shapes in `testset/Shapes/` are
red, green and blue, and all three are *darker* than mid-grey. Anything going
on brightness would have found almost nothing — or, on a dark shape over a
light background, the exact inverse of what was drawn. Alpha is unambiguous.

So: hide the background layer and export **PNG-24 with Transparency ticked**.

## How it works

`maskmaker.py`, top to bottom:

| | |
|---|---|
| `read_alpha` | Pull the alpha channel out of the PNG. |
| `boundary_steps` | Walk the edge between solid and see-through pixels, one step at a time. |
| `join_into_rings` | Chain those steps end to end into closed rings. |
| `drop_points_on_a_line` · `smooth` | Throw away points that add nothing. |
| `masks_xml` | Write the rings out as `<Shape>` elements. |

The boundary runs along the grid lines *between* pixels, not through their
centres, so the shape covers exactly the pixels that were solid. Outer edges
and the holes inside them come out wound opposite ways, which is what lets a
hole cut itself out when the shape is filled.

About a second for a 1920×1080 image.

## Being a proof of concept

It checks nothing. It expects an 8-bit RGBA PNG that is not interlaced —
what "export PNG-24 with transparency" gives you — and will fall over on
anything else rather than explain itself. Earlier versions handled 16-bit,
greyscale+alpha, palettes and sub-byte depths, and said something useful
about each failure; that is all in git history if it is ever wanted.

Traced shapes are corner nodes only. Hippotizer's format carries Bezier
handles and a parallel feather path per node, and a shape traced from a
raster has nothing to put in them, so they get the point itself. `Blur`,
`hvmix`/`hblend`/`vblend` and `infill` are written as the values Hippotizer
writes, never computed.

## What a mask coordinate is worth

One unit is one pixel at the image's own resolution, origin in the middle of
the image. Every `Masks.xml` Hippotizer writes declares `xres="1024"
yres="768"` whatever the artwork was drawn against, so that is a label, not a
scale. `docs/COORDINATES.md` has the evidence, and the test files for
settling it against Hippotizer itself.

## Files

| | |
|---|---|
| `maskmaker.py` | The conversion. |
| `mask_gui.py` | One button. |
| `tests/test.py` | The checks. |
| `testset/Shapes/` | Real artwork: three coloured shapes on transparency. |
| `Ref/Star for Mask.png` | A traced star, for a shape with many points. |
| `Mask Data/Masks.xml` | A real Hippotizer file. The reference for the format. |
| `testset/*.png` | The coordinate test set — see `docs/COORDINATES.md`. |
