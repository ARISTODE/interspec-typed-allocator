#define RLBOX_USE_EXCEPTIONS
#define RLBOX_ENABLE_DEBUG_ASSERTIONS
#define RLBOX_SINGLE_THREADED_INVOCATIONS

#include "rlbox.hpp"
#include "rlbox_nacl_sandbox.hpp"

#include "interspec/policy_runtime.h"
#include "interspec/pointer_census.h"
#include "interspec/policy_switches.h"
#include "interspec/boundary/popt_field_policies.h"
#include "interspec_popt_t_policy.h"
#include "popt.h"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
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
#ifdef INTERSPEC_FAULT_TESTS
void interspec_test_set_fault(uint32_t, uint32_t);
void interspec_poc_set_flags(int);
#endif
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
void* interspec_p4c_table_options(void*);
char* interspec_p4c_option_string(void*, uint32_t, uint32_t);
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

// Per-policy switches (INTERSPEC_SP1, INTERSPEC_SP2, INTERSPEC_SP3). The
// comparator and no-validation builds fix the pointer check when compiled, so
// their report line says so instead of naming a switch value they ignore.
#if defined(INTERSPEC_RLBOX_SECURITY_COMPARATOR) || \
    defined(INTERSPEC_P8_MEASURE_NO_VALIDATION) || \
    defined(INTERSPEC_P9A_RLBOX_ONLY)
constexpr const char* kPolicyBoundary = "rsync_popt+sp3_fixed_at_compile_time";
#else
constexpr const char* kPolicyBoundary = "rsync_popt";
#endif

