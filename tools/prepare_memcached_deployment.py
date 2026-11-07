#!/usr/bin/env python3
"""Apply pinned, asserted source edits for the complete memcached deployment."""
import argparse
from pathlib import Path
import shutil

p = argparse.ArgumentParser()
p.add_argument("--source", type=Path, required=True)
p.add_argument("--root", type=Path, required=True)
p.add_argument("--lru-mode", choices=("handle", "upstream", "domain", "extended"),
               default="handle", help="T-side LRU pointer policy; default is the deployed one-use handle")
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

# The security-delta variants retain the upstream raw-pointer wire format;
# only the existing production bridge uses opaque one-use T handles. Keep
# these separate source builds so a timing binary never contains fault hooks.
s = a.source / "items.c"
text = s.read_text()
prologue = '''extern void interspec_bipbuf_role(bipbuf_t *, unsigned int);'''
if a.lru_mode == "handle":
    prologue += '''
extern uintptr_t interspec_lru_hold(bipbuf_t *, void *, uint32_t);
extern void interspec_lru_cancel(bipbuf_t *, uintptr_t);
extern void *interspec_lru_take(bipbuf_t *, uintptr_t, uint32_t);
extern void interspec_lru_extent(unsigned int, unsigned int);
_Static_assert(sizeof(void *) == 8, "LRU wire handles require a 64-bit host");'''
elif a.lru_mode in ("domain", "extended"):
    prologue += '''
extern void interspec_lru_check_raw(bipbuf_t *, void *, unsigned int);'''
    if a.lru_mode == "extended":
        prologue += '''
extern void interspec_lru_register_raw(bipbuf_t *, void *, unsigned int, unsigned int);
extern void interspec_lru_revoke_raw(bipbuf_t *, void *);'''
prologue += '\nstatic bool lru_bump_async(lru_bump_buf *b, item *it, uint32_t hv);'
replace('static bool lru_bump_async(lru_bump_buf *b, item *it, uint32_t hv);', prologue)
replace('    pthread_mutex_init(&b->mutex, NULL);', '    interspec_bipbuf_role(b->buf, 3);\n    pthread_mutex_init(&b->mutex, NULL);')
if a.lru_mode == "handle":
    replace('        be->it = it;', '        uintptr_t token = interspec_lru_hold(b->buf, it, hv);\n        be->it = (item *)token;')
    replace('        if (bipbuf_push(b->buf, sizeof(lru_bump_entry)) == 0) {',
            '        if (bipbuf_push(b->buf, sizeof(lru_bump_entry)) == 0) {\n            interspec_lru_cancel(b->buf, token);')
    replace('        todo = size;', '        interspec_lru_extent(size, sizeof(lru_bump_entry));\n        todo = size;')
    replace('            item_lock(be->hv);',
            '            be->it = interspec_lru_take(b->buf, (uintptr_t)be->it, be->hv);\n            item_lock(be->hv);')
elif a.lru_mode in ("domain", "extended"):
    # A raw returned pointer is checked before *any* trusted item use. The
    # independent format/capacity checks are unchanged across both variants.
    replace('            item_lock(be->hv);',
            '            interspec_lru_check_raw(b->buf, be->it, sizeof(item));\n            item_lock(be->hv);')
    if a.lru_mode == "extended":
        replace('        be->it = it;',
                '        interspec_lru_register_raw(b->buf, it, sizeof(item), __alignof__(item));\n        be->it = it;')
        replace('        if (bipbuf_push(b->buf, sizeof(lru_bump_entry)) == 0) {',
                '        if (bipbuf_push(b->buf, sizeof(lru_bump_entry)) == 0) {\n            interspec_lru_revoke_raw(b->buf, it);')
s.write_text(text)
