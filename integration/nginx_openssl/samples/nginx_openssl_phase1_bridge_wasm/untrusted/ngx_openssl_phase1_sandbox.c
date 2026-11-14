#include "../../../benchmarks/nginx/src/event/rlbox/ngx_openssl_phase1_sandbox_abi.h"

#include <limits.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include <openssl/err.h>
#include <openssl/pem.h>
#include <openssl/rand.h>
#include <openssl/ssl.h>

extern unsigned int ossl_debug_ssl_ctx_new_stage(void);
#include <openssl/x509.h>

typedef struct ctx_entry_s
{
  ngx_openssl_phase1_sandbox_ctx_handle_t handle;
  SSL_CTX* ctx;
  struct ctx_entry_s* next;
} ctx_entry_t;

typedef struct conn_entry_s
{
  ngx_openssl_phase1_sandbox_conn_handle_t handle;
  SSL* ssl;
  int last_ssl_error;
  struct conn_entry_s* next;
} conn_entry_t;

static ctx_entry_t* g_ctx_entries = NULL;
static conn_entry_t* g_conn_entries = NULL;
static ngx_openssl_phase1_sandbox_ctx_handle_t g_next_ctx_handle = 1;
static ngx_openssl_phase1_sandbox_conn_handle_t g_next_conn_handle = 1;
static int g_initialized = 0;
static uint32_t g_last_ctx_create_stage = 0;

static void
clear_profile(ngx_openssl_phase1_sandbox_profile_t* profile)
{
  if (profile != NULL) {
    memset(profile, 0, sizeof(*profile));
  }
}

static ngx_openssl_phase1_sandbox_status_t
translate_ssl_error(int err)
{
  switch (err) {
    case SSL_ERROR_WANT_READ:
      return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_WANT_READ;
    case SSL_ERROR_WANT_WRITE:
      return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_WANT_WRITE;
    case SSL_ERROR_ZERO_RETURN:
      return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_CLOSED;
    default:
      return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
  }
}

static int
fits_in_int(ngx_openssl_phase1_sandbox_size_t len)
{
  return len <= (size_t) INT_MAX;
}

static ctx_entry_t*
find_ctx_entry(ngx_openssl_phase1_sandbox_ctx_handle_t handle)
{
  ctx_entry_t* cur = g_ctx_entries;
  while (cur != NULL) {
    if (cur->handle == handle) {
      return cur;
    }
    cur = cur->next;
  }
  return NULL;
}

static conn_entry_t*
find_conn_entry(ngx_openssl_phase1_sandbox_conn_handle_t handle)
{
  conn_entry_t* cur = g_conn_entries;
  while (cur != NULL) {
    if (cur->handle == handle) {
      return cur;
    }
    cur = cur->next;
  }
  return NULL;
}

static void
free_ctx_entries(void)
{
  ctx_entry_t* cur = g_ctx_entries;
  while (cur != NULL) {
    ctx_entry_t* next = cur->next;
    if (cur->ctx != NULL) {
      SSL_CTX_free(cur->ctx);
    }
    free(cur);
    cur = next;
  }
  g_ctx_entries = NULL;
}

static void
free_conn_entries(void)
{
  conn_entry_t* cur = g_conn_entries;
  while (cur != NULL) {
    conn_entry_t* next = cur->next;
    if (cur->ssl != NULL) {
      SSL_free(cur->ssl);
    }
    free(cur);
    cur = next;
  }
  g_conn_entries = NULL;
}

static void
remove_ctx_entry(ngx_openssl_phase1_sandbox_ctx_handle_t handle)
{
  ctx_entry_t** cur = &g_ctx_entries;
  while (*cur != NULL) {
    if ((*cur)->handle == handle) {
      ctx_entry_t* victim = *cur;
      *cur = victim->next;
      if (victim->ctx != NULL) {
        SSL_CTX_free(victim->ctx);
      }
      free(victim);
      return;
    }
    cur = &(*cur)->next;
  }
}

