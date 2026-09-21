// png_writer.h -- zero-dependency PNG encoder (no libpng, no zlib).
// Supports 8-bit grayscale and 8-bit RGBA output. Rows are adaptively
// filtered (all five PNG filter types tried per row, smallest kept) and
// compressed by deflate.h, this project's own fixed-Huffman DEFLATE.
// Output is a normal, normally-sized PNG any viewer opens.
//
// If the host product already links zlib, deflate.h can be deleted and
// zlibCompress() replaced with compress2() -- the call site is one line.
#pragma once
#include <cstdint>
#include <string>
#include <vector>

enum class PngColorType { Gray8 = 0, RGBA8 = 6 };

// `pixels` must be tightly packed, row-major, top-to-bottom: 1 byte/pixel
// for Gray8, 4 bytes/pixel (R,G,B,A) for RGBA8.
void writePng(const std::string& path, const std::vector<uint8_t>& pixels, int width, int height, PngColorType type);

// Convenience overload for the common grayscale mask case.
inline void writeGrayscalePng(const std::string& path, const std::vector<uint8_t>& gray, int w, int h) {
    writePng(path, gray, w, h, PngColorType::Gray8);
}
