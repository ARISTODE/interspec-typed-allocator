#!/usr/bin/env python3
"""Compile the real CodeQL inputs with its analysis stub, without CodeQL."""

import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="interspec-policy-test-") as tmp:
        subprocess.run(
            ["bash", str(ROOT / "scripts/run_policy_inference.sh"), "--build-only"],
            env={**os.environ, "TMPDIR": tmp},
            check=True,
        )
        work = Path(tmp) / "interspec-policy"
        for name in ("u.o", "t.o"):
            assert (work / name).stat().st_size > 0, name
        # The adversarial callback remains distinct from the ordinary malloc
        # calls that CodeQL selects; the stub is never linked into a runtime.
        symbols = subprocess.check_output(["nm", "-u", str(work / "u.o")], text=True)
        assert "interspec_analysis_site_alloc" in symbols
        assert "malloc" in symbols
    print("InterSpec policy inference build: all checks passed")


if __name__ == "__main__":
    main()
