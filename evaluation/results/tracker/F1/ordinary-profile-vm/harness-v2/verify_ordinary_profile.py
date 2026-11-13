#!/usr/bin/env python3
"""Saved-evidence verification for the separate ordinary-only single profile."""
import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

SCHEMA="ordinary-only-memcached-profile-v2"
CHECKS=["lru_async_item_bumps","set_get_flags","add_replace","cas","append_prepend","incr_decr",
        "binary_256k","multiget","touch_delete","fragmented_request","invalid_commands","expiry",
        "flush_all","watch_log_content","concurrent_cache_2000_ops","watcher_churn_25"]

def valid_normal_stop(value): return type(value) is int and value in (0, -15)

def require(ok,message):
    if not ok: raise ValueError(message)

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load(path):
    def pairs(values):
        result={}
        for key,value in values:
            require(key not in result,"duplicate JSON key"); result[key]=value
        return result
    def invalid(value): raise ValueError("nonfinite JSON")
    return json.loads(Path(path).read_text(),object_pairs_hook=pairs,parse_constant=invalid)

def shared_module(base):
    path=base/"sources/harness/tools/verify_memcached_profile.py"
    spec=importlib.util.spec_from_file_location("retained_profile_verifier",path)
    module=importlib.util.module_from_spec(spec)
    previous=sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode=True
        spec.loader.exec_module(module)
    finally: sys.dont_write_bytecode=previous
    return module

