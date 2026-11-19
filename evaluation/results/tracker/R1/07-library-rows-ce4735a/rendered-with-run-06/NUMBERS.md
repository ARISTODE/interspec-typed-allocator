# Numbers of the performance subsection

## Complete application

- measurements: 7; range includes zero: 7 (medians -1.3 to +1.8); whole range below zero: 0 (); whole range above zero: 0 ()
- geometric mean of the 7 medians: +0.80%
- instruction differences where counted: rsync/popt 194\,MiB file sync +0.00%, yaml/libyaml 1\,MiB document -0.08%

- memcached/bipbuffer, 8 clients, no log watcher: native 782.329, RLBox-only 760.773, InterSpec 758.042 [Kops/s]; +0.2% (-6.6 to +7.2)
- memcached/bipbuffer, 1 client, log watcher: native 29.874, RLBox-only 29.539, InterSpec 29.098 [Kops/s]; +1.7% (-7.9 to +6.7)
- memcached/bipbuffer, 2 clients, log watcher: native 98.919, RLBox-only 100.897, InterSpec 99.770 [Kops/s]; +1.1% (-3.8 to +9.2)
- nginx/libpcre, wrk, 4 threads: native 86.228, RLBox-only 72.145, InterSpec 71.025 [Kreq/s]; +1.3% (-5.5 to +7.3)
- nginx/libpcre, wrk, 8 threads: native 81.578, RLBox-only 67.331, InterSpec 66.005 [Kreq/s]; +1.8% (-6.1 to +5.4)
- rsync/popt, 194\,MiB file sync: native 1.344, RLBox-only 1.325, InterSpec 1.334 [Runtime (s)]; +0.8% (-2.2 to +2.8)
- yaml/libyaml, 1\,MiB document: native 8.486, RLBox-only 10.698, InterSpec 10.434 [Time per parse (ms)]; -1.3% (-6.5 to +2.9)

## Library workload

- measurements: 8; range includes zero: 4 (medians -1.0 to +1.6); whole range below zero: 2 (memcached/hash Hash function, memcached/hash Hash table); whole range above zero: 2 (zip/libzip Metadata queries, zip/libzip Archive listing, 1,000 entries)
- geometric mean of the 8 medians: +0.24%
- instruction differences where counted: ffmpeg/libvpx VP8 encode and decode -0.02%, magick/libpng PNG decode and encode -0.03%, memcached/hash Hash function -12.34%, memcached/hash Hash table -3.66%, nginx/openssl TLS~1.3 request and response -0.25%, ucl/libucl Parse, look up, emit -0.49%, zip/libzip Metadata queries +12.57%, zip/libzip Archive listing, 1,000 entries +4.63%

- ffmpeg/libvpx, VP8 encode and decode: native 10.112, RLBox-only 11.290, InterSpec 11.191 [Time per frame (ms)]; -0.7% (-7.3 to +5.6)
- magick/libpng, PNG decode and encode: native 196.270, RLBox-only 201.048, InterSpec 203.868 [Time per image (\textmu{}s)]; +1.6% (-2.9 to +9.6)
- memcached/hash, Hash function: native 8.896, RLBox-only 21.385, InterSpec 20.075 [Time per call (ns)]; -6.7% (-8.5 to -3.4)
- memcached/hash, Hash table: native 173.092, RLBox-only 226.343, InterSpec 215.979 [Time per operation (ns)]; -4.3% (-7.2 to -2.1)
- nginx/openssl, TLS~1.3 request and response: native 19.067, RLBox-only 111.128, InterSpec 110.381 [Time per exchange (\textmu{}s)]; -1.0% (-4.8 to +8.3)
- ucl/libucl, Parse, look up, emit: native 6.243, RLBox-only 7.271, InterSpec 7.617 [Time per iteration (\textmu{}s)]; -0.0% (-5.6 to +7.5)
- zip/libzip, Metadata queries: native 91.033, RLBox-only 116.843, InterSpec 126.875 [Time per query (ns)]; +8.6% (+3.9 to +14.6)
- zip/libzip, Archive listing, 1,000 entries: native 663.661, RLBox-only 571.139, InterSpec 602.512 [Time per listing (\textmu{}s)]; +5.2% (+1.2 to +8.8)

- geometric mean of all 15 medians: +0.50%

## Per-policy table

- rows: 13; rows whose combined cost has its whole range on one side of zero: 1 (memcached/hash, function)

