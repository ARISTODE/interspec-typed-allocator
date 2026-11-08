#!/usr/bin/env python3
"""Fix the pinned upstream logger's NEED_ALIGN padding only for T sanitizer builds.

AddressSanitizer changes the pinned source's configure alignment result from
``none`` to ``need``. Its upstream padding expression is missing parentheses:

    sizeof(logentry) + e->size % 8

When sizeof(logentry) is 40, this yields a uint8_t pad of roughly 224,
instead of 0..7. T's existing logger format validator correctly rejects that
invalid record, making a no-fault sanitizer control impossible. Do not apply
this source correction to the ordinary, uninstrumented timing baseline.
"""
import argparse
from pathlib import Path


UPSTREAM = """#ifdef NEED_ALIGN
    /* Need to ensure *next* request is aligned. */
    if (sizeof(logentry) + e->size % 8 != 0) {
        e->pad = 8 - (sizeof(logentry) + e->size % 8);
    }
#endif"""

SANITIZED = """#ifdef NEED_ALIGN
    /* Security-delta sanitizer build: compute the record's aligned extent.
     * The pinned upstream expression omits parentheses around the addition.
     * An excessive pad is rejected by the trusted logger record validator. */
    size_t record_remainder = (sizeof(logentry) + (size_t)e->size) % 8;
    if (record_remainder != 0) {
        e->pad = (uint8_t)(8 - record_remainder);
    }
#endif"""


def patch_source(source):
    if source.count(UPSTREAM) != 1:
        raise ValueError("pinned upstream logger padding expression changed")
    return source.replace(UPSTREAM, SANITIZED, 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    original = args.source.read_text()
    args.source.write_text(patch_source(original))
