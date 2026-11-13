#include "../shared/libvpx_bridge_abi.h"

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include <vpx/vp8dx.h>

static vpx_codec_iface_t*
bridge_iface(uint32_t iface_token)
{
  switch (iface_token) {
    case LIBVPX_BRIDGE_IFACE_VP8_DX:
      return vpx_codec_vp8_dx();
    case LIBVPX_BRIDGE_IFACE_VP9_DX:
      return vpx_codec_vp9_dx();
    case LIBVPX_BRIDGE_IFACE_VP8_CX:
      return vpx_codec_vp8_cx();
    case LIBVPX_BRIDGE_IFACE_VP9_CX:
      return vpx_codec_vp9_cx();
    default:
      return NULL;
  }
}

static vpx_codec_ctx_t*
bridge_ctx(uint32_t ctx_addr)
{
  return (vpx_codec_ctx_t*)(uintptr_t) ctx_addr;
}

static void
bridge_rational_to_native(vpx_rational_t* out,
                          const libvpx_bridge_rational_t* in)
{
  out->num = in->num;
  out->den = in->den;
}

static void
native_rational_to_bridge(libvpx_bridge_rational_t* out,
                          const vpx_rational_t* in)
{
  out->num = in->num;
  out->den = in->den;
}

static void
bridge_fixed_buf_to_native(vpx_fixed_buf_t* out,
                           const libvpx_bridge_fixed_buf_t* in)
{
  out->buf = (void*)(uintptr_t) in->buf_addr;
  out->sz = (size_t) in->size;
}

static void
native_fixed_buf_to_bridge(libvpx_bridge_fixed_buf_t* out,
                           const vpx_fixed_buf_t* in)
{
  out->buf_addr = (uint32_t)(uintptr_t) in->buf;
  out->size = (uint32_t) in->sz;
}

static void
bridge_dec_cfg_to_native(vpx_codec_dec_cfg_t* out,
                         const libvpx_bridge_dec_cfg_t* in)
{
  memset(out, 0, sizeof(*out));
  out->threads = in->threads;
  out->w = in->w;
  out->h = in->h;
}

static void
bridge_image_to_native(vpx_image_t* out, const libvpx_bridge_image_t* in)
{
  int i;
  memset(out, 0, sizeof(*out));
  out->fmt = (vpx_img_fmt_t) in->fmt;
  out->cs = (vpx_color_space_t) in->cs;
  out->range = (vpx_color_range_t) in->range;
  out->w = in->w;
  out->h = in->h;
  out->bit_depth = in->bit_depth;
  out->d_w = in->d_w;
  out->d_h = in->d_h;
  out->r_w = in->r_w;
  out->r_h = in->r_h;
  out->x_chroma_shift = in->x_chroma_shift;
  out->y_chroma_shift = in->y_chroma_shift;
  for (i = 0; i < 4; ++i) {
    out->planes[i] = (unsigned char*)(uintptr_t) in->planes[i];
    out->stride[i] = in->stride[i];
  }
  out->bps = in->bps;
  out->user_priv = (void*)(uintptr_t) in->user_priv;
  out->img_data = (unsigned char*)(uintptr_t) in->img_data;
  out->img_data_owner = in->img_data_owner;
  out->self_allocd = in->self_allocd;
  out->fb_priv = (void*)(uintptr_t) in->fb_priv;
}

static void
native_image_to_bridge(libvpx_bridge_image_t* out, const vpx_image_t* in)
{
  int i;
  memset(out, 0, sizeof(*out));
  out->present = in != NULL ? 1u : 0u;
  if (!in) {
    return;
  }
  out->fmt = (int32_t) in->fmt;
  out->cs = (int32_t) in->cs;
  out->range = (int32_t) in->range;
  out->w = in->w;
  out->h = in->h;
  out->bit_depth = in->bit_depth;
  out->d_w = in->d_w;
  out->d_h = in->d_h;
  out->r_w = in->r_w;
  out->r_h = in->r_h;
  out->x_chroma_shift = in->x_chroma_shift;
  out->y_chroma_shift = in->y_chroma_shift;
  for (i = 0; i < 4; ++i) {
    out->planes[i] = (uint32_t)(uintptr_t) in->planes[i];
    out->stride[i] = in->stride[i];
  }
  out->bps = in->bps;
  out->user_priv = (uint32_t)(uintptr_t) in->user_priv;
  out->img_data = (uint32_t)(uintptr_t) in->img_data;
  out->img_data_owner = in->img_data_owner;
  out->self_allocd = in->self_allocd;
  out->fb_priv = (uint32_t)(uintptr_t) in->fb_priv;
}

