// Trusted program for the ucl/libucl boundary (tracker item I11): the
// parse / look up two paths / emit JSON workload of the interspec-artifact
// libucl microbenchmark, with libucl inside an RLBox wasm2c sandbox.
//
// T-level interface (as in the artifact wrapper):
//   parse_query_emit(input, key1, key2, &val1, &val2, &emitted)
// Policies at this boundary:
//   SP1  the three out-parameters are written by U and never read by it, so
//        T's values in them are not copied in.
//   SP2  the document and the two keys are read by U and never written by it,
//        so U's copies are not copied back.
//   SP3  the three pointers U returns are checked against the object registry
//        (live object, expected type, bounds) before T copies from them.
#define RLBOX_USE_EXCEPTIONS
#define RLBOX_USE_STATIC_CALLS() rlbox_wasm2c_sandbox_lookup_symbol
#define RLBOX_WASM2C_MODULE_NAME glue__lib__wasm2c
#include "glue_lib_wasm2c.h"
#include "rlbox.hpp"
#include "rlbox_wasm2c_sandbox.hpp"

#include "interspec/boundary/wasm_port.h"
#if INTERSPEC_TRACKING
#include "interspec_ucl_t_policy.h"
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
unsigned char* interspec_ucl_setup(uint32_t);
char* interspec_ucl_key_buffer(uint32_t);
int interspec_ucl_parse(uint32_t, uint32_t, uint32_t, uint32_t);
unsigned char* interspec_ucl_value(uint32_t);
uint32_t interspec_ucl_value_size(uint32_t);
void interspec_ucl_shutdown(void);
#ifdef INTERSPEC_FAULT_TESTS
void interspec_ucl_fault(uint32_t);
void interspec_ucl_poc(uint32_t);
#endif
}

namespace {

#if INTERSPEC_TRACKING
namespace P = interspec::ucl_libucl_generated;
#else
namespace P {
struct NoAccess {};
constexpr NoAccess kUseUclStringValueRange{}, kUseUclEmittedRange{};
}  // namespace P
#endif

struct UclPolicy {
  static constexpr const char* boundary = "ucl_libucl";
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
using Port = interspec::WasmPort<UclPolicy>;

constexpr uint32_t kKeyCapacity = 256;
constexpr uint32_t kValueLimit = 1u << 20;

#if !INTERSPEC_TRACKING
constexpr const char* kVariant = "rlbox-only";
#elif !INTERSPEC_CHECKS
constexpr const char* kVariant = "tracked-no-check";
#else
constexpr const char* kVariant = "interspec";
#endif

class Engine {
 public:
  explicit Engine(uint32_t input_capacity) : port_(4u * 1024u * 1024u) {
    input_ = port_.input_buffer(
        port_.sandbox().invoke_sandbox_function(interspec_ucl_setup, input_capacity),
        input_capacity, "input");
    capacity_ = input_capacity;
    for (uint32_t i = 0; i < 2; ++i) {
      auto buffer = port_.sandbox().invoke_sandbox_function(interspec_ucl_key_buffer, i);
      keys_[i] = port_.input_buffer(
          rlbox::sandbox_reinterpret_cast<unsigned char*>(buffer), kKeyCapacity, "key");
    }
  }
  ~Engine() {
    try {
      port_.sandbox().invoke_sandbox_function(interspec_ucl_shutdown);
    } catch (...) {
    }
  }
  Port& port() { return port_; }

  // The out-parameters keep T's previous contents until U's results arrive.
  bool parse_query_emit(std::vector<unsigned char>& input, std::string& key1,
                        std::string& key2, const char** val1, const char** val2,
                        const unsigned char** emitted) {
    if (input.empty() || input.size() > capacity_ || key1.size() >= kKeyCapacity ||
        key2.size() >= kKeyCapacity)
      throw std::runtime_error("argument_capacity");
    std::memcpy(input_, input.data(), input.size());
    std::memcpy(keys_[0], key1.c_str(), key1.size() + 1);
    std::memcpy(keys_[1], key2.c_str(), key2.size() + 1);

    // SP1: U is handed zero for the three out-parameters unless SP1 is off.
    const uint32_t in1 = Port::withheld_unless_sp1_off(low32(*val1));
    const uint32_t in2 = Port::withheld_unless_sp1_off(low32(*val2));
    const uint32_t in3 = Port::withheld_unless_sp1_off(low32(*emitted));
    const int ok = port_.sandbox()
                       .invoke_sandbox_function(interspec_ucl_parse,
                                                static_cast<uint32_t>(input.size()), in1,
                                                in2, in3)
                       .UNSAFE_unverified();

    // SP2: U's copies of the document and the keys are not copied back.
    port_.copy_back_unless_sp2(input.data(), input_, input.size());
    port_.copy_back_unless_sp2(&key1[0], keys_[0], key1.size());
    port_.copy_back_unless_sp2(&key2[0], keys_[1], key2.size());
    if (ok != 1) return false;

    *val1 = fetch(0, value_[0]) ? value_[0].c_str() : nullptr;
    *val2 = fetch(1, value_[1]) ? value_[1].c_str() : nullptr;
    if (!fetch(2, value_[2])) Port::reject("emitted", "null_pointer");
    *emitted = reinterpret_cast<const unsigned char*>(value_[2].c_str());
    return true;
  }

