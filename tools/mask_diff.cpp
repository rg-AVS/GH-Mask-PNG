// mask_diff.cpp -- CLI: compare two grayscale PNGs and say how close they
// are. This is what turns "does PNG -> mask -> PNG come back unchanged?"
// into a number you can put in a build script.
//
//   mask_diff original.png roundtrip.png --out delta.png
//
// Exit code is 0 when the two agree within --tolerance, 2 when they do not,
// 1 on an error -- so it works as a test.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>
#include "../src/png/png_reader.h"
#include "../src/png/png_writer.h"
#include "cli.h"

int main(int argc, char** argv) {
    Cli cli(argc, argv);
    if (cli.positional.size() < 2 || cli.has("--help")) {
        std::cerr <<
            "usage: mask_diff a.png b.png [options]\n"
            "  --tolerance N   max per-pixel difference still counted as equal (default 0)\n"
            "  --out FILE      write a PNG of the absolute difference\n";
        return cli.has("--help") ? 0 : 1;
    }

    try {
        int aw = 0, ah = 0, bw = 0, bh = 0;
        auto a = readGrayscalePng(cli.positional[0], &aw, &ah);
        auto b = readGrayscalePng(cli.positional[1], &bw, &bh);

        if (aw != bw || ah != bh) {
            std::cout << "DIFFERENT SIZE  " << aw << "x" << ah << " vs " << bw << "x" << bh << "\n";
            return 2;
        }

        int tolerance = cli.integer("--tolerance", 0);
        std::vector<uint8_t> delta(a.size());
        long long sum = 0, over = 0;
        int worst = 0;
        for (size_t i = 0; i < a.size(); i++) {
            int d = std::abs((int)a[i] - (int)b[i]);
            delta[i] = (uint8_t)d;
            sum += d;
            worst = std::max(worst, d);
            if (d > tolerance) over++;
        }

        double mean = a.empty() ? 0.0 : (double)sum / a.size();
        double pct = a.empty() ? 0.0 : 100.0 * over / a.size();
        std::cout << aw << "x" << ah
                  << "  max_diff=" << worst
                  << "  mean_diff=" << mean
                  << "  pixels_over_tolerance=" << over << " (" << pct << "%)\n";

        if (cli.has("--out")) {
            writeGrayscalePng(cli.str("--out", "diff.png"), delta, aw, ah);
            std::cout << "wrote " << cli.str("--out", "diff.png") << "\n";
        }

        if (over == 0) { std::cout << "MATCH (within tolerance " << tolerance << ")\n"; return 0; }
        std::cout << "MISMATCH\n";
        return 2;
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << "\n";
        return 1;
    }
}
