// Native reference for the memcached/hash port (tracker item I9): the workload
// of hash_workload.h against the artifact's hash function without a sandbox.
#include <stdexcept>

#include "hash_workload.h"

extern "C" uint64_t hash_untrusted(const char* data, uint32_t len);

int main(int argc, char** argv) {
  if (argc != 3) {
    std::fprintf(stderr, "usage: %s KEYSPACE OPS\n", argv[0]);
    return 2;
  }
  try {
    const size_t keyspace = std::stoul(argv[1]), ops = std::stoul(argv[2]);
    if (!keyspace || !ops) throw std::runtime_error("arguments");
    const auto result = hash_workload::run(
        [](std::string& key) {
          return hash_untrusted(key.data(), static_cast<uint32_t>(key.size()));
        },
        ops, keyspace);
    hash_workload::print("native", ops, keyspace, result, 0);
    return 0;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "hash benchmark error: %s\n", error.what());
    return 1;
  }
}
