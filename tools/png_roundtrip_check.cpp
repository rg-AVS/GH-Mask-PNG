// png_roundtrip_check.cpp -- regression test for the png_reader/png_writer
// pair. Reads ANY PNG given on the command line (this is the real test of
// png_reader's from-scratch inflate: point it at a PNG saved by GIMP,
// Photoshop, a browser, Python/PIL, etc -- something that uses real
// DEFLATE compression and PNG filtering, not just this project's own
// uncompressed output), re-encodes it with png_writer, reads that back,
// and reports whether the pixels survived exactly.
#include <iostream>
#include <string>
#include "../src/png/png_reader.h"
#include "../src/png/png_writer.h"

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "usage: " << argv[0] << " input.png [tmp_out.png]\n";
        return 1;
    }
    std::string inPath = argv[1];
    std::string tmpPath = argc >= 3 ? argv[2] : "/tmp/png_roundtrip_check.png";

    try {
        PngImage img = readPng(inPath);
        std::cout << "read " << inPath << ": " << img.width << "x" << img.height
                  << ", " << img.channels << " channel(s)\n";

        PngColorType type = (img.channels == 1) ? PngColorType::Gray8 : PngColorType::RGBA8;
        std::vector<uint8_t> pixelsForWrite = img.pixels;
        if (img.channels == 3) {
            // png_writer only emits Gray8/RGBA8 -- expand RGB to RGBA (alpha=255)
            // for this round-trip test rather than adding an RGB8 writer path.
            pixelsForWrite.resize((size_t)img.width * img.height * 4);
            for (int i = (int)img.width * img.height - 1; i >= 0; i--) {
                pixelsForWrite[i * 4 + 0] = img.pixels[i * 3 + 0];
                pixelsForWrite[i * 4 + 1] = img.pixels[i * 3 + 1];
                pixelsForWrite[i * 4 + 2] = img.pixels[i * 3 + 2];
                pixelsForWrite[i * 4 + 3] = 255;
            }
            type = PngColorType::RGBA8;
        }
        writePng(tmpPath, pixelsForWrite, img.width, img.height, type);
        std::cout << "wrote " << tmpPath << "\n";

        PngImage reread = readPng(tmpPath);
        if (reread.width != img.width || reread.height != img.height) {
            std::cerr << "FAIL: dimensions changed\n";
            return 1;
        }
        size_t mismatches = 0;
        size_t n = std::min(pixelsForWrite.size(), reread.pixels.size());
        for (size_t i = 0; i < n; i++) if (pixelsForWrite[i] != reread.pixels[i]) mismatches++;
        std::cout << "pixel bytes compared: " << n << ", mismatches: " << mismatches << "\n";
        if (mismatches > 0) {
            std::cerr << "FAIL: round-trip changed pixel data\n";
            return 1;
        }
        std::cout << "OK: pixels round-tripped exactly through png_reader -> png_writer -> png_reader\n";
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << "\n";
        return 1;
    }
    return 0;
}
