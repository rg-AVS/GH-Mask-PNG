// mask_model.h -- the Masks.xml data model, and writing it out.
//
// WRITE ONLY. Nothing here reads Masks.xml, because nothing in the PNG ->
// mask direction needs to.
//
// The model is only as wide as what this tool produces: closed rings of
// CORNER nodes. Hippotizer's format carries more per node -- separate in and
// out Bezier handles, a parallel feather path, and per-shape angle, outline,
// linewidth, infill and hv/h/v blend -- and the writer fills all of them in
// with the fixed values a corner node implies (both handles and the whole
// feather path sit on the point itself, Type="1"). A shape traced from a
// raster has no curve or feather information to put there, so carrying
// fields that could only ever hold those constants would be pretending to a
// generality this does not have. Anyone adding curve support adds the fields
// back here and in writeMasksXml, and nowhere else.
#pragma once
#include <string>
#include <vector>

struct Vec2 { double x = 0, y = 0; };

struct MaskShape {
    std::string guid;                 // "{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}"
    std::vector<Vec2> points;         // a closed ring, in mask units
};

struct HippoMask {
    std::string index = "1";
    std::string name;
    bool invert = false;              // true cuts the shape out instead of keeping it
    int xres = 1024, yres = 768;      // what Hippotizer writes, whatever the artwork was
    std::vector<MaskShape> shapes;
};

// Writes a <Masks> document, in the flat one-element-per-line style
// Hippotizer's own files use.
void writeMasksXml(const std::string& path, const std::vector<HippoMask>& masks);