static void
remove_conn_entry(ngx_openssl_phase1_sandbox_conn_handle_t handle)
{
  conn_entry_t** cur = &g_conn_entries;
  while (*cur != NULL) {
    if ((*cur)->handle == handle) {
      conn_entry_t* victim = *cur;
      *cur = victim->next;
      if (victim->ssl != NULL) {
        SSL_free(victim->ssl);
      }
      free(victim);
      return;
    }
    cur = &(*cur)->next;
  }
}

static int
load_server_certificate_chain(SSL_CTX* ctx,
                              const unsigned char* pem,
                              size_t pem_len)
{
  BIO* bio = NULL;
  X509* cert = NULL;

  if (ctx == NULL || pem == NULL || pem_len == 0 || !fits_in_int(pem_len)) {
    return 0;
  }

  bio = BIO_new_mem_buf((const void*) pem, (int) pem_len);
  if (bio == NULL) {
    return 0;
  }

  cert = PEM_read_bio_X509_AUX(bio, NULL, NULL, NULL);
  if (cert == NULL) {
    BIO_free(bio);
    return 0;
  }

  if (SSL_CTX_use_certificate(ctx, cert) != 1) {
    X509_free(cert);
    BIO_free(bio);
    return 0;
  }
  X509_free(cert);
  cert = NULL;

  for (;;) {
    X509* extra = PEM_read_bio_X509(bio, NULL, NULL, NULL);
    if (extra == NULL) {
      ERR_clear_error();
      break;
    }
    if (SSL_CTX_add_extra_chain_cert(ctx, extra) != 1) {
      X509_free(extra);
      BIO_free(bio);
      return 0;
    }
  }

  BIO_free(bio);
  return 1;
}

static int
load_private_key(SSL_CTX* ctx, const unsigned char* pem, size_t pem_len)
{
  BIO* bio = NULL;
  EVP_PKEY* pkey = NULL;
  int ok = 0;

  if (ctx == NULL || pem == NULL || pem_len == 0 || !fits_in_int(pem_len)) {
    return 0;
  }

  bio = BIO_new_mem_buf((const void*) pem, (int) pem_len);
  if (bio == NULL) {
    return 0;
  }

  pkey = PEM_read_bio_PrivateKey(bio, NULL, NULL, NULL);
  if (pkey == NULL) {
    goto done;
  }

  if (SSL_CTX_use_PrivateKey(ctx, pkey) != 1) {
    goto done;
  }

  if (SSL_CTX_check_private_key(ctx) != 1) {
    goto done;
  }

  ok = 1;

done:
  if (pkey != NULL) {
    EVP_PKEY_free(pkey);
  }
  if (bio != NULL) {
    BIO_free(bio);
  }
  return ok;
}

static int
load_trusted_certificates(SSL_CTX* ctx,
                          const unsigned char* pem,
                          size_t pem_len)
{
  BIO* bio = NULL;
  X509_STORE* store = NULL;
  int loaded = 0;

  if (ctx == NULL || pem == NULL || pem_len == 0 || !fits_in_int(pem_len)) {
    return 0;
  }

  bio = BIO_new_mem_buf((const void*) pem, (int) pem_len);
  if (bio == NULL) {
    return 0;
  }

  store = SSL_CTX_get_cert_store(ctx);
  if (store == NULL) {
    BIO_free(bio);
    return 0;
  }

  for (;;) {
    X509* cert = PEM_read_bio_X509(bio, NULL, NULL, NULL);
    if (cert == NULL) {
      ERR_clear_error();
      break;
    }
    if (X509_STORE_add_cert(store, cert) == 1) {
      loaded++;
    } else {
      ERR_clear_error();
    }
    X509_free(cert);
  }

  BIO_free(bio);
  return loaded > 0;
}

static ngx_openssl_phase1_sandbox_status_t
status_from_ssl_rc(conn_entry_t* conn, int rc)
{
  conn->last_ssl_error = SSL_get_error(conn->ssl, rc);
  return translate_ssl_error(conn->last_ssl_error);
}

