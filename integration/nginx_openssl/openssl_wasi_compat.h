/* Force-included when OpenSSL is compiled for WASI. crypto/uid.c asks whether
 * the process is set-uid; WASI libc has no user or group ids. The port's U
 * glue (tls_u.c) defines the four functions to return 0. */
#ifdef __wasm__
#include <sys/types.h>
uid_t getuid(void);
uid_t geteuid(void);
gid_t getgid(void);
gid_t getegid(void);
#endif
