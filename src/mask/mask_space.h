// mask_space.h -- THE coordinate mapping between Masks.xml units and image
// pixels. Every other module goes through this one file, so PNG->mask and
// mask->PNG can never drift apart: mask_trace calls toUnits(), mask_render
// calls toPixels(), and they are exact inverses of each other by
// construction (see tools/mask_diff.cpp, which proves it numerically).
//
// THE OPEN QUESTION this file exists to answer
// --------------------------------------------
// Every Masks.xml Hippotizer writes declares xres="1024" yres="768",
// regardless of the resolution the mask was actually drawn against. Node
// coordinates are signed and centred on zero. What is not documented is
// what one unit is worth. Three candidates are implemented here; pick one
// with Mode, render, and see which cancels:
//
//   Native   1 unit = 1 pixel at the image's OWN resolution. xres/yres are
//            treated as a fixed editor-canvas label and ignored for scale.
//            Current best guess -- it is the only one of the three that
//            places the sample "Mask Data/Masks.xml" rectangle fully on a
//            1920x1080 canvas, and keeps it square (809.06 x 809.06 units),
//            which is what a square drawn on screen would produce.
//   Stretch  Units span exactly xres x yres, non-uniformly scaled to the
//            image. A 16:9 image squashed into the 4:3 declared box.
//   Fit      Units span xres x yres, uniformly scaled (aspect preserved,
//            letter/pillarboxed).
//
// In all three, the origin is the image centre, +X is right and +Y is DOWN
// (matching PNG row order). If a test shows the mask landing mirrored
// vertically, +Y is up and yFlip is the knob for it.
#pragma once
#include <string>
#include "mask_model.h"

struct MaskSpace {
    enum class Mode { Native, Stretch, Fit };

    Mode mode = Mode::Native;
    int imgW = 0, imgH = 0;        // the real image resolution, in pixels
    int declW = 1024, declH = 768; // the mask's declared xres/yres
    bool yFlip = false;            // true if +Y in mask units points UP

    MaskSpace() = default;
    MaskSpace(Mode m, int imageW, int imageH, int declaredW = 1024, int declaredH = 768)
        : mode(m), imgW(imageW), imgH(imageH), declW(declaredW), declH(declaredH) {}

    // Units per pixel along each axis. This is the whole of the difference
    // between the three modes; everything else is a centre offset.
    double scaleX() const;
    double scaleY() const;

    // Pixel coordinates are continuous, top-left origin, +Y down: pixel
    // centre of column i / row j is (i + 0.5, j + 0.5).
    Vec2 toUnits(double px, double py) const;
    Vec2 toPixels(double ux, double uy) const;

    // The image rectangle expressed in mask units -- what bounds_report
    // draws its canvas box from.
    void unitBounds(double& minX, double& maxX, double& minY, double& maxY) const;
};

// "native" | "stretch" | "fit", for CLI flags. Throws std::runtime_error on
// anything else so a typo in a batch script fails loudly.
MaskSpace::Mode parseSpaceMode(const std::string& name);
const char* spaceModeName(MaskSpace::Mode mode);
