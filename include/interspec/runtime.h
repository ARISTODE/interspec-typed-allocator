#ifndef INTERSPEC_RUNTIME_H_INCLUDED
#define INTERSPEC_RUNTIME_H_INCLUDED

#include <cstddef>
#include <cstdint>
#include <limits>
#include <map>
#include <mutex>
#include <shared_mutex>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>
#include "diagnostics.h"

namespace interspec {

using TypeId = uint32_t;
using SiteId = uint32_t;

struct Allocation {
  uintptr_t base;
  size_t size;
  uint64_t type_hash;
  SiteId site_id;
  // Zero means a legacy byte-range allocation.  Typed arrays retain
  // element stride and count, so pointer checks cannot span adjacent objects.
  size_t element_size = 0;
  size_t element_count = 0;
  size_t element_alignment = 0;
  // Bytes of arena behind this record, which can be more than `size` when the
  // record reuses a released block. Kept so that the block can be reused again.
  size_t capacity = 0;
};

enum class MemoryDomain { trusted, untrusted };
enum class ObjectStorage { heap, stack, global };
// Kept for existing callers of the nonheap-specific registration API.
using NonheapKind = ObjectStorage;

struct TypeLayout {
  size_t element_size;
  size_t alignment;
};

struct FieldLayout {
  size_t offset;
  size_t size;
  uint64_t type_hash;
  bool allow_interior;
};

struct BorrowedObject {
  uintptr_t base;
  size_t size;
  size_t element_size;
  uint64_t type_hash;
  MemoryDomain domain;
  ObjectStorage kind;
  uint64_t token;
};

struct TypeBinding {
  TypeId id;
  uint64_t type_hash;
};

struct AllocationSite {
  SiteId id;
  uintptr_t begin;
  uintptr_t end;
  TypeId type_id;
  uint64_t type_hash;
};

enum class CheckResult {
  ok,
  untracked,
  wrong_type,
  out_of_bounds,
  wrong_domain,
  wrong_object,
};

inline const char* check_result_name(CheckResult result) {
  switch (result) {
    case CheckResult::ok: return "ok";
    case CheckResult::untracked: return "untracked";
    case CheckResult::wrong_type: return "wrong_type";
    case CheckResult::out_of_bounds: return "out_of_bounds";
    case CheckResult::wrong_domain: return "wrong_domain";
    case CheckResult::wrong_object: return "wrong_object";
  }
  return "unknown";
}

class Runtime {
 public:
  Runtime(uintptr_t arena_base, size_t arena_size)
      : base_(arena_base),
        capacity_(arena_size),
        arena_valid_(arena_size <=
                     std::numeric_limits<uintptr_t>::max() - arena_base) {}

  bool register_type(TypeId id, uint64_t type_hash) {
    std::unique_lock<std::shared_mutex> lock(mu_);
    if (id == 0 || types_.find(id) != types_.end() ||
        type_ids_.find(type_hash) != type_ids_.end())
      return false;
    types_.emplace(id, type_hash);
    type_ids_.emplace(type_hash, id);
    return true;
  }

  // Layouts are supplied by trusted code generated from the interface or
  // compiler type information. A compromised U must never pick these values.
  // The size need not be a power of two; array stride is exact sizeof(T).
  bool register_type_layout(TypeId id, size_t element_size, size_t alignment) {
    std::unique_lock<std::shared_mutex> lock(mu_);
    if (!types_.count(id) || element_size == 0 || alignment == 0 ||
        element_size % alignment != 0 || layouts_.count(id))
      return false;
    layouts_.emplace(id, TypeLayout{element_size, alignment});
    return true;
  }

  // A registered field is the only permitted interior typed target. Ordinary
  // fields require an exact start; byte buffers may explicitly allow interior
  // byte pointers. Overlapping union views are not inferred or registered.
  bool register_field_layout(TypeId owner_id, TypeId field_id,
                             size_t offset, size_t size,
                             bool allow_interior = false) {
    std::unique_lock<std::shared_mutex> lock(mu_);
    auto layout = layouts_.find(owner_id);
    auto field = types_.find(field_id);
    if (layout == layouts_.end() || field == types_.end() ||
        frozen_layouts_.count(owner_id) || size == 0 ||
        offset > layout->second.element_size ||
        size > layout->second.element_size - offset)
      return false;
    auto& entries = fields_[owner_id];
    for (const auto& existing : entries) {
      if (offset < existing.offset + existing.size &&
          existing.offset < offset + size)
        return false;
    }
    entries.push_back(FieldLayout{offset, size, field->second, allow_interior});
    return true;
  }

