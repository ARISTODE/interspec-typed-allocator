#define RLBOX_USE_EXCEPTIONS
#define RLBOX_SINGLE_THREADED_INVOCATIONS
#define RLBOX_USE_STATIC_CALLS() rlbox_wasm2c_sandbox_lookup_symbol
#define RLBOX_WASM2C_MODULE_NAME glue__lib__wasm2c
#include "glue_lib_wasm2c.h"
#include "rlbox.hpp"
#include "rlbox_wasm2c_sandbox.hpp"
#include "interspec/runtime.h"
#include "pcre.h"
#if INTERSPEC_TRACKING
#include "interspec_pcre_t_policy.h"
#endif
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <vector>

extern "C" {
unsigned char *interspec_nginx_setup(void);
int interspec_nginx_compile(int);
int interspec_nginx_info(int);
int interspec_nginx_study(void);
unsigned char *interspec_nginx_names(void);
uint32_t interspec_nginx_names_bytes(void);
int interspec_nginx_exec(int, int, int, int);
unsigned char *interspec_nginx_offsets(void);
uint32_t interspec_nginx_offsets_bytes(void);
#ifdef INTERSPEC_FAULT_TESTS
void interspec_nginx_fault(uint32_t, uint32_t);
#endif
}

namespace {
using Backend = rlbox::rlbox_wasm2c_sandbox;
using Sandbox = rlbox::rlbox_sandbox<Backend>;
using Pointer = rlbox::tainted<unsigned char *, Backend>;
#if INTERSPEC_TRACKING
namespace P = interspec::nginx_server_generated;
#endif
constexpr uint32_t InputCapacity = 65536, OffsetCapacity = 4096;
static_assert(sizeof(int) == 4, "nginx PCRE Wasm capture ABI requires 32-bit int");
enum class Use { input, names, offsets };
[[noreturn]] void reject(const char *operation, const char *reason) {
    std::fprintf(stderr, "INTERSPEC_REJECT boundary=nginx_pcre operation=%s reason=%s\n", operation, reason);
    std::fflush(stderr);
    std::abort();
}

/* Nginx's event loop is single threaded. Each expression owns an independent
 * sandbox, copied by fork and destroyed by its configuration pool cleanup.
 * This deployment does not support concurrent third-party threaded regex use. */
struct Regex {
    Sandbox sandbox;
    Pointer input;
    int captures = 0, named = 0, entry = 0;
    std::vector<unsigned char> names;
    std::vector<int> offsets;
#if INTERSPEC_TRACKING
    std::unique_ptr<interspec::Runtime> runtime;
#endif
    Regex() {
        if (!sandbox.create_sandbox()) throw std::runtime_error("sandbox_creation");
        try {
#if INTERSPEC_TRACKING
            constexpr uint32_t arena_size = 1024 * 1024;
            uint32_t base = sandbox.get_sandbox_impl()->reserve_typed_arena(arena_size);
            if (!base) throw std::bad_alloc();
            runtime = std::make_unique<interspec::Runtime>(base, arena_size);
            if (!P::register_types(*runtime) || !P::register_wasm_allocation_policy(*runtime))
                throw std::runtime_error("policy_registration");
            sandbox.get_sandbox_impl()->set_interspec_runtime(this,
                [](void *ctx, uint32_t site, uint32_t size) -> uint32_t {
                    return static_cast<Regex *>(ctx)->runtime->allocate_from_site(size, site);
                },
                [](void *ctx, uint32_t ptr) -> uint32_t {
                    return static_cast<Regex *>(ctx)->runtime->release(ptr);
                },
                [](void *ctx, uint32_t ptr) -> uint32_t {
                    size_t bytes = 0;
                    static_cast<Regex *>(ctx)->runtime->allocation_size(ptr, bytes);
                    return static_cast<uint32_t>(bytes);
                },
                [](void *ctx, uint32_t ptr, uint32_t bytes) -> uint32_t {
                    return static_cast<Regex *>(ctx)->runtime->reallocate(ptr, bytes);
                });
#endif
            input = sandbox.invoke_sandbox_function(interspec_nginx_setup);
            validate(input, InputCapacity, Use::input);
#ifdef INTERSPEC_FAULT_TESTS
            const char *path = std::getenv("INTERSPEC_NGINX_FAULT_PATH");
            const char *kind = std::getenv("INTERSPEC_NGINX_FAULT_KIND");
            if (path && kind) sandbox.invoke_sandbox_function(interspec_nginx_fault,
                    static_cast<uint32_t>(std::atoi(path)), static_cast<uint32_t>(std::atoi(kind)));
#endif
        } catch (...) {
            sandbox.destroy_sandbox();
            throw;
        }
    }
    ~Regex() { sandbox.destroy_sandbox(); }

