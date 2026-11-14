# P2: memcached/bipbuffer timing

Tracker item P2 in `EVAL_TRACKER.md`. Measured on the Claude Code cloud VM
described in `evaluation/results/tracker/P1/`.

| Directory | Result |
|---|---|
| `01-vm-5037e6d-failed-driver-setup/` | Not a measurement. The driver (`driver.sh`) built memcached under a scratch directory and then ran the correctness gate without `--work`, so the gate looked for the binaries under its default `/tmp/interspec-memcached-deployment` and all 50 cases failed with "No such file or directory" within milliseconds. No timing was started. An error in the driver, not in memcached. |
