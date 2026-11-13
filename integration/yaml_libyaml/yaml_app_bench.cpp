#define RLBOX_USE_EXCEPTIONS
#define RLBOX_ENABLE_DEBUG_ASSERTIONS
#define RLBOX_SINGLE_THREADED_INVOCATIONS
#define RLBOX_USE_STATIC_CALLS() rlbox_wasm2c_sandbox_lookup_symbol
#define RLBOX_WASM2C_MODULE_NAME glue__lib__wasm2c

#include "glue_lib_wasm2c.h"
#include "rlbox.hpp"
#include "rlbox_wasm2c_sandbox.hpp"

#include "interspec/policy_runtime.h"
#include "interspec/pointer_census.h"
#include "interspec_yaml_t_policy.h"
#include "yaml.h"
#include "yaml_scalar_staging.h"

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

using SandboxType = rlbox::rlbox_wasm2c_sandbox;
using Sandbox = rlbox::rlbox_sandbox<SandboxType>;
namespace P = interspec::yaml_libyaml_generated;

extern "C" {
unsigned char* interspec_yaml_setup(uint32_t);
unsigned char* interspec_yaml_setup_with_staging(uint32_t, uint32_t);
void interspec_yaml_set_fault(uint32_t);
int interspec_yaml_begin(void);
int interspec_yaml_next(void);
uint32_t interspec_yaml_event_type(void);
unsigned char* interspec_yaml_scalar_pointer(void);
uint32_t interspec_yaml_scalar_size(void);
void interspec_yaml_end(void);
void interspec_yaml_shutdown(void);
}

enum class Mode {
  rlbox_only,
  tracked_no_check,
  extended_sp3,
  typed_staging_identity,
};

struct Stats {
  uint64_t events = 0;
  uint64_t scalars = 0;
  uint64_t scalar_bytes = 0;
  uint64_t hash = UINT64_C(1469598103934665603);
  uint64_t checks = 0;
};

class Engine;

static uint32_t alloc_cb(void*, uint32_t, uint32_t);
static uint32_t release_cb(void*, uint32_t);
static uint32_t size_cb(void*, uint32_t);
static uint32_t realloc_cb(void*, uint32_t, uint32_t);

class Engine {
 public:
  explicit Engine(Mode mode) : mode_(mode) {
    if (!sandbox_.create_sandbox())
      throw std::runtime_error("sandbox_creation");

    if (tracking()) {
      constexpr uint32_t kArenaSize = 64u * 1024u;
      const uint32_t base =
          sandbox_.get_sandbox_impl()->reserve_typed_arena(kArenaSize);
      if (!base)
        throw std::runtime_error("typed_arena");
      policy_ = std::make_unique<interspec::PolicyRuntime>(base, kArenaSize);
      if (!P::register_types(runtime()) ||
          !P::register_wasm_allocation_policy(runtime()))
        throw std::runtime_error("policy_registration");
      sandbox_.get_sandbox_impl()->set_interspec_runtime(
          this, alloc_cb, release_cb, size_cb, realloc_cb);
    }
  }

  ~Engine() noexcept {
    if (typed_staging()) {
      // One-shot fallback for setup/run/finish exceptions. A throwing guest
      // shutdown is never retried, and its sandbox is destroyed before release.
      if (guest_setup_attempted_ && !guest_shutdown_attempted_) {
        try {
          shutdown_typed_guest();
        } catch (...) {
        }
      }
      if (guest_shutdown_failed_)
        destroy_sandbox_noexcept();
      release_staging_noexcept();
      destroy_sandbox_noexcept();
      return;
    }
    if (sandbox_ready_) {
      try {
        sandbox_.invoke_sandbox_function(interspec_yaml_shutdown);
      } catch (...) {
      }
    }
    destroy_sandbox_noexcept();
  }

  bool tracking() const { return mode_ != Mode::rlbox_only; }
  bool typed_staging() const { return mode_ == Mode::typed_staging_identity; }
  bool checks_enabled() const {
    return mode_ == Mode::extended_sp3 || typed_staging();
  }