    unsigned char *validate(Pointer pointer, uint32_t bytes, Use use) {
        const char *operation = use == Use::names ? "name_table" : use == Use::offsets ? "capture_offsets" : "input";
        unsigned char *ptr = pointer.UNSAFE_unverified();
        if (!ptr) reject(operation, "null_pointer");
        const uint32_t address = sandbox.get_sandbox_impl()->sandbox_address(ptr);
        const uint64_t total = sandbox.get_total_memory();
        if (!sandbox.is_pointer_in_sandbox_memory(ptr) || address > total || bytes > total - address)
            reject(operation, "outside_sandbox");
#if INTERSPEC_CHECKS
        const auto policy = use == Use::names ? P::kUsePcreNameTableRange :
                            use == Use::offsets ? P::kUseCaptureOffsets : P::kUseSubjectInput;
        const auto result = P::check(*runtime, address, bytes, policy);
        if (result != interspec::CheckResult::ok) reject(operation, interspec::check_result_name(result));
#endif
        return ptr;
    }
    void copy_input(const char *subject, uint32_t bytes) {
        if (bytes > InputCapacity) throw std::runtime_error("subject_capacity");
        std::memcpy(validate(input, bytes, Use::input), subject, bytes);
    }
    bool compile(const char *pattern, int options) {
        const size_t size = std::strlen(pattern) + 1;
        if (size > InputCapacity) return false;
        copy_input(pattern, static_cast<uint32_t>(size));
        if (!sandbox.invoke_sandbox_function(interspec_nginx_compile, options).UNSAFE_unverified()) return false;
        captures = sandbox.invoke_sandbox_function(interspec_nginx_info, PCRE_INFO_CAPTURECOUNT).UNSAFE_unverified();
        named = sandbox.invoke_sandbox_function(interspec_nginx_info, PCRE_INFO_NAMECOUNT).UNSAFE_unverified();
        entry = sandbox.invoke_sandbox_function(interspec_nginx_info, PCRE_INFO_NAMEENTRYSIZE).UNSAFE_unverified();
        if (captures < 0 || captures > 1364 || named < 0 || named > captures ||
            (named && (entry < 3 || entry > 256))) reject("name_table", "malformed_metadata");
        if (named) {
            auto ptr = sandbox.invoke_sandbox_function(interspec_nginx_names);
            uint32_t bytes = sandbox.invoke_sandbox_function(interspec_nginx_names_bytes).UNSAFE_unverified();
            auto *raw = validate(ptr, bytes, Use::names);
            if (bytes != static_cast<uint32_t>(named * entry)) reject("name_table", "malformed_extent");
            names.assign(raw, raw + bytes);
            for (int i = 0; i < named; ++i) {
                const unsigned char *p = names.data() + i * entry;
                unsigned index = (static_cast<unsigned>(p[0]) << 8) | p[1];
                if (!index || index > static_cast<unsigned>(captures) ||
                    !std::memchr(p + 2, 0, entry - 2)) reject("name_table", "malformed_record");
            }
        }
        return true;
    }
    int exec(const char *subject, int length, int start, int options, int *target, int count) {
        if (length < 0 || length > static_cast<int>(InputCapacity) || start < 0 || start > length ||
            count < 0 || count > static_cast<int>(OffsetCapacity) || (count && !target)) return PCRE_ERROR_BADLENGTH;
        copy_input(subject, static_cast<uint32_t>(length));
        int rc = sandbox.invoke_sandbox_function(interspec_nginx_exec, length, start, options, count).UNSAFE_unverified();
        if (rc < 0) return rc;
        if (rc > count / 3 || rc > captures + 1) reject("capture_offsets", "malformed_count");
        if (!count) return rc;
        auto pointer = sandbox.invoke_sandbox_function(interspec_nginx_offsets);
        uint32_t bytes = sandbox.invoke_sandbox_function(interspec_nginx_offsets_bytes).UNSAFE_unverified();
        auto *raw = validate(pointer, bytes, Use::offsets);
        if (bytes != static_cast<uint32_t>(count) * sizeof(int)) reject("capture_offsets", "malformed_extent");
        offsets.resize(count);
        std::memcpy(offsets.data(), raw, bytes);
        int pairs = rc ? rc : count / 3;
        for (int i = 0; i < pairs; ++i) {
            int begin = offsets[2 * i], end = offsets[2 * i + 1];
            if (begin == -1 && end == -1) continue;
            if (begin < 0 || end < begin || end > length) reject("capture_offsets", "malformed_offsets");
        }
        std::memcpy(target, offsets.data(), bytes);
        return rc;
    }
};
Regex *unwrap(const pcre *code) { return reinterpret_cast<Regex *>(const_cast<pcre *>(code)); }
}

