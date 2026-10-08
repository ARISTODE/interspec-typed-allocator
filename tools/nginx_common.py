"""Pinned nginx deployment helpers. All listeners bind loopback."""
import http.client
import os
from pathlib import Path
import pwd
import grp
import resource
import signal
import socket
import subprocess
import time


def config(port, directory, workers=0):
    misses = '\n'.join(f'location ~ ^/unused{i}/([a-z]+)/([0-9]+)$ {{ return 200 "unused"; }}' for i in range(16))
    user = f'user {pwd.getpwuid(os.getuid()).pw_name} {grp.getgrgid(os.getgid()).gr_name};' if os.getuid() == 0 else ''
    return f'''{user}
daemon off;
master_process {"on" if workers else "off"};
worker_processes {workers or 1};
pid {directory}/nginx.pid;
error_log stderr notice;
env INTERSPEC_TRACE;
env INTERSPEC_NGINX_FAULT_PATH;
env INTERSPEC_NGINX_FAULT_KIND;
events {{ worker_connections 2048; }}
http {{
  access_log off;
  map $uri $mapped {{ default "other"; ~^/map/([a-z]+)$ $1; }}
  server {{
    listen 127.0.0.1:{port};
    location = /health {{ return 200 "ready"; }}
    {misses}
    location ~ ^/items/(?<itemid>[0-9]+)/(?<slug>[a-z]+)$ {{ return 200 "item:$itemid:$slug"; }}
    location ~* ^/case/([a-z]+)$ {{ return 200 "case:$1"; }}
    location ~ ^/optional/(a)?(b)$ {{ return 200 "optional:$1:$2"; }}
    location /rewrite/ {{ rewrite ^/rewrite/([a-z]+)$ /target/$1 last; }}
    location ~ ^/target/([a-z]+)$ {{ return 200 "rewrite:$1"; }}
    location /map/ {{ return 200 "map:$mapped"; }}
    location / {{ return 404 "missing"; }}
  }}
}}
'''


def request(port, path, method='GET'):
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    try:
        c.request(method, path)
        r = c.getresponse()
        return r.status, r.read().decode()
    finally:
        c.close()


class Server:
    def __init__(self, binary, directory, *, workers=0, fault=None, trace=False, cpu=None, wait=True):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / 'logs').mkdir(exist_ok=True)
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            self.port = s.getsockname()[1]
        self.conf = self.directory / 'nginx.conf'
        self.conf.write_text(config(self.port, self.directory, workers))
        self.logpath = self.directory / 'stderr.log'
        self.log = self.logpath.open('wb')
        env = {k: v for k, v in os.environ.items() if not k.startswith('INTERSPEC_NGINX_FAULT') and k != 'INTERSPEC_TRACE'}
        env['LC_ALL'] = 'C'
        if fault:
            env.update(INTERSPEC_NGINX_FAULT_PATH=str(fault[0]), INTERSPEC_NGINX_FAULT_KIND=str(fault[1]))
        if trace:
            env['INTERSPEC_TRACE'] = '1'
        args = [str(binary), '-p', str(self.directory) + '/', '-c', str(self.conf)]
        if cpu:
            args = ['taskset', '-c', cpu, *args]
        def setup():
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        start = time.monotonic()
        self.proc = subprocess.Popen(args, stdout=self.log, stderr=self.log, env=env, start_new_session=True, preexec_fn=setup)
        if wait:
            try:
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if self.proc.poll() is not None:
                        raise RuntimeError(f'nginx exit {self.proc.returncode}: {self.logpath.read_text()[-4000:]}')
                    try:
                        if request(self.port, '/health') == (200, 'ready'):
                            break
                    except (OSError, http.client.HTTPException):
                        pass
                    time.sleep(.02)
                else:
                    raise TimeoutError('nginx startup')
            except BaseException:
                self.close()
                raise
        self.startup_ms = 1000 * (time.monotonic() - start)

    def close(self):
        if self.proc.poll() is None:
            self.proc.send_signal(signal.SIGQUIT)
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
                self.proc.wait()
        self.log.close()

    def __enter__(self): return self
    def __exit__(self, *args): self.close()
