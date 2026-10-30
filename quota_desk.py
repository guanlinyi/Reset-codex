"""Quota Desk: read-only official metadata, explicitly requested native terminal opens."""
import argparse
import json
import os
import queue
import secrets
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from codex_rpc import Rpc, limits_view
from desk_terminal import DATA, ROOT, TerminalDesk, TerminalError, identity_alive, process_identity, thread_id, write_json
from desk_settings import SettingsError,SettingsStore,normalize,resolved
from message_mode import Awake,ContinuousMode,ModeError
from message_control import MessageControl

from app_config import RESOURCES,load,binary,network_environment
CHROME=binary('browser')
DEFAULT_PROXY=''

class Metadata:
    def __init__(self, proxy=DEFAULT_PROXY, rpc_factory=Rpc):
        self.proxy = proxy
        self.rpc_factory = rpc_factory
        self.rpc = None
        self.events = queue.Queue()
        self.lock = threading.RLock()
        self.quota = {'available': False, 'windows': []}
        self.threads = []
        self.cursor = None
        self.error = ''
        self.checked = 0
        self.models=[]
        self.models_error=''
        self.connected=False
        self.account_kind='unknown'
        self.error_code=''
        self.threads_error=''
        self.login_pending=False
        self.network_signature=None

    def connect(self):
        env = network_environment(self.proxy)
        signature=tuple(env.get(key) for key in ('HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy','ALL_PROXY','all_proxy'))
        if self.rpc and self.rpc.alive and signature==self.network_signature:
            return
        if self.rpc:
            self.rpc.close()
        self.rpc = self.rpc_factory(self.events, env=env)
        self.network_signature=signature
        self.connected=True

    def refresh(self):
        # Local titles must be available even when remote quota/model requests fail.
        for _ in range(100):
            try:event=self.events.get_nowait()
            except queue.Empty:break
            if event.get('method')=='account/login/completed':self.login_pending=False
        with self.lock:
            try:
                self.connect()
            except Exception:
                self.connected=False
                self.error_code='codex_missing' if not binary('codex').is_file() else 'connection_failed'
                self.error='无法连接本机 Codex。'
                self.quota={**self.quota,'available':False}
                return
            rpc=self.rpc
            self.error='';self.error_code=''
        try:
            account=rpc.call('account/read',{'refreshToken':False},timeout=5).get('account')
            with self.lock:
                self.account_kind=(account or {}).get('type','none')
                if self.account_kind=='chatgpt':self.login_pending=False
        except Exception:pass
        try:
            self.list_threads()
            with self.lock:self.threads_error=''
        except Exception:
            with self.lock:self.threads_error='threads_unavailable'
        try:self.list_models()
        except Exception:
            with self.lock:self.models_error='模型列表暂不可读，可保持默认。'
        try:
            quota=limits_view(rpc.call('account/rateLimits/read',timeout=15))
            with self.lock:self.quota=quota;self.checked=time.time()
        except Exception:
            with self.lock:
                self.quota={**self.quota,'available':False}
                self.error_code='login_required' if self.account_kind not in ('chatgpt','unknown') else 'quota_network'
                self.error='额度暂不可读；本地聊天目录仍可使用。'

    def list_models(self):
        with self.lock:
            self.connect();rpc=self.rpc
        rows=[];cursor=None
        for _ in range(5):
            params={'limit':100,'includeHidden':False}
            if cursor:params['cursor']=cursor
            result=rpc.call('model/list',params,timeout=10)
            for m in result.get('data',[]):
                if m.get('hidden') or not m.get('model'):continue
                rows.append({'model':m['model'],'name':m.get('displayName') or m['model'],
                             'default':bool(m.get('isDefault')),
                             'efforts':[e['reasoningEffort'] for e in m.get('supportedReasoningEfforts',[]) if e.get('reasoningEffort')]})
            cursor=result.get('nextCursor')
            if not cursor:break
        with self.lock:
            self.models=rows;self.models_error=''

    def list_threads(self, cursor=None):
        with self.lock:
            self.connect()
            rpc=self.rpc
        params = {'sourceKinds': ['cli'], 'sortKey': 'updated_at','sortDirection': 'desc', 'limit': 20}
        if load()['workspace']:params['cwd']=load()['workspace']
        if cursor:params['cursor']=cursor
        r=rpc.call('thread/list',params,timeout=10)
        rows=[]
        for t in r.get('data',[]):
            try:tid=thread_id(t['id'])
            except (ValueError,KeyError,TypeError):continue
            rows.append({'id':tid,'name':t.get('name') or '未命名聊天','cwd':t.get('cwd') or '','updatedAt':t.get('updatedAt')})
        with self.lock:
            known = {t['id']: t for t in self.threads} if cursor else {}
            known.update({t['id']: t for t in rows})
            self.threads = list(known.values())
            self.cursor = r.get('nextCursor')

    def read_title(self, tid):
        tid = thread_id(tid)
        with self.lock:
            self.connect()
            t = self.rpc.call('thread/read', {'threadId': tid, 'includeTurns': False}, timeout=25)['thread']
            if thread_id(t['id']) != tid:
                raise ValueError('聊天身份不一致')
            return {'id': tid, 'name': t.get('name') or '未命名聊天', 'cwd': t.get('cwd') or '',
                    'updatedAt': t.get('updatedAt')}

    def snapshot(self):
        with self.lock:
            stale = time.time()-self.checked > 150
            quota = dict(self.quota)
            quota['stale'] = stale
            if stale:
                quota['available'] = False
            return {'quota': quota, 'threads': list(self.threads), 'has_more': bool(self.cursor),
                    'error': self.error, 'checked_at': self.checked,
                    'models':list(self.models),'models_error':self.models_error,'connected':self.connected,
                    'account_kind':self.account_kind,'error_code':self.error_code,'threads_error':self.threads_error,
                    'login_pending':self.login_pending}

    def begin_login(self):
        from urllib.parse import urlparse
        with self.lock:
            self.connect()
            if self.account_kind=='chatgpt' or self.login_pending:return
            result=self.rpc.call('account/login/start',{'type':'chatgpt'},timeout=10)
            url=result.get('authUrl','')
            parsed=urlparse(url)
            if parsed.scheme!='https' or parsed.hostname not in ('auth.openai.com','chatgpt.com'):
                raise SettingsError('无法打开官方登录页面，请稍后重试。')
            os.startfile(url)
            self.login_pending=True

    def goal_state(self,tid):
        with self.lock:
            self.connect()
            goal=self.rpc.call('thread/goal/get',{'threadId':thread_id(tid)},timeout=8).get('goal')
            return {'exists':goal is not None,'status':goal.get('status') if goal else None}

    def pause_goal(self,tid,origin='user'):
        with self.lock:
            self.connect()
            return self.rpc.call('thread/goal/set',{'threadId':thread_id(tid),'status':'paused','origin':origin},timeout=8)

    def close(self):
        with self.lock:
            if self.rpc:
                self.rpc.close()