  /*
   * Backends with immutable direct-call identities, such as wasm2c, do not
   * need to authorize allocation from a native program-counter range.  They
   * bind a trusted site identifier directly to its inferred type instead.
   * The identifier itself is never accepted from ordinary U data; the backend
   * must embed it in a trusted host import/callback implementation.
   */
  bool register_allocation_site_id(SiteId id, TypeId type_id) {
    std::unique_lock<std::shared_mutex> lock(mu_);
    const auto type = types_.find(type_id);
    if (id == 0 || type == types_.end() ||
        site_types_.find(id) != site_types_.end())
      return false;
    site_types_.emplace(id, type->second);
    return true;
  }

  bool register_allocation_site(SiteId id, uintptr_t begin, uintptr_t end,
                                TypeId type_id) {
    std::unique_lock<std::shared_mutex> lock(mu_);
    const auto type = types_.find(type_id);
    if (id == 0 || begin == 0 || begin >= end || type == types_.end() ||
        sites_by_id_.find(id) != sites_by_id_.end() ||
        site_types_.find(id) != site_types_.end())
      return false;

    auto next = sites_.lower_bound(begin);
    if (next != sites_.end() && end > next->second.begin) return false;
    if (next != sites_.begin()) {
      const auto prev = std::prev(next);
      if (prev->second.end > begin) return false;
    }

    AllocationSite site{id, begin, end, type_id, type->second};
    const auto inserted = sites_.emplace(begin, site);
    if (!inserted.second) return false;
    sites_by_id_.emplace(id, begin);
    site_types_.emplace(id, type->second);
    return true;
  }

  uintptr_t allocate(size_t size, TypeId type_id) {
    DiagnosticEvent event(this, "allocate");
    event.requested = size;
    std::unique_lock<std::shared_mutex> lock(mu_);
    const auto type = types_.find(type_id);
    if (type == types_.end() || size == 0) return 0;
    const auto ptr = allocate_with_hash_unlocked(size, type->second, 0);
    describe_unlocked(event, ptr);
    event.result = ptr ? "ok" : "failed";
    return ptr;
  }

  uintptr_t allocate_from_site(size_t size, SiteId site_id) {
    DiagnosticEvent event(this, "allocate_from_site");
    event.requested = size;
    event.site = site_id;
    std::unique_lock<std::shared_mutex> lock(mu_);
    const auto site = site_types_.find(site_id);
    if (site == site_types_.end() || size == 0) return 0;
    const auto ptr = allocate_with_hash_unlocked(size, site->second, site_id);
    describe_unlocked(event, ptr);
    event.result = ptr ? "ok" : "failed";
    return ptr;
  }

  uintptr_t allocate_from_pc(size_t size, uintptr_t caller_pc) {
    DiagnosticEvent event(this, "allocate_from_pc");
    event.requested = size;
    std::unique_lock<std::shared_mutex> lock(mu_);
    const AllocationSite* site = find_site_unlocked(caller_pc);
    if (!site || size == 0) return 0;
    const auto ptr = allocate_with_hash_unlocked(size, site->type_hash, site->id);
    describe_unlocked(event, ptr);
    event.result = ptr ? "ok" : "failed";
    return ptr;
  }

  // Uses an exact element stride and independently aligns each array base.
  // This prevents a forged T* into the middle of a neighboring T object.
  uintptr_t allocate_typed_array(size_t count, TypeId type_id) {
    std::unique_lock<std::shared_mutex> lock(mu_);
    const auto type = types_.find(type_id);
    const auto layout = layouts_.find(type_id);
    if (type == types_.end() || layout == layouts_.end() || count == 0 ||
        count > std::numeric_limits<size_t>::max() / layout->second.element_size)
      return 0;
    const size_t size = count * layout->second.element_size;
    const uintptr_t ptr = allocate_with_hash_unlocked(
        size, type->second, 0, layout->second.alignment);
    if (!ptr) return 0;
    auto& allocation = allocations_.find(ptr)->second;
    allocation.element_size = layout->second.element_size;
    allocation.element_count = count;
    allocation.element_alignment = layout->second.alignment;
    frozen_layouts_.insert(type_id);
    return ptr;
  }

