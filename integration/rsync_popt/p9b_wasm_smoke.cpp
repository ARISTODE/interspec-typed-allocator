#define RLBOX_USE_EXCEPTIONS
#define RLBOX_ENABLE_DEBUG_ASSERTIONS
#define RLBOX_SINGLE_THREADED_INVOCATIONS
#define RLBOX_USE_STATIC_CALLS() rlbox_wasm2c_sandbox_lookup_symbol
#define RLBOX_WASM2C_MODULE_NAME glue__lib__wasm2c

#include "glue_lib_wasm2c.h"
#include "rlbox.hpp"
#include "rlbox_wasm2c_sandbox.hpp"

#include "interspec/policy_runtime.h"
#include "interspec_t_policy.h"

#include <cassert>
#include <cstdint>
#include <cstring>
#include <limits>
#include <memory>
#include <stdexcept>

namespace {
using SandboxType = rlbox::rlbox_wasm2c_sandbox;
using Sandbox = rlbox::rlbox_sandbox<SandboxType>;
using UPtr = rlbox::tainted<void*, SandboxType>;
using UCharPtr = rlbox::tainted<char*, SandboxType>;

extern "C" {
char* interspec_p4c_typed_copy(const char*);
void* interspec_p4c_table_new(uint32_t, uint32_t);
void* interspec_p4c_argv_new(uint32_t);
int interspec_p4c_argv_set(void*, uint32_t, char*);
void* interspec_p4c_context_new(char*, int, void*, void*, uint32_t);
void interspec_p4c_context_free(void*);
void interspec_p4c_table_free(void*);
void interspec_p4c_argv_free(void*);
}

class Engine;
static uint32_t alloc_cb(void*, uint32_t, uint32_t);
static uint32_t release_cb(void*, uint32_t);
static uint32_t size_cb(void*, uint32_t);
static uint32_t realloc_cb(void*, uint32_t, uint32_t);

class Engine {
 public:
  Engine() {
    if (!sandbox_.create_sandbox()) throw std::runtime_error("create wasm sandbox");
    constexpr uint32_t kArenaSize = 4u * 1024u * 1024u;
    const uint32_t base = sandbox_.get_sandbox_impl()->reserve_typed_arena(kArenaSize);
    if (!base) throw std::runtime_error("reserve wasm typed arena");
    policy_ = std::make_unique<interspec::PolicyRuntime>(base, kArenaSize);
    if (!interspec::rsync_popt_generated::register_types(runtime()) ||
        !interspec::rsync_popt_generated::register_wasm_allocation_policy(runtime()))
      throw std::runtime_error("register wasm allocation policy");
    sandbox_.get_sandbox_impl()->set_interspec_runtime(
        this, alloc_cb, release_cb, size_cb, realloc_cb);
  }

  Sandbox& sandbox() { return sandbox_; }
  interspec::Runtime& runtime() { return policy_->runtime(); }

  uint32_t allocate(uint32_t site, uint32_t size) {
    return static_cast<uint32_t>(runtime().allocate_from_site(size, site));
  }

  UCharPtr copy(const char* source) {
    const size_t bytes = std::strlen(source) + 1;
    auto temp = sandbox_.malloc_in_sandbox<char>(static_cast<uint32_t>(bytes));
    std::memcpy(temp.UNSAFE_unverified(), source, bytes);
    auto result = sandbox_.invoke_sandbox_function(interspec_p4c_typed_copy, temp);
    sandbox_.free_in_sandbox(temp);
    return result;
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
}  // namespace

int main() {
  using namespace interspec::rsync_popt_generated;
  Engine engine;

  auto tracked = engine.copy("abc");
  const uint32_t tracked_addr = engine.address(tracked.UNSAFE_unverified());
  assert(engine.runtime().check(tracked_addr, 4, kTypeHashChar) ==
         interspec::CheckResult::ok);
  assert(engine.runtime().check(tracked_addr, 5, kTypeHashChar) ==
         interspec::CheckResult::out_of_bounds);

  auto ordinary = engine.sandbox().malloc_in_sandbox<char>(4);
  std::memcpy(ordinary.UNSAFE_unverified(), "abc", 4);
  const uint32_t ordinary_addr = engine.address(ordinary.UNSAFE_unverified());
  assert(engine.runtime().check(ordinary_addr, 1, kTypeHashChar) ==
         interspec::CheckResult::untracked);

  auto name = engine.copy("p9b");
  auto arg0 = engine.copy("p9b");
  auto argv = engine.sandbox().invoke_sandbox_function(interspec_p4c_argv_new, 1u);
  assert(argv.UNSAFE_unverified() != nullptr);
  assert(engine.sandbox()
             .invoke_sandbox_function(interspec_p4c_argv_set, argv, 0u, arg0)
             .UNSAFE_unverified() == 1);
  auto table = engine.sandbox().invoke_sandbox_function(interspec_p4c_table_new, 1u, 0u);
  assert(table.UNSAFE_unverified() != nullptr);
  auto context = engine.sandbox().invoke_sandbox_function(
      interspec_p4c_context_new, name, 1, argv, table, 0u);
  assert(context.UNSAFE_unverified() != nullptr);
  const uint32_t context_addr = engine.address(context.UNSAFE_unverified());
  assert(engine.runtime().check(context_addr, 1, kTypeHashChar) ==
         interspec::CheckResult::wrong_type);

  engine.sandbox().invoke_sandbox_function(interspec_p4c_context_free, context);
  assert(engine.runtime().check(context_addr, 1, kTypeHashPoptContextS) ==
         interspec::CheckResult::untracked);

  engine.sandbox().invoke_sandbox_function(interspec_p4c_table_free, table);
  engine.sandbox().invoke_sandbox_function(interspec_p4c_argv_free, argv);
  engine.sandbox().free_in_sandbox(ordinary);
  return 0;
}
