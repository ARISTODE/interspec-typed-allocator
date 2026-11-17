#pragma once

// Per-policy switches for the boundary wrappers (SP1, SP2, SP3).
//
// One wrapper build carries all three policies. Each can be turned off through
// the trusted process environment, so that one executable serves the benign
// run, the per-policy tests and the per-policy measurements:
//
//   INTERSPEC_SP1=0|1            selective copy-in  (withhold fields U does not read)
//   INTERSPEC_SP2=0|1            selective copy-out (drop U updates to fields U
//                                does not write)
//   INTERSPEC_SP3=0|1            object-registry check before T uses a pointer
//                                from U (live object, expected type, bounds)
//
// Unset means on. The switches are read once, before the first boundary call.
// An unrecognized value stops the process: a mistyped setting must not run as
// a different configuration than the one the operator recorded.
//
// The on/off parsing follows env_flag_enabled() in the interspec-artifact
// wrappers (RSYNC_POPT_WASM_ENFORCE_SP1/SP2/SP3 and their counterparts).

#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <string>

namespace interspec {

enum class Sp3Mode { off, full };

struct PolicySwitches {
  bool sp1 = true;
  bool sp2 = true;
  Sp3Mode sp3 = Sp3Mode::full;
};

namespace detail {

[[noreturn]] inline void bad_policy_switch(const char* name, const char* raw) {
  std::fprintf(stderr, "INTERSPEC_POLICY error=invalid_switch %s=%s\n", name, raw);
  std::fflush(stderr);
  std::abort();
}

// Returns 0 (off), 1 (on) or -1 (not an on/off word).
inline int parse_on_off(const char* raw) {
  std::string value(raw);
  for (auto& c : value)
    c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
  if (value == "0" || value == "false" || value == "off" || value == "no") return 0;
  if (value == "1" || value == "true" || value == "on" || value == "yes") return 1;
  return -1;
}

inline bool env_flag_enabled(const char* name, bool default_value) {
  const char* raw = std::getenv(name);
  if (!raw || raw[0] == '\0') return default_value;
  const int parsed = parse_on_off(raw);
  if (parsed < 0) bad_policy_switch(name, raw);
  return parsed == 1;
}

inline Sp3Mode env_sp3_mode(const char* name) {
  const char* raw = std::getenv(name);
  if (!raw || raw[0] == '\0') return Sp3Mode::full;
  const int parsed = parse_on_off(raw);
  if (parsed < 0) bad_policy_switch(name, raw);
  return parsed == 1 ? Sp3Mode::full : Sp3Mode::off;
}

}  // namespace detail

inline const char* sp3_mode_name(Sp3Mode mode) {
  switch (mode) {
    case Sp3Mode::off: return "off";
    case Sp3Mode::full: return "full";
  }
  return "invalid";
}

// Reads the switches on first use. With INTERSPEC_POLICY_REPORT=1 the effective
// configuration is written to stderr once, so a retained log states which
// configuration actually ran.
inline const PolicySwitches& policy_switches(const char* boundary) {
  static const PolicySwitches value = [boundary] {
    PolicySwitches result;
    result.sp1 = detail::env_flag_enabled("INTERSPEC_SP1", true);
    result.sp2 = detail::env_flag_enabled("INTERSPEC_SP2", true);
    result.sp3 = detail::env_sp3_mode("INTERSPEC_SP3");
    if (detail::env_flag_enabled("INTERSPEC_POLICY_REPORT", false)) {
      std::fprintf(stderr, "INTERSPEC_POLICY boundary=%s sp1=%d sp2=%d sp3=%s\n",
                   boundary, result.sp1 ? 1 : 0, result.sp2 ? 1 : 0,
                   sp3_mode_name(result.sp3));
      std::fflush(stderr);
    }
    return result;
  }();
  return value;
}

}  // namespace interspec