class Desk:
    def __init__(self, metadata=None, terminal=None,settings=None,mode_path=None):
        self.settings=settings or SettingsStore()
        self.metadata = metadata or Metadata(proxy=self.settings.snapshot()['effective']['proxy_url'])
        self.terminal = terminal or TerminalDesk()
        self.stopping = threading.Event()
        self.refreshing = threading.Lock()
        self.action_lock = threading.Lock()
        self.last_action = None
        self.terminal_inventory = {'items': [], 'checked_at': None}
        self.background_plan = None
        # Construction never starts tasks. Only the explicit Start endpoint arms this controller.
        self.mode=ContinuousMode(MessageControl(self),path=mode_path)
        from setup_actions import SetupActions
        self.setup=SetupActions(self)

    def state(self):
        result = self.metadata.snapshot()
        processes = self.terminal.scan()
        for t in result['threads']:
            t['terminal'] = self.terminal.inspect(t['id'], processes)
        result.update(terminal_inventory=self.terminal_inventory,last_action=self.last_action, automatic_recovery_enabled=self.mode.snapshot()['enabled'],
                      continuous=self.mode.snapshot(),source='Codex 官方账号额度',working_directory=load()['workspace'],preferences={k:load()[k] for k in ('language','thread_id','recovery_limit')},settings=self.settings.snapshot(),setup=self.setup.snapshot())
        return result

    def start_continuous(self,tid=None,limit=0,shutdown=False,model='',effort='',command=None,auto_goal=True,auto_update=True):
        with self.metadata.lock:
            rows=self.metadata.threads
            if tid:tid=thread_id(tid)
            elif rows:
                processes=self.terminal.scan()
                usable=next((t for t in rows if self.terminal.inspect(t['id'],processes).get('state') in ('running','shell','closed')),rows[0])
                tid=usable['id']
            if not tid:raise ModeError('尚无可用聊天，请稍后刷新。')
            thread=next((t for t in rows if t['id']==tid),None) or self.metadata.read_title(tid)
            options=normalize({'model':model,'effort':effort})
            if model and not any(m['model']==model for m in self.metadata.models):raise SettingsError('请选择当前列表中的模型，或留空不修改。')
            from message_control import CONTINUE_MESSAGE
            self.mode.start(tid,thread['name'],limit,shutdown=shutdown,model=options['model'],effort=options['effort'],command=CONTINUE_MESSAGE if command is None else command,auto_goal=auto_goal,auto_update=auto_update)
        quota=self.metadata.snapshot()['quota']
        if not quota.get('available') or quota.get('stale'):
            try:
                quota=self.mode.driver.quota()
                with self.metadata.lock:
                    self.metadata.quota=quota;self.metadata.checked=time.time()
            except Exception:pass
        # Attempt the first submission before acknowledging the Start action.
        # The worker uses the same tick lock, so it cannot submit a second copy.
        self.mode.tick(quota)
        state=self.mode.snapshot()
        if state.get('phase')=='needs_attention':raise ModeError(state.get('last_error') or '终端尚未就绪，命令没有确认发送。')
        return state

    def continuous_loop(self):
        awake=Awake()
        try:
            while not self.stopping.is_set():
                self.reap_closed_terminal()
                enabled=self.mode.snapshot()['enabled']
                try:awake.set(enabled)
                except OSError:
                    with self.mode.lock:
                        if enabled:self.mode._stop('needs_attention','keep_awake_failed',pause=True)
                self.mode.tick(self.metadata.snapshot()['quota'])
                self.stopping.wait(1)
        finally:
            self.mode.shutdown()
            awake.set(False)

    def reap_closed_terminal(self):
        snapshot=self.mode.snapshot()
        if not snapshot.get('enabled') or not snapshot.get('native_dispatched'):return
        tid=snapshot.get('thread_id')
        try:record=self.terminal.load(tid)
        except TerminalError:return
        if not record or not record.get('display_armed') or not record.get('close_on_disconnect'):return
        if identity_alive(record.get('shell',{})):return
        # Psmux ends its exact session on last-client disconnect, even without Reset running.
        # Stop the recovery controller before its next tick can reopen that conversation.
        self.mode.cancel_event.set()
        with self.mode.tick_lock:
            with self.mode.lock:
                if self.mode.state.get('run_id')==snapshot.get('run_id'):
                    self.mode._stop('stopped','terminal_closed');self.mode.pending_pause=False

    def save_settings(self,values):
        if not self.action_lock.acquire(False):raise SettingsError('正在打开终端，请稍后保存设置。')
        try:
            values=normalize(values)
            with self.metadata.lock:
                if values['model']:
                    model=next((m for m in self.metadata.models if m['model']==values['model']),None)
                    if not model:raise SettingsError('请选择当前 Codex 列表中的模型，或保持默认。')
                    if values['effort'] and values['effort'] not in model['efforts']:
                        raise SettingsError('所选模型不支持这个推理强度，请重新选择。')
                snapshot=self.settings.save(values)
                proxy=snapshot['effective']['proxy_url']
                if proxy!=self.metadata.proxy:
                    self.metadata.close();self.metadata.rpc=None;self.metadata.proxy=proxy
                    self.metadata.checked=0;self.metadata.error=''
            return snapshot
        finally:self.action_lock.release()

    def refresh(self):
        if not self.refreshing.acquire(False):
            return False
        try:
            self.metadata.refresh()
            return True
        finally:
            self.refreshing.release()

    def open_terminal(self, tid, allow_unidentified=False,model='',effort='',cancel=None,auto_goal=True,auto_update=True):
        tid = thread_id(tid)
        if not self.action_lock.acquire(False):
            raise TerminalError('正在处理一次打开请求，请稍候；不会重复打开。')
        try:
            # Always fetch the exact selected UUID; never silently select --last or same-title thread.
            thread = self.metadata.read_title(tid)
            options=self.settings.snapshot()['effective']
            requested=normalize({'model':model,'effort':effort})
            args=(thread,options['proxy_url'],requested['model'],requested['effort'])
            kwargs={'allow_unidentified':True} if allow_unidentified is True else {}
            if cancel is not None:kwargs['cancel']=cancel
            if not auto_update:kwargs['auto_update']=False
            result=self.terminal.open(*args,**kwargs)
            if model and result.get('action') in ('focused_existing','reused','revealed_existing'):
                MessageControl(self,auto_goal=auto_goal,auto_update=auto_update).switch_model(tid,model,effort,cancel)
            self.last_action = dict(result, title=thread['name'], at=time.time())
            write_json(DATA/'last_action.json', self.last_action)
            return result
        finally:
            self.action_lock.release()

    def loop(self):
        while not self.stopping.is_set():
            self.refresh()
            # Quota updated events from our read-only engine may arrive; polling is the fallback.
            self.stopping.wait(5 if self.metadata.login_pending else 60)

    def check_terminals(self):
        threads=self.metadata.snapshot()['threads']
        items=self.terminal.inventory(threads)
        for item in items:
            if item.get('thread_id') and item['name'].startswith('…'):
                try:item['name']=self.metadata.read_title(item['thread_id'])['name']
                except Exception:pass
        self.terminal_inventory={'items':items,'checked_at':time.time()}
        return self.terminal_inventory

    def close_terminal(self, tid, expected, confirmed=False, background=False):
        if confirmed is not True:
            raise TerminalError('请先确认结束所选终端；聊天记录会保留，当前运行和未提交输入会中断。')
        tid=thread_id(tid)
        def validate():
            record=self.terminal.validate_close(tid,expected)
            if background and self.terminal.call(record,'list-clients','-t',record['session']).strip():
                raise TerminalError('此终端已经连接前端，已跳过结束。')
        def close():
            return self.terminal.close(tid,expected,require_background=True) if background else self.terminal.close(tid,expected)
        return self._close_target(tid,validate,close)

    def _close_target(self,tid,validate,close):
        # Validate before cancellation, then validate again after pending dispatch completes.
        with self.terminal.lock:validate()
        with self.mode.lock:
            if tid and self.mode.state.get('thread_id')==tid:self.mode.cancel_event.set()
        if not self.mode.tick_lock.acquire(timeout=30):
            with self.mode.lock:
                if tid and self.mode.state.get('thread_id')==tid:
                    self.mode._stop('needs_attention','terminal_close_unconfirmed')
            raise TerminalError('正在处理目标，请稍后重新检查；没有结束终端。')
        try:
            if not self.action_lock.acquire(False):
                raise TerminalError('正在打开终端，请稍后重新检查；没有结束终端。')
            try:
                with self.mode.lock:
                    if tid and self.mode.state.get('thread_id')==tid:
                        self.mode.cancel_event.set()
                        self.mode._stop('stopped','terminal_close_unconfirmed')
                        self.mode.pending_pause=False
                    validate();result=close()
                    if tid and self.mode.state.get('thread_id')==tid:
                        self.mode._stop('stopped','terminal_closed')
                self.last_action=dict(result,at=time.time())
                return result
            finally:self.action_lock.release()
        finally:
            with self.mode.lock:
                if (self.mode.state.get('thread_id')==tid and self.mode.state.get('enabled')
                        and self.mode.cancel_event.is_set()):
                    self.mode._stop('needs_attention','terminal_close_unconfirmed')
            self.mode.tick_lock.release()

    def prepare_background_close(self):
        inventory=self.check_terminals()
        items=[dict(item) for item in inventory['items'] if item.get('can_close') and
               item.get('target_type')=='managed' and item.get('connection')=='background']
        self.background_plan={'id':secrets.token_hex(16),'at':time.time(),'items':items}
        return {'plan_id':self.background_plan['id'],'items':items}

    def close_background(self,plan_id,confirmed=False):
        plan=self.background_plan
        if confirmed is not True or not plan or plan_id!=plan['id'] or time.time()-plan['at']>90:
            raise TerminalError('请重新检查后台聊天并确认结束列表。')
        self.background_plan=None;closed=[];skipped=[]
        for item in plan['items']:
            try:
                self.close_terminal(item['thread_id'],item['close_token'],True,background=True)
                closed.append({'name':item['name'],'pid':item.get('pid')})
            except TerminalError:skipped.append({'name':item['name'],'pid':item.get('pid')})
        self.check_terminals()
        return {'closed':closed,'skipped':skipped}

