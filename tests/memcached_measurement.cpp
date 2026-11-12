#include "../evaluation/memcached_measurement.h"
#include <cassert>
#include <cmath>
#include <iostream>
using namespace memcached_measurement;
int main(){
    Samples count(Mode::count_only,100000); assert(count.values.capacity()==0);
    assert(!count.observe_selection(false)); assert(count.values.empty());
    Samples bounded(Mode::sampled,3);assert(bounded.values.capacity()>=3);
    for(int i=0;i<100;++i)if(bounded.observe_selection(true))bounded.record(i);
    assert(bounded.values.size()==3 && bounded.selected_count==100 && bounded.dropped==97);
    uint64_t selected_n=0,selected_get=0; double key_total=0; const uint64_t N=2000000;
    for(uint64_t op=0;op<N;++op){
        bool a=selected(op,20261109,1024);assert(a==selected(op,20261109,1024));
        if(a){auto r=memcached_workload::request(memcached_workload::Mode::independent_v1,20261109,op,10000,50);++selected_n;selected_get+=r.get;key_total+=r.key;}
    }
    assert(selected_n>1700&&selected_n<2200);
    assert(double(selected_get)/selected_n>.44&&double(selected_get)/selected_n<.56);
    assert(key_total/selected_n>4500&&key_total/selected_n<5500);
    uint64_t by_batch=0;for(uint64_t first=0;first<N;first+=16)for(uint64_t op=first;op<std::min(first+16,N);++op)by_batch+=selected(op,20261109,1024);
    assert(by_batch==selected_n);
    std::cout<<"sample_count="<<selected_n<<" selected_GET_fraction="<<double(selected_get)/selected_n<<" mean_key="<<key_total/selected_n<<" cap and no-allocation checks passed\n";
}
