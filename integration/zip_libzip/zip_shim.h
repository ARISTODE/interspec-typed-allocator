#pragma once

#include <zip.h>

#ifdef __cplusplus
extern "C" {
#endif

// Performs the representative operation for the microbenchmark:
// - zip_stat_index
// - zip_get_name
// and returns size + both name pointers.
//
// Notes:
// - `out_name_*` point into libzip-managed memory (valid until archive close).
// - The host validates these pointers (SP3) before any host-side dereference.
int ziplib_stat_and_get_names(zip_t* za,
                              zip_uint64_t idx,
                              zip_uint64_t* out_size,
                              const char** out_name_direct,
                              const char** out_name_stat);

#ifdef __cplusplus
}
#endif
