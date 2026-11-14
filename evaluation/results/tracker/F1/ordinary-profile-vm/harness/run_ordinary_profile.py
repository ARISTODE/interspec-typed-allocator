#!/usr/bin/env python3
"""One preregistered ordinary-only diagnostic. Never the 50-case gate."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys
import threading
import traceback

SCHEMA = "ordinary-only-memcached-profile-v1"
NORMAL_CHECKS = ["lru_async_item_bumps", "set_get_flags", "add_replace", "cas", "append_prepend",
                 "incr_decr", "binary_256k", "multiget", "touch_delete", "fragmented_request",
                 "invalid_commands", "expiry", "flush_all", "watch_log_content", "concurrent_cache_2000_ops",
                 "watcher_churn_25"]

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, data):
    path = Path(path); tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as f:
        json.dump(data, f, indent=2, sort_keys=True); f.write("\n"); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def audit_client(base_class, directory):
    """Retain exact normal-check socket writes and reads, one stream per connection."""
    lock = threading.Lock(); next_id = [0]
    class Audit:
        def __init__(self, underlying, owner, read=False): self.underlying=underlying; self.owner=owner; self.read_mode=read
        def __getattr__(self, name): return getattr(self.underlying, name)
        def sendall(self, data):
            result=self.underlying.sendall(data); self.owner.record("send", data); return result
        def read(self, size):
            data=self.underlying.read(size); self.owner.record("read", data); return data
        def readline(self):
            data=self.underlying.readline(); self.owner.record("readline", data); return data
    class Client(base_class):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            with lock:
                number=next_id[0]; next_id[0]+=1
            self.audit=(directory / f"connection-{number:03}.jsonl").open("x", buffering=1)
            self.sock=Audit(self.sock,self); self.file=Audit(self.file,self,True)
        def record(self, operation, data):
            self.audit.write(json.dumps(dict(operation=operation, length=len(data),
                sha256=hashlib.sha256(data).hexdigest(), base64=base64.b64encode(data).decode()))+"\n")
        def close(self):
            try: super().close()
            finally: self.audit.flush(); os.fsync(self.audit.fileno()); self.audit.close()
    return Client


def normal_gate(binary, directory, deployment, common, trace):
    directory.mkdir(exist_ok=False); (directory / "wire").mkdir()
    result=dict(status="started", binary_sha256=sha(binary), expected_checks=NORMAL_CHECKS,
                full_50_case_gate_status="not_run", security_validation=False)
    save(directory / "gate.json", result)
    original=deployment.Client
    try:
        deployment.Client=audit_client(original,directory/"wire")
        with common.Server(binary,directory,"normal",trace=trace,guarded=True) as server:
            result["server_argv"]=server.args; save(directory/"gate.json",result)
            checks=deployment.normal(server,directory)
            if checks != NORMAL_CHECKS: raise ValueError("normal check inventory")
        result["server_returncode"]=server.proc.returncode
        if result["server_returncode"] != -15: raise ValueError("normal server exit")
        stderr=server.logpath.read_text()
        if "INTERSPEC_REJECT" in stderr or "AddressSanitizer" in stderr or "runtime error:" in stderr:
            raise ValueError("unexpected normal-server diagnostic")
        result.update(status="passed", checks=checks, checks_passed=len(checks))
    except Exception as exc:
        result.update(status="failed", failure=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()))
    finally:
        deployment.Client=original
        result["files"]={str(p.relative_to(directory)):sha(p) for p in sorted(directory.rglob("*")) if p.is_file() and p.name != "gate.json"}
        save(directory/"gate.json",result)
    return result


def prepare(args):
    source=args.source.resolve(); work=args.work.resolve(); out=args.out.resolve()
    if not __debug__ or sys.flags.optimize or os.environ.get("PYTHONOPTIMIZE"):
        raise ValueError("optimized Python is forbidden")
    if any(k.startswith("INTERSPEC_") for k in os.environ): raise ValueError("unexpected INTERSPEC environment")
    revision=subprocess.check_output(["git","-C",str(source),"rev-parse","HEAD"],text=True).strip()
    if revision != "708ceb73c8b048966b9c2becfeaabca2c3b0769e": raise ValueError("preregistered source revision")
    if subprocess.check_output(["git","-C",str(source),"status","--porcelain"],text=True): raise ValueError("source is not clean")
    out.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(source/"tools"))
    import profile_memcached_checks as collector
    import current_memcached_profile as builder
    import memcached_common as common
    import test_memcached_deployment as deployment
    build=json.loads((work/"build-manifest.json").read_text())
    if build["project_commit"] != revision or build["project_dirty"] is not False: raise ValueError("current build source identity")
    for name in ("native","diagnostics"):
        if sha(work/f"bin/memcached-{name}") != build["binary_sha256"][f"memcached-{name}"]: raise ValueError("build binary identity")
    client_args=builder.prepare_inputs(argparse.Namespace(client_build_directory=out/"client-build"),source)
    frozen=out/"frozen"; frozen.mkdir(); files={}
    def copy(src,rel):
        dst=frozen/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst); files[rel]=sha(dst)
    for name in ("native","diagnostics"): copy(work/f"bin/memcached-{name}",f"inputs/work/bin/memcached-{name}")
    copy(work/"build-manifest.json","inputs/work/build-manifest.json")
    copy(work.parent/"build-once.sh","inputs/build-recipe.sh")
    copy(work.parent/"dependencies/manifest.json","inputs/dependency-manifest.json")
    copy(work.parent/"toolchain-provenance.json","inputs/toolchain-provenance.json")
    copy(client_args.client_binary,"inputs/client")
    copy(client_args.client_provenance,"inputs/client-provenance.json")
    for name in ("provenance.json","compiler-version.txt","build.stdout","build.stderr","protocol.stderr","release-reproduction-functional.log","COMMANDS.md"):
        copy(client_args.client_validation_directory/name,"inputs/client-validation/"+name)
    for rel in builder.SOURCES: copy(source/rel,"sources/client/"+rel)
    for rel in collector.HARNESS+["tools/current_memcached_profile.py","tools/test_memcached_deployment.py"]:
        copy(source/rel,"sources/harness/"+rel)
    for rel in ("integration/memcached_server/bridge.cpp","integration/memcached_server/bipbuffer_u.c","include/interspec/policy_switches.h","scripts/build_memcached_deployment.sh"):
        copy(source/rel,"sources/server/"+rel)
    for name in ("run_ordinary_profile.py","verify_ordinary_profile.py"):
        copy(Path(__file__).parent/name,"sources/protocol/"+name)
    scenario=dict(next(row for row in collector.SCENARIOS if row["name"]=="balanced_1c"))
    scenario.update(operations=5000,profile_keys=2048)
    scenario["expected"]=collector.expected_work(5000,2048,50,20261109)
    plan=dict(schema=SCHEMA,source_revision=revision,client_revision=revision,scenario=scenario,normal_variants=["native","diagnostics"],
        normal_checks=NORMAL_CHECKS,workload_mode="independent-v1",workload_seed=20261109,measurement_mode="count-only",interval=collector.INTERVAL,
        full_50_case_gate_status="not_run",security_validation=False,timing_evidence=False,latency_evidence=False,
        attempt_policy="one attempt; no replacement or coverage-seeking retry",files=files,
        execution=dict(plan_root=str(frozen),harness_root=str(source),python=sys.executable,guard=str(source/"tools/process_guard.py"),account_name=pwd.getpwuid(os.getuid()).pw_name,uid=os.getuid()),
        original_inputs=dict(client=str(client_args.client_binary),client_source=str(source)),
        out=str(out),python_assertions_enabled=True)
    save(frozen/"plan.json",plan)
    from verify_ordinary_profile import validate_plan
    validate_plan(frozen/"plan.json")
    ledger=dict(schema=SCHEMA,plan_sha256=sha(frozen/"plan.json"),status="prepared",normal=[])
    save(out/"run.json",ledger)
    return dict(prepared=True,collected=False,plan=str(frozen/"plan.json"),sha256=sha(frozen/"plan.json"))


def collect(plan_path):
    from verify_ordinary_profile import validate_plan,verify,load
    if not __debug__ or sys.flags.optimize or os.environ.get("PYTHONOPTIMIZE"):
        raise ValueError("optimized Python is forbidden")
    if any(k.startswith("INTERSPEC_") for k in os.environ): raise ValueError("unexpected INTERSPEC environment")
    plan_path=plan_path.resolve();frozen=plan_path.parent
    plan,_=validate_plan(plan_path);out=Path(plan["out"]);source=Path(plan["execution"]["harness_root"])
    if str(frozen)!=plan["execution"]["plan_root"] or sys.executable!=plan["execution"]["python"] or os.getuid()!=plan["execution"]["uid"] or pwd.getpwuid(os.getuid()).pw_name!=plan["execution"]["account_name"]:
        raise ValueError("collection execution identity")
    for relative,digest in plan["files"].items():
        if relative.startswith("sources/harness/"):
            live=source/relative.removeprefix("sources/harness/")
        elif relative.startswith("sources/protocol/"):
            live=Path(__file__).parent/Path(relative).name
        else: continue
        if sha(live)!=digest: raise ValueError("live harness differs from freeze: "+relative)
    ledger=load(out/"run.json")
    if ledger!={"schema":SCHEMA,"plan_sha256":sha(plan_path),"status":"prepared","normal":[]}:
        raise ValueError("run already attempted or invalid preparation")
    with (out/"collect.lock").open("x") as lock: lock.write("one attempt claimed\n")
    ledger["status"]="running";save(out/"run.json",ledger)
    sys.path.insert(0,str(source/"tools"))
    import profile_memcached_checks as collector
    import memcached_common as common
    import test_memcached_deployment as deployment
    scenario=plan["scenario"]
    normal_root=out/"normal"; normal_root.mkdir()
    for variant in plan["normal_variants"]:
        state=normal_gate(frozen/f"inputs/work/bin/memcached-{variant}",normal_root/variant,deployment,common,variant=="diagnostics")
        ledger["normal"].append(dict(variant=variant,status=state["status"]))
        if state["status"] != "passed":
            ledger["status"]="normal_failed"; save(out/"run.json",ledger); raise ValueError("normal checks failed: "+variant)
        save(out/"run.json",ledger)
    profile=out/"profile"; profile.mkdir()
    state=collector.collect_one(plan,frozen,scenario,profile/scenario["name"])
    ledger.update(status="collected" if state["status"]=="collected" else "profile_failed",profile=dict(name=scenario["name"],attempt=1,status=state["status"]))
    save(out/"run.json",ledger)
    result=verify(out,frozen/"plan.json")
    save(out/"verification.json",result)
    return result


def main():
    parser=argparse.ArgumentParser(allow_abbrev=False)
    sub=parser.add_subparsers(dest="command",required=True)
    prep=sub.add_parser("prepare",allow_abbrev=False)
    for name in ("source","work","out"):prep.add_argument("--"+name,type=Path,required=True)
    run=sub.add_parser("collect",allow_abbrev=False);run.add_argument("--plan",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args) if args.command=="prepare" else collect(args.plan),indent=2))


if __name__=="__main__": main()
