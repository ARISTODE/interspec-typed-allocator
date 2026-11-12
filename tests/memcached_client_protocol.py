"""Functional loopback protocol fixture, NOT real-server performance evidence."""
import json
from collections import Counter
import socketserver
import subprocess
import sys
import threading

client = sys.argv[1]
MASK = (1 << 64) - 1

def mix(x):
    x = (x + 0x9e3779b97f4a7c15) & MASK
    x = ((x ^ (x >> 30)) * 0xbf58476d1ce4e5b9) & MASK
    x = ((x ^ (x >> 27)) * 0x94d049bb133111eb) & MASK
    return x ^ (x >> 31)

def bounded(op, seed, domain, bound):
    x = mix(op ^ mix(seed ^ domain))
    while x < ((1 << 64) % bound):
        x = mix(x)
    return x % bound

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        while line := self.rfile.readline():
            fields = line.split()
            with self.server.lock:
                self.server.requests[(fields[0].decode(), fields[1].decode())] += 1
            if fields[0] == b'get':
                with self.server.lock:
                    self.server.gets += 1
                reply = b'VALUE ' + fields[1] + b' 0 16\r\n' + b'x'*16 + b'\r\nEND\r\n'
            else:
                assert fields[0] == b'set' and fields[4] == b'16'
                assert self.rfile.read(18) == b'x'*16 + b'\r\n'
                with self.server.lock:
                    self.server.sets += 1
                reply = b'STORED\r\n'
            if self.server.bad:
                reply = b'!' + reply[1:]
            self.wfile.write(reply)

class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def handle_error(self, request, client_address):
        # Corrupt-response case intentionally makes the client close mid-pipeline.
        if not self.bad:
            super().handle_error(request, client_address)

with Server(('127.0.0.1', 0), Handler) as server:
    server.gets = server.sets = 0
    server.requests = Counter()
    server.bad = False
    server.lock = threading.Lock()
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    port = str(server.server_address[1])
    count, seed = 1003, 20261109
    expected_gets = sum(bounded(i,seed,0x13198a2e03707344,100)<50 for i in range(count))
    expected_requests = Counter(
        ('get' if bounded(i,seed,0x13198a2e03707344,100)<50 else 'set',
         'bench' + str(bounded(i,seed,0x243f6a8885a308d3,31)))
        for i in range(count))
    selected = sum(bounded(i,seed,0xa4093822299f31d0,8)==0 for i in range(count))
    for clients,pipeline in [(1,1),(8,16)]:
        for mode in ['count-only','full','sampled']:
            server.gets = server.sets = 0
            server.requests = Counter()
            args = [client,port,'0',str(clients),str(pipeline),'16','31','50',str(count),'independent-v1',str(seed),mode,'8','10000']
            result = subprocess.run(args,capture_output=True,text=True,timeout=15,check=True)
            row = json.loads(result.stdout)
            assert row['operations']==count and row['errors']==0
            assert server.requests == expected_requests
            assert server.gets==expected_gets and server.sets==count-expected_gets
            assert row['timed_client_cpu_s']>=0 and row['elapsed_s']>0
            if mode == 'count-only':
                assert all(row[k] is None for k in ('p50_us','p95_us','p99_us','max_us'))
                assert all(row[k] == 0 for k in ('latency_sample_count','latency_selected_count','latency_dropped_count','sample_every','sample_cap_per_client'))
                assert not row['latency_valid'] and row['latency_scope']=='unavailable'
            else:
                assert row['latency_valid'] and row['p99_us'] is not None
                assert row['latency_sample_count']==(count if mode=='full' else selected)
    args = [client,port,'0','1','16','16','31','50',str(count),'independent-v1',str(seed),'sampled','1','2']
    row = json.loads(subprocess.check_output(args,text=True,timeout=15))
    assert row['latency_sample_count']==2 and row['latency_dropped_count']==count-2
    assert row['p99_us'] is None and not row['latency_valid']
    server.bad = True
    result = subprocess.run(args,capture_output=True,text=True,timeout=15)
    assert result.returncode==1 and not result.stdout and 'response_mismatch' in result.stderr
    server.shutdown()

base = [client,'12345','1','1','1','16','31','50','1003','independent-v1','1','count-only','8','100']
for index,value in [(1,'65536'),(2,'nan'),(2,'inf'),(2,'1junk'),(3,'-1'),(8,'-1'),(8,str(MASK)),(10,'-1'),(12,'0'),(13,'0')]:
    args = base.copy(); args[index] = value
    result = subprocess.run(args,capture_output=True,text=True,timeout=3)
    assert result.returncode==2 and not result.stdout, (index,value,result)
print('6 normal protocol cases, overflow, response corruption, 10 argument cases passed; mock server only')