static ngx_openssl_phase1_sandbox_status_t
status_from_bio_read(BIO* bio, int rc)
{
  if (rc > 0) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_OK;
  }

  if (bio != NULL && BIO_should_retry(bio)) {
    if (BIO_should_write(bio)) {
      return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_WANT_WRITE;
    }

    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_WANT_READ;
  }

  if (bio != NULL && BIO_eof(bio)) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_CLOSED;
  }

  ERR_clear_error();
  return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
}

static ngx_openssl_phase1_sandbox_io_result_t
io_result_from_ssl_rc(conn_entry_t* conn, int rc)
{
  ngx_openssl_phase1_sandbox_status_t status;

  status = status_from_ssl_rc(conn, rc);

  switch (status) {
    case NGX_OPENSSL_PHASE1_SANDBOX_STATUS_WANT_READ:
      return NGX_OPENSSL_PHASE1_SANDBOX_IO_WANT_READ;
    case NGX_OPENSSL_PHASE1_SANDBOX_STATUS_WANT_WRITE:
      return NGX_OPENSSL_PHASE1_SANDBOX_IO_WANT_WRITE;
    case NGX_OPENSSL_PHASE1_SANDBOX_STATUS_CLOSED:
      return NGX_OPENSSL_PHASE1_SANDBOX_IO_CLOSED;
    case NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INVALID_ARGUMENT:
      return NGX_OPENSSL_PHASE1_SANDBOX_IO_INVALID_ARGUMENT;
    default:
      return NGX_OPENSSL_PHASE1_SANDBOX_IO_INTERNAL_ERROR;
  }
}

ngx_openssl_phase1_sandbox_status_t
ngx_openssl_phase1_sandbox_init(void)
{
  if (!g_initialized) {
    if (OPENSSL_init_ssl(0, NULL) != 1) {
      return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
    }
    g_initialized = 1;
  }
  return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_OK;
}

ngx_openssl_phase1_sandbox_status_t
ngx_openssl_phase1_sandbox_seed_rng(const unsigned char* seed,
                                    ngx_openssl_phase1_sandbox_size_t seed_len)
{
  if ((seed == NULL && seed_len != 0) ||
      seed_len > (ngx_openssl_phase1_sandbox_size_t) INT_MAX) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INVALID_ARGUMENT;
  }

  if (ngx_openssl_phase1_sandbox_init() != NGX_OPENSSL_PHASE1_SANDBOX_STATUS_OK) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
  }

  if (seed_len != 0) {
    RAND_seed(seed, (int) seed_len);
  }

  return RAND_status() == 1 ? NGX_OPENSSL_PHASE1_SANDBOX_STATUS_OK
                            : NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
}

int
ngx_openssl_phase1_sandbox_rand_status(void)
{
  return RAND_status();
}

void
ngx_openssl_phase1_sandbox_shutdown(void)
{
  free_conn_entries();
  free_ctx_entries();
  g_next_ctx_handle = 1;
  g_next_conn_handle = 1;
  g_initialized = 0;
}

