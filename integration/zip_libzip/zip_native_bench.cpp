// Native reference for the zip/libzip port (tracker item I12): the workload of
// the interspec-artifact microbenchmark (workloads/libzip/zip_microbench.cpp,
// mode native) with the output format of zip_app_bench.cpp. Unlike the
// artifact's native mode, a failing stat ends the run, as in its isolated mode.
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

#include <zip.h>

namespace {

uint64_t hash_bytes(const unsigned char* p, size_t n) {
  uint64_t h = UINT64_C(1469598103934665603);
  for (size_t i = 0; i < n; i++) {
    h ^= p[i];
    h *= UINT64_C(1099511628211);
  }
  return h;
}

std::string hex(const std::string& text) {
  static const char digits[] = "0123456789abcdef";
  std::string out;
  for (unsigned char c : text) {
    out += digits[c >> 4];
    out += digits[c & 15];
  }
  return out.empty() ? "(empty)" : out;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc != 3 && !(argc == 4 && std::string(argv[3]) == "list")) {
    std::fprintf(stderr, "usage: %s ARCHIVE ITERATIONS [list]\n", argv[0]);
    return 2;
  }
  const bool listing = argc == 4;
  // libzip converts the DOS time of every entry with mktime when it opens an
  // archive. Without TZ, glibc looks at /etc/localtime in every mktime call
  // (one system call per entry), which the sandboxed libc never does: it has
  // no time zone data and uses UTC. Fix the zone so that the native program
  // does the same work.
  setenv("TZ", "UTC0", 1);
  tzset();
  try {
    std::ifstream file(argv[1], std::ios::binary);
    if (!file) throw std::runtime_error("open_input");
    std::vector<unsigned char> archive((std::istreambuf_iterator<char>(file)),
                                       std::istreambuf_iterator<char>());
    const uint32_t iterations = static_cast<uint32_t>(std::stoul(argv[2]));
    if (iterations == 0 || archive.empty()) throw std::runtime_error("arguments");

    zip_error_t error;
    zip_error_init(&error);
    zip_t* za = nullptr;
    zip_int64_t entries = 0;
    auto open = [&] {
      zip_source_t* source =
          zip_source_buffer_create(archive.data(), archive.size(), 0, &error);
      if (!source) throw std::runtime_error("zip_source_buffer_create");
      za = zip_open_from_source(source, ZIP_RDONLY, &error);
      if (!za) throw std::runtime_error("zip_open");
      entries = zip_get_num_entries(za, 0);
      if (entries <= 0) throw std::runtime_error("zip_entries");
    };
    if (!listing) open();

    uint64_t checksum = 0, last_size = 0;
    std::string last_name;
    auto query = [&](zip_uint64_t idx) {
      zip_stat_t st;
      zip_stat_init(&st);
      if (zip_stat_index(za, idx, 0, &st) != 0) throw std::runtime_error("zip_stat");
      const char* name_direct = zip_get_name(za, idx, 0);
      const char* name_stat = st.name;
      if (name_direct)
        checksum += hash_bytes(reinterpret_cast<const unsigned char*>(name_direct),
                               std::strlen(name_direct));
      if (name_stat)
        checksum += hash_bytes(reinterpret_cast<const unsigned char*>(name_stat),
                               std::strlen(name_stat));
      checksum += static_cast<uint64_t>(st.size);
      last_size = st.size;
      last_name = name_direct ? name_direct : "";
    };
    const auto start = std::chrono::steady_clock::now();
    if (listing) {
      // Every iteration opens the archive, reads every entry once and closes it.
      for (uint32_t i = 0; i < iterations; ++i) {
        open();
        for (zip_int64_t idx = 0; idx < entries; ++idx) query(static_cast<zip_uint64_t>(idx));
        zip_close(za);
        za = nullptr;
      }
    } else {
      for (uint32_t i = 0; i < iterations; ++i) query(i % static_cast<zip_uint64_t>(entries));
    }
    const auto finish = std::chrono::steady_clock::now();
    std::printf(
        "ZIP_BENCH variant=native iterations=%u archive_bytes=%zu entries=%lld "
        "checksum=%016llx last_name=%s last_size=%llu checks=0 elapsed_ns=%llu\n",
        iterations, archive.size(), static_cast<long long>(entries),
        static_cast<unsigned long long>(checksum), hex(last_name).c_str(),
        static_cast<unsigned long long>(last_size),
        static_cast<unsigned long long>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(finish - start).count()));
    if (za) zip_close(za);
    zip_error_fini(&error);
    return 0;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "zip benchmark error: %s\n", error.what());
    return 1;
  }
}
