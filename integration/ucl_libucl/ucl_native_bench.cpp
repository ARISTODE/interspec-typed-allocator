// Native reference for the ucl/libucl boundary (tracker item I11): the same
// workload and output line as ucl_app_bench.cpp, with libucl linked directly.
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

#include <ucl.h>

static std::string hex(const char* text) {
  if (!text) return "(null)";
  static const char digits[] = "0123456789abcdef";
  std::string out;
  for (const unsigned char* p = reinterpret_cast<const unsigned char*>(text); *p; ++p) {
    out += digits[*p >> 4];
    out += digits[*p & 15];
  }
  return out.empty() ? "(empty)" : out;
}

int main(int argc, char** argv) {
  if (argc != 5) {
    std::fprintf(stderr, "usage: %s INPUT KEY1 KEY2 ITERATIONS\n", argv[0]);
    return 2;
  }
  try {
    std::ifstream file(argv[1], std::ios::binary);
    if (!file) throw std::runtime_error("open_input");
    const std::vector<unsigned char> input((std::istreambuf_iterator<char>(file)),
                                           std::istreambuf_iterator<char>());
    const uint32_t iterations = static_cast<uint32_t>(std::stoul(argv[4]));
    if (iterations == 0 || input.empty()) throw std::runtime_error("arguments");
    std::string last1, last2, last_emitted;
    bool has1 = false, has2 = false;
    const auto start = std::chrono::steady_clock::now();
    for (uint32_t i = 0; i < iterations; ++i) {
      struct ucl_parser* parser = ucl_parser_new(0);
      if (!parser || !ucl_parser_add_chunk(parser, input.data(), input.size()))
        throw std::runtime_error("ucl_parse");
      ucl_object_t* root = ucl_parser_get_object(parser);
      if (!root) throw std::runtime_error("ucl_parse");
      const ucl_object_t* v1 = ucl_object_lookup_path_char(root, argv[2], '.');
      const ucl_object_t* v2 = ucl_object_lookup_path_char(root, argv[3], '.');
      const char* t1 = v1 ? ucl_object_tostring(v1) : nullptr;
      const char* t2 = v2 ? ucl_object_tostring(v2) : nullptr;
      has1 = t1 != nullptr;
      has2 = t2 != nullptr;
      last1 = has1 ? t1 : "";
      last2 = has2 ? t2 : "";
      unsigned char* rendered = ucl_object_emit(root, UCL_EMIT_JSON_COMPACT);
      if (!rendered) throw std::runtime_error("ucl_emit");
      last_emitted = reinterpret_cast<const char*>(rendered);
      std::free(rendered);
      ucl_object_unref(root);
      ucl_parser_free(parser);
    }
    const auto finish = std::chrono::steady_clock::now();
    uint64_t fnv = UINT64_C(1469598103934665603);
    for (unsigned char c : last_emitted) {
      fnv ^= c;
      fnv *= UINT64_C(1099511628211);
    }
    std::printf(
        "UCL_BENCH variant=native iterations=%u input_bytes=%zu val1=%s val2=%s "
        "emitted_bytes=%zu emitted_fnv=%016llx checks=0 elapsed_ns=%llu\n",
        iterations, input.size(), hex(has1 ? last1.c_str() : nullptr).c_str(),
        hex(has2 ? last2.c_str() : nullptr).c_str(), last_emitted.size(),
        static_cast<unsigned long long>(fnv),
        static_cast<unsigned long long>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(finish - start).count()));
    return 0;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "native ucl benchmark error: %s\n", error.what());
    return 1;
  }
}