  // Scope-bound objects (including globals) are registered only by trusted
  // caller code with compiler-derived bounds and type. Never forward this
  // registration API to U, or accept U-supplied type/size/site metadata.
  // The opaque token binds checks to this registration instance (ABA defense).
  uint64_t register_external_array(uintptr_t ptr, size_t count, TypeId type_id,
                                   MemoryDomain domain, ObjectStorage kind) {
    std::unique_lock<std::shared_mutex> lock(mu_);
    const auto type = types_.find(type_id);
    const auto layout = layouts_.find(type_id);
    if (!ptr || type == types_.end() || layout == layouts_.end() ||
        count == 0 || next_borrowed_token_ == 0 ||
        ptr % layout->second.alignment != 0 ||
        count > std::numeric_limits<size_t>::max() / layout->second.element_size)
      return 0;
    const size_t size = count * layout->second.element_size;
    if (size > std::numeric_limits<uintptr_t>::max() - ptr) return 0;
    const uintptr_t end = ptr + size;
    // Never let an explicit nonheap registration alias the managed heap arena.
    if (arena_valid_ && ptr < base_ + capacity_ && end > base_) return 0;
    const auto next = borrowed_.lower_bound(ptr);
    if (next != borrowed_.end() && end > next->second.base) return 0;
    if (next != borrowed_.begin()) {
      const auto prev = std::prev(next);
      if (prev->second.base + prev->second.size > ptr) return 0;
    }
    const uint64_t token = next_borrowed_token_++;
    borrowed_.emplace(ptr, BorrowedObject{
        ptr, size, layout->second.element_size, type->second, domain, kind,
        token});
    borrowed_by_token_.emplace(token, ptr);
    frozen_layouts_.insert(type_id);
    return token;
  }

  uint64_t register_nonheap_array(uintptr_t ptr, size_t count, TypeId type_id,
                                  MemoryDomain domain, NonheapKind kind) {
    return register_external_array(ptr, count, type_id, domain, kind);
  }

  bool unregister_external(uint64_t token) {
    std::unique_lock<std::shared_mutex> lock(mu_);
    const auto it = borrowed_by_token_.find(token);
    if (it == borrowed_by_token_.end()) return false;
    borrowed_.erase(it->second);
    borrowed_by_token_.erase(it);
    return true;
  }

  bool unregister_nonheap(uint64_t token) { return unregister_external(token); }

  uintptr_t base() const { return base_; }
  size_t capacity() const { return capacity_; }
  bool arena_valid() const { return arena_valid_; }

  size_t allocation_count() const {
    std::shared_lock<std::shared_mutex> lock(mu_);
    return allocations_.size();
  }

  size_t allocation_site_count() const {
    std::shared_lock<std::shared_mutex> lock(mu_);
    return site_types_.size();
  }

  bool release(uintptr_t ptr) {
    DiagnosticEvent event(this, "release");
    std::unique_lock<std::shared_mutex> lock(mu_);
    describe_unlocked(event, ptr);
    const auto allocation = allocations_.find(ptr);
    if (allocation == allocations_.end()) return false;
    release_unlocked(allocation);
    event.result = "ok";
    return true;
  }

  bool allocation_size(uintptr_t ptr, size_t& size) const {
    std::shared_lock<std::shared_mutex> lock(mu_);
    const auto allocation = allocations_.find(ptr);
    if (allocation == allocations_.end()) return false;
    size = allocation->second.size;
    return true;
  }

  bool allocation_site(uintptr_t ptr, SiteId& site_id) const {
    std::shared_lock<std::shared_mutex> lock(mu_);
    const auto allocation = allocations_.find(ptr);
    if (allocation == allocations_.end()) return false;
    site_id = allocation->second.site_id;
    return true;
  }

