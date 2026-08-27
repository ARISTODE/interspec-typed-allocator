#include <interspec/runtime.h>

#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <memory>
#include <thread>
#include <vector>

namespace {

using Clock = std::chrono::steady_clock;
using interspec::CheckResult;
using interspec::Runtime;
using interspec::TypeId;
using interspec::type_hash;

constexpr uintptr_t kBase = 0x40000000;
constexpr TypeId kItemId = 1;
constexpr TypeId kOtherId = 2;
constexpr uint64_t kItem = type_hash("Item");
constexpr uint64_t kOther = type_hash("Other");
constexpr size_t kObjectSize = 32;

std::atomic<uint64_t> sink{0};

size_t iterations_from_env() {
  const char* value = std::getenv("INTERSPEC_BENCH_ITERATIONS");
  if (!value || !*value) return 200000;
  const unsigned long long parsed = std::strtoull(value, nullptr, 10);
  return parsed == 0 ? 200000 : static_cast<size_t>(parsed);
}

void print_result(const char* metric, size_t population, size_t threads,
                  uint64_t operations, uint64_t total_ns) {
  const double ns_per_op = operations == 0
                               ? 0.0
                               : static_cast<double>(total_ns) / operations;
  const double ops_per_sec = total_ns == 0
                                 ? 0.0
                                 : static_cast<double>(operations) * 1e9 /
                                       static_cast<double>(total_ns);
  std::cout << metric << ',' << population << ',' << threads << ','
            << operations << ',' << total_ns << ',' << std::fixed
            << std::setprecision(2) << ns_per_op << ',' << std::setprecision(0)
            << ops_per_sec << '\n';
}

std::unique_ptr<Runtime> make_runtime(size_t population,
                                      std::vector<uintptr_t>& objects) {
  const size_t capacity = (population + 16) * 64;
  auto runtime = std::make_unique<Runtime>(kBase, capacity);
  if (!runtime->register_type(kItemId, kItem) ||
      !runtime->register_type(kOtherId, kOther)) {
    std::abort();
  }
  objects.reserve(population);
  for (size_t i = 0; i < population; ++i) {
    const uintptr_t ptr = runtime->allocate(kObjectSize, kItemId);
    if (!ptr) std::abort();
    objects.push_back(ptr);
  }
  return runtime;
}

template <typename Fn>
uint64_t measure(size_t iterations, Fn fn) {
  const auto start = Clock::now();
  uint64_t local = 0;
  for (size_t i = 0; i < iterations; ++i) local += fn(i);
  const auto stop = Clock::now();
  sink.fetch_add(local, std::memory_order_relaxed);
  return static_cast<uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(stop - start).count());
}

void benchmark_lookup(size_t population, size_t iterations) {
  std::vector<uintptr_t> objects;
  auto runtime = make_runtime(population, objects);
  const uintptr_t target = objects.back();

  const uint64_t check_ns = measure(iterations, [&](size_t) {
    return runtime->check(target, 8, kItem) == CheckResult::ok ? 1u : 0u;
  });
  print_result("check_live", population, 1, iterations, check_ns);

  const uint64_t interior_ns = measure(iterations, [&](size_t) {
    return runtime->check(target + 8, 8, kItem) == CheckResult::ok ? 1u : 0u;
  });
  print_result("check_interior", population, 1, iterations, interior_ns);

  const uint64_t wrong_type_ns = measure(iterations, [&](size_t) {
    return runtime->check(target, 8, kOther) == CheckResult::wrong_type ? 1u : 0u;
  });
  print_result("check_wrong_type", population, 1, iterations, wrong_type_ns);

  size_t remaining = 0;
  const uint64_t remaining_ns = measure(iterations, [&](size_t) {
    return runtime->remaining_bytes(target + 8, kItem, remaining) ==
                   CheckResult::ok
               ? remaining
               : 0u;
  });
  print_result("remaining_bytes", population, 1, iterations, remaining_ns);
}

void benchmark_allocation(size_t population) {
  Runtime runtime(kBase, (population + 16) * 64);
  if (!runtime.register_type(kItemId, kItem)) std::abort();

  const auto start = Clock::now();
  uint64_t local = 0;
  for (size_t i = 0; i < population; ++i)
    local += runtime.allocate(kObjectSize, kItemId) != 0 ? 1u : 0u;
  const auto stop = Clock::now();
  sink.fetch_add(local, std::memory_order_relaxed);
  const uint64_t total_ns = static_cast<uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(stop - start).count());
  print_result("allocate", population, 1, population, total_ns);
}

void benchmark_concurrent_checks(size_t population, size_t iterations,
                                 size_t thread_count) {
  std::vector<uintptr_t> objects;
  auto runtime = make_runtime(population, objects);
  const uintptr_t target = objects.back();

  std::vector<std::thread> threads;
  threads.reserve(thread_count);
  const auto start = Clock::now();
  for (size_t t = 0; t < thread_count; ++t) {
    threads.emplace_back([&, t] {
      uint64_t local = t;
      for (size_t i = 0; i < iterations; ++i)
        local += runtime->check(target, 8, kItem) == CheckResult::ok ? 1u : 0u;
      sink.fetch_add(local, std::memory_order_relaxed);
    });
  }
  for (auto& thread : threads) thread.join();
  const auto stop = Clock::now();

  const uint64_t total_ns = static_cast<uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(stop - start).count());
  print_result("check_concurrent", population, thread_count,
               iterations * thread_count, total_ns);
}

}  // namespace

int main() {
  const size_t iterations = iterations_from_env();
  std::cout << "metric,population,threads,operations,total_ns,ns_per_op,ops_per_sec\n";

  for (const size_t population : {size_t{1}, size_t{16}, size_t{256},
                                  size_t{4096}, size_t{16384}})
    benchmark_lookup(population, iterations);

  benchmark_allocation(16384);

  for (const size_t threads : {size_t{1}, size_t{2}, size_t{4}, size_t{8}})
    benchmark_concurrent_checks(4096, iterations / 4 + 1, threads);

  if (sink.load(std::memory_order_relaxed) == 0) return 2;
  return 0;
}
