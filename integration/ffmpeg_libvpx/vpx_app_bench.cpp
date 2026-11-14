// Trusted program for the ffmpeg/libvpx boundary (tracker item I7): a libvpx
// client that encodes synthetic frames with VP8 and decodes the packets
// again, with libvpx inside an RLBox wasm2c sandbox behind the shim of the
// interspec-artifact wrapper.
//
// T-level interface (the libvpx calls an application such as FFmpeg makes):
//   encode(ctx, img, pts, duration, flags, deadline)
//   get_cx_data(ctx, &iter)   -> packet {buf, sz, ...}
//   decode(ctx, data, data_sz, deadline)
//   get_frame(ctx, &iter)     -> image {planes[], stride[], d_w, d_h, ...}
// Policies at this boundary:
//   SP1  five fields of the image passed to encode are not used by the
//        encoder (user_priv, img_data, fb_priv, img_data_owner, self_allocd;
//        three of them are T pointers), so T's values are not copied in.
//   SP2  the raw planes and the compressed data are read by U and never
//        written by it, so U's copies are not copied back.
//   SP3  the packet buffer and the frame planes that U returns are checked
//        against the object registry (live object, expected type, bounds)
//        before T copies from them.
#define RLBOX_USE_EXCEPTIONS
#define RLBOX_USE_STATIC_CALLS() rlbox_wasm2c_sandbox_lookup_symbol
#define RLBOX_WASM2C_MODULE_NAME glue__lib__wasm2c
#include "glue_lib_wasm2c.h"
#include "rlbox.hpp"
#include "rlbox_wasm2c_sandbox.hpp"

#include "interspec/boundary/wasm_port.h"
#if INTERSPEC_TRACKING
#include "interspec_vpx_t_policy.h"
#endif

#include "shared/libvpx_bridge_abi.h"
#include "vpx_workload.h"

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

extern "C" {
// The artifact shim. Addresses and enumerations are 32-bit values in U.
uint32_t libvpx_rlbox_codec_ctx_create(void);
void libvpx_rlbox_codec_ctx_free(uint32_t);
int libvpx_rlbox_codec_dec_init(uint32_t, uint32_t, uint32_t, uint32_t);
int libvpx_rlbox_codec_enc_init(uint32_t, uint32_t, uint32_t, uint32_t);
int libvpx_rlbox_codec_enc_config_default(uint32_t, uint32_t, uint32_t);
int libvpx_rlbox_codec_get_cx_data(uint32_t, uint32_t, uint32_t);
int libvpx_rlbox_codec_destroy(uint32_t);
int libvpx_rlbox_codec_control_int(uint32_t, int32_t, int32_t);
// vpx_u.c
unsigned char* interspec_vpx_stage(uint32_t, uint32_t);
int interspec_vpx_encode(uint32_t, uint32_t, long long, uint32_t, uint32_t, uint32_t);
int interspec_vpx_decode(uint32_t, uint32_t, uint32_t, int32_t);
int interspec_vpx_get_frame(uint32_t, uint32_t, uint32_t);
#ifdef INTERSPEC_FAULT_TESTS
void interspec_vpx_fault(uint32_t);
void interspec_vpx_poc(uint32_t);
#endif
}

