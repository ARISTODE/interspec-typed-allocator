#include <stdint.h>
/* Separate translation unit, no LTO. The caller cannot replace the call body. */
uint32_t interspec_native_empty_call(uint32_t value) { return value + 1; }
