#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace interspec {

using TypeId = uint32_t;

struct Allocation {
  uintptr_t base;
  size_t size;
  uint64_t type_hash;
};

struct TypeBinding {
  TypeId id;
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
      : base_(arena_base), capacity_(arena_size) {}

  bool register_type(TypeId id, uint64_t type_hash) {
    if (id == 0 || find_type(id) != nullptr) return false;
    types_.push_back({id, type_hash});
    return true;
  }

  uintptr_t allocate(size_t size, TypeId type_id) {
    const TypeBinding* type = find_type(type_id);
    if (!type || size == 0) return 0;
    return allocate_with_hash(size, type->type_hash);
  }

  uintptr_t base() const { return base_; }
  size_t allocation_count() const { return allocations_.size(); }

  bool release(uintptr_t ptr) {
    for (auto it = allocations_.begin(); it != allocations_.end(); ++it) {
      if (it->base == ptr) {
        allocations_.erase(it);
        return true;
      }
    }
    return false;
  }

  bool allocation_size(uintptr_t ptr, size_t& size) const {
    for (const auto& allocation : allocations_) {
      if (allocation.base == ptr) {
        size = allocation.size;
        return true;
      }
    }
    return false;
  }

  uintptr_t reallocate(uintptr_t ptr, size_t new_size) {
    if (new_size == 0) {
      release(ptr);
      return 0;
    }

    size_t old_index = allocations_.size();
    uint64_t type_hash = 0;
    for (size_t i = 0; i < allocations_.size(); ++i) {
      if (allocations_[i].base == ptr) {
        old_index = i;
        type_hash = allocations_[i].type_hash;
        break;
      }
    }
    if (old_index == allocations_.size()) return 0;

    const uintptr_t replacement = allocate_with_hash(new_size, type_hash);
    if (!replacement) return 0;

    allocations_.erase(allocations_.begin() + static_cast<std::ptrdiff_t>(old_index));
    return replacement;
  }

  CheckResult remaining_bytes(uintptr_t ptr, uint64_t expected_type,
                              size_t& bytes) const {
    const Allocation* allocation = find_allocation(ptr);
    if (!allocation) return CheckResult::untracked;
    if (allocation->type_hash != expected_type) return CheckResult::wrong_type;
    bytes = allocation->size - (ptr - allocation->base);
    return CheckResult::ok;
  }

  CheckResult check(uintptr_t ptr, size_t bytes, uint64_t expected_type) const {
    size_t remaining = 0;
    const CheckResult result = remaining_bytes(ptr, expected_type, remaining);
    if (result != CheckResult::ok) return result;
    return bytes <= remaining ? CheckResult::ok : CheckResult::out_of_bounds;
  }

 private:
  uintptr_t allocate_with_hash(size_t size, uint64_t type_hash) {
    if (size == 0) return 0;

    const size_t aligned = (size + 7u) & ~size_t{7u};
    if (aligned < size || used_ > capacity_ || aligned > capacity_ - used_)
      return 0;

    const uintptr_t ptr = base_ + used_;
    allocations_.push_back({ptr, size, type_hash});
    used_ += aligned;
    return ptr;
  }

  const TypeBinding* find_type(TypeId id) const {
    for (const auto& type : types_) {
      if (type.id == id) return &type;
    }
    return nullptr;
  }

  const Allocation* find_allocation(uintptr_t ptr) const {
    for (const auto& allocation : allocations_) {
      if (ptr >= allocation.base && ptr - allocation.base < allocation.size) {
        return &allocation;
      }
    }
    return nullptr;
  }

  uintptr_t base_;
  size_t capacity_;
  size_t used_ = 0;
  std::vector<TypeBinding> types_;
  std::vector<Allocation> allocations_;
};

constexpr uint64_t type_hash(const char* text) {
  uint64_t hash = 0;
  while (*text) hash = 129 * hash + static_cast<unsigned char>(*text++);
  return hash;
}

}  // namespace interspec