static void
bridge_enc_cfg_to_native(vpx_codec_enc_cfg_t* out,
                         const libvpx_bridge_enc_cfg_t* in)
{
  memset(out, 0, sizeof(*out));

  out->g_usage = in->g_usage;
  out->g_threads = in->g_threads;
  out->g_profile = in->g_profile;
  out->g_w = in->g_w;
  out->g_h = in->g_h;
  out->g_bit_depth = (vpx_bit_depth_t) in->g_bit_depth;
  out->g_input_bit_depth = in->g_input_bit_depth;
  bridge_rational_to_native(&out->g_timebase, &in->g_timebase);
  out->g_error_resilient = (vpx_codec_er_flags_t) in->g_error_resilient;
  out->g_pass = (enum vpx_enc_pass) in->g_pass;
  out->g_lag_in_frames = in->g_lag_in_frames;

  out->rc_dropframe_thresh = in->rc_dropframe_thresh;
  out->rc_resize_allowed = in->rc_resize_allowed;
  out->rc_scaled_width = in->rc_scaled_width;
  out->rc_scaled_height = in->rc_scaled_height;
  out->rc_resize_up_thresh = in->rc_resize_up_thresh;
  out->rc_resize_down_thresh = in->rc_resize_down_thresh;
  out->rc_end_usage = (enum vpx_rc_mode) in->rc_end_usage;
  bridge_fixed_buf_to_native(&out->rc_twopass_stats_in, &in->rc_twopass_stats_in);
  bridge_fixed_buf_to_native(&out->rc_firstpass_mb_stats_in,
                             &in->rc_firstpass_mb_stats_in);
  out->rc_target_bitrate = in->rc_target_bitrate;
  out->rc_min_quantizer = in->rc_min_quantizer;
  out->rc_max_quantizer = in->rc_max_quantizer;
  out->rc_undershoot_pct = in->rc_undershoot_pct;
  out->rc_overshoot_pct = in->rc_overshoot_pct;
  out->rc_buf_sz = in->rc_buf_sz;
  out->rc_buf_initial_sz = in->rc_buf_initial_sz;
  out->rc_buf_optimal_sz = in->rc_buf_optimal_sz;
  out->rc_2pass_vbr_bias_pct = in->rc_2pass_vbr_bias_pct;
  out->rc_2pass_vbr_minsection_pct = in->rc_2pass_vbr_minsection_pct;
  out->rc_2pass_vbr_maxsection_pct = in->rc_2pass_vbr_maxsection_pct;
  out->rc_2pass_vbr_corpus_complexity = in->rc_2pass_vbr_corpus_complexity;

  out->kf_mode = (enum vpx_kf_mode) in->kf_mode;
  out->kf_min_dist = in->kf_min_dist;
  out->kf_max_dist = in->kf_max_dist;

  out->ss_number_layers = in->ss_number_layers;
  memcpy(out->ss_enable_auto_alt_ref,
         in->ss_enable_auto_alt_ref,
         sizeof(out->ss_enable_auto_alt_ref));
  memcpy(out->ss_target_bitrate,
         in->ss_target_bitrate,
         sizeof(out->ss_target_bitrate));

  out->ts_number_layers = in->ts_number_layers;
  memcpy(out->ts_target_bitrate,
         in->ts_target_bitrate,
         sizeof(out->ts_target_bitrate));
  memcpy(out->ts_rate_decimator,
         in->ts_rate_decimator,
         sizeof(out->ts_rate_decimator));
  out->ts_periodicity = in->ts_periodicity;
  memcpy(out->ts_layer_id, in->ts_layer_id, sizeof(out->ts_layer_id));
  memcpy(out->layer_target_bitrate,
         in->layer_target_bitrate,
         sizeof(out->layer_target_bitrate));
  out->temporal_layering_mode = in->temporal_layering_mode;
  out->use_vizier_rc_params = in->use_vizier_rc_params;

  bridge_rational_to_native(&out->active_wq_factor, &in->active_wq_factor);
  bridge_rational_to_native(&out->err_per_mb_factor, &in->err_per_mb_factor);
  bridge_rational_to_native(&out->sr_default_decay_limit,
                            &in->sr_default_decay_limit);
  bridge_rational_to_native(&out->sr_diff_factor, &in->sr_diff_factor);
  bridge_rational_to_native(&out->kf_err_per_mb_factor,
                            &in->kf_err_per_mb_factor);
  bridge_rational_to_native(&out->kf_frame_min_boost_factor,
                            &in->kf_frame_min_boost_factor);
  bridge_rational_to_native(&out->kf_frame_max_boost_first_factor,
                            &in->kf_frame_max_boost_first_factor);
  bridge_rational_to_native(&out->kf_frame_max_boost_subs_factor,
                            &in->kf_frame_max_boost_subs_factor);
  bridge_rational_to_native(&out->kf_max_total_boost_factor,
                            &in->kf_max_total_boost_factor);
  bridge_rational_to_native(&out->gf_max_total_boost_factor,
                            &in->gf_max_total_boost_factor);
  bridge_rational_to_native(&out->gf_frame_max_boost_factor,
                            &in->gf_frame_max_boost_factor);
  bridge_rational_to_native(&out->zm_factor, &in->zm_factor);
  bridge_rational_to_native(&out->rd_mult_inter_qp_fac,
                            &in->rd_mult_inter_qp_fac);
  bridge_rational_to_native(&out->rd_mult_arf_qp_fac,
                            &in->rd_mult_arf_qp_fac);
  bridge_rational_to_native(&out->rd_mult_key_qp_fac,
                            &in->rd_mult_key_qp_fac);
}

