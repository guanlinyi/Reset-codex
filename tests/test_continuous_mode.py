"""No model turns, real goal mutations, or power operations in these tests."""
import copy
import threading
import unittest
import uuid
from unittest.mock import Mock,patch
from continuous_mode import Awake,ContinuousMode,ModeError,recovered
from desk_terminal import ROOT,DATA
TID=str(uuid.UUID(int=1))
from native_goal_control import blank_input,NativeGoalControl

def quota(five=10,week=20,reset=100,week_reset=1000,available=True):
    return {'available':available,'stale':False,'windows':[
        {'windowDurationMins':300,'usedPercent':five,'resetsAt':reset},
        {'windowDurationMins':10080,'usedPercent':week,'resetsAt':week_reset}]}

class Driver:
    def __init__(self):self.status=None;self.commands=[];self.pauses=0;self.on_dispatch=None
    def goal(self,tid):return {'exists':self.status is not None,'status':self.status}
    def dispatch(self,tid,action,cancel):
        if self.on_dispatch:self.on_dispatch()
        if not cancel.is_set():self.commands.append(action);self.status='active'
    def pause(self,tid):self.pauses+=1;self.status='paused'

class ModeTests(unittest.TestCase):
    def setUp(self):
        self.driver=Driver();self.now=0
        self.path=DATA/'tests'/uuid.uuid4().hex/'continuous.json'
        self.mode=ContinuousMode(self.driver,self.path,lambda:self.now)
    def start(self,n):
        self.mode.start(TID,'测试聊天',n);self.mode.tick(quota());self.mode.tick(quota())
        self.assertEqual(self.mode.snapshot()['phase'],'running')
    def exhaust(self,reset):
        self.driver.status='usageLimited';self.mode.tick(quota(100,reset=reset))
    def recover(self,reset):
        self.mode.tick(quota(0,reset=reset));self.mode.tick(quota(0,reset=reset))

    def test_zero_stops_at_first_exhaustion(self):
        self.start(0);self.exhaust(100);self.mode.tick(quota(100));self.recover(200)
        self.assertFalse(self.mode.snapshot()['enabled']);self.assertEqual(self.driver.commands,['start'])
        self.assertEqual(self.driver.pauses,1)
    def test_exactly_one_recovery(self):
        self.start(1);self.exhaust(100)
        self.assertEqual(self.mode.snapshot()['phase'],'waiting_quota')
        self.recover(200);self.assertEqual(self.mode.snapshot()['recoveries_done'],1)
        self.exhaust(200);self.mode.tick(quota(100,reset=200));self.recover(300)
        self.assertEqual(self.driver.commands,['start','resume']);self.assertFalse(self.mode.snapshot()['enabled'])
    def test_exactly_two_recoveries(self):
        self.start(2)
        for i in range(2):self.exhaust(100+i*100);self.recover(200+i*100)
        self.assertEqual(self.mode.snapshot()['recoveries_done'],2)
        self.exhaust(300);self.mode.tick(quota(100,reset=300));self.recover(400)
        self.assertEqual(self.driver.commands,['start','resume','resume'])
    def test_clock_alone_cannot_trigger_resume(self):
        self.start(1);self.exhaust(100);self.now=10000
        for _ in range(4):self.mode.tick(quota(100,reset=100))
        self.assertEqual(self.driver.commands,['start'])
    def test_weekly_limit_blocks_five_hour_recovery(self):
        self.start(1);self.driver.status='usageLimited';self.mode.tick(quota(100,100))
        self.mode.tick(quota(0,100,reset=200))
        self.assertEqual(self.driver.commands,['start'])
        self.mode.tick(quota(0,0,reset=200,week_reset=2000));self.mode.tick(quota(0,0,reset=200,week_reset=2000))
        self.assertEqual(self.mode.snapshot()['recoveries_done'],1)
    def test_weekly_only_wait_does_not_spend_a_five_hour_recovery(self):
        self.start(1);self.driver.status='usageLimited';self.mode.tick(quota(10,100))
        self.mode.tick(quota(10,0,week_reset=2000));self.mode.tick(quota(10,0,week_reset=2000))
        self.assertEqual(self.mode.snapshot()['recoveries_done'],0)
        self.assertEqual(self.driver.commands,['start','resume'])
    def test_manual_pause_and_blockers_are_not_auto_retried(self):
        for status in ('paused','blocked','budgetLimited'):
            self.setUp();self.start(3);self.driver.status=status;self.mode.tick(quota());self.recover(200)
            self.assertFalse(self.mode.snapshot()['enabled']);self.assertEqual(self.driver.commands,['start'])
    def test_cancel_while_waiting_prevents_future_resume(self):
        self.start(2);self.exhaust(100);self.mode.cancel();self.mode.tick(quota(0,reset=200));self.recover(300)
        self.assertEqual(self.mode.snapshot()['phase'],'cancelled');self.assertEqual(self.driver.commands,['start'])
    def test_cancel_between_plan_and_dispatch_never_sends(self):
        self.driver.on_dispatch=self.mode.cancel
        self.mode.start(TID,'title',1);self.mode.tick(quota());self.mode.tick(quota())
        self.assertEqual(self.driver.commands,[]);self.assertFalse(self.mode.snapshot()['enabled'])
    def test_no_repeat_after_uncertain_command_result(self):
        def uncertain(*args):raise OSError('incomplete')
        self.driver.dispatch=uncertain
        self.mode.start(TID,'title',2);self.mode.tick(quota());self.mode.tick(quota())
        self.assertEqual(self.mode.snapshot()['reason'],'terminal_not_ready')
        self.assertFalse(self.mode.snapshot()['enabled'])
    def test_app_restart_requires_fresh_click(self):
        self.start(1);fresh=ContinuousMode(self.driver,self.path)
        fresh.tick(quota());self.assertFalse(fresh.snapshot()['enabled'])
        self.assertEqual(fresh.snapshot()['reason'],'service_restarted')
        self.assertEqual(self.driver.commands,['start'])
    def test_complete_stops_and_does_not_restart(self):
        self.start(2);self.driver.status='complete';self.mode.tick(quota());self.mode.tick(quota())
        self.assertEqual(self.mode.snapshot()['phase'],'complete');self.assertEqual(self.driver.commands,['start'])
    def test_initial_existing_active_goal_is_attached_not_replaced(self):
        self.driver.status='active';self.start(1)
        self.assertEqual(self.driver.commands,['attach'])
    def test_no_quota_data_no_dispatch(self):
        self.mode.start(TID,'title',1);self.mode.tick(quota(available=False))
        self.assertEqual(self.driver.commands,[])
    def test_inflight_goal_timeout_requires_attention(self):
        self.driver.dispatch=lambda *a:None
        self.mode.start(TID,'title',1);self.mode.tick(quota());self.now=50;self.mode.tick(quota())
        self.assertFalse(self.mode.snapshot()['enabled']);self.assertEqual(self.mode.snapshot()['reason'],'resume_not_confirmed')
    def test_out_of_range_limit_rejected(self):
        for n in (-1,101,True,'1'):
            with self.assertRaises(ModeError):self.mode.start(TID,'title',n)

    def test_first_start_can_wait_for_quota_then_create_missing_goal(self):
        self.mode.start(TID,'title',1);self.mode.tick(quota(100))
        self.assertEqual(self.driver.commands,[])
        self.recover(200)
        self.assertEqual(self.driver.commands,['start'])
        self.assertEqual(self.mode.snapshot()['recoveries_done'],1)

    def test_clearing_goal_during_wait_stops_instead_of_recreating(self):
        self.start(1);self.exhaust(100);self.driver.status=None;self.recover(200)
        self.assertEqual(self.mode.snapshot()['reason'],'goal_cleared')
        self.assertEqual(self.driver.commands,['start'])

    def test_native_limit_before_rounded_official_percent_still_has_bounded_recovery(self):
        self.start(1);self.driver.status='usageLimited';self.mode.tick(quota(99))
        self.recover(200)
        self.assertEqual(self.mode.snapshot()['recoveries_done'],1)
        self.exhaust(200);self.recover(300)
        self.assertEqual(self.driver.commands,['start','resume'])

