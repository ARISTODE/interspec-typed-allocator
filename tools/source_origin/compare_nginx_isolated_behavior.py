#!/usr/bin/env python3
"""Compare actual native Nginx/PCRE8 and isolated Nginx/PCRE8 semantics.

Only original, pinned Nginx application behavior is evaluated. These are
black-box outputs, not pointer-origin observations. Differences are recorded,
not suppressed by checking only for a nonzero exit status.

An experimental audit completing successfully does not mean semantic parity:
read the "native_isolated_parity" field of the resulting JSON.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nginx_common import Server, request

VARIANTS = ("native", "rlbox-only", "tracked-no-check", "interspec")
VALID = (
    ("valid-captures", r"^/items/([0-9]+)/([a-z]+)$"),
    ("valid-char-class", r"^/items/[a-z]+$"),
)
INVALID = (
    ("invalid-class", "["),
    ("invalid-group", "("),
    ("invalid-option", "(?z)"),
)
HTTP_CASES = (
    "/items/123/alpha",
    "/items/0/z",
    "/CASE/AbC",
    "/optional/b",
    "/optional/ab",
    "/rewrite/hello",
    "/map/hello",
    "/not-found",
    "/items/no/alpha",
)


def error_detail(stderr):
    """Extract PCRE error reason, original pattern and reported error location.

    Pinned upstream ngx_regex.c formats the error offset as an optional
    at "<remaining pattern>" suffix. Keep that suffix in parity comparisons:
    comparing only the reason would miss an observable offset regression.
    """
    import re
    for line in stderr.splitlines():
        marker = "pcre_compile() failed:"
        if marker not in line:
            continue
        match = re.search(
            r'pcre_compile\(\) failed: (.*?) in "([^"]*)"(?: at "([^"]*)")?',
            line,
        )
        if not match:
            return {"unparsed_error_line": line}
        return {
            "reason": match.group(1),
            "pattern": match.group(2),
            "at_offset_suffix": match.group(3),
        }
    return None


def compile_config(binary, conf, prefix):
    prefix.mkdir(parents=True, exist_ok=True)
    (prefix / "logs").mkdir(exist_ok=True)
    env = dict(os.environ, LC_ALL="C")
    env.pop("INTERSPEC_TRACE", None)
    env.pop("INTERSPEC_POINTER_CENSUS", None)
    process = subprocess.run(
        [str(binary), "-t", "-p", str(prefix.resolve()) + "/",
         "-c", str(conf.resolve())],
        text=True, capture_output=True, timeout=30, env=env,
    )
    return {
        "exit_code": process.returncode,
        "stderr": process.stderr,
        "stdout": process.stdout,
        "compiler_error": error_detail(process.stderr),
    }


def run(work, output):
    output.mkdir(parents=True, exist_ok=True)
    binaries = {v: work / "bin" / ("nginx-" + v) for v in VARIANTS}
    missing = [str(path) for path in binaries.values() if not path.is_file()]
    if missing:
        raise RuntimeError(f"missing built Nginx variants: {missing}")
    sha256 = {v: hashlib.sha256(path.read_bytes()).hexdigest()
              for v, path in binaries.items()}

    # The runtime cases drive the genuine Nginx application, not a wrapper
    # test function manufactured to create stack/global pointer call sites.
    runtime = {}
    for variant in VARIANTS:
        with Server(binaries[variant], output / "runtime" / variant) as server:
            runtime[variant] = [
                {"path": path, "status": status, "body": body}
                for path in HTTP_CASES
                for status, body in (request(server.port, path),)
            ]
    reference = runtime["native"]
    if not all(x["status"] in (200, 404) for x in reference):
        raise RuntimeError("native HTTP reference did not serve expected routes")
    runtime_equal = {v: value == reference for v, value in runtime.items()}

    config_cases = []
    for name, pattern, valid in (
        *((name, pattern, True) for name, pattern in VALID),
        *((name, pattern, False) for name, pattern in INVALID),
    ):
        # Use one original Nginx configuration file for every binary to avoid
        # manufacturing a path-dependent diagnostic difference.
        conf_dir = output / "configs" / name
        conf_dir.mkdir(parents=True, exist_ok=True)
        conf = conf_dir / "nginx.conf"
        conf.write_text(
            'error_log stderr notice;\n'
            'events { worker_connections 64; }\n'
            'http { server { listen 127.0.0.1:18080; '
            'location ~ "' + pattern + '" { return 204; } } }\n'
        )
        observations = {
            variant: compile_config(
                binary, conf, output / "prefixes" / name / variant
            )
            for variant, binary in binaries.items()
        }
        native = observations["native"]
        if (native["exit_code"] == 0) != valid:
            raise RuntimeError(f"unexpected native PCRE8 reference: {name}: {native}")
        if not valid and native["compiler_error"] is None:
            raise RuntimeError(f"native did not expose a PCRE compiler error: {name}")
        parity = {}
        for variant, result in observations.items():
            parity[variant] = (
                (result["exit_code"] == 0) == (native["exit_code"] == 0)
                and result["compiler_error"] == native["compiler_error"]
            )
        config_cases.append({
            "name": name,
            "regex": pattern,
            "valid": valid,
            "native_to_variant_parity": parity,
            "observations": observations,
        })

    strict = all(runtime_equal.values()) and all(
        all(case["native_to_variant_parity"].values()) for case in config_cases
    )
    divergence = [
        {"case": case["name"], "variant": variant,
         "native_error": case["observations"]["native"]["compiler_error"],
         "variant_error": case["observations"][variant]["compiler_error"]}
        for case in config_cases
        for variant in VARIANTS if not case["native_to_variant_parity"][variant]
    ]
    report = {
        "schema": 1,
        "scope": "pinned upstream Nginx/PCRE8 semantics with deployed RLBox wasm2c bridge",
        "not_a_pointer_count": True,
        "original_application_version": "nginx 1be0fb0c9f9bc3489c7b40576efd6afe6b2eccd5",
        "original_pcre_version": "pcre8 e67dabe61b327bd2d888954b0e74a7c9cfd0a195",
        "native_isolated_parity": "pass" if strict else "mismatch",
        "runtime_http_parity": runtime_equal,
        "runtime_http": runtime,
        "config_compile_cases": config_cases,
        "compiler_diagnostic_mismatches": divergence,
        "limits": [
            "This checks measured HTTP responses and Nginx config compiler errors, not all behavior.",
            "This compares the Nginx-rendered error-offset suffix; it does not inspect the raw PCRE error-offset integer.",
            "No pointer-origin call sites are attributed to this test driver.",
        ],
        "binary_sha256": sha256,
    }
    (output / "native-versus-isolated.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({
        "native_isolated_parity": report["native_isolated_parity"],
        "runtime_http_parity": runtime_equal,
        "compile_cases": len(config_cases),
        "compiler_diagnostic_mismatches": divergence,
    }, sort_keys=True))
    if divergence:
        print("::warning::Native versus isolated Nginx error semantics differ. "
              "See native-versus-isolated.json for actual outputs.")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path,
                        default=Path("/tmp/interspec-nginx-deployment"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--require-parity", action="store_true",
                        help="fail the CI job if any native versus isolated output differs")
    args = parser.parse_args()
    report = run(args.work, args.out)
    if args.require_parity and report["native_isolated_parity"] != "pass":
        raise SystemExit("native versus isolated Nginx semantic parity failed")


if __name__ == "__main__":
    main()