/* ABI shim for the PCRE8 functions used by pinned nginx. Native callbacks are
 * retained only as nginx ABI globals and are never installed inside U. */
extern "C" {
void *(*pcre_malloc)(size_t) = std::malloc;
void (*pcre_free)(void *) = std::free;
pcre *pcre_compile(const char *pattern, int options, const char **error, int *offset, const unsigned char *tables) {
    if (error) *error = "sandbox PCRE compilation failed";
    if (offset) *offset = 0;
    if (!pattern || tables) return nullptr;
    try {
        auto regex = std::make_unique<Regex>();
        if (!regex->compile(pattern, options)) return nullptr;
        if (error) *error = nullptr;
        return reinterpret_cast<pcre *>(regex.release());
    } catch (const std::exception &e) {
        std::fprintf(stderr, "INTERSPEC_ERROR boundary=nginx_pcre reason=%s\n", e.what());
        return nullptr;
    }
}
void interspec_nginx_release(void *code) { delete reinterpret_cast<Regex *>(code); }
int pcre_fullinfo(const pcre *code, const pcre_extra *, int what, void *result) {
    if (!code || !result) return PCRE_ERROR_NULL;
    auto *re = unwrap(code);
    switch (what) {
        case PCRE_INFO_CAPTURECOUNT: *static_cast<int *>(result) = re->captures; break;
        case PCRE_INFO_NAMECOUNT: *static_cast<int *>(result) = re->named; break;
        case PCRE_INFO_NAMEENTRYSIZE: *static_cast<int *>(result) = re->entry; break;
        case PCRE_INFO_NAMETABLE: *static_cast<unsigned char **>(result) = re->names.data(); break;
        case PCRE_INFO_JIT: *static_cast<int *>(result) = 0; break;
        default: return PCRE_ERROR_BADOPTION;
    }
    return 0;
}
pcre_extra *pcre_study(const pcre *code, int options, const char **error) {
    if (error) *error = nullptr;
    if (!code || options) { if (error) *error = "unsupported study option"; return nullptr; }
    try {
        if (!unwrap(code)->sandbox.invoke_sandbox_function(interspec_nginx_study).UNSAFE_unverified() && error)
            *error = "sandbox study failed";
    } catch (...) { reject("study", "sandbox_failure"); }
    return nullptr;
}
void pcre_free_study(pcre_extra *) {}
int pcre_exec(const pcre *code, const pcre_extra *, const char *subject, int length,
              int start, int options, int *offsets, int count) {
    if (!code || !subject) return PCRE_ERROR_NULL;
    try { return unwrap(code)->exec(subject, length, start, options, offsets, count); }
    catch (...) { reject("exec", "sandbox_failure"); }
}
int pcre_config(int what, void *out) {
    if (what != PCRE_CONFIG_JIT || !out) return PCRE_ERROR_BADOPTION;
    *static_cast<int *>(out) = 0;
    return 0;
}
const char *pcre_version(void) { return "8.45 RLBox wasm2c"; }
}
