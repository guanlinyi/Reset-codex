"""Handle the official startup updater in one verified visible Psmux pane."""
import re
import time

from native_goal_control import plain
from desk_terminal import TerminalError, identity_alive

_COMMANDS = (
    r'npm (?:i|install) -g @openai/codex(?:@(?:latest|\d+\.\d+\.\d+(?:[-.a-z0-9]*)))?',
    r'brew upgrade --cask codex',
    r'winget upgrade (?:--id )?OpenAI\.Codex(?: --exact)?',
)

def update_choice(screen, cursor_y):
    """Require a live numbered picker, version notice and official release URL."""
    lines=plain(screen).splitlines()
    if not 0<=cursor_y<len(lines):return None
    text='\n'.join(lines)
    if not re.search(r'Update available[^\n]*\d+\.\d+',text,re.I):return None
    if 'https://github.com/openai/codex/releases/latest' not in text:return None
    match=re.search(r'\b1\.\s*Update now \(runs `([^`]+)`\)',text)
    if not match:return None
    if not any(re.fullmatch(pattern,match.group(1),re.I) for pattern in _COMMANDS):return None
    start=text[:match.start()].count('\n')
    if not re.search(r'\b2\.\s*Skip(?:\s|$)',text):return None
    if not re.search(r'\b3\.\s*Skip until next version',text):return None
    heading=next((i for i,line in enumerate(lines) if re.search(r'Update available[^\n]*\d+\.\d+',line,re.I)),start)
    if not heading<=cursor_y<=start+8:return None
    tail='\n'.join(lines[start+3:])
    if re.search(r'Ask Codex|context left|^\s*PS\s+.+>',tail,re.M|re.I):return None
    return bool(re.search(r'[›❯>]\s*1\.\s*Update now',text))

def finish_startup(terminal,record,settle=2,timeout=180,cancel=None,auto_update=True):
    """Return normally without input when there is no confirmed update dialog."""
    from desk_terminal import write_json, resume_command
    import desk_terminal
    tid=record['thread_id'];end=time.monotonic()+settle
    updating=False;resumed=False;selection_pending=False;updated=False
    while time.monotonic()<end:
        if cancel is not None and cancel.is_set():raise TerminalError('已取消后续接续；正在执行的官方更新不会被强行中断。')
        current=terminal.load(tid)
        if not current or current['shell']!=record['shell'] or current['session']!=record['session']:
            raise TerminalError('更新期间终端登记已变化；没有重新启动 Codex。')
        if not identity_alive(record['shell']):
            raise TerminalError('聊天终端已关闭，停止更新接续。')
        if not terminal.call(record,'list-clients','-t',record['session']).strip():
            raise TerminalError('聊天窗口已断开，停止更新接续。')
        raw=terminal.call(record,'capture-pane','-t',record['pane'],'-p')
        cursor=terminal.call(record,'display-message','-p','-t',record['pane'],'#{cursor_x}|#{cursor_y}').strip()
        try:cx,cy=map(int,cursor.split('|'))
        except ValueError:raise TerminalError('无法确认更新界面的输入位置；请手动处理。')
        choice=update_choice(raw,cy)
        if choice is None:
            rows=plain(raw).splitlines()
            picker=next((i for i,line in enumerate(rows) if re.search(r'\b1\.\s*Update now',line)),None)
            if picker is not None and max(0,picker-4)<=cy<=picker+8 and not re.search(r'Ask Codex|^\s*PS\s+.+>', '\n'.join(rows[picker+3:]),re.M|re.I):
                raise TerminalError('检测到更新选项，但无法确认是支持的官方更新命令；请在原终端手动处理。')
        if choice is not None:
            if not auto_update:raise TerminalError('遇到 Codex 更新弹窗；未勾选自动更新，请手动处理后重试。')
            if updated:raise TerminalError('重新进入后仍提示更新，已停止自动重试，请查看终端。')
            if not updating:
                if not choice:
                    if not selection_pending:
                        terminal.call(record,'send-keys','-t',record['pane'],'Home')
                        selection_pending=True;end=time.monotonic()+3
                    time.sleep(.2);continue
                # Recheck the exact pane/process before selecting the official updater.
                if terminal.inspect(tid).get('state')!='running':
                    raise TerminalError('Codex 状态已变化，未提交更新。')
                record['update']={'phase':'updating','at':time.time()}
                write_json(terminal.path(tid),record)
                if cancel is not None and cancel.is_set():raise TerminalError('已取消。')
                terminal.call(record,'send-keys','-t',record['pane'],'Enter')
                updating=True;updated=True;selection_pending=False;end=time.monotonic()+timeout
            time.sleep(.25);continue
        if updating:
            state=terminal.inspect(tid)
            lines=plain(raw).splitlines()
            at_prompt=0<=cy<len(lines) and bool(re.fullmatch(r'\s*PS\s+[^\r\n]+>\s*',lines[cy])) and cx>=len(lines[cy].rstrip())
            success='Update ran successfully! Please restart Codex.' in '\n'.join(lines[-24:])
            if state.get('state')=='shell' and at_prompt:
                if not success:raise TerminalError('更新未确认成功，已停止；请查看终端中的更新结果。')
                pane=terminal.pane(record)
                if pane['shell']!=record['shell']:raise TerminalError('更新后的终端身份已变化；没有恢复会话。')
                # Resolve the executable again: an updater may replace a versioned path.
                desk_terminal.CODEX=desk_terminal.binary('codex')
                options=record.get('launch_settings',{})
                command=resume_command(tid,options.get('model',''),options.get('effort',''))
                record['update']={'phase':'resuming','at':time.time()}
                write_json(terminal.path(tid),record)
                if cancel is not None and cancel.is_set():raise TerminalError('已取消。')
                terminal.call(record,'send-keys','-t',record['pane'],'-l',command)
                if cancel is not None and cancel.is_set():
                    terminal.call(record,'send-keys','-t',record['pane'],'C-u')
                    raise TerminalError('已取消。')
                terminal.call(record,'send-keys','-t',record['pane'],'Enter')
                updating=False;resumed=True;end=time.monotonic()+12
            elif state.get('state') not in ('running','shell'):
                raise TerminalError('更新期间会话身份无法确认，已停止接续。')
        elif resumed:
            state=terminal.inspect(tid)
            if state.get('state')=='running':
                record['codex']=state['identity'];record['update']={'phase':'complete','at':time.time()}
                write_json(terminal.path(tid),record)
                # Watch the new process briefly for a repeated update prompt.
                resumed=False;end=time.monotonic()+settle
        time.sleep(.2)
    if updating or resumed or selection_pending:
        raise TerminalError('更新或恢复等待超时，请查看原终端；不会重复启动 Codex。')
