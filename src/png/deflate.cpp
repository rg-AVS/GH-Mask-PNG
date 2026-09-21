#include "deflate.h"
#include "../common/checksums.h"
#include <algorithm>
#include <cstring>

namespace {

// DEFLATE packs bits low-to-high within a byte, but a Huffman code is
// written most-significant-bit first. Keeping those two rules in separate
// methods is the whole trick to not getting this wrong.
struct BitWriter {
    std::vector<uint8_t>& out;
    uint32_t buf = 0;
    int count = 0;
    explicit BitWriter(std::vector<uint8_t>& o) : out(o) {}

    void bits(uint32_t v, int n) {
        buf |= (v & ((1u << n) - 1)) << count;
        count += n;
        while (count >= 8) { out.push_back((uint8_t)(buf & 0xFF)); buf >>= 8; count -= 8; }
    }
    void huff(uint32_t code, int n) {
        for (int i = n - 1; i >= 0; i--) bits((code >> i) & 1, 1);
    }
    void flush() { if (count > 0) { out.push_back((uint8_t)(buf & 0xFF)); buf = 0; count = 0; } }
};

// RFC 1951 section 3.2.6: the fixed literal/length code.
void emitSymbol(BitWriter& bw, int sym) {
    if (sym <= 143)      bw.huff(0x30 + sym, 8);
    else if (sym <= 255) bw.huff(0x190 + sym - 144, 9);
    else if (sym <= 279) bw.huff(sym - 256, 7);
    else                 bw.huff(0xC0 + sym - 280, 8);
}

const int kLenBase[29]  = {3,4,5,6,7,8,9,10,11,13,15,17,19,23,27,31,35,43,51,59,67,83,99,115,131,163,195,227,258};
const int kLenExtra[29] = {0,0,0,0,0,0,0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4,  4,  5,  5,  5,  5,  0};
const int kDistBase[30]  = {1,2,3,4,5,7,9,13,17,25,33,49,65,97,129,193,257,385,513,769,1025,1537,2049,3073,4097,6145,8193,12289,16385,24577};
const int kDistExtra[30] = {0,0,0,0,1,1,2, 2, 3, 3, 4, 4, 5, 5,  6,  6,  7,  7,  8,  8,   9,   9,  10,  10,  11,  11,  12,   12,   13,   13};

void emitMatch(BitWriter& bw, int length, int distance) {
    int l = 28;
    while (l > 0 && kLenBase[l] > length) l--;
    emitSymbol(bw, 257 + l);
    if (kLenExtra[l]) bw.bits((uint32_t)(length - kLenBase[l]), kLenExtra[l]);

    int d = 29;
    while (d > 0 && kDistBase[d] > distance) d--;
    bw.huff((uint32_t)d, 5);   // fixed distance codes are 5 plain bits
    if (kDistExtra[d]) bw.bits((uint32_t)(distance - kDistBase[d]), kDistExtra[d]);
}

const int kWindow   = 32768;
const int kMinMatch = 3;
const int kMaxMatch = 258;
const int kHashBits = 15;
const int kHashSize = 1 << kHashBits;
const int kMaxChain = 128;   // how far back to search; the quality/speed dial

inline int hash3(const uint8_t* p) {
    return (int)((((uint32_t)p[0] << 10) ^ ((uint32_t)p[1] << 5) ^ (uint32_t)p[2]) & (kHashSize - 1));
}

} // namespace

std::vector<uint8_t> deflateFixed(const std::vector<uint8_t>& data) {
    std::vector<uint8_t> out;
    BitWriter bw(out);
    bw.bits(1, 1);   // BFINAL
    bw.bits(1, 2);   // BTYPE = 01, fixed Huffman

    const int n = (int)data.size();
    const uint8_t* d = data.data();
    std::vector<int> head(kHashSize, -1);
    std::vector<int> prev(std::max(n, 1), -1);

    auto insert = [&](int pos) {
        if (pos + kMinMatch > n) return;
        int h = hash3(d + pos);
        prev[pos] = head[h];
        head[h] = pos;
    };

    // Longest match for `pos`, searching the hash chain back to the window edge.
    auto findMatch = [&](int pos, int& bestLen, int& bestDist) {
        bestLen = 0; bestDist = 0;
        if (pos + kMinMatch > n) return;
        int limit = std::max(0, pos - kWindow);
        int maxLen = std::min(kMaxMatch, n - pos);
        int cand = head[hash3(d + pos)];
        for (int chain = 0; cand >= limit && cand >= 0 && chain < kMaxChain; chain++) {
            if (d[cand + bestLen] == d[pos + bestLen]) {   // cheap reject before memcmp
                int len = 0;
                while (len < maxLen && d[cand + len] == d[pos + len]) len++;
                if (len > bestLen) { bestLen = len; bestDist = pos - cand; if (len == maxLen) break; }
            }
            cand = prev[cand];
        }
        if (bestLen < kMinMatch) { bestLen = 0; bestDist = 0; }
    };

    int pos = 0;
    while (pos < n) {
        int len = 0, dist = 0;
        findMatch(pos, len, dist);

        // One-step lazy match: if starting a byte later does better, emit this
        // byte as a literal instead. Cheap, and worth a few percent.
        if (len >= kMinMatch && pos + 1 < n) {
            insert(pos);
            int nextLen = 0, nextDist = 0;
            findMatch(pos + 1, nextLen, nextDist);
            if (nextLen > len) {
                emitSymbol(bw, d[pos]);
                pos++;
                continue;
            }
            emitMatch(bw, len, dist);
            for (int i = 1; i < len; i++) insert(pos + i);
            pos += len;
            continue;
        }

        if (len >= kMinMatch) {
            emitMatch(bw, len, dist);
            for (int i = 0; i < len; i++) insert(pos + i);
            pos += len;
        } else {
            emitSymbol(bw, d[pos]);
            insert(pos);
            pos++;
        }
    }

    emitSymbol(bw, 256);   // end of block
    bw.flush();
    return out;
}

std::vector<uint8_t> zlibCompress(const std::vector<uint8_t>& data) {
    std::vector<uint8_t> out;
    out.push_back(0x78);   // CMF: deflate, 32K window
    out.push_back(0x01);   // FLG: no preset dict, and (0x7801 % 31) == 0 as required
    auto body = deflateFixed(data);
    out.insert(out.end(), body.begin(), body.end());
    uint32_t adler = adler32_update(1, data.data(), data.size());
    out.push_back((adler >> 24) & 0xFF); out.push_back((adler >> 16) & 0xFF);
    out.push_back((adler >> 8) & 0xFF);  out.push_back(adler & 0xFF);
    return out;
}
