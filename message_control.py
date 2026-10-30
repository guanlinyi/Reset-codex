"""Verified plain-message input to one registered native Codex terminal."""
import re
import subprocess
import time
from desk_terminal import TerminalError,identity_alive
from native_goal_control import plain,blank_input

CONTINUE_MESSAGE='持续推进至额度耗尽，确认独立任务结束后保存交接'

def resume_dialog(screen):
    # Codex draws this modal over the existing screen. capture-pane may retain
    # transcript text to the left of the dialog, so choices need not start a row.
    title=re.search(r'Resume\s+paused\s+goal\?',screen,re.I)
    first=re.search(r'\b1\.\s*Resume\s+goal',screen,re.I)
    second=re.search(r'\b2\.\s*Leave\s+paused',screen,re.I)
    if not (title and first and second):return False
    row=lambda match:screen[:match.start()].count('\n')
    return 0<=row(first)-row(title)<=12 and 0<=row(second)-row(first)<=3

class MessageControl:
    def __init__(self,desk,auto_goal=True,auto_update=True):self.desk=desk;self.auto_goal=auto_goal;self.auto_update=auto_update
    def alive(self,tid):return self.desk.terminal.inspect(tid).get('state')=='running'
    def record(self,tid):
        t=self.desk.terminal;s=t.inspect(tid);r=t.load(tid)
        if s.get('state')!='running' or not r or not identity_alive(r.get('shell',{})):
            raise TerminalError('目标 Codex 终端尚未就绪。')
        if not t.call(r,'list-clients','-t',r['session']).strip():raise TerminalError('目标终端没有显示窗口。')
        return r
    def _screen(self,r):return self.desk.terminal.call(r,'capture-pane','-e','-t',r['pane'],'-p')
    def _blank(self,r):
        raw=self._screen(r)
        cursor=self.desk.terminal.call(r,'display-message','-p','-t',r['pane'],'#{cursor_x}|#{cursor_y}').strip()
        try:x,y=map(int,cursor.split('|'))
        except ValueError:return False
        rows=raw.splitlines()
        return 0<=y<len(rows) and blank_input(rows[y],x)
    def idle(self,tid):
        try:
            r=self.record(tid)
            footer='\n'.join(plain(self._screen(r)).splitlines()[-12:])
            if re.search(r'esc(?:ape)? to interrupt|\bworking\s*\(|\bthinking\s*\(',footer,re.I):return False
            return self._blank(r)
        except (TerminalError,OSError):return False
    def _ready(self,r,cancel,timeout=12):
        t=self.desk.terminal;end=time.monotonic()+timeout;blank_since=None
        while time.monotonic()<end:
            if cancel.is_set():raise TerminalError('已取消。')
            screen=plain(self._screen(r))
            if resume_dialog(screen) and not self._blank(r):
                if not self.auto_goal:raise TerminalError('遇到目标恢复弹窗；未勾选自动取消，请手动处理后重试。')
                blank_since=None
                t.call(r,'send-keys','-t',r['pane'],'Home')
                t.call(r,'send-keys','-t',r['pane'],'Down')
                selection_end=time.monotonic()+3
                while time.monotonic()<selection_end:
                    if cancel.is_set():raise TerminalError('已取消。')
                    check=plain(self._screen(r))
                    if re.search(r'[›>❯]\s*2\.\s*Leave\s+paused',check):break
                    if not resume_dialog(check) and self._blank(r):break
                    time.sleep(.1)
                else:raise TerminalError('没有确认选中 Leave paused；命令未发送。')
                if cancel.is_set():raise TerminalError('已取消。')
                if resume_dialog(check):t.call(r,'send-keys','-t',r['pane'],'Enter')
            elif self._blank(r):
                if blank_since is None:blank_since=time.monotonic()
                elif time.monotonic()-blank_since>=.6:return
            else:
                from codex_update import update_choice,finish_startup
                cursor=t.call(r,'display-message','-p','-t',r['pane'],'#{cursor_x}|#{cursor_y}').strip()
                try:_,y=map(int,cursor.split('|'))
                except ValueError:y=-1
                if update_choice(screen,y) is not None:
                    finish_startup(t,r,cancel=cancel,auto_update=self.auto_update)
                    end=time.monotonic()+timeout
                blank_since=None
            time.sleep(.2)
        raise TerminalError('终端有未提交输入或需要处理的提示；未覆盖输入，请处理后重试。')
    def _send(self,r,text,cancel):
        if cancel.is_set():raise TerminalError('已取消。')
        # A previous attempt may have left this exact requested command in the
        # composer. Submit that draft instead of refusing or duplicating it.
        if not text.startswith('/') and self._draft_matches(r,text) is True:
            self._submit(r,text,cancel)
            return
        self._ready(r,cancel)
        if cancel.is_set():raise TerminalError('已取消。')
        t=self.desk.terminal
        # Bracketed paste keeps multiline/custom input together. Wait for the
        # native paste handler to settle before sending a separate Enter.
        t.call(r,'send-keys','-t',r['pane'],'-l','\x1b[200~'+text+'\x1b[201~')
        echo_end=time.monotonic()+3
        while time.monotonic()<echo_end:
            screen=plain(self._screen(r))
            if resume_dialog(screen):raise TerminalError('输入过程中出现恢复目标弹窗；命令没有提交，请处理 Leave paused 后重试。')
            if re.sub(r'\s+','',text) in re.sub(r'\s+','',screen):break
            if cancel.is_set():break
            time.sleep(.1)
        else:raise TerminalError('输入内容尚未确认；没有提交或重复发送。')
        if cancel.is_set():
            t.call(r,'send-keys','-t',r['pane'],'C-u');raise TerminalError('已取消。')
        self._submit(r,text,cancel)

    def _submit(self,r,text,cancel):
        t=self.desk.terminal
        time.sleep(.4)
        if cancel.is_set():
            t.call(r,'send-keys','-t',r['pane'],'C-u');raise TerminalError('已取消。')
        t.call(r,'send-keys','-t',r['pane'],'Enter')
        if not text.startswith('/'):
            # A retained exact draft means the first Enter was absorbed by paste
            # handling. Retry only Enter, never paste the command a second time.
            for attempt in range(2):
                until=time.monotonic()+1.5
                while time.monotonic()<until:
                    if cancel.is_set():raise TerminalError('已取消后续接续。')
                    retained=self._draft_matches(r,text)
                    if retained is False:return
                    time.sleep(.15)
                if attempt==0:
                    if self._draft_matches(r,text) is not True:break
                    if cancel.is_set():raise TerminalError('已取消。')
                    t.call(r,'send-keys','-t',r['pane'],'Enter')
            raise TerminalError('指令仍留在输入框，未确认发送；请查看终端，没有重复输入指令。')

    def _draft_matches(self,r,text):
        rows=plain(self._screen(r)).splitlines()
        cursor=self.desk.terminal.call(r,'display-message','-p','-t',r['pane'],'#{cursor_x}|#{cursor_y}').strip()
        try:_,y=map(int,cursor.split('|'))
        except ValueError:raise TerminalError('无法确认指令是否提交；没有自动重发。')
        if not 0<=y<len(rows):raise TerminalError('无法确认指令是否提交；请查看终端。')
        for start in range(y,max(-1,y-32),-1):
            match=re.match(r'^\s*[›❯>] (.*)',rows[start])
            if match:
                draft=match.group(1)+''.join(line.strip() for line in rows[start+1:y+1])
                normalize=lambda value:re.sub(r'\s+','',value)
                if normalize(draft)==normalize(text):return True
                if not draft.strip() or self._blank(r):return False
                return None
        if re.search(r'esc(?:ape)? to interrupt|\bworking\s*\(|\bthinking\s*\(|\bqueued\b','\n'.join(rows[-12:]),re.I):return False
        return None
    @staticmethod
    def _norm(s):return re.sub(r'[^a-z0-9]','',s.lower())
    def switch_model(self,tid,model,effort='',cancel=None):
        import threading
        cancel=cancel or threading.Event()
        if not model:return
        r=self.record(tid);t=self.desk.terminal
        self._send(r,'/model',cancel);time.sleep(.35)
        catalog=self.desk.metadata.snapshot().get('models',[])
        label=next((m['name'] for m in catalog if m['model']==model),model)
        targets={self._norm(model),self._norm(label)}
        t.call(r,'send-keys','-t',r['pane'],'Home')
        seen=set();chosen=False
        for _ in range(80):
            if cancel.is_set():raise TerminalError('已取消。')
            screen=plain(self._screen(r))
            match=re.search(r'^\s*[›❯>]\s*(?:\d+\.\s*)?(.+)$',screen,re.M)
            selected=match.group(1).strip() if match else ''
            norm=self._norm(selected)
            if selected and any(norm.startswith(v) for v in targets):
                t.call(r,'send-keys','-t',r['pane'],'Enter');chosen=True;break
            if selected and selected in seen:break
            if selected:seen.add(selected)
            t.call(r,'send-keys','-t',r['pane'],'Down');time.sleep(.04)
        if not chosen:raise TerminalError('未能在模型菜单中确认所选模型，请在终端中处理；没有发送推进命令。')
        time.sleep(.25)
        screen=plain(self._screen(r))
        if re.search(r'select.*reasoning|reasoning effort',screen,re.I) and not self._blank(r):
            if effort:
                t.call(r,'send-keys','-t',r['pane'],'Home')
                for _ in range(12):
                    screen=plain(self._screen(r));m=re.search(r'^\s*[›❯>]\s*(?:\d+\.\s*)?(.+)$',screen,re.M)
                    choices={'xhigh':('xhigh','extrahigh'),'minimal':('minimal',),'low':('low',),'medium':('medium',),'high':('high',),'max':('max',),'ultra':('ultra',)}.get(effort,(effort,))
                    if m and any(self._norm(m.group(1)).startswith(self._norm(v)) for v in choices):break
                    t.call(r,'send-keys','-t',r['pane'],'Down');time.sleep(.04)
                else:raise TerminalError('无法确认推理强度，请在终端中选择。')
            t.call(r,'send-keys','-t',r['pane'],'Enter')
        self._ready(r,cancel)
        screen=plain(self._screen(r))
        if not any(v in self._norm(screen) for v in targets):raise TerminalError('模型切换尚未确认，请查看终端。')
    def dispatch(self,tid,action,cancel):
        state=self.desk.mode.snapshot()
        self.auto_goal=state.get('auto_goal',True);self.auto_update=state.get('auto_update',True)
        self.desk.open_terminal(tid,model=state.get('model',''),effort=state.get('effort',''),cancel=cancel,auto_goal=self.auto_goal,auto_update=self.auto_update)
        if cancel.is_set():return
        record=self.record(tid)
        self._send(record,state.get('command',CONTINUE_MESSAGE),cancel)
    def quota(self):
        from codex_rpc import limits_view
        m=self.desk.metadata
        with m.lock:m.connect();rpc=m.rpc
        return limits_view(rpc.call('account/rateLimits/read',timeout=15))
    def power_off(self):
        # Countdown lives in Reset; /t 0 avoids Windows' implicit force-close timeout.
        subprocess.run(['shutdown.exe','/s','/t','0'],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
