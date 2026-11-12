#!/usr/bin/env python3
"""Linux parent-death guard, started normally (no threaded preexec_fn)."""
import ctypes
import os
import resource
import signal
import sys

def main():
    expected_parent = int(sys.argv[1])
    if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGKILL) != 0:
        raise OSError('PR_SET_PDEATHSIG failed')
    if os.getppid() != expected_parent or expected_parent == 1:
        os.kill(os.getpid(), signal.SIGKILL)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.execvp(sys.argv[2], sys.argv[2:])

if __name__ == '__main__': main()