static void
native_enc_cfg_to_bridge(libvpx_bridge_enc_cfg_t* out,
                         const vpx_codec_enc_cfg_t* in)
{
  memset(out, 0, sizeof(*out));

  out->g_usage = in->g_usage;
  out->g_threads = in->g_threads;
  out->g_profile = in->g_profile;
  out->g_w = in->g_w;
  out->g_h = in->g_h;
  out->g_bit_depth = (int32_t) in->g_bit_depth;
  out->g_input_bit_depth = in->g_input_bit_depth;
  native_rational_to_bridge(&out->g_timebase, &in->g_timebase);
  out->g_error_resilient = (uint32_t) in->g_error_resilient;
  out->g_pass = (int32_t) in->g_pass;
  out->g_lag_in_frames = in->g_lag_in_frames;

  out->rc_dropframe_thresh = in->rc_dropframe_thresh;
  out->rc_resize_allowed = in->rc_resize_allowed;
  out->rc_scaled_width = in->rc_scaled_width;
  out->rc_scaled_height = in->rc_scaled_height;
  out->rc_resize_up_thresh = in->rc_resize_up_thresh;
  out->rc_resize_down_thresh = in->rc_resize_down_thresh;
  out->rc_end_usage = (int32_t) in->rc_end_usage;
  native_fixed_buf_to_bridge(&out->rc_twopass_stats_in, &in->rc_twopass_stats_in);
  native_fixed_buf_to_bridge(&out->rc_firstpass_mb_stats_in,
                             &in->rc_firstpass_mb_stats_in);
  out->rc_target_bitrate = in->rc_target_bitrate;
  out->rc_min_quantizer = in->rc_min_quantizer;
  out->rc_max_quantizer = in->rc_max_quantizer;
  out->rc_undershoot_pct = in->rc_undershoot_pct;
  out->rc_overshoot_pct = in->rc_overshoot_pct;
  out->rc_buf_sz = in->rc_buf_sz;
  out->rc_buf_initial_sz = in->rc_buf_initial_sz;
  out->rc_buf_optimal_sz = in->rc_buf_optimal_sz;
  out->rc_2pass_vbr_bias_pct = in->rc_2pass_vbr_bias_pct;
  out->rc_2pass_vbr_minsection_pct = in->rc_2pass_vbr_minsection_pct;
  out->rc_2pass_vbr_maxsection_pct = in->rc_2pass_vbr_maxsection_pct;
  out->rc_2pass_vbr_corpus_complexity = in->rc_2pass_vbr_corpus_complexity;

  out->kf_mode = (int32_t) in->kf_mode;
  out->kf_min_dist = in->kf_min_dist;
  out->kf_max_dist = in->kf_max_dist;

  out->ss_number_layers = in->ss_number_layers;
  memcpy(out->ss_enable_auto_alt_ref,
         in->ss_enable_auto_alt_ref,
         sizeof(out->ss_enable_auto_alt_ref));
  memcpy(out->ss_target_bitrate,
         in->ss_target_bitrate,
         sizeof(out->ss_target_bitrate));

  out->ts_number_layers = in->ts_number_layers;
  memcpy(out->ts_target_bitrate,
         in->ts_target_bitrate,
         sizeof(out->ts_target_bitrate));
  memcpy(out->ts_rate_decimator,
         in->ts_rate_decimator,
         sizeof(out->ts_rate_decimator));
  out->ts_periodicity = in->ts_periodicity;
  memcpy(out->ts_layer_id, in->ts_layer_id, sizeof(out->ts_layer_id));
  memcpy(out->layer_target_bitrate,
         in->layer_target_bitrate,
         sizeof(out->layer_target_bitrate));
  out->temporal_layering_mode = in->temporal_layering_mode;
  out->use_vizier_rc_params = in->use_vizier_rc_params;

  native_rational_to_bridge(&out->active_wq_factor, &in->active_wq_factor);
  native_rational_to_bridge(&out->err_per_mb_factor, &in->err_per_mb_factor);
  native_rational_to_bridge(&out->sr_default_decay_limit,
                            &in->sr_default_decay_limit);
  native_rational_to_bridge(&out->sr_diff_factor, &in->sr_diff_factor);
  native_rational_to_bridge(&out->kf_err_per_mb_factor,
                            &in->kf_err_per_mb_factor);
  native_rational_to_bridge(&out->kf_frame_min_boost_factor,
                            &in->kf_frame_min_boost_factor);
  native_rational_to_bridge(&out->kf_frame_max_boost_first_factor,
                            &in->kf_frame_max_boost_first_factor);
  native_rational_to_bridge(&out->kf_frame_max_boost_subs_factor,
                            &in->kf_frame_max_boost_subs_factor);
  native_rational_to_bridge(&out->kf_max_total_boost_factor,
                            &in->kf_max_total_boost_factor);
  native_rational_to_bridge(&out->gf_max_total_boost_factor,
                            &in->gf_max_total_boost_factor);
  native_rational_to_bridge(&out->gf_frame_max_boost_factor,
                            &in->gf_frame_max_boost_factor);
  native_rational_to_bridge(&out->zm_factor, &in->zm_factor);
  native_rational_to_bridge(&out->rd_mult_inter_qp_fac,
                            &in->rd_mult_inter_qp_fac);
  native_rational_to_bridge(&out->rd_mult_arf_qp_fac,
                            &in->rd_mult_arf_qp_fac);
  native_rational_to_bridge(&out->rd_mult_key_qp_fac,
                            &in->rd_mult_key_qp_fac);
}

