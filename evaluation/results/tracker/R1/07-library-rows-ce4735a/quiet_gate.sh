#!/usr/bin/env bash
# quiet_gate.sh OUT [report]: waits until the machine is quiet (criterion fixed on 2026-11-18, tracker Log),
# appending every check to OUT. Exit 0 when quiet, 1 after 8 hours of waiting. With "report": one check, no waiting.
S=/tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad
cd /home/user/interspec-typed-allocator || exit 1
check() { INTERSPEC_SP1=0 INTERSPEC_SP2=0 INTERSPEC_SP3=1 python3 tools/machine_quiet_check.py --cpu 0 --runs 10 --median-max 0.128 --slow 0.145 --slow-allowed 1 \
  -- $S/calib/yaml-rlbox-bench-69cc6e1-unaligned rlbox_only $S/calib/document-1m.yaml 12 >> "$1" 2>&1; }
if [ "$2" = report ]; then check "$1"; exit 0; fi
for i in $(seq 1 80); do python3 -c "import sys; sys.exit(0 if float(open('/proc/loadavg').read().split()[0]) < 0.30 else 1)" && break; python3 -c "import time; time.sleep(15)"; done
for i in $(seq 1 160); do check "$1" && exit 0; python3 -c "import time; time.sleep(170)"; done
exit 1
