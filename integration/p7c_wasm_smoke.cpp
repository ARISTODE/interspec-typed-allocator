#define RLBOX_USE_EXCEPTIONS
#define RLBOX_ENABLE_DEBUG_ASSERTIONS
#define RLBOX_SINGLE_THREADED_INVOCATIONS
#define RLBOX_USE_STATIC_CALLS() rlbox_wasm2c_sandbox_lookup_symbol
#define RLBOX_WASM2C_MODULE_NAME glue__lib__wasm2c

#include "glue_lib_wasm2c.h"
#include "rlbox.hpp"
#include "rlbox_wasm2c_sandbox.hpp"

#include "interspec/policy_runtime.h"
#include "interspec_bipbuffer_t_policy.h"
#include "interspec_pcre_t_policy.h"
#include "interspec_yaml_t_policy.h"

#include <cassert>
#include <cstdint>
#include <cstring>
#include <limits>
#include <memory>
#include <stdexcept>
#include <vector>

namespace {
using SandboxType = rlbox::rlbox_wasm2c_sandbox;
using Sandbox = rlbox::rlbox_sandbox<SandboxType>;

extern "C" {
void* interspec_wasm_bipbuf_make_and_fill(void);
unsigned char* interspec_wasm_bipbuf_peek_valid(void*);
unsigned char* interspec_wasm_bipbuf_peek_wrong_type(void);
unsigned char* interspec_wasm_bipbuf_peek_untracked(void);
unsigned char* interspec_wasm_bipbuf_peek_oversized(void*);
uint32_t interspec_wasm_bipbuf_last_size(void);

void* interspec_wasm_pcre_compile_named(void);
unsigned char* interspec_wasm_pcre_name_table(void*);
unsigned char* interspec_wasm_pcre_name_table_wrong_type(void);
unsigned char* interspec_wasm_pcre_name_table_untracked(void);
unsigned char* interspec_wasm_pcre_name_table_oversized(void*);
uint32_t interspec_wasm_pcre_name_table_size(void);

void* interspec_wasm_yaml_make_scalar(void);
unsigned char* interspec_wasm_yaml_scalar_value(void*);
unsigned char* interspec_wasm_yaml_scalar_wrong_type(void);
unsigned char* interspec_wasm_yaml_scalar_untracked(void);
unsigned char* interspec_wasm_yaml_scalar_oversized(void*);
uint32_t interspec_wasm_yaml_scalar_size(void);
}

class Engine;
static uint32_t alloc_cb(void*, uint32_t, uint32_t);
static uint32_t release_cb(void*, uint32_t);
static uint32_t size_cb(void*, uint32_t);
static uint32_t realloc_cb(void*, uint32_t, uint32_t);

class Engine {
 public:
  template <typename RegisterTypes, typename RegisterSites>
  Engine(RegisterTypes register_types, RegisterSites register_sites,
         uint32_t arena_size = 4u * 1024u * 1024u) {
    if (!sandbox_.create_sandbox()) throw std::runtime_error("create wasm sandbox");
    const uint32_t base = sandbox_.get_sandbox_impl()->reserve_typed_arena(arena_size);
    if (!base) throw std::runtime_error("reserve wasm typed arena");
    policy_ = std::make_unique<interspec::PolicyRuntime>(base, arena_size);
    if (!register_types(runtime()) || !register_sites(runtime()))
      throw std::runtime_error("register wasm policy");
    sandbox_.get_sandbox_impl()->set_interspec_runtime(
        this, alloc_cb, release_cb, size_cb, realloc_cb);
  }

  Sandbox& sandbox() { return sandbox_; }
  interspec::Runtime& runtime() { return policy_->runtime(); }
  uint32_t allocate(uint32_t site, uint32_t size) {
    return static_cast<uint32_t>(runtime().allocate_from_site(size, site));
  }
  uint32_t address(const void* ptr) {
    return sandbox_.get_sandbox_impl()->sandbox_address(ptr);
  }

