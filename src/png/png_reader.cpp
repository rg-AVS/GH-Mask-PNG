#include "png_reader.h"
#include "../common/checksums.h"
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <unordered_map>

// ============================================================================
// Minimal DEFLATE (RFC 1951) decompressor -- "just enough inflate" to read
// real-world PNG IDAT streams. Not optimized for speed (bit-by-bit Huffman
// decode); optimized for being easy to read and verify against the spec.
// ============================================================================
namespace {

class BitReader {
public:
    explicit BitReader(const std::vector<uint8_t>& d) : data(d) {}

    // One bit at a time, LSB-first within each byte (the DEFLATE bitstream
    // convention for everything -- Huffman codes and plain integers alike;
    // only the *order in which multi-bit values are built* differs, see
    // getBitsLSB vs the Huffman decode loop in readSymbol()).
    int getBit() {
        if (bytePos >= data.size()) throw std::runtime_error("inflate: unexpected end of stream");
        int bit = (data[bytePos] >> bitPos) & 1;
        bitPos++;
        if (bitPos == 8) { bitPos = 0; bytePos++; }
        return bit;
    }

    // Reads n bits and returns them as a little-endian integer (first bit
    // read is the LOW-order bit of the result) -- used for stored-block
    // lengths, HLIT/HDIST/HCLEN, code-length-code lengths, and length/
    // distance extra bits.
    uint32_t getBitsLSB(int nBits) {
        uint32_t v = 0;
        for (int i = 0; i < nBits; i++) v |= (uint32_t)getBit() << i;
        return v;
    }

    void alignToByte() {
        if (bitPos != 0) { bitPos = 0; bytePos++; }
    }

    uint8_t getByte() {
        if (bytePos >= data.size()) throw std::runtime_error("inflate: unexpected end of stream");
        return data[bytePos++];
    }

    bool atEnd() const { return bytePos >= data.size(); }

private:
    const std::vector<uint8_t>& data;
    size_t bytePos = 0;
    int bitPos = 0;
};

// Canonical Huffman decode table: given code lengths per symbol (0 = symbol
// unused), builds a map from (length, code) to symbol. Decoding then reads
// one bit at a time, building `code = (code << 1) | bit` (Huffman codes are
// packed MSB-first, unlike every other field in DEFLATE), until the
// (length, code) pair matches an assigned symbol.
struct HuffmanTable {
    // codeByLenAndValue[len] maps code value -> symbol, for codes of exactly that length.
    std::vector<std::unordered_map<uint32_t, int>> codeByLenAndValue;
    int maxLen = 0;

    static HuffmanTable build(const std::vector<int>& lengths) {
        HuffmanTable table;
        int maxBits = 0;
        for (int l : lengths) maxBits = std::max(maxBits, l);
        table.maxLen = maxBits;
        table.codeByLenAndValue.resize(maxBits + 1);

        std::vector<int> blCount(maxBits + 1, 0);
        for (int l : lengths) if (l > 0) blCount[l]++;

        std::vector<int> nextCode(maxBits + 1, 0);
        int code = 0;
        for (int bits = 1; bits <= maxBits; bits++) {
            code = (code + blCount[bits - 1]) << 1;
            nextCode[bits] = code;
        }
        for (size_t sym = 0; sym < lengths.size(); sym++) {
            int len = lengths[sym];
            if (len == 0) continue;
            int c = nextCode[len]++;
            table.codeByLenAndValue[len][(uint32_t)c] = (int)sym;
        }
        return table;
    }

