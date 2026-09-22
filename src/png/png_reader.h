// png_reader.h -- zero-dependency PNG decoder (no libpng, no zlib).
// Implements its own DEFLATE inflate (stored + fixed + dynamic Huffman
// blocks, per RFC 1951) and PNG scanline unfiltering (per the PNG spec,
// filter types 0-4), so it can read REAL PNGs -- ones saved by Photoshop,
// GIMP, a browser, PIL, etc. That is the actual use case: a designer hands
// over artwork and it has to be read exactly as they saved it.
//
// Supported: bit depth 8, color type 0 (grayscale), 2 (RGB), 6 (RGBA).
// NOT supported (throws std::runtime_error naming what's missing):
// bit depths other than 8, palette images (color type 3), interlaced
// (Adam7) PNGs, grayscale+alpha (color type 4). All are addressable later;
// they just weren't needed for the sample files this was built against.
#pragma once
#include <cstdint>
#include <string>
#include <vector>

struct PngImage {
    int width = 0, height = 0;
    int channels = 0;                 // 1 = gray, 3 = RGB, 4 = RGBA
    std::vector<uint8_t> pixels;      // row-major, top-to-bottom, tightly packed
};

PngImage readPng(const std::string& path);

// Returns a PNG's ALPHA CHANNEL, and nothing else: what is solid is mask,
// what is see-through is not, and the colours are never read. Artwork is
// usually not white, so going on brightness would find the wrong thing -- or
// the exact inverse of what was drawn. Throws std::runtime_error, naming what
// to do about it, if the image has no alpha or is opaque everywhere.
std::vector<uint8_t> readMaskPng(const std::string& path, int* outW = nullptr, int* outH = nullptr);
