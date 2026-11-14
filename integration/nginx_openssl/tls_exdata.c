/* The ex_data pair for the nginx/openssl port (tracker items I10 and I6).
 *
 * nginx attaches its connection object to an SSL with
 *   SSL_set_ex_data(ssl, ngx_ssl_connection_index, c)
 * and its server configuration to an SSL_CTX with
 *   SSL_CTX_set_ex_data(ctx, ngx_ssl_server_conf_index, conf),
 * and later asks OpenSSL for the connection with SSL_get_ex_data. The
 * artifact's TLS shim has no such calls. This file adds them with the real
 * OpenSSL functions. It includes the artifact's shim, unchanged, because the
 * shim's table from connection handles to SSL objects is private to it.
 *
 * The values stored are whatever T passes: inside the sandbox a pointer is 32
 * bits wide, so T passes handles to its objects, not addresses. */
#include "samples/nginx_openssl_phase1_bridge_wasm/untrusted/ngx_openssl_phase1_sandbox.c"

#include <stdio.h>

static int g_connection_index = -1;
static int g_conf_index = -1;

#ifdef INTERSPEC_FAULT_TESTS
static uint32_t g_ex_fault, g_ex_fault_used;
/* What a compromised U returns from the next get instead of the stored
 * value: 1 = a value T never issued, 2 = the server configuration stored on
 * the SSL_CTX (an object of T of another type), 3 = the connection object of
 * another connection (same type). */
void interspec_tls_ex_fault(uint32_t mode) { g_ex_fault = mode; g_ex_fault_used = 0; }
#endif

int interspec_tls_set_conf(unsigned long long ctx, void *conf)
{
    ctx_entry_t *entry = find_ctx_entry(ctx);
    if (!entry || !entry->ctx) return 0;
    if (g_conf_index < 0)
        g_conf_index = SSL_CTX_get_ex_new_index(0, NULL, NULL, NULL, NULL);
    return g_conf_index >= 0 && SSL_CTX_set_ex_data(entry->ctx, g_conf_index, conf) == 1;
}

int interspec_tls_set_connection(unsigned long long conn, void *connection)
{
    conn_entry_t *entry = find_conn_entry(conn);
    if (!entry || !entry->ssl) return 0;
    if (g_connection_index < 0)
        g_connection_index = SSL_get_ex_new_index(0, NULL, NULL, NULL, NULL);
    return g_connection_index >= 0 &&
           SSL_set_ex_data(entry->ssl, g_connection_index, connection) == 1;
}

void *interspec_tls_get_connection(unsigned long long conn)
{
    conn_entry_t *entry = find_conn_entry(conn);
    if (!entry || !entry->ssl || g_connection_index < 0) return NULL;
    void *value = SSL_get_ex_data(entry->ssl, g_connection_index);
#ifdef INTERSPEC_FAULT_TESTS
    if (g_ex_fault && !g_ex_fault_used) {
        void *replacement = NULL;
        g_ex_fault_used = 1;
        if (g_ex_fault == 1) {
            replacement = (void *)(uintptr_t)0x5ec2e7f0u;
        } else if (g_ex_fault == 2 && g_conf_index >= 0) {
            replacement = SSL_CTX_get_ex_data(SSL_get_SSL_CTX(entry->ssl), g_conf_index);
        } else if (g_ex_fault == 3) {
            for (conn_entry_t *other = g_conn_entries; other; other = other->next)
                if (other != entry && other->ssl)
                    replacement = SSL_get_ex_data(other->ssl, g_connection_index);
        }
        fprintf(stderr, "FAULT_INJECTION boundary=nginx_openssl mode=%u original=0x%x "
                        "replacement=0x%x\n",
                g_ex_fault, (unsigned)(uintptr_t)value, (unsigned)(uintptr_t)replacement);
        fflush(stderr);
        value = replacement;
    }
#endif
    return value;
}