def validate_plan(path):
    path=Path(path).resolve();base=path.parent;plan=load(path)
    require(plan["schema"]==SCHEMA,"ordinary schema")
    require(plan["full_50_case_gate_status"]=="not_run" and plan["security_validation"] is False and
            plan["timing_evidence"] is False and plan["latency_evidence"] is False,"ordinary scope")
    require(plan["python_assertions_enabled"] is True,"normal checks require assertions")
    require(plan["attempt_policy"]=="one attempt; no replacement or coverage-seeking retry","attempt policy")
    require(plan["interval"]==("preload, pre-traffic 0.5 second drain, watcher setup/settle and 0.2 second pause excluded; "
        "trace begins after before-stats, includes fixed client traffic, post-traffic watcher settle "
        "when enabled (0.4 second quiet rule, 5 second ceiling), then 0.5 second drain; "
        "trace ends before after-stats; incidental client timings are raw provenance only"),"fixed interval")
    require(plan["source_revision"]==plan["client_revision"]=="708ceb73c8b048966b9c2becfeaabca2c3b0769e","selected source")
    require(plan["normal_checks"]==CHECKS and plan["normal_variants"]==["native","diagnostics"],"normal inventory")
    require(plan["workload_mode"]=="independent-v1" and type(plan["workload_seed"]) is int and plan["workload_seed"]==20261109 and plan["measurement_mode"]=="count-only","fixed workload")
    required={"inputs/client","inputs/client-provenance.json","inputs/work/build-manifest.json",
        "inputs/build-recipe.sh","inputs/dependency-manifest.json","inputs/toolchain-provenance.json","inputs/protocol-amendment.json",
        "inputs/work/bin/memcached-native","inputs/work/bin/memcached-diagnostics",
        "sources/protocol/run_ordinary_profile.py","sources/protocol/verify_ordinary_profile.py"}
    required|={"inputs/client-validation/"+name for name in ("provenance.json","compiler-version.txt","build.stdout","build.stderr","protocol.stderr","release-reproduction-functional.log","COMMANDS.md")}
    required|={"sources/client/"+name for name in ("evaluation/memcached_client.cpp","evaluation/memcached_workload.h","evaluation/memcached_measurement.h","tests/memcached_buffered_protocol.py")}
    required|={"sources/harness/tools/"+name+".py" for name in ("profile_memcached_checks","verify_memcached_profile","benchmark_memcached","benchmark_memcached_matrix","memcached_common","process_guard","current_memcached_profile","test_memcached_deployment")}
    required|={"sources/server/"+name for name in ("integration/memcached_server/bridge.cpp","integration/memcached_server/bipbuffer_u.c","include/interspec/policy_switches.h","scripts/build_memcached_deployment.sh")}
    require(set(plan["files"])==required,"frozen inventory")
    require({str(p.relative_to(base)) for p in base.rglob("*") if p.is_file()}==required|{"plan.json"},"extra frozen files")
    for rel,digest in plan["files"].items():
        require(not Path(rel).is_absolute() and ".." not in Path(rel).parts and not (base/rel).is_symlink(),"frozen path")
        require(sha(base/rel)==digest,"frozen hash: "+rel)
    amendment=load(base/"inputs/protocol-amendment.json")
    require(amendment["previous_plan_sha256"]=="d9ec81e30f0edd4e56810c4c71c371dfb5f147eafc7292254f4ef2ca5e6ea2df" and
            amendment["previous_status"]=="normal_failed" and amendment["previous_profile_started"] is False and
            amendment["new_schema"]==SCHEMA,"documented predeclared correction")
    module=shared_module(base)
    build=load(base/"inputs/work/build-manifest.json")
    for variant in ("native","diagnostics"):
        name="memcached-"+variant
        require(sha(base/"inputs/work/bin"/name)==build["binary_sha256"][name],"server binary binding")
    for rel,field in (("integration/memcached_server/bridge.cpp","bridge_source_sha256"),("integration/memcached_server/bipbuffer_u.c","untrusted_source_sha256")):
        require(sha(base/"sources/server"/rel)==build[field],"server source binding")
    provenance=load(base/"inputs/client-provenance.json");validation=load(base/"inputs/client-validation/provenance.json")
    require(sha(base/"inputs/client")==provenance["binary_sha256"],"client binary binding")
    require(provenance["revision"]==validation["candidate_commit"]==plan["client_revision"] and validation["validation"]["release_candidate_protocol"]=="passed","client revision/status")
    for rel,digest in provenance["source_sha256"].items(): require(sha(base/"sources/client"/rel)==digest,"client source binding")
    execution=plan["execution"]
    require(all(Path(execution[key]).is_absolute() for key in ("plan_root","harness_root","python","guard")),"execution roots")
    require(execution["guard"]==str(Path(execution["harness_root"])/"tools/process_guard.py") and type(execution["uid"]) is int and isinstance(execution["account_name"],str) and execution["account_name"],"execution identity")
    module.validate_current_inputs(plan,base,provenance,validation,build)
    row=plan["scenario"]
    shape=dict(name="balanced_1c",mode="cache_only",clients=1,pipeline=10,value_bytes=256,keys=10000,get_percent=50,operations=5000,profile_keys=2048)
    require(all(row[key]==value and type(row[key]) is type(value) for key,value in shape.items()),"single fixed scenario")
    histogram=module.independent_oracle(5000,2048,50,20261109);gets=sum(x[1] for x in histogram)
    require(row["expected"]["key_verb_multiset"]==histogram and row["expected"]["get"]==gets and row["expected"]["set"]==5000-gets,"independent workload oracle")
    require(row["expected"]["key_verb_multiset_sha256"]==hashlib.sha256(json.dumps(histogram,separators=(",",":")).encode()).hexdigest(),"oracle hash")
    return plan,module


