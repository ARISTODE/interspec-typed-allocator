/* Native smoke probe. All counted source sites are in original upstream code.
 * Values created by this probe driver are NOT included in the statistics. */
#define _GNU_SOURCE
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pcre.h"
#include "popt.h"
#include "yaml.h"
#include "bipbuffer.h"

static const char *mapping(const void *pointer) {
    static char label[32];
    FILE *file = fopen("/proc/self/maps", "r");
    if (!file) return "unavailable";
    char line[1024], perm[8], name[512];
    uintptr_t address = (uintptr_t)pointer;
    while (fgets(line, sizeof(line), file)) {
        unsigned long long start, end;
        name[0] = '\0';
        if (sscanf(line, "%llx-%llx %7s %*s %*s %*s %511[^\n]",
                   &start, &end, perm, name) < 3) continue;
        if (address < start || address >= end) continue;
        if (strstr(name, "[stack]")) strcpy(label, "stack_mapping");
        else if (strstr(name, "[heap]")) strcpy(label, "heap_mapping");
        else if (perm[0] == 'r' && perm[1] == '-' && perm[2] == '-')
            strcpy(label, "readonly_mapping");
        else strcpy(label, "other_mapping");
        fclose(file);
        return label;
    }
    fclose(file);
    return "unmapped";
}

static void report(const char *site, const char *expected, const void *pointer) {
    assert(pointer);
    printf("{\"probe\":\"%s\",\"source_origin\":\"%s\",\"mapping\":\"%s\"}\n",
           site, expected, mapping(pointer));
}

int main(void) {
    const char *error = NULL;
    int offset = -1;
    pcre *code = pcre_compile("(", 0, &error, &offset, NULL);
    assert(code == NULL && error && offset >= 0);
    report("pcre_compile_error", "U_static", error);

    error = NULL;
    code = pcre_compile("a", 0, &error, &offset, NULL);
    assert(code && error == NULL);
    pcre_extra *extra = pcre_study(code, 0x7fffffff, &error);
    assert(extra == NULL && error);
    report("pcre_study_error", "U_static", error);
    pcre_free(code);

    const char *popt_error = poptStrerror(POPT_ERROR_BADOPT);
    assert(popt_error && *popt_error);
    report("poptStrerror", "U_literal_or_i18n", popt_error);

    yaml_parser_t parser;
    yaml_event_t event;
    const unsigned char invalid_utf8[] = {0xff};
    assert(yaml_parser_initialize(&parser));
    yaml_parser_set_input_string(&parser, invalid_utf8, sizeof(invalid_utf8));
    int parsed = yaml_parser_parse(&parser, &event);
    assert(!parsed && parser.problem);
    report("yaml_parser_problem", "U_static", parser.problem);
    yaml_parser_delete(&parser);

    bipbuf_t *buf = bipbuf_new(128);
    assert(buf);
    unsigned char data[] = "source-only";
    assert(bipbuf_offer(buf, data, sizeof(data)) != 0);
    unsigned int length = 0;
    unsigned char *bytes = bipbuf_peek_all(buf, &length);
    assert(bytes && length == sizeof(data));
    report("bipbuf_peek_all", "U_heap_interior", bytes);
    bipbuf_free(buf);
    return 0;
}
