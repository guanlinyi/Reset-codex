"""Native goal monitoring with a bounded number of verified five-hour recoveries."""
import ctypes
import json
import threading
import time
import uuid
from pathlib import Path
from desk_terminal import DATA,thread_id,write_json

class ModeError(ValueError):pass

def five_window(quota):
    return next((w for w in quota.get('windows',[]) if w.get('windowDurationMins')==300),None)

def quota_blocked(quota):
    return any(float(w.get('usedPercent',0))>=100 for w in quota.get('windows',[]))

def recovered(before,current):
    if not current.get('available') or current.get('stale') or quota_blocked(current):return False
    if not five_window(current):return False
    for a in before.get('windows',[]):
        b=next((w for w in current.get('windows',[]) if w.get('windowDurationMins')==a.get('windowDurationMins')),None)
        if b and (float(b.get('usedPercent',100))<float(a.get('usedPercent',0)) or
                  float(b.get('resetsAt') or 0)>float(a.get('resetsAt') or 0)):return True
    return False

class Awake:
    def __init__(self):self.enabled=False
    def set(self,enabled):
        if self.enabled==enabled:return
        # Must be called by the same worker thread for set and release.
        result=ctypes.windll.kernel32.SetThreadExecutionState(0x80000001 if enabled else 0x80000000)
        if not result:raise OSError('Cannot set execution state')
        self.enabled=enabled

