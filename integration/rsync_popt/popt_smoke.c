#include "popt.h"

static int archive_seen;

static const struct poptOption options[] = {
  {"archive", 'a', POPT_ARG_NONE, &archive_seen, 0, 0, 0},
  POPT_TABLEEND
};

void* interspec_popt_parse_smoke(void)
{
  const char* argv[] = {"rsync", "--archive", 0};
  archive_seen = 0;

  poptContext ctx = poptGetContext("rsync", 2, argv, options, 0);
  if (!ctx) return 0;

  if (poptGetNextOpt(ctx) < -1) return 0;
  return ctx;
}

int interspec_popt_archive_seen(void)
{
  return archive_seen;
}
