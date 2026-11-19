#!/usr/bin/env bash
# After the library re-measurement (campaign3c.sh): the R5 analysis runs, which need the CPUs.
S=/tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad
while pgrep -f "bash $S/campaign3c.sh" > /dev/null; do python3 -c "import time; time.sleep(30)"; done
echo "campaign3c ended, DONE=$([ -e $S/camp3c/DONE ] && echo yes || echo no) $(date -u +%FT%TZ)" >> $S/chain5.log
[ -e $S/camp3c/DONE ] || { echo "campaign3c did not finish; R5 runs not started" >> $S/chain5.log; exit 1; }
cd $S/r5-work-d8/root && { echo "slot-writes-2 start $(date -u +%FT%TZ)" >> $S/r5-out/steps.txt
  timeout 14400 python3 $S/r5-slot.py $S/r5-out/slot-writes-2 $S/codeql-bundle/codeql/codeql
  echo "slot-writes-2 exit=$? $(date -u +%FT%TZ)" >> $S/r5-out/steps.txt; }
for d in d10 d12; do timeout 21600 bash $S/r5-run.sh $d; echo "$d driver exit=$? $(date -u +%FT%TZ)" >> $S/chain5.log; done
touch $S/chain5.DONE