 private:
  Sandbox sandbox_;
  std::unique_ptr<interspec::PolicyRuntime> policy_;
};

static uint32_t alloc_cb(void* context, uint32_t site, uint32_t size) {
  return static_cast<Engine*>(context)->allocate(site, size);
}
static uint32_t release_cb(void* context, uint32_t ptr) {
  return static_cast<Engine*>(context)->runtime().release(ptr) ? 1u : 0u;
}
static uint32_t size_cb(void* context, uint32_t ptr) {
  size_t size = 0;
  if (!static_cast<Engine*>(context)->runtime().allocation_size(ptr, size) ||
      size > std::numeric_limits<uint32_t>::max())
    return 0u;
  return static_cast<uint32_t>(size);
}
static uint32_t realloc_cb(void* context, uint32_t ptr, uint32_t size) {
  return static_cast<uint32_t>(
      static_cast<Engine*>(context)->runtime().reallocate(ptr, size));
}

void test_bipbuffer() {
  namespace P = interspec::memcached_bipbuffer_generated;
  Engine engine(P::register_types, P::register_wasm_allocation_policy);
  auto owner = engine.sandbox().invoke_sandbox_function(interspec_wasm_bipbuf_make_and_fill);
  assert(owner.UNSAFE_unverified() != nullptr);
  const uint32_t owner_addr = engine.address(owner.UNSAFE_unverified());
  assert(engine.runtime().check(owner_addr, 1, P::kTypeHashBipbufT) == interspec::CheckResult::ok);

  auto valid = engine.sandbox().invoke_sandbox_function(interspec_wasm_bipbuf_peek_valid, owner);
  const uint32_t valid_len = engine.sandbox().invoke_sandbox_function(interspec_wasm_bipbuf_last_size).UNSAFE_unverified();
  const uint32_t valid_addr = engine.address(valid.UNSAFE_unverified());
  assert(P::check(engine.runtime(), valid_addr, valid_len, P::kUseBipbufPeekAllRange) == interspec::CheckResult::ok);

  auto wrong = engine.sandbox().invoke_sandbox_function(interspec_wasm_bipbuf_peek_wrong_type);
  const uint32_t wrong_len = engine.sandbox().invoke_sandbox_function(interspec_wasm_bipbuf_last_size).UNSAFE_unverified();
  assert(P::check(engine.runtime(), engine.address(wrong.UNSAFE_unverified()), wrong_len, P::kUseBipbufPeekAllRange) == interspec::CheckResult::wrong_type);

  auto untracked = engine.sandbox().invoke_sandbox_function(interspec_wasm_bipbuf_peek_untracked);
  const uint32_t untracked_len = engine.sandbox().invoke_sandbox_function(interspec_wasm_bipbuf_last_size).UNSAFE_unverified();
  assert(P::check(engine.runtime(), engine.address(untracked.UNSAFE_unverified()), untracked_len, P::kUseBipbufPeekAllRange) == interspec::CheckResult::untracked);

  auto oversized = engine.sandbox().invoke_sandbox_function(interspec_wasm_bipbuf_peek_oversized, owner);
  const uint32_t oversized_len = engine.sandbox().invoke_sandbox_function(interspec_wasm_bipbuf_last_size).UNSAFE_unverified();
  assert(P::check(engine.runtime(), engine.address(oversized.UNSAFE_unverified()), oversized_len, P::kUseBipbufPeekAllRange) == interspec::CheckResult::out_of_bounds);
}

void test_pcre() {
  namespace P = interspec::nginx_libpcre_generated;
  Engine engine(P::register_types, P::register_wasm_allocation_policy);
  auto compiled = engine.sandbox().invoke_sandbox_function(interspec_wasm_pcre_compile_named);
  assert(compiled.UNSAFE_unverified() != nullptr);
  const uint32_t compiled_addr = engine.address(compiled.UNSAFE_unverified());
  assert(engine.runtime().check(compiled_addr, 1, P::kTypeHashConstPcre) == interspec::CheckResult::ok);

  auto valid = engine.sandbox().invoke_sandbox_function(interspec_wasm_pcre_name_table, compiled);
  const uint32_t valid_len = engine.sandbox().invoke_sandbox_function(interspec_wasm_pcre_name_table_size).UNSAFE_unverified();
  assert(P::check(engine.runtime(), engine.address(valid.UNSAFE_unverified()), valid_len, P::kUsePcreNameTableRange) == interspec::CheckResult::ok);

  auto wrong = engine.sandbox().invoke_sandbox_function(interspec_wasm_pcre_name_table_wrong_type);
  const uint32_t wrong_len = engine.sandbox().invoke_sandbox_function(interspec_wasm_pcre_name_table_size).UNSAFE_unverified();
  assert(P::check(engine.runtime(), engine.address(wrong.UNSAFE_unverified()), wrong_len, P::kUsePcreNameTableRange) == interspec::CheckResult::wrong_type);

  auto untracked = engine.sandbox().invoke_sandbox_function(interspec_wasm_pcre_name_table_untracked);
  const uint32_t untracked_len = engine.sandbox().invoke_sandbox_function(interspec_wasm_pcre_name_table_size).UNSAFE_unverified();
  assert(P::check(engine.runtime(), engine.address(untracked.UNSAFE_unverified()), untracked_len, P::kUsePcreNameTableRange) == interspec::CheckResult::untracked);

  auto oversized = engine.sandbox().invoke_sandbox_function(interspec_wasm_pcre_name_table_oversized, compiled);
  const uint32_t oversized_len = engine.sandbox().invoke_sandbox_function(interspec_wasm_pcre_name_table_size).UNSAFE_unverified();
  assert(P::check(engine.runtime(), engine.address(oversized.UNSAFE_unverified()), oversized_len, P::kUsePcreNameTableRange) == interspec::CheckResult::out_of_bounds);
}

void test_yaml() {
  namespace P = interspec::yaml_libyaml_generated;
  Engine engine(P::register_types, P::register_wasm_allocation_policy);
  auto event = engine.sandbox().invoke_sandbox_function(interspec_wasm_yaml_make_scalar);
  assert(event.UNSAFE_unverified() != nullptr);
  auto valid = engine.sandbox().invoke_sandbox_function(interspec_wasm_yaml_scalar_value, event);
  const uint32_t valid_len = engine.sandbox().invoke_sandbox_function(interspec_wasm_yaml_scalar_size).UNSAFE_unverified();
  const uint32_t valid_addr = engine.address(valid.UNSAFE_unverified());
  assert(P::check(engine.runtime(), valid_addr, valid_len, P::kUseYamlScalarValueRange) == interspec::CheckResult::ok);
  assert(engine.runtime().check(valid_addr, 1, P::kTypeHashYamlScalarValue) == interspec::CheckResult::ok);

  auto wrong = engine.sandbox().invoke_sandbox_function(interspec_wasm_yaml_scalar_wrong_type);
  const uint32_t wrong_len = engine.sandbox().invoke_sandbox_function(interspec_wasm_yaml_scalar_size).UNSAFE_unverified();
  assert(P::check(engine.runtime(), engine.address(wrong.UNSAFE_unverified()), wrong_len, P::kUseYamlScalarValueRange) == interspec::CheckResult::wrong_type);

  auto untracked = engine.sandbox().invoke_sandbox_function(interspec_wasm_yaml_scalar_untracked);
  const uint32_t untracked_len = engine.sandbox().invoke_sandbox_function(interspec_wasm_yaml_scalar_size).UNSAFE_unverified();
  assert(P::check(engine.runtime(), engine.address(untracked.UNSAFE_unverified()), untracked_len, P::kUseYamlScalarValueRange) == interspec::CheckResult::untracked);

  auto oversized = engine.sandbox().invoke_sandbox_function(interspec_wasm_yaml_scalar_oversized, event);
  const uint32_t oversized_len = engine.sandbox().invoke_sandbox_function(interspec_wasm_yaml_scalar_size).UNSAFE_unverified();
  assert(P::check(engine.runtime(), engine.address(oversized.UNSAFE_unverified()), oversized_len, P::kUseYamlScalarValueRange) == interspec::CheckResult::out_of_bounds);
}
}  // namespace

int main() {
  test_bipbuffer();
  test_pcre();
  test_yaml();
  return 0;
}
