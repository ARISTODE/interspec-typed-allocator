#ifndef INTERSPEC_RUNTIME_H_INCLUDED
#define INTERSPEC_RUNTIME_H_INCLUDED

#include <cstddef>
#include <cstdint>
#include <limits>
#include <map>
#include <mutex>
#include <shared_mutex>
#include <unordered_map>

namespace interspec {

using TypeId = uint32_t;
using SiteId = uint32_t;

struct Allocation {
  uintptr_t base;
  size_t size;
  uint64_t type_hash;
  SiteId site_id;
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
};

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
    std::unique_lock<std::shared_mutex> lock(mu_);
    const auto type = types_.find(type_id);
    if (type == types_.end() || size == 0) return 0;
    return allocate_with_hash_unlocked(size, type->second, 0);
  }

  uintptr_t allocate_from_site(size_t size, SiteId site_id) {
    std::unique_lock<std::shared_mutex> lock(mu_);
    const auto site = site_types_.find(site_id);
    if (site == site_types_.end() || size == 0) return 0;
    return allocate_with_hash_unlocked(size, site->second, site_id);
  }

  uintptr_t allocate_from_pc(size_t size, uintptr_t caller_pc) {
    std::unique_lock<std::shared_mutex> lock(mu_);
    const AllocationSite* site = find_site_unlocked(caller_pc);
    if (!site || size == 0) return 0;
    return allocate_with_hash_unlocked(size, site->type_hash, site->id);
  }

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
    std::unique_lock<std::shared_mutex> lock(mu_);
    const auto allocation = allocations_.find(ptr);
    if (allocation == allocations_.end()) return false;
    allocations_.erase(allocation);
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
    std::unique_lock<std::shared_mutex> lock(mu_);
    const auto old = allocations_.find(ptr);
    if (old == allocations_.end()) return 0;

    if (new_size == 0) {
      allocations_.erase(old);
      return 0;
    }

    const uint64_t type_hash = old->second.type_hash;
    const SiteId site_id = old->second.site_id;
    const uintptr_t replacement =
        allocate_with_hash_unlocked(new_size, type_hash, site_id);
    if (!replacement) return 0;

    allocations_.erase(ptr);
    return replacement;
  }

  CheckResult remaining_bytes(uintptr_t ptr, uint64_t expected_type,
                              size_t& bytes) const {
    std::shared_lock<std::shared_mutex> lock(mu_);
    const Allocation* allocation = find_allocation_unlocked(ptr);
    if (!allocation) return CheckResult::untracked;
    if (allocation->type_hash != expected_type) return CheckResult::wrong_type;
    bytes = allocation->size - static_cast<size_t>(ptr - allocation->base);
    return CheckResult::ok;
  }

  CheckResult check(uintptr_t ptr, size_t bytes, uint64_t expected_type) const {
    std::shared_lock<std::shared_mutex> lock(mu_);
    const Allocation* allocation = find_allocation_unlocked(ptr);
    if (!allocation) return CheckResult::untracked;
    if (allocation->type_hash != expected_type) return CheckResult::wrong_type;

    const size_t offset = static_cast<size_t>(ptr - allocation->base);
    const size_t remaining = allocation->size - offset;
    return bytes <= remaining ? CheckResult::ok : CheckResult::out_of_bounds;
  }

 private:
  static bool aligned_size(size_t size, size_t& aligned) {
    constexpr size_t kAlignment = 8;
    if (size > std::numeric_limits<size_t>::max() - (kAlignment - 1))
      return false;
    aligned = (size + (kAlignment - 1)) & ~(kAlignment - 1);
    return aligned >= size;
  }

  uintptr_t allocate_with_hash_unlocked(size_t size, uint64_t type_hash,
                                        SiteId site_id) {
    if (!arena_valid_ || size == 0) return 0;

    size_t aligned = 0;
    if (!aligned_size(size, aligned)) return 0;
    if (used_ > capacity_ || aligned > capacity_ - used_) return 0;
    if (used_ > std::numeric_limits<uintptr_t>::max() - base_) return 0;

    const uintptr_t ptr = base_ + used_;
    const auto inserted = allocations_.emplace(
        ptr, Allocation{ptr, size, type_hash, site_id});
    if (!inserted.second) return 0;

    used_ += aligned;
    return ptr;
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

  mutable std::shared_mutex mu_;
  std::unordered_map<TypeId, uint64_t> types_;
  std::unordered_map<uint64_t, TypeId> type_ids_;
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