  uintptr_t reallocate(uintptr_t ptr, size_t new_size) {
    DiagnosticEvent event(this, "reallocate");
    event.requested = new_size;
    std::unique_lock<std::shared_mutex> lock(mu_);
    describe_unlocked(event, ptr);
    const auto old = allocations_.find(ptr);
    if (old == allocations_.end()) return 0;

    if (new_size == 0) {
      release_unlocked(old);
      event.result = "released";
      return 0;
    }

    const Allocation original = old->second;
    // Do not silently turn a typed array into a partial trailing object.
    if (original.element_size && new_size % original.element_size != 0)
      return 0;
    const uintptr_t replacement = allocate_with_hash_unlocked(
        new_size, original.type_hash, original.site_id,
        original.element_alignment ? original.element_alignment : 8);
    if (!replacement) return 0;
    if (original.element_size) {
      auto& next = allocations_.find(replacement)->second;
      next.element_size = original.element_size;
      next.element_count = new_size / original.element_size;
      next.element_alignment = original.element_alignment;
    }

    release_unlocked(allocations_.find(ptr));
    event.replacement = replacement;
    event.result = "ok";
    return replacement;
  }

  CheckResult remaining_bytes(uintptr_t ptr, uint64_t expected_type,
                              size_t& bytes) const {
    DiagnosticEvent event(this, "remaining_bytes");
    event.expected_type = expected_type;
    std::shared_lock<std::shared_mutex> lock(mu_);
    const Allocation* allocation = find_allocation_unlocked(ptr);
    describe_unlocked(event, ptr, allocation);
    if (!allocation) { event.result = "untracked"; return CheckResult::untracked; }
    if (allocation->type_hash != expected_type) {
      event.result = "wrong_type";
      return CheckResult::wrong_type;
    }
    bytes = allocation->size - static_cast<size_t>(ptr - allocation->base);
    event.result = "ok";
    return CheckResult::ok;
  }

  CheckResult check(uintptr_t ptr, size_t bytes, uint64_t expected_type) const {
    DiagnosticEvent event(this, "check");
    event.expected_type = expected_type;
    event.requested = bytes;
    std::shared_lock<std::shared_mutex> lock(mu_);
    const Allocation* allocation = find_allocation_unlocked(ptr);
    describe_unlocked(event, ptr, allocation);
    if (!allocation) { event.result = "untracked"; return CheckResult::untracked; }
    if (allocation->type_hash != expected_type) {
      event.result = "wrong_type";
      return CheckResult::wrong_type;
    }

    const size_t offset = static_cast<size_t>(ptr - allocation->base);
    const size_t remaining = allocation->size - offset;
    const auto result = bytes <= remaining ? CheckResult::ok : CheckResult::out_of_bounds;
    event.result = check_result_name(result);
    return result;
  }

  // A T* may refer only to the beginning of an actual T element. Legacy
  // check() remains byte-range based for existing char/byte buffers.
  CheckResult check_typed_element(uintptr_t ptr, size_t bytes,
                                  uint64_t expected_type,
                                  uintptr_t expected_element_base = 0) const {
    std::shared_lock<std::shared_mutex> lock(mu_);
    const auto* allocation = find_allocation_unlocked(ptr);
    if (!allocation || allocation->element_size == 0)
      return CheckResult::untracked;
    if (allocation->type_hash != expected_type) return CheckResult::wrong_type;
    const size_t offset = static_cast<size_t>(ptr - allocation->base);
    if (offset % allocation->element_size != 0 ||
        bytes > allocation->element_size)
      return CheckResult::out_of_bounds;
    // An expected origin from trusted T rejects same-type redirection to
    // another object in the same pool. Zero means intentional free selection.
    if (expected_element_base && ptr != expected_element_base)
      return CheckResult::wrong_object;
    return CheckResult::ok;
  }

  CheckResult check_typed_field(uintptr_t ptr, size_t bytes,
                                uint64_t expected_owner,
                                uint64_t expected_field,
                                uintptr_t expected_element_base = 0) const {
    std::shared_lock<std::shared_mutex> lock(mu_);
    const auto* allocation = find_allocation_unlocked(ptr);
    if (!allocation || allocation->element_size == 0)
      return CheckResult::untracked;
    if (allocation->type_hash != expected_owner) return CheckResult::wrong_type;
    const size_t delta = static_cast<size_t>(ptr - allocation->base);
    const uintptr_t element_base =
        ptr - (delta % allocation->element_size);
    if (expected_element_base && element_base != expected_element_base)
      return CheckResult::wrong_object;
    return check_field_unlocked(ptr, bytes, expected_owner, expected_field,
                                allocation->base, allocation->element_size);
  }

