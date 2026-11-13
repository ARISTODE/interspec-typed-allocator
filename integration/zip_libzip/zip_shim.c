#include "zip_shim.h"

int ziplib_stat_and_get_names(zip_t* za,
                              zip_uint64_t idx,
                              zip_uint64_t* out_size,
                              const char** out_name_direct,
                              const char** out_name_stat)
{
  if (!za || !out_size || !out_name_direct || !out_name_stat) {
    return -1;
  }

  zip_stat_t st;
  zip_stat_init(&st);
  if (zip_stat_index(za, idx, 0, &st) != 0) {
    *out_size = 0;
    *out_name_direct = NULL;
    *out_name_stat = NULL;
    return -2;
  }

  *out_size = st.size;
  *out_name_direct = zip_get_name(za, idx, 0);
  *out_name_stat = st.name;
  return 0;
}