ngx_openssl_phase1_sandbox_status_t
ngx_openssl_phase1_sandbox_ctx_create_server(
  const ngx_openssl_phase1_sandbox_server_config_t* server_config,
  ngx_openssl_phase1_sandbox_ctx_handle_t* out_ctx)
{
  SSL_CTX* ctx = NULL;
  ctx_entry_t* entry = NULL;

  if (server_config == NULL || out_ctx == NULL) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INVALID_ARGUMENT;
  }

  *out_ctx = NGX_OPENSSL_PHASE1_SANDBOX_INVALID_CTX_HANDLE;
  g_last_ctx_create_stage = 1;

  if (ngx_openssl_phase1_sandbox_init() != NGX_OPENSSL_PHASE1_SANDBOX_STATUS_OK) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
  }

  g_last_ctx_create_stage = 2;
  ctx = SSL_CTX_new(TLS_server_method());
  if (ctx == NULL) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
  }

  g_last_ctx_create_stage = 3;
  if (server_config->min_tls_version != 0 &&
      SSL_CTX_set_min_proto_version(ctx, (int) server_config->min_tls_version) != 1) {
    SSL_CTX_free(ctx);
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
  }

  g_last_ctx_create_stage = 4;
  if (server_config->max_tls_version != 0 &&
      SSL_CTX_set_max_proto_version(ctx, (int) server_config->max_tls_version) != 1) {
    SSL_CTX_free(ctx);
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
  }

  g_last_ctx_create_stage = 5;
  if (server_config->ciphers != NULL && server_config->ciphers[0] != '\0' &&
      SSL_CTX_set_cipher_list(ctx, server_config->ciphers) != 1) {
    SSL_CTX_free(ctx);
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
  }

  if (server_config->session_tickets == 0) {
    SSL_CTX_set_options(ctx, SSL_OP_NO_TICKET);
  }

  g_last_ctx_create_stage = 6;
  if (!load_server_certificate_chain(ctx,
                                     server_config->cert_pem,
                                     server_config->cert_pem_len) ||
      !load_private_key(ctx, server_config->key_pem, server_config->key_pem_len)) {
    SSL_CTX_free(ctx);
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
  }

  g_last_ctx_create_stage = 7;
  if (server_config->trusted_cert_pem != NULL &&
      server_config->trusted_cert_pem_len != 0 &&
      !load_trusted_certificates(ctx,
                                 server_config->trusted_cert_pem,
                                 server_config->trusted_cert_pem_len)) {
    SSL_CTX_free(ctx);
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
  }

  g_last_ctx_create_stage = 8;
  entry = (ctx_entry_t*) calloc(1, sizeof(*entry));
  if (entry == NULL) {
    SSL_CTX_free(ctx);
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
  }

  entry->handle = g_next_ctx_handle++;
  entry->ctx = ctx;
  entry->next = g_ctx_entries;
  g_ctx_entries = entry;

  *out_ctx = entry->handle;
  g_last_ctx_create_stage = 9;
  return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_OK;
}

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
  ngx_openssl_phase1_sandbox_ctx_handle_t* out_ctx)
{
  ngx_openssl_phase1_sandbox_server_config_t cfg;

  memset(&cfg, 0, sizeof(cfg));
  cfg.cert_pem = cert_pem;
  cfg.cert_pem_len = cert_pem_len;
  cfg.key_pem = key_pem;
  cfg.key_pem_len = key_pem_len;
  cfg.trusted_cert_pem = trusted_cert_pem;
  cfg.trusted_cert_pem_len = trusted_cert_pem_len;
  cfg.ciphers = ciphers;
  cfg.min_tls_version = min_tls_version;
  cfg.max_tls_version = max_tls_version;
  cfg.session_tickets = session_tickets;

  return ngx_openssl_phase1_sandbox_ctx_create_server(&cfg, out_ctx);
}

void
ngx_openssl_phase1_sandbox_ctx_destroy(ngx_openssl_phase1_sandbox_ctx_handle_t ctx)
{
  if (ctx != NGX_OPENSSL_PHASE1_SANDBOX_INVALID_CTX_HANDLE) {
    remove_ctx_entry(ctx);
  }
}

ngx_openssl_phase1_sandbox_status_t
ngx_openssl_phase1_sandbox_conn_create(
  ngx_openssl_phase1_sandbox_ctx_handle_t ctx,
  ngx_openssl_phase1_sandbox_conn_handle_t* out_conn)
{
  ctx_entry_t* ctx_entry = NULL;
  conn_entry_t* conn_entry = NULL;
  SSL* ssl = NULL;
  BIO* rbio = NULL;
  BIO* wbio = NULL;

  if (out_conn == NULL) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INVALID_ARGUMENT;
  }

  *out_conn = NGX_OPENSSL_PHASE1_SANDBOX_INVALID_CONN_HANDLE;
  ctx_entry = find_ctx_entry(ctx);
  if (ctx_entry == NULL) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INVALID_ARGUMENT;
  }

  ssl = SSL_new(ctx_entry->ctx);
  if (ssl == NULL) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
  }

  rbio = BIO_new(BIO_s_mem());
  wbio = BIO_new(BIO_s_mem());
  if (rbio == NULL || wbio == NULL) {
    if (rbio != NULL) {
      BIO_free(rbio);
    }
    if (wbio != NULL) {
      BIO_free(wbio);
    }
    SSL_free(ssl);
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
  }

  BIO_set_mem_eof_return(rbio, -1);
  BIO_set_mem_eof_return(wbio, -1);
  SSL_set_bio(ssl, rbio, wbio);
  SSL_set_accept_state(ssl);

  conn_entry = (conn_entry_t*) calloc(1, sizeof(*conn_entry));
  if (conn_entry == NULL) {
    SSL_free(ssl);
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
  }

  conn_entry->handle = g_next_conn_handle++;
  conn_entry->ssl = ssl;
  conn_entry->last_ssl_error = 0;
  conn_entry->next = g_conn_entries;
  g_conn_entries = conn_entry;

  *out_conn = conn_entry->handle;
  return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_OK;
}

