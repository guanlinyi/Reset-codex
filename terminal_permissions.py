"""Read Windows integrity metadata; never alter tokens, files, or permissions."""
import ctypes as c
from ctypes import wintypes as w

kernel=c.WinDLL('kernel32',use_last_error=True)
adv=c.WinDLL('advapi32',use_last_error=True)
kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
kernel.CloseHandle.argtypes=[w.HANDLE]
kernel.LocalFree.argtypes=[w.HLOCAL]
adv.OpenProcessToken.argtypes=[w.HANDLE,w.DWORD,c.POINTER(w.HANDLE)]
adv.GetTokenInformation.argtypes=[w.HANDLE,w.DWORD,w.LPVOID,w.DWORD,c.POINTER(w.DWORD)]
adv.GetSidSubAuthorityCount.argtypes=[w.LPVOID];adv.GetSidSubAuthorityCount.restype=c.POINTER(c.c_ubyte)
adv.GetSidSubAuthority.argtypes=[w.LPVOID,w.DWORD];adv.GetSidSubAuthority.restype=c.POINTER(w.DWORD)
adv.GetNamedSecurityInfoW.argtypes=[w.LPWSTR,w.DWORD,w.DWORD,c.POINTER(w.LPVOID),c.POINTER(w.LPVOID),c.POINTER(w.LPVOID),c.POINTER(w.LPVOID),c.POINTER(w.LPVOID)]
adv.GetAce.argtypes=[w.LPVOID,w.DWORD,c.POINTER(w.LPVOID)]

def sid_rid(sid):
    count=adv.GetSidSubAuthorityCount(sid)[0]
    return adv.GetSidSubAuthority(sid,count-1)[0]

def process_integrity(pid):
    process=kernel.OpenProcess(0x1000,False,pid);token=w.HANDLE()
    if not process:raise c.WinError(c.get_last_error())
    try:
        if not adv.OpenProcessToken(process,8,c.byref(token)):raise c.WinError(c.get_last_error())
        size=w.DWORD();adv.GetTokenInformation(token,25,None,0,c.byref(size))
        buffer=c.create_string_buffer(size.value)
        if not adv.GetTokenInformation(token,25,buffer,size.value,c.byref(size)):raise c.WinError(c.get_last_error())
        return sid_rid(c.cast(buffer,c.POINTER(w.LPVOID))[0])
    finally:
        if token:kernel.CloseHandle(token)
        kernel.CloseHandle(process)

def file_integrity(path):
    sacl=w.LPVOID();descriptor=w.LPVOID()
    error=adv.GetNamedSecurityInfoW(str(path),1,0x10,None,None,None,c.byref(sacl),c.byref(descriptor))
    if error:raise c.WinError(error)
    try:
        if not sacl:return 0x2000
        class ACL(c.Structure):_fields_=[('revision',c.c_ubyte),('reserved',c.c_ubyte),('size',w.WORD),('count',w.WORD),('reserved2',w.WORD)]
        count=c.cast(sacl,c.POINTER(ACL)).contents.count
        for i in range(count):
            ace=w.LPVOID()
            if not adv.GetAce(sacl,i,c.byref(ace)):raise c.WinError(c.get_last_error())
            if c.cast(ace,c.POINTER(c.c_ubyte))[0]==0x11:return sid_rid(ace.value+8)
        return 0x2000
    finally:
        if descriptor:kernel.LocalFree(descriptor)