namespace {

#if INTERSPEC_TRACKING
namespace P = interspec::ffmpeg_libvpx_generated;
#else
namespace P {
struct NoAccess {};
constexpr NoAccess kUseVp8FrameBufferRange{}, kUseVp8CxDataRange{};
}  // namespace P
#endif

struct VpxPolicy {
  static constexpr const char* boundary = "ffmpeg_libvpx";
  static constexpr int reject_exit = 86;
#if INTERSPEC_TRACKING
  static bool register_all(interspec::Runtime& runtime) {
    return P::register_types(runtime) && P::register_wasm_allocation_policy(runtime);
  }
  template <class Access>
  static interspec::CheckResult check(const interspec::Runtime& runtime, uintptr_t base,
                                      size_t bytes, const Access& access) {
    return P::check(runtime, base, bytes, access);
  }
#endif
};
using Port = interspec::WasmPort<VpxPolicy>;

constexpr unsigned kMaxDimension = 4096;

// invoke_sandbox_function is a macro that needs the function's name, so this
// is a macro too. The returned status codes are plain integers from U.
#define VPX_CALL(name, ...) \
  (port_.sandbox().invoke_sandbox_function(name, __VA_ARGS__).UNSAFE_unverified())

#if !INTERSPEC_TRACKING
constexpr const char* kVariant = "rlbox-only";
#elif !INTERSPEC_CHECKS
constexpr const char* kVariant = "tracked-no-check";
#else
constexpr const char* kVariant = "interspec";
#endif

// What T keeps of a packet or frame after copying it out of U.
struct Packet {
  std::vector<unsigned char> data;
  uint64_t pts = 0;
  uint32_t flags = 0;
};
struct Decoded {
  unsigned width = 0, height = 0;
  std::vector<unsigned char> plane[3];
};

class Engine {
 public:
  Engine(unsigned width, unsigned height) : port_(128u * 1024u * 1024u) {
    auto& sandbox = port_.sandbox();
    encoder_ = sandbox.invoke_sandbox_function(libvpx_rlbox_codec_ctx_create).UNSAFE_unverified();
    decoder_ = sandbox.invoke_sandbox_function(libvpx_rlbox_codec_ctx_create).UNSAFE_unverified();
    if (!encoder_ || !decoder_) throw std::runtime_error("ctx_create");

    // Encoder configuration: libvpx defaults, then the workload's settings.
    libvpx_bridge_enc_cfg_t cfg;
    unsigned char* scratch = stage(0, sizeof(cfg));
    if (VPX_CALL(libvpx_rlbox_codec_enc_config_default, uint32_t{LIBVPX_BRIDGE_IFACE_VP8_CX},
             port_.address_of(scratch), 0u) != 0)
      throw std::runtime_error("enc_config_default");
    std::memcpy(&cfg, scratch, sizeof(cfg));
    cfg.g_w = width;
    cfg.g_h = height;
    cfg.g_timebase.num = 1;
    cfg.g_timebase.den = 30;
    cfg.g_threads = 1;
    cfg.g_lag_in_frames = 0;
    cfg.rc_target_bitrate = vpx_workload::kBitrateKbps;
    cfg.rc_twopass_stats_in = {0, 0};
    cfg.rc_firstpass_mb_stats_in = {0, 0};
    std::memcpy(scratch, &cfg, sizeof(cfg));
    if (VPX_CALL(libvpx_rlbox_codec_enc_init, encoder_, uint32_t{LIBVPX_BRIDGE_IFACE_VP8_CX},
             port_.address_of(scratch), 0u) != 0)
      throw std::runtime_error("enc_init");
    if (VPX_CALL(libvpx_rlbox_codec_control_int, encoder_, int32_t{VP8E_SET_CPUUSED},
             int32_t{vpx_workload::kCpuUsed}) != 0)
      throw std::runtime_error("set_cpuused");

    libvpx_bridge_dec_cfg_t dec_cfg{1, width, height};
    scratch = stage(0, sizeof(dec_cfg));
    std::memcpy(scratch, &dec_cfg, sizeof(dec_cfg));
    if (VPX_CALL(libvpx_rlbox_codec_dec_init, decoder_, uint32_t{LIBVPX_BRIDGE_IFACE_VP8_DX},
             port_.address_of(scratch), 0u) != 0)
      throw std::runtime_error("dec_init");
  }
  ~Engine() {
    try {
      VPX_CALL(libvpx_rlbox_codec_destroy, encoder_);
      VPX_CALL(libvpx_rlbox_codec_destroy, decoder_);
      port_.sandbox().invoke_sandbox_function(libvpx_rlbox_codec_ctx_free, encoder_);
      port_.sandbox().invoke_sandbox_function(libvpx_rlbox_codec_ctx_free, decoder_);
    } catch (...) {
    }
  }
  Port& port() { return port_; }

