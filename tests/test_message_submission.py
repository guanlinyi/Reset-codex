from pathlib import Path
import sys,unittest,threading
from types import SimpleNamespace
from unittest.mock import Mock,patch
from message_control import MessageControl,CONTINUE_MESSAGE
from desk_terminal import TerminalError

class SubmissionTests(unittest.TestCase):
    def exercise(self,absorbed=False,stuck=False,text=CONTINUE_MESSAGE):
        keys=[];clock=[0.];enters=[0];terminal=Mock()
        def call(r,cmd,*args):
            if cmd=='send-keys':
                keys.append(args[2:])
                if args[-1]=='Enter':enters[0]+=1
            return ''
        terminal.call.side_effect=call
        c=MessageControl(SimpleNamespace(terminal=terminal));c._ready=Mock();c._screen=lambda r:'› '+text
        c._draft_matches=lambda r,t:bool(keys) and (stuck or (absorbed and enters[0]<2))
        with patch('message_control.time.monotonic',side_effect=lambda:clock[0]),patch('message_control.time.sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)):
            try:c._send({'pane':'%0'},text,threading.Event())
            except TerminalError as e:return keys,str(e)
        return keys,''
    def test_paste_then_enter_and_confirm(self):
        keys,error=self.exercise()
        self.assertEqual(error,'');self.assertEqual(keys,[('-l','\x1b[200~'+CONTINUE_MESSAGE+'\x1b[201~'),('Enter',)])
    def test_absorbed_enter_retries_enter_only(self):
        keys,error=self.exercise(absorbed=True)
        self.assertEqual(error,'');self.assertEqual(sum(k[0]=='-l' for k in keys),1);self.assertEqual(keys[-2:],[('Enter',),('Enter',)])
    def test_stuck_input_is_not_reported_sent(self):
        keys,error=self.exercise(stuck=True)
        self.assertTrue(error);self.assertEqual(sum(k[0]=='-l' for k in keys),1)
    def test_existing_exact_draft_is_submitted_without_pasting_again(self):
        terminal=Mock();entered=[False]
        terminal.call.side_effect=lambda r,cmd,*a:entered.__setitem__(0,True) if cmd=='send-keys' and a[-1]=='Enter' else ''
        c=MessageControl(SimpleNamespace(terminal=terminal));c._ready=Mock();c._draft_matches=lambda *a:not entered[0]
        with patch('message_control.time.sleep'):
            c._send({'pane':'%0'},CONTINUE_MESSAGE,threading.Event())
        c._ready.assert_not_called()
        sent=[call.args for call in terminal.call.call_args_list if call.args[1]=='send-keys']
        self.assertEqual(len(sent),1);self.assertEqual(sent[0][-1],'Enter')
    def test_custom_multiline_message_is_preserved(self):
        text='Custom task\nFinish work and save handoff.'
        keys,error=self.exercise(text=text)
        self.assertEqual(error,'');self.assertEqual(keys[0],('-l','\x1b[200~'+text+'\x1b[201~'))

if __name__=='__main__':unittest.main()
