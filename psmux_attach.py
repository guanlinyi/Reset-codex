"""Real-terminal passthrough; scrub inherited noninteractive flags at final launch."""
import argparse
import os
import subprocess
import time
from desk_terminal import TerminalDesk, PSMUX, thread_id, write_json

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
    return subprocess.call([str(PSMUX),'attach','-t',record['session']],env=env)

if __name__=='__main__':raise SystemExit(main())