  // img may be null (flush). The image's planes are T memory.
  int encode(vpx_image_t* img, long long pts, uint32_t duration, uint32_t flags,
             uint32_t deadline) {
    libvpx_bridge_image_t bridge{};
    unsigned char* staged[3] = {nullptr, nullptr, nullptr};
    size_t bytes[3] = {0, 0, 0};
    if (img) {
      if (img->fmt != VPX_IMG_FMT_I420 || img->d_w == 0 || img->d_h == 0 ||
          img->d_w > kMaxDimension || img->d_h > kMaxDimension)
        return VPX_CODEC_INVALID_PARAM;
      size_t total = 0;
      for (int i = 0; i < 3; ++i) {
        const unsigned rows = i == 0 ? img->d_h : (img->d_h + 1) / 2;
        if (img->stride[i] <= 0 || !img->planes[i]) return VPX_CODEC_INVALID_PARAM;
        bytes[i] = static_cast<size_t>(img->stride[i]) * rows;
        total += bytes[i];
      }
      unsigned char* planes = stage(1, static_cast<uint32_t>(total));
      size_t offset = 0;
      for (int i = 0; i < 3; ++i) {
        staged[i] = planes + offset;
        std::memcpy(staged[i], img->planes[i], bytes[i]);
        bridge.planes[i] = port_.address_of(staged[i]);
        bridge.stride[i] = img->stride[i];
        offset += bytes[i];
      }
      bridge.present = 1;
      bridge.fmt = img->fmt;
      bridge.cs = img->cs;
      bridge.range = img->range;
      bridge.w = img->w;
      bridge.h = img->h;
      bridge.bit_depth = img->bit_depth;
      bridge.d_w = img->d_w;
      bridge.d_h = img->d_h;
      bridge.r_w = img->r_w;
      bridge.r_h = img->r_h;
      bridge.x_chroma_shift = img->x_chroma_shift;
      bridge.y_chroma_shift = img->y_chroma_shift;
      bridge.bps = img->bps;
      // SP1: U is handed zero for the five image fields that the encoder does
      // not use, unless SP1 is off.
      bridge.user_priv = Port::withheld_unless_sp1_off(low32(img->user_priv));
      bridge.img_data = Port::withheld_unless_sp1_off(low32(img->img_data));
      bridge.fb_priv = Port::withheld_unless_sp1_off(low32(img->fb_priv));
      bridge.img_data_owner = Port::withheld_unless_sp1_off(img->img_data_owner);
      bridge.self_allocd = Port::withheld_unless_sp1_off(img->self_allocd);
    }
    unsigned char* scratch = stage(0, sizeof(bridge));
    std::memcpy(scratch, &bridge, sizeof(bridge));
    const int rc = VPX_CALL(interspec_vpx_encode, encoder_, port_.address_of(scratch), pts,
                        duration, flags, deadline);
    // SP2: U's copies of the planes are not copied back.
    for (int i = 0; i < 3; ++i)
      if (staged[i]) port_.copy_back_unless_sp2(img->planes[i], staged[i], bytes[i]);
    return rc;
  }

  // Next frame packet of the encoder, or false.
  bool get_cx_data(uint32_t* iter, Packet* out) {
    for (;;) {
      libvpx_bridge_packet_t packet;
      unsigned char* scratch = stage(0, sizeof(packet));
      const int rc =
          VPX_CALL(libvpx_rlbox_codec_get_cx_data, encoder_, *iter, port_.address_of(scratch));
      std::memcpy(&packet, scratch, sizeof(packet));
      if (rc < 0) throw std::runtime_error("get_cx_data");
      *iter = packet.iter_state;
      if (rc == 0 || !packet.present) return false;
      if (packet.kind != VPX_CODEC_CX_FRAME_PKT) continue;
      if (packet.size == 0 || packet.size > 64u * 1024u * 1024u)
        Port::reject("cx_data", "packet_size");
      // SP3: the packet buffer must lie in a live registered object of the
      // expected type that holds `size` bytes from that address.
      const unsigned char* raw = port_.validate_address(packet.buf_addr, packet.size,
                                                        P::kUseVp8CxDataRange, "cx_data");
      out->data.assign(raw, raw + packet.size);
      out->pts = packet.pts;
      out->flags = packet.flags;
      return true;
    }
  }

