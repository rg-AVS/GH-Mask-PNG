// gen_testset.cpp -- builds the coordinate-mapping test set: one PNG per
// (resolution x mapping hypothesis) pair, plus a single Masks.xml holding
// the matching <Mask> for each.
//
//   gen_testset testset/
//
// HOW TO USE IT
// -------------
// Every Masks.xml Hippotizer writes says xres="1024" yres="768" no matter
// what resolution the mask was drawn against, and nothing says what one
// coordinate unit is worth. Three candidates are implemented (mask_space.h):
// native, stretch, fit. This tool emits the SAME test shape under all three,
// at three resolutions, so the question can be settled in one import:
//
//   1. Load PNG NN as media on a layer running at that PNG's resolution.
//   2. Load testset/Masks.xml and apply the <Mask> whose name matches NN.
//   3. Exactly one mapping will line up pixel-for-pixel. That is the answer.
//
// The shape is deliberately asymmetric -- a bite out of the TOP-LEFT corner
// and a lone square at the BOTTOM-LEFT -- so a mirrored or rotated result is
// obvious rather than looking like a near miss. The square hole in the middle
// checks that hole winding survives the trip, and the small corner square
// checks scale far from the origin, where an error is largest.
//
// The PNG and the mask are generated from ONE set of coordinates, so a
// mismatch can only come from the mapping, never from the shape.
#include <algorithm>
#include <cmath>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include "../src/mask/mask_model.h"
#include "../src/mask/mask_render.h"
#include "../src/mask/mask_space.h"
#include "../src/mask/mask_trace.h"
#include "../src/png/png_writer.h"
#include "cli.h"

namespace {

struct Ring { std::vector<Vec2> pts; bool hole; };

// The test shape, in fractions of the frame. Frame-relative so it looks the
// same at every resolution while landing on different pixels.
const std::vector<Ring> kShape = {
    // Outer: a 10%-inset rectangle with the top-left corner bitten out.
    {{{0.10, 0.30}, {0.30, 0.30}, {0.30, 0.10}, {0.90, 0.10}, {0.90, 0.90}, {0.10, 0.90}}, false},
    // A square hole dead centre.
    {{{0.40, 0.40}, {0.60, 0.40}, {0.60, 0.60}, {0.40, 0.60}}, true},
    // A separate square hard into the bottom-left corner.
    {{{0.02, 0.93}, {0.07, 0.93}, {0.07, 0.98}, {0.02, 0.98}}, false},
};

double signedArea(const std::vector<Vec2>& r) {
    double a = 0;
    for (size_t i = 0; i < r.size(); i++) {
        const Vec2& p = r[i];
        const Vec2& q = r[(i + 1) % r.size()];
        a += p.x * q.y - q.x * p.y;
    }
    return a * 0.5;
}

// Solid rings wind one way, holes the other, so the nonzero fill rule cuts
// the hole out with no special casing.
std::vector<std::vector<Vec2>> shapeInPixels(int w, int h) {
    std::vector<std::vector<Vec2>> out;
    for (const auto& ring : kShape) {
        std::vector<Vec2> px;
        for (const auto& p : ring.pts) px.push_back({p.x * w, p.y * h});
        bool positive = signedArea(px) > 0;
        if (positive == ring.hole) std::reverse(px.begin(), px.end());
        out.push_back(px);
    }
    return out;
}

std::string two(int n) { return (n < 10 ? "0" : "") + std::to_string(n); }

} // namespace

int main(int argc, char** argv) {
    Cli cli(argc, argv);
    if (cli.has("--help")) {
        std::cerr <<
            "usage: gen_testset [out_dir] [options]\n"
            "  --decl WxH      declared xres/yres to write (default 1024x768)\n"
            "  --invert-mask   set invert=\"true\" on every <Mask>\n"
            "  --yflip         emit +Y pointing up instead of down\n";
        return 0;
    }

    try {
        std::string outDir = cli.positional.empty() ? "testset" : cli.positional[0];
        int declW = 1024, declH = 768;
        if (cli.has("--decl")) parseRes(cli.str("--decl", ""), declW, declH);

        const int resolutions[3][2] = {{1920, 1080}, {3840, 1080}, {1024, 768}};
        const MaskSpace::Mode modes[3] = {MaskSpace::Mode::Native, MaskSpace::Mode::Stretch,
                                           MaskSpace::Mode::Fit};

        std::vector<HippoMask> masks;
        std::ofstream manifest(outDir + "/MANIFEST.txt");
        if (!manifest) throw std::runtime_error("cannot write into '" + outDir + "' -- does it exist?");
        manifest << "Hippotizer mask coordinate test set\n"
                    "===================================\n\n"
                    "Nine PNG + <Mask> pairs. Load each PNG as media at its own resolution,\n"
                    "apply the <Mask> of the same name from Masks.xml, and note which ones\n"
                    "line up pixel-for-pixel. The mapping named in the matching file is the\n"
                    "one Hippotizer actually uses.\n\n"
                    "If a pair lines up but is inverted -- the shape survives where it should\n"
                    "vanish -- the geometry is right and only the mask sense is flipped;\n"
                    "regenerate with --invert-mask.\n\n"
                    "file                              resolution   mapping   unit range\n"
                    "--------------------------------  -----------  --------  -----------------------\n";

        int n = 0;
        for (const auto& res : resolutions) {
            for (MaskSpace::Mode mode : modes) {
                n++;
                int w = res[0], h = res[1];
                MaskSpace space(mode, w, h, declW, declH);
                space.yFlip = cli.has("--yflip");

                auto rings = shapeInPixels(w, h);

                std::vector<float> coverage((size_t)w * h, 0.0f);
                rasterizeRings(rings, w, h, coverage);
                std::vector<uint8_t> gray(coverage.size());
                for (size_t i = 0; i < coverage.size(); i++)
                    gray[i] = (uint8_t)std::lround(std::min(1.0f, coverage[i]) * 255.0f);

                std::string name = two(n) + "_" + std::to_string(w) + "x" + std::to_string(h) +
                                    "_" + spaceModeName(mode);
                writeGrayscalePng(outDir + "/" + name + ".png", gray, w, h);

                HippoMask mask;
                mask.index = std::to_string(n);
                mask.name = name;
                mask.xres = declW;
                mask.yres = declH;
                mask.invert = cli.has("--invert-mask");
                // Fixed seeds: regenerating the set gives byte-identical GUIDs,
                // so a diff between two runs shows real changes only.
                unsigned seed = 1000u * n + 1;
                for (const auto& ring : rings)
                    mask.shapes.push_back(ringToShape(ring, space, 255.0, 2.2, seed++));
                masks.push_back(mask);

                double minX, maxX, minY, maxY;
                space.unitBounds(minX, maxX, minY, maxY);
                char line[256];
                std::snprintf(line, sizeof line, "%-32s  %-11s  %-8s  x %.1f..%.1f  y %.1f..%.1f\n",
                              (name + ".png").c_str(),
                              (std::to_string(w) + "x" + std::to_string(h)).c_str(),
                              spaceModeName(mode), minX, maxX, minY, maxY);
                manifest << line;
                std::cout << "wrote " << outDir << "/" << name << ".png\n";
            }
        }

        writeMasksXml(outDir + "/Masks.xml", masks);
        manifest << "\nAll nine <Mask> elements are in Masks.xml, declared "
                 << declW << "x" << declH << ", matched to the PNGs by name.\n";
        std::cout << "wrote " << outDir << "/Masks.xml  (" << masks.size() << " masks)\n"
                  << "wrote " << outDir << "/MANIFEST.txt\n";
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << "\n";
        return 1;
    }
    return 0;
}