void
ngx_openssl_phase1_sandbox_conn_destroy(ngx_openssl_phase1_sandbox_conn_handle_t conn)
{
  if (conn != NGX_OPENSSL_PHASE1_SANDBOX_INVALID_CONN_HANDLE) {
    remove_conn_entry(conn);
  }
}

ngx_openssl_phase1_sandbox_status_t
ngx_openssl_phase1_sandbox_conn_feed_encrypted(
  ngx_openssl_phase1_sandbox_conn_handle_t conn,
  const unsigned char* ciphertext,
  ngx_openssl_phase1_sandbox_size_t ciphertext_len,
  ngx_openssl_phase1_sandbox_size_t* bytes_consumed,
  ngx_openssl_phase1_sandbox_profile_t* profile)
{
  conn_entry_t* entry = NULL;
  BIO* rbio = NULL;
  int rc = 0;

  clear_profile(profile);
  if (bytes_consumed != NULL) {
    *bytes_consumed = 0;
  }

  if ((ciphertext == NULL && ciphertext_len != 0) || !fits_in_int(ciphertext_len)) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INVALID_ARGUMENT;
  }

  entry = find_conn_entry(conn);
  if (entry == NULL) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INVALID_ARGUMENT;
  }

  rbio = SSL_get_rbio(entry->ssl);
  if (rbio == NULL) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
  }

  if (ciphertext_len == 0) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_OK;
  }

  rc = BIO_write(rbio, ciphertext, (int) ciphertext_len);
  if (rc <= 0) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
  }

  if (bytes_consumed != NULL) {
    *bytes_consumed = (ngx_openssl_phase1_sandbox_size_t) rc;
  }
  return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_OK;
}

ngx_openssl_phase1_sandbox_status_t
ngx_openssl_phase1_sandbox_conn_drain_encrypted(
  ngx_openssl_phase1_sandbox_conn_handle_t conn,
  unsigned char* out_ciphertext,
  ngx_openssl_phase1_sandbox_size_t out_ciphertext_cap,
  ngx_openssl_phase1_sandbox_size_t* out_ciphertext_len,
  ngx_openssl_phase1_sandbox_profile_t* profile)
{
  conn_entry_t* entry = NULL;
  BIO* wbio = NULL;
  size_t pending = 0;
  int rc = 0;

  clear_profile(profile);
  if (out_ciphertext_len != NULL) {
    *out_ciphertext_len = 0;
  }

  if ((out_ciphertext == NULL && out_ciphertext_cap != 0) || !fits_in_int(out_ciphertext_cap)) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INVALID_ARGUMENT;
  }

  entry = find_conn_entry(conn);
  if (entry == NULL) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INVALID_ARGUMENT;
  }

  wbio = SSL_get_wbio(entry->ssl);
  if (wbio == NULL) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
  }

  pending = (size_t) BIO_ctrl_pending(wbio);
  if (pending == 0 || out_ciphertext_cap == 0) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_OK;
  }

  if (pending > out_ciphertext_cap) {
    pending = out_ciphertext_cap;
  }

  rc = BIO_read(wbio, out_ciphertext, (int) pending);
  if (rc <= 0) {
    return status_from_bio_read(wbio, rc);
  }

  if (out_ciphertext_len != NULL) {
    *out_ciphertext_len = (ngx_openssl_phase1_sandbox_size_t) rc;
  }
  return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_OK;
}

