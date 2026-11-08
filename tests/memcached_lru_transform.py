#!/usr/bin/env python3
"""Guard raw H2 record framing without changing its pointer-policy comparison."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--source', type=Path, help='optional pinned upstream source tree')
p.add_argument('--compiler', default='c++')
a = p.parse_args()
LOGGER = '''/* Logger GID's can be used */
    l->entry_map = default_entries;
    bipbuf_offer(w->buf, (unsigned char *) "OK\\r\\n", 4);
    /* parse buffer */
        e = (logentry *) (data + pos);
'''
ITEMS = '''static bool lru_bump_async(lru_bump_buf *b, item *it, uint32_t hv);
    pthread_mutex_init(&b->mutex, NULL);
        be->it = it;
        if (bipbuf_push(b->buf, sizeof(lru_bump_entry)) == 0) {
        todo = size;
        while (todo) {
            item_lock(be->hv);
            do_item_update(be->it);
            do_item_remove(be->it);
            item_unlock(be->hv);
            be++;
            todo -= sizeof(lru_bump_entry);
        }
'''
with tempfile.TemporaryDirectory(prefix='interspec-lru-transform-') as tmp:
    tmp = Path(tmp)
    for mode in ('upstream', 'domain', 'extended', 'handle'):
        dest = tmp / mode
        dest.mkdir()
        for name, fixture in [('items.c', ITEMS), ('logger.c', LOGGER)]:
            if a.source:
                shutil.copyfile(a.source / name, dest / name)
            else:
                (dest / name).write_text(fixture)
        subprocess.run([sys.executable, str(ROOT / 'tools/prepare_memcached_deployment.py'),
                        '--root', str(ROOT), '--source', str(dest), '--lru-mode', mode], check=True)
        text = (dest / 'items.c').read_text()
        guard = '        interspec_lru_extent(size, sizeof(lru_bump_entry));'
        assert text.count(guard) == (0 if mode == 'upstream' else 1), mode
        if mode != 'upstream':
            assert text.index(guard) < text.index('        todo = size;')
            assert text.count('extern void interspec_lru_extent(') == 1
        if mode in ('domain', 'extended'):
            check = '            interspec_lru_check_raw(b->buf, be->it, sizeof(item));'
            assert text.index(guard) < text.index(check) < text.index('            item_lock(be->hv);')
            assert 'interspec_lru_take(' not in text
            assert ('interspec_lru_register_raw(b->buf' in text) == (mode == 'extended')
        if mode == 'handle':
            assert 'interspec_lru_take(b->buf, (uintptr_t)be->it, be->hv)' in text
    # Compile the actual defensive extent helper, replacing only its fatal
    # rejection sink with an exception so every input can be checked safely.
    bridge = (ROOT / 'integration/memcached_server/bridge.cpp').read_text()
    helper = re.search(r'void interspec_lru_extent\([^}]+\}', bridge).group(0)
    source = tmp / 'extent.cpp'
    source.write_text('''#include <cassert>
#include <climits>
struct Rejected {};
void reject(const char *, const char *) { throw Rejected{}; }
''' + helper + '''
bool accepts(unsigned bytes, unsigned size) {
    try { interspec_lru_extent(bytes, size); return true; }
    catch (const Rejected &) { return false; }
}
int main() {
    for (unsigned size : {8u, 16u, 24u, 32u}) {
        for (unsigned bytes = 0; bytes <= 4096; ++bytes)
            assert(accepts(bytes, size) == (bytes != 0 && bytes % size == 0));
        assert(accepts(UINT_MAX, size) == (UINT_MAX % size == 0));
    }
    assert(!accepts(16, 0));
}
'''.replace('int main()', '#include <initializer_list>\nint main()'))
    binary = tmp / 'extent'
    subprocess.run([a.compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                    str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('Memcached LRU transform and defensive record extent: pass')
