#define RLBOX_USE_EXCEPTIONS
#define RLBOX_ENABLE_DEBUG_ASSERTIONS
#define RLBOX_SINGLE_THREADED_INVOCATIONS

#include "rlbox.hpp"
#include "rlbox_nacl_sandbox.hpp"

#include "interspec/runtime.h"
#include "interspec_popt_t_policy.h"
#include "popt.h"
#include "site_provenance.h"

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <memory>
#include <stdexcept>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {

using SandboxType = rlbox::rlbox_nacl_sandbox;
using Sandbox = rlbox::rlbox_sandbox<SandboxType>;
using UPtr = rlbox::tainted<void*, SandboxType>;
using UCharPtr = rlbox::tainted<char*, SandboxType>;
using U32 = rlbox::tainted<uint32_t, SandboxType>;

using p4c_release_fn = uint32_t (*)(uint32_t);
using p4c_size_fn = uint32_t (*)(uint32_t);
using p4c_realloc_fn = uint32_t (*)(uint32_t, uint32_t);

extern "C" {
void interspec_popt_init_lifetime(uint32_t,
                                  p4c_release_fn,
                                  p4c_size_fn,
                                  p4c_realloc_fn);
char* interspec_p4c_typed_copy(const char*);
void* interspec_p4c_table_new(uint32_t, uint32_t);
int interspec_p4c_slot_set_int(void*, uint32_t, int);
int interspec_p4c_slot_set_string(void*, uint32_t, char*);
int interspec_p4c_option_set(void*, uint32_t, uint32_t, uint32_t, uint32_t, int);
int interspec_p4c_option_set_strings(void*, uint32_t, char*, char*, char*);
int interspec_p4c_slot_get_int(void*, uint32_t);
char* interspec_p4c_slot_get_string(void*, uint32_t);
void* interspec_p4c_argv_new(uint32_t);
int interspec_p4c_argv_set(void*, uint32_t, char*);
void* interspec_p4c_context_new(char*, int, void*, void*, uint32_t);
int interspec_p4c_next(void*);
char* interspec_p4c_opt_arg(void*);
char* interspec_p4c_bad_option(void*, uint32_t);
uint32_t interspec_p4c_args_count(void*);
char* interspec_p4c_args_at(void*, uint32_t);
void interspec_p4c_context_free(void*);
void interspec_p4c_table_free(void*);
void interspec_p4c_argv_free(void*);
}

class Engine;
Engine& engine_from(Sandbox& sandbox);

static U32 p4c_allocate(Sandbox& sandbox, U32 size);
static U32 p4c_release(Sandbox& sandbox, U32 ptr);
static U32 p4c_size(Sandbox& sandbox, U32 ptr);
static U32 p4c_reallocate(Sandbox& sandbox, U32 ptr, U32 size);

class Engine {
 public:
  Engine() {
    if (!sandbox_.create_sandbox(GLUE_LIB_NACL_PATH, NACL_LIBC_PATH))
      throw std::runtime_error("failed to create RLBox NaCl sandbox");

    constexpr uint32_t kArenaSize = 16u * 1024u * 1024u;
    const uint32_t arena_base =
      sandbox_.get_sandbox_impl()->reserve_typed_arena(kArenaSize);
    if (!arena_base) throw std::runtime_error("failed to reserve typed arena");

    runtime_ = std::make_unique<interspec::Runtime>(arena_base, kArenaSize);
    using namespace interspec::rsync_popt_generated;
    if (!register_types(*runtime_))
      throw std::runtime_error("failed to register InterSpec types");

    auto resolve_symbol = [&](const char* name) -> uintptr_t {
      return reinterpret_cast<uintptr_t>(
        sandbox_.get_sandbox_impl()->impl_lookup_symbol(name));
    };
    if (!register_allocation_sites(*runtime_, resolve_symbol))
      throw std::runtime_error("failed to register InterSpec allocation sites");
    if (!runtime_->register_allocation_site(
          INTERSPEC_POPT_STRDUP_SITE_ID,
          resolve_symbol(INTERSPEC_POPT_STRDUP_BEGIN_SYMBOL),
          resolve_symbol(INTERSPEC_POPT_STRDUP_END_SYMBOL),
          kTypeIdChar))
      throw std::runtime_error("failed to register popt strdup allocation site");

    sandbox_.sandbox_storage = this;
    alloc_cb_ = sandbox_.register_callback(p4c_allocate);
    release_cb_ = sandbox_.register_callback(p4c_release);
    size_cb_ = sandbox_.register_callback(p4c_size);
    realloc_cb_ = sandbox_.register_callback(p4c_reallocate);
    const uint32_t alloc_slot = sandbox_.get_sandbox_impl()->callback_slot_for_key(
      reinterpret_cast<const void*>(p4c_allocate));
    if (alloc_slot == std::numeric_limits<uint32_t>::max())
      throw std::runtime_error("failed to resolve allocator callback slot");
    sandbox_.invoke_sandbox_function(interspec_popt_init_lifetime,
                                     alloc_slot,
                                     release_cb_,
                                     size_cb_,
                                     realloc_cb_);
  }

