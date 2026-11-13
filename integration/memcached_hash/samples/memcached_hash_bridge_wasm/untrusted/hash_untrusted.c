#include <stddef.h>
#include <stdint.h>
#define XXH_INLINE_ALL
#include "../../benchmarks/memcached/xxhash.h"

uint64_t
hash_untrusted(const char* data, uint32_t len)
{
  return XXH3_64bits(data, (size_t)len);
}
