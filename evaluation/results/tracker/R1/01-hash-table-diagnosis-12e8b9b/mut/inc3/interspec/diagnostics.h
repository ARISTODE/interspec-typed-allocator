#ifndef INTERSPEC_DIAGNOSTICS_H_INCLUDED
#define INTERSPEC_DIAGNOSTICS_H_INCLUDED

#include <cstddef>
#include <cstdint>
#ifdef INTERSPEC_ENABLE_TRACE
#include <atomic>
#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <thread>
#if defined(_WIN32)
#include <process.h>
#else
#include <unistd.h>
#endif
#endif

namespace interspec {

// Trusted diagnostics only. No user memory is read by this record or its sink.
// Declare before the runtime lock so destruction emits after unlocking.
struct DiagnosticEvent {
  const void* runtime;
  const char* event;
  uintptr_t ptr = 0, base = 0, replacement = 0;
  size_t size = 0, requested = 0, offset = 0, remaining = 0;
  uint64_t actual_type = 0, expected_type = 0;
  uint32_t site = 0;
  const char* result = "failed";

  DiagnosticEvent(const void* owner, const char* name)
      : runtime(owner), event(name) {}

  static bool enabled() noexcept {
#ifdef INTERSPEC_ENABLE_TRACE
    static const bool value = [] {
      const char* setting = std::getenv("INTERSPEC_TRACE");
      return setting && setting[0] == '1' && setting[1] == '\0';
    }();
    return value;
#else
    return false;
#endif
  }

  ~DiagnosticEvent() noexcept {
#ifdef INTERSPEC_ENABLE_TRACE
    if (!enabled()) return;
    static std::atomic<uint64_t> sequence{0};
#if defined(_WIN32)
    const long process = static_cast<long>(::_getpid());
#else
    const long process = static_cast<long>(::getpid());
#endif
    std::fprintf(stderr,
      "INTERSPEC seq=%" PRIu64 " pid=%ld runtime=%p thread=%zu event=%s"
      " ptr=0x%" PRIxPTR " base=0x%" PRIxPTR " size=%zu site=%u"
      " actual_type=0x%" PRIx64 " expected_type=0x%" PRIx64
      " requested=%zu offset=%zu remaining=%zu replacement=0x%" PRIxPTR
      " result=%s\n",
      ++sequence, process, runtime, std::hash<std::thread::id>{}(std::this_thread::get_id()),
      event, ptr, base, size, site, actual_type, expected_type,
      requested, offset, remaining, replacement, result);
    std::fflush(stderr);
#endif
  }
};

}  // namespace interspec
#endif
