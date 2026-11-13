/* Compiled into U together with OpenSSL and the TLS shim of the
 * interspec-artifact wrapper (ngx_openssl_phase1_sandbox.c, unchanged). The
 * shim's interface exchanges copied buffers and numeric handles only. This
 * file adds staging memory for T's buffers and wrappers that take addresses
 * as 32-bit values and handles as unsigned long long (RLBox maps types by
 * name, and long is 32 bits wide inside the sandbox). */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "benchmarks/nginx/src/event/rlbox/ngx_openssl_phase1_sandbox_abi.h"

#ifdef __wasm__
#include <sys/types.h>
/* See openssl_wasi_compat.h: there are no user ids inside the sandbox. */
uid_t getuid(void) { return 0; }
uid_t geteuid(void) { return 0; }
gid_t getgid(void) { return 0; }
gid_t getegid(void) { return 0; }
#endif

/* Staging memory that T fills or reads: 0 = out-parameters, 1 = input bytes,
 * 2 = output bytes, 3 = certificate, 4 = key. Zeroed when allocated. */
#define STAGES 5
static unsigned char *g_stage[STAGES];
static uint32_t g_stage_capacity[STAGES];

#ifdef INTERSPEC_FAULT_TESTS
static uint32_t g_poc_flags;
/* Policy-switch tests, same flag bits as the other boundaries:
 * 1 = U reads the output buffer it was handed before writing to it,
 * 2 = U overwrites its copy of the plaintext after sending it. */
void interspec_tls_poc(uint32_t flags) { g_poc_flags = flags; }
#endif

unsigned char *interspec_tls_stage(uint32_t which, uint32_t bytes)
{
    if (which >= STAGES) return NULL;
    if (bytes > g_stage_capacity[which]) {
        free(g_stage[which]);
        g_stage[which] = calloc(1, bytes);
        g_stage_capacity[which] = g_stage[which] ? bytes : 0;
    }
    return g_stage[which];
}

int interspec_tls_init(uint32_t seed_addr, uint32_t seed_len)
{
    return (int)ngx_openssl_phase1_sandbox_seed_rng((const unsigned char *)(uintptr_t)seed_addr,
                                                    seed_len);
}

int interspec_tls_ctx_create(uint32_t cert_addr, uint32_t cert_len, uint32_t key_addr,
                             uint32_t key_len, uint32_t min_version, uint32_t max_version,
                             int session_tickets, uint32_t out_ctx_addr)
{
    return (int)ngx_openssl_phase1_sandbox_ctx_create_server_flat(
        (const unsigned char *)(uintptr_t)cert_addr, cert_len,
        (const unsigned char *)(uintptr_t)key_addr, key_len, NULL, 0, NULL, min_version,
        max_version, session_tickets,
        (ngx_openssl_phase1_sandbox_ctx_handle_t *)(uintptr_t)out_ctx_addr);
}

int interspec_tls_conn_create(unsigned long long ctx, uint32_t out_conn_addr)
{
    return (int)ngx_openssl_phase1_sandbox_conn_create(
        ctx, (ngx_openssl_phase1_sandbox_conn_handle_t *)(uintptr_t)out_conn_addr);
}

int interspec_tls_feed(unsigned long long conn, uint32_t data_addr, uint32_t len,
                       uint32_t consumed_addr)
{
    return (int)ngx_openssl_phase1_sandbox_conn_feed_encrypted(
        conn, (const unsigned char *)(uintptr_t)data_addr, len,
        (ngx_openssl_phase1_sandbox_size_t *)(uintptr_t)consumed_addr, NULL);
}

int interspec_tls_drain(unsigned long long conn, uint32_t out_addr, uint32_t cap,
                        uint32_t out_len_addr)
{
    return (int)ngx_openssl_phase1_sandbox_conn_drain_encrypted(
        conn, (unsigned char *)(uintptr_t)out_addr, cap,
        (ngx_openssl_phase1_sandbox_size_t *)(uintptr_t)out_len_addr, NULL);
}

int interspec_tls_read(unsigned long long conn, uint32_t out_addr, uint32_t cap)
{
#ifdef INTERSPEC_FAULT_TESTS
    if ((g_poc_flags & 1u) && cap >= 8) {
        const unsigned char *out = (const unsigned char *)(uintptr_t)out_addr;
        fprintf(stderr, "[InterSpec][PoC][SP1] sandbox read output buffer before writing "
                        "first8=%02x%02x%02x%02x%02x%02x%02x%02x\n",
                out[0], out[1], out[2], out[3], out[4], out[5], out[6], out[7]);
        fflush(stderr);
        g_poc_flags &= ~1u; /* once */
    }
#endif
    return (int)ngx_openssl_phase1_sandbox_conn_read_plain(
        conn, (unsigned char *)(uintptr_t)out_addr, cap, NULL);
}

int interspec_tls_write(unsigned long long conn, uint32_t data_addr, uint32_t len)
{
    const int rc = (int)ngx_openssl_phase1_sandbox_conn_write_plain(
        conn, (const unsigned char *)(uintptr_t)data_addr, len, NULL);
#ifdef INTERSPEC_FAULT_TESTS
    if (rc > 0 && (g_poc_flags & 2u)) {
        unsigned char *data = (unsigned char *)(uintptr_t)data_addr;
        const unsigned old = data[0];
        data[0] ^= 0xff;
        fprintf(stderr, "[InterSpec][PoC][SP2] sandbox mutated plaintext byte=0 "
                        "old=0x%02x new=0x%02x\n", old, (unsigned)data[0]);
        fflush(stderr);
        g_poc_flags &= ~2u; /* once */
    }
#endif
    return rc;
}

int interspec_tls_handshake(unsigned long long conn)
{
    return (int)ngx_openssl_phase1_sandbox_conn_handshake_step(conn, NULL);
}

void interspec_tls_destroy(unsigned long long conn, unsigned long long ctx)
{
    ngx_openssl_phase1_sandbox_conn_destroy(conn);
    ngx_openssl_phase1_sandbox_ctx_destroy(ctx);
    ngx_openssl_phase1_sandbox_shutdown();
}
