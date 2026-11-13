// Policy-switch test driver for rsync/popt (tracker item I1).
//
// Trusted (T) program linked against the same bridge object as the complete
// rsync executable, built with INTERSPEC_FAULT_TESTS so that U can misbehave on
// request. It uses the PoC 1 option table from the paper appendix and prints
// what T observes; tools/run_policy_switch_tests.py runs it once per switch
// setting and compares the observations. This program never decides pass/fail.
#include "popt.h"

#include <cstdio>
#include <cstring>

extern "C" int interspec_test_sandbox_contains(const char* needle);

static char* g_slot = nullptr;

int main() {
  std::setvbuf(stdout, nullptr, _IONBF, 0);

  struct poptOption options[] = {
    {"set", 's', POPT_ARG_STRING, &g_slot, 0, "SECRET_HELP", "SECRET_ARG"},
    {"readonly", 'r', POPT_ARG_NONE, nullptr, 42, nullptr, nullptr},
    POPT_TABLEEND,
  };
  const char* args[] = {"poc", "--set", "hello", "--readonly", nullptr};

  poptContext context = poptGetContext("poc", 4, args, options, 0);
  if (!context) {
    std::printf("T_OBSERVE stage=context result=null\n");
    return 3;
  }
  std::printf(
    "T_OBSERVE stage=context secret_help_in_u=%d secret_arg_in_u=%d "
    "readonly_val=%d\n",
    interspec_test_sandbox_contains("SECRET_HELP"),
    interspec_test_sandbox_contains("SECRET_ARG"),
    options[1].val);

  int rc;
  while ((rc = poptGetNextOpt(context)) >= 0)
    std::printf("T_OBSERVE stage=next rc=%d readonly_val=%d\n", rc,
                options[1].val);

  std::printf(
    "T_OBSERVE stage=done rc=%d g_slot=%s readonly_val=%d set_descrip=%s "
    "set_arg_descrip=%s\n",
    rc, g_slot ? g_slot : "(null)", options[1].val,
    options[0].descrip ? options[0].descrip : "(null)",
    options[0].argDescrip ? options[0].argDescrip : "(null)");

  poptFreeContext(context);
  return rc == -1 ? 0 : 2;
}
