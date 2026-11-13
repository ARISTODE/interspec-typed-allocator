// Native reference for the magick/libpng port (tracker item I8): the
// decode-then-encode workload of the interspec-artifact PNG microbenchmark,
// calling the same shim (magick_png_shim.c) without a sandbox, with the output
// format of png_app_bench.cpp.
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

#include "magick_png_shim.h"

namespace {
uint64_t fnv(const unsigned char* p, size_t n) {
  uint64_t h = UINT64_C(1469598103934665603);
  for (size_t i = 0; i < n; i++) {
    h ^= p[i];
    h *= UINT64_C(1099511628211);
  }
  return h;
}
}  // namespace

int main(int argc, char** argv) {
  if (argc != 3) {
    std::fprintf(stderr, "usage: %s PNG ITERATIONS\n", argv[0]);
    return 2;
  }
  try {
    std::ifstream file(argv[1], std::ios::binary);
    if (!file) throw std::runtime_error("open_input");
    std::vector<unsigned char> png((std::istreambuf_iterator<char>(file)),
                                   std::istreambuf_iterator<char>());
    const uint32_t iterations = static_cast<uint32_t>(std::stoul(argv[2]));
    if (iterations == 0 || png.empty()) throw std::runtime_error("arguments");

    uint32_t width = 0, height = 0;
    std::vector<unsigned char> rgba, encoded;
    const auto start = std::chrono::steady_clock::now();
    for (uint32_t i = 0; i < iterations; ++i) {
      uint32_t size = 0;
      unsigned char* pixels = magickpng_decode_rgba(
          png.data(), static_cast<uint32_t>(png.size()), &width, &height, &size);
      if (!pixels || size != uint64_t{width} * height * 4) throw std::runtime_error("decode");
      rgba.assign(pixels, pixels + size);
      magickpng_free(pixels);
      uint32_t png_size = 0;
      unsigned char* out = magickpng_encode_rgba(rgba.data(), width, height, &png_size);
      if (!out || png_size == 0) throw std::runtime_error("encode");
      encoded.assign(out, out + png_size);
      magickpng_free(out);
    }
    const auto finish = std::chrono::steady_clock::now();
    std::printf(
        "PNG_BENCH variant=native iterations=%u input_bytes=%zu width=%u height=%u "
        "rgba_bytes=%zu rgba_fnv=%016llx png_bytes=%zu png_fnv=%016llx checks=0 "
        "elapsed_ns=%llu\n",
        iterations, png.size(), width, height, rgba.size(),
        static_cast<unsigned long long>(fnv(rgba.data(), rgba.size())), encoded.size(),
        static_cast<unsigned long long>(fnv(encoded.data(), encoded.size())),
        static_cast<unsigned long long>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(finish - start).count()));
    return 0;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "png benchmark error: %s\n", error.what());
    return 1;
  }
}
