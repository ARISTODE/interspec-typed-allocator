/* Included after upstream default_entries. This is application validation,
 * distinct from SP3's pointer type/extent/liveness checks. U can change bytes
 * inside a valid allocation, including array indexes and record lengths. */
#include <stddef.h>
#if defined(EXTSTORE) || defined(PROXY)
#error "The memcached deployment currently supports the cache server without extstore/proxy"
#endif
extern void interspec_bipbuf_role(bipbuf_t *, unsigned int);

static void interspec_bad_log(void) {
    fprintf(stderr, "INTERSPEC_REJECT boundary=memcached_logger reason=malformed_record\n");
    fflush(stderr);
    abort();
}

static logentry *interspec_checked_log(const unsigned char *source,
        size_t remaining, unsigned char *aligned) {
    if (remaining < sizeof(logentry)) interspec_bad_log();
    memcpy(aligned, source, sizeof(logentry));
    logentry *e = (logentry *)aligned;
    if (e->size < 0 || e->pad > 7 ||
            (size_t)e->size > LOGGER_ENTRY_MAX_SIZE - sizeof(logentry) - e->pad ||
            (size_t)e->size + e->pad > remaining - sizeof(logentry)) interspec_bad_log();
    if ((unsigned)e->event >= sizeof(default_entries) / sizeof(default_entries[0])) interspec_bad_log();
    memcpy(aligned, source, sizeof(logentry) + e->size + e->pad);
    size_t n = (size_t)e->size;
#define KEY_RECORD(type) \
    if (n < sizeof(struct type)) interspec_bad_log(); \
    struct type *v = (struct type *)e->data; \
    if (v->nkey > n - sizeof(struct type) || v->nkey > KEY_MAX_LENGTH) interspec_bad_log()
    switch (e->event) {
    case LOGGER_EVICTION: { KEY_RECORD(logentry_eviction); break; }
    case LOGGER_ITEM_GET: {
        KEY_RECORD(logentry_item_get);
        if (v->was_found > 3) interspec_bad_log();
        break;
    }
    case LOGGER_ITEM_STORE: {
        KEY_RECORD(logentry_item_store);
        if (v->status < 0 || v->status > 5 || v->cmd < 0 || v->cmd > 8) interspec_bad_log();
        break;
    }
    case LOGGER_DELETIONS: {
        KEY_RECORD(logentry_deletion);
        if (v->cmd < 0 || v->cmd > 2) interspec_bad_log();
        break;
    }
    case LOGGER_CONNECTION_NEW:
    case LOGGER_CONNECTION_CLOSE: {
        if (n < sizeof(struct logentry_conn_event)) interspec_bad_log();
        struct logentry_conn_event *v = (struct logentry_conn_event *)e->data;
        if (v->transport < 0 || v->transport > 2 || v->reason < 0 || v->reason > 3) interspec_bad_log();
        break;
    }
    default:
        if (!default_entries[e->event].parse_cb || !memchr(e->data, '\0', n)) interspec_bad_log();
        break;
    }
#undef KEY_RECORD
    return e;
}
