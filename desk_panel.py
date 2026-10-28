"""Window lifecycle for this application's own isolated browser profile only."""
import ctypes
import subprocess
import time
from pathlib import Path
import psutil

TITLE = 'Reset'

def panel_processes(profile):
    expected = '--user-data-dir='+str(Path(profile).resolve())
    ids = set()
    for p in psutil.process_iter(['name']):
        if (p.info['name'] or '').lower() not in ('chrome.exe','msedge.exe'):
            continue
        try:
            args = p.cmdline()
            if expected in args and any(a.startswith('--app=http://127.0.0.1:') for a in args):
                ids.add(p.pid)
        except psutil.Error:
            pass
    return ids

def panel_windows(profile):
    ids = panel_processes(profile)
    if not ids:
        return []
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
    user.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    user.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    user.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    user.IsWindowVisible.argtypes = [ctypes.c_void_p]
    user.IsIconic.argtypes = [ctypes.c_void_p]
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user.EnumWindows.argtypes = [callback_type, ctypes.c_void_p]
    result = []
    @callback_type
    def visit(hwnd, unused):
        pid = ctypes.c_ulong()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in ids:
            text = ctypes.create_unicode_buffer(user.GetWindowTextLengthW(hwnd)+1)
            cls = ctypes.create_unicode_buffer(128)
            user.GetWindowTextW(hwnd, text, len(text))
            user.GetClassNameW(hwnd, cls, len(cls))
            if text.value in (TITLE,'Reset · 额度与接续') and cls.value.startswith('Chrome_WidgetWin_'):
                result.append({'hwnd': int(hwnd), 'pid': pid.value,
                               'visible': bool(user.IsWindowVisible(hwnd)),
                               'minimized': bool(user.IsIconic(hwnd)), 'title': text.value})
        return True
    user.EnumWindows(visit, None)
    return result

def show_own_window(window):
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user.SetForegroundWindow.argtypes = [ctypes.c_void_p]
    user.ShowWindow(window['hwnd'], 9)  # Restore only our own verified application window.
    foreground = bool(user.SetForegroundWindow(window['hwnd']))
    return dict(window, visible=True, minimized=False, foreground_requested=foreground)

def open_panel(port, data, chrome):
    profile = Path(data)/'app_profile'
    windows = panel_windows(profile)
    if windows:
        return dict(show_own_window(windows[0]), action='reused')
    if not Path(chrome).is_file():
        raise RuntimeError('未找到 Chrome 或 Edge；请填写 config.local.json 的 browser_path。')
    profile.mkdir(parents=True, exist_ok=True)
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 1  # Explicitly visible; never inherit a hidden startup state.
    log = Path(data)/'panel_browser_start.txt'
    with log.open('a', encoding='utf-8') as output:
        child=subprocess.Popen([str(chrome), '--app=http://127.0.0.1:'+str(port)+'/',
                          '--user-data-dir='+str(profile), '--no-first-run',
                          '--no-default-browser-check', '--window-size=1080,1060'],
                         cwd=Path(data), startupinfo=startup,stdin=subprocess.DEVNULL,
                         stdout=output,stderr=output)
    end = time.monotonic()+18
    while time.monotonic()<end:
        windows = panel_windows(profile)
        if windows:
            return dict(show_own_window(windows[0]), action='opened')
        code=child.poll()
        if code not in (None,0):
            with log.open('a',encoding='utf-8') as output:
                output.write(time.strftime('%Y-%m-%d %H:%M:%S')+' browser_exit='+str(code)+'\n')
            raise RuntimeError('额度面板浏览器异常退出（'+str(code)+'），请查看 panel_browser_start.txt。')
        time.sleep(.25)
    with log.open('a',encoding='utf-8') as output:
        output.write(time.strftime('%Y-%m-%d %H:%M:%S')+' panel_timeout; browser_exit='+str(child.poll())+'\n')
    raise RuntimeError('后台已启动，但18秒内未检测到额度面板窗口。请查看 runtime\\quota_desk\\panel_browser_start.txt。')
