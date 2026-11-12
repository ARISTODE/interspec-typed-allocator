#ifndef INTERSPEC_MEMCACHED_WORKLOAD_H
#define INTERSPEC_MEMCACHED_WORKLOAD_H
#include <cstdint>
#include <stdexcept>
#include <string>
namespace memcached_workload {
enum class Mode { legacy, independent_v1 };
inline Mode parse_mode(const std::string &s) {
    if (s == "legacy") return Mode::legacy;
    if (s == "independent-v1") return Mode::independent_v1;
    throw std::invalid_argument("unknown workload mode");
}
inline const char *mode_name(Mode mode) {
    return mode == Mode::legacy ? "legacy" : "independent-v1";
}
// SplitMix64 finalizer with explicitly domain-separated counter inputs. These
// are reproducible pseudorandom draws, not cryptographic randomness. A pure
// operation-index mapping avoids dependence on thread/batch assignment.
inline uint64_t mix(uint64_t x) {
    x += UINT64_C(0x9e3779b97f4a7c15);
    x = (x ^ (x >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
    x = (x ^ (x >> 27)) * UINT64_C(0x94d049bb133111eb);
    return x ^ (x >> 31);
}
inline uint64_t bounded(uint64_t op, uint64_t seed, uint64_t domain, uint64_t bound) {
    // Reject the low remainder range rather than directly reducing every word.
    // This is a pseudorandom mapping, not a proof of exact uniformity. Retry
    // is local to this operation/domain,
    // never consumes another worker's stream or changes the other draw.
    uint64_t x = mix(op ^ mix(seed ^ domain));
    const uint64_t threshold = (uint64_t(0) - bound) % bound;
    while (x < threshold) x = mix(x);
    return x % bound;
}
struct Request { uint64_t key; bool get; };
inline Request request(Mode mode, uint64_t seed, uint64_t op,
                       uint64_t keys, unsigned get_percent) {
    if (!keys || get_percent > 100) throw std::invalid_argument("invalid workload parameters");
    if (mode == Mode::legacy)
        return {(op * UINT64_C(104729)) % keys, (op * UINT64_C(37)) % 100 < get_percent};
    return {bounded(op, seed, UINT64_C(0x243f6a8885a308d3), keys),
            bounded(op, seed, UINT64_C(0x13198a2e03707344), 100) < get_percent};
}
inline uint64_t timed_op(Mode mode, uint64_t ordinal, unsigned worker, unsigned clients) {
    // Legacy preserves its old per-thread phase/overlapping sequences exactly.
    // Independent IDs are disjoint across workers. Timed runs may complete
    // different per-worker prefixes; fixed-work runs cover exactly [0,N).
    return mode == Mode::legacy ? uint64_t(worker) * 997 + ordinal
                               : ordinal * clients + worker;
}
}
#endif
