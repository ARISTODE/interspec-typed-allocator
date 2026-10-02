#include <stdint.h>
#include <stdlib.h>
#ifdef INTERSPEC_FAULT_TESTS
#include <stdio.h>
#include <string.h>
#endif

#include "popt.h"

extern char* interspec_typed_strdup(const char* src);

enum interspec_p4c_slot_kind {
  INTERSPEC_P4C_SLOT_INT = 1,
  INTERSPEC_P4C_SLOT_STRING = 2,
};

struct interspec_p4c_slot {
  uint32_t kind;
  union {
    int i;
    char* s;
  } value;
};

struct interspec_p4c_table {
  uint32_t option_count;
  uint32_t slot_count;
  struct poptOption* options;
  struct interspec_p4c_slot* slots;
};

struct interspec_p4c_argv {
  uint32_t argc;
  const char** argv;
};

#ifdef INTERSPEC_FAULT_TESTS
// Test builds only. Allocation policy and trusted checks are unchanged.
static uint32_t fault_mode, fault_target, fault_fired;
static void* fault_context;
static struct interspec_p4c_table* fault_table;
static uintptr_t fault_decoy;
extern void interspec_typed_free(void*);

void interspec_test_set_fault(uint32_t mode, uint32_t target)
{
  fault_mode = mode;
  fault_target = target;
  fault_fired = 0;
}

static char* inject_pointer(char* value, uint32_t target)
{
  if (!value || fault_fired || !fault_mode || fault_mode > 5 ||
      fault_target != target) return value;
  char* replacement = value;
  size_t size = strlen(value) + 1;
  if (fault_mode == 1) replacement = (char*)fault_context;
  if (fault_mode == 2) {
    replacement = malloc(size);
    if (!replacement) abort();
    memcpy(replacement, value, size);
  }
  if (fault_mode == 3) interspec_typed_free(value);
  if (fault_mode == 4) memset(value, 'X', size);
  if (fault_mode == 5) {
    replacement = interspec_typed_strdup(value);
    if (!replacement) abort();
  }
  fault_fired = 1;
  fprintf(stderr, "FAULT_INJECTION mode=%u target=%u original=%p replacement=%p\n",
          fault_mode, target, (void*)value, (void*)replacement);
  fflush(stderr);
  return replacement;
}
#endif

char* interspec_p4c_typed_copy(const char* src)
{
  return interspec_typed_strdup(src);
}

void* interspec_p4c_table_new(uint32_t option_count, uint32_t slot_count)
{
  struct interspec_p4c_table* table = calloc(1, sizeof(*table));
  if (!table) return NULL;

  table->options = calloc(option_count, sizeof(*table->options));
  table->slots = calloc(slot_count ? slot_count : 1, sizeof(*table->slots));
  if (!table->options || !table->slots) {
    free(table->options);
    free(table->slots);
    free(table);
    return NULL;
  }

  table->option_count = option_count;
  table->slot_count = slot_count;
  return table;
}

int interspec_p4c_slot_set_int(void* opaque, uint32_t index, int value)
{
  struct interspec_p4c_table* table = opaque;
  if (!table || index >= table->slot_count) return 0;
  table->slots[index].kind = INTERSPEC_P4C_SLOT_INT;
  table->slots[index].value.i = value;
  return 1;
}

int interspec_p4c_slot_set_string(void* opaque, uint32_t index, char* value)
{
  struct interspec_p4c_table* table = opaque;
  if (!table || index >= table->slot_count) return 0;
  table->slots[index].kind = INTERSPEC_P4C_SLOT_STRING;
  table->slots[index].value.s = value;
  return 1;
}

int interspec_p4c_option_set(void* opaque,
                             uint32_t index,
                             uint32_t short_name,
                             uint32_t arg_info,
                             uint32_t slot_index,
                             int value)
{
  struct interspec_p4c_table* table = opaque;
  if (!table || index >= table->option_count) return 0;

  struct poptOption* option = &table->options[index];
  option->shortName = (char)short_name;
  option->argInfo = arg_info;
  option->val = value;

  if (slot_index == UINT32_MAX) {
    option->arg = NULL;
    return 1;
  }
  if (slot_index >= table->slot_count) return 0;

  struct interspec_p4c_slot* slot = &table->slots[slot_index];
  if (slot->kind == INTERSPEC_P4C_SLOT_INT)
    option->arg = &slot->value.i;
  else if (slot->kind == INTERSPEC_P4C_SLOT_STRING)
    option->arg = &slot->value.s;
  else
    return 0;

  return 1;
}

