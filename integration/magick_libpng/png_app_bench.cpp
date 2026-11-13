// Trusted program for the magick/libpng boundary (tracker item I8): the
// decode-then-encode workload of the interspec-artifact PNG microbenchmark,
// with libpng and zlib inside an RLBox wasm2c sandbox.
//
// T-level interface (as in the artifact wrapper):
//   decode_rgba(png, png_len, &w, &h, &rgba, &rgba_len)
//   encode_rgba(rgba, w, h, &png, &png_len)
#define RLBOX_USE_EXCEPTIONS
#define RLBOX_USE_STATIC_CALLS() rlbox_wasm2c_sandbox_lookup_symbol
#define RLBOX_WASM2C_MODULE_NAME glue__lib__wasm2c
#include "glue_lib_wasm2c.h"
#include "rlbox.hpp"
#include "rlbox_wasm2c_sandbox.hpp"

#include "interspec/boundary/wasm_port.h"
#if INTERSPEC_TRACKING
#include "interspec_png_t_policy.h"
#endif

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

extern "C" {
unsigned char* interspec_png_input(uint32_t, uint32_t);
unsigned char* interspec_png_decode(uint32_t, uint32_t, uint32_t, uint32_t, uint32_t);
unsigned char* interspec_png_encode(uint32_t, uint32_t, uint32_t, uint32_t);
uint32_t interspec_png_width(void);
uint32_t interspec_png_height(void);
uint32_t interspec_png_size(uint32_t);
void interspec_png_done(uint32_t);
#ifdef INTERSPEC_FAULT_TESTS
void interspec_png_fault(uint32_t);
void interspec_png_poc(uint32_t);
#endif
}

namespace {

#if INTERSPEC_TRACKING
namespace P = interspec::magick_libpng_generated;
#else
namespace P {
struct NoAccess {};
constexpr NoAccess kUsePngDecodedPixelsRange{}, kUsePngEncodedImageRange{};
}  // namespace P
#endif

struct PngPolicy {
  static constexpr const char* boundary = "magick_libpng";
  static constexpr int reject_exit = 86;
#if INTERSPEC_TRACKING
  static bool register_all(interspec::Runtime& runtime) {
    return P::register_types(runtime) && P::register_wasm_allocation_policy(runtime);
  }
  template <class Access>
  static interspec::CheckResult check(const interspec::Runtime& runtime, uintptr_t base,
                                      size_t bytes, const Access& access) {
    return P::check(runtime, base, bytes, access);
  }
#endif
};
using Port = interspec::WasmPort<PngPolicy>;

constexpr uint32_t kMaxBytes = 16u * 1024u * 1024u;  // per buffer

#if !INTERSPEC_TRACKING
constexpr const char* kVariant = "rlbox-only";
#elif !INTERSPEC_CHECKS
constexpr const char* kVariant = "tracked-no-check";
#else
constexpr const char* kVariant = "interspec";
#endif

class Engine {
 public:
  Engine() : port_(64u * 1024u * 1024u) {}
  Port& port() { return port_; }

  // The out-parameters keep T's previous contents until U's results arrive.
  int decode_rgba(std::vector<unsigned char>& png, uint32_t* w, uint32_t* h,
                  std::vector<unsigned char>* rgba, size_t* rgba_len) {
    if (png.empty() || png.size() > kMaxBytes) return -1;
    const uint32_t len = static_cast<uint32_t>(png.size());
    unsigned char* in_u = stage(0, len);
    std::memcpy(in_u, png.data(), len);

    // T's current values of the four out-parameters are copied in.
    const uint32_t w_in = *w;
    const uint32_t h_in = *h;
    const uint32_t rgba_in = low32(rgba->data());
    const uint32_t size_in = static_cast<uint32_t>(*rgba_len);
    auto pixels =
        port_.sandbox().invoke_sandbox_function(interspec_png_decode, len, w_in, h_in,
                                                rgba_in, size_in);
    // U's version of the PNG bytes is copied back over T's.
    std::memcpy(png.data(), in_u, len);
    if (pixels.UNSAFE_unverified() == nullptr) return -2;

    const uint32_t width =
        port_.sandbox().invoke_sandbox_function(interspec_png_width).UNSAFE_unverified();
    const uint32_t height =
        port_.sandbox().invoke_sandbox_function(interspec_png_height).UNSAFE_unverified();
    const uint32_t size =
        port_.sandbox().invoke_sandbox_function(interspec_png_size, 0u).UNSAFE_unverified();
    // As in the artifact wrapper: the three values must be consistent.
    if (width == 0 || height == 0 || size == 0 || size > kMaxBytes ||
        uint64_t{width} * height * 4 != size)
      return -3;
    // SP3: the returned pointer must be a live registered object of the
    // expected type that holds `size` bytes.
    const unsigned char* raw =
        port_.validate(pixels, size, P::kUsePngDecodedPixelsRange, "decoded_pixels");
    rgba->assign(raw, raw + size);
    port_.sandbox().invoke_sandbox_function(interspec_png_done, 0u);
    *w = width;
    *h = height;
    *rgba_len = size;
    return 0;
  }

