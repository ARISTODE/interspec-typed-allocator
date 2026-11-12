#include "../evaluation/memcached_workload.h"
#include <algorithm>
#include <atomic>
#include <cassert>
#include <cmath>
#include <iostream>
#include <set>
#include <thread>
#include <vector>
using namespace memcached_workload;
int main() {
    assert(parse_mode("legacy") == Mode::legacy);
    assert(parse_mode("independent-v1") == Mode::independent_v1);
    bool rejected=false;try{parse_mode("typo");}catch(const std::invalid_argument&){rejected=true;}assert(rejected);
    for(uint64_t op=0;op<100000;++op) {
        auto a=request(Mode::legacy,42,op,10000,50);
        assert(a.key==(op*104729)%10000 && a.get==((op*37)%100<50));
        for(unsigned w=0;w<8;++w)assert(timed_op(Mode::legacy,op,w,8)==w*997+op);
    }
    const uint64_t N=2000000, keys=10000;
    for(uint64_t seed:{uint64_t(0),uint64_t(20261109),UINT64_C(0xffffffffffffffff)}) {
        for(unsigned pct:{10u,50u,95u}) {
            std::vector<unsigned> get(keys),set(keys);uint64_t total=0,differences=0;
            for(uint64_t op=0;op<N;++op) {
                auto a=request(Mode::independent_v1,seed,op,keys,pct);
                auto b=request(Mode::independent_v1,seed,op,keys,pct);
                assert(a.key==b.key && a.get==b.get);
                auto c=request(Mode::independent_v1,seed^12345,op,keys,pct);
                differences+=a.key!=c.key;
                assert(a.key<keys); (a.get?get:set)[a.key]++;total+=a.get;
            }
            const double p=pct/100.0;
            // A deterministic regression tolerance, not a statistical proof:
            // six binomial standard deviations plus a rounding allowance.
            assert(std::abs(double(total)-N*p)<6*std::sqrt(N*p*(1-p))+1);
            unsigned mixed=0;double pearson=0;
            for(unsigned k=0;k<keys;++k){unsigned n=get[k]+set[k];assert(n>0);mixed+=get[k]>0&&set[k]>0;pearson+=std::pow(get[k]-n*p,2)/(n*p*(1-p));}
            assert(mixed>=9990);assert(pearson<13000);assert(differences>N*0.99);
            std::cout<<"seed="<<seed<<" pct="<<pct<<" N="<<N<<" gets="<<total<<" mixed_keys="<<mixed<<" conditional_pearson="<<pearson<<"\n";
        }
    }
    for(unsigned pct:{0u,100u}) for(uint64_t op=0;op<10000;++op)
        assert(request(Mode::independent_v1,7,op,10000,pct).get==(pct==100));
    // Global fixed-work IDs cover exactly [0,N), regardless of batch ownership.
    const uint64_t fixed=10003;
    for(unsigned clients:{1u,8u})for(unsigned pipeline:{1u,10u,16u}){
        std::atomic<uint64_t> next{0};std::vector<Request> got(fixed);std::vector<std::thread> threads;
        for(unsigned w=0;w<clients;++w)threads.emplace_back([&]{while(true){auto first=next.fetch_add(pipeline);if(first>=fixed)break;for(auto op=first;op<std::min(first+pipeline,fixed);++op)got[op]=request(Mode::independent_v1,20261109,op,10000,50);}});
        for(auto &t:threads)t.join();
        for(uint64_t op=0;op<fixed;++op){auto a=request(Mode::independent_v1,20261109,op,10000,50);assert(got[op].key==a.key&&got[op].get==a.get);}
        std::set<uint64_t> ids;for(unsigned w=0;w<clients;++w)for(uint64_t n=0;n<1000;++n)assert(ids.insert(timed_op(Mode::independent_v1,n,w,clients)).second);
        std::cout<<"fixed_coverage clients="<<clients<<" pipeline="<<pipeline<<" N="<<fixed<<" passed\n";
    }
    for(unsigned pct:{10u,50u,95u}){uint64_t n=0;for(uint64_t op=0;op<5000;++op)n+=request(Mode::independent_v1,20261109,op,10000,pct).get;std::cout<<"smoke_expected pct="<<pct<<" gets="<<n<<" sets="<<5000-n<<"\n";}
}
