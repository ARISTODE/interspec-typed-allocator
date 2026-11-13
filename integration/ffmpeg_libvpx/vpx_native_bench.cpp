// Native reference for the ffmpeg/libvpx port (tracker item I7): the workload
// of vpx_app_bench.cpp against libvpx without a sandbox, same output format.
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>

#include <vpx/vp8cx.h>
#include <vpx/vp8dx.h>
#include <vpx/vpx_decoder.h>
#include <vpx/vpx_encoder.h>

#include "vpx_workload.h"

int main(int argc, char** argv) {
  if (argc != 4) {
    std::fprintf(stderr, "usage: %s WIDTH HEIGHT FRAMES\n", argv[0]);
    return 2;
  }
  try {
    const unsigned width = static_cast<unsigned>(std::stoul(argv[1]));
    const unsigned height = static_cast<unsigned>(std::stoul(argv[2]));
    const unsigned frames = static_cast<unsigned>(std::stoul(argv[3]));
    if (!width || !height || !frames || width % 2 || height % 2)
      throw std::runtime_error("arguments");

    vpx_codec_enc_cfg_t cfg;
    if (vpx_codec_enc_config_default(vpx_codec_vp8_cx(), &cfg, 0) != VPX_CODEC_OK)
      throw std::runtime_error("enc_config_default");
    cfg.g_w = width;
    cfg.g_h = height;
    cfg.g_timebase.num = 1;
    cfg.g_timebase.den = 30;
    cfg.g_threads = 1;
    cfg.g_lag_in_frames = 0;
    cfg.rc_target_bitrate = vpx_workload::kBitrateKbps;
    vpx_codec_ctx_t encoder, decoder;
    if (vpx_codec_enc_init(&encoder, vpx_codec_vp8_cx(), &cfg, 0) != VPX_CODEC_OK)
      throw std::runtime_error("enc_init");
    if (vpx_codec_control(&encoder, VP8E_SET_CPUUSED, vpx_workload::kCpuUsed) != VPX_CODEC_OK)
      throw std::runtime_error("set_cpuused");
    vpx_codec_dec_cfg_t dec_cfg{1, width, height};
    if (vpx_codec_dec_init(&decoder, vpx_codec_vp8_dx(), &dec_cfg, 0) != VPX_CODEC_OK)
      throw std::runtime_error("dec_init");

    vpx_workload::Frame frame;
    vpx_workload::Fnv encoded_hash, decoded_hash;
    uint64_t encoded_bytes = 0;
    unsigned packets = 0, decoded_frames = 0;
    const auto start = std::chrono::steady_clock::now();
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
      }
      if (vpx_codec_encode(&encoder, index < frames ? &image : nullptr, index, 1, 0,
                           vpx_workload::kDeadline) != VPX_CODEC_OK)
        throw std::runtime_error("encode");
      vpx_codec_iter_t iter = nullptr;
      while (const vpx_codec_cx_pkt_t* packet = vpx_codec_get_cx_data(&encoder, &iter)) {
        if (packet->kind != VPX_CODEC_CX_FRAME_PKT) continue;
        const auto* data = static_cast<const unsigned char*>(packet->data.frame.buf);
        const size_t size = packet->data.frame.sz;
        ++packets;
        encoded_bytes += size;
        encoded_hash.add(data, size);
        std::vector<unsigned char> copy(data, data + size);
        if (vpx_codec_decode(&decoder, copy.data(), static_cast<unsigned>(size), nullptr, 0) !=
            VPX_CODEC_OK)
          throw std::runtime_error("decode");
        vpx_codec_iter_t frame_iter = nullptr;
        while (const vpx_image_t* out = vpx_codec_get_frame(&decoder, &frame_iter)) {
          ++decoded_frames;
          for (int i = 0; i < 3; ++i) {
            const unsigned w = i == 0 ? out->d_w : (out->d_w + 1) / 2;
            const unsigned rows = i == 0 ? out->d_h : (out->d_h + 1) / 2;
            for (unsigned row = 0; row < rows; ++row)
              decoded_hash.add(out->planes[i] + size_t{row} * out->stride[i], w);
          }
        }
      }
    }
    const auto finish = std::chrono::steady_clock::now();
    std::printf(
        "VPX_BENCH variant=native frames=%u width=%u height=%u packets=%u encoded_bytes=%llu "
        "encoded_fnv=%016llx decoded_frames=%u decoded_fnv=%016llx checks=0 elapsed_ns=%llu\n",
        frames, width, height, packets, static_cast<unsigned long long>(encoded_bytes),
        static_cast<unsigned long long>(encoded_hash.state), decoded_frames,
        static_cast<unsigned long long>(decoded_hash.state),
        static_cast<unsigned long long>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(finish - start).count()));
    vpx_codec_destroy(&encoder);
    vpx_codec_destroy(&decoder);
    return 0;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "vpx benchmark error: %s\n", error.what());
    return 1;
  }
}
