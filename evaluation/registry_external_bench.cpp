// Cost of the registry operations behind a wrapper that hands U tokens for
// objects of T (the memcached hash table port): resolving a token that U
// returned, and registering and unregistering an object. Tracker item R1.
//
// Builds against the registry before and after the token index was added
// (INTERSPEC_RUNTIME_RESOLVES_TOKENS). Before it, the wrapper kept its own
// map from token to object and then asked the registry to check the object;
// that is what "resolve" measures for the older header.
//
// With INTERSPEC_RUNTIME_HAS_HANDLES the same two operations are also measured
// for the handle table (register_handle, resolve_handle), which is what the
// hash table port uses since that header.
//
// Output: CSV, one line per metric.
#include <interspec/runtime.h>

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <random>
#include <unordered_map>
#include <vector>

using interspec::CheckResult;
using interspec::MemoryDomain;
using interspec::ObjectStorage;
using interspec::Runtime;

namespace {
struct Item {
  std::uint64_t words[8];  // 64 bytes, like a small cache item header
};
constexpr uint32_t kItemId = 1;
constexpr uint64_t kItemType = interspec::type_hash("Item");

uint64_t now_ns() {
  return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
      std::chrono::steady_clock::now().time_since_epoch()).count());
}
void report(const char* metric, size_t population, uint64_t operations, uint64_t total_ns) {
  std::printf("%s,%zu,%llu,%llu,%.3f\n", metric, population,
              static_cast<unsigned long long>(operations),
              static_cast<unsigned long long>(total_ns),
              static_cast<double>(total_ns) / static_cast<double>(operations));
}
}  // namespace

int main() {
  const char* raw = std::getenv("INTERSPEC_BENCH_ITERATIONS");
  const uint64_t iterations = raw ? std::strtoull(raw, nullptr, 10) : 1000000;
  std::printf("metric,population,operations,total_ns,ns_per_op\n");
  for (const size_t population : {size_t{2}, size_t{20000}}) {
    Runtime runtime(0, 0);
    if (!runtime.register_type(kItemId, kItemType) ||
        !runtime.register_type_layout(kItemId, sizeof(Item), alignof(Item)))
      return 1;
    std::vector<Item> items(population);
    std::vector<uint64_t> tokens(population);
#ifndef INTERSPEC_RUNTIME_RESOLVES_TOKENS
    std::unordered_map<uint32_t, Item*> by_token;
#endif
    auto add = [&](size_t i) {
      tokens[i] = runtime.register_external_array(reinterpret_cast<uintptr_t>(&items[i]), 1,
                                                  kItemId, MemoryDomain::trusted,
                                                  ObjectStorage::heap);
      if (!tokens[i]) std::abort();
#ifndef INTERSPEC_RUNTIME_RESOLVES_TOKENS
      by_token[static_cast<uint32_t>(tokens[i])] = &items[i];
#endif
    };
    auto drop = [&](size_t i) {
      if (!runtime.unregister_external(tokens[i])) std::abort();
#ifndef INTERSPEC_RUNTIME_RESOLVES_TOKENS
      by_token.erase(static_cast<uint32_t>(tokens[i]));
#endif
    };
    for (size_t i = 0; i < population; ++i) add(i);
    // Age the population as a cache does: replace entries in random order, so
    // that live tokens are not in address order.
    std::mt19937_64 random(20261116);
    for (size_t step = 0; step < population * 4; ++step) {
      const size_t i = random() % population;
      drop(i);
      add(i);
    }
    std::vector<uint32_t> order(1u << 16);
    for (auto& index : order) index = static_cast<uint32_t>(random() % population);

    uint64_t sink = 0;
    uint64_t start = now_ns();
    for (uint64_t n = 0; n < iterations; ++n) {
      const size_t i = order[n & (order.size() - 1)];
#ifdef INTERSPEC_RUNTIME_RESOLVES_TOKENS
      uintptr_t base = 0;
      if (runtime.resolve_external(tokens[i], sizeof(Item), kItemType, MemoryDomain::trusted,
                                   base) != CheckResult::ok)
        std::abort();
      sink += base;
#else
      const auto found = by_token.find(static_cast<uint32_t>(tokens[i]));
      Item* item = found == by_token.end() ? nullptr : found->second;
      if (runtime.check_nonheap_element(reinterpret_cast<uintptr_t>(item), sizeof(Item),
                                        kItemType, MemoryDomain::trusted, tokens[i]) !=
          CheckResult::ok)
        std::abort();
      sink += reinterpret_cast<uintptr_t>(item);
#endif
    }
    report("resolve_token", population, iterations, now_ns() - start);

    start = now_ns();
    for (uint64_t n = 0; n < iterations; ++n) {
      const size_t i = order[n & (order.size() - 1)];
      drop(i);
      add(i);
    }
    report("unregister_and_register", population, iterations, now_ns() - start);
    if (sink == 1) std::printf("#\n");

#ifdef INTERSPEC_RUNTIME_HAS_HANDLES
    Runtime handles_runtime(0, 0);
    if (!handles_runtime.register_type(kItemId, kItemType) ||
        !handles_runtime.register_type_layout(kItemId, sizeof(Item), alignof(Item)))
      return 1;
    std::vector<uint32_t> handles(population);
    auto add_handle = [&](size_t i) {
      handles[i] = handles_runtime.register_handle(reinterpret_cast<uintptr_t>(&items[i]), 1,
                                                   kItemId, MemoryDomain::trusted);
      if (!handles[i]) std::abort();
    };
    auto drop_handle = [&](size_t i) {
      if (!handles_runtime.unregister_handle(handles[i])) std::abort();
    };
    for (size_t i = 0; i < population; ++i) add_handle(i);
    for (size_t step = 0; step < population * 4; ++step) {
      const size_t i = random() % population;
      drop_handle(i);
      add_handle(i);
    }
    start = now_ns();
    for (uint64_t n = 0; n < iterations; ++n) {
      const size_t i = order[n & (order.size() - 1)];
      uintptr_t base = 0;
      if (handles_runtime.resolve_handle(handles[i], sizeof(Item), kItemType,
                                         MemoryDomain::trusted, base) != CheckResult::ok)
        std::abort();
      sink += base;
    }
    report("resolve_handle", population, iterations, now_ns() - start);
    start = now_ns();
    for (uint64_t n = 0; n < iterations; ++n) {
      const size_t i = order[n & (order.size() - 1)];
      drop_handle(i);
      add_handle(i);
    }
    report("unregister_and_register_handle", population, iterations, now_ns() - start);
    if (sink == 1) std::printf("#\n");
#endif
  }
  return 0;
}
