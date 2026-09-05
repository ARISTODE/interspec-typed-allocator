#include "pcre.h"
#include "interspec_pcre_u_policy.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

static uint32_t g_name_table_bytes;

pcre *interspec_wasm_pcre_compile_named(void)
{
    const char *error = NULL;
    int error_offset = 0;
    return pcre_compile("(?<word>abc)", 0, &error, &error_offset, NULL);
}

/*
 * P10 composition probe. A compromised U can reach authorized import sites
 * that exist anywhere in the linked Wasm module. When this PCRE import is
 * invoked while another boundary's PolicyRuntime is active, its namespaced
 * SiteId must be unregistered and the allocation must fail closed.
 */
void *interspec_wasm_pcre_foreign_site_probe(uint32_t size)
{
    uint32_t raw = INTERSPEC_SITE_COMPILED_REGEX_ALLOC(size);
    return (void *)(uintptr_t)raw;
}

unsigned char *interspec_wasm_pcre_name_table(pcre *compiled)
{
    unsigned char *table = NULL;
    int name_count = 0;
    int entry_size = 0;
    if (compiled == NULL)
        return NULL;
    if (pcre_fullinfo(compiled, NULL, PCRE_INFO_NAMECOUNT, &name_count) != 0)
        return NULL;
    if (pcre_fullinfo(compiled, NULL, PCRE_INFO_NAMEENTRYSIZE, &entry_size) != 0)
        return NULL;
    if (pcre_fullinfo(compiled, NULL, PCRE_INFO_NAMETABLE, &table) != 0)
        return NULL;
    if (name_count <= 0 || entry_size <= 0 || table == NULL)
        return NULL;
    g_name_table_bytes = (uint32_t)(name_count * entry_size);
    return table;
}

unsigned char *interspec_wasm_pcre_name_table_wrong_type(void)
{
    static const unsigned char bytes[] = "bad";
    uint32_t raw = INTERSPEC_SITE_WRONG_TYPE_ALLOC(sizeof(bytes));
    if (raw == 0)
        return NULL;
    memcpy((void *)(uintptr_t)raw, bytes, sizeof(bytes));
    g_name_table_bytes = (uint32_t)sizeof(bytes);
    return (unsigned char *)(uintptr_t)raw;
}

unsigned char *interspec_wasm_pcre_name_table_untracked(void)
{
    unsigned char *ptr = (unsigned char *)malloc(8);
    if (ptr == NULL)
        return NULL;
    memset(ptr, 'U', 8);
    g_name_table_bytes = 8;
    return ptr;
}

unsigned char *interspec_wasm_pcre_name_table_oversized(pcre *compiled)
{
    unsigned char *table = interspec_wasm_pcre_name_table(compiled);
    if (table == NULL)
        return NULL;
    g_name_table_bytes += 4096;
    return table;
}

uint32_t interspec_wasm_pcre_name_table_size(void)
{
    return g_name_table_bytes;
}
