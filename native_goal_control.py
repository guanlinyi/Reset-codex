"""Terminal text helpers; module name retained for source compatibility."""
import re

SGR=re.compile(r'\x1b\[([0-9;]*)m')

def plain(value):return SGR.sub('',value)

def blank_input(row,cursor_x):
    text=plain(row)
    if not text.startswith('› ') or cursor_x!=2:return False
    if not text[2:].strip():return True
    dim=False;offset=0;visible=[]
    for match in SGR.finditer(row):
        visible.extend((c,dim) for c in row[offset:match.start()]);codes=[int(c or 0) for c in match.group(1).split(';')]
        i=0
        while i<len(codes):
            code=codes[i]
            if code in (38,48,58) and i+1<len(codes):
                i+=5 if codes[i+1]==2 else 3;continue
            if code in (0,22):dim=False
            elif code==2:dim=True
            i+=1
        offset=match.end()
    visible.extend((c,dim) for c in row[offset:])
    return all(is_dim for c,is_dim in visible[2:] if not c.isspace())
