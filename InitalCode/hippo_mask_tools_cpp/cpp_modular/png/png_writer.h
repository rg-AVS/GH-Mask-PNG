// png_writer.h -- zero-dependency PNG encoder (no libpng, no zlib).
// Supports 8-bit grayscale and 8-bit RGBA output. Image data is stored
// using UNCOMPRESSED ("stored") DEFLATE blocks inside a minimal zlib
// wrapper -- fully spec-valid PNG, just larger than a compressed file
// would be. Swap in real zlib (deflate()) for production; this trades file
// size for having no external dependency at all, which is the point of a
// hand-off POC.
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
