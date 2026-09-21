// mask_trace.h -- the PNG -> mask direction: an 8-bit coverage raster in,
// a HippoMask full of <Shape> node rings out.
//
// The trace is a CRACK FOLLOW, not a pixel-centre walk: contours run along
// the grid lines BETWEEN pixels, so with simplifyEps = 0 the polygon that
// comes out covers exactly the pixels that were thresholded in -- feed the
// result back through mask_render at the same resolution and it is
// bit-identical. That is what makes tools/mask_diff.cpp a real test rather
// than a tolerance check.
//
// Rings come out oriented so that outer boundaries and the holes inside
// them wind opposite ways. mask_render fills all same-Level rings of a mask
// with the nonzero rule in one pass, so holes cut themselves out with no
// special casing anywhere.
#pragma once
#include <cstdint>
#include <string>
#include <vector>
#include "mask_model.h"
#include "mask_space.h"

struct TraceOptions {
    uint8_t threshold = 128;   // >= this is inside the mask
    bool invertInput = false;  // treat DARK pixels as inside instead
    double simplifyEps = 1.0;  // Douglas-Peucker tolerance, in pixels. 0 = lossless
                                // (collinear points still dropped, so a rectangle is
                                // still 4 nodes, not 4 x width).
    size_t minArea = 4;        // drop specks smaller than this many pixels
    double level = 255.0;      // <Shape Level="...">
    double gamma = 2.2;        // <Shape gamma="..."> -- matches what Hippotizer writes
    unsigned guidSeed = 0;     // 0 = seed from the clock; anything else is reproducible
};

// Traces `gray` (w*h, row-major, top-down) into mask units using `space`.
// `name` and `index` populate the <Mask> attributes; the mask's declared
// xres/yres come from space.declW/declH, NOT from w/h -- Hippotizer always
// writes 1024x768 there and this keeps that true.
HippoMask traceMask(const std::vector<uint8_t>& gray, int w, int h,
                    const MaskSpace& space, const std::string& name,
                    const std::string& index, const TraceOptions& opts = {});

// Exposed for tools that want the raw pixel-space rings without the XML
// model around them (and so the tracer can be tested on its own).
std::vector<std::vector<Vec2>> traceContours(const std::vector<uint8_t>& gray, int w, int h,
                                              const TraceOptions& opts);

// Douglas-Peucker on a CLOSED ring. eps <= 0 only drops collinear points.
std::vector<Vec2> simplifyRing(const std::vector<Vec2>& ring, double eps);

// Converts one pixel-space ring into a <Shape> of corner nodes (Type="1",
// both handles on the point). Shared by traceMask and by tools/gen_testset,
// so a hand-authored test shape and a traced one go through identical code.
MaskShape ringToShape(const std::vector<Vec2>& pixelRing, const MaskSpace& space,
                      double level = 255.0, double gamma = 2.2, unsigned guidSeed = 0);

// A Hippotizer-style "{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}" GUID.
std::string makeGuid(unsigned seed = 0);
