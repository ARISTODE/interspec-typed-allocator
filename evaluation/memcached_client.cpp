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
int main(int argc, char **argv) {
    if (argc != 8) {
        std::fprintf(stderr, "usage: client PORT SECONDS CLIENTS PIPELINE VALUE_BYTES KEYS GET_PERCENT\n");
        return 2;
    }
    int port = std::stoi(argv[1]), clients = std::stoi(argv[3]), pipeline = std::stoi(argv[4]);
    double seconds = std::stod(argv[2]);
    int value_bytes = std::stoi(argv[5]), keys = std::stoi(argv[6]), get_percent = std::stoi(argv[7]);
    if (seconds <= 0 || clients < 1 || pipeline < 1 || value_bytes < 1 || keys < 1 || get_percent < 0 || get_percent > 100) return 2;
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
    Clock::time_point deadline;
    std::vector<std::vector<double>> latencies(clients);
    std::vector<std::thread> threads;
    for (int worker = 0; worker < clients; ++worker) threads.emplace_back([&, worker] {
        int fd = -1;
        bool announced = false;
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
            std::vector<char> buffer(value_bytes + 256);
            std::vector<const std::string *> expected(pipeline);
            auto &samples = latencies[worker];
            samples.reserve(100000);
            std::string batch;
            batch.reserve(pipeline * (value_bytes + 80));
            ready++; announced = true;
            while (!go.load()) std::this_thread::yield();
            uint64_t n = worker * 997;
            while (Clock::now() < deadline) {
                batch.clear();
                for (int j = 0; j < pipeline; ++j, ++n) {
                    // Deterministic key permutation; identical mix for all variants.
                    auto key = (n * 104729) % keys;
                    bool get = (n * 37) % 100 < static_cast<uint64_t>(get_percent);
                    batch += get ? gets[key] : sets[key];
                    expected[j] = get ? &responses[key] : &stored;
                }
                auto start = Clock::now();
                send_all(fd, batch);
                for (int j = 0; j < pipeline; ++j) {
                    expect(fd, *expected[j], buffer);
                    samples.push_back(std::chrono::duration<double, std::micro>(Clock::now() - start).count());
                }
            }
        } catch (const std::exception &e) {
            std::fprintf(stderr, "client_error=%s worker=%d\n", e.what(), worker);
            errors++;
            if (!announced) ready++;
        }
        if (fd >= 0) close(fd);
    });
    while (ready.load() != clients) std::this_thread::yield();
    auto start = Clock::now();
    deadline = start + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(seconds));
    go = true;
    for (auto &thread : threads) thread.join();
    double elapsed = std::chrono::duration<double>(Clock::now() - start).count();
    std::vector<double> all;
    for (auto &v : latencies) all.insert(all.end(), v.begin(), v.end());
    if (errors || all.empty()) return 1;
    std::sort(all.begin(), all.end());
    auto q = [&](double p) { return all[static_cast<size_t>(p * (all.size() - 1))]; };
    std::printf("{\"operations\":%zu,\"elapsed_s\":%.9f,\"ops_per_s\":%.3f,\"p50_us\":%.3f,\"p95_us\":%.3f,\"p99_us\":%.3f,\"max_us\":%.3f,\"errors\":0}\n",
        all.size(), elapsed, all.size()/elapsed, q(.50), q(.95), q(.99), all.back());
}