static void
bridge_roi_map_to_native(vpx_roi_map_t* out, const libvpx_bridge_roi_map_t* in)
{
  memset(out, 0, sizeof(*out));
  out->enabled = in->enabled;
  out->roi_map = (unsigned char*)(uintptr_t) in->roi_map_addr;
  out->rows = in->rows;
  out->cols = in->cols;
  memcpy(out->delta_q, in->delta_q, sizeof(out->delta_q));
  memcpy(out->delta_lf, in->delta_lf, sizeof(out->delta_lf));
  memcpy(out->skip, in->skip, sizeof(out->skip));
  memcpy(out->ref_frame, in->ref_frame, sizeof(out->ref_frame));
  memcpy(out->static_threshold,
         in->static_threshold,
         sizeof(out->static_threshold));
}

static void
bridge_svc_layer_id_to_native(vpx_svc_layer_id_t* out,
                              const libvpx_bridge_svc_layer_id_t* in)
{
  memset(out, 0, sizeof(*out));
  out->spatial_layer_id = in->spatial_layer_id;
  out->temporal_layer_id = in->temporal_layer_id;
  memcpy(out->temporal_layer_id_per_spatial,
         in->temporal_layer_id_per_spatial,
         sizeof(out->temporal_layer_id_per_spatial));
}

