import json
from pathlib import Path
import unittest
import uuid
from unittest.mock import Mock,patch
import app_config
from audit_public import audit
from desk_settings import SettingsStore,resolved,SettingsError
from desk_terminal import TerminalDesk,TerminalError
import startup

class ConfigTests(unittest.TestCase):
    def test_no_private_public_defaults(self):
        for key in ('codex_path','vscode_path','browser_path','psmux_path','workspace','proxy_host','proxy_port','thread_id'):
            self.assertEqual(app_config.DEFAULTS[key],'')
        self.assertEqual(resolved({})['proxy_url'],'')
    def test_proxy_needs_both_fields(self):
        for settings in ({'proxy_host':'localhost'},{'proxy_port':'12345'}):
            with self.assertRaises(SettingsError):resolved(settings)
        self.assertEqual(resolved({'proxy_host':'localhost','proxy_port':'12345'})['proxy_url'],'http://localhost:12345')
    def test_ui_saves_only_local_overrides(self):
        folder=app_config.DATA/'tests'/uuid.uuid4().hex;folder.mkdir(parents=True)
        with patch.object(app_config,'ROOT',folder),patch.object(app_config,'DATA',folder):
            app_config.save_local({'workspace':'example'})
            self.assertTrue((folder/'config.local.json').is_file())
            self.assertFalse((folder/'config.json').exists())
    def test_frozen_terminal_uses_console_helper(self):
        with patch.object(app_config,'FROZEN',True):
            self.assertEqual(Path(app_config.command('--attach','example')[0]).name,'ResetTerminal.exe')
            self.assertEqual(Path(app_config.command('--autostart')[0]).name,'Reset.exe')

class SafetyTests(unittest.TestCase):
    def test_low_executable_blocked_before_any_shell_or_codex(self):
        terminal=TerminalDesk(app_config.DATA/'tests'/uuid.uuid4().hex,process_scan=lambda:[])
        with patch('desk_terminal.file_integrity',return_value=0x1000),patch.object(terminal,'call') as call:
            with self.assertRaises(TerminalError):terminal._new({'id':str(uuid.UUID(int=1)),'cwd':str(app_config.ROOT)})
            call.assert_not_called()
    def test_startup_only_opens_apps(self):
        with patch.object(startup,'open_editor') as editor,patch('quota_desk.main') as desktop,patch('quota_desk.Desk.open_terminal') as native:
            startup.launch()
            editor.assert_called_once();desktop.assert_called_once_with(['--open']);native.assert_not_called()
    def test_ui_workspace_has_no_autorun_task(self):
        directory=app_config.DATA/'tests'/uuid.uuid4().hex
        with patch.object(startup,'DATA',directory),patch.object(startup,'binary',return_value=Path('code.exe')),patch.object(startup.subprocess,'Popen'):
            startup.open_editor()
        doc=json.loads((directory/'startup.code-workspace').read_text(encoding='utf-8'))
        self.assertNotIn('tasks',doc)
        self.assertNotIn('resume',json.dumps(doc))
    def test_local_service_rejects_cross_origin(self):
        from quota_desk import Handler
        request=Mock();request.headers={'Host':'127.0.0.1:12345','X-Reset-Desk':'nonce','Origin':'https://example.invalid'}
        request.server.server_port=12345;request.server.token='nonce'
        request.valid_host=lambda:Handler.valid_host(request)
        self.assertFalse(Handler.authorized(request))
    def test_public_tree_audit(self):self.assertEqual(audit(),[])

if __name__=='__main__':unittest.main()
