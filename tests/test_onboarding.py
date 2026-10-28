import json
import threading
import time
import unittest
import uuid
from types import SimpleNamespace
import network
from unittest.mock import Mock,patch
from app_config import network_environment
from quota_desk import Metadata
from desk_settings import SettingsError
from setup_actions import SetupActions

TID=str(uuid.UUID(int=2))

def rpc_for(block=None):
    rpc=Mock();rpc.alive=True
    def call(method,*args,**kwargs):
        if method=='account/read':return {'account':{'type':'chatgpt','email':'sample@example.invalid'}}
        if method=='thread/list':return {'data':[{'id':TID,'name':'Example conversation','cwd':'','updatedAt':1}]}
        if method=='model/list':return {'data':[]}
        if method=='account/rateLimits/read':
            if block:block()
            raise RuntimeError('Synthetic network failure')
        return {}
    rpc.call.side_effect=call
    return rpc

class MetadataTests(unittest.TestCase):
    def test_local_conversations_survive_quota_failure(self):
        rpc=rpc_for();metadata=Metadata(rpc_factory=lambda *a,**k:rpc)
        metadata.refresh();state=metadata.snapshot()
        self.assertEqual(len(state['threads']),1)
        self.assertEqual(state['error_code'],'quota_network')
        self.assertEqual(state['account_kind'],'chatgpt')
        self.assertNotIn('sample@example.invalid',json.dumps(state))
    def test_slow_network_does_not_block_title_snapshot(self):
        entered=threading.Event();release=threading.Event()
        def block():entered.set();release.wait(4)
        metadata=Metadata(rpc_factory=lambda *a,**k:rpc_for(block))
        worker=threading.Thread(target=metadata.refresh);worker.start()
        try:
            self.assertTrue(entered.wait(2))
            start=time.monotonic();state=metadata.snapshot()
            self.assertLess(time.monotonic()-start,.3)
            self.assertEqual(len(state['threads']),1)
        finally:release.set();worker.join(3)
    def test_official_login_starts_only_on_explicit_method(self):
        rpc=Mock();rpc.alive=True;rpc.call.return_value={'authUrl':'https://auth.openai.com/authorize?state=example'}
        metadata=Metadata(rpc_factory=lambda *a,**k:rpc)
        with patch('quota_desk.os.startfile') as browser:
            browser.assert_not_called();metadata.begin_login();browser.assert_called_once()
        self.assertTrue(metadata.login_pending)
    def test_login_url_must_be_official_https(self):
        rpc=Mock();rpc.alive=True;rpc.call.return_value={'authUrl':'https://example.invalid/authorize'}
        metadata=Metadata(rpc_factory=lambda *a,**k:rpc)
        with patch('quota_desk.os.startfile') as browser:
            with self.assertRaises(SettingsError):metadata.begin_login()
            browser.assert_not_called()

class NetworkTests(unittest.TestCase):
    def test_direct_connection_needs_no_proxy(self):
        with patch.dict('os.environ',{},clear=True),patch('app_config.urllib.request.getproxies',return_value={}),patch('network.local_proxy',return_value=''):
            env=network_environment()
            self.assertNotIn('HTTP_PROXY',env);self.assertNotIn('HTTPS_PROXY',env)
    def test_proxy_port_is_discovered_from_a_running_client_not_a_default(self):
        import network
        proc=Mock();proc.info={'name':'example-geph-client.exe'}
        proc.net_connections.return_value=[SimpleNamespace(status='LISTEN',laddr=('127.0.0.1',12345))]
        stream=Mock();stream.recv.return_value=b'HTTP/1.1 200 OK\r\n\r\n'
        connection=Mock();connection.__enter__=Mock(return_value=stream);connection.__exit__=Mock(return_value=False)
        tls=Mock();tls.wrap_socket.return_value.__enter__=Mock();tls.wrap_socket.return_value.__exit__=Mock()
        with patch.object(network,'_checked',0),patch.object(network,'_cached',''),patch.object(network.psutil,'process_iter',return_value=[proc]),patch.object(network.socket,'create_connection',return_value=connection),patch.object(network.ssl,'create_default_context',return_value=tls):
            self.assertEqual(network.local_proxy(),'http://127.0.0.1:12345')
            tls.wrap_socket.assert_called_once_with(stream,server_hostname='auth.openai.com')
    def test_static_system_proxy_is_adopted_without_a_private_default(self):
        with patch.dict('os.environ',{},clear=True),patch('app_config.urllib.request.getproxies',return_value={'http':'http://localhost:12345'}):
            self.assertEqual(network_environment()['HTTP_PROXY'],'http://localhost:12345')
    def test_explicit_proxy_replaces_case_variants(self):
        with patch.dict('os.environ',{'http_proxy':'http://obsolete.invalid'},clear=True):
            env=network_environment('http://localhost:12345')
            self.assertNotIn('http_proxy',env)
            self.assertEqual(env['HTTPS_PROXY'],'http://localhost:12345')

class SetupTests(unittest.TestCase):
    def test_snapshot_never_installs_logs_in_or_repairs(self):
        desk=Mock();desk.settings.snapshot.return_value={'effective':{'proxy_url':''}};setup=SetupActions(desk)
        with patch('startup.enabled',return_value=False),patch('setup_actions.process_integrity',return_value=0x3000),patch('setup_actions.file_integrity',return_value=0x3000),patch('setup_actions.subprocess.run') as execute:
            setup.snapshot();execute.assert_not_called()
        desk.metadata.begin_login.assert_not_called();desk.open_terminal.assert_not_called()
    def test_startup_switch_requires_boolean_and_explicit_action(self):
        setup=SetupActions(Mock())
        with patch('startup.register') as register:
            with self.assertRaises(SettingsError):setup.perform({'action':'startup','enabled':'true'})
            register.assert_not_called()
            setup.perform({'action':'startup','enabled':True});register.assert_called_once_with(True)
    def test_install_and_repair_require_confirmation(self):
        setup=SetupActions(Mock())
        for action in ('install','repair'):
            with self.assertRaises(SettingsError):setup.perform({'action':action,'kind':'codex'})
    def test_installer_is_allowlisted_and_never_runs_an_arbitrary_command(self):
        setup=SetupActions(Mock())
        with patch('setup_actions.subprocess.run',return_value=Mock(returncode=0)) as run:
            setup._install('winget.exe','codex')
            command=run.call_args.args[0]
            self.assertIn('OpenAI.Codex',command)
            self.assertIn('--exact',command)
            self.assertIn('winget',command)
        setup.desk.open_terminal.assert_not_called()

if __name__=='__main__':unittest.main()