int interspec_p4c_option_set_strings(void* opaque,
                                     uint32_t index,
                                     char* long_name,
                                     char* description,
                                     char* arg_description)
{
  struct interspec_p4c_table* table = opaque;
  if (!table || index >= table->option_count) return 0;

  table->options[index].longName = long_name;
  table->options[index].descrip = description;
  table->options[index].argDescrip = arg_description;
  return 1;
}

int interspec_p4c_slot_get_int(void* opaque, uint32_t index)
{
  struct interspec_p4c_table* table = opaque;
  if (!table || index >= table->slot_count ||
      table->slots[index].kind != INTERSPEC_P4C_SLOT_INT)
    return 0;
  return table->slots[index].value.i;
}

char* interspec_p4c_slot_get_string(void* opaque, uint32_t index)
{
  struct interspec_p4c_table* table = opaque;
  if (!table || index >= table->slot_count ||
      table->slots[index].kind != INTERSPEC_P4C_SLOT_STRING)
    return NULL;
#ifdef INTERSPEC_FAULT_TESTS
  return inject_pointer(table->slots[index].value.s, 2);
#else
  return table->slots[index].value.s;
#endif
}

void* interspec_p4c_argv_new(uint32_t argc)
{
  struct interspec_p4c_argv* box = calloc(1, sizeof(*box));
  if (!box) return NULL;

  box->argv = calloc((size_t)argc + 1, sizeof(*box->argv));
  if (!box->argv) {
    free(box);
    return NULL;
  }

  box->argc = argc;
  return box;
}

int interspec_p4c_argv_set(void* opaque, uint32_t index, char* value)
{
  struct interspec_p4c_argv* box = opaque;
  if (!box || index >= box->argc) return 0;
  box->argv[index] = value;
  return 1;
}

void* interspec_p4c_context_new(char* name,
                                int argc,
                                void* argv_opaque,
                                void* table_opaque,
                                uint32_t flags)
{
  struct interspec_p4c_argv* argv = argv_opaque;
  struct interspec_p4c_table* table = table_opaque;
  if (!argv || !table || argc < 0 || (uint32_t)argc != argv->argc) return NULL;
  void* context = poptGetContext(name, argc, argv->argv, table->options, flags);
#ifdef INTERSPEC_FAULT_TESTS
  fault_context = context;
  fault_table = table;
#endif
  return context;
}

int interspec_p4c_next(void* opaque)
{
  int result = poptGetNextOpt((poptContext)opaque);
#ifdef INTERSPEC_FAULT_TESTS
  if (fault_mode == 6 && !fault_fired && fault_table) {
    for (uint32_t i = 0; i < fault_table->option_count; ++i)
      if (fault_table->options[i].arg)
        fault_table->options[i].arg = &fault_decoy;
    fault_fired = 1;
    fprintf(stderr, "FAULT_INJECTION mode=6 target=option_destination replacement=%p\n",
            (void*)&fault_decoy);
    fflush(stderr);
  }
#endif
  return result;
}

char* interspec_p4c_opt_arg(void* opaque)
{
  char* value = poptGetOptArg((poptContext)opaque);
#ifdef INTERSPEC_FAULT_TESTS
  return inject_pointer(value, 1);
#else
  return value;
#endif
}

char* interspec_p4c_bad_option(void* opaque, uint32_t flags)
{
  return (char*)poptBadOption((poptContext)opaque, flags);
}

uint32_t interspec_p4c_args_count(void* opaque)
{
  const char** args = poptGetArgs((poptContext)opaque);
  uint32_t count = 0;
  if (!args) return 0;
  while (args[count]) count++;
  return count;
}

char* interspec_p4c_args_at(void* opaque, uint32_t index)
{
  const char** args = poptGetArgs((poptContext)opaque);
  if (!args) return NULL;
  for (uint32_t i = 0; i < index; ++i)
    if (!args[i]) return NULL;
#ifdef INTERSPEC_FAULT_TESTS
  return inject_pointer((char*)args[index], 3);
#else
  return (char*)args[index];
#endif
}

void interspec_p4c_context_free(void* opaque)
{
  poptFreeContext((poptContext)opaque);
}

void interspec_p4c_table_free(void* opaque)
{
  struct interspec_p4c_table* table = opaque;
  if (!table) return;
  free(table->options);
  free(table->slots);
  free(table);
}

void interspec_p4c_argv_free(void* opaque)
{
  struct interspec_p4c_argv* argv = opaque;
  if (!argv) return;
  free(argv->argv);
  free(argv);
}