static void
bridge_svc_parameters_to_native(vpx_svc_extra_cfg_t* out,
                                const libvpx_bridge_svc_parameters_t* in)
{
  memset(out, 0, sizeof(*out));
  memcpy(out->max_quantizers, in->max_quantizers, sizeof(out->max_quantizers));
  memcpy(out->min_quantizers, in->min_quantizers, sizeof(out->min_quantizers));
  memcpy(out->scaling_factor_num,
         in->scaling_factor_num,
         sizeof(out->scaling_factor_num));
  memcpy(out->scaling_factor_den,
         in->scaling_factor_den,
         sizeof(out->scaling_factor_den));
  memcpy(out->speed_per_layer, in->speed_per_layer, sizeof(out->speed_per_layer));
  out->temporal_layering_mode = in->temporal_layering_mode;
  memcpy(out->loopfilter_ctrl, in->loopfilter_ctrl, sizeof(out->loopfilter_ctrl));
}

static void
bridge_svc_ref_frame_config_to_native(vpx_svc_ref_frame_config_t* out,
                                      const libvpx_bridge_svc_ref_frame_config_t* in)
{
  memset(out, 0, sizeof(*out));
  memcpy(out->lst_fb_idx, in->lst_fb_idx, sizeof(out->lst_fb_idx));
  memcpy(out->gld_fb_idx, in->gld_fb_idx, sizeof(out->gld_fb_idx));
  memcpy(out->alt_fb_idx, in->alt_fb_idx, sizeof(out->alt_fb_idx));
  memcpy(out->update_buffer_slot,
         in->update_buffer_slot,
         sizeof(out->update_buffer_slot));
  memcpy(out->update_last, in->update_last, sizeof(out->update_last));
  memcpy(out->update_golden, in->update_golden, sizeof(out->update_golden));
  memcpy(out->update_alt_ref, in->update_alt_ref, sizeof(out->update_alt_ref));
  memcpy(out->reference_last, in->reference_last, sizeof(out->reference_last));
  memcpy(out->reference_golden, in->reference_golden, sizeof(out->reference_golden));
  memcpy(out->reference_alt_ref,
         in->reference_alt_ref,
         sizeof(out->reference_alt_ref));
  memcpy(out->duration, in->duration, sizeof(out->duration));
}

static void
native_packet_to_bridge(libvpx_bridge_packet_t* out,
                        const vpx_codec_cx_pkt_t* in)
{
  memset(out, 0, sizeof(*out));
  out->present = in != NULL ? 1u : 0u;
  if (!in) {
    return;
  }

  out->kind = (int32_t) in->kind;
  switch (in->kind) {
    case VPX_CODEC_CX_FRAME_PKT:
      out->buf_addr = (uint32_t)(uintptr_t) in->data.frame.buf;
      out->size = (uint32_t) in->data.frame.sz;
      out->pts = (uint64_t) in->data.frame.pts;
      out->duration = (uint32_t) in->data.frame.duration;
      out->flags = (uint32_t) in->data.frame.flags;
      out->partition_id = in->data.frame.partition_id;
      memcpy(out->width, in->data.frame.width, sizeof(out->width));
      memcpy(out->height, in->data.frame.height, sizeof(out->height));
      memcpy(out->spatial_layer_encoded,
             in->data.frame.spatial_layer_encoded,
             sizeof(out->spatial_layer_encoded));
      break;
    case VPX_CODEC_STATS_PKT:
      out->buf_addr = (uint32_t)(uintptr_t) in->data.twopass_stats.buf;
      out->size = (uint32_t) in->data.twopass_stats.sz;
      break;
    case VPX_CODEC_FPMB_STATS_PKT:
      out->buf_addr = (uint32_t)(uintptr_t) in->data.firstpass_mb_stats.buf;
      out->size = (uint32_t) in->data.firstpass_mb_stats.sz;
      break;
    case VPX_CODEC_PSNR_PKT:
      memcpy(out->psnr_samples, in->data.psnr.samples, sizeof(out->psnr_samples));
      memcpy(out->psnr_sse, in->data.psnr.sse, sizeof(out->psnr_sse));
      memcpy(out->psnr_value, in->data.psnr.psnr, sizeof(out->psnr_value));
      break;
    case VPX_CODEC_CUSTOM_PKT:
      out->buf_addr = (uint32_t)(uintptr_t) in->data.raw.buf;
      out->size = (uint32_t) in->data.raw.sz;
      break;
    default:
      break;
  }
}

