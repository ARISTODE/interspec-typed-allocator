#!/usr/bin/env bash
# After the third campaign: the R5 analysis runs that need the CPUs (not timing-sensitive).
S=/tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad
while pgrep -f "bash $S/campaign3.sh" > /dev/null; do python3 -c "import time; time.sleep(30)"; done
echo "campaign3 ended, DONE=$([ -e $S/camp3/DONE ] && echo yes || echo no) $(date -u +%FT%TZ)" > $S/chain3.log
# slot writes of the ten functions (depth 8 pack)
cp /home/user/interspec-typed-allocator/evaluation/coverage/queries/r5_slot_writes.ql $S/r5-work-d8/root/ql/queries/
mkdir -p $S/r5-out/slot-writes
echo "slot-writes start $(date -u +%FT%TZ)" >> $S/r5-out/steps.txt
(cd $S/r5-work-d8/root && timeout 14400 $S/codeql-bundle/codeql/codeql query run --threads 4 --ram 10000 --database db/nginx_openssl_libs \
   --output $S/r5-out/slot-writes/r5_slot_writes.bqrs ql/queries/r5_slot_writes.ql > $S/r5-out/slot-writes/run.log 2>&1 &&
 $S/codeql-bundle/codeql/codeql bqrs decode --format=csv --output $S/r5-out/slot-writes/r5_slot_writes.csv $S/r5-out/slot-writes/r5_slot_writes.bqrs >> $S/r5-out/slot-writes/run.log 2>&1)
echo "slot-writes exit=$? $(date -u +%FT%TZ)" >> $S/r5-out/steps.txt
for d in d10 d12; do timeout 21600 bash $S/r5-run.sh $d; echo "$d driver exit=$? $(date -u +%FT%TZ)" >> $S/chain3.log; done
touch $S/chain3.DONE
