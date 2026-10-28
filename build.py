"""Build fresh portable output; existing output is never removed or overwritten."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--work-root',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'release')
    args=parser.parse_args()
    output=args.output.resolve()
    if (output/'Reset').exists():raise SystemExit('Output already exists. Choose a new --output directory; no files were removed.')
    work=(args.work_root or Path(tempfile.gettempdir())/('reset-build-'+uuid.uuid4().hex)).resolve()
    work.mkdir(parents=True,exist_ok=True)
    spec=work/'Reset.spec'
    spec.write_text('''from pathlib import Path
root=Path(ROOT_PATH)
a=Analysis([str(root/'main.py')],pathex=[str(root)],binaries=[],datas=[(str(root/'assets'),'assets'),(str(root/'fonts'),'fonts'),(str(root/'desk_ui'),'desk_ui'),(str(root/'vendor'),'vendor')],hiddenimports=[],hookspath=[],runtime_hooks=[],excludes=['tkinter','PIL','numpy','pandas','torch','playwright'],noarchive=False,optimize=1)
pyz=PYZ(a.pure)
desktop=EXE(pyz,a.scripts,[],exclude_binaries=True,name='Reset',debug=False,strip=False,upx=False,console=False,icon=str(root/'assets'/'reset.ico'))
terminal=EXE(pyz,a.scripts,[],exclude_binaries=True,name='ResetTerminal',debug=False,strip=False,upx=False,console=True,icon=str(root/'assets'/'reset.ico'))
collection=COLLECT(desktop,terminal,a.binaries,a.datas,strip=False,upx=False,name='Reset')
'''.replace('ROOT_PATH',repr(str(ROOT))),encoding='utf-8')
    subprocess.run([sys.executable,'-m','PyInstaller','--distpath',str(output),'--workpath',str(work/'analysis'),str(spec)],check=True,cwd=ROOT)
    bundle=output/'Reset'
    for name in ('config.json','repair-permissions.ps1','README.md','README.zh-CN.md','LICENSE','THIRD_PARTY_NOTICES.md','VALIDATION.md'):
        (bundle/name).write_bytes((ROOT/name).read_bytes())
    for path in (ROOT/'licenses').glob('*.txt'):(bundle/path.name).write_bytes(path.read_bytes())
    print(json.dumps({'portable_directory':str(bundle),'entry':'Reset.exe','terminal_helper':'ResetTerminal.exe'}))

if __name__=='__main__':main()
