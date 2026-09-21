// bounds_report.cpp -- CLI: prints a plain-text/CSV table of every mask's
// canvas size and every shape's raw-coordinate bounding box, plus whether
// that box falls inside, partially inside, or fully outside the canvas
// under the current "centred, 1 unit = 1 pixel" assumption. Quick
// diagnostic for the coordinate-mapping question, no viewer needed --
// useful in a terminal or piped into a spreadsheet.
#include <algorithm>
#include <iostream>
#include <string>
#include "../mask/mask_model.h"

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "usage: " << argv[0] << " Masks.xml [--csv]\n";
        return 1;
    }
    std::string xmlPath = argv[1];
    bool csv = argc >= 3 && std::string(argv[2]) == "--csv";

    try {
        auto masks = parseMasksXml(xmlPath);
        if (csv) {
            std::cout << "mask_index,mask_name,xres,yres,shape_i,shape_guid,"
                         "min_x,max_x,min_y,max_y,fit\n";
        }
        for (const auto& m : masks) {
            double cx = m.xres / 2.0, cy = m.yres / 2.0;
            double canvasMinX = -cx, canvasMaxX = cx, canvasMinY = -cy, canvasMaxY = cy;

            if (!csv) {
                std::cout << "Mask index=" << m.index << " name=\"" << m.name << "\"  canvas "
                          << m.xres << "x" << m.yres << " (assumed range x:["
                          << canvasMinX << "," << canvasMaxX << "] y:[" << canvasMinY << "," << canvasMaxY
                          << "])  blur=" << m.blur << " invert=" << (m.invert ? "true" : "false") << "\n";
            }

            for (size_t i = 0; i < m.shapes.size(); i++) {
                const auto& shape = m.shapes[i];
                double minX = 1e18, maxX = -1e18, minY = 1e18, maxY = -1e18;
                for (const auto& node : shape.nodes) {
                    minX = std::min(minX, node.pos.x); maxX = std::max(maxX, node.pos.x);
                    minY = std::min(minY, node.pos.y); maxY = std::max(maxY, node.pos.y);
                }
                bool fullyInside = minX >= canvasMinX && maxX <= canvasMaxX && minY >= canvasMinY && maxY <= canvasMaxY;
                bool fullyOutside = maxX < canvasMinX || minX > canvasMaxX || maxY < canvasMinY || minY > canvasMaxY;
                std::string fit = fullyInside ? "inside" : (fullyOutside ? "OUTSIDE" : "partial");

                if (csv) {
                    std::cout << m.index << "," << m.name << "," << m.xres << "," << m.yres << ","
                              << i << "," << shape.guid << "," << minX << "," << maxX << ","
                              << minY << "," << maxY << "," << fit << "\n";
                } else {
                    std::cout << "  shape[" << i << "] " << shape.nodes.size() << " nodes  bbox x:["
                              << minX << "," << maxX << "] y:[" << minY << "," << maxY << "]  -> " << fit << "\n";
                }
            }
        }
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << "\n";
        return 1;
    }
    return 0;
}
