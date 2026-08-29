#ifndef INTERSPEC_POLICY_RUNTIME_H_INCLUDED
#define INTERSPEC_POLICY_RUNTIME_H_INCLUDED

#include "interspec/runtime.h"

#include <cstddef>
#include <cstdint>
#include <utility>

namespace interspec {

/*
 * P7b common binding between a generated InterSpec policy and a sandbox
 * backend.  Application bridges should not need to duplicate type/site
 * registration or callback-PC provenance lookup.
 *
 * The class intentionally does not depend on RLBox headers.  A sandbox backend
 * only needs to provide the small interface used by initialize_from_sandbox()
 * and allocate_from_callback():
 *
 *   uintptr_t lookup_symbol_address(const char*);
 *   uintptr_t callback_program_counter() const;
 *   uintptr_t callback_new_program_counter() const;
 *
 * This keeps generated policy/runtime logic reusable while leaving ABI and
 * application marshalling outside the trusted allocation mechanism.
 */
class PolicyRuntime {
 public:
  PolicyRuntime(uintptr_t arena_base, size_t arena_size)
      : runtime_(arena_base, arena_size) {}

  Runtime& runtime() { return runtime_; }
  const Runtime& runtime() const { return runtime_; }

  template <typename RegisterTypes, typename RegisterSites, typename Resolver>
  bool initialize(RegisterTypes&& register_types,
                  RegisterSites&& register_sites,
                  Resolver&& resolve) {
    if (!std::forward<RegisterTypes>(register_types)(runtime_)) return false;
    return std::forward<RegisterSites>(register_sites)(
        runtime_, std::forward<Resolver>(resolve));
  }

  template <typename SandboxImpl, typename RegisterTypes, typename RegisterSites>
  bool initialize_from_sandbox(SandboxImpl& impl,
                               RegisterTypes&& register_types,
                               RegisterSites&& register_sites) {
    auto resolve = [&impl](const char* name) -> uintptr_t {
      return impl.lookup_symbol_address(name);
    };
    return initialize(std::forward<RegisterTypes>(register_types),
                      std::forward<RegisterSites>(register_sites),
                      resolve);
  }

  template <typename SandboxImpl>
  uintptr_t allocate_from_callback(SandboxImpl& impl, size_t size) {
    const uintptr_t pc = impl.callback_program_counter();
    uintptr_t result = runtime_.allocate_from_pc(size, pc);
    if (result) return result;

    /*
     * Some backend revisions expose both the current and post-syscall program
     * counters.  P7a's pinned backend normalizes callback_program_counter() to
     * the return PC, but retaining this fail-closed fallback keeps the helper
     * usable with compatible backends that expose the two values separately.
     */
    const uintptr_t next_pc = impl.callback_new_program_counter();
    if (next_pc && next_pc != pc)
      result = runtime_.allocate_from_pc(size, next_pc);
    return result;
  }

 private:
  Runtime runtime_;
};

}  // namespace interspec

#endif  // INTERSPEC_POLICY_RUNTIME_H_INCLUDED
