"""One visible native Codex per pinned thread. Never submits a model task."""
import json
import os
import re
import subprocess
import threading
import time
import uuid
import hashlib
import ctypes
from contextlib import contextmanager
from pathlib import Path

import psutil
from terminal_hosts import classify
from terminal_permissions import process_integrity,file_integrity

from app_config import ROOT,DATA,RESOURCES,binary,command,load,network_environment
PSMUX=binary('psmux')
CODE=binary('windows_terminal')
CODEX=binary('codex')
POWERSHELL=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32'/'WindowsPowerShell'/'v1.0'/'powershell.exe'

def thread_id(value):
    return str(uuid.UUID(str(value)))

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())

def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"

def resume_command(tid,model='',effort=''):
    from desk_settings import normalize
    options=normalize({'model':model,'effort':effort})
    args=[str(CODEX),'--no-daemon','resume']
    if options['model']:args+=['--model',options['model']]
    if options['effort']:args+=['--config','model_reasoning_effort='+json.dumps(options['effort'])]
    args.append(thread_id(tid))
    return '& '+' '.join(ps_quote(a) for a in args)

def color_environment():
    env = network_environment()
    for key in ('NO_COLOR', 'CODEX_CI', 'CLICOLOR', 'CLICOLOR_FORCE', 'FORCE_COLOR'):
        env.pop(key, None)
    env.update(TERM='xterm-256color', COLORTERM='truecolor', TERM_PROGRAM='Windows_Terminal')
    return env

def process_identity(pid):
    p = psutil.Process(int(pid))
    return {'pid': p.pid, 'created': p.create_time(), 'name': p.name()}

def identity_alive(identity):
    try:
        p = psutil.Process(int(identity['pid']))
        return abs(p.create_time() - float(identity['created'])) < .05 and p.is_running()
    except (psutil.Error, ValueError, KeyError, TypeError):
        return False

_file_identity_cache={}
_file_identity_lock=threading.Lock()

def open_session_ids(process):
    """Find rollouts persistently held for writing; one process may host several."""
    key=(process.pid,process.create_time());now=time.monotonic()
    with _file_identity_lock:
        cached=_file_identity_cache.get(key)
        if cached and now-cached[0]<5:return list(cached[1])
    home=Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex').resolve()/'sessions'
    def snapshot():
        ids=set()
        from session_handles import writable_files
        for filename in writable_files(process.pid):
            path=Path(filename)
            if not path.is_relative_to(home):continue
            match=re.fullmatch(r'rollout-.+-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl',path.name,re.I)
            if match:ids.add(thread_id(match.group(1)))
        return ids
    try:
        first=snapshot()
        # One Codex host can write a main conversation and related conversations.
        # Preserve every persistent writer identity instead of guessing one UUID.
        if first:
            time.sleep(.05)
            ids=sorted(first & snapshot())
        else:ids=[]
    except (psutil.Error,OSError,ValueError):ids=[]
    with _file_identity_lock:
        if len(_file_identity_cache)>128:_file_identity_cache.clear()
        _file_identity_cache[key]=(now,ids)
    return ids

def scan_codex():
    """Inspect command metadata only; never return command lines or environments."""
    found = []
    for p in psutil.process_iter(['pid', 'name', 'create_time']):
        if (p.info['name'] or '').lower() != 'codex.exe':
            continue
        try:
            args = p.cmdline()
            host=classify(args,[q.name() for q in p.parents()])
            if host=='service':
                continue
            ids = open_session_ids(p)
            source='open_session_file' if ids else ''
            if not ids and 'resume' in args:
                for arg in args[args.index('resume') + 1:]:
                    try:
                        ids.append(thread_id(arg))
                        source='resume_argument'
                    except (ValueError, TypeError):
                        pass
            if not ids:
                try:
                    known=json.loads((DATA/'known_clients'/(str(p.pid)+'.json')).read_text(encoding='utf-8'))
                    if (known.get('source')=='codex_child_environment' and
                            abs(float(known['created'])-p.create_time())<.05):
                        ids=[thread_id(known['thread_id'])]
                        source='codex_child_environment'
                except (OSError,ValueError,KeyError,TypeError):pass
            found.append({'pid': p.pid, 'created': p.create_time(), 'thread_ids': ids,
                          'host_kind':host,'identity_source':source,
                          'unidentified': not ids and 'exec' not in args})
        except (psutil.Error, OSError):
            found.append({'pid': p.pid, 'unidentified': True, 'thread_ids': []})
    return found

