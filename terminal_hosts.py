"""Host metadata for an explicitly selected native Codex process."""
import ctypes
import psutil
from pathlib import Path

def classify(args,parents):
    commands={'app-server','mcp-server','exec-server'}
    if any(a in commands or a.split('=')[0] in {'--app-server','--mcp-server','--exec-server'} for a in args[1:]):
        return 'service'
    names={name.lower() for name in parents}
    if 'psmux.exe' in names:return 'psmux'
    if names & {'code.exe','code - insiders.exe','vscodium.exe'}:return 'vscode'
    if names & {'powershell.exe','pwsh.exe','cmd.exe','windowsterminal.exe','openconsole.exe'}:return 'console'
    if names & {'chatgpt.exe','codex-desktop.exe'}:return 'service'
    return 'unknown'

def windows_for(identity,cwd=''):
    process=psutil.Process(int(identity['pid']))
    if abs(process.create_time()-float(identity['created']))>=.05:return []
    hosts={p.pid for p in process.parents() if p.name().lower() in
           {'code.exe','code - insiders.exe','vscodium.exe','windowsterminal.exe','openconsole.exe'}}
    if not hosts:return []
    user=ctypes.WinDLL('user32',use_last_error=True)
    user.GetWindowTextLengthW.argtypes=[ctypes.c_void_p]
    user.GetWindowTextW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_int]
    user.GetWindowThreadProcessId.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
    user.IsWindowVisible.argtypes=[ctypes.c_void_p]
    callback=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)
    user.EnumWindows.argtypes=[callback,ctypes.c_void_p]
    found=[]
    @callback
    def visit(hwnd,unused):
        pid=ctypes.c_ulong();user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        if pid.value in hosts and user.IsWindowVisible(hwnd):
            title=ctypes.create_unicode_buffer(user.GetWindowTextLengthW(hwnd)+1)
            user.GetWindowTextW(hwnd,title,len(title))
            if title.value:found.append({'hwnd':int(hwnd),'pid':pid.value,'title':title.value})
        return True
    user.EnumWindows(visit,None)
    if len(found)>1 and cwd:
        matching=[w for w in found if Path(cwd).name.casefold() in w['title'].casefold()]
        if len(matching)==1:return matching
    return found

def focus(identity,cwd=''):
    windows=windows_for(identity,cwd)
    if len(windows)!=1:
        raise ValueError('无法唯一定位原来的终端窗口；请在运行列表核对并结束该进程后重新打开，未新建重复 Codex。')
    # The PID/create-time and ancestor host were verified; this is a user-clicked action.
    user=ctypes.WinDLL('user32',use_last_error=True)
    user.ShowWindow.argtypes=[ctypes.c_void_p,ctypes.c_int]
    user.SetForegroundWindow.argtypes=[ctypes.c_void_p]
    user.ShowWindow(windows[0]['hwnd'],9)
    user.SetForegroundWindow(windows[0]['hwnd'])
