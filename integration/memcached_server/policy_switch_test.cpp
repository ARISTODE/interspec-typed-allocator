// Policy-switch test driver for memcached/bipbuffer (tracker item I2).
//
// Trusted (T) program linked against the server's bridge source and the
// fault-test U module. It makes the calls the memcached logger makes and prints
// what T observes; tools/run_policy_switch_tests.py runs it once per switch
// setting and compares the observations. This program never decides pass/fail.
#include <cstdio>
#include <cstring>

extern "C" {
#include "bipbuffer.h"
void interspec_bipbuf_role(bipbuf_t*, unsigned int);
}

static void hex(const char* label, const unsigned char* bytes, unsigned count) {
  std::printf(" %s=", label);
  for (unsigned i = 0; i < count; ++i) std::printf("%02x", bytes[i]);
}

int main() {
  std::setvbuf(stdout, nullptr, _IONBF, 0);

  bipbuf_t* buffer = bipbuf_new(4096);
  if (!buffer) {
    std::printf("T_OBSERVE stage=new result=null\n");
    return 3;
  }
  interspec_bipbuf_role(buffer, 1);

  // SP2: `data` of bipbuf_offer is read by U and never written by it.
  unsigned char record[16];
  std::memcpy(record, "T_RECORD_0123456", sizeof(record));
  const int written = bipbuf_offer(buffer, record, sizeof(record));
  std::printf("T_OBSERVE stage=offer written=%d", written);
  hex("record", record, sizeof(record));
  std::printf("\n");

  // SP1: the length out-parameter of bipbuf_peek_all is written by U and never
  // read by it. T's value before the call stands for whatever T had there.
  unsigned int size = 0x5ec2e7u;
  const unsigned char* data = bipbuf_peek_all(buffer, &size);
  std::printf("T_OBSERVE stage=peek_all size=%u", size);
  if (data && size <= sizeof(record)) hex("data", data, size);
  std::printf("\n");

  const unsigned char* polled = bipbuf_poll(buffer, size);
  std::printf("T_OBSERVE stage=poll returned=%d empty=%d\n", polled != nullptr,
              bipbuf_is_empty(buffer));

  bipbuf_free(buffer);
  std::printf("T_OBSERVE stage=done\n");
  return 0;
}
