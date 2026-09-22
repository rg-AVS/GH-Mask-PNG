# What is a mask coordinate worth?

## The problem

Every `Masks.xml` Hippotizer writes declares the same canvas:

```xml
<Mask index="1" name="LiveMask" ... xres="1024" yres="768">
```

`Mask Data/Masks.xml` says `1024x768`, and the mask it describes was drawn
against a 1920x1080 output. So `xres`/`yres` are not the resolution the mask
was made at — they look like a fixed editor-canvas label.

Node positions are signed and centred on zero:

```xml
<Node PosX="-350.20379638671875" PosY="-434.8330078125" .../>
```

So the origin is the centre of *something*. What is not written down anywhere
is the scale: how many of those units span the frame.

## The three candidates

All three put the origin at the centre of the image with +X right and +Y down.
They differ only in the scale factor, which is the whole of `mask_space.cpp`:

| `--map` | Units per pixel | One unit is |
|---|---|---|
| `native` | `1` | one pixel at the image's own resolution |
| `stretch` | `1024/width`, `768/height` | 1/1024th of the width, 1/768th of the height |
| `fit` | `min(1024/width, 768/height)` on both axes | the same, aspect preserved |

(If a test comes back mirrored top-to-bottom, +Y points up instead. Every tool
takes `--yflip` for that, and the mapping is otherwise unchanged.)

## What the one real sample already tells us

`Mask Data/Masks.xml` holds one rectangle, drawn against 1920x1080:

```sh
./build/bounds_report "Mask Data/Masks.xml" --res 1920x1080 --all-maps
```

```
map=native   canvas in units x:[-960,960]  y:[-540,540]   -> inside
map=stretch  canvas in units x:[-512,512]  y:[-384,384]   -> partial
map=fit      canvas in units x:[-512,512]  y:[-288,288]   -> partial
```

Two things point the same way:

1. **Only `native` puts the shape on the canvas.** Under `stretch` and `fit`
   the rectangle hangs off the top and bottom edges. A mask someone drew in
   an editor should be inside the frame they drew it in.

2. **The rectangle is square in raw units** — 809.06 wide by 809.06 high.
   Under `native` that is a 809x809 pixel square on a 1920x1080 frame, which
   is what drawing a square gets you. Under `stretch` the same numbers become
   1517 x 1138 pixels on screen, which is not square, so a square in the
   editor would have had to come out as 809 x 1079 in the file. It did not.

That is why `native` is the default everywhere. It is still inference from a
single shape in a single file, which is what the test set is for.

## Settling it

`make testset` (or the GUI's **Test set** tab) writes nine PNGs and one
`Masks.xml`:

```
01_1920x1080_native   02_1920x1080_stretch   03_1920x1080_fit
04_3840x1080_native   05_3840x1080_stretch   06_3840x1080_fit
07_1024x768_native    08_1024x768_stretch    09_1024x768_fit
```

The same shape at three resolutions, each written out under all three
mappings. Image and mask are generated from one set of coordinates, so a
mismatch can only come from the mapping.

The PNGs are a white shape on a see-through background -- solid is mask,
see-through is not -- because that is the only thing the converter reads.

The shape is asymmetric on purpose — a bite out of the **top-left** corner, a
lone square hard into the **bottom-left**, and a square hole dead centre — so
a mirrored or rotated result reads as obviously wrong rather than as a near
miss. The hole checks that ring winding survives; the corner square checks
scale far from the origin, where an error is biggest.

To run it:

1. Load PNG *NN* as media on a layer running at that PNG's own resolution.
2. Apply the `<Mask>` of the same name from `testset/Masks.xml`.
3. Note which pairs line up pixel for pixel.

Expected outcomes:

| What you see | What it means |
|---|---|
| Exactly one mapping lines up at every resolution | That is the mapping. Make it the default in `mask_space.cpp` and delete the other two. |
| All three line up at 1024x768 only | Expected — at the declared size all three scales are 1. The other two resolutions are the ones that discriminate. |
| One lines up but inverted (shape survives where it should vanish) | Geometry is right, mask sense is flipped. Regenerate with `--invert-mask`. |
| One lines up but mirrored top to bottom | Geometry and scale are right, +Y points up. Regenerate with `--yflip`. |
| None line up at any resolution | The mapping is not a centred scale at all — likely an offset, or units relative to something other than the frame. Send back a screenshot of one and `bounds_report --all-maps` output. |

Before any of that, `make test` proves the nine pairs cancel inside this
toolkit, so anything that does not cancel in Hippotizer is a finding about
Hippotizer and not a bug here.

## Once it is known

Change the default in `src/mask/mask_space.h`, drop the modes that turned out
to be wrong, and the `--map` flag can go with them. Nothing else in the
project needs touching — `mask_space` is the only file that knows the mapping,
and both directions call it.
