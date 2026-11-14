#ifndef LIBVPX_WASM_FAKE_SETJMP_H_
#define LIBVPX_WASM_FAKE_SETJMP_H_

typedef struct libvpx_wasm_fake_jmp_buf_s
{
  int unused;
} libvpx_wasm_fake_jmp_buf_t;

typedef libvpx_wasm_fake_jmp_buf_t jmp_buf[1];

#define setjmp(env) (0)

static inline void
longjmp(jmp_buf env, int value)
{
  (void) env;
  (void) value;
  __builtin_trap();
}

#endif
