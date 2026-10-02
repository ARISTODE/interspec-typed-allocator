#include "popt.h"
#include <cstdint>
#include <cstdio>
#include <cstring>

// Uses the exact application bridge and the real sandboxed popt parser.
// U rewrites option.arg after parsing; the private T binding must remain fixed.
static int refresh_regression() {
  int counter = 42;
  char initial[] = "first";
  char* text = initial;
  const char* argv[] = {"shadow-refresh", "--yield", "--yield", nullptr};
  const poptOption options[] = {
    {"yield", 0, POPT_ARG_NONE, nullptr, 77, nullptr, nullptr},
    {"counter", 0, POPT_ARG_INT, &counter, 0, nullptr, nullptr},
    {"text", 0, POPT_ARG_STRING, &text, 0, nullptr, nullptr},
    {nullptr, 0, 0, nullptr, 0, nullptr, nullptr},
  };
  auto context = poptGetContext("shadow-refresh", 3, argv, options, 0);
  if (!context || poptGetNextOpt(context) != 77) return 1;
  counter = 99;
  text[0] = 'F'; // In-place T mutation must refresh even with the same pointer.
  const bool pass = poptGetNextOpt(context) == 77 && counter == 99 &&
                    std::strcmp(text, "First") == 0;
  std::printf("shadow_refresh=%s counter=%d text=%s\n", pass ? "pass" : "fail", counter, text);
  poptFreeContext(context);
  return pass ? 0 : 1;
}

int main(int argc, char** argv_in) {
  if (argc == 2 && std::strcmp(argv_in[1], "refresh") == 0) return refresh_regression();
  struct {
    uint64_t before;
    char* destination;
    uint64_t after;
  } value{0x123456789abcdef0ULL, nullptr, 0xfedcba9876543210ULL};
  const char* argv[] = {"copyback-canary", "--output=expected", nullptr};
  const poptOption options[] = {
    {"output", 0, POPT_ARG_STRING, &value.destination, 77, nullptr, nullptr},
    {nullptr, 0, 0, nullptr, 0, nullptr, nullptr},
  };
  auto context = poptGetContext("copyback-canary", 2, argv, options, 0);
  if (!context || poptGetNextOpt(context) != 77) return 1;
  const bool pass = value.destination &&
      std::strcmp(value.destination, "expected") == 0 &&
      value.before == 0x123456789abcdef0ULL &&
      value.after == 0xfedcba9876543210ULL;
  std::printf("copyback_canary=%s destination_value=%s guards_unchanged=%s\n",
              pass ? "pass" : "fail", value.destination ? value.destination : "null",
              pass ? "true" : "false");
  poptFreeContext(context);
  return pass ? 0 : 1;
}
