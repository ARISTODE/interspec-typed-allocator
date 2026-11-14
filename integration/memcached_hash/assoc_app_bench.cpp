// Trusted program for the memcached/hash boundary with the hash table in U
// (tracker item I9, JH decision of 2026-11-14): the cache workload of
// assoc_workload.h with memcached's hash function and hash table inside an
// RLBox wasm2c sandbox.
//
// T-level interface (memcached's hash.h and assoc.h):
//   hash(key, nkey)
//   assoc_find(key, nkey, hv) -> item*
//   assoc_insert(item*, hv)
//   assoc_delete(key, nkey, hv)
//   assoc_get_iterator / assoc_iterate(iter, &item) / assoc_iterate_final
// T keeps its items; U keeps the table. U names an item of T by a handle.
#define RLBOX_USE_EXCEPTIONS
#define RLBOX_USE_STATIC_CALLS() rlbox_wasm2c_sandbox_lookup_symbol
#define RLBOX_WASM2C_MODULE_NAME glue__lib__wasm2c
#include "glue_lib_wasm2c.h"
#include "rlbox.hpp"
#include "rlbox_wasm2c_sandbox.hpp"

#include "assoc_workload.h"
#include "interspec/boundary/wasm_port.h"

#include <unordered_map>

extern "C" {
#include "assoc_bridge.h"
// hash_u.c
unsigned char* interspec_hash_stage(uint32_t);
unsigned long long interspec_hash_run(uint32_t, uint32_t);
// assoc_u.c. Addresses and handles are 32-bit values inside the sandbox.
int interspec_assoc_init(uint32_t);
uint32_t interspec_assoc_find(uint32_t, uint32_t, uint32_t);
int interspec_assoc_insert(uint32_t, uint32_t, uint32_t, uint32_t);
void interspec_assoc_delete(uint32_t, uint32_t, uint32_t);
uint32_t interspec_assoc_get_iterator(void);
int interspec_assoc_iterate(uint32_t);
uint32_t interspec_assoc_iterate_item(uint32_t);
void interspec_assoc_iterate_final(uint32_t);
unsigned char* interspec_assoc_stage(uint32_t, uint32_t);
#ifdef INTERSPEC_FAULT_TESTS
void interspec_assoc_fault(uint32_t);
void interspec_assoc_poc(uint32_t);
void interspec_hash_poc(uint32_t);
#endif
}

namespace {

using assoc_workload::Item;

struct AssocPolicy {
  static constexpr const char* boundary = "memcached_hash";
  static constexpr int reject_exit = 86;
};
using Port = interspec::WasmPort<AssocPolicy>;

#if !INTERSPEC_CHECKS
constexpr const char* kVariant = "rlbox-only";
#else
constexpr const char* kVariant = "interspec";
#endif

// invoke_sandbox_function is a macro that needs the function's name.
#define ASSOC_CALL(name, ...) \
  (port_.sandbox().invoke_sandbox_function(name, __VA_ARGS__).UNSAFE_unverified())
#define ASSOC_CALL0(name) (port_.sandbox().invoke_sandbox_function(name).UNSAFE_unverified())

class SandboxTable {
 public:
  SandboxTable() : port_(0) {}
  Port& port() { return port_; }

  bool init(unsigned hashpower) { return ASSOC_CALL(interspec_assoc_init, hashpower) == 1; }

  uint32_t hash(std::string& key) {
    const uint32_t len = static_cast<uint32_t>(key.size());
    unsigned char* staged = port_.input_buffer(
        port_.sandbox().invoke_sandbox_function(interspec_hash_stage, len), len, "key");
    std::memcpy(staged, key.data(), len);
    const unsigned long long value =
        ASSOC_CALL(interspec_hash_run, port_.address_of(staged), len);
    std::memcpy(&key[0], staged, len);  // U's version of the key is copied back
    return static_cast<uint32_t>(value);
  }

  Item* find(std::string& key, uint32_t hv) {
    unsigned char* staged = stage_key(key);
    const uint32_t handle = ASSOC_CALL(interspec_assoc_find, port_.address_of(staged),
                                       static_cast<uint32_t>(key.size()), hv);
    std::memcpy(&key[0], staged, key.size());  // copied back
    return handle ? resolve(handle, "assoc_find") : nullptr;
  }

  bool insert(Item* it, uint32_t hv) {
    // The whole item is copied in: header fields, key and value.
    const uint32_t body = it->nkey + static_cast<uint32_t>(it->nbytes);
    const uint32_t bytes = static_cast<uint32_t>(sizeof(assoc_item_image_t)) + body;
    unsigned char* staged = stage(1, bytes);
    assoc_item_image_t image{};
    image.next = low32(it->next);
    image.prev = low32(it->prev);
    image.h_next = low32(it->h_next);
    image.time = it->time;
    image.exptime = it->exptime;
    image.nbytes = it->nbytes;
    image.refcount = it->refcount;
    image.it_flags = it->it_flags;
    image.slabs_clsid = it->slabs_clsid;
    image.nkey = it->nkey;
    std::memcpy(staged, &image, sizeof(image));
    std::memcpy(staged + sizeof(image), it->key(), body);

    const uint32_t handle = issue(it);
    const int rc =
        ASSOC_CALL(interspec_assoc_insert, port_.address_of(staged), bytes, handle, hv);

    // U's version of the item is copied back, except the pointer fields.
    std::memcpy(&image, staged, sizeof(image));
    it->time = image.time;
    it->exptime = image.exptime;
    it->nbytes = image.nbytes;
    it->refcount = image.refcount;
    it->it_flags = image.it_flags;
    it->slabs_clsid = image.slabs_clsid;
    it->nkey = image.nkey;
    std::memcpy(it->key(), staged + sizeof(image), body);
    return rc == 1;
  }