  interspec::Runtime& runtime() {
    if (!policy_)
      throw std::runtime_error("runtime_disabled");
    return policy_->runtime();
  }

  uint32_t allocate(uint32_t site, uint32_t bytes) {
    return static_cast<uint32_t>(
        runtime().allocate_from_site(bytes, site));
  }

  void setup(const std::vector<unsigned char>& input) {
    if (typed_staging()) {
      if (typed_setup_started_)
        throw std::runtime_error("typed_setup_already_attempted");
      typed_setup_started_ = true;
    }
    if (input.size() > std::numeric_limits<uint32_t>::max())
      throw std::runtime_error("input_too_large");

    if (typed_staging()) {
      if (!runtime().register_type_layout(
              P::kTypeIdYamlScalarValue, sizeof(interspec_yaml_scalar_staging),
              alignof(interspec_yaml_scalar_staging)))
        throw std::runtime_error("staging_layout_registration");
      expected_staging_ = runtime().allocate_typed_array(
          1, P::kTypeIdYamlScalarValue);
      if (!expected_staging_ ||
          expected_staging_ > std::numeric_limits<uint32_t>::max())
        throw std::runtime_error("staging_allocation");
      const uintptr_t base = runtime().base();
      const size_t capacity = runtime().capacity();
      const uint64_t total = sandbox_.get_total_memory();
      if (expected_staging_ < base || expected_staging_ - base > capacity ||
          sizeof(interspec_yaml_scalar_staging) >
              capacity - (expected_staging_ - base) ||
          expected_staging_ > total ||
          sizeof(interspec_yaml_scalar_staging) > total - expected_staging_)
        throw std::runtime_error("staging_extent");

      guest_setup_attempted_ = true;
      input_raw_ = sandbox_.invoke_sandbox_function(
          interspec_yaml_setup_with_staging, static_cast<uint32_t>(input.size()),
          static_cast<uint32_t>(expected_staging_)).UNSAFE_unverified();
    } else {
      input_raw_ = sandbox_.invoke_sandbox_function(
          interspec_yaml_setup, static_cast<uint32_t>(input.size()))
          .UNSAFE_unverified();
    }
    if (!input_raw_ || !sandbox_.is_pointer_in_sandbox_memory(input_raw_))
      throw std::runtime_error("input_allocation");
    const uint32_t address =
        sandbox_.get_sandbox_impl()->sandbox_address(input_raw_);
    const uint64_t total = sandbox_.get_total_memory();
    if (address > total || input.size() > total - address)
      throw std::runtime_error("input_extent");
    input_size_ = static_cast<uint32_t>(input.size());
    sandbox_ready_ = true;
  }

  void finish() {
    if (!typed_staging())
      return;
    shutdown_typed_guest();
    if (!expected_staging_)
      throw std::runtime_error("missing_staging_allocation");
    const uintptr_t allocation = expected_staging_;
    expected_staging_ = 0;  // Exactly one release attempt, including failure.
    if (!runtime().release(allocation))
      throw std::runtime_error("staging_release");
  }

  void set_fault(uint32_t mode) {
    sandbox_.invoke_sandbox_function(interspec_yaml_set_fault, mode);
  }

