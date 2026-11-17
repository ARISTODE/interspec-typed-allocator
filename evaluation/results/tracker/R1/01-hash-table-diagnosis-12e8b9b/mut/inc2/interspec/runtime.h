#ifndef INTERSPEC_RUNTIME_H_INCLUDED
#define INTERSPEC_RUNTIME_H_INCLUDED

#include <cstddef>
#include <algorithm>
#include <cstdint>
#include <deque>
#include <limits>
#include <map>
#include <memory>
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
// The lock that guards the registry. A sandbox and its registry are normally
// shared between threads, and every operation takes the reader-writer lock.
// An application that uses a sandbox from one thread at a time can say so by
// defining INTERSPEC_SINGLE_THREADED_REGISTRY before this header is included,
// in every translation unit that includes it; the lock then does nothing.
// This is the registry's counterpart of RLBOX_SINGLE_THREADED_INVOCATIONS,
// with which RLBox omits its own locks, and it rests on the same promise by
// the application. Define both or neither.
//
// The two forms of the registry have different layouts. They live in inline
// namespaces of different names, so that two translation units that disagree
// about the definition cannot be linked into sharing one registry.
#ifdef INTERSPEC_SINGLE_THREADED_REGISTRY
#define INTERSPEC_REGISTRY_ABI single_threaded_registry
#else
#define INTERSPEC_REGISTRY_ABI locked_registry
#endif

// Lets code that must build against older versions of this header detect
// resolve_external() and the token index.
#define INTERSPEC_RUNTIME_RESOLVES_TOKENS 1
// register_handle(), resolve_handle() and the handle table.
#define INTERSPEC_RUNTIME_HAS_HANDLES 1

inline namespace INTERSPEC_REGISTRY_ABI {
#ifdef INTERSPEC_SINGLE_THREADED_REGISTRY
struct RegistryMutex {
  void lock() noexcept {}
  void unlock() noexcept {}
  void lock_shared() noexcept {}
  void unlock_shared() noexcept {}
};
constexpr bool kRegistryLocked = false;
#else
using RegistryMutex = std::shared_mutex;
constexpr bool kRegistryLocked = true;
#endif
}  // inline namespace INTERSPEC_REGISTRY_ABI

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

// Index from a registration token to its record: an open-addressing table
// with linear probing, kept at most half full. Tokens are issued in increasing
// order, so the slot of a token comes from a multiplicative hash; with the
// token's low bits as the slot, one collision would push every later token one
// slot further. One lookup touches one cache line of the table where a
// node-based map touches a bucket and a node. Removal leaves a tombstone; the
// table is rebuilt when live entries and tombstones together fill half of it.
template <class Value>
class TokenIndex {
 public:
  const Value* find(uint64_t token) const {
    if (token == kEmpty || token == kTombstone || slots_.empty()) return nullptr;
    for (size_t i = home(token);; i = (i + 1) & mask_) {
      const Slot& slot = slots_[i];
      if (slot.token == token) return &slot.value;
      if (slot.token == kEmpty) return nullptr;
    }
  }

  void insert(uint64_t token, const Value& value) {
    if ((used_ + 1) * 2 > slots_.size()) rebuild();
    place(token, value);
  }

  // Removes the entry and hands its value to the caller.
  bool take(uint64_t token, Value& value) {
    if (token == kEmpty || token == kTombstone || slots_.empty()) return false;
    for (size_t i = home(token);; i = (i + 1) & mask_) {
      Slot& slot = slots_[i];
      if (slot.token == token) {
        value = slot.value;
        slot.token = kTombstone;
        slot.value = Value();
        --live_;
        return true;
      }
      if (slot.token == kEmpty) return false;
    }
  }

  size_t size() const { return live_; }

 private:
  // Token 0 is never issued, and the registry stops before the largest value.
  // Neither can be inserted; find and take refuse both.
  static constexpr uint64_t kEmpty = 0;
  static constexpr uint64_t kTombstone = ~uint64_t{0};
  struct Slot {
    uint64_t token = kEmpty;
    Value value{};
  };

  size_t home(uint64_t token) const {
    return static_cast<size_t>((token * UINT64_C(0x9E3779B97F4A7C15)) >> shift_);
  }