static const interspec::PolicySwitches& switches() {
  return interspec::policy_switches(kPolicyBoundary);
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

    policy_runtime_ =
      std::make_unique<interspec::PolicyRuntime>(arena_base, kArenaSize);
    auto* impl = sandbox_.get_sandbox_impl();
    if (!policy_runtime_->initialize_from_sandbox(
          *impl,
          [](interspec::Runtime& runtime) {
            return interspec::rsync_popt_generated::register_types(runtime);
          },
          [](interspec::Runtime& runtime, auto resolve) {
            return interspec::rsync_popt_generated::register_allocation_policy(
              runtime, resolve);
          }))
      throw std::runtime_error("failed to initialize InterSpec allocation policy");

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
  interspec::Runtime& runtime() { return policy_runtime_->runtime(); }

  uintptr_t allocate_for_callback_pc(uint32_t size) {
    return policy_runtime_->allocate_from_callback(
      *sandbox_.get_sandbox_impl(), size);
  }

  UCharPtr copy_to_u(const char* src) {
    if (!src) return UCharPtr(nullptr);
    // Record original T pointee; only its bytes enter the sandbox.
    interspec::census::trusted_input("rsync_popt", "string_copy_source", src);

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
    interspec::DiagnosticEvent event(this, "copy_checked");

#ifdef INTERSPEC_RLBOX_SECURITY_COMPARATOR
    // Fault-only RLBox comparator. Confinement and T's bounded string copy
    // remain active; there is no InterSpec allocation table or type check.
    if (!sandbox_.is_pointer_in_sandbox_memory(raw))
      throw std::runtime_error("RLBox rejected outside-sandbox popt string");
    const uintptr_t address = sandbox_.get_sandbox_impl()->sandbox_address(raw);
    const size_t total = sandbox_.get_total_memory();
    if (address >= total)
      throw std::runtime_error("RLBox rejected invalid popt address");
    const size_t cap = std::min<size_t>(total - address, 1u << 20);
    const char* end = static_cast<const char*>(std::memchr(raw, '\0', cap));
    if (!end)
      throw std::runtime_error("RLBox rejected unterminated bounded popt string");
    const size_t bytes = end - raw + 1;
#elif defined(INTERSPEC_P8_MEASURE_NO_VALIDATION)
    /*
     * Measurement-only baseline. The sandbox, marshalling, typed allocation,
     * provenance, and workload remain identical; only the final Extended-SP3
     * acceptance check is bypassed. This build is never used by correctness
     * tests and deliberately trusts the known-valid benchmark workload.
     */
    const size_t bytes = std::strlen(raw) + 1;
#else
    size_t bytes = 0;
    const interspec::Sp3Mode sp3 = switches().sp3;
    if (sp3 == interspec::Sp3Mode::off) {
      // SP3 off: no pointer check. Tracking in U is unchanged; T uses the
      // pointer as returned.
      bytes = std::strlen(raw) + 1;
    } else {
      const uintptr_t sandbox_ptr =
        sandbox_.get_sandbox_impl()->sandbox_address(raw);
      event.runtime = &runtime();
      event.ptr = sandbox_ptr;
      event.expected_type = kTypeHashChar;
      size_t remaining = 0;
      const auto result = runtime().remaining_bytes(
        sandbox_ptr, kTypeHashChar, remaining);
      event.remaining = remaining;
      if (result == interspec::CheckResult::ok && remaining != 0)
        interspec::census::sandbox_result("rsync_popt", "checked_string_result", sandbox_ptr, true);
      if (result != interspec::CheckResult::ok || remaining == 0) {
        event.result = interspec::check_result_name(result);
        if (std::getenv("INTERSPEC_TRACE_DUMP")) runtime().dump_allocations();
        throw std::runtime_error(std::string("InterSpec rejected popt char pointer: ") +
                                 event.result);
      }

      const void* end = std::memchr(raw, '\0', remaining);
      if (!end) {
        event.result = "unterminated_string";
        throw std::runtime_error("InterSpec rejected unterminated popt string");
      }

      bytes = static_cast<const char*>(end) - raw + 1;
    }
#endif
    auto copy = std::make_unique<char[]>(bytes);
    std::memcpy(copy.get(), raw, bytes);
    event.requested = bytes;
    event.result = "copied";
    char* result_ptr = copy.get();
    trusted_strings_.push_back(std::move(copy));
    return result_ptr;
  }

  // Sandbox address of a pointer T placed in U, or 0 for null.
  uint32_t u_address(UCharPtr value) {
    char* raw = value.UNSAFE_unverified();
    if (!raw) return 0;
    return static_cast<uint32_t>(sandbox_.get_sandbox_impl()->sandbox_address(raw));
  }

  // True if [raw, raw + bytes) is U memory.
  bool in_u_memory(const void* raw, size_t bytes) {
    if (!raw || bytes == 0) return false;
    const char* first = static_cast<const char*>(raw);
    return sandbox_.is_pointer_in_sandbox_memory(first) &&
           sandbox_.is_pointer_in_sandbox_memory(first + (bytes - 1));
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
  std::unique_ptr<interspec::PolicyRuntime> policy_runtime_;
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
  int last_integer = 0;
  bool last_string_null = true;
  std::string last_string;
};

// String fields of one option as T placed them in U (sandbox addresses).
struct InstalledStrings {
  std::array<uint32_t, 3> address{};  // longName, descrip, argDescrip
};

struct TrustedContext {
  UPtr untrusted_context;
  UPtr untrusted_table;
  UPtr untrusted_argv;
  std::vector<SlotBinding> slots;
  std::vector<const char*> args_cache;
  // Option-table copy-out (SP2 off) writes U's changes into T's table.
  struct poptOption* trusted_options = nullptr;
  std::vector<InstalledStrings> installed;
};

// --- SP1 / SP2: selective copy of the poptOption table ----------------------
//
// Which fields cross the boundary comes from kPoptOptionFields, the field
// policy table of the interspec-artifact wrapper. SP1 on withholds the fields
// marked skip-copy-in from U. SP2 on drops U's changes to the fields marked
// skip-copy-out. With a switch off the wrapper copies that direction in full,
// as a wrapper without the policy would.
//
// `arg` is the one field U legitimately writes through. Its pointer never
// returns to T; values travel through the shadow slots (sync_slots).

using popt::rlbox::kFieldArgDescrip;
using popt::rlbox::kFieldArgInfo;
using popt::rlbox::kFieldDescrip;
using popt::rlbox::kFieldLongName;
using popt::rlbox::kFieldShortName;
using popt::rlbox::kFieldVal;
using popt::rlbox::kPoptOptionFields;

static bool copy_in_field(size_t field) {
  return !(switches().sp1 &&
           popt::rlbox::should_skip_copy_in(kPoptOptionFields[field].policy));
}

// A field that was withheld from U has nothing to copy back.
static bool copy_out_field(size_t field) {
  return copy_in_field(field) &&
         !(switches().sp2 &&
           popt::rlbox::should_skip_copy_out(kPoptOptionFields[field].policy));
}

// struct poptOption as U lays it out: 32-bit pointers on wasm32 and NaCl
// x86-32. Same layout as poptOption_wasm32 in the artifact wrapper.
struct PoptOptionU32 {
  uint32_t longName;
  uint8_t shortName;
  uint8_t padding[3];
  uint32_t argInfo;
  uint32_t arg;
  int32_t val;
  uint32_t descrip;
  uint32_t argDescrip;
};
static_assert(sizeof(PoptOptionU32) == 28, "unexpected ILP32 poptOption layout");

static void trace_binding(const char* operation, const SlotBinding& binding) {
  // The T destination is retained inside T; U receives a shadow slot.
  if (std::strcmp(operation, "bind") == 0)
    interspec::census::trusted_adapter_reference("rsync_popt", "shadow_destination", binding.trusted_address);
  if (!interspec::DiagnosticEvent::enabled()) return;
  std::fprintf(stderr, "INTERSPEC_BINDING event=%s slot=%u destination=%p kind=%s\n",
               operation, binding.index, binding.trusted_address,
               binding.kind == SlotKind::integer ? "integer" : "string");
  std::fflush(stderr);
}

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
  for (auto& binding : context.slots) {
    if (binding.kind == SlotKind::integer) {
      const int value = e.sandbox()
                          .invoke_sandbox_function(interspec_p4c_slot_get_int,
                                                   context.untrusted_table,
                                                   binding.index)
                          .UNSAFE_unverified();
      std::memcpy(binding.trusted_address, &value, sizeof(value));
      binding.last_integer = value;
    } else {
      auto value = e.sandbox().invoke_sandbox_function(
        interspec_p4c_slot_get_string,
        context.untrusted_table,
        binding.index);
      char* copy = e.copy_checked(value);
      std::memcpy(binding.trusted_address, &copy, sizeof(copy));
      binding.last_string_null = copy == nullptr;
      binding.last_string = copy ? copy : "";
    }
    trace_binding("copyback", binding);
  }
}

