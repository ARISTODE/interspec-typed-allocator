#include "yaml.h"
#include "interspec_yaml_u_policy.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

extern uint32_t interspec_site_alloc_slot;

static uint32_t g_scalar_bytes;

void interspec_yaml_init(uint32_t site_alloc_slot)
{
    interspec_site_alloc_slot = site_alloc_slot;
}

yaml_event_t *interspec_yaml_make_scalar(void)
{
    static const yaml_char_t value[] = "InterSpec-yaml";
    yaml_event_t *event = (yaml_event_t *)malloc(sizeof(*event));
    if (event == NULL)
        return NULL;
    memset(event, 0, sizeof(*event));

    if (!yaml_scalar_event_initialize(event,
                                      NULL,
                                      NULL,
                                      value,
                                      (int)(sizeof(value) - 1),
                                      1,
                                      1,
                                      YAML_PLAIN_SCALAR_STYLE)) {
        free(event);
        return NULL;
    }
    return event;
}

yaml_char_t *interspec_yaml_scalar_value(yaml_event_t *event)
{
    if (event == NULL || event->type != YAML_SCALAR_EVENT ||
        event->data.scalar.value == NULL)
        return NULL;
    g_scalar_bytes = (uint32_t)event->data.scalar.length;
    return event->data.scalar.value;
}

yaml_char_t *interspec_yaml_scalar_wrong_type(void)
{
    static const yaml_char_t bytes[] = "bad";
    uint32_t raw = 0;

    INTERSPEC_SITE_WRONG_TYPE_BEGIN();
    raw = INTERSPEC_SITE_ALLOC(sizeof(bytes));
    INTERSPEC_SITE_WRONG_TYPE_END();
    if (raw == 0)
        return NULL;

    memcpy((void *)(uintptr_t)raw, bytes, sizeof(bytes));
    g_scalar_bytes = (uint32_t)(sizeof(bytes) - 1);
    return (yaml_char_t *)(uintptr_t)raw;
}

yaml_char_t *interspec_yaml_scalar_untracked(void)
{
    yaml_char_t *ptr = (yaml_char_t *)malloc(8);
    if (ptr == NULL)
        return NULL;
    memset(ptr, 'U', 8);
    g_scalar_bytes = 8;
    return ptr;
}

yaml_char_t *interspec_yaml_scalar_oversized(yaml_event_t *event)
{
    yaml_char_t *ptr = interspec_yaml_scalar_value(event);
    if (ptr == NULL)
        return NULL;
    g_scalar_bytes += 4096;
    return ptr;
}

uint32_t interspec_yaml_scalar_size(void)
{
    return g_scalar_bytes;
}
