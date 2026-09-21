// mask2png.cpp -- CLI: Masks.xml -> one PNG per <Mask>. Thin glue over
// mask_model (XML read) + mask_render (geometry/raster) + png_writer.
#include <iostream>
#include <string>
#include "../mask/mask_model.h"
#include "../mask/mask_render.h"
#include "../png/png_writer.h"

static std::string sanitizeFilename(std::string s) {
    for (auto& c : s) if (c == ' ' || c == '/' || c == '\\') c = '_';
    return s.empty() ? "mask" : s;
}

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "usage: " << argv[0] << " Masks.xml [out_dir] [--mask INDEX] [--blur-scale N]\n";
        return 1;
    }
    std::string xmlPath = argv[1];
    std::string outDir = (argc >= 3 && argv[2][0] != '-') ? argv[2] : ".";
    std::string onlyIndex;
    double blurScale = 1.0;
    for (int i = 2; i < argc; i++) {
        std::string a = argv[i];
        if (a == "--mask" && i + 1 < argc) onlyIndex = argv[++i];
        else if (a == "--blur-scale" && i + 1 < argc) blurScale = std::stod(argv[++i]);
    }

    try {
        auto masks = parseMasksXml(xmlPath);
        for (const auto& m : masks) {
            if (!onlyIndex.empty() && m.index != onlyIndex) continue;
            auto gray = renderMask(m, blurScale);
            std::string outPath = outDir + "/" + sanitizeFilename(m.name) + ".png";
            writeGrayscalePng(outPath, gray, m.xres, m.yres);
            std::cout << "wrote " << outPath << "  (" << m.xres << "x" << m.yres
                      << ", " << m.shapes.size() << " shape(s), blur=" << m.blur << ")\n";
        }
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << "\n";
        return 1;
    }
    return 0;
}
