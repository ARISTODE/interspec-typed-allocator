/* Force-included into the Wasm build of libucl. WASI libc has no realpath.
 * libucl calls it only for file includes and for remembering the name of a
 * parsed file; the sandboxed workload parses memory buffers and has no
 * filesystem. The definition in ucl_u.c always fails. */
#ifndef INTERSPEC_UCL_WASI_COMPAT_H
#define INTERSPEC_UCL_WASI_COMPAT_H
char *realpath(const char *path, char *resolved_path);
#endif