class InputTests(unittest.TestCase):
    def test_native_pause_still_interrupts_when_metadata_writer_refuses(self):
        desk=Mock();desk.mode.snapshot.return_value={'reason':'user_cancelled'}
        desk.metadata.pause_goal.side_effect=RuntimeError('active writer')
        desk.metadata.goal_state.side_effect=[{'exists':True,'status':'active'},{'exists':True,'status':'paused'}]
        record={'pane':'%1','session':'owned'}
        def terminal_call(r,*args):
            if args[0]=='capture-pane':return '\x1b[2m› Ask Codex to do anything\x1b[0m'
            if args[0]=='display-message':return '2|0'
            return ''
        desk.terminal.call.side_effect=terminal_call
        control=NativeGoalControl(desk)
        with patch.object(control,'record',return_value=record):control.pause(TID)
        calls=[c.args[1:] for c in desk.terminal.call.call_args_list]
        self.assertIn(('send-keys','-t','%1','Escape'),calls)
        self.assertIn(('send-keys','-t','%1','-l','/goal pause'),calls)
        desk.open_terminal.assert_not_called()

    def test_cancel_before_dispatch_never_opens_terminal(self):
        desk=Mock();cancel=threading.Event();cancel.set()
        NativeGoalControl(desk).dispatch(TID,'resume',cancel)
        desk.open_terminal.assert_not_called();desk.terminal.call.assert_not_called()

    def test_empty_and_dim_placeholder_only(self):
        self.assertTrue(blank_input('› ',2))
        self.assertTrue(blank_input('\x1b[0;2m› Ask Codex to do anything\x1b[0m',2))
        self.assertFalse(blank_input('› user draft',12))
        self.assertFalse(blank_input('› user draft',2))
        self.assertFalse(blank_input('\x1b[38;2;120;2;2m› user draft\x1b[0m',2))
        self.assertFalse(blank_input('› 1. Resume goal',0))
        self.assertFalse(blank_input('PS workspace> ',2))
    def test_awake_flag_is_released(self):
        awake=Awake()
        with patch('continuous_mode.ctypes.windll.kernel32.SetThreadExecutionState',return_value=1) as call:
            awake.set(True);awake.set(True);awake.set(False)
            self.assertEqual([c.args[0] for c in call.call_args_list],[0x80000001,0x80000000])

if __name__=='__main__':unittest.main()
