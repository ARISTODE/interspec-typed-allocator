// Workload shared by assoc_app_bench.cpp and assoc_native_bench.cpp (tracker
// item I9): a trusted cache that keeps its items in T and its hash table
// behind memcached's assoc interface.
//
// Table is the trusted-side view of that interface:
//   bool  init(unsigned hashpower)
//   uint32_t hash(std::string& key)
//   Item* find(std::string& key, uint32_t hv)                assoc_find
//   bool  insert(Item* it, uint32_t hv)                      assoc_insert
//   void  remove(std::string& key, uint32_t hv)              assoc_delete
//   void  forget(Item* it)        T is about to free the item
//   iterator: begin_walk(), walk(&it) (false at the end), end_walk()
#pragma once

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace assoc_workload {

// The header fields of memcached's item (struct _stritem at the pinned
// revision); the key (nkey bytes) and the value (nbytes bytes) follow.
struct Item {
  Item* next = nullptr;
  Item* prev = nullptr;
  Item* h_next = nullptr;
  uint32_t time = 0;
  uint32_t exptime = 0;
  int nbytes = 0;
  uint16_t refcount = 0;
  uint16_t it_flags = 0;
  uint8_t slabs_clsid = 0;
  uint8_t nkey = 0;
  char* key() { return reinterpret_cast<char*>(this + 1); }
  char* value() { return key() + nkey; }
};

inline Item* new_item(const std::string& key, const std::string& value) {
  void* memory = std::calloc(1, sizeof(Item) + key.size() + value.size());
  if (!memory) throw std::bad_alloc();
  Item* it = new (memory) Item;
  it->nkey = static_cast<uint8_t>(key.size());
  it->nbytes = static_cast<int>(value.size());
  it->refcount = 1;
  it->exptime = 0x5ec2e701;
  it->next = it->prev = it;  // T pointers that the hash table has no use for
  std::memcpy(it->key(), key.data(), key.size());
  std::memcpy(it->value(), value.data(), value.size());
  return it;
}

inline uint64_t fnv(const char* p, size_t n, uint64_t h = UINT64_C(1469598103934665603)) {
  for (size_t i = 0; i < n; i++) {
    h ^= static_cast<unsigned char>(p[i]);
    h *= UINT64_C(1099511628211);
  }
  return h;
}

inline std::string value_for(size_t key_index, size_t op) {
  return "T_SECRET_VALUE_" + std::to_string(key_index) + "_" + std::to_string(op);
}

struct Result {
  size_t finds = 0, hits = 0, inserts = 0, deletes = 0, live = 0, iterated = 0;
  uint64_t checksum = 0, iter_xor = 0, elapsed_ns = 0;
  // Of the first item T inserted, read from T's own item after the run.
  unsigned first_refcount = 0, first_key_byte = 0;
};

template <class Table>
Result run(Table& table, size_t ops, size_t keyspace, unsigned hashpower) {
  if (!table.init(hashpower)) throw std::runtime_error("assoc_init");
  std::vector<std::string> keys;
  for (size_t i = 0; i < keyspace; i++) keys.push_back("k" + std::to_string(i));
  std::mt19937_64 rng(0xC0FFEEULL);
  Result result;
  Item first_copy;
  bool have_first = false;
  Item* first = nullptr;

  const auto start = std::chrono::steady_clock::now();
  for (size_t op = 0; op < ops; op++) {
    const size_t index = rng() % keyspace;
    const unsigned kind = static_cast<unsigned>(rng() % 10);
    std::string& key = keys[index];
    const uint32_t hv = table.hash(key);
    Item* it = table.find(key, hv);
    if (kind < 6) {  // get
      result.finds++;
      if (it) {
        result.hits++;
        result.checksum ^= fnv(it->value(), static_cast<size_t>(it->nbytes));
      }
    } else if (kind < 9) {  // set
      if (!it) {
        it = new_item(key, value_for(index, op));
        if (!table.insert(it, hv)) throw std::runtime_error("assoc_insert");
        result.inserts++;
        result.live++;
        if (!have_first) {
          have_first = true;
          first = it;
        }
      } else {
        it->time++;
      }
    } else if (it) {  // delete
      if (it == first) {
        first_copy = *first;
        result.first_key_byte = static_cast<unsigned char>(first->key()[0]);
        first = nullptr;
      }
      table.remove(key, hv);
      table.forget(it);
      std::free(it);
      result.deletes++;
      result.live--;
    }
  }
  // Walk the table, as memcached's crawler does, and release everything.
  std::vector<Item*> remaining;
  table.begin_walk();
  for (Item* it = nullptr; table.walk(&it);) {
    if (!it) continue;
    result.iterated++;
    result.iter_xor ^= fnv(it->key(), it->nkey);
    remaining.push_back(it);
  }
  table.end_walk();
  const auto finish = std::chrono::steady_clock::now();

  if (first) {
    first_copy = *first;
    result.first_key_byte = static_cast<unsigned char>(first->key()[0]);
  }
  result.first_refcount = first_copy.refcount;
  for (Item* it : remaining) {
    table.forget(it);
    std::free(it);
  }
  result.elapsed_ns = static_cast<uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(finish - start).count());
  return result;
}

inline void print(const char* variant, size_t ops, size_t keyspace, const Result& r,
                  unsigned long long checks) {
  std::printf(
      "ASSOC_BENCH variant=%s ops=%zu keyspace=%zu finds=%zu hits=%zu inserts=%zu "
      "deletes=%zu live=%zu checksum=%016llx iterated=%zu iter_xor=%016llx checks=%llu "
      "elapsed_ns=%llu\n",
      variant, ops, keyspace, r.finds, r.hits, r.inserts, r.deletes, r.live,
      static_cast<unsigned long long>(r.checksum), r.iterated,
      static_cast<unsigned long long>(r.iter_xor), checks,
      static_cast<unsigned long long>(r.elapsed_ns));
}

// Two fixed sequences for the tests that need a particular order of calls.
//   find:  insert k0, insert k1, find k0
//   stale: insert k0, delete k0 (T frees it), insert k1, find k0
// Prints which item T was handed for k0.
template <class Table> void run_script(Table& table, const std::string& script) {
  if (!table.init(4)) throw std::runtime_error("assoc_init");
  std::string k0 = "k0", k1 = "k1";
  Item* a = new_item(k0, value_for(0, 0));
  Item* b = new_item(k1, value_for(1, 1));
  if (!table.insert(a, table.hash(k0))) throw std::runtime_error("assoc_insert");
  if (script == "stale") {
    table.remove(k0, table.hash(k0));
    table.forget(a);
    std::free(a);
    a = nullptr;
  } else if (script != "find") {
    throw std::runtime_error("unknown_script");
  }
  if (!table.insert(b, table.hash(k1))) throw std::runtime_error("assoc_insert");
  Item* found = table.find(k0, table.hash(k0));
  std::printf("ASSOC_SCRIPT script=%s find_k0=%s\n", script.c_str(),
              found ? std::string(found->key(), found->nkey).c_str() : "none");
  if (a) { table.forget(a); std::free(a); }
  table.forget(b);
  std::free(b);
}

}  // namespace assoc_workload
