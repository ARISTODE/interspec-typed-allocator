#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Sandbox ABI contract for the phase-1 real-isolation nginx/OpenSSL design.
 *
 * The host bridge should only exchange copied buffers and opaque numeric
 * handles with the sandbox. No raw SSL*, SSL_CTX*, BIO*, or X509* pointers may
 * cross the T/U boundary in this phase-1 design.
 */

typedef uint64_t ngx_openssl_phase1_sandbox_ctx_handle_t;
typedef uint64_t ngx_openssl_phase1_sandbox_conn_handle_t;
typedef uint32_t ngx_openssl_phase1_sandbox_size_t;
typedef int32_t ngx_openssl_phase1_sandbox_io_result_t;

enum
{
  NGX_OPENSSL_PHASE1_SANDBOX_INVALID_CTX_HANDLE = 0,
  NGX_OPENSSL_PHASE1_SANDBOX_INVALID_CONN_HANDLE = 0,
  NGX_OPENSSL_PHASE1_SANDBOX_IO_WANT_READ = -101,
  NGX_OPENSSL_PHASE1_SANDBOX_IO_WANT_WRITE = -102,
  NGX_OPENSSL_PHASE1_SANDBOX_IO_CLOSED = -103,
  NGX_OPENSSL_PHASE1_SANDBOX_IO_INVALID_ARGUMENT = -104,
  NGX_OPENSSL_PHASE1_SANDBOX_IO_INTERNAL_ERROR = -105,
};

typedef enum ngx_openssl_phase1_sandbox_status_e
{
  NGX_OPENSSL_PHASE1_SANDBOX_STATUS_OK = 0,
  NGX_OPENSSL_PHASE1_SANDBOX_STATUS_WANT_READ = 1,
  NGX_OPENSSL_PHASE1_SANDBOX_STATUS_WANT_WRITE = 2,
  NGX_OPENSSL_PHASE1_SANDBOX_STATUS_CLOSED = 3,
  NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INVALID_ARGUMENT = -1,
  NGX_OPENSSL_PHASE1_SANDBOX_STATUS_NOT_IMPLEMENTED = -2,
  NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR = -3,
} ngx_openssl_phase1_sandbox_status_t;

typedef struct ngx_openssl_phase1_sandbox_profile_s
{
  uint64_t copy_in_ns;
  uint64_t sandbox_ns;
  uint64_t copy_out_ns;
} ngx_openssl_phase1_sandbox_profile_t;

typedef struct ngx_openssl_phase1_sandbox_server_config_s
{
  const unsigned char* cert_pem;
  ngx_openssl_phase1_sandbox_size_t cert_pem_len;
  const unsigned char* key_pem;
  ngx_openssl_phase1_sandbox_size_t key_pem_len;
  const unsigned char* trusted_cert_pem;
  ngx_openssl_phase1_sandbox_size_t trusted_cert_pem_len;
  const char* ciphers;
  uint32_t min_tls_version;
  uint32_t max_tls_version;
  int session_tickets;
} ngx_openssl_phase1_sandbox_server_config_t;

/*
 * Process / sandbox lifetime.
 */
ngx_openssl_phase1_sandbox_status_t ngx_openssl_phase1_sandbox_init(void);
void ngx_openssl_phase1_sandbox_shutdown(void);
ngx_openssl_phase1_sandbox_status_t ngx_openssl_phase1_sandbox_seed_rng(
  const unsigned char* seed,
  ngx_openssl_phase1_sandbox_size_t seed_len);
int ngx_openssl_phase1_sandbox_rand_status(void);

/*
 * Sandbox-owned TLS context lifetime.
 */
ngx_openssl_phase1_sandbox_status_t ngx_openssl_phase1_sandbox_ctx_create_server(
  const ngx_openssl_phase1_sandbox_server_config_t* server_config,
  ngx_openssl_phase1_sandbox_ctx_handle_t* out_ctx);

/*
 * Bridge-friendly equivalent of ctx_create_server that avoids copying a
 * pointer-bearing host struct across the 64-bit host / 32-bit wasm boundary.
 */
ngx_openssl_phase1_sandbox_status_t
ngx_openssl_phase1_sandbox_ctx_create_server_flat(
  const unsigned char* cert_pem,
  ngx_openssl_phase1_sandbox_size_t cert_pem_len,
  const unsigned char* key_pem,
  ngx_openssl_phase1_sandbox_size_t key_pem_len,
  const unsigned char* trusted_cert_pem,
  ngx_openssl_phase1_sandbox_size_t trusted_cert_pem_len,
  const char* ciphers,
  uint32_t min_tls_version,
  uint32_t max_tls_version,
  int session_tickets,
  ngx_openssl_phase1_sandbox_ctx_handle_t* out_ctx);
