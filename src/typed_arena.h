#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace interspec {

struct Allocation {
  uintptr_t base;
  size_t size;
  uint64_t type_hash;
};

enum class CheckResult {
  ok,
  untracked,
  wrong_type,
  out_of_bounds,
};

class TypedArena {
 public:
  TypedArena(uintptr_t base, size_t capacity) : base_(base), capacity_(capacity) {}

  uintptr_t allocate(size_t size, uint64_t type_hash) {
    if (size == 0) return 0;
    const size_t aligned = (size + 7u) & ~size_t{7u};
    if (aligned < size || aligned > capacity_ - used_) return 0;

    const uintptr_t ptr = base_ + used_;
    allocations_.push_back({ptr, size, type_hash});
    used_ += aligned;
    return ptr;
  }

  uintptr_t base() const { return base_; }

  bool release(uintptr_t ptr) {
    for (auto it = allocations_.begin(); it != allocations_.end(); ++it) {
      if (it->base == ptr) {
        allocations_.erase(it);
        return true;
      }
    }
    return false;
  }

  CheckResult check(uintptr_t ptr, size_t bytes, uint64_t expected_type) const {
    const Allocation* allocation = find(ptr);
    if (!allocation) return CheckResult::untracked;
    if (allocation->type_hash != expected_type) return CheckResult::wrong_type;

    const size_t offset = ptr - allocation->base;
    if (bytes > allocation->size - offset) return CheckResult::out_of_bounds;
    return CheckResult::ok;
  }

 private:
  const Allocation* find(uintptr_t ptr) const {
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
  std::vector<Allocation> allocations_;
};

constexpr uint64_t type_hash(const char* text) {
  uint64_t hash = 0;
  while (*text) hash = 129 * hash + static_cast<unsigned char>(*text++);
  return hash;
}

}  // namespace interspec
