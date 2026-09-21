#include "png_writer.h"
#include "../common/checksums.h"
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

// Wraps `raw` in a minimal zlib stream: 2-byte header, then `raw` split
// into DEFLATE "stored" (BTYPE=00, uncompressed) blocks, then Adler-32.
std::vector<uint8_t> zlibStoreUncompressed(const std::vector<uint8_t>& raw) {
    std::vector<uint8_t> out;
    out.push_back(0x78); out.push_back(0x01); // CMF/FLG: deflate, 32K window, default level flag

    size_t pos = 0, n = raw.size();
    const size_t MAXB = 65535;
    if (n == 0) {
        out.push_back(1); out.push_back(0); out.push_back(0); out.push_back(0xFF); out.push_back(0xFF);
    }
    while (pos < n) {
        size_t blockLen = std::min(MAXB, n - pos);
        bool last = (pos + blockLen >= n);
        out.push_back(last ? 1 : 0); // BFINAL | BTYPE=00
        uint16_t len = (uint16_t)blockLen;
        uint16_t nlen = (uint16_t)~len;
        out.push_back(len & 0xFF); out.push_back((len >> 8) & 0xFF);
        out.push_back(nlen & 0xFF); out.push_back((nlen >> 8) & 0xFF);
        out.insert(out.end(), raw.begin() + pos, raw.begin() + pos + blockLen);
        pos += blockLen;
    }

    uint32_t adler = adler32_update(1, raw.data(), raw.size());
    out.push_back((adler >> 24) & 0xFF); out.push_back((adler >> 16) & 0xFF);
    out.push_back((adler >> 8) & 0xFF);  out.push_back(adler & 0xFF);
    return out;
}

} // namespace

void writePng(const std::string& path, const std::vector<uint8_t>& pixels, int width, int height, PngColorType type) {
    int channels = (type == PngColorType::Gray8) ? 1 : 4;
    size_t expected = (size_t)width * height * channels;
    if (pixels.size() != expected)
        throw std::runtime_error("writePng: pixel buffer size doesn't match width*height*channels");

    std::vector<uint8_t> raw;
    raw.reserve((size_t)(width * channels + 1) * height);
    for (int y = 0; y < height; y++) {
        raw.push_back(0); // filter type 0 ("None") for every row -- simplest correct choice
        raw.insert(raw.end(), pixels.begin() + (size_t)y * width * channels,
                   pixels.begin() + (size_t)(y + 1) * width * channels);
    }
    std::vector<uint8_t> idatData = zlibStoreUncompressed(raw);

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
