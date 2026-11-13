#pragma once

// Shared trusted-side engine for the registry ports of the remaining
// boundaries (EVAL_TRACKER.md items I7 to I12). One sandbox per engine, the
// object registry for U allocations, and the three policy switches.
//
// The including file defines the RLBox wasm2c macros and includes the module
// header before this one:
//
//   #define RLBOX_USE_EXCEPTIONS
//   #define RLBOX_USE_STATIC_CALLS() rlbox_wasm2c_sandbox_lookup_symbol
//   #define RLBOX_WASM2C_MODULE_NAME glue__lib__wasm2c
//   #include "glue_lib_wasm2c.h"
//   #include "rlbox.hpp"
//   #include "rlbox_wasm2c_sandbox.hpp"
//
// Build-time variants, as for the memcached and nginx bridges:
//   INTERSPEC_TRACKING=0                    RLBox-only module, no registry
//   INTERSPEC_TRACKING=1 INTERSPEC_CHECKS=0 tracking without check
//   INTERSPEC_TRACKING=1 INTERSPEC_CHECKS=1 InterSpec; INTERSPEC_SP3 switches
//                                           the registry check at run time
// Every variant keeps the sandbox confinement check on pointers from U.
// INTERSPEC_TRACKING=0 INTERSPEC_CHECKS=1 is InterSpec at a boundary where U
// returns no pointer to T: the SP1 and SP2 switches apply, there is no registry.

#include "interspec/policy_switches.h"
#include "interspec/runtime.h"

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <string>

#ifndef INTERSPEC_TRACKING
#define INTERSPEC_TRACKING 0
#endif
#ifndef INTERSPEC_CHECKS
#define INTERSPEC_CHECKS 0
#endif

namespace interspec {

// Policy is a struct of the port:
//   static constexpr const char* boundary;            name in reports
//   static bool register_all(Runtime&);               generated types and sites
//   static constexpr int reject_exit;                  exit status of a rejection
//   static CheckResult check(runtime, base, bytes, access);      for validate()
//   static CheckResult remaining(runtime, base, access, bytes&); for c_string()
template <class Policy>
class WasmPort {
 public:
  using Backend = rlbox::rlbox_wasm2c_sandbox;
  using Sandbox = rlbox::rlbox_sandbox<Backend>;
  using Pointer = rlbox::tainted<unsigned char*, Backend>;

  explicit WasmPort(uint32_t arena_bytes) {
    switches();  // read (and, if asked, report) the configuration first
    if (!sandbox_.create_sandbox()) throw std::runtime_error("sandbox_creation");
    try {
#if INTERSPEC_TRACKING
      const uint32_t base = sandbox_.get_sandbox_impl()->reserve_typed_arena(arena_bytes);
      if (!base) throw std::bad_alloc();
      runtime_ = std::make_unique<Runtime>(base, arena_bytes);
      if (!Policy::register_all(*runtime_)) throw std::runtime_error("policy_registration");
      sandbox_.get_sandbox_impl()->set_interspec_runtime(
          this,
          [](void* ctx, uint32_t site, uint32_t bytes) -> uint32_t {
            return static_cast<WasmPort*>(ctx)->runtime_->allocate_from_site(bytes, site);
          },
          [](void* ctx, uint32_t ptr) -> uint32_t {
            return static_cast<WasmPort*>(ctx)->runtime_->release(ptr);
          },
          [](void* ctx, uint32_t ptr) -> uint32_t {
            size_t bytes = 0;
            static_cast<WasmPort*>(ctx)->runtime_->allocation_size(ptr, bytes);
            return static_cast<uint32_t>(bytes);
          },
          [](void* ctx, uint32_t ptr, uint32_t bytes) -> uint32_t {
            return static_cast<WasmPort*>(ctx)->runtime_->reallocate(ptr, bytes);
          });
#else
      (void)arena_bytes;
#endif
    } catch (...) {
      sandbox_.destroy_sandbox();
      throw;
    }
  }
  ~WasmPort() { sandbox_.destroy_sandbox(); }
  WasmPort(const WasmPort&) = delete;
  WasmPort& operator=(const WasmPort&) = delete;

  Sandbox& sandbox() { return sandbox_; }

  static const PolicySwitches& switches() {
#if INTERSPEC_CHECKS
    static const std::string name = Policy::boundary;
#else
    static const std::string name =
        std::string(Policy::boundary) + "+sp3_fixed_at_compile_time";
#endif
    return policy_switches(name.c_str());
  }
  static bool sp1() { return switches().sp1; }
  static bool sp2() { return switches().sp2; }
  static bool sp3() {
#if INTERSPEC_CHECKS
    return switches().sp3 == Sp3Mode::full;
#else
    return false;
#endif
  }

  [[noreturn]] static void reject(const char* operation, const char* reason) {
    std::fprintf(stderr, "INTERSPEC_REJECT boundary=%s operation=%s reason=%s\n",
                 Policy::boundary, operation, reason);
    std::fflush(stderr);
    std::exit(Policy::reject_exit);
  }