ngx_openssl_phase1_sandbox_io_result_t
ngx_openssl_phase1_sandbox_conn_read_plain(
  ngx_openssl_phase1_sandbox_conn_handle_t conn,
  unsigned char* out_plaintext,
  ngx_openssl_phase1_sandbox_size_t out_plaintext_cap,
  ngx_openssl_phase1_sandbox_profile_t* profile)
{
  conn_entry_t* entry = NULL;
  int rc = 0;

  clear_profile(profile);
  if ((out_plaintext == NULL && out_plaintext_cap != 0) || !fits_in_int(out_plaintext_cap)) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INVALID_ARGUMENT;
  }

  entry = find_conn_entry(conn);
  if (entry == NULL) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INVALID_ARGUMENT;
  }

  rc = SSL_read(entry->ssl, out_plaintext, (int) out_plaintext_cap);
  if (rc > 0) {
    return (ngx_openssl_phase1_sandbox_io_result_t) rc;
  }
  return io_result_from_ssl_rc(entry, rc);
}

ngx_openssl_phase1_sandbox_io_result_t
ngx_openssl_phase1_sandbox_conn_write_plain(
  ngx_openssl_phase1_sandbox_conn_handle_t conn,
  const unsigned char* plaintext,
  ngx_openssl_phase1_sandbox_size_t plaintext_len,
  ngx_openssl_phase1_sandbox_profile_t* profile)
{
  conn_entry_t* entry = NULL;
  int rc = 0;

  clear_profile(profile);
  if ((plaintext == NULL && plaintext_len != 0) || !fits_in_int(plaintext_len)) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INVALID_ARGUMENT;
  }

  entry = find_conn_entry(conn);
  if (entry == NULL) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INVALID_ARGUMENT;
  }

  rc = SSL_write(entry->ssl, plaintext, (int) plaintext_len);
  if (rc > 0) {
    return (ngx_openssl_phase1_sandbox_io_result_t) rc;
  }
  return io_result_from_ssl_rc(entry, rc);
}

ngx_openssl_phase1_sandbox_status_t
ngx_openssl_phase1_sandbox_conn_handshake_step(
  ngx_openssl_phase1_sandbox_conn_handle_t conn,
  ngx_openssl_phase1_sandbox_profile_t* profile)
{
  conn_entry_t* entry = NULL;
  int rc = 0;

  clear_profile(profile);
  entry = find_conn_entry(conn);
  if (entry == NULL) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INVALID_ARGUMENT;
  }

  rc = SSL_do_handshake(entry->ssl);
  if (rc == 1) {
    entry->last_ssl_error = 0;
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_OK;
  }

  return status_from_ssl_rc(entry, rc);
}

ngx_openssl_phase1_sandbox_status_t
ngx_openssl_phase1_sandbox_conn_shutdown(
  ngx_openssl_phase1_sandbox_conn_handle_t conn,
  ngx_openssl_phase1_sandbox_profile_t* profile)
{
  conn_entry_t* entry = NULL;
  int rc = 0;

  clear_profile(profile);
  entry = find_conn_entry(conn);
  if (entry == NULL) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INVALID_ARGUMENT;
  }

  rc = SSL_shutdown(entry->ssl);
  if (rc == 1) {
    entry->last_ssl_error = 0;
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_OK;
  }
  if (rc == 0) {
    if (BIO_ctrl_pending(SSL_get_wbio(entry->ssl)) > 0) {
      return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_WANT_WRITE;
    }
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_WANT_READ;
  }
  return status_from_ssl_rc(entry, rc);
}

