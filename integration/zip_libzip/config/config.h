#ifndef HAD_CONFIG_H
#define HAD_CONFIG_H

#ifndef _HAD_ZIPCONF_H
#include "zipconf.h"
#endif

// Minimal config for wasm32-wasi (avoid optional OS/crypto backends).
#define HAVE_STDBOOL_H 1
#define HAVE_STRINGS_H 1
#define HAVE_UNISTD_H 1

#define HAVE_STRCASECMP 1
#define HAVE_STRDUP 1
#define HAVE_SNPRINTF 1
#define HAVE_STRTOLL 1
#define HAVE_STRTOULL 1

// WASI libc provides ftello/fseeko; define these to avoid compat.h macro
// collisions with stdio.h declarations.
#define HAVE_FSEEKO 1
#define HAVE_FTELLO 1

// The artifact fixes this at 4 for wasm32; the native reference build of the
// port uses the same file, so the compiler's value is used instead.
#define SIZEOF_SIZE_T __SIZEOF_SIZE_T__
#define SIZEOF_OFF_T 8

#define PACKAGE "libzip"
#define VERSION "1.11.4"

#endif /* HAD_CONFIG_H */
