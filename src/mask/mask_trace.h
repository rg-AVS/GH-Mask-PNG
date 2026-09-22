// mask_trace.h -- the whole PNG -> mask conversion: an alpha channel in, a
// HippoMask full of <Shape> rings out.
//
// The trace is a CRACK FOLLOW, not a pixel-centre walk: contours run along
// the grid lines BETWEEN pixels, so with simplifyEps = 0 the polygon that
// comes out covers exactly the pixels that were thresholded in.
//
// Rings come out oriented so that outer boundaries and the holes inside them
// wind opposite ways, which is what lets a hole cut itself out under the
// nonzero fill rule with no special casing.
//
// COORDINATES. One mask unit is one pixel at the image's own resolution, and
// the origin is the middle of the image. Hippotizer writes xres="1024"
// yres="768" into every file whatever the artwork was drawn against, so the
// declared size is a label, not a scale -- see docs/COORDINATES.md for the
// evidence, and for the two other readings that were tested and dropped.
#pragma once
#include <cstdint>
#include <string>
#include <vector>
#include "mask_model.h"

struct TraceOptions {
    uint8_t threshold = 128;   // alpha at or above this is inside the mask
    double simplifyEps = 1.0;  // Douglas-Peucker tolerance, in pixels. 0 = lossless
                                // (collinear points still go, so a rectangle is
                                // still 4 nodes, not 4 x width).
};

// Traces `alpha` (w*h, row-major, top-down: 255 solid, 0 see-through).
HippoMask traceMask(const std::vector<uint8_t>& alpha, int w, int h,
                    const std::string& name, const TraceOptions& opts = {});

// Exposed so the tracer can be tested without the XML around it.
std::vector<std::vector<Vec2>> traceContours(const std::vector<uint8_t>& alpha, int w, int h,
                                              const TraceOptions& opts);

// Douglas-Peucker on a CLOSED ring. eps <= 0 only drops collinear points.
std::vector<Vec2> simplifyRing(const std::vector<Vec2>& ring, double eps);
