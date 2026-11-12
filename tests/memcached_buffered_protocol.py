"""Excluded functional fixtures for stream framing, not performance evidence.

The Python oracle intentionally does not import the C++ workload implementation.
All normal cases compare full request sequences, including key, verb and SET body.
The existing multi-client fixture separately compares complete key/verb multisets.
"""
import json
import socketserver
import subprocess
import sys
import threading
import time

CLIENT = sys.argv[1]
MASK = (1 << 64) - 1
SEED = 20261109


def mix(x):
    x = (x + 0x9e3779b97f4a7c15) & MASK
    x = ((x ^ (x >> 30)) * 0xbf58476d1ce4e5b9) & MASK
    x = ((x ^ (x >> 27)) * 0x94d049bb133111eb) & MASK
    return x ^ (x >> 31)


def bounded(op, domain, bound):
    x = mix(op ^ mix(SEED ^ domain))
    while x < (1 << 64) % bound:
        x = mix(x)
    return x % bound


def fixture(pipeline, value_bytes, count, pct=50, fragment=False, corrupt=None,
            truncate=False, mode='count-only', legacy=False):
    expected = []
    for op in range(count):
        key = (op * 104729) % 31 if legacy else bounded(op, 0x243f6a8885a308d3, 31)
        get = (op * 37) % 100 < pct if legacy else bounded(op, 0x13198a2e03707344, 100) < pct
        expected.append((b'get' if get else b'set', ('bench' + str(key)).encode()))

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            try:
                for first in range(0, count, pipeline):
                    replies = []
                    for op in range(first, min(first + pipeline, count)):
                        fields = self.rfile.readline().split()
                        assert tuple(fields[:2]) == expected[op], (op, fields, expected[op])
                        if fields[0] == b'set':
                            assert fields[2:] == [b'0', b'0', str(value_bytes).encode()]
                            assert self.rfile.read(value_bytes + 2) == b'x' * value_bytes + b'\r\n'
                            replies.append(b'STORED\r\n')
                        else:
                            assert len(fields) == 2
                            replies.append(b'VALUE ' + fields[1] + b' 0 ' + str(value_bytes).encode()
                                           + b'\r\n' + b'x' * value_bytes + b'\r\nEND\r\n')
                        self.server.seen += 1
                    # Deliberately return a whole pipeline together, independent of
                    # the request TCP segmentation. A response can span 64 KiB refills.
                    payload = b''.join(replies)
                    if first == 0 and corrupt is not None:
                        offset = {'first': 0, 'middle': len(payload)//2,
                                  'last': len(payload)-1}.get(corrupt, corrupt)
                        assert 0 <= offset < len(payload)
                        payload = payload[:offset] + bytes([payload[offset] ^ 1]) + payload[offset+1:]
                    if first == 0 and truncate:
                        self.wfile.write(payload[:-1])
                        return
                    if fragment:
                        # Split header, payload and terminators; delay only these
                        # excluded tests to make separate arrivals likely.
                        offset = 0
                        for size in [1, 2, 3, 7, 11, 17, 31]:
                            self.wfile.write(payload[offset:offset+size])
                            offset += size
                            time.sleep(.001)
                        while offset < len(payload):
                            size = min(127, len(payload)-offset)
                            self.wfile.write(payload[offset:offset+size])
                            offset += size
                    else:
                        self.wfile.write(payload)
                    if first == 0 and corrupt is not None:
                        return
            except (BrokenPipeError, ConnectionResetError):
                if corrupt is None and not truncate:
                    self.server.failures.append('unexpected connection close')
            except Exception as exc:
                self.server.failures.append(repr(exc))

    class Server(socketserver.TCPServer):
        allow_reuse_address = True

    with Server(('127.0.0.1', 0), Handler) as server:
        server.seen = 0
        server.failures = []
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01})
        thread.start()
        try:
            args = [CLIENT, str(server.server_address[1]), '0', '1', str(pipeline),
                    str(value_bytes), '31', str(pct), str(count),
                    'legacy' if legacy else 'independent-v1', str(SEED), mode, '8', '10000']
            result = subprocess.run(args, capture_output=True, text=True, timeout=20)
        finally:
            server.shutdown()
            thread.join()
        assert not server.failures, server.failures
        if corrupt is not None or truncate:
            assert result.returncode == 1 and not result.stdout, (args, result)
            assert ('receive' if truncate else 'response_mismatch') in result.stderr, result.stderr
        else:
            assert result.returncode == 0, (args, result.stderr)
            row = json.loads(result.stdout)
            assert server.seen == count and row['operations'] == count and row['errors'] == 0
            if mode == 'count-only':
                assert all(row[k] is None for k in ['p50_us','p95_us','p99_us','max_us'])
                assert all(row[k] == 0 for k in ['latency_sample_count','latency_selected_count',
                                               'latency_dropped_count','sample_every','sample_cap_per_client'])
                assert not row['latency_valid'] and row['latency_scope'] == 'unavailable'
            else:
                selected = count if mode == 'full' else sum(bounded(i,0xa4093822299f31d0,8)==0 for i in range(count))
                assert row['latency_sample_count'] == selected and row['latency_selected_count'] == selected
                assert row['latency_dropped_count'] == 0 and row['latency_valid']
    return 1


cases = 0
for mode in ['count-only','full','sampled']:
    for fragment in [False, True]:
        cases += fixture(16, 16, 67, fragment=fragment, mode=mode)
for pipeline in [1, 16]:
    for pct in [0, 50, 100]:
        cases += fixture(pipeline, 70000, 35, pct=pct)
# Multiple small responses fill the bounded buffer; final batch is incomplete.
cases += fixture(256, 256, 515, pct=100)
cases += fixture(16, 16, 67, legacy=True)
for corrupt in ['first','middle','last',65535,65536]:
    cases += fixture(4, 70000, 9, pct=100, corrupt=corrupt)
cases += fixture(4, 70000, 9, pct=100, truncate=True)
cases += fixture(16, 16, 67, truncate=True)
print(f'{cases} buffered stream functional cases passed; no performance evidence')
