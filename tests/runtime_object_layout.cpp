#include <interspec/runtime.h>

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <limits>
#include <vector>

using interspec::CheckResult;
using interspec::MemoryDomain;
using interspec::NonheapKind;
using interspec::ObjectStorage;
using interspec::Runtime;
using interspec::type_hash;

#define EXPECT_EQ(actual, expected)                                            \
  do {                                                                         \
    const auto observed = (actual);                                           \
    const auto wanted = (expected);                                           \
    if (observed != wanted) {                                                 \
      std::cerr << "runtime_object_layout failed at line " << __LINE__ << '\n';\
      return 1;                                                                \
    }                                                                         \
  } while (0)

struct Record {
  std::uint64_t tag;
  std::uint32_t count;
  char payload[9];
};
static_assert(sizeof(Record) == 24, "test needs a non-power-of-two stride");
static_assert(alignof(Record) == 8, "expected ABI alignment");

alignas(8) static Record u_global{123, 6, "global"};

int main() {
  // Real backing storage makes both directions of the copy test executable.
  std::vector<unsigned char> backing(8192 + 64);
  const uintptr_t raw = reinterpret_cast<uintptr_t>(backing.data());
  const uintptr_t aligned = raw + ((64 - (raw % 64)) % 64);
  Runtime runtime(aligned, 8192);

  constexpr interspec::TypeId kRecordId = 1;
  constexpr interspec::TypeId kCountId = 2;
  constexpr interspec::TypeId kPayloadId = 3;
  constexpr interspec::TypeId kOddId = 4;
  constexpr uint64_t kRecord = type_hash("Record");
  constexpr uint64_t kCount = type_hash("uint32_t");
  constexpr uint64_t kPayload = type_hash("char[9]");
  constexpr uint64_t kOdd = type_hash("Odd18");
  EXPECT_EQ(runtime.register_type(kRecordId, kRecord), true);
  EXPECT_EQ(runtime.register_type(kCountId, kCount), true);
  EXPECT_EQ(runtime.register_type(kPayloadId, kPayload), true);
  EXPECT_EQ(runtime.register_type(kOddId, kOdd), true);
  EXPECT_EQ(runtime.register_type_layout(kRecordId, sizeof(Record),
                                         alignof(Record)), true);
  EXPECT_EQ(runtime.register_field_layout(kRecordId, kCountId,
                                          offsetof(Record, count),
                                          sizeof(Record::count)), true);
  EXPECT_EQ(runtime.register_field_layout(kRecordId, kPayloadId,
                                          offsetof(Record, payload),
                                          sizeof(Record::payload), true), true);
  // Overlapping field definitions, invalid shapes, and unknown layouts fail.
  EXPECT_EQ(runtime.register_field_layout(kRecordId, kCountId,
                                          offsetof(Record, count) + 1, 2), false);
  EXPECT_EQ(runtime.register_type_layout(kCountId, 17, 4), false);
  EXPECT_EQ(runtime.register_type_layout(kOddId, 18, 3), true);

  const uintptr_t pool = runtime.allocate_typed_array(3, kRecordId);
  EXPECT_EQ(pool != uintptr_t{0}, true);
  EXPECT_EQ(pool % alignof(Record), uintptr_t{0});
  EXPECT_EQ(runtime.check_typed_element(pool, sizeof(Record), kRecord),
            CheckResult::ok);
  EXPECT_EQ(runtime.check_typed_element(pool + sizeof(Record),
                                        sizeof(Record), kRecord),
            CheckResult::ok);
  EXPECT_EQ(runtime.check_typed_element(pool + 2 * sizeof(Record),
                                        sizeof(Record), kRecord),
            CheckResult::ok);
  // When a trusted original T pointer identifies one element, U cannot
  // substitute another equally typed element from the same allocation.
  EXPECT_EQ(runtime.check_typed_element(pool + sizeof(Record),
                                        sizeof(Record), kRecord, pool),
            CheckResult::wrong_object);
  // A forged Record* into a field, tail padding, or the next element's
  // bytes must not inherit the parent allocation's type merely by containment.
  EXPECT_EQ(runtime.check_typed_element(pool + 1, 1, kRecord),
            CheckResult::out_of_bounds);
  EXPECT_EQ(runtime.check_typed_element(pool + sizeof(Record) - 1, 2, kRecord),
            CheckResult::out_of_bounds);
  EXPECT_EQ(runtime.check_typed_element(pool, sizeof(Record) + 1, kRecord),
            CheckResult::out_of_bounds);
  EXPECT_EQ(runtime.check_typed_element(pool, 1, kCount),
            CheckResult::wrong_type);
  EXPECT_EQ(runtime.register_field_layout(kRecordId, kCountId, 0, 1), false);

  const uintptr_t count_ptr = pool + sizeof(Record) + offsetof(Record, count);
  EXPECT_EQ(runtime.check_typed_field(count_ptr, sizeof(std::uint32_t),
                                      kRecord, kCount), CheckResult::ok);
  EXPECT_EQ(runtime.check_typed_field(count_ptr, 4, kRecord, kCount, pool),
            CheckResult::wrong_object);
  EXPECT_EQ(runtime.check_typed_field(count_ptr + 1, 1, kRecord, kCount),
            CheckResult::out_of_bounds);
  EXPECT_EQ(runtime.check_typed_field(count_ptr, 4, kRecord, kPayload),
            CheckResult::wrong_type);
  EXPECT_EQ(runtime.check_typed_field(count_ptr, 5, kRecord, kCount),
            CheckResult::out_of_bounds);
  const uintptr_t payload_ptr =
      pool + 2 * sizeof(Record) + offsetof(Record, payload);
  EXPECT_EQ(runtime.check_typed_field(payload_ptr + 3, 6, kRecord, kPayload),
            CheckResult::ok);
  EXPECT_EQ(runtime.check_typed_field(payload_ptr + 3, 7, kRecord, kPayload),
            CheckResult::out_of_bounds);
  EXPECT_EQ(runtime.check_typed_field(pool + 23, 1, kRecord, kPayload),
            CheckResult::out_of_bounds);

  // Neither alignment nor element stride is assumed to be a power of two.
  const uintptr_t odd = runtime.allocate_typed_array(3, kOddId);
  EXPECT_EQ(odd != uintptr_t{0}, true);
  EXPECT_EQ(odd % 3, uintptr_t{0});
  EXPECT_EQ(runtime.check_typed_element(odd + 36, 18, kOdd), CheckResult::ok);
  EXPECT_EQ(runtime.check_typed_element(odd + 37, 1, kOdd),
            CheckResult::out_of_bounds);
  EXPECT_EQ(runtime.allocate_typed_array(
                std::numeric_limits<size_t>::max(), kRecordId),
            uintptr_t{0});

  // Typed realloc never truncates a logical element or weakens its layout.
  EXPECT_EQ(runtime.reallocate(pool, 25), uintptr_t{0});
  EXPECT_EQ(runtime.check_typed_element(pool, 1, kRecord), CheckResult::ok);
  const uintptr_t replacement = runtime.reallocate(pool, 2 * sizeof(Record));
  EXPECT_EQ(replacement != uintptr_t{0}, true);
  EXPECT_EQ(runtime.check_typed_element(pool, 1, kRecord),
            CheckResult::untracked);
  EXPECT_EQ(runtime.check_typed_element(replacement + sizeof(Record),
                                        sizeof(Record), kRecord),
            CheckResult::ok);
  EXPECT_EQ(runtime.check_typed_element(replacement + 2 * sizeof(Record),
                                        1, kRecord), CheckResult::untracked);

  // T stack and U static storage use explicit trusted registrations, not
  // heap registrations. Every check supplies domain and lifetime token.
  alignas(8) Record t_stack{987, 4, "stack"};
  const uintptr_t stack_ptr = reinterpret_cast<uintptr_t>(&t_stack);
  const uintptr_t global_ptr = reinterpret_cast<uintptr_t>(&u_global);
  EXPECT_EQ(runtime.check(stack_ptr, sizeof(Record), kRecord),
            CheckResult::untracked);
  EXPECT_EQ(runtime.check(global_ptr, sizeof(Record), kRecord),
            CheckResult::untracked);
  const uint64_t stack_token = runtime.register_nonheap_array(
      stack_ptr, 1, kRecordId, MemoryDomain::trusted, NonheapKind::stack);
  const uint64_t global_token = runtime.register_nonheap_array(
      global_ptr, 1, kRecordId, MemoryDomain::untrusted, NonheapKind::global);
  EXPECT_EQ(stack_token != uint64_t{0}, true);
  EXPECT_EQ(global_token != uint64_t{0}, true);
  EXPECT_EQ(runtime.register_nonheap_array(
                stack_ptr, 1, kRecordId, MemoryDomain::trusted,
                NonheapKind::stack), uint64_t{0});
  EXPECT_EQ(runtime.register_nonheap_array(
                stack_ptr + 1, 1, kRecordId, MemoryDomain::trusted,
                NonheapKind::stack), uint64_t{0});
  EXPECT_EQ(runtime.check_nonheap_element(stack_ptr, sizeof(Record), kRecord,
                                          MemoryDomain::trusted, stack_token),
            CheckResult::ok);
  EXPECT_EQ(runtime.check_nonheap_element(stack_ptr, 1, kRecord,
                                          MemoryDomain::trusted, stack_token,
                                          global_ptr),
            CheckResult::wrong_object);
  EXPECT_EQ(runtime.check_nonheap_element(stack_ptr, 1, kRecord,
                                          MemoryDomain::untrusted, stack_token),
            CheckResult::wrong_domain);
  EXPECT_EQ(runtime.check_nonheap_element(global_ptr, sizeof(Record), kRecord,
                                          MemoryDomain::untrusted, global_token),
            CheckResult::ok);
  EXPECT_EQ(runtime.check_nonheap_field(
                stack_ptr + offsetof(Record, count), 4,
                kRecord, kCount, MemoryDomain::trusted, stack_token),
            CheckResult::ok);
  EXPECT_EQ(runtime.check_nonheap_field(
                stack_ptr + offsetof(Record, count) + 1, 1,
                kRecord, kCount, MemoryDomain::trusted, stack_token),
            CheckResult::out_of_bounds);
  EXPECT_EQ(runtime.check_nonheap_element(global_ptr, 1, kRecord,
                                          MemoryDomain::trusted, global_token),
            CheckResult::wrong_domain);

  // T -> U: create a registered U allocation, then copy T stack bytes.
  const uintptr_t u_copy = runtime.allocate_typed_array(1, kRecordId);
  EXPECT_EQ(u_copy != uintptr_t{0}, true);
  EXPECT_EQ(runtime.check_typed_element(u_copy, sizeof(Record), kRecord),
            CheckResult::ok);
  std::memcpy(reinterpret_cast<void*>(u_copy), &t_stack, sizeof(Record));
  EXPECT_EQ(std::memcmp(reinterpret_cast<const void*>(u_copy), &t_stack,
                        sizeof(Record)), 0);
  // U -> T: verify a trusted registration, then stage the U static bytes.
  Record t_copy{};
  if (runtime.check_nonheap_element(global_ptr, sizeof(Record), kRecord,
                                    MemoryDomain::untrusted, global_token)
      != CheckResult::ok) return 1;
  std::memcpy(&t_copy, &u_global, sizeof(Record));
  EXPECT_EQ(t_copy.tag, u_global.tag);
  EXPECT_EQ(t_copy.count, u_global.count);

  // T heap pools shared with U are registered at trusted T allocation sites.
  // Same-type neighboring objects are valid only when the trusted origin
  // explicitly permits selecting them.
  std::vector<Record> t_heap(2);
  const uintptr_t heap_base =
      reinterpret_cast<uintptr_t>(t_heap.data());
  const uint64_t heap_token = runtime.register_external_array(
      heap_base, t_heap.size(), kRecordId, MemoryDomain::trusted,
      ObjectStorage::heap);
  EXPECT_EQ(heap_token != uint64_t{0}, true);
  EXPECT_EQ(runtime.check_nonheap_element(heap_base + sizeof(Record),
                                          sizeof(Record), kRecord,
                                          MemoryDomain::trusted, heap_token),
            CheckResult::ok);
  EXPECT_EQ(runtime.check_nonheap_element(heap_base + sizeof(Record),
                                          sizeof(Record), kRecord,
                                          MemoryDomain::trusted, heap_token,
                                          heap_base),
            CheckResult::wrong_object);
  // Raw-pointer C interfaces have no token slot. T can look up a live,
  // trusted registration by address, without accepting unknown or revoked
  // addresses. Both element extent and subobject layout remain enforced.
  EXPECT_EQ(runtime.check_external_element_by_address(
                heap_base, sizeof(Record), kRecord, MemoryDomain::trusted),
            CheckResult::ok);
  EXPECT_EQ(runtime.check_external_element_by_address(
                heap_base + sizeof(Record), sizeof(Record), kRecord,
                MemoryDomain::trusted), CheckResult::ok);
  EXPECT_EQ(runtime.check_external_element_by_address(
                heap_base + sizeof(Record), sizeof(Record), kRecord,
                MemoryDomain::trusted, heap_base), CheckResult::wrong_object);
  EXPECT_EQ(runtime.check_external_element_by_address(
                heap_base + 1, 1, kRecord, MemoryDomain::trusted),
            CheckResult::out_of_bounds);
  EXPECT_EQ(runtime.check_external_element_by_address(
                heap_base + sizeof(Record), sizeof(Record) + 1, kRecord,
                MemoryDomain::trusted), CheckResult::out_of_bounds);
  EXPECT_EQ(runtime.check_external_element_by_address(
                heap_base, 1, kRecord, MemoryDomain::untrusted),
            CheckResult::wrong_domain);
  EXPECT_EQ(runtime.check_external_element_by_address(
                heap_base, 1, kCount, MemoryDomain::trusted),
            CheckResult::wrong_type);
  EXPECT_EQ(runtime.check_external_element_by_address(
                heap_base + 2 * sizeof(Record), 1, kRecord,
                MemoryDomain::trusted), CheckResult::untracked);
  EXPECT_EQ(runtime.check_external_field_by_address(
                heap_base + offsetof(Record, count), sizeof(Record::count),
                kRecord, kCount, MemoryDomain::trusted), CheckResult::ok);
  EXPECT_EQ(runtime.check_external_field_by_address(
                heap_base + offsetof(Record, count) + 1, 1,
                kRecord, kCount, MemoryDomain::trusted),
            CheckResult::out_of_bounds);
  EXPECT_EQ(runtime.check_external_field_by_address(
                heap_base + offsetof(Record, payload) + 4, 5,
                kRecord, kPayload, MemoryDomain::trusted), CheckResult::ok);
  EXPECT_EQ(runtime.check_external_field_by_address(
                heap_base + offsetof(Record, payload) + 4, 6,
                kRecord, kPayload, MemoryDomain::trusted),
            CheckResult::out_of_bounds);
  EXPECT_EQ(runtime.check_external_element_by_address(
                stack_ptr, 1, kRecord, MemoryDomain::trusted),
            CheckResult::ok);
  EXPECT_EQ(runtime.check_external_element_by_address(
                global_ptr, 1, kRecord, MemoryDomain::trusted),
            CheckResult::wrong_domain);
  EXPECT_EQ(runtime.unregister_external(heap_token), true);
  EXPECT_EQ(runtime.check_nonheap_element(heap_base, 1, kRecord,
                                          MemoryDomain::trusted, heap_token),
            CheckResult::untracked);
  EXPECT_EQ(runtime.check_external_element_by_address(
                heap_base, 1, kRecord, MemoryDomain::trusted),
            CheckResult::untracked);
  const uint64_t fresh_heap_token = runtime.register_external_array(
      heap_base, t_heap.size(), kRecordId, MemoryDomain::trusted,
      ObjectStorage::heap);
  EXPECT_EQ(fresh_heap_token > heap_token, true);
  EXPECT_EQ(runtime.check_nonheap_element(heap_base, 1, kRecord,
                                          MemoryDomain::trusted, heap_token),
            CheckResult::untracked);
  EXPECT_EQ(runtime.check_external_element_by_address(
                heap_base, 1, kRecord, MemoryDomain::trusted), CheckResult::ok);
  // Address-only checks intentionally cannot distinguish an ABA reuse from
  // the new live object; token-bound checks must be used for that guarantee.
  EXPECT_EQ(runtime.unregister_external(fresh_heap_token), true);

  // Expired stack registrations fail. Address reuse cannot resurrect an
  // old trusted token, even if the new object has the same type and base.
  EXPECT_EQ(runtime.unregister_nonheap(stack_token), true);
  EXPECT_EQ(runtime.check_nonheap_element(stack_ptr, 1, kRecord,
                                          MemoryDomain::trusted, stack_token),
            CheckResult::untracked);
  const uint64_t reused = runtime.register_nonheap_array(
      stack_ptr, 1, kRecordId, MemoryDomain::trusted, NonheapKind::stack);
  EXPECT_EQ(reused > stack_token, true);
  EXPECT_EQ(runtime.check_nonheap_element(stack_ptr, 1, kRecord,
                                          MemoryDomain::trusted, stack_token),
            CheckResult::untracked);
  EXPECT_EQ(runtime.check_nonheap_element(stack_ptr, 1, kRecord,
                                          MemoryDomain::trusted, reused),
            CheckResult::ok);
  EXPECT_EQ(runtime.unregister_nonheap(reused), true);
  EXPECT_EQ(runtime.unregister_nonheap(global_token), true);
  EXPECT_EQ(runtime.check_nonheap_element(global_ptr, 1, kRecord,
                                          MemoryDomain::untrusted, global_token),
            CheckResult::untracked);

  std::cout << "typed pool and nonheap object checks: pass\n";
  return 0;
}
