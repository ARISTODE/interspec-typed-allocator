#!/usr/bin/env bash
# The other nine boundaries with variant paper_counting_rule_sp3_opacity, after the nginx/openssl test run.
S=/tmp/claude-0/-home-user/875e1a03-82ac-5cc7-996e-5a0301286f02/scratchpad
while pgrep -f "sp3op-run.sh nginx_openssl" > /dev/null; do python3 -c "import time; time.sleep(30)"; done
P=$S/coverage-work-paper-rule/root/reports
for spec in memcached_bipbuffer:memcached memcached_hash:memcached rsync_popt:rsync_popt ucl_libucl:ucl_libucl \
            yaml_libyaml:yaml_libyaml zip_libzip:zip_libzip magick_libpng:magick_libpng nginx_libpcre:nginx_pcre; do
  b=${spec%%:*}; db=${spec#*:}
  bash $S/sp3op-run.sh $b $db $P/$b
done
bash $S/sp3op-run.sh ffmpeg_libvpx ffmpeg_vpx_only $S/coverage-work-inlined-b/root/reports/ffmpeg_libvpx
touch $S/sp3op.DONE
