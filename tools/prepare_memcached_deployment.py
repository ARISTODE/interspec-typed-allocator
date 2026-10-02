#!/usr/bin/env python3
"""Apply pinned, asserted source edits for the complete memcached deployment."""
import argparse
from pathlib import Path
import shutil

p = argparse.ArgumentParser()
p.add_argument("--source", type=Path, required=True)
p.add_argument("--root", type=Path, required=True)
a = p.parse_args()
s = a.source / "logger.c"
text = s.read_text()

def replace(old, new):
    global text
    assert text.count(old) == 1, old
    text = text.replace(old, new, 1)

replace("/* Logger GID's can be used", '#include "interspec_logger_validate.h"\n\n/* Logger GID\'s can be used')
replace("    l->entry_map = default_entries;", "    interspec_bipbuf_role(l->buf, 1);\n    l->entry_map = default_entries;")
replace('    bipbuf_offer(w->buf, (unsigned char *) "OK\\r\\n", 4);',
        '    interspec_bipbuf_role(w->buf, 2);\n    bipbuf_offer(w->buf, (unsigned char *) "OK\\r\\n", 4);')
replace("    /* parse buffer */", "    union { max_align_t align; unsigned char bytes[LOGGER_ENTRY_MAX_SIZE]; } safe_entry;\n    /* parse buffer */")
replace("        e = (logentry *) (data + pos);",
        "        e = interspec_checked_log(data + pos, size - pos, safe_entry.bytes);")
s.write_text(text)
shutil.copyfile(a.root / "integration/memcached_server/logger_validate.h", a.source / "interspec_logger_validate.h")