  Stats run(const std::vector<unsigned char>& input, uint32_t iterations) {
    if (!sandbox_ready_ || input.size() != input_size_)
      throw std::runtime_error("input_setup_mismatch");

    Stats stats;
    std::vector<unsigned char> snapshot(INTERSPEC_YAML_STAGING_CAPACITY);

    for (uint32_t iteration = 0; iteration < iterations; ++iteration) {
      interspec::census::trusted_input("yaml_libyaml", "document_copy_source", input.data());
      std::memcpy(input_raw_, input.data(), input.size());
      const int begin =
          sandbox_.invoke_sandbox_function(interspec_yaml_begin)
              .UNSAFE_unverified();
      if (begin != 1)
        throw std::runtime_error("yaml_begin");

      bool stream_end = false;
      while (!stream_end) {
        const int next =
            sandbox_.invoke_sandbox_function(interspec_yaml_next)
                .UNSAFE_unverified();
        if (next != 1)
          throw std::runtime_error(next == -2 ?
                                   "scalar_staging_capacity" :
                                   "yaml_parse");

        const uint32_t type =
            sandbox_.invoke_sandbox_function(interspec_yaml_event_type)
                .UNSAFE_unverified();
        ++stats.events;

        if (type == YAML_SCALAR_EVENT) {
          auto scalar =
              sandbox_.invoke_sandbox_function(
                  interspec_yaml_scalar_pointer);
          const uint32_t bytes =
              sandbox_.invoke_sandbox_function(
                  interspec_yaml_scalar_size)
                  .UNSAFE_unverified();
          unsigned char* ptr = scalar.UNSAFE_unverified();
          if (!ptr)
            throw std::runtime_error("null_scalar");

          if (!sandbox_.is_pointer_in_sandbox_memory(ptr))
            reject("outside_sandbox");
          const uint32_t address =
              sandbox_.get_sandbox_impl()->sandbox_address(ptr);
          const uint64_t total = sandbox_.get_total_memory();
          if (address > total || bytes > total - address)
            reject("outside_sandbox");

          if (checks_enabled()) {
            ++stats.checks;
            interspec::CheckResult result;
            if (typed_staging()) {
              if (!expected_staging_)
                reject("missing_staging_allocation");
              if (bytes >= INTERSPEC_YAML_STAGING_CAPACITY)
                reject("scalar_staging_capacity");
              result = runtime().check_typed_element(
                  address, bytes, P::kTypeHashYamlScalarValue, expected_staging_);
            } else {
              result = P::check(
                  runtime(), address, bytes, P::kUseYamlScalarValueRange);
            }
            if (result != interspec::CheckResult::ok)
              reject(interspec::check_result_name(result));
            interspec::census::sandbox_result("yaml_libyaml", "checked_scalar_result", address, true);
          }

          if (bytes > snapshot.size())
            snapshot.resize(bytes);
          std::memcpy(snapshot.data(), ptr, bytes);

          ++stats.scalars;
          stats.scalar_bytes += bytes;
          for (uint32_t i = 0; i < bytes; ++i) {
            stats.hash ^= snapshot[i];
            stats.hash *= UINT64_C(1099511628211);
          }
        }

        stream_end = type == YAML_STREAM_END_EVENT;
      }

      sandbox_.invoke_sandbox_function(interspec_yaml_end);
    }
    return stats;
  }

 private:
  void shutdown_typed_guest() {
    if (!guest_setup_attempted_ || guest_shutdown_attempted_)
      throw std::runtime_error("staging_shutdown_state");
    guest_shutdown_attempted_ = true;
    try {
      sandbox_.invoke_sandbox_function(interspec_yaml_shutdown);
      sandbox_ready_ = false;
    } catch (...) {
      guest_shutdown_failed_ = true;
      throw;
    }
  }

  void release_staging_noexcept() noexcept {
    const uintptr_t allocation = expected_staging_;
    expected_staging_ = 0;
    if (allocation && policy_) {
      try {
        (void)runtime().release(allocation);
      } catch (...) {
      }
    }
  }

  void destroy_sandbox_noexcept() noexcept {
    if (sandbox_destroyed_)
      return;
    sandbox_destroyed_ = true;
    try {
      sandbox_.destroy_sandbox();
    } catch (...) {
    }
  }

  [[noreturn]] void reject(const char* reason) {
    std::fprintf(stderr,
                 "INTERSPEC_REJECT boundary=yaml_libyaml reason=%s\n",
                 reason);
    std::fflush(stderr);
    std::exit(86);
  }

  Sandbox sandbox_;
  std::unique_ptr<interspec::PolicyRuntime> policy_;
  Mode mode_;
  unsigned char* input_raw_ = nullptr;
  uint32_t input_size_ = 0;
  bool sandbox_ready_ = false;
  uintptr_t expected_staging_ = 0;
  bool typed_setup_started_ = false;
  bool guest_setup_attempted_ = false;
  bool guest_shutdown_attempted_ = false;
  bool guest_shutdown_failed_ = false;
  bool sandbox_destroyed_ = false;
};

