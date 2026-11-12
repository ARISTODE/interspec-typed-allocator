/* Loopback ASCII workload client. Validate every response, record response
 * latency from batch send to response completion (closed-loop pipelining). */
#include <arpa/inet.h>
#include <netinet/tcp.h>
#include <sys/socket.h>
#include <unistd.h>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
#include "memcached_workload.h"
#include "memcached_measurement.h"
#include <time.h>
#include <cmath>
#include <limits>
#include <cerrno>

using Clock = std::chrono::steady_clock;
static void send_all(int fd, const std::string &s) {
    size_t sent = 0;
    while (sent < s.size()) {
        auto n = send(fd, s.data() + sent, s.size() - sent, MSG_NOSIGNAL);
        if (n <= 0) throw std::runtime_error("send");
        sent += n;
    }
}
static void expect(int fd, const std::string &expected, std::vector<char> &buffer) {
    size_t got = 0;
    while (got < expected.size()) {
        auto n = recv(fd, buffer.data() + got, expected.size() - got, 0);
        if (n <= 0) throw std::runtime_error("receive");
        got += n;
    }
    if (std::memcmp(buffer.data(), expected.data(), got)) throw std::runtime_error("response_mismatch");
}
// Count-only may consume several responses from one receive. Keep unread bytes
// across calls, but compare every byte before counting an operation complete.
// Latency-bearing modes deliberately retain the original per-response reader.
class BufferedResponses {
    std::vector<char> &buffer;
    size_t begin = 0, end = 0;
public:
    explicit BufferedResponses(std::vector<char> &storage) : buffer(storage) {}
    void expect(int fd, const std::string &expected) {
        size_t checked = 0;
        while (checked < expected.size()) {
            if (begin == end) {
                auto n = recv(fd, buffer.data(), buffer.size(), 0);
                if (n <= 0) throw std::runtime_error("receive");
                begin = 0;
                end = static_cast<size_t>(n);
            }
            const size_t count = std::min(end - begin, expected.size() - checked);
            if (std::memcmp(buffer.data() + begin, expected.data() + checked, count))
                throw std::runtime_error("response_mismatch");
            begin += count;
            checked += count;
        }
    }
};
static uint64_t unsigned_arg(const char *text) {
    std::string s(text);
    if (s.empty() || s.find_first_not_of("0123456789") != std::string::npos)
        throw std::invalid_argument("expected unsigned decimal integer");
    size_t end = 0; auto value = std::stoull(s, &end);
    if (end != s.size()) throw std::invalid_argument("invalid integer");
    return value;
}
static int integer_arg(const char *text) {
    auto value = unsigned_arg(text);
    if (value > static_cast<uint64_t>(std::numeric_limits<int>::max()))
        throw std::invalid_argument("integer out of range");
    return static_cast<int>(value);
}
static int run(int argc, char **argv) {
    if (argc < 8 || argc > 14) {
        std::fprintf(stderr, "usage: client PORT SECONDS CLIENTS PIPELINE VALUE_BYTES KEYS GET_PERCENT [TOTAL_OPERATIONS [WORKLOAD_MODE [SEED [MEASUREMENT_MODE [SAMPLE_EVERY [SAMPLE_CAP_PER_CLIENT]]]]]]\n");
        return 2;
    }
    int port = integer_arg(argv[1]), clients = integer_arg(argv[3]), pipeline = integer_arg(argv[4]);
    size_t seconds_end = 0;
    double seconds = std::stod(argv[2], &seconds_end);
    if (seconds_end != std::strlen(argv[2]) || !std::isfinite(seconds) || seconds < 0 || seconds > 86400) return 2;
    int value_bytes = integer_arg(argv[5]), keys = integer_arg(argv[6]), get_percent = integer_arg(argv[7]);
    uint64_t total_operations = argc >= 9 ? unsigned_arg(argv[8]) : 0;
    auto mode = memcached_workload::parse_mode(argc >= 10 ? argv[9] : "legacy");
    uint64_t seed = argc >= 11 ? unsigned_arg(argv[10]) : UINT64_C(20261109);
    auto measurement = memcached_measurement::parse(argc >= 12 ? argv[11] : "full");
    uint64_t sample_every = argc >= 13 ? unsigned_arg(argv[12]) : 1024;
    uint64_t sample_cap = argc >= 14 ? unsigned_arg(argv[13]) : 100000;
    if (!sample_every || !sample_cap || sample_cap > 10000000 || port < 1 || port > 65535) return 2;
    // Keep the fixed-work ticket counter from wrapping, including final worker tickets.
    if (clients > 0 && pipeline > 0 && total_operations > std::numeric_limits<uint64_t>::max() -
        uint64_t(pipeline) * (uint64_t(clients) + 1)) return 2;
    if ((seconds <= 0 && total_operations == 0) || clients < 1 || pipeline < 1 || value_bytes < 1 || keys < 1 || get_percent < 0 || get_percent > 100) return 2;
    std::vector<std::string> sets, gets, responses;
    for (int i = 0; i < keys; ++i) {
        auto key = "bench" + std::to_string(i);
        auto value = std::string(value_bytes, 'x');
        sets.push_back("set " + key + " 0 0 " + std::to_string(value_bytes) + "\r\n" + value + "\r\n");
        gets.push_back("get " + key + "\r\n");
        responses.push_back("VALUE " + key + " 0 " + std::to_string(value_bytes) + "\r\n" + value + "\r\nEND\r\n");
    }
    const std::string stored = "STORED\r\n";
    std::atomic<int> ready{0}, errors{0};
    std::atomic<bool> go{false};
    std::atomic<uint64_t> next_operation{0};
    Clock::time_point deadline;
    std::vector<std::vector<double>> latencies(clients);
    std::vector<uint64_t> completions(clients), selected_counts(clients), dropped_counts(clients);
    std::vector<std::thread> threads;
    for (int worker = 0; worker < clients; ++worker) threads.emplace_back([&, worker] {
        int fd = -1;
        bool announced = false;
        uint64_t completed = 0;
        try {
            fd = socket(AF_INET, SOCK_STREAM, 0);
            int yes = 1;
            setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &yes, sizeof(yes));
            timeval timeout{10, 0};
            setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
            setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
            sockaddr_in address{};
            address.sin_family = AF_INET; address.sin_port = htons(port);
            inet_pton(AF_INET, "127.0.0.1", &address.sin_addr);
            if (connect(fd, reinterpret_cast<sockaddr *>(&address), sizeof(address))) throw std::runtime_error("connect");
            std::vector<char> buffer(measurement == memcached_measurement::Mode::count_only
                ? size_t(64 * 1024) : size_t(value_bytes) + 256);
            BufferedResponses buffered_responses(buffer);
            std::vector<const std::string *> expected(pipeline);
            memcached_measurement::Samples samples(measurement, sample_cap);
            std::vector<unsigned char> take_sample(pipeline);
            std::string batch;
            batch.reserve(size_t(pipeline) * (size_t(value_bytes) + 80));
            ready++; announced = true;
            while (!go.load()) std::this_thread::yield();
            uint64_t n = 0;
            while (true) {
                int batch_count = pipeline;
                uint64_t first = n;
                if (total_operations) {
                    first = next_operation.fetch_add(static_cast<uint64_t>(pipeline));
                    if (first >= total_operations) break;
                    batch_count = static_cast<int>(std::min<uint64_t>(
                        static_cast<uint64_t>(pipeline), total_operations - first));
                } else if (Clock::now() >= deadline) {
                    break;
                }
                batch.clear();
                bool timed_batch = measurement == memcached_measurement::Mode::full;
                for (int j = 0; j < batch_count; ++j) {
                    uint64_t op = total_operations ? first + static_cast<uint64_t>(j)
                        : memcached_workload::timed_op(mode, n++, worker, clients);
                    auto choice = memcached_workload::request(mode, seed, op, keys, get_percent);
                    auto key = choice.key;
                    bool get = choice.get;
                    batch += get ? gets[key] : sets[key];
                    expected[j] = get ? &responses[key] : &stored;
                    if (measurement == memcached_measurement::Mode::sampled) {
                        take_sample[j] = memcached_measurement::selected(op, seed, sample_every);
                        timed_batch = timed_batch || (take_sample[j] && samples.values.size() < sample_cap);
                    }
                }
                Clock::time_point batch_start{};
                if (timed_batch) batch_start = Clock::now();
                send_all(fd, batch);
                for (int j = 0; j < batch_count; ++j) {
                    if (measurement == memcached_measurement::Mode::count_only)
                        buffered_responses.expect(fd, *expected[j]);
                    else
                        expect(fd, *expected[j], buffer);
                    ++completed;
                    if (measurement != memcached_measurement::Mode::count_only &&
                        samples.observe_selection(measurement == memcached_measurement::Mode::full || take_sample[j]))
                        samples.record(std::chrono::duration<double, std::micro>(Clock::now() - batch_start).count());
                }
            }
            selected_counts[worker] = samples.selected_count;
            dropped_counts[worker] = samples.dropped;
            latencies[worker] = std::move(samples.values);
        } catch (const std::exception &e) {
            std::fprintf(stderr, "client_error=%s worker=%d\n", e.what(), worker);
            errors++;
            if (!announced) ready++;
        }
        completions[worker] = completed;
        if (fd >= 0) close(fd);
    });
    while (ready.load() != clients) std::this_thread::yield();
    auto process_cpu = []() {
        timespec t{};
        if (clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &t)) throw std::runtime_error("process CPU clock");
        return double(t.tv_sec) + double(t.tv_nsec) * 1e-9;
    };
    auto start = Clock::now();
    const double cpu_start = process_cpu();
    deadline = total_operations ? Clock::time_point::max() : start + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(seconds));
    go = true;
    for (auto &thread : threads) thread.join();
    const double cpu_elapsed = process_cpu() - cpu_start;
    double elapsed = std::chrono::duration<double>(Clock::now() - start).count();
    uint64_t total = 0, selected_total = 0, dropped_total = 0;
    for (int i = 0; i < clients; ++i) {
        total += completions[i]; selected_total += selected_counts[i]; dropped_total += dropped_counts[i];
    }
    if (errors || !total) return 1;
    std::vector<double> all;
    for (auto &v : latencies) all.insert(all.end(), v.begin(), v.end());
    const bool valid_latency = measurement != memcached_measurement::Mode::count_only && !all.empty() && !dropped_total;
    std::sort(all.begin(), all.end());
    auto q = [&](double p) { return all[static_cast<size_t>(p * (all.size() - 1))]; };
    std::printf("{\"operations\":%llu,\"elapsed_s\":%.9f,\"ops_per_s\":%.3f,\"timed_client_cpu_s\":%.9f,",
        static_cast<unsigned long long>(total), elapsed, total/elapsed, cpu_elapsed);
    if (valid_latency)
        std::printf("\"p50_us\":%.3f,\"p95_us\":%.3f,\"p99_us\":%.3f,\"max_us\":%.3f,",q(.50),q(.95),q(.99),all.back());
    else std::printf("\"p50_us\":null,\"p95_us\":null,\"p99_us\":null,\"max_us\":null,");
    std::printf("\"errors\":0,\"workload_mode\":\"%s\",\"workload_seed\":%llu,\"measurement_mode\":\"%s\",\"sample_every\":%llu,\"sample_cap_per_client\":%llu,\"latency_sample_count\":%zu,\"latency_selected_count\":%llu,\"latency_dropped_count\":%llu,\"latency_valid\":%s,\"latency_scope\":\"%s\"}\n",
        memcached_workload::mode_name(mode), static_cast<unsigned long long>(seed), memcached_measurement::name(measurement),
        static_cast<unsigned long long>(measurement == memcached_measurement::Mode::sampled ? sample_every : 0),
        static_cast<unsigned long long>(measurement == memcached_measurement::Mode::sampled ? sample_cap : 0), all.size(),
        static_cast<unsigned long long>(selected_total), static_cast<unsigned long long>(dropped_total),valid_latency?"true":"false",
        measurement == memcached_measurement::Mode::count_only ? "unavailable" : measurement == memcached_measurement::Mode::sampled ? "sampled_response_batch_send_to_validation" : "all_responses_batch_send_to_validation");
    return 0;
}

int main(int argc, char **argv) {
    try { return run(argc, argv); }
    catch (const std::exception &e) {
        std::fprintf(stderr, "client_error=%s\n", e.what());
        return 2;
    }
}