- memcached/bipbuffer: sp1 -0.2% (-2.3 to +6.7); sp2 +0.3% (-3.7 to +3.6); sp3 +0.8% (-2.3 to +5.4); all-on +1.1% (-1.0 to +5.2); all on against RLBox-only +1.3% (-1.3 to +5.6); all off against RLBox-only +0.2% (-5.1 to +3.7)
- nginx/libpcre: sp1 -1.4% (-9.5 to +3.7); sp2 -2.3% (-10.9 to +6.2); sp3 -0.3% (-10.4 to +6.8); all-on -2.5% (-13.2 to +8.2); all on against RLBox-only -1.4% (-6.4 to +11.0); all off against RLBox-only +3.5% (-6.7 to +14.9)
- rsync/popt, option parsing: sp1 +0.4% (-2.2 to +1.3); sp2 -0.4% (-3.9 to +4.8); sp3 -0.2% (-2.6 to +1.0); all-on -0.3% (-2.0 to +2.0); all on against RLBox-only +0.9% (-0.8 to +2.9); all off against RLBox-only +1.2% (+0.1 to +3.0)
- rsync/popt, file sync: sp1 -0.0% (-0.8 to +1.2); sp2 -0.4% (-1.4 to +0.7); sp3 +0.2% (-1.7 to +1.0); all-on +0.0% (-1.3 to +1.1); all on against RLBox-only +0.2% (-2.6 to +1.8); all off against RLBox-only +0.0% (-1.6 to +1.7)
- yaml/libyaml: sp1 no such policy; sp2 -0.3% (-4.8 to +6.6); sp3 -1.1% (-5.8 to +4.8); all-on -0.6% (-7.2 to +4.9); all on against RLBox-only +0.2% (-5.5 to +4.3); all off against RLBox-only +0.1% (-6.8 to +7.5)
- ffmpeg/libvpx: sp1 +0.7% (-11.4 to +7.2); sp2 +1.4% (-4.6 to +9.4); sp3 +0.8% (-7.1 to +12.9); all-on +0.8% (-9.7 to +8.1); all on against RLBox-only -2.0% (-7.0 to +8.6); all off against RLBox-only -1.7% (-7.8 to +6.7)
- magick/libpng: sp1 -1.4% (-7.8 to +4.3); sp2 -1.2% (-6.7 to +5.1); sp3 -0.9% (-5.2 to +3.7); all-on +1.8% (-5.1 to +6.0); all on against RLBox-only +1.6% (-3.8 to +4.4); all off against RLBox-only +0.0% (-3.4 to +7.1)
- memcached/hash, function: sp1 +1.1% (-4.5 to +7.1); sp2 -8.0% (-11.9 to -5.2); sp3 -0.3% (-4.9 to +4.3); all-on -8.3% (-12.3 to -5.7); all on against RLBox-only -8.6% (-11.4 to -4.2); all off against RLBox-only +1.2% (-5.1 to +4.1)
- memcached/hash, table: sp1 -5.9% (-7.6 to -1.4); sp2 -2.7% (-8.4 to +0.3); sp3 +3.7% (-2.2 to +7.6); all-on -4.8% (-8.8 to +0.9); all on against RLBox-only -3.3% (-8.8 to +1.6); all off against RLBox-only +1.3% (-3.9 to +4.5)
- nginx/openssl: sp1 +0.2% (-4.0 to +2.3); sp2 -0.2% (-4.6 to +3.6); sp3 -0.3% (-2.8 to +4.1); all-on -0.4% (-3.3 to +2.4); all on against RLBox-only -1.1% (-5.0 to +3.4); all off against RLBox-only -0.6% (-5.9 to +4.1)
- ucl/libucl: sp1 +1.1% (-4.9 to +6.9); sp2 -0.4% (-6.7 to +5.7); sp3 +1.3% (-6.0 to +9.0); all-on +1.1% (-3.4 to +7.0); all on against RLBox-only +2.6% (-6.2 to +8.2); all off against RLBox-only -0.0% (-6.8 to +7.2)
- zip/libzip, queries: sp1 -0.0% (-4.3 to +4.0); sp2 +1.3% (-3.6 to +7.5); sp3 +5.5% (+1.4 to +11.1); all-on +4.4% (-2.4 to +10.6); all on against RLBox-only +7.9% (+2.1 to +14.9); all off against RLBox-only +4.0% (-2.9 to +8.2)
- zip/libzip, listing: sp1 +0.1% (-6.6 to +10.7); sp2 -0.4% (-8.0 to +10.2); sp3 +2.6% (-5.3 to +11.0); all-on +2.1% (-3.5 to +13.2); all on against RLBox-only +4.1% (-1.2 to +10.3); all off against RLBox-only +1.6% (-4.1 to +7.8)

## Details