  Sandbox& sandbox() { return sandbox_; }
  interspec::Runtime& runtime() { return *runtime_; }

  uintptr_t allocate_for_callback_pc(uint32_t size) {
    auto* impl = sandbox_.get_sandbox_impl();
    const uintptr_t pc = impl->callback_program_counter();
    uintptr_t result = runtime_->allocate_from_pc(size, pc);
    if (result) return result;

    const uintptr_t new_pc = impl->callback_new_program_counter();
    if (new_pc && new_pc != pc)
      result = runtime_->allocate_from_pc(size, new_pc);
    return result;
  }

  UCharPtr copy_to_u(const char* src) {
    if (!src) return UCharPtr(nullptr);

    const size_t bytes = std::strlen(src) + 1;
    if (bytes > std::numeric_limits<uint32_t>::max())
      throw std::runtime_error("popt string exceeds sandbox ABI");

    auto temporary = sandbox_.malloc_in_sandbox<char>(static_cast<uint32_t>(bytes));
    if (temporary.UNSAFE_unverified() == nullptr)
      throw std::bad_alloc();
    std::memcpy(temporary.UNSAFE_unverified(), src, bytes);

    auto typed =
      sandbox_.invoke_sandbox_function(interspec_p4c_typed_copy, temporary);
    sandbox_.free_in_sandbox(temporary);
    if (typed.UNSAFE_unverified() == nullptr) throw std::bad_alloc();
    return typed;
  }

  char* copy_checked(UCharPtr source) {
    using namespace interspec::rsync_popt_generated;

    char* raw = source.UNSAFE_unverified();
    if (!raw) return nullptr;

    const uintptr_t sandbox_ptr =
      sandbox_.get_sandbox_impl()->sandbox_address(raw);
    size_t remaining = 0;
    const auto result = runtime_->remaining_bytes(
      sandbox_ptr, kTypeHashChar, remaining);
    if (result != interspec::CheckResult::ok || remaining == 0)
      throw std::runtime_error("InterSpec rejected popt char pointer");

    const void* end = std::memchr(raw, '\0', remaining);
    if (!end)
      throw std::runtime_error("InterSpec rejected unterminated popt string");

    const size_t bytes =
      static_cast<const char*>(end) - raw + 1;
    auto copy = std::make_unique<char[]>(bytes);
    std::memcpy(copy.get(), raw, bytes);
    char* result_ptr = copy.get();
    trusted_strings_.push_back(std::move(copy));
    return result_ptr;
  }

 private:
  using AllocCallback = decltype(
    std::declval<Sandbox&>().register_callback(&p4c_allocate));
  using ReleaseCallback = decltype(
    std::declval<Sandbox&>().register_callback(&p4c_release));
  using SizeCallback = decltype(
    std::declval<Sandbox&>().register_callback(&p4c_size));
  using ReallocCallback = decltype(
    std::declval<Sandbox&>().register_callback(&p4c_reallocate));

