#include "mask_model.h"
#include <cstdio>
#include <fstream>
#include <stdexcept>

namespace {

// Matches what Hippotizer writes, and what gui/maskmaker.py writes, so the
// three agree digit for digit.
std::string number(double value) {
    char buf[32];
    std::snprintf(buf, sizeof buf, "%.15g", value);
    return buf;
}

std::string escape(const std::string& s) {
    std::string out;
    out.reserve(s.size());
    for (char c : s) {
        switch (c) {
            case '&': out += "&amp;"; break;
            case '<': out += "&lt;"; break;
            case '>': out += "&gt;"; break;
            case '"': out += "&quot;"; break;
            default: out += c;
        }
    }
    return out;
}

} // namespace

void writeMasksXml(const std::string& path, const std::vector<HippoMask>& masks) {
    std::ofstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("cannot open " + path + " for writing");

    f << "<Masks>\n";
    for (const auto& m : masks) {
        f << "<Mask index=\"" << escape(m.index) << "\" name=\"" << escape(m.name)
          << "\" invert=\"" << (m.invert ? "true" : "false")
          << "\" alpha=\"false\" Blur=\"0\" showpoints=\"false\""
          << " xres=\"" << m.xres << "\" yres=\"" << m.yres << "\">\n";

        for (const auto& shape : m.shapes) {
            f << "<Shape Level=\"255\" guid=\"" << escape(shape.guid)
              << "\" angle=\"0\" locked=\"false\" Outline=\"false\" linewidth=\"1\""
              << " gamma=\"2.2\" infill=\"false\" hvmix=\"127\" hblend=\"127\""
              << " vblend=\"127\">\n";

            for (const auto& p : shape.points) {
                // A corner node keeps both handles, and the whole feather
                // path, on the point itself.
                std::string x = number(p.x), y = number(p.y);
                f << "<Node PosX=\"" << x << "\" PosY=\"" << y
                  << "\" InHandleX=\"" << x << "\" InHandleY=\"" << y
                  << "\" OutHandleX=\"" << x << "\" OutHandleY=\"" << y
                  << "\" Type=\"1\" FeatherPosX=\"" << x << "\" FeatherPosY=\"" << y
                  << "\" FeatherInHandleX=\"" << x << "\" FeatherInHandleY=\"" << y
                  << "\" FeatherOutHandleX=\"" << x << "\" FeatherOutHandleY=\"" << y
                  << "\" FeatherType=\"1\"/>\n";
            }
            f << "</Shape>\n";
        }
        f << "</Mask>\n";
    }
    f << "</Masks>\n";
}
