#pragma once

#include <sys/types.h>

uid_t getuid(void);
uid_t geteuid(void);
gid_t getgid(void);
gid_t getegid(void);
int execvp(const char* file, char* const argv[]);
