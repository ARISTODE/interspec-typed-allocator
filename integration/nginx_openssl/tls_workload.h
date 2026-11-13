// Workload shared by tls_app_bench.cpp and tls_native_bench.cpp (tracker item
// I10), after the artifact's smoke tests (tests/phase1_native_smoke.c): a TLS
// server whose OpenSSL state lives behind the artifact's shim talks to an
// ordinary OpenSSL client in the same process through memory BIOs. After the
// handshake the client sends `rounds` requests and the server answers each.
//
// Server is the trusted-side view of the shim (the functions of
// ngx_openssl_phase1_bridge.h):
//   bool create(cert_pem, key_pem)
//   int  feed_encrypted(unsigned char*, size_t, size_t* consumed)
//   int  drain_encrypted(unsigned char* out, size_t cap, size_t* out_len)
//   long read_plain(unsigned char* out, size_t cap)
//   long write_plain(unsigned char* plaintext, size_t len)
//   int  handshake_step()
#pragma once

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

#include <openssl/bio.h>
#include <openssl/ec.h>
#include <openssl/evp.h>
#include <openssl/pem.h>
#include <openssl/ssl.h>
#include <openssl/x509.h>

namespace tls_workload {

enum { kStatusOk = 0, kStatusWantRead = 1, kStatusWantWrite = 2 };

struct Fnv {
  uint64_t state = UINT64_C(1469598103934665603);
  void add(const unsigned char* p, size_t n) {
    for (size_t i = 0; i < n; i++) {
      state ^= p[i];
      state *= UINT64_C(1099511628211);
    }
  }
};

inline std::string bio_to_string(BIO* bio) {
  char* data = nullptr;
  const long size = BIO_get_mem_data(bio, &data);
  std::string out(data, static_cast<size_t>(size));
  BIO_free(bio);
  return out;
}

// A fresh P-256 key and a self-signed certificate for the server.
inline void make_identity(std::string& cert_pem, std::string& key_pem) {
  EVP_PKEY_CTX* kctx = EVP_PKEY_CTX_new_id(EVP_PKEY_EC, nullptr);
  EVP_PKEY* key = nullptr;
  if (!kctx || EVP_PKEY_keygen_init(kctx) != 1 ||
      EVP_PKEY_CTX_set_ec_paramgen_curve_nid(kctx, NID_X9_62_prime256v1) != 1 ||
      EVP_PKEY_keygen(kctx, &key) != 1)
    throw std::runtime_error("keygen");
  EVP_PKEY_CTX_free(kctx);
  X509* cert = X509_new();
  X509_set_version(cert, 2);
  ASN1_INTEGER_set(X509_get_serialNumber(cert), 1);
  X509_gmtime_adj(X509_getm_notBefore(cert), -3600);
  X509_gmtime_adj(X509_getm_notAfter(cert), 24 * 3600);
  X509_set_pubkey(cert, key);
  X509_NAME* name = X509_get_subject_name(cert);
  X509_NAME_add_entry_by_txt(name, "CN", MBSTRING_ASC,
                             reinterpret_cast<const unsigned char*>("interspec.test"), -1, -1,
                             0);
  X509_set_issuer_name(cert, name);
  if (X509_sign(cert, key, EVP_sha256()) == 0) throw std::runtime_error("x509_sign");
  BIO* cert_bio = BIO_new(BIO_s_mem());
  BIO* key_bio = BIO_new(BIO_s_mem());
  if (PEM_write_bio_X509(cert_bio, cert) != 1 ||
      PEM_write_bio_PrivateKey(key_bio, key, nullptr, nullptr, 0, nullptr, nullptr) != 1)
    throw std::runtime_error("pem");
  cert_pem = bio_to_string(cert_bio);
  key_pem = bio_to_string(key_bio);
  X509_free(cert);
  EVP_PKEY_free(key);
}

template <class Server> bool pump_client_to_server(SSL* client, Server& server) {
  unsigned char buf[4096];
  for (;;) {
    int pending = static_cast<int>(BIO_ctrl_pending(SSL_get_wbio(client)));
    if (pending <= 0) return true;
    while (pending > 0) {
      const int chunk = pending > static_cast<int>(sizeof(buf)) ? sizeof(buf) : pending;
      const int n = BIO_read(SSL_get_wbio(client), buf, chunk);
      if (n <= 0) return false;
      size_t consumed = 0;
      if (server.feed_encrypted(buf, static_cast<size_t>(n), &consumed) != kStatusOk ||
          consumed != static_cast<size_t>(n))
        return false;
      pending -= n;
    }
  }
}

template <class Server> bool pump_server_to_client(Server& server, SSL* client) {
  unsigned char buf[4096];
  for (;;) {
    size_t out_len = 0;
    if (server.drain_encrypted(buf, sizeof(buf), &out_len) != kStatusOk) return false;
    if (out_len == 0) return true;
    if (BIO_write(SSL_get_rbio(client), buf, static_cast<int>(out_len)) !=
        static_cast<int>(out_len))
      return false;
  }
}

template <class Server> bool drive_handshake(SSL* client, Server& server) {
  for (int i = 0; i < 128; ++i) {
    const int client_rc = SSL_do_handshake(client);
    const int client_err = client_rc == 1 ? SSL_ERROR_NONE : SSL_get_error(client, client_rc);
    const int server_status = server.handshake_step();
    if (!pump_client_to_server(client, server) || !pump_server_to_client(server, client))
      return false;
    if (SSL_is_init_finished(client) && server_status == kStatusOk) return true;
    if (client_rc != 1 && client_err != SSL_ERROR_WANT_READ &&
        client_err != SSL_ERROR_WANT_WRITE)
      return false;
    if (server_status != kStatusOk && server_status != kStatusWantRead &&
        server_status != kStatusWantWrite)
      return false;
  }
  return false;
}

struct Result {
  std::string version, cipher;
  uint64_t server_received_fnv = 0, client_received_fnv = 0;
  uint64_t elapsed_ns = 0;
  unsigned char response_first_byte = 0;  // of T's own response buffer, after the run
};

// Deterministic payload bytes for round `round` in direction `salt`.
inline void fill(std::vector<unsigned char>& data, size_t size, unsigned round,
                 unsigned salt) {
  data.resize(size);
  for (size_t i = 0; i < size; ++i)
    data[i] = static_cast<unsigned char>('A' + (i * 7 + round * 13 + salt) % 26);
}

template <class Server>
Result run(Server& server, unsigned rounds, size_t request_bytes, size_t response_bytes) {
  if (OPENSSL_init_ssl(0, nullptr) != 1) throw std::runtime_error("init_ssl");
  std::string cert_pem, key_pem;
  make_identity(cert_pem, key_pem);
  if (!server.create(cert_pem, key_pem)) throw std::runtime_error("server_create");

  SSL_CTX* client_ctx = SSL_CTX_new(TLS_client_method());
  if (!client_ctx) throw std::runtime_error("client_ctx");
  SSL_CTX_set_verify(client_ctx, SSL_VERIFY_NONE, nullptr);
  SSL* client = SSL_new(client_ctx);
  BIO* rbio = BIO_new(BIO_s_mem());
  BIO* wbio = BIO_new(BIO_s_mem());
  if (!client || !rbio || !wbio) throw std::runtime_error("client");
  BIO_set_mem_eof_return(rbio, -1);
  BIO_set_mem_eof_return(wbio, -1);
  SSL_set_bio(client, rbio, wbio);
  SSL_set_connect_state(client);

  Result result;
  Fnv server_received, client_received;
  std::vector<unsigned char> request, response;
  // T's receive buffer starts out holding older data of T.
  std::vector<unsigned char> server_in(request_bytes);
  for (size_t i = 0; i < server_in.size(); ++i) server_in[i] = "T_STALE_"[i % 8];
  std::vector<unsigned char> client_in(response_bytes);

  const auto start = std::chrono::steady_clock::now();
  if (!drive_handshake(client, server)) throw std::runtime_error("handshake");
  for (unsigned round = 0; round < rounds; ++round) {
    fill(request, request_bytes, round, 0);
    if (SSL_write(client, request.data(), static_cast<int>(request.size())) !=
        static_cast<int>(request.size()))
      throw std::runtime_error("client_write");
    if (!pump_client_to_server(client, server)) throw std::runtime_error("pump_request");
    size_t got = 0;
    while (got < request_bytes) {
      const long n = server.read_plain(server_in.data() + got, request_bytes - got);
      if (n <= 0) throw std::runtime_error("server_read");
      got += static_cast<size_t>(n);
    }
    server_received.add(server_in.data(), got);

    fill(response, response_bytes, round, 5);
    size_t sent = 0;
    while (sent < response_bytes) {
      const long n = server.write_plain(response.data() + sent, response_bytes - sent);
      if (n <= 0) throw std::runtime_error("server_write");
      sent += static_cast<size_t>(n);
      if (!pump_server_to_client(server, client)) throw std::runtime_error("pump_response");
    }
    got = 0;
    while (got < response_bytes) {
      const int n = SSL_read(client, client_in.data() + got,
                             static_cast<int>(response_bytes - got));
      if (n <= 0) throw std::runtime_error("client_read");
      got += static_cast<size_t>(n);
    }
    client_received.add(client_in.data(), got);
  }
  const auto finish = std::chrono::steady_clock::now();

  result.version = SSL_get_version(client);
  result.cipher = SSL_get_cipher_name(client);
  result.server_received_fnv = server_received.state;
  result.client_received_fnv = client_received.state;
  result.response_first_byte = response.empty() ? 0 : response[0];
  result.elapsed_ns = static_cast<uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(finish - start).count());
  SSL_free(client);
  SSL_CTX_free(client_ctx);
  return result;
}

inline void print(const char* variant, unsigned rounds, size_t request_bytes,
                  size_t response_bytes, const Result& r, unsigned long long checks) {
  std::printf(
      "TLS_BENCH variant=%s rounds=%u request_bytes=%zu response_bytes=%zu version=%s "
      "cipher=%s server_received_fnv=%016llx client_received_fnv=%016llx checks=%llu "
      "elapsed_ns=%llu\n",
      variant, rounds, request_bytes, response_bytes, r.version.c_str(), r.cipher.c_str(),
      static_cast<unsigned long long>(r.server_received_fnv),
      static_cast<unsigned long long>(r.client_received_fnv), checks,
      static_cast<unsigned long long>(r.elapsed_ns));
}

}  // namespace tls_workload