class ContinuousMode:
    def __init__(self,driver,path=None,clock=time.time):
        self.driver=driver;self.path=Path(path) if path else DATA/'continuous.json'
        self.clock=clock;self.lock=threading.RLock();self.tick_lock=threading.Lock()
        self.cancel_event=threading.Event();self.state={'enabled':False,'phase':'idle','recoveries_done':0,'recovery_limit':0}
        if self.path.exists():
            old=json.loads(self.path.read_text(encoding='utf-8'))
            self.state=old
            if old.get('enabled'):
                self.state.update(enabled=False,phase='needs_attention',reason='service_restarted')
                self.save()
        self.pending_pause=False

    def save(self):
        self.state['updated_at']=self.clock();write_json(self.path,self.state)
    def snapshot(self):
        with self.lock:
            return {k:v for k,v in self.state.items() if k not in ('baseline',)}
    def start(self,tid,title,limit=0):
        tid=thread_id(tid)
        if isinstance(limit,bool) or not isinstance(limit,int) or not 0<=limit<=100:
            raise ModeError('恢复次数需为 0–100 的整数。')
        with self.lock:
            if self.state.get('enabled') or self.pending_pause or self.state.get('phase')=='cancelling':
                raise ModeError('持续模式正在运行或取消中。')
            self.cancel_event.clear()
            self.state={'enabled':True,'phase':'starting','reason':'','thread_id':tid,'title':title,
                        'recovery_limit':limit,'recoveries_done':0,'run_id':uuid.uuid4().hex,
                        'started_at':self.clock(),'last_goal_status':None,'action_pending':False}
            self.save()
        return self.snapshot()
    def cancel(self):
        # Set before acquiring the state lock: a pending native dispatch sees cancellation.
        self.cancel_event.set()
        with self.lock:
            if self.state.get('enabled') or self.state.get('phase')=='needs_attention':
                self.state.update(enabled=False,phase='cancelling',reason='user_cancelled')
                self.pending_pause=True;self.save()
        return self.snapshot()

    def _stop(self,phase,reason,pause=False):
        self.state.update(enabled=False,phase=phase,reason=reason,action_pending=False)
        self.pending_pause=pause;self.save()
    def _wait(self,quota,reason):
        other_limit=any(w.get('windowDurationMins')!=300 and w.get('usedPercent',0)>=100 for w in quota.get('windows',[]))
        self.state.update(phase='waiting_quota',reason=reason,baseline=quota,
                          count_recovery=(five_window(quota) or {}).get('usedPercent',0)>=100 or
                                         (self.state.get('last_goal_status')=='usageLimited' and not other_limit),
                          waiting_since=self.clock(),wait_until=max(
                              [w.get('resetsAt') or 0 for w in quota.get('windows',[]) if w.get('usedPercent',0)>=100],
                              default=(five_window(quota) or {}).get('resetsAt')))
        self.save()

    def tick(self,quota):
        if not self.tick_lock.acquire(False):return
        try:self._tick(quota)
        finally:self.tick_lock.release()

    def _tick(self,quota):
        with self.lock:
            pause=self.pending_pause
            tid=self.state.get('thread_id')
            if pause:self.pending_pause=False
            enabled=self.state.get('enabled',False)
        if pause:
            try:
                self.driver.pause(tid)
                with self.lock:
                    if self.state['phase']=='cancelling':self.state['phase']='cancelled'
                    self.state['pause_confirmed']=True;self.save()
            except Exception:
                with self.lock:
                    self.state.update(phase='needs_attention',reason='pause_not_confirmed',pause_confirmed=False);self.save()
            return
        if not enabled:return
        try:goal=self.driver.goal(tid)
        except Exception:
            with self.lock:
                if self.state.get('enabled'):self.state.update(data_warning=True);self.save()
            return
        dispatch=None;run_id=None;first=False
        with self.lock:
            if not self.state.get('enabled') or self.cancel_event.is_set():return
            self.state.update(last_goal_status=goal.get('status'),data_warning=False)
            if goal.get('exists'):self.state['ever_had_goal']=True
            status=goal.get('status');phase=self.state['phase']
            if status=='complete':
                self._stop('complete','task_complete');return
            if phase!='starting' and self.state.get('ever_had_goal') and not goal.get('exists'):
                self._stop('needs_attention','goal_cleared');return
            if phase not in ('starting','resuming') and status in ('paused','blocked','budgetLimited'):
                self._stop('needs_attention','goal_'+status);return
            if not quota.get('available') or quota.get('stale') or not five_window(quota):
                self.state.update(data_warning=True);self.save();return
            if phase=='waiting_quota':
                if (five_window(quota) or {}).get('usedPercent',0)>=100 and not self.state.get('count_recovery'):
                    self.state.update(baseline=quota,count_recovery=True);self.save()
                if not recovered(self.state['baseline'],quota):return
                if self.state.get('count_recovery'):
                    a,b=five_window(self.state['baseline']),five_window(quota)
                    if not a or not b or not (b.get('usedPercent',100)<a.get('usedPercent',0) or
                                             (b.get('resetsAt') or 0)>(a.get('resetsAt') or 0)):return
                if self.state['recoveries_done']>=self.state['recovery_limit']:
                    self._stop('stopped','recovery_limit',pause=True);return
                if self.state.get('count_recovery'):self.state['recoveries_done']+=1
                dispatch='resume' if goal.get('exists') else 'start';self.state['phase']='resuming'
            elif phase=='starting':
                if quota_blocked(quota):
                    if not self.state['recovery_limit']:self._stop('stopped','quota_exhausted',pause=status=='active')
                    else:self._wait(quota,'quota_exhausted')
                    return
                dispatch='attach' if status=='active' else 'resume' if goal.get('exists') else 'start';first=True
            elif phase=='running' and (quota_blocked(quota) or status=='usageLimited'):
                if self.state['recoveries_done']>=self.state['recovery_limit']:
                    self._stop('stopped','recovery_limit',pause=True)
                else:self._wait(quota,'quota_exhausted')
                return
            elif phase=='resuming':
                # A dispatched command is never blindly repeated after uncertain confirmation.
                if status=='active':
                    self.state['phase']='running';self.state['action_pending']=False;self.save()
                elif status=='usageLimited' and quota_blocked(quota):
                    if self.state['recoveries_done']>=self.state['recovery_limit']:
                        self._stop('stopped','recovery_limit',pause=True)
                    else:self._wait(quota,'quota_exhausted')
                elif self.clock()-self.state.get('dispatch_at',self.clock())>45:
                    self._stop('needs_attention','resume_not_confirmed')
                return
            else:return
            self.state.update(action_pending=True,dispatch_at=self.clock())
            self.state['phase']='resuming';run_id=self.state['run_id'];self.save()
        try:
            self.driver.dispatch(tid,dispatch,self.cancel_event)
            with self.lock:
                if self.state.get('run_id')==run_id:
                    self.state['native_dispatched']=True;self.save()
        except Exception:
            with self.lock:
                if self.state.get('enabled') and self.state.get('run_id')==run_id:
                    self._stop('needs_attention','terminal_not_ready')

    def shutdown(self):
        # Never resume automatically across an application restart.
        self.cancel_event.set()
        with self.lock:
            if self.state.get('enabled'):self._stop('needs_attention','service_restarted',pause=True)
        self.tick({})
