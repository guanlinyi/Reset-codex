"""Windows writable-file handle metadata; never reads file contents or process memory."""
import ctypes as c
from ctypes import wintypes as w

def writable_files(pid):
    class Entry(c.Structure):
        _fields_=[('object',c.c_void_p),('pid',c.c_size_t),('handle',c.c_size_t),
                  ('access',w.ULONG),('trace',w.USHORT),('kind',w.USHORT),
                  ('attributes',w.ULONG),('reserved',w.ULONG)]
    nt=c.WinDLL('ntdll');kernel=c.WinDLL('kernel32',use_last_error=True)
    nt.NtQuerySystemInformation.argtypes=[w.ULONG,c.c_void_p,w.ULONG,c.POINTER(w.ULONG)]
    nt.NtQuerySystemInformation.restype=w.LONG
    kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
    kernel.GetCurrentProcess.restype=w.HANDLE
    kernel.DuplicateHandle.argtypes=[w.HANDLE,w.HANDLE,w.HANDLE,c.POINTER(w.HANDLE),w.DWORD,w.BOOL,w.DWORD]
    kernel.GetFileType.argtypes=[w.HANDLE];kernel.GetFileType.restype=w.DWORD
    kernel.GetFinalPathNameByHandleW.argtypes=[w.HANDLE,w.LPWSTR,w.DWORD,w.DWORD]
    kernel.GetFinalPathNameByHandleW.restype=w.DWORD
    kernel.CloseHandle.argtypes=[w.HANDLE]
    size=1<<20
    while size<=64<<20:
        buffer=c.create_string_buffer(size);needed=w.ULONG()
        status=nt.NtQuerySystemInformation(64,buffer,size,c.byref(needed))
        if status==0:break
        if status!=-1073741820:raise OSError('Cannot inspect Windows handle metadata')
        size=max(size*2,needed.value+65536)
    else:raise OSError('Windows handle metadata exceeded size limit')
    source=kernel.OpenProcess(0x0040,False,int(pid))
    if not source:raise c.WinError(c.get_last_error())
    paths=[]
    try:
        count=c.cast(buffer,c.POINTER(c.c_size_t))[0]
        offset=2*c.sizeof(c.c_size_t)
        if offset+count*c.sizeof(Entry)>size:raise OSError('Invalid handle metadata size')
        entries=(Entry*count).from_buffer(buffer,offset)
        for entry in entries:
            # Examine only this process and handles with write-data/append access.
            if entry.pid!=pid or not entry.access&0x6:continue
            duplicate=w.HANDLE()
            if not kernel.DuplicateHandle(source,w.HANDLE(entry.handle),kernel.GetCurrentProcess(),c.byref(duplicate),0,False,2):continue
            try:
                if kernel.GetFileType(duplicate)!=1:continue  # Disk files only; skip pipes/devices.
                text=c.create_unicode_buffer(32768)
                length=kernel.GetFinalPathNameByHandleW(duplicate,text,len(text),0)
                if 0<length<len(text):
                    path=text.value
                    if path.startswith('\\\\?\\UNC\\'):path='\\\\'+path[8:]
                    elif path.startswith('\\\\?\\'):path=path[4:]
                    paths.append(path)
            finally:kernel.CloseHandle(duplicate)
    finally:kernel.CloseHandle(source)
    return paths
