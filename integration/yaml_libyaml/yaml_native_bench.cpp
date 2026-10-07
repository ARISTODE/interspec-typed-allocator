#include "yaml.h"

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <stdexcept>
#include <vector>

namespace {

struct Stats {
  uint64_t events = 0;
  uint64_t scalars = 0;
  uint64_t scalar_bytes = 0;
  uint64_t hash = UINT64_C(1469598103934665603);
};

std::vector<unsigned char> read_file(const char* path) {
  std::ifstream input(path, std::ios::binary);
  if (!input)
    throw std::runtime_error("open_input");
  return std::vector<unsigned char>(
      std::istreambuf_iterator<char>(input),
      std::istreambuf_iterator<char>());
}

Stats run(const std::vector<unsigned char>& input, uint32_t iterations) {
  Stats stats;
  for (uint32_t iteration = 0; iteration < iterations; ++iteration) {
    yaml_parser_t parser;
    if (!yaml_parser_initialize(&parser))
      throw std::runtime_error("yaml_parser_initialize");
    yaml_parser_set_input_string(
        &parser, input.data(), input.size());

    bool stream_end = false;
    while (!stream_end) {
      yaml_event_t event;
      if (!yaml_parser_parse(&parser, &event)) {
        yaml_parser_delete(&parser);
        throw std::runtime_error("yaml_parser_parse");
      }

      ++stats.events;
      if (event.type == YAML_SCALAR_EVENT) {
        ++stats.scalars;
        stats.scalar_bytes += event.data.scalar.length;
        for (size_t i = 0; i < event.data.scalar.length; ++i) {
          stats.hash ^= event.data.scalar.value[i];
          stats.hash *= UINT64_C(1099511628211);
        }
      }
      stream_end = event.type == YAML_STREAM_END_EVENT;
      yaml_event_delete(&event);
    }

    yaml_parser_delete(&parser);
  }
  return stats;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc != 3) {
    std::fprintf(stderr, "usage: %s INPUT ITERATIONS\n", argv[0]);
    return 2;
  }

  try {
    const auto input = read_file(argv[1]);
    const uint32_t iterations =
        static_cast<uint32_t>(std::stoul(argv[2]));
    if (iterations == 0)
      throw std::runtime_error("zero_iterations");

    const auto start = std::chrono::steady_clock::now();
    const Stats stats = run(input, iterations);
    const auto finish = std::chrono::steady_clock::now();
    const uint64_t elapsed = static_cast<uint64_t>(
        std::chrono::duration_cast<std::chrono::nanoseconds>(
            finish - start)
            .count());

    std::printf(
        "YAML_BENCH mode=native iterations=%u input_bytes=%zu "
        "events=%llu scalars=%llu scalar_bytes=%llu hash=%016llx "
        "checks=0 elapsed_ns=%llu\n",
        iterations, input.size(),
        static_cast<unsigned long long>(stats.events),
        static_cast<unsigned long long>(stats.scalars),
        static_cast<unsigned long long>(stats.scalar_bytes),
        static_cast<unsigned long long>(stats.hash),
        static_cast<unsigned long long>(elapsed));
    return 0;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "native yaml benchmark error: %s\n", error.what());
    return 1;
  }
}
