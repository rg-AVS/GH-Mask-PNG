// checksums.h -- CRC-32 (PNG chunk checksums) and Adler-32 (zlib stream
// checksum). Shared by png_reader and png_writer so the two don't each
// carry their own copy.
#pragma once
#include <cstdint>
#include <cstddef>

// PNG chunk CRC-32 (ISO 3309 / ITU-T V.42, poly 0xEDB88320, same as zlib/zip).
uint32_t crc32_update(uint32_t crc, const uint8_t* data, size_t len);

// zlib stream Adler-32 checksum.
uint32_t adler32_update(uint32_t adler, const uint8_t* data, size_t len);
