/* The artifact's shim reports a diagnostic value through
 * ossl_debug_ssl_ctx_new_stage(), a function of the artifact authors' locally
 * patched OpenSSL, which the artifact does not ship. Upstream OpenSSL has no
 * such function; the port never asks for the diagnostic. */
unsigned int ossl_debug_ssl_ctx_new_stage(void);
unsigned int ossl_debug_ssl_ctx_new_stage(void) { return 0; }