class Server(ThreadingHTTPServer):
    daemon_threads = True

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def valid_host(self):
        return self.headers.get('Host') == '127.0.0.1:'+str(self.server.server_port)

    def authorized(self):
        if not self.valid_host():
            return False
        if not secrets.compare_digest(self.headers.get('X-Reset-Desk', ''), self.server.token):
            return False
        origin = self.headers.get('Origin')
        return not origin or origin == 'http://127.0.0.1:'+str(self.server.server_port)

    def reply(self, code, value, kind='application/json; charset=utf-8'):
        payload = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if not self.valid_host():
            self.reply(403, {'error': 'Forbidden'})
            return
        if self.path == '/':
            html = (RESOURCES/'desk_ui'/'index.html').read_text(encoding='utf-8').replace('__RESET_API_TOKEN__', self.server.token)
            self.reply(200, html.encode('utf-8'), 'text/html; charset=utf-8')
        elif self.path == '/fonts/NotoSansSC.ttf':
            self.reply(200, (RESOURCES/'fonts'/'NotoSansSC.ttf').read_bytes(), 'font/ttf')
        elif self.path in ('/assets/reset.png','/assets/reset.ico'):
            self.reply(200,(RESOURCES/self.path[1:]).read_bytes(),'image/png' if self.path.endswith('.png') else 'image/x-icon')
        elif self.path in ('/app.css', '/app.js','/setup.js'):
            kind = 'text/css; charset=utf-8' if self.path.endswith('.css') else 'text/javascript; charset=utf-8'
            self.reply(200, (RESOURCES/'desk_ui'/self.path[1:]).read_bytes(), kind)
        elif self.path == '/api/state' and self.authorized():
            self.reply(200, self.server.desk.state())
        else:
            self.reply(403, {'error': 'Forbidden'})

    def do_POST(self):
        if not self.authorized():
            self.reply(403, {'ok': False, 'error': '请求未获本机界面授权。'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length > 16384 or length < 0:
                raise ValueError('请求过大')
            data = json.loads(self.rfile.read(length) or b'{}')
            if self.path == '/api/refresh':
                self.server.desk.refresh()
                result = {'ok': True}
            elif self.path == '/api/more':
                m = self.server.desk.metadata
                with m.lock:
                    if m.cursor:
                        m.list_threads(m.cursor)
                result = {'ok': True}
            elif self.path == '/api/terminal/open':
                result = {'ok': True, **self.server.desk.open_terminal(data.get('thread_id'),data.get('allow_unidentified'),model=data.get('model') or '',effort=data.get('effort') or '')}
            elif self.path == '/api/terminal/check':
                result={'ok':True,'terminal_inventory':self.server.desk.check_terminals()}
            elif self.path == '/api/terminal/close':
                if data.get('target_type')=='process':
                    raise TerminalError('Reset 只管理自己的 Psmux 终端。')
                result={'ok':True,**self.server.desk.close_terminal(data.get('thread_id'),data.get('close_token'),data.get('confirmed'))}
            elif self.path == '/api/terminal/view':
                raise TerminalError('Reset 只管理自己的 Psmux 终端。')
            elif self.path == '/api/terminal/background/prepare':
                result={'ok':True,**self.server.desk.prepare_background_close()}
            elif self.path == '/api/terminal/background/close':
                result={'ok':True,**self.server.desk.close_background(data.get('plan_id'),data.get('confirmed'))}
            elif self.path == '/api/settings':
                result={'ok':True,'settings':self.server.desk.save_settings(data)}
                threading.Thread(target=self.server.desk.refresh,daemon=True).start()
            elif self.path == '/api/setup':
                result={'ok':True,**self.server.desk.setup.perform(data)}
            elif self.path == '/api/continuous/start':
                result={'ok':True,'continuous':self.server.desk.start_continuous(data.get('thread_id'),data.get('recovery_limit',0),shutdown=data.get('shutdown',False),model=data.get('model') or '',effort=data.get('effort') or '',command=data.get('command'),auto_goal=data.get('auto_goal',True),auto_update=data.get('auto_update',True))}
            elif self.path == '/api/continuous/cancel':
                result={'ok':True,'continuous':self.server.desk.mode.cancel()}
            else:
                self.reply(404, {'ok': False, 'error': '没有这个操作。'})
                return
            self.reply(200, result)
        except (ValueError, TerminalError) as exc:
            self.reply(400, {'ok': False, 'error': str(exc) if isinstance(exc, (TerminalError,SettingsError,ModeError)) else '请选择有效聊天后再试。'})
        except Exception:
            self.reply(500, {'ok': False, 'error': '本次操作未完成，请查看终端或刷新；工具不会自动重复发送命令。'})

def app_window(port):
    from desk_panel import open_panel
    return open_panel(port, DATA, CHROME)

def launch_report(path, result):
    if not path:
        return
    path = Path(path).resolve()
    if not path.is_relative_to((DATA/'launch_reports').resolve()):
        raise ValueError('启动结果路径必须位于本工具目录。')
    write_json(path, result)

def run_service(server, desk, open_requested=False, report_path=None):
    worker = threading.Thread(target=desk.loop, daemon=True)
    web = threading.Thread(target=lambda: server.serve_forever(poll_interval=.2), daemon=True)
    worker.start()
    mode_worker=None
    if hasattr(desk,'continuous_loop'):
        mode_worker=threading.Thread(target=desk.continuous_loop,daemon=True);mode_worker.start()
    # Serve the page before waiting for the browser's loaded page title.
    web.start()
    try:
        if open_requested:
            result = app_window(server.server_port)
            launch_report(report_path, {'ok': True, 'panel': result, 'checked_at': time.time()})
        while web.is_alive():
            web.join(timeout=1)
    finally:
        desk.stopping.set()
        server.shutdown()
        web.join(timeout=5)
        worker.join(timeout=35)
        if mode_worker:mode_worker.join(timeout=35)
        desk.metadata.close()
        server.server_close()

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--open', action='store_true')
    ap.add_argument('--headless', action='store_true')
    ap.add_argument('--launch-report')
    args = ap.parse_args(argv)
    DATA.mkdir(parents=True, exist_ok=True)
    # Persistent file + OS advisory lock. No deletion/rename; automatically released on process exit.
    import msvcrt
    lock = (DATA/'host.lock').open('a+b')
    if (DATA/'host.lock').stat().st_size == 0:
        lock.write(b'0'); lock.flush()
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        info = json.loads((DATA/'host.json').read_text(encoding='utf-8'))
        if not identity_alive(info.get('identity', {})):
            raise RuntimeError('面板登记暂不可确认，请稍后重试。')
        if args.open:
            result = app_window(info['port'])
            launch_report(args.launch_report, {'ok': True, 'panel': result, 'checked_at': time.time()})
        return
    desk = Desk()
    # Reuse the previous local URL on a cold restart when it is free, so an open
    # panel can reload without being routed to a dead service address.
    previous={}
    try:previous=json.loads((DATA/'host.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):pass
    previous_port=previous.get('port',0)
    if not isinstance(previous_port,int) or not 1024<=previous_port<=65535:previous_port=0
    try:server = Server(('127.0.0.1',previous_port), Handler)
    except OSError:server = Server(('127.0.0.1',0), Handler)
    server.desk = desk
    old_token=previous.get('token')
    server.token = old_token if previous_port==server.server_port and isinstance(old_token,str) and len(old_token)>=24 else secrets.token_urlsafe(32)
    write_json(DATA/'host.json', {'port': server.server_port, 'token': server.token,
                                'identity': process_identity(os.getpid())})
    try:
        run_service(server, desk, args.open, args.launch_report)
    finally:
        lock.close()

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        import sys
        if '--launch-report' in sys.argv:
            report = sys.argv[sys.argv.index('--launch-report')+1]
            # App metadata/provider errors are not dumped. These startup diagnostics are local only.
            message = str(exc) if isinstance(exc, RuntimeError) else '启动失败：'+type(exc).__name__
            launch_report(report, {'ok': False, 'error': message, 'checked_at': time.time()})
        raise
