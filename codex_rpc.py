import json,queue,subprocess,threading,time
from app_config import ROOT,binary

def limits_view(payload):
    result = payload.get('result', payload)
    bucket = (result.get('rateLimitsByLimitId') or {}).get('codex') or result.get('rateLimits')
    if not bucket:
        return {'available': False, 'reason': '服务未提供账号额度', 'windows': []}
    windows = [dict(x) for x in [bucket.get('primary'), bucket.get('secondary')] if x]
    exhausted = [x for x in windows if x.get('usedPercent', 0) >= 100]

    def percent(mins):
        w = next((x for x in windows if x.get('windowDurationMins') == mins), None)
        return None if not w else max(0, min(100, 100 - w['usedPercent']))
    return {'available': bool(windows), 'five_hour_remaining': percent(300), 'weekly_remaining': percent(10080), 'windows': windows, 'exhausted': bool(exhausted), 'wait_until': max([x.get('resetsAt') or time.time() + 300 for x in exhausted], default=None), 'checked_at': time.time(), 'bucket': bucket.get('limitId', 'codex')}

class RpcError(Exception):

    def __init__(self, error):
        self.error = error
        super().__init__(str(error.get('message', error)))

class Rpc:

    def __init__(self, events, command=None, env=None):
        self.events = events
        self.pending = {}
        self.seq = 0
        self.lock = threading.Lock()
        self.write_lock = threading.Lock()
        self.alive = True
        command = command or [str(binary('codex',required=True)), 'app-server', '--listen', 'stdio://']
        self.proc = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        self.call('initialize', {'clientInfo': {'name': 'reset', 'title': 'Reset', 'version': '0.1.0'}})
        self.send({'method': 'initialized'})

    def _drain_stderr(self):
        for line in self.proc.stderr:
            pass

    def _read(self):
        try:
            for line in self.proc.stdout:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if 'id' in r and 'method' not in r:
                    q = self.pending.get(r['id'])
                    if q:
                        q.put(r)
                else:
                    self.events.put(r)
        finally:
            self.alive = False
            for q in list(self.pending.values()):
                q.put({'error': {'message': 'Codex app-server 已断开'}})

    def send(self, r):
        with self.write_lock:
            self.proc.stdin.write(json.dumps(r, ensure_ascii=False) + '\n')
            self.proc.stdin.flush()

    def call(self, method, params=None, timeout=60):
        with self.lock:
            self.seq += 1
            seq = self.seq
            wait = queue.Queue()
            self.pending[seq] = wait
        try:
            r = {'id': seq, 'method': method}
            if params is not None:
                r['params'] = params
            self.send(r)
            response = wait.get(timeout=timeout)
            if 'error' in response:
                raise RpcError(response['error'])
            return response.get('result', {})
        finally:
            self.pending.pop(seq, None)

    def close(self):
        if self.proc.poll() is None:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                self.proc.terminate()
                self.proc.wait(timeout=5)
