// Native reference for the memcached/hash port with the hash table in U
// (tracker item I9): the workload of assoc_workload.h against assoc_u.c and
// the hash function compiled without a sandbox. A handle is the item's address.
#include "assoc_workload.h"

extern "C" {
#include "assoc_bridge.h"
uint64_t hash_untrusted(const char* data, uint32_t len);
int interspec_assoc_init(uint32_t);
uintptr_t interspec_assoc_find(const char*, uint32_t, uint32_t);
int interspec_assoc_insert(assoc_item_image_t*, uint32_t, uintptr_t, uint32_t);
void interspec_assoc_delete(const char*, uint32_t, uint32_t);
uintptr_t interspec_assoc_get_iterator(void);
int interspec_assoc_iterate(uintptr_t);
uintptr_t interspec_assoc_iterate_item(uintptr_t);
void interspec_assoc_iterate_final(uintptr_t);
}

namespace {
using assoc_workload::Item;

class NativeTable {
 public:
  bool init(unsigned hashpower) { return interspec_assoc_init(hashpower) == 1; }
  uint32_t hash(std::string& key) {
    return static_cast<uint32_t>(hash_untrusted(key.data(), static_cast<uint32_t>(key.size())));
  }
  Item* find(std::string& key, uint32_t hv) {
    return reinterpret_cast<Item*>(
        interspec_assoc_find(key.data(), static_cast<uint32_t>(key.size()), hv));
  }
  bool insert(Item* it, uint32_t hv) {
    const uint32_t bytes = static_cast<uint32_t>(sizeof(assoc_item_image_t)) + it->nkey +
                           static_cast<uint32_t>(it->nbytes);
    image_.resize(bytes);
    auto* image = reinterpret_cast<assoc_item_image_t*>(image_.data());
    *image = assoc_item_image_t{};
    image->time = it->time;
    image->exptime = it->exptime;
    image->nbytes = it->nbytes;
    image->refcount = it->refcount;
    image->it_flags = it->it_flags;
    image->slabs_clsid = it->slabs_clsid;
    image->nkey = it->nkey;
    std::memcpy(ASSOC_IMAGE_KEY(image), it->key(), it->nkey + static_cast<size_t>(it->nbytes));
    return interspec_assoc_insert(image, bytes, reinterpret_cast<uintptr_t>(it), hv) == 1;
  }
  void remove(std::string& key, uint32_t hv) {
    interspec_assoc_delete(key.data(), static_cast<uint32_t>(key.size()), hv);
  }
  void forget(Item*) {}
  void begin_walk() { iterator_ = interspec_assoc_get_iterator(); }
  bool walk(Item** it) {
    if (!interspec_assoc_iterate(iterator_)) return false;
    *it = reinterpret_cast<Item*>(interspec_assoc_iterate_item(iterator_));
    return true;
  }
  void end_walk() { interspec_assoc_iterate_final(iterator_); }

 private:
  std::vector<unsigned char> image_;
  uintptr_t iterator_ = 0;
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
    NativeTable table;
    const auto result = assoc_workload::run(table, ops, keyspace, 12);
    assoc_workload::print("native", ops, keyspace, result, 0);
    return 0;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "assoc benchmark error: %s\n", error.what());
    return 1;
  }
}