uint32_t
libvpx_rlbox_codec_ctx_create(void)
{
  vpx_codec_ctx_t* ctx = (vpx_codec_ctx_t*) malloc(sizeof(*ctx));
  if (!ctx) {
    return 0;
  }
  memset(ctx, 0, sizeof(*ctx));
  return (uint32_t)(uintptr_t) ctx;
}

void
libvpx_rlbox_codec_ctx_free(uint32_t ctx_addr)
{
  vpx_codec_ctx_t* ctx = bridge_ctx(ctx_addr);
  if (ctx) {
    free(ctx);
  }
}

vpx_codec_caps_t
libvpx_rlbox_codec_get_caps(uint32_t iface_token)
{
  vpx_codec_iface_t* iface = bridge_iface(iface_token);
  if (!iface) {
    return 0;
  }
  return vpx_codec_get_caps(iface);
}

const char*
libvpx_rlbox_codec_error(uint32_t ctx_addr)
{
  vpx_codec_ctx_t* ctx = bridge_ctx(ctx_addr);
  return ctx ? vpx_codec_error(ctx) : NULL;
}

const char*
libvpx_rlbox_codec_error_detail(uint32_t ctx_addr)
{
  vpx_codec_ctx_t* ctx = bridge_ctx(ctx_addr);
  return ctx ? vpx_codec_error_detail(ctx) : NULL;
}

vpx_codec_err_t
libvpx_rlbox_codec_dec_init(uint32_t ctx_addr,
                            uint32_t iface_token,
                            const libvpx_bridge_dec_cfg_t* cfg,
                            uint32_t flags)
{
  vpx_codec_ctx_t* ctx = bridge_ctx(ctx_addr);
  vpx_codec_iface_t* iface = bridge_iface(iface_token);
  vpx_codec_dec_cfg_t native_cfg;
  const vpx_codec_dec_cfg_t* native_cfg_ptr = NULL;
  if (!ctx || !iface) {
    return VPX_CODEC_INVALID_PARAM;
  }
  if (cfg) {
    bridge_dec_cfg_to_native(&native_cfg, cfg);
    native_cfg_ptr = &native_cfg;
  }
  return vpx_codec_dec_init_ver(
    ctx, iface, native_cfg_ptr, (vpx_codec_flags_t) flags, VPX_DECODER_ABI_VERSION);
}

vpx_codec_err_t
libvpx_rlbox_codec_enc_init(uint32_t ctx_addr,
                            uint32_t iface_token,
                            const libvpx_bridge_enc_cfg_t* cfg,
                            uint32_t flags)
{
  vpx_codec_ctx_t* ctx = bridge_ctx(ctx_addr);
  vpx_codec_iface_t* iface = bridge_iface(iface_token);
  vpx_codec_enc_cfg_t native_cfg;
  const vpx_codec_enc_cfg_t* native_cfg_ptr = NULL;
  if (!ctx || !iface) {
    return VPX_CODEC_INVALID_PARAM;
  }
  if (cfg) {
    bridge_enc_cfg_to_native(&native_cfg, cfg);
    native_cfg_ptr = &native_cfg;
  }
  return vpx_codec_enc_init_ver(
    ctx, iface, native_cfg_ptr, (vpx_codec_flags_t) flags, VPX_ENCODER_ABI_VERSION);
}