ngx_openssl_phase1_sandbox_status_t
ngx_openssl_phase1_sandbox_conn_export_session(
  ngx_openssl_phase1_sandbox_conn_handle_t conn,
  unsigned char* out_session,
  ngx_openssl_phase1_sandbox_size_t out_session_cap,
  ngx_openssl_phase1_sandbox_size_t* out_session_len)
{
  conn_entry_t* entry = NULL;
  SSL_SESSION* session = NULL;
  unsigned char* cursor = out_session;
  int der_len = 0;

  if (out_session_len != NULL) {
    *out_session_len = 0;
  }

  if ((out_session == NULL && out_session_cap != 0) || !fits_in_int(out_session_cap)) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INVALID_ARGUMENT;
  }

  entry = find_conn_entry(conn);
  if (entry == NULL) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INVALID_ARGUMENT;
  }

  session = SSL_get1_session(entry->ssl);
  if (session == NULL) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
  }

  der_len = i2d_SSL_SESSION(session, NULL);
  if (der_len <= 0 || (size_t) der_len > out_session_cap) {
    SSL_SESSION_free(session);
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
  }

  if (i2d_SSL_SESSION(session, &cursor) != der_len) {
    SSL_SESSION_free(session);
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
  }

  SSL_SESSION_free(session);
  if (out_session_len != NULL) {
    *out_session_len = (ngx_openssl_phase1_sandbox_size_t) der_len;
  }
  return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_OK;
}

ngx_openssl_phase1_sandbox_status_t
ngx_openssl_phase1_sandbox_conn_import_session(
  ngx_openssl_phase1_sandbox_conn_handle_t conn,
  const unsigned char* session_bytes,
  ngx_openssl_phase1_sandbox_size_t session_len)
{
  conn_entry_t* entry = NULL;
  const unsigned char* cursor = session_bytes;
  SSL_SESSION* session = NULL;

  if ((session_bytes == NULL && session_len != 0) || !fits_in_int(session_len)) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INVALID_ARGUMENT;
  }

  entry = find_conn_entry(conn);
  if (entry == NULL) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INVALID_ARGUMENT;
  }

  session = d2i_SSL_SESSION(NULL, &cursor, (long) session_len);
  if (session == NULL) {
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
  }

  if (SSL_set_session(entry->ssl, session) != 1) {
    SSL_SESSION_free(session);
    return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR;
  }

  SSL_SESSION_free(session);
  return NGX_OPENSSL_PHASE1_SANDBOX_STATUS_OK;
}

int
ngx_openssl_phase1_sandbox_conn_last_ssl_error(
  ngx_openssl_phase1_sandbox_conn_handle_t conn)
{
  conn_entry_t* entry = find_conn_entry(conn);
  if (entry == NULL) {
    return 0;
  }
  return entry->last_ssl_error;
}

unsigned long
ngx_openssl_phase1_sandbox_last_err_code(void)
{
  return ERR_peek_last_error();
}

uint32_t
ngx_openssl_phase1_sandbox_last_ctx_create_stage(void)
{
  return g_last_ctx_create_stage;
}

uint32_t
ngx_openssl_phase1_sandbox_last_ssl_ctx_new_stage(void)
{
  return ossl_debug_ssl_ctx_new_stage();
}

uint32_t
ngx_openssl_phase1_sandbox_openssl_malloc_probe(
  ngx_openssl_phase1_sandbox_size_t size)
{
  void* ptr = OPENSSL_zalloc(size);
  if (ptr == NULL && size != 0) {
    return 0;
  }
  OPENSSL_free(ptr);
  return 1;
}

const char*
ngx_openssl_phase1_sandbox_status_string(
  ngx_openssl_phase1_sandbox_status_t status)
{
  switch (status) {
    case NGX_OPENSSL_PHASE1_SANDBOX_STATUS_OK:
      return "ok";
    case NGX_OPENSSL_PHASE1_SANDBOX_STATUS_WANT_READ:
      return "want_read";
    case NGX_OPENSSL_PHASE1_SANDBOX_STATUS_WANT_WRITE:
      return "want_write";
    case NGX_OPENSSL_PHASE1_SANDBOX_STATUS_CLOSED:
      return "closed";
    case NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INVALID_ARGUMENT:
      return "invalid_argument";
    case NGX_OPENSSL_PHASE1_SANDBOX_STATUS_NOT_IMPLEMENTED:
      return "not_implemented";
    case NGX_OPENSSL_PHASE1_SANDBOX_STATUS_INTERNAL_ERROR:
      return "internal_error";
    default:
      return "unknown";
  }
}
