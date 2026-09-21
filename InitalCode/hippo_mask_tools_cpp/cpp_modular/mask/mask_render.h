// mask_render.h -- turns a parsed HippoMask (mask_model.h) into an 8-bit
// grayscale pixel buffer: Bezier reconstruction from Node/handle pairs,
// scanline polygon fill, per-shape gamma-corrected opacity, per-mask
// Gaussian blur and invert. This is the rendering core that used to live
// inside the original single-file mask2png.cpp -- pulled out so it can be
// reused by other tools (svg_export, etc) without dragging PNG I/O along.
//
// UNVERIFIED assumptions carried over from the original POC (see the
// project README for the full discussion):
//   - Coordinate -> pixel mapping: 1 unit = 1 pixel, origin at canvas
//     centre, Y down. Confirmed wrong-ish on both sample files (fits the
//     rectangle roughly, puts LiveMask 2's shapes fully off-canvas) --
//     needs a real answer from Hippotizer's own renderer, not another
//     guess from out here.
//   - Blur: used as a Gaussian sigma in pixels.
//   - hvmix / hblend / vblend: NOT implemented at all.
//   - Feather*: parsed but unused -- no sample file has a feather path
//     that actually diverges from the main path, so there's nothing to
//     verify a soft-edge implementation against yet.
//   - infill: ignored, every shape is treated as a solid fill.
//   - Shape/mask compositing: "lighten" (max) across shapes, a guess.
#pragma once
#include <cstdint>
#include <vector>
#include "mask_model.h"

// Renders one <Mask> to an 8-bit grayscale buffer (row-major, top-down,
// size mask.xres * mask.yres). `blurScale` multiplies the mask's Blur
// attribute before it's used as a Gaussian sigma (in pixels).
std::vector<uint8_t> renderMask(const HippoMask& mask, double blurScale = 1.0);

// Flattens one Shape's closed Bezier ring into a polygon (line-segment
// list) in pixel space, using the same coordinate mapping as renderMask.
// Exposed separately because svg_export and bounds_report only need the
// geometry, not a rasterized image.
std::vector<Vec2> shapeToPixelPolygon(const MaskShape& shape, int xres, int yres, int segmentsPerCurve = 24);
