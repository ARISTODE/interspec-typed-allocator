/* Same upstream buffer API and production bridge. Setup, drain, and content
 * validation are outside each measured batch. Raw times are not subtracted. */
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
extern "C" {
#include "bipbuffer.h"
#ifdef INTERSPEC_NATIVE_BENCH
uint32_t interspec_native_empty_call(uint32_t);
#else
uint64_t interspec_bench_primitive(bipbuf_t *, unsigned, unsigned, unsigned, uint64_t *);
#endif
}
using Clock = std::chrono::steady_clock;
static void require(bool ok) { if (!ok) throw std::runtime_error("boundary benchmark functional control failed"); }
static void emit(const char *metric, unsigned bytes, unsigned iterations, uint64_t ns, uint64_t checksum) {
    require(ns > 0);
    std::printf("%s,%u,%u,%llu,%.9f,%llu\n", metric, bytes, iterations,
                (unsigned long long)ns, double(ns) / iterations, (unsigned long long)checksum);
}
int main(int argc, char **argv) {
    try {
        unsigned iterations = argc == 2 ? std::stoul(argv[1]) : 20000;
        require(iterations >= 100 && iterations <= 10000000);
        // Ensure glibc uses its multithreaded mutex path, as the server does.
        std::thread([] {}).join();
        constexpr unsigned capacity = 65536;
        bipbuf_t *buffer = bipbuf_new(capacity);
        require(buffer != nullptr);
        std::printf("metric,bytes,operations,total_ns,ns_per_op,checksum\n");
        uint64_t checksum = 0;
#ifdef INTERSPEC_NATIVE_BENCH
        // One untimed pass warms the exact call path before the recorded loop.
        for (unsigned i = 0; i < 1000; ++i) require(interspec_native_empty_call(i) == i + 1);
        auto begin = Clock::now();
        for (unsigned i = 0; i < iterations; ++i) {
            auto value = interspec_native_empty_call(i);
            asm volatile("" : : "r"(value) : "memory");
            checksum += value;
        }
        auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - begin).count();
        require(checksum == uint64_t(iterations) * (iterations + 1) / 2);
        emit("empty_call", 0, iterations, elapsed, checksum);
#else
        const char *names[] = {"empty_call", "wrapper_mutex", "pointer_confinement", "copy_into_u", "copy_from_u"};
        for (unsigned metric = 0; metric < 5; ++metric) {
            for (unsigned bytes : {64u, 256u, 1024u, 4096u}) {
                if (metric < 3 && bytes != 64) continue;
                unsigned recorded_bytes = metric < 2 ? 0 : bytes;
                interspec_bench_primitive(buffer, metric, bytes, 1000, &checksum);
                auto ns = interspec_bench_primitive(buffer, metric, bytes, iterations, &checksum);
                emit(names[metric], recorded_bytes, iterations, ns, checksum);
            }
        }
#endif
        for (unsigned bytes : {64u, 256u, 1024u, 4096u}) {
            std::vector<unsigned char> payload(bytes);
            for (unsigned i = 0; i < bytes; ++i) payload[i] = static_cast<unsigned char>(i * 13 + 7);
            auto offer = [&] { require(bipbuf_offer(buffer, payload.data(), bytes) == int(bytes)); };
            auto verify = [&](unsigned char *p) { require(p && !std::memcmp(p, payload.data(), bytes)); };
            // Untimed content controls for both read APIs before any timing.
            bipbuf_init(buffer, capacity);
            offer();
            unsigned returned = 0;
            verify(bipbuf_peek_all(buffer, &returned));
            require(returned == bytes);
            verify(bipbuf_poll(buffer, bytes));
            require(bipbuf_used(buffer) == 0);
            for (const char *operation : {"request_push", "offer", "peek_all", "poll"}) {
                const unsigned kind = !std::strcmp(operation, "request_push") ? 0 :
                                      !std::strcmp(operation, "offer") ? 1 :
                                      !std::strcmp(operation, "peek_all") ? 2 : 3;
                uint64_t total = 0;
                unsigned completed = 0;
                checksum = 0;
                while (completed < iterations + 1000) {
                    // At least 16 operations amortize a clock pair at 4 KiB.
                    unsigned batch = std::min(capacity / bytes, iterations + 1000 - completed);
                    // Do not let a batch straddle the warmup boundary.
                    if (completed < 1000) batch = std::min(batch, 1000 - completed);
                    bipbuf_init(buffer, capacity);
                    bool peek = kind == 2, poll = kind == 3;
                    if (peek) offer();
                    if (poll) for (unsigned i = 0; i < batch; ++i) offer();
                    auto begin = Clock::now();
                    for (unsigned i = 0; i < batch; ++i) {
                        unsigned char *value = nullptr;
                        if (kind == 0) {
                            value = bipbuf_request(buffer, bytes);
                            require(value != nullptr);
                            std::memcpy(value, payload.data(), bytes);
                            require(bipbuf_push(buffer, bytes) == int(bytes));
                        } else if (kind == 1) {
                            offer();
                        } else if (peek) {
                            unsigned actual = 0;
                            value = bipbuf_peek_all(buffer, &actual);
                            require(actual == bytes && value != nullptr);
                        } else {
                            value = bipbuf_poll(buffer, bytes);
                            require(value != nullptr);
                        }
                        asm volatile("" : : "r"(value) : "memory");
                    }
                    auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - begin).count();
                    if (completed >= 1000) total += ns;
                    // Check every remaining payload outside the timed region.
                    if (peek) verify(bipbuf_poll(buffer, bytes));
                    else if (!poll) for (unsigned i = 0; i < batch; ++i) verify(bipbuf_poll(buffer, bytes));
                    require(bipbuf_used(buffer) == 0);
                    if (completed >= 1000) checksum += batch;
                    completed += batch;
                }
                require(checksum == iterations);
                emit(operation, bytes, iterations, total, checksum);
            }
        }
        bipbuf_free(buffer);
    } catch (const std::exception &error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 1;
    }
}
