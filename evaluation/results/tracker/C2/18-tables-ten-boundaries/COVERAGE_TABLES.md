# Coverage tables regenerated from analysis output

Boundaries with output: 10 of 10. Missing: none.

## SP1 (confidentiality)

| Boundary | Interface fields | SP1 fields | Coverage | Paper: fields | Paper: SP1 | Paper: coverage |
|---|---:|---:|---:|---:|---:|---:|
| ffmpeg/libvpx | 4715 | 2465 | 52.3% | 345 | 112 | 32.5% |
| magick/libpng | 12937 | 9228 | 71.3% | 418 | 156 | 37.3% |
| memcached/bipbuffer | 80 | 23 | 28.8% | 80 | 1 | 1.3% |
| memcached/hash | 86 | 33 | 38.4% | 86 | 17 | 19.8% |
| nginx/libpcre | 158 | 41 | 25.9% | 57 | 3 | 5.3% |
| nginx/openssl | 351808 | 130196 | 37.0% | 1485 | 624 | 42.0% |
| rsync/popt | 1667 | 1087 | 65.2% | 767 | 92 | 12.0% |
| ucl/libucl | 1622 | 904 | 55.7% | 152 | 0 | 0.0% |
| yaml/libyaml | 1919 | 1454 | 75.8% | 1903 | 1303 | 68.5% |
| zip/libzip | 2230 | 873 | 39.1% | 2230 | 871 | 39.1% |
| Subtotal of these rows | 377222 | 146304 | 38.8% | 7523 | 3179 | |

## SP2 and SP3 (integrity)

| Boundary | Fields | SP2 fields | SP2 share | Pointer fields | Pointer: SP2 | Pointer: SP1 only | Pointer: SP3 | Pointer: other | Paper: SP2 | Paper: pointers | Paper: SP3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ffmpeg/libvpx | 4715 | 2531 | 53.7% | 347 | 21 | 1 | 26 | 299 | 138 | 74 | 2 |
| magick/libpng | 12937 | 9577 | 74.0% | 2183 | 21 | 0 | 1 | 2161 | 178 | 96 | 3 |
| memcached/bipbuffer | 80 | 45 | 56.2% | 12 | 2 | 0 | 2 | 8 | 7 | 12 | 2 |
| memcached/hash | 86 | 48 | 55.8% | 24 | 8 | 0 | 5 | 11 | 33 | 26 | 4 |
| nginx/libpcre | 158 | 101 | 63.9% | 44 | 8 | 0 | 0 | 36 | 14 | 31 | 2 |
| nginx/openssl | 351808 | 132396 | 37.6% | 120812 | 98 | 0 | 2443 | 118271 | 651 | 512 | 5 |
| rsync/popt | 1667 | 1159 | 69.5% | 637 | 8 | 0 | 21 | 608 | 116 | 37 | 7 |
| ucl/libucl | 1622 | 1035 | 63.8% | 649 | 2 | 0 | 1 | 646 | 8 | 64 | 3 |
| yaml/libyaml | 1919 | 1460 | 76.1% | 461 | 8 | 0 | 1 | 452 | 1194 | 461 | 1 |
| zip/libzip | 2230 | 947 | 42.5% | 653 | 8 | 0 | 2 | 643 | 947 | 653 | 3 |
| Subtotal of these rows | 377222 | 149299 | 39.6% | 125822 | 184 | 1 | 2502 | 123135 | 3286 | 1966 | 32 |

## Pointer fields that need SP3

| Boundary | Pointer fields | Value from U used by T (needs SP3) | Expected domain resolved | Unresolved | Pointer coverage |
|---|---:|---:|---:|---:|---:|
| ffmpeg/libvpx | 347 | 29 | 18 | 11 | 96.8% |
| magick/libpng | 2183 | 1 | 1 | 0 | 100.0% |
| memcached/bipbuffer | 12 | 2 | 2 | 0 | 100.0% |
| memcached/hash | 24 | 7 | 7 | 0 | 100.0% |
| nginx/libpcre | 44 | 0 | 0 | 0 | 100.0% |
| nginx/openssl | 120812 | 2472 | 501 | 1971 | 98.4% |
| rsync/popt | 637 | 23 | 8 | 15 | 97.6% |
| ucl/libucl | 649 | 1 | 1 | 0 | 100.0% |
| yaml/libyaml | 461 | 2 | 2 | 0 | 100.0% |
| zip/libzip | 653 | 3 | 3 | 0 | 100.0% |
| Subtotal of these rows | 125822 | 2540 | 543 | 1997 | 98.4% |
