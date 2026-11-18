# Numbers of the performance subsection

## Complete application

- measurements: 7; range includes zero: 7 (medians -0.5 to +3.7); whole range below zero: 0 (); whole range above zero: 0 ()
- geometric mean of the 7 medians: +1.07%
- instruction differences where counted: rsync/popt 194\,MiB file sync +0.00%, yaml/libyaml 1\,MiB document -0.08%

- memcached/bipbuffer, 8 clients, no log watcher: native 648.056, RLBox-only 611.941, InterSpec 608.130 [Kops/s]; +0.2% (-8.3 to +9.5)
- memcached/bipbuffer, 1 client, log watcher: native 25.473, RLBox-only 25.224, InterSpec 24.603 [Kops/s]; +3.4% (-5.7 to +10.7)
- memcached/bipbuffer, 2 clients, log watcher: native 83.928, RLBox-only 83.447, InterSpec 80.386 [Kops/s]; +3.7% (-2.7 to +9.2)
- nginx/libpcre, wrk, 4 threads: native 71.660, RLBox-only 57.503, InterSpec 59.382 [Kreq/s]; -0.5% (-8.6 to +9.3)
- nginx/libpcre, wrk, 8 threads: native 69.058, RLBox-only 56.034, InterSpec 54.415 [Kreq/s]; +0.5% (-24.4 to +20.4)
- rsync/popt, 194\,MiB file sync: native 1.411, RLBox-only 1.407, InterSpec 1.421 [Runtime (s)]; -0.2% (-6.2 to +8.9)
- yaml/libyaml, 1\,MiB document: native 10.141, RLBox-only 16.375, InterSpec 16.639 [Time per parse (ms)]; +0.5% (-2.6 to +5.1)

## Library workload

- measurements: 8; range includes zero: 6 (medians -2.7 to +5.2); whole range below zero: 1 (memcached/hash Hash function); whole range above zero: 1 (zip/libzip Metadata queries)
- geometric mean of the 8 medians: -1.00%
- instruction differences where counted: ffmpeg/libvpx VP8 encode and decode -0.02%, magick/libpng PNG decode and encode -0.03%, memcached/hash Hash function -19.33%, memcached/hash Hash table -3.59%, nginx/openssl TLS~1.3 request and response -0.26%, ucl/libucl Parse, look up, emit -1.68%, zip/libzip Metadata queries +10.50%, zip/libzip Archive listing, 1,000 entries +4.26%

- ffmpeg/libvpx, VP8 encode and decode: native 9.334, RLBox-only 9.915, InterSpec 10.131 [Time per frame (ms)]; -1.1% (-3.6 to +6.7)
- magick/libpng, PNG decode and encode: native 192.496, RLBox-only 192.627, InterSpec 193.731 [Time per image (\textmu{}s)]; -0.6% (-7.0 to +4.5)
- memcached/hash, Hash function: native 9.012, RLBox-only 23.078, InterSpec 20.049 [Time per call (ns)]; -13.3% (-14.9 to -9.0)
- memcached/hash, Hash table: native 183.621, RLBox-only 234.017, InterSpec 232.370 [Time per operation (ns)]; -2.7% (-6.2 to +0.4)
- nginx/openssl, TLS~1.3 request and response: native 17.493, RLBox-only 104.203, InterSpec 103.517 [Time per exchange (\textmu{}s)]; -0.9% (-3.1 to +3.2)
- ucl/libucl, Parse, look up, emit: native 4.899, RLBox-only 6.101, InterSpec 6.160 [Time per iteration (\textmu{}s)]; +0.2% (-3.3 to +5.4)
- zip/libzip, Metadata queries: native 86.473, RLBox-only 117.585, InterSpec 126.797 [Time per query (ns)]; +6.3% (+2.5 to +10.2)
- zip/libzip, Archive listing, 1,000 entries: native 633.135, RLBox-only 554.401, InterSpec 572.906 [Time per listing (\textmu{}s)]; +5.2% (-0.6 to +9.4)

- geometric mean of all 15 medians: -0.04%

## Per-policy table

- rows: 13; rows whose combined cost has its whole range on one side of zero: 3 (memcached/hash, function, memcached/hash, table, zip/libzip, queries)

