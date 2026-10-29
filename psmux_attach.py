"""Real-terminal passthrough; scrub inherited noninteractive flags at final launch."""
import argparse
import os
import subprocess
import time
from desk_terminal import TerminalDesk, PSMUX, thread_id, write_json, process_identity
import re

def arm_disconnect_policy(service,record):
    if not record.get('close_on_disconnect',True):return False
    # Arm only after a real client connected. An initial detached shell must survive startup.
    service.call(record,'set-option','-g','-t',record['session'],'destroy-unattached','on')
    value=service.call(record,'show-options','-g','-v','-t',record['session'],'destroy-unattached').strip()
    if value!='on':raise RuntimeError('Cannot confirm terminal disconnect policy; no Codex started.')
    return True

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('thread_id')
    args=parser.parse_args()
    tid=thread_id(args.thread_id)
    service=TerminalDesk()
    record=service.load(tid)
    if not record:
        raise RuntimeError('没有找到此聊天的终端登记；没有启动新的 Codex。')
    env=service.env(record)
    # VS Code's env:null is not sufficient evidence that an already-running task was scrubbed.
    # Build the final client environment here, after any editor/task environment processing.
    for key in ('NO_COLOR','CODEX_CI','CLICOLOR','CLICOLOR_FORCE','FORCE_COLOR'):
        env.pop(key,None)
    env.update(TERM='xterm-256color',COLORTERM='truecolor',TERM_PROGRAM='vscode')
    write_json(service.data/'client_env_evidence.json',{
        'at':time.time(),'thread_id':tid,'wrapper_pid':os.getpid(),
        'NO_COLOR_present':'NO_COLOR' in env,'CODEX_CI_present':'CODEX_CI' in env,
        'TERM':env['TERM'],'COLORTERM':env['COLORTERM']})
    # No captured pipes and no hidden engine: inherit VS Code's actual terminal stdio.
    child=subprocess.Popen([str(PSMUX),'attach','-t',record['session']],env=env)
    viewer_id=os.environ.get('RESET_VIEWER_ID','')
    connected=False;end=time.monotonic()+8
    while child.poll() is None and time.monotonic()<end:
        if service.call(record,'list-clients','-t',record['session']).strip():
            connected=True;break
        time.sleep(.2)
    if not connected:
        if child.poll() is None:child.terminate();child.wait(timeout=5)
        raise RuntimeError('Terminal attachment was not confirmed; no Codex started.')
    try:armed=arm_disconnect_policy(service,record)
    except Exception:
        if child.poll() is None:child.terminate();child.wait(timeout=5)
        raise
    if re.fullmatch(r'[a-f0-9]{32}',viewer_id) and child.poll() is None:
        # Evidence belongs to this request; stale clients cannot confirm a new viewer.
        write_json(service.data/'viewers'/tid/(viewer_id+'.json'),{
            'viewer_id':viewer_id,'client':process_identity(child.pid),'at':time.time(),
            'disconnect_policy_armed':armed})
    return child.wait()

if __name__=='__main__':raise SystemExit(main())
