"""File-handle identity inference without reading conversations or process memory."""
from pathlib import Path
import os
import unittest
from unittest.mock import Mock,patch
import desk_terminal as dt

class SessionIdentityTests(unittest.TestCase):
    def setUp(self):
        dt._file_identity_cache.clear()
        self.process=Mock(pid=123);self.process.create_time.return_value=42
        self.home=Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex').resolve()/'sessions'
        self.one='00000000-0000-0000-0000-000000000071'
        self.two='00000000-0000-0000-0000-000000000072'
    def log(self,tid):return str(self.home/'2026/10/30'/('rollout-2026-10-30T12-00-00-'+tid+'.jsonl'))
    def test_persistent_writer_can_hold_multiple_conversations(self):
        with patch('session_handles.writable_files',return_value=[self.log(self.one),self.log(self.two)]),patch('desk_terminal.time.sleep'):
            self.assertEqual(dt.open_session_ids(self.process),[self.one,self.two])
    def test_transient_history_open_is_not_an_identity(self):
        with patch('session_handles.writable_files',side_effect=[[self.log(self.one)],[]]),patch('desk_terminal.time.sleep'):
            self.assertEqual(dt.open_session_ids(self.process),[])
    def test_unrelated_writable_file_is_not_a_conversation(self):
        with patch('session_handles.writable_files',return_value=[str(self.home.parent/('other-'+self.one+'.jsonl'))]),patch('desk_terminal.time.sleep'):
            self.assertEqual(dt.open_session_ids(self.process),[])
    def test_permission_failure_leaves_identity_unknown(self):
        with patch('session_handles.writable_files',side_effect=OSError('denied')):
            self.assertEqual(dt.open_session_ids(self.process),[])
    def test_pid_reuse_does_not_reuse_old_identity(self):
        with patch('session_handles.writable_files',return_value=[self.log(self.one)]),patch('desk_terminal.time.sleep'):
            self.assertEqual(dt.open_session_ids(self.process),[self.one])
        self.process.create_time.return_value=99
        with patch('session_handles.writable_files',return_value=[]):
            self.assertEqual(dt.open_session_ids(self.process),[])
