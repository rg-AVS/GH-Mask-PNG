// deflate.h -- a small, from-scratch DEFLATE compressor (RFC 1951) with the
// zlib wrapper (RFC 1950), so png_writer can produce normally-sized files
// without linking zlib.
//
// It emits a single fixed-Huffman block with LZ77 back-references found by
// hash chains. That is not the smallest possible output -- real zlib also
// builds per-block dynamic Huffman trees -- but it is a few hundred lines
// instead of a few thousand, and on the flat runs a mask image is made of
// it gets within a small factor of zlib for a fraction of the code. If a
// product already links zlib, deleting this file and calling compress2()
// from png_writer is a two-line change.
#pragma once
#include <cstdint>
#include <vector>

// Raw DEFLATE stream, no wrapper.
std::vector<uint8_t> deflateFixed(const std::vector<uint8_t>& data);

// The same stream inside a zlib container (2-byte header + Adler-32), which
// is what a PNG IDAT chunk holds.
std::vector<uint8_t> zlibCompress(const std::vector<uint8_t>& data);
