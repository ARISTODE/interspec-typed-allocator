#include "p9b_wasi_compat.h"

#include <errno.h>

uid_t getuid(void) { return 0; }
uid_t geteuid(void) { return 0; }
gid_t getgid(void) { return 0; }
gid_t getegid(void) { return 0; }

int execvp(const char* file, char* const argv[])
{
  (void)file;
  (void)argv;
  errno = ENOSYS;
  return -1;
}
