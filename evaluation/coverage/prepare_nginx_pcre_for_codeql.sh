#!/usr/bin/env bash
# Untraced preparation of the database nginx_pcre (tracker item C2): the same
# nginx configuration as the database nginx, with OpenSSL built here, before
# CodeQL starts tracing, so that its sources are not extracted. nginx and PCRE
# are cleaned so that the traced build compiles both.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root/benchmarks/nginx"
rm -rf objs
(cd "$root/benchmarks/pcre" && { [[ ! -f Makefile ]] || make distclean >/dev/null 2>&1 || true; })
./auto/configure --without-pcre2 --with-pcre="$root/benchmarks/pcre" \
  --with-http_ssl_module --with-openssl="$root/benchmarks/openssl" \
  --without-http_gzip_module
make -f objs/Makefile "$root/benchmarks/openssl/.openssl/include/openssl/ssl.h"
# Newer than objs/Makefile, so the traced make does not build OpenSSL again.
touch "$root/benchmarks/openssl/.openssl/include/openssl/ssl.h"
