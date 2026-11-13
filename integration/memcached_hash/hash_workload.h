// Workload shared by hash_app_bench.cpp and hash_native_bench.cpp (tracker
// item I9), after the artifact's microbenchmark
// (code/workloads/memcached/hash_microbench.cpp) with one client: keys "k0" to
// "k<keyspace-1>", `ops` hashes of keys drawn with the artifact's generator
// and seed, and the XOR of the results.
#pragma once

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <random>
#include <string>
#include <vector>

namespace hash_workload {

struct Result {
  uint64_t sink = 0, elapsed_ns = 0;
  unsigned char first_key_first_byte = 0;  // of T's own key, after the run
};

// hash(key): the key is T's object and may be modified by a wrapper that
// copies U's version back.
template <class Hash> Result run(Hash&& hash, size_t ops, size_t keyspace) {
  std::vector<std::string> keys;
  keys.reserve(keyspace);
  for (size_t i = 0; i < keyspace; i++) keys.push_back("k" + std::to_string(i));
  std::mt19937_64 rng(0xC0FFEEULL);
  std::uniform_int_distribution<size_t> key_dist(0, keyspace - 1);
  Result result;
  std::string* first = nullptr;
  const auto start = std::chrono::steady_clock::now();
  for (size_t i = 0; i < ops; i++) {
    std::string& key = keys[key_dist(rng)];
    if (!first) first = &key;
    result.sink ^= hash(key);
  }
  const auto finish = std::chrono::steady_clock::now();
  result.first_key_first_byte = static_cast<unsigned char>((*first)[0]);
  result.elapsed_ns = static_cast<uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(finish - start).count());
  return result;
}

inline void print(const char* variant, size_t ops, size_t keyspace, const Result& r,
                  unsigned long long checks) {
  std::printf("HASH_BENCH variant=%s ops=%zu keyspace=%zu sink=%016llx checks=%llu "
              "elapsed_ns=%llu\n",
              variant, ops, keyspace, static_cast<unsigned long long>(r.sink), checks,
              static_cast<unsigned long long>(r.elapsed_ns));
}

}  // namespace hash_workload