  int encode_rgba(std::vector<unsigned char>& rgba, uint32_t w, uint32_t h,
                  std::vector<unsigned char>* png, size_t* png_len) {
    if (w == 0 || h == 0 || uint64_t{w} * h * 4 != rgba.size() || rgba.size() > kMaxBytes)
      return -1;
    const uint32_t len = static_cast<uint32_t>(rgba.size());
    unsigned char* in_u = stage(1, len);
    std::memcpy(in_u, rgba.data(), len);

    // T's current values of the two out-parameters are copied in.
    const uint32_t png_in = low32(png->data());
    const uint32_t size_in = static_cast<uint32_t>(*png_len);
    auto encoded =
        port_.sandbox().invoke_sandbox_function(interspec_png_encode, w, h, png_in, size_in);
    // U's version of the pixels is copied back over T's.
    std::memcpy(rgba.data(), in_u, len);
    if (encoded.UNSAFE_unverified() == nullptr) return -2;

    const uint32_t size =
        port_.sandbox().invoke_sandbox_function(interspec_png_size, 1u).UNSAFE_unverified();
    if (size == 0 || size > kMaxBytes) return -3;
    // SP3, as for the decoded pixels.
    const unsigned char* raw =
        port_.validate(encoded, size, P::kUsePngEncodedImageRange, "encoded_png");
    png->assign(raw, raw + size);
    port_.sandbox().invoke_sandbox_function(interspec_png_done, 1u);
    *png_len = size;
    return 0;
  }

 private:
  static uint32_t low32(const void* pointer) {
    return static_cast<uint32_t>(reinterpret_cast<uintptr_t>(pointer));
  }

  unsigned char* stage(uint32_t which, uint32_t bytes) {
    return port_.input_buffer(
        port_.sandbox().invoke_sandbox_function(interspec_png_input, which, bytes), bytes,
        "input");
  }

  Port port_;
};

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
  if (argc < 3 || argc > 4) {
    std::fprintf(stderr, "usage: %s PNG ITERATIONS [FAULT_MODE]\n", argv[0]);
    return 2;
  }
  try {
    std::ifstream file(argv[1], std::ios::binary);
    if (!file) throw std::runtime_error("open_input");
    std::vector<unsigned char> png((std::istreambuf_iterator<char>(file)),
                                   std::istreambuf_iterator<char>());
    const uint32_t iterations = static_cast<uint32_t>(std::stoul(argv[2]));
    const uint32_t fault = argc == 4 ? static_cast<uint32_t>(std::stoul(argv[3])) : 0;
    if (iterations == 0 || png.empty()) throw std::runtime_error("arguments");
    Engine engine;
#ifdef INTERSPEC_FAULT_TESTS
    if (fault) engine.port().sandbox().invoke_sandbox_function(interspec_png_fault, fault);
    if (const char* poc = std::getenv("INTERSPEC_TEST_POC_FLAGS"))
      engine.port().sandbox().invoke_sandbox_function(
          interspec_png_poc, static_cast<uint32_t>(std::stoul(poc)));
#else
    if (fault) throw std::runtime_error("fault_requires_test_build");
#endif

    uint32_t width = 0, height = 0;
    std::vector<unsigned char> rgba, encoded;
    const auto start = std::chrono::steady_clock::now();
    for (uint32_t i = 0; i < iterations; ++i) {
      // What T happens to hold in its out-parameters before the first call.
      if (i == 0) {
        width = 0x5ec2e701;
        height = 0x5ec2e702;
        rgba.assign(8, 0);
      }
      size_t rgba_len = i == 0 ? 0x5ec2e703 : rgba.size();
      size_t png_len = encoded.size();
      if (engine.decode_rgba(png, &width, &height, &rgba, &rgba_len) != 0)
        throw std::runtime_error("decode");
      if (engine.encode_rgba(rgba, width, height, &encoded, &png_len) != 0)
        throw std::runtime_error("encode");
    }
    const auto finish = std::chrono::steady_clock::now();
#ifdef INTERSPEC_FAULT_TESTS
    // What T's own copy of the PNG bytes looks like after the run.
    std::fprintf(stderr, "INTERSPEC_T_OBSERVE boundary=magick_libpng png_first_byte=0x%02x\n",
                 static_cast<unsigned>(png[0]));
#endif
    std::printf(
        "PNG_BENCH variant=%s iterations=%u input_bytes=%zu width=%u height=%u "
        "rgba_bytes=%zu rgba_fnv=%016llx png_bytes=%zu png_fnv=%016llx checks=%llu "
        "elapsed_ns=%llu\n",
        kVariant, iterations, png.size(), width, height, rgba.size(),
        static_cast<unsigned long long>(fnv(rgba.data(), rgba.size())), encoded.size(),
        static_cast<unsigned long long>(fnv(encoded.data(), encoded.size())),
        static_cast<unsigned long long>(engine.port().checks()),
        static_cast<unsigned long long>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(finish - start).count()));
    return 0;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "png benchmark error: %s\n", error.what());
    return 1;
  }
}
