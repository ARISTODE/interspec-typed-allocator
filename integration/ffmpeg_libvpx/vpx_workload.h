// Workload shared by vpx_app_bench.cpp and vpx_native_bench.cpp (tracker item
// I7): synthetic I420 frames, the encoder settings, and the running hashes.
// The artifact's workload is FFmpeg transcoding through libvpx; the artifact
// ships neither its patched FFmpeg nor its inputs, so the port drives the
// libvpx API directly: each frame is encoded with VP8 and the packets are
// decoded again.
#pragma once

#include <cstdint>
#include <vector>

namespace vpx_workload {

constexpr unsigned kBitrateKbps = 200;
constexpr int kCpuUsed = 4;
constexpr unsigned long kDeadline = 1000000;  // VPX_DL_GOOD_QUALITY

struct Frame {
  unsigned width = 0, height = 0;
  std::vector<unsigned char> y, u, v;
};

inline void fill(Frame& frame, unsigned width, unsigned height, unsigned index) {
  const unsigned cw = width / 2, ch = height / 2;
  frame.width = width;
  frame.height = height;
  frame.y.resize(size_t{width} * height);
  frame.u.resize(size_t{cw} * ch);
  frame.v.resize(size_t{cw} * ch);
  for (unsigned row = 0; row < height; ++row)
    for (unsigned col = 0; col < width; ++col)
      frame.y[size_t{row} * width + col] =
          static_cast<unsigned char>(16 + (((col + 2 * index) ^ (row + index)) % 200));
  for (unsigned row = 0; row < ch; ++row)
    for (unsigned col = 0; col < cw; ++col) {
      frame.u[size_t{row} * cw + col] = static_cast<unsigned char>(112 + ((col + index) % 32));
      frame.v[size_t{row} * cw + col] =
          static_cast<unsigned char>(112 + ((row + 2 * index) % 32));
    }
}

struct Fnv {
  uint64_t state = UINT64_C(1469598103934665603);
  void add(const unsigned char* p, size_t n) {
    for (size_t i = 0; i < n; i++) {
      state ^= p[i];
      state *= UINT64_C(1099511628211);
    }
  }
};

}  // namespace vpx_workload
