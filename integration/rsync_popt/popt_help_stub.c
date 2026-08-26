#include "popt.h"

/* The rsync smoke path does not use popt's host-oriented help printer. */
struct poptOption poptHelpOptions[] = {
    POPT_TABLEEND
};

struct poptOption *poptHelpOptionsI18N = poptHelpOptions;
