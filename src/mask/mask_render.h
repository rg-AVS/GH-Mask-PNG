// mask_render.h -- turns a parsed HippoMask (mask_model.h) into an 8-bit
// grayscale pixel buffer: Bezier reconstruction from Node/handle pairs,
// scanline polygon fill, per-shape gamma-corrected opacity, per-mask
// Gaussian blur and invert.
//
// The output resolution comes from the MaskSpace you pass in, NOT from the
// mask's xres/yres. That separation is the point: Hippotizer writes
// xres="1024" yres="768" into every file regardless of what the mask was
// drawn against, so the declared size is a label, and the resolution you
// want pixels at is a separate question. See mask_space.h.
//
// STILL UNVERIFIED (see docs/COORDINATES.md for the full discussion):
//   - Which MaskSpace::Mode is the real one. Native is the default and the
//     best-supported guess; the test set exists to settle it.
//   - Blur: used as a Gaussian sigma in pixels.
//   - hvmix / hblend / vblend: NOT implemented at all.
//   - Feather*: parsed but unused -- no sample file has a feather path that
//     diverges from the main path, so there is nothing to verify against.
//   - infill: ignored, every shape is treated as a solid fill.
//   - Compositing: shapes sharing a Level are filled together with the
//     nonzero rule, so a hole ring cuts itself out of its parent. Different
//     Levels are combined with max ("lighten"), which is still a guess.
#pragma once
#include <cstdint>
#include <vector>
#include "mask_model.h"
#include "mask_space.h"

// Renders one <Mask> to an 8-bit grayscale buffer (row-major, top-down,
// size space.imgW * space.imgH). `blurScale` multiplies the mask's Blur
// attribute before it is used as a Gaussian sigma in pixels.
std::vector<uint8_t> renderMask(const HippoMask& mask, const MaskSpace& space, double blurScale = 1.0);

// Flattens one Shape's closed Bezier ring into a polygon (line-segment
// list) in pixel space, using the same mapping renderMask uses. Exposed
// separately because svg_export and bounds_report only want the geometry.
std::vector<Vec2> shapeToPixelPolygon(const MaskShape& shape, const MaskSpace& space,
                                       int segmentsPerCurve = 24);

// Fills a set of rings into `coverage` (0..1, size w*h) with the nonzero
// winding rule, antialiased 4x vertically and by exact span overlap
// horizontally. Rings wound opposite their parent cut holes in it.
void rasterizeRings(const std::vector<std::vector<Vec2>>& rings, int w, int h,
                    std::vector<float>& coverage, int ySubsamples = 4);