 private:
  static uint32_t low32(const void* pointer) {
    return static_cast<uint32_t>(reinterpret_cast<uintptr_t>(pointer));
  }

  // SP3: the pointer U returns for value `which` must be a live registered
  // object of the expected type that holds size + 1 bytes.
  bool fetch(uint32_t which, std::string& out) {
    auto pointer = port_.sandbox().invoke_sandbox_function(interspec_ucl_value, which);
    if (pointer.UNSAFE_unverified() == nullptr) return false;
    const uint32_t size = port_.sandbox()
                              .invoke_sandbox_function(interspec_ucl_value_size, which)
                              .UNSAFE_unverified();
    const char* operation = which == 2 ? "emitted" : "string_value";
    if (size >= kValueLimit) Port::reject(operation, "value_capacity");
    const unsigned char* raw =
        which == 2 ? port_.validate(pointer, size + 1, P::kUseUclEmittedRange, operation)
                   : port_.validate(pointer, size + 1, P::kUseUclStringValueRange, operation);
    out.assign(reinterpret_cast<const char*>(raw), size);
    return true;
  }

  Port port_;
  unsigned char* input_ = nullptr;
  unsigned char* keys_[2] = {nullptr, nullptr};
  uint32_t capacity_ = 0;
  std::string value_[3];
};

std::vector<unsigned char> read_file(const char* path) {
  std::ifstream input(path, std::ios::binary);
  if (!input) throw std::runtime_error("open_input");
  return std::vector<unsigned char>(std::istreambuf_iterator<char>(input),
                                    std::istreambuf_iterator<char>());
}

std::string hex(const char* text) {
  if (!text) return "(null)";
  static const char digits[] = "0123456789abcdef";
  std::string out;
  for (const unsigned char* p = reinterpret_cast<const unsigned char*>(text); *p; ++p) {
    out += digits[*p >> 4];
    out += digits[*p & 15];
  }
  return out.empty() ? "(empty)" : out;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 5 || argc > 6) {
    std::fprintf(stderr, "usage: %s INPUT KEY1 KEY2 ITERATIONS [FAULT_MODE]\n", argv[0]);
    return 2;
  }
  try {
    auto input = read_file(argv[1]);
    std::string key1 = argv[2], key2 = argv[3];
    const uint32_t iterations = static_cast<uint32_t>(std::stoul(argv[4]));
    const uint32_t fault = argc == 6 ? static_cast<uint32_t>(std::stoul(argv[5])) : 0;
    if (iterations == 0) throw std::runtime_error("zero_iterations");
    Engine engine(static_cast<uint32_t>(input.size()));
#ifdef INTERSPEC_FAULT_TESTS
    if (fault) engine.port().sandbox().invoke_sandbox_function(interspec_ucl_fault, fault);
    if (const char* poc = std::getenv("INTERSPEC_TEST_POC_FLAGS"))
      engine.port().sandbox().invoke_sandbox_function(
          interspec_ucl_poc, static_cast<uint32_t>(std::stoul(poc)));
#else
    if (fault) throw std::runtime_error("fault_requires_test_build");
#endif

    std::string last1, last2, last_emitted;
    bool has1 = false, has2 = false;
    const auto start = std::chrono::steady_clock::now();
    for (uint32_t i = 0; i < iterations; ++i) {
      // What T happens to hold in its out-parameters before the call.
      const char* val1 = reinterpret_cast<const char*>(uintptr_t{0x5ec2e701});
      const char* val2 = reinterpret_cast<const char*>(uintptr_t{0x5ec2e702});
      const unsigned char* emitted =
          reinterpret_cast<const unsigned char*>(uintptr_t{0x5ec2e703});
      if (!engine.parse_query_emit(input, key1, key2, &val1, &val2, &emitted))
        throw std::runtime_error("ucl_parse");
      has1 = val1 != nullptr;
      has2 = val2 != nullptr;
      last1 = has1 ? val1 : "";
      last2 = has2 ? val2 : "";
      last_emitted = reinterpret_cast<const char*>(emitted);
    }
    const auto finish = std::chrono::steady_clock::now();
    uint64_t fnv = UINT64_C(1469598103934665603);
    for (unsigned char c : last_emitted) {
      fnv ^= c;
      fnv *= UINT64_C(1099511628211);
    }
#ifdef INTERSPEC_FAULT_TESTS
    // What T's own copies of the arguments look like after the run.
    std::fprintf(stderr,
                 "INTERSPEC_T_OBSERVE boundary=ucl_libucl input_first_byte=0x%02x "
                 "key1_first_byte=0x%02x\n",
                 static_cast<unsigned>(input[0]),
                 static_cast<unsigned>(static_cast<unsigned char>(key1[0])));
#endif
    std::printf(
        "UCL_BENCH variant=%s iterations=%u input_bytes=%zu val1=%s val2=%s "
        "emitted_bytes=%zu emitted_fnv=%016llx checks=%llu elapsed_ns=%llu\n",
        kVariant, iterations, input.size(), hex(has1 ? last1.c_str() : nullptr).c_str(),
        hex(has2 ? last2.c_str() : nullptr).c_str(), last_emitted.size(),
        static_cast<unsigned long long>(fnv),
        static_cast<unsigned long long>(engine.port().checks()),
        static_cast<unsigned long long>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(finish - start).count()));
    return 0;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "ucl benchmark error: %s\n", error.what());
    return 1;
  }
}
