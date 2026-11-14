# P2: memcached/bipbuffer timing

Tracker item P2 in `EVAL_TRACKER.md`. Measured on the Claude Code cloud VM
described in `evaluation/results/tracker/P1/`.

| Directory | Result |
|---|---|
| `01-vm-5037e6d-failed-driver-setup/` | Not a measurement. The driver (`driver.sh`) built memcached under a scratch directory and then ran the correctness gate without `--work`, so the gate looked for the binaries under its default `/tmp/interspec-memcached-deployment` and all 50 cases failed with "No such file or directory" within milliseconds. No timing was started. An error in the driver, not in memcached. |
| `02-vm-5994983-interrupted-by-restart/` | Not a complete measurement. With the work directory passed correctly the build and the correctness gate passed (50 of 50) and the timed matrix started (six scenarios, four variants, 15 repetitions of 30 s). The session's machine restarted after 206 of the 360 samples, during the fourth scenario, and the run died with it. The samples that exist are in `matrix.stdout.txt` and `matrix/`; they are kept and are not used for any number. The run was launched detached while the session was idle, and an idle session's machine can be reclaimed. |
