#define RLBOX_USE_EXCEPTIONS
#define RLBOX_USE_STATIC_CALLS() rlbox_wasm2c_sandbox_lookup_symbol
#define RLBOX_WASM2C_MODULE_NAME glue__lib__wasm2c
#include "glue_lib_wasm2c.h"
#include "rlbox.hpp"
#include "rlbox_wasm2c_sandbox.hpp"
#include "interspec/runtime.h"
#if INTERSPEC_TRACKING
#include "interspec_bipbuffer_t_policy.h"
#endif
#include <climits>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <unordered_map>
#include <vector>
#ifdef INTERSPEC_BOUNDARY_BENCH
#include <chrono>
#endif

extern "C" {
#include "bipbuffer.h"
unsigned char *interspec_mc_new(uint32_t);
unsigned char *interspec_mc_request(uint32_t);
unsigned char *interspec_mc_peek_all();
unsigned char *interspec_mc_peek(uint32_t);
unsigned char *interspec_mc_poll(uint32_t);
uint32_t interspec_mc_last_size();
int interspec_mc_push(uint32_t);
int interspec_mc_offer(uint32_t);
int interspec_mc_used();
int interspec_mc_unused();
int interspec_mc_empty();
void interspec_mc_reset(uint32_t);
void interspec_mc_free();
#ifdef INTERSPEC_BOUNDARY_BENCH
uint32_t interspec_mc_bench_noop(uint32_t);
#endif
#ifdef INTERSPEC_FAULT_TESTS
void interspec_mc_fault(uint32_t, uint32_t);
#endif
}

