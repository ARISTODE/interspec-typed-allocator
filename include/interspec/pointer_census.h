#pragma once

// Optional observations at explicit application boundary sites. Unknown is
// intentionally different from heap. T pointers are copied or tokenized;
// their numerical addresses do not pass into the sandbox.

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#if defined(__linux__)
#include <link.h>
#include <pthread.h>
#include <unistd.h>
#endif

namespace interspec {
namespace census {

inline bool enabled() {
  static const bool value = [] {
    const char* env = std::getenv("INTERSPEC_POINTER_CENSUS");
    return env && std::strcmp(env, "1") == 0;
  }();
  return value;
}

inline const char* host_storage(const void* ptr) {
  if (!ptr) return "null";
#if defined(__linux__)
  const uintptr_t address = reinterpret_cast<uintptr_t>(ptr);
  pthread_attr_t attr;
  if (pthread_getattr_np(pthread_self(), &attr) == 0) {
    void* base = nullptr;
    size_t size = 0;
    const bool valid = pthread_attr_getstack(&attr, &base, &size) == 0;
    pthread_attr_destroy(&attr);
    if (valid) {
      const uintptr_t start = reinterpret_cast<uintptr_t>(base);
      if (address >= start && address - start < size) return "t_stack";
    }
  }

  struct ImageLookup { uintptr_t address; bool found; } lookup{address, false};
  dl_iterate_phdr([](struct dl_phdr_info* info, size_t, void* opaque) {
    auto* lookup = static_cast<ImageLookup*>(opaque);
    for (int i = 0; i < info->dlpi_phnum; ++i) {
      const auto& segment = info->dlpi_phdr[i];
      if (segment.p_type != PT_LOAD || !(segment.p_flags & PF_R) ||
          (segment.p_flags & PF_X)) continue;
      const uintptr_t base = static_cast<uintptr_t>(info->dlpi_addr);
      const uintptr_t offset = static_cast<uintptr_t>(segment.p_vaddr);
      if (offset > UINTPTR_MAX - base) continue;
      const uintptr_t start = base + offset;
      if (lookup->address >= start &&
          lookup->address - start < segment.p_memsz) {
        lookup->found = true;
        return 1;
      }
    }
    return 0;
  }, &lookup);
  if (lookup.found) return "t_image_static";
#endif
  return "unknown";
}

inline void emit(const char* boundary, const char* direction,
                 const char* site, const char* storage,
                 uintptr_t address, const char* result = "observed") {
  if (!enabled()) return;
#if defined(__linux__)
  // One kernel write prevents record interleaving between nginx workers.
  // stdio locks synchronize threads, not independently forked processes.
  char line[384];
  const int count = std::snprintf(
      line, sizeof(line),
      "INTERSPEC_POINTER_CENSUS schema=1 pid=%ld boundary=%s direction=%s "
      "site=%s storage=%s address=0x%zx result=%s\n",
      static_cast<long>(getpid()), boundary, direction, site, storage,
      static_cast<size_t>(address), result);
  if (count > 0 && static_cast<size_t>(count) < sizeof(line)) {
    (void)::write(STDERR_FILENO, line, static_cast<size_t>(count));
  }
#else
  std::fprintf(stderr,
               "INTERSPEC_POINTER_CENSUS schema=1 pid=0 boundary=%s direction=%s "
               "site=%s storage=%s address=0x%zx result=%s\n",
               boundary, direction, site, storage,
               static_cast<size_t>(address), result);
#endif
}

inline void trusted_input(const char* boundary, const char* site,
                          const void* address) {
  if (!enabled()) return;
  emit(boundary, "t_to_u", site, host_storage(address),
       reinterpret_cast<uintptr_t>(address));
}

inline void trusted_adapter_reference(const char* boundary, const char* site,
                                      const void* address) {
  if (!enabled()) return;
  emit(boundary, "t_adapter_only", site, host_storage(address),
       reinterpret_cast<uintptr_t>(address));
}

inline void sandbox_result(const char* boundary, const char* site,
                           uintptr_t address, bool tracked_live) {
  emit(boundary, "u_to_t", site,
       tracked_live ? "u_tracked_heap" : "u_unclassified",
       address, tracked_live ? "accepted" : "rejected_or_untracked");
}

}  // namespace census
}  // namespace interspec

