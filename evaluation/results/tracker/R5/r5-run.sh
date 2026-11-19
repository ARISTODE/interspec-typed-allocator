#!/usr/bin/env bash
# R5: run one prepared variant work directory. Usage: r5-run.sh NAME
cd /home/user/interspec-typed-allocator
echo "$1 start $(date -u +%FT%TZ)" >> /tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad/r5-out/steps.txt
CODEQL=/tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad/codeql-bundle/codeql/codeql COVERAGE_WORK=/tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad/r5-work-$1 COVERAGE_THREADS=4 COVERAGE_RAM_MB=10000 COVERAGE_MAX_DISK_CACHE_MB=6000 \
  bash scripts/run_coverage_analysis.sh /tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad/r5-out/$1 nginx_openssl:nginx_openssl_libs > /tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad/r5-out/$1.log 2>&1
echo "$1 exit=$? $(date -u +%FT%TZ)" >> /tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad/r5-out/steps.txt
