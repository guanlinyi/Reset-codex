"""Explicit native TUI goal commands on the exact owned Psmux pane only."""
import re
import time
from desk_terminal import TerminalError,identity_alive

DEFAULT_OBJECTIVE='继续当前聊天中尚未完成的任务，完成后停止。保持电脑开机，不要关机、重启或休眠。'
SGR=re.compile(r'\x1b\[([0-9;]*)m')

def plain(value):return SGR.sub('',value)

def blank_input(row,cursor_x):
    text=plain(row)
    if not text.startswith('› ') or cursor_x!=2:return False
    if not text[2:].strip():return True
    dim=False;offset=0;visible=[]
    for match in SGR.finditer(row):
        visible.extend((c,dim) for c in row[offset:match.start()]);codes=[int(c or 0) for c in match.group(1).split(';')]
        i=0
        while i<len(codes):
            code=codes[i]
            if code in (38,48,58) and i+1<len(codes):
                i+=5 if codes[i+1]==2 else 3;continue
            if code in (0,22):dim=False
            elif code==2:dim=True
            i+=1
        offset=match.end()
    visible.extend((c,dim) for c in row[offset:])
    return all(is_dim for c,is_dim in visible[2:] if not c.isspace())

class NativeGoalControl:
    def __init__(self,desk):self.desk=desk
    def goal(self,tid):return self.desk.metadata.goal_state(tid)
    def record(self,tid):
        terminal=self.desk.terminal
        state=terminal.inspect(tid);record=terminal.load(tid)
        if state.get('state')!='running' or not record or not identity_alive(record.get('shell',{})):
            raise TerminalError('目标终端尚未就绪。')
        if not terminal.call(record,'list-clients','-t',record['session']).strip():
            raise TerminalError('目标终端尚未显示。')
        return record
    def dispatch(self,tid,action,cancel):
        if cancel.is_set():return
        terminal=self.desk.terminal
        # Opening uses the same guarded, explicit-UUID workflow as the UI.
        self.desk.open_terminal(tid)
        if cancel.is_set():return
        record=self.record(tid)
        if action=='attach':return
        end=time.monotonic()+8
        while time.monotonic()<end:
            if cancel.is_set():return
            raw=terminal.call(record,'capture-pane','-e','-t',record['pane'],'-p')
            screen=plain(raw)
            if 'Resume paused goal?' in screen and action=='resume':
                terminal.call(record,'send-keys','-t',record['pane'],'Home')
                check=terminal.call(record,'capture-pane','-t',record['pane'],'-p')
                if not re.search(r'›\s*1\.\s*Resume goal',check):raise TerminalError('目标选择框状态需核实。')
                if cancel.is_set():return
                terminal.call(record,'send-keys','-t',record['pane'],'Enter');return
            cursor=terminal.call(record,'display-message','-p','-t',record['pane'],'#{cursor_x}|#{cursor_y}').strip()
            try:x,y=map(int,cursor.split('|'))
            except ValueError:raise TerminalError('无法确认终端输入位置。')
            rows=raw.splitlines()
            if 0<=y<len(rows) and blank_input(rows[y],x):
                command='/goal resume' if action=='resume' else '/goal '+DEFAULT_OBJECTIVE
                if cancel.is_set():return
                terminal.call(record,'send-keys','-t',record['pane'],'-l',command)
                if cancel.is_set():
                    terminal.call(record,'send-keys','-t',record['pane'],'C-u');return
                terminal.call(record,'send-keys','-t',record['pane'],'Enter');return
            time.sleep(.25)
        raise TerminalError('终端有输入或交互提示，请处理后再启动。')
    def pause(self,tid):
        # This is persisted goal control, not a new hidden model turn.
        reason=self.desk.mode.snapshot().get('reason')
        try:
            if self.goal(tid).get('exists'):
                self.desk.metadata.pause_goal(tid,origin='user' if reason=='user_cancelled' else 'automatic')
        except Exception:pass
        try:
            record=self.record(tid)
            self.desk.terminal.call(record,'send-keys','-t',record['pane'],'Escape')
            # Pause the native controller too; an independent metadata reader is
            # not assumed to update an already-loaded TUI's in-memory state.
            end=time.monotonic()+3
            while time.monotonic()<end:
                raw=self.desk.terminal.call(record,'capture-pane','-e','-t',record['pane'],'-p')
                cursor=self.desk.terminal.call(record,'display-message','-p','-t',record['pane'],'#{cursor_x}|#{cursor_y}').strip()
                try:x,y=map(int,cursor.split('|'))
                except ValueError:break
                rows=raw.splitlines()
                if 0<=y<len(rows) and blank_input(rows[y],x):
                    self.desk.terminal.call(record,'send-keys','-t',record['pane'],'-l','/goal pause')
                    self.desk.terminal.call(record,'send-keys','-t',record['pane'],'Enter');break
                time.sleep(.2)
        except TerminalError:pass
        end=time.monotonic()+3
        while time.monotonic()<end:
            goal=self.goal(tid)
            if not goal.get('exists') or goal.get('status') in ('paused','complete','blocked','budgetLimited','usageLimited'):return
            time.sleep(.2)
        raise TerminalError('尚未确认目标暂停。')
