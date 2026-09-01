#!/usr/bin/env python3

import argparse
from pathlib import Path


CONSTRUCTOR = '''  Engine() {
    if (!sandbox_.create_sandbox(GLUE_LIB_NACL_PATH, NACL_LIBC_PATH))
      throw std::runtime_error("failed to create RLBox NaCl sandbox");

    constexpr uint32_t kArenaSize = 16u * 1024u * 1024u;
    const uint32_t arena_base =
      sandbox_.get_sandbox_impl()->reserve_typed_arena(kArenaSize);
    if (!arena_base) throw std::runtime_error("failed to reserve typed arena");

    policy_runtime_ =
      std::make_unique<interspec::PolicyRuntime>(arena_base, kArenaSize);
    auto* impl = sandbox_.get_sandbox_impl();
    if (!policy_runtime_->initialize_from_sandbox(
          *impl,
          [](interspec::Runtime& runtime) {
            return interspec::rsync_popt_generated::register_types(runtime);
          },
          [](interspec::Runtime& runtime, auto resolve) {
            return interspec::rsync_popt_generated::register_allocation_policy(
              runtime, resolve);
          }))
      throw std::runtime_error("failed to initialize InterSpec allocation policy");

    sandbox_.sandbox_storage = this;
    alloc_cb_ = sandbox_.register_callback(p4c_allocate);
    release_cb_ = sandbox_.register_callback(p4c_release);
    size_cb_ = sandbox_.register_callback(p4c_size);
    realloc_cb_ = sandbox_.register_callback(p4c_reallocate);
    const uint32_t alloc_slot = sandbox_.get_sandbox_impl()->callback_slot_for_key(
      reinterpret_cast<const void*>(p4c_allocate));
    if (alloc_slot == std::numeric_limits<uint32_t>::max())
      throw std::runtime_error("failed to resolve allocator callback slot");
    sandbox_.invoke_sandbox_function(interspec_popt_init_lifetime,
                                     alloc_slot,
                                     release_cb_,
                                     size_cb_,
                                     realloc_cb_);
  }
'''

RLBOX_ONLY_CONSTRUCTOR = '''  Engine() {
    if (!sandbox_.create_sandbox(GLUE_LIB_NACL_PATH, NACL_LIBC_PATH))
      throw std::runtime_error("failed to create RLBox NaCl sandbox");

    /*
     * P9a RLBox-only baseline: do not reserve the InterSpec typed arena, create
     * PolicyRuntime, register allocation provenance, or install lifetime
     * callbacks. The sandbox and host-side API bridge remain unchanged.
     */
    sandbox_.sandbox_storage = this;
  }
'''

COPY_TO_U = '''  UCharPtr copy_to_u(const char* src) {
    if (!src) return UCharPtr(nullptr);

    const size_t bytes = std::strlen(src) + 1;
    if (bytes > std::numeric_limits<uint32_t>::max())
      throw std::runtime_error("popt string exceeds sandbox ABI");

    auto temporary = sandbox_.malloc_in_sandbox<char>(static_cast<uint32_t>(bytes));
    if (temporary.UNSAFE_unverified() == nullptr)
      throw std::bad_alloc();
    std::memcpy(temporary.UNSAFE_unverified(), src, bytes);

    auto typed =
      sandbox_.invoke_sandbox_function(interspec_p4c_typed_copy, temporary);
    sandbox_.free_in_sandbox(temporary);
    if (typed.UNSAFE_unverified() == nullptr) throw std::bad_alloc();
    return typed;
  }
'''

RLBOX_ONLY_COPY_TO_U = '''  UCharPtr copy_to_u(const char* src) {
    if (!src) return UCharPtr(nullptr);

    const size_t bytes = std::strlen(src) + 1;
    if (bytes > std::numeric_limits<uint32_t>::max())
      throw std::runtime_error("popt string exceeds sandbox ABI");

    /* RLBox-only marshalling uses the sandbox's ordinary allocator. */
    auto copy = sandbox_.malloc_in_sandbox<char>(static_cast<uint32_t>(bytes));
    if (copy.UNSAFE_unverified() == nullptr) throw std::bad_alloc();
    std::memcpy(copy.UNSAFE_unverified(), src, bytes);
    return copy;
  }
'''

P8_NO_CHECK = '''#ifdef INTERSPEC_P8_MEASURE_NO_VALIDATION
    /*
     * Measurement-only baseline. The sandbox, marshalling, typed allocation,
     * provenance, and workload remain identical; only the final Extended-SP3
     * acceptance check is bypassed. This build is never used by correctness
     * tests and deliberately trusts the known-valid benchmark workload.
     */
    const size_t bytes = std::strlen(raw) + 1;
#else
'''

P9A_AND_P8_NO_CHECK = '''#ifdef INTERSPEC_P9A_RLBOX_ONLY
    /*
     * P9a RLBox-only baseline. InterSpec typed allocation/provenance is absent
     * from both T and U. The benchmark uses known-valid data and keeps the
     * established copy behavior while omitting the Extended-SP3 acceptance
     * check.
     */
    const size_t bytes = std::strlen(raw) + 1;
#elif defined(INTERSPEC_P8_MEASURE_NO_VALIDATION)
    /*
     * Measurement-only baseline. The sandbox, marshalling, typed allocation,
     * provenance, and workload remain identical; only the final Extended-SP3
     * acceptance check is bypassed. This build is never used by correctness
     * tests and deliberately trusts the known-valid benchmark workload.
     */
    const size_t bytes = std::strlen(raw) + 1;
#else
'''


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise ValueError(f"expected exactly one {label} block, found {count}")
    return text.replace(old, new, 1)


def transform(text):
    text = replace_once(text, CONSTRUCTOR, RLBOX_ONLY_CONSTRUCTOR, "Engine constructor")
    text = replace_once(text, COPY_TO_U, RLBOX_ONLY_COPY_TO_U, "copy_to_u")
    text = replace_once(text, P8_NO_CHECK, P9A_AND_P8_NO_CHECK, "copy_checked baseline")
    return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source = Path(args.source).read_text()
    Path(args.output).write_text(transform(source))


if __name__ == "__main__":
    main()
