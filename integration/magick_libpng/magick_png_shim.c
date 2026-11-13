#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "png.h"
#include "magick_png_shim.h"

/* The shim of the interspec-artifact wrapper (magick_png_rlbox_shim.c) with
 * one change, marked "port:" below: the two buffers that are handed to T, the
 * decoded pixels and the encoded PNG, come from returned_reserve().
 *
 * In the tracked builds each buffer is allocated at a declared site that the
 * trusted registry knows. In every build the shim keeps one buffer of each
 * kind and reuses it for the next call while it is large enough, instead of
 * allocating and freeing one per call as the artifact shim does: the
 * registry's arena does not reuse released addresses, so a buffer per call
 * would exhaust it. magickpng_free() therefore keeps the buffer. */
#ifndef INTERSPEC_TRACKING
#define INTERSPEC_TRACKING 0
#endif
#if INTERSPEC_TRACKING
#include "interspec_png_u_policy.h"
#endif

enum { RETURNED_PIXELS = 0, RETURNED_PNG = 1 };
static unsigned char* g_returned[2];
static size_t g_returned_cap[2];

/* The buffer of `kind` with room for `bytes`; its first `keep` bytes survive. */
static unsigned char* returned_reserve(int kind, size_t bytes, size_t keep)
{
  if (bytes <= g_returned_cap[kind]) {
    return g_returned[kind];
  }
#if INTERSPEC_TRACKING
  unsigned char* p = (unsigned char*)(uintptr_t)(
    kind == RETURNED_PIXELS ? INTERSPEC_SITE_DECODED_PIXELS_ALLOC(bytes)
                            : INTERSPEC_SITE_ENCODED_PNG_ALLOC(bytes));
#else
  unsigned char* p = (unsigned char*)malloc(bytes);
#endif
  if (!p) {
    return NULL;
  }
  if (keep) {
    memcpy(p, g_returned[kind], keep);
  }
#if INTERSPEC_TRACKING
  if (g_returned[kind]) {
    (void)interspec_wasm_release((uint32_t)(uintptr_t)g_returned[kind]);
  }
#else
  free(g_returned[kind]);
#endif
  g_returned[kind] = p;
  g_returned_cap[kind] = bytes;
  return p;
}

typedef struct
{
  const unsigned char* data;
  size_t size;
  size_t offset;
} mem_reader_t;

static void read_cb(png_structp png_ptr, png_bytep outBytes, png_size_t byteCountToRead)
{
  mem_reader_t* r = (mem_reader_t*)png_get_io_ptr(png_ptr);
  if (!r || !outBytes) {
    png_error(png_ptr, "bad read state");
    return;
  }
  if (byteCountToRead > (r->size - r->offset)) {
    png_error(png_ptr, "read past end");
    return;
  }
  memcpy(outBytes, r->data + r->offset, byteCountToRead);
  r->offset += (size_t)byteCountToRead;
}

typedef struct
{
  unsigned char* data;
  size_t size;
  size_t cap;
} mem_writer_t;

static void write_cb(png_structp png_ptr, png_bytep data, png_size_t length)
{
  mem_writer_t* w = (mem_writer_t*)png_get_io_ptr(png_ptr);
  if (!w || !data) {
    png_error(png_ptr, "bad write state");
    return;
  }
  size_t need = w->size + (size_t)length;
  if (need < w->size) {
    png_error(png_ptr, "overflow");
    return;
  }
  if (need > w->cap) {
    size_t new_cap = w->cap ? w->cap : 4096;
    while (new_cap < need) {
      size_t next = new_cap * 2;
      if (next < new_cap) {
        png_error(png_ptr, "overflow");
        return;
      }
      new_cap = next;
    }
    /* port: was realloc(w->data, new_cap) */
    unsigned char* p = returned_reserve(RETURNED_PNG, new_cap, w->size);
    if (!p) {
      png_error(png_ptr, "oom");
      return;
    }
    w->data = p;
    w->cap = new_cap;
  }
  memcpy(w->data + w->size, data, (size_t)length);
  w->size = need;
}

static void flush_cb(png_structp png_ptr)
{
  (void)png_ptr;
}

