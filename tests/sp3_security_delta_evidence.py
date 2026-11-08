#!/usr/bin/env python3
"""Synthetic raw evidence only; ensure the independent verifier fails closed."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from verify_sp3_security_delta import EvidenceError, verify
from patch_memcached_sanitizer_logger import UPSTREAM, SANITIZED, patch_source


def dump(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(root):
    entries = []
    scenarios = ("legitimate", "untracked", "revoked", "wrong_type", "same_type", "same_type_pinned")
    for scenario in scenarios:
        for policy in ("domain_sp3", "extended_sp3"):
            case = f"h2-yaml-{scenario}-{policy}"
            directory = root / "cases" / case
            directory.mkdir(parents=True)
            rejected = (policy == "extended_sp3" and scenario in
                        ("untracked", "revoked", "wrong_type", "same_type_pinned"))
            decision = "reject" if rejected else "accept"
            reason = "untracked" if rejected else "ok"
            scalar = "none" if rejected else "trusted" if scenario == "legitimate" else "altered"
            stdout = (f"SP3_T_DELTA boundary=yaml_read_handler scenario={scenario} "
                      f"policy={policy} decision={decision} reason={reason} "
                      f"scalar={scalar} source=project_authored_t\n")
            (directory / "server.stdout").write_text(stdout)
            (directory / "server.stderr").write_text("")
            execution = {"case": case, "status": "observed", "kind": "yaml_t_driver",
                         "binary_sha256": "a" * 64,
                         "exit_code_before_teardown": 86 if rejected else 0}
            dump(directory / "execution.json", execution)
            entries.append({"case": case, "status": "observed", "binary_sha256": "a" * 64,
                            "execution_sha256": sha(directory / "execution.json"),
                            "stdout_sha256": sha(directory / "server.stdout"),
                            "stderr_sha256": sha(directory / "server.stderr")})
    dump(root / "collection.json", {"schema": 1, "scope": "h2_yaml",
         "initial_correctness_gate_sha256": "b" * 64,
         "cases": entries, "post_case_gates": []})
    dump(root / "provenance.json", {"schema": 1,
         "initial_correctness_gate_sha256": "b" * 64})


def must_fail(fn):
    try:
        fn()
    except EvidenceError:
        return
    raise AssertionError("tampered or incomplete evidence was accepted")


def main():
    # Guard against silently dropping the source-specific sanitizer repair.
    assert patch_source("before\n" + UPSTREAM + "\nafter") == (
        "before\n" + SANITIZED + "\nafter")
    try:
        patch_source("no longer the pinned logger source")
    except ValueError:
        pass
    else:
        raise AssertionError("unmatched sanitizer source must fail closed")
    for header_size in (32, 40, 48):
        for payload_size in range(1, 1025):
            rem = (header_size + payload_size) % 8
            pad = 0 if rem == 0 else 8 - rem
            assert 0 <= pad < 8
            assert (header_size + payload_size + pad) % 8 == 0
    with tempfile.TemporaryDirectory(prefix="interspec-sp3-verifier-") as temp:
        root = Path(temp)
        fixture(root)
        result = verify(root, "h2_yaml")
        assert result["raw_executions"] == 12
        assert sum(x["verdict"] == "security_delta" for x in result["h2_yaml"]) == 4
        must_fail(lambda: verify(root, "h2_yaml", require_pointer_census=True))
        case = root / "cases/h2-yaml-wrong_type-domain_sp3/server.stdout"
        case.write_text(case.read_text().replace("altered", "trusted"))
        must_fail(lambda: verify(root, "h2_yaml"))
        fixture_dir = root / "cases/h2-yaml-wrong_type-domain_sp3"
        case.write_text("SP3_T_DELTA corrupted\n")
        items = json.loads((root / "collection.json").read_text())
        for item in items["cases"]:
            if item["case"] == "h2-yaml-wrong_type-domain_sp3":
                item["stdout_sha256"] = sha(case)
        dump(root / "collection.json", items)
        must_fail(lambda: verify(root, "h2_yaml"))
        case.unlink()
        must_fail(lambda: verify(root, "h2_yaml"))
    # A coherent, hash-updated recording of an unhealthy legitimate control
    # must fail the semantic validity gate, not merely the hash audit.
    with tempfile.TemporaryDirectory(prefix="interspec-sp3-invalid-control-") as temp:
        root = Path(temp)
        fixture(root)
        case = root / "cases/h2-yaml-legitimate-domain_sp3/server.stdout"
        case.write_text(case.read_text().replace("scalar=trusted", "scalar=altered"))
        items = json.loads((root / "collection.json").read_text())
        for item in items["cases"]:
            if item["case"] == "h2-yaml-legitimate-domain_sp3":
                item["stdout_sha256"] = sha(case)
        dump(root / "collection.json", items)
        must_fail(lambda: verify(root, "h2_yaml"))
    print("SP3 security-delta verifier tamper tests: pass")


if __name__ == "__main__":
    main()
