#!/usr/bin/env bash
# Second pass of the campaign for the nginx steps. The first pass built nginx into the
# build script's default directory (the script takes the directory from INTERSPEC_NGINX_WORK,
# not from its argument), so p3 failed at once and the steps that depend on it were skipped.
# /tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad/camp-nginx-work now links to that build; campaign.sh skips every finished step.
S=/tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad
while pgrep -f "bash $S/campaign.sh" > /dev/null; do python3 -c "import time; time.sleep(20)"; done
[ -e $S/camp/DONE ] || { echo "first pass ended without DONE" > $S/camp-chain.log; exit 1; }
echo "note second pass for nginx: p3 failed because the build was in /tmp/interspec-nginx-deployment; linked as camp-nginx-work $(date -u +%FT%TZ)" >> $S/camp/steps.txt
rm $S/camp/DONE
cd /home/user; bash $S/campaign.sh > $S/campaign-pass2.log 2>&1
echo "second pass exit=$? $(date -u +%FT%TZ)" > $S/camp-chain.log
