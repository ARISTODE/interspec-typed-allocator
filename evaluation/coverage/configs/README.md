# Boundary configurations written for the rebuilt databases (tracker item C2)

`interspec-artifact` defines the interface of these three boundaries as bridge
wrapper functions (`ngx_pcre_rlbox_*`, `ngx_openssl_rlbox_*`,
`ffmpeg_libvpx_rlbox_*`) that exist only in modified application sources. The
databases of C1 are built from upstream sources, which call the libraries
directly. These configurations therefore leave `interfaces` empty, as the
artifact does for yaml, zip, ucl and memcached: the interface is then every
library function the application calls.

- `nginx_libpcre.json`: PCRE 8.45 under `benchmarks/pcre` (the artifact has
  PCRE2 under `benchmarks/pcre2/src`).
- `nginx_openssl.json`: all of OpenSSL as called by nginx, not the 42 wrappers
  of the artifact's first phase.
- `ffmpeg_libvpx.json`: same trusted and untrusted file sets as the artifact,
  without the bridge sample directory.

Numbers from these configurations are not comparable row by row with the
paper's current numbers for the same boundaries.
