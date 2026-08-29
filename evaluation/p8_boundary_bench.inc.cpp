#include <chrono>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <limits>
#include <vector>

namespace {

using P8Clock = std::chrono::steady_clock;
volatile uint64_t p8_bench_sink = 0;

size_t p8_iterations()
{
  const char* value = std::getenv("INTERSPEC_P8_BOUNDARY_ITERATIONS");
  if (!value || !*value) return 20000;
  const unsigned long parsed = std::strtoul(value, nullptr, 10);
  return parsed == 0 ? 20000 : static_cast<size_t>(parsed);
}

template<typename Fn>
void p8_measure(const char* boundary,
                const char* mode,
                size_t repetition,
                size_t iterations,
                Fn&& operation)
{
  const auto begin = P8Clock::now();
  for (size_t i = 0; i < iterations; ++i) operation();
  const auto end = P8Clock::now();
  const uint64_t total_ns = static_cast<uint64_t>(
    std::chrono::duration_cast<std::chrono::nanoseconds>(end - begin).count());
  const double ns_per_op = static_cast<double>(total_ns) /
                           static_cast<double>(iterations);
  std::cout << "P8BENCH," << boundary << ',' << mode << ',' << repetition << ','
            << iterations << ',' << total_ns << ',' << std::fixed
            << std::setprecision(3) << ns_per_op << '\n';
}

template<typename BaselineFn, typename ExtendedFn>
void p8_paired_measure(const char* boundary,
                       size_t repetitions,
                       size_t iterations,
                       BaselineFn&& baseline,
                       ExtendedFn&& extended)
{
  for (size_t rep = 0; rep < repetitions; ++rep) {
    // Alternate order so frequency scaling / warmup does not systematically
    // favor either side of the pair.
    if ((rep & 1u) == 0) {
      p8_measure(boundary, "tracked_no_check", rep, iterations, baseline);
      p8_measure(boundary, "extended_sp3", rep, iterations, extended);
    } else {
      p8_measure(boundary, "extended_sp3", rep, iterations, extended);
      p8_measure(boundary, "tracked_no_check", rep, iterations, baseline);
    }
  }
}

}  // namespace

