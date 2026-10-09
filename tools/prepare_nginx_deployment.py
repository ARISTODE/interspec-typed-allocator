#!/usr/bin/env python3
"""Apply bounded source transformations to the pinned nginx/PCRE revisions."""
import argparse
from pathlib import Path


def replace_once(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise RuntimeError(f"unexpected patch context in {path}")
    path.write_text(text.replace(old, new, 1))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--nginx', type=Path, required=True)
    p.add_argument('--generated', type=Path, required=True)
    a = p.parse_args()
    source = a.nginx / 'src/core/ngx_regex.c'
    replace_once(source, '#include <ngx_core.h>', '#include <ngx_core.h>\nextern void interspec_nginx_release(void *);')
    replace_once(source, '''    rc->regex = ngx_pcalloc(rc->pool, sizeof(ngx_regex_t));''', '''    /* Destroy the T handle and its sandbox with this configuration pool,
     * including failed configuration and graceful-reload cleanup paths. */
    {
        ngx_pool_cleanup_t *cln = ngx_pool_cleanup_add(rc->pool, 0);
        if (cln == NULL) {
            interspec_nginx_release(re);
            goto nomem;
        }
        cln->handler = interspec_nginx_release;
        cln->data = re;
    }

    rc->regex = ngx_pcalloc(rc->pool, sizeof(ngx_regex_t));''')
    source = a.generated / 'pcre_compile.c'
    replace_once(source, '#include "pcre_internal.h"', '#include "pcre_internal.h"\n#include <stdint.h>\n#include "interspec_pcre_u_policy.h"')
    replace_once(source, 're = (REAL_PCRE *)(PUBL(malloc))(size);',
                 're = (REAL_PCRE *)(uintptr_t)INTERSPEC_SITE_COMPILED_REGEX_ALLOC((uint32_t)size);')
    text = source.read_text()
    assert text.count('(PUBL(free))(re);') == 2
    source.write_text(text.replace('(PUBL(free))(re);', 'interspec_wasm_release((uint32_t)(uintptr_t)re);'))


if __name__ == '__main__':
    main()