  Sandbox sandbox_;
  std::unique_ptr<interspec::Runtime> runtime_;
  AllocCallback alloc_cb_;
  ReleaseCallback release_cb_;
  SizeCallback size_cb_;
  ReallocCallback realloc_cb_;
  std::vector<std::unique_ptr<char[]>> trusted_strings_;
};

Engine& engine() {
  static Engine* instance = new Engine();
  return *instance;
}

Engine& engine_from(Sandbox& sandbox) {
  auto* value = static_cast<Engine*>(sandbox.sandbox_storage);
  if (!value) throw std::runtime_error("missing P4c engine context");
  return *value;
}

static U32 p4c_allocate(Sandbox& sandbox, U32 size) {
  return static_cast<uint32_t>(
    engine_from(sandbox).allocate_for_callback_pc(size.UNSAFE_unverified()));
}

static U32 p4c_release(Sandbox& sandbox, U32 ptr) {
  return engine_from(sandbox).runtime().release(ptr.UNSAFE_unverified()) ? 1u : 0u;
}

static U32 p4c_size(Sandbox& sandbox, U32 ptr) {
  size_t size = 0;
  if (!engine_from(sandbox).runtime().allocation_size(
        ptr.UNSAFE_unverified(), size))
    return 0u;
  if (size > std::numeric_limits<uint32_t>::max()) return 0u;
  return static_cast<uint32_t>(size);
}

static U32 p4c_reallocate(Sandbox& sandbox, U32 ptr, U32 size) {
  return static_cast<uint32_t>(engine_from(sandbox).runtime().reallocate(
    ptr.UNSAFE_unverified(), size.UNSAFE_unverified()));
}

enum class SlotKind { integer, string };

struct SlotBinding {
  void* trusted_address;
  SlotKind kind;
  uint32_t index;
};

struct TrustedContext {
  UPtr untrusted_context;
  UPtr untrusted_table;
  UPtr untrusted_argv;
  std::vector<SlotBinding> slots;
  std::vector<const char*> args_cache;
};

static TrustedContext* unwrap(poptContext context) {
  return reinterpret_cast<TrustedContext*>(context);
}

static SlotKind option_slot_kind(const struct poptOption& option) {
  const unsigned type = option.argInfo & POPT_ARG_MASK;
  if (type == POPT_ARG_STRING) return SlotKind::string;
  if (type == POPT_ARG_NONE || type == POPT_ARG_INT || type == POPT_ARG_VAL)
    return SlotKind::integer;
  throw std::runtime_error("unsupported rsync popt destination type");
}

static uint32_t option_count(const struct poptOption* options) {
  if (!options) throw std::runtime_error("null popt option table");
  uint32_t count = 0;
  for (;;) {
    if (count == std::numeric_limits<uint32_t>::max())
      throw std::runtime_error("popt option table too large");
    const auto& option = options[count++];
    if (!option.longName && option.shortName == '\0' && !option.arg) return count;
  }
}

static void sync_slots(TrustedContext& context) {
  Engine& e = engine();
  for (const auto& binding : context.slots) {
    if (binding.kind == SlotKind::integer) {
      const int value = e.sandbox()
                          .invoke_sandbox_function(interspec_p4c_slot_get_int,
                                                   context.untrusted_table,
                                                   binding.index)
                          .UNSAFE_unverified();
      std::memcpy(binding.trusted_address, &value, sizeof(value));
    } else {
      auto value = e.sandbox().invoke_sandbox_function(
        interspec_p4c_slot_get_string,
        context.untrusted_table,
        binding.index);
      char* copy = e.copy_checked(value);
      std::memcpy(binding.trusted_address, &copy, sizeof(copy));
    }
  }
}