  // Nonheap checks require the trusted registration token AND expected
  // domain. They do not relax ordinary check(), which remains heap-only.
  CheckResult check_nonheap_element(uintptr_t ptr, size_t bytes,
                                   uint64_t expected_type,
                                   MemoryDomain expected_domain,
                                   uint64_t token,
                                   uintptr_t expected_element_base = 0) const {
    std::shared_lock<std::shared_mutex> lock(mu_);
    const BorrowedObject* object = find_borrowed_unlocked(token);
    return check_borrowed_element_unlocked(object, ptr, bytes, expected_type,
                                           expected_domain, expected_element_base);
  }

  CheckResult check_nonheap_field(uintptr_t ptr, size_t bytes,
                                 uint64_t expected_owner,
                                 uint64_t expected_field,
                                 MemoryDomain expected_domain,
                                 uint64_t token,
                                 uintptr_t expected_element_base = 0) const {
    std::shared_lock<std::shared_mutex> lock(mu_);
    const BorrowedObject* object = find_borrowed_unlocked(token);
    return check_borrowed_field_unlocked(object, ptr, bytes, expected_owner,
                                         expected_field, expected_domain,
                                         expected_element_base);
  }

  // Validates an external T/U object returned as a *raw address*, when the
  // interface cannot carry an opaque registration token (e.g. a C callback
  // data pointer or a queue entry). The metadata lookup happens in T, never
  // from an untrusted token or type supplied by U. This rejects unknown,
  // revoked, wrong-domain, wrong-type, interior and excessive-extent pointers.
  //
  // Address lookup alone cannot disambiguate an old address from a newly
  // registered object at the same address (ABA). Use the token-taking APIs
  // for temporal identity, or pass an authenticated expected_element_base for
  // spatial object identity. Same-type substitution otherwise remains possible.
  CheckResult check_external_element_by_address(
      uintptr_t ptr, size_t bytes, uint64_t expected_type,
      MemoryDomain expected_domain,
      uintptr_t expected_element_base = 0) const {
    std::shared_lock<std::shared_mutex> lock(mu_);
    return check_borrowed_element_unlocked(find_borrowed_by_address_unlocked(ptr),
                                           ptr, bytes, expected_type,
                                           expected_domain, expected_element_base);
  }

  CheckResult check_external_field_by_address(
      uintptr_t ptr, size_t bytes, uint64_t expected_owner,
      uint64_t expected_field, MemoryDomain expected_domain,
      uintptr_t expected_element_base = 0) const {
    std::shared_lock<std::shared_mutex> lock(mu_);
    return check_borrowed_field_unlocked(find_borrowed_by_address_unlocked(ptr),
                                         ptr, bytes, expected_owner,
                                         expected_field, expected_domain,
                                         expected_element_base);
  }

  // Snapshot only trusted metadata while locked; emit after unlocking.
  void dump_allocations() const {
    if (!DiagnosticEvent::enabled()) return;
    std::vector<Allocation> snapshot;
    {
      std::shared_lock<std::shared_mutex> lock(mu_);
      for (const auto& entry : allocations_) snapshot.push_back(entry.second);
    }
    for (const auto& allocation : snapshot) {
      DiagnosticEvent event(this, "live_allocation");
      describe_unlocked(event, allocation.base, &allocation);
      event.result = "live";
    }
  }

 private:
  static void describe_unlocked(DiagnosticEvent& event, uintptr_t ptr,
                                const Allocation* allocation) {
    event.ptr = ptr;
    if (!allocation) return;
    event.base = allocation->base;
    event.size = allocation->size;
    event.site = allocation->site_id;
    event.actual_type = allocation->type_hash;
    event.offset = static_cast<size_t>(ptr - allocation->base);
    event.remaining = allocation->size - event.offset;
  }

  void describe_unlocked(DiagnosticEvent& event, uintptr_t ptr) const {
#ifdef INTERSPEC_ENABLE_TRACE
    if (DiagnosticEvent::enabled())
      describe_unlocked(event, ptr, find_allocation_unlocked(ptr));
#else
    (void)event;
    (void)ptr;
#endif
  }

  const BorrowedObject* find_borrowed_unlocked(uint64_t token) const {
    if (!token) return nullptr;
    const auto indexed = borrowed_by_token_.find(token);
    if (indexed == borrowed_by_token_.end()) return nullptr;
    const auto object = borrowed_.find(indexed->second);
    if (object == borrowed_.end() || object->second.token != token)
      return nullptr;
    return &object->second;
  }