    int decode(BitReader& br) const {
        uint32_t code = 0;
        for (int len = 1; len <= maxLen; len++) {
            code = (code << 1) | (uint32_t)br.getBit();
            auto& m = codeByLenAndValue[len];
            auto it = m.find(code);
            if (it != m.end()) return it->second;
        }
        throw std::runtime_error("inflate: invalid Huffman code (no match up to max length)");
    }
};

// RFC 1951 3.2.5 length/distance extra-bit tables.
const int LEN_BASE[29]  = {3,4,5,6,7,8,9,10,11,13,15,17,19,23,27,31,35,43,51,59,67,83,99,115,131,163,195,227,258};
const int LEN_EXTRA[29] = {0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2,3,3,3,3,4,4,4,4,5,5,5,5,0};
const int DIST_BASE[30]  = {1,2,3,4,5,7,9,13,17,25,33,49,65,97,129,193,257,385,513,769,1025,1537,2049,3073,4097,6145,8193,12289,16385,24577};
const int DIST_EXTRA[30] = {0,0,0,0,1,1,2,2,3,3,4,4,5,5,6,6,7,7,8,8,9,9,10,10,11,11,12,12,13,13};
const int CLEN_ORDER[19] = {16,17,18,0,8,7,9,6,10,5,11,4,12,3,13,2,14,1,15};

HuffmanTable fixedLiteralTable() {
    std::vector<int> lengths(288);
    for (int i = 0; i <= 143; i++) lengths[i] = 8;
    for (int i = 144; i <= 255; i++) lengths[i] = 9;
    for (int i = 256; i <= 279; i++) lengths[i] = 7;
    for (int i = 280; i <= 287; i++) lengths[i] = 8;
    return HuffmanTable::build(lengths);
}
HuffmanTable fixedDistanceTable() {
    std::vector<int> lengths(30, 5);
    return HuffmanTable::build(lengths);
}

void inflateBlock(BitReader& br, const HuffmanTable& litTable, const HuffmanTable& distTable, std::vector<uint8_t>& out) {
    for (;;) {
        int sym = litTable.decode(br);
        if (sym < 256) {
            out.push_back((uint8_t)sym);
        } else if (sym == 256) {
            return; // end of block
        } else {
            int idx = sym - 257;
            if (idx >= 29) throw std::runtime_error("inflate: invalid length symbol");
            int length = LEN_BASE[idx] + (int)br.getBitsLSB(LEN_EXTRA[idx]);
            int distSym = distTable.decode(br);
            if (distSym >= 30) throw std::runtime_error("inflate: invalid distance symbol");
            int distance = DIST_BASE[distSym] + (int)br.getBitsLSB(DIST_EXTRA[distSym]);
            if ((size_t)distance > out.size())
                throw std::runtime_error("inflate: back-reference distance exceeds output so far");
            size_t start = out.size() - distance;
            for (int i = 0; i < length; i++) out.push_back(out[start + i]); // byte-by-byte: source may overlap dest
        }
    }
}

std::vector<uint8_t> inflateRaw(const std::vector<uint8_t>& deflateData) {
    BitReader br(deflateData);
    std::vector<uint8_t> out;
    bool final = false;
    while (!final) {
        final = br.getBit() != 0;
        int btype = (int)br.getBitsLSB(2);
        if (btype == 0) {
            br.alignToByte();
            uint8_t lenLo = br.getByte(), lenHi = br.getByte();
            uint8_t nlenLo = br.getByte(), nlenHi = br.getByte();
            uint16_t len = (uint16_t)(lenLo | (lenHi << 8));
            uint16_t nlen = (uint16_t)(nlenLo | (nlenHi << 8));
            if ((uint16_t)~len != nlen) throw std::runtime_error("inflate: stored block LEN/NLEN mismatch");
            for (int i = 0; i < len; i++) out.push_back(br.getByte());
        } else if (btype == 1) {
            static const HuffmanTable lit = fixedLiteralTable();
            static const HuffmanTable dist = fixedDistanceTable();
            inflateBlock(br, lit, dist, out);
        } else if (btype == 2) {
            int hlit = (int)br.getBitsLSB(5) + 257;
            int hdist = (int)br.getBitsLSB(5) + 1;
            int hclen = (int)br.getBitsLSB(4) + 4;
            std::vector<int> clLengths(19, 0);
            for (int i = 0; i < hclen; i++) clLengths[CLEN_ORDER[i]] = (int)br.getBitsLSB(3);
            HuffmanTable clTable = HuffmanTable::build(clLengths);

            std::vector<int> lengths;
            lengths.reserve(hlit + hdist);
            while ((int)lengths.size() < hlit + hdist) {
                int sym = clTable.decode(br);
                if (sym <= 15) {
                    lengths.push_back(sym);
                } else if (sym == 16) {
                    if (lengths.empty()) throw std::runtime_error("inflate: repeat code 16 with no previous length");
                    int repeat = 3 + (int)br.getBitsLSB(2);
                    int prev = lengths.back();
                    for (int i = 0; i < repeat; i++) lengths.push_back(prev);
                } else if (sym == 17) {
                    int repeat = 3 + (int)br.getBitsLSB(3);
                    for (int i = 0; i < repeat; i++) lengths.push_back(0);
                } else { // 18
                    int repeat = 11 + (int)br.getBitsLSB(7);
                    for (int i = 0; i < repeat; i++) lengths.push_back(0);
                }
            }
            std::vector<int> litLengths(lengths.begin(), lengths.begin() + hlit);
            std::vector<int> distLengths(lengths.begin() + hlit, lengths.begin() + hlit + hdist);
            HuffmanTable litTable = HuffmanTable::build(litLengths);
            HuffmanTable distTable = HuffmanTable::build(distLengths);
            inflateBlock(br, litTable, distTable, out);
        } else {
            throw std::runtime_error("inflate: reserved block type 3");
        }
    }
    return out;
}

// Strips the 2-byte zlib header and 4-byte Adler-32 trailer around a raw
// DEFLATE stream (this is the "zlib format", RFC 1950, which is what PNG's
// IDAT data is). The Adler-32 is checked but not fatal -- a corrupt
// trailer shouldn't hide already-successfully-decoded pixel data from the
// caller.
std::vector<uint8_t> zlibInflate(const std::vector<uint8_t>& zlibData) {
    if (zlibData.size() < 6) throw std::runtime_error("inflate: zlib stream too short");
    uint8_t cmf = zlibData[0];
    if ((cmf & 0x0F) != 8) throw std::runtime_error("inflate: not a DEFLATE zlib stream (unexpected CMF)");
    std::vector<uint8_t> body(zlibData.begin() + 2, zlibData.end() - 4);
    std::vector<uint8_t> out = inflateRaw(body);

    uint32_t expectedAdler = ((uint32_t)zlibData[zlibData.size() - 4] << 24) |
                              ((uint32_t)zlibData[zlibData.size() - 3] << 16) |
                              ((uint32_t)zlibData[zlibData.size() - 2] << 8) |
                              (uint32_t)zlibData[zlibData.size() - 1];
    uint32_t actualAdler = adler32_update(1, out.data(), out.size());
    if (expectedAdler != actualAdler) {
        // Non-fatal: surfaced via stderr rather than thrown, since the
        // pixel data itself decoded fine either way.
        fprintf(stderr, "png_reader: warning: zlib Adler-32 mismatch (stream may be truncated)\n");
    }
    return out;
}

// ============================================================================
// PNG scanline defiltering (PNG spec section 9, filter types 0-4).
// ============================================================================
uint8_t paethPredictor(int a, int b, int c) {
    int p = a + b - c;
    int pa = std::abs(p - a), pb = std::abs(p - b), pc = std::abs(p - c);
    if (pa <= pb && pa <= pc) return (uint8_t)a;
    if (pb <= pc) return (uint8_t)b;
    return (uint8_t)c;
}

void unfilter(std::vector<uint8_t>& raw, int width, int height, int bpp) {
    int stride = width * bpp;
    std::vector<uint8_t> prevRow(stride, 0);
    for (int y = 0; y < height; y++) {
        uint8_t* row = raw.data() + (size_t)y * (stride + 1);
        uint8_t filterType = row[0];
        uint8_t* pixels = row + 1;
        for (int x = 0; x < stride; x++) {
            int a = (x >= bpp) ? pixels[x - bpp] : 0;   // left
            int b = prevRow[x];                          // up
            int c = (x >= bpp) ? prevRow[x - bpp] : 0;   // up-left
            uint8_t recon;
            switch (filterType) {
                case 0: recon = pixels[x]; break;                                  // None
                case 1: recon = (uint8_t)(pixels[x] + a); break;                    // Sub
                case 2: recon = (uint8_t)(pixels[x] + b); break;                    // Up
                case 3: recon = (uint8_t)(pixels[x] + (uint8_t)((a + b) / 2)); break; // Average
                case 4: recon = (uint8_t)(pixels[x] + paethPredictor(a, b, c)); break; // Paeth
                default: throw std::runtime_error("png_reader: invalid filter type " + std::to_string(filterType));
            }
            pixels[x] = recon;
        }
        std::memcpy(prevRow.data(), pixels, stride);
    }
}

} // namespace