void ngx_openssl_phase1_sandbox_ctx_destroy(
  ngx_openssl_phase1_sandbox_ctx_handle_t ctx);

/*
 * Sandbox-owned TLS connection lifetime.
 */
ngx_openssl_phase1_sandbox_status_t ngx_openssl_phase1_sandbox_conn_create(
  ngx_openssl_phase1_sandbox_ctx_handle_t ctx,
  ngx_openssl_phase1_sandbox_conn_handle_t* out_conn);
void ngx_openssl_phase1_sandbox_conn_destroy(
  ngx_openssl_phase1_sandbox_conn_handle_t conn);

/*
 * Encrypted data path.
 */
ngx_openssl_phase1_sandbox_status_t ngx_openssl_phase1_sandbox_conn_feed_encrypted(
  ngx_openssl_phase1_sandbox_conn_handle_t conn,
  const unsigned char* ciphertext,
  ngx_openssl_phase1_sandbox_size_t ciphertext_len,
  ngx_openssl_phase1_sandbox_size_t* bytes_consumed,
  ngx_openssl_phase1_sandbox_profile_t* profile);

ngx_openssl_phase1_sandbox_status_t ngx_openssl_phase1_sandbox_conn_drain_encrypted(
  ngx_openssl_phase1_sandbox_conn_handle_t conn,
  unsigned char* out_ciphertext,
  ngx_openssl_phase1_sandbox_size_t out_ciphertext_cap,
  ngx_openssl_phase1_sandbox_size_t* out_ciphertext_len,
  ngx_openssl_phase1_sandbox_profile_t* profile);

/*
 * Plaintext data path.
 */
ngx_openssl_phase1_sandbox_io_result_t ngx_openssl_phase1_sandbox_conn_read_plain(
  ngx_openssl_phase1_sandbox_conn_handle_t conn,
  unsigned char* out_plaintext,
  ngx_openssl_phase1_sandbox_size_t out_plaintext_cap,
  ngx_openssl_phase1_sandbox_profile_t* profile);

ngx_openssl_phase1_sandbox_io_result_t ngx_openssl_phase1_sandbox_conn_write_plain(
  ngx_openssl_phase1_sandbox_conn_handle_t conn,
  const unsigned char* plaintext,
  ngx_openssl_phase1_sandbox_size_t plaintext_len,
  ngx_openssl_phase1_sandbox_profile_t* profile);

/*
 * Handshake / shutdown.
 */
ngx_openssl_phase1_sandbox_status_t ngx_openssl_phase1_sandbox_conn_handshake_step(
  ngx_openssl_phase1_sandbox_conn_handle_t conn,
  ngx_openssl_phase1_sandbox_profile_t* profile);

ngx_openssl_phase1_sandbox_status_t ngx_openssl_phase1_sandbox_conn_shutdown(
  ngx_openssl_phase1_sandbox_conn_handle_t conn,
  ngx_openssl_phase1_sandbox_profile_t* profile);

/*
 * Session helpers for the benchmark's resumption path.
 */
ngx_openssl_phase1_sandbox_status_t ngx_openssl_phase1_sandbox_conn_export_session(
  ngx_openssl_phase1_sandbox_conn_handle_t conn,
  unsigned char* out_session,
  ngx_openssl_phase1_sandbox_size_t out_session_cap,
  ngx_openssl_phase1_sandbox_size_t* out_session_len);

ngx_openssl_phase1_sandbox_status_t ngx_openssl_phase1_sandbox_conn_import_session(
  ngx_openssl_phase1_sandbox_conn_handle_t conn,
  const unsigned char* session_bytes,
  ngx_openssl_phase1_sandbox_size_t session_len);

/*
 * Diagnostics.
 */
int ngx_openssl_phase1_sandbox_conn_last_ssl_error(
  ngx_openssl_phase1_sandbox_conn_handle_t conn);

unsigned long ngx_openssl_phase1_sandbox_last_err_code(void);
uint32_t ngx_openssl_phase1_sandbox_last_ctx_create_stage(void);
uint32_t ngx_openssl_phase1_sandbox_last_ssl_ctx_new_stage(void);
uint32_t ngx_openssl_phase1_sandbox_openssl_malloc_probe(
  ngx_openssl_phase1_sandbox_size_t size);

const char* ngx_openssl_phase1_sandbox_status_string(
  ngx_openssl_phase1_sandbox_status_t status);

#ifdef __cplusplus
}
#endif