  void place(uint64_t token, const Value& value) {
    size_t i = home(token);
    while (slots_[i].token != kEmpty) i = (i + 1) & mask_;
    slots_[i].token = token;
    slots_[i].value = value;
    ++used_;
    ++live_;
  }

  void rebuild() {
    size_t capacity = 16;
    unsigned bits = 4;
    while (capacity < (live_ + 1) * 4) {
      capacity *= 2;
      ++bits;
    }
    std::vector<Slot> old(capacity);
    old.swap(slots_);
    mask_ = capacity - 1;
    shift_ = 64 - bits;
    used_ = live_ = 0;
    for (const Slot& slot : old)
      if (slot.token != kEmpty && slot.token != kTombstone) place(slot.token, slot.value);
  }

  std::vector<Slot> slots_;
  size_t mask_ = 0;
  unsigned shift_ = 60;
  size_t used_ = 0;  // live entries and tombstones
  size_t live_ = 0;
};

// Objects of T that U names by a handle and never by address, such as the
// items of a hash table that U keeps. A handle is a 32-bit value, so it fits
// wherever U's 32-bit code stored a pointer. Its low kSlotBits bits name a
// slot of a dense table and the remaining bits the generation of the slot. A
// slot is reused with the next generation, and a slot whose generations are
// used up is retired, so no handle is issued twice. A check reads one record
// of 32 bytes. These objects are not in the address index: they cannot be
// found by address, and a second registration of one address is not refused
// (a wrapper that releases handles keeps the handle of each object anyway).
class HandleTable {
 public:
  static constexpr unsigned kSlotBits = 22;
  static constexpr uint32_t kSlotMask = (uint32_t{1} << kSlotBits) - 1;
  static constexpr uint32_t kLastGeneration = (uint32_t{1} << (32 - kSlotBits)) - 1;

  struct Record {
    uintptr_t base = 0;       // while the slot is free: the next free slot
    size_t bytes = 0;
    uint64_t type_hash = 0;
    uint32_t handle = 0;      // 0 while the slot is free
    uint16_t generation = 0;  // of the last handle issued for the slot
    uint8_t domain = 0;
  };
  static_assert(sizeof(Record) == 32, "two records per cache line");

  // 0 when every slot is in use or retired.
  uint32_t insert(uintptr_t base, size_t bytes, uint64_t type_hash, MemoryDomain domain) {
    uint32_t slot;
    if (free_ != kNone) {
      slot = free_;
      free_ = static_cast<uint32_t>(records_[slot].base);
    } else {
      if (records_.size() > kSlotMask) return 0;
      slot = static_cast<uint32_t>(records_.size());
      records_.emplace_back();
    }
    Record& record = records_[slot];
    ++record.generation;  // at most kLastGeneration: a retired slot is never free
    record.handle = (static_cast<uint32_t>(record.generation) << kSlotBits) | slot;
    record.base = base;
    record.bytes = bytes;
    record.type_hash = type_hash;
    record.domain = static_cast<uint8_t>(domain);
    ++live_;
    return record.handle;
  }

  // A live handle is never 0 (its generation is at least 1); a free slot
  // holds 0, so 0 must not be looked up.
  const Record* find(uint32_t handle) const {
    const uint32_t slot = handle & kSlotMask;
    if (handle == 0 || slot >= records_.size()) return nullptr;
    const Record& record = records_[slot];
    return record.handle == handle ? &record : nullptr;
  }

  bool erase(uint32_t handle) {
    const uint32_t slot = handle & kSlotMask;
    if (handle == 0 || slot >= records_.size() || records_[slot].handle != handle)
      return false;
    Record& record = records_[slot];
    record.handle = 0;
    --live_;
    if (true) {
      record.base = free_;
      free_ = slot;
    }
    return true;
  }

  size_t size() const { return live_; }

 private:
  static constexpr uint32_t kNone = ~uint32_t{0};
  std::vector<Record> records_;
  uint32_t free_ = kNone;
  size_t live_ = 0;
};

// The externally registered objects, ordered by address. The registry needs
// the neighbours of an address (to refuse a registration that overlaps another
// one) and the object that contains an address. Records live in a pool and do
// not move. The order is kept in blocks of up to kBlock addresses, each block
// a sorted array, with the first address of every block in one more sorted
// array. A search is two binary searches over arrays that stay in the cache,
// written without data-dependent branches; a balanced tree of the same objects
// is a walk over as many scattered nodes as the tree is deep.
class OrderedObjects {
 public:
  OrderedObjects() = default;
  OrderedObjects(const OrderedObjects&) = delete;
  OrderedObjects& operator=(const OrderedObjects&) = delete;

