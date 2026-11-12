#ifndef INTERSPEC_MEMCACHED_MEASUREMENT_H
#define INTERSPEC_MEMCACHED_MEASUREMENT_H
#include "memcached_workload.h"
#include <string>
#include <vector>
namespace memcached_measurement {
enum class Mode { full, count_only, sampled };
inline Mode parse(const std::string &s) {
    if(s=="full") return Mode::full;
    if(s=="count-only") return Mode::count_only;
    if(s=="sampled") return Mode::sampled;
    throw std::invalid_argument("unknown measurement mode");
}
inline const char *name(Mode m) { return m==Mode::full?"full":m==Mode::sampled?"sampled":"count-only"; }
inline bool selected(uint64_t op,uint64_t seed,uint64_t every) {
    if(!every) throw std::invalid_argument("sample_every must be positive");
    // Third domain, distinct from both key and GET/SET draws. A deterministic
    // pseudorandom selection, not a guarantee of finite-sample independence.
    return memcached_workload::bounded(op,seed,UINT64_C(0xa4093822299f31d0),every)==0;
}
struct Samples {
    Mode mode;
    size_t cap;
    uint64_t selected_count=0, dropped=0;
    std::vector<double> values;
    Samples(Mode m,size_t c):mode(m),cap(c) {
        if(m==Mode::sampled) values.reserve(c);
        else if(m==Mode::full) values.reserve(100000);
    }
    bool observe_selection(bool take) {
        if(!take) return false;
        ++selected_count;
        if(mode==Mode::sampled && values.size()>=cap){++dropped;return false;}
        return mode!=Mode::count_only;
    }
    void record(double us) { values.push_back(us); }
};
}
#endif
