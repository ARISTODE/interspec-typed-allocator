# P1: host check on the Claude Code cloud VM

Tracker item P1 in `EVAL_TRACKER.md`. By JH's decision of 2026-11-13 (D2) the
performance items are measured on this VM and the paper describes it. Saved on
2026-11-14, before any timing run.

## The machine (`vm-configuration/`)

| | |
|---|---|
| Kind | Claude Code cloud session: a container inside a KVM (Firecracker) virtual machine. Not a dedicated host; other tenants and the hypervisor are outside the session's control. |
| CPUs | 4 virtual CPUs, Intel Xeon @ 2.10 GHz (family 6, model 207), one thread per core as seen by the guest; the mapping to physical cores is not visible. |
| Memory | 16 GB, no swap |
| Kernel | Linux 6.18.44 (`uname.txt`), command line in `kernel-cmdline.txt` |
| Frequency control | not visible to the guest (no `cpufreq`); SMT control `notsupported` |
| Software | `software.txt`: OS release, compilers, CMake, Python |

## CPU sets

Server: CPUs 0 and 1. Client or load generator: CPUs 2 and 3. For the
single-process benchmarks the measured program is pinned to CPU 0.

## Preflight output

| Directory | Result |
|---|---|
| `01-vm-preflight/` | `tools/publication_host_preflight.py --server-cpus 0-1 --client-cpus 2-3`: exit status 1, six shortfalls against the dedicated-host protocol, one of them a missing tool (`wrk`). |
| `02-vm-preflight-with-wrk/` | The same after `apt-get install wrk` (4.1.0): exit status 1, five shortfalls. |

The five shortfalls that remain are properties of the VM and are what the
paper has to state about its measurements:

1. the protocol asks for four server and four client CPUs; the VM has four in
   all, so two and two are used;
2. and 3. each set has two cores, not four;
4. the machine is not a dedicated host;
5. the frequency policy is not visible, so it cannot be fixed or reported.

The tool therefore reports `publication_ready: false`. That is the tool's
verdict for the protocol written for a dedicated host; D2 replaced that host
by this VM knowingly.