  // The object with the greatest base that is not above `address`.
  BorrowedObject* floor(uintptr_t address) const {
    const size_t blocks = count_not_above(firsts_.data(), firsts_.size(), address);
    if (blocks == 0) return nullptr;
    const Block& b = *blocks_[blocks - 1];
    // The block's first key is not above `address`, so the count is positive.
    return b.values[count_not_above(b.keys, b.count, address) - 1];
  }

  // Stores `object` unless its bytes overlap a stored object. Returns the
  // stored record, or nullptr for an overlap. `object.size` must be positive
  // and base + size must not wrap.
  BorrowedObject* insert_unless_overlapping(const BorrowedObject& object) {
    const uintptr_t key = object.base;
    if (blocks_.empty()) {
      blocks_.push_back(std::make_unique<Block>());
      firsts_.push_back(key);
    }
    const size_t not_above = count_not_above(firsts_.data(), firsts_.size(), key);
    size_t block = not_above == 0 ? 0 : not_above - 1;
    Block* b = blocks_[block].get();
    size_t position = count_below(b->keys, b->count, key);
    // The neighbours: the first object at or above `key`, the last one below.
    const BorrowedObject* next =
        position < b->count ? b->values[position]
        : block + 1 < blocks_.size() ? blocks_[block + 1]->values[0] : nullptr;
    const BorrowedObject* previous =
        position > 0 ? b->values[position - 1]
        : block > 0 ? blocks_[block - 1]->values[blocks_[block - 1]->count - 1] : nullptr;
    if (next && object.base + object.size > next->base) return nullptr;
    if (previous && previous->base + previous->size > object.base) return nullptr;

    if (b->count == kBlock) {
      // Split: the upper half moves to a new block behind this one.
      auto upper = std::make_unique<Block>();
      const uint32_t half = kBlock / 2;
      std::copy(b->keys + half, b->keys + kBlock, upper->keys);
      std::copy(b->values + half, b->values + kBlock, upper->values);
      upper->count = kBlock - half;
      b->count = half;
      firsts_.insert(firsts_.begin() + static_cast<std::ptrdiff_t>(block) + 1, upper->keys[0]);
      blocks_.insert(blocks_.begin() + static_cast<std::ptrdiff_t>(block) + 1, std::move(upper));
      if (position > half) {
        ++block;
        position -= half;
      }
      b = blocks_[block].get();
    }
    BorrowedObject* record;
    if (free_.empty()) {
      pool_.push_back(object);
      record = &pool_.back();
    } else {
      record = free_.back();
      free_.pop_back();
      *record = object;
    }
    std::copy_backward(b->keys + position, b->keys + b->count, b->keys + b->count + 1);
    std::copy_backward(b->values + position, b->values + b->count, b->values + b->count + 1);
    b->keys[position] = key;
    b->values[position] = record;
    ++b->count;
    if (position == 0) firsts_[block] = key;
    ++size_;
    return record;
  }

  // `record` must have come from insert_unless_overlapping() and not been
  // erased since.
  void erase(BorrowedObject* record) {
    const uintptr_t key = record->base;
    const size_t block = count_not_above(firsts_.data(), firsts_.size(), key) - 1;
    Block& b = *blocks_[block];
    const size_t position = count_below(b.keys, b.count, key);
    std::copy(b.keys + position + 1, b.keys + b.count, b.keys + position);
    std::copy(b.values + position + 1, b.values + b.count, b.values + position);
    --b.count;
    if (b.count == 0) {
      blocks_.erase(blocks_.begin() + static_cast<std::ptrdiff_t>(block));
      firsts_.erase(firsts_.begin() + static_cast<std::ptrdiff_t>(block));
    } else if (position == 0) {
      firsts_[block] = b.keys[0];
    }
    free_.push_back(record);
    --size_;
  }

  size_t size() const { return size_; }

 private:
  static constexpr uint32_t kBlock = 64;
  struct Block {
    uint32_t count = 0;
    uintptr_t keys[kBlock];
    BorrowedObject* values[kBlock];
  };