- memcached balanced_1c: Kops/s native 221.2, RLBox-only 217.4, InterSpec 217.7; InterSpec against RLBox-only -0.1% (-4.3 to +10.2); RLBox-only against native +1.9%
- memcached balanced_8c: Kops/s native 782.3, RLBox-only 760.8, InterSpec 758.0; InterSpec against RLBox-only +0.2% (-6.6 to +7.2); RLBox-only against native +3.6%
- memcached read_heavy_1k: Kops/s native 1100.0, RLBox-only 1025.9, InterSpec 1017.3; InterSpec against RLBox-only +0.8% (-2.3 to +5.9); RLBox-only against native +7.4%
- memcached write_heavy: Kops/s native 595.8, RLBox-only 580.4, InterSpec 578.4; InterSpec against RLBox-only +0.6% (-3.5 to +2.9); RLBox-only against native +3.1%
- memcached watch_light: Kops/s native 29.9, RLBox-only 29.5, InterSpec 29.1; InterSpec against RLBox-only +1.7% (-7.9 to +6.7); RLBox-only against native +0.5%
- memcached watch_moderate: Kops/s native 98.9, RLBox-only 100.9, InterSpec 99.8; InterSpec against RLBox-only +1.1% (-3.8 to +9.2); RLBox-only against native +1.2%
- nginx 4 threads: RLBox-only against native +21.7% (+16.5 to +25.6) time per request; 16.3% fewer requests per second (ratio of medians)
- nginx 8 threads: RLBox-only against native +21.6% (+14.4 to +27.3) time per request; 17.5% fewer requests per second (ratio of medians)
- rsync file_sync_194mb: ms native 1343.501, RLBox-only 1325.113, InterSpec 1334.332; +0.8% (-2.2 to +2.8); RLBox-only against native -1.1%; instructions of the whole run: native 6,277,320,100 (-0.105%, repeats differ by 14,005), rlbox-only 6,283,942,524 (+0.000%, repeats differ by 57,382), interspec 6,284,227,708 (+0.005%, repeats differ by 20,687), interspec-all-off 6,284,552,597 (+0.010%, repeats differ by 10,415)
- rsync option_parse: ms native 1.243, RLBox-only 1.990, InterSpec 2.030; +2.0% (-7.4 to +17.5); RLBox-only against native +57.4%; instructions of the whole run: native 565,057 (-80.746%, repeats differ by 0), rlbox-only 2,934,762 (+0.000%, repeats differ by 0), interspec 2,937,836 (+0.105%, repeats differ by 0), interspec-all-off 3,075,163 (+4.784%, repeats differ by 0)
- yaml sliced (30 slices of 12 parses): RLBox-only against native +26.8% (+16.5 to +33.4); registry without checks against RLBox-only -1.1% (-3.5 to +2.8); instructions per parse: native 100,457,393 (-17.988%, repeats differ by 0), rlbox-only 122,491,642 (+0.000%, repeats differ by 0), interspec 122,391,251 (-0.082%, repeats differ by 0), interspec-all-off 122,501,882 (+0.008%, repeats differ by 14)
- ffmpeg/libvpx, VP8 encode and decode: RLBox-only against native +11.1% (+0.8 to +17.8); instructions per iteration native 101,925,682.8, RLBox-only 121,498,686.7, InterSpec 121,479,104.7 (-0.02%); largest difference between repeated counts 4
- magick/libpng, PNG decode and encode: RLBox-only against native +2.0% (-5.2 to +8.4); instructions per iteration native 1,571,021.0, RLBox-only 1,977,337.0, InterSpec 1,976,815.0 (-0.03%); largest difference between repeated counts 0
- memcached/hash, Hash function: RLBox-only against native +140.9% (+128.6 to +144.6); instructions per iteration native 96.3, RLBox-only 230.9, InterSpec 202.4 (-12.34%); largest difference between repeated counts 0
- memcached/hash, Hash table: RLBox-only against native +28.3% (+23.8 to +32.3); instructions per iteration native 463.4, RLBox-only 804.3, InterSpec 774.9 (-3.66%); largest difference between repeated counts 0
- nginx/openssl, TLS~1.3 request and response: RLBox-only against native +485.2% (+450.2 to +517.2); instructions per iteration native 149,501.2, RLBox-only 912,403.6, InterSpec 910,161.7 (-0.25%); largest difference between repeated counts 16732
- ucl/libucl, Parse, look up, emit: RLBox-only against native +22.4% (+12.3 to +34.2); instructions per iteration native 46,048.2, RLBox-only 62,103.0, InterSpec 61,798.0 (-0.49%); largest difference between repeated counts 7820000
- zip/libzip, Metadata queries: RLBox-only against native +29.3% (+22.5 to +36.1); instructions per iteration native 863.0, RLBox-only 1,285.4, InterSpec 1,447.0 (+12.57%); largest difference between repeated counts 14
- zip/libzip, Archive listing, 1,000 entries: RLBox-only against native -11.6% (-15.0 to -8.0); instructions per iteration native 8,084,160.7, RLBox-only 6,444,321.7, InterSpec 6,742,384.7 (+4.63%); largest difference between repeated counts 0