def verify(root,plan_path):
    root=Path(root).resolve();plan_path=Path(plan_path).resolve();base=plan_path.parent
    require(not any(p.is_symlink() for p in root.rglob("*")),"symlink in evidence")
    plan,module=validate_plan(plan_path);ledger=load(root/"run.json")
    require((root/"collect.lock").read_text()=="one attempt claimed\n","attempt lock")
    require(ledger["schema"]==SCHEMA and ledger["plan_sha256"]==sha(plan_path) and ledger["status"]=="collected","run status/binding")
    require(ledger["normal"]==[dict(variant=x,status="passed") for x in ("native","diagnostics")],"normal run grid")
    require(ledger["profile"]==dict(name="balanced_1c",attempt=1,status="collected"),"single attempt")
    gate_results=[]
    for variant in ("native","diagnostics"):
        directory=root/"normal"/variant;gate=load(directory/"gate.json")
        require(gate["status"]=="passed" and gate["checks"]==gate["expected_checks"]==CHECKS and gate["checks_passed"]==16 and gate["normal_function_completed"] is True,"normal check inventory/status")
        require(gate["full_50_case_gate_status"]=="not_run" and gate["security_validation"] is False,"normal gate scope")
        require(gate["binary_sha256"]==sha(base/f"inputs/work/bin/memcached-{variant}") and valid_normal_stop(gate["server_returncode"]),"normal binary/process binding")
        argv=gate["server_argv"]
        require(len(argv)==13 and argv[0]==str(Path(plan["execution"]["plan_root"])/f"inputs/work/bin/memcached-{variant}") and argv[1:4]==["-l","127.0.0.1","-p"] and re.fullmatch(r"[1-9][0-9]*",argv[4]) is not None and 0<int(argv[4])<65536 and argv[5:]==["-U","0","-m","64","-t","4","-u",plan["execution"]["account_name"]],"normal argv")
        actual={str(p.relative_to(directory)) for p in directory.rglob("*") if p.is_file() and p.name!="gate.json"}
        expected={"normal.stdout","normal.stderr","watch-records.json"}|{f"wire/connection-{i:03}.jsonl" for i in range(34)}
        require(actual==set(gate["files"])==expected,"normal evidence inventory")
        require((directory/"normal.stdout").read_bytes()==b"","unexpected normal stdout")
        records=load(directory/"watch-records.json")
        require(isinstance(records,list) and all(isinstance(row,str) for row in records) and
                all(any("key=evidence " in row and "type="+kind in row for row in records) for kind in ("item_store","item_get","deleted")),"normal watcher evidence")
        for rel,digest in gate["files"].items(): require(sha(directory/rel)==digest,"normal evidence hash")
        text=(directory/"normal.stderr").read_text()
        require(not any(word in text for word in ("INTERSPEC_REJECT","AddressSanitizer","runtime error:")),"unexpected normal diagnostic")
        connections=list((directory/"wire").glob("connection-*.jsonl"));require(len(connections)==34,"normal wire connections")
        events=0
        for stream in connections:
            for line in stream.read_text().splitlines():
                event=json.loads(line);data=base64.b64decode(event["base64"],validate=True)
                require(event["operation"] in ("send","read","readline") and type(event["length"]) is int and event["length"]==len(data) and event["sha256"]==hashlib.sha256(data).hexdigest(),"wire record schema/hash")
                events+=1
        require(events>2000,"normal wire evidence")
        gate_results.append(dict(variant=variant,checks_passed=16,wire_connections=len(connections),wire_events=events))
    require({p.name for p in (root/"profile").iterdir()}=={"balanced_1c"},"profile grid")
    row=module.verify_attempt(root/"profile/balanced_1c",plan["scenario"],plan,base)
    return dict(validated=True,schema=SCHEMA,source_revision=plan["source_revision"],normal_checks=gate_results,
        profile=row,plan_sha256=sha(plan_path),full_50_case_gate_status="not_run",security_validation=False,timing_evidence=False,latency_evidence=False,
        bounds="One ordinary diagnostic scenario at this source on this VM. Normal assertions and profile aggregate/trace recount passed. No security gate, timing, capacity, policy-effectiveness or comparative-performance claim.",
        transcript_scope="Exact normal() socket reads/writes retained with hashes, excluding Server startup probes. Verification checks transcript integrity; it does not independently replay all normal assertions.")


if __name__=="__main__":
    parser=argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--root",type=Path,required=True);parser.add_argument("--plan",type=Path,required=True)
    args=parser.parse_args();print(json.dumps(verify(args.root,args.plan),indent=2))
