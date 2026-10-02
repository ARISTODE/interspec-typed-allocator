import os
import subprocess
import sys

exe = sys.argv[1]
enabled = subprocess.run([exe], env={**os.environ, "INTERSPEC_TRACE": "1"},
                         capture_output=True, text=True, check=True)
records = [dict(field.split("=", 1) for field in line.split()[1:])
           for line in enabled.stderr.splitlines() if line.startswith("INTERSPEC ")]
assert any(r["event"] == "live_allocation" and r["base"] == "0x1000"
           and r["size"] == "16" and r["site"] == "7" for r in records)
assert any(r["event"] == "check" and r["offset"] == "12" and
           r["remaining"] == "4" and r["result"] == "out_of_bounds" for r in records)
assert {"ok", "wrong_type", "untracked", "out_of_bounds"} <= {r["result"] for r in records}
assert any(r["event"] == "reallocate" and r["replacement"] == "0x1010" for r in records)
disabled = subprocess.run([exe], env={**os.environ, "INTERSPEC_TRACE": "0"},
                          capture_output=True, text=True, check=True)
assert not disabled.stderr
print("Trusted diagnostics: metadata, rejection reasons, lifetime events and disabled sink passed")