- memcached/bipbuffer: sp1 +0.6% (-7.0 to +4.2); sp2 +0.3% (-4.0 to +5.1); sp3 +2.8% (-3.5 to +6.0); all-on +2.0% (-3.2 to +4.8); all on against RLBox-only +2.3% (-2.4 to +3.6); all off against RLBox-only -0.6% (-4.1 to +5.7)
- nginx/libpcre: sp1 -0.1% (-12.4 to +6.6); sp2 -3.4% (-17.7 to +12.4); sp3 +0.5% (-7.4 to +13.8); all-on -3.7% (-15.4 to +8.8); all on against RLBox-only +1.7% (-14.0 to +9.6); all off against RLBox-only +3.8% (-8.4 to +11.2)
- rsync/popt, option parsing: sp1 +0.7% (-3.2 to +4.8); sp2 -0.2% (-2.6 to +3.9); sp3 +0.3% (-2.2 to +3.4); all-on +0.3% (-2.1 to +3.6); all on against RLBox-only -0.5% (-3.7 to +3.2); all off against RLBox-only -0.3% (-5.7 to +1.7)
- rsync/popt, file sync: sp1 -0.4% (-2.2 to +2.1); sp2 +0.8% (-1.6 to +3.6); sp3 +0.1% (-1.6 to +2.6); all-on +0.5% (-1.6 to +2.2); all on against RLBox-only -0.2% (-2.1 to +4.4); all off against RLBox-only -0.5% (-2.5 to +2.1)
- yaml/libyaml: sp1 no such policy; sp2 +0.6% (-4.9 to +6.6); sp3 -0.3% (-6.5 to +9.0); all-on +1.4% (-4.3 to +9.5); all on against RLBox-only +0.9% (-5.4 to +7.4); all off against RLBox-only -1.9% (-6.1 to +12.2)
- ffmpeg/libvpx: sp1 -0.6% (-7.1 to +7.7); sp2 -0.6% (-10.1 to +5.5); sp3 -1.6% (-5.0 to +5.1); all-on -3.3% (-11.2 to +7.6); all on against RLBox-only -1.6% (-6.4 to +4.2); all off against RLBox-only +1.6% (-6.2 to +11.4)
- magick/libpng: sp1 -2.6% (-5.2 to +8.9); sp2 -0.5% (-5.7 to +2.4); sp3 -1.4% (-9.3 to +10.8); all-on -0.3% (-5.2 to +4.3); all on against RLBox-only -0.7% (-5.8 to +7.3); all off against RLBox-only +0.7% (-4.8 to +6.7)
- memcached/hash, function: sp1 -0.3% (-4.8 to +7.8); sp2 -7.5% (-12.0 to -4.6); sp3 -0.3% (-5.5 to +6.3); all-on -7.4% (-13.9 to -3.3); all on against RLBox-only -12.4% (-20.0 to -6.7); all off against RLBox-only -4.9% (-13.5 to +1.1)
- memcached/hash, table: sp1 -5.7% (-9.9 to -4.0); sp2 -1.5% (-5.5 to +0.8); sp3 +4.0% (+1.4 to +7.9); all-on -3.9% (-8.1 to -0.3); all on against RLBox-only -2.1% (-7.4 to -0.2); all off against RLBox-only +1.5% (-2.7 to +3.4)
- nginx/openssl: sp1 +1.0% (-4.0 to +2.5); sp2 -0.3% (-4.3 to +2.7); sp3 -1.2% (-6.6 to +5.4); all-on -0.8% (-4.1 to +8.1); all on against RLBox-only -0.1% (-3.7 to +8.7); all off against RLBox-only +0.5% (-2.7 to +3.9)
- ucl/libucl: sp1 +0.7% (-6.8 to +9.0); sp2 +1.9% (-4.3 to +7.4); sp3 -0.6% (-6.1 to +15.6); all-on -0.7% (-9.0 to +7.7); all on against RLBox-only -0.4% (-11.1 to +10.7); all off against RLBox-only +0.0% (-7.4 to +8.9)
- zip/libzip, queries: sp1 -0.3% (-4.7 to +3.6); sp2 +0.7% (-3.5 to +6.4); sp3 +5.4% (-2.5 to +11.6); all-on +5.4% (+0.8 to +13.2); all on against RLBox-only +8.1% (+2.8 to +15.4); all off against RLBox-only +2.1% (-3.5 to +6.9)
- zip/libzip, listing: sp1 +0.3% (-6.9 to +6.2); sp2 -1.2% (-4.5 to +6.8); sp3 +2.8% (-3.3 to +6.5); all-on +0.6% (-5.3 to +8.6); all on against RLBox-only +2.7% (-2.0 to +14.3); all off against RLBox-only +3.7% (-1.6 to +7.3)

## Details

