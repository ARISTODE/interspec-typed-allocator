#pragma once

#include <stdint.h>

#include "native_client/src/trusted/service_runtime/include/bits/nacl_syscalls.h"
#include "native_client/src/trusted/service_runtime/nacl_config.h"
#include "native_client/src/trusted/service_runtime/sel_rt.h"

/*
 * P7a invokes the existing NaCl callback syscall directly at the analyzed
 * allocation expression instead of first calling a reusable U helper.  The
 * trusted service runtime records the real sandbox program counter at syscall
 * entry, so replaying the allocator callback from another U instruction does
 * not acquire the allocation site's authority.
 */
extern uint32_t interspec_site_alloc_slot;

typedef int32_t (*interspec_site_callback_syscall_t)(uint32_t,
                                                     nacl_reg_t*,
                                                     uintptr_t);

#define INTERSPEC_SITE_ALLOC(_size)                                             \
  ({                                                                            \
    uint64_t __interspec_ret = 0;                                               \
    nacl_reg_t __interspec_regs[6] = {0, 0, 0, 0, 0, 0};                       \
    __interspec_regs[0] = (nacl_reg_t)(uint32_t)(_size);                       \
    ((interspec_site_callback_syscall_t)                                        \
       NACL_SYSCALL_ADDR(NACL_sys_callback))(                                   \
      interspec_site_alloc_slot,                                                \
      __interspec_regs,                                                         \
      (uintptr_t)&__interspec_ret);                                             \
    (uint32_t)__interspec_ret;                                                  \
  })
