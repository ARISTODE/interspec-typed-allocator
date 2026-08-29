#include "yaml.h"

/*
 * CodeQL-only representation of T consuming a pointer nested inside a real
 * yaml_event_t. Internal libyaml parser pointers are deliberately not part of
 * the policy because T never dereferences them.
 */
void interspec_trusted_use_yaml_scalar(const yaml_event_t *event)
{
    if (event != NULL && event->type == YAML_SCALAR_EVENT &&
        event->data.scalar.value != NULL && event->data.scalar.length != 0) {
        volatile yaml_char_t first = event->data.scalar.value[0];
        volatile yaml_char_t last =
            event->data.scalar.value[event->data.scalar.length - 1];
        (void)first;
        (void)last;
    }
}
