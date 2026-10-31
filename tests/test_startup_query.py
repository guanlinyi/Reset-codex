"""Windows task XML encoding must never block quota/conversation state."""
import subprocess
import unittest
from unittest.mock import Mock,patch
from xml.sax.saxutils import escape

import startup


class StartupQueryTests(unittest.TestCase):
    def query(self, raw):
        with patch.object(startup.subprocess, 'run', return_value=Mock(returncode=0, stdout=raw)):
            return startup.enabled()

    def task_xml(self, enabled='true'):
        args=startup.command('--autostart')
        return ('<?xml version="1.0" encoding="UTF-16"?>'
                '<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
                '<Settings><Enabled>'+enabled+'</Enabled></Settings><Actions><Exec>'
                '<Command>'+escape(args[0])+'</Command><Arguments>'+
                escape(subprocess.list2cmdline(args[1:]))+'</Arguments></Exec></Actions></Task>')

    def test_utf8_bytes_with_utf16_declaration(self):
        self.assertIs(self.query(self.task_xml().encode('utf-8')),True)

    def test_real_utf16_bytes(self):
        self.assertIs(self.query(self.task_xml().encode('utf-16')),True)

    def test_disabled_task(self):
        self.assertIs(self.query(self.task_xml('false').encode('utf-8')),False)

    def test_malformed_task_returns_unknown(self):
        self.assertIsNone(self.query(b'<?xml version="1.0"?><Task>'))

    def test_other_app_is_not_enabled_for_this_copy(self):
        args=['another.exe','--autostart']
        with patch.object(startup,'command',return_value=args):
            raw=self.task_xml().encode('utf-8')
        self.assertIs(self.query(raw),False)


if __name__=='__main__':unittest.main()