TEST_CASE("P8 paired real-boundary validation benchmark", "[p8_boundary_bench]")
{
  constexpr size_t kRepetitions = 7;
  const size_t iterations = p8_iterations();

  SECTION("rsync popt returned string") {
    using namespace interspec::rsync_popt_generated;
    PoptSandbox sandbox;
    CreateSandbox(sandbox);
    const uint32_t arena_base =
      sandbox.get_sandbox_impl()->reserve_typed_arena(64 * 1024);
    REQUIRE(arena_base != 0);
    interspec::PolicyRuntime policy_runtime(arena_base, 64 * 1024);
    popt_policy_runtime = &policy_runtime;
    REQUIRE(policy_runtime.initialize_from_sandbox(
      *sandbox.get_sandbox_impl(),
      [](interspec::Runtime& runtime) { return register_types(runtime); },
      [](interspec::Runtime& runtime, auto resolve) {
        return register_allocation_policy(runtime, resolve);
      }));
    auto alloc_cb = sandbox.register_callback(popt_allocate);
    auto release_cb = sandbox.register_callback(popt_release);
    auto size_cb = sandbox.register_callback(popt_size);
    auto realloc_cb = sandbox.register_callback(popt_reallocate);
    const uint32_t alloc_slot = sandbox.get_sandbox_impl()->callback_slot_for_key(
      reinterpret_cast<const void*>(popt_allocate));
    REQUIRE(alloc_slot != std::numeric_limits<uint32_t>::max());
    sandbox.invoke_sandbox_function(interspec_popt_init_lifetime,
                                    alloc_slot, release_cb, size_cb, realloc_cb);
    auto ctx = sandbox.invoke_sandbox_function(interspec_popt_parse_smoke);
    REQUIRE(ctx.UNSAFE_unverified() != nullptr);
    auto arg = sandbox.invoke_sandbox_function(interspec_popt_get_opt_arg, ctx);
    REQUIRE(arg.UNSAFE_unverified() != nullptr);
    char* raw = arg.UNSAFE_unverified();
    const uintptr_t ptr = sandbox.get_sandbox_impl()->sandbox_address(raw);
    size_t bytes = 0;
    REQUIRE(policy_runtime.runtime().remaining_bytes(ptr, kTypeHashChar, bytes) ==
            interspec::CheckResult::ok);
    REQUIRE(bytes > 0);
    std::vector<char> trusted(bytes);

    auto baseline = [&] {
      std::memcpy(trusted.data(), raw, bytes);
      p8_bench_sink += static_cast<unsigned char>(trusted[0]);
    };
    auto extended = [&] {
      if (check(policy_runtime.runtime(), ptr, kUsePoptOptArgFirstByte) !=
          interspec::CheckResult::ok) std::abort();
      size_t checked_bytes = 0;
      if (policy_runtime.runtime().remaining_bytes(ptr, kTypeHashChar, checked_bytes) !=
          interspec::CheckResult::ok || checked_bytes != bytes) std::abort();
      std::memcpy(trusted.data(), raw, checked_bytes);
      p8_bench_sink += static_cast<unsigned char>(trusted[0]);
    };
    p8_paired_measure("rsync_popt", kRepetitions, iterations, baseline, extended);
    sandbox.destroy_sandbox();
  }

  SECTION("memcached bipbuffer interior range") {
    using namespace interspec::memcached_bipbuffer_generated;
    BipbufSandbox sandbox;
    CreateSandbox(sandbox);
    const uint32_t arena_base =
      sandbox.get_sandbox_impl()->reserve_typed_arena(64 * 1024);
    REQUIRE(arena_base != 0);
    interspec::PolicyRuntime policy_runtime(arena_base, 64 * 1024);
    bipbuf_policy_runtime = &policy_runtime;
    REQUIRE(policy_runtime.initialize_from_sandbox(
      *sandbox.get_sandbox_impl(),
      [](interspec::Runtime& runtime) { return register_types(runtime); },
      [](interspec::Runtime& runtime, auto resolve) {
        return register_allocation_policy(runtime, resolve);
      }));
    auto alloc_cb = sandbox.register_callback(bipbuf_allocate);
    const uint32_t alloc_slot = sandbox.get_sandbox_impl()->callback_slot_for_key(
      reinterpret_cast<const void*>(bipbuf_allocate));
    REQUIRE(alloc_slot != std::numeric_limits<uint32_t>::max());
    sandbox.invoke_sandbox_function(interspec_bipbuf_init, alloc_slot);
    auto owner = sandbox.invoke_sandbox_function(interspec_bipbuf_make_and_fill);
    REQUIRE(owner.UNSAFE_unverified() != nullptr);
    auto value = sandbox.invoke_sandbox_function(interspec_bipbuf_peek_valid, owner);
    REQUIRE(value.UNSAFE_unverified() != nullptr);
    const uint32_t bytes = sandbox.invoke_sandbox_function(
      interspec_bipbuf_last_size).UNSAFE_unverified();
    unsigned char* raw = value.UNSAFE_unverified();
    const uintptr_t ptr = sandbox.get_sandbox_impl()->sandbox_address(raw);
    std::vector<unsigned char> trusted(bytes);
    auto baseline = [&] {
      std::memcpy(trusted.data(), raw, bytes);
      p8_bench_sink += trusted[0];
    };
    auto extended = [&] {
      if (check_dynamic(policy_runtime.runtime(), ptr, bytes,
                        kUseBipbufPeekAllRange) != interspec::CheckResult::ok)
        std::abort();
      std::memcpy(trusted.data(), raw, bytes);
      p8_bench_sink += trusted[0];
    };
    p8_paired_measure("memcached_bipbuffer", kRepetitions, iterations,
                      baseline, extended);
    sandbox.destroy_sandbox();
  }

  SECTION("PCRE interior name table") {
    using namespace interspec::nginx_libpcre_generated;
    PcreSandbox sandbox;
    CreateSandbox(sandbox);
    const uint32_t arena_base =
      sandbox.get_sandbox_impl()->reserve_typed_arena(128 * 1024);
    REQUIRE(arena_base != 0);
    interspec::PolicyRuntime policy_runtime(arena_base, 128 * 1024);
    pcre_policy_runtime = &policy_runtime;
    REQUIRE(policy_runtime.initialize_from_sandbox(
      *sandbox.get_sandbox_impl(),
      [](interspec::Runtime& runtime) { return register_types(runtime); },
      [](interspec::Runtime& runtime, auto resolve) {
        return register_allocation_policy(runtime, resolve);
      }));
    auto alloc_cb = sandbox.register_callback(pcre_allocate);
    const uint32_t alloc_slot = sandbox.get_sandbox_impl()->callback_slot_for_key(
      reinterpret_cast<const void*>(pcre_allocate));
    REQUIRE(alloc_slot != std::numeric_limits<uint32_t>::max());
    sandbox.invoke_sandbox_function(interspec_pcre_init, alloc_slot);
    auto compiled = sandbox.invoke_sandbox_function(interspec_pcre_compile_named);
    REQUIRE(compiled.UNSAFE_unverified() != nullptr);
    auto value = sandbox.invoke_sandbox_function(interspec_pcre_name_table, compiled);
    REQUIRE(value.UNSAFE_unverified() != nullptr);
    const uint32_t bytes = sandbox.invoke_sandbox_function(
      interspec_pcre_name_table_size).UNSAFE_unverified();
    unsigned char* raw = value.UNSAFE_unverified();
    const uintptr_t ptr = sandbox.get_sandbox_impl()->sandbox_address(raw);
    std::vector<unsigned char> trusted(bytes);
    auto baseline = [&] {
      std::memcpy(trusted.data(), raw, bytes);
      p8_bench_sink += trusted[0];
    };
    auto extended = [&] {
      if (check_dynamic(policy_runtime.runtime(), ptr, bytes,
                        kUsePcreNameTableRange) != interspec::CheckResult::ok)
        std::abort();
      std::memcpy(trusted.data(), raw, bytes);
      p8_bench_sink += trusted[0];
    };
    p8_paired_measure("nginx_libpcre", kRepetitions, iterations,
                      baseline, extended);
    sandbox.destroy_sandbox();
  }

  SECTION("libyaml structured scalar") {
    using namespace interspec::yaml_libyaml_generated;
    YamlSandbox sandbox;
    CreateSandbox(sandbox);
    const uint32_t arena_base =
      sandbox.get_sandbox_impl()->reserve_typed_arena(64 * 1024);
    REQUIRE(arena_base != 0);
    interspec::PolicyRuntime policy_runtime(arena_base, 64 * 1024);
    yaml_policy_runtime = &policy_runtime;
    REQUIRE(policy_runtime.initialize_from_sandbox(
      *sandbox.get_sandbox_impl(),
      [](interspec::Runtime& runtime) { return register_types(runtime); },
      [](interspec::Runtime& runtime, auto resolve) {
        return register_allocation_policy(runtime, resolve);
      }));
    auto alloc_cb = sandbox.register_callback(yaml_allocate);
    const uint32_t alloc_slot = sandbox.get_sandbox_impl()->callback_slot_for_key(
      reinterpret_cast<const void*>(yaml_allocate));
    REQUIRE(alloc_slot != std::numeric_limits<uint32_t>::max());
    sandbox.invoke_sandbox_function(interspec_yaml_init, alloc_slot);
    auto event = sandbox.invoke_sandbox_function(interspec_yaml_make_scalar);
    REQUIRE(event.UNSAFE_unverified() != nullptr);
    auto value = sandbox.invoke_sandbox_function(interspec_yaml_scalar_value, event);
    REQUIRE(value.UNSAFE_unverified() != nullptr);
    const uint32_t bytes = sandbox.invoke_sandbox_function(
      interspec_yaml_scalar_size).UNSAFE_unverified();
    unsigned char* raw = value.UNSAFE_unverified();
    const uintptr_t ptr = sandbox.get_sandbox_impl()->sandbox_address(raw);
    std::vector<unsigned char> trusted(bytes);
    auto baseline = [&] {
      std::memcpy(trusted.data(), raw, bytes);
      p8_bench_sink += trusted[0];
    };
    auto extended = [&] {
      if (check_dynamic(policy_runtime.runtime(), ptr, bytes,
                        kUseYamlScalarValueRange) != interspec::CheckResult::ok)
        std::abort();
      std::memcpy(trusted.data(), raw, bytes);
      p8_bench_sink += trusted[0];
    };
    p8_paired_measure("yaml_libyaml", kRepetitions, iterations,
                      baseline, extended);
    sandbox.destroy_sandbox();
  }
}
