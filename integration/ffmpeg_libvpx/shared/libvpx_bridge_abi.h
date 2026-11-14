#pragma once

#include <stdint.h>

#include <vpx/vp8cx.h>
#include <vpx/vpx_decoder.h>
#include <vpx/vpx_encoder.h>
#include <vpx/vpx_image.h>

#ifdef __cplusplus
extern "C" {
#endif

#define LIBVPX_BRIDGE_PACKED __attribute__((packed))

enum
{
  LIBVPX_BRIDGE_IFACE_VP8_DX = 1,
  LIBVPX_BRIDGE_IFACE_VP9_DX = 2,
  LIBVPX_BRIDGE_IFACE_VP8_CX = 3,
  LIBVPX_BRIDGE_IFACE_VP9_CX = 4,
};

typedef struct LIBVPX_BRIDGE_PACKED libvpx_bridge_fixed_buf_s
{
  uint32_t buf_addr;
  uint32_t size;
} libvpx_bridge_fixed_buf_t;

typedef struct LIBVPX_BRIDGE_PACKED libvpx_bridge_rational_s
{
  int32_t num;
  int32_t den;
} libvpx_bridge_rational_t;

typedef struct LIBVPX_BRIDGE_PACKED libvpx_bridge_dec_cfg_s
{
  uint32_t threads;
  uint32_t w;
  uint32_t h;
} libvpx_bridge_dec_cfg_t;

typedef struct LIBVPX_BRIDGE_PACKED libvpx_bridge_image_s
{
  uint32_t present;
  uint32_t iter_state;

  int32_t fmt;
  int32_t cs;
  int32_t range;

  uint32_t w;
  uint32_t h;
  uint32_t bit_depth;
  uint32_t d_w;
  uint32_t d_h;
  uint32_t r_w;
  uint32_t r_h;
  uint32_t x_chroma_shift;
  uint32_t y_chroma_shift;

  uint32_t planes[4];
  int32_t stride[4];

  int32_t bps;
  uint32_t user_priv;
  uint32_t img_data;
  int32_t img_data_owner;
  int32_t self_allocd;
  uint32_t fb_priv;
} libvpx_bridge_image_t;

typedef struct LIBVPX_BRIDGE_PACKED libvpx_bridge_enc_cfg_s
{
  uint32_t g_usage;
  uint32_t g_threads;
  uint32_t g_profile;
  uint32_t g_w;
  uint32_t g_h;
  int32_t g_bit_depth;
  uint32_t g_input_bit_depth;
  libvpx_bridge_rational_t g_timebase;
  uint32_t g_error_resilient;
  int32_t g_pass;
  uint32_t g_lag_in_frames;

  uint32_t rc_dropframe_thresh;
  uint32_t rc_resize_allowed;
  uint32_t rc_scaled_width;
  uint32_t rc_scaled_height;
  uint32_t rc_resize_up_thresh;
  uint32_t rc_resize_down_thresh;
  int32_t rc_end_usage;
  libvpx_bridge_fixed_buf_t rc_twopass_stats_in;
  libvpx_bridge_fixed_buf_t rc_firstpass_mb_stats_in;
  uint32_t rc_target_bitrate;
  uint32_t rc_min_quantizer;
  uint32_t rc_max_quantizer;
  uint32_t rc_undershoot_pct;
  uint32_t rc_overshoot_pct;
  uint32_t rc_buf_sz;
  uint32_t rc_buf_initial_sz;
  uint32_t rc_buf_optimal_sz;
  uint32_t rc_2pass_vbr_bias_pct;
  uint32_t rc_2pass_vbr_minsection_pct;
  uint32_t rc_2pass_vbr_maxsection_pct;
  uint32_t rc_2pass_vbr_corpus_complexity;

  int32_t kf_mode;
  uint32_t kf_min_dist;
  uint32_t kf_max_dist;

  uint32_t ss_number_layers;
  int32_t ss_enable_auto_alt_ref[VPX_SS_MAX_LAYERS];
  uint32_t ss_target_bitrate[VPX_SS_MAX_LAYERS];

  uint32_t ts_number_layers;
  uint32_t ts_target_bitrate[VPX_TS_MAX_LAYERS];
  uint32_t ts_rate_decimator[VPX_TS_MAX_LAYERS];
  uint32_t ts_periodicity;
  uint32_t ts_layer_id[VPX_TS_MAX_PERIODICITY];

  uint32_t layer_target_bitrate[VPX_MAX_LAYERS];
  int32_t temporal_layering_mode;
  int32_t use_vizier_rc_params;

  libvpx_bridge_rational_t active_wq_factor;
  libvpx_bridge_rational_t err_per_mb_factor;
  libvpx_bridge_rational_t sr_default_decay_limit;
  libvpx_bridge_rational_t sr_diff_factor;
  libvpx_bridge_rational_t kf_err_per_mb_factor;
  libvpx_bridge_rational_t kf_frame_min_boost_factor;
  libvpx_bridge_rational_t kf_frame_max_boost_first_factor;
  libvpx_bridge_rational_t kf_frame_max_boost_subs_factor;
  libvpx_bridge_rational_t kf_max_total_boost_factor;
  libvpx_bridge_rational_t gf_max_total_boost_factor;
  libvpx_bridge_rational_t gf_frame_max_boost_factor;
  libvpx_bridge_rational_t zm_factor;
  libvpx_bridge_rational_t rd_mult_inter_qp_fac;
  libvpx_bridge_rational_t rd_mult_arf_qp_fac;
  libvpx_bridge_rational_t rd_mult_key_qp_fac;
} libvpx_bridge_enc_cfg_t;

typedef struct LIBVPX_BRIDGE_PACKED libvpx_bridge_packet_s
{
  uint32_t present;
  uint32_t iter_state;
  int32_t kind;

  uint32_t buf_addr;
  uint32_t size;
  uint64_t pts;
  uint32_t duration;
  uint32_t flags;
  int32_t partition_id;
  uint32_t width[VPX_SS_MAX_LAYERS];
  uint32_t height[VPX_SS_MAX_LAYERS];
  uint8_t spatial_layer_encoded[VPX_SS_MAX_LAYERS];

  uint32_t psnr_samples[4];
  uint64_t psnr_sse[4];
  double psnr_value[4];
} libvpx_bridge_packet_t;

typedef struct LIBVPX_BRIDGE_PACKED libvpx_bridge_roi_map_s
{
  uint8_t enabled;
  uint32_t roi_map_addr;
  uint32_t rows;
  uint32_t cols;
  int32_t delta_q[8];
  int32_t delta_lf[8];
  int32_t skip[8];
  int32_t ref_frame[8];
  uint32_t static_threshold[4];
} libvpx_bridge_roi_map_t;

typedef struct LIBVPX_BRIDGE_PACKED libvpx_bridge_svc_layer_id_s
{
  int32_t spatial_layer_id;
  int32_t temporal_layer_id;
  int32_t temporal_layer_id_per_spatial[VPX_SS_MAX_LAYERS];
} libvpx_bridge_svc_layer_id_t;

typedef struct LIBVPX_BRIDGE_PACKED libvpx_bridge_svc_parameters_s
{
  int32_t max_quantizers[VPX_MAX_LAYERS];
  int32_t min_quantizers[VPX_MAX_LAYERS];
  int32_t scaling_factor_num[VPX_MAX_LAYERS];
  int32_t scaling_factor_den[VPX_MAX_LAYERS];
  int32_t speed_per_layer[VPX_MAX_LAYERS];
  int32_t temporal_layering_mode;
  int32_t loopfilter_ctrl[VPX_MAX_LAYERS];
} libvpx_bridge_svc_parameters_t;

typedef struct LIBVPX_BRIDGE_PACKED libvpx_bridge_svc_ref_frame_config_s
{
  int32_t lst_fb_idx[VPX_SS_MAX_LAYERS];
  int32_t gld_fb_idx[VPX_SS_MAX_LAYERS];
  int32_t alt_fb_idx[VPX_SS_MAX_LAYERS];
  int32_t update_buffer_slot[VPX_SS_MAX_LAYERS];
  int32_t update_last[VPX_SS_MAX_LAYERS];
  int32_t update_golden[VPX_SS_MAX_LAYERS];
  int32_t update_alt_ref[VPX_SS_MAX_LAYERS];
  int32_t reference_last[VPX_SS_MAX_LAYERS];
  int32_t reference_golden[VPX_SS_MAX_LAYERS];
  int32_t reference_alt_ref[VPX_SS_MAX_LAYERS];
  int64_t duration[VPX_SS_MAX_LAYERS];
} libvpx_bridge_svc_ref_frame_config_t;

#ifdef __cplusplus
}
#endif
