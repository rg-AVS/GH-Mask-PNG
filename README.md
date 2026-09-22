# PNG to Hippotizer mask

Turns a PNG into a Hippotizer `Masks.xml`. That is the only thing here.

**The mask is whatever is not see-through.** Only the alpha channel is read;
the colours are never looked at, and a PNG with no transparency is refused
with a message saying what to do about it rather than guessed at.

That is not fussiness. Artwork is usually not white -- the three shapes in
`testset/Shapes/` are red, green and blue, all darker than mid-grey -- so
anything going on brightness would find almost nothing, or, on a dark shape
over a light background, the exact inverse of what was drawn. Alpha is
unambiguous.

## Using it

Nothing to build and nothing to install. With Python 3:

```sh
python3 gui/mask_gui.py                        # the window
python3 gui/maskmaker.py a.png b.png c.png     # or straight from a shell
```

On Windows, double-click **`gui/Make Mask.bat`**.

The window is one button and one line of feedback. Pick a PNG; a `Masks.xml`
is written into the same folder as the image, and it is ready for the next
one immediately. A `Masks.xml` already in that folder is moved aside to
`Masks.backup.xml` rather than replaced, and only the first time, so a
hand-written file is never lost and reconverting a folder never nags.

The window needs tkinter, which ships with python.org and Windows Python
(`apt install python3-tk` on Debian/Ubuntu). `maskmaker.py` does not need
even that.

## The C++ version

The same conversion, for dropping into a product. Plain C++17, no external
dependencies -- no libpng, no zlib, no XML library.

```sh
make
./build/png2mask artwork.png Masks.xml
```

```
src/
  common/checksums    CRC-32 and Adler-32, for verifying a PNG as it is read
  png/png_reader      PNG -> pixels, and readMaskPng -> the alpha channel
  mask/mask_trace     alpha -> contours -> shapes. The conversion.
  mask/mask_model     the Masks.xml schema, and writing it
tools/png2mask.cpp    the CLI, thin glue over the above
```

`png2mask --help` lists its four flags. `mask_trace.h` is the file to read
first.

### Why it exists twice

`gui/maskmaker.py` and `src/mask/mask_trace.cpp` do the same job, which is
normally a smell worth naming. The C++ is what ships inside the product; the
Python is what an operator runs on a show laptop that has no compiler.
`tests/test_maskmaker.py` holds the two together -- same rings, point for
point -- and skips that half if `build/` is empty, so the tests pass on a
machine that has never run `make`.

## What a mask coordinate is worth

One unit is one pixel at the image's own resolution, with the origin in the
middle of the image.

Every `Masks.xml` Hippotizer writes declares `xres="1024" yres="768"`
whatever the artwork was drawn against, so that is a label and not a scale.
Two other readings of it were implemented and tested against the one real
sample; both put its shape off the canvas, and only this one keeps a square
square. `docs/COORDINATES.md` has the evidence and the test files for
settling it against Hippotizer itself, and the code for the other two is in
git history if it is ever needed.

## What is still guessed

- **Curves.** Traced shapes are corner nodes only. Hippotizer's format
  carries Bezier handles and a parallel feather path per node; a raster has
  no curve or feather information to put in them, so the writer fills them
  with the point itself. `mask_model.h` says what was left out.
- **`Blur`**, **`hvmix`/`hblend`/`vblend`**, **`infill`** -- written as the
  values Hippotizer writes, never computed.

## Testing

```sh
./tests/run_tests.sh       # or: make test
```

## Files

| | |
|---|---|
| `testset/Shapes/` | Real artwork: three coloured shapes on transparency. |
| `Ref/Star for Mask.png` | A traced star, for a shape with many points. |
| `Mask Data/Masks.xml` | A real Hippotizer file. The reference for the format. |
| `testset/*.png` | The coordinate test set -- see `docs/COORDINATES.md`. |
