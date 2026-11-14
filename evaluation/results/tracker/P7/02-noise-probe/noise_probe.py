import subprocess, sys, time, statistics, re
binary, args, runs = sys.argv[1], sys.argv[2].split(), int(sys.argv[3])
def cpu_stat(c):
    for l in open('/proc/stat'):
        if l.startswith(f'cpu{c} '):
            return list(map(int, l.split()[1:]))
for cpu in (0, 1, 2, 3):
    vals, steal = [], []
    for _ in range(runs):
        a = cpu_stat(cpu)
        out = subprocess.run(['taskset', '-c', str(cpu), binary] + args, capture_output=True, text=True).stdout
        b = cpu_stat(cpu)
        vals.append(int(re.search(r'elapsed_ns=(\d+)', out).group(1)) / 1e6)
        d = [y - x for x, y in zip(a, b)]
        steal.append(100 * d[7] / max(1, sum(d[:8])))
    print(f'cpu{cpu} median {statistics.median(vals):8.1f} ms  min {min(vals):8.1f}  max {max(vals):8.1f}  max/min {max(vals)/min(vals):.2f}  steal% median {statistics.median(steal):.1f} max {max(steal):.1f}', flush=True)
