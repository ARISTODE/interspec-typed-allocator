// Trusted program for the memcached/hash boundary (tracker item I9): the hash
// microbenchmark of the interspec-artifact with the hash function inside an
// RLBox wasm2c sandbox.
//
// T-level interface (the artifact wrapper's memcached_hash_host_run):
//   hash(data, len) -> 64-bit value
// The artifact isolates only this call; memcached's hash table stays in T.
// The call has one pointer argument and returns a number.
// Policies at this boundary:
//   SP1  no field: U reads everything it is handed (the key).
//   SP2  the key is read by U and never written by it, so U's copy is not
//        copied back.
//   SP3  no field: U returns no pointer to T.
#define RLBOX_USE_EXCEPTIONS
#define RLBOX_USE_STATIC_CALLS() rlbox_wasm2c_sandbox_lookup_symbol
#define RLBOX_WASM2C_MODULE_NAME glue__lib__wasm2c
#include "glue_lib_wasm2c.h"
#include "rlbox.hpp"
#include "rlbox_wasm2c_sandbox.hpp"

#include "hash_workload.h"
#include "interspec/boundary/wasm_port.h"

#include <cstring>

extern "C" {
unsigned char* interspec_hash_stage(uint32_t);
unsigned long long interspec_hash_run(uint32_t, uint32_t);
#ifdef INTERSPEC_FAULT_TESTS
void interspec_hash_poc(uint32_t);
#endif
}

namespace {

struct HashPolicy {
  static constexpr const char* boundary = "memcached_hash";
  static constexpr int reject_exit = 86;
};
using Port = interspec::WasmPort<HashPolicy>;

#if !INTERSPEC_CHECKS
constexpr const char* kVariant = "rlbox-only";
#else
constexpr const char* kVariant = "interspec";
#endif

class Engine {
 public:
  Engine() : port_(0) {}
  Port& port() { return port_; }

  uint64_t hash(char* data, size_t len) {
    if (len == 0 || len > (1u << 20)) return 0;
    unsigned char* staged = port_.input_buffer(
        port_.sandbox().invoke_sandbox_function(interspec_hash_stage,
                                                static_cast<uint32_t>(len)),
        static_cast<uint32_t>(len), "key");
    std::memcpy(staged, data, len);
    const uint64_t value = port_.sandbox()
                               .invoke_sandbox_function(interspec_hash_run,
                                                        port_.address_of(staged),
                                                        static_cast<uint32_t>(len))
                               .UNSAFE_unverified();
    // SP2: U's copy of the key is not copied back.
    port_.copy_back_unless_sp2(data, staged, len);
    return value;
  }

 private:
  Port port_;
};

}  // namespace

int main(int argc, char** argv) {
  if (argc != 3) {
    std::fprintf(stderr, "usage: %s KEYSPACE OPS\n", argv[0]);
    return 2;
  }
  try {
    const size_t keyspace = std::stoul(argv[1]), ops = std::stoul(argv[2]);
    if (!keyspace || !ops) throw std::runtime_error("arguments");
    Engine engine;
#ifdef INTERSPEC_FAULT_TESTS
    if (const char* poc = std::getenv("INTERSPEC_TEST_POC_FLAGS"))
      engine.port().sandbox().invoke_sandbox_function(
          interspec_hash_poc, static_cast<uint32_t>(std::stoul(poc)));
#endif
    const auto result = hash_workload::run(
        [&engine](std::string& key) { return engine.hash(&key[0], key.size()); }, ops,
        keyspace);
#ifdef INTERSPEC_FAULT_TESTS
    // What T's own copy of the first key it hashed looks like after the run.
    std::fprintf(stderr, "INTERSPEC_T_OBSERVE boundary=memcached_hash key_first_byte=0x%02x\n",
                 static_cast<unsigned>(result.first_key_first_byte));
#endif
    hash_workload::print(kVariant, ops, keyspace, result, engine.port().checks());
    return 0;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "hash benchmark error: %s\n", error.what());
    return 1;
  }
}
