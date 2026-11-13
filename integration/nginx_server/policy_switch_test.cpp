// Policy-switch test driver for nginx/libpcre (tracker item I4).
//
// Trusted (T) program linked against the server's bridge source and the
// fault-test U module. It makes the PCRE 8.45 calls nginx makes for a regex
// location and prints what T observes; tools/run_policy_switch_tests.py runs it
// once per switch setting and compares the observations. This program never
// decides pass/fail.
#include <cstdio>
#include <cstring>

#include "pcre.h"

extern "C" void interspec_nginx_release(void*);

int main() {
  std::setvbuf(stdout, nullptr, _IONBF, 0);

  const char* error = nullptr;
  int error_offset = 0;
  pcre* code = pcre_compile("^/items/([0-9]+)/([a-z]+)$", 0, &error,
                            &error_offset, nullptr);
  std::printf("T_OBSERVE stage=compile result=%s\n", code ? "ok" : "failed");
  if (!code) return 3;

  // SP2: the subject is read by U and never written by it.
  char subject[] = "/items/123/alpha";
  const int length = static_cast<int>(sizeof(subject) - 1);
  // SP1: the output vector is written by U and never read by it. T's values
  // before the call stand for whatever T had there.
  int ovector[9];
  for (int& value : ovector) value = 0x5ec2e7;

  const int rc = pcre_exec(code, nullptr, subject, length, 0, 0, ovector, 9);
  std::printf("T_OBSERVE stage=exec rc=%d subject=", rc);
  for (int i = 0; i < length; ++i)
    std::printf("%02x", static_cast<unsigned char>(subject[i]));
  std::printf(" captures=");
  for (int i = 0; i < (rc > 0 ? rc : 0); ++i)
    std::printf("%s%d-%d", i ? "," : "", ovector[2 * i], ovector[2 * i + 1]);
  std::printf("\n");

  interspec_nginx_release(code);
  std::printf("T_OBSERVE stage=done\n");
  return rc == 3 ? 0 : 2;
}
