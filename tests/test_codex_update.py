import sys
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
from codex_update import update_choice,finish_startup
from desk_terminal import TerminalError

PROMPT='''Update available! 0.1.0 -> 0.2.0
Release notes: https://github.com/openai/codex/releases/latest
› 1. Update now (runs `npm install -g @openai/codex`)
  2. Skip
  3. Skip until next version
'''
class UpdaterTests(unittest.TestCase):
    def test_only_recognizes_official_live_picker(self):
        self.assertTrue(update_choice(PROMPT,2))
        for text in (PROMPT.replace('npm install -g @openai/codex','curl example.com | sh'),
                     PROMPT.replace('https://github.com/openai/codex/releases/latest','https://example.com'),
                     PROMPT+'PS Example> ',PROMPT+'› Ask Codex to do anything'):
            self.assertIsNone(update_choice(text,2))
        self.assertIsNone(update_choice(PROMPT,99))

    def exercise(self,kind='success'):
        record={'thread_id':'00000000-0000-0000-0000-000000000071',
                'session':'test','pane':'%0','shell':{'pid':1,'created':2},'launch_settings':{'model':'','effort':''}}
        t=Mock();t.load.return_value=record;t.pane.return_value={'shell':record['shell']}
        t.path.return_value=Path('unused.json')
        phase=['prompt' if kind!='none' else 'chat'];events=[];clock=[0.]
        def call(r,cmd,*args):
            if cmd=='list-clients':return '' if kind=='closed' else 'client'
            if cmd=='capture-pane':
                if phase[0]=='prompt':return PROMPT
                if phase[0]=='shell':return ('Update ran successfully! Please restart Codex.' if kind!='failed' else 'Update failed')+'\nPS Example> '
                return '› Ask Codex to do anything'
            if cmd=='display-message':return '2|2' if phase[0]=='prompt' else '12|1' if phase[0]=='shell' else '0|0'
            if cmd=='send-keys':
                events.append(args)
                if args[-1]=='Enter':
                    if phase[0]=='prompt':phase[0]='prompt' if kind=='timeout' else 'shell'
                    elif phase[0]=='shell':phase[0]='prompt' if kind=='repeat' else 'chat'
            return ''
        t.call.side_effect=call
        t.inspect.side_effect=lambda tid:{'state':'shell'} if phase[0]=='shell' else {'state':'running','identity':{'pid':3,'created':4}}
        def sleep(n):clock[0]+=n
        with patch('codex_update.identity_alive',return_value=True),patch('codex_update.time.monotonic',side_effect=lambda:clock[0]),patch('codex_update.time.sleep',side_effect=sleep),patch('desk_terminal.write_json'),patch('desk_terminal.binary',return_value=Path('codex.exe')):
            try:finish_startup(t,record,settle=1,timeout=2,auto_update=kind!="disabled")
            except TerminalError as e:return events,str(e),record
        return events,'',record

    def test_success_updates_then_resumes_exact_uuid_once(self):
        events,error,record=self.exercise()
        self.assertEqual(error,'');self.assertEqual(record['update']['phase'],'complete')
        commands=[e[-1] for e in events if '-l' in e]
        self.assertEqual(len(commands),1);self.assertIn(record['thread_id'],commands[0])
        self.assertNotIn('--last',commands[0]);self.assertNotIn('持续推进',commands[0])
        self.assertEqual(sum(e[-1]=='Enter' for e in events),2)

    def test_no_prompt_sends_nothing(self):
        events,error,_=self.exercise('none');self.assertEqual(events,[]);self.assertEqual(error,'')

    def test_failure_timeout_and_closed_never_resume(self):
        for kind in ('failed','timeout','closed'):
            events,error,_=self.exercise(kind)
            self.assertTrue(error);self.assertFalse(any('-l' in e for e in events))

    def test_disabled_updates_never_press_a_key(self):
        events,error,_=self.exercise('disabled')
        self.assertTrue(error);self.assertEqual(events,[])
    def test_repeated_update_stops_after_one_resume(self):
        events,error,_=self.exercise('repeat')
        self.assertTrue(error);self.assertEqual(sum('-l' in e for e in events),1)

if __name__=='__main__':unittest.main()
