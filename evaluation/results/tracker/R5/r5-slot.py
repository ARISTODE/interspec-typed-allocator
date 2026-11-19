"""R5: run r5_slot_writes.ql the way run_slot_policy_analysis.py runs its queries: in an isolated
pack whose generated configuration is the nginx_openssl manifest of the work directory (the
ten-function variant). Run from the work directory root."""
import subprocess, sys
from pathlib import Path
sys.path.insert(0, "scripts")
import run_slot_policy_analysis as m
out = Path(sys.argv[1]); codeql = sys.argv[2]
out.mkdir(parents=True, exist_ok=True)
m.SLOT_TYPES_QUERY = Path("ql/queries/r5_slot_writes.ql")
tmp, pack_root, qmap = m.build_isolated_query_pack(Path("coverage/configs/nginx_openssl.json"))
query = qmap[m.SLOT_TYPES_QUERY]
(out / "generated-index.qll").write_text((pack_root / "generated" / "index.qll").read_text())
cmd = [codeql, "query", "run", str(query), "--database", "db/nginx_openssl_libs", "--search-path", str(pack_root),
       "--threads", "4", "--ram", "10000", "--output", str(out / "r5_slot_writes.bqrs")]
(out / "command.txt").write_text(" ".join(cmd) + "\n")
with open(out / "run.log", "w") as log:
    code = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT).returncode
    if code == 0:
        code = subprocess.run([codeql, "bqrs", "decode", "--format=csv", "--output", str(out / "r5_slot_writes.csv"),
                               str(out / "r5_slot_writes.bqrs")], stdout=log, stderr=subprocess.STDOUT).returncode
sys.exit(code)