// Native popt observes changes T makes between parser calls through the shared
// option destinations. Refresh changed shadows before invoking sandboxed popt,
// otherwise copying every shadow back can erase T's handling of options like -a.
// All destination addresses and previous values remain private to T.
static void refresh_slots(TrustedContext& context) {
  Engine& e = engine();
  for (auto& binding : context.slots) {
    int ok = 1;
    if (binding.kind == SlotKind::integer) {
      int value = 0;
      std::memcpy(&value, binding.trusted_address, sizeof(value));
      if (value == binding.last_integer) continue;
      ok = e.sandbox().invoke_sandbox_function(interspec_p4c_slot_set_int,
        context.untrusted_table, binding.index, value).UNSAFE_unverified();
      binding.last_integer = value;
    } else {
      const char* value = nullptr;
      std::memcpy(&value, binding.trusted_address, sizeof(value));
      if ((value == nullptr) == binding.last_string_null &&
          (!value || binding.last_string == value)) continue;
      auto copy = e.copy_to_u(value);
      ok = e.sandbox().invoke_sandbox_function(interspec_p4c_slot_set_string,
        context.untrusted_table, binding.index, copy).UNSAFE_unverified();
      binding.last_string_null = value == nullptr;
      binding.last_string = value ? value : "";
    }
    if (!ok) throw std::runtime_error("failed to refresh popt shadow slot");
    trace_binding("refresh", binding);
  }
}

