"""Detached sessions, viewer recreation, exact close targets and mode cancellation."""
import json
from pathlib import Path
import threading
import unittest
import uuid
from unittest.mock import Mock, patch
from app_config import DATA
from desk_terminal import TerminalDesk, TerminalError, write_json
from quota_desk import Desk
from continuous_mode import ContinuousMode
from psmux_attach import arm_disconnect_policy

TID=str(uuid.UUID(int=15))

class TerminalManagerTests(unittest.TestCase):
    def setUp(self):
        self.root=DATA/'tests'/uuid.uuid4().hex
        self.terminal=TerminalDesk(self.root,process_scan=lambda:[])
        directory=self.root/'sessions'/TID/'attempt_test';directory.mkdir(parents=True)
        self.record={'thread_id':TID,'directory':str(directory),'session':'reset_test_15',
                     'workspace':str(directory/'Terminal.code-workspace'),'pane':'%0',
                     'shell':{'pid':111,'created':100,'name':'powershell.exe'},
                     'title':'Background example','cwd':str(self.root)}
        write_json(self.terminal.path(TID),self.record)
        self.state={'state':'running','identity':{'pid':222,'created':101}}

    def test_each_explicit_viewer_has_new_workspace_and_same_session(self):
        with patch('desk_terminal.subprocess.Popen') as launch:
            one=self.terminal.viewer(self.record,{'name':'Example','cwd':str(self.root)})
            two=self.terminal.viewer(self.record,{'name':'Example','cwd':str(self.root)})
        self.assertNotEqual(one,two)
        for call in launch.call_args_list:
            args=call.args[0];self.assertIn('new-tab',args)
            self.assertEqual(args[args.index('--colorScheme')+1],'Campbell')
            self.assertIn('--suppressApplicationTitle',args)
            self.assertEqual(args[-1],TID)
            self.assertEqual(call.kwargs['env']['RESET_DATA_DIR'],str(self.root))
            self.assertIn('RESET_VIEWER_ID',call.kwargs['env'])
            self.assertNotIn('resume',args)

    def test_running_open_only_reconnects_without_sending_commands(self):
        thread={'id':TID,'name':'Example','cwd':str(self.root)}
        with patch('desk_terminal.binary',return_value=Path(__file__)),patch.object(self.terminal,'inspect',return_value=self.state),patch.object(self.terminal,'viewer',return_value='a'*32),patch.object(self.terminal,'viewer_connected',return_value=True),patch.object(self.terminal,'call',return_value='') as call,patch.object(self.terminal,'_new') as new,patch.object(self.terminal,'finish_startup') as finish:
            result=self.terminal.open(thread,'')
        self.assertEqual(result['action'],'reused');new.assert_not_called();finish.assert_called_once()
        self.assertEqual(call.call_args.args[1],'list-clients')

    def test_attached_session_never_creates_another_viewer_or_codex(self):
        thread={'id':TID,'name':'Example','cwd':str(self.root)}
        with patch('desk_terminal.binary',return_value=Path(__file__)),patch.object(self.terminal,'inspect',return_value=self.state),patch.object(self.terminal,'call',return_value='existing client'),patch.object(self.terminal,'viewer') as viewer,patch.object(self.terminal,'_new') as new:
            with self.assertRaisesRegex(TerminalError,'无法准确定位'):
                self.terminal.open(thread,'')
        viewer.assert_not_called();new.assert_not_called()

    def test_stale_client_does_not_confirm_new_viewer(self):
        write_json(self.root/'viewers'/TID/('a'*32+'.json'),{'viewer_id':'a'*32,'client':{'pid':1,'created':1}})
        with patch('desk_terminal.identity_alive',return_value=True),patch.object(self.terminal,'call',return_value='test client'):
            self.assertFalse(self.terminal.viewer_connected(TID,'b'*32))
            self.assertTrue(self.terminal.viewer_connected(TID,'a'*32))

    def test_inventory_includes_background_not_in_recent_conversations(self):
        with patch('desk_terminal.identity_alive',return_value=True),patch.object(self.terminal,'inspect',return_value=self.state),patch.object(self.terminal,'call',return_value=''):
            rows=self.terminal.inventory([])
        self.assertEqual(len(rows),1);row=rows[0]
        self.assertEqual(row['name'],'Background example');self.assertEqual(row['connection'],'background')
        self.assertTrue(row['can_open']);self.assertTrue(row['can_close'])
        self.assertNotIn('directory',row)

    def test_dead_registry_is_not_reported_as_a_running_terminal(self):
        with patch('desk_terminal.identity_alive',return_value=False):
            rows=self.terminal.inventory([], [{'pid':444,'thread_ids':[],'unidentified':True}])
        self.assertEqual(rows,[])

    def test_external_and_unknown_processes_are_read_only(self):
        other=str(uuid.UUID(int=16))
        processes=[{'pid':333,'thread_ids':[other]},{'pid':444,'thread_ids':[],'unidentified':True}]
        with patch.object(self.terminal,'inspect',return_value={'state':'external'}):
            rows=self.terminal.inventory([],processes)
        self.assertEqual(rows,[])

    def test_stale_close_token_cannot_kill_replacement_process(self):
        expected=self.terminal.close_token(self.record,self.state)
        changed={'state':'running','identity':{'pid':223,'created':102}}
        with patch.object(self.terminal,'inspect',return_value=changed),patch.object(self.terminal,'call') as call:
            with self.assertRaises(TerminalError):self.terminal.close(TID,expected)
        call.assert_not_called()

    def test_close_only_ends_exact_session_and_keeps_record(self):
        expected=self.terminal.close_token(self.record,self.state)
        with patch.object(self.terminal,'inspect',return_value=self.state),patch('desk_terminal.identity_alive',return_value=False),patch.object(self.terminal,'call') as call:
            self.terminal.close(TID,expected)
        self.assertEqual(call.call_args.args[1:],('kill-session','-t','reset_test_15'))
        self.assertEqual(call.call_args.args[0]['session'],self.record['session'])
        self.assertIn('closed_at',json.loads(self.terminal.path(TID).read_text(encoding='utf-8')))

    def test_outside_same_session_does_not_prevent_ending_our_empty_shell(self):
        outside={'pid':999,'created':120,'thread_ids':[TID]}
        with patch('desk_terminal.identity_alive',return_value=True),patch.object(self.terminal,'pane',return_value={'shell':self.record['shell']}),patch('desk_terminal.psutil.Process') as process:
            process.return_value.children.return_value=[]
            state=self.terminal.inspect(TID,[outside])
        self.assertEqual(state['state'],'conflict');self.assertTrue(state['can_close'])
        self.assertEqual(state['pid'],111);self.assertEqual(state['outside_pids'],[999])
        with patch.object(self.terminal,'inspect',return_value=state),patch('desk_terminal.identity_alive',return_value=False),patch.object(self.terminal,'call') as call:
            self.terminal.close(TID,state['close_token'])
        self.assertEqual(call.call_count,1)
        self.assertEqual(call.call_args.args[1:],('kill-session','-t','reset_test_15'))
        self.assertEqual(call.call_args.args[0]['shell']['pid'],111)

    def make_desk(self):
        desk=Desk.__new__(Desk);desk.terminal=Mock();desk.terminal.lock=threading.RLock()
        desk.terminal.close.return_value={'action':'closed','thread_id':TID}
        desk.action_lock=threading.Lock();desk.last_action=None
        driver=Mock();desk.mode=ContinuousMode(driver,self.root/'mode.json')
        desk.mode.start(TID,'Example',1)
        return desk

    def test_close_requires_explicit_confirmation(self):
        desk=self.make_desk()
        with self.assertRaises(TerminalError):desk.close_terminal(TID,'test')
        desk.terminal.close.assert_not_called();self.assertTrue(desk.mode.snapshot()['enabled'])

    def test_end_stops_continuation_before_exact_terminal_close(self):
        desk=self.make_desk();order=[]
        def close(*args):
            self.assertFalse(desk.mode.snapshot()['enabled']);self.assertTrue(desk.mode.cancel_event.is_set())
            order.append(args);return {'action':'closed','thread_id':TID}
        desk.terminal.close.side_effect=close
        desk.close_terminal(TID,'fingerprint',True)
        self.assertEqual(order,[(TID,'fingerprint')]);self.assertEqual(desk.mode.snapshot()['reason'],'terminal_closed')
        self.assertFalse(desk.mode.pending_pause)

    def test_ending_another_chat_does_not_cancel_active_chat(self):
        desk=self.make_desk()
        desk.close_terminal(str(uuid.UUID(int=16)),'fingerprint',True)
        self.assertTrue(desk.mode.snapshot()['enabled']);self.assertFalse(desk.mode.cancel_event.is_set())

    def test_close_during_open_does_not_leave_enabled_cancelled_mode(self):
        desk=self.make_desk();desk.action_lock.acquire()
        try:
            with self.assertRaises(TerminalError):desk.close_terminal(TID,'fingerprint',True)
        finally:desk.action_lock.release()
        self.assertFalse(desk.mode.snapshot()['enabled']);desk.terminal.close.assert_not_called()

    def test_disconnect_policy_is_armed_and_verified_in_exact_namespace(self):
        service=Mock();service.call.side_effect=['','on\n']
        self.assertTrue(arm_disconnect_policy(service,self.record))
        self.assertEqual(service.call.call_args_list[0].args[1:],('set-option','-g','-t','reset_test_15','destroy-unattached','on'))

    def test_unverified_disconnect_policy_is_not_accepted(self):
        service=Mock();service.call.side_effect=['','off\n']
        with self.assertRaises(RuntimeError):arm_disconnect_policy(service,self.record)

    def test_closed_backend_stops_current_recovery_controller(self):
        desk=self.make_desk();desk.mode.state['native_dispatched']=True
        desk.terminal.load.return_value={**self.record,'close_on_disconnect':True,'display_armed':True}
        with patch('quota_desk.identity_alive',return_value=False):desk.reap_closed_terminal()
        self.assertFalse(desk.mode.snapshot()['enabled']);self.assertTrue(desk.mode.cancel_event.is_set())
        self.assertEqual(desk.mode.snapshot()['reason'],'terminal_closed')

    def test_live_backend_is_not_ended_when_window_is_minimized(self):
        desk=self.make_desk();desk.mode.state['native_dispatched']=True
        desk.terminal.load.return_value={**self.record,'close_on_disconnect':True,'display_armed':True}
        with patch('quota_desk.identity_alive',return_value=True):desk.reap_closed_terminal()
        self.assertTrue(desk.mode.snapshot()['enabled']);desk.terminal.close.assert_not_called()

    def test_new_explicit_start_is_not_cancelled_due_to_old_closed_backend(self):
        desk=self.make_desk()
        desk.terminal.load.return_value={**self.record,'close_on_disconnect':True,'display_armed':True}
        with patch('quota_desk.identity_alive',return_value=False):desk.reap_closed_terminal()
        self.assertTrue(desk.mode.snapshot()['enabled'])

if __name__=='__main__':unittest.main()