  // Binary searches over a sorted array whose loop makes the same steps for
  // every key (the comparison selects an offset, not a branch).
  static size_t count_below(const uintptr_t* keys, size_t count, uintptr_t key) {
    size_t base = 0;
    while (count > 1) {
      const size_t half = count / 2;
      base += keys[base + half - 1] < key ? half : 0;
      count -= half;
    }
    return base + (count == 1 && keys[base] < key ? 1 : 0);
  }
  static size_t count_not_above(const uintptr_t* keys, size_t count, uintptr_t key) {
    size_t base = 0;
    while (count > 1) {
      const size_t half = count / 2;
      base += keys[base + half - 1] <= key ? half : 0;
      count -= half;
    }
    return base + (count == 1 && keys[base] <= key ? 1 : 0);
  }

  std::vector<std::unique_ptr<Block>> blocks_;
  std::vector<uintptr_t> firsts_;
  std::deque<BorrowedObject> pool_;
  std::vector<BorrowedObject*> free_;
  size_t size_ = 0;
};

inline namespace INTERSPEC_REGISTRY_ABI {

class Runtime {
 public:
  Runtime(uintptr_t arena_base, size_t arena_size)
      : base_(arena_base),
        capacity_(arena_size),
        arena_valid_(arena_size <=
                     std::numeric_limits<uintptr_t>::max() - arena_base) {}

  bool register_type(TypeId id, uint64_t type_hash) {
    std::unique_lock<RegistryMutex> lock(mu_);
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
    std::unique_lock<RegistryMutex> lock(mu_);
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
    std::unique_lock<RegistryMutex> lock(mu_);
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
    std::unique_lock<RegistryMutex> lock(mu_);
    const auto type = types_.find(type_id);
    if (id == 0 || type == types_.end() ||
        site_types_.find(id) != site_types_.end())
      return false;
    site_types_.emplace(id, type->second);
    return true;
  }

  bool register_allocation_site(SiteId id, uintptr_t begin, uintptr_t end,
                                TypeId type_id) {
    std::unique_lock<RegistryMutex> lock(mu_);
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
    std::unique_lock<RegistryMutex> lock(mu_);
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
    std::unique_lock<RegistryMutex> lock(mu_);
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
    std::unique_lock<RegistryMutex> lock(mu_);
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
    std::unique_lock<RegistryMutex> lock(mu_);
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
    std::unique_lock<RegistryMutex> lock(mu_);
    const auto type = types_.find(type_id);
    const auto layout = layouts_.find(type_id);
    if (!ptr || type == types_.end() || layout == layouts_.end() ||
        count == 0 || next_borrowed_token_ == 0 ||
        next_borrowed_token_ == std::numeric_limits<uint64_t>::max() ||
        ptr % layout->second.alignment != 0 ||
        count > std::numeric_limits<size_t>::max() / layout->second.element_size)
      return 0;
    const size_t size = count * layout->second.element_size;
    if (size > std::numeric_limits<uintptr_t>::max() - ptr) return 0;
    const uintptr_t end = ptr + size;
    // Never let an explicit nonheap registration alias the managed heap arena.
    if (arena_valid_ && ptr < base_ + capacity_ && end > base_) return 0;
    // Refused when the bytes overlap another registered object.
    const uint64_t token = next_borrowed_token_;
    BorrowedObject* inserted = borrowed_.insert_unless_overlapping(BorrowedObject{
        ptr, size, layout->second.element_size, type->second, domain, kind,
        token});
    if (!inserted) return 0;
    ++next_borrowed_token_;
    borrowed_by_token_.insert(token, inserted);
    frozen_layouts_.insert(type_id);
    return token;
  }

  uint64_t register_nonheap_array(uintptr_t ptr, size_t count, TypeId type_id,
                                  MemoryDomain domain, NonheapKind kind) {
    return register_external_array(ptr, count, type_id, domain, kind);
  }

  bool unregister_external(uint64_t token) {
    std::unique_lock<RegistryMutex> lock(mu_);
    BorrowedObject* object = nullptr;
    if (!borrowed_by_token_.take(token, object)) return false;
    borrowed_.erase(object);
    return true;
  }

  bool unregister_nonheap(uint64_t token) { return unregister_external(token); }

  // Handles for objects of T that U names without their address (see
  // HandleTable). Like register_external_array, only trusted caller code
  // registers; the type must be registered with its layout. Returns 0 on
  // refusal.
  uint32_t register_handle(uintptr_t ptr, size_t count, TypeId type_id,
                           MemoryDomain domain) {
    std::unique_lock<RegistryMutex> lock(mu_);
    if (!handle_type_.valid || handle_type_.id != type_id) {
      const auto type = types_.find(type_id);
      const auto layout = layouts_.find(type_id);
      if (type == types_.end() || layout == layouts_.end()) return 0;
      // The layout of a type cannot change once an object of it is registered.
      frozen_layouts_.insert(type_id);
      handle_type_ = HandleType{true, type_id, type->second,
                                layout->second.element_size, layout->second.alignment};
    }
    if (!ptr || count == 0 || ptr % handle_type_.alignment != 0 ||
        count > std::numeric_limits<size_t>::max() / handle_type_.element_size)
      return 0;
    const size_t size = count * handle_type_.element_size;
    if (size > std::numeric_limits<uintptr_t>::max() - ptr) return 0;
    if (arena_valid_ && ptr < base_ + capacity_ && ptr + size > base_) return 0;
    return handles_.insert(ptr, size, handle_type_.type_hash, domain);
  }

  bool unregister_handle(uint32_t handle) {
    std::unique_lock<RegistryMutex> lock(mu_);
    return handles_.erase(handle);
  }

  // The object behind a handle that U returned: refused when the handle was
  // never issued, was unregistered, or names an object of another domain or
  // type, or an object smaller than `bytes`. `base` is written only when the
  // result is ok.
  CheckResult resolve_handle(uint32_t handle, size_t bytes, uint64_t expected_type,
                             MemoryDomain expected_domain, uintptr_t& base) const {
    std::shared_lock<RegistryMutex> lock(mu_);
    const HandleTable::Record* record = handles_.find(handle);
    if (!record) return CheckResult::untracked;
    if (record->domain != static_cast<uint8_t>(expected_domain))
      return CheckResult::wrong_domain;
    if (record->type_hash != expected_type) return CheckResult::wrong_type;
    if (bytes > record->bytes) return CheckResult::out_of_bounds;
    base = record->base;
    return CheckResult::ok;
  }

  // The address registered under `handle`, without any check of type or
  // domain. For measurements of registration alone; a wrapper uses
  // resolve_handle.
  bool handle_base(uint32_t handle, uintptr_t& base) const {
    std::shared_lock<RegistryMutex> lock(mu_);
    const HandleTable::Record* record = handles_.find(handle);
    if (!record) return false;
    base = record->base;
    return true;
  }

  size_t handle_count() const {
    std::shared_lock<RegistryMutex> lock(mu_);
    return handles_.size();
  }

  uintptr_t base() const { return base_; }
  size_t capacity() const { return capacity_; }
  bool arena_valid() const { return arena_valid_; }

  size_t allocation_count() const {
    std::shared_lock<RegistryMutex> lock(mu_);
    return allocations_.size();
  }

  size_t allocation_site_count() const {
    std::shared_lock<RegistryMutex> lock(mu_);
    return site_types_.size();
  }

  bool release(uintptr_t ptr) {
    DiagnosticEvent event(this, "release");
    std::unique_lock<RegistryMutex> lock(mu_);
    describe_unlocked(event, ptr);
    const auto allocation = allocations_.find(ptr);
    if (allocation == allocations_.end()) return false;
    release_unlocked(allocation);
    event.result = "ok";
    return true;
  }

  bool allocation_size(uintptr_t ptr, size_t& size) const {
    std::shared_lock<RegistryMutex> lock(mu_);
    const auto allocation = allocations_.find(ptr);
    if (allocation == allocations_.end()) return false;
    size = allocation->second.size;
    return true;
  }

  bool allocation_site(uintptr_t ptr, SiteId& site_id) const {
    std::shared_lock<RegistryMutex> lock(mu_);
    const auto allocation = allocations_.find(ptr);
    if (allocation == allocations_.end()) return false;
    site_id = allocation->second.site_id;
    return true;
  }

  uintptr_t reallocate(uintptr_t ptr, size_t new_size) {
    DiagnosticEvent event(this, "reallocate");
    event.requested = new_size;
    std::unique_lock<RegistryMutex> lock(mu_);
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
    std::shared_lock<RegistryMutex> lock(mu_);
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
    std::shared_lock<RegistryMutex> lock(mu_);
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
    std::shared_lock<RegistryMutex> lock(mu_);
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
    std::shared_lock<RegistryMutex> lock(mu_);
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
    std::shared_lock<RegistryMutex> lock(mu_);
    const BorrowedObject* object = find_borrowed_unlocked(token);
    return check_borrowed_element_unlocked(object, ptr, bytes, expected_type,
                                           expected_domain, expected_element_base);
  }

  // For a wrapper that hands U the token of an object in place of its
  // address: the object behind a token that U returned. The checks are those
  // of check_nonheap_element on the object's first element, so a token that
  // was never issued, was unregistered, or names an object of another type or
  // domain is refused. `base` is written only when the result is ok.
  CheckResult resolve_external(uint64_t token, size_t bytes,
                               uint64_t expected_type,
                               MemoryDomain expected_domain,
                               uintptr_t& base) const {
    std::shared_lock<RegistryMutex> lock(mu_);
    const BorrowedObject* object = find_borrowed_unlocked(token);
    if (!object) return CheckResult::untracked;
    const CheckResult result = check_borrowed_element_unlocked(
        object, object->base, bytes, expected_type, expected_domain, 0);
    if (result == CheckResult::ok) base = object->base;
    return result;
  }

  // The address registered under `token`, without any check of type or
  // domain. For measurements of registration alone; a wrapper uses
  // resolve_external.
  bool external_base(uint64_t token, uintptr_t& base) const {
    std::shared_lock<RegistryMutex> lock(mu_);
    const BorrowedObject* object = find_borrowed_unlocked(token);
    if (!object) return false;
    base = object->base;
    return true;
  }

  CheckResult check_nonheap_field(uintptr_t ptr, size_t bytes,
                                 uint64_t expected_owner,
                                 uint64_t expected_field,
                                 MemoryDomain expected_domain,
                                 uint64_t token,
                                 uintptr_t expected_element_base = 0) const {
    std::shared_lock<RegistryMutex> lock(mu_);
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
    std::shared_lock<RegistryMutex> lock(mu_);
    return check_borrowed_element_unlocked(find_borrowed_by_address_unlocked(ptr),
                                           ptr, bytes, expected_type,
                                           expected_domain, expected_element_base);
  }

  CheckResult check_external_field_by_address(
      uintptr_t ptr, size_t bytes, uint64_t expected_owner,
      uint64_t expected_field, MemoryDomain expected_domain,
      uintptr_t expected_element_base = 0) const {
    std::shared_lock<RegistryMutex> lock(mu_);
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
      std::shared_lock<RegistryMutex> lock(mu_);
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
    BorrowedObject* const* object = borrowed_by_token_.find(token);
    return object ? *object : nullptr;
  }

  const BorrowedObject* find_borrowed_by_address_unlocked(uintptr_t ptr) const {
    const BorrowedObject* object = borrowed_.floor(ptr);
    return object && ptr - object->base < object->size ? object : nullptr;
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

  mutable RegistryMutex mu_;
  std::unordered_map<TypeId, uint64_t> types_;
  std::unordered_map<uint64_t, TypeId> type_ids_;
  std::unordered_map<TypeId, TypeLayout> layouts_;
  std::unordered_map<TypeId, std::vector<FieldLayout>> fields_;
  std::unordered_set<TypeId> frozen_layouts_;
  OrderedObjects borrowed_;
  TokenIndex<BorrowedObject*> borrowed_by_token_;
  uint64_t next_borrowed_token_ = 1;
  HandleTable handles_;
  struct HandleType {  // the type of the last register_handle call
    bool valid = false;
    TypeId id = 0;
    uint64_t type_hash = 0;
    size_t element_size = 0;
    size_t alignment = 0;
  };
  HandleType handle_type_;
  std::map<uintptr_t, AllocationSite> sites_;
  std::unordered_map<SiteId, uintptr_t> sites_by_id_;
  std::unordered_map<SiteId, uint64_t> site_types_;
  std::map<uintptr_t, Allocation> allocations_;
};

}  // inline namespace INTERSPEC_REGISTRY_ABI

constexpr uint64_t type_hash(const char* text) {
  uint64_t hash = 0;
  while (*text) hash = 129 * hash + static_cast<unsigned char>(*text++);
  return hash;
}

}  // namespace interspec

#endif  // INTERSPEC_RUNTIME_H_INCLUDED
