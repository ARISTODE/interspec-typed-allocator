// Native reference for the nginx/openssl port (tracker item I10): the workload
// of tls_workload.h against the artifact's shim compiled without a sandbox.
#include "tls_workload.h"

extern "C" {
#include "benchmarks/nginx/src/event/rlbox/ngx_openssl_phase1_sandbox_abi.h"
}

namespace {
class NativeServer {
 public:
  ~NativeServer() {
    ngx_openssl_phase1_sandbox_conn_destroy(conn_);
    ngx_openssl_phase1_sandbox_ctx_destroy(ctx_);
    ngx_openssl_phase1_sandbox_shutdown();
  }
  bool create(const std::string& cert, const std::string& key) {
    if (ngx_openssl_phase1_sandbox_init() != 0) return false;
    if (ngx_openssl_phase1_sandbox_ctx_create_server_flat(
            reinterpret_cast<const unsigned char*>(cert.data()),
            static_cast<uint32_t>(cert.size()),
            reinterpret_cast<const unsigned char*>(key.data()),
            static_cast<uint32_t>(key.size()), nullptr, 0, nullptr, TLS1_2_VERSION,
            TLS1_3_VERSION, 1, &ctx_) != 0)
      return false;
    return ngx_openssl_phase1_sandbox_conn_create(ctx_, &conn_) == 0;
  }
  int feed_encrypted(unsigned char* data, size_t len, size_t* consumed) {
    ngx_openssl_phase1_sandbox_size_t n = 0;
    const int rc = ngx_openssl_phase1_sandbox_conn_feed_encrypted(
        conn_, data, static_cast<uint32_t>(len), &n, nullptr);
    *consumed = n;
    return rc;
  }
  int drain_encrypted(unsigned char* out, size_t cap, size_t* out_len) {
    ngx_openssl_phase1_sandbox_size_t n = 0;
    const int rc = ngx_openssl_phase1_sandbox_conn_drain_encrypted(
        conn_, out, static_cast<uint32_t>(cap), &n, nullptr);
    *out_len = n;
    return rc;
  }
  long read_plain(unsigned char* out, size_t cap) {
    return ngx_openssl_phase1_sandbox_conn_read_plain(conn_, out, static_cast<uint32_t>(cap),
                                                      nullptr);
  }
  long write_plain(unsigned char* data, size_t len) {
    return ngx_openssl_phase1_sandbox_conn_write_plain(conn_, data,
                                                       static_cast<uint32_t>(len), nullptr);
  }
  int handshake_step() {
    return ngx_openssl_phase1_sandbox_conn_handshake_step(conn_, nullptr);
  }

 private:
  ngx_openssl_phase1_sandbox_ctx_handle_t ctx_ = 0;
  ngx_openssl_phase1_sandbox_conn_handle_t conn_ = 0;
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
    if (!request_bytes || !response_bytes || !rounds || request_bytes > (1u << 20) ||
        response_bytes > (1u << 20))
      throw std::runtime_error("arguments");
    NativeServer server;
    const auto result = tls_workload::run(server, rounds, request_bytes, response_bytes);
    tls_workload::print("native", rounds, request_bytes, response_bytes, result, 0);
    return 0;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "tls benchmark error: %s\n", error.what());
    return 1;
  }
}
