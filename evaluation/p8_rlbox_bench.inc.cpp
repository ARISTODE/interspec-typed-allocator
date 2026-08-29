#include "interspec/runtime.h"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <string>
#include <vector>

using P8BenchSandbox = rlbox::rlbox_sandbox<TestType>;

namespace {

using P8Clock = std::chrono::steady_clock;
constexpr interspec::TypeId kP8BenchTypeId = 60000;
constexpr uint64_t kP8BenchTypeHash = interspec::type_hash("P8BenchObject");
constexpr size_t kP8BenchObjectSize = 32;
volatile uint64_t p8_rlbox_sink = 0;

size_t p8_bench_iterations()
{
  const char* value = std::getenv("INTERSPEC_BENCH_ITERATIONS");
  if (!value || !*value) return 200000;
  const unsigned long long parsed = std::strtoull(value, nullptr, 10);
  return parsed == 0 ? 200000 : static_cast<size_t>(parsed);
}

size_t p8_bench_repetitions()
{
  const char* value = std::getenv("INTERSPEC_P8_REPETITIONS");
  if (!value || !*value) return 5;
  const unsigned long long parsed = std::strtoull(value, nullptr, 10);
  return parsed < 3 ? 3 : static_cast<size_t>(parsed);
}

template<typename Fn>
double p8_measure_ns_per_op(size_t iterations, Fn fn)
{
  uint64_t local = 0;
  const auto start = P8Clock::now();
  for (size_t i = 0; i < iterations; ++i) local += fn();
  const auto stop = P8Clock::now();
  p8_rlbox_sink += local;
  const uint64_t ns = static_cast<uint64_t>(
    std::chrono::duration_cast<std::chrono::nanoseconds>(stop - start).count());
  return static_cast<double>(ns) / static_cast<double>(iterations);
}

struct P8BenchRow
{
  std::string metric;
  size_t population;
  size_t operations;
  size_t samples;
  double median;
  double minimum;
  double maximum;
};

P8BenchRow p8_summarize(const char* metric,
                        size_t population,
                        size_t operations,
                        std::vector<double> samples)
{
  std::sort(samples.begin(), samples.end());
  const double median = samples[samples.size() / 2];
  return { metric, population, operations, samples.size(), median,
           samples.front(), samples.back() };
}

}  // namespace

TEST_CASE("P8 RLBox NaCl domain-check baseline", "[p8_rlbox_bench]")
{
  constexpr size_t kMaxPopulation = 16384;
  constexpr uint32_t kArenaSize = static_cast<uint32_t>((kMaxPopulation + 16) * 64);
  const size_t iterations = p8_bench_iterations();
  const size_t repetitions = p8_bench_repetitions();

  P8BenchSandbox sandbox;
  CreateSandbox(sandbox);
  const uint32_t arena_base = sandbox.get_sandbox_impl()->reserve_typed_arena(kArenaSize);
  REQUIRE(arena_base != 0);

  std::vector<P8BenchRow> rows;
  for (const size_t population : {size_t{1}, size_t{16}, size_t{256},
                                  size_t{4096}, size_t{16384}}) {
    interspec::Runtime runtime(arena_base, kArenaSize);
    REQUIRE(runtime.register_type(kP8BenchTypeId, kP8BenchTypeHash));

    uintptr_t target = 0;
    for (size_t i = 0; i < population; ++i) {
      target = runtime.allocate(kP8BenchObjectSize, kP8BenchTypeId);
      REQUIRE(target != 0);
    }

    auto* host_target = sandbox.template get_unsandboxed_pointer<unsigned char*>(
      static_cast<uint32_t>(target));
    REQUIRE(host_target != nullptr);
    REQUIRE(sandbox.is_pointer_in_sandbox_memory(host_target));
    REQUIRE(sandbox.is_pointer_in_sandbox_memory(host_target + 7));
    REQUIRE(runtime.check(target, 8, kP8BenchTypeHash) == interspec::CheckResult::ok);

    /*
     * Volatile sources model a freshly unwrapped U pointer value and prevent
     * the pure domain predicate from being hoisted out of the timing loop.
     * Both sides pay the same volatile load per measured operation.
     */
    volatile uintptr_t raw_source = target;
    volatile uintptr_t host_source = reinterpret_cast<uintptr_t>(host_target);

    std::vector<double> domain_samples;
    std::vector<double> extended_samples;
    domain_samples.reserve(repetitions);
    extended_samples.reserve(repetitions);

    for (size_t repeat = 0; repeat < repetitions; ++repeat) {
      domain_samples.push_back(p8_measure_ns_per_op(iterations, [&] {
        auto* ptr = reinterpret_cast<const unsigned char*>(host_source);
        return (sandbox.is_pointer_in_sandbox_memory(ptr) &&
                sandbox.is_pointer_in_sandbox_memory(ptr + 7)) ? 1u : 0u;
      }));

      extended_samples.push_back(p8_measure_ns_per_op(iterations, [&] {
        const uintptr_t ptr = raw_source;
        return runtime.check(ptr, 8, kP8BenchTypeHash) == interspec::CheckResult::ok
                 ? 1u : 0u;
      }));
    }

    rows.push_back(p8_summarize(
      "rlbox_domain_range", population, iterations, domain_samples));
    rows.push_back(p8_summarize(
      "extended_sp3", population, iterations, extended_samples));
  }

  REQUIRE(p8_rlbox_sink != 0);

  if (const char* output = std::getenv("INTERSPEC_P8_RLBOX_RUNTIME")) {
    std::ofstream stream(output);
    REQUIRE(stream.good());
    stream << "metric,population,operations,samples,median_ns_per_op,min_ns_per_op,max_ns_per_op\n";
    stream << std::fixed << std::setprecision(6);
    for (const auto& row : rows) {
      stream << row.metric << ',' << row.population << ',' << row.operations << ','
             << row.samples << ',' << row.median << ',' << row.minimum << ','
             << row.maximum << '\n';
    }
  }

  sandbox.destroy_sandbox();
}