static std::unique_ptr<TrustedContext> make_context(
  const char* name,
  int argc,
  const char** argv,
  const struct poptOption* options,
  unsigned int flags) {
  if (argc < 0 || (argc > 0 && !argv))
    throw std::runtime_error("invalid popt argv");

  Engine& e = engine();
  auto context = std::make_unique<TrustedContext>();

  const uint32_t count = option_count(options);
  std::unordered_map<void*, uint32_t> slot_by_address;
  std::vector<SlotKind> kinds;

  for (uint32_t i = 0; i < count; ++i) {
    if (!options[i].arg) continue;
    const SlotKind kind = option_slot_kind(options[i]);
    auto inserted = slot_by_address.emplace(
      options[i].arg, static_cast<uint32_t>(kinds.size()));
    if (inserted.second) {
      kinds.push_back(kind);
    } else if (kinds[inserted.first->second] != kind) {
      throw std::runtime_error("popt destination reused with incompatible types");
    }
  }

  context->untrusted_table = e.sandbox().invoke_sandbox_function(
    interspec_p4c_table_new,
    count,
    static_cast<uint32_t>(kinds.size()));
  if (context->untrusted_table.UNSAFE_unverified() == nullptr)
    throw std::bad_alloc();

  context->slots.reserve(kinds.size());
  for (const auto& entry : slot_by_address) {
    const uint32_t index = entry.second;
    const SlotKind kind = kinds[index];
    context->slots.push_back({entry.first, kind, index});

    if (kind == SlotKind::integer) {
      int initial = 0;
      std::memcpy(&initial, entry.first, sizeof(initial));
      const int ok = e.sandbox()
                       .invoke_sandbox_function(interspec_p4c_slot_set_int,
                                                context->untrusted_table,
                                                index,
                                                initial)
                       .UNSAFE_unverified();
      if (!ok) throw std::runtime_error("failed to initialize popt int slot");
    } else {
      const char* initial = nullptr;
      std::memcpy(&initial, entry.first, sizeof(initial));
      auto copied = e.copy_to_u(initial);
      const int ok = e.sandbox()
                       .invoke_sandbox_function(interspec_p4c_slot_set_string,
                                                context->untrusted_table,
                                                index,
                                                copied)
                       .UNSAFE_unverified();
      if (!ok) throw std::runtime_error("failed to initialize popt string slot");
    }
  }

  for (uint32_t i = 0; i < count; ++i) {
    const auto& option = options[i];
    uint32_t slot = std::numeric_limits<uint32_t>::max();
    if (option.arg) slot = slot_by_address.at(option.arg);

    const int ok = e.sandbox()
                     .invoke_sandbox_function(interspec_p4c_option_set,
                                              context->untrusted_table,
                                              i,
                                              static_cast<uint32_t>(
                                                static_cast<unsigned char>(
                                                  option.shortName)),
                                              option.argInfo,
                                              slot,
                                              option.val)
                     .UNSAFE_unverified();
    if (!ok) throw std::runtime_error("failed to copy popt option");

    auto long_name = e.copy_to_u(option.longName);
    auto description = e.copy_to_u(option.descrip);
    auto arg_description = e.copy_to_u(option.argDescrip);
    const int strings_ok =
      e.sandbox()
        .invoke_sandbox_function(interspec_p4c_option_set_strings,
                                 context->untrusted_table,
                                 i,
                                 long_name,
                                 description,
                                 arg_description)
        .UNSAFE_unverified();
    if (!strings_ok) throw std::runtime_error("failed to copy popt option strings");
  }

  context->untrusted_argv = e.sandbox().invoke_sandbox_function(
    interspec_p4c_argv_new, static_cast<uint32_t>(argc));
  if (context->untrusted_argv.UNSAFE_unverified() == nullptr)
    throw std::bad_alloc();

  for (int i = 0; i < argc; ++i) {
    auto copied = e.copy_to_u(argv[i]);
    const int ok = e.sandbox()
                     .invoke_sandbox_function(interspec_p4c_argv_set,
                                              context->untrusted_argv,
                                              static_cast<uint32_t>(i),
                                              copied)
                     .UNSAFE_unverified();
    if (!ok) throw std::runtime_error("failed to copy popt argv");
  }

  auto copied_name = e.copy_to_u(name);
  context->untrusted_context = e.sandbox().invoke_sandbox_function(
    interspec_p4c_context_new,
    copied_name,
    argc,
    context->untrusted_argv,
    context->untrusted_table,
    flags);
  if (context->untrusted_context.UNSAFE_unverified() == nullptr)
    return nullptr;

  return context;
}

