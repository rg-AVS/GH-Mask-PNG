// checksums.h -- the two checksums reading a PNG needs: CRC-32 over each
// chunk, and Adler-32 over the inflated image data.
#pragma once
#include <cstdint>
#include <cstddef>

// PNG chunk CRC-32 (ISO 3309 / ITU-T V.42, poly 0xEDB88320, same as zlib/zip).
uint32_t crc32_update(uint32_t crc, const uint8_t* data, size_t len);

// zlib stream Adler-32 checksum, verified after inflating the image data.
uint32_t adler32_update(uint32_t adler, const uint8_t* data, size_t len);