static uint32_t alloc_cb(void* context, uint32_t site, uint32_t bytes) {
  auto* engine = static_cast<Engine*>(context);
  return engine ? engine->allocate(site, bytes) : 0;
}

static uint32_t release_cb(void* context, uint32_t ptr) {
  auto* engine = static_cast<Engine*>(context);
  return engine && engine->runtime().release(ptr) ? 1u : 0u;
}

static uint32_t size_cb(void* context, uint32_t ptr) {
  auto* engine = static_cast<Engine*>(context);
  if (!engine)
    return 0;
  size_t bytes = 0;
  if (!engine->runtime().allocation_size(ptr, bytes) ||
      bytes > std::numeric_limits<uint32_t>::max())
    return 0;
  return static_cast<uint32_t>(bytes);
}

static uint32_t realloc_cb(
    void* context, uint32_t ptr, uint32_t bytes) {
  auto* engine = static_cast<Engine*>(context);
  return engine
             ? static_cast<uint32_t>(
                   engine->runtime().reallocate(ptr, bytes))
             : 0;
}

std::vector<unsigned char> read_file(const char* path) {
  std::ifstream input(path, std::ios::binary);
  if (!input)
    throw std::runtime_error("open_input");
  return std::vector<unsigned char>(
      std::istreambuf_iterator<char>(input),
      std::istreambuf_iterator<char>());
}

Mode parse_mode(const std::string& value) {
  if (value == "rlbox_only")
    return Mode::rlbox_only;
  if (value == "tracked_no_check")
    return Mode::tracked_no_check;
  if (value == "extended_sp3")
    return Mode::extended_sp3;
  if (value == "typed_staging_identity")
    return Mode::typed_staging_identity;
  throw std::runtime_error("unknown_mode");
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 4 || argc > 5) {
    std::fprintf(stderr,
                 "usage: %s MODE INPUT ITERATIONS [FAULT_MODE]\n",
                 argv[0]);
    return 2;
  }

  try {
    const std::string mode_name = argv[1];
    const Mode mode = parse_mode(mode_name);
    const auto input = read_file(argv[2]);
    const uint32_t iterations =
        static_cast<uint32_t>(std::stoul(argv[3]));
    const uint32_t fault =
        argc == 5 ? static_cast<uint32_t>(std::stoul(argv[4])) : 0;

    if (iterations == 0)
      throw std::runtime_error("zero_iterations");
#if INTERSPEC_FAULT_TESTS
    if (fault && mode != Mode::extended_sp3 && mode != Mode::rlbox_only)
      throw std::runtime_error("fault_requires_security_comparator");
#else
    if (fault)
      throw std::runtime_error("fault_requires_separate_security_binary");
#endif

    Engine engine(mode);
    engine.setup(input);
    if (fault)
      engine.set_fault(fault);

    const auto start = std::chrono::steady_clock::now();
    const Stats stats = engine.run(input, iterations);
    const auto finish = std::chrono::steady_clock::now();
    engine.finish();
    const uint64_t elapsed = static_cast<uint64_t>(
        std::chrono::duration_cast<std::chrono::nanoseconds>(
            finish - start)
            .count());

    std::printf(
        "YAML_BENCH mode=%s iterations=%u input_bytes=%zu "
        "events=%llu scalars=%llu scalar_bytes=%llu hash=%016llx "
        "checks=%llu elapsed_ns=%llu\n",
        mode_name.c_str(), iterations, input.size(),
        static_cast<unsigned long long>(stats.events),
        static_cast<unsigned long long>(stats.scalars),
        static_cast<unsigned long long>(stats.scalar_bytes),
        static_cast<unsigned long long>(stats.hash),
        static_cast<unsigned long long>(stats.checks),
        static_cast<unsigned long long>(elapsed));
    return 0;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "yaml benchmark error: %s\n", error.what());
    return 1;
  }
}
