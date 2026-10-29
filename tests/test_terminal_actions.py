"""Process roles, exact external targets and confirmed-background batch boundaries."""
from pathlib import Path
import threading
import time
import unittest
import uuid
from unittest.mock import Mock,patch
from app_config import DATA
from desk_terminal import TerminalDesk,TerminalError,write_json
from quota_desk import Desk
from terminal_hosts import classify

TID=str(uuid.UUID(int=71))

class ProcessRoleTests(unittest.TestCase):
    def test_internal_services_are_not_chat_terminals(self):
        for command in ('app-server','mcp-server','exec-server','--app-server','--exec-server=pipe'):
            self.assertEqual(classify(['codex.exe',command],['Code.exe']),'service')
        self.assertEqual(classify(['codex.exe','--something'],['ChatGPT.exe']),'service')

    def test_psmux_and_direct_vscode_terminals_are_different_hosts(self):
        self.assertEqual(classify(['codex.exe','resume','--last'],['powershell.exe','psmux.exe','Code.exe']),'psmux')
        self.assertEqual(classify(['codex.exe','resume','--last'],['powershell.exe','Code.exe']),'vscode')
        self.assertEqual(classify(['codex.exe'],['pwsh.exe']),'console')

class TargetTests(unittest.TestCase):
    def setUp(self):
        self.root=DATA/'tests'/uuid.uuid4().hex
        self.process={'pid':1234,'created':17,'thread_ids':[TID],'host_kind':'vscode'}
        self.terminal=TerminalDesk(self.root,process_scan=lambda:[dict(self.process)])

    def test_unrelated_unidentified_process_does_not_lock_other_chats(self):
        state=self.terminal.inspect(str(uuid.UUID(int=72)),[{'pid':999,'unidentified':True,'thread_ids':[]}])
        self.assertEqual(state['state'],'closed')

    def test_external_target_has_exact_identity_and_end_token(self):
        state=self.terminal.inspect(TID)
        self.assertEqual(state['state'],'external');self.assertTrue(state['can_close'])
        self.assertEqual(state['identity'],{'pid':1234,'created':17})
        self.assertEqual(state['close_token'],self.terminal.process_token(self.process))

    def test_unknown_identity_keeps_view_available_but_does_not_silently_duplicate(self):
        other=str(uuid.UUID(int=72));self.terminal.scan=lambda:[{'pid':999,'unidentified':True,'thread_ids':[]}]
        with patch('desk_terminal.binary',return_value=Path(__file__)),patch.object(self.terminal,'_new') as new:
            result=self.terminal.open({'id':other,'name':'Example','cwd':str(self.root)},'')
        self.assertEqual(result['action'],'confirm_new');self.assertEqual(result['unidentified_pids'],[999]);new.assert_not_called()

    def test_view_running_external_chat_focuses_host_without_starting_codex(self):
        with patch('desk_terminal.binary',return_value=Path(__file__)),patch('desk_terminal.identity_alive',return_value=True),patch('terminal_hosts.focus') as focus,patch.object(self.terminal,'_new') as new:
            result=self.terminal.open({'id':TID,'name':'Example','cwd':str(self.root)},'')
        self.assertEqual(result['action'],'focused');focus.assert_called_once();new.assert_not_called()

    def test_stale_process_token_cannot_focus_or_end_reused_pid(self):
        expected=self.terminal.process_token(self.process);self.process['created']=18
        with patch('desk_terminal.identity_alive',return_value=True),patch('terminal_hosts.focus') as focus,patch('desk_terminal.psutil.Process') as process:
            with self.assertRaises(TerminalError):self.terminal.view_process(1234,expected)
            with self.assertRaises(TerminalError):self.terminal.close_process(1234,expected)
        focus.assert_not_called();process.assert_not_called()

    def test_external_end_only_terminates_selected_codex_process(self):
        expected=self.terminal.process_token(self.process)
        with patch('desk_terminal.identity_alive',return_value=True),patch('desk_terminal.psutil.Process') as process:
            result=self.terminal.close_process(1234,expected)
        process.assert_called_once_with(1234);process.return_value.terminate.assert_called_once()
        self.assertEqual(result['pid'],1234)

    def test_internal_service_is_rejected_even_if_passed_to_target_scan(self):
        self.process['host_kind']='service';expected=self.terminal.process_token(self.process)
        with patch('desk_terminal.identity_alive',return_value=True),patch('desk_terminal.psutil.Process') as process:
            with self.assertRaises(TerminalError):self.terminal.close_process(1234,expected)
        process.assert_not_called()

    def test_background_end_rechecks_frontend_before_terminating(self):
        directory=self.root/'sessions'/TID;directory.mkdir(parents=True)
        record={'thread_id':TID,'directory':str(directory),'workspace':str(directory/'Terminal.code-workspace'),
                'session':'reset_actions_test','pane':'%0','shell':{'pid':111,'created':1}}
        write_json(self.terminal.path(TID),record)
        state={'state':'shell'};token=self.terminal.close_token(record,state)
        with patch.object(self.terminal,'inspect',return_value=state),patch.object(self.terminal,'call',return_value='connected client') as call:
            with self.assertRaises(TerminalError):self.terminal.close(TID,token,require_background=True)
        self.assertEqual(call.call_args.args[1],'list-clients')

