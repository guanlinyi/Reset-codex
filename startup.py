"""Explicit optional logon registration; startup opens apps and never a conversation."""
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
from string import Template
from app_config import ROOT,DATA,command,load,binary

TASK='ResetDesktop'

def enabled():
    try:
        result=subprocess.run(['schtasks.exe','/Query','/TN',TASK,'/XML'],stdin=subprocess.DEVNULL,capture_output=True,
            timeout=3,creationflags=subprocess.CREATE_NO_WINDOW)
    except (OSError,subprocess.TimeoutExpired):return None
    if result.returncode:return False
    try:
        tree=ET.fromstring(result.stdout);ns={'t':'http://schemas.microsoft.com/windows/2004/02/mit/task'}
        args=command('--autostart')
        return (tree.findtext('.//t:Exec/t:Command',namespaces=ns)==args[0] and
                tree.findtext('.//t:Exec/t:Arguments',default='',namespaces=ns)==subprocess.list2cmdline(args[1:]) and
                tree.findtext('.//t:Settings/t:Enabled',default='true',namespaces=ns)!='false')
    except (ValueError,UnicodeError):return False

def open_editor():
    folder=load()['workspace']
    workspace=DATA/'startup.code-workspace'
    workspace.parent.mkdir(parents=True,exist_ok=True)
    workspace.write_text(json.dumps({'folders':[{'path':folder}] if folder else [],
        'settings':{'window.title':'Reset · VS Code','terminal.integrated.enablePersistentSessions':False}},ensure_ascii=False),encoding='utf-8')
    subprocess.Popen([str(binary('vscode',True)),'--new-window',str(workspace)],cwd=ROOT,
        stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)

def register(enabled=True):
    # The task is deliberately named separately from development installations.
    args=command('--autostart')
    quote=lambda value:"'"+str(value).replace("'","''")+"'"
    argline=subprocess.list2cmdline(args[1:])
    script="""$ErrorActionPreference='Stop'
$me=[Security.Principal.WindowsIdentity]::GetCurrent()
$old=Get-ScheduledTask -TaskName ${taskname} -TaskPath '\\' -ErrorAction SilentlyContinue
if($old -and ($old.Actions[0].Execute -ne ${executable} -or $old.Actions[0].Arguments -ne ${arguments} -or $old.Actions[0].WorkingDirectory -ne ${workingdir})){throw 'Task name already belongs to another app'}
${disable}
$action=New-ScheduledTaskAction -Execute ${executable} -Argument ${arguments} -WorkingDirectory ${workingdir}
$trigger=New-ScheduledTaskTrigger -AtLogOn -User $me.Name
$trigger.Delay='PT${delay}S'
$principal=New-ScheduledTaskPrincipal -UserId $me.User.Value -LogonType Interactive -RunLevel ${level}
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName ${taskname} -TaskPath '\\' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Open Reset and VS Code only; no conversation or goal' -Force | Out-Null
"""
    script=Template(script).safe_substitute(executable=quote(args[0]),arguments=quote(argline),workingdir=quote(ROOT),taskname=quote(TASK),
        delay=str(load()['startup_delay_seconds']),level='Highest' if load()['require_admin'] else 'Limited',
        disable='' if enabled else "if($old){Disable-ScheduledTask -TaskName "+quote(TASK)+" -TaskPath '\\' | Out-Null}; exit 0")
    result=subprocess.run(['powershell.exe','-NoLogo','-NoProfile','-NonInteractive','-Command',script],
        stdin=subprocess.DEVNULL,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:raise RuntimeError('Cannot update logon task. Run as administrator and check Task Scheduler.')

def launch():
    error=None
    if load()['startup_open_vscode']:
        try:open_editor()
        except Exception as exc:error=type(exc).__name__
    from quota_desk import main
    # No terminal-open, goal, or start endpoint is called here.
    main(['--open'])
