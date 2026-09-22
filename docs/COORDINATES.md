# What is a mask coordinate worth?

## What the code does

One unit is one pixel at the image's own resolution, and the origin is the
middle of the image. That is the whole mapping, and it lives in one line of
`maskmaker.py` (`masks_xml`, subtracting half the width and height).

## Why that, and not something else

Every `Masks.xml` Hippotizer writes declares the same canvas:

```xml
<Mask index="1" name="LiveMask" ... xres="1024" yres="768">
```

`Mask Data/Masks.xml` says `1024x768`, and the mask it describes was drawn
against a 1920x1080 output. So `xres`/`yres` are not the size the mask was
made at -- they look like a fixed editor-canvas label. Node positions are
signed and centred on zero, so the origin is the middle of *something*; what
was never written down is the scale.

Three readings were implemented and tested. All three put the origin at the
centre with +X right and +Y down, and differ only in the scale:

| | Units per pixel |
|---|---|
| **native** (kept) | `1` |
| stretch | `1024/width`, `768/height` |
| fit | `min(1024/width, 768/height)` on both axes |

Two things pointed the same way on the one real sample:

1. **Only `native` puts the shape on the canvas.** Under the other two the
   rectangle hangs off the top and bottom edges. A mask someone drew in an
   editor should be inside the frame they drew it in.

2. **The rectangle is square in raw units** -- 809.06 by 809.06. Under
   `native` that is an 809x809 pixel square on a 1920x1080 frame, which is
   what drawing a square gets you. Under `stretch` the same numbers are
   1517 x 1138 pixels on screen, which is not square: a square in the editor
   would have had to come out as 809 x 1079 in the file. It did not.

So `native` is what the code does. The other two are in git history.

## Settling it properly

That is still inference from one shape in one file. `testset/` holds nine
PNGs and a `Masks.xml` for checking it against Hippotizer itself -- the same
shape at 1920x1080, 3840x1080 and 1024x768, written out under all three
readings:

```
01_1920x1080_native   02_1920x1080_stretch   03_1920x1080_fit
04_3840x1080_native   05_3840x1080_stretch   06_3840x1080_fit
07_1024x768_native    08_1024x768_stretch    09_1024x768_fit
```

1. Load PNG *NN* as media on a layer running at that PNG's own resolution.
2. Apply the `<Mask>` of the same name from `testset/Masks.xml`.
3. Note which pairs line up pixel for pixel.

The shape is asymmetric on purpose -- a bite out of the **top-left** corner,
a lone square hard into the **bottom-left**, a square hole dead centre -- so
a mirrored or rotated result reads as obviously wrong rather than as a near
miss.

| What you see | What it means |
|---|---|
| The three `native` files line up | The code is right. Nothing to do. |
| All three line up at 1024x768 only | Expected -- at the declared size all three scales are 1. The other resolutions are what discriminate. |
| A `stretch` or `fit` file lines up instead | Take that mapping back out of git history and make it the one. |
| One lines up but inverted | Geometry is right, only the mask sense is flipped: `invert="true"` on the `<Mask>`. |
| One lines up but mirrored top to bottom | Scale is right, +Y points up: negate the Y in `masks_xml`. |
| None line up anywhere | The mapping is not a centred scale at all. Send back a screenshot of one. |
