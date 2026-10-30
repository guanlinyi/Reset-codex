"""Public defaults, optional local overrides, and machine-independent paths."""
import json
import os
from pathlib import Path
import shutil
import sys
import urllib.request

FROZEN=bool(getattr(sys,'frozen',False))
ROOT=Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
RESOURCES=Path(getattr(sys,'_MEIPASS',ROOT))
DATA=Path(os.environ.get('RESET_DATA_DIR') or (Path(os.environ.get('LOCALAPPDATA',Path.home()))/'Reset'))
DEFAULTS={'windows_terminal_path':'','codex_path':'','vscode_path':'','browser_path':'','psmux_path':'','workspace':'',
          'proxy_host':'','proxy_port':'','model':'','effort':'','thread_id':'','language':'zh',
          'recovery_limit':0,'require_admin':True,'startup_delay_seconds':10,'startup_open_vscode':False}

def load():
    values=dict(DEFAULTS)
    for path in (ROOT/'config.json',ROOT/'config.local.json',DATA/'config.local.json'):
        if path.is_file():
            obj=json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(obj,dict) or set(obj)-set(DEFAULTS):raise ValueError('Invalid configuration keys')
            values.update(obj)
    if values['language'] not in ('zh','en'):raise ValueError('language must be zh or en')
    if type(values['require_admin']) is not bool:raise ValueError('require_admin must be true or false')
    if type(values['recovery_limit']) is not int or not 0<=values['recovery_limit']<=100:raise ValueError('Invalid recovery_limit')
    if type(values['startup_delay_seconds']) is not int or not 0<=values['startup_delay_seconds']<=300:raise ValueError('Invalid startup delay')
    for key in ('windows_terminal_path','codex_path','vscode_path','browser_path','psmux_path','workspace','proxy_host','proxy_port','model','effort','thread_id'):
        if not isinstance(values[key],str):raise ValueError(key+' must be a string')
    return values

def save_local(changes):
    path=DATA/'config.local.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    old=json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
    old.update(changes)
    path.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def network_environment(override=''):
    env=os.environ.copy()
    if override:
        for key in list(env):
            if key.lower() in ('http_proxy','https_proxy'):env.pop(key)
        env.update(HTTP_PROXY=override,HTTPS_PROXY=override)
    else:
        proxies=urllib.request.getproxies()
        for protocol in ('http','https'):
            if proxies.get(protocol) and not any(env.get(key) for key in (protocol+'_proxy',protocol.upper()+'_PROXY')):
                env[protocol.upper()+'_PROXY']=proxies[protocol]
        if not any(env.get(key) for key in ('HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy','ALL_PROXY','all_proxy')):
            from network import local_proxy
            discovered=local_proxy()
            if discovered:env.update(HTTP_PROXY=discovered,HTTPS_PROXY=discovered)
    return env

def command(*args):
    if FROZEN:
        executable=ROOT/('ResetTerminal.exe' if args[:1]==('--attach',) else 'Reset.exe')
        return [str(executable),*args]
    return [sys.executable,'-B',str(ROOT/'main.py'),*args]

def binary(kind,required=False):
    configured=load().get(kind+'_path','')
    if configured:
        candidates=[Path(os.path.expandvars(configured)).expanduser()]
    else:
        candidates=[]
        if kind=='psmux':candidates=[RESOURCES/'vendor'/'psmux'/'psmux.exe']
        elif kind=='codex':
            found=shutil.which('codex.exe')
            if found:candidates.append(Path(found))
            launcher=shutil.which('codex.cmd')
            if launcher:
                npm=Path(launcher).parent/'node_modules'/'@openai'/'codex'
                candidates.extend(npm.glob('node_modules/@openai/codex-win32-*/vendor/*/bin/codex.exe'))
                candidates.extend(npm.glob('vendor/*/bin/codex.exe'))
            local=Path(os.environ.get('LOCALAPPDATA',''))
            candidates.extend([local/'Programs'/'OpenAI'/'Codex'/'bin'/'codex.exe',local/'Microsoft'/'WinGet'/'Links'/'codex.exe'])
            candidates.extend((local/'Microsoft'/'WinGet'/'Packages').glob('OpenAI.Codex*/codex.exe'))
        elif kind=='windows_terminal':
            found=shutil.which('wt.exe')
            if found:candidates.append(Path(found))
            candidates.append(Path(os.environ.get('LOCALAPPDATA',''))/'Microsoft/WindowsApps/wt.exe')
        elif kind=='browser':
            for base in ('ProgramFiles','ProgramFiles(x86)','LOCALAPPDATA'):
                folder=Path(os.environ.get(base,''))
                candidates += [folder/'Google'/'Chrome'/'Application'/'chrome.exe',folder/'Microsoft'/'Edge'/'Application'/'msedge.exe']
    for path in candidates:
        if path.is_file():return path.resolve()
    if required:raise RuntimeError('Cannot find '+kind+'. Set '+kind+'_path in config.local.json.')
    return RESOURCES/('missing-'+kind+'.exe')