namespace {
/* Count completed boundary calls only in diagnostic builds. The lambda and
 * helper inline away in release builds; trace code is preprocessor excluded. */
template <class B, class F>
decltype(auto) invoke_observed(B &buffer, const char *name, F &&fn) {
#ifdef INTERSPEC_ENABLE_TRACE
    interspec::DiagnosticEvent event(&buffer, "sandbox_call");
    event.result = name;
#else
    (void)buffer; (void)name;
#endif
    return fn();
}
#define MC_CALL(buffer, fn, ...) invoke_observed(buffer, #fn, [&]() { \
    return (buffer).sandbox.invoke_sandbox_function(fn, ##__VA_ARGS__); })
using Backend = rlbox::rlbox_wasm2c_sandbox;
using Sandbox = rlbox::rlbox_sandbox<Backend>;
using Pointer = rlbox::tainted<unsigned char *, Backend>;
#if INTERSPEC_TRACKING
namespace P = interspec::memcached_bipbuffer_generated;
#endif

[[noreturn]] void reject(const char *operation, const char *reason) {
    std::fprintf(stderr, "INTERSPEC_REJECT boundary=memcached_bipbuffer operation=%s reason=%s\n", operation, reason);
    std::fflush(stderr);
    std::abort();
}

/* The C API contains opaque T handles, never U-owned host pointers. Each handle
 * owns its sandbox and serializes calls. Read and write staging are separate:
 * logger_thread_read parses its snapshot after releasing the upstream mutex. */
struct Buffer {
    Sandbox sandbox;
#if INTERSPEC_TRACKING
    std::unique_ptr<interspec::Runtime> runtime;
#endif
    std::mutex mutex;
    const uint32_t capacity;
    Pointer input;
    std::vector<unsigned char> write_copy, read_copy;
    uint32_t pending = 0;
    struct ItemReference { void *item; uint32_t hash; };
    std::unordered_map<uintptr_t, ItemReference> item_references;
    uintptr_t next_reference = 1;

    explicit Buffer(uint32_t size) : capacity(size), write_copy(size), read_copy(size) {
        if (!sandbox.create_sandbox()) throw std::runtime_error("sandbox_creation");
        try {
#if INTERSPEC_TRACKING
        /* Owner + persistent input + room for one test-only same-type copy.
         * Normal traffic makes no additional typed allocations. Destroying a
         * watcher destroys its entire sandbox, avoiding a global bump arena. */
        const uint32_t arena_size = 3 * size + 4096;
        uint32_t base = sandbox.get_sandbox_impl()->reserve_typed_arena(arena_size);
        if (!base) throw std::bad_alloc();
        runtime = std::make_unique<interspec::Runtime>(base, arena_size);
        if (!P::register_types(*runtime) || !P::register_wasm_allocation_policy(*runtime))
            throw std::runtime_error("policy_registration");
        sandbox.get_sandbox_impl()->set_interspec_runtime(this,
            [](void *ctx, uint32_t site, uint32_t bytes) -> uint32_t {
                return static_cast<Buffer *>(ctx)->runtime->allocate_from_site(bytes, site);
            },
            [](void *ctx, uint32_t ptr) -> uint32_t {
                return static_cast<Buffer *>(ctx)->runtime->release(ptr);
            },
            [](void *ctx, uint32_t ptr) -> uint32_t {
                size_t bytes = 0;
                static_cast<Buffer *>(ctx)->runtime->allocation_size(ptr, bytes);
                return static_cast<uint32_t>(bytes);
            },
            [](void *ctx, uint32_t ptr, uint32_t bytes) -> uint32_t {
                return static_cast<Buffer *>(ctx)->runtime->reallocate(ptr, bytes);
            });
#endif
        input = MC_CALL(*this, interspec_mc_new, size);
        if (!input.UNSAFE_unverified()) throw std::bad_alloc();
        validate(input, capacity, "input", true);
        } catch (...) {
            sandbox.destroy_sandbox();
            throw;
        }
    }
    ~Buffer() { sandbox.destroy_sandbox(); }

    unsigned char *validate(Pointer pointer, uint32_t bytes, const char *op, bool is_input = false) {
        unsigned char *ptr = pointer.UNSAFE_unverified();
        if (!ptr) reject(op, "null_pointer");
        uint32_t address = sandbox.get_sandbox_impl()->sandbox_address(ptr);
        /* The common RLBox baseline retains sandbox confinement and T's
         * staging capacity limit. Only the SP3 variant checks object metadata. */
        if (!sandbox.is_pointer_in_sandbox_memory(ptr) ||
            bytes > sandbox.get_total_memory() - address)
            reject(op, "outside_sandbox");
#if INTERSPEC_CHECKS
        interspec::DiagnosticEvent sp3_event(this, op);
        sp3_event.requested = bytes;
        auto result = runtime->check(address, bytes, is_input ? P::kTypeHashChar : P::kTypeHashBipbufT);
        sp3_event.result = result == interspec::CheckResult::ok ? "sp3_ok" : interspec::check_result_name(result);
        if (result != interspec::CheckResult::ok) {
            runtime->dump_allocations();
            reject(op, interspec::check_result_name(result));
        }
#else
        (void)is_input;
#endif
        if (bytes > capacity) reject(op, "staging_capacity");
        return ptr;
    }

    unsigned char *snapshot(Pointer pointer, uint32_t bytes, const char *op) {
        if (!pointer.UNSAFE_unverified()) return nullptr;
        auto *ptr = validate(pointer, bytes, op);
        std::memcpy(read_copy.data(), ptr, bytes);
        event(op, "copied", bytes);
        event("copy_from_u", op, bytes);
        return read_copy.data();
    }
    void event(const char *op, const char *result, uint32_t bytes) {
        interspec::DiagnosticEvent event(this, op);
        event.requested = bytes;
        event.result = result;
    }
};

Buffer &get(const bipbuf_t *ptr) {
    if (!ptr) reject("handle", "null_handle");
    return *reinterpret_cast<Buffer *>(const_cast<bipbuf_t *>(ptr));
}
template <class F> auto guarded(F fn) -> decltype(fn()) {
    try { return fn(); }
    catch (const std::exception &e) { reject("bridge", e.what()); }
    catch (...) { reject("bridge", "unknown_exception"); }
}
}

extern "C" {
bipbuf_t *bipbuf_new(unsigned int size) {
    if (!size || size > (UINT32_MAX - 4096u) / 3u || size > INT_MAX) return nullptr;
    try { return reinterpret_cast<bipbuf_t *>(new Buffer(size)); }
    catch (const std::bad_alloc &) { return nullptr; }
    catch (const std::exception &e) { reject("new", e.what()); }
}

/* role: 1=worker logger, 2=watcher output, 3=LRU bump queue. Configuration is T,
 * and the mutations themselves execute in compiled U source. */
void interspec_bipbuf_role(bipbuf_t *ptr, unsigned int role) {
    guarded([&] {
        auto &b = get(ptr);
        std::lock_guard<std::mutex> lock(b.mutex);
#ifdef INTERSPEC_FAULT_TESTS
        auto value = [](const char *key, uint32_t fallback) {
            const char *s = std::getenv(key);
            return s ? static_cast<uint32_t>(std::strtoul(s, nullptr, 10)) : fallback;
        };
        if (role == value("INTERSPEC_TEST_ROLE", 1))
            MC_CALL(b, interspec_mc_fault,
                value("INTERSPEC_TEST_FAULT", 0), value("INTERSPEC_TEST_TARGET", 2));
#else
        (void)role;
#endif
        b.event("buffer_role", role == 1 ? "worker" : role == 2 ? "watcher" : "lru", b.capacity);
    });
}

/* LRU entries originally carry native item pointers through bipbuffer. U gets
 * only one-use integer handles; T retains the item reference and its lock hash.
 * Upstream's refcount_incr keeps the item alive until the handle is consumed or
 * cancelled. A token is meaningful only within its originating queue. */
uintptr_t interspec_lru_hold(bipbuf_t *ptr, void *item, uint32_t hash) {
    return guarded([&] {
        auto &b = get(ptr);
        std::lock_guard<std::mutex> lock(b.mutex);
        if (!b.next_reference) reject("lru_hold", "handle_exhaustion");
        uintptr_t token = b.next_reference++;
        b.item_references.emplace(token, Buffer::ItemReference{item, hash});
        b.event("lru_hold", "ok", 1);
        return token;
    });
}
void interspec_lru_cancel(bipbuf_t *ptr, uintptr_t token) {
    guarded([&] {
        auto &b = get(ptr);
        std::lock_guard<std::mutex> lock(b.mutex);
        if (b.item_references.erase(token) != 1) reject("lru_cancel", "unknown_handle");
    });
}
void *interspec_lru_take(bipbuf_t *ptr, uintptr_t token, uint32_t hash) {
    return guarded([&]() -> void * {
        auto &b = get(ptr);
        std::lock_guard<std::mutex> lock(b.mutex);
        auto found = b.item_references.find(token);
        if (found == b.item_references.end()) reject("lru_take", "unknown_handle");
        if (found->second.hash != hash) reject("lru_take", "wrong_item_hash");
        void *item = found->second.item;
        b.item_references.erase(found);
        b.event("lru_take", "ok", 1);
        return item;
    });
}
void interspec_lru_extent(unsigned int bytes, unsigned int entry_size) {
    if (!bytes || !entry_size || bytes % entry_size) reject("lru_extent", "malformed_record");
}
void bipbuf_free(bipbuf_t *ptr) {
    if (!ptr) return;
    guarded([&] {
        auto &b = get(ptr);
        { std::lock_guard<std::mutex> lock(b.mutex);
          MC_CALL(b, interspec_mc_free); }
        delete &b;
    });
}
unsigned char *bipbuf_request(bipbuf_t *ptr, int size) {
    return guarded([&]() -> unsigned char * {
        auto &b = get(ptr);
        std::lock_guard<std::mutex> lock(b.mutex);
        b.pending = 0;
        if (size < 0 || static_cast<uint32_t>(size) > b.capacity) return nullptr;
        auto result = MC_CALL(b, interspec_mc_request, static_cast<uint32_t>(size));
        if (!result.UNSAFE_unverified()) return nullptr;
        b.validate(result, size, "request");
        b.pending = size;
        return b.write_copy.data();
    });
}
int bipbuf_push(bipbuf_t *ptr, int size) {
    return guarded([&] {
        auto &b = get(ptr);
        std::lock_guard<std::mutex> lock(b.mutex);
        if (size < 0 || static_cast<uint32_t>(size) > b.pending) reject("push", "unreserved_write");
        auto result = MC_CALL(b, interspec_mc_request, static_cast<uint32_t>(size));
        auto *destination = b.validate(result, size, "push");
        std::memcpy(destination, b.write_copy.data(), size);
        b.event("copy_into_u", "push", size);
        b.pending = 0;
        int written = MC_CALL(b, interspec_mc_push, static_cast<uint32_t>(size)).UNSAFE_unverified();
        if (written != 0 && written != size) reject("push", "invalid_count");
        return written;
    });
}
int bipbuf_offer(bipbuf_t *ptr, const unsigned char *data, int size) {
    return guarded([&] {
        auto &b = get(ptr);
        std::lock_guard<std::mutex> lock(b.mutex);
        b.pending = 0;
        if (size < 0 || static_cast<uint32_t>(size) > b.capacity) return 0;
        std::memcpy(b.validate(b.input, size, "offer_input", true), data, size);
        b.event("copy_into_u", "offer", size);
        int written = MC_CALL(b, interspec_mc_offer, static_cast<uint32_t>(size)).UNSAFE_unverified();
        if (written != 0 && written != size) reject("offer", "invalid_count");
        return written;
    });
}
unsigned char *bipbuf_peek_all(const bipbuf_t *ptr, unsigned int *size) {
    return guarded([&]() -> unsigned char * {
        auto &b = get(ptr);
        std::lock_guard<std::mutex> lock(b.mutex);
        auto result = MC_CALL(b, interspec_mc_peek_all);
        *size = MC_CALL(b, interspec_mc_last_size).UNSAFE_unverified();
        if (!result.UNSAFE_unverified()) { *size = 0; return nullptr; }
        return b.snapshot(result, *size, "peek_all");
    });
}
unsigned char *bipbuf_peek(const bipbuf_t *ptr, unsigned int size) {
    return guarded([&] {
        auto &b = get(ptr);
        std::lock_guard<std::mutex> lock(b.mutex);
        return b.snapshot(MC_CALL(b, interspec_mc_peek, size), size, "peek");
    });
}
unsigned char *bipbuf_poll(bipbuf_t *ptr, unsigned int size) {
    return guarded([&] {
        auto &b = get(ptr);
        std::lock_guard<std::mutex> lock(b.mutex);
        return b.snapshot(MC_CALL(b, interspec_mc_poll, size), size, "poll");
    });
}
void bipbuf_init(bipbuf_t *ptr, unsigned int size) {
    guarded([&] {
        auto &b = get(ptr);
        std::lock_guard<std::mutex> lock(b.mutex);
        if (size != b.capacity) reject("init", "capacity_change");
        b.pending = 0;
        MC_CALL(b, interspec_mc_reset, size);
    });
}
int bipbuf_size(const bipbuf_t *ptr) { return get(ptr).capacity; }
#define COUNT_WRAPPER(name, fn, max) \
int name(const bipbuf_t *ptr) { return guarded([&] { \
    auto &b = get(ptr); std::lock_guard<std::mutex> lock(b.mutex); \
    int value = MC_CALL(b, fn).UNSAFE_unverified(); \
    if (value < 0 || static_cast<uint32_t>(value) > (max)) reject(#name, "invalid_count"); \
    return value; }); }
COUNT_WRAPPER(bipbuf_used, interspec_mc_used, b.capacity)
COUNT_WRAPPER(bipbuf_unused, interspec_mc_unused, b.capacity)
COUNT_WRAPPER(bipbuf_is_empty, interspec_mc_empty, 1u)
#undef COUNT_WRAPPER

#ifdef INTERSPEC_BOUNDARY_BENCH
/* These exports exist only in the separate microbenchmark binary. Production
 * Buffer, RLBox backend, confinement and copy buffers are used unchanged. */
uint64_t interspec_bench_primitive(bipbuf_t *ptr, unsigned metric,
                                  unsigned bytes, unsigned iterations,
                                  uint64_t *checksum) {
    auto &b = get(ptr);
    if (!iterations || bytes > b.capacity) reject("bench", "invalid_parameters");
    auto *input = b.validate(b.input, bytes, "bench_input", true);
    for (unsigned i = 0; i < bytes; ++i) b.write_copy[i] = static_cast<unsigned char>(i * 13 + 7);
    std::memcpy(input, b.write_copy.data(), bytes);
    uint64_t sum = 0;
    auto begin = std::chrono::steady_clock::now();
    switch (metric) {
    case 0:
        for (unsigned i = 0; i < iterations; ++i) {
            auto value = MC_CALL(b, interspec_mc_bench_noop, i).UNSAFE_unverified();
            asm volatile("" : : "r"(value) : "memory");
            sum += value;
        }
        break;
    case 1:
        for (unsigned i = 0; i < iterations; ++i) {
            std::lock_guard<std::mutex> lock(b.mutex);
            asm volatile("" : : "r"(&b) : "memory");
        }
        break;
    case 2:
        for (unsigned i = 0; i < iterations; ++i) {
            uint32_t address = b.sandbox.get_sandbox_impl()->sandbox_address(input);
            bool valid = b.sandbox.is_pointer_in_sandbox_memory(input) &&
                         bytes <= b.sandbox.get_total_memory() - address;
            asm volatile("" : : "r"(valid) : "memory");
            sum += valid;
        }
        break;
    case 3:
        for (unsigned i = 0; i < iterations; ++i) {
            std::memcpy(input, b.write_copy.data(), bytes);
            asm volatile("" : : "r"(input) : "memory");
        }
        break;
    case 4:
        for (unsigned i = 0; i < iterations; ++i) {
            std::memcpy(b.read_copy.data(), input, bytes);
            asm volatile("" : : "r"(b.read_copy.data()) : "memory");
        }
        break;
    default: reject("bench", "unknown_metric");
    }
    auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - begin).count();
    if (metric == 0 && sum != uint64_t(iterations) * (iterations + 1) / 2)
        reject("bench", "call_checksum");
    if (metric == 2 && sum != iterations) reject("bench", "confinement_checksum");
    if (metric == 3 && std::memcmp(input, b.write_copy.data(), bytes)) reject("bench", "copy_into_u");
    if (metric == 4 && std::memcmp(b.read_copy.data(), b.write_copy.data(), bytes)) reject("bench", "copy_from_u");
    *checksum = sum;
    return elapsed;
}
#endif
}
