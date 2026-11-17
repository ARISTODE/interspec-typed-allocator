#!/usr/bin/env python3
"""Archive for the zip/libzip listing workload (tracker item R4).

Usage: make_zip_listing_archive.py OUT.zip [ENTRIES]

Writes a zip archive with ENTRIES (default 1,000) stored entries of 16 bytes
each, with path names of the form project/module_017/source_0421.c and a fixed
date, so that the bytes do not depend on when the script runs. The archive is
synthetic: it gives the listing workload many entries and little data, so that
the time goes to opening the archive and reading names and sizes. The copy in
evaluation/parity/zip_listing is the one the measurements used; SHA256SUMS
there names it.
"""
import sys
import zipfile

out = sys.argv[1]
entries = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as archive:
    for i in range(entries):
        info = zipfile.ZipInfo(f"project/module_{i % 40:03d}/source_{i:04d}.c",
                               date_time=(2026, 1, 1, 0, 0, 0))
        info.external_attr = 0o644 << 16
        info.create_system = 3
        archive.writestr(info, f"/* file {i:05d} */\n".encode())
