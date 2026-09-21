#include "png_writer.h"
#include "../common/checksums.h"
#include "deflate.h"
#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <stdexcept>

namespace {

void putBE32(std::vector<uint8_t>& out, uint32_t v) {
    out.push_back((v >> 24) & 0xFF); out.push_back((v >> 16) & 0xFF);
    out.push_back((v >> 8) & 0xFF);  out.push_back(v & 0xFF);
}

void writeChunk(std::vector<uint8_t>& out, const char* type, const std::vector<uint8_t>& data) {
    putBE32(out, (uint32_t)data.size());
    std::vector<uint8_t> typeAndData(4 + data.size());
    std::memcpy(typeAndData.data(), type, 4);
    if (!data.empty()) std::memcpy(typeAndData.data() + 4, data.data(), data.size());
    out.insert(out.end(), typeAndData.begin(), typeAndData.end());
    uint32_t crc = crc32_update(0, typeAndData.data(), typeAndData.size());
    putBE32(out, crc);
}

// PNG lets each row pick one of five filters. Trying all five and keeping
// the one with the smallest sum of absolute signed values is the standard
// heuristic (and what libpng does by default): it costs one pass per row
// and it is what lets a flat mask image compress down to almost nothing.
uint8_t paeth(uint8_t a, uint8_t b, uint8_t c) {
    int p = (int)a + (int)b - (int)c;
    int pa = std::abs(p - a), pb = std::abs(p - b), pc = std::abs(p - c);
    if (pa <= pb && pa <= pc) return a;
    return pb <= pc ? b : c;
}

void filterRow(int filter, const uint8_t* cur, const uint8_t* prev, int stride, int bpp,
               std::vector<uint8_t>& out) {
    for (int i = 0; i < stride; i++) {
        uint8_t a = i >= bpp ? cur[i - bpp] : 0;
        uint8_t b = prev ? prev[i] : 0;
        uint8_t c = (prev && i >= bpp) ? prev[i - bpp] : 0;
        uint8_t v;
        switch (filter) {
            case 1:  v = (uint8_t)(cur[i] - a); break;
            case 2:  v = (uint8_t)(cur[i] - b); break;
            case 3:  v = (uint8_t)(cur[i] - (uint8_t)(((int)a + (int)b) / 2)); break;
            case 4:  v = (uint8_t)(cur[i] - paeth(a, b, c)); break;
            default: v = cur[i]; break;
        }
        out.push_back(v);
    }
}

// Builds the filtered scanline stream PNG compresses: one filter-type byte
// per row, then that row's filtered bytes.
std::vector<uint8_t> filterImage(const std::vector<uint8_t>& pixels, int width, int height, int channels) {
    const int stride = width * channels;
    const int bpp = channels;
    std::vector<uint8_t> raw;
    raw.reserve((size_t)(stride + 1) * height);

    std::vector<uint8_t> candidate, best;
    for (int y = 0; y < height; y++) {
        const uint8_t* cur = pixels.data() + (size_t)y * stride;
        const uint8_t* prev = y > 0 ? pixels.data() + (size_t)(y - 1) * stride : nullptr;

        int bestFilter = 0;
        long bestScore = -1;
        for (int f = 0; f <= 4; f++) {
            candidate.clear();
            filterRow(f, cur, prev, stride, bpp, candidate);
            long score = 0;
            for (uint8_t v : candidate) score += (v < 128) ? v : (256 - v);
            if (bestScore < 0 || score < bestScore) { bestScore = score; bestFilter = f; best = candidate; }
        }
        raw.push_back((uint8_t)bestFilter);
        raw.insert(raw.end(), best.begin(), best.end());
    }
    return raw;
}

} // namespace

void writePng(const std::string& path, const std::vector<uint8_t>& pixels, int width, int height, PngColorType type) {
    int channels = (type == PngColorType::Gray8) ? 1 : 4;
    size_t expected = (size_t)width * height * channels;
    if (pixels.size() != expected)
        throw std::runtime_error("writePng: pixel buffer size doesn't match width*height*channels");

    std::vector<uint8_t> idatData = zlibCompress(filterImage(pixels, width, height, channels));

    std::vector<uint8_t> out;
    static const uint8_t sig[8] = {0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A};
    out.insert(out.end(), sig, sig + 8);

    std::vector<uint8_t> ihdr;
    putBE32(ihdr, (uint32_t)width);
    putBE32(ihdr, (uint32_t)height);
    ihdr.push_back(8);                    // bit depth
    ihdr.push_back((uint8_t)type);        // color type: 0 = grayscale, 6 = RGBA
    ihdr.push_back(0);                    // compression method
    ihdr.push_back(0);                    // filter method
    ihdr.push_back(0);                    // interlace method
    writeChunk(out, "IHDR", ihdr);
    writeChunk(out, "IDAT", idatData);
    writeChunk(out, "IEND", {});

    std::ofstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("writePng: cannot open " + path + " for writing");
    f.write((const char*)out.data(), out.size());
}
