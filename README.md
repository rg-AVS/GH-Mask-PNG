# Hippotizer mask tools

Converts between Hippotizer's `Masks.xml` and PNG images, in both directions,
with no external dependencies at all: plain C++17 and the standard library.
No libpng, no zlib, no tinyxml2, no graphics toolkit. Every piece is small
enough to lift into another codebase on its own.

```
src/
  common/checksums      CRC-32 + Adler-32
  xml/xml_reader        XML -> DOM            xml/xml_writer   DOM -> XML
  png/png_reader        PNG -> pixels         png/png_writer   pixels -> PNG
  png/deflate           DEFLATE + zlib container (drop-in replaceable by real zlib)
  mask/mask_model       the Masks.xml schema, read and written
  mask/mask_space       THE unit <-> pixel mapping. Everything goes through it.
  mask/mask_trace       raster -> contours -> shapes      (PNG -> mask)
  mask/mask_render      shapes -> raster                  (mask -> PNG)
tools/                  one small CLI per job, thin glue over the above
gui/                    one button: pick a PNG, get a Masks.xml
tests/                  the self-checks
```

## Build and run

```sh
make                 # every tool into build/
make test            # the self-checks
make testset         # regenerate testset/
make gui             # the operator window
```

`make` needs only a C++17 compiler. The GUI needs Python 3 with tkinter,
which ships with python.org and Windows Python (`apt install python3-tk` on
Debian/Ubuntu). Nothing else in the project needs Python at all.

## The window

`make gui` opens one screen with one button and one line of feedback. Pick a
PNG; a `Masks.xml` is written into the same folder as the image. There is
nothing to configure -- the image is taken at face value, so whatever size it
is, is the size the mask is for, and one mask unit is one pixel at that size.

A `Masks.xml` already in that folder is moved aside to `Masks.backup.xml`
rather than being replaced, and only the first time, so a hand-written file
is never lost and reconverting the same folder never nags.

Everything else -- the other candidate mappings, the threshold, the corner
smoothing -- stays on the command line, for when something needs pinning
down.

## The tools

| Tool | Does |
|---|---|
| `png2mask` | PNG -> `Masks.xml`. Traces the image into shapes. |
| `mask2png` | `Masks.xml` -> PNG, at any resolution, under any mapping. |
| `mask_diff` | Compares two PNGs and says whether they cancel. Exit code 0/2. |
| `gen_testset` | Writes the nine-file coordinate test set. |
| `bounds_report` | Where each shape lands, and whether it fits the canvas. |
| `svg_export` | Each mask as an SVG, for eyeballing in a browser. |
| `xml_roundtrip_check` | Parse -> write -> reparse keeps every field. |
| `png_roundtrip_check` | Decode -> encode -> decode keeps every pixel. |

Each takes `--help`. A typical pass:

```sh
./build/png2mask "Ref/Star for Mask.png" star.xml --map native --simplify 1.0
./build/mask2png star.xml out/ --res 1920x1080 --map native
./build/mask_diff "Ref/Star for Mask.png" out/Star_for_Mask.png
```

## The coordinate question

Every `Masks.xml` Hippotizer writes says `xres="1024" yres="768"`, whatever
resolution the mask was actually drawn against, and nothing says what one
coordinate unit is worth. Three candidates are implemented, switchable with
`--map`:

| `--map` | One unit is |
|---|---|
| `native` | one pixel at the image's own resolution. Current best guess. |
| `stretch` | 1/1024th of the width and 1/768th of the height, squashed to fit. |
| `fit` | the same, uniformly scaled so the aspect ratio is kept. |

`testset/` exists to settle it — see **docs/COORDINATES.md**, which has the
evidence so far and how to run the test.

## Accuracy

`png2mask --simplify 0` traces along the grid lines *between* pixels rather
than through pixel centres, so the polygon it emits covers exactly the pixels
that crossed the threshold. Feeding that mask back through `mask2png` at the
same resolution returns a bit-identical image — `make test` asserts it on
every mapping. With a non-zero `--simplify` the trace is deliberately lossy,
trading nodes for smoothness.

Note that a mask is a hard-edged shape and a painted PNG usually is not: a
threshold has to throw away the antialiased edge, so a source image and the
first render of its mask differ along that edge (about 0.2% of pixels on the
sample star). What is lossless is everything after that first render.

## What is still guessed

Unchanged from the original proof of concept, and flagged in the headers of
the files that would implement them:

- **Which mapping is real.** See above. This one has a test now.
- **`Blur` units** — used as a Gaussian sigma in pixels; could be a percentage.
- **`hvmix` / `hblend` / `vblend`** — parsed, carried through, not implemented.
- **`Feather*`** — parsed and written, not rendered. No sample file has a
  feather path that diverges from its main path, so there is nothing to check
  an implementation against.
- **`infill`** — ignored; every shape renders as a solid fill.
- **Compositing** — shapes sharing a `Level` are filled together with the
  nonzero rule, so a reversed ring cuts a hole. Different `Level`s combine
  with max ("lighten"), which is still a guess.

None of these need more guessing from outside. They are the constants someone
with Hippotizer source access drops into `mask_render.cpp`.

## Notes for dropping this into a product

- `deflate.cpp` exists so the project needs no zlib. If the host already
  links zlib, delete it and swap `zlibCompress()` for `compress2()` — one line
  in `png_writer.cpp`.
- `xml_reader` is a minimal parser sized for `Masks.xml`'s flat structure, not
  a general XML library. If the host already has one, `mask_model.cpp` is the
  only file that would need rewriting.
- `mask_space.h` is the file to read first. It is the only place the
  coordinate mapping is defined, and both directions go through it, so the
  two cannot drift apart.
- The GUI is an operator front-end, not part of the plugin. It shells out to
  the same binaries rather than reimplementing anything, so the window and a
  build script cannot disagree.

`docs/POC-notes.md` is the original proof-of-concept write-up, kept for
history.