[[noreturn]] static void bridge_failure() {
  std::abort();
}

}  // namespace

extern "C" poptContext poptGetContext(const char* name,
                                       int argc,
                                       const char** argv,
                                       const struct poptOption* options,
                                       unsigned int flags) {
  try {
    auto context = make_context(name, argc, argv, options, flags);
    return reinterpret_cast<poptContext>(context.release());
  } catch (...) {
    bridge_failure();
  }
}

extern "C" int poptGetNextOpt(poptContext opaque) {
  try {
    TrustedContext* context = unwrap(opaque);
    if (!context) return POPT_ERROR_NULLARG;
    const int result = engine().sandbox()
                         .invoke_sandbox_function(interspec_p4c_next,
                                                  context->untrusted_context)
                         .UNSAFE_unverified();
    sync_slots(*context);
    return result;
  } catch (...) {
    bridge_failure();
  }
}

extern "C" char* poptGetOptArg(poptContext opaque) {
  try {
    TrustedContext* context = unwrap(opaque);
    if (!context) return nullptr;
    auto value = engine().sandbox().invoke_sandbox_function(
      interspec_p4c_opt_arg, context->untrusted_context);
    return engine().copy_checked(value);
  } catch (...) {
    bridge_failure();
  }
}

extern "C" const char** poptGetArgs(poptContext opaque) {
  try {
    TrustedContext* context = unwrap(opaque);
    if (!context) return nullptr;

    const uint32_t count = engine().sandbox()
                             .invoke_sandbox_function(interspec_p4c_args_count,
                                                      context->untrusted_context)
                             .UNSAFE_unverified();
    if (count == 0) return nullptr;

    context->args_cache.clear();
    context->args_cache.reserve(static_cast<size_t>(count) + 1);
    for (uint32_t i = 0; i < count; ++i) {
      auto value = engine().sandbox().invoke_sandbox_function(
        interspec_p4c_args_at, context->untrusted_context, i);
      char* copy = engine().copy_checked(value);
      if (!copy) bridge_failure();
      context->args_cache.push_back(copy);
    }
    context->args_cache.push_back(nullptr);
    return context->args_cache.data();
  } catch (...) {
    bridge_failure();
  }
}

extern "C" const char* poptBadOption(poptContext opaque, unsigned int flags) {
  try {
    TrustedContext* context = unwrap(opaque);
    if (!context) return nullptr;
    auto value = engine().sandbox().invoke_sandbox_function(
      interspec_p4c_bad_option, context->untrusted_context, flags);
    return engine().copy_checked(value);
  } catch (...) {
    bridge_failure();
  }
}

extern "C" poptContext poptFreeContext(poptContext opaque) {
  try {
    std::unique_ptr<TrustedContext> context(unwrap(opaque));
    if (!context) return nullptr;

    engine().sandbox().invoke_sandbox_function(
      interspec_p4c_context_free, context->untrusted_context);
    engine().sandbox().invoke_sandbox_function(
      interspec_p4c_table_free, context->untrusted_table);
    engine().sandbox().invoke_sandbox_function(
      interspec_p4c_argv_free, context->untrusted_argv);
    return nullptr;
  } catch (...) {
    bridge_failure();
  }
}

extern "C" int poptReadDefaultConfig(poptContext, int) {
  /* The NaCl sandbox intentionally has no host filesystem authority.  The
   * rsync caller ignores errors here; no default config also means there are no
   * config aliases to import into the sandboxed parser. */
  return 0;
}

extern "C" int poptAddAlias(poptContext, struct poptAlias, int) {
  /* rsync uses this only to shadow --daemon and --server aliases after reading
   * the default config.  P4c does not import that config, so there are no
   * aliases to suppress. */
  return 0;
}
