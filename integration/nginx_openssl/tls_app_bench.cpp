// Trusted program for the nginx/openssl boundary (tracker item I10): the TLS
// server workload of tls_workload.h with OpenSSL inside an RLBox wasm2c
// sandbox behind the shim of the interspec-artifact wrapper. The client is
// ordinary OpenSSL in T.
//
// T-level interface: the functions of the artifact's ngx_openssl_phase1_bridge.h
// (feed_encrypted, drain_encrypted, read_plain, write_plain, handshake_step).
// By the artifact's design only copied buffers and numeric handles cross this
// boundary, so U returns no pointer to T.
#define RLBOX_USE_EXCEPTIONS
#define RLBOX_USE_STATIC_CALLS() rlbox_wasm2c_sandbox_lookup_symbol
#define RLBOX_WASM2C_MODULE_NAME glue__lib__wasm2c
#include "glue_lib_wasm2c.h"
#include "rlbox.hpp"
#include "rlbox_wasm2c_sandbox.hpp"

#include "interspec/boundary/wasm_port.h"
#include "tls_workload.h"

#include <openssl/rand.h>

extern "C" {
unsigned char* interspec_tls_stage(uint32_t, uint32_t);
int interspec_tls_init(uint32_t, uint32_t);
int interspec_tls_ctx_create(uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, int,
                             uint32_t);
int interspec_tls_conn_create(unsigned long long, uint32_t);
int interspec_tls_feed(unsigned long long, uint32_t, uint32_t, uint32_t);
int interspec_tls_drain(unsigned long long, uint32_t, uint32_t, uint32_t);
int interspec_tls_read(unsigned long long, uint32_t, uint32_t);
int interspec_tls_write(unsigned long long, uint32_t, uint32_t);
int interspec_tls_handshake(unsigned long long);
void interspec_tls_destroy(unsigned long long, unsigned long long);
#ifdef INTERSPEC_FAULT_TESTS
void interspec_tls_poc(uint32_t);
#endif
}

namespace {

struct TlsPolicy {
  static constexpr const char* boundary = "nginx_openssl";
  static constexpr int reject_exit = 86;
};
using Port = interspec::WasmPort<TlsPolicy>;

#if !INTERSPEC_CHECKS
constexpr const char* kVariant = "rlbox-only";
#else
constexpr const char* kVariant = "interspec";
#endif

constexpr size_t kMaxBytes = 1u << 20;

// invoke_sandbox_function is a macro that needs the function's name.
#define TLS_CALL(name, ...) \
  (port_.sandbox().invoke_sandbox_function(name, __VA_ARGS__).UNSAFE_unverified())

class SandboxServer {
 public:
  SandboxServer() : port_(0) {}
  ~SandboxServer() {
    try {
      port_.sandbox().invoke_sandbox_function(interspec_tls_destroy, conn_, ctx_);
    } catch (...) {
    }
  }
  Port& port() { return port_; }

  bool create(const std::string& cert, const std::string& key) {
    unsigned char seed[48];
    if (RAND_bytes(seed, sizeof(seed)) != 1) return false;
    unsigned char* in = stage(1, sizeof(seed));
    std::memcpy(in, seed, sizeof(seed));
    if (TLS_CALL(interspec_tls_init, port_.address_of(in), uint32_t{sizeof(seed)}) != 0)
      return false;
    unsigned char* cert_u = stage(3, static_cast<uint32_t>(cert.size()));
    unsigned char* key_u = stage(4, static_cast<uint32_t>(key.size()));
    std::memcpy(cert_u, cert.data(), cert.size());
    std::memcpy(key_u, key.data(), key.size());
    unsigned char* out = stage(0, 8);
    if (TLS_CALL(interspec_tls_ctx_create, port_.address_of(cert_u),
                 static_cast<uint32_t>(cert.size()), port_.address_of(key_u),
                 static_cast<uint32_t>(key.size()), uint32_t{TLS1_2_VERSION},
                 uint32_t{TLS1_3_VERSION}, 1, port_.address_of(out)) != 0)
      return false;
    std::memcpy(&ctx_, out, 8);
    out = stage(0, 8);
    if (TLS_CALL(interspec_tls_conn_create, ctx_, port_.address_of(out)) != 0) return false;
    std::memcpy(&conn_, out, 8);
    return ctx_ != 0 && conn_ != 0;
  }

