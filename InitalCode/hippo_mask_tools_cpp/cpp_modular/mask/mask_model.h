// mask_model.h -- the Hippotizer Masks.xml data model, plus read/write of
// it via xml_reader.h / xml_writer.h. This is the "XML reader" and "XML
// writer" pieces made concrete for this specific file format (as opposed
// to xml_reader.h/xml_writer.h, which know nothing about masks at all).
#pragma once
#include <string>
#include <vector>

struct Vec2 { double x = 0, y = 0; };

struct MaskNode {
    Vec2 pos, inH, outH;
    std::string type;                 // "1" = corner, "2" = smooth (editor metadata only --
                                       // geometry comes entirely from pos/inH/outH regardless)
    Vec2 featherPos, featherIn, featherOut;
    std::string featherType;
};

struct MaskShape {
    double level = 255.0;             // 0-255 opacity/brightness
    std::string guid;
    double angle = 0.0;
    bool locked = false;
    bool outline = false;
    double linewidth = 1.0;
    double gamma = 1.0;
    bool infill = false;
    int hvmix = 127, hblend = 127, vblend = 127; // unimplemented in mask_render -- see its header
    std::vector<MaskNode> nodes;
};

struct HippoMask {
    std::string index, name;
    bool invert = false;
    bool alpha = false;
    double blur = 0.0;
    bool showpoints = false;
    int xres = 0, yres = 0;
    std::vector<MaskShape> shapes;
};

// Reads a Masks.xml file into the data model above.
std::vector<HippoMask> parseMasksXml(const std::string& path);

// Writes the data model back out as a Masks.xml file, in the same flat,
// one-element-per-line style the sample files use. Round-tripping
// parseMasksXml -> writeMasksXml -> parseMasksXml should reproduce the
// same numeric field values (see tools/xml_roundtrip_check.cpp).
void writeMasksXml(const std::string& path, const std::vector<HippoMask>& masks);
