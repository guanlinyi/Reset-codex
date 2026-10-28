"""Editable local overrides; blank proxy fields never invent a proxy or port."""
import ipaddress
import json
import re
import threading
from pathlib import Path
from app_config import ROOT,load,save_local

EMPTY={'model':'','effort':'','proxy_host':'','proxy_port':''}
class SettingsError(ValueError):pass

def normalize(values):
    if not isinstance(values,dict) or set(values)-set(EMPTY):raise SettingsError('Invalid settings')
    out={k:str(values.get(k) or '').strip() for k in EMPTY}
    for key in ('model','effort'):
        if out[key] and not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,119}',out[key]):raise SettingsError('Invalid '+key)
    if out['effort'] and not out['model']:raise SettingsError('Select a model before choosing effort')
    host=out['proxy_host']
    if host:
        try:ipaddress.ip_address(host)
        except ValueError:
            if len(host)>253 or not all(re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?',part) for part in host.split('.')):raise SettingsError('Invalid proxy host')
    port=out['proxy_port']
    if port and (not port.isdigit() or not 1<=int(port)<=65535):raise SettingsError('Proxy port must be between 1 and 65535')
    if bool(host)!=bool(port):raise SettingsError('Fill both proxy host and port, or leave both blank')
    if port:out['proxy_port']=str(int(port))
    return out

def resolved(values):
    out=normalize(values)
    host=out['proxy_host']
    out['proxy_url']=('http://'+('['+host+']' if ':' in host else host)+':'+out['proxy_port']) if host else ''
    return out

class SettingsStore:
    def __init__(self,path=None):self.path=Path(path) if path else None;self.lock=threading.RLock()
    def read(self):
        with self.lock:
            data=json.loads(self.path.read_text(encoding='utf-8')) if self.path and self.path.exists() else load() if self.path is None else EMPTY
            return normalize({k:data.get(k,'') for k in EMPTY})
    def snapshot(self):
        values=self.read()
        return {'values':values,'effective':resolved(values),'defaults':{'model':'Codex','effort':'Codex','proxy_host':'','proxy_port':''}}
    def save(self,values):
        values=normalize(values)
        with self.lock:
            if self.path:
                self.path.parent.mkdir(parents=True,exist_ok=True)
                self.path.write_text(json.dumps(values,indent=2),encoding='utf-8')
            else:save_local(values)
        return self.snapshot()
