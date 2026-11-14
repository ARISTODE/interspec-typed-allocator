#!/usr/bin/env bash
# CodeQL build command for the database nginx_pcre (tracker item C2): nginx
# and PCRE 8.45 as in build_nginx_for_codeql.sh; OpenSSL was built by
# prepare_nginx_pcre_for_codeql.sh and must not be compiled here.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root/benchmarks/nginx"
make -j"$(nproc)"
