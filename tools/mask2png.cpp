// mask2png.cpp -- CLI: Masks.xml -> one PNG per <Mask>. Thin glue over
// mask_model (XML read) + mask_space (mapping) + mask_render (raster) +
// png_writer.
//
//   mask2png Masks.xml out/ --res 1920x1080 --map native
#include <iostream>
#include <string>
#include "../src/mask/mask_model.h"
#include "../src/mask/mask_render.h"
#include "../src/mask/mask_space.h"
#include "../src/png/png_writer.h"
#include "cli.h"

int main(int argc, char** argv) {
    Cli cli(argc, argv);
    if (cli.positional.empty() || cli.has("--help")) {
        std::cerr <<
            "usage: mask2png Masks.xml [out_dir] [options]\n"
            "  --mask INDEX       render only the <Mask index=\"INDEX\">\n"
            "  --res WxH          output resolution (default: the mask's own xres x yres)\n"
            "  --map MODE         native | stretch | fit   (default native)\n"
            "  --yflip            treat +Y in mask units as pointing up\n"
            "  --invert           force invert on, whatever the file says\n"
            "  --blur-scale N     multiply the mask's Blur before using it as a sigma\n";
        return cli.has("--help") ? 0 : 1;
    }

    try {
        std::string xmlPath = cli.positional[0];
        std::string outDir = cli.positional.size() > 1 ? cli.positional[1] : ".";
        std::string onlyIndex = cli.str("--mask", "");
        double blurScale = cli.num("--blur-scale", 1.0);
        auto mode = parseSpaceMode(cli.str("--map", "native"));

        int forceW = 0, forceH = 0;
        if (cli.has("--res")) parseRes(cli.str("--res", ""), forceW, forceH);

        auto masks = parseMasksXml(xmlPath);
        if (masks.empty()) { std::cerr << "error: no <Mask> elements in " << xmlPath << "\n"; return 1; }

        int rendered = 0;
        for (auto& m : masks) {
            if (!onlyIndex.empty() && m.index != onlyIndex) continue;
            rendered++;
            int w = forceW ? forceW : m.xres;
            int h = forceH ? forceH : m.yres;
            if (w <= 0 || h <= 0) { std::cerr << "error: mask " << m.index << " has no usable resolution\n"; return 1; }

            MaskSpace space(mode, w, h, m.xres, m.yres);
            space.yFlip = cli.has("--yflip");
            if (cli.has("--invert")) m.invert = true;

            auto gray = renderMask(m, space, blurScale);
            std::string outPath = outDir + "/" + sanitizeFilename(m.name) + ".png";
            writeGrayscalePng(outPath, gray, w, h);
            std::cout << "wrote " << outPath << "  (" << w << "x" << h
                      << ", map=" << spaceModeName(mode)
                      << ", " << m.shapes.size() << " shape(s), blur=" << m.blur << ")\n";
        }
        if (rendered == 0) {
            std::cerr << "error: no mask with index=\"" << onlyIndex << "\" in " << xmlPath << "\n";
            return 1;
        }
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << "\n";
        return 1;
    }
    return 0;
}
