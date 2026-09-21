// xml_roundtrip_check.cpp -- regression test for the xml_reader/xml_writer
// pair: parse Masks.xml -> data model -> write it back out -> reparse ->
// compare every numeric field against the original. Reports the worst
// (max absolute) difference found; anything above float round-off (~1e-9)
// means something's actually wrong, not just text-formatting noise.
#include <algorithm>
#include <cmath>
#include <iostream>
#include <string>
#include "../mask/mask_model.h"

static double maxAbsDiffNode(const MaskNode& a, const MaskNode& b) {
    double d = 0;
    auto upd = [&](double x, double y) { d = std::max(d, std::abs(x - y)); };
    upd(a.pos.x, b.pos.x); upd(a.pos.y, b.pos.y);
    upd(a.inH.x, b.inH.x); upd(a.inH.y, b.inH.y);
    upd(a.outH.x, b.outH.x); upd(a.outH.y, b.outH.y);
    upd(a.featherPos.x, b.featherPos.x); upd(a.featherPos.y, b.featherPos.y);
    upd(a.featherIn.x, b.featherIn.x); upd(a.featherIn.y, b.featherIn.y);
    upd(a.featherOut.x, b.featherOut.x); upd(a.featherOut.y, b.featherOut.y);
    return d;
}

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "usage: " << argv[0] << " Masks.xml [tmp_out.xml]\n";
        return 1;
    }
    std::string xmlPath = argv[1];
    std::string tmpPath = argc >= 3 ? argv[2] : "/tmp/xml_roundtrip_check.xml";

    try {
        auto original = parseMasksXml(xmlPath);
        writeMasksXml(tmpPath, original);
        auto reparsed = parseMasksXml(tmpPath);

        if (original.size() != reparsed.size()) {
            std::cerr << "FAIL: mask count changed (" << original.size() << " -> " << reparsed.size() << ")\n";
            return 1;
        }

        double worst = 0;
        int totalNodes = 0;
        for (size_t mi = 0; mi < original.size(); mi++) {
            const auto& a = original[mi];
            const auto& b = reparsed[mi];
            if (a.shapes.size() != b.shapes.size()) {
                std::cerr << "FAIL: mask " << mi << " shape count changed\n";
                return 1;
            }
            worst = std::max(worst, std::abs(a.blur - b.blur));
            for (size_t si = 0; si < a.shapes.size(); si++) {
                const auto& sa = a.shapes[si];
                const auto& sb = b.shapes[si];
                if (sa.nodes.size() != sb.nodes.size()) {
                    std::cerr << "FAIL: mask " << mi << " shape " << si << " node count changed\n";
                    return 1;
                }
                worst = std::max(worst, std::abs(sa.level - sb.level));
                worst = std::max(worst, std::abs(sa.gamma - sb.gamma));
                for (size_t ni = 0; ni < sa.nodes.size(); ni++) {
                    worst = std::max(worst, maxAbsDiffNode(sa.nodes[ni], sb.nodes[ni]));
                    totalNodes++;
                }
            }
        }

        std::cout << "checked " << original.size() << " mask(s), " << totalNodes << " node(s) total\n";
        std::cout << "max absolute difference after parse -> write -> reparse: " << worst << "\n";
        if (worst > 1e-6) {
            std::cout << "^ that's bigger than float round-off -- something in the reader or writer is lossy\n";
            return 1;
        }
        std::cout << "OK: round-trip is numerically lossless (within float round-off)\n";
        std::cout << "(re-serialized file written to " << tmpPath << " for inspection)\n";
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << "\n";
        return 1;
    }
    return 0;
}
