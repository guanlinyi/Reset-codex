"""Scan a public checkout for local state and obvious credential/path leaks."""
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
TEXT={'.py','.ps1','.cmd','.json','.md','.html','.js','.css','.svg','.txt','.gitignore'}
PATTERNS={
    'hardcoded_drive_path':re.compile(r'(?i)\b(?!C:[/\\]+Windows\b)[a-z]:[/\\]'),
    'personal_windows_profile':re.compile(r'(?i)[a-z]:[\\/]+Users[\\/]+(?!Public|Default)[^\\/\s"\']+'),
    'private_key':re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'api_key':re.compile(r'\bsk-[A-Za-z0-9_-]{24,}'),
    'proxy_credentials':re.compile(r'https?://[^\s/:"\']+:[^\s/@"\']+@'),
}
FORBIDDEN={'config.local.json','auth.json','host.json','continuous.json','last_action.json','ConsoleHost_history.txt'}

def audit(root=ROOT):
    findings=[]
    for path in root.rglob('*'):
        if not path.is_file() or '.git' in path.parts:continue
        relative=path.relative_to(root)
        if relative.parts[0]=='experiments':continue
        if '通俗进展日记' in path.name or path.name.startswith('HANDOFF_TECH_'):
            findings.append({'file':str(relative),'rule':'internal_document_not_for_publication'})
        if path.name in FORBIDDEN:findings.append({'file':str(relative),'rule':'local_runtime_or_credentials'})
        if path.suffix.lower() not in TEXT and path.name!='.gitignore':continue
        try:text=path.read_text(encoding='utf-8-sig')
        except UnicodeError:continue
        for name,pattern in PATTERNS.items():
            if pattern.search(text):findings.append({'file':str(relative),'rule':name})
    config=json.loads((root/'config.json').read_text(encoding='utf-8-sig'))
    for key in ('codex_path','vscode_path','browser_path','psmux_path','workspace','proxy_host','proxy_port','model','effort','thread_id'):
        if config.get(key):findings.append({'file':'config.json','rule':'nonempty_private_default:'+key})
    return findings

if __name__=='__main__':
    findings=audit()
    print(json.dumps({'passed':not findings,'findings':findings},ensure_ascii=False,indent=2))
    raise SystemExit(bool(findings))
