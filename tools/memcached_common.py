"""Local process and wire helpers shared by deployment tests and benchmarks."""
import os
from pathlib import Path
import pwd
import resource
import socket
import subprocess
import time


class Client:
    def __init__(self, port, timeout=8):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.file = self.sock.makefile("rb")

    def send(self, data):
        self.sock.sendall(data)

    def line(self):
        line = self.file.readline()
        if not line:
            raise EOFError("server closed connection")
        return line

    def command(self, data):
        self.send(data + b"\r\n")
        return self.line()

    def store(self, key, data, command=b"set", flags=0, expiry=0, cas=None):
        tail = b" " + str(cas).encode() if cas is not None else b""
        self.send(command + b" " + key + f" {flags} {expiry} {len(data)}".encode() + tail + b"\r\n" + data + b"\r\n")
        return self.line()

    def get(self, key, command=b"get"):
        self.send(command + b" " + key + b"\r\n")
        values = {}
        while True:
            line = self.line()
            if line == b"END\r\n":
                return values
            fields = line.split()
            assert fields[0] == b"VALUE", line
            data = self.file.read(int(fields[3]))
            assert self.file.read(2) == b"\r\n"
            values[fields[1]] = {"flags": int(fields[2]), "data": data,
                               "cas": int(fields[4]) if len(fields) > 4 else None}

    def stats(self, kind=b""):
        self.send(b"stats" + (b" " + kind if kind else b"") + b"\r\n")
        result = {}
        while True:
            line = self.line()
            if line == b"END\r\n": return result
            _, key, value = line.decode().split()
            result[key] = value

    def close(self):
        self.file.close()
        self.sock.close()

    def __enter__(self): return self
    def __exit__(self, *args): self.close()


class Server:
    def __init__(self, binary, logdir, name, *, trace=False, fault=None, extra=(), cpu=None):
        logdir = Path(logdir)
        logdir.mkdir(parents=True, exist_ok=True)
        self.logpath = logdir / f"{name}.stderr"
        self.outpath = logdir / f"{name}.stdout"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        env = {k: v for k, v in os.environ.items() if not k.startswith("INTERSPEC_TEST_") and k != "INTERSPEC_TRACE"}
        env["LC_ALL"] = "C"
        if trace: env["INTERSPEC_TRACE"] = "1"
        if fault: env.update({f"INTERSPEC_TEST_{k.upper()}": str(v) for k, v in fault.items()})
        self.args = [str(binary), "-l", "127.0.0.1", "-p", str(self.port), "-U", "0", "-m", "64", "-t", "4",
                     "-u", pwd.getpwuid(os.getuid()).pw_name, *extra]
        if cpu is not None: self.args = ["taskset", "-c", str(cpu), *self.args]
        self.err = self.logpath.open("wb")
        self.out = self.outpath.open("wb")
        def no_core(): resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        start = time.monotonic_ns()
        self.proc = subprocess.Popen(self.args, stdout=self.out, stderr=self.err, env=env, preexec_fn=no_core)
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if self.proc.poll() is not None:
                    raise RuntimeError(f"exit={self.proc.returncode}\n{self.logpath.read_text()}\n{self.outpath.read_text()}")
                try:
                    with Client(self.port, timeout=0.2) as client:
                        assert client.command(b"version").startswith(b"VERSION ")
                    break
                except (OSError, EOFError): time.sleep(0.02)
            else: raise TimeoutError("memcached startup")
        except BaseException:
            self.close()
            raise
        self.startup_ns = time.monotonic_ns() - start

    def close(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try: self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill(); self.proc.wait()
        self.err.close(); self.out.close()

    def __enter__(self): return self
    def __exit__(self, *args): self.close()
