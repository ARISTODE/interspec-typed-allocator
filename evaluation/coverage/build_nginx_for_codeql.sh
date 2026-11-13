#!/usr/bin/env bash
# CodeQL build command for nginx with PCRE 8.45 and OpenSSL built from source
# (tracker item C1). nginx's own build compiles both libraries.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root/benchmarks/nginx"
./auto/configure --without-pcre2 --with-pcre="$root/benchmarks/pcre" \
  --with-http_ssl_module --with-openssl="$root/benchmarks/openssl" \
  --without-http_gzip_module
make -j"$(nproc)"
