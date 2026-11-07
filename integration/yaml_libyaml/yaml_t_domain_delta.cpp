// Project-authored T driver for libyaml's read-handler data pointer.
// The pinned native libyaml API is real; the simulated compromised return is
// NOT an observed wasm2c/libyaml boundary or an upstream libyaml attack.
#define RLBOX_USE_EXCEPTIONS
#define RLBOX_USE_STATIC_CALLS() rlbox_wasm2c_sandbox_lookup_symbol
#define RLBOX_WASM2C_MODULE_NAME glue__lib__wasm2c
#include "glue_lib_wasm2c.h"
#include "rlbox.hpp"
#include "rlbox_wasm2c_sandbox.hpp"

#include "interspec/runtime.h"
#include "yaml.h"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>

namespace {
using Sandbox = rlbox::rlbox_sandbox<rlbox::rlbox_wasm2c_sandbox>;
constexpr interspec::TypeId kContextId = 1;
constexpr interspec::TypeId kOtherId = 2;
constexpr uint64_t kContextType = interspec::type_hash("yaml::TReadContext");

struct ReadContext {
  const unsigned char* input;
  size_t length;
  size_t consumed;
};

struct OtherContext {
  ReadContext leading_context;
  uint64_t other_field;
};
static_assert(offsetof(OtherContext, leading_context) == 0,
              "the wrong-type case needs a safely readable first subobject");

int read_handler(void* data, unsigned char* buffer, size_t capacity,
                 size_t* size_read) {
  auto* ctx = static_cast<ReadContext*>(data);
  if (!ctx || ctx->consumed > ctx->length) return 0;
  const size_t n = std::min(capacity, ctx->length - ctx->consumed);
  if (n) std::memcpy(buffer, ctx->input + ctx->consumed, n);
  ctx->consumed += n;
  *size_read = n;
  return 1;
}

std::string parse_read_handler(yaml_parser_t* parser) {
  std::string last_scalar;
  for (;;) {
    yaml_event_t event;
    if (!yaml_parser_parse(parser, &event))
      throw std::runtime_error("yaml_parse_error");
    const bool finished = event.type == YAML_STREAM_END_EVENT;
    if (event.type == YAML_SCALAR_EVENT)
      last_scalar.assign(reinterpret_cast<const char*>(event.data.scalar.value),
                         event.data.scalar.length);
    yaml_event_delete(&event);
    if (finished) return last_scalar;
  }
}

void record(const char* scenario, const char* mode, const char* decision,
            const char* reason, const char* observed) {
  std::printf("SP3_T_DELTA boundary=yaml_read_handler scenario=%s policy=%s "
              "decision=%s reason=%s scalar=%s source=project_authored_t\n",
              scenario, mode, decision, reason, observed);
  std::fflush(stdout);
}
}  // namespace

int main(int argc, char** argv) {
  if (argc != 3) {
    std::fprintf(stderr, "usage: yaml-t-domain-delta {domain_sp3|extended_sp3} "
                         "{legitimate|untracked|revoked|wrong_type|same_type|same_type_pinned}\n");
    return 2;
  }
  const std::string mode = argv[1], scenario = argv[2];
  if (mode != "domain_sp3" && mode != "extended_sp3") return 2;

  static constexpr unsigned char kTrusted[] = "key: trusted\n";
  static constexpr unsigned char kAltered[] = "key: altered\n";
  ReadContext original{kTrusted, sizeof(kTrusted) - 1, 0};
  ReadContext alternate{kAltered, sizeof(kAltered) - 1, 0};
  OtherContext wrong{{kAltered, sizeof(kAltered) - 1, 0}, 42};
  void* candidate = &original;

  interspec::Runtime metadata(0, 0); // No managed U arena, only T registrations.
  if (!metadata.register_type(kContextId, kContextType) ||
      !metadata.register_type(kOtherId, interspec::type_hash("yaml::OtherContext")) ||
      !metadata.register_type_layout(kContextId, sizeof(ReadContext), alignof(ReadContext)) ||
      !metadata.register_type_layout(kOtherId, sizeof(OtherContext), alignof(OtherContext)))
    return 3;
  const uint64_t original_token = metadata.register_external_array(
      reinterpret_cast<uintptr_t>(&original), 1, kContextId,
      interspec::MemoryDomain::trusted, interspec::ObjectStorage::stack);
  if (!original_token) return 3;

  uint64_t other_token = 0;
  if (scenario == "legitimate") {
    // Keep the initial data pointer chosen by the trusted caller.
  } else if (scenario == "untracked") {
    candidate = &alternate;
  } else if (scenario == "revoked") {
    other_token = metadata.register_external_array(
        reinterpret_cast<uintptr_t>(&alternate), 1, kContextId,
        interspec::MemoryDomain::trusted, interspec::ObjectStorage::stack);
    if (!other_token || !metadata.unregister_external(other_token)) return 3;
    candidate = &alternate; // Scope is still alive but authority was revoked.
  } else if (scenario == "wrong_type") {
    other_token = metadata.register_external_array(
        reinterpret_cast<uintptr_t>(&wrong), 1, kOtherId,
        interspec::MemoryDomain::trusted, interspec::ObjectStorage::stack);
    if (!other_token) return 3;
    candidate = &wrong.leading_context;
  } else if (scenario == "same_type" || scenario == "same_type_pinned") {
    other_token = metadata.register_external_array(
        reinterpret_cast<uintptr_t>(&alternate), 1, kContextId,
        interspec::MemoryDomain::trusted, interspec::ObjectStorage::stack);
    if (!other_token) return 3;
    candidate = &alternate;
  } else {
    return 2;
  }

  Sandbox sandbox;
  if (!sandbox.create_sandbox()) return 3;
  // The sandbox supplies the real RLBox domain predicate. The native libyaml
  // parser and forged return are both T-side, and intentionally labeled so.
  const bool outside_u = candidate &&
      !sandbox.is_pointer_in_sandbox_memory(static_cast<unsigned char*>(candidate));
  const bool extended = mode == "extended_sp3";
  const auto result = outside_u && extended
      ? metadata.check_external_element_by_address(
            reinterpret_cast<uintptr_t>(candidate), sizeof(ReadContext),
            kContextType, interspec::MemoryDomain::trusted,
            scenario == "same_type_pinned"
                ? reinterpret_cast<uintptr_t>(&original) : 0)
      : interspec::CheckResult::ok;
  if (!outside_u || (extended && result != interspec::CheckResult::ok)) {
    const char* reason = outside_u ? interspec::check_result_name(result) : "wrong_domain";
    record(argv[2], argv[1], "reject", reason, "none");
    std::fprintf(stderr, "INTERSPEC_REJECT boundary=yaml_read_handler reason=%s\n", reason);
    sandbox.destroy_sandbox();
    return 86;
  }

  yaml_parser_t parser;
  if (!yaml_parser_initialize(&parser)) return 3;
  yaml_parser_set_input(&parser, read_handler, &original);
  // Model a U-originated corruption on the data pointer after it crossed the
  // API boundary. T's check above runs before libyaml invokes the callback.
  parser.read_handler_data = candidate;
  try {
    const std::string scalar = parse_read_handler(&parser);
    record(argv[2], argv[1], "accept", "ok", scalar.c_str());
  } catch (const std::exception& error) {
    record(argv[2], argv[1], "parse_error", error.what(), "none");
    yaml_parser_delete(&parser);
    sandbox.destroy_sandbox();
    return 4;
  }
  yaml_parser_delete(&parser);
  sandbox.destroy_sandbox();
  return 0;
}