def register_current_client():
    """Only our own native ancestor and its exported UUID; no other process env read."""
    tid=thread_id(os.environ.get('CODEX_THREAD_ID'))
    for p in psutil.Process().parents():
        if p.name().lower()=='codex.exe':
            if classify(p.cmdline(),[q.name() for q in p.parents()])=='service':continue
            record={**process_identity(p.pid),'thread_id':tid,
                    'source':'codex_child_environment'}
            write_json(DATA/'known_clients'/(str(p.pid)+'.json'),record)
            return record
    raise TerminalError('当前操作不在原生 Codex 子进程中，不能登记。')

class TerminalError(ValueError):
    pass

@contextmanager
def thread_launch_lock(tid):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p]
    kernel.CreateMutexW.restype=ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
    kernel.ReleaseMutex.argtypes=[ctypes.c_void_p]
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.CreateMutexW(None,False,'Local\\ResetCodexThread_'+thread_id(tid))
    if not handle:raise TerminalError('无法锁定会话启动，请稍后重试。')
    acquired=False
    try:
        acquired=kernel.WaitForSingleObject(handle,0) in (0,0x80)
        if not acquired:raise TerminalError('这段会话正在打开，请稍候；不会重复启动。')
        yield
    finally:
        if acquired:kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)

class TerminalDesk:
    def __init__(self, data=DATA, process_scan=scan_codex):
        self.data = Path(data)
        self.data.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.scan = process_scan

    def path(self, tid):
        return self.data / 'terminals' / (thread_id(tid) + '.json')

    def load(self, tid):
        path = self.path(tid)
        if not path.exists():
            return None
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
            if record.get('thread_id') != thread_id(tid):
                raise ValueError('identity mismatch')
            # Registry files must never route terminal actions outside our namespaces.
            directory = Path(record['directory']).resolve()
            if not directory.is_relative_to(self.data.resolve()):
                raise ValueError('namespace outside project terminal registry')
            if not re.fullmatch(r'[a-zA-Z0-9_\-]+', record['session']):
                raise ValueError('invalid session name')
            if 'workspace' in record and not Path(record['workspace']).resolve().is_relative_to(directory):
                raise ValueError('workspace outside terminal namespace')
            if not re.fullmatch(r'%\d+', str(record.get('pane', ''))):
                raise ValueError('invalid pane identity')
            return record
        except (ValueError, OSError, KeyError, TypeError) as exc:
            raise TerminalError('终端登记暂不可读，请刷新；没有另开 Codex。') from exc

    def env(self, record):
        env = color_environment()
        directory = Path(record['directory'])
        env.update(PSMUX_DATA_DIR=str(directory/'registry'), PSMUX_NO_WARM='1',
                   PSMUX_CONFIG_FILE=str(directory/'empty.conf'))
        return env

    def call(self, record, *args):
        r = subprocess.run([str(PSMUX), *map(str, args)], cwd=ROOT, env=self.env(record),
                           capture_output=True, text=True, encoding='utf-8', errors='replace',
                           timeout=12, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if r.returncode:
            raise TerminalError('终端暂时无法连接；不会重复启动。')
        return r.stdout

    def pane(self, record):
        text = self.call(record, 'list-panes', '-t', record['session'], '-F', '#{pane_id}|#{pane_pid}')
        lines = [line.split('|') for line in text.strip().splitlines() if '|' in line]
        if len(lines) != 1:
            raise TerminalError('终端窗格数量变化，请先核实；不会猜测操作位置。')
        return {'pane': lines[0][0], 'shell': process_identity(int(lines[0][1]))}

    def inspect(self, tid, processes=None):
        tid = thread_id(tid)
        processes = self.scan() if processes is None else processes
        matches = [p for p in processes if tid in p.get('thread_ids', [])]
        try:
            record = self.load(tid)
            if record and identity_alive(record.get('shell', {})):
                pane = self.pane(record)
                if not identity_alive(record['shell']) or pane['shell']['pid'] != record['shell']['pid']:
                    return {'state': 'uncertain', 'label': '终端身份需核实'}
                children = {p.pid for p in psutil.Process(record['shell']['pid']).children(recursive=True)}
                ours = [p for p in matches if p['pid'] in children]
                outside = [p for p in matches if p['pid'] not in children]
                if len(ours)>1:
                    return {'state':'conflict','label':'本终端内有多个 Codex，需核实后再操作'}
                if outside:
                    state={'state':'conflict','label':'同一会话还在其他终端运行；结束仅关闭本软件登记的终端',
                           'outside_pids':[p['pid'] for p in outside]}
                    if ours:state['identity']={k:ours[0][k] for k in ('pid','created')}
                    return dict(state,pid=state.get('identity',record['shell'])['pid'],can_close=True,
                                target_type='managed',close_token=self.close_token(record,state))
                if ours:
                    state={'state': 'running', 'label': '终端已连接', 'identity': {k: ours[0][k] for k in ('pid', 'created')}}
                    return dict(state,pid=state['identity']['pid'],can_close=True,target_type='managed',close_token=self.close_token(record,state))
                if any(p.get('unidentified') and p['pid'] in children for p in processes):
                    return {'state': 'uncertain', 'label': '终端内 Codex 身份需核实'}
                state={'state':'shell','label':'空闲终端 · Codex 已退出'}
                return dict(state,pid=record['shell']['pid'],can_close=True,target_type='managed',close_token=self.close_token(record,state))
            if matches:
                if len(matches)!=1:return {'state':'conflict','label':'此聊天由多个进程持有，请在运行列表按 PID 核对'}
                target=matches[0]
                return {'state': 'external', 'label': '已在其他终端运行',
                        'pid':target['pid'], 'can_close':False,'host_kind':target.get('host_kind','unknown')}
            # Unrelated clients without a known UUID are not evidence that this
            # particular conversation is running. Managed children remain checked above.
            return {'state': 'closed', 'label': '可新建终端'}
        except (TerminalError, psutil.Error, OSError, subprocess.TimeoutExpired):
            return {'state': 'uncertain', 'label': '终端状态暂不可确认'}

    def viewer(self, record, thread):
        viewer_id=uuid.uuid4().hex
        record.setdefault('close_on_disconnect',True)
        write_json(self.path(record['thread_id']),record)
        env=self.env(record)
        env.update(RESET_DATA_DIR=str(self.data),RESET_VIEWER_ID=viewer_id)
        args=[str(CODE),'-w','new','new-tab','--colorScheme','Campbell',
              '--title','Codex · '+record['thread_id'],'--suppressApplicationTitle',
              '--inheritEnvironment',*command('--attach',record['thread_id'])]
        subprocess.Popen(args,cwd=thread['cwd'],env=env)
        return viewer_id

    def viewer_connected(self, tid, viewer_id):
        try:
            evidence=json.loads((self.data/'viewers'/thread_id(tid)/(viewer_id+'.json')).read_text(encoding='utf-8'))
            if evidence.get('viewer_id')!=viewer_id or not identity_alive(evidence.get('client',{})):return False
            record=self.load(tid)
            connected=bool(record and self.call(record,'list-clients','-t',record['session']).strip())
            if connected and evidence.get('disconnect_policy_armed') and not record.get('display_armed'):
                record.update(display_armed=True,display_armed_at=time.time())
                write_json(self.path(tid),record)
            return connected
        except (OSError,ValueError,TypeError,TerminalError,subprocess.TimeoutExpired):
            return False

    def finish_startup(self, record, cancel=None,auto_update=True):
        from codex_update import finish_startup
        finish_startup(self, record,cancel=cancel,auto_update=auto_update)

    def close_token(self, record, state):
        value=[record['session'],record['pane'],record['shell'],state.get('identity')]
        return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

    def inventory(self, threads, processes=None):
        """Registry and process identities only; no terminal text or conversation bodies."""
        processes=self.scan() if processes is None else processes
        titles={t['id']:t for t in threads};ids=set()
        for path in (self.data/'terminals').glob('*.json'):
            try:ids.add(thread_id(path.stem))
            except ValueError:pass
        rows=[]
        for tid in sorted(ids):
            try:record=self.load(tid)
            except TerminalError:record=None
            if not record or not identity_alive(record.get('shell',{})):continue
            state=self.inspect(tid,processes)
            if state['state'] in ('closed','external'):continue
            known=titles.get(tid,{})
            row={'thread_id':tid,'name':known.get('name') or (record or {}).get('title') or '…'+tid[-8:],
                 'cwd':known.get('cwd') or (record or {}).get('cwd',''),
                 'state':state['state'],'connection':'unknown','can_open':False,'can_close':False}
            if record and (state['state'] in ('running','shell') or (state['state']=='conflict' and state.get('can_close'))):
                try:row['connection']='attached' if self.call(record,'list-clients','-t',record['session']).strip() else 'background'
                except (TerminalError,subprocess.TimeoutExpired):pass
                row.update(can_open=state['state']!='conflict',can_close=True,close_token=self.close_token(record,state),
                           target_type='managed',
                           pid=state.get('identity',record['shell'])['pid'],outside_pids=state.get('outside_pids',[]))
            rows.append(row)
        return rows

    def validate_close(self, tid, expected):
        state=self.inspect(tid);record=self.load(tid)
        if not record or (state['state'] not in ('running','shell') and not
                          (state['state']=='conflict' and state.get('can_close') and state.get('target_type')=='managed')):
            raise TerminalError('无法确认此终端归 Reset 管理；没有结束任何进程。')
        if not isinstance(expected,str) or self.close_token(record,state)!=expected:
            raise TerminalError('终端已变化，请重新检查列表后再确认；没有结束任何进程。')
        return record

    def close(self, tid, expected, require_background=False):
        with self.lock:
            record=self.validate_close(thread_id(tid),expected)
            if require_background and self.call(record,'list-clients','-t',record['session']).strip():
                raise TerminalError('此终端已经连接前端，已跳过结束。')
            self.call(record,'kill-session','-t',record['session'])
            end=time.monotonic()+5
            while identity_alive(record['shell']) and time.monotonic()<end:time.sleep(.1)
            if identity_alive(record['shell']):
                raise TerminalError('已请求结束，但尚未确认终端退出；请重新检查。')
            record['closed_at']=time.time()
            write_json(self.path(tid),record)
            return {'action':'closed','thread_id':tid}

    def _new(self, thread):
        try:
            if file_integrity(PSMUX)<0x2000:
                raise TerminalError('Psmux 程序被标记为低完整性，无法访问 Codex 用户目录；请运行 repair-permissions.ps1 后重试。没有启动 Codex。')
        except OSError as exc:
            raise TerminalError('无法核实 Psmux 程序安全标记；没有启动 Codex。') from exc
        tid = thread_id(thread['id'])
        directory = self.data/'sessions'/tid/('attempt_'+uuid.uuid4().hex)
        directory.mkdir(parents=True, exist_ok=True)
        (directory/'empty.conf').write_text('set -g warm off\n', encoding='utf-8')
        # Unique session per creation attempt; no stale process is killed or replaced.
        session = 'reset_'+tid.replace('-', '')[:16]+'_'+uuid.uuid4().hex[:6]
        record = {'thread_id': tid, 'directory': str(directory), 'session': session,
                  'close_on_disconnect': True,
                  'title': str(thread.get('name') or ''), 'cwd': thread['cwd'],
                  'registered_at': time.time()}
        self.call(record, '-f', directory/'empty.conf', 'new-session', '-d', '-s', session,
                  '-x', '150', '-y', '42', '-c', thread['cwd'], '--', POWERSHELL, '-NoLogo', '-NoProfile')
        time.sleep(.4)
        record.update(self.pane(record))
        if process_integrity(record['shell']['pid'])<(0x3000 if load()['require_admin'] else 0x2000):
            raise TerminalError('新终端未保持管理员完整性；没有启动 Codex。请从管理员 Reset 启动。')
        write_json(self.path(tid), record)
        return record

    def open(self, thread, proxy, model='', effort='', allow_unidentified=False,cancel=None,auto_update=True):
        global CODE,CODEX,PSMUX
        CODE=binary('windows_terminal');CODEX=binary('codex');PSMUX=binary('psmux')
        tid = thread_id(thread['id'])
        cwd = str(Path(thread.get('cwd') or '').resolve())
        if not thread.get('cwd') or not Path(cwd).is_dir():
            raise TerminalError('聊天的工作目录不存在，无法打开。')
        if not CODE.is_file() or not PSMUX.is_file() or not CODEX.is_file():
            raise TerminalError('缺少 Windows Terminal、项目 Psmux 或官方 Codex，请检查安装路径。')
        thread = dict(thread, id=tid, cwd=cwd)
        with self.lock,thread_launch_lock(tid):
            state = self.inspect(tid)
            if state['state']=='external':
                if state.get('host_kind')=='psmux':
                    raise TerminalError('此会话已在另一套 Psmux 中运行，但没有本软件可验证的接回登记；未新开终端。请先关闭原终端，再通过 Reset 打开。')
                raise TerminalError('此聊天已在 Reset 以外运行，原窗口不是本软件管理的 Psmux 终端。建议先关闭原 Codex，再用 Reset 打开；未启动重复进程。')
            if state['state'] in ('conflict', 'uncertain'):
                raise TerminalError(state['label']+'；没有另开 Codex。请先在原终端核实。')
            record = self.load(tid) if state['state'] != 'closed' else self._new(thread)
            if state['state'] == 'running':
                if self.call(record,'list-clients','-t',record['session']).strip():
                    from terminal_hosts import windows_for
                    from desk_panel import show_own_window
                    for path in (self.data/'viewers'/tid).glob('*.json'):
                        try:
                            client=json.loads(path.read_text(encoding='utf-8'))['client']
                            if not identity_alive(client):continue
                            all_windows=windows_for(client)
                            windows=[w for w in all_windows if tid in w['title']]
                            if not windows and len(all_windows)==1 and any(p.name().lower()=='windowsterminal.exe' for p in psutil.Process(client['pid']).parents()):
                                windows=all_windows
                            if len(windows)==1:
                                show_own_window(windows[0])
                                self.finish_startup(record,cancel=cancel,auto_update=auto_update)
                                return {'action':'focused_existing','thread_id':tid,'identity':state['identity']}
                        except TerminalError:raise
                        except (OSError,ValueError,KeyError,psutil.Error):continue
                    raise TerminalError('原终端仍在运行，但无法准确定位其窗口；未新开第二份，请先检查原终端。')
                viewer_id=self.viewer(record, thread)
                end=time.monotonic()+12
                while time.monotonic()<end:
                    if self.viewer_connected(tid,viewer_id):break
                    time.sleep(.2)
                else:
                    return {'action':'awaiting_viewer','thread_id':tid,'identity':state['identity']}
                self.finish_startup(record,cancel=cancel,auto_update=auto_update)
                return {'action': 'reused', 'message': '已请求 Windows Terminal 接回同一个终端，没有启动新的 Codex。',
                        'identity': state['identity'], 'thread_id': tid}
            # Native shell must still be the exact one registered by this tool.
            pane = self.pane(record)
            if not identity_alive(record['shell']) or pane['shell']['pid'] != record['shell']['pid']:
                raise TerminalError('终端进程已变化，停止启动。')
            try:level=process_integrity(record['shell']['pid'])
            except OSError as exc:raise TerminalError('无法确认终端权限；没有发送启动命令。') from exc
            if level<(0x3000 if load()['require_admin'] else 0x2000):
                # Rebuild only an empty, exited shell on the next explicit user click.
                screen=self.call(record,'capture-pane','-t',record['pane'],'-p')
                last=next((s.strip() for s in reversed(screen.splitlines()) if s.strip()),'')
                if not re.fullmatch(r'PS\s+[^\r\n]+>\s*',last):
                    raise TerminalError('旧终端权限不足且存在未提交输入；没有重建或发送命令。')
                if self.inspect(tid)['state']!='shell':
                    raise TerminalError('终端状态已变化；没有重建或发送命令。')
                write_json(self.data/'terminal_attempts'/(tid+'_'+uuid.uuid4().hex+'.json'),record)
                record=self._new(thread)
            if not self.call(record,'list-clients','-t',record['session']).strip():
                viewer_id=self.viewer(record, thread)
                end = time.monotonic()+12
                while time.monotonic() < end:
                    if self.viewer_connected(tid,viewer_id):
                        break
                    time.sleep(.3)
                else:
                    return {'action': 'awaiting_viewer', 'thread_id': tid,
                            'message': 'Windows Terminal 终端已准备。若提示终端窗口或权限，请自行核对；接入后再点一次打开。尚未启动 Codex。'}
            # Ensure an already-started Codex cannot receive a PowerShell command as chat text.
            if self.inspect(tid)['state'] != 'shell':
                raise TerminalError('终端状态已变化，请刷新；没有发送启动命令。')
            screen = self.call(record, 'capture-pane', '-t', record['pane'], '-p')
            last = next((s.strip() for s in reversed(screen.splitlines()) if s.strip()), '')
            if not re.fullmatch(r'PS\s+[^\r\n]+>\s*', last):
                raise TerminalError('终端不是空白 PowerShell 提示符，可能有未提交输入；没有发送命令。')
            # Validated UUID and quoted fixed paths only; proxy comes from the user-provided local setting.
            parts = ["$Host.UI.RawUI.BackgroundColor='Black'", 'Clear-Host', '$env:NO_COLOR=$null', '$env:CODEX_CI=$null', "$env:TERM='xterm-256color'",
                     "$env:COLORTERM='truecolor'", "$env:TERM_PROGRAM='Windows_Terminal'"]
            if proxy:
                parts += ['$env:HTTP_PROXY='+ps_quote(proxy), '$env:HTTPS_PROXY='+ps_quote(proxy)]
            parts += [resume_command(tid,model,effort)]
            record['start_requested_at'] = time.time()
            record['launch_settings']={'model':model,'effort':effort,'proxy':proxy}
            write_json(self.path(tid), record)
            self.call(record, 'send-keys', '-t', record['pane'], '-l', '; '.join(parts))
            time.sleep(.35)
            self.call(record, 'send-keys', '-t', record['pane'], 'Enter')
            end = time.monotonic()+10
            while time.monotonic() < end:
                current = self.inspect(tid)
                if current['state'] == 'running':
                    record['codex'] = current['identity']
                    write_json(self.path(tid), record)
                    self.finish_startup(record,cancel=cancel,auto_update=auto_update)
                    return {'action': 'started', 'message': '已在 Windows Terminal 终端恢复选中的聊天；没有发送任务或恢复目标。',
                            'thread_id': tid, 'identity': record['codex']}
                time.sleep(.3)
            raise TerminalError('启动命令已发送，但尚未确认 Codex 进程。请查看终端；不会自动重复发送。')