  const BorrowedObject* find_borrowed_by_address_unlocked(uintptr_t ptr) const {
    auto it = borrowed_.upper_bound(ptr);
    if (it == borrowed_.begin()) return nullptr;
    --it;
    const BorrowedObject& object = it->second;
    return ptr - object.base < object.size ? &object : nullptr;
  }

  CheckResult check_borrowed_element_unlocked(
      const BorrowedObject* object, uintptr_t ptr, size_t bytes,
      uint64_t expected_type, MemoryDomain expected_domain,
      uintptr_t expected_element_base) const {
    if (!object) return CheckResult::untracked;
    if (object->domain != expected_domain) return CheckResult::wrong_domain;
    if (object->type_hash != expected_type) return CheckResult::wrong_type;
    if (ptr < object->base || ptr - object->base >= object->size)
      return CheckResult::out_of_bounds;
    const size_t offset = static_cast<size_t>(ptr - object->base);
    if (offset % object->element_size != 0 || bytes > object->element_size)
      return CheckResult::out_of_bounds;
    if (expected_element_base && ptr != expected_element_base)
      return CheckResult::wrong_object;
    return CheckResult::ok;
  }

  CheckResult check_borrowed_field_unlocked(
      const BorrowedObject* object, uintptr_t ptr, size_t bytes,
      uint64_t expected_owner, uint64_t expected_field,
      MemoryDomain expected_domain, uintptr_t expected_element_base) const {
    if (!object) return CheckResult::untracked;
    if (object->domain != expected_domain) return CheckResult::wrong_domain;
    if (object->type_hash != expected_owner) return CheckResult::wrong_type;
    if (ptr < object->base || ptr - object->base >= object->size)
      return CheckResult::out_of_bounds;
    const size_t delta = static_cast<size_t>(ptr - object->base);
    const uintptr_t element_base = ptr - (delta % object->element_size);
    if (expected_element_base && element_base != expected_element_base)
      return CheckResult::wrong_object;
    return check_field_unlocked(ptr, bytes, expected_owner, expected_field,
                                object->base, object->element_size);
  }

  CheckResult check_field_unlocked(uintptr_t ptr, size_t bytes,
                                  uint64_t expected_owner,
                                  uint64_t expected_field,
                                  uintptr_t base,
                                  size_t element_size) const {
    const auto owner = type_ids_.find(expected_owner);
    if (owner == type_ids_.end()) return CheckResult::untracked;
    const auto positions = fields_.find(owner->second);
    if (positions == fields_.end()) return CheckResult::out_of_bounds;
    const size_t offset = static_cast<size_t>((ptr - base) % element_size);
    for (const auto& field : positions->second) {
      if (offset < field.offset || offset - field.offset >= field.size)
        continue;
      if (field.type_hash != expected_field) return CheckResult::wrong_type;
      if (!field.allow_interior && offset != field.offset)
        return CheckResult::out_of_bounds;
      if (bytes > field.size - (offset - field.offset))
        return CheckResult::out_of_bounds;
      return CheckResult::ok;
    }
    return CheckResult::out_of_bounds;
  }

  static bool aligned_size(size_t size, size_t& aligned) {
    constexpr size_t kAlignment = 8;
    if (size > std::numeric_limits<size_t>::max() - (kAlignment - 1))
      return false;
    aligned = (size + (kAlignment - 1)) & ~(kAlignment - 1);
    return aligned >= size;
  }

