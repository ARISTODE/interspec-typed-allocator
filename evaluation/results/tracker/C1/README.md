# C1 raw output: CodeQL databases for the ten boundaries

Tracker item C1 in `EVAL_TRACKER.md`. Built on the Claude Code VM with
`scripts/build_codeql_databases.sh`, CodeQL bundle v2.23.2 (CLI 2.23.2 with
`codeql/cpp-all` 5.6.1, the version in the artifact's lock file; bundle SHA-256
`0478926e…e177b`), analysis code and configurations from `interspec-artifact`
at `2b2d2fd`. Source revisions are in `evaluation/coverage/pins.json`.

Eight databases cover the ten boundaries. For each one the record directory
holds `source-revisions.txt`, `command.txt` (the exact `codeql database create`
call), `build.log`, `database-files.sha256` (SHA-256 of every database file)
and `database-tree.sha256` (the hash of that list).

| Database | Boundaries | Record | Tree hash (first 12) | Size |
|---|---|---|---|---:|
| `yaml_libyaml` | yaml/libyaml | `02-databases-1b8e924/yaml_libyaml/` | `58be9be3147e` | 14 MB |
| `ucl_libucl` | ucl/libucl | `02-databases-1b8e924/ucl_libucl/` | `871edb1d2a49` | 16 MB |
| `memcached` | memcached/bipbuffer, memcached/hash | `02-databases-1b8e924/memcached/` | `7a69eede76e6` | 23 MB |
| `rsync_popt` | rsync/popt | `02-databases-1b8e924/rsync_popt/` | `3d98d7a16cf8` | 25 MB |
| `zip_libzip` | zip/libzip | `03-databases-54f9e9b/zip_libzip/` | `07aef7e15e18` | 40 MB |
| `magick_libpng` | magick/libpng | `04-databases-bf79a64/magick_libpng/` | `212f5130a053` | 19 MB |
| `nginx` | nginx/libpcre, nginx/openssl | `03-databases-54f9e9b/nginx/` | `5aa1e73a543b` | 402 MB |
| `ffmpeg_libvpx` | ffmpeg/libvpx | `03-databases-54f9e9b/ffmpeg_libvpx/` | `c469cdd8247c` | 520 MB |

The databases themselves are not in the repository (about 1 GB). They exist in
this session's scratch space and can be rebuilt with the script; a rebuild
gives the same sources and commands but not byte-identical database files, so
the tree hash identifies these builds, it is not a reproducibility check.

## Failed attempts, kept

- `01-databases-22f772b/`: built nothing. The script overwrote its own list of
  database names. Fixed in `1b8e924`.
- `02-databases-1b8e924/zip_libzip` and `magick_libpng`: source fetch failed
  (exit 97). The zlib pin named the tag object instead of the commit. Fixed in
  `54f9e9b`.
- `03-databases-54f9e9b/magick_libpng`: build failed. The artifact's script
  expects `pnglibconf.h.prebuilt` next to the libpng sources; upstream keeps it
  under `scripts/`. A wrapper copies it (`bf79a64`).

## Differences from the databases behind the paper's numbers

The original revisions were not recorded, so these are not the same databases.
Known differences, to be carried into C2:

- nginx/libpcre is built with PCRE 8.45 (JH's I5 decision). The artifact
  analysed PCRE2; its configuration `configs/nginx_libpcre.json` names
  `benchmarks/pcre2/src` and PCRE2 interface functions and does not match this
  database as it stands.
- OpenSSL 3.5.9, libpng 1.6.59, zlib 1.3.2, libucl 0.9.4 and libzip 1.11.4 are
  current releases chosen now.
- rsync, memcached, nginx and libyaml use the revisions of this repository's
  integrations. ffmpeg 8.0 and libvpx 1.15.2 are the versions the artifact names.
- ffmpeg is configured with `--disable-x86asm`; libvpx is built with its
  default assembly.
