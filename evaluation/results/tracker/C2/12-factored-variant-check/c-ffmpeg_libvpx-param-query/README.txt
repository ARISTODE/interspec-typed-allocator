ffmpeg/libvpx on database ffmpeg_vpx_only, first pointer query (param).

pointer_slots.param.factored.bqrs: output with paper_counting_rule_factored
  (run ../../13-…, 22:16:52 to 23:11:32 UTC on 2026-11-14, 55 minutes).
../../11-ffmpeg_libvpx-regrouped-stopped/pointer_slots.param.bqrs: output with
  paper_counting_rule_regrouped (72 minutes).

Both decoded with `codeql bqrs decode --format=csv` and sorted with `sort`:
580 rows and a header each, same SHA-256 (sha256.txt). The two .bqrs files
differ as bytes because the query has no "order by" and the rows come out in a
different order.
