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

# LRU bump records also use bipbuffer and originally contain native pointers.
# Preserve T ownership with one-use, per-buffer handles before bytes enter U.
s = a.source / "items.c"
text = s.read_text()
replace('static bool lru_bump_async(lru_bump_buf *b, item *it, uint32_t hv);', '''extern void interspec_bipbuf_role(bipbuf_t *, unsigned int);
extern uintptr_t interspec_lru_hold(bipbuf_t *, void *, uint32_t);
extern void interspec_lru_cancel(bipbuf_t *, uintptr_t);
extern void *interspec_lru_take(bipbuf_t *, uintptr_t, uint32_t);
extern void interspec_lru_extent(unsigned int, unsigned int);
_Static_assert(sizeof(void *) == 8, "LRU wire handles require a 64-bit host");
static bool lru_bump_async(lru_bump_buf *b, item *it, uint32_t hv);''')
replace('    pthread_mutex_init(&b->mutex, NULL);', '    interspec_bipbuf_role(b->buf, 3);\n    pthread_mutex_init(&b->mutex, NULL);')
replace('        be->it = it;', '        uintptr_t token = interspec_lru_hold(b->buf, it, hv);\n        be->it = (item *)token;')
replace('        if (bipbuf_push(b->buf, sizeof(lru_bump_entry)) == 0) {',
        '        if (bipbuf_push(b->buf, sizeof(lru_bump_entry)) == 0) {\n            interspec_lru_cancel(b->buf, token);')
replace('        todo = size;', '        interspec_lru_extent(size, sizeof(lru_bump_entry));\n        todo = size;')
replace('            item_lock(be->hv);', '            be->it = interspec_lru_take(b->buf, (uintptr_t)be->it, be->hv);\n            item_lock(be->hv);')
s.write_text(text)
