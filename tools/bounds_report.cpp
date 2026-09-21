// bounds_report.cpp -- CLI: for a given target resolution and mapping
// hypothesis, prints where every shape lands and whether it fits on the
// canvas. The quickest read on the coordinate question, no viewer needed.
//
//   bounds_report "Mask Data/Masks.xml" --res 1920x1080 --all-maps
//
// --all-maps runs the same file through native, stretch and fit at once,
// which is usually the answer on its own: a mask drawn on a real canvas
// should land INSIDE it, so any hypothesis that throws the shape off the
// edge is the wrong hypothesis.
#include <algorithm>
#include <iostream>
#include <string>
#include <vector>
#include "../src/mask/mask_model.h"
#include "../src/mask/mask_space.h"
#include "cli.h"

namespace {

struct Box { double minX = 1e18, maxX = -1e18, minY = 1e18, maxY = -1e18; };

Box shapeBox(const MaskShape& shape) {
    Box b;
    for (const auto& n : shape.nodes) {
        b.minX = std::min(b.minX, n.pos.x); b.maxX = std::max(b.maxX, n.pos.x);
        b.minY = std::min(b.minY, n.pos.y); b.maxY = std::max(b.maxY, n.pos.y);
    }
    return b;
}

const char* fitOf(const Box& s, double cMinX, double cMaxX, double cMinY, double cMaxY) {
    if (s.minX >= cMinX && s.maxX <= cMaxX && s.minY >= cMinY && s.maxY <= cMaxY) return "inside";
    if (s.maxX < cMinX || s.minX > cMaxX || s.maxY < cMinY || s.minY > cMaxY) return "OUTSIDE";
    return "partial";
}

} // namespace

int main(int argc, char** argv) {
    Cli cli(argc, argv);
    if (cli.positional.empty() || cli.has("--help")) {
        std::cerr <<
            "usage: bounds_report Masks.xml [options]\n"
            "  --res WxH     canvas to test against (default: the mask's own xres x yres)\n"
            "  --map MODE    native | stretch | fit   (default native)\n"
            "  --all-maps    test all three mappings side by side\n"
            "  --csv         machine-readable output\n";
        return cli.has("--help") ? 0 : 1;
    }

    try {
        auto masks = parseMasksXml(cli.positional[0]);
        bool csv = cli.has("--csv");

        std::vector<MaskSpace::Mode> modes;
        if (cli.has("--all-maps"))
            modes = {MaskSpace::Mode::Native, MaskSpace::Mode::Stretch, MaskSpace::Mode::Fit};
        else
            modes = {parseSpaceMode(cli.str("--map", "native"))};

        int forceW = 0, forceH = 0;
        if (cli.has("--res")) parseRes(cli.str("--res", ""), forceW, forceH);

        if (csv) std::cout << "mask_index,mask_name,res,map,shape_i,shape_guid,min_x,max_x,min_y,max_y,fit\n";

        for (const auto& m : masks) {
            int w = forceW ? forceW : m.xres;
            int h = forceH ? forceH : m.yres;
            for (MaskSpace::Mode mode : modes) {
                MaskSpace space(mode, w, h, m.xres, m.yres);
                space.yFlip = cli.has("--yflip");
                double cMinX, cMaxX, cMinY, cMaxY;
                space.unitBounds(cMinX, cMaxX, cMinY, cMaxY);
                std::string res = std::to_string(w) + "x" + std::to_string(h);

                if (!csv) {
                    std::cout << "Mask index=" << m.index << " name=\"" << m.name << "\"  declared "
                              << m.xres << "x" << m.yres << "  target " << res
                              << "  map=" << spaceModeName(mode)
                              << "  canvas in units x:[" << cMinX << "," << cMaxX
                              << "] y:[" << cMinY << "," << cMaxY << "]\n";
                }
                for (size_t i = 0; i < m.shapes.size(); i++) {
                    Box b = shapeBox(m.shapes[i]);
                    const char* fit = fitOf(b, cMinX, cMaxX, cMinY, cMaxY);
                    if (csv) {
                        std::cout << m.index << "," << m.name << "," << res << "," << spaceModeName(mode)
                                  << "," << i << "," << m.shapes[i].guid << "," << b.minX << "," << b.maxX
                                  << "," << b.minY << "," << b.maxY << "," << fit << "\n";
                    } else {
                        std::cout << "  shape[" << i << "] " << m.shapes[i].nodes.size()
                                  << " nodes  bbox x:[" << b.minX << "," << b.maxX
                                  << "] y:[" << b.minY << "," << b.maxY << "]  -> " << fit << "\n";
                    }
                }
            }
        }
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << "\n";
        return 1;
    }
    return 0;
}
