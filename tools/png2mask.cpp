// png2mask.cpp -- CLI: PNG -> Masks.xml. The direction this project exists
// for. Thin glue over png_reader + mask_space + mask_trace + mask_model.
//
//   png2mask star.png Masks.xml --map native --simplify 1.0
//
// An RGBA PNG is read through its alpha channel (so a shape painted on a
// transparent background works straight out of Photoshop); a grayscale or
// RGB one is read by luma, white = masked.
#include <iostream>
#include <string>
#include "../src/mask/mask_model.h"
#include "../src/mask/mask_space.h"
#include "../src/mask/mask_trace.h"
#include "../src/png/png_reader.h"
#include "cli.h"

int main(int argc, char** argv) {
    Cli cli(argc, argv);
    if (cli.positional.size() < 2 || cli.has("--help")) {
        std::cerr <<
            "usage: png2mask input.png output.xml [options]\n"
            "  --map MODE         native | stretch | fit   (default native)\n"
            "  --decl WxH         declared xres/yres to write (default 1024x768)\n"
            "  --yflip            emit +Y pointing up instead of down\n"
            "  --threshold N      0-255, pixels >= N are inside the mask (default 128)\n"
            "  --invert-input     treat DARK pixels as inside instead\n"
            "  --invert-mask      set invert=\"true\" on the <Mask>\n"
            "  --simplify EPS     Douglas-Peucker tolerance in pixels (default 1.0; 0 = lossless)\n"
            "  --min-area N       drop traced regions under N pixels (default 4)\n"
            "  --name NAME        <Mask name> (default: the PNG's filename)\n"
            "  --index N          <Mask index> (default: 1, or next free when appending)\n"
            "  --blur N           <Mask Blur> (default 0)\n"
            "  --guid-seed N      fixed seed for reproducible GUIDs (default: clock)\n"
            "  --append           add to output.xml's existing masks instead of replacing\n";
        return cli.has("--help") ? 0 : 1;
    }

    try {
        std::string pngPath = cli.positional[0];
        std::string xmlPath = cli.positional[1];

        int w = 0, h = 0;
        auto gray = readGrayscalePng(pngPath, &w, &h);

        int declW = 1024, declH = 768;
        if (cli.has("--decl")) parseRes(cli.str("--decl", ""), declW, declH);

        MaskSpace space(parseSpaceMode(cli.str("--map", "native")), w, h, declW, declH);
        space.yFlip = cli.has("--yflip");

        TraceOptions opts;
        opts.threshold = (uint8_t)std::max(0, std::min(255, cli.integer("--threshold", 128)));
        opts.invertInput = cli.has("--invert-input");
        opts.simplifyEps = cli.num("--simplify", 1.0);
        opts.minArea = (size_t)std::max(0, cli.integer("--min-area", 4));
        opts.guidSeed = (unsigned)cli.integer("--guid-seed", 0);

        std::vector<HippoMask> masks;
        if (cli.has("--append")) {
            try { masks = parseMasksXml(xmlPath); } catch (...) { /* no file yet: start fresh */ }
        }

        std::string base = pngPath;
        size_t slash = base.find_last_of("/\\");
        if (slash != std::string::npos) base = base.substr(slash + 1);
        size_t dot = base.find_last_of('.');
        if (dot != std::string::npos) base = base.substr(0, dot);

        std::string index = cli.str("--index", std::to_string(masks.size() + 1));
        auto mask = traceMask(gray, w, h, space, cli.str("--name", base), index, opts);
        mask.invert = cli.has("--invert-mask");
        mask.blur = cli.num("--blur", 0.0);

        size_t nodes = 0;
        for (const auto& s : mask.shapes) nodes += s.nodes.size();
        masks.push_back(mask);
        writeMasksXml(xmlPath, masks);

        std::cout << "wrote " << xmlPath << "  (mask index=" << index
                  << " from " << w << "x" << h
                  << ", map=" << spaceModeName(space.mode)
                  << ", " << mask.shapes.size() << " shape(s), " << nodes << " node(s))\n";
        if (mask.shapes.empty())
            std::cout << "  note: nothing crossed the threshold -- try --threshold or --invert-input\n";
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << "\n";
        return 1;
    }
    return 0;
}