  uintptr_t allocate_with_hash_unlocked(size_t size, uint64_t type_hash,
                                        SiteId site_id,
                                        size_t alignment = 8) {
    if (!arena_valid_ || size == 0 || alignment == 0) return 0;
    size_t aligned = 0;
    if (!aligned_size(size, aligned)) return 0;

    // Reuse: the smallest released block of this site and type that holds the
    // request and has the required alignment. A released address is never
    // handed to another site, so a stale pointer can at most meet a later
    // object of the same site. The record carries the new size, so the bounds
    // of a check are those of the new object.
    const auto released = released_.find(ReleasedKey{type_hash, site_id});
    if (released != released_.end()) {
      for (auto block = released->second.lower_bound(aligned);
           block != released->second.end(); ++block) {
        if (block->second % alignment != 0) continue;
        const uintptr_t ptr = block->second;
        const size_t capacity = block->first;
        Allocation allocation{ptr, size, type_hash, site_id};
        allocation.capacity = capacity;
        if (!allocations_.emplace(ptr, allocation).second) return 0;
        released->second.erase(block);
        return ptr;
      }
    }

    if (used_ > capacity_ ||
        used_ > std::numeric_limits<uintptr_t>::max() - base_)
      return 0;

    const uintptr_t start = base_ + used_;
    const size_t remainder = static_cast<size_t>(start % alignment);
    // Division/remainder handles any positive alignment and non-power-of-two
    // sizeof(T). No masking, clamping, or guessed element base is used.
    const size_t padding = remainder ? alignment - remainder : 0;
    if (padding > capacity_ - used_ ||
        aligned > capacity_ - used_ - padding)
      return 0;
    const uintptr_t ptr = start + padding;
    Allocation allocation{ptr, size, type_hash, site_id};
    allocation.capacity = aligned;
    const auto inserted = allocations_.emplace(ptr, allocation);
    if (!inserted.second) return 0;
    used_ += padding + aligned;
    return ptr;
  }

  // Removes the record and keeps the block for a later allocation at the same
  // site. Until then no record covers the address, so a check of a pointer to
  // it reports `untracked`.
  void release_unlocked(std::map<uintptr_t, Allocation>::iterator allocation) {
    const Allocation& record = allocation->second;
    if (record.capacity)
      released_[ReleasedKey{record.type_hash, record.site_id}].emplace(
          record.capacity, record.base);
    allocations_.erase(allocation);
  }

  const Allocation* find_allocation_unlocked(uintptr_t ptr) const {
    if (allocations_.empty()) return nullptr;

    auto it = allocations_.upper_bound(ptr);
    if (it == allocations_.begin()) return nullptr;
    --it;

    const Allocation& allocation = it->second;
    if (ptr < allocation.base) return nullptr;
    const uintptr_t offset = ptr - allocation.base;
    return offset < allocation.size ? &allocation : nullptr;
  }

  const AllocationSite* find_site_unlocked(uintptr_t pc) const {
    if (sites_.empty()) return nullptr;
    auto it = sites_.upper_bound(pc);
    if (it == sites_.begin()) return nullptr;
    --it;
    const AllocationSite& site = it->second;
    return pc >= site.begin && pc < site.end ? &site : nullptr;
  }

  const AllocationSite* find_site_by_id_unlocked(SiteId id) const {
    const auto indexed = sites_by_id_.find(id);
    if (indexed == sites_by_id_.end()) return nullptr;
    const auto site = sites_.find(indexed->second);
    return site == sites_.end() ? nullptr : &site->second;
  }

  const uintptr_t base_;
  const size_t capacity_;
  const bool arena_valid_;
  size_t used_ = 0;
  // Released arena blocks by (type, site), each list ordered by capacity.
  using ReleasedKey = std::pair<uint64_t, SiteId>;
  std::map<ReleasedKey, std::multimap<size_t, uintptr_t>> released_;

  mutable std::shared_mutex mu_;
  std::unordered_map<TypeId, uint64_t> types_;
  std::unordered_map<uint64_t, TypeId> type_ids_;
  std::unordered_map<TypeId, TypeLayout> layouts_;
  std::unordered_map<TypeId, std::vector<FieldLayout>> fields_;
  std::unordered_set<TypeId> frozen_layouts_;
  std::map<uintptr_t, BorrowedObject> borrowed_;
  std::unordered_map<uint64_t, uintptr_t> borrowed_by_token_;
  uint64_t next_borrowed_token_ = 1;
  std::map<uintptr_t, AllocationSite> sites_;
  std::unordered_map<SiteId, uintptr_t> sites_by_id_;
  std::unordered_map<SiteId, uint64_t> site_types_;
  std::map<uintptr_t, Allocation> allocations_;
};

constexpr uint64_t type_hash(const char* text) {
  uint64_t hash = 0;
  while (*text) hash = 129 * hash + static_cast<unsigned char>(*text++);
  return hash;
}

}  // namespace interspec

#endif  // INTERSPEC_RUNTIME_H_INCLUDED
