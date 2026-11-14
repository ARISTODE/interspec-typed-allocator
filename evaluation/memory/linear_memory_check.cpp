// Validation of the sandbox heap measurement of tools/measure_memory_cost.py
// (tracker item P9). The tool reads the size of a sandbox's linear memory from
// /proc/PID/smaps. This program reports the size RLBox itself gives
// (get_total_memory) so the two can be compared, before and after the sandbox
// heap grows. Built against the module of the memcached/hash port.
//
// Protocol on stdout/stdin: prints "TOTAL_MEMORY <bytes>", waits for a line,
// allocates 96 MiB inside the sandbox, prints "TOTAL_MEMORY <bytes>" again and
// waits for a line.
#define RLBOX_USE_EXCEPTIONS
#define RLBOX_USE_STATIC_CALLS() rlbox_wasm2c_sandbox_lookup_symbol
#define RLBOX_WASM2C_MODULE_NAME glue__lib__wasm2c
#include "glue_lib_wasm2c.h"
#include "rlbox.hpp"
#include "rlbox_wasm2c_sandbox.hpp"

#include <cstdio>
#include <cstring>

int main() {
  rlbox::rlbox_sandbox<rlbox::rlbox_wasm2c_sandbox> sandbox;
  if (!sandbox.create_sandbox()) return 1;
  char line[16];
  std::printf("TOTAL_MEMORY %zu\n", static_cast<size_t>(sandbox.get_total_memory()));
  std::fflush(stdout);
  if (!std::fgets(line, sizeof line, stdin)) return 1;
  const uint32_t bytes = 96u << 20;
  auto block = sandbox.malloc_in_sandbox<char>(bytes);
  char* raw = block.unverified_safe_pointer_because(bytes, "validation program");
  if (!raw) return 1;
  std::memset(raw, 1, bytes / 2);  // touch half, so resident and committed differ
  std::printf("TOTAL_MEMORY %zu\n", static_cast<size_t>(sandbox.get_total_memory()));
  std::fflush(stdout);
  if (!std::fgets(line, sizeof line, stdin)) return 1;
  sandbox.destroy_sandbox();
  return 0;
}
