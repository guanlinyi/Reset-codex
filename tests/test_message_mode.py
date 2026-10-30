import sys,uuid,unittest
from pathlib import Path
from app_config import DATA
EXP=DATA/'tests'
from message_mode import ContinuousMode
TID=str(uuid.UUID(int=100))
def quota(used=10,reset=1000):return {'available':True,'windows':[{'windowDurationMins':300,'usedPercent':used,'resetsAt':reset}]}
class Driver:
    def __init__(self):self.sent=0;self.powered=0;self.is_idle=True;self.present=True;self.fresh=quota(100)
    def dispatch(self,*args):self.sent+=1
    def alive(self,tid):return self.present
    def idle(self,tid):return self.is_idle
    def quota(self):return self.fresh
    def power_off(self):self.powered+=1
class Tests(unittest.TestCase):
    def make(self,limit=0,shutdown=False):
        d=Driver();now=[100.0];p=EXP/'runtime'/('mode_'+uuid.uuid4().hex+'.json')
        m=ContinuousMode(d,p,clock=lambda:now[0]);m.start(TID,'test',limit,shutdown);return m,d,now
    def test_zero_does_not_wait_or_power_without_optin(self):
        m,d,n=self.make();m.tick(quota());m.tick(quota());self.assertEqual(d.sent,1)
        m.tick(quota(100));m.tick(quota(0,2000));self.assertFalse(m.snapshot()['enabled']);self.assertEqual(d.sent,1);self.assertEqual(d.powered,0)
    def test_one_recovery_sends_exactly_once_then_finishes(self):
        m,d,n=self.make(1);m.tick(quota());m.tick(quota(100));self.assertEqual(m.snapshot()['phase'],'waiting_quota')
        m.tick(quota(100));self.assertEqual(d.sent,1)
        m.tick(quota(0,2000));m.tick(quota(10,2000));self.assertEqual(d.sent,2);self.assertEqual(m.snapshot()['recoveries_done'],1)
        m.tick(quota(100,2000));self.assertFalse(m.snapshot()['enabled']);self.assertEqual(d.powered,0)
    def test_shutdown_after_final_round_and_cancel(self):
        m,d,n=self.make(1,True);m.tick(quota());m.tick(quota(100));self.assertEqual(d.powered,0)
        m.tick(quota(0,2000));m.tick(quota(100,2000));m.tick(quota(100,2000));self.assertEqual(m.snapshot()['phase'],'shutdown_pending')
        m.cancel();n[0]+=100;m.tick(quota(100));self.assertEqual(d.powered,0)
    def test_shutdown_rechecks_idle_and_live_quota(self):
        m,d,n=self.make(0,True);m.tick(quota());m.tick(quota(100));d.is_idle=False;m.tick(quota(100));self.assertIsNone(m.snapshot()['shutdown_at'])
        d.is_idle=True;m.tick(quota(100));n[0]+=61;d.fresh=quota(50);m.tick(quota(100));self.assertEqual(d.powered,0)
    def test_optin_shutdown_uses_fake_power_only_after_countdown(self):
        m,d,n=self.make(0,True);m.tick(quota());m.tick(quota(100));m.tick(quota(100));self.assertEqual(d.powered,0)
        n[0]+=61;m.tick(quota(100));self.assertEqual(d.powered,1)
    def test_unreadable_quota_and_closed_terminal_never_resume(self):
        m,d,n=self.make(1);m.tick({});self.assertEqual(d.sent,0)
        m.tick(quota());m.tick(quota(100));d.present=False;m.tick(quota(0,2000));self.assertEqual(d.sent,1);self.assertFalse(m.snapshot()['enabled'])
    def test_leave_paused_is_confirmed_before_continuation_is_submitted(self):
        import threading
        from types import SimpleNamespace
        from message_control import MessageControl,CONTINUE_MESSAGE
        class Terminal:
            def __init__(self):self.modal=True;self.second=False;self.typed='';self.sent=[]
            def call(self,r,*args):
                if args[0]=='capture-pane':
                    return ('Resume paused goal?\n'+('  1. Resume goal\n› 2. Leave paused' if self.second else '› 1. Resume goal\n  2. Leave paused')) if self.modal else '› '+self.typed
                if args[0]=='display-message':return '2|0'
                if args[0]=='send-keys':
                    keys=args[3:];self.sent.append(keys)
                    if keys==('Down',):self.second=True
                    if keys==('Enter',) and self.modal:
                        self.assert_second=self.second;self.modal=False
                    elif keys and keys[0]=='-l':self.typed=keys[1].removeprefix('\x1b[200~').removesuffix('\x1b[201~')
                    elif keys==('Enter',):self.typed=''
                return ''
        t=Terminal();c=MessageControl(SimpleNamespace(terminal=t));c._blank=lambda r:not t.modal and not t.typed
        c._send({'pane':'%0'},CONTINUE_MESSAGE,threading.Event())
        self.assertTrue(t.assert_second)
        self.assertEqual(t.sent[:3],[('Home',),('Down',),('Enter',)])
        self.assertEqual(t.sent[3:], [('-l','\x1b[200~'+CONTINUE_MESSAGE+'\x1b[201~'),('Enter',)])
if __name__=='__main__':unittest.main()
