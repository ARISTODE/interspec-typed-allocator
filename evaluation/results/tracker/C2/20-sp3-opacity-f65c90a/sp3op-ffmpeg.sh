#!/usr/bin/env bash
S=/tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad
bash $S/sp3op-run.sh ffmpeg_libvpx ffmpeg_vpx_only $S/coverage-work-inlined-b/root/reports/ffmpeg_libvpx
touch $S/sp3op-ffmpeg.DONE
