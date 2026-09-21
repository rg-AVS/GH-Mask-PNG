// svg_export.cpp -- CLI: Masks.xml -> one SVG per <Mask>, in the mask's
// OWN raw coordinate units (not remapped to pixel space the way mask2png
// does). Also draws the xres/yres canvas as a dashed reference rectangle,
// under the same "centred, 1 unit = 1 pixel" guess mask_render uses.
//
// Why this exists: it's the fastest way to get eyes on the actual
// coordinate-mapping mystery flagged in the project README. Open the SVG
// in a browser or Illustrator, and you can see immediately whether a
// shape's node coordinates sit anywhere near the canvas rectangle, zoom
// in with real rulers, and compare against a screenshot of the same mask
// open in Hippotizer's own editor -- much faster than eyeballing raw
// numbers in the XML.
//
// Also doubles as a demonstration that xml_writer.h is a generic XML
// serializer, not Masks-specific: it builds an <svg> tree the same way
// mask_model.cpp builds a <Masks> tree.
#include <algorithm>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include "../mask/mask_model.h"
#include "../xml/xml_writer.h"

static std::string sanitizeFilename(std::string s) {
    for (auto& c : s) if (c == ' ' || c == '/' || c == '\\') c = '_';
    return s.empty() ? "mask" : s;
}

// Builds an SVG path "d" attribute for one shape's closed Bezier ring,
// directly in the shape's own raw units (no pixel remapping at all).
static std::string pathData(const MaskShape& shape) {
    std::ostringstream d;
    d.precision(6);
    size_t n = shape.nodes.size();
    if (n == 0) return "";
    d << "M " << shape.nodes[0].pos.x << " " << shape.nodes[0].pos.y << " ";
    for (size_t i = 0; i < n; i++) {
        const MaskNode& cur = shape.nodes[i];
        const MaskNode& nxt = shape.nodes[(i + 1) % n];
        d << "C " << cur.outH.x << " " << cur.outH.y << " "
          << nxt.inH.x << " " << nxt.inH.y << " "
          << nxt.pos.x << " " << nxt.pos.y << " ";
    }
    d << "Z";
    return d.str();
}

static const char* PALETTE[] = {"#e63946", "#ffd166", "#06d6a0", "#118ab2", "#a78bfa", "#f77f00"};

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "usage: " << argv[0] << " Masks.xml [out_dir]\n";
        return 1;
    }
    std::string xmlPath = argv[1];
    std::string outDir = argc >= 3 ? argv[2] : ".";

    try {
        auto masks = parseMasksXml(xmlPath);
        for (const auto& m : masks) {
            // Bounding box over the assumed canvas rectangle AND every
            // shape's raw node positions, so both are visible at once.
            double cx = m.xres / 2.0, cy = m.yres / 2.0;
            double minX = -cx, maxX = cx, minY = -cy, maxY = cy;
            for (const auto& shape : m.shapes) {
                for (const auto& node : shape.nodes) {
                    minX = std::min(minX, node.pos.x); maxX = std::max(maxX, node.pos.x);
                    minY = std::min(minY, node.pos.y); maxY = std::max(maxY, node.pos.y);
                }
            }
            double pad = 0.05 * std::max(maxX - minX, maxY - minY);
            minX -= pad; maxX += pad; minY -= pad; maxY += pad;
            double w = maxX - minX, h = maxY - minY;

            XmlElement svg;
            svg.tag = "svg";
            svg.setAttr("xmlns", "http://www.w3.org/2000/svg");
            std::ostringstream vb; vb.precision(6);
            vb << minX << " " << minY << " " << w << " " << h;
            svg.setAttr("viewBox", vb.str());
            svg.setAttr("width", "1000");
            svg.setAttr("height", std::to_string((int)(1000.0 * h / w)));

            // Background
            auto bg = svg.addChild("rect");
            bg->setAttrD("x", minX); bg->setAttrD("y", minY);
            bg->setAttrD("width", w); bg->setAttrD("height", h);
            bg->setAttr("fill", "#111318");

            // Assumed canvas rectangle (xres x yres, centred at origin) --
            // this is the guess being tested, drawn dashed so it reads as
            // "hypothesis", not "known fact".
            auto canvasRect = svg.addChild("rect");
            canvasRect->setAttrD("x", -cx); canvasRect->setAttrD("y", -cy);
            canvasRect->setAttrD("width", m.xres); canvasRect->setAttrD("height", m.yres);
            canvasRect->setAttr("fill", "none");
            canvasRect->setAttr("stroke", "#ffffff");
            canvasRect->setAttrD("stroke-width", w * 0.002);
            canvasRect->setAttr("stroke-dasharray", "8,6");

            for (size_t i = 0; i < m.shapes.size(); i++) {
                std::string color = PALETTE[i % (sizeof(PALETTE) / sizeof(PALETTE[0]))];
                auto path = svg.addChild("path");
                path->setAttr("d", pathData(m.shapes[i]));
                path->setAttr("fill", color);
                path->setAttr("fill-opacity", "0.35");
                path->setAttr("stroke", color);
                path->setAttrD("stroke-width", w * 0.0025);
            }

            XmlWriteOptions opts;
            opts.declaration = true;
            std::string outPath = outDir + "/" + sanitizeFilename(m.name) + ".svg";
            writeXmlFile(outPath, svg, opts);
            std::cout << "wrote " << outPath << "  (canvas " << m.xres << "x" << m.yres
                      << ", viewBox " << vb.str() << ")\n";
        }
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << "\n";
        return 1;
    }
    return 0;
}