- memcached balanced_1c: Kops/s native 178.3, RLBox-only 176.5, InterSpec 177.8; InterSpec against RLBox-only +0.4% (-6.8 to +5.2); RLBox-only against native +1.4%
- memcached balanced_8c: Kops/s native 648.1, RLBox-only 611.9, InterSpec 608.1; InterSpec against RLBox-only +0.2% (-8.3 to +9.5); RLBox-only against native +5.6%
- memcached read_heavy_1k: Kops/s native 906.6, RLBox-only 816.7, InterSpec 803.6; InterSpec against RLBox-only +0.6% (-4.6 to +8.2); RLBox-only against native +9.5%
- memcached write_heavy: Kops/s native 482.1, RLBox-only 466.6, InterSpec 457.8; InterSpec against RLBox-only +3.1% (-3.4 to +14.5); RLBox-only against native +3.8%
- memcached watch_light: Kops/s native 25.5, RLBox-only 25.2, InterSpec 24.6; InterSpec against RLBox-only +3.4% (-5.7 to +10.7); RLBox-only against native -1.0%
- memcached watch_moderate: Kops/s native 83.9, RLBox-only 83.4, InterSpec 80.4; InterSpec against RLBox-only +3.7% (-2.7 to +9.2); RLBox-only against native -1.1%
- nginx 4 threads: RLBox-only against native +24.4% (+3.2 to +48.0) time per request; 19.8% fewer requests per second (ratio of medians)
- nginx 8 threads: RLBox-only against native +23.5% (+12.1 to +55.6) time per request; 18.9% fewer requests per second (ratio of medians)
- rsync file_sync_194mb: ms native 1411.170, RLBox-only 1407.197, InterSpec 1421.237; -0.2% (-6.2 to +8.9); RLBox-only against native +0.3%; instructions of the whole run: native 6,277,320,100 (-0.105%, repeats differ by 14,005), rlbox-only 6,283,942,524 (+0.000%, repeats differ by 57,382), interspec 6,284,227,708 (+0.005%, repeats differ by 20,687), interspec-all-off 6,284,552,597 (+0.010%, repeats differ by 10,415)
- rsync option_parse: ms native 2.224, RLBox-only 3.455, InterSpec 3.646; +4.9% (-13.3 to +24.7); RLBox-only against native +55.3%; instructions of the whole run: native 565,057 (-80.746%, repeats differ by 0), rlbox-only 2,934,762 (+0.000%, repeats differ by 0), interspec 2,937,836 (+0.105%, repeats differ by 0), interspec-all-off 3,075,163 (+4.784%, repeats differ by 0)
- yaml sliced (30 slices of 12 parses): RLBox-only against native +64.2% (+54.3 to +68.6); registry without checks against RLBox-only -0.2% (-4.8 to +4.9); instructions per parse: native 100,457,393 (-17.988%, repeats differ by 0), rlbox-only 122,491,642 (+0.000%, repeats differ by 0), interspec 122,391,251 (-0.082%, repeats differ by 0), interspec-all-off 122,501,882 (+0.008%, repeats differ by 14)
- ffmpeg/libvpx, VP8 encode and decode: RLBox-only against native +7.3% (+4.0 to +12.6); instructions per iteration native 101,925,684.8, RLBox-only 121,498,845.0, InterSpec 121,479,264.0 (-0.02%); largest difference between repeated counts 16
- magick/libpng, PNG decode and encode: RLBox-only against native -0.1% (-6.4 to +9.4); instructions per iteration native 1,571,021.0, RLBox-only 1,977,488.0, InterSpec 1,976,926.0 (-0.03%); largest difference between repeated counts 0
- memcached/hash, Hash function: RLBox-only against native +155.9% (+136.3 to +171.1); instructions per iteration native 96.3, RLBox-only 250.9, InterSpec 202.4 (-19.33%); largest difference between repeated counts 0
- memcached/hash, Hash table: RLBox-only against native +28.8% (+20.3 to +35.2); instructions per iteration native 463.4, RLBox-only 836.0, InterSpec 806.1 (-3.59%); largest difference between repeated counts 0
- nginx/openssl, TLS~1.3 request and response: RLBox-only against native +497.0% (+484.7 to +505.1); instructions per iteration native 149,513.1, RLBox-only 912,604.8, InterSpec 910,216.5 (-0.26%); largest difference between repeated counts 17867
- ucl/libucl, Parse, look up, emit: RLBox-only against native +24.7% (+12.8 to +28.4); instructions per iteration native 45,923.3, RLBox-only 62,281.0, InterSpec 61,237.0 (-1.68%); largest difference between repeated counts 4880000
- zip/libzip, Metadata queries: RLBox-only against native +36.6% (+30.0 to +43.1); instructions per iteration native 862.4, RLBox-only 1,339.4, InterSpec 1,480.0 (+10.50%); largest difference between repeated counts 0
- zip/libzip, Archive listing, 1,000 entries: RLBox-only against native -12.4% (-17.3 to -5.8); instructions per iteration native 7,967,178.1, RLBox-only 6,498,335.4, InterSpec 6,775,392.7 (+4.26%); largest difference between repeated counts 0