vpx_codec_err_t
libvpx_rlbox_codec_enc_config_default(uint32_t iface_token,
                                      libvpx_bridge_enc_cfg_t* out_cfg,
                                      uint32_t usage)
{
  vpx_codec_iface_t* iface = bridge_iface(iface_token);
  vpx_codec_enc_cfg_t native_cfg;
  vpx_codec_err_t rc;
  if (!iface || !out_cfg) {
    return VPX_CODEC_INVALID_PARAM;
  }
  memset(&native_cfg, 0, sizeof(native_cfg));
  rc = vpx_codec_enc_config_default(iface, &native_cfg, usage);
  if (rc == VPX_CODEC_OK) {
    native_enc_cfg_to_bridge(out_cfg, &native_cfg);
  }
  return rc;
}

vpx_codec_err_t
libvpx_rlbox_codec_enc_config_set(uint32_t ctx_addr,
                                  const libvpx_bridge_enc_cfg_t* cfg)
{
  vpx_codec_ctx_t* ctx = bridge_ctx(ctx_addr);
  vpx_codec_enc_cfg_t native_cfg;
  if (!ctx || !cfg) {
    return VPX_CODEC_INVALID_PARAM;
  }
  bridge_enc_cfg_to_native(&native_cfg, cfg);
  return vpx_codec_enc_config_set(ctx, &native_cfg);
}

vpx_codec_err_t
libvpx_rlbox_codec_encode(uint32_t ctx_addr,
                          const libvpx_bridge_image_t* img,
                          int64_t pts,
                          uint32_t duration,
                          uint32_t flags,
                          uint32_t deadline)
{
  vpx_codec_ctx_t* ctx = bridge_ctx(ctx_addr);
  vpx_image_t native_img;
  const vpx_image_t* native_img_ptr = NULL;
  if (!ctx) {
    return VPX_CODEC_INVALID_PARAM;
  }
  if (img && img->present) {
    bridge_image_to_native(&native_img, img);
    native_img_ptr = &native_img;
  }
  return vpx_codec_encode(ctx,
                          native_img_ptr,
                          (vpx_codec_pts_t) pts,
                          (unsigned long) duration,
                          (vpx_enc_frame_flags_t) flags,
                          (unsigned long) deadline);
}

vpx_codec_err_t
libvpx_rlbox_codec_decode(uint32_t ctx_addr,
                          uint32_t data_addr,
                          uint32_t data_sz,
                          int32_t deadline)
{
  vpx_codec_ctx_t* ctx = bridge_ctx(ctx_addr);
  const uint8_t* data = (const uint8_t*)(uintptr_t) data_addr;
  if (!ctx) {
    return VPX_CODEC_INVALID_PARAM;
  }
  return vpx_codec_decode(ctx, data, data_sz, NULL, deadline);
}

int
libvpx_rlbox_codec_get_frame(uint32_t ctx_addr,
                             uint32_t iter_state,
                             libvpx_bridge_image_t* out_image)
{
  vpx_codec_ctx_t* ctx = bridge_ctx(ctx_addr);
  vpx_codec_iter_t iter = (vpx_codec_iter_t)(uintptr_t) iter_state;
  const vpx_image_t* img;
  if (!ctx || !out_image) {
    return -1;
  }
  img = vpx_codec_get_frame(ctx, &iter);
  native_image_to_bridge(out_image, img);
  out_image->iter_state = (uint32_t)(uintptr_t) iter;
  return img ? 1 : 0;
}

int
libvpx_rlbox_codec_get_cx_data(uint32_t ctx_addr,
                               uint32_t iter_state,
                               libvpx_bridge_packet_t* out_pkt)
{
  vpx_codec_ctx_t* ctx = bridge_ctx(ctx_addr);
  vpx_codec_iter_t iter = (vpx_codec_iter_t)(uintptr_t) iter_state;
  const vpx_codec_cx_pkt_t* pkt;
  if (!ctx || !out_pkt) {
    return -1;
  }
  pkt = vpx_codec_get_cx_data(ctx, &iter);
  native_packet_to_bridge(out_pkt, pkt);
  out_pkt->iter_state = (uint32_t)(uintptr_t) iter;
  return pkt ? 1 : 0;
}

