"""User-clicked onboarding actions. No login, install, repair, or startup change on GET."""
import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import urllib.request
from app_config import ROOT,DATA,RESOURCES,binary,load,save_local
from desk_settings import SettingsError
from terminal_permissions import process_integrity,file_integrity

PACKAGES={'codex':'OpenAI.Codex','vscode':'Microsoft.VisualStudioCode'}

def choose_program(kind):
    # A normal file picker owned by the user's explicit Choose button.
    script="""Add-Type -AssemblyName System.Windows.Forms
[Console]::OutputEncoding=[Text.Encoding]::UTF8
$dialog=New-Object System.Windows.Forms.OpenFileDialog
$dialog.Filter='Executable files (*.exe)|*.exe'
$dialog.Title='Select PROGRAM executable'
if($dialog.ShowDialog() -eq 'OK'){[Console]::Write($dialog.FileName)}
""".replace('PROGRAM',kind)
    result=subprocess.run(['powershell.exe','-STA','-NoProfile','-Command',script],
        stdin=subprocess.DEVNULL,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
    path=result.stdout.decode('utf-8-sig').strip()
    if not path:return None
    chosen=Path(path)
    if not chosen.is_file() or chosen.suffix.lower()!='.exe':raise SettingsError('请选择可执行程序。')
    return str(chosen.resolve())

class SetupActions:
    def __init__(self,desk):
        self.desk=desk;self.installing='';self.result='';self.lock=threading.RLock()
        self.startup_enabled=False;self.startup_checked=0
    def snapshot(self):
        import startup
        from network import has_discovered_proxy
        if time.monotonic()-self.startup_checked>20:
            self.startup_enabled=startup.enabled()
            self.startup_checked=time.monotonic()
        deps={kind:binary(kind).is_file() for kind in ('codex','vscode','browser','psmux')}
        psmux=binary('psmux')
        try:permissions_ok=process_integrity(os.getpid())>=(0x3000 if load()['require_admin'] else 0x2000) and (not psmux.is_file() or file_integrity(psmux)>=0x2000)
        except OSError:permissions_ok=False
        return {'dependencies':deps,'permissions_ok':permissions_ok,'startup_enabled':self.startup_enabled,
                'installing':self.installing,'result':self.result,'winget_available':bool(shutil.which('winget.exe')),
                'proxy_source':'configured' if self.desk.settings.snapshot()['effective']['proxy_url'] else
                    'environment' if any(os.environ.get(k) for k in ('HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy','ALL_PROXY','all_proxy')) else
                    'system' if urllib.request.getproxies() else 'automatic' if has_discovered_proxy() else 'direct'}
    def perform(self,data):
        action=data.get('action')
        if action=='login':
            self.desk.metadata.begin_login()
            return {'status':'login_opened'}
        if action=='startup':
            import startup
            enabled=data.get('enabled')
            if type(enabled) is not bool:raise SettingsError('Invalid startup setting')
            startup.register(enabled)
            self.startup_enabled=enabled;self.startup_checked=time.monotonic()
            return {'status':'startup_saved'}
        if action=='choose':
            kind=data.get('kind')
            if kind not in PACKAGES:raise SettingsError('Invalid program')
            selected=choose_program(kind)
            if selected:save_local({kind+'_path':selected})
            threading.Thread(target=self.desk.refresh,daemon=True).start()
            return {'status':'program_selected' if selected else 'cancelled'}
        if action=='install':
            kind=data.get('kind')
            if kind not in PACKAGES or data.get('confirmed') is not True:raise SettingsError('Installation requires confirmation')
            winget=shutil.which('winget.exe')
            if not winget:
                os.startfile('https://learn.chatgpt.com/docs/quickstart' if kind=='codex' else 'https://code.visualstudio.com/Download')
                return {'status':'download_opened'}
            with self.lock:
                if self.installing:return {'status':'installing'}
                self.installing=kind;self.result=''
            threading.Thread(target=self._install,args=(winget,kind),daemon=True).start()
            return {'status':'installing'}
        if action=='repair':
            if data.get('confirmed') is not True:raise SettingsError('Repair requires confirmation')
            script=ROOT/'repair-permissions.ps1'
            if not script.is_file():raise SettingsError('Missing repair-permissions.ps1')
            # Explicit button confirmation only. The script has a fixed per-app file allowlist.
            args=subprocess.list2cmdline(['-NoProfile','-ExecutionPolicy','Bypass','-File',str(script)])
            result=ctypes.windll.shell32.ShellExecuteW(None,'runas','powershell.exe',args,str(ROOT),0)
            if result<=32:raise SettingsError('权限修复未获系统授权。')
            return {'status':'repair_started'}
        raise SettingsError('Unknown setup action')
    def _install(self,winget,kind):
        try:
            result=subprocess.run([winget,'install','--id',PACKAGES[kind],'--exact','--source','winget',
                '--accept-package-agreements','--accept-source-agreements','--disable-interactivity'],
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            with self.lock:self.result='install_done' if result.returncode==0 else 'install_failed'
        except Exception:
            with self.lock:self.result='install_failed'
        finally:
            with self.lock:self.installing=''
            self.desk.refresh()
