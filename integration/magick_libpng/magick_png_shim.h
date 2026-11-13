#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

unsigned char* magickpng_decode_rgba(const unsigned char* input,
                                    uint32_t input_len,
                                    uint32_t* out_w,
                                    uint32_t* out_h,
                                    uint32_t* out_size);

unsigned char* magickpng_encode_rgba(const unsigned char* rgba,
                                    uint32_t width,
                                    uint32_t height,
                                    uint32_t* out_size);

void magickpng_free(unsigned char* p);

#ifdef __cplusplus
}
#endif