  // Pointer from U to memory that T is about to read or write for `bytes`.
  // Confinement always; the registry check (live object, expected type,
  // bounds) when SP3 is on. `checks` counts registry checks performed.
  template <class Access>
  unsigned char* validate(Pointer pointer, uint32_t bytes, const Access& access,
                          const char* operation) {
    unsigned char* ptr = pointer.UNSAFE_unverified();
    if (!ptr) reject(operation, "null_pointer");
    if (!sandbox_.is_pointer_in_sandbox_memory(ptr)) reject(operation, "outside_sandbox");
    const uint32_t address = sandbox_.get_sandbox_impl()->sandbox_address(ptr);
    const uint64_t total = sandbox_.get_total_memory();
    if (address > total || bytes > total - address) reject(operation, "outside_sandbox");
#if INTERSPEC_CHECKS && INTERSPEC_TRACKING
    if (sp3()) {
      ++checks_;
      const CheckResult result = Policy::check(*runtime_, address, bytes, access);
      if (result != CheckResult::ok) reject(operation, check_result_name(result));
    }
#else
    (void)access;
#endif
    return ptr;
  }

  // As validate(), for a U address that T read out of a U structure.
  template <class Access>
  unsigned char* validate_address(uint32_t address, uint32_t bytes, const Access& access,
                                  const char* operation) {
    if (!address) reject(operation, "null_pointer");
    const uint64_t total = sandbox_.get_total_memory();
    if (address >= total || bytes > total - address) reject(operation, "outside_sandbox");
#if INTERSPEC_CHECKS && INTERSPEC_TRACKING
    if (sp3()) {
      ++checks_;
      const CheckResult result = Policy::check(*runtime_, address, bytes, access);
      if (result != CheckResult::ok) reject(operation, check_result_name(result));
    }
#else
    (void)access;
#endif
    return static_cast<unsigned char*>(sandbox_.get_memory_location()) + address;
  }

  // U address of the staging memory behind a pointer from input_buffer().
  uint32_t address_of(const unsigned char* staging) {
    return sandbox_.get_sandbox_impl()->sandbox_address(staging);
  }

  // NUL-terminated string that U returns, at most `limit` bytes before the
  // terminator. Confinement always. With SP3 on, the pointer must lie in a
  // live registered object of the expected type and the terminator must lie
  // inside that object. The bytes stay in U memory; `length` receives
  // the string length.
  template <class Access>
  const char* c_string(Pointer pointer, size_t limit, const Access& access,
                       const char* operation, size_t& length) {
    unsigned char* ptr = pointer.UNSAFE_unverified();
    if (!ptr) reject(operation, "null_pointer");
    if (!sandbox_.is_pointer_in_sandbox_memory(ptr)) reject(operation, "outside_sandbox");
    const uint32_t address = sandbox_.get_sandbox_impl()->sandbox_address(ptr);
    const uint64_t total = sandbox_.get_total_memory();
    if (address >= total) reject(operation, "outside_sandbox");
    size_t available = static_cast<size_t>(
        std::min<uint64_t>(static_cast<uint64_t>(limit) + 1, total - address));
    bool bounded_by_object = false;
#if INTERSPEC_CHECKS && INTERSPEC_TRACKING
    if (sp3()) {
      ++checks_;
      size_t remaining = 0;
      const CheckResult result = Policy::remaining(*runtime_, address, access, remaining);
      if (result != CheckResult::ok) reject(operation, check_result_name(result));
      if (remaining < available) {
        available = remaining;
        bounded_by_object = true;
      }
    }
#else
    (void)access;
#endif
    const void* end = std::memchr(ptr, 0, available);
    if (!end) reject(operation, bounded_by_object ? "out_of_bounds" : "unterminated");
    length = static_cast<size_t>(static_cast<const unsigned char*>(end) - ptr);
    return reinterpret_cast<const char*>(ptr);
  }

  // Staging memory that U handed out for T to fill (inputs). Confinement only:
  // it is U's own buffer and T only writes U-readable data into it.
  unsigned char* input_buffer(Pointer pointer, uint32_t bytes, const char* operation) {
    unsigned char* ptr = pointer.UNSAFE_unverified();
    if (!ptr) reject(operation, "null_pointer");
    if (!sandbox_.is_pointer_in_sandbox_memory(ptr)) reject(operation, "outside_sandbox");
    const uint32_t address = sandbox_.get_sandbox_impl()->sandbox_address(ptr);
    const uint64_t total = sandbox_.get_total_memory();
    if (address > total || bytes > total - address) reject(operation, "outside_sandbox");
    return ptr;
  }

  // SP2 off: copy U's version of an argument back over T's object, as a wrapper
  // without the policy would. Only a changed argument is written.
  void copy_back_unless_sp2(void* trusted, const unsigned char* in_u, size_t bytes) {
    if (sp2() || !bytes) return;
    if (std::memcmp(trusted, in_u, bytes) != 0) std::memcpy(trusted, in_u, bytes);
  }

  // SP1: what the wrapper copies in for an out-parameter U only writes.
  template <class T> static T withheld_unless_sp1_off(T trusted_value) {
    return sp1() ? T{} : trusted_value;
  }

  uint64_t checks() const { return checks_; }

 private:
  Sandbox sandbox_;
#if INTERSPEC_TRACKING
  std::unique_ptr<Runtime> runtime_;
#endif
  uint64_t checks_ = 0;
};

}  // namespace interspec