  void remove(std::string& key, uint32_t hv) {
    unsigned char* staged = stage_key(key);
    port_.sandbox().invoke_sandbox_function(interspec_assoc_delete, port_.address_of(staged),
                                            static_cast<uint32_t>(key.size()), hv);
    std::memcpy(&key[0], staged, key.size());  // copied back
  }

  // T is about to free the item: its handle stops naming it.
  void forget(Item* it) {
    const auto found = handle_of_.find(it);
    if (found == handle_of_.end()) return;
    slots_[found->second - 1] = nullptr;
    free_slots_.push_back(found->second);
    handle_of_.erase(found);
  }

  void begin_walk() { iterator_ = ASSOC_CALL0(interspec_assoc_get_iterator); }
  bool walk(Item** it) {
    if (!ASSOC_CALL(interspec_assoc_iterate, iterator_)) return false;
    const uint32_t handle = ASSOC_CALL(interspec_assoc_iterate_item, iterator_);
    *it = handle ? resolve(handle, "assoc_iterate") : nullptr;
    return true;
  }
  void end_walk() {
    port_.sandbox().invoke_sandbox_function(interspec_assoc_iterate_final, iterator_);
  }

 private:
  static uint32_t low32(const void* pointer) {
    return static_cast<uint32_t>(reinterpret_cast<uintptr_t>(pointer));
  }

  // Handles: slots of a table in T, reused after an item is freed.
  uint32_t issue(Item* it) {
    uint32_t handle;
    if (!free_slots_.empty()) {
      handle = free_slots_.back();
      free_slots_.pop_back();
      slots_[handle - 1] = it;
    } else {
      slots_.push_back(it);
      handle = static_cast<uint32_t>(slots_.size());
    }
    handle_of_[it] = handle;
    return handle;
  }

  // Only a handle whose slot is in use names an item.
  Item* resolve(uint32_t handle, const char* operation) {
    if (handle == 0 || handle > slots_.size() || !slots_[handle - 1])
      Port::reject(operation, "unknown_handle");
    return slots_[handle - 1];
  }

  unsigned char* stage(uint32_t which, uint32_t bytes) {
    return port_.input_buffer(
        port_.sandbox().invoke_sandbox_function(interspec_assoc_stage, which, bytes), bytes,
        "stage");
  }
  unsigned char* stage_key(const std::string& key) {
    unsigned char* staged = stage(0, static_cast<uint32_t>(key.size()));
    std::memcpy(staged, key.data(), key.size());
    return staged;
  }

  Port port_;
  std::vector<Item*> slots_;
  std::vector<uint32_t> free_slots_;
  std::unordered_map<Item*, uint32_t> handle_of_;
  uint32_t iterator_ = 0;
};

}  // namespace

int main(int argc, char** argv) {
  if (argc != 3) {
    std::fprintf(stderr, "usage: %s KEYSPACE OPS\n", argv[0]);
    return 2;
  }
  try {
    const size_t keyspace = std::stoul(argv[1]), ops = std::stoul(argv[2]);
    if (!keyspace || !ops) throw std::runtime_error("arguments");
    SandboxTable table;
#ifdef INTERSPEC_FAULT_TESTS
    if (const char* poc = std::getenv("INTERSPEC_TEST_POC_FLAGS"))
      table.port().sandbox().invoke_sandbox_function(
          interspec_assoc_poc, static_cast<uint32_t>(std::stoul(poc)));
    if (const char* fault = std::getenv("INTERSPEC_TEST_FAULT"))
      table.port().sandbox().invoke_sandbox_function(
          interspec_assoc_fault, static_cast<uint32_t>(std::stoul(fault)));
    if (const char* script = std::getenv("INTERSPEC_TEST_SCRIPT")) {
      assoc_workload::run_script(table, script);
      return 0;
    }
#endif
    const auto result = assoc_workload::run(table, ops, keyspace, 12);
#ifdef INTERSPEC_FAULT_TESTS
    // What T's own first item looks like after the run.
    std::fprintf(stderr,
                 "INTERSPEC_T_OBSERVE boundary=memcached_hash first_item_refcount=%u "
                 "first_item_key_byte=0x%02x\n",
                 result.first_refcount, result.first_key_byte);
#endif
    assoc_workload::print(kVariant, ops, keyspace, result, table.port().checks());
    return 0;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "assoc benchmark error: %s\n", error.what());
    return 1;
  }
}
