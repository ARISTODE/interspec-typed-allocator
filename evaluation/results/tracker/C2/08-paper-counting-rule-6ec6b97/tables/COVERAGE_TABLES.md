# Coverage tables regenerated from analysis output

Boundaries with output: 7 of 10. Missing: ffmpeg/libvpx, nginx/libpcre, nginx/openssl.

## SP1 (confidentiality)

| Boundary | Interface fields | SP1 fields | Coverage | Paper: fields | Paper: SP1 | Paper: coverage |
|---|---:|---:|---:|---:|---:|---:|
| magick/libpng | 12937 | 9228 | 71.3% | 418 | 156 | 37.3% |
| memcached/bipbuffer | 80 | 23 | 28.8% | 80 | 1 | 1.3% |
| memcached/hash | 86 | 33 | 38.4% | 86 | 17 | 19.8% |
| rsync/popt | 1667 | 1087 | 65.2% | 767 | 92 | 12.0% |
| ucl/libucl | 1622 | 904 | 55.7% | 152 | 0 | 0.0% |
| yaml/libyaml | 1919 | 1454 | 75.8% | 1903 | 1303 | 68.5% |
| zip/libzip | 2230 | 873 | 39.1% | 2230 | 871 | 39.1% |
| Subtotal of these rows | 20541 | 13602 | 66.2% | 5636 | 2440 | |

## SP2 and SP3 (integrity)

| Boundary | Fields | SP2 fields | SP2 share | Pointer fields | Pointer: SP2 | Pointer: SP1 only | Pointer: SP3 | Pointer: other | Paper: SP2 | Paper: pointers | Paper: SP3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| magick/libpng | 12937 | 9577 | 74.0% | 2183 | 21 | 0 | 1 | 2161 | 178 | 96 | 3 |
| memcached/bipbuffer | 80 | 45 | 56.2% | 12 | 2 | 0 | 2 | 8 | 7 | 12 | 2 |
| memcached/hash | 86 | 48 | 55.8% | 24 | 8 | 0 | 5 | 11 | 33 | 26 | 4 |
| rsync/popt | 1667 | 1159 | 69.5% | 637 | 8 | 0 | 21 | 608 | 116 | 37 | 7 |
| ucl/libucl | 1622 | 1035 | 63.8% | 649 | 2 | 0 | 1 | 646 | 8 | 64 | 3 |
| yaml/libyaml | 1919 | 1460 | 76.1% | 461 | 8 | 0 | 1 | 452 | 1194 | 461 | 1 |
| zip/libzip | 2230 | 947 | 42.5% | 653 | 8 | 0 | 2 | 643 | 947 | 653 | 3 |
