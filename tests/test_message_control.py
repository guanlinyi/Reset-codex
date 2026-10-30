from pathlib import Path
import sys,threading,unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from message_control import MessageControl,CONTINUE_MESSAGE,resume_dialog
from desk_terminal import TerminalError

class PromptTests(unittest.TestCase):
    def test_overlay_dialog_dismisses_then_submits_exactly_once(self):
        modal=[True];second=[False];typed=[''];keys=[];clock=[0.]
        def screen():
            if modal[0]:return 'old output  Resume paused goal?\nGoal: example\nold text '+(' 1. Resume goal\nnoise › 2. Leave paused' if second[0] else '› 1. Resume goal\nnoise   2. Leave paused')
            return '› '+typed[0]
        def call(r,cmd,*args):
            if cmd=='capture-pane':return screen()
            if cmd=='display-message':return '2|0'
            if cmd=='send-keys':
                event=args[2:];keys.append(event)
                if event==('Down',):second[0]=True
                elif event==('Enter',) and modal[0]:
                    self.assertTrue(second[0]);modal[0]=False
                elif event[0]=='-l':typed[0]=event[1].removeprefix('\x1b[200~').removesuffix('\x1b[201~')
                elif event==('Enter',):typed[0]=''
            return ''
        terminal=Mock();terminal.call.side_effect=call
        c=MessageControl(SimpleNamespace(terminal=terminal));c._blank=lambda r:not modal[0] and not typed[0]
        with patch('message_control.time.monotonic',side_effect=lambda:clock[0]),patch('message_control.time.sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)):
            c._send({'pane':'%0'},CONTINUE_MESSAGE,threading.Event())
        self.assertEqual(keys,[('Home',),('Down',),('Enter',),('-l','\x1b[200~'+CONTINUE_MESSAGE+'\x1b[201~'),('Enter',)])

    def test_plain_user_input_is_never_overwritten(self):
        terminal=Mock();terminal.call.return_value='unfinished input';clock=[0.]
        c=MessageControl(SimpleNamespace(terminal=terminal));c._blank=lambda r:False
        with patch('message_control.time.monotonic',side_effect=lambda:clock[0]),patch('message_control.time.sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)):
            with self.assertRaises(TerminalError):c._ready({'pane':'%0'},threading.Event(),timeout=1)
        self.assertFalse(any(call.args[1]=='send-keys' for call in terminal.call.call_args_list))

    def test_dispatch_uses_custom_command_and_checkbox_values(self):
        desk=Mock();desk.mode.snapshot.return_value={'command':'Custom work','auto_goal':False,'auto_update':False}
        c=MessageControl(desk);c.record=Mock(return_value={'pane':'%0'});c._send=Mock()
        c.dispatch('thread','continue',threading.Event())
        self.assertFalse(c.auto_goal);self.assertFalse(c.auto_update)
        self.assertEqual(c._send.call_args.args[1],'Custom work')
        self.assertFalse(desk.open_terminal.call_args.kwargs['auto_update'])
    def test_unchecked_goal_option_never_presses_keys(self):
        terminal=Mock();terminal.call.return_value='old Resume paused goal?\nnoise > 1. Resume goal\n  2. Leave paused'
        c=MessageControl(SimpleNamespace(terminal=terminal),auto_goal=False);c._blank=lambda r:False
        with self.assertRaises(TerminalError):c._ready({'pane':'%0'},threading.Event())
        self.assertFalse(any(call.args[1]=='send-keys' for call in terminal.call.call_args_list))

if __name__=='__main__':unittest.main()