unsigned char*
magickpng_decode_rgba(const unsigned char* input,
                      uint32_t input_len,
                      uint32_t* out_w,
                      uint32_t* out_h,
                      uint32_t* out_size)
{
  if (out_w) *out_w = 0;
  if (out_h) *out_h = 0;
  if (out_size) *out_size = 0;

  if (input == NULL || input_len == 0) {
    return NULL;
  }

  png_structp png_ptr = png_create_read_struct(PNG_LIBPNG_VER_STRING, NULL, NULL, NULL);
  if (!png_ptr) {
    return NULL;
  }
  png_infop info_ptr = png_create_info_struct(png_ptr);
  if (!info_ptr) {
    png_destroy_read_struct(&png_ptr, NULL, NULL);
    return NULL;
  }

  mem_reader_t reader;
  reader.data = input;
  reader.size = (size_t)input_len;
  reader.offset = 0;
  png_set_read_fn(png_ptr, &reader, read_cb);

  png_read_info(png_ptr, info_ptr);

  png_uint_32 width = 0, height = 0;
  int bit_depth = 0, color_type = 0, interlace_type = 0, compression_type = 0, filter_method = 0;
  png_get_IHDR(png_ptr,
               info_ptr,
               &width,
               &height,
               &bit_depth,
               &color_type,
               &interlace_type,
               &compression_type,
               &filter_method);

  if (width == 0 || height == 0 || width > 1u << 24 || height > 1u << 24) {
    png_destroy_read_struct(&png_ptr, &info_ptr, NULL);
    return NULL;
  }

  if (color_type == PNG_COLOR_TYPE_PALETTE) {
    png_set_palette_to_rgb(png_ptr);
  }
  if (color_type == PNG_COLOR_TYPE_GRAY && bit_depth < 8) {
    png_set_expand_gray_1_2_4_to_8(png_ptr);
  }
  if (png_get_valid(png_ptr, info_ptr, PNG_INFO_tRNS)) {
    png_set_tRNS_to_alpha(png_ptr);
  }
  if (bit_depth == 16) {
    png_set_strip_16(png_ptr);
  }
  if (color_type == PNG_COLOR_TYPE_GRAY || color_type == PNG_COLOR_TYPE_GRAY_ALPHA) {
    png_set_gray_to_rgb(png_ptr);
  }

  png_set_filler(png_ptr, 0xFF, PNG_FILLER_AFTER);
  png_read_update_info(png_ptr, info_ptr);

  png_size_t rowbytes = png_get_rowbytes(png_ptr, info_ptr);
  if (rowbytes == 0 || rowbytes > (png_size_t)UINT32_MAX) {
    png_destroy_read_struct(&png_ptr, &info_ptr, NULL);
    return NULL;
  }

  uint64_t total = (uint64_t)rowbytes * (uint64_t)height;
  if (total == 0 || total > UINT32_MAX) {
    png_destroy_read_struct(&png_ptr, &info_ptr, NULL);
    return NULL;
  }

  /* port: was malloc((size_t)total) */
  unsigned char* out = returned_reserve(RETURNED_PIXELS, (size_t)total, 0);
  if (!out) {
    png_destroy_read_struct(&png_ptr, &info_ptr, NULL);
    return NULL;
  }

  png_bytep* rows = (png_bytep*)malloc(sizeof(png_bytep) * (size_t)height);
  if (!rows) {
    /* port: was free(out) */
    png_destroy_read_struct(&png_ptr, &info_ptr, NULL);
    return NULL;
  }
  for (png_uint_32 y = 0; y < height; ++y) {
    rows[y] = out + ((size_t)rowbytes * (size_t)y);
  }

  png_read_image(png_ptr, rows);
  png_read_end(png_ptr, NULL);

  free(rows);
  png_destroy_read_struct(&png_ptr, &info_ptr, NULL);

  if (out_w) *out_w = (uint32_t)width;
  if (out_h) *out_h = (uint32_t)height;
  if (out_size) *out_size = (uint32_t)total;
  return out;
}

unsigned char*
magickpng_encode_rgba(const unsigned char* rgba,
                      uint32_t width,
                      uint32_t height,
                      uint32_t* out_size)
{
  if (out_size) *out_size = 0;
  if (!rgba || width == 0 || height == 0) {
    return NULL;
  }

  if (width > 1u << 24 || height > 1u << 24) {
    return NULL;
  }

  png_structp png_ptr = png_create_write_struct(PNG_LIBPNG_VER_STRING, NULL, NULL, NULL);
  if (!png_ptr) {
    return NULL;
  }
  png_infop info_ptr = png_create_info_struct(png_ptr);
  if (!info_ptr) {
    png_destroy_write_struct(&png_ptr, NULL);
    return NULL;
  }

  mem_writer_t writer;
  /* port: was data = NULL, cap = 0 */
  writer.data = g_returned[RETURNED_PNG];
  writer.size = 0;
  writer.cap = g_returned_cap[RETURNED_PNG];
  png_set_write_fn(png_ptr, &writer, write_cb, flush_cb);

  png_set_IHDR(png_ptr,
               info_ptr,
               width,
               height,
               8,
               PNG_COLOR_TYPE_RGBA,
               PNG_INTERLACE_NONE,
               PNG_COMPRESSION_TYPE_BASE,
               PNG_FILTER_TYPE_BASE);

  png_write_info(png_ptr, info_ptr);

  png_bytep* rows = (png_bytep*)malloc(sizeof(png_bytep) * (size_t)height);
  if (!rows) {
    png_destroy_write_struct(&png_ptr, &info_ptr);
    /* port: was free(writer.data) */
    return NULL;
  }

  size_t rowbytes = (size_t)width * 4u;
  for (png_uint_32 y = 0; y < height; ++y) {
    rows[y] = (png_bytep)(rgba + (rowbytes * (size_t)y));
  }

  png_write_image(png_ptr, rows);
  png_write_end(png_ptr, NULL);

  free(rows);
  png_destroy_write_struct(&png_ptr, &info_ptr);

  if (writer.size == 0 || writer.size > UINT32_MAX) {
    /* port: was free(writer.data) */
    return NULL;
  }

  if (out_size) *out_size = (uint32_t)writer.size;
  return writer.data;
}

void
magickpng_free(unsigned char* p)
{
  /* port: was free(p); the buffer is kept for the next call */
  (void)p;
}
