// Trusted program for the zip/libzip boundary (tracker item I12): the
// stat-and-names workload of the interspec-artifact libzip microbenchmark,
// with libzip and zlib inside an RLBox wasm2c sandbox.
//
// T-level interface (the shim call of the artifact wrapper):
//   stat_and_get_names(idx, &size, &name_direct, &name_stat)
// on an archive that T opened from a buffer.
#define RLBOX_USE_EXCEPTIONS
#define RLBOX_USE_STATIC_CALLS() rlbox_wasm2c_sandbox_lookup_symbol
#define RLBOX_WASM2C_MODULE_NAME glue__lib__wasm2c
#include "glue_lib_wasm2c.h"
#include "rlbox.hpp"
#include "rlbox_wasm2c_sandbox.hpp"

#include "interspec/boundary/wasm_port.h"
#if INTERSPEC_TRACKING
#include "interspec_zip_t_policy.h"
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
unsigned char* interspec_zip_setup(uint32_t);
// 64-bit values are (unsigned) long long: RLBox maps types by name, and long
// is 32 bits wide inside the sandbox.
long long interspec_zip_open(uint32_t);
int interspec_zip_stat_and_get_names(unsigned long long, unsigned long long, uint32_t,
                                     uint32_t);
unsigned long long interspec_zip_size(void);
const char* interspec_zip_name(uint32_t);
void interspec_zip_close(void);
#ifdef INTERSPEC_FAULT_TESTS
void interspec_zip_fault(uint32_t);
void interspec_zip_poc(uint32_t);
#endif
}

namespace {

#if INTERSPEC_TRACKING
namespace P = interspec::zip_libzip_generated;
#else
namespace P {
struct NoAccess {};
constexpr NoAccess kUseZipEntryName{};
}  // namespace P
#endif

struct ZipPolicy {
  static constexpr const char* boundary = "zip_libzip";
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
  static interspec::CheckResult remaining(const interspec::Runtime& runtime, uintptr_t base,
                                          const P::AccessPolicy& access, size_t& bytes) {
    return runtime.remaining_bytes(base, access.type_hash, bytes);
  }
#endif
};
using Port = interspec::WasmPort<ZipPolicy>;

constexpr size_t kMaxNameBytes = 16u * 1024u;  // as in the artifact wrapper

#if !INTERSPEC_TRACKING
constexpr const char* kVariant = "rlbox-only";
#elif !INTERSPEC_CHECKS
constexpr const char* kVariant = "tracked-no-check";
#else
constexpr const char* kVariant = "interspec";
#endif

// A name that U returned: bytes in U memory, valid until the archive closes.
struct Name {
  const char* data = nullptr;
  size_t length = 0;
};

class Engine {
 public:
  explicit Engine(uint32_t capacity) : port_(16u * 1024u * 1024u) {
    archive_ = port_.input_buffer(
        port_.sandbox().invoke_sandbox_function(interspec_zip_setup, capacity), capacity,
        "archive");
    capacity_ = capacity;
  }
  ~Engine() {
    try {
      port_.sandbox().invoke_sandbox_function(interspec_zip_close);
    } catch (...) {
    }
  }
  Port& port() { return port_; }

  // Returns the number of entries, or a negative value.
  int64_t open(std::vector<unsigned char>& archive) {
    if (archive.empty() || archive.size() > capacity_)
      throw std::runtime_error("argument_capacity");
    std::memcpy(archive_, archive.data(), archive.size());
    const int64_t entries =
        port_.sandbox()
            .invoke_sandbox_function(interspec_zip_open, static_cast<uint32_t>(archive.size()))
            .UNSAFE_unverified();
    // U's version of the archive bytes is copied back over T's.
    std::memcpy(archive.data(), archive_, archive.size());
    return entries;
  }

  // The out-parameters keep T's previous contents until U's results arrive.
  int stat_and_get_names(uint64_t idx, uint64_t* size, Name* name_direct, Name* name_stat) {
    // T's current values of the three out-parameters are copied in.
    const unsigned long long size_in = *size;
    const uint32_t direct_in = low32(name_direct->data);
    const uint32_t stat_in = low32(name_stat->data);
    const int rc = port_.sandbox()
                       .invoke_sandbox_function(interspec_zip_stat_and_get_names,
                                                static_cast<unsigned long long>(idx), size_in,
                                                direct_in, stat_in)
                       .UNSAFE_unverified();
    if (rc != 0) return rc;
    *size = port_.sandbox().invoke_sandbox_function(interspec_zip_size).UNSAFE_unverified();
    *name_direct = fetch(0, "name_direct");
    *name_stat = fetch(1, "name_stat");
    return 0;
  }

