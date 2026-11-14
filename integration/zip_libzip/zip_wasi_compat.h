/* Force-included when libzip is compiled for WASI. libzip's file-backed source
 * calls chmod() when it writes an archive to disk; WASI libc has no chmod.
 * The port only opens archives from a memory buffer, read-only, so the call
 * is never reached; zip_u.c defines a stub that fails. */
#ifdef __wasm__
#include <sys/types.h>
int chmod(const char *path, mode_t mode);
#endif