// ============================================================================
// PNG chunk reading
// ============================================================================
PngImage readPng(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("readPng: cannot open " + path);
    std::stringstream ss;
    ss << in.rdbuf();
    std::string content = ss.str();
    const uint8_t* data = (const uint8_t*)content.data();
    size_t n = content.size();

    static const uint8_t sig[8] = {0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A};
    if (n < 8 || std::memcmp(data, sig, 8) != 0) throw std::runtime_error("readPng: not a PNG file (bad signature)");

    size_t pos = 8;
    int width = 0, height = 0, bitDepth = 0, colorType = 0, interlace = 0;
    std::vector<uint8_t> idat;
    bool sawIHDR = false, sawIEND = false;

    while (pos + 8 <= n && !sawIEND) {
        uint32_t len = ((uint32_t)data[pos] << 24) | ((uint32_t)data[pos+1] << 16) | ((uint32_t)data[pos+2] << 8) | data[pos+3];
        std::string type((const char*)data + pos + 4, 4);
        size_t dataStart = pos + 8;
        if (dataStart + len + 4 > n) throw std::runtime_error("readPng: truncated chunk");

        if (type == "IHDR") {
            if (len < 13) throw std::runtime_error("readPng: IHDR too short");
            const uint8_t* d = data + dataStart;
            width = (int)(((uint32_t)d[0] << 24) | ((uint32_t)d[1] << 16) | ((uint32_t)d[2] << 8) | d[3]);
            height = (int)(((uint32_t)d[4] << 24) | ((uint32_t)d[5] << 16) | ((uint32_t)d[6] << 8) | d[7]);
            bitDepth = d[8];
            colorType = d[9];
            interlace = d[12];
            sawIHDR = true;
        } else if (type == "IDAT") {
            idat.insert(idat.end(), data + dataStart, data + dataStart + len);
        } else if (type == "IEND") {
            sawIEND = true;
        }
        // Other ancillary chunks (gAMA, pHYs, tEXt, ...) are intentionally
        // ignored -- this reader only cares about pixels.
        pos = dataStart + len + 4; // skip CRC
    }

    if (!sawIHDR) throw std::runtime_error("readPng: missing IHDR");
    if (bitDepth != 8) throw std::runtime_error("readPng: only 8-bit depth is supported (got " + std::to_string(bitDepth) + ")");
    if (interlace != 0) throw std::runtime_error("readPng: interlaced (Adam7) PNGs are not supported");

    int channels;
    switch (colorType) {
        case 0: channels = 1; break; // grayscale
        case 2: channels = 3; break; // RGB
        case 6: channels = 4; break; // RGBA
        default: throw std::runtime_error("readPng: unsupported color type " + std::to_string(colorType) +
                                           " (palette and grayscale+alpha aren't implemented)");
    }

    std::vector<uint8_t> raw = zlibInflate(idat);
    size_t expectedRaw = (size_t)(width * channels + 1) * height;
    if (raw.size() != expectedRaw)
        throw std::runtime_error("readPng: decompressed size mismatch (got " + std::to_string(raw.size()) +
                                  ", expected " + std::to_string(expectedRaw) + ")");

    unfilter(raw, width, height, channels);

    PngImage img;
    img.width = width;
    img.height = height;
    img.channels = channels;
    img.pixels.resize((size_t)width * height * channels);
    for (int y = 0; y < height; y++) {
        const uint8_t* src = raw.data() + (size_t)y * (width * channels + 1) + 1; // skip filter-type byte
        std::memcpy(img.pixels.data() + (size_t)y * width * channels, src, (size_t)width * channels);
    }
    return img;
}

std::vector<uint8_t> readGrayscalePng(const std::string& path, int* outW, int* outH) {
    PngImage img = readPng(path);
    if (outW) *outW = img.width;
    if (outH) *outH = img.height;
    if (img.channels == 1) return img.pixels;

    std::vector<uint8_t> gray((size_t)img.width * img.height);
    for (size_t i = 0; i < gray.size(); i++) {
        const uint8_t* px = img.pixels.data() + i * img.channels;
        if (img.channels == 4) {
            gray[i] = px[3]; // treat alpha as the mask value, matching png_writer's Gray8 convention
        } else {
            gray[i] = (uint8_t)(0.299 * px[0] + 0.587 * px[1] + 0.114 * px[2]);
        }
    }
    return gray;
}