// SP2 off: copy the option table back as a struct copy would. Scalars are
// copied by value. A string is copied only if U replaced the pointer, and then
// through copy_checked, so the SP3 switch governs that pointer like any other.
// SP2 on: every table field is marked skip-copy-out and this does nothing.
static void copy_out_options(TrustedContext& context) {
  static const size_t kStringFields[3] = {kFieldLongName, kFieldDescrip,
                                          kFieldArgDescrip};
  const bool scalars[3] = {copy_out_field(kFieldShortName),
                           copy_out_field(kFieldArgInfo),
                           copy_out_field(kFieldVal)};
  const bool strings[3] = {copy_out_field(kStringFields[0]),
                           copy_out_field(kStringFields[1]),
                           copy_out_field(kStringFields[2])};
  if (!scalars[0] && !scalars[1] && !scalars[2] &&
      !strings[0] && !strings[1] && !strings[2])
    return;

  Engine& e = engine();
  const size_t count = context.installed.size();
  const size_t bytes = count * sizeof(PoptOptionU32);
  auto u_options = e.sandbox().invoke_sandbox_function(
    interspec_p4c_table_options, context.untrusted_table);
  const void* raw = u_options.UNSAFE_unverified();
  // U names the array. T reads only bytes that are U memory, into its own copy.
  if (!e.in_u_memory(raw, bytes))
    throw std::runtime_error("popt option table is not in U memory");
  std::vector<PoptOptionU32> snapshot(count);
  std::memcpy(snapshot.data(), raw, bytes);

  for (size_t i = 0; i < count; ++i) {
    struct poptOption& trusted = context.trusted_options[i];
    const PoptOptionU32& u = snapshot[i];
    if (scalars[0] && trusted.shortName != static_cast<char>(u.shortName))
      trusted.shortName = static_cast<char>(u.shortName);
    if (scalars[1] && static_cast<uint32_t>(trusted.argInfo) != u.argInfo)
      trusted.argInfo = u.argInfo;
    if (scalars[2] && trusted.val != u.val) trusted.val = u.val;

    const uint32_t u_strings[3] = {u.longName, u.descrip, u.argDescrip};
    const char** t_strings[3] = {&trusted.longName, &trusted.descrip,
                                 &trusted.argDescrip};
    for (uint32_t field = 0; field < 3; ++field) {
      if (!strings[field] ||
          u_strings[field] == context.installed[i].address[field])
        continue;
      auto value = e.sandbox().invoke_sandbox_function(
        interspec_p4c_option_string, context.untrusted_table,
        static_cast<uint32_t>(i), field);
      *t_strings[field] = e.copy_checked(value);
      context.installed[i].address[field] = e.u_address(value);
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
  switches();  // read (and, if asked, report) the configuration before any call
  auto context = std::make_unique<TrustedContext>();

  const uint32_t count = option_count(options);
  // popt takes the table as const, but a wrapper that copies the table back
  // (SP2 off) writes to the caller's object. Only differing values are written.
  context->trusted_options = const_cast<struct poptOption*>(options);
  context->installed.reserve(count);
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
    trace_binding("bind", context->slots.back());

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
      context->slots.back().last_integer = initial;
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
      context->slots.back().last_string_null = initial == nullptr;
      context->slots.back().last_string = initial ? initial : "";
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
    // SP1: fields U does not read are not copied in; U sees null.
    auto description = copy_in_field(kFieldDescrip)
                         ? e.copy_to_u(option.descrip) : UCharPtr(nullptr);
    auto arg_description = copy_in_field(kFieldArgDescrip)
                             ? e.copy_to_u(option.argDescrip) : UCharPtr(nullptr);
    context->installed.push_back({{e.u_address(long_name),
                                   e.u_address(description),
                                   e.u_address(arg_description)}});
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

#ifdef INTERSPEC_FAULT_TESTS
  // Policy-switch tests: the U-side PoC behavior fires inside context_new.
  if (const char* poc_setting = std::getenv("INTERSPEC_TEST_POC_FLAGS"))
    e.sandbox().invoke_sandbox_function(
      interspec_poc_set_flags, static_cast<int>(std::stoul(poc_setting)));
#endif

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

#ifdef INTERSPEC_FAULT_TESTS
  // Only the U fault selector changes. T's policy and checks stay identical.
  const char* mode_setting = std::getenv("INTERSPEC_TEST_FAULT");
  const char* target_setting = std::getenv("INTERSPEC_TEST_TARGET");
  const uint32_t mode = mode_setting ? static_cast<uint32_t>(std::stoul(mode_setting)) : 0;
  const uint32_t target = target_setting ? static_cast<uint32_t>(std::stoul(target_setting)) : 1;
  if (mode > 6 || target < 1 || target > 3)
    throw std::runtime_error("invalid test fault selector");
  e.sandbox().invoke_sandbox_function(interspec_test_set_fault, mode, target);
#endif

  copy_out_options(*context);
  return context;
}

[[noreturn]] static void bridge_failure() {
  const auto exception = std::current_exception();
  try {
    if (exception) std::rethrow_exception(exception);
    std::fprintf(stderr, "INTERSPEC_REJECT reason=bridge_invariant_failure\n");
  } catch (const std::exception& error) {
    std::fprintf(stderr, "INTERSPEC_REJECT reason=%s\n", error.what());
  } catch (...) {
    std::fprintf(stderr, "INTERSPEC_REJECT reason=unknown_exception\n");
  }
  std::fflush(stderr);
  std::abort();
}

}  // namespace

#ifdef INTERSPEC_FAULT_TESTS
// Test builds only. T scans all of U's memory for a byte string, so a test can
// state that a withheld T value is absent from U rather than merely unprinted.
extern "C" int interspec_test_sandbox_contains(const char* needle) {
  Sandbox& sandbox = engine().sandbox();
  const void* base = sandbox.get_memory_location();
  const size_t total = sandbox.get_total_memory();
  const size_t bytes = std::strlen(needle);
  if (!base || bytes == 0 || bytes > total) return 0;
  const char* begin = static_cast<const char*>(base);
  const char* end = begin + total;
  return std::search(begin, end, needle, needle + bytes) != end ? 1 : 0;
}
#endif

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
    refresh_slots(*context);
    const int result = engine().sandbox()
                         .invoke_sandbox_function(interspec_p4c_next,
                                                  context->untrusted_context)
                         .UNSAFE_unverified();
    sync_slots(*context);
    copy_out_options(*context);
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
