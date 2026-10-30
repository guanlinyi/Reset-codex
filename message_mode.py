"""Send one plain continuation message per verified quota round."""
import json,threading,time,uuid
from pathlib import Path
from desk_terminal import DATA,thread_id,write_json,TerminalError
from continuous_mode import Awake,ModeError,five_window,quota_blocked,recovered
from message_control import CONTINUE_MESSAGE

class ContinuousMode:
    def __init__(self,driver,path=None,clock=time.time):
        self.driver=driver;self.path=Path(path) if path else DATA/'continuous.json';self.clock=clock
        self.lock=threading.RLock();self.tick_lock=threading.Lock();self.cancel_event=threading.Event()
        self.pending_pause=False
        self.state={'enabled':False,'phase':'idle','recoveries_done':0,'recovery_limit':0,'shutdown_enabled':False}
        if self.path.exists():
            self.state.update(json.loads(self.path.read_text(encoding='utf-8')))
            if self.state.get('enabled') or self.state.get('phase')=='shutdown_pending':
                self.state.update(enabled=False,phase='needs_attention',reason='service_restarted',shutdown_at=None)
                self.save()
    def save(self):self.state['updated_at']=self.clock();write_json(self.path,self.state)
    def snapshot(self):
        with self.lock:return {k:v for k,v in self.state.items() if k!='baseline'}
    def start(self,tid,title,limit=0,shutdown=False,model='',effort='',command=CONTINUE_MESSAGE,auto_goal=True,auto_update=True):
        tid=thread_id(tid)
        if type(limit) is not int or not 0<=limit<=100:raise ModeError('恢复次数需为 0–100 的整数。')
        if type(shutdown) is not bool:raise ModeError('自动关机选项无效。')
        if type(auto_goal) is not bool or type(auto_update) is not bool:raise ModeError('弹窗处理选项无效。')
        if not isinstance(command,str) or not command.strip() or len(command)>2000 or any(ord(c)<32 and c not in '\n\r\t' for c in command):raise ModeError('请输入 1–2000 字的推进指令，不能包含终端控制字符。')
        with self.lock:
            if self.state.get('enabled'):raise ModeError('持续推进已经启动。')
            self.cancel_event.clear()
            self.state={'enabled':True,'phase':'starting','reason':'','thread_id':tid,'title':title,
                        'recovery_limit':limit,'recoveries_done':0,'shutdown_enabled':shutdown,
                        'model':model,'effort':effort,'command':command,'auto_goal':auto_goal,'auto_update':auto_update,'run_id':uuid.uuid4().hex,'started_at':self.clock(),
                        'native_dispatched':False,'messages_sent':0,'shutdown_at':None}
            self.save();return self.snapshot()
    def cancel(self):
        self.cancel_event.set()
        with self.lock:
            self.state.update(enabled=False,phase='cancelled',reason='user_cancelled',shutdown_at=None)
            self.save();return self.snapshot()
    def _stop(self,phase,reason,pause=False):
        self.state.update(enabled=False,phase=phase,reason=reason,shutdown_at=None,action_pending=False)
        self.pending_pause=False;self.save()
    def _exhausted(self,quota):
        if self.state['recoveries_done']>=self.state['recovery_limit']:
            if self.state.get('shutdown_enabled'):
                self.state.update(phase='awaiting_idle',reason='quota_exhausted',baseline=quota)
                self.save()
            else:self._stop('stopped','recovery_limit')
        else:
            self.state.update(phase='waiting_quota',reason='quota_exhausted',baseline=quota,
                              count_recovery=(five_window(quota) or {}).get('usedPercent',0)>=100,
                              wait_until=max([w.get('resetsAt') or 0 for w in quota.get('windows',[]) if w.get('usedPercent',0)>=100],default=None))
            self.save()
    def tick(self,quota):
        if not self.tick_lock.acquire(False):return
        try:self._tick(quota)
        finally:self.tick_lock.release()
    def _tick(self,quota):
        with self.lock:
            if not self.state.get('enabled') or self.cancel_event.is_set():return
            tid=self.state['thread_id'];run_id=self.state['run_id'];phase=self.state['phase']
            started=self.state.get('native_dispatched',False)
        if started:
            try:alive=self.driver.alive(tid)
            except Exception:alive=None
            if alive is False:
                with self.lock:
                    if self.state.get('run_id')==run_id:self._stop('stopped','terminal_closed')
                return
        valid=quota.get('available') and not quota.get('stale') and five_window(quota)
        with self.lock:
            if self.cancel_event.is_set() or not self.state.get('enabled'):return
            self.state['data_warning']=not bool(valid)
            if not valid:
                # Missing quota cannot trigger continuation or power actions.
                if phase=='shutdown_pending':self.state.update(phase='awaiting_idle',shutdown_at=None)
                self.save();return
            if phase in ('awaiting_idle','shutdown_pending'):
                if not quota_blocked(quota):
                    self._stop('stopped','shutdown_quota_changed');return
            elif phase=='waiting_quota':
                if (five_window(quota) or {}).get('usedPercent',0)>=100:
                    self.state.update(baseline=quota,count_recovery=True)
                if not recovered(self.state['baseline'],quota):self.save();return
                if self.state.get('count_recovery'):
                    a=five_window(self.state['baseline']);b=five_window(quota)
                    if not a or not b or not (b.get('usedPercent',100)<a.get('usedPercent',0) or (b.get('resetsAt') or 0)>(a.get('resetsAt') or 0)):return
                self.state.update(phase='resuming',reason='',action_pending=True);self.save()
            elif phase in ('starting','running'):
                if quota_blocked(quota):self._exhausted(quota);return
                if phase=='running':return
                self.state.update(phase='resuming',action_pending=True);self.save()
            else:return
        if phase in ('awaiting_idle','shutdown_pending'):
            try:idle=self.driver.idle(tid)
            except Exception:idle=False
            with self.lock:
                if self.cancel_event.is_set() or not self.state.get('enabled'):return
                if not idle:
                    self.state.update(phase='awaiting_idle',shutdown_at=None);self.save();return
                if not self.state.get('shutdown_at'):
                    self.state.update(phase='shutdown_pending',shutdown_at=self.clock()+60);self.save();return
                if self.clock()<self.state['shutdown_at']:return
            # Verify live official quota once more immediately before power-off.
            try:fresh=self.driver.quota()
            except Exception:fresh={}
            with self.lock:
                if self.cancel_event.is_set() or not self.state.get('enabled'):return
                if not fresh.get('available') or fresh.get('stale') or not quota_blocked(fresh):
                    self._stop('needs_attention','shutdown_quota_unconfirmed');return
                try:still_idle=self.driver.idle(tid)
                except Exception:still_idle=False
                if not still_idle:
                    self.state.update(phase='awaiting_idle',shutdown_at=None);self.save();return
                if self.cancel_event.is_set():return
                try:self.driver.power_off()
                except Exception:self._stop('needs_attention','shutdown_failed')
                else:self._stop('stopped','shutdown_requested')
            return
        try:
            self.driver.dispatch(tid,'continue',self.cancel_event)
            with self.lock:
                if self.cancel_event.is_set() or self.state.get('run_id')!=run_id:return
                if phase=='waiting_quota' and self.state.get('count_recovery'):self.state['recoveries_done']+=1
                self.state.update(phase='running',reason='',action_pending=False,native_dispatched=True,
                                  messages_sent=self.state.get('messages_sent',0)+1)
                self.save()
        except Exception as exc:
            with self.lock:
                if self.state.get('run_id')==run_id and not self.cancel_event.is_set():
                    self.state['last_error']=str(exc) if isinstance(exc,TerminalError) else '发送失败（'+type(exc).__name__+'）；请检查终端。'
                    self._stop('needs_attention','terminal_not_ready')
    def shutdown(self):
        self.cancel_event.set()
        with self.lock:
            if self.state.get('enabled'):self._stop('needs_attention','service_restarted')