  int decode(std::vector<unsigned char>& data, int32_t deadline) {
    if (data.empty() || data.size() > 64u * 1024u * 1024u) return VPX_CODEC_INVALID_PARAM;
    const uint32_t size = static_cast<uint32_t>(data.size());
    unsigned char* staged = stage(2, size);
    std::memcpy(staged, data.data(), size);
    const int rc = VPX_CALL(interspec_vpx_decode, decoder_, port_.address_of(staged), size, deadline);
    // SP2: U's copy of the compressed data is not copied back.
    port_.copy_back_unless_sp2(data.data(), staged, size);
    return rc;
  }

  // Next decoded frame, or false.
  bool get_frame(uint32_t* iter, Decoded* out) {
    libvpx_bridge_image_t image;
    unsigned char* scratch = stage(0, sizeof(image));
    const int rc = VPX_CALL(interspec_vpx_get_frame, decoder_, *iter, port_.address_of(scratch));
    std::memcpy(&image, scratch, sizeof(image));
    if (rc < 0) throw std::runtime_error("get_frame");
    *iter = image.iter_state;
    if (rc == 0 || !image.present) return false;
    if (image.fmt != VPX_IMG_FMT_I420 || image.d_w == 0 || image.d_h == 0 ||
        image.d_w > kMaxDimension || image.d_h > kMaxDimension)
      Port::reject("frame_plane", "image_header");
    out->width = image.d_w;
    out->height = image.d_h;
    for (int i = 0; i < 3; ++i) {
      const uint32_t width = i == 0 ? image.d_w : (image.d_w + 1) / 2;
      const uint32_t rows = i == 0 ? image.d_h : (image.d_h + 1) / 2;
      if (image.stride[i] < static_cast<int32_t>(width) || image.stride[i] > 65536)
        Port::reject("frame_plane", "image_header");
      const uint32_t stride = static_cast<uint32_t>(image.stride[i]);
      // SP3: each plane must lie in a live registered frame buffer that
      // holds every row T is about to read.
      const unsigned char* raw = port_.validate_address(
          image.planes[i], stride * (rows - 1) + width, P::kUseVp8FrameBufferRange,
          "frame_plane");
      out->plane[i].resize(size_t{width} * rows);
      for (uint32_t row = 0; row < rows; ++row)
        std::memcpy(&out->plane[i][size_t{row} * width], raw + size_t{row} * stride, width);
    }
    return true;
  }

 private:
  static uint32_t low32(const void* pointer) {
    return static_cast<uint32_t>(reinterpret_cast<uintptr_t>(pointer));
  }

  unsigned char* stage(uint32_t which, uint32_t bytes) {
    return port_.input_buffer(
        port_.sandbox().invoke_sandbox_function(interspec_vpx_stage, which, bytes), bytes,
        "stage");
  }

  Port port_;
  uint32_t encoder_ = 0, decoder_ = 0;
};

}  // namespace