  int feed_encrypted(unsigned char* data, size_t len, size_t* consumed) {
    if (len == 0 || len > kMaxBytes) return -1;
    unsigned char* in = stage(1, static_cast<uint32_t>(len));
    std::memcpy(in, data, len);
    // T's current value of the out-parameter is copied in.
    uint32_t count = static_cast<uint32_t>(*consumed);
    unsigned char* out = stage(0, 8);
    std::memcpy(out, &count, 4);
    const int rc = TLS_CALL(interspec_tls_feed, conn_, port_.address_of(in),
                            static_cast<uint32_t>(len), port_.address_of(out));
    // U's version of the ciphertext is copied back over T's.
    std::memcpy(data, in, len);
    std::memcpy(&count, out, 4);
    if (count > len) Port::reject("feed_encrypted", "count");
    *consumed = count;
    return rc;
  }

  int drain_encrypted(unsigned char* out_ciphertext, size_t cap, size_t* out_len) {
    if (cap == 0 || cap > kMaxBytes) return -1;
    unsigned char* buffer = stage(2, static_cast<uint32_t>(cap));
    // T's current contents of the output buffer and of the out-parameter are
    // copied in.
    std::memcpy(buffer, out_ciphertext, cap);
    uint32_t count = static_cast<uint32_t>(*out_len);
    unsigned char* out = stage(0, 8);
    std::memcpy(out, &count, 4);
    const int rc = TLS_CALL(interspec_tls_drain, conn_, port_.address_of(buffer),
                            static_cast<uint32_t>(cap), port_.address_of(out));
    std::memcpy(&count, out, 4);
    if (count > cap) Port::reject("drain_encrypted", "count");
    std::memcpy(out_ciphertext, buffer, count);
    *out_len = count;
    return rc;
  }

  long read_plain(unsigned char* out_plaintext, size_t cap) {
    if (cap == 0 || cap > kMaxBytes) return -1;
    unsigned char* buffer = stage(2, static_cast<uint32_t>(cap));
    // T's current contents of the output buffer are copied in.
    std::memcpy(buffer, out_plaintext, cap);
    const int rc =
        TLS_CALL(interspec_tls_read, conn_, port_.address_of(buffer), static_cast<uint32_t>(cap));
    if (rc > 0) {
      if (static_cast<size_t>(rc) > cap) Port::reject("read_plain", "count");
      std::memcpy(out_plaintext, buffer, static_cast<size_t>(rc));
    }
    return rc;
  }

  long write_plain(unsigned char* plaintext, size_t len) {
    if (len == 0 || len > kMaxBytes) return -1;
    unsigned char* in = stage(1, static_cast<uint32_t>(len));
    std::memcpy(in, plaintext, len);
    const int rc =
        TLS_CALL(interspec_tls_write, conn_, port_.address_of(in), static_cast<uint32_t>(len));
    // U's version of the plaintext is copied back over T's.
    std::memcpy(plaintext, in, len);
    if (rc > 0 && static_cast<size_t>(rc) > len) Port::reject("write_plain", "count");
    return rc;
  }

  int handshake_step() { return TLS_CALL(interspec_tls_handshake, conn_); }

 private:
  unsigned char* stage(uint32_t which, uint32_t bytes) {
    return port_.input_buffer(
        port_.sandbox().invoke_sandbox_function(interspec_tls_stage, which, bytes), bytes,
        "stage");
  }

  Port port_;
  unsigned long long ctx_ = 0, conn_ = 0;
};

}  // namespace

int main(int argc, char** argv) {
  if (argc != 4) {
    std::fprintf(stderr, "usage: %s REQUEST_BYTES RESPONSE_BYTES ROUNDS\n", argv[0]);
    return 2;
  }
  try {
    const size_t request_bytes = std::stoul(argv[1]), response_bytes = std::stoul(argv[2]);
    const unsigned rounds = static_cast<unsigned>(std::stoul(argv[3]));
    if (!request_bytes || !response_bytes || !rounds || request_bytes > kMaxBytes ||
        response_bytes > kMaxBytes)
      throw std::runtime_error("arguments");
    SandboxServer server;
#ifdef INTERSPEC_FAULT_TESTS
    if (const char* poc = std::getenv("INTERSPEC_TEST_POC_FLAGS"))
      server.port().sandbox().invoke_sandbox_function(
          interspec_tls_poc, static_cast<uint32_t>(std::stoul(poc)));
#endif
    const auto result = tls_workload::run(server, rounds, request_bytes, response_bytes);
#ifdef INTERSPEC_FAULT_TESTS
    // What T's own copy of the last response looks like after the run.
    std::fprintf(stderr, "INTERSPEC_T_OBSERVE boundary=nginx_openssl response_first_byte=0x%02x\n",
                 static_cast<unsigned>(result.response_first_byte));
#endif
    tls_workload::print(kVariant, rounds, request_bytes, response_bytes, result,
                        server.port().checks());
    return 0;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "tls benchmark error: %s\n", error.what());
    return 1;
  }
}