vpx_codec_err_t
libvpx_rlbox_codec_destroy(uint32_t ctx_addr)
{
  vpx_codec_ctx_t* ctx = bridge_ctx(ctx_addr);
  if (!ctx) {
    return VPX_CODEC_INVALID_PARAM;
  }
  return vpx_codec_destroy(ctx);
}

vpx_codec_err_t
libvpx_rlbox_codec_control_int(uint32_t ctx_addr, int32_t ctrl_id, int32_t value)
{
  vpx_codec_ctx_t* ctx = bridge_ctx(ctx_addr);
  if (!ctx) {
    return VPX_CODEC_INVALID_PARAM;
  }
  return vpx_codec_control_(ctx, ctrl_id, value);
}

vpx_codec_err_t
libvpx_rlbox_codec_control_uint(uint32_t ctx_addr,
                                int32_t ctrl_id,
                                uint32_t value)
{
  vpx_codec_ctx_t* ctx = bridge_ctx(ctx_addr);
  if (!ctx) {
    return VPX_CODEC_INVALID_PARAM;
  }
  return vpx_codec_control_(ctx, ctrl_id, value);
}

vpx_codec_err_t
libvpx_rlbox_codec_control_out_int(uint32_t ctx_addr,
                                   int32_t ctrl_id,
                                   int32_t* out_value)
{
  vpx_codec_ctx_t* ctx = bridge_ctx(ctx_addr);
  if (!ctx || !out_value) {
    return VPX_CODEC_INVALID_PARAM;
  }
  return vpx_codec_control_(ctx, ctrl_id, out_value);
}

vpx_codec_err_t
libvpx_rlbox_codec_control_roi_map(uint32_t ctx_addr,
                                   int32_t ctrl_id,
                                   const libvpx_bridge_roi_map_t* map)
{
  vpx_codec_ctx_t* ctx = bridge_ctx(ctx_addr);
  vpx_roi_map_t native_map;
  if (!ctx || !map) {
    return VPX_CODEC_INVALID_PARAM;
  }
  bridge_roi_map_to_native(&native_map, map);
  return vpx_codec_control_(ctx, ctrl_id, &native_map);
}

vpx_codec_err_t
libvpx_rlbox_codec_control_svc_layer_id(
  uint32_t ctx_addr,
  int32_t ctrl_id,
  const libvpx_bridge_svc_layer_id_t* layer_id)
{
  vpx_codec_ctx_t* ctx = bridge_ctx(ctx_addr);
  vpx_svc_layer_id_t native_layer_id;
  if (!ctx || !layer_id) {
    return VPX_CODEC_INVALID_PARAM;
  }
  bridge_svc_layer_id_to_native(&native_layer_id, layer_id);
  return vpx_codec_control_(ctx, ctrl_id, &native_layer_id);
}

vpx_codec_err_t
libvpx_rlbox_codec_control_svc_parameters(
  uint32_t ctx_addr,
  int32_t ctrl_id,
  const libvpx_bridge_svc_parameters_t* params)
{
  vpx_codec_ctx_t* ctx = bridge_ctx(ctx_addr);
  vpx_svc_extra_cfg_t native_params;
  if (!ctx || !params) {
    return VPX_CODEC_INVALID_PARAM;
  }
  bridge_svc_parameters_to_native(&native_params, params);
  return vpx_codec_control_(ctx, ctrl_id, &native_params);
}

vpx_codec_err_t
libvpx_rlbox_codec_control_svc_ref_frame_config(
  uint32_t ctx_addr,
  int32_t ctrl_id,
  const libvpx_bridge_svc_ref_frame_config_t* cfg)
{
  vpx_codec_ctx_t* ctx = bridge_ctx(ctx_addr);
  vpx_svc_ref_frame_config_t native_cfg;
  if (!ctx || !cfg) {
    return VPX_CODEC_INVALID_PARAM;
  }
  bridge_svc_ref_frame_config_to_native(&native_cfg, cfg);
  return vpx_codec_control_(ctx, ctrl_id, &native_cfg);
}