int main(int argc, char** argv) {
  if (argc < 4 || argc > 5) {
    std::fprintf(stderr, "usage: %s WIDTH HEIGHT FRAMES [FAULT_MODE]\n", argv[0]);
    return 2;
  }
  try {
    const unsigned width = static_cast<unsigned>(std::stoul(argv[1]));
    const unsigned height = static_cast<unsigned>(std::stoul(argv[2]));
    const unsigned frames = static_cast<unsigned>(std::stoul(argv[3]));
    const uint32_t fault = argc == 5 ? static_cast<uint32_t>(std::stoul(argv[4])) : 0;
    if (!width || !height || !frames || width % 2 || height % 2 || width > kMaxDimension ||
        height > kMaxDimension)
      throw std::runtime_error("arguments");
    Engine engine(width, height);
#ifdef INTERSPEC_FAULT_TESTS
    if (fault) engine.port().sandbox().invoke_sandbox_function(interspec_vpx_fault, fault);
    if (const char* poc = std::getenv("INTERSPEC_TEST_POC_FLAGS"))
      engine.port().sandbox().invoke_sandbox_function(
          interspec_vpx_poc, static_cast<uint32_t>(std::stoul(poc)));
#else
    if (fault) throw std::runtime_error("fault_requires_test_build");
#endif

    vpx_workload::Frame frame;
    vpx_workload::Fnv encoded_hash, decoded_hash;
    uint64_t encoded_bytes = 0;
    unsigned packets = 0, decoded_frames = 0;
    Packet packet;
    Decoded decoded;
    const auto start = std::chrono::steady_clock::now();
    // One extra pass with a null image flushes the encoder.
    for (unsigned index = 0; index <= frames; ++index) {
      vpx_image_t image{};
      if (index < frames) {
        vpx_workload::fill(frame, width, height, index);
        image.fmt = VPX_IMG_FMT_I420;
        image.w = image.d_w = width;
        image.h = image.d_h = height;
        image.bit_depth = 8;
        image.x_chroma_shift = image.y_chroma_shift = 1;
        image.bps = 12;
        image.planes[0] = frame.y.data();
        image.planes[1] = frame.u.data();
        image.planes[2] = frame.v.data();
        image.stride[0] = static_cast<int>(width);
        image.stride[1] = image.stride[2] = static_cast<int>(width / 2);
        // Fields of T's image that the encoder has no use for.
        image.user_priv = reinterpret_cast<void*>(uintptr_t{0x5ec2e701});
        image.img_data = frame.y.data();
        image.fb_priv = reinterpret_cast<void*>(uintptr_t{0x5ec2e703});
        image.img_data_owner = 1;
      }
      if (engine.encode(index < frames ? &image : nullptr, index, 1, 0,
                        vpx_workload::kDeadline) != 0)
        throw std::runtime_error("encode");
      uint32_t iter = 0;
      while (engine.get_cx_data(&iter, &packet)) {
        ++packets;
        encoded_bytes += packet.data.size();
        encoded_hash.add(packet.data.data(), packet.data.size());
        if (engine.decode(packet.data, 0) != 0) throw std::runtime_error("decode");
        uint32_t frame_iter = 0;
        while (engine.get_frame(&frame_iter, &decoded)) {
          ++decoded_frames;
          for (const auto& plane : decoded.plane) decoded_hash.add(plane.data(), plane.size());
        }
      }
    }
    const auto finish = std::chrono::steady_clock::now();
#ifdef INTERSPEC_FAULT_TESTS
    // What T's own copy of the last raw frame looks like after the run.
    std::fprintf(stderr, "INTERSPEC_T_OBSERVE boundary=ffmpeg_libvpx luma_first_byte=0x%02x\n",
                 static_cast<unsigned>(frame.y[0]));
#endif
    std::printf(
        "VPX_BENCH variant=%s frames=%u width=%u height=%u packets=%u encoded_bytes=%llu "
        "encoded_fnv=%016llx decoded_frames=%u decoded_fnv=%016llx checks=%llu "
        "elapsed_ns=%llu\n",
        kVariant, frames, width, height, packets,
        static_cast<unsigned long long>(encoded_bytes),
        static_cast<unsigned long long>(encoded_hash.state), decoded_frames,
        static_cast<unsigned long long>(decoded_hash.state),
        static_cast<unsigned long long>(engine.port().checks()),
        static_cast<unsigned long long>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(finish - start).count()));
    return 0;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "vpx benchmark error: %s\n", error.what());
    return 1;
  }
}
