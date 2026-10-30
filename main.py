"""Reset entry point shared by source, desktop EXE, and console terminal helper."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import sys

def main():
    parser=argparse.ArgumentParser(description='Reset: quota monitor and visible Codex continuation')
    parser.add_argument('--attach',metavar='THREAD_ID')
    parser.add_argument('--autostart',action='store_true')
    parser.add_argument('--install-startup',action='store_true')
    parser.add_argument('--disable-startup',action='store_true')
    parser.add_argument('--diagnose',action='store_true')
    parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--report',type=Path)
    parser.add_argument('--headless',action='store_true')
    parser.add_argument('--open',action='store_true')
    args=parser.parse_args()
    if sys.platform!='win32':raise RuntimeError('Windows 11 x64 is required')
    from app_config import ROOT,RESOURCES,DATA,load,command,binary
    from terminal_permissions import process_integrity,file_integrity
    if args.diagnose or args.smoke:
        details={'frozen':bool(getattr(sys,'frozen',False)),'admin':bool(ctypes.windll.shell32.IsUserAnAdmin()),
            'integrity':process_integrity(os.getpid()),'assets_present':all((RESOURCES/name).is_file() for name in ('assets/reset.ico','fonts/NotoSansSC.ttf','desk_ui/index.html')),
            'config_has_no_proxy_default':not load()['proxy_host'] and not load()['proxy_port'],
            'no_task_started':True}
        if args.diagnose:
            details['dependencies']={kind:{'found':binary(kind).is_file(),'low_integrity':file_integrity(binary(kind))<0x2000 if binary(kind).is_file() else None} for kind in ('codex','windows_terminal','browser','psmux')}
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True)
            args.report.write_text(json.dumps(details,indent=2),encoding='utf-8')
        if sys.stdout:print(json.dumps(details))
        return
    if load()['require_admin'] and process_integrity(os.getpid())<0x3000:
        # Do not pretend an elevated bit alone is sufficient when integrity is Low.
        if process_integrity(os.getpid())<0x2000:
            script=ROOT/'repair-permissions.ps1'
            answer=ctypes.windll.user32.MessageBoxW(None,
                'Windows has restricted this app file. Repair only this app executables and reopen Reset? No profile or Codex sandbox permissions will be changed.',
                'Reset: repair startup permissions',0x34)
            if answer!=6:return
            invocation=__import__('subprocess').list2cmdline(['-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),'-Restart'])
            if not script.is_file() or ctypes.windll.shell32.ShellExecuteW(None,'runas','powershell.exe',invocation,str(ROOT),0)<=32:
                raise RuntimeError('Repair was not authorized. Open repair-permissions.ps1 as administrator to retry.')
            return
        exe,*rest=command(*sys.argv[1:])
        result=ctypes.windll.shell32.ShellExecuteW(None,'runas',exe,__import__('subprocess').list2cmdline(rest),str(ROOT),1)
        if result<=32:raise RuntimeError('Administrator permission was not granted')
        return
    if args.attach:
        from psmux_attach import main as attach
        sys.argv=[sys.argv[0],args.attach]
        return attach()
    if args.install_startup or args.disable_startup:
        from startup import register
        return register(not args.disable_startup)
    if args.autostart:
        from startup import launch
        return launch()
    # Reuse only our own native ancestor's exported thread identity. Never inspect another process environment.
    if os.environ.get('CODEX_THREAD_ID'):
        try:
            from desk_terminal import register_current_client
            register_current_client()
        except Exception:pass
    from quota_desk import main as desktop
    return desktop(['--headless'] if args.headless else ['--open'])

if __name__=='__main__':
    try:main()
    except Exception as exc:
        # Never include conversation/provider/auth diagnostics in a dialog or log.
        message=str(exc) if isinstance(exc,(RuntimeError,ValueError)) else type(exc).__name__
        if sys.stderr:print(message,file=sys.stderr)
        else:ctypes.windll.user32.MessageBoxW(None,message,'Reset',0x10)
        raise SystemExit(1)
