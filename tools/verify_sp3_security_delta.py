#!/usr/bin/env python3
"""Re-derive SP3 security-delta verdicts from raw, hash-pinned observations.

Predictions are never read as observations. Unexpected results remain in the
report with their original bytes, and are not silently retried or suppressed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


H1_MODES = [(1, 2, m) for m in (1, 2, 3, 4, 5, 6, 9, 10)] + [(3, 2, 7), (3, 2, 8)]
H2_VARIANTS = ("h2-upstream", "h2-domain", "h2-extended", "h2-handle")
H2_YAML = ("legitimate", "untracked", "revoked", "wrong_type", "same_type", "same_type_pinned")
H1_NGINX = [(p, k) for p in (1, 2) for k in (1, 2, 3, 4, 5)] + [
    (2, 6), (3, 1), (3, 2), (3, 3), (3, 4)
]
H1_RSYNC = [(t, m) for t in (1, 2, 3) for m in (1, 2, 3, 4, 5)] + [(6, 6)]
SANITIZER = re.compile(r"ERROR: AddressSanitizer|runtime error:|UndefinedBehaviorSanitizer|SUMMARY: AddressSanitizer")
INJECTION = re.compile(r"^FAULT_INJECTION .*\bmode=(\d+)\b.*\btarget=(\d+)\b", re.M)
COPY = re.compile(r"^INTERSPEC_T_COPY .*\boperation=(\S+) bytes=(\d+) fnv64=([0-9a-f]{16})$", re.M)
YAML_LINE = re.compile(r"^SP3_T_DELTA boundary=yaml_read_handler scenario=(\w+) "
                       r"policy=(\w+) decision=(\w+) reason=(\w+) scalar=(\w+) "
                       r"source=project_authored_t$", re.M)
YAML_BENCH = re.compile(r"^YAML_BENCH ([^\n]+)$", re.M)


class EvidenceError(ValueError):
    pass


def require(condition, message):
    if not condition: raise EvidenceError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data(path):
    return json.loads(path.read_text())


def event_reason(log):
    matches = re.findall(r"INTERSPEC_REJECT [^\n]*\breason=([^\s]+)", log)
    return matches[0] if matches else None


def digest_after_fault(log):
    injection = INJECTION.search(log)
    if not injection: return None
    copy = COPY.search(log, injection.end())
    return (copy[1], int(copy[2]), copy[3]) if copy else None


def read_verified(root, expected_case, entry):
    require(entry["case"] == expected_case, "mismatched evidence case " + expected_case)
    directory = root / "cases" / expected_case
    execution = directory / "execution.json"
    require(execution.is_file() and sha(execution) == entry["execution_sha256"],
            "missing or changed execution: " + expected_case)
    raw = data(execution)
    require(raw["case"] == expected_case and raw["status"] == entry["status"],
            "execution metadata mismatch: " + expected_case)
    require(raw["binary_sha256"] == entry["binary_sha256"],
            "binary digest mismatch: " + expected_case)
    if raw["kind"] in ("memcached", "nginx_h1"):
        protocol_file = directory / "protocol.json"
        require(protocol_file.is_file() and sha(protocol_file) == entry["protocol_sha256"],
                "missing or changed protocol: " + expected_case)
        protocol = data(protocol_file)
    else:
        protocol = {}
    filesystem = None
    if raw["kind"] == "rsync_h1":
        manifest = directory / "filesystem.json"
        require(manifest.is_file() and sha(manifest) == entry["filesystem_sha256"],
                "missing or changed rsync filesystem manifest: " + expected_case)
        filesystem = data(manifest)
        output = directory / "dst"
        actual = set()
        if output.exists():
            for file in output.rglob("*"):
                key = str(file.relative_to(output))
                actual.add(key)
                require(key in filesystem, "unmanifested rsync output: " + key)
                saved = filesystem[key]
                if file.is_symlink():
                    require(saved["kind"] == "symlink" and saved["target"] == file.readlink().as_posix(),
                            "changed rsync symlink: " + key)
                elif file.is_file():
                    require(saved["kind"] == "file" and saved["sha256"] == sha(file) and
                            saved["bytes"] == file.stat().st_size,
                            "changed rsync file: " + key)
                else:
                    require(saved["kind"] == "directory", "changed rsync directory: " + key)
        require(actual == set(filesystem), "missing rsync output paths")
    texts = {}
    for kind in ("stdout", "stderr"):
        filename = directory / f"server.{kind}"
        key = kind + "_sha256"
        require(filename.is_file() and key in entry and sha(filename) == entry[key],
                "missing or changed raw " + kind + ": " + expected_case)
        texts[kind] = filename.read_text(errors="replace")
    return {"entry": entry, "execution": raw, "protocol": protocol,
            "filesystem": filesystem,
            "stdout": texts["stdout"], "stderr": texts["stderr"],
            "sanitizer": bool(SANITIZER.search(texts["stderr"])),
            "reason": event_reason(texts["stderr"]),
            "copy": digest_after_fault(texts["stderr"])}


def classify_h1(role, target, mode, observations):
    prefix = f"h1-r{role}-t{target}-m{mode}"
    legit = observations[f"{prefix}-h1-rlbox-legitimate"]
    control = observations[f"{prefix}-h1-rlbox-content-control"]
    baseline = observations[f"{prefix}-h1-rlbox-fault"]
    extended = observations[f"{prefix}-h1-extended-fault"]
    recognized = all(o["execution"]["status"] == "observed"
                     for o in (legit, control, baseline, extended))
    marker = INJECTION.search(baseline["stderr"])
    control_marker = INJECTION.search(control["stderr"])
    ext_marker = INJECTION.search(extended["stderr"])
    recognized &= bool(marker and control_marker and ext_marker)
    if marker:
        recognized &= marker[1] == str(mode) and marker[2] == str(target)
    if control_marker:
        recognized &= control_marker[1] == str(mode + 100)
        recognized &= "control=1" in control["stderr"][control_marker.start():control_marker.end() + 40]
    if ext_marker: recognized &= ext_marker[1] == str(mode)

    # Equal staged bytes provide stronger evidence than relying on U's claim
    # that it supplied the same content. Bridge rejections before staging are
    # also attributable to the existing capacity/format validation when both
    # configurations report the identical non-SP3 reason.
    equal_content = bool(control["copy"] and baseline["copy"] and
                         control["copy"] == baseline["copy"])
    same_bridge_rejection = bool(control["reason"] and
                                 control["reason"] == baseline["reason"] and
                                 control["reason"] not in ("wrong_type", "untracked",
                                                            "out_of_bounds", "wrong_domain"))
    same_health = (control["execution"].get("alive_before_teardown") ==
                   baseline["execution"].get("alive_before_teardown"))
    # A passing 50-case suite for the normal (nonfault) build cannot make a
    # different instrumented fault-only binary's failed legitimate case valid.
    # Inspect that legitimate run independently before comparing the faults.
    legitimate_valid = (legit["execution"].get("alive_before_teardown") is True and
                        legit["protocol"].get("version") is True and
                        not legit["sanitizer"] and legit["reason"] is None and
                        (legit["protocol"].get("lru_bump") == "completed" if role == 3 else
                         legit["protocol"].get("watch_event_types") ==
                         ["deleted", "item_get", "item_store"]))
    # A matching copy digest is not sufficient by itself: the observable
    # memcached protocol must also agree with the matched-content control.
    # This is deliberately strict. If asynchronous watch records differ or
    # the comparator cannot serve, retain an inconclusive result for review.
    same_protocol = control["protocol"] == baseline["protocol"]
    no_sanitizer = not baseline["sanitizer"] and not control["sanitizer"]
    if not recognized or not legitimate_valid:
        verdict = "incomplete"
    elif baseline["sanitizer"]:
        verdict = "T_sanitizer_harm"
    elif no_sanitizer and same_health and same_protocol and (equal_content or same_bridge_rejection):
        verdict = "no_observed_delta"
    else:
        verdict = "inconclusive"
    prediction = "accepted" if mode == 5 else "bridge_validator" if mode in (6, 7, 8) else "sp3_reject"
    expected_reason = {1: "wrong_type", 2: "untracked", 3: "untracked", 4: "out_of_bounds",
                       7: "wrong_item_hash", 8: "malformed_record", 9: "untracked", 10: "untracked"}.get(mode)
    extended_reason = extended["reason"]
    expected_ok = (not extended["sanitizer"] and
                   (extended_reason == expected_reason if expected_reason else
                    extended_reason is None if mode == 5 else extended_reason is not None))
    # The H1 table separately predicts that the RLBox-only application keeps
    # serving for modes 1..5, 9, 10. Its T bridge may instead deliberately
    # abort on U-controlled malformed content. Record this prediction
    # deviation even if another content control triggers the same rejection:
    # matching aborts do not imply that the server remained available.
    predicted_keeps_serving = mode in (1, 2, 3, 4, 5, 9, 10)
    availability_prediction_matches = (
        baseline["execution"].get("alive_before_teardown") is True
        if predicted_keeps_serving else None)
    return {"case": prefix, "role": role, "target": target, "mode": mode,
            "verdict": verdict, "predicted_extended": prediction,
            "extended_reason": extended_reason, "prediction_matches": expected_ok,
            "rlbox_predicted_keeps_serving": predicted_keeps_serving,
            "rlbox_availability_prediction_matches": availability_prediction_matches,
            "equal_content_at_T_copy": equal_content,
            "same_protocol_as_content_control": same_protocol,
            "legitimate_valid": legitimate_valid,
            "same_non_sp3_bridge_rejection": same_bridge_rejection,
            "baseline_t_sanitizer": baseline["sanitizer"],
            "baseline_alive": baseline["execution"].get("alive_before_teardown"),
            "content_control_alive": control["execution"].get("alive_before_teardown")}


def classify_h1_yaml(mode, observations):
    prefix = f"h1-yaml-m{mode}"
    legitimate = observations[f"{prefix}-rlbox-legitimate"]
    baseline = observations[f"{prefix}-rlbox-fault"]
    extended = observations[f"{prefix}-typed-fault"]
    def signature(raw):
        found = YAML_BENCH.findall(raw["stdout"])
        if len(found) != 1: return None
        fields = dict(field.split("=", 1) for field in found[0].split() if "=" in field)
        return tuple(fields.get(k) for k in ("events", "scalars", "scalar_bytes", "hash"))
    baseline_ok = (baseline["execution"].get("exit_code_before_teardown") == 0 and
                   not baseline["sanitizer"] and signature(baseline) is not None)
    legitimate_valid = (legitimate["execution"].get("status") == "observed" and
                        legitimate["execution"].get("exit_code_before_teardown") == 0 and
                        not legitimate["sanitizer"] and signature(legitimate) is not None)
    same_content_outcome = baseline_ok and signature(baseline) == signature(legitimate)
    marker = re.search(r"FAULT_INJECTION boundary=yaml_libyaml mode=(\d+)", baseline["stderr"])
    ext_marker = re.search(r"FAULT_INJECTION boundary=yaml_libyaml mode=(\d+)", extended["stderr"])
    exercised = bool(marker and ext_marker and marker[1] == ext_marker[1] == str(mode))
    verdict = "incomplete" if not exercised or not legitimate_valid else "T_sanitizer_harm" if baseline["sanitizer"] else (
        "no_observed_delta" if same_content_outcome else "inconclusive")
    expected_reason = {1: "wrong_type", 2: "untracked", 3: "untracked", 4: "out_of_bounds"}.get(mode)
    return {"case": prefix, "mode": mode, "verdict": verdict,
            "legitimate_valid": legitimate_valid,
            "same_observable_YAML_content": same_content_outcome,
            "baseline_T_sanitizer": baseline["sanitizer"],
            "baseline_exit": baseline["execution"].get("exit_code_before_teardown"),
            "extended_reason": extended["reason"],
            "prediction_matches": extended["reason"] == expected_reason if expected_reason else
                                  extended["reason"] is None and
                                  extended["execution"].get("exit_code_before_teardown") == 0}


def classify_h1_nginx(path, kind, observations):
    prefix = f"h1-nginx-p{path}-k{kind}"
    legitimate = observations[f"{prefix}-rlbox-legitimate"]
    baseline = observations[f"{prefix}-rlbox-fault"]
    extended = observations[f"{prefix}-extended-fault"]
    marker = re.search(r"FAULT_INJECTION boundary=nginx_pcre path=(\d+) kind=(\d+)", baseline["stderr"])
    ext_marker = re.search(r"FAULT_INJECTION boundary=nginx_pcre path=(\d+) kind=(\d+)", extended["stderr"])
    exercised = bool(marker and ext_marker and int(marker[1]) == int(ext_marker[1]) == path and
                     int(marker[2]) == int(ext_marker[2]) == kind)
    # Two empty/missing HTTP responses must never be called equivalence.
    legitimate_route = legitimate["protocol"].get("route")
    same_http = (isinstance(legitimate_route, list) and
                 len(legitimate_route) == 2 and legitimate_route[0] == 200 and
                 baseline["protocol"].get("route") == legitimate_route and
                 baseline["execution"].get("alive_before_teardown") is True and
                 legitimate["execution"].get("alive_before_teardown") is True)
    same_config_result = (path == 3 and
                          isinstance(legitimate["execution"].get("exit_code_before_teardown"), int) and
                          legitimate["execution"].get("exit_code_before_teardown") != 0 and
                          baseline["execution"].get("exit_code_before_teardown") ==
                              legitimate["execution"].get("exit_code_before_teardown"))
    legitimate_valid = (legitimate["execution"].get("status") == "observed" and
                        not legitimate["sanitizer"] and
                        ((path == 3 and
                          legitimate["execution"].get("exit_code_before_teardown") == 1) or
                         (path != 3 and legitimate["execution"].get("alive_before_teardown") is True and
                          legitimate["protocol"].get("health") == [200, "ready"] and
                          isinstance(legitimate_route, list) and
                          legitimate_route == [200, "item:123:alpha"])))
    no_harm = not baseline["sanitizer"] and not legitimate["sanitizer"]
    bridge_reason = baseline["reason"] in ("malformed_extent", "malformed_offsets",
                                            "outside_sandbox", "malformed_termination",
                                            "malformed_text", "malformed_offset")
    verdict = "incomplete" if not exercised or not legitimate_valid else "T_sanitizer_harm" if baseline["sanitizer"] else (
        "no_observed_delta" if no_harm and (same_http or same_config_result) else
        "bridge_guarded" if no_harm and bridge_reason else "inconclusive")
    expected_reason = {1: "wrong_type", 2: "untracked", 3: "untracked",
                       4: "out_of_bounds", 6: "malformed_offsets"}.get(kind)
    return {"case": prefix, "path": path, "kind": kind,
            "legitimate_valid": legitimate_valid,
            "verdict": verdict, "fault_fired_in_both": exercised,
            "same_http_as_legitimate": same_http,
            "T_sanitizer": baseline["sanitizer"],
            "baseline_reason": baseline["reason"],
            "extended_reason": extended["reason"],
            "prediction_matches": (extended["reason"] == expected_reason)
                                  if expected_reason and path != 3 else True}


def classify_h1_rsync(target, mode, observations):
    prefix = f"h1-rsync-t{target}-m{mode}"
    legit = observations[f"{prefix}-rlbox-legitimate"]
    baseline = observations[f"{prefix}-rlbox-fault"]
    extended = observations[f"{prefix}-extended-fault"]
    if mode == 6:
        match = "FAULT_INJECTION mode=6 target=option_destination" in baseline["stderr"]
        ext_match = "FAULT_INJECTION mode=6 target=option_destination" in extended["stderr"]
    else:
        match = bool(re.search(rf"FAULT_INJECTION mode={mode} target={target}\b", baseline["stderr"]))
        ext_match = bool(re.search(rf"FAULT_INJECTION mode={mode} target={target}\b", extended["stderr"]))
    exercised = match and ext_match
    same_tree = baseline["filesystem"] == legit["filesystem"]
    same_stdout = baseline["stdout"] == legit["stdout"]
    clean = (legit["execution"].get("exit_code_before_teardown") == 0 and
             baseline["execution"].get("exit_code_before_teardown") == 0 and
             not baseline["sanitizer"] and not legit["sanitizer"])
    legitimate_valid = (legit["execution"].get("status") == "observed" and
                        legit["execution"].get("exit_code_before_teardown") == 0 and
                        not legit["sanitizer"])
    verdict = "incomplete" if not exercised or not legitimate_valid else "T_sanitizer_harm" if baseline["sanitizer"] else (
        "no_observed_delta" if clean and same_tree and same_stdout else
        "inconclusive")
    return {"case": prefix, "target": target, "mode": mode,
            "legitimate_valid": legitimate_valid,
            "verdict": verdict, "fault_fired_in_both": exercised,
            "baseline_T_sanitizer": baseline["sanitizer"],
            "baseline_exit": baseline["execution"].get("exit_code_before_teardown"),
            "same_output_tree": same_tree, "same_stdout": same_stdout,
            "extended_reason": extended["reason"]}


def classify_h2_memcached(mode, observations):
    rows = []
    healthy_controls = {}
    for variant in H2_VARIANTS:
        scenario = observations[f"h2-lru-m{mode}-{variant}"]
        legitimate = observations[f"h2-{variant}-legitimate"]
        healthy_controls[variant] = (
            legitimate["execution"].get("status") == "observed" and
            legitimate["execution"].get("alive_before_teardown") is True and
            legitimate["protocol"].get("lru_bump") == "completed" and
            legitimate["protocol"].get("version") is True and
            legitimate["reason"] is None and not legitimate["sanitizer"])
        delta_log = scenario["stderr"]
        accepted = bool(re.search(r"INTERSPEC_T_DELTA .*event=check policy=domain_sp3 result=ok", delta_log))
        rejected = bool(re.search(r"INTERSPEC_T_DELTA .*event=check policy=extended_sp3 "
                                  r"result=(untracked|out_of_bounds|wrong_type)", delta_log))
        changed = (scenario["sanitizer"] or
                   scenario["execution"].get("alive_before_teardown") !=
                       legitimate["execution"].get("alive_before_teardown") or
                   scenario["protocol"].get("lru_bump") != legitimate["protocol"].get("lru_bump"))
        marker = INJECTION.search(delta_log)
        rows.append({"case": f"h2-lru-m{mode}-{variant}", "variant": variant,
                     "mode": mode, "fault_fired": bool(marker and int(marker[1]) == mode),
                     "domain_accept": accepted, "extended_preuse_reject": rejected,
                     "T_outcome_differs_from_legitimate": changed,
                     "T_sanitizer": scenario["sanitizer"],
                     "raw_reason": scenario["reason"],
                     "alive": scenario["execution"].get("alive_before_teardown")})
    domain = next(x for x in rows if x["variant"] == "h2-domain")
    extended = next(x for x in rows if x["variant"] == "h2-extended")
    verdict = ("incomplete" if not all(healthy_controls.values()) else
               "security_delta" if domain["domain_accept"] and
               domain["T_outcome_differs_from_legitimate"] and
               extended["extended_preuse_reject"] else "inconclusive")
    return {"case": f"h2-lru-m{mode}", "mode": mode,
            "verdict": verdict, "variants": rows,
            "healthy_legitimate_controls": healthy_controls}


def classify_h2_yaml(scenario, observations):
    variants = {}
    for policy in ("domain_sp3", "extended_sp3"):
        raw = observations[f"h2-yaml-{scenario}-{policy}"]
        matches = YAML_LINE.findall(raw["stdout"])
        require(len(matches) == 1 or raw["execution"].get("exit_code_before_teardown") != 0,
                "clean YAML execution without an auditable outcome line")
        variants[policy] = {"parsed": len(matches) == 1,
                            "decision": matches[0][2] if len(matches) == 1 else None,
                            "reason": matches[0][3] if len(matches) == 1 else None,
                            "scalar": matches[0][4] if len(matches) == 1 else None,
                            "exit": raw["execution"].get("exit_code_before_teardown"),
                            "T_sanitizer": raw["sanitizer"]}
        if len(matches) == 1:
            require(matches[0][0] == scenario and matches[0][1] == policy,
                    "YAML stdout describes the wrong case")
    expected_rejection = scenario in ("untracked", "revoked", "wrong_type", "same_type_pinned")
    domain, extended = variants["domain_sp3"], variants["extended_sp3"]
    changed = domain["scalar"] == ("trusted" if scenario == "legitimate" else "altered")
    verdict = "security_delta" if expected_rejection and changed and (
        domain["decision"] == "accept" and domain["exit"] == 0 and
        extended["decision"] == "reject" and extended["exit"] == 86 and
        not domain["T_sanitizer"] and not extended["T_sanitizer"]) else (
        "negative_scope_control" if scenario == "same_type" and
        domain["decision"] == extended["decision"] == "accept" and
        domain["scalar"] == extended["scalar"] == "altered" and
        domain["exit"] == extended["exit"] == 0 and
        not domain["T_sanitizer"] and not extended["T_sanitizer"] else (
        "legitimate" if scenario == "legitimate" and
        domain["decision"] == extended["decision"] == "accept" else "inconclusive"))
    return {"case": f"h2-yaml-{scenario}", "scenario": scenario,
            "verdict": verdict, "variants": variants}


def markdown(summary):
    lines = ["# Extended SP3 security-delta results", "",
             "Generated only from independently verified raw execution logs. "
             "Fault and sanitizer binaries are excluded from performance analysis.", "",
             f"Evidence integrity: **{summary['evidence_integrity']}**. "
             f"Raw executions: **{summary['raw_executions']}**.", ""]
    if summary["h1"]:
        lines.extend(["## H1: U-domain comparisons", "",
                      "| Case | Verdict | Same bytes in T | T sanitizer | SP3 rejection |",
                      "| --- | --- | --- | --- | --- |"])
        for r in summary["h1"]:
            lines.append(f"| {r['case']} | {r['verdict']} | {r['equal_content_at_T_copy']} "
                         f"| {r['baseline_t_sanitizer']} | {r['extended_reason']} |")
        lines.append("")
        lines.extend(["The preregistered RLBox-only prediction that the process "
                      "would keep serving has explicit exceptions in this run:", ""])
        for r in summary["h1"]:
            if r["rlbox_availability_prediction_matches"] is False:
                lines.append(f"* {r['case']}: the fault-only process exited before teardown.")
        lines.append("")
    if summary["h1_yaml"]:
        lines.extend(["## H1: yaml/libyaml U-domain comparisons", "",
                      "| Mode | Verdict | Same T-visible YAML result | T sanitizer | Extended rejection |",
                      "| --- | --- | --- | --- | --- |"])
        for r in summary["h1_yaml"]:
            lines.append(f"| {r['mode']} | {r['verdict']} | {r['same_observable_YAML_content']} "
                         f"| {r['baseline_T_sanitizer']} | {r['extended_reason']} |")
        lines.append("")
    if summary["h1_nginx"]:
        lines.extend(["## H1: nginx/libpcre U-domain comparisons", "",
                      "| Path/kind | Verdict | T sanitizer | Extended rejection |",
                      "| --- | --- | --- | --- |"])
        for r in summary["h1_nginx"]:
            lines.append(f"| {r['path']}/{r['kind']} | {r['verdict']} "
                         f"| {r['T_sanitizer']} | {r['extended_reason']} |")
        lines.append("")
    if summary["h1_rsync"]:
        lines.extend(["## H1: rsync/popt U-domain comparisons", "",
                      "| Target/mode | Verdict | Same file outputs | T sanitizer |",
                      "| --- | --- | --- | --- |"])
        for r in summary["h1_rsync"]:
            lines.append(f"| {r['target']}/{r['mode']} | {r['verdict']} "
                         f"| {r['same_output_tree']} | {r['baseline_T_sanitizer']} |")
        lines.append("")
    if summary["h2_memcached"]:
        lines.extend(["## H2: memcached T-domain LRU pointers", "",
                      "| Fault | Verdict | Domain accepts | Domain T outcome changed | Extended rejects before use |",
                      "| --- | --- | --- | --- | --- |"])
        for r in summary["h2_memcached"]:
            d = next(v for v in r["variants"] if v["variant"] == "h2-domain")
            e = next(v for v in r["variants"] if v["variant"] == "h2-extended")
            lines.append(f"| {r['mode']} | {r['verdict']} | {d['domain_accept']} "
                         f"| {d['T_outcome_differs_from_legitimate']} | {e['extended_preuse_reject']} |")
        lines.append("")
    if summary["h2_yaml"]:
        lines.extend(["## H2: libyaml project-authored T driver", "",
                      "The real libyaml read-handler API and RLBox domain predicate are "
                      "used, but the simulated pointer mutation is project-authored T "
                      "code, not an upstream or wasm2c attack.", "",
                      "| Scenario | Verdict | Domain scalar | Extended decision |",
                      "| --- | --- | --- | --- |"])
        for r in summary["h2_yaml"]:
            d, e = r["variants"]["domain_sp3"], r["variants"]["extended_sp3"]
            lines.append(f"| {r['scenario']} | {r['verdict']} | {d['scalar']} | {e['decision']} |")
        lines.append("")
    lines.extend(["## Limits", "",
                  "The validator does not infer a missing trace is a successful attack. "
                  "Inconclusive cases require follow-up, preserving the original raw logs. "
                  "Address-only registration cannot prove temporal identity after address "
                  "reuse or original-object identity without a trusted expected base. "
                  "Same-type substitution without identity binding remains in scope limits.", ""])
    return "\n".join(lines)


def verify(root, expected_scope, require_post_gates=False,
           require_pointer_census=False):
    collection = data(root / "collection.json")
    provenance = data(root / "provenance.json")
    require(collection["schema"] == provenance["schema"] == 1, "unknown evidence schema")
    require(collection["scope"] == expected_scope, "evidence scope mismatch")
    require(collection["initial_correctness_gate_sha256"] ==
            provenance["initial_correctness_gate_sha256"], "correctness provenance mismatch")
    entries = {x["case"]: x for x in collection["cases"]}
    require(len(entries) == len(collection["cases"]), "duplicate case names")
    observed = {name: read_verified(root, name, entry) for name, entry in entries.items()}
    expected_names = set()
    h1, h1_yaml, h1_nginx, h1_rsync, h2_memcached, h2_yaml = [], [], [], [], [], []
    if expected_scope in ("all", "h1"):
        for role, target, mode in H1_MODES:
            case = f"h1-r{role}-t{target}-m{mode}"
            expected_names.update((f"{case}-h1-rlbox-legitimate",
                                   f"{case}-h1-rlbox-content-control",
                                   f"{case}-h1-rlbox-fault", f"{case}-h1-extended-fault"))
            if expected_names.issubset(observed):
                h1.append(classify_h1(role, target, mode, observed))
    if expected_scope in ("all", "h1_yaml"):
        for mode in (1, 2, 3, 4, 5):
            expected_names.update((f"h1-yaml-m{mode}-rlbox-legitimate",
                                   f"h1-yaml-m{mode}-rlbox-fault",
                                   f"h1-yaml-m{mode}-typed-fault"))
            if expected_names.issubset(observed):
                h1_yaml.append(classify_h1_yaml(mode, observed))
    if expected_scope in ("all", "h1_nginx"):
        for path, kind in H1_NGINX:
            prefix = f"h1-nginx-p{path}-k{kind}"
            expected_names.update((f"{prefix}-rlbox-legitimate",
                                   f"{prefix}-rlbox-fault", f"{prefix}-extended-fault"))
            if expected_names.issubset(observed):
                h1_nginx.append(classify_h1_nginx(path, kind, observed))
    if expected_scope in ("all", "h1_rsync"):
        for target, mode in H1_RSYNC:
            prefix = f"h1-rsync-t{target}-m{mode}"
            expected_names.update((f"{prefix}-rlbox-legitimate",
                                   f"{prefix}-rlbox-fault", f"{prefix}-extended-fault"))
            if expected_names.issubset(observed):
                h1_rsync.append(classify_h1_rsync(target, mode, observed))
    if expected_scope in ("all", "h2_memcached"):
        for variant in H2_VARIANTS: expected_names.add(f"h2-{variant}-legitimate")
        for mode in (11, 12):
            for variant in H2_VARIANTS: expected_names.add(f"h2-lru-m{mode}-{variant}")
            if expected_names.issubset(observed):
                h2_memcached.append(classify_h2_memcached(mode, observed))
    if expected_scope in ("all", "h2_yaml"):
        for scenario in H2_YAML:
            for policy in ("domain_sp3", "extended_sp3"):
                expected_names.add(f"h2-yaml-{scenario}-{policy}")
            if expected_names.issubset(observed):
                h2_yaml.append(classify_h2_yaml(scenario, observed))
    require(set(observed) == expected_names, "missing or extraneous raw cases: " +
            str(sorted(expected_names.symmetric_difference(observed))))
    require(all(x["execution"]["status"] == "observed" for x in observed.values()),
            "one or more executions are incomplete; raw logs retained")
    if require_pointer_census:
        require(all("INTERSPEC_POINTER_CENSUS schema=1" in x["stderr"]
                    for x in observed.values()),
                "pointer census missing in one or more raw executions")
    if h2_yaml:
        control = next(r for r in h2_yaml if r["scenario"] == "legitimate")
        require(all(v["decision"] == "accept" and v["scalar"] == "trusted" and
                    v["exit"] == 0 and not v["T_sanitizer"]
                    for v in control["variants"].values()),
                "invalid H2 libyaml legitimate T-context control")
    if require_post_gates:
        expected_gates = (len(H1_MODES) if expected_scope in ("all", "h1") else 0) + (
            2 if expected_scope in ("all", "h2_memcached") else 0)
        require(len(collection["post_case_gates"]) == expected_gates,
                "wrong number of post-case correctness gates")
        for gate in collection["post_case_gates"]:
            directory = root / "gates" / gate["case"]
            log = directory / "gate.log"
            result = directory / "correctness/summary.json"
            require(sha(log) == gate["gate_log_sha256"] and
                    sha(result) == gate["gate_summary_sha256"], "corrupted post-case gate")
            require(gate["exit_code"] == 0 and gate["passed"] == gate["total"] == 50,
                    "post-case correctness gate failed: " + gate["case"])
    return {"schema": 1, "evidence_integrity": "verified", "scope": expected_scope,
            "raw_executions": len(observed), "h1": h1, "h1_yaml": h1_yaml,
            "h1_nginx": h1_nginx, "h1_rsync": h1_rsync,
            "h2_memcached": h2_memcached, "h2_yaml": h2_yaml,
            "post_case_gates": len(collection["post_case_gates"]),
            "prediction_deviations": [x["case"] for x in h1 + h1_yaml + h1_nginx if not x["prediction_matches"]],
            "extended_rejection_prediction_deviations": [
                x["case"] for x in h1 + h1_yaml + h1_nginx if not x["prediction_matches"]],
            "rlbox_availability_prediction_deviations": [
                x["case"] for x in h1 if x["rlbox_availability_prediction_matches"] is False]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--scope", choices=("all", "h1", "h1_yaml", "h1_nginx", "h1_rsync", "h2_memcached", "h2_yaml"), default="all")
    parser.add_argument("--require-post-gates", action="store_true")
    parser.add_argument("--require-pointer-census", action="store_true",
                        help="require a structured census record from every raw execution")
    parser.add_argument("--fail-on-incomplete", action="store_true",
                        help="fail CI if a malformed/invalid legitimate control prevents classification")
    args = parser.parse_args()
    try:
        summary = verify(args.results, args.scope, args.require_post_gates,
                         args.require_pointer_census)
    except (EvidenceError, KeyError, ValueError, FileNotFoundError) as error:
        parser.exit(1, f"SP3_SECURITY_DELTA_EVIDENCE_INVALID: {error}\n")
    (args.results / "verified-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (args.results / "SP3_SECURITY_DELTA_RESULTS.md").write_text(markdown(summary))
    if args.fail_on_incomplete:
        unresolved = [r["case"] for key in ("h1", "h1_yaml", "h1_nginx", "h1_rsync", "h2_memcached")
                      for r in summary[key] if r["verdict"] == "incomplete"]
        if unresolved:
            parser.exit(2, "SP3_SECURITY_DELTA_INCOMPLETE_CONTROLS: " + ", ".join(unresolved) + "\n")
    print(f"Verified {summary['raw_executions']} immutable raw executions; "
          f"{len(summary['extended_rejection_prediction_deviations'])} Extended rejection-code "
          f"deviations; {len(summary['rlbox_availability_prediction_deviations'])} "
          "RLBox availability prediction deviations", flush=True)


if __name__ == "__main__":
    main()