class BatchTests(unittest.TestCase):
    def make_desk(self):
        desk=Desk.__new__(Desk);desk.background_plan=None
        items=[{'thread_id':TID,'name':'Background example','pid':11,'can_close':True,'connection':'background','target_type':'managed','close_token':'one'},
               {'thread_id':'other','name':'Visible example','pid':12,'can_close':True,'connection':'attached','target_type':'managed'},
               {'thread_id':None,'name':'Unidentified external','pid':13,'can_close':True,'connection':'unknown','target_type':'process'}]
        desk.check_terminals=Mock(return_value={'items':items});desk.close_terminal=Mock()
        return desk

    def test_prepare_contains_only_confirmed_background_managed_targets(self):
        desk=self.make_desk();plan=desk.prepare_background_close()
        self.assertEqual([x['pid'] for x in plan['items']],[11]);desk.close_terminal.assert_not_called()

    def test_no_batch_action_without_matching_explicit_confirmation(self):
        desk=self.make_desk();plan=desk.prepare_background_close()
        for plan_id,confirmed in [(plan['plan_id'],False),('different',True)]:
            with self.assertRaises(TerminalError):desk.close_background(plan_id,confirmed)
        desk.close_terminal.assert_not_called()

    def test_batch_rechecks_background_and_is_not_replayed(self):
        desk=self.make_desk();plan=desk.prepare_background_close();result=desk.close_background(plan['plan_id'],True)
        desk.close_terminal.assert_called_once_with(TID,'one',True,background=True)
        self.assertEqual(len(result['closed']),1)
        with self.assertRaises(TerminalError):desk.close_background(plan['plan_id'],True)

    def test_reconnected_target_is_skipped(self):
        desk=self.make_desk();plan=desk.prepare_background_close()
        desk.close_terminal.side_effect=TerminalError('Target reconnected')
        result=desk.close_background(plan['plan_id'],True)
        self.assertEqual(result['closed'],[]);self.assertEqual(len(result['skipped']),1)

    def test_expired_plan_needs_another_review(self):
        desk=self.make_desk();plan=desk.prepare_background_close();desk.background_plan['at']=time.time()-91
        with self.assertRaises(TerminalError):desk.close_background(plan['plan_id'],True)
        desk.close_terminal.assert_not_called()

    def test_pid_is_paired_with_official_conversation_title(self):
        desk=Desk.__new__(Desk);desk.metadata=Mock();desk.metadata.snapshot.return_value={'threads':[]}
        desk.metadata.read_title.return_value={'name':'Identified example title'}
        desk.terminal=Mock();desk.terminal.inventory.return_value=[{'thread_id':TID,'name':'…'+TID[-8:],'pid':1234}]
        row=desk.check_terminals()['items'][0]
        self.assertEqual(row['name'],'Identified example title');self.assertEqual(row['pid'],1234)

if __name__=='__main__':unittest.main()
