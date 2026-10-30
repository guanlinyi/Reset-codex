"""Shared quota predicates and Windows keep-awake support."""
import ctypes

class ModeError(ValueError):pass

def five_window(quota):
    return next((w for w in quota.get('windows',[]) if w.get('windowDurationMins')==300),None)

def quota_blocked(quota):
    return any(float(w.get('usedPercent',0))>=100 for w in quota.get('windows',[]))

def recovered(before,current):
    if not current.get('available') or current.get('stale') or quota_blocked(current):return False
    if not five_window(current):return False
    for a in before.get('windows',[]):
        b=next((w for w in current.get('windows',[]) if w.get('windowDurationMins')==a.get('windowDurationMins')),None)
        if b and (float(b.get('usedPercent',100))<float(a.get('usedPercent',0)) or
                  float(b.get('resetsAt') or 0)>float(a.get('resetsAt') or 0)):return True
    return False

class Awake:
    def __init__(self):self.enabled=False
    def set(self,enabled):
        if self.enabled==enabled:return
        # Must be called by the same worker thread for set and release.
        result=ctypes.windll.kernel32.SetThreadExecutionState(0x80000001 if enabled else 0x80000000)
        if not result:raise OSError('Cannot set execution state')
        self.enabled=enabled
