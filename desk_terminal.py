"""One visible native Codex per pinned thread. Never submits a model task."""
import json
import os
import re
import subprocess
import threading
import time
import uuid
import hashlib
from pathlib import Path

import psutil
from terminal_hosts import classify
from terminal_permissions import process_integrity,file_integrity

from app_config import ROOT,DATA,RESOURCES,binary,command,load,network_environment
PSMUX=binary('psmux')
CODE=binary('vscode')
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
    env.update(TERM='xterm-256color', COLORTERM='truecolor', TERM_PROGRAM='vscode')
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
            ids = []
            if 'resume' in args:
                for arg in args[args.index('resume') + 1:]:
                    try:
                        ids.append(thread_id(arg))
                    except (ValueError, TypeError):
                        pass
            if not ids:
                try:
                    known=json.loads((DATA/'known_clients'/(str(p.pid)+'.json')).read_text(encoding='utf-8'))
                    if (known.get('source')=='codex_child_environment' and
                            abs(float(known['created'])-p.create_time())<.05):
                        ids=[thread_id(known['thread_id'])]
                except (OSError,ValueError,KeyError,TypeError):pass
            found.append({'pid': p.pid, 'created': p.create_time(), 'thread_ids': ids,
                          'host_kind':host,
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
            if not Path(record['workspace']).resolve().is_relative_to(directory):
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
                if outside or len(ours) > 1:
                    return {'state': 'conflict', 'label': '发现多个或其他终端持有此聊天'}
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
                        'target_type':'process','pid':target['pid'],
                        'identity':{k:target[k] for k in ('pid','created')},
                        'host_kind':target.get('host_kind','unknown'),
                        'can_close':True,'close_token':self.process_token(target)}
            return {'state': 'closed', 'label': '可新建终端',
                    'unidentified_pids':[p['pid'] for p in processes if p.get('unidentified')]}
        except (TerminalError, psutil.Error, OSError, subprocess.TimeoutExpired):
            return {'state': 'uncertain', 'label': '终端状态暂不可确认'}

    def viewer(self, record, thread):
        # Opening an already-open workspace does not rerun folderOpen tasks.
        # A fresh viewer attaches to the same backend, including after a panel was closed.
        viewer_id = uuid.uuid4().hex
        record.setdefault('close_on_disconnect',True)
        write_json(self.path(record['thread_id']),record)
        workspace = Path(record['directory']) / ('Viewer_'+viewer_id+'.code-workspace')
        title = str(thread.get('name') or '未命名聊天')
        # Root remains the requested working directory; only workspace JSON is written in this tool.
        doc = {'folders': [{'name': Path(thread['cwd']).name or 'Reset', 'path': thread['cwd']}],
               'settings': {'window.title': title.replace('${', '')+' · Reset终端',
                            'terminal.integrated.enablePersistentSessions': False,
                            'python.terminal.activateEnvironment': False},
               'tasks': {'version': '2.0.0', 'tasks': [{
                   'label': 'Reset：接回 '+title[:48], 'type': 'process',
                   'command': command('--attach',record['thread_id'])[0],
                   'args': command('--attach',record['thread_id'])[1:],
                   'options': {'cwd': thread['cwd'], 'env': {
                       'PSMUX_DATA_DIR': str(Path(record['directory'])/'registry'),
                       'PSMUX_CONFIG_FILE': str(Path(record['directory'])/'empty.conf'),
                       'PSMUX_NO_WARM': '1', 'TERM': 'xterm-256color', 'COLORTERM': 'truecolor',
                       'RESET_DATA_DIR': str(self.data), 'RESET_VIEWER_ID': viewer_id,
                       'NO_COLOR': None, 'CODEX_CI': None}},
                   'problemMatcher': [], 'runOptions': {'runOn': 'folderOpen', 'instanceLimit': 1},
                   'presentation': {'reveal': 'always', 'focus': True, 'panel': 'dedicated',
                                    'echo': False, 'showReuseMessage': False}}]}}
        # Workspace and task definitions stay inside this terminal namespace.
        write_json(workspace, doc)
        args = [str(CODE), '--new-window', str(workspace)]
        subprocess.Popen(args, cwd=ROOT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
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

    def close_token(self, record, state):
        value=[record['session'],record['pane'],record['shell'],state.get('identity')]
        return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

    def process_token(self, process):
        return hashlib.sha256(json.dumps([process['pid'],process.get('created'),process.get('thread_ids',[])],sort_keys=True).encode()).hexdigest()

    def process_target(self,pid,expected):
        target=next((p for p in self.scan() if p['pid']==pid and p.get('created')),None)
        if not target or target.get('host_kind')=='service' or self.process_token(target)!=expected or not identity_alive(target):
            raise TerminalError('所选进程已变化，请重新检查；没有结束或打开其他进程。')
        return target

    def view_process(self,pid,expected,cwd=''):
        target=self.process_target(pid,expected)
        from terminal_hosts import focus
        try:focus(target,cwd)
        except (ValueError,OSError,psutil.Error) as exc:raise TerminalError(str(exc)) from exc
        return {'action':'focused','pid':pid,'thread_id':next(iter(target.get('thread_ids',[])),None)}

    def close_process(self,pid,expected):
        with self.lock:
            target=self.process_target(pid,expected)
            process=psutil.Process(pid)
            if not identity_alive(target):raise TerminalError('进程已退出，请重新检查。')
            process.terminate()
            try:process.wait(timeout=5)
            except psutil.TimeoutExpired:raise TerminalError('已请求结束 Codex，但尚未确认退出，请重新检查。')
            return {'action':'closed','pid':pid,'thread_id':next(iter(target.get('thread_ids',[])),None)}

    def inventory(self, threads, processes=None):
        """Registry and process identities only; no terminal text or conversation bodies."""
        processes=self.scan() if processes is None else processes
        titles={t['id']:t for t in threads};ids=set(titles)
        for path in (self.data/'terminals').glob('*.json'):
            try:ids.add(thread_id(path.stem))
            except ValueError:pass
        for process in processes:ids.update(process.get('thread_ids',[]))
        rows=[];identified=set()
        for tid in sorted(ids):
            try:record=self.load(tid)
            except TerminalError:record=None
            matched=any(tid in p.get('thread_ids',[]) for p in processes)
            if not matched and (not record or not identity_alive(record.get('shell',{}))):continue
            state=self.inspect(tid,processes)
            if state['state']=='closed':continue
            known=titles.get(tid,{})
            row={'thread_id':tid,'name':known.get('name') or (record or {}).get('title') or '…'+tid[-8:],
                 'cwd':known.get('cwd') or (record or {}).get('cwd',''),
                 'state':state['state'],'connection':'unknown','can_open':False,'can_close':False}
            if record and state['state'] in ('running','shell'):
                try:row['connection']='attached' if self.call(record,'list-clients','-t',record['session']).strip() else 'background'
                except (TerminalError,subprocess.TimeoutExpired):pass
                row.update(can_open=True,can_close=True,close_token=self.close_token(record,state),
                           target_type='managed',
                           pid=state.get('identity',record['shell'])['pid'])
            elif state['state']=='external' and state.get('identity'):
                row.update(can_open=True,can_close=True,close_token=state['close_token'],
                           target_type='process',pid=state['pid'],host_kind=state.get('host_kind','unknown'))
            for p in processes:
                if tid in p.get('thread_ids',[]):identified.add(p['pid'])
            rows.append(row)
        for p in processes:
            if p['pid'] not in identified:
                rows.append({'thread_id':None,'name':'Codex · PID '+str(p['pid']),
                             'state':'external','connection':'unknown','can_open':bool(p.get('created')),
                             'can_close':bool(p.get('created')),'pid':p['pid'],'target_type':'process',
                             'close_token':self.process_token(p),'host_kind':p.get('host_kind','unknown')})
        return rows

    def validate_close(self, tid, expected):
        state=self.inspect(tid);record=self.load(tid)
        if not record or state['state'] not in ('running','shell'):
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
                  'workspace': str(directory/'Terminal.code-workspace'), 'registered_at': time.time()}
        self.call(record, '-f', directory/'empty.conf', 'new-session', '-d', '-s', session,
                  '-x', '150', '-y', '42', '-c', thread['cwd'], '--', POWERSHELL, '-NoLogo', '-NoProfile')
        time.sleep(.4)
        record.update(self.pane(record))
        if process_integrity(record['shell']['pid'])<(0x3000 if load()['require_admin'] else 0x2000):
            raise TerminalError('新终端未保持管理员完整性；没有启动 Codex。请从管理员 Reset 启动。')
        write_json(self.path(tid), record)
        return record

    def open(self, thread, proxy, model='', effort='', allow_unidentified=False):
        global CODE,CODEX,PSMUX
        CODE=binary('vscode');CODEX=binary('codex');PSMUX=binary('psmux')
        tid = thread_id(thread['id'])
        cwd = str(Path(thread.get('cwd') or '').resolve())
        if not thread.get('cwd') or not Path(cwd).is_dir():
            raise TerminalError('聊天的工作目录不存在，无法打开。')
        if not CODE.is_file() or not PSMUX.is_file() or not CODEX.is_file():
            raise TerminalError('缺少 VS Code、项目 Psmux 或官方 Codex，请检查安装路径。')
        thread = dict(thread, id=tid, cwd=cwd)
        with self.lock:
            state = self.inspect(tid)
            if state['state']=='external':return self.view_process(state['pid'],state['close_token'],cwd)
            if state['state'] in ('conflict', 'uncertain'):
                raise TerminalError(state['label']+'；没有另开 Codex。请先在原终端核实。')
            if state['state']=='closed' and state.get('unidentified_pids') and allow_unidentified is not True:
                return {'action':'confirm_new','thread_id':tid,'unidentified_pids':state['unidentified_pids']}
            record = self.load(tid) if state['state'] != 'closed' else self._new(thread)
            if state['state'] == 'running':
                viewer_id=self.viewer(record, thread)
                end=time.monotonic()+12
                while time.monotonic()<end:
                    if self.viewer_connected(tid,viewer_id):break
                    time.sleep(.2)
                else:
                    return {'action':'awaiting_viewer','thread_id':tid,'identity':state['identity']}
                return {'action': 'reused', 'message': '已请求 VS Code 接回同一个终端，没有启动新的 Codex。',
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
            viewer_id=self.viewer(record, thread)
            end = time.monotonic()+12
            while time.monotonic() < end:
                if self.viewer_connected(tid,viewer_id):
                    break
                time.sleep(.3)
            else:
                return {'action': 'awaiting_viewer', 'thread_id': tid,
                        'message': 'VS Code 终端已准备。若提示工作区信任或自动任务，请自行核对；接入后再点一次打开。尚未启动 Codex。'}
            # Ensure an already-started Codex cannot receive a PowerShell command as chat text.
            if self.inspect(tid)['state'] != 'shell':
                raise TerminalError('终端状态已变化，请刷新；没有发送启动命令。')
            screen = self.call(record, 'capture-pane', '-t', record['pane'], '-p')
            last = next((s.strip() for s in reversed(screen.splitlines()) if s.strip()), '')
            if not re.fullmatch(r'PS\s+[^\r\n]+>\s*', last):
                raise TerminalError('终端不是空白 PowerShell 提示符，可能有未提交输入；没有发送命令。')
            # Validated UUID and quoted fixed paths only; proxy comes from the user-provided local setting.
            parts = ['$env:NO_COLOR=$null', '$env:CODEX_CI=$null', "$env:TERM='xterm-256color'",
                     "$env:COLORTERM='truecolor'", "$env:TERM_PROGRAM='vscode'"]
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
                    return {'action': 'started', 'message': '已在 VS Code 终端恢复选中的聊天；没有发送任务或恢复目标。',
                            'thread_id': tid, 'identity': current['identity']}
                time.sleep(.3)
            raise TerminalError('启动命令已发送，但尚未确认 Codex 进程。请查看终端；不会自动重复发送。')