 private:
  static uint32_t low32(const void* pointer) {
    return static_cast<uint32_t>(reinterpret_cast<uintptr_t>(pointer));
  }

  // The pointer U returns for a name must lie in a live registered object of
  // the expected type, and the terminator must lie inside that object.
  Name fetch(uint32_t which, const char* operation) {
    auto pointer = port_.sandbox().invoke_sandbox_function(interspec_zip_name, which);
    Name name;
    if (pointer.UNSAFE_unverified() == nullptr) return name;
    name.data = port_.c_string(rlbox::sandbox_reinterpret_cast<unsigned char*>(
                                   rlbox::sandbox_const_cast<char*>(pointer)),
                               kMaxNameBytes, P::kUseZipEntryName, operation, name.length);
    return name;
  }

  Port port_;
  unsigned char* archive_ = nullptr;
  uint32_t capacity_ = 0;
};

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
  if (argc < 3 || argc > 4) {
    std::fprintf(stderr, "usage: %s ARCHIVE ITERATIONS [FAULT_MODE]\n", argv[0]);
    return 2;
  }
  try {
    std::ifstream file(argv[1], std::ios::binary);
    if (!file) throw std::runtime_error("open_input");
    std::vector<unsigned char> archive((std::istreambuf_iterator<char>(file)),
                                       std::istreambuf_iterator<char>());
    const uint32_t iterations = static_cast<uint32_t>(std::stoul(argv[2]));
    const uint32_t fault = argc == 4 ? static_cast<uint32_t>(std::stoul(argv[3])) : 0;
    if (iterations == 0 || archive.empty()) throw std::runtime_error("arguments");
    Engine engine(static_cast<uint32_t>(archive.size()));
#ifdef INTERSPEC_FAULT_TESTS
    if (fault) engine.port().sandbox().invoke_sandbox_function(interspec_zip_fault, fault);
    if (const char* poc = std::getenv("INTERSPEC_TEST_POC_FLAGS"))
      engine.port().sandbox().invoke_sandbox_function(
          interspec_zip_poc, static_cast<uint32_t>(std::stoul(poc)));
#else
    if (fault) throw std::runtime_error("fault_requires_test_build");
#endif
    const int64_t entries = engine.open(archive);
    if (entries <= 0) throw std::runtime_error("zip_open");

    uint64_t checksum = 0, last_size = 0;
    std::string last_name;
    const auto start = std::chrono::steady_clock::now();
    for (uint32_t i = 0; i < iterations; ++i) {
      // What T happens to hold in its out-parameters before the call.
      uint64_t size = UINT64_C(0x5ec2e70100000001);
      Name name_direct, name_stat;
      name_direct.data = reinterpret_cast<const char*>(uintptr_t{0x5ec2e702});
      name_stat.data = reinterpret_cast<const char*>(uintptr_t{0x5ec2e703});
      const uint64_t idx = i % static_cast<uint64_t>(entries);
      if (engine.stat_and_get_names(idx, &size, &name_direct, &name_stat) != 0)
        throw std::runtime_error("zip_stat");
      if (name_direct.data)
        checksum += hash_bytes(reinterpret_cast<const unsigned char*>(name_direct.data),
                               name_direct.length);
      if (name_stat.data)
        checksum += hash_bytes(reinterpret_cast<const unsigned char*>(name_stat.data),
                               name_stat.length);
      checksum += size;
      last_size = size;
      last_name = name_direct.data ? std::string(name_direct.data, name_direct.length) : "";
    }
    const auto finish = std::chrono::steady_clock::now();
#ifdef INTERSPEC_FAULT_TESTS
    // What T's own copy of the archive looks like after the run.
    std::fprintf(stderr, "INTERSPEC_T_OBSERVE boundary=zip_libzip archive_first_byte=0x%02x\n",
                 static_cast<unsigned>(archive[0]));
#endif
    std::printf(
        "ZIP_BENCH variant=%s iterations=%u archive_bytes=%zu entries=%lld "
        "checksum=%016llx last_name=%s last_size=%llu checks=%llu elapsed_ns=%llu\n",
        kVariant, iterations, archive.size(), static_cast<long long>(entries),
        static_cast<unsigned long long>(checksum), hex(last_name).c_str(),
        static_cast<unsigned long long>(last_size),
        static_cast<unsigned long long>(engine.port().checks()),
        static_cast<unsigned long long>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(finish - start).count()));
    return 0;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "zip benchmark error: %s\n", error.what());
    return 1;
  }
}
