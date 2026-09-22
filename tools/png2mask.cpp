// png2mask.cpp -- CLI: PNG -> Masks.xml. The one thing this project does.
//
//   png2mask artwork.png Masks.xml
//
// ONLY the alpha channel is read: what is solid becomes mask, what is
// see-through does not, and the colours are never looked at. A PNG with no
// transparency is refused rather than guessed at -- artwork is usually not
// white, so going on brightness would find the wrong thing, or the exact
// inverse of what was drawn.
#include <exception>
#include <iostream>
#include <string>
#include <vector>
#include "../src/mask/mask_model.h"
#include "../src/mask/mask_trace.h"
#include "../src/png/png_reader.h"

namespace {

// Four flags is not enough to justify an argument parser.
std::string flag(int argc, char** argv, const std::string& name, const std::string& def) {
    for (int i = 1; i + 1 < argc; i++)
        if (name == argv[i]) return argv[i + 1];
    return def;
}

bool present(int argc, char** argv, const std::string& name) {
    for (int i = 1; i < argc; i++)
        if (name == argv[i]) return true;
    return false;
}

std::string stem(std::string path) {
    size_t slash = path.find_last_of("/\\");
    if (slash != std::string::npos) path = path.substr(slash + 1);
    size_t dot = path.find_last_of('.');
    return dot == std::string::npos ? path : path.substr(0, dot);
}

} // namespace

int main(int argc, char** argv) {
    std::vector<std::string> positional;
    for (int i = 1; i < argc; i++) {
        std::string a = argv[i];
        if (a.rfind("--", 0) == 0) { if (a != "--invert-mask" && a != "--help") i++; }
        else positional.push_back(a);
    }

    if (positional.size() < 2 || present(argc, argv, "--help")) {
        std::cerr <<
            "usage: png2mask artwork.png Masks.xml [options]\n"
            "  --threshold N   0-255, alpha at or above N is inside the mask (default 128)\n"
            "  --simplify EPS  how far a traced edge may be straightened, in pixels\n"
            "                  (default 1; 0 keeps every step exactly)\n"
            "  --invert-mask   cut the shape out instead of keeping it\n"
            "  --name NAME     <Mask name> (default: the PNG's filename)\n";
        return present(argc, argv, "--help") ? 0 : 1;
    }

    try {
        const std::string pngPath = positional[0], xmlPath = positional[1];

        int w = 0, h = 0;
        auto alpha = readMaskPng(pngPath, &w, &h);

        TraceOptions opts;
        opts.threshold = (uint8_t)std::stoi(flag(argc, argv, "--threshold", "128"));
        opts.simplifyEps = std::stod(flag(argc, argv, "--simplify", "1"));

        auto mask = traceMask(alpha, w, h, flag(argc, argv, "--name", stem(pngPath)), opts);
        mask.invert = present(argc, argv, "--invert-mask");
        writeMasksXml(xmlPath, {mask});

        size_t points = 0;
        for (const auto& s : mask.shapes) points += s.points.size();
        std::cout << "wrote " << xmlPath << "  (" << mask.shapes.size() << " shape(s), "
                  << points << " point(s), from " << w << "x" << h << ")\n";
        if (mask.shapes.empty())
            std::cout << "  note: nothing in it was solid enough to trace.\n";
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << "\n";
        return 1;
    }
    return 0;
}
