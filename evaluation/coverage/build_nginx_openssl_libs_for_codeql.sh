#!/usr/bin/env bash
# CodeQL build command for the database nginx_openssl_libs (tracker item C2):
# nginx as in build_nginx_for_codeql.sh, with OpenSSL configured "no-apps", so
# that only libssl, libcrypto and the providers are compiled. In the database
# nginx, 6,691 of OpenSSL's 27,954 functions are its command-line program,
# tests and fuzzers (evaluation/results/tracker/C2/09: openssl-by-directory-nginx.csv),
# which nginx does not link.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root/benchmarks/nginx"
rm -rf objs
./auto/configure --without-pcre2 --with-pcre="$root/benchmarks/pcre" \
  --with-http_ssl_module --with-openssl="$root/benchmarks/openssl" \
  --with-openssl-opt=no-apps --without-http_gzip_module
make -j"$(nproc)"
