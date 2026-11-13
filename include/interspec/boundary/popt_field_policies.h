// popt_field_policies.h - SP1/SP2 Copy Elision Policies for poptOption fields
//
// Taken from interspec-artifact (main, 2b2d2fd),
// code/generated_wrappers/samples/popt_sandbox_bridge/trusted/popt_field_policies.h.
// Only the popt.h include path differs: the bridge is compiled with the rsync
// popt directory on its include path.
//
// SP1 (skip copy-in): Fields exposed T→U, T-owned, U doesn't read
// SP2 (skip copy-out): Fields exposed T→U, T-owned, U doesn't write
//
// Based on CodeQL analysis from reports/rsync_popt/pointer_slots_full.csv

#pragma once

#include <cstddef>
#include <cstdint>

#include "popt.h"

namespace popt::rlbox {

// Field-level copy policy flags
enum class FieldCopyPolicy : uint8_t {
  kCopyBoth = 0,      // Normal: copy-in and copy-out
  kSkipCopyIn = 1,    // SP1: Don't copy T→U (U doesn't read)
  kSkipCopyOut = 2,   // SP2: Don't copy U→T (U doesn't write)
  kSkipBoth = 3,      // SP1+SP2: Skip both directions
};

// Field descriptor for struct-level copy control
struct FieldPolicy {
  size_t offset;              // Byte offset within struct
  size_t size;                // Field size in bytes
  FieldCopyPolicy policy;     // Copy policy
  bool is_pointer;            // True if field is a pointer (needs deep copy)
  const char* name;           // Debug name
};

// poptOption field policies based on CodeQL analysis:
//
// Field analysis from pointer_slots_full.csv:
// - longName:    U reads for option matching, never writes -> kSkipCopyOut
// - shortName:   U reads for option matching, never writes -> kSkipCopyOut
// - argInfo:     U reads for type dispatch, never writes -> kSkipCopyOut
// - arg:         U writes slot values here -> kCopyBoth (no elision)
// - val:         U reads for return value, never writes -> kSkipCopyOut
// - descrip:     Only read for poptPrintHelp (not wrapped), parsing doesn't read -> kSkipBoth
// - argDescrip:  Only read for poptPrintHelp (not wrapped), parsing doesn't read -> kSkipBoth
//
// Note: For descrip/argDescrip, the popt library DOES read these fields in help
// functions, but those functions (poptPrintHelp, poptPrintUsage) are not wrapped
// in our sandboxed interface. The wrapped functions (poptGetNextOpt, etc.) do NOT
// read these fields, so we can safely skip copying them.

constexpr FieldPolicy kPoptOptionFields[] = {
  { offsetof(struct poptOption, longName),
    sizeof(const char*),
    FieldCopyPolicy::kSkipCopyOut,
    true,
    "longName" },

  { offsetof(struct poptOption, shortName),
    sizeof(char),
    FieldCopyPolicy::kSkipCopyOut,
    false,
    "shortName" },

  { offsetof(struct poptOption, argInfo),
    sizeof(unsigned int),
    FieldCopyPolicy::kSkipCopyOut,
    false,
    "argInfo" },

  { offsetof(struct poptOption, arg),
    sizeof(void*),
    FieldCopyPolicy::kCopyBoth,  // U writes to slots - must copy both ways
    true,
    "arg" },

  { offsetof(struct poptOption, val),
    sizeof(int),
    FieldCopyPolicy::kSkipCopyOut,
    false,
    "val" },

  { offsetof(struct poptOption, descrip),
    sizeof(const char*),
    FieldCopyPolicy::kSkipBoth,  // Help text only - not read during parsing
    true,
    "descrip" },

  { offsetof(struct poptOption, argDescrip),
    sizeof(const char*),
    FieldCopyPolicy::kSkipBoth,  // Help text only - not read during parsing
    true,
    "argDescrip" },
};

constexpr size_t kPoptOptionFieldCount =
  sizeof(kPoptOptionFields) / sizeof(kPoptOptionFields[0]);

// Field indices for direct access
constexpr size_t kFieldLongName = 0;
constexpr size_t kFieldShortName = 1;
constexpr size_t kFieldArgInfo = 2;
constexpr size_t kFieldArg = 3;
constexpr size_t kFieldVal = 4;
constexpr size_t kFieldDescrip = 5;
constexpr size_t kFieldArgDescrip = 6;

// Helper functions
inline constexpr bool should_skip_copy_in(FieldCopyPolicy p) {
  return p == FieldCopyPolicy::kSkipCopyIn || p == FieldCopyPolicy::kSkipBoth;
}

inline constexpr bool should_skip_copy_out(FieldCopyPolicy p) {
  return p == FieldCopyPolicy::kSkipCopyOut || p == FieldCopyPolicy::kSkipBoth;
}

// SP1/SP2 elision statistics for profiling
struct ElisionStats {
  uint32_t total_options = 0;        // Total poptOption entries processed
  uint32_t sp1_descrip_elided = 0;   // descrip fields skipped on copy-in
  uint32_t sp1_argDescrip_elided = 0; // argDescrip fields skipped on copy-in
  uint32_t sp2_fields_elided = 0;    // Fields skipped on copy-out (future use)

  void reset() {
    total_options = 0;
    sp1_descrip_elided = 0;
    sp1_argDescrip_elided = 0;
    sp2_fields_elided = 0;
  }
};

} // namespace popt::rlbox
